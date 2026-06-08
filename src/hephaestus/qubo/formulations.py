"""QUBO formulations for agent decision problems."""

from __future__ import annotations

from collections.abc import Sequence
from itertools import combinations
from typing import TypedDict

from hephaestus.benchmarks.schemas import BenchmarkCase
from hephaestus.core.config import PrivacyLevel
from hephaestus.models import ModelProfile, fake_model_profiles
from hephaestus.optimize.context_packer import ContextCandidate
from hephaestus.pareto.schemas import ObjectiveDimension, PreferenceProfile
from hephaestus.policy_learning import (
    apply_context_packer_profiles,
    apply_failure_memory_context_boost,
)
from hephaestus.policy_learning.schemas import (
    DecisionArea,
    DecisionQualityProfile,
    ProfileStatus,
)
from hephaestus.qubo.builder import QuboBuilder, safe_variable_id
from hephaestus.qubo.schemas import (
    FormulationReport,
    QuboConstraint,
    QuboConstraintType,
    QuboObjective,
    QuboProblem,
    QuboProblemType,
)
from hephaestus.spec.tasks import Task


class BudgetStrategy(TypedDict):
    """Typed budget strategy metrics used by the QUBO formulation."""

    name: str
    quality_preservation: float
    safety: float
    profile_alignment: float
    estimated_cost: float
    token_usage: float
    quality_risk: float
    missing_critical: float
    context_token_target: int


def formulate_benchmark_case(
    case: BenchmarkCase,
    problem_type: QuboProblemType,
    *,
    run_id: str | None = None,
    active_profiles: Sequence[DecisionQualityProfile] | None = None,
    source_frontier_id: str | None = None,
    source_decision_trace_ids: Sequence[str] | None = None,
    preference_profile: PreferenceProfile | None = None,
) -> FormulationReport:
    """Formulate one benchmark fixture as a selected QUBO problem."""

    if problem_type == QuboProblemType.CONTEXT_PACKING:
        return formulate_context_packing(
            case,
            run_id=run_id,
            active_profiles=active_profiles,
            source_frontier_id=source_frontier_id,
            source_decision_trace_ids=source_decision_trace_ids,
        )
    if problem_type == QuboProblemType.MODEL_SELECTION:
        return formulate_model_selection(
            case,
            run_id=run_id,
            active_profiles=active_profiles,
            source_frontier_id=source_frontier_id,
            source_decision_trace_ids=source_decision_trace_ids,
        )
    if problem_type == QuboProblemType.BUDGET_STRATEGY:
        return formulate_budget_strategy(
            case,
            run_id=run_id,
            active_profiles=active_profiles,
            source_frontier_id=source_frontier_id,
            source_decision_trace_ids=source_decision_trace_ids,
            preference_profile=preference_profile,
        )
    if problem_type == QuboProblemType.TASK_ORDERING_DEMO:
        return formulate_task_ordering_demo(
            case,
            run_id=run_id,
            active_profiles=active_profiles,
            source_frontier_id=source_frontier_id,
            source_decision_trace_ids=source_decision_trace_ids,
        )
    raise ValueError(f"Unsupported QUBO problem type: {problem_type.value}")


