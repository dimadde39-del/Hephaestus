"""Candidate generation and multi-objective scoring."""

from __future__ import annotations

from collections.abc import Sequence

from hephaestus.core.config import DEFAULT_CONFIG, ObjectiveWeights, PrivacyLevel
from hephaestus.models.base import ModelProfile
from hephaestus.optimize.context_packer import (
    ContextCandidate,
    ContextPackResult,
    ExcludedContext,
    pack_context,
)
from hephaestus.optimize.greedy import SchedulerResult, schedule_greedy
from hephaestus.optimize.model_router import ModelRouteRequest
from hephaestus.optimize.task_scheduler import compare_schedulers
from hephaestus.pareto.schemas import CandidateType, DecisionCandidate, ObjectiveVector
from hephaestus.policy_learning import (
    apply_context_packer_profiles,
    apply_failure_memory_context_boost,
    apply_scheduler_profiles,
)
from hephaestus.policy_learning.schemas import (
    DecisionArea,
    DecisionQualityProfile,
    ProfileRuleType,
    ProfileStatus,
)
from hephaestus.spec.tasks import Task


def generate_model_routing_candidates(
    request: ModelRouteRequest,
    *,
    active_profiles: Sequence[DecisionQualityProfile] | None = None,
    task_id: str | None = None,
    source_decision_trace_ids: Sequence[str] | None = None,
) -> list[DecisionCandidate]:
    """Create one Pareto candidate per model profile, including rejected models."""

    profile_list = list(active_profiles or [])
    total_tokens = request.input_tokens + request.output_tokens
    candidates: list[DecisionCandidate] = []
    for profile in sorted(request.profiles, key=lambda item: item.identifier):
        quality = profile.quality_for(request.required_capabilities)
        cost = profile.estimated_cost(request.input_tokens, request.output_tokens)
        violated_constraints = _model_violations(profile, request, total_tokens, quality)
        constraints_satisfied = not violated_constraints
        risk = _model_risk(quality, request.quality_threshold, violated_constraints, profile, request)
        profile_alignment = _model_profile_alignment(profile, request, profile_list)
        if profile_alignment < 0.4:
            risk = min(1.0, risk + 0.12)
        candidate_id = _candidate_id(
            "model",
            *(["task", task_id] if task_id is not None else []),
            profile.provider,
            profile.model,
        )
        candidates.append(
            DecisionCandidate(
                id=candidate_id,
                candidate_type=CandidateType.MODEL_ROUTE,
                label=profile.identifier if task_id is None else f"{task_id}: {profile.identifier}",
                objective_vector=ObjectiveVector(
                    quality=quality,
                    cost=cost,
                    latency=max(0.0, 1.0 - profile.latency_score),
                    risk=risk,
                    privacy=_privacy_score(profile.privacy_level),
                    token_usage=float(total_tokens),
                    confidence=_confidence_from_quality(quality, risk, constraints_satisfied),
                    safety=max(0.0, 1.0 - risk),
                    profile_alignment=profile_alignment,
                ),
                constraints_satisfied=constraints_satisfied,
                violated_constraints=violated_constraints,
                estimated_cost=cost,
                estimated_tokens=total_tokens,
                rationale=_model_candidate_rationale(profile, quality, cost, violated_constraints),
                source_decision_trace_ids=list(source_decision_trace_ids or []),
                source_profile_ids=_active_profile_ids(profile_list),
                tags=["model-routing", profile.provider, profile.model, *sorted(profile.capabilities)],
                metadata={
                    "provider": profile.provider,
                    "model": profile.model,
                    "task_id": task_id or "",
                    "quality_threshold": request.quality_threshold,
                    "latency_score": profile.latency_score,
                },
            )
        )
    return candidates


