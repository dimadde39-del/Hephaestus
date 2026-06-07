"""Benchmark execution over the existing optimizer stack."""

from __future__ import annotations

from collections import Counter
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
from hephaestus.decision import (
    DecisionTraceBuilder,
    DecisionTraceRepository,
    most_common_rationale,
    most_common_rejection_reason,
)
from hephaestus.decision.schemas import (
    DecisionAlternative,
    DecisionTraceVariant,
    ModelRoutingDecision,
    metric,
)
from hephaestus.models import fake_model_profiles
from hephaestus.optimize.context_packer import (
    ContextCandidate,
    ContextPackResult,
    ExcludedContext,
    pack_context,
)
from hephaestus.optimize.model_router import ModelRouteRequest, ModelRoutingError, route_model
from hephaestus.optimize.task_scheduler import SchedulerComparison, compare_schedulers
from hephaestus.optimize.token_firewall import BudgetDecision, TokenBudget
from hephaestus.policy_learning import (
    ProfileStore,
    apply_context_packer_profiles,
    apply_failure_memory_context_boost,
    apply_model_router_profiles,
    apply_scheduler_profiles,
    apply_token_firewall_profiles,
    profiles_for_execution,
)
from hephaestus.policy_learning.schemas import DecisionQualityProfile, ProfileApplicationResult
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
    profile_ids: Iterable[str] | None = None,
) -> list[BenchmarkResult]:
    """Run every benchmark fixture in the benchmark directory."""

    cases = load_all_benchmarks(directory)
    profile_id_list = list(profile_ids) if profile_ids is not None else None
    return [
        run_benchmark(
            case,
            repository=repository,
            persist=persist,
            profile_ids=profile_id_list,
        )
        for case in cases
    ]


def run_benchmark(
    case: BenchmarkCase,
    *,
    repository: RunRepository | None = None,
    persist: bool = True,
    profile_ids: Iterable[str] | None = None,
) -> BenchmarkResult:
    """Run one benchmark and optionally persist a benchmark-mode run."""

    run_repository = repository or (RunRepository() if persist else None)
    run = None
    if persist and run_repository is not None:
        run = run_repository.save_run(
            RunRecord(goal=f"Benchmark {case.id}: {case.goal or case.title}", mode="benchmark")
        )

    profile_store = _profile_store_for_run(run_repository, profile_ids)
    active_profiles = (
        profiles_for_execution(profile_store, profile_ids)
        if profile_store is not None
        else []
    )
    active_profile_ids = [profile.id for profile in active_profiles]
    profile_applications: list[ProfileApplicationResult] = []
    application_run_id = run.id if run is not None else None
    scheduler_weights, scheduler_apps = apply_scheduler_profiles(
        DEFAULT_CONFIG.objective_weights,
        active_profiles,
        run_id=application_run_id,
        store=profile_store if persist else None,
    )
    profile_applications.extend(scheduler_apps)
    comparison = compare_schedulers(case.tasks, scheduler_weights)
    scheduler = summarize_scheduler(comparison)
    best_order = comparison.best_order
    context_settings, context_apps = apply_context_packer_profiles(
        active_profiles,
        run_id=application_run_id,
        store=profile_store if persist else None,
    )
    profile_applications.extend(context_apps)
    context_candidates = apply_failure_memory_context_boost(
        case.context_candidates,
        context_settings,
    )
    context_result = pack_context(
        context_candidates,
        case.context_token_budget,
        preserve_critical_context=context_settings.preserve_critical_context,
        failure_memory_importance_boost=context_settings.failure_memory_importance_boost,
        compression_aggressiveness=context_settings.compression_aggressiveness,
    )
    context = summarize_context(
        context_candidates,
        context_result.selected,
        context_result.excluded,
        case.context_token_budget,
    )
    approval_tasks = [task for task in best_order if task.requires_approval]
    model_routes, model_apps = _route_tasks(
        case,
        best_order,
        active_profiles=active_profiles,
        run_id=application_run_id,
        store=profile_store if persist else None,
    )
    profile_applications.extend(model_apps)
    total_input = sum(task.estimated_input_tokens for task in best_order)
    total_output = sum(task.estimated_output_tokens for task in best_order)
    total_cost = sum(route.estimated_cost for route in model_routes)
    quality_preserved = bool(model_routes) and all(route.quality_preserved for route in model_routes)
    adjusted_token_budget, token_apps = apply_token_firewall_profiles(
        case.token_budget,
        active_profiles,
        run_id=application_run_id,
        store=profile_store if persist else None,
    )
    profile_applications.extend(token_apps)
    budget = summarize_budget(
        input_tokens=total_input,
        output_tokens=total_output,
        estimated_cost=total_cost,
        quality_preserved=quality_preserved,
        case=case,
        token_budget=adjusted_token_budget,
    )
    trace_run_id = run.id if run is not None else f"benchmark_{case.id}"
    decision_traces = _build_benchmark_traces(
        run_id=trace_run_id,
        case=case,
        comparison=comparison,
        context_result=context_result,
        context_candidates=context_candidates,
        budget=budget,
        token_budget=adjusted_token_budget,
        model_routes=model_routes,
        approval_tasks=approval_tasks,
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
            token_budget=adjusted_token_budget,
            approval_tasks=approval_tasks,
            decision_traces=decision_traces,
        )

    top_rationale = most_common_rationale(decision_traces)
    top_decision_type = _top_decision_type(decision_traces)
    common_rejection_reason = most_common_rejection_reason(decision_traces)
    token_savings_summary = _token_savings_summary(context)
    summary = _summary_text(
        case,
        scheduler,
        context,
        budget,
        model_routes,
        approval_tasks,
        decision_count=len(decision_traces),
        top_decision_type=top_decision_type,
        top_decision_rationale=top_rationale,
        most_common_rejection_reason=common_rejection_reason,
        token_savings_summary=token_savings_summary,
        active_profile_ids=active_profile_ids,
        profile_applications=profile_applications,
    )
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
        decision_count=len(decision_traces),
        top_decision_type=top_decision_type,
        top_decision_rationale=top_rationale,
        most_common_rejection_reason=common_rejection_reason,
        token_savings_summary=token_savings_summary,
        active_profile_ids=active_profile_ids,
        profile_applications=profile_applications,
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
    token_budget: TokenBudget | None = None,
) -> BudgetDecision:
    """Create an aggregate token/cost/quality budget decision."""

    effective_budget = token_budget or case.token_budget
    within_token_budget = (
        input_tokens <= effective_budget.max_input_tokens
        and output_tokens <= effective_budget.max_output_tokens
    )
    within_cost_budget = estimated_cost <= effective_budget.max_cost
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