def formulate_context_packing(
    case: BenchmarkCase,
    *,
    run_id: str | None = None,
    active_profiles: Sequence[DecisionQualityProfile] | None = None,
    source_frontier_id: str | None = None,
    source_decision_trace_ids: Sequence[str] | None = None,
    max_item_count: int | None = None,
) -> FormulationReport:
    """Build a QUBO for selecting context items under token and criticality pressure."""

    profiles = list(active_profiles or [])
    settings, _ = apply_context_packer_profiles(profiles)
    candidates = apply_failure_memory_context_boost(list(case.context_candidates), settings)
    objective = QuboObjective(
        description=(
            "Minimize negative context utility plus token, redundancy, and constraint penalties."
        ),
        reward_summary=[
            "relevance",
            "importance",
            "criticality",
            "failure memory usefulness",
            "active context profile alignment",
        ],
        penalty_summary=[
            "token cost",
            "redundancy",
            "missing critical context",
            "token budget pressure",
            "optional item count pressure",
        ],
    )
    weights = {
        "relevance": 2.0,
        "importance": 1.5,
        "criticality": 1.0,
        "failure_memory": 0.45,
        "profile_alignment": 0.35,
        "token_cost": 0.9,
        "redundancy": 1.35,
        "missing_critical": 7.0,
        "token_budget": 12.0,
        "max_item_count": 3.0,
    }
    builder = QuboBuilder(
        problem_type=QuboProblemType.CONTEXT_PACKING,
        run_id=run_id,
        source_benchmark_id=case.id,
        source_frontier_id=source_frontier_id,
        source_decision_trace_ids=list(source_decision_trace_ids or []),
        tags=["qubo", "context-packing", *case.tags],
        objective=objective,
        metadata={"fixture_title": case.title, "context_token_budget": case.context_token_budget},
    )

    variable_by_candidate: dict[str, str] = {}
    token_costs: dict[str, int] = {}
    for candidate in candidates:
        variable_id = safe_variable_id("x_context", candidate.id)
        variable_by_candidate[candidate.id] = variable_id
        token_costs[variable_id] = candidate.token_cost
        profile_alignment = _context_profile_alignment(candidate, profiles)
        failure_bonus = weights["failure_memory"] if _is_failure_memory_context(candidate) else 0.0
        reward = (
            weights["relevance"] * candidate.relevance
            + weights["importance"] * candidate.importance
            + (weights["criticality"] if candidate.critical else 0.0)
            + failure_bonus
            + weights["profile_alignment"] * profile_alignment
        )
        token_penalty = weights["token_cost"] * candidate.token_cost / max(1, case.context_token_budget)
        builder.add_variable(
            variable_id,
            label=candidate.id,
            description=f"include context item {candidate.id}",
            metadata={
                "source_id": candidate.id,
                "relevance": candidate.relevance,
                "importance": candidate.importance,
                "token_cost": candidate.token_cost,
                "critical": candidate.critical,
                "profile_alignment": profile_alignment,
                "failure_memory": _is_failure_memory_context(candidate),
            },
        )
        builder.add_linear(
            variable_id,
            token_penalty - reward,
            reason=(
                f"context utility reward {reward:.3f}; token penalty {token_penalty:.3f}"
            ),
        )
        if candidate.critical and candidate.token_cost <= case.context_token_budget:
            builder.add_required_variable(
                variable_id,
                weight=weights["missing_critical"],
                description=f"Critical context {candidate.id} should be included when it fits.",
                constraint_id=f"critical_{variable_id}",
                metadata={"source_id": candidate.id},
            )
        if candidate.token_cost > case.context_token_budget:
            builder.add_linear(
                variable_id,
                weights["token_budget"],
                reason="single item exceeds token budget",
            )

    variable_ids = list(variable_by_candidate.values())
    budget = max(1, case.context_token_budget)
    for first, second in combinations(candidates, 2):
        first_variable = variable_by_candidate[first.id]
        second_variable = variable_by_candidate[second.id]
        pair_penalty = (
            weights["token_budget"]
            * first.token_cost
            * second.token_cost
            / (budget * budget)
        )
        redundancy = _redundancy_score(first, second)
        if redundancy:
            pair_penalty += weights["redundancy"] * redundancy
        if pair_penalty:
            builder.add_quadratic(
                first_variable,
                second_variable,
                pair_penalty,
                reason=(
                    f"token-budget pair pressure {pair_penalty:.3f}; "
                    f"redundancy {redundancy:.2f}"
                ),
            )

    builder.add_constraint(
        QuboConstraint(
            id="context_token_budget",
            constraint_type=QuboConstraintType.TOKEN_BUDGET,
            description="Selected context should stay within the token budget.",
            variable_ids=variable_ids,
            operator="<=",
            target_value=float(case.context_token_budget),
            penalty_weight=weights["token_budget"],
            metadata={
                "budget": case.context_token_budget,
                "token_cost_by_variable": token_costs,
            },
        )
    )
    if max_item_count is not None:
        builder.add_constraint(
            QuboConstraint(
                id="context_max_item_count",
                constraint_type=QuboConstraintType.MAX_ITEM_COUNT,
                description=f"Selected context should use at most {max_item_count} items.",
                variable_ids=variable_ids,
                operator="<=",
                target_value=float(max_item_count),
                penalty_weight=weights["max_item_count"],
                metadata={"max_count": max_item_count},
            )
        )

    problem = builder.build()
    return _report(
        problem,
        summary=(
            f"Context packing QUBO maps {len(candidates)} context candidates to binary "
            f"include/exclude variables under a {case.context_token_budget} token budget."
        ),
        notes=[
            "Critical items are encoded with required-variable penalties when they fit.",
            "Token budget pressure is represented with linear token cost and pairwise token interactions.",
        ],
    )


