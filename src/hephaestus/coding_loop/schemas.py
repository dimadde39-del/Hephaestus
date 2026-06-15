"""Typed schemas for the repo-aware coding loop."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class CodingLoopStatus(StrEnum):
    """Lifecycle statuses for a controlled coding loop."""

    PLANNED = "planned"
    SCOPE_TOO_LARGE = "scope_too_large"
    REQUIRES_APPROVAL = "requires_approval"
    PATCH_PROPOSED = "patch_proposed"
    PATCH_APPLIED = "patch_applied"
    VALIDATION_RUNNING = "validation_running"
    VALIDATION_PASSED = "validation_passed"
    VALIDATION_FAILED = "validation_failed"
    ROLLED_BACK = "rolled_back"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    NEEDS_USER_INPUT = "needs_user_input"


class CodingScopeType(StrEnum):
    """Supported scope types for early repo-aware coding work."""

    DOCS = "docs"
    TESTS = "tests"
    BUGFIX = "bugfix"
    SMALL_FEATURE = "small_feature"
    REFACTOR = "refactor"
    CONFIG = "config"
    UNKNOWN = "unknown"


class CodingRisk(StrEnum):
    """Human-readable coding-loop risk levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class CodingRequest(BaseModel):
    """A user request to plan or run a small repo change."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"coding_request_{uuid4().hex[:12]}")
    repo_path: str
    repo_profile_id: str | None = None
    conversation_id: str | None = None
    run_id: str | None = None
    active_policy_profile: str = ""
    user_request: str
    requested_scope: CodingScopeType | None = None
    provider: str = "auto"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class CodingScope(BaseModel):
    """Scope classification for a coding request."""

    model_config = ConfigDict(frozen=True)

    scope_type: CodingScopeType = CodingScopeType.UNKNOWN
    risk: CodingRisk = CodingRisk.MEDIUM
    summary: str = ""
    likely_files: list[str] = Field(default_factory=list)
    too_large: bool = False
    reasons: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.55, ge=0, le=1)

    @field_validator("likely_files", "reasons", mode="after")
    @classmethod
    def _dedupe_text(cls, values: list[str]) -> list[str]:
        return _dedupe_text(values)


class CodingPlanStep(BaseModel):
    """One small step in the coding loop plan."""

    model_config = ConfigDict(frozen=True)

    order: int = Field(ge=1)
    title: str
    summary: str = ""
    expected_files: list[str] = Field(default_factory=list)
    requires_approval: bool = False
    status: CodingLoopStatus = CodingLoopStatus.PLANNED

    @field_validator("expected_files", mode="after")
    @classmethod
    def _dedupe_files(cls, values: list[str]) -> list[str]:
        return _dedupe_text(values)


class CodingPlan(BaseModel):
    """Repo-aware plan for one scoped coding request."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"coding_plan_{uuid4().hex[:12]}")
    request_id: str
    repo_path: str
    repo_profile_id: str | None = None
    conversation_id: str | None = None
    run_id: str | None = None
    active_policy_profile: str = ""
    user_request: str
    scope: CodingScope
    summary: str = ""
    steps: list[CodingPlanStep] = Field(default_factory=list)
    likely_files: list[str] = Field(default_factory=list)
    validation_commands: list[str] = Field(default_factory=list)
    validation_plan_id: str | None = None
    checkpoint_plan: str = "Create a checkpoint for touched files before applying a patch."
    rollback_plan: str = "Restore the checkpoint if validation fails and rollback is requested."
    approval_behavior: str = ""
    patch_proposal_possible: bool = False
    scope_too_large: bool = False
    requires_approval: bool = True
    status: CodingLoopStatus = CodingLoopStatus.PLANNED
    strategic_memory_ids: list[str] = Field(default_factory=list)
    decision_trace_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "likely_files",
        "validation_commands",
        "strategic_memory_ids",
        "decision_trace_ids",
        mode="after",
    )
    @classmethod
    def _dedupe_lists(cls, values: list[str]) -> list[str]:
        return _dedupe_text(values)


class CodingPatch(BaseModel):
    """One patch inside a coding-loop proposal."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"coding_patch_{uuid4().hex[:12]}")
    path: str
    diff: str
    find: str = ""
    replace: str = ""
    tool_patch_id: str | None = None
    tool_action_id: str | None = None
    original_hash: str = ""
    patch_kind: str = "deterministic"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class CodingPatchSet(BaseModel):
    """A proposal-level collection of patches."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"coding_patch_set_{uuid4().hex[:12]}")
    patches: list[CodingPatch] = Field(default_factory=list)
    files_touched: list[str] = Field(default_factory=list)
    diff: str = ""
    patch_ids: list[str] = Field(default_factory=list)
    tool_action_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("files_touched", "patch_ids", "tool_action_ids", mode="after")
    @classmethod
    def _dedupe_lists(cls, values: list[str]) -> list[str]:
        return _dedupe_text(values)


