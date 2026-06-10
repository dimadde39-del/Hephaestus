"""SQLite persistence for validation execution plans and evidence."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from hephaestus.storage.sqlite import connect_database, init_database
from hephaestus.validation.schemas import (
    ReleaseValidationSummary,
    ValidationEvidence,
    ValidationExecutionPlan,
    ValidationSuiteResult,
)


class ValidationRepository:
    """Persist validation plans, command evidence, and release summaries."""

    def __init__(self, database_path: Path | str | None = None) -> None:
        self.database_path = init_database(database_path)

    def save_plan(self, plan: ValidationExecutionPlan) -> ValidationExecutionPlan:
        """Persist a validation execution plan and its commands."""

        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO validation_plans (
                    id, repo_path, repo_profile_id, release_plan_id, run_id,
                    command_count, confidence, status, created_at, updated_at, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    repo_path = excluded.repo_path,
                    repo_profile_id = excluded.repo_profile_id,
                    release_plan_id = excluded.release_plan_id,
                    run_id = excluded.run_id,
                    command_count = excluded.command_count,
                    confidence = excluded.confidence,
                    status = excluded.status,
                    updated_at = excluded.updated_at,
                    raw_json = excluded.raw_json
                """,
                (
                    plan.id,
                    plan.repo_path,
                    plan.repo_profile_id,
                    plan.release_plan_id,
                    plan.run_id,
                    len(plan.commands),
                    plan.confidence,
                    "planned",
                    _datetime_to_text(plan.created_at),
                    _datetime_to_text(plan.updated_at),
                    plan.model_dump_json(),
                ),
            )
            connection.execute("DELETE FROM validation_commands WHERE plan_id = ?", (plan.id,))
            for command in plan.commands:
                connection.execute(
                    """
                    INSERT OR REPLACE INTO validation_commands (
                        id, plan_id, repo_profile_id, command_text, command_type,
                        source, risk_level, requires_approval, blocked,
                        execution_order, decision_trace_id, created_at, raw_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        command.id,
                        plan.id,
                        command.repo_profile_id or plan.repo_profile_id,
                        command.command,
                        command.command_type.value,
                        command.source,
                        command.risk_level.value,
                        int(command.requires_approval),
                        int(command.blocked),
                        command.order,
                        command.decision_trace_id,
                        _datetime_to_text(command.created_at),
                        command.model_dump_json(),
                    ),
                )
        return plan

    def get_plan(self, plan_id: str) -> ValidationExecutionPlan | None:
        """Read one validation plan."""

        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT raw_json FROM validation_plans WHERE id = ?",
                (plan_id,),
            ).fetchone()
        if row is None:
            return None
        return ValidationExecutionPlan.model_validate_json(_row_str(row, "raw_json"))

    def latest_plan_for_path(self, path: Path | str) -> ValidationExecutionPlan | None:
        """Return newest validation plan for a repository path."""

        repo_path = str(Path(path).resolve())
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT raw_json FROM validation_plans
                WHERE repo_path = ?
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (repo_path,),
            ).fetchone()
        if row is None:
            return None
        return ValidationExecutionPlan.model_validate_json(_row_str(row, "raw_json"))

    def save_evidence(self, evidence: ValidationEvidence) -> ValidationEvidence:
        """Persist one command evidence record."""

        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO validation_evidence (
                    id, validation_result_id, plan_id, command_id, repo_path,
                    repo_profile_id, command_text, command_type, status, exit_code,
                    stdout_summary, stderr_summary, duration_seconds, tool_action_id,
                    tool_execution_result_id, outcome_id, decision_trace_id,
                    failure_classification, warning_count, created_at, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evidence.id,
                    evidence.validation_result_id,
                    evidence.plan_id,
                    evidence.command_id,
                    evidence.repo_path,
                    evidence.repo_profile_id,
                    evidence.command,
                    evidence.command_type.value,
                    evidence.status.value,
                    evidence.exit_code,
                    evidence.stdout_summary,
                    evidence.stderr_summary,
                    evidence.duration_seconds,
                    evidence.tool_action_id,
                    evidence.tool_execution_result_id,
                    evidence.outcome_id,
                    evidence.decision_trace_id,
                    evidence.failure_classification,
                    evidence.warning_count,
                    _datetime_to_text(evidence.created_at),
                    evidence.model_dump_json(),
                ),
            )
        return evidence

    def save_suite_result(self, suite: ValidationSuiteResult) -> ValidationSuiteResult:
        """Persist a validation suite result and all child evidence."""

        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO validation_results (
                    id, plan_id, repo_path, repo_profile_id, release_plan_id, run_id,
                    status, command_count, pass_count, fail_count, skipped_count,
                    timed_out_count, blocked_count, requires_approval_count,
                    warning_count, readiness_impact, evidence_mode, summary,
                    created_at, updated_at, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status = excluded.status,
                    command_count = excluded.command_count,
                    pass_count = excluded.pass_count,
                    fail_count = excluded.fail_count,
                    skipped_count = excluded.skipped_count,
                    timed_out_count = excluded.timed_out_count,
                    blocked_count = excluded.blocked_count,
                    requires_approval_count = excluded.requires_approval_count,
                    warning_count = excluded.warning_count,
                    readiness_impact = excluded.readiness_impact,
                    evidence_mode = excluded.evidence_mode,
                    summary = excluded.summary,
                    updated_at = excluded.updated_at,
                    raw_json = excluded.raw_json
                """,
                (
                    suite.id,
                    suite.plan_id,
                    suite.repo_path,
                    suite.repo_profile_id,
                    suite.release_plan_id,
                    suite.run_id,
                    suite.status.value,
                    len(suite.command_results),
                    suite.pass_count,
                    suite.fail_count,
                    suite.skipped_count,
                    suite.timed_out_count,
                    suite.blocked_count,
                    suite.requires_approval_count,
                    suite.warning_count,
                    suite.readiness_impact,
                    suite.evidence_mode,
                    suite.summary,
                    _datetime_to_text(suite.created_at),
                    _datetime_to_text(suite.updated_at),
                    suite.model_dump_json(),
                ),
            )
        for evidence in suite.evidence:
            self.save_evidence(evidence)
        return suite

    def get_suite_result(self, result_id: str) -> ValidationSuiteResult | None:
        """Read one validation suite result."""

        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT raw_json FROM validation_results WHERE id = ?",
                (result_id,),
            ).fetchone()
        if row is None:
            return None
        return ValidationSuiteResult.model_validate_json(_row_str(row, "raw_json"))

    def list_suite_results(
        self,
        *,
        repo_path: Path | str | None = None,
        limit: int = 20,
    ) -> list[ValidationSuiteResult]:
        """List recent validation suite results."""

        with connect_database(self.database_path) as connection:
            if repo_path is None:
                rows = connection.execute(
                    """
                    SELECT raw_json FROM validation_results
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT raw_json FROM validation_results
                    WHERE repo_path = ?
                    ORDER BY created_at DESC, id DESC
                    LIMIT ?
                    """,
                    (str(Path(repo_path).resolve()), limit),
                ).fetchall()
        return [ValidationSuiteResult.model_validate_json(_row_str(row, "raw_json")) for row in rows]

    def latest_suite_result_for_path(self, path: Path | str) -> ValidationSuiteResult | None:
        """Return newest validation suite result for a repository path."""

        results = self.list_suite_results(repo_path=path, limit=1)
        return results[0] if results else None

    def list_evidence_for_result(self, result_id: str) -> list[ValidationEvidence]:
        """List command evidence for one validation result."""

        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT raw_json FROM validation_evidence
                WHERE validation_result_id = ?
                ORDER BY created_at, id
                """,
                (result_id,),
            ).fetchall()
        return [ValidationEvidence.model_validate_json(_row_str(row, "raw_json")) for row in rows]

    def count_failure_pattern(
        self,
        *,
        repo_path: str,
        command: str,
        command_type: str,
        failure_classification: str,
    ) -> int:
        """Count previous matching validation failure evidence."""

        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM validation_evidence
                WHERE repo_path = ?
                  AND command_text = ?
                  AND command_type = ?
                  AND failure_classification = ?
                  AND status IN ('failed', 'timed_out', 'blocked', 'requires_approval')
                """,
                (repo_path, command, command_type, failure_classification),
            ).fetchone()
        return int(cast(int, row["count"])) if row is not None else 0

    def save_release_summary(
        self,
        summary: ReleaseValidationSummary,
    ) -> ReleaseValidationSummary:
        """Persist a release validation summary."""

        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO release_validation_summaries (
                    id, release_plan_id, validation_result_id, repo_path,
                    repo_profile_id, status, evidence_based, simulated,
                    readiness_score_before, readiness_score_after,
                    readiness_score_delta, pass_count, fail_count, timed_out_count,
                    blocked_count, requires_approval_count, skipped_count,
                    warning_count, summary, created_at, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    summary.id,
                    summary.release_plan_id,
                    summary.validation_result_id,
                    summary.repo_path,
                    summary.repo_profile_id,
                    summary.status.value,
                    int(summary.evidence_based),
                    int(summary.simulated),
                    summary.readiness_score_before,
                    summary.readiness_score_after,
                    summary.readiness_score_delta,
                    summary.pass_count,
                    summary.fail_count,
                    summary.timed_out_count,
                    summary.blocked_count,
                    summary.requires_approval_count,
                    summary.skipped_count,
                    summary.warning_count,
                    summary.summary,
                    _datetime_to_text(summary.created_at),
                    summary.model_dump_json(),
                ),
            )
        return summary

    def latest_release_summary(
        self,
        *,
        release_plan_id: str | None = None,
        validation_result_id: str | None = None,
    ) -> ReleaseValidationSummary | None:
        """Read the newest release validation summary by release or result id."""

        clauses: list[str] = []
        params: list[str] = []
        if release_plan_id is not None:
            clauses.append("release_plan_id = ?")
            params.append(release_plan_id)
        if validation_result_id is not None:
            clauses.append("validation_result_id = ?")
            params.append(validation_result_id)
        if not clauses:
            return None
        where = " AND ".join(clauses)
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                f"""
                SELECT raw_json FROM release_validation_summaries
                WHERE {where}
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                params,
            ).fetchone()
        if row is None:
            return None
        return ReleaseValidationSummary.model_validate_json(_row_str(row, "raw_json"))


def _datetime_to_text(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _row_str(row: sqlite3.Row, key: str) -> str:
    return cast(str, row[key])
