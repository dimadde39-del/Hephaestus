"""SQLite repository for rich decision traces."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from hephaestus.decision.schemas import (
    DecisionAlternative,
    DecisionMetric,
    DecisionTraceNode,
    DecisionTraceVariant,
    DecisionType,
    MetricValue,
    parse_decision_trace,
)
from hephaestus.storage.sqlite import connect_database, init_database


class DecisionTraceRepository:
    """Persist and reconstruct rich Phase 3A decision traces."""

    def __init__(self, database_path: Path | str | None = None) -> None:
        self.database_path = init_database(database_path)

    def save_trace(self, trace: DecisionTraceVariant) -> DecisionTraceVariant:
        """Insert or replace a decision trace."""

        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO decision_traces (
                    id, run_id, parent_id, decision_type, phase, timestamp,
                    selected_option, rationale, objective_score, confidence,
                    alternatives_json, metrics_json, constraints_json, tags_json,
                    caused_by_json, will_affect_json, learning_hooks_json, outcome_id,
                    failure_memory_id, policy_update_id, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _trace_values(trace),
            )
        return trace

    def save_traces(
        self,
        traces: Iterable[DecisionTraceVariant],
    ) -> list[DecisionTraceVariant]:
        """Persist several decision traces."""

        saved: list[DecisionTraceVariant] = []
        for trace in traces:
            saved.append(self.save_trace(trace))
        return saved

    def get_trace(self, trace_id: str) -> DecisionTraceVariant | None:
        """Read one decision trace by ID."""

        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM decision_traces WHERE id = ?",
                (trace_id,),
            ).fetchone()
        return _trace_from_row(row) if row is not None else None

    def list_traces(
        self,
        *,
        run_id: str | None = None,
        decision_type: DecisionType | str | None = None,
    ) -> list[DecisionTraceVariant]:
        """List traces, optionally filtered by run and decision type."""

        clauses: list[str] = []
        params: list[str] = []
        if run_id is not None:
            clauses.append("run_id = ?")
            params.append(run_id)
        if decision_type is not None:
            clauses.append("decision_type = ?")
            params.append(_decision_type_value(decision_type))
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT * FROM decision_traces
                {where}
                ORDER BY timestamp, id
                """,
                params,
            ).fetchall()
        return [_trace_from_row(row) for row in rows]

    def list_traces_by_run(self, run_id: str) -> list[DecisionTraceVariant]:
        """List all decision traces for one run."""

        return self.list_traces(run_id=run_id)

    def list_traces_by_type(
        self,
        decision_type: DecisionType | str,
    ) -> list[DecisionTraceVariant]:
        """List all decision traces of one type."""

        return self.list_traces(decision_type=decision_type)

    def aggregate_traces(self) -> object:
        """Aggregate all persisted traces into decision stats."""

        from hephaestus.decision.analysis import aggregate_decision_stats

        return aggregate_decision_stats(self.list_traces())

    def get_trace_tree(self, run_id: str) -> list[DecisionTraceNode]:
        """Reconstruct parent/child trace trees for one run."""

        traces = self.list_traces(run_id=run_id)
        nodes = {trace.id: DecisionTraceNode(decision=trace) for trace in traces}
        roots: list[DecisionTraceNode] = []
        for trace in traces:
            node = nodes[trace.id]
            if trace.parent_id is None or trace.parent_id not in nodes:
                roots.append(node)
                continue
            nodes[trace.parent_id].children.append(node)
        return roots


def _trace_values(trace: DecisionTraceVariant) -> tuple[Any, ...]:
    raw = trace.model_dump(mode="json")
    return (
        trace.id,
        trace.run_id,
        trace.parent_id,
        trace.decision_type.value,
        trace.phase,
        _datetime_to_text(trace.timestamp),
        trace.selected_option,
        trace.rationale,
        trace.objective_score,
        trace.confidence,
        _json_dumps(raw["alternatives"]),
        _json_dumps(raw["metrics"]),
        _json_dumps(trace.constraints_considered),
        _json_dumps(trace.tags),
        _json_dumps(trace.caused_by),
        _json_dumps(trace.will_affect),
        _json_dumps(trace.learning_hooks),
        trace.outcome_id,
        trace.failure_memory_id,
        trace.policy_update_id,
        _json_dumps(raw),
    )


