"""SQLite persistence for decision quality profiles."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from hephaestus.policy_learning.schemas import (
    DecisionArea,
    DecisionQualityProfile,
    ProfileApplicationResult,
    ProfileStatus,
)
from hephaestus.storage.sqlite import connect_database, init_database


class ProfileStore:
    """Persist profiles and profile application records."""

    def __init__(self, database_path: Path | str | None = None) -> None:
        self.database_path = init_database(database_path)

    def save_profile(self, profile: DecisionQualityProfile) -> DecisionQualityProfile:
        """Insert or replace a decision quality profile."""

        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO decision_quality_profiles (
                    id, name, decision_area, status, created_at, updated_at,
                    description, rules_json, evidence_json, confidence,
                    source_learning_signal_ids_json, source_outcome_ids_json,
                    source_policy_suggestion_ids_json, tags_json, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _profile_values(profile),
            )
        return profile

    def list_profiles(
        self,
        *,
        status: ProfileStatus | str | None = None,
        decision_area: DecisionArea | str | None = None,
    ) -> list[DecisionQualityProfile]:
        """List profiles with optional status and area filters."""

        clauses: list[str] = []
        params: list[str] = []
        if status is not None:
            clauses.append("status = ?")
            params.append(status.value if isinstance(status, ProfileStatus) else status)
        if decision_area is not None:
            clauses.append("decision_area = ?")
            params.append(
                decision_area.value if isinstance(decision_area, DecisionArea) else decision_area
            )
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM decision_quality_profiles
                {where}
                ORDER BY created_at, id
                """,
                params,
            ).fetchall()
        return [_profile_from_row(row) for row in rows]

    def get_profile(self, profile_id: str) -> DecisionQualityProfile | None:
        """Read one profile by id."""

        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM decision_quality_profiles WHERE id = ?",
                (profile_id,),
            ).fetchone()
        return _profile_from_row(row) if row is not None else None

    def activate_profile(self, profile_id: str) -> DecisionQualityProfile | None:
        """Mark a profile active."""

        profile = self.get_profile(profile_id)
        if profile is None:
            return None
        activated = profile.model_copy(
            update={
                "status": ProfileStatus.ACTIVE,
                "updated_at": datetime.now(UTC),
            }
        )
        return self.save_profile(activated)

    def archive_profile(self, profile_id: str) -> DecisionQualityProfile | None:
        """Archive a profile so it no longer influences future decisions."""

        profile = self.get_profile(profile_id)
        if profile is None:
            return None
        archived = profile.model_copy(
            update={
                "status": ProfileStatus.ARCHIVED,
                "updated_at": datetime.now(UTC),
            }
        )
        return self.save_profile(archived)

    def list_active_profiles(self) -> list[DecisionQualityProfile]:
        """List all active profiles."""

        return self.list_profiles(status=ProfileStatus.ACTIVE)

    def record_profile_application(
        self,
        application: ProfileApplicationResult,
    ) -> ProfileApplicationResult:
        """Persist a profile application result."""

        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO profile_applications (
                    id, profile_id, profile_name, decision_area, run_id, trace_id,
                    target, applied, created_at, effect_summary, before_json,
                    after_json, adjustments_json, notes_json, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _application_values(application),
            )
        return application

    def list_profile_applications(
        self,
        *,
        run_id: str | None = None,
        profile_id: str | None = None,
        decision_area: DecisionArea | str | None = None,
    ) -> list[ProfileApplicationResult]:
        """List recorded profile applications."""

        clauses: list[str] = []
        params: list[str] = []
        if run_id is not None:
            clauses.append("run_id = ?")
            params.append(run_id)
        if profile_id is not None:
            clauses.append("profile_id = ?")
            params.append(profile_id)
        if decision_area is not None:
            clauses.append("decision_area = ?")
            params.append(
                decision_area.value if isinstance(decision_area, DecisionArea) else decision_area
            )
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM profile_applications
                {where}
                ORDER BY created_at, id
                """,
                params,
            ).fetchall()
        return [_application_from_row(row) for row in rows]


def _profile_values(profile: DecisionQualityProfile) -> tuple[Any, ...]:
    raw = profile.model_dump(mode="json")
    return (
        profile.id,
        profile.name,
        profile.decision_area.value,
        profile.status.value,
        _datetime_to_text(profile.created_at),
        _datetime_to_text(profile.updated_at),
        profile.description,
        _json_dumps(raw["rules"]),
        _json_dumps(raw["evidence"]),
        profile.confidence,
        _json_dumps(profile.source_learning_signal_ids),
        _json_dumps(profile.source_outcome_ids),
        _json_dumps(profile.source_policy_suggestion_ids),
        _json_dumps(profile.tags),
        _json_dumps(raw),
    )


def _application_values(application: ProfileApplicationResult) -> tuple[Any, ...]:
    raw = application.model_dump(mode="json")
    return (
        application.id,
        application.profile_id,
        application.profile_name,
        application.decision_area.value,
        application.run_id,
        application.trace_id,
        application.target,
        int(application.applied),
        _datetime_to_text(application.created_at),
        application.effect_summary,
        _json_dumps(application.before),
        _json_dumps(application.after),
        _json_dumps(raw["adjustments_applied"]),
        _json_dumps(application.notes),
        _json_dumps(raw),
    )


def _profile_from_row(row: sqlite3.Row) -> DecisionQualityProfile:
    raw = _json_loads_dict(_row_optional_str(row, "raw_json") or "{}")
    if raw:
        return DecisionQualityProfile.model_validate(raw)
    return DecisionQualityProfile(
        id=_row_str(row, "id"),
        name=_row_str(row, "name"),
        decision_area=DecisionArea(_row_str(row, "decision_area")),
        status=ProfileStatus(_row_str(row, "status")),
        created_at=_datetime_from_text(_row_str(row, "created_at")),
        updated_at=_datetime_from_text(_row_str(row, "updated_at")),
        description=_row_str(row, "description"),
        rules=_json_loads(_row_str(row, "rules_json")),
        evidence=_json_loads(_row_str(row, "evidence_json")),
        confidence=_row_float(row, "confidence"),
        source_learning_signal_ids=_json_loads_list(
            _row_str(row, "source_learning_signal_ids_json")
        ),
        source_outcome_ids=_json_loads_list(_row_str(row, "source_outcome_ids_json")),
        source_policy_suggestion_ids=_json_loads_list(
            _row_str(row, "source_policy_suggestion_ids_json")
        ),
        tags=_json_loads_list(_row_str(row, "tags_json")),
    )


def _application_from_row(row: sqlite3.Row) -> ProfileApplicationResult:
    raw = _json_loads_dict(_row_optional_str(row, "raw_json") or "{}")
    if raw:
        return ProfileApplicationResult.model_validate(raw)
    return ProfileApplicationResult(
        id=_row_str(row, "id"),
        profile_id=_row_str(row, "profile_id"),
        profile_name=_row_str(row, "profile_name"),
        decision_area=DecisionArea(_row_str(row, "decision_area")),
        run_id=_row_optional_str(row, "run_id"),
        trace_id=_row_optional_str(row, "trace_id"),
        target=_row_str(row, "target"),
        applied=bool(_row_int(row, "applied")),
        created_at=_datetime_from_text(_row_str(row, "created_at")),
        effect_summary=_row_str(row, "effect_summary"),
        before=_json_loads_dict(_row_str(row, "before_json")),
        after=_json_loads_dict(_row_str(row, "after_json")),
        adjustments_applied=_json_loads(_row_str(row, "adjustments_json")),
        notes=_json_loads_list(_row_str(row, "notes_json")),
    )


def _datetime_to_text(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _datetime_from_text(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _json_loads(value: str) -> Any:
    return json.loads(value)


def _json_loads_dict(value: str) -> dict[str, Any]:
    loaded = json.loads(value)
    if not isinstance(loaded, dict):
        return {}
    return cast(dict[str, Any], loaded)


def _json_loads_list(value: str) -> list[str]:
    loaded = json.loads(value)
    if not isinstance(loaded, list):
        raise ValueError("Expected JSON list")
    return [str(item) for item in loaded]


def _row_str(row: sqlite3.Row, key: str) -> str:
    return cast(str, row[key])


def _row_optional_str(row: sqlite3.Row, key: str) -> str | None:
    return cast(str | None, row[key])


def _row_int(row: sqlite3.Row, key: str) -> int:
    return cast(int, row[key])


def _row_float(row: sqlite3.Row, key: str) -> float:
    return float(cast(int | float, row[key]))