class CodingChangeProposal(BaseModel):
    """A persisted patch proposal for a coding request."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"coding_change_{uuid4().hex[:12]}")
    request_id: str
    plan_id: str
    repo_path: str
    repo_profile_id: str | None = None
    active_policy_profile: str = ""
    summary: str
    risk: CodingRisk = CodingRisk.MEDIUM
    scope_type: CodingScopeType = CodingScopeType.UNKNOWN
    patch_set: CodingPatchSet
    validation_commands: list[str] = Field(default_factory=list)
    checkpoint_plan: str = ""
    approval_required: bool = True
    status: CodingLoopStatus = CodingLoopStatus.PATCH_PROPOSED
    review_id: str | None = None
    decision_trace_ids: list[str] = Field(default_factory=list)
    outcome_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("validation_commands", "decision_trace_ids", "outcome_ids", mode="after")
    @classmethod
    def _dedupe_lists(cls, values: list[str]) -> list[str]:
        return _dedupe_text(values)


class CodingReview(BaseModel):
    """Lightweight pre-apply review for a patch proposal."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"coding_review_{uuid4().hex[:12]}")
    request_id: str
    plan_id: str
    change_id: str
    approved: bool = False
    blocked: bool = False
    risk: CodingRisk = CodingRisk.MEDIUM
    summary: str = ""
    findings: list[str] = Field(default_factory=list)
    expected_files: list[str] = Field(default_factory=list)
    actual_files: list[str] = Field(default_factory=list)
    protected_files: list[str] = Field(default_factory=list)
    validation_present: bool = False
    decision_trace_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("findings", "expected_files", "actual_files", "protected_files", mode="after")
    @classmethod
    def _dedupe_lists(cls, values: list[str]) -> list[str]:
        return _dedupe_text(values)


class CodingValidationSummary(BaseModel):
    """Coding-loop view of a validation suite result."""

    model_config = ConfigDict(frozen=True)

    validation_result_id: str | None = None
    validation_plan_id: str | None = None
    status: str = "not_run"
    command_count: int = Field(default=0, ge=0)
    pass_count: int = Field(default=0, ge=0)
    fail_count: int = Field(default=0, ge=0)
    skipped_count: int = Field(default=0, ge=0)
    blocked_count: int = Field(default=0, ge=0)
    requires_approval_count: int = Field(default=0, ge=0)
    summary: str = ""
    evidence_mode: str = "no_validation_evidence"
    decision_trace_ids: list[str] = Field(default_factory=list)
    outcome_ids: list[str] = Field(default_factory=list)
    learning_signal_ids: list[str] = Field(default_factory=list)

    @field_validator("decision_trace_ids", "outcome_ids", "learning_signal_ids", mode="after")
    @classmethod
    def _dedupe_lists(cls, values: list[str]) -> list[str]:
        return _dedupe_text(values)


class CodingLearningSignal(BaseModel):
    """Compact coding-loop learning signal view."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"coding_signal_{uuid4().hex[:12]}")
    signal_type: str
    summary: str
    outcome_id: str | None = None
    learning_signal_id: str | None = None
    severity: float = Field(default=0.5, ge=0, le=1)
    confidence: float = Field(default=0.7, ge=0, le=1)
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("tags", mode="after")
    @classmethod
    def _dedupe_tags(cls, values: list[str]) -> list[str]:
        return _dedupe_text(values)


class CodingIteration(BaseModel):
    """One bounded coding loop iteration."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"coding_iteration_{uuid4().hex[:12]}")
    request_id: str
    plan_id: str | None = None
    change_id: str | None = None
    review_id: str | None = None
    status: CodingLoopStatus = CodingLoopStatus.PLANNED
    summary: str = ""
    apply_tool_action_id: str | None = None
    apply_tool_result_id: str | None = None
    checkpoint_id: str | None = None
    validation_result_id: str | None = None
    rollback_tool_action_id: str | None = None
    rollback_checkpoint_id: str | None = None
    outcome_ids: list[str] = Field(default_factory=list)
    learning_signal_ids: list[str] = Field(default_factory=list)
    decision_trace_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("outcome_ids", "learning_signal_ids", "decision_trace_ids", mode="after")
    @classmethod
    def _dedupe_lists(cls, values: list[str]) -> list[str]:
        return _dedupe_text(values)


class CodingLoopResult(BaseModel):
    """Final or current result for a coding loop request."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"coding_result_{uuid4().hex[:12]}")
    request_id: str
    plan_id: str | None = None
    change_id: str | None = None
    repo_path: str
    repo_profile_id: str | None = None
    conversation_id: str | None = None
    run_id: str | None = None
    active_policy_profile: str = ""
    user_request: str
    scope_type: CodingScopeType = CodingScopeType.UNKNOWN
    risk: CodingRisk = CodingRisk.MEDIUM
    status: CodingLoopStatus = CodingLoopStatus.PLANNED
    summary: str = ""
    iteration_ids: list[str] = Field(default_factory=list)
    patch_ids: list[str] = Field(default_factory=list)
    tool_action_ids: list[str] = Field(default_factory=list)
    checkpoint_ids: list[str] = Field(default_factory=list)
    validation_result_ids: list[str] = Field(default_factory=list)
    outcome_ids: list[str] = Field(default_factory=list)
    learning_signal_ids: list[str] = Field(default_factory=list)
    decision_trace_ids: list[str] = Field(default_factory=list)
    validation: CodingValidationSummary = Field(default_factory=CodingValidationSummary)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "iteration_ids",
        "patch_ids",
        "tool_action_ids",
        "checkpoint_ids",
        "validation_result_ids",
        "outcome_ids",
        "learning_signal_ids",
        "decision_trace_ids",
        mode="after",
    )
    @classmethod
    def _dedupe_lists(cls, values: list[str]) -> list[str]:
        return _dedupe_text(values)


class CodingLoopDetail(BaseModel):
    """Joined view used by CLI show output."""

    model_config = ConfigDict(frozen=True)

    request: CodingRequest | None = None
    plan: CodingPlan | None = None
    change: CodingChangeProposal | None = None
    iteration: CodingIteration | None = None
    result: CodingLoopResult | None = None


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
