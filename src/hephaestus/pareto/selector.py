"""Preference profiles and Pareto selection."""

from __future__ import annotations

from collections.abc import Sequence

from hephaestus.pareto.frontier import (
    candidate_satisfies_preference_thresholds,
    compute_frontier,
    dominance_comparisons,
    rank_frontier,
)
from hephaestus.pareto.schemas import (
    DEFAULT_DIMENSIONS,
    CandidateType,
    DecisionCandidate,
    ObjectiveDimension,
    ParetoFrontier,
    ParetoSelectionResult,
    PreferenceProfile,
    TradeoffExplanation,
)


def builtin_preference_profiles() -> dict[str, PreferenceProfile]:
    """Return built-in, inspectable Pareto selection modes."""

    return {
        "balanced": PreferenceProfile(
            id="balanced",
            label="Balanced",
            description="Moderate quality, cost, latency, risk, privacy, safety, and profile alignment.",
            weights={
                ObjectiveDimension.QUALITY: 1.2,
                ObjectiveDimension.COST: 0.9,
                ObjectiveDimension.LATENCY: 0.7,
                ObjectiveDimension.RISK: 1.0,
                ObjectiveDimension.PRIVACY: 0.8,
                ObjectiveDimension.TOKEN_USAGE: 0.8,
                ObjectiveDimension.CONFIDENCE: 1.0,
                ObjectiveDimension.SAFETY: 1.0,
                ObjectiveDimension.PROFILE_ALIGNMENT: 0.7,
            },
            minimum_thresholds={
                ObjectiveDimension.QUALITY: 0.65,
                ObjectiveDimension.SAFETY: 0.65,
            },
            priorities=[
                ObjectiveDimension.QUALITY,
                ObjectiveDimension.SAFETY,
                ObjectiveDimension.COST,
            ],
        ),
        "frugal": PreferenceProfile(
            id="frugal",
            label="Frugal",
            description="Prefer low cost and token usage while preserving basic quality and safety.",
            weights={
                ObjectiveDimension.COST: 1.6,
                ObjectiveDimension.TOKEN_USAGE: 1.5,
                ObjectiveDimension.QUALITY: 0.9,
                ObjectiveDimension.SAFETY: 0.9,
                ObjectiveDimension.RISK: 0.8,
                ObjectiveDimension.LATENCY: 0.7,
                ObjectiveDimension.CONFIDENCE: 0.6,
                ObjectiveDimension.PRIVACY: 0.5,
                ObjectiveDimension.PROFILE_ALIGNMENT: 0.5,
            },
            minimum_thresholds={
                ObjectiveDimension.QUALITY: 0.68,
                ObjectiveDimension.SAFETY: 0.7,
            },
            priorities=[
                ObjectiveDimension.COST,
                ObjectiveDimension.TOKEN_USAGE,
                ObjectiveDimension.QUALITY,
            ],
        ),
        "quality_first": PreferenceProfile(
            id="quality_first",
            label="Quality First",
            description="Prefer the highest quality and confidence even when cost rises.",
            weights={
                ObjectiveDimension.QUALITY: 2.0,
                ObjectiveDimension.CONFIDENCE: 1.5,
                ObjectiveDimension.SAFETY: 1.0,
                ObjectiveDimension.RISK: 0.8,
                ObjectiveDimension.PROFILE_ALIGNMENT: 0.7,
                ObjectiveDimension.COST: 0.4,
                ObjectiveDimension.TOKEN_USAGE: 0.4,
                ObjectiveDimension.LATENCY: 0.4,
                ObjectiveDimension.PRIVACY: 0.6,
            },
            minimum_thresholds={
                ObjectiveDimension.QUALITY: 0.78,
                ObjectiveDimension.CONFIDENCE: 0.65,
            },
            priorities=[
                ObjectiveDimension.QUALITY,
                ObjectiveDimension.CONFIDENCE,
                ObjectiveDimension.SAFETY,
            ],
        ),
        "privacy_first": PreferenceProfile(
            id="privacy_first",
            label="Privacy First",
            description="Prefer local/private choices and lower exposure risk.",
            weights={
                ObjectiveDimension.PRIVACY: 2.0,
                ObjectiveDimension.RISK: 1.2,
                ObjectiveDimension.SAFETY: 1.2,
                ObjectiveDimension.QUALITY: 0.9,
                ObjectiveDimension.CONFIDENCE: 0.8,
                ObjectiveDimension.COST: 0.6,
                ObjectiveDimension.TOKEN_USAGE: 0.6,
                ObjectiveDimension.LATENCY: 0.5,
                ObjectiveDimension.PROFILE_ALIGNMENT: 0.8,
            },
            minimum_thresholds={
                ObjectiveDimension.PRIVACY: 0.75,
                ObjectiveDimension.SAFETY: 0.7,
            },
            priorities=[
                ObjectiveDimension.PRIVACY,
                ObjectiveDimension.SAFETY,
                ObjectiveDimension.RISK,
            ],
        ),
        "safety_first": PreferenceProfile(
            id="safety_first",
            label="Safety First",
            description="Prefer low risk, strong safety posture, and approval-preserving strategies.",
            weights={
                ObjectiveDimension.SAFETY: 2.0,
                ObjectiveDimension.RISK: 1.8,
                ObjectiveDimension.CONFIDENCE: 1.0,
                ObjectiveDimension.QUALITY: 0.9,
                ObjectiveDimension.PRIVACY: 0.9,
                ObjectiveDimension.PROFILE_ALIGNMENT: 0.8,
                ObjectiveDimension.COST: 0.4,
                ObjectiveDimension.TOKEN_USAGE: 0.4,
                ObjectiveDimension.LATENCY: 0.4,
            },
            minimum_thresholds={
                ObjectiveDimension.SAFETY: 0.8,
                ObjectiveDimension.CONFIDENCE: 0.6,
            },
            maximum_thresholds={ObjectiveDimension.RISK: 0.35},
            priorities=[
                ObjectiveDimension.SAFETY,
                ObjectiveDimension.RISK,
                ObjectiveDimension.CONFIDENCE,
            ],
        ),
        "speed_first": PreferenceProfile(
            id="speed_first",
            label="Speed First",
            description="Prefer low latency and simpler plans while maintaining usable quality.",
            weights={
                ObjectiveDimension.LATENCY: 1.8,
                ObjectiveDimension.TOKEN_USAGE: 1.1,
                ObjectiveDimension.COST: 0.9,
                ObjectiveDimension.QUALITY: 0.9,
                ObjectiveDimension.CONFIDENCE: 0.7,
                ObjectiveDimension.SAFETY: 0.8,
                ObjectiveDimension.RISK: 0.7,
                ObjectiveDimension.PRIVACY: 0.5,
                ObjectiveDimension.PROFILE_ALIGNMENT: 0.5,
            },
            minimum_thresholds={
                ObjectiveDimension.QUALITY: 0.65,
                ObjectiveDimension.SAFETY: 0.65,
            },
            priorities=[
                ObjectiveDimension.LATENCY,
                ObjectiveDimension.TOKEN_USAGE,
                ObjectiveDimension.COST,
            ],
        ),
    }