def generate_context_packing_candidates(
    candidates: Sequence[ContextCandidate],
    token_budget: int,
    *,
    active_profiles: Sequence[DecisionQualityProfile] | None = None,
    source_decision_trace_ids: Sequence[str] | None = None,
) -> list[DecisionCandidate]:
    """Generate practical context packing strategy candidates."""

    source_candidates = list(candidates)
    profile_list = list(active_profiles or [])
    settings, _ = apply_context_packer_profiles(profile_list)
    adjusted_candidates = apply_failure_memory_context_boost(source_candidates, settings)
    strategies = [
        ("minimal", max(1, int(token_budget * 0.45)), True, settings.failure_memory_importance_boost),
        ("balanced", max(1, int(token_budget * 0.7)), True, settings.failure_memory_importance_boost),
        ("rich", token_budget, True, settings.failure_memory_importance_boost),
        ("critical_only", token_budget, True, settings.failure_memory_importance_boost),
        (
            "failure_memory_heavy",
            token_budget,
            True,
            min(1.0, settings.failure_memory_importance_boost + 0.25),
        ),
    ]
    results: list[DecisionCandidate] = []
    for strategy, strategy_budget, preserve_critical, failure_boost in strategies:
        strategy_candidates = adjusted_candidates
        if strategy == "failure_memory_heavy":
            strategy_candidates = _boost_failure_memory_items(adjusted_candidates, 0.25)
        if strategy == "critical_only":
            packed = _pack_critical_only(strategy_candidates, strategy_budget)
        else:
            packed = pack_context(
                strategy_candidates,
                strategy_budget,
                preserve_critical_context=preserve_critical,
                failure_memory_importance_boost=failure_boost,
                compression_aggressiveness=settings.compression_aggressiveness,
            )
        results.append(
            _context_candidate(
                strategy,
                packed,
                source_candidates,
                token_budget,
                profile_list,
                source_decision_trace_ids=list(source_decision_trace_ids or []),
            )
        )
    return results


def generate_scheduler_candidates(
    tasks: Sequence[Task],
    weights: ObjectiveWeights | None = None,
    *,
    active_profiles: Sequence[DecisionQualityProfile] | None = None,
    source_decision_trace_ids: Sequence[str] | None = None,
) -> list[DecisionCandidate]:
    """Generate scheduler strategy candidates for a task graph."""

    task_list = list(tasks)
    base_weights = weights or DEFAULT_CONFIG.objective_weights
    greedy = schedule_greedy(task_list, base_weights)
    comparison = compare_schedulers(task_list, base_weights)
    scheduler_results: list[tuple[str, SchedulerResult, bool]] = [
        ("greedy", greedy, False),
        ("annealing", comparison.annealed, False),
    ]
    profile_list = list(active_profiles or [])
    if profile_list:
        adjusted_weights, _ = apply_scheduler_profiles(base_weights, profile_list)
        profile_comparison = compare_schedulers(task_list, adjusted_weights)
        selected = (
            profile_comparison.annealed
            if profile_comparison.annealed.score >= profile_comparison.greedy.score
            else profile_comparison.greedy
        )
        scheduler_results.append(("profile_adjusted", selected, True))

    score_values = [result.score for _, result, _ in scheduler_results]
    minimum_score = min(score_values) if score_values else 0.0
    maximum_score = max(score_values) if score_values else 0.0
    return [
        _scheduler_candidate(
            name,
            result,
            task_list,
            profile_adjusted=profile_adjusted,
            minimum_score=minimum_score,
            maximum_score=maximum_score,
            active_profiles=profile_list,
            source_decision_trace_ids=list(source_decision_trace_ids or []),
        )
        for name, result, profile_adjusted in scheduler_results
    ]


def _model_violations(
    profile: ModelProfile,
    request: ModelRouteRequest,
    total_tokens: int,
    quality: float,
) -> list[str]:
    violations: list[str] = []
    if not request.required_capabilities.issubset(profile.capabilities):
        missing = sorted(request.required_capabilities - profile.capabilities)
        violations.append(f"missing capabilities: {', '.join(missing)}")
    avoided_tags = _matched_tags(profile, request.avoided_model_tags)
    if avoided_tags:
        violations.append(f"avoided by active profile: {', '.join(avoided_tags)}")
    if total_tokens > profile.context_window:
        violations.append(f"context window {profile.context_window} below {total_tokens} tokens")
    if request.needs_tools and not profile.supports_tools:
        violations.append("tool support required")
    if request.needs_json and not profile.supports_json:
        violations.append("JSON support required")
    if not profile.can_handle(request.required_capabilities, request.privacy_level):
        violations.append(f"privacy level {profile.privacy_level} cannot handle {request.privacy_level}")
    if quality < request.quality_threshold:
        violations.append(f"quality {quality:.2f} below threshold {request.quality_threshold:.2f}")
    return violations


