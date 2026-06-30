"""Studio Workbench projections over real Hephaestus runtime records."""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any, Literal, cast

from pydantic import BaseModel, ConfigDict, Field

from hephaestus.coding_loop import (
    CodingChangeProposal,
    CodingLoopDetail,
    CodingLoopExecutor,
    CodingLoopRepository,
    CodingLoopStatus,
    CodingRisk,
    CodingScopeType,
)
from hephaestus.coding_loop.greenfield import GreenfieldCodingExecutor
from hephaestus.coding_loop.schemas import CodingWorkflowMode
from hephaestus.outcomes import (
    LearningSignal,
    OutcomeRecord,
    OutcomeRepository,
    ReflectionRecord,
)
from hephaestus.policy import PolicyProfileType, PolicyRepository
from hephaestus.release import ReleasePlanningResult, ReleasePlanRepository
from hephaestus.repo import RepoProfileRepository
from hephaestus.storage.sqlite import connect_database, init_database
from hephaestus.tool_runtime import (
    CheckpointRecord,
    ToolAction,
    ToolRuntime,
    ToolRuntimeRepository,
)
from hephaestus.tool_runtime.checkpoint import rollback_plan
from hephaestus.tool_runtime.filesystem import is_protected_path
from hephaestus.validation import (
    ValidationExecutionPlan,
    ValidationExecutor,
    ValidationPlanner,
    ValidationRepository,
    ValidationStatus,
    ValidationSuiteResult,
)

WorkbenchTone = Literal["neutral", "accent", "success", "warning", "error"]

_TRUST_SETTINGS_KEY = "local"
_OUTPUT_LIMIT = 4_000
_DIFF_LARGE_THRESHOLD = 850


class TrustMode(StrEnum):
    """Studio-local autonomy modes mapped onto policy profiles."""

    MANUAL = "manual"
    DEVELOPER = "developer"
    LOCAL_POWER_USER = "local_power_user"
    STRICT = "strict"


class TrustRuleKey(StrEnum):
    """Fine-grained local Workbench trust rules."""

    READ_REPO_FILES = "read_repo_files"
    SEARCH_REPO = "search_repo"
    INSPECT_REPO_METADATA = "inspect_repo_metadata"
    CREATE_CODING_PLANS = "create_coding_plans"
    CREATE_PATCH_PROPOSALS = "create_patch_proposals"
    CREATE_CHECKPOINTS = "create_checkpoints"
    RUN_SAFE_VALIDATION = "run_safe_validation"
    APPLY_LOW_RISK_DOC_PATCHES = "apply_low_risk_documentation_patches"
    APPLY_LOW_RISK_CODE_PATCHES = "apply_low_risk_code_patches_with_validation"
    RESTORE_CHECKPOINTS = "restore_checkpoints"
    INSTALL_DEPENDENCIES = "install_dependencies"
    PUSH_GIT_CHANGES = "push_git_changes"
    SEND_EXTERNAL_MESSAGES = "send_external_messages"


class WorkbenchActionState(StrEnum):
    """Long-running action states shown by Studio."""

    QUEUED = "queued"
    PLANNING = "planning"
    PATCHING = "patching"
    AWAITING_APPROVAL = "awaiting_approval"
    APPLYING = "applying"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


class WorkbenchStatus(BaseModel):
    """Small status label with UI tone."""

    model_config = ConfigDict(frozen=True)

    value: str
    label: str
    tone: WorkbenchTone = "neutral"


class WorkbenchLink(BaseModel):
    """A route link for Studio Workbench and chat navigation."""

    model_config = ConfigDict(frozen=True)

    label: str
    href: str


class WorkbenchArtifactSummary(BaseModel):
    """Practical summary card shown on the Workbench overview."""

    model_config = ConfigDict(frozen=True)

    id: str
    kind: str
    title: str
    status: WorkbenchStatus
    repo: str
    repo_path: str
    summary: str = ""
    files_changed: int = 0
    validation: str = ""
    checkpoint: str = ""
    conversation_id: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
    href: str


class PendingDecision(BaseModel):
    """One meaningful user decision surfaced by Workbench."""

    model_config = ConfigDict(frozen=True)

    id: str
    kind: str
    title: str
    description: str
    repo: str
    files: list[str] = Field(default_factory=list)
    risk: str = "medium"
    rollback_available: bool = False
    external_side_effects: bool = False
    primary_label: str
    primary_endpoint: str
    reject_label: str = "Cancel"


class WorkbenchOverviewResponse(BaseModel):
    """Workbench landing response."""

    model_config = ConfigDict(frozen=True)

    active_coding_work: list[WorkbenchArtifactSummary]
    recent_completed_coding_work: list[WorkbenchArtifactSummary]
    recent_validation_runs: list[WorkbenchArtifactSummary]
    failed_validation_requiring_attention: list[WorkbenchArtifactSummary]
    pending_decisions: list[PendingDecision]
    recent_checkpoints: list[WorkbenchArtifactSummary]
    latest_release_evidence: list[WorkbenchArtifactSummary]


class CodingRequestSummary(BaseModel):
    """Coding request row shown in list views."""

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    repo: str
    repo_path: str
    scope: str
    risk: str
    status: WorkbenchStatus
    files_touched: list[str]
    validation_result: str
    checkpoint_state: str
    conversation_id: str | None = None
    conversation_title: str | None = None
    created_at: datetime
    updated_at: datetime
    href: str


class CodingListResponse(BaseModel):
    """Deterministic local coding request search response."""

    model_config = ConfigDict(frozen=True)

    items: list[CodingRequestSummary]
    total: int
    filters: dict[str, str | None]


class CodingPlanView(BaseModel):
    """Human-readable coding plan section."""

    model_config = ConfigDict(frozen=True)

    summary: str
    steps: list[str]
    expected_files: list[str]
    validation_strategy: list[str]
    rollback_behavior: str
    current_state: WorkbenchStatus


class DiffStats(BaseModel):
    """Small diff statistics for UI display."""

    model_config = ConfigDict(frozen=True)

    additions: int = 0
    deletions: int = 0
    line_count: int = 0
    large: bool = False


class CodingPatchView(BaseModel):
    """Patch proposal/application view."""

    model_config = ConfigDict(frozen=True)

    id: str
    status: WorkbenchStatus
    summary: str
    files: list[str]
    proposed: bool = True
    applied: bool = False
    diff: str
    diff_stats: DiffStats
    review_result: str
    protected_files: list[str] = Field(default_factory=list)


class ValidationCommandView(BaseModel):
    """User-readable validation command evidence."""

    model_config = ConfigDict(frozen=True)

    id: str
    command_type: str
    command: str
    risk: str = ""
    status: WorkbenchStatus
    exit_code: int | None = None
    duration_seconds: float = 0.0
    output_summary: str = ""
    stdout: str = ""
    stderr: str = ""
    output_truncated: bool = False
    tool_action_id: str | None = None
    outcome_id: str | None = None
    readiness_effect: int = 0


class ValidationSummary(BaseModel):
    """Validation suite row."""

    model_config = ConfigDict(frozen=True)

    id: str
    repo: str
    repo_path: str
    related_coding_request_id: str | None = None
    release_plan_id: str | None = None
    evidence_mode: str
    total_commands: int
    passed: int
    failed: int
    skipped: int
    duration_seconds: float
    status: WorkbenchStatus
    created_at: datetime
    href: str


class ValidationListResponse(BaseModel):
    """Recent validation runs."""

    model_config = ConfigDict(frozen=True)

    items: list[ValidationSummary]
    total: int


class ValidationDetailResponse(BaseModel):
    """Validation result detail."""

    model_config = ConfigDict(frozen=True)

    summary: ValidationSummary
    commands: list[ValidationCommandView]
    linked_tool_actions: list[WorkbenchLink]
    linked_outcomes: list[WorkbenchLink]


class ValidationPlanResponse(BaseModel):
    """Validation plan created from repo intelligence."""

    model_config = ConfigDict(frozen=True)

    id: str
    repo: str
    repo_path: str
    commands: list[ValidationCommandView]
    notes: list[str]
    status: WorkbenchStatus


class CheckpointFileView(BaseModel):
    """Checkpointed file row."""

    model_config = ConfigDict(frozen=True)

    path: str
    existed: bool
    original_hash: str
    protected: bool = False
    modified_at: datetime | None = None


class CheckpointSummary(BaseModel):
    """Checkpoint list row."""

    model_config = ConfigDict(frozen=True)

    id: str
    created_at: datetime
    associated_coding_request_id: str | None = None
    files_covered: list[str]
    availability: str
    restored_at: datetime | None = None
    href: str


