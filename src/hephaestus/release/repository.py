"""SQLite persistence for repo-aware release planning results."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, cast

from hephaestus.release.schemas import ReleasePlanningResult
from hephaestus.storage.sqlite import connect_database, init_database


class ReleasePlanRepository:
    """Persist and read release planning results."""

    def __init__(self, database_path: Path | str | None = None) -> None:
        self.database_path = init_database(database_path)

    def save_release_plan(self, plan: ReleasePlanningResult) -> ReleasePlanningResult:
        """Persist one release planning result."""

        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO release_plans (
                    id, repo_profile_id, goal, optimizer_run_id, readiness_score,
                    recommendation_status, recommendation_summary,
                    pareto_frontier_ids_json, qubo_problem_ids_json,
                    decision_trace_ids_json, outcome_ids_json, learning_signal_ids_json,
                    raw_json, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    plan.id,
                    plan.repo_profile_id,
                    plan.goal,
                    plan.optimizer_run_id,
                    plan.readiness_score,
                    plan.recommendation.status.value,
                    plan.recommendation.summary,
                    _json_dumps(plan.pareto_frontier_ids),
                    _json_dumps(plan.qubo_problem_ids),
                    _json_dumps(plan.decision_trace_ids),
                    _json_dumps(plan.outcome_ids),
                    _json_dumps(plan.learning_signal_ids),
                    plan.model_dump_json(),
                    _datetime_to_text(plan.created_at),
                ),
            )
        return plan

    def list_release_plans(self, *, limit: int = 20) -> list[ReleasePlanningResult]:
        """List recent release planning results newest-first."""

        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT raw_json FROM release_plans
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [ReleasePlanningResult.model_validate_json(_row_str(row, "raw_json")) for row in rows]

    def get_release_plan(self, release_plan_id: str) -> ReleasePlanningResult | None:
        """Read one release planning result by ID."""

        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT raw_json FROM release_plans WHERE id = ?",
                (release_plan_id,),
            ).fetchone()
        if row is None:
            return None
        return ReleasePlanningResult.model_validate_json(_row_str(row, "raw_json"))

    def latest_release_plan_for_repo_profile(
        self,
        repo_profile_id: str,
    ) -> ReleasePlanningResult | None:
        """Return the newest release plan for one repo profile."""

        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT raw_json FROM release_plans
                WHERE repo_profile_id = ?
                ORDER BY created_at DESC, id DESC
                LIMIT 1
                """,
                (repo_profile_id,),
            ).fetchone()
        if row is None:
            return None
        return ReleasePlanningResult.model_validate_json(_row_str(row, "raw_json"))

    def latest_release_plan_for_path(self, path: Path | str) -> ReleasePlanningResult | None:
        """Return the newest release plan for a repository path."""

        repo_path = str(Path(path).resolve())
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT release_plans.raw_json
                FROM release_plans
                JOIN repo_profiles ON repo_profiles.id = release_plans.repo_profile_id
                WHERE repo_profiles.repo_path = ?
                ORDER BY release_plans.created_at DESC, release_plans.id DESC
                LIMIT 1
                """,
                (repo_path,),
            ).fetchone()
        if row is None:
            return None
        return ReleasePlanningResult.model_validate_json(_row_str(row, "raw_json"))


def _datetime_to_text(value: object) -> str:
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return str(value)


def _json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _row_str(row: sqlite3.Row, key: str) -> str:
    return cast(str, row[key])