def _model_risk(
    quality: float,
    threshold: float,
    violated_constraints: Sequence[str],
    profile: ModelProfile,
    request: ModelRouteRequest,
) -> float:
    quality_gap = max(0.0, threshold - quality)
    constraint_pressure = min(0.6, len(violated_constraints) * 0.14)
    privacy_pressure = 0.0 if profile.can_handle(request.required_capabilities, request.privacy_level) else 0.2
    return min(1.0, max(0.0, 1.0 - quality) + quality_gap + constraint_pressure + privacy_pressure)


def _model_profile_alignment(
    profile: ModelProfile,
    request: ModelRouteRequest,
    active_profiles: Sequence[DecisionQualityProfile],
) -> float:
    alignment = 0.58
    if _matched_tags(profile, request.preferred_model_tags):
        alignment += 0.25
    if _matched_tags(profile, request.avoided_model_tags):
        alignment -= 0.35
    for decision_profile in active_profiles:
        if decision_profile.status == ProfileStatus.ARCHIVED:
            continue
        if decision_profile.decision_area != DecisionArea.MODEL_ROUTER:
            continue
        alignment += 0.05 * decision_profile.confidence
        for rule in decision_profile.rules:
            if rule.rule_type == ProfileRuleType.MODEL_PREFERENCE and _matched_tags(
                profile,
                set(rule.prefer_model_tags),
            ):
                alignment += 0.15
            if _matched_tags(profile, set(rule.avoid_model_tags)):
                alignment -= 0.25
            if rule.minimum_quality_score is not None:
                quality = profile.quality_for(request.required_capabilities)
                if quality >= rule.minimum_quality_score:
                    alignment += 0.08
                else:
                    alignment -= 0.08
    return _clamp01(alignment)


def _model_candidate_rationale(
    profile: ModelProfile,
    quality: float,
    cost: float,
    violated_constraints: Sequence[str],
) -> str:
    if violated_constraints:
        return (
            f"{profile.identifier} has quality {quality:.2f} at ${cost:.6f}, "
            f"but violates: {', '.join(violated_constraints)}."
        )
    return f"{profile.identifier} is valid with quality {quality:.2f} at ${cost:.6f}."


def _context_candidate(
    strategy: str,
    result: ContextPackResult,
    all_candidates: Sequence[ContextCandidate],
    token_budget: int,
    active_profiles: Sequence[DecisionQualityProfile],
    *,
    source_decision_trace_ids: list[str],
) -> DecisionCandidate:
    total_value = sum(_context_value(candidate) for candidate in all_candidates)
    selected_value = sum(_context_value(candidate) for candidate in result.selected)
    quality = min(1.0, selected_value / total_value) if total_value > 0 else 0.0
    critical_missing = _missing_critical_items(all_candidates, result.selected, token_budget)
    risk = _context_risk(quality, critical_missing, result.used_tokens, token_budget)
    profile_alignment = _context_profile_alignment(strategy, result.selected, active_profiles)
    violated = ["critical context missing"] if critical_missing else []
    if result.used_tokens > token_budget:
        violated.append("token budget exceeded")
    return DecisionCandidate(
        id=_candidate_id("context", strategy),
        candidate_type=CandidateType.CONTEXT_PACK,
        label=strategy.replace("_", " "),
        objective_vector=ObjectiveVector(
            quality=quality,
            cost=result.used_tokens * 0.0000002,
            latency=max(0.0, len(result.selected) * 0.02),
            risk=risk,
            privacy=1.0,
            token_usage=float(result.used_tokens),
            confidence=0.86 if not violated else 0.58,
            safety=max(0.0, 1.0 - risk),
            profile_alignment=profile_alignment,
        ),
        constraints_satisfied=not violated,
        violated_constraints=violated,
        estimated_cost=result.used_tokens * 0.0000002,
        estimated_tokens=result.used_tokens,
        rationale=(
            f"{strategy.replace('_', ' ')} selected {len(result.selected)}/"
            f"{len(all_candidates)} context items using {result.used_tokens}/{token_budget} tokens."
        ),
        source_decision_trace_ids=source_decision_trace_ids,
        source_profile_ids=_active_profile_ids(active_profiles),
        tags=["context-packing", strategy],
        metadata={
            "strategy": strategy,
            "selected_context_ids": [item.id for item in result.selected],
            "excluded_context": [f"{item.id}: {item.reason}" for item in result.excluded],
            "token_budget": token_budget,
            "score": result.score,
        },
    )


