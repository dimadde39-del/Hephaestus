"""Benchmark execution over the existing optimizer stack."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from hephaestus.benchmarks.loader import load_all_benchmarks
from hephaestus.benchmarks.schemas import (
    BenchmarkCase,
    BenchmarkResult,
    ContextBenchmarkSummary,
    ModelRouteSummary,
    RejectedModelSummary,
    SchedulerBenchmarkSummary,
)
from hephaestus.core.config import DEFAULT_CONFIG, RiskLevel
from hephaestus.models import fake_model_profiles
from hephaestus.optimize.context_packer import (
    ContextCandidate,
    ExcludedContext,
    pack_context,
)
from hephaestus.optimize.model_router import ModelRouteRequest, ModelRoutingError, route_model
from hephaestus.optimize.task_scheduler import SchedulerComparison, compare_schedulers
from hephaestus.optimize.token_firewall import BudgetDecision
from hephaestus.spec.tasks import Task
from hephaestus.storage import (
    ApprovalRecord,
    RunDecisionRecord,
    RunRecord,
    RunRepository,
    RunTaskRecord,
)


def run_all_benchmarks(
    *,
    directory: Path | str | None = None,
    repository: RunRepository | None = None,
    persist: bool = True,
) -> list[BenchmarkResult]:
    """Run every benchmark fixture in the benchmark directory."""

    cases = load_all_benchmarks(directory)
    return [run_benchmark(case, repository=repository, persist=persist) for case in cases]


def run_benchmark(
    case: BenchmarkCase,
    *,
    repository: RunRepository | None = None,
    persist: bool = True,
) -> BenchmarkResult:
    """Run one benchmark and optionally persist a benchmark-mode run."""

    run_repository = repository or (RunRepository() if persist else None)
    run = None
    if persist and run_repository is not None:
        run = run_repository.save_run(
            RunRecord(goal=f"Benchmark {case.id}: {case.goal or case.title}", mode="benchmark")
        )

    comparison = compare_schedulers(case.tasks, DEFAULT_CONFIG.objective_weights)
    scheduler = summarize_scheduler(comparison)
    best_order = comparison.best_order
    context_result = pack_context(case.context_candidates, case.context_token_budget)
    context = summarize_context(
        case.context_candidates,
        context_result.selected,
        context_result.excluded,
        case.context_token_budget,
    )
    approval_tasks = [task for task in best_order if task.requires_approval]
    model_routes = _route_tasks(case, best_order)
    total_input = sum(task.estimated_input_tokens for task in best_order)
    total_output = sum(task.estimated_output_tokens for task in best_order)
    total_cost = sum(route.estimated_cost for route in model_routes)
    quality_preserved = bool(model_routes) and all(route.quality_preserved for route in model_routes)
    budget = summarize_budget(
        input_tokens=total_input,
        output_tokens=total_output,
        estimated_cost=total_cost,
        quality_preserved=quality_preserved,
        case=case,
    )

    if persist and run_repository is not None and run is not None:
        _persist_benchmark_run(
            repository=run_repository,
            run_id=run.id,
            case=case,
            best_order=best_order,
            scheduler=scheduler,
            model_routes=model_routes,
            context=context,
            budget=budget,
            approval_tasks=approval_tasks,
        )

    summary = _summary_text(case, scheduler, context, budget, model_routes, approval_tasks)
    if persist and run_repository is not None and run is not None:
        run_repository.complete_run(
            run.id,
            estimated_input_tokens=total_input,
            estimated_output_tokens=total_output,
            estimated_cost=total_cost,
            objective_score=scheduler.best_score,
            risk_score=max((task.risk for task in best_order), default=0.0),
            summary=summary,
        )

    return BenchmarkResult(
        case=case,
        run_id=run.id if run is not None else None,
        scheduler=scheduler,
        model_routes=model_routes,
        context=context,
        budget=budget,
        approval_required_count=len(approval_tasks),
        estimated_input_tokens=total_input,
        estimated_output_tokens=total_output,
        estimated_cost=total_cost,
        quality_preserved=quality_preserved,
        summary=summary,
    )


def summarize_scheduler(comparison: SchedulerComparison) -> SchedulerBenchmarkSummary:
    """Convert a scheduler comparison into benchmark report metrics."""

    greedy = comparison.greedy
    annealed = comparison.annealed
    score_delta = calculate_score_delta(greedy.score, annealed.score)
    best_scheduler = "annealing" if annealed.score >= greedy.score else "greedy"
    best_order = comparison.best_order
    return SchedulerBenchmarkSummary(
        greedy_score=greedy.score,
        annealing_score=annealed.score,
        score_delta=score_delta,
        score_delta_percent=calculate_score_delta_percent(greedy.score, score_delta),
        greedy_dependency_violations=greedy.breakdown.dependency_violations,
        annealing_dependency_violations=annealed.breakdown.dependency_violations,
        best_scheduler=best_scheduler,
        best_score=comparison.best_score,
        greedy_order=[task.id for task in greedy.order],
        annealing_order=[task.id for task in annealed.order],
        best_order=[task.id for task in best_order],
    )


def calculate_score_delta(greedy_score: float, annealing_score: float) -> float:
    """Return annealing minus greedy score."""

    return annealing_score - greedy_score


def calculate_score_delta_percent(greedy_score: float, score_delta: float) -> float:
    """Return score delta percentage using absolute greedy score as denominator."""

    denominator = abs(greedy_score)
    if denominator == 0:
        return 0.0
    return score_delta / denominator * 100.0


def summarize_context(
    candidates: list[ContextCandidate],
    selected: list[ContextCandidate],
    excluded: Iterable[ExcludedContext],
    token_budget: int,
) -> ContextBenchmarkSummary:
    """Summarize token savings and critical context preservation."""

    excluded_items = list(excluded)
    tokens_before = sum(item.token_cost for item in candidates)
    tokens_after = sum(item.token_cost for item in selected)
    return ContextBenchmarkSummary(
        candidate_count=len(candidates),
        selected_count=len(selected),
        excluded_count=len(excluded_items),
        tokens_before=tokens_before,
        tokens_after=tokens_after,
        token_savings_percent=calculate_token_savings_percent(tokens_before, tokens_after),
        critical_items_included=critical_context_included(candidates, selected, token_budget),
        selected_context_ids=[item.id for item in selected],
        excluded_context=[f"{item.id}: {item.reason}" for item in excluded_items],
    )


def calculate_token_savings_percent(tokens_before: int, tokens_after: int) -> float:
    """Return context token savings percentage."""

    if tokens_before <= 0:
        return 0.0
    return max(0.0, tokens_before - tokens_after) / tokens_before * 100.0


def critical_context_included(
    candidates: list[ContextCandidate],
    selected: list[ContextCandidate],
    token_budget: int,
) -> bool:
    """Report whether every critical item that individually fits was selected."""

    selected_ids = {item.id for item in selected}
    fitting_critical_ids = {
        item.id for item in candidates if item.critical and item.token_cost <= token_budget
    }
    return fitting_critical_ids.issubset(selected_ids)


def summarize_budget(
    *,
    input_tokens: int,
    output_tokens: int,
    estimated_cost: float,
    quality_preserved: bool,
    case: BenchmarkCase,
) -> BudgetDecision:
    """Create an aggregate token/cost/quality budget decision."""

    within_token_budget = (
        input_tokens <= case.token_budget.max_input_tokens
        and output_tokens <= case.token_budget.max_output_tokens
    )
    within_cost_budget = estimated_cost <= case.token_budget.max_cost
    explanation = (
        f"Benchmark aggregate uses {input_tokens}+{output_tokens} tokens at "
        f"about ${estimated_cost:.6f}. Quality "
        f"{'meets' if quality_preserved else 'misses'} required thresholds. "
        f"Token budget is {'within' if within_token_budget else 'over'} limit; "
        f"cost budget is {'within' if within_cost_budget else 'over'} limit."
    )
    return BudgetDecision(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        estimated_cost=estimated_cost,
        within_token_budget=within_token_budget,
        within_cost_budget=within_cost_budget,
        meets_quality_threshold=quality_preserved,
        explanation=explanation,
    )


def _route_tasks(case: BenchmarkCase, tasks: list[Task]) -> list[ModelRouteSummary]:
    profiles = case.model_profiles or fake_model_profiles()
    routes: list[ModelRouteSummary] = []
    for task in tasks:
        threshold = case.quality_thresholds.get(task.id, case.quality_threshold)
        try:
            route = route_model(
                ModelRouteRequest(
                    required_capabilities=task.required_capabilities,
                    input_tokens=task.estimated_input_tokens,
                    output_tokens=task.estimated_output_tokens,
                    quality_threshold=threshold,
                    privacy_level=task.privacy_level,
                    needs_tools=bool(task.allowed_tools),
                    needs_json=True,
                    profiles=profiles,
                )
            )
        except ModelRoutingError as error:
            routes.append(
                ModelRouteSummary(
                    task_id=task.id,
                    selected_model="unrouted",
                    required_quality_threshold=threshold,
                    estimated_cost=0.0,
                    rejected_models=[RejectedModelSummary(identifier="all", reason=str(error))],
                    error=str(error),
                )
            )
            continue
        routes.append(
            ModelRouteSummary(
                task_id=task.id,
                selected_model=route.profile.identifier,
                selected_quality=route.quality,
                required_quality_threshold=threshold,
                estimated_cost=route.estimated_cost,
                rejected_models=[
                    RejectedModelSummary(identifier=item.identifier, reason=item.reason)
                    for item in route.rejected
                ],
            )
        )
    return routes


def _persist_benchmark_run(
    *,
    repository: RunRepository,
    run_id: str,
    case: BenchmarkCase,
    best_order: list[Task],
    scheduler: SchedulerBenchmarkSummary,
    model_routes: list[ModelRouteSummary],
    context: ContextBenchmarkSummary,
    budget: BudgetDecision,
    approval_tasks: list[Task],
) -> None:
    repository.save_run_tasks(
        RunTaskRecord(
            run_id=run_id,
            task_id=task.id,
            title=task.title,
            description=task.description,
            selected_order=index,
            priority=task.priority,
            risk=task.risk,
            expected_value=task.expected_value,
            dependencies=task.dependencies,
            required_capabilities=sorted(task.required_capabilities),
            requires_approval=task.requires_approval,
        )
        for index, task in enumerate(best_order, start=1)
    )
    repository.save_decision(
        RunDecisionRecord(
            run_id=run_id,
            decision_type="scheduler_greedy",
            selected_option=" -> ".join(scheduler.greedy_order),
            objective_score=scheduler.greedy_score,
            rationale=(
                f"Greedy dependency violations: {scheduler.greedy_dependency_violations}."
            ),
        )
    )
    repository.save_decision(
        RunDecisionRecord(
            run_id=run_id,
            decision_type="scheduler_annealing",
            selected_option=" -> ".join(scheduler.annealing_order),
            objective_score=scheduler.annealing_score,
            rationale=(
                f"Annealing dependency violations: {scheduler.annealing_dependency_violations}."
            ),
        )
    )
    repository.save_decision(
        RunDecisionRecord(
            run_id=run_id,
            decision_type="scheduler_comparison",
            selected_option=scheduler.best_scheduler,
            objective_score=scheduler.best_score,
            rationale=(
                f"Score delta {scheduler.score_delta:+.2f} "
                f"({scheduler.score_delta_percent:+.2f}%)."
            ),
        )
    )
    for route in model_routes:
        repository.save_decision(
            RunDecisionRecord(
                run_id=run_id,
                decision_type=f"model_route:{route.task_id}",
                selected_option=route.selected_model,
                rejected_options=[
                    f"{item.identifier}: {item.reason}" for item in route.rejected_models
                ],
                objective_score=route.selected_quality,
                estimated_cost=route.estimated_cost,
                rationale=route.error or "Selected cheapest model preserving required quality.",
            )
        )
    repository.save_decision(
        RunDecisionRecord(
            run_id=run_id,
            decision_type="context_packing",
            selected_option=", ".join(context.selected_context_ids) or "none",
            rejected_options=context.excluded_context,
            objective_score=context.token_savings_percent,
            rationale=(
                f"Packed {context.selected_count}/{context.candidate_count} context items; "
                f"critical included: {context.critical_items_included}."
            ),
        )
    )
    repository.save_decision(
        RunDecisionRecord(
            run_id=run_id,
            decision_type="quality_guard",
            selected_option="preserved" if budget.meets_quality_threshold else "missed",
            objective_score=1.0 if budget.meets_quality_threshold else 0.0,
            rationale=f"Required benchmark threshold: {case.quality_threshold:.2f}.",
        )
    )
    repository.save_decision(
        RunDecisionRecord(
            run_id=run_id,
            decision_type="token_budget",
            selected_option="approved" if budget.approved else "blocked",
            rejected_options=_budget_rejections(budget),
            estimated_cost=budget.estimated_cost,
            rationale=budget.explanation,
        )
    )
    for task in approval_tasks:
        repository.save_approval(
            ApprovalRecord(
                run_id=run_id,
                action_type="benchmark_task",
                action_description=task.description,
                risk_level=_risk_level_from_score(task.risk),
            )
        )


def _summary_text(
    case: BenchmarkCase,
    scheduler: SchedulerBenchmarkSummary,
    context: ContextBenchmarkSummary,
    budget: BudgetDecision,
    model_routes: list[ModelRouteSummary],
    approval_tasks: list[Task],
) -> str:
    selected_models = sorted({route.selected_model for route in model_routes})
    return "\n".join(
        [
            f"Benchmark: {case.id}",
            (
                f"Greedy score {scheduler.greedy_score:.2f}; annealing score "
                f"{scheduler.annealing_score:.2f}; delta "
                f"{scheduler.score_delta_percent:+.2f}%."
            ),
            f"Selected scheduler: {scheduler.best_scheduler}.",
            (
                f"Context tokens: {context.tokens_before} before, {context.tokens_after} "
                f"after, savings {context.token_savings_percent:.1f}%."
            ),
            f"Selected models: {', '.join(selected_models) or 'none'}.",
            f"Quality preserved: {'yes' if budget.meets_quality_threshold else 'no'}.",
            "Approval-needed tasks: " + (", ".join(task.id for task in approval_tasks) or "none"),
            budget.explanation,
        ]
    )


def _risk_level_from_score(score: float) -> RiskLevel:
    if score >= 0.75:
        return RiskLevel.CRITICAL
    if score >= 0.5:
        return RiskLevel.HIGH
    if score >= 0.25:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def _budget_rejections(decision: BudgetDecision) -> list[str]:
    rejected: list[str] = []
    if not decision.within_token_budget:
        rejected.append("token budget exceeded")
    if not decision.within_cost_budget:
        rejected.append("cost budget exceeded")
    if not decision.meets_quality_threshold:
        rejected.append("quality threshold missed")
    return rejected