def _route_tasks(
    case: BenchmarkCase,
    tasks: list[Task],
    *,
    active_profiles: list[DecisionQualityProfile],
    run_id: str | None,
    store: ProfileStore | None,
) -> tuple[list[ModelRouteSummary], list[ProfileApplicationResult]]:
    profiles = case.model_profiles or fake_model_profiles()
    routes: list[ModelRouteSummary] = []
    applications: list[ProfileApplicationResult] = []
    for task in tasks:
        threshold = case.quality_thresholds.get(task.id, case.quality_threshold)
        request = ModelRouteRequest(
            required_capabilities=task.required_capabilities,
            input_tokens=task.estimated_input_tokens,
            output_tokens=task.estimated_output_tokens,
            quality_threshold=threshold,
            privacy_level=task.privacy_level,
            needs_tools=bool(task.allowed_tools),
            needs_json=True,
            profiles=profiles,
        )
        request, request_apps = apply_model_router_profiles(
            request,
            active_profiles,
            run_id=run_id,
            store=store,
        )
        applications.extend(request_apps)
        try:
            route = route_model(request)
        except ModelRoutingError as error:
            routes.append(
                ModelRouteSummary(
                    task_id=task.id,
                    selected_model="unrouted",
                    required_quality_threshold=request.quality_threshold,
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
                required_quality_threshold=request.quality_threshold,
                estimated_cost=route.estimated_cost,
                rejected_models=[
                    RejectedModelSummary(identifier=item.identifier, reason=item.reason)
                    for item in route.rejected
                ],
            )
        )
    return routes, applications


def _build_benchmark_traces(
    *,
    run_id: str,
    case: BenchmarkCase,
    comparison: SchedulerComparison,
    context_result: ContextPackResult,
    context_candidates: list[ContextCandidate],
    budget: BudgetDecision,
    token_budget: TokenBudget,
    model_routes: list[ModelRouteSummary],
    approval_tasks: list[Task],
) -> list[DecisionTraceVariant]:
    builder = DecisionTraceBuilder(run_id, phase="benchmark", tags=["benchmark"])
    optimization_trace = builder.optimization(comparison)
    task_trace = builder.task_selection(
        comparison,
        parent_id=optimization_trace.id,
    )
    traces: list[DecisionTraceVariant] = [
        optimization_trace,
        task_trace,
        builder.context_selection(
            context_candidates,
            context_result,
            case.context_token_budget,
        ),
        builder.budget(budget, token_budget),
    ]
    traces.extend(
        _model_route_trace(
            run_id=run_id,
            route=route,
            candidate_count=len(case.model_profiles or fake_model_profiles()),
            parent_id=task_trace.id,
        )
        for route in model_routes
    )
    traces.extend(
        builder.safety_approval(
            action=task.description,
            reason=f"Benchmark task {task.id} requires approval before execution.",
            risk_level=_risk_level_from_score(task.risk),
            parent_id=task_trace.id,
        )
        for task in approval_tasks
    )
    return traces