def _pack_critical_only(
    candidates: Sequence[ContextCandidate],
    token_budget: int,
) -> ContextPackResult:
    selected: list[ContextCandidate] = []
    excluded: list[ExcludedContext] = []
    used_tokens = 0
    critical = sorted(
        [candidate for candidate in candidates if candidate.critical],
        key=lambda item: (item.token_cost, -_context_value(item), item.id),
    )
    for item in critical:
        if used_tokens + item.token_cost <= token_budget:
            selected.append(item)
            used_tokens += item.token_cost
        else:
            excluded.append(ExcludedContext(id=item.id, reason="critical item did not fit token budget"))
    selected_ids = {item.id for item in selected}
    for item in candidates:
        if item.id not in selected_ids:
            excluded.append(ExcludedContext(id=item.id, reason="not part of critical-only strategy"))
    return ContextPackResult(
        selected=selected,
        excluded=excluded,
        used_tokens=used_tokens,
        score=sum(_context_value(item) for item in selected),
        explanation=f"Selected only critical context into {used_tokens}/{token_budget} tokens.",
    )


def _scheduler_candidate(
    name: str,
    result: SchedulerResult,
    tasks: Sequence[Task],
    *,
    profile_adjusted: bool,
    minimum_score: float,
    maximum_score: float,
    active_profiles: Sequence[DecisionQualityProfile],
    source_decision_trace_ids: list[str],
) -> DecisionCandidate:
    task_count = len(tasks)
    dependency_violations = result.breakdown.dependency_violations
    total_tokens = sum(task.estimated_total_tokens for task in result.order)
    max_task_risk = max((task.risk for task in result.order), default=0.0)
    risk = min(1.0, max_task_risk + dependency_violations * 0.2)
    score_span = maximum_score - minimum_score
    quality = 1.0 if score_span <= 0 else (result.score - minimum_score) / score_span
    profile_alignment = 0.88 if profile_adjusted else (0.58 if active_profiles else 0.65)
    order = [task.id for task in result.order]
    return DecisionCandidate(
        id=_candidate_id("scheduler", name),
        candidate_type=CandidateType.TASK_ORDER,
        label=name.replace("_", " "),
        objective_vector=ObjectiveVector(
            quality=_clamp01(quality),
            cost=total_tokens * 0.0000002,
            latency=float(task_count + dependency_violations * 2),
            risk=risk,
            privacy=1.0,
            token_usage=float(total_tokens),
            confidence=0.84 if dependency_violations == 0 else 0.64,
            safety=max(0.0, 1.0 - risk),
            profile_alignment=profile_alignment,
        ),
        constraints_satisfied=dependency_violations == 0,
        violated_constraints=["dependency order"] if dependency_violations else [],
        estimated_cost=total_tokens * 0.0000002,
        estimated_tokens=total_tokens,
        rationale=(
            f"{name.replace('_', ' ')} produced score {result.score:.2f} "
            f"with {dependency_violations} dependency violations."
        ),
        source_decision_trace_ids=source_decision_trace_ids,
        source_profile_ids=_active_profile_ids(active_profiles),
        tags=["scheduler", name, *(["profile-adjusted"] if profile_adjusted else [])],
        metadata={
            "order": order,
            "score": result.score,
            "dependency_violations": dependency_violations,
        },
    )


