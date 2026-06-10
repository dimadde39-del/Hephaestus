"""Typed schemas for outcome tracking and failure learning."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

type OutcomeMetricValue = bool | int | float | str | None


class OutcomeStatus(StrEnum):
    """Observed result of a decision trace."""

    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class LearningSignalType(StrEnum):
    """Decision-quality dimension affected by an outcome."""

    MODEL_QUALITY = "model_quality"
    CONTEXT_STRATEGY = "context_strategy"
    BUDGET_STRATEGY = "budget_strategy"
    SAFETY_POLICY = "safety_policy"
    TASK_ORDERING = "task_ordering"
    OPTIMIZER_WEIGHT = "optimizer_weight"
    MEMORY_RETRIEVAL = "memory_retrieval"
    VALIDATION_STRATEGY = "validation_strategy"


class LearningDirection(StrEnum):
    """Direction suggested by a learning signal."""

    INCREASE = "increase"
    DECREASE = "decrease"
    AVOID = "avoid"
    PREFER = "prefer"
    INVESTIGATE = "investigate"


class LearningSignalStatus(StrEnum):
    """Lifecycle status for a learning signal or suggested rule change."""

    DRAFT = "draft"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    SUPERSEDED = "superseded"


class PolicyArea(StrEnum):
    """Policy surface that may need a reviewed rule update."""

    MODEL_ROUTER = "model_router"
    CONTEXT_PACKER = "context_packer"
    TOKEN_FIREWALL = "token_firewall"
    SAFETY = "safety"
    SCHEDULER = "scheduler"
    MEMORY = "memory"


class OutcomeMetric(BaseModel):
    """A measured observation attached to an outcome."""

    model_config = ConfigDict(frozen=True)

    name: str
    value: OutcomeMetricValue
    unit: str = ""
    description: str = ""
    higher_is_better: bool | None = None


class OutcomeEvidence(BaseModel):
    """Evidence supporting an outcome assessment."""

    model_config = ConfigDict(frozen=True)

    evidence_type: str
    source: str
    content: str
    uri: str | None = None
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, OutcomeMetricValue] = Field(default_factory=dict)


class OutcomeRecord(BaseModel):
    """A real or simulated result attached to a decision trace."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"outcome_{uuid4().hex[:12]}")
    run_id: str
    decision_trace_id: str
    status: OutcomeStatus
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    summary: str
    metrics: list[OutcomeMetric] = Field(default_factory=list)
    evidence: list[OutcomeEvidence] = Field(default_factory=list)
    severity: float = Field(default=0.0, ge=0, le=1)
    confidence: float = Field(default=0.7, ge=0, le=1)
    tags: list[str] = Field(default_factory=list)

    @field_validator("tags", mode="after")
    @classmethod
    def _normalize_tags(cls, values: list[str]) -> list[str]:
        return _normalize_tags(values)


class ReflectionRecord(BaseModel):
    """A deterministic reflection over a decision and its outcome."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"reflection_{uuid4().hex[:12]}")
    outcome_id: str
    run_id: str
    decision_trace_id: str
    what_worked: str = ""
    what_failed: str = ""
    likely_cause: str = ""
    recommended_change: str = ""
    confidence: float = Field(default=0.7, ge=0, le=1)
    tags: list[str] = Field(default_factory=list)

    @field_validator("tags", mode="after")
    @classmethod
    def _normalize_tags(cls, values: list[str]) -> list[str]:
        return _normalize_tags(values)


class LearningSignal(BaseModel):
    """A draft learning signal derived from an observed outcome."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"signal_{uuid4().hex[:12]}")
    run_id: str
    decision_trace_id: str
    outcome_id: str
    signal_type: LearningSignalType
    direction: LearningDirection
    target: str
    rationale: str
    strength: float = Field(default=0.5, ge=0, le=1)
    confidence: float = Field(default=0.7, ge=0, le=1)
    status: LearningSignalStatus = LearningSignalStatus.DRAFT
    tags: list[str] = Field(default_factory=list)

    @field_validator("tags", mode="after")
    @classmethod
    def _normalize_tags(cls, values: list[str]) -> list[str]:
        return _normalize_tags(values)


class FailureMemoryDraft(BaseModel):
    """A failure observation shaped for later explicit promotion into memory."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"failure_draft_{uuid4().hex[:12]}")
    run_id: str
    decision_trace_id: str
    outcome_id: str
    memory_type: Literal["failure"] = "failure"
    summary: str
    content: str
    tags: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.7, ge=0, le=1)
    severity: float = Field(default=0.5, ge=0, le=1)
    suggested_memory_importance: float = Field(default=0.6, ge=0, le=1)

    @field_validator("tags", mode="after")
    @classmethod
    def _normalize_tags(cls, values: list[str]) -> list[str]:
        return _normalize_tags(values)


class PolicyUpdateSuggestion(BaseModel):
    """A reviewed, non-applied policy change suggested by an outcome."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"policy_suggestion_{uuid4().hex[:12]}")
    run_id: str
    decision_trace_id: str
    outcome_id: str
    policy_area: PolicyArea
    current_rule: str
    suggested_rule: str
    rationale: str
    confidence: float = Field(default=0.7, ge=0, le=1)
    status: LearningSignalStatus = LearningSignalStatus.DRAFT
    tags: list[str] = Field(default_factory=list)

    @field_validator("tags", mode="after")
    @classmethod
    def _normalize_tags(cls, values: list[str]) -> list[str]:
        return _normalize_tags(values)


def outcome_metric(
    name: str,
    value: OutcomeMetricValue,
    *,
    unit: str = "",
    description: str = "",
    higher_is_better: bool | None = None,
) -> OutcomeMetric:
    """Create a concise outcome metric."""

    return OutcomeMetric(
        name=name,
        value=value,
        unit=unit,
        description=description,
        higher_is_better=higher_is_better,
    )


def _normalize_tags(values: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for value in values:
        tag = value.strip().lower()
        if not tag or tag in seen:
            continue
        seen.add(tag)
        normalized.append(tag)
    return normalized
