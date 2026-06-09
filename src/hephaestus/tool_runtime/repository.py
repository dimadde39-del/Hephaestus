"""SQLite persistence for safe tool runtime actions."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from hephaestus.storage.sqlite import connect_database, init_database
from hephaestus.tool_runtime.schemas import (
    CheckpointRecord,
    PatchProposal,
    ToolAction,
    ToolApprovalDecision,
    ToolApprovalRequest,
    ToolExecutionResult,
    ToolObservation,
)


class ToolRuntimeRepository:
    """Persist tool actions, approvals, results, observations, and checkpoints."""

    def __init__(self, database_path: Path | str | None = None) -> None:
        self.database_path = init_database(database_path)

    def create_action(self, action: ToolAction) -> ToolAction:
        """Insert or replace a tool action."""

        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO tool_actions (
                    id, action_type, workspace_path, command_text, target_path, summary,
                    risk_level, active_policy_profile, approval_status, execution_status,
                    stdout_summary, stderr_summary, exit_code, files_touched_json,
                    checkpoint_id, decision_trace_id, outcome_id, conversation_id,
                    run_id, repo_profile_id, patch_id, created_at, updated_at, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    action_type = excluded.action_type,
                    workspace_path = excluded.workspace_path,
                    command_text = excluded.command_text,
                    target_path = excluded.target_path,
                    summary = excluded.summary,
                    risk_level = excluded.risk_level,
                    active_policy_profile = excluded.active_policy_profile,
                    approval_status = excluded.approval_status,
                    execution_status = excluded.execution_status,
                    stdout_summary = excluded.stdout_summary,
                    stderr_summary = excluded.stderr_summary,
                    exit_code = excluded.exit_code,
                    files_touched_json = excluded.files_touched_json,
                    checkpoint_id = excluded.checkpoint_id,
                    decision_trace_id = excluded.decision_trace_id,
                    outcome_id = excluded.outcome_id,
                    conversation_id = excluded.conversation_id,
                    run_id = excluded.run_id,
                    repo_profile_id = excluded.repo_profile_id,
                    patch_id = excluded.patch_id,
                    updated_at = excluded.updated_at,
                    raw_json = excluded.raw_json
                """,
                _action_values(action, action.model_dump(mode="json")),
            )
        return action

    def list_actions(self, *, limit: int = 20) -> list[ToolAction]:
        """List recent tool actions."""

        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT raw_json FROM tool_actions
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [_action_from_raw(_row_str(row, "raw_json")) for row in rows]

    def get_action(self, action_id: str) -> ToolAction | None:
        """Read one action by id."""

        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT raw_json FROM tool_actions WHERE id = ?",
                (action_id,),
            ).fetchone()
        if row is None:
            return None
        return _action_from_raw(_row_str(row, "raw_json"))

    def save_approval(
        self,
        request: ToolApprovalRequest,
        decision: ToolApprovalDecision,
    ) -> ToolApprovalDecision:
        """Persist an approval request and decision."""

        raw = {
            "request": request.model_dump(mode="json"),
            "decision": decision.model_dump(mode="json"),
        }
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO tool_approvals (
                    id, action_id, risk_level, policy_profile, status, approved,
                    reason, created_at, decided_at, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision.id,
                    decision.action_id,
                    request.risk_level.value,
                    request.policy_profile,
                    decision.status.value,
                    int(decision.approved),
                    decision.reason,
                    _datetime_to_text(request.created_at),
                    _datetime_to_text(decision.decided_at),
                    _json_dumps(raw),
                ),
            )
        return decision

    def list_approvals_for_action(self, action_id: str) -> list[ToolApprovalDecision]:
        """List approval decisions for one action."""

        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT raw_json FROM tool_approvals
                WHERE action_id = ?
                ORDER BY created_at, id
                """,
                (action_id,),
            ).fetchall()
        return [_approval_decision_from_raw(_row_str(row, "raw_json")) for row in rows]

    def save_execution_result(self, result: ToolExecutionResult) -> ToolExecutionResult:
        """Persist an execution result."""

        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO tool_execution_results (
                    id, action_id, status, stdout_summary, stderr_summary, exit_code,
                    files_touched_json, checkpoint_id, decision_trace_id, outcome_id,
                    duration_seconds, timed_out, output_truncated, created_at, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    result.id,
                    result.action_id,
                    result.status.value,
                    result.stdout_summary,
                    result.stderr_summary,
                    result.exit_code,
                    _json_dumps(result.files_touched),
                    result.checkpoint_id,
                    result.decision_trace_id,
                    result.outcome_id,
                    result.duration_seconds,
                    int(result.timed_out),
                    int(result.output_truncated),
                    _datetime_to_text(result.created_at),
                    result.model_dump_json(),
                ),
            )
        return result

    def list_results_for_action(self, action_id: str) -> list[ToolExecutionResult]:
        """List execution results for one action."""

        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT raw_json FROM tool_execution_results
                WHERE action_id = ?
                ORDER BY created_at, id
                """,
                (action_id,),
            ).fetchall()
        return [ToolExecutionResult.model_validate_json(_row_str(row, "raw_json")) for row in rows]

    def save_observation(self, observation: ToolObservation) -> ToolObservation:
        """Persist one tool observation."""

        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO tool_observations (
                    id, action_id, result_id, observation_type, summary, signal,
                    severity, created_at, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    observation.id,
                    observation.action_id,
                    observation.result_id,
                    observation.observation_type,
                    observation.summary,
                    observation.signal,
                    observation.severity,
                    _datetime_to_text(observation.created_at),
                    observation.model_dump_json(),
                ),
            )
        return observation

    def list_observations_for_action(self, action_id: str) -> list[ToolObservation]:
        """List observations for one action."""

        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT raw_json FROM tool_observations
                WHERE action_id = ?
                ORDER BY created_at, id
                """,
                (action_id,),
            ).fetchall()
        return [ToolObservation.model_validate_json(_row_str(row, "raw_json")) for row in rows]

    def save_checkpoint(self, checkpoint: CheckpointRecord) -> CheckpointRecord:
        """Persist checkpoint metadata and file snapshots."""

        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO tool_checkpoints (
                    id, action_id, workspace_path, files_touched_json, created_at,
                    restored_at, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    checkpoint.id,
                    checkpoint.action_id,
                    checkpoint.workspace_path,
                    _json_dumps(checkpoint.files_touched),
                    _datetime_to_text(checkpoint.created_at),
                    _optional_datetime_to_text(checkpoint.restored_at),
                    checkpoint.model_dump_json(),
                ),
            )
        return checkpoint

    def get_checkpoint(self, checkpoint_id: str) -> CheckpointRecord | None:
        """Read one checkpoint by id."""

        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT raw_json FROM tool_checkpoints WHERE id = ?",
                (checkpoint_id,),
            ).fetchone()
        if row is None:
            return None
        return CheckpointRecord.model_validate_json(_row_str(row, "raw_json"))

    def list_checkpoints(self, *, limit: int = 20) -> list[CheckpointRecord]:
        """List recent checkpoints."""

        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT raw_json FROM tool_checkpoints
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [CheckpointRecord.model_validate_json(_row_str(row, "raw_json")) for row in rows]

    def restore_checkpoint_metadata(self, checkpoint: CheckpointRecord) -> CheckpointRecord:
        """Persist restored checkpoint metadata."""

        return self.save_checkpoint(checkpoint)

    def save_patch_proposal(self, action: ToolAction, proposal: PatchProposal) -> PatchProposal:
        """Persist a patch proposal inside its propose_patch action payload."""

        raw = {
            "action": action.model_dump(mode="json"),
            "patch_proposal": proposal.model_dump(mode="json"),
        }
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO tool_actions (
                    id, action_type, workspace_path, command_text, target_path, summary,
                    risk_level, active_policy_profile, approval_status, execution_status,
                    stdout_summary, stderr_summary, exit_code, files_touched_json,
                    checkpoint_id, decision_trace_id, outcome_id, conversation_id,
                    run_id, repo_profile_id, patch_id, created_at, updated_at, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    action_type = excluded.action_type,
                    workspace_path = excluded.workspace_path,
                    command_text = excluded.command_text,
                    target_path = excluded.target_path,
                    summary = excluded.summary,
                    risk_level = excluded.risk_level,
                    active_policy_profile = excluded.active_policy_profile,
                    approval_status = excluded.approval_status,
                    execution_status = excluded.execution_status,
                    stdout_summary = excluded.stdout_summary,
                    stderr_summary = excluded.stderr_summary,
                    exit_code = excluded.exit_code,
                    files_touched_json = excluded.files_touched_json,
                    checkpoint_id = excluded.checkpoint_id,
                    decision_trace_id = excluded.decision_trace_id,
                    outcome_id = excluded.outcome_id,
                    conversation_id = excluded.conversation_id,
                    run_id = excluded.run_id,
                    repo_profile_id = excluded.repo_profile_id,
                    patch_id = excluded.patch_id,
                    updated_at = excluded.updated_at,
                    raw_json = excluded.raw_json
                """,
                _action_values(action, raw),
            )
        return proposal

    def get_patch_proposal(self, patch_id: str) -> PatchProposal | None:
        """Read a stored patch proposal by patch id or action id."""

        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT raw_json FROM tool_actions
                WHERE action_type = 'propose_patch'
                  AND (patch_id = ? OR id = ?)
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (patch_id, patch_id),
            ).fetchone()
        if row is None:
            return None
        raw = _json_loads_dict(_row_str(row, "raw_json"))
        proposal = raw.get("patch_proposal")
        if not isinstance(proposal, dict):
            return None
        return PatchProposal.model_validate(proposal)