def get_preference_profile(profile_id: str) -> PreferenceProfile:
    """Return a built-in preference profile by ID."""

    profiles = builtin_preference_profiles()
    try:
        return profiles[profile_id]
    except KeyError as error:
        valid = ", ".join(sorted(profiles))
        raise ValueError(f"Unknown Pareto preference profile '{profile_id}'. Valid: {valid}") from error


def select_candidate(
    candidates: Sequence[DecisionCandidate],
    preference_profile: PreferenceProfile,
    *,
    dimensions: Sequence[ObjectiveDimension] | None = None,
    run_id: str | None = None,
    title: str = "",
    candidate_type: CandidateType | None = None,
) -> ParetoSelectionResult:
    """Filter candidates, compute a frontier, rank it, and explain the selection."""

    all_candidates = list(candidates)
    if not all_candidates:
        raise ValueError("At least one candidate is required for Pareto selection")

    relevant_dimensions = list(dimensions or DEFAULT_DIMENSIONS)
    valid_candidates = [
        candidate
        for candidate in all_candidates
        if candidate.constraints_satisfied
        and candidate_satisfies_preference_thresholds(candidate, preference_profile)
    ]
    if not valid_candidates:
        valid_candidates = [candidate for candidate in all_candidates if candidate.constraints_satisfied]
    if not valid_candidates:
        valid_candidates = all_candidates

    frontier_candidates = compute_frontier(valid_candidates, relevant_dimensions)
    comparisons = dominance_comparisons(valid_candidates, relevant_dimensions)
    ranked = rank_frontier(frontier_candidates, preference_profile, relevant_dimensions)
    if not ranked:
        raise ValueError("No rankable candidates were produced")

    selected = ranked[0].candidate
    candidate_scores = {item.candidate.id: item.score for item in ranked}
    dominated_ids = sorted({comparison.candidate_id for comparison in comparisons if not comparison.is_frontier})
    explanation = explain_tradeoff(
        selected,
        all_candidates,
        preference_profile,
        candidate_scores=candidate_scores,
    )
    frontier = ParetoFrontier(
        run_id=run_id,
        title=title,
        candidate_type=candidate_type or _single_candidate_type(all_candidates),
        dimensions=relevant_dimensions,
        candidates=all_candidates,
        frontier_candidate_ids=[candidate.id for candidate in frontier_candidates],
        dominated_candidate_ids=dominated_ids,
        comparisons=comparisons,
        preference_profile_id=preference_profile.id,
        selected_candidate_id=selected.id,
        tradeoff_explanation=explanation,
    )
    return ParetoSelectionResult(
        frontier=frontier,
        selected_candidate=selected,
        preference_profile=preference_profile,
        ranked_candidate_ids=[item.candidate.id for item in ranked],
        candidate_scores=candidate_scores,
        valid_candidate_count=len(valid_candidates),
        dominated_candidate_count=len(dominated_ids),
        tradeoff_explanation=explanation,
    )