class CheckpointDetailResponse(BaseModel):
    """Checkpoint detail and rollback plan."""

    model_config = ConfigDict(frozen=True)

    summary: CheckpointSummary
    workspace_path: str
    files: list[CheckpointFileView]
    related_patch_id: str | None = None
    validation_result: str = ""
    restore_warnings: list[str] = Field(default_factory=list)
    restore_history: list[WorkbenchLink] = Field(default_factory=list)


class ToolActionSummary(BaseModel):
    """Tool action list row."""

    model_config = ConfigDict(frozen=True)

    id: str
    action: str
    status: WorkbenchStatus
    risk: str
    policy_decision: str
    result: str
    related_coding_request_id: str | None = None
    related_validation_id: str | None = None
    created_at: datetime
    href: str


class ToolActionDetailResponse(BaseModel):
    """Tool action detail."""

    model_config = ConfigDict(frozen=True)

    summary: ToolActionSummary
    workspace_path: str
    command: str = ""
    target_path: str = ""
    files_touched: list[str]
    stdout: str = ""
    stderr: str = ""
    exit_code: int | None = None
    checkpoint_id: str | None = None
    outcome_id: str | None = None
    observations: list[str] = Field(default_factory=list)


class ReleaseSummary(BaseModel):
    """Release evidence list row."""

    model_config = ConfigDict(frozen=True)

    id: str
    repo: str
    repo_path: str
    readiness: int
    evidence_mode: str
    validation_status: str
    blockers: list[str]
    recommendation: str
    created_at: datetime
    linked_work: list[WorkbenchLink] = Field(default_factory=list)
    href: str


class ReleaseListResponse(BaseModel):
    """Release evidence list."""

    model_config = ConfigDict(frozen=True)

    items: list[ReleaseSummary]
    total: int


class ReleaseDetailResponse(BaseModel):
    """Release plan detail."""

    model_config = ConfigDict(frozen=True)

    summary: ReleaseSummary
    practical_summary: str
    real_validation_evidence: list[ValidationSummary]
    blockers: list[str]
    next_actions: list[str]
    related_coding_requests: list[CodingRequestSummary]
    advanced_optimization_details: dict[str, list[str]]


class OutcomeSummary(BaseModel):
    """Human-language outcome row."""

    model_config = ConfigDict(frozen=True)

    id: str
    what_happened: str
    evidence: str
    status: WorkbenchStatus
    rollback: str
    practical_lesson: str = ""
    related_task: str = ""
    observed_at: datetime
    href: str


class OutcomeListResponse(BaseModel):
    """Outcome list."""

    model_config = ConfigDict(frozen=True)

    items: list[OutcomeSummary]
    total: int


class OutcomeDetailResponse(BaseModel):
    """Outcome detail with meaningful learning only."""

    model_config = ConfigDict(frozen=True)

    summary: OutcomeSummary
    evidence_items: list[str]
    reflections: list[str]
    what_hephaestus_learned: list[str]
    related_links: list[WorkbenchLink]


class CodingDetailResponse(BaseModel):
    """Readable coding detail view."""

    model_config = ConfigDict(frozen=True)

    summary: CodingRequestSummary
    original_user_request: str
    linked_conversation: WorkbenchLink | None = None
    policy_trust_profile: str
    plan: CodingPlanView | None = None
    changes: list[CodingPatchView]
    validation: list[ValidationDetailResponse]
    result: str
    practical_next_step: str
    checkpoint_available: bool
    rollback_available: bool
    advanced_details: dict[str, list[str]]
    plan_id: str | None = None
    manifest_available: bool = False
    provider_usage: str = ""


class TrustRule(BaseModel):
    """One local trust setting row."""

    model_config = ConfigDict(frozen=True)

    key: TrustRuleKey
    label: str
    allowed: bool
    implemented: bool = True
    risk: str = "safe"
    hard_blocked: bool = False


class TrustSettingsResponse(BaseModel):
    """Local Studio trust settings and effective behavior."""

    model_config = ConfigDict(frozen=True)

    mode: TrustMode
    effective_policy_profile: str
    rules: list[TrustRule]
    effective_behavior: list[str]
    hard_blocks: list[str]
    updated_at: datetime


class TrustPatchRequest(BaseModel):
    """Patch local trust settings."""

    model_config = ConfigDict(frozen=True)

    mode: TrustMode | None = None
    rules: dict[TrustRuleKey, bool] | None = None


class CodingPlanRequest(BaseModel):
    """Create a Workbench coding plan."""

    model_config = ConfigDict(frozen=True)

    user_request: str = Field(min_length=1)
    repo_path: str = "."
    scope: CodingScopeType | None = None
    conversation_id: str | None = None
    workflow_mode: CodingWorkflowMode = CodingWorkflowMode.PLAN
    provider: str = "auto"
    max_calls: int = Field(default=3, ge=1)
    max_output_tokens: int = Field(default=4096, ge=1)
    estimated_cost_cap: float = Field(default=0.05, gt=0)


class CodingProposeRequest(CodingPlanRequest):
    """Create a Workbench patch proposal."""


class CodingApplyRequest(BaseModel):
    """Apply a coding change as one approved batch."""

    model_config = ConfigDict(frozen=True)

    approved: bool = False
    dry_run: bool = False
    no_validate: bool = False
    rollback_on_failure: bool = False
    allow_one_repair: bool = False
    retain_failed_snapshot: bool = False
    artifact_root: str | None = None


class ValidationPlanRequest(BaseModel):
    """Plan validation from a repo path."""

    model_config = ConfigDict(frozen=True)

    repo_path: str = "."
    release_plan_id: str | None = None


class ValidationRunRequest(BaseModel):
    """Run or dry-run validation from Studio."""

    model_config = ConfigDict(frozen=True)

    repo_path: str = "."
    plan_id: str | None = None
    release_plan_id: str | None = None
    approved: bool = False
    dry_run: bool = False
    stop_on_failure: bool = False


class CheckpointRestoreRequest(BaseModel):
    """Restore a checkpoint as one approved action."""

    model_config = ConfigDict(frozen=True)

    approved: bool = False
    dry_run: bool = False


