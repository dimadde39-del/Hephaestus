"""Typed schemas for real validation execution and release evidence."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from hephaestus.tool_runtime.schemas import ToolRiskLevel


class ValidationCommandType(StrEnum):
    """Supported validation command categories."""

    LINT = "lint"
    TEST = "test"
    TYPECHECK = "typecheck"
    BUILD = "build"
    FORMAT_CHECK = "format_check"
    SECURITY_CHECK = "security_check"
    CUSTOM = "custom"


class ValidationStatus(StrEnum):
    """Execution status for validation commands and suites."""

    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMED_OUT = "timed_out"
    BLOCKED = "blocked"
    REQUIRES_APPROVAL = "requires_approval"
    UNKNOWN = "unknown"


class ValidationCommand(BaseModel):
    """One validation command selected from repo intelligence."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"validation_cmd_{uuid4().hex[:12]}")
    plan_id: str | None = None
    repo_profile_id: str | None = None
    command: str
    command_type: ValidationCommandType = ValidationCommandType.CUSTOM
    source: str = ""
    framework: str = ""
    order: int = Field(default=1, ge=1)
    risk_level: ToolRiskLevel = ToolRiskLevel.SAFE_VALIDATION
    requires_approval: bool = True
    tool_policy_approval_required: bool = False
    blocked: bool = False
    reasons: list[str] = Field(default_factory=list)
    suggestion: bool = False
    timeout_seconds: int = Field(default=120, gt=0)
    decision_trace_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("reasons", mode="after")
    @classmethod
    def _dedupe_reasons(cls, values: list[str]) -> list[str]:
        return _dedupe_text(values)


class ValidationExecutionPlan(BaseModel):
    """A persisted repo validation execution plan."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"validation_plan_{uuid4().hex[:12]}")
    repo_path: str
    repo_profile_id: str | None = None
    release_plan_id: str | None = None
    run_id: str | None = None
    commands: list[ValidationCommand] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)
    decision_trace_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("notes", "decision_trace_ids", mode="after")
    @classmethod
    def _dedupe_lists(cls, values: list[str]) -> list[str]:
        return _dedupe_text(values)

    @property
    def command_texts(self) -> list[str]:
        """Return selected commands in execution order."""

        return [command.command for command in self.commands]


class ValidationFailure(BaseModel):
    """Classified validation failure pattern."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"validation_failure_{uuid4().hex[:12]}")
    evidence_id: str | None = None
    command: str
    command_type: ValidationCommandType
    classification: str
    summary: str
    pattern_key: str
    repeated_count: int = Field(default=1, ge=1)
    severity: float = Field(default=0.5, ge=0, le=1)
    output_excerpt: str = ""