def explain_tradeoff(
    selected: DecisionCandidate,
    candidates: Sequence[DecisionCandidate],
    preference_profile: PreferenceProfile,
    *,
    candidate_scores: dict[str, float],
) -> TradeoffExplanation:
    """Create a concise human explanation for the selected candidate."""

    valid_others = [
        candidate
        for candidate in candidates
        if candidate.id != selected.id and candidate.constraints_satisfied
    ]
    advantages = _advantages(selected, valid_others, preference_profile)
    tradeoffs = _tradeoffs(selected, valid_others)
    rejected_notes = _rejected_notes(selected, candidates, candidate_scores)
    if tradeoffs:
        summary = f"Selected {selected.label}. It {advantages[0].lower()} but {tradeoffs[0].lower()}."
    elif advantages:
        summary = f"Selected {selected.label}. It {advantages[0].lower()}."
    else:
        summary = f"Selected {selected.label} as the best match for {preference_profile.label}."
    return TradeoffExplanation(
        selected_candidate_id=selected.id,
        selected_label=selected.label,
        preference_profile_id=preference_profile.id,
        summary=summary,
        advantages=advantages,
        tradeoffs=tradeoffs,
        rejected_candidate_notes=rejected_notes,
    )


def _advantages(
    selected: DecisionCandidate,
    others: Sequence[DecisionCandidate],
    preference_profile: PreferenceProfile,
) -> list[str]:
    if not others:
        return ["was the only valid candidate"]
    advantages: list[str] = []
    for dimension in preference_profile.priorities:
        selected_value = selected.objective_vector.value_for(dimension)
        other_values = [candidate.objective_vector.value_for(dimension) for candidate in others]
        if not other_values:
            continue
        best_other = max(other_values) if _dimension_is_maximized(dimension) else min(other_values)
        if _is_better(selected_value, best_other, dimension):
            advantages.append(f"led on {dimension.value.replace('_', ' ')}")
        elif _is_close(selected_value, best_other, dimension):
            advantages.append(f"kept competitive {dimension.value.replace('_', ' ')}")
        if len(advantages) >= 3:
            break
    if selected.constraints_satisfied:
        advantages.append("satisfied the active constraints")
    return advantages or ["matched the selected preference profile"]


def _tradeoffs(
    selected: DecisionCandidate,
    others: Sequence[DecisionCandidate],
) -> list[str]:
    if not others:
        return []
    tradeoffs: list[str] = []
    selected_vector = selected.objective_vector
    cheapest_cost = min(candidate.objective_vector.cost for candidate in others)
    fastest_latency = min(candidate.objective_vector.latency for candidate in others)
    lowest_tokens = min(candidate.objective_vector.token_usage for candidate in others)
    highest_quality = max(candidate.objective_vector.quality for candidate in others)
    safest = max(candidate.objective_vector.safety for candidate in others)
    if selected_vector.cost > cheapest_cost:
        tradeoffs.append("was not the cheapest option")
    if selected_vector.latency > fastest_latency:
        tradeoffs.append("was not the fastest option")
    if selected_vector.token_usage > lowest_tokens:
        tradeoffs.append("used more tokens than the leanest option")
    if selected_vector.quality < highest_quality:
        tradeoffs.append("did not have the highest quality score")
    if selected_vector.safety < safest:
        tradeoffs.append("did not have the strongest safety score")
    return tradeoffs[:3]


def _rejected_notes(
    selected: DecisionCandidate,
    candidates: Sequence[DecisionCandidate],
    candidate_scores: dict[str, float],
) -> list[str]:
    notes: list[str] = []
    for candidate in candidates:
        if candidate.id == selected.id:
            continue
        if not candidate.constraints_satisfied:
            notes.append(
                f"{candidate.label} violated {', '.join(candidate.violated_constraints) or 'constraints'}."
            )
            continue
        score = candidate_scores.get(candidate.id)
        if score is not None:
            notes.append(f"{candidate.label} ranked below the selected frontier score ({score:.3f}).")
    return notes[:5]


def _single_candidate_type(candidates: Sequence[DecisionCandidate]) -> CandidateType | None:
    candidate_types = {candidate.candidate_type for candidate in candidates}
    if len(candidate_types) == 1:
        return next(iter(candidate_types))
    return None


def _dimension_is_maximized(dimension: ObjectiveDimension) -> bool:
    return dimension in {
        ObjectiveDimension.QUALITY,
        ObjectiveDimension.PRIVACY,
        ObjectiveDimension.CONFIDENCE,
        ObjectiveDimension.SAFETY,
        ObjectiveDimension.PROFILE_ALIGNMENT,
    }


def _is_better(value: float, baseline: float, dimension: ObjectiveDimension) -> bool:
    if _dimension_is_maximized(dimension):
        return value > baseline
    return value < baseline


def _is_close(value: float, baseline: float, dimension: ObjectiveDimension) -> bool:
    tolerance = max(abs(baseline) * 0.05, 0.01)
    if _dimension_is_maximized(dimension):
        return value + tolerance >= baseline
    return value <= baseline + tolerance