class WorkbenchService:
    """Project real backend artifacts into calm Studio Workbench views."""

    def __init__(self, database_path: Path | str | None = None) -> None:
        self.database_path = init_database(database_path)
        self.coding_repository = CodingLoopRepository(self.database_path)
        self.validation_repository = ValidationRepository(self.database_path)
        self.tool_repository = ToolRuntimeRepository(self.database_path)
        self.release_repository = ReleasePlanRepository(self.database_path)
        self.outcome_repository = OutcomeRepository(self.database_path)
        self.policy_repository = PolicyRepository(self.database_path)
        self.repo_repository = RepoProfileRepository(self.database_path)

    def overview(self) -> WorkbenchOverviewResponse:
        """Return practical current work for the Workbench landing page."""

        coding = self.list_coding(limit=80).items
        active = [
            _artifact_from_coding(item)
            for item in coding
            if item.status.value
            in {
                CodingLoopStatus.PLANNED.value,
                CodingLoopStatus.PATCH_PROPOSED.value,
                CodingLoopStatus.REQUIRES_APPROVAL.value,
                CodingLoopStatus.VALIDATION_RUNNING.value,
                CodingLoopStatus.VALIDATION_FAILED.value,
                CodingLoopStatus.BLOCKED.value,
                CodingLoopStatus.NEEDS_USER_INPUT.value,
            }
        ][:6]
        completed = [
            _artifact_from_coding(item)
            for item in coding
            if item.status.value
            in {
                CodingLoopStatus.COMPLETED.value,
                CodingLoopStatus.VALIDATION_PASSED.value,
                CodingLoopStatus.ROLLED_BACK.value,
            }
        ][:6]
        validations = self.list_validation(limit=20).items
        checkpoints = self.list_checkpoints(limit=8)
        releases = self.list_releases(limit=6).items
        return WorkbenchOverviewResponse(
            active_coding_work=active,
            recent_completed_coding_work=completed,
            recent_validation_runs=[_artifact_from_validation(item) for item in validations[:6]],
            failed_validation_requiring_attention=[
                _artifact_from_validation(item)
                for item in validations
                if item.status.value != ValidationStatus.PASSED.value
            ][:6],
            pending_decisions=self.pending_decisions(),
            recent_checkpoints=[_artifact_from_checkpoint(item) for item in checkpoints[:6]],
            latest_release_evidence=[_artifact_from_release(item) for item in releases[:3]],
        )

    def list_coding(
        self,
        *,
        status_filter: str | None = None,
        repo: str | None = None,
        conversation: str | None = None,
        query: str = "",
        limit: int = 100,
    ) -> CodingListResponse:
        """List coding requests with deterministic local filters."""

        rows = self._coding_request_rows(limit=max(limit * 3, limit))
        items = [
            self._coding_summary_from_row(row)
            for row in rows
            if self._coding_row_matches(row, status_filter, repo, conversation, query)
        ][:limit]
        return CodingListResponse(
            items=items,
            total=len(items),
            filters={
                "status": status_filter,
                "repo": repo,
                "conversation": conversation,
                "query": query or None,
            },
        )

    def get_coding(self, request_id: str) -> CodingDetailResponse | None:
        """Return one readable coding detail."""

        detail = self.coding_repository.show_result(request_id)
        if detail.request is None:
            return None
        row = self._coding_request_row(detail.request.id)
        if row is None:
            return None
        summary = self._coding_summary_from_row(row)
        conversation_link = None
        if summary.conversation_id is not None:
            conversation_link = WorkbenchLink(
                label=summary.conversation_title or "Open linked conversation",
                href=f"/conversations/{summary.conversation_id}",
            )
        validation_details = [
            item
            for result_id in _validation_ids(detail)
            if (item := self.get_validation(result_id)) is not None
        ]
        return CodingDetailResponse(
            summary=summary,
            original_user_request=detail.request.user_request,
            linked_conversation=conversation_link,
            policy_trust_profile=_trust_profile_label(self.trust_settings()),
            plan=_plan_view(detail),
            changes=_patch_views(detail),
            validation=validation_details,
            result=_result_summary(detail),
            practical_next_step=_practical_next_step(detail),
            checkpoint_available=bool(_checkpoint_ids(detail)),
            rollback_available=any(
                self.tool_repository.get_checkpoint(checkpoint_id) is not None
                and self.tool_repository.get_checkpoint(checkpoint_id).restored_at is None  # type: ignore[union-attr]
                for checkpoint_id in _checkpoint_ids(detail)
            ),
            advanced_details={
                "decision_traces": _decision_trace_ids(detail),
                "tool_actions": _tool_action_ids(detail),
                "outcomes": _outcome_ids(detail),
                "learning_signals": _learning_signal_ids(detail),
            },
            plan_id=detail.plan.id if detail.plan is not None else None,
            manifest_available=bool(detail.change and detail.change.manifest),
            provider_usage=(
                (
                    f"{detail.plan.provider_name}/{detail.plan.provider_model} · "
                    f"{detail.plan.budget.calls} calls · "
                    f"{detail.plan.budget.input_tokens}/{detail.plan.budget.output_tokens} tokens · "
                    f"${detail.plan.budget.estimated_cost:.6f}"
                )
                if detail.plan is not None
                else ""
            ),
        )

    def create_coding_plan(self, request: CodingPlanRequest) -> CodingDetailResponse:
        """Create a coding plan through the Python orchestrator."""

        if request.scope is not None:
            coding_request, _plan = CodingLoopExecutor(self.database_path).plan(
                request.user_request,
                repo_path=request.repo_path,
                scope=request.scope,
                conversation_id=request.conversation_id,
            )
        else:
            coding_request, _plan = GreenfieldCodingExecutor(self.database_path).plan(
                request.user_request,
                repo_path=request.repo_path,
                provider=request.provider,
                workflow_mode=request.workflow_mode,
                max_calls=request.max_calls,
                max_output_tokens=request.max_output_tokens,
                estimated_cost_cap=request.estimated_cost_cap,
            )
            if request.conversation_id is not None:
                self._attach_coding_request_to_conversation(
                    coding_request.id, request.conversation_id
                )
        detail = self.get_coding(coding_request.id)
        if detail is None:
            raise RuntimeError("Coding plan was created but could not be reloaded.")
        return detail

    def prepare_coding_manifest(self, plan_id: str, *, approved: bool) -> CodingDetailResponse:
        change = GreenfieldCodingExecutor(self.database_path).prepare(plan_id, approved=approved)
        detail = self.get_coding(change.request_id)
        if detail is None:
            raise RuntimeError("Coding manifest was created but could not be reloaded.")
        return detail

    def propose_coding_change(self, request: CodingProposeRequest) -> CodingDetailResponse:
        """Create a patch proposal through the Python orchestrator."""

        coding_request, _plan, _change = CodingLoopExecutor(self.database_path).propose(
            request.user_request,
            repo_path=request.repo_path,
            scope=request.scope,
        )
        if request.conversation_id is not None:
            self._attach_coding_request_to_conversation(coding_request.id, request.conversation_id)
        detail = self.get_coding(coding_request.id)
        if detail is None:
            raise RuntimeError("Coding proposal was created but could not be reloaded.")
        return detail

    def apply_coding_change(
        self,
        change_id: str,
        request: CodingApplyRequest,
    ) -> CodingDetailResponse:
        """Apply a patch proposal as one Studio-approved batch."""

        change = self.coding_repository.get_change_proposal(change_id)
        if change is None:
            raise ValueError(f"Coding change not found: {change_id}")
        yes = request.approved or self._can_auto_apply_change(change)
        result = CodingLoopExecutor(self.database_path).apply_change(
            change_id,
            yes=yes,
            dry_run=request.dry_run,
            no_validate=request.no_validate,
            rollback_on_failure=request.rollback_on_failure,
            allow_one_repair=request.allow_one_repair,
            retain_failed_snapshot=request.retain_failed_snapshot,
            artifact_root=request.artifact_root,
        )
        detail = self.get_coding(result.request_id)
        if detail is None:
            raise RuntimeError("Coding change was applied but could not be reloaded.")
        return detail

    def list_validation(self, *, limit: int = 100) -> ValidationListResponse:
        """List recent validation runs."""

        suites = self.validation_repository.list_suite_results(limit=limit)
        items = [self._validation_summary(suite) for suite in suites]
        return ValidationListResponse(items=items, total=len(items))

    def get_validation(self, result_id: str) -> ValidationDetailResponse | None:
        """Return one validation result detail."""

        suite = self.validation_repository.get_suite_result(result_id)
        if suite is None:
            return None
        summary = self._validation_summary(suite)
        evidence = suite.evidence or self.validation_repository.list_evidence_for_result(suite.id)
        commands = [
            ValidationCommandView(
                id=item.id,
                command_type=item.command_type.value,
                command=_redact(item.command),
                risk="",
                status=_validation_status(item.status.value),
                exit_code=item.exit_code,
                duration_seconds=item.duration_seconds,
                output_summary=_redact(item.stdout_summary or item.stderr_summary),
                stdout=_truncate(_redact(item.stdout_summary)),
                stderr=_truncate(_redact(item.stderr_summary)),
                output_truncated=item.output_truncated,
                tool_action_id=item.tool_action_id,
                outcome_id=item.outcome_id,
                readiness_effect=suite.readiness_impact,
            )
            for item in evidence
        ]
        return ValidationDetailResponse(
            summary=summary,
            commands=commands,
            linked_tool_actions=[
                WorkbenchLink(label=command.tool_action_id, href=f"/workbench/tools/{command.tool_action_id}")
                for command in commands
                if command.tool_action_id is not None
            ],
            linked_outcomes=[
                WorkbenchLink(label=command.outcome_id, href=f"/workbench/outcomes/{command.outcome_id}")
                for command in commands
                if command.outcome_id is not None
            ],
        )

    def plan_validation(self, request: ValidationPlanRequest) -> ValidationPlanResponse:
        """Create a validation plan."""

        plan = ValidationPlanner(self.database_path).build_plan(
            request.repo_path,
            release_plan_id=request.release_plan_id,
            persist=True,
        )
        return self._validation_plan_response(plan)

    def run_validation(self, request: ValidationRunRequest) -> ValidationDetailResponse:
        """Run or dry-run validation through the Python executor."""

        plan = (
            self.validation_repository.get_plan(request.plan_id)
            if request.plan_id is not None
            else None
        )
        yes = request.approved or self._trust_allows(TrustRuleKey.RUN_SAFE_VALIDATION)
        suite = ValidationExecutor(self.database_path, workspace_path=request.repo_path).run(
            request.repo_path,
            plan=plan,
            dry_run=request.dry_run,
            yes=yes,
            stop_on_failure=request.stop_on_failure,
            release_plan_id=request.release_plan_id,
        )
        detail = self.get_validation(suite.id)
        if detail is None:
            raise RuntimeError("Validation result was created but could not be reloaded.")
        return detail

    def list_checkpoints(self, *, limit: int = 100) -> list[CheckpointSummary]:
        """List recent checkpoints."""

        return [
            self._checkpoint_summary(checkpoint)
            for checkpoint in self.tool_repository.list_checkpoints(limit=limit)
        ]

    def get_checkpoint(self, checkpoint_id: str) -> CheckpointDetailResponse | None:
        """Return one checkpoint detail."""

        checkpoint = self.tool_repository.get_checkpoint(checkpoint_id)
        if checkpoint is None:
            return None
        summary = self._checkpoint_summary(checkpoint)
        plan = rollback_plan(checkpoint)
        restore_history = [
            WorkbenchLink(label=action.id, href=f"/workbench/tools/{action.id}")
            for action in self.tool_repository.list_actions(limit=200)
            if action.action_type.value == "restore_checkpoint"
            and action.target_path == checkpoint.id
        ]
        return CheckpointDetailResponse(
            summary=summary,
            workspace_path=checkpoint.workspace_path,
            files=[
                CheckpointFileView(
                    path=item.path,
                    existed=item.existed,
                    original_hash=item.hash_sha256,
                    protected=is_protected_path(item.path),
                    modified_at=item.modified_at,
                )
                for item in checkpoint.files
            ],
            related_patch_id=self._patch_for_checkpoint(checkpoint.id),
            validation_result=self._validation_for_checkpoint(checkpoint.id),
            restore_warnings=plan.warnings,
            restore_history=restore_history,
        )

    def restore_checkpoint(
        self,
        checkpoint_id: str,
        request: CheckpointRestoreRequest,
    ) -> CheckpointDetailResponse:
        """Restore a checkpoint through the Python runtime."""

        checkpoint = self.tool_repository.get_checkpoint(checkpoint_id)
        if checkpoint is None:
            raise ValueError(f"Checkpoint not found: {checkpoint_id}")
        yes = request.approved or self._trust_allows(TrustRuleKey.RESTORE_CHECKPOINTS)
        runtime = ToolRuntime(self.database_path, workspace_path=checkpoint.workspace_path)
        runtime.restore_checkpoint(checkpoint_id, yes=yes, dry_run=request.dry_run)
        detail = self.get_checkpoint(checkpoint_id)
        if detail is None:
            raise RuntimeError("Checkpoint restore result could not be reloaded.")
        return detail

    def list_tool_actions(self, *, limit: int = 100) -> list[ToolActionSummary]:
        """List recent tool actions in plain language."""

        return [
            self._tool_action_summary(action)
            for action in self.tool_repository.list_actions(limit=limit)
        ]

    def get_tool_action(self, action_id: str) -> ToolActionDetailResponse | None:
        """Return one tool action detail."""

        action = self.tool_repository.get_action(action_id)
        if action is None:
            return None
        summary = self._tool_action_summary(action)
        results = self.tool_repository.list_results_for_action(action.id)
        result = results[-1] if results else None
        observations = self.tool_repository.list_observations_for_action(action.id)
        return ToolActionDetailResponse(
            summary=summary,
            workspace_path=action.workspace_path,
            command=_redact(action.command),
            target_path=_protected_path_label(action.target_path),
            files_touched=[_protected_path_label(path) for path in action.files_touched],
            stdout=_truncate(_redact(result.stdout if result is not None else "")),
            stderr=_truncate(_redact(result.stderr if result is not None else "")),
            exit_code=result.exit_code if result is not None else action.exit_code,
            checkpoint_id=action.checkpoint_id,
            outcome_id=action.outcome_id,
            observations=[_redact(item.summary) for item in observations],
        )

    def list_releases(self, *, limit: int = 100) -> ReleaseListResponse:
        """List release evidence."""

        plans = self.release_repository.list_release_plans(limit=limit)
        items = [self._release_summary(plan) for plan in plans]
        return ReleaseListResponse(items=items, total=len(items))

    def get_release(self, release_plan_id: str) -> ReleaseDetailResponse | None:
        """Return one release plan detail."""

        plan = self.release_repository.get_release_plan(release_plan_id)
        if plan is None:
            return None
        summary = self._release_summary(plan)
        validation_items = [
            item
            for result_id in [plan.validation_result_id]
            if result_id is not None
            if (item := self.validation_repository.get_suite_result(result_id)) is not None
        ]
        related_coding = [
            item
            for item in self.list_coding(limit=100).items
            if item.repo_path == summary.repo_path
        ][:8]
        return ReleaseDetailResponse(
            summary=summary,
            practical_summary=plan.recommendation.summary,
            real_validation_evidence=[
                self._validation_summary(item) for item in validation_items
            ],
            blockers=summary.blockers,
            next_actions=plan.recommendation.next_steps,
            related_coding_requests=related_coding,
            advanced_optimization_details={
                "pareto_frontier_ids": plan.pareto_frontier_ids,
                "qubo_problem_ids": plan.qubo_problem_ids,
            },
        )

    def list_outcomes(self, *, limit: int = 100) -> OutcomeListResponse:
        """List outcomes in newest-first order."""

        outcomes = sorted(
            self.outcome_repository.list_outcomes(),
            key=lambda item: item.observed_at,
            reverse=True,
        )[:limit]
        items = [self._outcome_summary(outcome) for outcome in outcomes]
        return OutcomeListResponse(items=items, total=len(items))

    def get_outcome(self, outcome_id: str) -> OutcomeDetailResponse | None:
        """Return one outcome detail with meaningful learning signals."""

        outcome = self.outcome_repository.get_outcome(outcome_id)
        if outcome is None:
            return None
        reflections = self.outcome_repository.list_reflections(outcome_id=outcome.id)
        signals = self.outcome_repository.list_learning_signals(outcome_id=outcome.id)
        return OutcomeDetailResponse(
            summary=self._outcome_summary(outcome),
            evidence_items=[_redact(item.content) for item in outcome.evidence],
            reflections=_reflection_lines(reflections),
            what_hephaestus_learned=_learning_lines(signals),
            related_links=[
                WorkbenchLink(label=outcome.decision_trace_id, href=f"/workbench/outcomes/{outcome.id}")
            ],
        )

    def trust_settings(self) -> TrustSettingsResponse:
        """Read local trust settings, creating defaults when absent."""

        stored = self._read_trust_raw()
        if stored is None:
            settings = _default_trust_settings(TrustMode.DEVELOPER)
            self._write_trust(settings)
            return settings
        return stored

    def update_trust(self, request: TrustPatchRequest) -> TrustSettingsResponse:
        """Patch local trust settings and synchronize the active policy profile."""

        current = self.trust_settings()
        mode = request.mode or current.mode
        existing = {rule.key: rule.allowed for rule in current.rules}
        if request.rules:
            existing.update(request.rules)
        settings = _trust_settings_from_values(mode, existing)
        self._write_trust(settings)
        self.policy_repository.set_active_profile(_policy_profile_for_trust(mode))
        return settings

    def pending_decisions(self) -> list[PendingDecision]:
        """Return meaningful pending decisions only."""

        decisions: list[PendingDecision] = []
        for item in self.list_coding(limit=100).items:
            if item.status.value in {
                CodingLoopStatus.PATCH_PROPOSED.value,
                CodingLoopStatus.REQUIRES_APPROVAL.value,
            }:
                detail = self.coding_repository.show_result(item.id)
                change_id = detail.change.id if detail.change is not None else item.id
                decisions.append(
                    PendingDecision(
                        id=f"approve_patch:{item.id}",
                        kind="approve_patch_batch",
                        title=f"Approve patch for {item.title}",
                        description="Apply the proposed patch batch through the Python runtime.",
                        repo=item.repo,
                        files=item.files_touched,
                        risk=item.risk,
                        rollback_available=True,
                        external_side_effects=False,
                        primary_label="Apply patch",
                        primary_endpoint=f"/api/coding/{change_id}/apply",
                    )
                )
            if item.status.value == CodingLoopStatus.VALIDATION_FAILED.value:
                decisions.append(
                    PendingDecision(
                        id=f"retry_validation:{item.id}",
                        kind="retry_validation",
                        title=f"Retry validation for {item.title}",
                        description="Run the detected validation commands again.",
                        repo=item.repo,
                        files=item.files_touched,
                        risk="safe_validation",
                        rollback_available=item.checkpoint_state != "none",
                        external_side_effects=False,
                        primary_label="Retry validation",
                        primary_endpoint="/api/validation/run",
                    )
                )
        return decisions[:8]

    def _coding_request_rows(self, *, limit: int) -> list[sqlite3.Row]:
        with connect_database(self.database_path) as connection:
            return connection.execute(
                """
                SELECT *
                FROM coding_requests
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

    def _coding_request_row(self, request_id: str) -> sqlite3.Row | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM coding_requests WHERE id = ?",
                (request_id,),
            ).fetchone()
        return cast(sqlite3.Row | None, row)

    def _coding_row_matches(
        self,
        row: sqlite3.Row,
        status_filter: str | None,
        repo: str | None,
        conversation: str | None,
        query: str,
    ) -> bool:
        status = _row_str(row, "status")
        status_groups = {
            "active": {
                "planned",
                "patch_proposed",
                "requires_approval",
                "validation_running",
                "validation_failed",
                "blocked",
                "needs_user_input",
            },
            "completed": {"completed", "validation_passed"},
            "failed": {"validation_failed", "blocked"},
            "rolled_back": {"rolled_back"},
            "needs_input": {"needs_user_input", "requires_approval", "scope_too_large"},
        }
        if status_filter:
            allowed = status_groups.get(status_filter, {status_filter})
            if status not in allowed:
                return False
        if repo and repo.lower() not in _row_str(row, "repo_path").lower():
            return False
        if conversation and conversation != _row_optional_str(row, "conversation_id"):
            return False
        if query.strip():
            haystack = " ".join(
                [
                    _row_str(row, "user_request"),
                    _row_str(row, "repo_path"),
                    _row_str(row, "plan_summary"),
                    " ".join(_json_list(_row_str(row, "likely_files_json"))),
                ]
            ).lower()
            if query.strip().lower() not in haystack:
                return False
        return True

    def _coding_summary_from_row(self, row: sqlite3.Row) -> CodingRequestSummary:
        request_id = _row_str(row, "id")
        detail = self.coding_repository.show_result(request_id)
        files = _files_for_coding(row, detail)
        conversation_id = _row_optional_str(row, "conversation_id")
        conversation_title = self._conversation_title(conversation_id) if conversation_id else None
        status = _coding_status(_row_str(row, "status"))
        validation_result = _validation_label(detail)
        checkpoints = _checkpoint_ids(detail) or _json_list(_row_str(row, "checkpoint_ids_json"))
        return CodingRequestSummary(
            id=request_id,
            title=_title_from_request(_row_str(row, "user_request")),
            repo=_repo_label(_row_str(row, "repo_path")),
            repo_path=_row_str(row, "repo_path"),
            scope=_row_str(row, "scope_type"),
            risk=_row_str(row, "risk"),
            status=status,
            files_touched=files,
            validation_result=validation_result,
            checkpoint_state=_checkpoint_label(checkpoints, self.tool_repository),
            conversation_id=conversation_id,
            conversation_title=conversation_title,
            created_at=_datetime_from_text(_row_str(row, "created_at")),
            updated_at=_datetime_from_text(_row_str(row, "updated_at")),
            href=f"/workbench/coding/{request_id}",
        )

    def _validation_summary(self, suite: ValidationSuiteResult) -> ValidationSummary:
        related_request = self._coding_request_for_validation(suite.id)
        return ValidationSummary(
            id=suite.id,
            repo=_repo_label(suite.repo_path),
            repo_path=suite.repo_path,
            related_coding_request_id=related_request,
            release_plan_id=suite.release_plan_id,
            evidence_mode=suite.evidence_mode,
            total_commands=len(suite.command_results),
            passed=suite.pass_count,
            failed=suite.fail_count + suite.timed_out_count + suite.blocked_count,
            skipped=suite.skipped_count,
            duration_seconds=suite.duration_seconds,
            status=_validation_status(suite.status.value),
            created_at=suite.created_at,
            href=f"/workbench/validation/{suite.id}",
        )

    def _validation_plan_response(self, plan: ValidationExecutionPlan) -> ValidationPlanResponse:
        return ValidationPlanResponse(
            id=plan.id,
            repo=_repo_label(plan.repo_path),
            repo_path=plan.repo_path,
            commands=[
                ValidationCommandView(
                    id=command.id,
                    command_type=command.command_type.value,
                    command=_redact(command.command),
                    risk=command.risk_level.value,
                    status=_validation_status(
                        "blocked" if command.blocked else "requires_approval"
                    ),
                    output_summary=", ".join(command.reasons),
                )
                for command in plan.commands
            ],
            notes=plan.notes,
            status=WorkbenchStatus(value="planned", label="Planned", tone="neutral"),
        )

    def _checkpoint_summary(self, checkpoint: CheckpointRecord) -> CheckpointSummary:
        return CheckpointSummary(
            id=checkpoint.id,
            created_at=checkpoint.created_at,
            associated_coding_request_id=self._coding_request_for_checkpoint(checkpoint.id),
            files_covered=checkpoint.files_touched,
            availability="restored" if checkpoint.restored_at is not None else "available",
            restored_at=checkpoint.restored_at,
            href=f"/workbench/checkpoints/{checkpoint.id}",
        )

    def _tool_action_summary(self, action: ToolAction) -> ToolActionSummary:
        validation_id = self._validation_for_tool_action(action.id)
        coding_request_id = self._coding_request_for_tool_action(action.id)
        result = action.stdout_summary or action.stderr_summary or action.execution_status.value
        return ToolActionSummary(
            id=action.id,
            action=_plain_tool_action(action),
            status=_tool_status(action.execution_status.value),
            risk=action.risk_level.value,
            policy_decision=_policy_decision_from_action(action),
            result=_redact(result),
            related_coding_request_id=coding_request_id,
            related_validation_id=validation_id,
            created_at=action.created_at,
            href=f"/workbench/tools/{action.id}",
        )

    def _release_summary(self, plan: ReleasePlanningResult) -> ReleaseSummary:
        repo = self.repo_repository.get_profile(plan.repo_profile_id)
        validation_status = (
            plan.validation_summary.status.value
            if plan.validation_summary is not None
            else "not_run"
        )
        blockers = [
            risk.summary
            for risk in plan.recommendation.risks
            if risk.level.value in {"high", "destructive", "external_side_effect"}
        ]
        linked = []
        if plan.validation_result_id is not None:
            linked.append(
                WorkbenchLink(
                    label="Validation evidence",
                    href=f"/workbench/validation/{plan.validation_result_id}",
                )
            )
        return ReleaseSummary(
            id=plan.id,
            repo=repo.name if repo is not None else plan.repo_profile_id,
            repo_path=repo.path if repo is not None else "",
            readiness=plan.readiness_score,
            evidence_mode=plan.evidence_mode,
            validation_status=validation_status,
            blockers=blockers,
            recommendation=plan.recommendation.summary,
            created_at=plan.created_at,
            linked_work=linked,
            href=f"/workbench/releases/{plan.id}",
        )

    def _outcome_summary(self, outcome: OutcomeRecord) -> OutcomeSummary:
        learning = self.outcome_repository.list_learning_signals(outcome_id=outcome.id)
        lesson = _learning_lines(learning)
        return OutcomeSummary(
            id=outcome.id,
            what_happened=_redact(outcome.summary),
            evidence=_redact(outcome.evidence[0].content if outcome.evidence else ""),
            status=_outcome_status(outcome.status.value),
            rollback=_rollback_text(outcome),
            practical_lesson=lesson[0] if lesson else "",
            related_task=outcome.run_id,
            observed_at=outcome.observed_at,
            href=f"/workbench/outcomes/{outcome.id}",
        )

    def _conversation_title(self, conversation_id: str | None) -> str | None:
        if conversation_id is None:
            return None
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT COALESCE(NULLIF(display_title, ''), title) AS title
                FROM conversation_sessions
                WHERE id = ?
                """,
                (conversation_id,),
            ).fetchone()
        return _row_optional_str(row, "title") if row is not None else None

    def _coding_request_for_validation(self, validation_id: str) -> str | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT id
                FROM coding_requests
                WHERE validation_result_ids_json LIKE ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (f"%{validation_id}%",),
            ).fetchone()
        return _row_optional_str(row, "id") if row is not None else None

    def _coding_request_for_checkpoint(self, checkpoint_id: str) -> str | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT request_id
                FROM coding_loop_results
                WHERE checkpoint_ids_json LIKE ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (f"%{checkpoint_id}%",),
            ).fetchone()
        return _row_optional_str(row, "request_id") if row is not None else None

    def _coding_request_for_tool_action(self, action_id: str) -> str | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT id
                FROM coding_requests
                WHERE tool_action_ids_json LIKE ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (f"%{action_id}%",),
            ).fetchone()
        return _row_optional_str(row, "id") if row is not None else None

    def _validation_for_tool_action(self, action_id: str) -> str | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT validation_result_id
                FROM validation_evidence
                WHERE tool_action_id = ?
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (action_id,),
            ).fetchone()
        return _row_optional_str(row, "validation_result_id") if row is not None else None

    def _patch_for_checkpoint(self, checkpoint_id: str) -> str | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT patch_id
                FROM tool_actions
                WHERE checkpoint_id = ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (checkpoint_id,),
            ).fetchone()
        return _row_optional_str(row, "patch_id") if row is not None else None

    def _validation_for_checkpoint(self, checkpoint_id: str) -> str:
        request_id = self._coding_request_for_checkpoint(checkpoint_id)
        if request_id is None:
            return ""
        detail = self.coding_repository.show_result(request_id)
        return _validation_label(detail)

    def _attach_coding_request_to_conversation(self, request_id: str, conversation_id: str) -> None:
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                UPDATE coding_requests
                SET conversation_id = ?, updated_at = ?
                WHERE id = ?
                """,
                (conversation_id, _datetime_to_text(datetime.now(UTC)), request_id),
            )

    def _can_auto_apply_change(self, change: CodingChangeProposal) -> bool:
        if change.risk != CodingRisk.LOW:
            return False
        if change.scope_type == CodingScopeType.DOCS:
            return self._trust_allows(TrustRuleKey.APPLY_LOW_RISK_DOC_PATCHES)
        return self._trust_allows(TrustRuleKey.APPLY_LOW_RISK_CODE_PATCHES)

    def _trust_allows(self, key: TrustRuleKey) -> bool:
        return any(rule.key == key and rule.allowed for rule in self.trust_settings().rules)

    def _read_trust_raw(self) -> TrustSettingsResponse | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT raw_json FROM studio_trust_settings WHERE id = ?",
                (_TRUST_SETTINGS_KEY,),
            ).fetchone()
        if row is None:
            return None
        raw = _json_dict(_row_str(row, "raw_json"))
        return TrustSettingsResponse.model_validate(raw)

    def _write_trust(self, settings: TrustSettingsResponse) -> None:
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO studio_trust_settings (id, mode, updated_at, raw_json)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    mode = excluded.mode,
                    updated_at = excluded.updated_at,
                    raw_json = excluded.raw_json
                """,
                (
                    _TRUST_SETTINGS_KEY,
                    settings.mode.value,
                    _datetime_to_text(settings.updated_at),
                    settings.model_dump_json(),
                ),
            )


