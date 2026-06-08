"""High-level Pareto analysis helpers for benchmarks and traces."""

from __future__ import annotations

from collections.abc import Sequence

from hephaestus.benchmarks.schemas import BenchmarkCase
from hephaestus.core.config import DEFAULT_CONFIG
from hephaestus.decision.schemas import (
    DecisionAlternative,
    DecisionMetric,
    OptimizationDecision,
    metric,
)
from hephaestus.models import fake_model_profiles
from hephaestus.optimize.model_router import ModelRouteRequest
from hephaestus.pareto.schemas import (
    DecisionCandidate,
    ObjectiveDimension,
    ParetoSelectionResult,
    PreferenceProfile,
)
from hephaestus.pareto.scorer import (
    generate_context_packing_candidates,
    generate_model_routing_candidates,
    generate_scheduler_candidates,
)
from hephaestus.pareto.selector import select_candidate
from hephaestus.policy_learning import apply_model_router_profiles
from hephaestus.policy_learning.schemas import DecisionQualityProfile


def compare_benchmark_case(
    case: BenchmarkCase,
    preference_profile: PreferenceProfile,
    *,
    run_id: str | None = None,
    active_profiles: Sequence[DecisionQualityProfile] | None = None,
    source_decision_trace_ids: Sequence[str] | None = None,
) -> list[ParetoSelectionResult]:
    """Generate Pareto frontiers for benchmark model, context, and scheduler surfaces."""

    profile_list = list(active_profiles or [])
    source_trace_ids = list(source_decision_trace_ids or [])
    selections: list[ParetoSelectionResult] = []

    scheduler_candidates = generate_scheduler_candidates(
        case.tasks,
        DEFAULT_CONFIG.objective_weights,
        active_profiles=profile_list,
        source_decision_trace_ids=source_trace_ids,
    )
    selections.append(
        select_candidate(
            scheduler_candidates,
            preference_profile,
            run_id=run_id,
            title=f"{case.id}: scheduler tradeoff frontier",
        )
    )

    if case.context_candidates:
        context_candidates = generate_context_packing_candidates(
            case.context_candidates,
            case.context_token_budget,
            active_profiles=profile_list,
            source_decision_trace_ids=source_trace_ids,
        )
        selections.append(
            select_candidate(
                context_candidates,
                preference_profile,
                run_id=run_id,
                title=f"{case.id}: context packing frontier",
            )
        )

    model_profiles = case.model_profiles or fake_model_profiles()
    for task in case.tasks:
        threshold = case.quality_thresholds.get(task.id, case.quality_threshold)
        route_request = ModelRouteRequest(
            required_capabilities=task.required_capabilities,
            input_tokens=task.estimated_input_tokens,
            output_tokens=task.estimated_output_tokens,
            quality_threshold=threshold,
            privacy_level=task.privacy_level,
            needs_tools=bool(task.allowed_tools),
            needs_json=True,
            profiles=model_profiles,
        )
        adjusted_request, _ = apply_model_router_profiles(route_request, profile_list)
        model_candidates = generate_model_routing_candidates(
            adjusted_request,
            active_profiles=profile_list,
            task_id=task.id,
            source_decision_trace_ids=source_trace_ids,
        )
        selections.append(
            select_candidate(
                model_candidates,
                preference_profile,
                run_id=run_id,
                title=f"{case.id}: model route frontier for {task.id}",
            )
        )

    return selections


