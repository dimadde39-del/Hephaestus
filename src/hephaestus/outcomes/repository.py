"""SQLite repository for outcomes, reflections, and learning signals."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from hephaestus.outcomes.schemas import (
    FailureMemoryDraft,
    LearningDirection,
    LearningSignal,
    LearningSignalStatus,
    LearningSignalType,
    OutcomeRecord,
    OutcomeStatus,
    PolicyArea,
    PolicyUpdateSuggestion,
    ReflectionRecord,
)
from hephaestus.storage.sqlite import connect_database, init_database


class OutcomeRepository:
    """Persist outcome learning records in SQLite."""

    def __init__(self, database_path: Path | str | None = None) -> None:
        self.database_path = init_database(database_path)

    def save_outcome(self, outcome: OutcomeRecord) -> OutcomeRecord:
        """Persist an outcome and link it back to its decision trace."""

        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO outcomes (
                    id, run_id, decision_trace_id, status, observed_at, summary,
                    metrics_json, evidence_json, severity, confidence, tags_json, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    outcome.id,
                    outcome.run_id,
                    outcome.decision_trace_id,
                    outcome.status.value,
                    _datetime_to_text(outcome.observed_at),
                    outcome.summary,
                    _json_dumps([item.model_dump(mode="json") for item in outcome.metrics]),
                    _json_dumps([item.model_dump(mode="json") for item in outcome.evidence]),
                    outcome.severity,
                    outcome.confidence,
                    _json_dumps(outcome.tags),
                    _json_dumps(outcome.model_dump(mode="json")),
                ),
            )
        self.link_decision_trace(outcome.decision_trace_id, outcome_id=outcome.id)
        return outcome

    def get_outcome(self, outcome_id: str) -> OutcomeRecord | None:
        """Read one outcome by ID."""

        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM outcomes WHERE id = ?",
                (outcome_id,),
            ).fetchone()
        return _outcome_from_row(row) if row is not None else None

    def list_outcomes(
        self,
        *,
        run_id: str | None = None,
        decision_trace_id: str | None = None,
        status: OutcomeStatus | str | None = None,
    ) -> list[OutcomeRecord]:
        """List outcomes with optional filters."""

        clauses: list[str] = []
        params: list[str] = []
        if run_id is not None:
            clauses.append("run_id = ?")
            params.append(run_id)
        if decision_trace_id is not None:
            clauses.append("decision_trace_id = ?")
            params.append(decision_trace_id)
        if status is not None:
            clauses.append("status = ?")
            params.append(status.value if isinstance(status, OutcomeStatus) else status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM outcomes
                {where}
                ORDER BY observed_at, id
                """,
                params,
            ).fetchall()
        return [_outcome_from_row(row) for row in rows]

    def list_outcomes_by_run(self, run_id: str) -> list[OutcomeRecord]:
        """List outcomes for one run."""

        return self.list_outcomes(run_id=run_id)

    def list_outcomes_by_decision_trace(self, decision_trace_id: str) -> list[OutcomeRecord]:
        """List outcomes for one decision trace."""

        return self.list_outcomes(decision_trace_id=decision_trace_id)

    def save_reflection(self, reflection: ReflectionRecord) -> ReflectionRecord:
        """Persist a reflection."""

        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO reflections (
                    id, outcome_id, run_id, decision_trace_id, what_worked, what_failed,
                    likely_cause, recommended_change, confidence, tags_json, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    reflection.id,
                    reflection.outcome_id,
                    reflection.run_id,
                    reflection.decision_trace_id,
                    reflection.what_worked,
                    reflection.what_failed,
                    reflection.likely_cause,
                    reflection.recommended_change,
                    reflection.confidence,
                    _json_dumps(reflection.tags),
                    _json_dumps(reflection.model_dump(mode="json")),
                ),
            )
        return reflection

    def list_reflections(
        self,
        *,
        run_id: str | None = None,
        outcome_id: str | None = None,
        decision_trace_id: str | None = None,
    ) -> list[ReflectionRecord]:
        """List reflections with optional filters."""

        clauses: list[str] = []
        params: list[str] = []
        if run_id is not None:
            clauses.append("run_id = ?")
            params.append(run_id)
        if outcome_id is not None:
            clauses.append("outcome_id = ?")
            params.append(outcome_id)
        if decision_trace_id is not None:
            clauses.append("decision_trace_id = ?")
            params.append(decision_trace_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM reflections
                {where}
                ORDER BY id
                """,
                params,
            ).fetchall()
        return [_reflection_from_row(row) for row in rows]

    def save_learning_signal(self, signal: LearningSignal) -> LearningSignal:
        """Persist a learning signal."""

        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO learning_signals (
                    id, run_id, decision_trace_id, outcome_id, signal_type, direction,
                    target, rationale, strength, confidence, status, tags_json, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    signal.id,
                    signal.run_id,
                    signal.decision_trace_id,
                    signal.outcome_id,
                    signal.signal_type.value,
                    signal.direction.value,
                    signal.target,
                    signal.rationale,
                    signal.strength,
                    signal.confidence,
                    signal.status.value,
                    _json_dumps(signal.tags),
                    _json_dumps(signal.model_dump(mode="json")),
                ),
            )
        return signal

    def list_learning_signals(
        self,
        *,
        run_id: str | None = None,
        outcome_id: str | None = None,
        signal_type: LearningSignalType | str | None = None,
        status: LearningSignalStatus | str | None = None,
    ) -> list[LearningSignal]:
        """List learning signals."""

        clauses: list[str] = []
        params: list[str] = []
        if run_id is not None:
            clauses.append("run_id = ?")
            params.append(run_id)
        if outcome_id is not None:
            clauses.append("outcome_id = ?")
            params.append(outcome_id)
        if signal_type is not None:
            clauses.append("signal_type = ?")
            params.append(signal_type.value if isinstance(signal_type, LearningSignalType) else signal_type)
        if status is not None:
            clauses.append("status = ?")
            params.append(status.value if isinstance(status, LearningSignalStatus) else status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM learning_signals
                {where}
                ORDER BY id
                """,
                params,
            ).fetchall()
        return [_learning_signal_from_row(row) for row in rows]

    def save_failure_memory_draft(self, draft: FailureMemoryDraft) -> FailureMemoryDraft:
        """Persist a failure memory draft and link it to its decision trace."""

        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO failure_memory_drafts (
                    id, run_id, decision_trace_id, outcome_id, memory_type, summary,
                    content, tags_json, confidence, severity, suggested_memory_importance,
                    raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    draft.id,
                    draft.run_id,
                    draft.decision_trace_id,
                    draft.outcome_id,
                    draft.memory_type,
                    draft.summary,
                    draft.content,
                    _json_dumps(draft.tags),
                    draft.confidence,
                    draft.severity,
                    draft.suggested_memory_importance,
                    _json_dumps(draft.model_dump(mode="json")),
                ),
            )
        self.link_decision_trace(draft.decision_trace_id, failure_memory_id=draft.id)
        return draft

    def get_failure_memory_draft(self, draft_id: str) -> FailureMemoryDraft | None:
        """Read one failure memory draft by ID."""

        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM failure_memory_drafts WHERE id = ?",
                (draft_id,),
            ).fetchone()
        return _failure_memory_draft_from_row(row) if row is not None else None

    def list_failure_memory_drafts(
        self,
        *,
        run_id: str | None = None,
        outcome_id: str | None = None,
    ) -> list[FailureMemoryDraft]:
        """List failure memory drafts."""

        clauses: list[str] = []
        params: list[str] = []
        if run_id is not None:
            clauses.append("run_id = ?")
            params.append(run_id)
        if outcome_id is not None:
            clauses.append("outcome_id = ?")
            params.append(outcome_id)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM failure_memory_drafts
                {where}
                ORDER BY id
                """,
                params,
            ).fetchall()
        return [_failure_memory_draft_from_row(row) for row in rows]

    def save_policy_update_suggestion(
        self,
        suggestion: PolicyUpdateSuggestion,
    ) -> PolicyUpdateSuggestion:
        """Persist a policy update suggestion and link it to its decision trace."""

        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO policy_update_suggestions (
                    id, run_id, decision_trace_id, outcome_id, policy_area,
                    current_rule, suggested_rule, rationale, confidence, status,
                    tags_json, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    suggestion.id,
                    suggestion.run_id,
                    suggestion.decision_trace_id,
                    suggestion.outcome_id,
                    suggestion.policy_area.value,
                    suggestion.current_rule,
                    suggestion.suggested_rule,
                    suggestion.rationale,
                    suggestion.confidence,
                    suggestion.status.value,
                    _json_dumps(suggestion.tags),
                    _json_dumps(suggestion.model_dump(mode="json")),
                ),
            )
        self.link_decision_trace(suggestion.decision_trace_id, policy_update_id=suggestion.id)
        return suggestion

    def list_policy_update_suggestions(
        self,
        *,
        run_id: str | None = None,
        outcome_id: str | None = None,
        policy_area: PolicyArea | str | None = None,
        status: LearningSignalStatus | str | None = None,
    ) -> list[PolicyUpdateSuggestion]:
        """List policy update suggestions."""

        clauses: list[str] = []
        params: list[str] = []
        if run_id is not None:
            clauses.append("run_id = ?")
            params.append(run_id)
        if outcome_id is not None:
            clauses.append("outcome_id = ?")
            params.append(outcome_id)
        if policy_area is not None:
            clauses.append("policy_area = ?")
            params.append(policy_area.value if isinstance(policy_area, PolicyArea) else policy_area)
        if status is not None:
            clauses.append("status = ?")
            params.append(status.value if isinstance(status, LearningSignalStatus) else status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM policy_update_suggestions
                {where}
                ORDER BY id
                """,
                params,
            ).fetchall()
        return [_policy_update_suggestion_from_row(row) for row in rows]

    def link_decision_trace(
        self,
        decision_trace_id: str,
        *,
        outcome_id: str | None = None,
        failure_memory_id: str | None = None,
        policy_update_id: str | None = None,
    ) -> None:
        """Update a decision trace's learning links and raw JSON copy."""

        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT outcome_id, failure_memory_id, policy_update_id, raw_json
                FROM decision_traces
                WHERE id = ?
                """,
                (decision_trace_id,),
            ).fetchone()
            if row is None:
                return
            linked_outcome_id = outcome_id if outcome_id is not None else _row_optional_str(row, "outcome_id")
            linked_failure_memory_id = (
                failure_memory_id
                if failure_memory_id is not None
                else _row_optional_str(row, "failure_memory_id")
            )
            linked_policy_update_id = (
                policy_update_id
                if policy_update_id is not None
                else _row_optional_str(row, "policy_update_id")
            )
            raw = _json_loads_dict(_row_optional_str(row, "raw_json") or "{}")
            raw["outcome_id"] = linked_outcome_id
            raw["failure_memory_id"] = linked_failure_memory_id
            raw["policy_update_id"] = linked_policy_update_id
            connection.execute(
                """
                UPDATE decision_traces
                SET outcome_id = ?,
                    failure_memory_id = ?,
                    policy_update_id = ?,
                    raw_json = ?
                WHERE id = ?
                """,
                (
                    linked_outcome_id,
                    linked_failure_memory_id,
                    linked_policy_update_id,
                    _json_dumps(raw),
                    decision_trace_id,
                ),
            )


def _outcome_from_row(row: sqlite3.Row) -> OutcomeRecord:
    raw = _json_loads_dict(_row_optional_str(row, "raw_json") or "{}")
    if raw:
        return OutcomeRecord.model_validate(raw)
    return OutcomeRecord(
        id=_row_str(row, "id"),
        run_id=_row_str(row, "run_id"),
        decision_trace_id=_row_str(row, "decision_trace_id"),
        status=OutcomeStatus(_row_str(row, "status")),
        observed_at=_datetime_from_text(_row_str(row, "observed_at")),
        summary=_row_str(row, "summary"),
        metrics=_json_loads(_row_str(row, "metrics_json")),
        evidence=_json_loads(_row_str(row, "evidence_json")),
        severity=_row_float(row, "severity"),
        confidence=_row_float(row, "confidence"),
        tags=_json_loads_list(_row_str(row, "tags_json")),
    )


def _reflection_from_row(row: sqlite3.Row) -> ReflectionRecord:
    raw = _json_loads_dict(_row_optional_str(row, "raw_json") or "{}")
    if raw:
        return ReflectionRecord.model_validate(raw)
    return ReflectionRecord(
        id=_row_str(row, "id"),
        outcome_id=_row_str(row, "outcome_id"),
        run_id=_row_str(row, "run_id"),
        decision_trace_id=_row_str(row, "decision_trace_id"),
        what_worked=_row_str(row, "what_worked"),
        what_failed=_row_str(row, "what_failed"),
        likely_cause=_row_str(row, "likely_cause"),
        recommended_change=_row_str(row, "recommended_change"),
        confidence=_row_float(row, "confidence"),
        tags=_json_loads_list(_row_str(row, "tags_json")),
    )


def _learning_signal_from_row(row: sqlite3.Row) -> LearningSignal:
    raw = _json_loads_dict(_row_optional_str(row, "raw_json") or "{}")
    if raw:
        return LearningSignal.model_validate(raw)
    return LearningSignal(
        id=_row_str(row, "id"),
        run_id=_row_str(row, "run_id"),
        decision_trace_id=_row_str(row, "decision_trace_id"),
        outcome_id=_row_str(row, "outcome_id"),
        signal_type=LearningSignalType(_row_str(row, "signal_type")),
        direction=LearningDirection(_row_str(row, "direction")),
        target=_row_str(row, "target"),
        rationale=_row_str(row, "rationale"),
        strength=_row_float(row, "strength"),
        confidence=_row_float(row, "confidence"),
        status=LearningSignalStatus(_row_str(row, "status")),
        tags=_json_loads_list(_row_str(row, "tags_json")),
    )


def _failure_memory_draft_from_row(row: sqlite3.Row) -> FailureMemoryDraft:
    raw = _json_loads_dict(_row_optional_str(row, "raw_json") or "{}")
    if raw:
        return FailureMemoryDraft.model_validate(raw)
    return FailureMemoryDraft(
        id=_row_str(row, "id"),
        run_id=_row_str(row, "run_id"),
        decision_trace_id=_row_str(row, "decision_trace_id"),
        outcome_id=_row_str(row, "outcome_id"),
        summary=_row_str(row, "summary"),
        content=_row_str(row, "content"),
        tags=_json_loads_list(_row_str(row, "tags_json")),
        confidence=_row_float(row, "confidence"),
        severity=_row_float(row, "severity"),
        suggested_memory_importance=_row_float(row, "suggested_memory_importance"),
    )


def _policy_update_suggestion_from_row(row: sqlite3.Row) -> PolicyUpdateSuggestion:
    raw = _json_loads_dict(_row_optional_str(row, "raw_json") or "{}")
    if raw:
        return PolicyUpdateSuggestion.model_validate(raw)
    return PolicyUpdateSuggestion(
        id=_row_str(row, "id"),
        run_id=_row_str(row, "run_id"),
        decision_trace_id=_row_str(row, "decision_trace_id"),
        outcome_id=_row_str(row, "outcome_id"),
        policy_area=PolicyArea(_row_str(row, "policy_area")),
        current_rule=_row_str(row, "current_rule"),
        suggested_rule=_row_str(row, "suggested_rule"),
        rationale=_row_str(row, "rationale"),
        confidence=_row_float(row, "confidence"),
        status=LearningSignalStatus(_row_str(row, "status")),
        tags=_json_loads_list(_row_str(row, "tags_json")),
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


def _row_float(row: sqlite3.Row, key: str) -> float:
    return float(cast(int | float, row[key]))