def _artifact_from_coding(item: CodingRequestSummary) -> WorkbenchArtifactSummary:
    return WorkbenchArtifactSummary(
        id=item.id,
        kind="coding_request",
        title=item.title,
        status=item.status,
        repo=item.repo,
        repo_path=item.repo_path,
        summary=f"{len(item.files_touched)} file(s) touched",
        files_changed=len(item.files_touched),
        validation=item.validation_result,
        checkpoint=item.checkpoint_state,
        conversation_id=item.conversation_id,
        created_at=item.created_at,
        updated_at=item.updated_at,
        href=item.href,
    )


def _artifact_from_validation(item: ValidationSummary) -> WorkbenchArtifactSummary:
    return WorkbenchArtifactSummary(
        id=item.id,
        kind="validation_result",
        title=f"Validation for {item.repo}",
        status=item.status,
        repo=item.repo,
        repo_path=item.repo_path,
        summary=f"{item.passed}/{item.total_commands} passed",
        validation=f"{item.passed} passed, {item.failed} failed",
        created_at=item.created_at,
        href=item.href,
    )


def _artifact_from_checkpoint(item: CheckpointSummary) -> WorkbenchArtifactSummary:
    status = (
        WorkbenchStatus(value="restored", label="Restored", tone="warning")
        if item.restored_at is not None
        else WorkbenchStatus(value="available", label="Available", tone="success")
    )
    return WorkbenchArtifactSummary(
        id=item.id,
        kind="checkpoint",
        title="Checkpoint available" if item.restored_at is None else "Checkpoint restored",
        status=status,
        repo="Local workspace",
        repo_path="",
        summary=f"{len(item.files_covered)} file(s) covered",
        checkpoint=item.availability,
        created_at=item.created_at,
        updated_at=item.restored_at,
        href=item.href,
    )


