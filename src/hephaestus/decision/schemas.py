"""Typed schemas for explainable decision traces."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal, cast
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

type MetricValue = bool | int | float | str | None


class DecisionType(StrEnum):
    """Supported Phase 3A decision categories."""

    TASK_SELECTION = "task_selection"
    MODEL_ROUTING = "model_routing"
    CONTEXT_SELECTION = "context_selection"
    BUDGET = "budget"
    SAFETY = "safety"
    OPTIMIZATION = "optimization"


class DecisionMetric(BaseModel):
    """A typed metric that contributed to a decision."""

    model_config = ConfigDict(frozen=True)

    name: str
    value: MetricValue
    unit: str = ""
    description: str = ""
    higher_is_better: bool | None = None


class DecisionAlternative(BaseModel):
    """A rejected or non-selected option considered by a decision."""

    model_config = ConfigDict(frozen=True)

    option_id: str
    option_name: str = ""
    score: float | None = None
    rejection_reason: str = ""
    violated_constraints: list[str] = Field(default_factory=list)
    metrics: list[DecisionMetric] = Field(default_factory=list)
    would_have_cost: float | None = Field(default=None, ge=0)
    expected_quality: float | None = Field(default=None, ge=0, le=1)
    risk: float | None = Field(default=None, ge=0)

    @property
    def label(self) -> str:
        """Return a compact human-readable label."""

        if self.option_name and self.option_name != self.option_id:
            return f"{self.option_id} ({self.option_name})"
        return self.option_id


class DecisionTrace(BaseModel):
    """Shared fields every persisted decision trace must expose."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"trace_{uuid4().hex[:12]}")
    run_id: str
    decision_type: DecisionType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    phase: str = "runtime"
    selected_option: str
    alternatives: list[DecisionAlternative] = Field(default_factory=list)
    rationale: str
    metrics: list[DecisionMetric] = Field(default_factory=list)
    objective_score: float | None = None
    confidence: float = Field(default=0.75, ge=0, le=1)
    constraints_considered: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    caused_by: list[str] = Field(default_factory=list)
    will_affect: list[str] = Field(default_factory=list)
    learning_hooks: list[str] = Field(default_factory=list)
    outcome_id: str | None = None
    failure_memory_id: str | None = None
    policy_update_id: str | None = None
    parent_id: str | None = None

    @field_validator("tags", "caused_by", "will_affect", "learning_hooks", mode="after")
    @classmethod
    def _dedupe_text(cls, values: list[str]) -> list[str]:
        seen: set[str] = set()
        deduped: list[str] = []
        for value in values:
            normalized = value.strip()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            deduped.append(normalized)
        return deduped

    @property
    def metric_map(self) -> dict[str, MetricValue]:
        """Return metrics keyed by name for callers that need dictionary access."""

        return {metric.name: metric.value for metric in self.metrics}


class TaskSelectionDecision(DecisionTrace):
    """Why a task or task order was selected over alternatives."""

    decision_type: Literal[DecisionType.TASK_SELECTION] = DecisionType.TASK_SELECTION


class ModelRoutingDecision(DecisionTrace):
    """Why a model was selected and why other models were rejected."""

    decision_type: Literal[DecisionType.MODEL_ROUTING] = DecisionType.MODEL_ROUTING


class ContextSelectionDecision(DecisionTrace):
    """Why context was included or excluded from a packed prompt."""

    decision_type: Literal[DecisionType.CONTEXT_SELECTION] = DecisionType.CONTEXT_SELECTION


class BudgetDecision(DecisionTrace):
    """Why token, cost, or quality budget controls approved or intervened."""

    decision_type: Literal[DecisionType.BUDGET] = DecisionType.BUDGET


class SafetyDecision(DecisionTrace):
    """Why a safety or approval gate allowed, blocked, or escalated an action."""

    decision_type: Literal[DecisionType.SAFETY] = DecisionType.SAFETY


class OptimizationDecision(DecisionTrace):
    """Why an optimizer, strategy, or objective result was selected."""

    decision_type: Literal[DecisionType.OPTIMIZATION] = DecisionType.OPTIMIZATION


type DecisionTraceVariant = (
    TaskSelectionDecision
    | ModelRoutingDecision
    | ContextSelectionDecision
    | BudgetDecision
    | SafetyDecision
    | OptimizationDecision
)


class DecisionTraceNode(BaseModel):
    """A trace node with children for reconstructing decision trees."""

    decision: DecisionTraceVariant
    children: list[DecisionTraceNode] = Field(default_factory=list)


_DECISION_MODELS: dict[DecisionType, type[DecisionTrace]] = {
    DecisionType.TASK_SELECTION: TaskSelectionDecision,
    DecisionType.MODEL_ROUTING: ModelRoutingDecision,
    DecisionType.CONTEXT_SELECTION: ContextSelectionDecision,
    DecisionType.BUDGET: BudgetDecision,
    DecisionType.SAFETY: SafetyDecision,
    DecisionType.OPTIMIZATION: OptimizationDecision,
}


def metric(
    name: str,
    value: MetricValue,
    *,
    unit: str = "",
    description: str = "",
    higher_is_better: bool | None = None,
) -> DecisionMetric:
    """Create a decision metric with concise call sites."""

    return DecisionMetric(
        name=name,
        value=value,
        unit=unit,
        description=description,
        higher_is_better=higher_is_better,
    )


def parse_decision_trace(data: Mapping[str, object]) -> DecisionTraceVariant:
    """Parse stored trace data into its concrete decision model."""

    decision_type = DecisionType(str(data["decision_type"]))
    model = _DECISION_MODELS[decision_type]
    parsed = model.model_validate(data)
    return cast(DecisionTraceVariant, parsed)
