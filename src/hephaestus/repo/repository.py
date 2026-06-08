"""SQLite persistence for repository intelligence profiles."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any, cast

from hephaestus.repo.analysis import repo_stack_summary
from hephaestus.repo.schemas import RepoInspectionReport, RepoProfile
from hephaestus.storage.sqlite import connect_database, init_database


class RepoProfileRepository:
    """Persist and read repo intelligence profiles."""

    def __init__(self, database_path: Path | str | None = None) -> None:
        self.database_path = init_database(database_path)

    def save_profile(self, profile: RepoProfile) -> RepoProfile:
        """Persist one repository profile."""

        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO repo_profiles (
                    id, repo_path, repo_name, detected_stack_summary,
                    validation_plan_json, generated_tasks_json, risk_summary_json,
                    inspected_at, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile.id,
                    profile.path,
                    profile.name,
                    repo_stack_summary(profile),
                    profile.validation_plan.model_dump_json(),
                    _json_dumps([task.model_dump(mode="json") for task in profile.generated_tasks]),
                    _json_dumps([signal.model_dump(mode="json") for signal in profile.risk_signals]),
                    _datetime_to_text(profile.inspected_at),
                    profile.model_dump_json(),
                ),
            )
        return profile

    def save_inspection(self, report: RepoInspectionReport) -> RepoInspectionReport:
        """Persist a complete inspection report and its profile."""

        self.save_profile(report.profile)
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO repo_inspections (
                    id, profile_id, repo_path, repo_name, inspected_at, summary,
                    detected_stack_summary, validation_summary, risk_summary, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    report.id,
                    report.profile.id,
                    report.profile.path,
                    report.profile.name,
                    _datetime_to_text(report.inspected_at),
                    report.summary,
                    report.detected_stack_summary,
                    report.validation_summary,
                    report.risk_summary,
                    report.model_dump_json(),
                ),
            )
        return report

    def list_profiles(self, *, limit: int = 20) -> list[RepoProfile]:
        """List recent repo profiles newest-first."""

        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT raw_json FROM repo_profiles
                ORDER BY inspected_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [RepoProfile.model_validate_json(_row_str(row, "raw_json")) for row in rows]

    def get_profile(self, profile_id: str) -> RepoProfile | None:
        """Read one repo profile by ID."""

        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT raw_json FROM repo_profiles WHERE id = ?",
                (profile_id,),
            ).fetchone()
        if row is None:
            return None
        return RepoProfile.model_validate_json(_row_str(row, "raw_json"))

    def latest_profile_for_path(self, path: Path | str) -> RepoProfile | None:
        """Return the newest profile for a repository path."""

        repo_path = str(Path(path).resolve())
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT raw_json FROM repo_profiles
                WHERE repo_path = ?
                ORDER BY inspected_at DESC, id DESC
                LIMIT 1
                """,
                (repo_path,),
            ).fetchone()
        if row is None:
            return None
        return RepoProfile.model_validate_json(_row_str(row, "raw_json"))

    def list_inspections(
        self,
        *,
        profile_id: str | None = None,
        limit: int = 20,
    ) -> list[RepoInspectionReport]:
        """List persisted repo inspections."""

        with connect_database(self.database_path) as connection:
            if profile_id is None:
                rows = connection.execute(
                    """
                    SELECT raw_json FROM repo_inspections
                    ORDER BY inspected_at DESC, id DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT raw_json FROM repo_inspections
                    WHERE profile_id = ?
                    ORDER BY inspected_at DESC, id DESC
                    LIMIT ?
                    """,
                    (profile_id, limit),
                ).fetchall()
        return [RepoInspectionReport.model_validate_json(_row_str(row, "raw_json")) for row in rows]


def _datetime_to_text(value: object) -> str:
    if hasattr(value, "isoformat"):
        return str(value.isoformat())
    return str(value)


def _json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _row_str(row: sqlite3.Row, key: str) -> str:
    return cast(str, row[key])