def _artifact_from_release(item: ReleaseSummary) -> WorkbenchArtifactSummary:
    tone: WorkbenchTone = "success" if item.validation_status == "passed" else "warning"
    return WorkbenchArtifactSummary(
        id=item.id,
        kind="release_plan",
        title=f"Release evidence for {item.repo}",
        status=WorkbenchStatus(value=item.validation_status, label=_label(item.validation_status), tone=tone),
        repo=item.repo,
        repo_path=item.repo_path,
        summary=item.recommendation,
        validation=item.validation_status,
        created_at=item.created_at,
        href=item.href,
    )


def _default_trust_settings(mode: TrustMode) -> TrustSettingsResponse:
    return _trust_settings_from_values(mode, _default_rule_values(mode))


def _trust_settings_from_values(
    mode: TrustMode,
    values: dict[TrustRuleKey, bool],
) -> TrustSettingsResponse:
    normalized = _default_rule_values(mode)
    normalized.update(values)
    rules = [
        TrustRule(
            key=key,
            label=_rule_label(key),
            allowed=False if _hard_blocked(key) else normalized.get(key, False),
            implemented=_implemented_rule(key),
            risk=_rule_risk(key),
            hard_blocked=_hard_blocked(key),
        )
        for key in TrustRuleKey
    ]
    return TrustSettingsResponse(
        mode=mode,
        effective_policy_profile=_policy_profile_for_trust(mode),
        rules=rules,
        effective_behavior=_effective_behavior(rules),
        hard_blocks=[
            "Destructive/system-level actions remain blocked by the tool runtime.",
            "Dependency installation, Git push, and external messages are not exposed in this phase.",
            "Protected files and secret-like content are redacted or withheld.",
        ],
        updated_at=datetime.now(UTC),
    )