def build_pareto_selection_trace(
    selection: ParetoSelectionResult,
    run_id: str,
    *,
    parent_id: str | None = None,
) -> OptimizationDecision:
    """Represent a Pareto selection as an explainable optimization decision trace."""

    frontier = selection.frontier
    selected = selection.selected_candidate
    return OptimizationDecision(
        run_id=run_id,
        phase="pareto",
        selected_option=selected.label,
        alternatives=_candidate_alternatives(selection),
        rationale=selection.tradeoff_explanation.summary,
        metrics=[
            metric("frontier_id", frontier.id),
            metric("candidate_type", selected.candidate_type.value),
            metric("candidate_count", len(frontier.candidates)),
            metric("frontier_count", len(frontier.frontier_candidate_ids)),
            metric("dominated_count", selection.dominated_candidate_count),
            metric("preference_profile", selection.preference_profile.id),
            metric("selected_quality", selected.objective_vector.quality, higher_is_better=True),
            metric("selected_cost", selected.objective_vector.cost, unit="USD", higher_is_better=False),
            metric("selected_risk", selected.objective_vector.risk, higher_is_better=False),
            metric("selected_safety", selected.objective_vector.safety, higher_is_better=True),
        ],
        objective_score=selection.candidate_scores.get(selected.id),
        confidence=selected.objective_vector.confidence,
        constraints_considered=[
            "candidate constraint satisfaction",
            "Pareto non-dominance",
            *[f"{dimension.value} ({_direction_text(dimension)})" for dimension in frontier.dimensions],
        ],
        tags=["pareto", "tradeoff-frontier", selected.candidate_type.value],
        caused_by=[
            f"pareto_frontier:{frontier.id}",
            *selected.source_decision_trace_ids,
        ],
        will_affect=[
            "final_recommendation",
            "tradeoff_explanation",
            "decision_quality_learning",
        ],
        learning_hooks=[
            "pareto_selection_outcome",
            "tradeoff_weight_learning",
            "qubo_formulation_future",
        ],
        parent_id=parent_id,
    )


def _candidate_alternatives(
    selection: ParetoSelectionResult,
) -> list[DecisionAlternative]:
    alternatives: list[DecisionAlternative] = []
    frontier_ids = set(selection.frontier.frontier_candidate_ids)
    for candidate in selection.frontier.candidates:
        if candidate.id == selection.selected_candidate.id:
            continue
        reason = _candidate_rejection_reason(candidate, frontier_ids, selection)
        alternatives.append(
            DecisionAlternative(
                option_id=candidate.id,
                option_name=candidate.label,
                score=selection.candidate_scores.get(candidate.id),
                rejection_reason=reason,
                violated_constraints=candidate.violated_constraints,
                metrics=_candidate_metrics(candidate),
                would_have_cost=candidate.estimated_cost,
                expected_quality=candidate.objective_vector.quality,
                risk=candidate.objective_vector.risk,
            )
        )
    return alternatives


def _candidate_rejection_reason(
    candidate: DecisionCandidate,
    frontier_ids: set[str],
    selection: ParetoSelectionResult,
) -> str:
    if not candidate.constraints_satisfied:
        return "constraint violation: " + (", ".join(candidate.violated_constraints) or "invalid")
    if candidate.id not in frontier_ids:
        return "Pareto dominated by another valid candidate"
    return f"lower {selection.preference_profile.id} preference score than selected candidate"


def _candidate_metrics(candidate: DecisionCandidate) -> list[DecisionMetric]:
    vector = candidate.objective_vector
    return [
        metric("quality", vector.quality, higher_is_better=True),
        metric("cost", vector.cost, unit="USD", higher_is_better=False),
        metric("latency", vector.latency, higher_is_better=False),
        metric("risk", vector.risk, higher_is_better=False),
        metric("privacy", vector.privacy, higher_is_better=True),
        metric("token_usage", vector.token_usage, unit="tokens", higher_is_better=False),
        metric("confidence", vector.confidence, higher_is_better=True),
        metric("safety", vector.safety, higher_is_better=True),
        metric("profile_alignment", vector.profile_alignment, higher_is_better=True),
    ]


def _direction_text(dimension: ObjectiveDimension) -> str:
    if dimension in {
        ObjectiveDimension.QUALITY,
        ObjectiveDimension.PRIVACY,
        ObjectiveDimension.CONFIDENCE,
        ObjectiveDimension.SAFETY,
        ObjectiveDimension.PROFILE_ALIGNMENT,
    }:
        return "maximize"
    return "minimize"
