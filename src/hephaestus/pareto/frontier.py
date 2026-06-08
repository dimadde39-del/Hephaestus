"""Pareto dominance and frontier ranking."""

from __future__ import annotations

from collections.abc import Sequence

from pydantic import BaseModel, ConfigDict, Field

from hephaestus.pareto.schemas import (
    DEFAULT_DIMENSIONS,
    DecisionCandidate,
    ObjectiveDimension,
    ObjectiveDirection,
    ParetoComparison,
    PreferenceProfile,
    direction_for,
)

_EPSILON = 1e-12


class RankedCandidate(BaseModel):
    """Candidate plus scalarized rank score for a preference profile."""

    model_config = ConfigDict(frozen=True)

    candidate: DecisionCandidate
    score: float
    threshold_penalty: float = Field(default=0.0, ge=0.0)


def is_dominated(
    candidate_a: DecisionCandidate,
    candidate_b: DecisionCandidate,
    dimensions: Sequence[ObjectiveDimension] | None = None,
) -> bool:
    """Return True when candidate_b Pareto-dominates candidate_a."""

    relevant_dimensions = list(dimensions or DEFAULT_DIMENSIONS)
    strictly_better = False
    for dimension in relevant_dimensions:
        a_value = candidate_a.objective_vector.value_for(dimension)
        b_value = candidate_b.objective_vector.value_for(dimension)
        direction = direction_for(dimension)
        if direction == ObjectiveDirection.MAXIMIZE:
            if b_value + _EPSILON < a_value:
                return False
            if b_value > a_value + _EPSILON:
                strictly_better = True
        else:
            if b_value > a_value + _EPSILON:
                return False
            if b_value + _EPSILON < a_value:
                strictly_better = True
    return strictly_better


def compute_frontier(
    candidates: Sequence[DecisionCandidate],
    dimensions: Sequence[ObjectiveDimension] | None = None,
) -> list[DecisionCandidate]:
    """Return all non-dominated candidates in deterministic input order."""

    candidate_list = list(candidates)
    relevant_dimensions = list(dimensions or DEFAULT_DIMENSIONS)
    frontier: list[DecisionCandidate] = []
    for candidate in candidate_list:
        dominated = any(
            other.id != candidate.id and is_dominated(candidate, other, relevant_dimensions)
            for other in candidate_list
        )
        if not dominated:
            frontier.append(candidate)
    return frontier


def dominance_comparisons(
    candidates: Sequence[DecisionCandidate],
    dimensions: Sequence[ObjectiveDimension] | None = None,
) -> list[ParetoComparison]:
    """Build candidate-by-candidate dominance relationships."""

    candidate_list = list(candidates)
    relevant_dimensions = list(dimensions or DEFAULT_DIMENSIONS)
    comparisons: list[ParetoComparison] = []
    for candidate in candidate_list:
        dominates: list[str] = []
        dominated_by: list[str] = []
        for other in candidate_list:
            if other.id == candidate.id:
                continue
            if is_dominated(other, candidate, relevant_dimensions):
                dominates.append(other.id)
            if is_dominated(candidate, other, relevant_dimensions):
                dominated_by.append(other.id)
        if dominated_by:
            reason = f"Dominated by {', '.join(sorted(dominated_by))}."
        elif dominates:
            reason = f"On frontier; dominates {', '.join(sorted(dominates))}."
        else:
            reason = "On frontier; no candidate is at least as good across all dimensions."
        comparisons.append(
            ParetoComparison(
                candidate_id=candidate.id,
                dominates=sorted(dominates),
                dominated_by=sorted(dominated_by),
                is_frontier=not dominated_by,
                reason=reason,
            )
        )
    return comparisons


def rank_frontier(
    candidates: Sequence[DecisionCandidate],
    preference_profile: PreferenceProfile,
    dimensions: Sequence[ObjectiveDimension] | None = None,
) -> list[RankedCandidate]:
    """Rank frontier candidates with weighted normalized objectives."""

    candidate_list = list(candidates)
    relevant_dimensions = list(dimensions or DEFAULT_DIMENSIONS)
    ranges = _dimension_ranges(candidate_list, relevant_dimensions)
    ranked: list[RankedCandidate] = []
    for candidate in candidate_list:
        weighted_total = 0.0
        weight_total = 0.0
        for dimension in relevant_dimensions:
            weight = preference_profile.weight_for(dimension)
            if weight <= 0:
                continue
            weighted_total += weight * _normalized_value(candidate, dimension, ranges[dimension])
            weight_total += weight
        base_score = weighted_total / weight_total if weight_total else 0.0
        penalty = _threshold_penalty(candidate, preference_profile)
        ranked.append(
            RankedCandidate(
                candidate=candidate,
                score=base_score - penalty,
                threshold_penalty=penalty,
            )
        )
    return sorted(
        ranked,
        key=lambda item: (-item.score, item.threshold_penalty, item.candidate.id),
    )


def candidate_satisfies_preference_thresholds(
    candidate: DecisionCandidate,
    preference_profile: PreferenceProfile,
) -> bool:
    """Return whether a candidate satisfies hard thresholds for a preference profile."""

    return _threshold_penalty(candidate, preference_profile) == 0.0


def _dimension_ranges(
    candidates: Sequence[DecisionCandidate],
    dimensions: Sequence[ObjectiveDimension],
) -> dict[ObjectiveDimension, tuple[float, float]]:
    ranges: dict[ObjectiveDimension, tuple[float, float]] = {}
    for dimension in dimensions:
        values = [candidate.objective_vector.value_for(dimension) for candidate in candidates]
        if not values:
            ranges[dimension] = (0.0, 0.0)
        else:
            ranges[dimension] = (min(values), max(values))
    return ranges


def _normalized_value(
    candidate: DecisionCandidate,
    dimension: ObjectiveDimension,
    value_range: tuple[float, float],
) -> float:
    minimum, maximum = value_range
    value = candidate.objective_vector.value_for(dimension)
    if maximum - minimum <= _EPSILON:
        return 1.0
    if direction_for(dimension) == ObjectiveDirection.MAXIMIZE:
        return (value - minimum) / (maximum - minimum)
    return (maximum - value) / (maximum - minimum)


def _threshold_penalty(
    candidate: DecisionCandidate,
    preference_profile: PreferenceProfile,
) -> float:
    penalty = 0.0
    for dimension, minimum in preference_profile.minimum_thresholds.items():
        value = candidate.objective_vector.value_for(dimension)
        if value < minimum:
            penalty += minimum - value
    for dimension, maximum in preference_profile.maximum_thresholds.items():
        value = candidate.objective_vector.value_for(dimension)
        if value > maximum:
            denominator = max(abs(maximum), 1.0)
            penalty += (value - maximum) / denominator
    return penalty