def _default_rule_values(mode: TrustMode) -> dict[TrustRuleKey, bool]:
    safe_defaults = {
        TrustRuleKey.READ_REPO_FILES: True,
        TrustRuleKey.SEARCH_REPO: True,
        TrustRuleKey.INSPECT_REPO_METADATA: True,
        TrustRuleKey.CREATE_CODING_PLANS: True,
        TrustRuleKey.CREATE_PATCH_PROPOSALS: True,
        TrustRuleKey.CREATE_CHECKPOINTS: True,
        TrustRuleKey.RUN_SAFE_VALIDATION: mode != TrustMode.STRICT,
        TrustRuleKey.APPLY_LOW_RISK_DOC_PATCHES: mode
        in {TrustMode.DEVELOPER, TrustMode.LOCAL_POWER_USER},
        TrustRuleKey.APPLY_LOW_RISK_CODE_PATCHES: mode == TrustMode.LOCAL_POWER_USER,
        TrustRuleKey.RESTORE_CHECKPOINTS: False,
        TrustRuleKey.INSTALL_DEPENDENCIES: False,
        TrustRuleKey.PUSH_GIT_CHANGES: False,
        TrustRuleKey.SEND_EXTERNAL_MESSAGES: False,
    }
    if mode == TrustMode.MANUAL:
        safe_defaults[TrustRuleKey.APPLY_LOW_RISK_DOC_PATCHES] = False
        safe_defaults[TrustRuleKey.RUN_SAFE_VALIDATION] = True
    if mode == TrustMode.STRICT:
        safe_defaults[TrustRuleKey.CREATE_PATCH_PROPOSALS] = True
    return safe_defaults


def _policy_profile_for_trust(mode: TrustMode) -> str:
    return {
        TrustMode.MANUAL: PolicyProfileType.BALANCED.value,
        TrustMode.DEVELOPER: PolicyProfileType.DEVELOPER.value,
        TrustMode.LOCAL_POWER_USER: PolicyProfileType.LOCAL_POWER_USER.value,
        TrustMode.STRICT: PolicyProfileType.STRICT.value,
    }[mode]


