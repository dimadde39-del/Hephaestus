"""Typed schemas for the safe local tool execution runtime."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ToolActionType(StrEnum):
    """Local tool actions supported by the Phase 5E runtime."""

    READ_FILE = "read_file"
    LIST_DIRECTORY = "list_directory"
    SEARCH_FILES = "search_files"
    PROPOSE_PATCH = "propose_patch"
    APPLY_PATCH = "apply_patch"
    RUN_COMMAND = "run_command"
    CREATE_CHECKPOINT = "create_checkpoint"
    RESTORE_CHECKPOINT = "restore_checkpoint"


class ToolRiskLevel(StrEnum):
    """Risk levels aligned with repo intelligence and policy profile language."""

    SAFE_READONLY = "safe_readonly"
    SAFE_VALIDATION = "safe_validation"
    MEDIUM_RISK = "medium_risk"
    HIGH_RISK = "high_risk"
    DESTRUCTIVE = "destructive"
    EXTERNAL_SIDE_EFFECT = "external_side_effect"


class ToolApprovalStatus(StrEnum):
    """Lifecycle of a tool approval gate."""

    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    BLOCKED = "blocked"


class ToolExecutionStatus(StrEnum):
    """Execution status for a local tool action."""

    PLANNED = "planned"
    DRY_RUN = "dry_run"
    APPROVAL_REQUIRED = "approval_required"
    BLOCKED = "blocked"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    RESTORED = "restored"


class ToolApprovalPolicy(BaseModel):
    """Resolved approval behavior for the active policy profile."""

    model_config = ConfigDict(frozen=True)

    profile_id: str
    profile_name: str
    allow_readonly: bool = True
    allow_safe_validation: bool = True
    require_approval_for_validation: bool = False
    require_approval_for_medium: bool = True
    require_approval_for_high: bool = True
    require_approval_for_external: bool = True
    block_high_risk: bool = False
    block_external_side_effects: bool = False
    block_destructive: bool = True
    notes: list[str] = Field(default_factory=list)


class ToolRiskDecision(BaseModel):
    """Risk classification plus profile-aware approval decision."""

    model_config = ConfigDict(frozen=True)

    risk_level: ToolRiskLevel
    approval_required: bool = False
    blocked: bool = False
    reasons: list[str] = Field(default_factory=list)
    policy: ToolApprovalPolicy
    policy_decision: str = "allow"


class ToolAction(BaseModel):
    """Persisted local tool action."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"tool_action_{uuid4().hex[:12]}")
    action_type: ToolActionType
    workspace_path: str
    command: str = ""
    target_path: str = ""
    summary: str = ""
    risk_level: ToolRiskLevel = ToolRiskLevel.SAFE_READONLY
    active_policy_profile: str = ""
    approval_status: ToolApprovalStatus = ToolApprovalStatus.NOT_REQUIRED
    execution_status: ToolExecutionStatus = ToolExecutionStatus.PLANNED
    stdout_summary: str = ""
    stderr_summary: str = ""
    exit_code: int | None = None
    files_touched: list[str] = Field(default_factory=list)
    checkpoint_id: str | None = None
    decision_trace_id: str | None = None
    outcome_id: str | None = None
    conversation_id: str | None = None
    run_id: str | None = None
    repo_profile_id: str | None = None
    patch_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @field_validator("files_touched", mode="after")
    @classmethod
    def _dedupe_files(cls, values: list[str]) -> list[str]:
        return _dedupe_text(values)


class ToolApprovalRequest(BaseModel):
    """Approval request shown before a side-effectful tool action."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"tool_approval_request_{uuid4().hex[:12]}")
    action_id: str
    action_type: ToolActionType
    risk_level: ToolRiskLevel
    policy_profile: str
    summary: str
    reasons: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ToolApprovalDecision(BaseModel):
    """User or CLI approval decision for one request."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"tool_approval_{uuid4().hex[:12]}")
    request_id: str
    action_id: str
    status: ToolApprovalStatus
    approved: bool = False
    reason: str = ""
    decided_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ToolExecutionPlan(BaseModel):
    """Explainable plan before executing a local tool action."""

    model_config = ConfigDict(frozen=True)

    action: ToolAction
    risk_decision: ToolRiskDecision
    dry_run: bool = False
    approval_required: bool = False
    blocked: bool = False
    recommended_order: int = 1
    exact_cli_command: str = ""
    explanation: str = ""