def formulate_model_selection(
    case: BenchmarkCase,
    *,
    run_id: str | None = None,
    active_profiles: Sequence[DecisionQualityProfile] | None = None,
    source_frontier_id: str | None = None,
    source_decision_trace_ids: Sequence[str] | None = None,
    task: Task | None = None,
) -> FormulationReport:
    """Build a QUBO for selecting exactly one model profile."""

    profiles = list(active_profiles or [])
    selected_task = task or _model_selection_task(case)
    models = case.model_profiles or list(fake_model_profiles())
    input_tokens = selected_task.estimated_input_tokens
    output_tokens = selected_task.estimated_output_tokens
    total_tokens = input_tokens + output_tokens
    quality_threshold = case.quality_thresholds.get(selected_task.id, case.quality_threshold)
    objective = QuboObjective(
        description="Minimize model selection risk and cost while preserving capability and quality.",
        reward_summary=[
            "quality",
            "confidence",
            "privacy fit",
            "capability match",
            "profile alignment",
        ],
        penalty_summary=[
            "estimated cost",
            "latency",
            "token/context risk",
            "quality threshold violation",
            "required capability violation",
            "exactly one selected model",
        ],
    )
    weights = {
        "quality": 3.0,
        "confidence": 0.8,
        "privacy": 0.5,
        "capability": 0.8,
        "profile_alignment": 0.6,
        "cost": 1.0,
        "latency": 0.3,
        "risk": 0.8,
        "exactly_one": 8.0,
        "required_capability": 6.0,
        "quality_threshold": 6.0,
        "quality_threshold_hard": 2.0,
    }
    builder = QuboBuilder(
        problem_type=QuboProblemType.MODEL_SELECTION,
        run_id=run_id,
        source_benchmark_id=case.id,
        source_frontier_id=source_frontier_id,
        source_decision_trace_ids=list(source_decision_trace_ids or []),
        tags=["qubo", "model-selection", *case.tags],
        objective=objective,
        metadata={
            "fixture_title": case.title,
            "task_id": selected_task.id,
            "quality_threshold": quality_threshold,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
        },
    )

    max_cost = max(
        (model.estimated_cost(input_tokens, output_tokens) for model in models),
        default=1.0,
    )
    variable_ids: list[str] = []
    invalid_variables: list[str] = []
    quality_by_variable: dict[str, float] = {}
    for model in sorted(models, key=lambda item: item.identifier):
        variable_id = safe_variable_id("x_model", model.identifier)
        variable_ids.append(variable_id)
        quality = model.quality_for(selected_task.required_capabilities)
        cost = model.estimated_cost(input_tokens, output_tokens)
        capability_match = (
            1.0
            if selected_task.required_capabilities.issubset(model.capabilities)
            else len(selected_task.required_capabilities.intersection(model.capabilities))
            / max(1, len(selected_task.required_capabilities))
        )
        privacy_fit = 1.0 if model.can_handle(selected_task.required_capabilities, selected_task.privacy_level) else 0.0
        profile_alignment = _model_profile_alignment(model, profiles)
        violations = _model_violations(model, selected_task, total_tokens, quality, quality_threshold)
        if violations:
            invalid_variables.append(variable_id)
        risk = _model_risk(quality, quality_threshold, violations)
        confidence = _clamp01(quality * 0.75 + (1.0 - risk) * 0.25)
        reward = (
            weights["quality"] * quality
            + weights["confidence"] * confidence
            + weights["privacy"] * privacy_fit
            + weights["capability"] * capability_match
            + weights["profile_alignment"] * profile_alignment
        )
        normalized_cost = cost / max(max_cost, 1e-12)
        latency_penalty = weights["latency"] * max(0.0, 1.0 - model.latency_score)
        risk_penalty = weights["risk"] * risk
        coefficient = -reward + weights["cost"] * normalized_cost + latency_penalty + risk_penalty
        if quality < quality_threshold:
            coefficient += (
                weights["quality_threshold_hard"]
                + weights["quality_threshold"] * (quality_threshold - quality)
            )
        if violations:
            coefficient += weights["required_capability"] * _hard_violation_count(violations)
        quality_by_variable[variable_id] = quality
        builder.add_variable(
            variable_id,
            label=model.identifier,
            description=f"choose model {model.identifier}",
            metadata={
                "provider": model.provider,
                "model": model.model,
                "quality": quality,
                "quality_threshold": quality_threshold,
                "estimated_cost": cost,
                "latency_score": model.latency_score,
                "risk": risk,
                "privacy_fit": privacy_fit,
                "capability_match": capability_match,
                "profile_alignment": profile_alignment,
                "violations": violations,
                "task_id": selected_task.id,
            },
        )
        builder.add_linear(
            variable_id,
            coefficient,
            reason=(
                f"model reward {reward:.3f}; normalized cost {normalized_cost:.3f}; "
                f"risk {risk:.3f}; violations {len(violations)}"
            ),
        )

    builder.add_exactly_one(
        variable_ids,
        weight=weights["exactly_one"],
        description="Exactly one model should be selected.",
        constraint_id="model_exactly_one",
    )
    builder.add_constraint(
        QuboConstraint(
            id="model_required_capability",
            constraint_type=QuboConstraintType.REQUIRED_CAPABILITY,
            description="Selected model must satisfy represented capability/privacy/tool constraints.",
            variable_ids=variable_ids,
            penalty_weight=weights["required_capability"],
            metadata={"invalid_variables": invalid_variables},
        )
    )
    builder.add_constraint(
        QuboConstraint(
            id="model_quality_threshold",
            constraint_type=QuboConstraintType.QUALITY_THRESHOLD,
            description=f"Selected model should meet quality threshold {quality_threshold:.2f}.",
            variable_ids=variable_ids,
            operator=">=",
            target_value=quality_threshold,
            penalty_weight=weights["quality_threshold"],
            metadata={
                "threshold": quality_threshold,
                "quality_by_variable": quality_by_variable,
            },
        )
    )
    problem = builder.build()
    return _report(
        problem,
        summary=(
            f"Model selection QUBO maps {len(models)} model profiles to one-hot variables "
            f"for task {selected_task.id}."
        ),
        notes=[
            "Quality threshold violations stay inspectable as both linear penalties and constraints.",
            "The formulation optimizes locally and does not call paid model APIs.",
        ],
    )


