"""Analysis helpers for outcome learning records."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field

from hephaestus.outcomes.schemas import (
    FailureMemoryDraft,
    LearningSignal,
    OutcomeRecord,
    OutcomeStatus,
    PolicyUpdateSuggestion,
    ReflectionRecord,
)


class OutcomeCount(BaseModel):
    """A counted outcome label."""

    model_config = ConfigDict(frozen=True)

    label: str
    count: int = Field(ge=0)


class OutcomeLearningSummary(BaseModel):
    """Per-run summary of outcome learning artifacts."""

    model_config = ConfigDict(frozen=True)

    total_outcomes: int = Field(ge=0)
    success_count: int = Field(ge=0)
    failure_count: int = Field(ge=0)
    partial_count: int = Field(ge=0)
    unknown_count: int = Field(ge=0)
    outcomes_by_status: list[OutcomeCount] = Field(default_factory=list)
    reflection_count: int = Field(ge=0)
    learning_signal_count: int = Field(ge=0)
    failure_memory_draft_count: int = Field(ge=0)
    policy_update_suggestion_count: int = Field(ge=0)


def summarize_outcome_learning(
    outcomes: Iterable[OutcomeRecord],
    reflections: Iterable[ReflectionRecord] | None = None,
    learning_signals: Iterable[LearningSignal] | None = None,
    failure_memory_drafts: Iterable[FailureMemoryDraft] | None = None,
    policy_update_suggestions: Iterable[PolicyUpdateSuggestion] | None = None,
) -> OutcomeLearningSummary:
    """Summarize outcome and learning artifact counts."""

    outcome_list = list(outcomes)
    counts = Counter(outcome.status for outcome in outcome_list)
    return OutcomeLearningSummary(
        total_outcomes=len(outcome_list),
        success_count=counts[OutcomeStatus.SUCCESS],
        failure_count=counts[OutcomeStatus.FAILURE],
        partial_count=counts[OutcomeStatus.PARTIAL],
        unknown_count=counts[OutcomeStatus.UNKNOWN],
        outcomes_by_status=[
            OutcomeCount(label=status.value, count=counts[status])
            for status in OutcomeStatus
            if counts[status] > 0
        ],
        reflection_count=len(list(reflections or [])),
        learning_signal_count=len(list(learning_signals or [])),
        failure_memory_draft_count=len(list(failure_memory_drafts or [])),
        policy_update_suggestion_count=len(list(policy_update_suggestions or [])),
    )
