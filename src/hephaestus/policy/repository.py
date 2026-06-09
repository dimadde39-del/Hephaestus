"""SQLite persistence for policy profile configuration and evaluations."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from hephaestus.policy.profiles import (
    built_in_policy_profiles,
    default_policy_profile,
    get_builtin_policy_profile,
)
from hephaestus.policy.schemas import (
    PolicyEvaluation,
    PolicyProfile,
    PolicyProfileType,
)
from hephaestus.storage.sqlite import connect_database, init_database

ACTIVE_PROFILE_KEY = "active_policy_profile"


class PolicyRepository:
    """Persist active policy profile, custom profiles, and evaluations."""

    def __init__(self, database_path: Path | str | None = None) -> None:
        self.database_path = init_database(database_path)

    def list_profiles(self) -> list[PolicyProfile]:
        """List built-in and custom policy profiles."""

        return [*built_in_policy_profiles(), *self.list_custom_profiles()]

    def get_profile(self, profile_id: str | PolicyProfileType) -> PolicyProfile | None:
        """Resolve a built-in or custom policy profile."""

        value = profile_id.value if isinstance(profile_id, PolicyProfileType) else profile_id
        try:
            built_in = get_builtin_policy_profile(value)
        except ValueError:
            built_in = None
        if built_in is not None:
            return built_in
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT raw_json FROM policy_custom_profiles
                WHERE id = ? OR profile_type = ? OR name = ?
                ORDER BY updated_at DESC
                LIMIT 1
                """,
                (value, value, value),
            ).fetchone()
        if row is None:
            return None
        return PolicyProfile.model_validate_json(_row_str(row, "raw_json"))

    def get_active_profile_name(self) -> str:
        """Return the configured active profile id, or balanced when unset."""

        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT value FROM policy_settings WHERE key = ?",
                (ACTIVE_PROFILE_KEY,),
            ).fetchone()
        if row is None:
            return PolicyProfileType.BALANCED.value
        return _row_str(row, "value")

    def get_active_profile(self) -> PolicyProfile:
        """Return the active profile, falling back to balanced."""

        profile = self.get_profile(self.get_active_profile_name())
        return profile if profile is not None else default_policy_profile()

    def set_active_profile(self, profile_id: str | PolicyProfileType) -> PolicyProfile | None:
        """Set the active policy profile if it exists."""

        profile = self.get_profile(profile_id)
        if profile is None:
            return None
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO policy_settings (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (
                    ACTIVE_PROFILE_KEY,
                    profile.id,
                    _datetime_to_text(datetime.now(UTC)),
                ),
            )
        return profile

    def save_custom_profile(self, profile: PolicyProfile) -> PolicyProfile:
        """Persist a custom policy profile."""

        if profile.profile_type != PolicyProfileType.CUSTOM:
            raise ValueError("Only custom policy profiles can be saved as custom profiles.")
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO policy_custom_profiles (
                    id, profile_type, name, created_at, updated_at, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    profile.id,
                    profile.profile_type.value,
                    profile.name,
                    _datetime_to_text(profile.created_at),
                    _datetime_to_text(profile.updated_at),
                    profile.model_dump_json(),
                ),
            )
        return profile

    def list_custom_profiles(self) -> list[PolicyProfile]:
        """List persisted custom policy profiles."""

        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT raw_json FROM policy_custom_profiles
                ORDER BY updated_at DESC, id
                """
            ).fetchall()
        return [PolicyProfile.model_validate_json(_row_str(row, "raw_json")) for row in rows]

    def record_evaluation(self, evaluation: PolicyEvaluation) -> PolicyEvaluation:
        """Persist a policy evaluation for transparency and later analysis."""

        raw = evaluation.model_dump(mode="json")
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO policy_evaluations (
                    id, prompt, profile_type, profile_name, decision_type,
                    primary_category, categories_json, requires_approval,
                    created_at, over_refusal_detected, moralizing_detected,
                    notes_json, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    evaluation.id,
                    evaluation.prompt,
                    evaluation.profile_type.value,
                    evaluation.profile_name,
                    evaluation.decision.decision_type.value,
                    evaluation.decision.primary_category.value,
                    _json_dumps([category.value for category in evaluation.decision.categories]),
                    int(evaluation.decision.requires_approval),
                    _datetime_to_text(evaluation.created_at),
                    int(evaluation.over_refusal_detected),
                    int(evaluation.moralizing_detected),
                    _json_dumps(evaluation.notes),
                    _json_dumps(raw),
                ),
            )
        return evaluation

    def list_evaluations(self, *, limit: int = 20) -> list[PolicyEvaluation]:
        """List recent policy evaluations."""

        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT raw_json FROM policy_evaluations
                ORDER BY created_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [PolicyEvaluation.model_validate_json(_row_str(row, "raw_json")) for row in rows]


def _datetime_to_text(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _row_str(row: sqlite3.Row, key: str) -> str:
    return cast(str, row[key])