def formulate_budget_strategy(
    case: BenchmarkCase,
    *,
    run_id: str | None = None,
    active_profiles: Sequence[DecisionQualityProfile] | None = None,
    source_frontier_id: str | None = None,
    source_decision_trace_ids: Sequence[str] | None = None,
    preference_profile: PreferenceProfile | None = None,
) -> FormulationReport:
    """Build a QUBO for choosing one budget strategy."""

    profiles = list(active_profiles or [])
    objective = QuboObjective(
        description="Minimize budget strategy risk while preserving quality and safety.",
        reward_summary=["quality preservation", "safety", "profile alignment"],
        penalty_summary=[
            "estimated cost",
            "token usage",
            "quality risk",
            "missing critical context",
            "exactly one selected strategy",
        ],
    )
    weights = {
        "quality": 2.5,
        "safety": 1.4,
        "profile_alignment": 0.9,
        "cost": 0.7,
        "tokens": 0.7,
        "quality_risk": 1.6,
        "missing_critical": 2.5,
        "exactly_one": 7.0,
    }
    total_input = sum(task.estimated_input_tokens for task in case.tasks)
    total_output = sum(task.estimated_output_tokens for task in case.tasks)
    total_context_tokens = sum(candidate.token_cost for candidate in case.context_candidates)
    critical_tokens = sum(
        candidate.token_cost for candidate in case.context_candidates if candidate.critical
    )
    estimated_cost = _fixture_cost_estimate(case)
    strategies = _budget_strategies(
        case_context_budget=case.context_token_budget,
        total_context_tokens=total_context_tokens,
        critical_tokens=critical_tokens,
        total_input=total_input,
        total_output=total_output,
        estimated_cost=estimated_cost,
        active_profiles=profiles,
        preference_profile=preference_profile,
    )
    max_cost = max((strategy["estimated_cost"] for strategy in strategies), default=1.0)
    max_tokens = max((strategy["token_usage"] for strategy in strategies), default=1.0)
    builder = QuboBuilder(
        problem_type=QuboProblemType.BUDGET_STRATEGY,
        run_id=run_id,
        source_benchmark_id=case.id,
        source_frontier_id=source_frontier_id,
        source_decision_trace_ids=list(source_decision_trace_ids or []),
        tags=["qubo", "budget-strategy", *case.tags],
        objective=objective,
        metadata={
            "fixture_title": case.title,
            "token_budget": case.token_budget.model_dump(),
            "context_token_budget": case.context_token_budget,
        },
    )

    variable_ids: list[str] = []
    for strategy in strategies:
        name = str(strategy["name"])
        variable_id = safe_variable_id("x_strategy", name)
        variable_ids.append(variable_id)
        quality = float(strategy["quality_preservation"])
        safety = float(strategy["safety"])
        alignment = float(strategy["profile_alignment"])
        quality_risk = float(strategy["quality_risk"])
        missing_critical = float(strategy["missing_critical"])
        cost_norm = float(strategy["estimated_cost"]) / max(max_cost, 1e-12)
        token_norm = float(strategy["token_usage"]) / max(max_tokens, 1.0)
        reward = (
            weights["quality"] * quality
            + weights["safety"] * safety
            + weights["profile_alignment"] * alignment
        )
        penalty = (
            weights["cost"] * cost_norm
            + weights["tokens"] * token_norm
            + weights["quality_risk"] * quality_risk
            + weights["missing_critical"] * missing_critical
        )
        builder.add_variable(
            variable_id,
            label=name,
            description=f"choose budget strategy {name}",
            metadata=dict(strategy),
        )
        builder.add_linear(
            variable_id,
            penalty - reward,
            reason=f"strategy reward {reward:.3f}; penalty {penalty:.3f}",
        )

    builder.add_exactly_one(
        variable_ids,
        weight=weights["exactly_one"],
        description="Exactly one budget strategy should be selected.",
        constraint_id="budget_strategy_exactly_one",
    )
    problem = builder.build()
    return _report(
        problem,
        summary=f"Budget strategy QUBO maps {len(strategies)} strategies to one-hot variables.",
        notes=[
            "Strategies are deterministic policy options, not model calls.",
            "Pareto preference priorities can tilt profile alignment when supplied.",
        ],
    )


