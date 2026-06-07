"""Schemas for policy learning and decision quality profiles."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

type ProfileValue = bool | int | float | str | None


class DecisionArea(StrEnum):
    """Decision surface that a quality profile can influence."""

    MODEL_ROUTER = "model_router"
    CONTEXT_PACKER = "context_packer"
    TOKEN_FIREWALL = "token_firewall"
    SCHEDULER = "scheduler"
    SAFETY = "safety"
    MEMORY_RETRIEVAL = "memory_retrieval"
    OPTIMIZER = "optimizer"


class ProfileStatus(StrEnum):
    """Lifecycle state for a decision quality profile."""

    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class ProfileRuleType(StrEnum):
    """Structured rule categories used by profile appliers."""

    QUALITY_THRESHOLD = "quality_threshold"
    MODEL_PREFERENCE = "model_preference"
    CONTEXT_PRESERVATION = "context_preservation"
    TOKEN_COMPRESSION = "token_compression"
    SCHEDULER_WEIGHT = "scheduler_weight"
    SAFETY_GATE = "safety_gate"
    MEMORY_RETRIEVAL = "memory_retrieval"
    OPTIMIZER_BIAS = "optimizer_bias"


class AdjustmentOperation(StrEnum):
    """How an adjustment changes a decision input."""

    INCREASE = "increase"
    DECREASE = "decrease"
    SET = "set"
    REQUIRE = "require"
    PREFER = "prefer"
    AVOID = "avoid"
    MULTIPLY = "multiply"


class ProfileEvidenceType(StrEnum):
    """Source artifact type used as profile evidence."""

    OUTCOME = "outcome"
    REFLECTION = "reflection"
    LEARNING_SIGNAL = "learning_signal"
    FAILURE_MEMORY_DRAFT = "failure_memory_draft"
    POLICY_SUGGESTION = "policy_suggestion"
    DECISION_TRACE = "decision_trace"


class ProfileAdjustment(BaseModel):
    """A typed change a profile can apply to a future decision."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"adjustment_{uuid4().hex[:12]}")
    target: str
    operation: AdjustmentOperation
    value: ProfileValue = None
    unit: str = ""
    rationale: str = ""


class ProfileRule(BaseModel):
    """A structured rule in a decision quality profile."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"rule_{uuid4().hex[:12]}")
    decision_area: DecisionArea
    rule_type: ProfileRuleType
    target: str
    conditions: dict[str, ProfileValue] = Field(default_factory=dict)
    adjustments: list[ProfileAdjustment] = Field(default_factory=list)
    minimum_quality_score: float | None = Field(default=None, ge=0, le=1)
    max_failure_rate: float | None = Field(default=None, ge=0, le=1)
    prefer_model_tags: list[str] = Field(default_factory=list)
    avoid_model_tags: list[str] = Field(default_factory=list)
    hard_constraint: bool = False
    require_approval: bool = False
    rationale: str = ""

    @field_validator("prefer_model_tags", "avoid_model_tags", mode="after")
    @classmethod
    def _normalize_tags(cls, values: list[str]) -> list[str]:
        return _normalize_text(values)


class ProfileEvidence(BaseModel):
    """Evidence that supports a profile suggestion."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"evidence_{uuid4().hex[:12]}")
    evidence_type: ProfileEvidenceType
    source_id: str
    summary: str
    weight: float = Field(default=0.5, ge=0, le=1)
    confidence: float = Field(default=0.7, ge=0, le=1)
    severity: float = Field(default=0.0, ge=0, le=1)
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tags: list[str] = Field(default_factory=list)

    @field_validator("tags", mode="after")
    @classmethod
    def _normalize_tags(cls, values: list[str]) -> list[str]:
        return _normalize_text(values)


class DecisionQualityProfile(BaseModel):
    """Inspectable learned preferences for one decision area."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"profile_{uuid4().hex[:12]}")
    name: str
    decision_area: DecisionArea
    status: ProfileStatus = ProfileStatus.DRAFT
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    description: str = ""
    rules: list[ProfileRule] = Field(default_factory=list)
    evidence: list[ProfileEvidence] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)
    source_learning_signal_ids: list[str] = Field(default_factory=list)
    source_outcome_ids: list[str] = Field(default_factory=list)
    source_policy_suggestion_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @field_validator(
        "source_learning_signal_ids",
        "source_outcome_ids",
        "source_policy_suggestion_ids",
        "tags",
        mode="after",
    )
    @classmethod
    def _normalize_text_fields(cls, values: list[str]) -> list[str]:
        return _normalize_text(values)

    @model_validator(mode="after")
    def _rules_match_area(self) -> DecisionQualityProfile:
        mismatched = [
            rule.id for rule in self.rules if rule.decision_area != self.decision_area
        ]
        if mismatched:
            raise ValueError(
                "Profile rules must match profile decision area: "
                + ", ".join(mismatched)
            )
        return self


class ProfileEvaluation(BaseModel):
    """Summary returned by a learning aggregation pass."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"profile_eval_{uuid4().hex[:12]}")
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    profiles_created: int = Field(ge=0)
    evidence_count: int = Field(ge=0)
    confidence: float = Field(default=0.0, ge=0, le=1)
    profiles: list[DecisionQualityProfile] = Field(default_factory=list)
    summary: str = ""


class ProfileApplicationResult(BaseModel):
    """A recorded influence from a profile onto a concrete decision input."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"profile_app_{uuid4().hex[:12]}")
    profile_id: str
    profile_name: str
    decision_area: DecisionArea
    run_id: str | None = None
    trace_id: str | None = None
    target: str = ""
    applied: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    effect_summary: str = ""
    before: dict[str, Any] = Field(default_factory=dict)
    after: dict[str, Any] = Field(default_factory=dict)
    adjustments_applied: list[ProfileAdjustment] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)

    @field_validator("notes", mode="after")
    @classmethod
    def _normalize_notes(cls, values: list[str]) -> list[str]:
        return _normalize_text(values)


def _normalize_text(values: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for value in values:
        item = value.strip().lower()
        if not item or item in seen:
            continue
        seen.add(item)
        normalized.append(item)
    return normalized
