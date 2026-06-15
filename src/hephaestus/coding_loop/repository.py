"""SQLite persistence for repo-aware coding loop records."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from hephaestus.coding_loop.schemas import (
    CodingChangeProposal,
    CodingIteration,
    CodingLoopDetail,
    CodingLoopResult,
    CodingLoopStatus,
    CodingPlan,
    CodingRequest,
)
from hephaestus.storage.sqlite import connect_database, init_database


class CodingLoopRepository:
    """Persist coding requests, plans, proposals, iterations, and results."""

    def __init__(self, database_path: Path | str | None = None) -> None:
        self.database_path = init_database(database_path)

    def create_coding_request(self, request: CodingRequest) -> CodingRequest:
        """Insert or update a coding request."""

        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO coding_requests (
                    id, repo_path, repo_profile_id, conversation_id, run_id,
                    active_policy_profile, user_request, scope_type, risk, status,
                    plan_summary, likely_files_json, patch_ids_json,
                    tool_action_ids_json, checkpoint_ids_json, validation_result_ids_json,
                    outcome_ids_json, decision_trace_ids_json, created_at, updated_at, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    repo_path = excluded.repo_path,
                    repo_profile_id = excluded.repo_profile_id,
                    conversation_id = excluded.conversation_id,
                    run_id = excluded.run_id,
                    active_policy_profile = excluded.active_policy_profile,
                    user_request = excluded.user_request,
                    updated_at = excluded.updated_at,
                    raw_json = excluded.raw_json
                """,
                (
                    request.id,
                    request.repo_path,
                    request.repo_profile_id,
                    request.conversation_id,
                    request.run_id,
                    request.active_policy_profile,
                    request.user_request,
                    (request.requested_scope.value if request.requested_scope is not None else "unknown"),
                    "medium",
                    CodingLoopStatus.PLANNED.value,
                    "",
                    "[]",
                    "[]",
                    "[]",
                    "[]",
                    "[]",
                    "[]",
                    "[]",
                    _datetime_to_text(request.created_at),
                    _datetime_to_text(request.updated_at),
                    request.model_dump_json(),
                ),
            )
        return request

    def get_request(self, request_id: str) -> CodingRequest | None:
        """Read one coding request."""

        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT raw_json FROM coding_requests WHERE id = ?",
                (request_id,),
            ).fetchone()
        if row is None:
            return None
        return CodingRequest.model_validate_json(_row_str(row, "raw_json"))

    def save_plan(self, plan: CodingPlan) -> CodingPlan:
        """Persist a coding plan and update request summary columns."""

        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO coding_plans (
                    id, request_id, repo_path, repo_profile_id, conversation_id,
                    run_id, active_policy_profile, user_request, scope_type, risk,
                    status, summary, likely_files_json, validation_commands_json,
                    validation_plan_id, patch_proposal_possible, scope_too_large,
                    requires_approval, decision_trace_ids_json, created_at,
                    updated_at, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    summary = excluded.summary,
                    likely_files_json = excluded.likely_files_json,
                    validation_commands_json = excluded.validation_commands_json,
                    validation_plan_id = excluded.validation_plan_id,
                    patch_proposal_possible = excluded.patch_proposal_possible,
                    scope_too_large = excluded.scope_too_large,
                    requires_approval = excluded.requires_approval,
                    decision_trace_ids_json = excluded.decision_trace_ids_json,
                    updated_at = excluded.updated_at,
                    raw_json = excluded.raw_json
                """,
                (
                    plan.id,
                    plan.request_id,
                    plan.repo_path,
                    plan.repo_profile_id,
                    plan.conversation_id,
                    plan.run_id,
                    plan.active_policy_profile,
                    plan.user_request,
                    plan.scope.scope_type.value,
                    plan.scope.risk.value,
                    plan.status.value,
                    plan.summary,
                    _json_dumps(plan.likely_files),
                    _json_dumps(plan.validation_commands),
                    plan.validation_plan_id,
                    int(plan.patch_proposal_possible),
                    int(plan.scope_too_large),
                    int(plan.requires_approval),
                    _json_dumps(plan.decision_trace_ids),
                    _datetime_to_text(plan.created_at),
                    _datetime_to_text(plan.updated_at),
                    plan.model_dump_json(),
                ),
            )
            connection.execute(
                """
                UPDATE coding_requests
                SET repo_profile_id = ?,
                    run_id = ?,
                    active_policy_profile = ?,
                    scope_type = ?,
                    risk = ?,
                    status = ?,
                    plan_summary = ?,
                    likely_files_json = ?,
                    decision_trace_ids_json = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    plan.repo_profile_id,
                    plan.run_id,
                    plan.active_policy_profile,
                    plan.scope.scope_type.value,
                    plan.scope.risk.value,
                    plan.status.value,
                    plan.summary,
                    _json_dumps(plan.likely_files),
                    _json_dumps(plan.decision_trace_ids),
                    _datetime_to_text(plan.updated_at),
                    plan.request_id,
                ),
            )
        return plan

    def get_plan(self, plan_id: str) -> CodingPlan | None:
        """Read one coding plan."""

        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT raw_json FROM coding_plans WHERE id = ?",
                (plan_id,),
            ).fetchone()
        if row is None:
            return None
        return CodingPlan.model_validate_json(_row_str(row, "raw_json"))

    def latest_plan_for_request(self, request_id: str) -> CodingPlan | None:
        """Return the newest plan for a request."""

        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT raw_json FROM coding_plans
                WHERE request_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (request_id,),
            ).fetchone()
        if row is None:
            return None
        return CodingPlan.model_validate_json(_row_str(row, "raw_json"))

    def save_change_proposal(self, change: CodingChangeProposal) -> CodingChangeProposal:
        """Persist a coding change proposal."""

        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO coding_changes (
                    id, request_id, plan_id, repo_path, repo_profile_id,
                    active_policy_profile, scope_type, risk, status, summary,
                    files_touched_json, patch_ids_json, tool_action_ids_json,
                    review_id, decision_trace_ids_json, outcome_ids_json,
                    created_at, updated_at, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    summary = excluded.summary,
                    files_touched_json = excluded.files_touched_json,
                    patch_ids_json = excluded.patch_ids_json,
                    tool_action_ids_json = excluded.tool_action_ids_json,
                    review_id = excluded.review_id,
                    decision_trace_ids_json = excluded.decision_trace_ids_json,
                    outcome_ids_json = excluded.outcome_ids_json,
                    updated_at = excluded.updated_at,
                    raw_json = excluded.raw_json
                """,
                (
                    change.id,
                    change.request_id,
                    change.plan_id,
                    change.repo_path,
                    change.repo_profile_id,
                    change.active_policy_profile,
                    change.scope_type.value,
                    change.risk.value,
                    change.status.value,
                    change.summary,
                    _json_dumps(change.patch_set.files_touched),
                    _json_dumps(change.patch_set.patch_ids),
                    _json_dumps(change.patch_set.tool_action_ids),
                    change.review_id,
                    _json_dumps(change.decision_trace_ids),
                    _json_dumps(change.outcome_ids),
                    _datetime_to_text(change.created_at),
                    _datetime_to_text(change.updated_at),
                    change.model_dump_json(),
                ),
            )
            connection.execute(
                """
                UPDATE coding_requests
                SET status = ?,
                    patch_ids_json = ?,
                    tool_action_ids_json = ?,
                    outcome_ids_json = ?,
                    decision_trace_ids_json = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    change.status.value,
                    _json_dumps(change.patch_set.patch_ids),
                    _json_dumps(change.patch_set.tool_action_ids),
                    _json_dumps(change.outcome_ids),
                    _json_dumps(change.decision_trace_ids),
                    _datetime_to_text(change.updated_at),
                    change.request_id,
                ),
            )
        return change

    def get_change_proposal(self, change_id: str) -> CodingChangeProposal | None:
        """Read one coding change proposal by change id or tool patch id."""

        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT raw_json FROM coding_changes
                WHERE id = ? OR patch_ids_json LIKE ?
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (change_id, f"%{change_id}%"),
            ).fetchone()
        if row is None:
            return None
        return CodingChangeProposal.model_validate_json(_row_str(row, "raw_json"))

    def latest_change_for_request(self, request_id: str) -> CodingChangeProposal | None:
        """Return the newest proposal for a request."""

        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT raw_json FROM coding_changes
                WHERE request_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (request_id,),
            ).fetchone()
        if row is None:
            return None
        return CodingChangeProposal.model_validate_json(_row_str(row, "raw_json"))

    def save_iteration(self, iteration: CodingIteration) -> CodingIteration:
        """Persist a coding loop iteration."""

        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO coding_iterations (
                    id, request_id, plan_id, change_id, review_id, status,
                    summary, apply_tool_action_id, apply_tool_result_id,
                    checkpoint_id, validation_result_id, rollback_tool_action_id,
                    rollback_checkpoint_id, outcome_ids_json, learning_signal_ids_json,
                    decision_trace_ids_json, created_at, updated_at, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    summary = excluded.summary,
                    apply_tool_action_id = excluded.apply_tool_action_id,
                    apply_tool_result_id = excluded.apply_tool_result_id,
                    checkpoint_id = excluded.checkpoint_id,
                    validation_result_id = excluded.validation_result_id,
                    rollback_tool_action_id = excluded.rollback_tool_action_id,
                    rollback_checkpoint_id = excluded.rollback_checkpoint_id,
                    outcome_ids_json = excluded.outcome_ids_json,
                    learning_signal_ids_json = excluded.learning_signal_ids_json,
                    decision_trace_ids_json = excluded.decision_trace_ids_json,
                    updated_at = excluded.updated_at,
                    raw_json = excluded.raw_json
                """,
                (
                    iteration.id,
                    iteration.request_id,
                    iteration.plan_id,
                    iteration.change_id,
                    iteration.review_id,
                    iteration.status.value,
                    iteration.summary,
                    iteration.apply_tool_action_id,
                    iteration.apply_tool_result_id,
                    iteration.checkpoint_id,
                    iteration.validation_result_id,
                    iteration.rollback_tool_action_id,
                    iteration.rollback_checkpoint_id,
                    _json_dumps(iteration.outcome_ids),
                    _json_dumps(iteration.learning_signal_ids),
                    _json_dumps(iteration.decision_trace_ids),
                    _datetime_to_text(iteration.created_at),
                    _datetime_to_text(iteration.updated_at),
                    iteration.model_dump_json(),
                ),
            )
        return iteration

    def latest_iteration_for_request(self, request_id: str) -> CodingIteration | None:
        """Return the newest iteration for a request."""

        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT raw_json FROM coding_iterations
                WHERE request_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (request_id,),
            ).fetchone()
        if row is None:
            return None
        return CodingIteration.model_validate_json(_row_str(row, "raw_json"))

    def save_result(self, result: CodingLoopResult) -> CodingLoopResult:
        """Persist a coding loop result and update request summary columns."""

        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO coding_loop_results (
                    id, request_id, plan_id, change_id, repo_path, repo_profile_id,
                    conversation_id, run_id, active_policy_profile, user_request,
                    scope_type, risk, status, summary, iteration_ids_json,
                    patch_ids_json, tool_action_ids_json, checkpoint_ids_json,
                    validation_result_ids_json, outcome_ids_json,
                    learning_signal_ids_json, decision_trace_ids_json,
                    created_at, updated_at, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    summary = excluded.summary,
                    iteration_ids_json = excluded.iteration_ids_json,
                    patch_ids_json = excluded.patch_ids_json,
                    tool_action_ids_json = excluded.tool_action_ids_json,
                    checkpoint_ids_json = excluded.checkpoint_ids_json,
                    validation_result_ids_json = excluded.validation_result_ids_json,
                    outcome_ids_json = excluded.outcome_ids_json,
                    learning_signal_ids_json = excluded.learning_signal_ids_json,
                    decision_trace_ids_json = excluded.decision_trace_ids_json,
                    updated_at = excluded.updated_at,
                    raw_json = excluded.raw_json
                """,
                (
                    result.id,
                    result.request_id,
                    result.plan_id,
                    result.change_id,
                    result.repo_path,
                    result.repo_profile_id,
                    result.conversation_id,
                    result.run_id,
                    result.active_policy_profile,
                    result.user_request,
                    result.scope_type.value,
                    result.risk.value,
                    result.status.value,
                    result.summary,
                    _json_dumps(result.iteration_ids),
                    _json_dumps(result.patch_ids),
                    _json_dumps(result.tool_action_ids),
                    _json_dumps(result.checkpoint_ids),
                    _json_dumps(result.validation_result_ids),
                    _json_dumps(result.outcome_ids),
                    _json_dumps(result.learning_signal_ids),
                    _json_dumps(result.decision_trace_ids),
                    _datetime_to_text(result.created_at),
                    _datetime_to_text(result.updated_at),
                    result.model_dump_json(),
                ),
            )
            connection.execute(
                """
                UPDATE coding_requests
                SET status = ?,
                    scope_type = ?,
                    risk = ?,
                    patch_ids_json = ?,
                    tool_action_ids_json = ?,
                    checkpoint_ids_json = ?,
                    validation_result_ids_json = ?,
                    outcome_ids_json = ?,
                    decision_trace_ids_json = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    result.status.value,
                    result.scope_type.value,
                    result.risk.value,
                    _json_dumps(result.patch_ids),
                    _json_dumps(result.tool_action_ids),
                    _json_dumps(result.checkpoint_ids),
                    _json_dumps(result.validation_result_ids),
                    _json_dumps(result.outcome_ids),
                    _json_dumps(result.decision_trace_ids),
                    _datetime_to_text(result.updated_at),
                    result.request_id,
                ),
            )
        return result

    def get_result(self, result_id: str) -> CodingLoopResult | None:
        """Read one coding loop result by result id or request id."""

        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT raw_json FROM coding_loop_results
                WHERE id = ? OR request_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (result_id, result_id),
            ).fetchone()
        if row is None:
            return None
        return CodingLoopResult.model_validate_json(_row_str(row, "raw_json"))

    def list_results(self, *, limit: int = 20) -> list[CodingLoopResult]:
        """List recent coding loop results."""

        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT raw_json FROM coding_loop_results
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [CodingLoopResult.model_validate_json(_row_str(row, "raw_json")) for row in rows]

    def show_result(self, identifier: str) -> CodingLoopDetail:
        """Return a joined detail view by request id, result id, plan id, or change id."""

        result = self.get_result(identifier)
        request_id = result.request_id if result is not None else identifier
        request = self.get_request(request_id)
        if request is None:
            plan = self.get_plan(identifier)
            if plan is not None:
                request_id = plan.request_id
                request = self.get_request(request_id)
            else:
                change = self.get_change_proposal(identifier)
                if change is not None:
                    request_id = change.request_id
                    request = self.get_request(request_id)
        plan = self.latest_plan_for_request(request_id) if request is not None else None
        change = self.latest_change_for_request(request_id) if request is not None else None
        iteration = self.latest_iteration_for_request(request_id) if request is not None else None
        if result is None and request is not None:
            result = self.get_result(request.id)
        return CodingLoopDetail(
            request=request,
            plan=plan,
            change=change,
            iteration=iteration,
            result=result,
        )


def _datetime_to_text(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _row_str(row: sqlite3.Row, key: str) -> str:
    return cast(str, row[key])
