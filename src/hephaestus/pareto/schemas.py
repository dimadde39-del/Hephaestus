"""Typed schemas for Pareto decision frontiers."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class ObjectiveDirection(StrEnum):
    """Whether an objective should be maximized or minimized."""

    MAXIMIZE = "maximize"
    MINIMIZE = "minimize"


class ObjectiveDimension(StrEnum):
    """Objective dimensions available to Pareto comparison."""

    QUALITY = "quality"
    COST = "cost"
    LATENCY = "latency"
    RISK = "risk"
    PRIVACY = "privacy"
    TOKEN_USAGE = "token_usage"
    CONFIDENCE = "confidence"
    SAFETY = "safety"
    PROFILE_ALIGNMENT = "profile_alignment"


class CandidateType(StrEnum):
    """Decision surface represented by a candidate."""

    MODEL_ROUTE = "model_route"
    CONTEXT_PACK = "context_pack"
    TASK_ORDER = "task_order"
    BUDGET_STRATEGY = "budget_strategy"
    SAFETY_STRATEGY = "safety_strategy"
    OPTIMIZER_PLAN = "optimizer_plan"


OBJECTIVE_DIRECTIONS: dict[ObjectiveDimension, ObjectiveDirection] = {
    ObjectiveDimension.QUALITY: ObjectiveDirection.MAXIMIZE,
    ObjectiveDimension.COST: ObjectiveDirection.MINIMIZE,
    ObjectiveDimension.LATENCY: ObjectiveDirection.MINIMIZE,
    ObjectiveDimension.RISK: ObjectiveDirection.MINIMIZE,
    ObjectiveDimension.PRIVACY: ObjectiveDirection.MAXIMIZE,
    ObjectiveDimension.TOKEN_USAGE: ObjectiveDirection.MINIMIZE,
    ObjectiveDimension.CONFIDENCE: ObjectiveDirection.MAXIMIZE,
    ObjectiveDimension.SAFETY: ObjectiveDirection.MAXIMIZE,
    ObjectiveDimension.PROFILE_ALIGNMENT: ObjectiveDirection.MAXIMIZE,
}

DEFAULT_DIMENSIONS: tuple[ObjectiveDimension, ...] = tuple(ObjectiveDimension)


class ObjectiveVector(BaseModel):
    """Multi-objective values for a single decision candidate."""

    model_config = ConfigDict(frozen=True)

    quality: float = Field(default=0.0, ge=0.0, le=1.0)
    cost: float = Field(default=0.0, ge=0.0)
    latency: float = Field(default=0.0, ge=0.0)
    risk: float = Field(default=0.0, ge=0.0, le=1.0)
    privacy: float = Field(default=0.0, ge=0.0, le=1.0)
    token_usage: float = Field(default=0.0, ge=0.0)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    safety: float = Field(default=0.0, ge=0.0, le=1.0)
    profile_alignment: float = Field(default=0.0, ge=0.0, le=1.0)

    def value_for(self, dimension: ObjectiveDimension) -> float:
        """Return the numeric value for one objective dimension."""

        return float(getattr(self, dimension.value))

    def values_for(self, dimensions: list[ObjectiveDimension]) -> dict[ObjectiveDimension, float]:
        """Return a dimension-keyed value map."""

        return {dimension: self.value_for(dimension) for dimension in dimensions}


class DecisionCandidate(BaseModel):
    """A candidate option before scalar collapse."""

    model_config = ConfigDict(frozen=True)

    id: str
    candidate_type: CandidateType
    label: str
    objective_vector: ObjectiveVector
    constraints_satisfied: bool = True
    violated_constraints: list[str] = Field(default_factory=list)
    estimated_cost: float = Field(default=0.0, ge=0.0)
    estimated_tokens: int = Field(default=0, ge=0)
    rationale: str = ""
    source_decision_trace_ids: list[str] = Field(default_factory=list)
    source_profile_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "violated_constraints",
        "source_decision_trace_ids",
        "source_profile_ids",
        "tags",
        mode="after",
    )
    @classmethod
    def _dedupe_text(cls, values: list[str]) -> list[str]:
        seen: set[str] = set()
        normalized: list[str] = []
        for value in values:
            text = value.strip()
            if not text or text in seen:
                continue
            seen.add(text)
            normalized.append(text)
        return normalized

    @model_validator(mode="after")
    def _constraints_match_state(self) -> DecisionCandidate:
        if self.constraints_satisfied and self.violated_constraints:
            raise ValueError("Satisfied candidates cannot include violated constraints")
        return self


class PreferenceProfile(BaseModel):
    """Inspectable selection mode for ranking a frontier."""

    model_config = ConfigDict(frozen=True)

    id: str
    label: str
    description: str
    weights: dict[ObjectiveDimension, float]
    minimum_thresholds: dict[ObjectiveDimension, float] = Field(default_factory=dict)
    maximum_thresholds: dict[ObjectiveDimension, float] = Field(default_factory=dict)
    priorities: list[ObjectiveDimension] = Field(default_factory=list)

    @field_validator("weights", mode="after")
    @classmethod
    def _weights_are_non_negative(
        cls,
        weights: dict[ObjectiveDimension, float],
    ) -> dict[ObjectiveDimension, float]:
        for dimension, weight in weights.items():
            if weight < 0:
                raise ValueError(f"Weight for {dimension.value} must be non-negative")
        return weights

    def weight_for(self, dimension: ObjectiveDimension) -> float:
        """Return this profile's weight for a dimension."""

        return self.weights.get(dimension, 0.0)