def _context_value(item: ContextCandidate) -> float:
    return item.relevance * 2.0 + item.importance * 1.5 + (1.0 if item.critical else 0.0)


def _context_risk(
    quality: float,
    critical_missing: Sequence[str],
    used_tokens: int,
    token_budget: int,
) -> float:
    overage = max(0, used_tokens - token_budget)
    overage_risk = overage / max(1, token_budget)
    return _clamp01((1.0 - quality) * 0.55 + len(critical_missing) * 0.22 + overage_risk)


def _missing_critical_items(
    candidates: Sequence[ContextCandidate],
    selected: Sequence[ContextCandidate],
    token_budget: int,
) -> list[str]:
    selected_ids = {item.id for item in selected}
    return [
        item.id
        for item in candidates
        if item.critical and item.token_cost <= token_budget and item.id not in selected_ids
    ]


def _context_profile_alignment(
    strategy: str,
    selected: Sequence[ContextCandidate],
    active_profiles: Sequence[DecisionQualityProfile],
) -> float:
    alignment = 0.62
    context_profile_count = sum(
        1
        for profile in active_profiles
        if profile.status != ProfileStatus.ARCHIVED
        and profile.decision_area in {DecisionArea.CONTEXT_PACKER, DecisionArea.MEMORY_RETRIEVAL}
    )
    if context_profile_count:
        alignment += 0.08 * context_profile_count
    if strategy == "failure_memory_heavy" and any(_is_failure_memory_context(item) for item in selected):
        alignment += 0.25
    if strategy == "critical_only":
        alignment += 0.08
    return _clamp01(alignment)


def _boost_failure_memory_items(
    candidates: Sequence[ContextCandidate],
    boost: float,
) -> list[ContextCandidate]:
    adjusted: list[ContextCandidate] = []
    for candidate in candidates:
        if _is_failure_memory_context(candidate):
            adjusted.append(
                candidate.model_copy(update={"importance": min(1.0, candidate.importance + boost)})
            )
        else:
            adjusted.append(candidate)
    return adjusted


def _is_failure_memory_context(item: ContextCandidate) -> bool:
    metadata = item.metadata
    tags_value = metadata.get("tags", [])
    tags = {str(tag).lower() for tag in tags_value} if isinstance(tags_value, list) else set()
    memory_type = str(metadata.get("memory_type", "")).lower()
    return item.id.lower().startswith("failure") or memory_type == "failure" or "failure" in tags


def _privacy_score(level: PrivacyLevel) -> float:
    return {
        PrivacyLevel.PUBLIC: 0.25,
        PrivacyLevel.INTERNAL: 0.5,
        PrivacyLevel.PRIVATE: 0.75,
        PrivacyLevel.SECRET: 1.0,
    }[level]


def _confidence_from_quality(
    quality: float,
    risk: float,
    constraints_satisfied: bool,
) -> float:
    base = quality * 0.75 + (1.0 - risk) * 0.25
    if not constraints_satisfied:
        base *= 0.65
    return _clamp01(base)


def _matched_tags(profile: ModelProfile, tags: set[str]) -> list[str]:
    if not tags:
        return []
    normalized = {tag.lower() for tag in tags}
    profile_tags = _profile_tags(profile)
    return sorted(normalized.intersection(profile_tags))


def _profile_tags(profile: ModelProfile) -> set[str]:
    return {
        profile.identifier.lower(),
        profile.provider.lower(),
        profile.model.lower(),
        f"provider:{profile.provider}".lower(),
        f"model:{profile.model}".lower(),
        *{capability.lower() for capability in profile.capabilities},
    }


def _active_profile_ids(active_profiles: Sequence[DecisionQualityProfile]) -> list[str]:
    return [
        profile.id
        for profile in active_profiles
        if profile.status != ProfileStatus.ARCHIVED
    ]


def _candidate_id(*parts: str) -> str:
    normalized = [
        part.lower()
        .replace("/", "_")
        .replace(" ", "_")
        .replace(":", "_")
        .replace("-", "_")
        for part in parts
        if part
    ]
    return "candidate_" + "_".join(normalized)


def _clamp01(value: float) -> float:
    return min(1.0, max(0.0, value))