def formulate_task_ordering_demo(
    case: BenchmarkCase,
    *,
    run_id: str | None = None,
    active_profiles: Sequence[DecisionQualityProfile] | None = None,
    source_frontier_id: str | None = None,
    source_decision_trace_ids: Sequence[str] | None = None,
) -> FormulationReport:
    """Build a small demonstrative task-ordering QUBO."""

    profiles = list(active_profiles or [])
    tasks = list(case.tasks)
    objective = QuboObjective(
        description=(
            "Assign each task to one position while penalizing dependency inversions. "
            "This is a compact demo, not a full scheduling engine."
        ),
        reward_summary=["priority earlier", "expected value earlier", "profile-adjusted risk caution"],
        penalty_summary=["task assigned once", "position filled once", "dependency order"],
    )
    weights = {
        "assignment": 6.0,
        "dependency": 5.0,
        "priority": 0.18,
        "expected_value": 0.12,
        "risk": 0.16 + 0.06 * _profile_count(profiles, {DecisionArea.SCHEDULER, DecisionArea.OPTIMIZER}),
    }
    builder = QuboBuilder(
        problem_type=QuboProblemType.TASK_ORDERING_DEMO,
        run_id=run_id,
        source_benchmark_id=case.id,
        source_frontier_id=source_frontier_id,
        source_decision_trace_ids=list(source_decision_trace_ids or []),
        tags=["qubo", "task-ordering-demo", *case.tags],
        objective=objective,
        metadata={"fixture_title": case.title, "task_count": len(tasks)},
    )
    variable_by_task_position: dict[tuple[str, int], str] = {}
    for task in tasks:
        for position in range(len(tasks)):
            variable_id = safe_variable_id("x_order", f"{task.id}_{position + 1}")
            variable_by_task_position[(task.id, position)] = variable_id
            earlier_reward = (len(tasks) - position) / max(1, len(tasks))
            utility = (
                weights["priority"] * task.priority * earlier_reward
                + weights["expected_value"] * task.expected_value * earlier_reward
                - weights["risk"] * task.risk * earlier_reward
            )
            builder.add_variable(
                variable_id,
                label=f"{task.id}@{position + 1}",
                description=f"assign task {task.id} to position {position + 1}",
                metadata={"task_id": task.id, "position": position},
            )
            builder.add_linear(variable_id, -utility, reason=f"position utility {utility:.3f}")

    for task in tasks:
        builder.add_exactly_one(
            [variable_by_task_position[(task.id, position)] for position in range(len(tasks))],
            weight=weights["assignment"],
            description=f"Task {task.id} should be assigned exactly once.",
            constraint_id=f"task_once_{safe_variable_id('task', task.id)}",
        )
    for position in range(len(tasks)):
        builder.add_exactly_one(
            [variable_by_task_position[(task.id, position)] for task in tasks],
            weight=weights["assignment"],
            description=f"Position {position + 1} should contain exactly one task.",
            constraint_id=f"position_once_{position + 1}",
        )
    dependency_pairs: list[list[str]] = []
    task_ids = {task.id for task in tasks}
    for task in tasks:
        for dependency in task.dependencies:
            if dependency not in task_ids:
                continue
            dependency_pairs.append([task.id, dependency])
            for task_position in range(len(tasks)):
                for dependency_position in range(task_position, len(tasks)):
                    builder.add_quadratic(
                        variable_by_task_position[(task.id, task_position)],
                        variable_by_task_position[(dependency, dependency_position)],
                        weights["dependency"],
                        reason=f"dependency {dependency} must precede {task.id}",
                    )
    if dependency_pairs:
        builder.add_constraint(
            QuboConstraint(
                id="task_dependency_order",
                constraint_type=QuboConstraintType.DEPENDENCY_ORDER,
                description="Dependencies should appear before dependent tasks.",
                variable_ids=list(variable_by_task_position.values()),
                penalty_weight=weights["dependency"],
                metadata={"dependency_pairs": dependency_pairs},
            )
        )
    problem = builder.build()
    return _report(
        problem,
        summary=(
            f"Task ordering demo QUBO maps {len(tasks)} tasks into "
            f"{len(problem.variables)} task-position variables."
        ),
        notes=[
            "This demonstrative formulation is intentionally small and classical.",
            "Full scheduling with resource calendars remains a future extension.",
        ],
    )


