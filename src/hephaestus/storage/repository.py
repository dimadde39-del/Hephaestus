"""Repository abstractions for SQLite persistence."""

from __future__ import annotations

import builtins
import json
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from hephaestus.core.config import RiskLevel
from hephaestus.memory.schemas import MemoryItem, MemoryType
from hephaestus.memory.store import score_memory
from hephaestus.safety.approval import ApprovalStatus
from hephaestus.storage.sqlite import connect_database, init_database


class RunRecord(BaseModel):
    """A persisted CLI optimization or planning run."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"run_{uuid4().hex[:12]}")
    goal: str
    mode: str
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    status: str = "running"
    estimated_input_tokens: int = Field(default=0, ge=0)
    estimated_output_tokens: int = Field(default=0, ge=0)
    estimated_cost: float = Field(default=0.0, ge=0)
    objective_score: float = 0.0
    risk_score: float = Field(default=0.0, ge=0)
    summary: str = ""


class RunTaskRecord(BaseModel):
    """A task persisted as part of a run."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"run_task_{uuid4().hex[:12]}")
    run_id: str
    task_id: str
    title: str
    description: str
    selected_order: int = Field(ge=1)
    priority: int = Field(ge=0)
    risk: float = Field(ge=0)
    expected_value: float = Field(ge=0)
    dependencies: list[str] = Field(default_factory=list)
    required_capabilities: list[str] = Field(default_factory=list)
    requires_approval: bool = False


class RunDecisionRecord(BaseModel):
    """An optimizer, router, or budget decision persisted for a run."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"decision_{uuid4().hex[:12]}")
    run_id: str
    decision_type: str
    selected_option: str
    rejected_options: list[str] = Field(default_factory=list)
    objective_score: float | None = None
    estimated_cost: float | None = None
    rationale: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ApprovalRecord(BaseModel):
    """An approval-required action captured during a run."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"approval_{uuid4().hex[:12]}")
    run_id: str
    action_type: str
    action_description: str
    risk_level: RiskLevel
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    resolved_at: datetime | None = None


class RunDetail(BaseModel):
    """A run plus its child records."""

    run: RunRecord
    tasks: list[RunTaskRecord] = Field(default_factory=list)
    decisions: list[RunDecisionRecord] = Field(default_factory=list)
    approvals: list[ApprovalRecord] = Field(default_factory=list)


class SqliteMemoryRepository:
    """SQLite-backed memory repository with Phase 1 lexical scoring."""

    def __init__(self, database_path: Path | str | None = None) -> None:
        self.database_path = init_database(database_path)

    def add(self, item: MemoryItem) -> MemoryItem:
        """Persist a memory item."""

        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO memories (
                    id, type, content, summary, tags, project, confidence, importance,
                    created_at, last_verified_at, source
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item.id,
                    item.type.value,
                    item.content,
                    item.summary,
                    _json_dumps(item.tags),
                    item.project,
                    item.confidence,
                    item.importance,
                    _datetime_to_text(item.created_at),
                    _optional_datetime_to_text(item.last_verified_at),
                    item.source,
                ),
            )
        return item

    def list(self, project: str | None = None) -> builtins.list[MemoryItem]:
        """List memories in creation order."""

        with connect_database(self.database_path) as connection:
            if project is None:
                rows = connection.execute(
                    "SELECT * FROM memories ORDER BY created_at"
                ).fetchall()
            else:
                rows = connection.execute(
                    "SELECT * FROM memories WHERE project = ? ORDER BY created_at",
                    (project,),
                ).fetchall()
        return [_memory_from_row(row) for row in rows]

    def search(
        self,
        query: str = "",
        *,
        tags: Iterable[str] | None = None,
        project: str | None = None,
    ) -> builtins.list[MemoryItem]:
        """Search memories with the same lexical filter as Phase 1."""

        query_terms = _terms(query)
        required_tags = {tag.lower() for tag in tags or []}
        matches: builtins.list[MemoryItem] = []
        for item in self.list(project=project):
            if required_tags and not required_tags.issubset(set(item.tags)):
                continue
            text = item.searchable_text
            if query_terms and not all(term in text for term in query_terms):
                continue
            matches.append(item)
        return matches

    def retrieve_top(
        self,
        query: str,
        *,
        limit: int = 5,
        tags: Iterable[str] | None = None,
        project: str | None = None,
    ) -> builtins.list[MemoryItem]:
        """Rank memories using the existing confidence/importance scoring."""

        candidates = self.search("", tags=tags, project=project)
        scored = [(score_memory(item, query), item) for item in candidates]
        ranked = sorted(scored, key=lambda pair: pair[0], reverse=True)
        return [item for score, item in ranked[:limit] if score > 0]