def _rule_label(key: TrustRuleKey) -> str:
    return {
        TrustRuleKey.READ_REPO_FILES: "Read normal repo files",
        TrustRuleKey.SEARCH_REPO: "Search repo",
        TrustRuleKey.INSPECT_REPO_METADATA: "Inspect repo metadata",
        TrustRuleKey.CREATE_CODING_PLANS: "Create coding plans",
        TrustRuleKey.CREATE_PATCH_PROPOSALS: "Create patch proposals",
        TrustRuleKey.CREATE_CHECKPOINTS: "Create checkpoints",
        TrustRuleKey.RUN_SAFE_VALIDATION: "Run safe validation",
        TrustRuleKey.APPLY_LOW_RISK_DOC_PATCHES: "Apply low-risk documentation patches",
        TrustRuleKey.APPLY_LOW_RISK_CODE_PATCHES: "Apply low-risk code patches with validation",
        TrustRuleKey.RESTORE_CHECKPOINTS: "Restore checkpoints",
        TrustRuleKey.INSTALL_DEPENDENCIES: "Install dependencies",
        TrustRuleKey.PUSH_GIT_CHANGES: "Push Git changes",
        TrustRuleKey.SEND_EXTERNAL_MESSAGES: "Send external messages",
    }[key]


def _implemented_rule(key: TrustRuleKey) -> bool:
    return key not in {
        TrustRuleKey.INSTALL_DEPENDENCIES,
        TrustRuleKey.PUSH_GIT_CHANGES,
        TrustRuleKey.SEND_EXTERNAL_MESSAGES,
    }


def _hard_blocked(key: TrustRuleKey) -> bool:
    return key in {
        TrustRuleKey.INSTALL_DEPENDENCIES,
        TrustRuleKey.PUSH_GIT_CHANGES,
        TrustRuleKey.SEND_EXTERNAL_MESSAGES,
    }


def _rule_risk(key: TrustRuleKey) -> str:
    if key in {
        TrustRuleKey.READ_REPO_FILES,
        TrustRuleKey.SEARCH_REPO,
        TrustRuleKey.INSPECT_REPO_METADATA,
        TrustRuleKey.CREATE_CODING_PLANS,
        TrustRuleKey.CREATE_PATCH_PROPOSALS,
        TrustRuleKey.CREATE_CHECKPOINTS,
    }:
        return "safe"
    if key == TrustRuleKey.RUN_SAFE_VALIDATION:
        return "safe_validation"
    if key in {
        TrustRuleKey.APPLY_LOW_RISK_DOC_PATCHES,
        TrustRuleKey.APPLY_LOW_RISK_CODE_PATCHES,
        TrustRuleKey.RESTORE_CHECKPOINTS,
    }:
        return "medium"
    return "external"


def _effective_behavior(rules: list[TrustRule]) -> list[str]:
    allowed = {rule.key for rule in rules if rule.allowed}
    behavior = ["Read-only repo work and planning proceed without approval spam."]
    if TrustRuleKey.RUN_SAFE_VALIDATION in allowed:
        behavior.append("Safe validation can run from Studio without a separate prompt.")
    if TrustRuleKey.APPLY_LOW_RISK_DOC_PATCHES in allowed:
        behavior.append("Low-risk documentation patches may apply as a reviewed batch.")
    if TrustRuleKey.APPLY_LOW_RISK_CODE_PATCHES in allowed:
        behavior.append("Low-risk code patches may apply when validation is available.")
    if TrustRuleKey.RESTORE_CHECKPOINTS not in allowed:
        behavior.append("Checkpoint restores require explicit confirmation.")
    return behavior


def _trust_profile_label(settings: TrustSettingsResponse) -> str:
    return f"{settings.mode.value} -> {settings.effective_policy_profile}"


def _plan_view(detail: CodingLoopDetail) -> CodingPlanView | None:
    if detail.plan is None:
        return None
    return CodingPlanView(
        summary=detail.plan.summary,
        steps=[
            f"{step.title}: {step.summary}"
            for step in sorted(detail.plan.steps, key=lambda item: item.order)
        ],
        expected_files=detail.plan.likely_files,
        validation_strategy=detail.plan.validation_commands,
        rollback_behavior=detail.plan.rollback_plan,
        current_state=_coding_status(detail.plan.status.value),
    )


def _patch_views(detail: CodingLoopDetail) -> list[CodingPatchView]:
    if detail.change is None:
        return []
    review = detail.change.metadata.get("review")
    review_summary = ""
    protected: list[str] = []
    if isinstance(review, dict):
        review_summary = str(review.get("summary", ""))
        protected = [str(item) for item in review.get("protected_files", []) if item]
    applied = detail.result is not None and detail.result.status in {
        CodingLoopStatus.COMPLETED,
        CodingLoopStatus.PATCH_APPLIED,
        CodingLoopStatus.VALIDATION_PASSED,
        CodingLoopStatus.VALIDATION_FAILED,
        CodingLoopStatus.ROLLED_BACK,
    }
    patches = [
        CodingPatchView(
            id=patch.tool_patch_id or patch.id,
            status=_coding_status(detail.change.status.value),
            summary=detail.change.summary,
            files=detail.change.patch_set.files_touched,
            proposed=True,
            applied=applied,
            diff=_truncate_diff(_redact(detail.change.patch_set.diff)),
            diff_stats=_diff_stats(detail.change.patch_set.diff),
            review_result=review_summary or "Review pending.",
            protected_files=protected,
        )
        for patch in detail.change.patch_set.patches
    ]
    if detail.change.manifest is not None:
        patches.append(
            CodingPatchView(
                id=detail.change.id,
                status=_coding_status(detail.change.status.value),
                summary=detail.change.summary,
                files=detail.change.patch_set.files_touched,
                proposed=True,
                applied=applied,
                diff=detail.change.manifest.model_dump_json(indent=2),
                diff_stats=DiffStats(
                    line_count=len(detail.change.manifest.model_dump_json().splitlines()),
                    large=False,
                ),
                review_result="Structured manifest passed schema validation; apply approval required.",
                protected_files=[],
            )
        )
    return patches


def _result_summary(detail: CodingLoopDetail) -> str:
    if detail.result is not None:
        return detail.result.summary
    if detail.iteration is not None:
        return detail.iteration.summary
    if detail.plan is not None:
        return detail.plan.summary
    return "Coding request was created."


def _practical_next_step(detail: CodingLoopDetail) -> str:
    status = detail.result.status if detail.result is not None else None
    if status == CodingLoopStatus.COMPLETED:
        return "Review the changed files or continue in the linked conversation."
    if status == CodingLoopStatus.VALIDATION_FAILED:
        return "Inspect failed validation and decide whether to fix forward or restore the checkpoint."
    if status == CodingLoopStatus.REQUIRES_APPROVAL:
        return "Review the diff, then approve the patch batch if it matches the request."
    if status == CodingLoopStatus.ROLLED_BACK:
        return "The checkpoint was restored. Narrow the patch or adjust validation before retrying."
    if detail.change is not None:
        return "Review the proposed diff before applying it."
    return "Create a patch proposal when the scope is clear."


def _validation_ids(detail: CodingLoopDetail) -> list[str]:
    ids: list[str] = []
    if detail.iteration is not None and detail.iteration.validation_result_id is not None:
        ids.append(detail.iteration.validation_result_id)
    if detail.result is not None:
        ids.extend(detail.result.validation_result_ids)
    return list(dict.fromkeys(ids))


def _checkpoint_ids(detail: CodingLoopDetail) -> list[str]:
    ids: list[str] = []
    if detail.iteration is not None:
        ids.extend(
            [
                item
                for item in [detail.iteration.checkpoint_id, detail.iteration.rollback_checkpoint_id]
                if item is not None
            ]
        )
    if detail.result is not None:
        ids.extend(detail.result.checkpoint_ids)
    return list(dict.fromkeys(ids))


def _tool_action_ids(detail: CodingLoopDetail) -> list[str]:
    ids: list[str] = []
    if detail.change is not None:
        ids.extend(detail.change.patch_set.tool_action_ids)
    if detail.iteration is not None:
        ids.extend(
            [
                item
                for item in [detail.iteration.apply_tool_action_id, detail.iteration.rollback_tool_action_id]
                if item is not None
            ]
        )
    if detail.result is not None:
        ids.extend(detail.result.tool_action_ids)
    return list(dict.fromkeys(ids))