def _report(problem: QuboProblem, *, summary: str, notes: list[str]) -> FormulationReport:
    return FormulationReport(
        problem=problem,
        summary=summary,
        variable_count=len(problem.variables),
        linear_term_count=len(problem.linear_terms),
        quadratic_term_count=len(problem.quadratic_terms),
        constraint_count=len(problem.constraints),
        notes=notes,
    )


def _model_selection_task(case: BenchmarkCase) -> Task:
    return sorted(case.tasks, key=lambda item: (-item.priority, item.id))[0]


def _context_profile_alignment(
    candidate: ContextCandidate,
    profiles: Sequence[DecisionQualityProfile],
) -> float:
    alignment = 0.55
    profile_count = _profile_count(profiles, {DecisionArea.CONTEXT_PACKER, DecisionArea.MEMORY_RETRIEVAL})
    if profile_count:
        alignment += min(0.25, profile_count * 0.08)
    if candidate.critical:
        alignment += 0.1
    if _is_failure_memory_context(candidate):
        alignment += 0.15
    return _clamp01(alignment)


def _model_profile_alignment(
    model: ModelProfile,
    profiles: Sequence[DecisionQualityProfile],
) -> float:
    alignment = 0.58
    for profile in profiles:
        if profile.status == ProfileStatus.ARCHIVED or profile.decision_area != DecisionArea.MODEL_ROUTER:
            continue
        alignment += 0.04 * profile.confidence
        for rule in profile.rules:
            if _matched_model_tags(model, set(rule.prefer_model_tags)):
                alignment += 0.15
            if _matched_model_tags(model, set(rule.avoid_model_tags)):
                alignment -= 0.25
            if rule.minimum_quality_score is not None:
                quality = model.quality_scores.get("general", 0.0)
                alignment += 0.06 if quality >= rule.minimum_quality_score else -0.06
    return _clamp01(alignment)