def _action_values(action: ToolAction, raw: dict[str, Any]) -> tuple[Any, ...]:
    return (
        action.id,
        action.action_type.value,
        action.workspace_path,
        action.command,
        action.target_path,
        action.summary,
        action.risk_level.value,
        action.active_policy_profile,
        action.approval_status.value,
        action.execution_status.value,
        action.stdout_summary,
        action.stderr_summary,
        action.exit_code,
        _json_dumps(action.files_touched),
        action.checkpoint_id,
        action.decision_trace_id,
        action.outcome_id,
        action.conversation_id,
        action.run_id,
        action.repo_profile_id,
        action.patch_id,
        _datetime_to_text(action.created_at),
        _datetime_to_text(action.updated_at),
        _json_dumps(raw),
    )


def _action_from_raw(raw_json: str) -> ToolAction:
    raw = _json_loads_dict(raw_json)
    action = raw.get("action", raw)
    if not isinstance(action, dict):
        raise ValueError("Invalid tool action payload")
    return ToolAction.model_validate(action)


def _approval_decision_from_raw(raw_json: str) -> ToolApprovalDecision:
    raw = _json_loads_dict(raw_json)
    decision = raw.get("decision", raw)
    if not isinstance(decision, dict):
        raise ValueError("Invalid tool approval payload")
    return ToolApprovalDecision.model_validate(decision)


def _datetime_to_text(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _optional_datetime_to_text(value: datetime | None) -> str | None:
    return _datetime_to_text(value) if value is not None else None


def _json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _json_loads_dict(value: str) -> dict[str, Any]:
    loaded = json.loads(value)
    if not isinstance(loaded, dict):
        return {}
    return cast(dict[str, Any], loaded)


def _row_str(row: sqlite3.Row, key: str) -> str:
    return cast(str, row[key])