def _decision_trace_ids(detail: CodingLoopDetail) -> list[str]:
    ids: list[str] = []
    for item in [detail.plan, detail.change, detail.iteration, detail.result]:
        if item is not None and hasattr(item, "decision_trace_ids"):
            ids.extend(cast(Any, item).decision_trace_ids)
    return list(dict.fromkeys(ids))


def _outcome_ids(detail: CodingLoopDetail) -> list[str]:
    ids: list[str] = []
    for item in [detail.change, detail.iteration, detail.result]:
        if item is not None and hasattr(item, "outcome_ids"):
            ids.extend(cast(Any, item).outcome_ids)
    return list(dict.fromkeys(ids))


def _learning_signal_ids(detail: CodingLoopDetail) -> list[str]:
    ids: list[str] = []
    for item in [detail.iteration, detail.result]:
        if item is not None and hasattr(item, "learning_signal_ids"):
            ids.extend(cast(Any, item).learning_signal_ids)
    return list(dict.fromkeys(ids))


def _files_for_coding(row: sqlite3.Row, detail: CodingLoopDetail) -> list[str]:
    files: list[str] = []
    if detail.change is not None:
        files.extend(detail.change.patch_set.files_touched)
    if detail.plan is not None:
        files.extend(detail.plan.likely_files)
    files.extend(_json_list(_row_str(row, "likely_files_json")))
    return list(dict.fromkeys(files))


def _validation_label(detail: CodingLoopDetail) -> str:
    if detail.result is None:
        return "not run"
    validation = detail.result.validation
    if validation.command_count:
        total = validation.command_count
        passed = validation.pass_count
        failed = validation.fail_count + validation.blocked_count + validation.requires_approval_count
        return f"{passed}/{total} passed" if failed == 0 else f"{failed} issue(s)"
    return validation.status.replace("_", " ")


def _checkpoint_label(checkpoint_ids: list[str], repository: ToolRuntimeRepository) -> str:
    if not checkpoint_ids:
        return "none"
    restored = 0
    available = 0
    for checkpoint_id in checkpoint_ids:
        checkpoint = repository.get_checkpoint(checkpoint_id)
        if checkpoint is None:
            continue
        if checkpoint.restored_at is None:
            available += 1
        else:
            restored += 1
    if available:
        return "available"
    if restored:
        return "restored"
    return "missing"


def _plain_tool_action(action: ToolAction) -> str:
    if action.action_type.value == "read_file":
        return f"Read {_protected_path_label(action.target_path)}"
    if action.action_type.value == "search_files":
        return action.summary or "Searched repo"
    if action.action_type.value == "list_directory":
        return f"Listed {_protected_path_label(action.target_path or '.')}"
    if action.action_type.value == "propose_patch":
        return f"Created patch proposal for {_protected_path_label(action.target_path)}"
    if action.action_type.value == "apply_patch":
        return f"Applied patch to {len(action.files_touched) or 1} file(s)"
    if action.action_type.value == "run_command":
        return f"Ran {_redact(action.command)}"
    if action.action_type.value == "create_checkpoint":
        return "Created checkpoint"
    if action.action_type.value == "restore_checkpoint":
        return "Restored checkpoint"
    return action.summary or action.action_type.value.replace("_", " ")


def _policy_decision_from_action(action: ToolAction) -> str:
    if action.approval_status.value == "pending":
        return "approval required"
    if action.approval_status.value == "approved":
        return "approved"
    if action.approval_status.value == "blocked":
        return "blocked"
    return "allowed"


def _reflection_lines(reflections: list[ReflectionRecord]) -> list[str]:
    lines: list[str] = []
    for reflection in reflections:
        for value in [
            reflection.what_worked,
            reflection.what_failed,
            reflection.likely_cause,
            reflection.recommended_change,
        ]:
            if value:
                lines.append(_redact(value))
    return lines


def _learning_lines(signals: list[LearningSignal]) -> list[str]:
    lines: list[str] = []
    for signal in signals:
        if signal.strength < 0.45:
            continue
        direction = signal.direction.value.replace("_", " ")
        target = signal.target.replace("_", " ")
        lines.append(_redact(f"Hephaestus will {direction} {target}: {signal.rationale}"))
    return lines


def _rollback_text(outcome: OutcomeRecord) -> str:
    if any("rollback" in tag or "restored" in tag for tag in outcome.tags):
        return "Rollback evidence is linked."
    if outcome.status.value == "failure":
        return "Rollback may be available if a checkpoint is linked."
    return "No rollback needed."


def _coding_status(value: str) -> WorkbenchStatus:
    tone: WorkbenchTone = "neutral"
    if value in {"completed", "validation_passed", "patch_applied"}:
        tone = "success"
    elif value in {"validation_failed", "blocked"}:
        tone = "error"
    elif value in {"requires_approval", "needs_user_input", "scope_too_large"} or value in {"rolled_back"}:
        tone = "warning"
    return WorkbenchStatus(value=value, label=_label(value), tone=tone)


def _validation_status(value: str) -> WorkbenchStatus:
    tone: WorkbenchTone = "neutral"
    if value == "passed":
        tone = "success"
    elif value in {"failed", "timed_out", "blocked"}:
        tone = "error"
    elif value in {"requires_approval", "skipped"}:
        tone = "warning"
    return WorkbenchStatus(value=value, label=_label(value), tone=tone)


def _tool_status(value: str) -> WorkbenchStatus:
    tone: WorkbenchTone = "neutral"
    if value in {"succeeded", "restored"}:
        tone = "success"
    elif value in {"failed", "timed_out", "blocked"}:
        tone = "error"
    elif value in {"approval_required", "dry_run"}:
        tone = "warning"
    return WorkbenchStatus(value=value, label=_label(value), tone=tone)


def _outcome_status(value: str) -> WorkbenchStatus:
    tone: WorkbenchTone = "neutral"
    if value == "success":
        tone = "success"
    elif value == "failure":
        tone = "error"
    elif value == "partial":
        tone = "warning"
    return WorkbenchStatus(value=value, label=_label(value), tone=tone)


def _diff_stats(diff: str) -> DiffStats:
    additions = 0
    deletions = 0
    lines = diff.splitlines()
    for line in lines:
        if line.startswith("+") and not line.startswith("+++"):
            additions += 1
        elif line.startswith("-") and not line.startswith("---"):
            deletions += 1
    return DiffStats(
        additions=additions,
        deletions=deletions,
        line_count=len(lines),
        large=len(lines) > _DIFF_LARGE_THRESHOLD,
    )


def _truncate_diff(diff: str) -> str:
    lines = diff.splitlines()
    if len(lines) <= _DIFF_LARGE_THRESHOLD:
        return diff
    head = "\n".join(lines[:_DIFF_LARGE_THRESHOLD])
    return f"{head}\n... diff truncated after {_DIFF_LARGE_THRESHOLD} lines ..."


def _artifact_status(value: str) -> WorkbenchStatus:
    return WorkbenchStatus(value=value, label=_label(value), tone="neutral")


def _title_from_request(value: str) -> str:
    title = " ".join(value.split())
    if len(title) <= 74:
        return title
    return title[:73].rstrip() + "..."


def _repo_label(path: str) -> str:
    return Path(path).name or path or "Workspace"


def _label(value: str) -> str:
    return value.replace("_", " ").strip().capitalize()


def _protected_path_label(path: str) -> str:
    return "[protected path]" if path and is_protected_path(path) else path


_SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?([A-Za-z0-9_\-./]{6,})"),
    re.compile(r"(?i)(bearer)\s+([A-Za-z0-9_\-./]{12,})"),
    re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----.*?-----END [A-Z ]+PRIVATE KEY-----", re.DOTALL),
]


def _redact(value: str) -> str:
    redacted = value
    for pattern in _SECRET_PATTERNS:
        redacted = pattern.sub(lambda match: f"{match.group(1)}=[redacted]", redacted)
    return redacted


def _truncate(value: str, *, limit: int = _OUTPUT_LIMIT) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 44].rstrip() + "\n... output truncated by Studio ..."


def _datetime_to_text(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _datetime_from_text(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _json_list(value: str) -> list[str]:
    loaded = json.loads(value or "[]")
    if not isinstance(loaded, list):
        return []
    return [str(item) for item in loaded]


def _json_dict(value: str) -> dict[str, Any]:
    loaded = json.loads(value or "{}")
    if not isinstance(loaded, dict):
        return {}
    return cast(dict[str, Any], loaded)


def _row_str(row: sqlite3.Row, key: str) -> str:
    return cast(str, row[key])


def _row_optional_str(row: sqlite3.Row, key: str) -> str | None:
    return cast(str | None, row[key])