class ToolExecutionResult(BaseModel):
    """Persisted execution result for any tool action."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"tool_result_{uuid4().hex[:12]}")
    action_id: str
    status: ToolExecutionStatus
    stdout: str = ""
    stderr: str = ""
    stdout_summary: str = ""
    stderr_summary: str = ""
    exit_code: int | None = None
    files_touched: list[str] = Field(default_factory=list)
    checkpoint_id: str | None = None
    decision_trace_id: str | None = None
    outcome_id: str | None = None
    duration_seconds: float = Field(default=0.0, ge=0)
    timed_out: bool = False
    output_truncated: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("files_touched", mode="after")
    @classmethod
    def _dedupe_files(cls, values: list[str]) -> list[str]:
        return _dedupe_text(values)


class ToolObservation(BaseModel):
    """A compact observation learned from a tool action."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"tool_observation_{uuid4().hex[:12]}")
    action_id: str
    result_id: str | None = None
    observation_type: str
    summary: str
    signal: str = ""
    severity: float = Field(default=0.0, ge=0, le=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class FilesystemReadRequest(BaseModel):
    """Request to read a file inside a workspace."""

    model_config = ConfigDict(frozen=True)

    path: str
    workspace_path: str = "."
    allow_outside_workspace: bool = False
    include_protected_content: bool = False
    max_bytes: int = Field(default=120_000, gt=0)


class FilesystemWriteRequest(BaseModel):
    """Request to write a file; direct overwrite is not used in Phase 5E."""

    model_config = ConfigDict(frozen=True)

    path: str
    content: str
    workspace_path: str = "."
    allow_outside_workspace: bool = False
    overwrite: bool = False


class FilesystemSearchRequest(BaseModel):
    """Simple text search request inside a workspace."""

    model_config = ConfigDict(frozen=True)

    query: str
    path: str = "."
    workspace_path: str = "."
    max_matches: int = Field(default=50, gt=0)
    max_file_bytes: int = Field(default=300_000, gt=0)


class FileMetadata(BaseModel):
    """Safe file metadata for read/list/search outputs."""

    model_config = ConfigDict(frozen=True)

    path: str
    is_file: bool
    is_dir: bool
    size_bytes: int = 0
    modified_at: datetime | None = None
    protected: bool = False
    hash_sha256: str = ""


class FilesystemReadResult(BaseModel):
    """Result of reading a local file."""

    model_config = ConfigDict(frozen=True)

    path: str
    content: str | None
    metadata: FileMetadata
    protected: bool = False
    truncated: bool = False
    message: str = ""


class FilesystemListResult(BaseModel):
    """Result of listing a directory."""

    model_config = ConfigDict(frozen=True)

    path: str
    entries: list[FileMetadata] = Field(default_factory=list)


class FilesystemSearchMatch(BaseModel):
    """One text search match."""

    model_config = ConfigDict(frozen=True)

    path: str
    line_number: int
    line: str


class FilesystemSearchResult(BaseModel):
    """Result of simple text search."""

    model_config = ConfigDict(frozen=True)

    query: str
    path: str
    matches: list[FilesystemSearchMatch] = Field(default_factory=list)
    skipped_protected: list[str] = Field(default_factory=list)
    truncated: bool = False


class PatchProposal(BaseModel):
    """A deterministic single-file find/replace patch proposal."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"patch_{uuid4().hex[:12]}")
    action_id: str | None = None
    workspace_path: str
    path: str
    find: str
    replace: str
    original_hash: str
    diff: str
    files_touched: list[str] = Field(default_factory=list)
    status: str = "proposed"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PatchApplyResult(BaseModel):
    """Result of applying a stored patch proposal."""

    model_config = ConfigDict(frozen=True)

    proposal_id: str
    action_id: str
    applied: bool
    message: str
    files_touched: list[str] = Field(default_factory=list)
    checkpoint_id: str | None = None


class ShellCommandRequest(BaseModel):
    """Request to run a local shell command."""

    model_config = ConfigDict(frozen=True)

    command: str
    cwd: str = "."
    timeout_seconds: int = Field(default=120, gt=0)
    dry_run: bool = False
    yes: bool = False
    require_approval: bool = False
    max_output_chars: int = Field(default=12_000, gt=0)


class ShellCommandResult(BaseModel):
    """Normalized shell command execution result."""

    model_config = ConfigDict(frozen=True)

    command: str
    cwd: str
    status: ToolExecutionStatus
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    duration_seconds: float = Field(default=0.0, ge=0)
    timed_out: bool = False
    output_truncated: bool = False


class CheckpointFileSnapshot(BaseModel):
    """Original content snapshot for one file touched by Hephaestus."""

    model_config = ConfigDict(frozen=True)

    path: str
    existed: bool
    content: str | None = None
    hash_sha256: str = ""
    modified_at: datetime | None = None


class CheckpointRecord(BaseModel):
    """Lightweight rollback checkpoint for files changed by Hephaestus."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"checkpoint_{uuid4().hex[:12]}")
    action_id: str | None = None
    workspace_path: str
    files: list[CheckpointFileSnapshot] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    restored_at: datetime | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def files_touched(self) -> list[str]:
        """Return checkpointed paths in stable order."""

        return [item.path for item in self.files]


class RollbackPlan(BaseModel):
    """Plan for restoring a checkpoint."""

    model_config = ConfigDict(frozen=True)

    checkpoint_id: str
    files: list[str] = Field(default_factory=list)
    can_restore: bool = True
    warnings: list[str] = Field(default_factory=list)


class ToolProposal(BaseModel):
    """Conversation-facing proposed tool action that is not executed."""

    model_config = ConfigDict(frozen=True)

    order: int
    action_type: ToolActionType
    summary: str
    risk_level: ToolRiskLevel
    approval_required: bool
    blocked: bool = False
    exact_cli_command: str
    reasons: list[str] = Field(default_factory=list)


def path_to_text(path: Path | str) -> str:
    """Return a stable resolved path string."""

    return str(Path(path).resolve())


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
