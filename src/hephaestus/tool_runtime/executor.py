"""High-level safe tool runtime orchestration."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from hephaestus.policy import PolicyRepository
from hephaestus.repo import RepoProfileRepository
from hephaestus.tool_runtime.analysis import record_tool_decision_and_outcome
from hephaestus.tool_runtime.approval import build_approval_request, decide_approval
from hephaestus.tool_runtime.checkpoint import restore_checkpoint as restore_checkpoint_files
from hephaestus.tool_runtime.classifier import classify_tool_action
from hephaestus.tool_runtime.filesystem import (
    is_protected_path,
    list_directory,
    read_file,
    resolve_workspace,
    search_files,
)
from hephaestus.tool_runtime.patch import apply_patch_proposal, propose_patch
from hephaestus.tool_runtime.repository import ToolRuntimeRepository
from hephaestus.tool_runtime.schemas import (
    CheckpointRecord,
    FilesystemListResult,
    FilesystemReadRequest,
    FilesystemReadResult,
    FilesystemSearchRequest,
    FilesystemSearchResult,
    PatchApplyResult,
    PatchProposal,
    ShellCommandRequest,
    ToolAction,
    ToolActionType,
    ToolExecutionPlan,
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolObservation,
    ToolRiskDecision,
)
from hephaestus.tool_runtime.shell import run_shell_command


class ToolRuntime:
    """Safe local tool execution runtime."""

    def __init__(
        self,
        database_path: Path | str | None = None,
        *,
        workspace_path: Path | str = ".",
    ) -> None:
        self.workspace = resolve_workspace(workspace_path)
        self.repository = ToolRuntimeRepository(database_path)
        self.database_path = self.repository.database_path
        self.policy_repository = PolicyRepository(self.database_path)
        self.repo_repository = RepoProfileRepository(self.database_path)

    def list_directory(self, path: str = ".") -> tuple[ToolAction, ToolExecutionResult, FilesystemListResult]:
        """Persist and execute a safe directory listing."""

        policy_profile = self.policy_repository.get_active_profile()
        risk_decision = classify_tool_action(
            ToolActionType.LIST_DIRECTORY,
            policy_profile=policy_profile,
            target_path=path,
        )
        action = self._action(
            ToolActionType.LIST_DIRECTORY,
            risk_decision=risk_decision,
            target_path=path,
            summary=f"List directory {path}",
        )
        listing = list_directory(self.workspace, path)
        stdout = "\n".join(
            f"{entry.path}{'/' if entry.is_dir else ''}" for entry in listing.entries
        )
        result = ToolExecutionResult(
            action_id=action.id,
            status=ToolExecutionStatus.SUCCEEDED,
            stdout=stdout,
            stdout_summary=_summarize(stdout) or "Directory listed.",
        )
        action = self._complete_action(action, result)
        self.repository.create_action(action)
        self.repository.save_execution_result(result)
        self._observe(action, result, "filesystem", f"Listed {len(listing.entries)} entries.")
        return action, result, listing

    def read_file(self, path: str) -> tuple[ToolAction, ToolExecutionResult, FilesystemReadResult]:
        """Persist and execute a safe file read."""

        protected = is_protected_path(path)
        policy_profile = self.policy_repository.get_active_profile()
        risk_decision = classify_tool_action(
            ToolActionType.READ_FILE,
            policy_profile=policy_profile,
            target_path=path,
            protected_path=protected,
        )
        action = self._action(
            ToolActionType.READ_FILE,
            risk_decision=risk_decision,
            target_path=path,
            summary=f"Read file {path}",
        )
        read_result = read_file(
            FilesystemReadRequest(
                path=path,
                workspace_path=str(self.workspace),
                include_protected_content=False,
            )
        )
        stdout = read_result.content or read_result.message
        status = (
            ToolExecutionStatus.BLOCKED
            if read_result.protected and read_result.content is None
            else ToolExecutionStatus.SUCCEEDED
        )
        result = ToolExecutionResult(
            action_id=action.id,
            status=status,
            stdout=stdout,
            stdout_summary=_summarize(stdout) or "File read.",
            output_truncated=read_result.truncated,
        )
        action = self._complete_action(action, result)
        if status == ToolExecutionStatus.BLOCKED:
            action, result = record_tool_decision_and_outcome(
                self.database_path,
                action,
                risk_decision,
                result,
            )
        self.repository.create_action(action)
        self.repository.save_execution_result(result)
        self._observe(action, result, "filesystem", result.stdout_summary)
        return action, result, read_result

    def search_files(
        self,
        query: str,
        *,
        path: str = ".",
    ) -> tuple[ToolAction, ToolExecutionResult, FilesystemSearchResult]:
        """Persist and execute a simple text search."""

        policy_profile = self.policy_repository.get_active_profile()
        risk_decision = classify_tool_action(
            ToolActionType.SEARCH_FILES,
            policy_profile=policy_profile,
            target_path=path,
        )
        action = self._action(
            ToolActionType.SEARCH_FILES,
            risk_decision=risk_decision,
            target_path=path,
            summary=f"Search for {query!r} in {path}",
        )
        search_result = search_files(
            FilesystemSearchRequest(query=query, path=path, workspace_path=str(self.workspace))
        )
        stdout = "\n".join(
            f"{match.path}:{match.line_number}: {match.line}" for match in search_result.matches
        )
        result = ToolExecutionResult(
            action_id=action.id,
            status=ToolExecutionStatus.SUCCEEDED,
            stdout=stdout,
            stdout_summary=_summarize(stdout)
            or f"{len(search_result.matches)} matches; {len(search_result.skipped_protected)} protected skipped.",
            output_truncated=search_result.truncated,
        )
        action = self._complete_action(action, result)
        self.repository.create_action(action)
        self.repository.save_execution_result(result)
        self._observe(action, result, "filesystem", result.stdout_summary)
        return action, result, search_result

    def run_command(
        self,
        request: ShellCommandRequest,
    ) -> tuple[ToolExecutionPlan, ToolAction, ToolExecutionResult]:
        """Classify, approval-gate, and optionally run a shell command."""

        policy_profile = self.policy_repository.get_active_profile()
        risk_decision = classify_tool_action(
            ToolActionType.RUN_COMMAND,
            policy_profile=policy_profile,
            command=request.command,
        )
        approval_required = request.require_approval or risk_decision.approval_required
        action = self._action(
            ToolActionType.RUN_COMMAND,
            risk_decision=risk_decision,
            command=request.command,
            target_path=request.cwd,
            summary=f"Run command: {request.command}",
        )
        approval_request = build_approval_request(action, risk_decision)
        approval = decide_approval(
            approval_request,
            blocked=risk_decision.blocked,
            approval_required=approval_required,
            yes=request.yes,
            dry_run=request.dry_run,
        )
        action = action.model_copy(update={"approval_status": approval.status})
        plan = ToolExecutionPlan(
            action=action,
            risk_decision=risk_decision,
            dry_run=request.dry_run,
            approval_required=approval_required,
            blocked=risk_decision.blocked,
            exact_cli_command=f'heph tools run "{request.command}"',
            explanation=", ".join(risk_decision.reasons) or "Command classified.",
        )
        self.repository.create_action(action)
        self.repository.save_approval(approval_request, approval)
        if request.dry_run:
            result = ToolExecutionResult(
                action_id=action.id,
                status=ToolExecutionStatus.DRY_RUN,
                stdout="Dry-run only; command not executed.",
                stdout_summary="Dry-run only; command not executed.",
            )
        elif risk_decision.blocked:
            result = ToolExecutionResult(
                action_id=action.id,
                status=ToolExecutionStatus.BLOCKED,
                stdout_summary="Command blocked by tool policy.",
            )
        elif not approval.approved:
            result = ToolExecutionResult(
                action_id=action.id,
                status=ToolExecutionStatus.APPROVAL_REQUIRED,
                stdout_summary=approval.reason,
            )
        else:
            shell_result = run_shell_command(request.model_copy(update={"cwd": str(self.workspace)}))
            result = ToolExecutionResult(
                action_id=action.id,
                status=shell_result.status,
                stdout=shell_result.stdout,
                stderr=shell_result.stderr,
                stdout_summary=_summarize(shell_result.stdout),
                stderr_summary=_summarize(shell_result.stderr),
                exit_code=shell_result.exit_code,
                duration_seconds=shell_result.duration_seconds,
                timed_out=shell_result.timed_out,
                output_truncated=shell_result.output_truncated,
            )
        action = self._complete_action(action, result)
        action, result = record_tool_decision_and_outcome(
            self.database_path,
            action,
            risk_decision,
            result,
        )
        self.repository.create_action(action)
        self.repository.save_execution_result(result)
        self._observe(action, result, "shell", _result_observation(action, result))
        return plan, action, result

    def propose_patch(
        self,
        path: str,
        *,
        find: str,
        replace: str,
    ) -> tuple[ToolAction, ToolExecutionResult, PatchProposal]:
        """Create and persist a patch proposal without changing files."""

        policy_profile = self.policy_repository.get_active_profile()
        risk_decision = classify_tool_action(
            ToolActionType.PROPOSE_PATCH,
            policy_profile=policy_profile,
            target_path=path,
        )
        action = self._action(
            ToolActionType.PROPOSE_PATCH,
            risk_decision=risk_decision,
            target_path=path,
            summary=f"Propose patch for {path}",
        )
        proposal = propose_patch(
            self.workspace,
            path,
            find=find,
            replace=replace,
            action_id=action.id,
        )
        action = action.model_copy(
            update={
                "patch_id": proposal.id,
                "files_touched": proposal.files_touched,
                "execution_status": ToolExecutionStatus.SUCCEEDED,
                "updated_at": datetime.now(UTC),
            }
        )
        result = ToolExecutionResult(
            action_id=action.id,
            status=ToolExecutionStatus.SUCCEEDED,
            stdout=proposal.diff,
            stdout_summary=f"Patch proposal {proposal.id} created for {path}.",
            files_touched=proposal.files_touched,
        )
        self.repository.save_patch_proposal(action, proposal)
        self.repository.save_execution_result(result)
        self._observe(action, result, "patch", result.stdout_summary)
        return action, result, proposal

    def apply_patch(
        self,
        patch_id: str,
        *,
        yes: bool = False,
        dry_run: bool = False,
        require_approval: bool = False,
    ) -> tuple[ToolExecutionPlan, ToolAction, ToolExecutionResult, PatchApplyResult | None]:
        """Apply a stored patch proposal after approval."""

        proposal = self.repository.get_patch_proposal(patch_id)
        if proposal is None:
            raise ValueError(f"Patch proposal not found: {patch_id}")
        policy_profile = self.policy_repository.get_active_profile()
        risk_decision = classify_tool_action(
            ToolActionType.APPLY_PATCH,
            policy_profile=policy_profile,
            target_path=proposal.path,
        )
        approval_required = True
        action = self._action(
            ToolActionType.APPLY_PATCH,
            risk_decision=risk_decision,
            target_path=proposal.path,
            summary=f"Apply patch {proposal.id}",
        ).model_copy(update={"patch_id": proposal.id})
        approval_request = build_approval_request(action, risk_decision)
        approval = decide_approval(
            approval_request,
            blocked=risk_decision.blocked,
            approval_required=approval_required,
            yes=yes,
            dry_run=dry_run,
        )
        action = action.model_copy(update={"approval_status": approval.status})
        plan = ToolExecutionPlan(
            action=action,
            risk_decision=risk_decision,
            dry_run=dry_run,
            approval_required=approval_required,
            blocked=risk_decision.blocked,
            exact_cli_command=f"heph tools patch apply {proposal.id} --yes",
            explanation=", ".join(risk_decision.reasons) or "Patch application classified.",
        )
        self.repository.create_action(action)
        self.repository.save_approval(approval_request, approval)
        apply_result: PatchApplyResult | None = None
        if dry_run:
            result = ToolExecutionResult(
                action_id=action.id,
                status=ToolExecutionStatus.DRY_RUN,
                stdout=proposal.diff,
                stdout_summary="Dry-run only; patch not applied.",
                files_touched=proposal.files_touched,
            )
        elif risk_decision.blocked:
            result = ToolExecutionResult(
                action_id=action.id,
                status=ToolExecutionStatus.BLOCKED,
                stdout_summary="Patch blocked by tool policy.",
                files_touched=proposal.files_touched,
            )
        elif not approval.approved:
            result = ToolExecutionResult(
                action_id=action.id,
                status=ToolExecutionStatus.APPROVAL_REQUIRED,
                stdout_summary=approval.reason,
                files_touched=proposal.files_touched,
            )
        else:
            apply_result, checkpoint = apply_patch_proposal(proposal, action_id=action.id)
            self.repository.save_checkpoint(checkpoint)
            result = ToolExecutionResult(
                action_id=action.id,
                status=ToolExecutionStatus.SUCCEEDED,
                stdout_summary=apply_result.message,
                files_touched=apply_result.files_touched,
                checkpoint_id=checkpoint.id,
            )
        action = self._complete_action(action, result)
        action, result = record_tool_decision_and_outcome(
            self.database_path,
            action,
            risk_decision,
            result,
        )
        self.repository.create_action(action)
        self.repository.save_execution_result(result)
        self._observe(action, result, "patch", _result_observation(action, result))
        return plan, action, result, apply_result

    def restore_checkpoint(
        self,
        checkpoint_id: str,
        *,
        yes: bool = False,
        dry_run: bool = False,
        require_approval: bool = False,
    ) -> tuple[ToolExecutionPlan, ToolAction, ToolExecutionResult, CheckpointRecord | None]:
        """Restore a checkpoint after approval."""

        checkpoint = self.repository.get_checkpoint(checkpoint_id)
        if checkpoint is None:
            raise ValueError(f"Checkpoint not found: {checkpoint_id}")
        policy_profile = self.policy_repository.get_active_profile()
        risk_decision = classify_tool_action(
            ToolActionType.RESTORE_CHECKPOINT,
            policy_profile=policy_profile,
            target_path=checkpoint_id,
        )
        approval_required = True
        action = self._action(
            ToolActionType.RESTORE_CHECKPOINT,
            risk_decision=risk_decision,
            target_path=checkpoint_id,
            summary=f"Restore checkpoint {checkpoint_id}",
        )
        approval_request = build_approval_request(action, risk_decision)
        approval = decide_approval(
            approval_request,
            blocked=risk_decision.blocked,
            approval_required=approval_required,
            yes=yes,
            dry_run=dry_run,
        )
        action = action.model_copy(update={"approval_status": approval.status})
        plan = ToolExecutionPlan(
            action=action,
            risk_decision=risk_decision,
            dry_run=dry_run,
            approval_required=approval_required,
            blocked=risk_decision.blocked,
            exact_cli_command=f"heph tools checkpoint restore {checkpoint_id} --yes",
            explanation=", ".join(risk_decision.reasons) or "Checkpoint restore classified.",
        )
        self.repository.create_action(action)
        self.repository.save_approval(approval_request, approval)
        restored: CheckpointRecord | None = None
        if dry_run:
            result = ToolExecutionResult(
                action_id=action.id,
                status=ToolExecutionStatus.DRY_RUN,
                stdout_summary="Dry-run only; checkpoint not restored.",
                files_touched=checkpoint.files_touched,
            )
        elif not approval.approved:
            result = ToolExecutionResult(
                action_id=action.id,
                status=ToolExecutionStatus.APPROVAL_REQUIRED,
                stdout_summary=approval.reason,
                files_touched=checkpoint.files_touched,
            )
        else:
            restored = restore_checkpoint_files(checkpoint)
            self.repository.restore_checkpoint_metadata(restored)
            result = ToolExecutionResult(
                action_id=action.id,
                status=ToolExecutionStatus.RESTORED,
                stdout_summary=f"Checkpoint restored: {checkpoint_id}",
                files_touched=checkpoint.files_touched,
                checkpoint_id=checkpoint.id,
            )
        action = self._complete_action(action, result)
        action, result = record_tool_decision_and_outcome(
            self.database_path,
            action,
            risk_decision,
            result,
        )
        self.repository.create_action(action)
        self.repository.save_execution_result(result)
        self._observe(action, result, "checkpoint", _result_observation(action, result))
        return plan, action, result, restored

    def _action(
        self,
        action_type: ToolActionType,
        *,
        risk_decision: ToolRiskDecision,
        command: str = "",
        target_path: str = "",
        summary: str = "",
    ) -> ToolAction:
        profile_id = risk_decision.policy.profile_id
        latest_profile = self.repo_repository.latest_profile_for_path(self.workspace)
        return ToolAction(
            action_type=action_type,
            workspace_path=str(self.workspace),
            command=command,
            target_path=target_path,
            summary=summary,
            risk_level=risk_decision.risk_level,
            active_policy_profile=profile_id,
            repo_profile_id=latest_profile.id if latest_profile is not None else None,
        )

    def _complete_action(self, action: ToolAction, result: ToolExecutionResult) -> ToolAction:
        return action.model_copy(
            update={
                "execution_status": result.status,
                "stdout_summary": result.stdout_summary,
                "stderr_summary": result.stderr_summary,
                "exit_code": result.exit_code,
                "files_touched": result.files_touched,
                "checkpoint_id": result.checkpoint_id,
                "decision_trace_id": result.decision_trace_id,
                "outcome_id": result.outcome_id,
                "updated_at": datetime.now(UTC),
            }
        )

    def _observe(self, action: ToolAction, result: ToolExecutionResult, kind: str, summary: str) -> None:
        signal = "success" if result.status in {ToolExecutionStatus.SUCCEEDED, ToolExecutionStatus.RESTORED} else result.status.value
        self.repository.save_observation(
            ToolObservation(
                action_id=action.id,
                result_id=result.id,
                observation_type=kind,
                summary=summary,
                signal=signal,
                severity=0.0 if signal == "success" else 0.5,
            )
        )


def _summarize(value: str, *, limit: int = 500) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(0, limit - 3)].rstrip() + "..."


def _result_observation(action: ToolAction, result: ToolExecutionResult) -> str:
    subject = action.command or action.target_path or action.action_type.value
    return f"{subject}: {result.status.value}"
