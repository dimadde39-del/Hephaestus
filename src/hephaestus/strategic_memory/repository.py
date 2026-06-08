"""SQLite persistence for strategic memory."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from hephaestus.storage.sqlite import connect_database, init_database
from hephaestus.strategic_memory.analysis import normalize_conflict_text
from hephaestus.strategic_memory.schemas import (
    StrategicMemoryConflict,
    StrategicMemoryItem,
    StrategicMemoryRecall,
    StrategicMemoryScope,
    StrategicMemoryType,
)


class StrategicMemoryRepository:
    """SQLite-backed strategic memory repository."""

    def __init__(self, database_path: Path | str | None = None) -> None:
        self.database_path = init_database(database_path)

    def save_memory(self, item: StrategicMemoryItem) -> StrategicMemoryItem:
        """Persist a strategic memory and record simple detected conflicts."""

        now = datetime.now(UTC)
        item_to_save = item.model_copy(update={"updated_at": item.updated_at or now})
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO strategic_memories (
                    id, type, scope, project, repo_profile_id, conversation_id,
                    content, summary, evidence_json, confidence, importance,
                    stability, source, tags_json, created_at, updated_at,
                    archived_at, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _memory_values(item_to_save),
            )
        for conflict in self.detect_simple_conflicts(item_to_save):
            self.save_conflict(conflict)
        return item_to_save

    def get_memory(self, memory_id: str) -> StrategicMemoryItem | None:
        """Read one strategic memory."""

        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT raw_json FROM strategic_memories WHERE id = ?",
                (memory_id,),
            ).fetchone()
        if row is None:
            return None
        return StrategicMemoryItem.model_validate_json(_row_str(row, "raw_json"))

    def list_memories(
        self,
        *,
        project: str | None = None,
        type_: StrategicMemoryType | None = None,
        scope: StrategicMemoryScope | None = None,
        include_archived: bool = False,
    ) -> list[StrategicMemoryItem]:
        """List strategic memories with optional filters."""

        clauses: list[str] = []
        params: list[str] = []
        if project is not None:
            clauses.append("(project = ? OR scope = ?)")
            params.extend([project, StrategicMemoryScope.GLOBAL.value])
        if type_ is not None:
            clauses.append("type = ?")
            params.append(type_.value)
        if scope is not None:
            clauses.append("scope = ?")
            params.append(scope.value)
        if not include_archived:
            clauses.append("archived_at IS NULL")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT raw_json FROM strategic_memories
                {where}
                ORDER BY importance DESC, updated_at DESC, id
                """,
                params,
            ).fetchall()
        return [StrategicMemoryItem.model_validate_json(_row_str(row, "raw_json")) for row in rows]

    def search_memories(
        self,
        query: str,
        *,
        tags: Iterable[str] | None = None,
        types: Iterable[StrategicMemoryType] | None = None,
        scopes: Iterable[StrategicMemoryScope] | None = None,
        project: str | None = None,
        repo_profile_id: str | None = None,
        limit: int = 20,
        include_archived: bool = False,
    ) -> list[StrategicMemoryItem]:
        """Search strategic memories using deterministic lexical scoring."""

        required_tags = {tag.strip().lower() for tag in tags or [] if tag.strip()}
        required_types = set(types or [])
        required_scopes = set(scopes or [])
        query_terms = _terms(query)
        candidates = self.list_memories(project=project, include_archived=include_archived)
        matches: list[tuple[float, StrategicMemoryItem]] = []
        for memory in candidates:
            if required_types and memory.type not in required_types:
                continue
            if required_scopes and memory.scope not in required_scopes:
                continue
            if repo_profile_id is not None and memory.repo_profile_id not in {None, repo_profile_id}:
                continue
            if required_tags and not (required_tags & set(memory.tags)):
                continue
            if query_terms and not any(term in memory.searchable_text for term in query_terms):
                if required_tags or required_types:
                    score = _score_memory(memory, " ".join([*query_terms, *required_tags]))
                else:
                    continue
            else:
                score = _score_memory(memory, query)
            if score > 0:
                matches.append((score, memory))
        ranked = sorted(
            matches,
            key=lambda pair: (pair[0], pair[1].importance, pair[1].confidence),
            reverse=True,
        )
        return [memory for _, memory in ranked[:limit]]

    def archive_memory(self, memory_id: str) -> StrategicMemoryItem | None:
        """Soft-archive a strategic memory."""

        memory = self.get_memory(memory_id)
        if memory is None:
            return None
        archived = memory.model_copy(
            update={"archived_at": datetime.now(UTC), "updated_at": datetime.now(UTC)}
        )
        return self.save_memory(archived)

    def recall(
        self,
        *,
        query: str = "",
        tags: Iterable[str] | None = None,
        types: Iterable[StrategicMemoryType] | None = None,
        scopes: Iterable[StrategicMemoryScope] | None = None,
        project: str | None = None,
        repo_profile_id: str | None = None,
        limit: int = 8,
        metadata: dict[str, Any] | None = None,
    ) -> StrategicMemoryRecall:
        """Recall matching memories without requiring the caller to build a record."""

        type_list = list(types or [])
        scope_list = list(scopes or [])
        tag_list = list(tags or [])
        memories = self.search_memories(
            query,
            tags=tag_list,
            types=type_list,
            scopes=scope_list,
            project=project,
            repo_profile_id=repo_profile_id,
            limit=limit,
        )
        return StrategicMemoryRecall(
            query=query,
            tags=tag_list,
            types=type_list,
            scopes=scope_list,
            memory_ids=[memory.id for memory in memories],
            memories=memories,
            metadata=metadata or {},
        )

    def save_recall_event(self, recall: StrategicMemoryRecall) -> StrategicMemoryRecall:
        """Persist a recall event for auditability."""

        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO strategic_memory_recalls (
                    id, query, tags_json, types_json, scopes_json, selected_memory_ids_json,
                    created_at, metadata_json, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    recall.id,
                    recall.query,
                    _json_dumps(recall.tags),
                    _json_dumps([item.value for item in recall.types]),
                    _json_dumps([item.value for item in recall.scopes]),
                    _json_dumps(recall.memory_ids),
                    _datetime_to_text(recall.created_at),
                    _json_dumps(recall.metadata),
                    recall.model_dump_json(),
                ),
            )
        return recall

    def save_conflict(self, conflict: StrategicMemoryConflict) -> StrategicMemoryConflict:
        """Persist a strategic memory conflict."""

        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO strategic_memory_conflicts (
                    id, existing_memory_id, candidate_memory_id, conflict_type,
                    description, severity, status, created_at, resolved_at, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    conflict.id,
                    conflict.existing_memory_id,
                    conflict.candidate_memory_id,
                    conflict.conflict_type,
                    conflict.description,
                    conflict.severity,
                    conflict.status,
                    _datetime_to_text(conflict.created_at),
                    _optional_datetime_to_text(conflict.resolved_at),
                    conflict.model_dump_json(),
                ),
            )
        return conflict

    def list_conflicts(self, *, status: str | None = "open") -> list[StrategicMemoryConflict]:
        """List detected conflicts."""

        clauses: list[str] = []
        params: list[str] = []
        if status is not None:
            clauses.append("status = ?")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT raw_json FROM strategic_memory_conflicts
                {where}
                ORDER BY created_at DESC, id
                """,
                params,
            ).fetchall()
        return [
            StrategicMemoryConflict.model_validate_json(_row_str(row, "raw_json"))
            for row in rows
        ]

    def detect_simple_conflicts(
        self,
        candidate: StrategicMemoryItem,
    ) -> list[StrategicMemoryConflict]:
        """Detect basic contradictions against existing active memories."""

        conflicts: list[StrategicMemoryConflict] = []
        candidate_terms = normalize_conflict_text(candidate.content)
        candidate_negative = _has_negative_marker(candidate.content)
        candidate_positive = _has_positive_marker(candidate.content)
        for memory in self.list_memories(project=candidate.project):
            if memory.id == candidate.id or memory.archived_at is not None:
                continue
            if memory.type != candidate.type and not _related_decision_types(memory.type, candidate.type):
                continue
            overlap = candidate_terms & normalize_conflict_text(memory.content)
            if len(overlap) < 2:
                continue
            memory_negative = _has_negative_marker(memory.content)
            memory_positive = _has_positive_marker(memory.content)
            if (candidate_negative and memory_positive) or (candidate_positive and memory_negative):
                conflicts.append(
                    StrategicMemoryConflict(
                        existing_memory_id=memory.id,
                        candidate_memory_id=candidate.id,
                        description=(
                            "Potential conflict between strategic memories: "
                            f"'{memory.summary or memory.content}' vs "
                            f"'{candidate.summary or candidate.content}'."
                        ),
                        severity=0.65,
                    )
                )
        return conflicts


def _memory_values(item: StrategicMemoryItem) -> tuple[Any, ...]:
    raw = item.model_dump(mode="json")
    return (
        item.id,
        item.type.value,
        item.scope.value,
        item.project,
        item.repo_profile_id,
        item.conversation_id,
        item.content,
        item.summary,
        _json_dumps(raw["evidence"]),
        item.confidence,
        item.importance,
        item.stability.value,
        item.source.value,
        _json_dumps(item.tags),
        _datetime_to_text(item.created_at),
        _datetime_to_text(item.updated_at),
        _optional_datetime_to_text(item.archived_at),
        _json_dumps(raw),
    )


def _score_memory(item: StrategicMemoryItem, query: str) -> float:
    terms = _terms(query)
    score = item.importance * 1.25 + item.confidence * 0.75
    if not terms:
        return score
    text = item.searchable_text
    score += sum(1.4 for term in terms if term in text)
    score += sum(2.0 for term in terms if term in item.tags)
    score += sum(1.2 for term in terms if term == item.type.value)
    return score


def _terms(query: str) -> list[str]:
    return [part.lower() for part in query.split() if part.strip()]


def _related_decision_types(
    left: StrategicMemoryType,
    right: StrategicMemoryType,
) -> bool:
    decision_types = {
        StrategicMemoryType.STRATEGIC_DECISION,
        StrategicMemoryType.ROADMAP_DECISION,
        StrategicMemoryType.POSITIONING_DECISION,
        StrategicMemoryType.LAUNCH_DECISION,
        StrategicMemoryType.REJECTED_PATH,
        StrategicMemoryType.CONSTRAINT,
    }
    return left in decision_types and right in decision_types


def _has_negative_marker(text: str) -> bool:
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in ("do not", "don't", "defer", "avoid", "reject", "not ", "never")
    )


def _has_positive_marker(text: str) -> bool:
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in ("should", "must", "prioritize", "launch", "build", "pursue")
    )


def _datetime_to_text(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _optional_datetime_to_text(value: datetime | None) -> str | None:
    return _datetime_to_text(value) if value is not None else None


def _json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _row_str(row: sqlite3.Row, key: str) -> str:
    return cast(str, row[key])