class ParetoComparison(BaseModel):
    """Dominance relationship for one candidate within a comparison set."""

    model_config = ConfigDict(frozen=True)

    candidate_id: str
    dominates: list[str] = Field(default_factory=list)
    dominated_by: list[str] = Field(default_factory=list)
    is_frontier: bool
    reason: str = ""


class TradeoffExplanation(BaseModel):
    """Human-facing explanation of why the final candidate was selected."""

    model_config = ConfigDict(frozen=True)

    selected_candidate_id: str
    selected_label: str
    preference_profile_id: str
    summary: str
    advantages: list[str] = Field(default_factory=list)
    tradeoffs: list[str] = Field(default_factory=list)
    rejected_candidate_notes: list[str] = Field(default_factory=list)


class ParetoFrontier(BaseModel):
    """A persisted decision frontier and its candidate set."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"frontier_{uuid4().hex[:12]}")
    run_id: str | None = None
    title: str = ""
    candidate_type: CandidateType | None = None
    dimensions: list[ObjectiveDimension] = Field(default_factory=lambda: list(DEFAULT_DIMENSIONS))
    candidates: list[DecisionCandidate] = Field(default_factory=list)
    frontier_candidate_ids: list[str] = Field(default_factory=list)
    dominated_candidate_ids: list[str] = Field(default_factory=list)
    comparisons: list[ParetoComparison] = Field(default_factory=list)
    preference_profile_id: str = "balanced"
    selected_candidate_id: str | None = None
    tradeoff_explanation: TradeoffExplanation | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def frontier_candidates(self) -> list[DecisionCandidate]:
        """Return candidates on the non-dominated frontier."""

        frontier_ids = set(self.frontier_candidate_ids)
        return [candidate for candidate in self.candidates if candidate.id in frontier_ids]

    @property
    def selected_candidate(self) -> DecisionCandidate | None:
        """Return the selected candidate if present in this frontier."""

        if self.selected_candidate_id is None:
            return None
        return next(
            (candidate for candidate in self.candidates if candidate.id == self.selected_candidate_id),
            None,
        )


class ParetoSelectionResult(BaseModel):
    """Complete candidate selection result."""

    model_config = ConfigDict(frozen=True)

    frontier: ParetoFrontier
    selected_candidate: DecisionCandidate
    preference_profile: PreferenceProfile
    ranked_candidate_ids: list[str]
    candidate_scores: dict[str, float]
    valid_candidate_count: int = Field(ge=0)
    dominated_candidate_count: int = Field(ge=0)
    tradeoff_explanation: TradeoffExplanation


def direction_for(dimension: ObjectiveDimension) -> ObjectiveDirection:
    """Return the configured optimization direction for a dimension."""

    return OBJECTIVE_DIRECTIONS[dimension]