def _matched_model_tags(model: ModelProfile, tags: set[str]) -> set[str]:
    if not tags:
        return set()
    profile_tags = {
        model.identifier.lower(),
        model.provider.lower(),
        model.model.lower(),
        f"provider:{model.provider}".lower(),
        f"model:{model.model}".lower(),
        *{capability.lower() for capability in model.capabilities},
    }
    return {tag.lower() for tag in tags}.intersection(profile_tags)


def _model_violations(
    model: ModelProfile,
    task: Task,
    total_tokens: int,
    quality: float,
    quality_threshold: float,
) -> list[str]:
    violations: list[str] = []
    if not task.required_capabilities.issubset(model.capabilities):
        missing = sorted(task.required_capabilities - model.capabilities)
        violations.append(f"missing capabilities: {', '.join(missing)}")
    if total_tokens > model.context_window:
        violations.append(f"context window {model.context_window} below {total_tokens} tokens")
    if task.allowed_tools and not model.supports_tools:
        violations.append("tool support required")
    if not model.supports_json:
        violations.append("JSON support required")
    if not model.can_handle(task.required_capabilities, task.privacy_level):
        violations.append(f"privacy level {model.privacy_level} cannot handle {task.privacy_level}")
    if quality < quality_threshold:
        violations.append(f"quality {quality:.2f} below threshold {quality_threshold:.2f}")
    return violations


def _model_risk(quality: float, threshold: float, violations: Sequence[str]) -> float:
    quality_gap = max(0.0, threshold - quality)
    return _clamp01((1.0 - quality) + quality_gap + 0.12 * len(violations))


def _hard_violation_count(violations: Sequence[str]) -> int:
    return sum(1 for violation in violations if "quality" not in violation)