class RunRepository:
    """Repository for run history and optimizer decisions."""

    def __init__(self, database_path: Path | str | None = None) -> None:
        self.database_path = init_database(database_path)

    def save_run(self, run: RunRecord) -> RunRecord:
        """Insert or replace a run."""

        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO runs (
                    id, goal, mode, started_at, completed_at, status,
                    estimated_input_tokens, estimated_output_tokens, estimated_cost,
                    objective_score, risk_score, summary
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _run_values(run),
            )
        return run

    def complete_run(
        self,
        run_id: str,
        *,
        estimated_input_tokens: int,
        estimated_output_tokens: int,
        estimated_cost: float,
        objective_score: float,
        risk_score: float,
        summary: str,
        status: str = "completed",
        completed_at: datetime | None = None,
    ) -> None:
        """Mark a run complete and store its final aggregate metrics."""

        completed = completed_at or datetime.now(UTC)
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                UPDATE runs
                SET completed_at = ?,
                    status = ?,
                    estimated_input_tokens = ?,
                    estimated_output_tokens = ?,
                    estimated_cost = ?,
                    objective_score = ?,
                    risk_score = ?,
                    summary = ?
                WHERE id = ?
                """,
                (
                    _datetime_to_text(completed),
                    status,
                    estimated_input_tokens,
                    estimated_output_tokens,
                    estimated_cost,
                    objective_score,
                    risk_score,
                    summary,
                    run_id,
                ),
            )

    def save_run_task(self, task: RunTaskRecord) -> RunTaskRecord:
        """Persist a task associated with a run."""

        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO run_tasks (
                    id, run_id, task_id, title, description, selected_order, priority, risk,
                    expected_value, dependencies, required_capabilities, requires_approval
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task.id,
                    task.run_id,
                    task.task_id,
                    task.title,
                    task.description,
                    task.selected_order,
                    task.priority,
                    task.risk,
                    task.expected_value,
                    _json_dumps(task.dependencies),
                    _json_dumps(task.required_capabilities),
                    int(task.requires_approval),
                ),
            )
        return task

    def save_run_tasks(self, tasks: Iterable[RunTaskRecord]) -> list[RunTaskRecord]:
        """Persist several run tasks."""

        saved: list[RunTaskRecord] = []
        for task in tasks:
            saved.append(self.save_run_task(task))
        return saved

    def save_decision(self, decision: RunDecisionRecord) -> RunDecisionRecord:
        """Persist an optimizer/router decision."""

        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO run_decisions (
                    id, run_id, decision_type, selected_option, rejected_options,
                    objective_score, estimated_cost, rationale, created_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    decision.id,
                    decision.run_id,
                    decision.decision_type,
                    decision.selected_option,
                    _json_dumps(decision.rejected_options),
                    decision.objective_score,
                    decision.estimated_cost,
                    decision.rationale,
                    _datetime_to_text(decision.created_at),
                ),
            )
        return decision

    def save_approval(self, approval: ApprovalRecord) -> ApprovalRecord:
        """Persist an approval-required action."""

        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO approvals (
                    id, run_id, action_type, action_description, risk_level, status,
                    created_at, resolved_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    approval.id,
                    approval.run_id,
                    approval.action_type,
                    approval.action_description,
                    approval.risk_level.value,
                    approval.status.value,
                    _datetime_to_text(approval.created_at),
                    _optional_datetime_to_text(approval.resolved_at),
                ),
            )
        return approval

    def list_recent_runs(self, limit: int = 10) -> list[RunRecord]:
        """List recent runs newest-first."""

        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                "SELECT * FROM runs ORDER BY started_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_run_from_row(row) for row in rows]

    def get_run(self, run_id: str) -> RunDetail | None:
        """Read a run and its child records by ID."""

        with connect_database(self.database_path) as connection:
            run_row = connection.execute(
                "SELECT * FROM runs WHERE id = ?",
                (run_id,),
            ).fetchone()
            if run_row is None:
                return None
            task_rows = connection.execute(
                "SELECT * FROM run_tasks WHERE run_id = ? ORDER BY selected_order",
                (run_id,),
            ).fetchall()
            decision_rows = connection.execute(
                "SELECT * FROM run_decisions WHERE run_id = ? ORDER BY created_at",
                (run_id,),
            ).fetchall()
            approval_rows = connection.execute(
                "SELECT * FROM approvals WHERE run_id = ? ORDER BY created_at",
                (run_id,),
            ).fetchall()
        return RunDetail(
            run=_run_from_row(run_row),
            tasks=[_run_task_from_row(row) for row in task_rows],
            decisions=[_decision_from_row(row) for row in decision_rows],
            approvals=[_approval_from_row(row) for row in approval_rows],
        )


def _run_values(run: RunRecord) -> tuple[Any, ...]:
    return (
        run.id,
        run.goal,
        run.mode,
        _datetime_to_text(run.started_at),
        _optional_datetime_to_text(run.completed_at),
        run.status,
        run.estimated_input_tokens,
        run.estimated_output_tokens,
        run.estimated_cost,
        run.objective_score,
        run.risk_score,
        run.summary,
    )


def _memory_from_row(row: sqlite3.Row) -> MemoryItem:
    return MemoryItem(
        id=_row_str(row, "id"),
        type=MemoryType(_row_str(row, "type")),
        content=_row_str(row, "content"),
        summary=_row_str(row, "summary"),
        tags=_json_loads_list(_row_str(row, "tags")),
        project=_row_str(row, "project"),
        confidence=_row_float(row, "confidence"),
        importance=_row_float(row, "importance"),
        created_at=_datetime_from_text(_row_str(row, "created_at")),
        last_verified_at=_optional_datetime_from_text(_row_optional_str(row, "last_verified_at")),
        source=_row_str(row, "source"),
    )


def _run_from_row(row: sqlite3.Row) -> RunRecord:
    return RunRecord(
        id=_row_str(row, "id"),
        goal=_row_str(row, "goal"),
        mode=_row_str(row, "mode"),
        started_at=_datetime_from_text(_row_str(row, "started_at")),
        completed_at=_optional_datetime_from_text(_row_optional_str(row, "completed_at")),
        status=_row_str(row, "status"),
        estimated_input_tokens=_row_int(row, "estimated_input_tokens"),
        estimated_output_tokens=_row_int(row, "estimated_output_tokens"),
        estimated_cost=_row_float(row, "estimated_cost"),
        objective_score=_row_float(row, "objective_score"),
        risk_score=_row_float(row, "risk_score"),
        summary=_row_str(row, "summary"),
    )


def _run_task_from_row(row: sqlite3.Row) -> RunTaskRecord:
    return RunTaskRecord(
        id=_row_str(row, "id"),
        run_id=_row_str(row, "run_id"),
        task_id=_row_str(row, "task_id"),
        title=_row_str(row, "title"),
        description=_row_str(row, "description"),
        selected_order=_row_int(row, "selected_order"),
        priority=_row_int(row, "priority"),
        risk=_row_float(row, "risk"),
        expected_value=_row_float(row, "expected_value"),
        dependencies=_json_loads_list(_row_str(row, "dependencies")),
        required_capabilities=_json_loads_list(_row_str(row, "required_capabilities")),
        requires_approval=bool(_row_int(row, "requires_approval")),
    )


def _decision_from_row(row: sqlite3.Row) -> RunDecisionRecord:
    return RunDecisionRecord(
        id=_row_str(row, "id"),
        run_id=_row_str(row, "run_id"),
        decision_type=_row_str(row, "decision_type"),
        selected_option=_row_str(row, "selected_option"),
        rejected_options=_json_loads_list(_row_str(row, "rejected_options")),
        objective_score=_row_optional_float(row, "objective_score"),
        estimated_cost=_row_optional_float(row, "estimated_cost"),
        rationale=_row_str(row, "rationale"),
        created_at=_datetime_from_text(_row_str(row, "created_at")),
    )


def _approval_from_row(row: sqlite3.Row) -> ApprovalRecord:
    return ApprovalRecord(
        id=_row_str(row, "id"),
        run_id=_row_str(row, "run_id"),
        action_type=_row_str(row, "action_type"),
        action_description=_row_str(row, "action_description"),
        risk_level=RiskLevel(_row_str(row, "risk_level")),
        status=ApprovalStatus(_row_str(row, "status")),
        created_at=_datetime_from_text(_row_str(row, "created_at")),
        resolved_at=_optional_datetime_from_text(_row_optional_str(row, "resolved_at")),
    )


def _datetime_to_text(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _optional_datetime_to_text(value: datetime | None) -> str | None:
    return _datetime_to_text(value) if value is not None else None


def _datetime_from_text(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _optional_datetime_from_text(value: str | None) -> datetime | None:
    return _datetime_from_text(value) if value is not None else None


def _json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _json_loads_list(value: str) -> list[str]:
    loaded = json.loads(value)
    if not isinstance(loaded, list):
        raise ValueError("Expected JSON list")
    return [str(item) for item in loaded]


def _terms(query: str) -> list[str]:
    return [part.lower() for part in query.split() if part.strip()]


def _row_str(row: sqlite3.Row, key: str) -> str:
    return cast(str, row[key])


def _row_optional_str(row: sqlite3.Row, key: str) -> str | None:
    return cast(str | None, row[key])


def _row_int(row: sqlite3.Row, key: str) -> int:
    return cast(int, row[key])


def _row_float(row: sqlite3.Row, key: str) -> float:
    return float(cast(int | float, row[key]))


def _row_optional_float(row: sqlite3.Row, key: str) -> float | None:
    value = cast(int | float | None, row[key])
    return float(value) if value is not None else None