def _model_route_trace(
    *,
    run_id: str,
    route: ModelRouteSummary,
    candidate_count: int,
    parent_id: str | None = None,
) -> ModelRoutingDecision:
    return ModelRoutingDecision(
        run_id=run_id,
        phase="benchmark",
        selected_option=route.selected_model,
        alternatives=[
            DecisionAlternative(
                option_id=item.identifier,
                rejection_reason=item.reason,
                violated_constraints=_constraints_for_rejection(item.reason),
            )
            for item in route.rejected_models
        ],
        rationale=route.error or "Selected cheapest model preserving required quality.",
        metrics=[
            metric("quality_threshold", route.required_quality_threshold),
            metric("selected_quality", route.selected_quality),
            metric("estimated_cost", route.estimated_cost, unit="USD"),
            metric("candidate_count", candidate_count),
            metric("rejected_count", len(route.rejected_models)),
        ],
        objective_score=route.selected_quality,
        confidence=0.84 if not route.error else 0.62,
        constraints_considered=[
            f"quality >= {route.required_quality_threshold:.2f}",
            "required capabilities",
            "context window",
            "privacy",
            "tools/JSON support",
        ],
        tags=["benchmark", "model-routing"],
        caused_by=[f"benchmark_route:{route.task_id}", "model_profiles"],
        will_affect=["quality_preserved_status", "estimated_cost"],
        learning_hooks=[
            "model_quality_outcome",
            "benchmark_failure_learning",
            "routing_threshold_policy",
        ],
        parent_id=parent_id,
    )


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
    token_budget: TokenBudget,
    approval_tasks: list[Task],
    decision_traces: list[DecisionTraceVariant],
) -> None:
    trace_repository = DecisionTraceRepository(repository.database_path)
    trace_repository.save_traces(decision_traces)
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
            rationale=f"Required benchmark threshold: {token_budget.quality_threshold:.2f}.",
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
    *,
    decision_count: int,
    top_decision_type: str,
    top_decision_rationale: str,
    most_common_rejection_reason: str,
    token_savings_summary: str,
    active_profile_ids: list[str],
    profile_applications: list[ProfileApplicationResult],
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
            f"Decision count: {decision_count}.",
            "Active profiles: " + (", ".join(active_profile_ids) or "none"),
            f"Profile applications: {len(profile_applications)}.",
            f"Top decision type: {_sentence(top_decision_type)}",
            f"Top decision rationale: {_sentence(top_decision_rationale)}",
            f"Most common rejection reason: {_sentence(most_common_rejection_reason)}",
            f"Token savings summary: {_sentence(token_savings_summary)}",
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


def _constraints_for_rejection(reason: str) -> list[str]:
    lowered = reason.lower()
    constraints: list[str] = []
    if "quality" in lowered or "threshold" in lowered:
        constraints.append("quality threshold")
    if "capabilit" in lowered:
        constraints.append("required capabilities")
    if "context" in lowered or "token" in lowered:
        constraints.append("token budget")
    if "cost" in lowered:
        constraints.append("cost budget")
    if "tool" in lowered:
        constraints.append("tool support")
    if "json" in lowered:
        constraints.append("JSON output")
    if "privacy" in lowered:
        constraints.append("privacy policy")
    return constraints or ["objective comparison"]


def _top_decision_type(traces: Iterable[DecisionTraceVariant]) -> str:
    counts = Counter(trace.decision_type.value for trace in traces)
    top = counts.most_common(1)
    return top[0][0] if top else ""


def _token_savings_summary(context: ContextBenchmarkSummary) -> str:
    saved = max(0, context.tokens_before - context.tokens_after)
    return f"saved {saved} context tokens ({context.token_savings_percent:.1f}%)"


def _sentence(value: str) -> str:
    if not value:
        return "none."
    if value.endswith((".", "!", "?")):
        return value
    return f"{value}."


def _profile_store_for_run(
    repository: RunRepository | None,
    profile_ids: Iterable[str] | None,
) -> ProfileStore | None:
    if repository is not None:
        return ProfileStore(repository.database_path)
    if profile_ids is not None:
        return ProfileStore()
    return None