def _budget_strategies(
    *,
    case_context_budget: int,
    total_context_tokens: int,
    critical_tokens: int,
    total_input: int,
    total_output: int,
    estimated_cost: float,
    active_profiles: Sequence[DecisionQualityProfile],
    preference_profile: PreferenceProfile | None,
) -> list[BudgetStrategy]:
    strategy_specs = [
        ("frugal", 0.45, 0.74, 0.78, 0.24, 0.58, 0.58),
        ("balanced", 0.70, 0.84, 0.84, 0.12, 0.74, 0.78),
        ("rich_context", 1.00, 0.90, 0.80, 0.08, 0.88, 0.95),
        ("quality_guard", 0.85, 0.96, 0.95, 0.03, 0.90, 0.88),
        ("critical_only", 0.30, 0.72, 0.90, 0.18, 0.68, 0.35),
    ]
    profile_bonus = min(0.18, _profile_count(active_profiles, {DecisionArea.TOKEN_FIREWALL}) * 0.06)
    preference_bonus = 0.0
    if preference_profile is not None and ObjectiveDimension.SAFETY in preference_profile.priorities:
        preference_bonus += 0.06
    results: list[BudgetStrategy] = []
    for name, context_fraction, quality, safety, quality_risk, alignment, cost_multiplier in strategy_specs:
        context_tokens = int(min(total_context_tokens, max(critical_tokens, case_context_budget * context_fraction)))
        missing_critical = 1.0 if critical_tokens > context_tokens else 0.0
        token_usage = total_input + total_output + context_tokens
        results.append(
            {
                "name": name,
                "quality_preservation": _clamp01(quality + (profile_bonus if name == "quality_guard" else 0.0)),
                "safety": _clamp01(safety + preference_bonus),
                "profile_alignment": _clamp01(alignment + profile_bonus),
                "estimated_cost": estimated_cost * cost_multiplier,
                "token_usage": token_usage,
                "quality_risk": quality_risk,
                "missing_critical": missing_critical,
                "context_token_target": context_tokens,
            }
        )
    return results


def _fixture_cost_estimate(case: BenchmarkCase) -> float:
    if not case.model_profiles:
        return 0.0
    model = max(case.model_profiles, key=lambda item: item.quality_scores.get("general", 0.0))
    input_tokens = sum(task.estimated_input_tokens for task in case.tasks)
    output_tokens = sum(task.estimated_output_tokens for task in case.tasks)
    return model.estimated_cost(input_tokens, output_tokens)


def _redundancy_score(first: ContextCandidate, second: ContextCandidate) -> float:
    first_redundant = _metadata_list(first, "redundant_with")
    second_redundant = _metadata_list(second, "redundant_with")
    if second.id in first_redundant or first.id in second_redundant:
        return 1.0
    first_words = _content_words(first.content)
    second_words = _content_words(second.content)
    if not first_words or not second_words:
        return 0.0
    overlap = len(first_words.intersection(second_words)) / len(first_words.union(second_words))
    return overlap if overlap >= 0.55 else 0.0


def _content_words(content: str) -> set[str]:
    return {
        word
        for word in "".join(character.lower() if character.isalnum() else " " for character in content).split()
        if len(word) > 4
    }


def _metadata_list(candidate: ContextCandidate, key: str) -> list[str]:
    value = candidate.metadata.get(key, [])
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _profile_count(
    profiles: Sequence[DecisionQualityProfile],
    areas: set[DecisionArea],
) -> int:
    return sum(
        1
        for profile in profiles
        if profile.status != ProfileStatus.ARCHIVED and profile.decision_area in areas
    )


def _is_failure_memory_context(candidate: ContextCandidate) -> bool:
    metadata = candidate.metadata
    tags_value = metadata.get("tags", [])
    tags = {str(tag).lower() for tag in tags_value} if isinstance(tags_value, list) else set()
    memory_type = str(metadata.get("memory_type", "")).lower()
    return (
        candidate.id.lower().startswith("failure")
        or memory_type == "failure"
        or "failure" in tags
    )


def _privacy_score(level: PrivacyLevel) -> float:
    return {
        PrivacyLevel.PUBLIC: 0.25,
        PrivacyLevel.INTERNAL: 0.5,
        PrivacyLevel.PRIVATE: 0.75,
        PrivacyLevel.SECRET: 1.0,
    }[level]


def _clamp01(value: float) -> float:
    return min(1.0, max(0.0, value))