def _trace_from_row(row: sqlite3.Row) -> DecisionTraceVariant:
    raw_json = _row_optional_str(row, "raw_json")
    if raw_json and raw_json != "{}":
        raw = json.loads(raw_json)
        if isinstance(raw, dict) and raw:
            raw["outcome_id"] = _row_optional_str(row, "outcome_id")
            raw["failure_memory_id"] = _row_optional_str(row, "failure_memory_id")
            raw["policy_update_id"] = _row_optional_str(row, "policy_update_id")
            return parse_decision_trace(cast(dict[str, object], raw))
    return parse_decision_trace(
        {
            "id": _row_str(row, "id"),
            "run_id": _row_str(row, "run_id"),
            "parent_id": _row_optional_str(row, "parent_id"),
            "decision_type": _row_str(row, "decision_type"),
            "timestamp": _datetime_from_text(_row_str(row, "timestamp")),
            "phase": _row_optional_str(row, "phase") or "runtime",
            "selected_option": _row_str(row, "selected_option"),
            "alternatives": _json_loads_alternatives(_row_json_text(row, "alternatives_json")),
            "rationale": _row_str(row, "rationale"),
            "metrics": _json_loads_metrics(_row_json_text(row, "metrics_json")),
            "objective_score": _row_optional_float(row, "objective_score"),
            "confidence": _row_float(row, "confidence"),
            "constraints_considered": _json_loads_list(_row_json_text(row, "constraints_json")),
            "tags": _json_loads_list(_row_json_text(row, "tags_json")),
            "caused_by": _json_loads_list(_row_json_text(row, "caused_by_json")),
            "will_affect": _json_loads_list(_row_json_text(row, "will_affect_json")),
            "learning_hooks": _json_loads_list(_row_json_text(row, "learning_hooks_json")),
            "outcome_id": _row_optional_str(row, "outcome_id"),
            "failure_memory_id": _row_optional_str(row, "failure_memory_id"),
            "policy_update_id": _row_optional_str(row, "policy_update_id"),
        }
    )


def _decision_type_value(value: DecisionType | str) -> str:
    if isinstance(value, DecisionType):
        return value.value
    return value


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


def _json_loads_list(value: str) -> list[str]:
    loaded = json.loads(value)
    if not isinstance(loaded, list):
        raise ValueError("Expected JSON list")
    return [str(item) for item in loaded]


def _json_loads_alternatives(value: str) -> list[DecisionAlternative]:
    loaded = json.loads(value)
    if not isinstance(loaded, list):
        raise ValueError("Expected JSON list")
    alternatives: list[DecisionAlternative] = []
    for item in loaded:
        if isinstance(item, dict):
            alternatives.append(DecisionAlternative.model_validate(item))
        else:
            alternatives.append(_legacy_alternative(str(item)))
    return alternatives


def _json_loads_metrics(value: str) -> list[DecisionMetric]:
    loaded = json.loads(value)
    if isinstance(loaded, list):
        return [
            DecisionMetric.model_validate(item)
            if isinstance(item, dict)
            else DecisionMetric(name=str(index), value=_metric_value(item))
            for index, item in enumerate(loaded)
        ]
    if isinstance(loaded, dict):
        return [
            DecisionMetric(name=str(key), value=_metric_value(metric_value))
            for key, metric_value in loaded.items()
        ]
    raise ValueError("Expected JSON list or object")


def _legacy_alternative(value: str) -> DecisionAlternative:
    if ":" in value:
        option_id, reason = value.split(":", 1)
        return DecisionAlternative(
            option_id=option_id.strip(),
            rejection_reason=reason.strip(),
        )
    return DecisionAlternative(option_id=value.strip(), rejection_reason=value.strip())


def _metric_value(value: object) -> MetricValue:
    if value is None or isinstance(value, bool | int | float | str):
        return value
    return str(value)


def _row_json_text(row: sqlite3.Row, key: str) -> str:
    value = _row_optional_str(row, key)
    if value is not None:
        return value
    return "[]"


def _row_str(row: sqlite3.Row, key: str) -> str:
    return cast(str, row[key])


def _row_optional_str(row: sqlite3.Row, key: str) -> str | None:
    try:
        return cast(str | None, row[key])
    except (IndexError, KeyError):
        return None


def _row_float(row: sqlite3.Row, key: str) -> float:
    return float(cast(int | float, row[key]))


def _row_optional_float(row: sqlite3.Row, key: str) -> float | None:
    value = cast(int | float | None, row[key])
    return float(value) if value is not None else None