class ValidationEvidence(BaseModel):
    """Concrete evidence produced by one validation command."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"validation_evidence_{uuid4().hex[:12]}")
    validation_result_id: str | None = None
    plan_id: str
    command_id: str
    repo_path: str
    repo_profile_id: str | None = None
    command: str
    command_type: ValidationCommandType
    status: ValidationStatus = ValidationStatus.UNKNOWN
    exit_code: int | None = None
    stdout_summary: str = ""
    stderr_summary: str = ""
    duration_seconds: float = Field(default=0.0, ge=0)
    tool_action_id: str | None = None
    tool_execution_result_id: str | None = None
    outcome_id: str | None = None
    decision_trace_id: str | None = None
    failure_classification: str | None = None
    failure: ValidationFailure | None = None
    warning_count: int = Field(default=0, ge=0)
    output_truncated: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class ValidationExecutionResult(BaseModel):
    """Command-level validation result shown inside a suite."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"validation_exec_{uuid4().hex[:12]}")
    plan_id: str
    command_id: str
    command: str
    command_type: ValidationCommandType
    status: ValidationStatus = ValidationStatus.UNKNOWN
    evidence_id: str | None = None
    exit_code: int | None = None
    stdout_summary: str = ""
    stderr_summary: str = ""
    duration_seconds: float = Field(default=0.0, ge=0)
    tool_action_id: str | None = None
    tool_execution_result_id: str | None = None
    outcome_id: str | None = None
    decision_trace_id: str | None = None
    failure: ValidationFailure | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ValidationLearningSignal(BaseModel):
    """Compact validation-facing view of a persisted learning signal."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"validation_signal_{uuid4().hex[:12]}")
    signal_type: str
    summary: str
    rationale: str = ""
    command_type: ValidationCommandType | None = None
    command: str | None = None
    severity: float = Field(default=0.5, ge=0, le=1)
    confidence: float = Field(default=0.7, ge=0, le=1)
    outcome_id: str | None = None
    learning_signal_id: str | None = None
    failure_memory_draft_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tags: list[str] = Field(default_factory=list)

    @field_validator("tags", mode="after")
    @classmethod
    def _dedupe_tags(cls, values: list[str]) -> list[str]:
        return _dedupe_text(values)


class ValidationSuiteResult(BaseModel):
    """Aggregate result for one validation suite execution."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"validation_result_{uuid4().hex[:12]}")
    plan_id: str
    repo_path: str
    repo_profile_id: str | None = None
    release_plan_id: str | None = None
    run_id: str | None = None
    status: ValidationStatus = ValidationStatus.UNKNOWN
    command_results: list[ValidationExecutionResult] = Field(default_factory=list)
    evidence: list[ValidationEvidence] = Field(default_factory=list)
    pass_count: int = Field(default=0, ge=0)
    fail_count: int = Field(default=0, ge=0)
    skipped_count: int = Field(default=0, ge=0)
    timed_out_count: int = Field(default=0, ge=0)
    blocked_count: int = Field(default=0, ge=0)
    requires_approval_count: int = Field(default=0, ge=0)
    unknown_count: int = Field(default=0, ge=0)
    warning_count: int = Field(default=0, ge=0)
    duration_seconds: float = Field(default=0.0, ge=0)
    outcome_ids: list[str] = Field(default_factory=list)
    learning_signals: list[ValidationLearningSignal] = Field(default_factory=list)
    learning_signal_ids: list[str] = Field(default_factory=list)
    failure_memory_draft_ids: list[str] = Field(default_factory=list)
    decision_trace_ids: list[str] = Field(default_factory=list)
    evidence_mode: str = "no_validation_evidence"
    readiness_impact: int = 0
    summary: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator(
        "outcome_ids",
        "learning_signal_ids",
        "failure_memory_draft_ids",
        "decision_trace_ids",
        mode="after",
    )
    @classmethod
    def _dedupe_ids(cls, values: list[str]) -> list[str]:
        return _dedupe_text(values)


class ReleaseValidationSummary(BaseModel):
    """Release-plan-facing summary of real validation evidence."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"release_validation_{uuid4().hex[:12]}")
    release_plan_id: str | None = None
    validation_result_id: str
    repo_path: str
    repo_profile_id: str | None = None
    status: ValidationStatus
    evidence_based: bool = False
    simulated: bool = False
    readiness_score_before: int | None = Field(default=None, ge=0, le=100)
    readiness_score_after: int | None = Field(default=None, ge=0, le=100)
    readiness_score_delta: int = 0
    pass_count: int = Field(default=0, ge=0)
    fail_count: int = Field(default=0, ge=0)
    timed_out_count: int = Field(default=0, ge=0)
    blocked_count: int = Field(default=0, ge=0)
    requires_approval_count: int = Field(default=0, ge=0)
    skipped_count: int = Field(default=0, ge=0)
    warning_count: int = Field(default=0, ge=0)
    summary: str = ""
    outcome_ids: list[str] = Field(default_factory=list)
    learning_signal_ids: list[str] = Field(default_factory=list)
    decision_trace_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("outcome_ids", "learning_signal_ids", "decision_trace_ids", mode="after")
    @classmethod
    def _dedupe_summary_ids(cls, values: list[str]) -> list[str]:
        return _dedupe_text(values)


def _dedupe_text(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped
