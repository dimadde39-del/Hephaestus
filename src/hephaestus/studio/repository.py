"""SQLite repository helpers for Studio metadata and search."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from hephaestus.conversation.repository import ConversationRepository
from hephaestus.conversation.schemas import (
    ConversationMessage,
    ConversationSession,
    DeliberationMode,
)
from hephaestus.storage.sqlite import connect_database, init_database
from hephaestus.studio.schemas import (
    ConversationSummary,
    RecentRepo,
    SearchResult,
    StudioMessage,
)

EMPTY_CONVERSATION_TITLE = "New Conversation"


class StudioRepository:
    """Read and mutate Studio-facing conversation metadata."""

    def __init__(self, database_path: Path | str | None = None) -> None:
        self.database_path = init_database(database_path)
        self.conversations = ConversationRepository(self.database_path)

    def create_conversation(
        self,
        *,
        title: str = EMPTY_CONVERSATION_TITLE,
        mode: DeliberationMode = DeliberationMode.BALANCED,
        repo_profile_id: str | None = None,
        workspace_path: str | None = None,
        manual_title: bool = False,
    ) -> ConversationSummary:
        """Create an empty conversation that the CLI can also read."""

        metadata: dict[str, Any] = {
            "studio": True,
            "manual_title": manual_title,
        }
        if workspace_path is not None:
            metadata["workspace_path"] = workspace_path
        session = self.conversations.create_session(
            ConversationSession(
                title=title,
                mode=mode,
                repo_profile_id=repo_profile_id,
                metadata=metadata,
            )
        )
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                UPDATE conversation_sessions
                SET display_title = ?, workspace_path = ?
                WHERE id = ?
                """,
                (title, workspace_path, session.id),
            )
        summary = self.get_summary(session.id)
        if summary is None:
            raise RuntimeError("Created conversation could not be reloaded.")
        return summary

    def list_conversations(
        self,
        *,
        query: str = "",
        include_archived: bool = False,
        archived_only: bool = False,
        repo_profile_id: str | None = None,
        workspace_path: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[ConversationSummary], int]:
        """List conversations with Studio ordering and deterministic filtering."""

        where, params = self._conversation_filters(
            query=query,
            include_archived=include_archived,
            archived_only=archived_only,
            repo_profile_id=repo_profile_id,
            workspace_path=workspace_path,
        )
        with connect_database(self.database_path) as connection:
            total = cast(
                int,
                connection.execute(
                    f"SELECT COUNT(*) FROM conversation_sessions s {where}",
                    params,
                ).fetchone()[0],
            )
            rows = connection.execute(
                f"""
                {_conversation_summary_select()}
                {where}
                ORDER BY s.is_pinned DESC, s.updated_at DESC, s.id DESC
                LIMIT ? OFFSET ?
                """,
                (*params, limit, offset),
            ).fetchall()
        return [_summary_from_row(row) for row in rows], total

    def get_summary(self, session_id: str) -> ConversationSummary | None:
        """Read one Studio conversation summary."""

        with connect_database(self.database_path) as connection:
            row = connection.execute(
                f"""
                {_conversation_summary_select()}
                WHERE s.id = ?
                """,
                (session_id,),
            ).fetchone()
        return _summary_from_row(row) if row is not None else None

    def get_session(self, session_id: str) -> ConversationSession | None:
        """Read the canonical conversation session."""

        return self.conversations.get_session(session_id)

    def list_messages(self, session_id: str) -> list[StudioMessage]:
        """List exact persisted messages in chronological order."""

        return [
            _studio_message_from_message(message)
            for message in self.conversations.list_messages(session_id)
        ]

    def message_count(self, session_id: str) -> int:
        """Count exact persisted messages for a conversation."""

        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT COUNT(*) FROM conversation_messages WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return cast(int, row[0])

    def rename_conversation(
        self,
        session_id: str,
        title: str,
        *,
        manual: bool,
    ) -> ConversationSummary | None:
        """Rename a conversation and preserve the rename for the CLI."""

        session = self.conversations.get_session(session_id)
        if session is None:
            return None
        metadata = dict(session.metadata)
        metadata["manual_title"] = manual
        updated = session.model_copy(
            update={
                "title": title,
                "updated_at": datetime.now(UTC),
                "metadata": metadata,
            }
        )
        self.conversations.create_session(updated)
        with connect_database(self.database_path) as connection:
            connection.execute(
                "UPDATE conversation_sessions SET display_title = ? WHERE id = ?",
                (title, session_id),
            )
        return self.get_summary(session_id)

    def set_pin(self, session_id: str, *, is_pinned: bool) -> ConversationSummary | None:
        """Pin or unpin a conversation."""

        if self.conversations.get_session(session_id) is None:
            return None
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                UPDATE conversation_sessions
                SET is_pinned = ?, updated_at = ?
                WHERE id = ?
                """,
                (int(is_pinned), _datetime_to_text(datetime.now(UTC)), session_id),
            )
        return self.get_summary(session_id)

    def set_archive(
        self,
        session_id: str,
        *,
        is_archived: bool,
    ) -> ConversationSummary | None:
        """Archive or restore a conversation using the canonical archived flag."""

        session = self.conversations.get_session(session_id)
        if session is None:
            return None
        updated = session.model_copy(
            update={"archived": is_archived, "updated_at": datetime.now(UTC)}
        )
        self.conversations.create_session(updated)
        return self.get_summary(session_id)

    def patch_context(
        self,
        session_id: str,
        *,
        mode: DeliberationMode | None = None,
        repo_profile_id: str | None = None,
        workspace_path: str | None = None,
        repo_profile_id_provided: bool = False,
        workspace_path_provided: bool = False,
    ) -> ConversationSummary | None:
        """Patch mode and optional repo/workspace context on the session."""

        session = self.conversations.get_session(session_id)
        if session is None:
            return None
        metadata = dict(session.metadata)
        if workspace_path_provided:
            metadata["workspace_path"] = workspace_path
        updated = session.model_copy(
            update={
                "mode": mode or session.mode,
                "repo_profile_id": repo_profile_id
                if repo_profile_id_provided
                else session.repo_profile_id,
                "updated_at": datetime.now(UTC),
                "metadata": metadata,
            }
        )
        self.conversations.create_session(updated)
        if workspace_path_provided:
            with connect_database(self.database_path) as connection:
                connection.execute(
                    "UPDATE conversation_sessions SET workspace_path = ? WHERE id = ?",
                    (workspace_path, session_id),
                )
        return self.get_summary(session_id)

    def touch_opened(self, session_id: str) -> ConversationSummary | None:
        """Record that a conversation was opened without generating any recap."""

        if self.conversations.get_session(session_id) is None:
            return None
        with connect_database(self.database_path) as connection:
            connection.execute(
                "UPDATE conversation_sessions SET last_opened_at = ? WHERE id = ?",
                (_datetime_to_text(datetime.now(UTC)), session_id),
            )
        return self.get_summary(session_id)

    def search(
        self,
        query: str,
        *,
        include_archived: bool = False,
        limit: int = 30,
    ) -> list[SearchResult]:
        """Search titles, user messages, and assistant messages without model calls."""

        normalized = query.strip()
        if not normalized:
            return []
        like = f"%{normalized.lower()}%"
        archived_clause = "" if include_archived else "AND s.archived = 0"
        results: list[SearchResult] = []
        with connect_database(self.database_path) as connection:
            title_rows = connection.execute(
                f"""
                SELECT
                    s.id AS conversation_id,
                    COALESCE(NULLIF(s.display_title, ''), s.title) AS conversation_title,
                    s.updated_at AS occurred_at,
                    s.archived AS is_archived
                FROM conversation_sessions s
                WHERE lower(COALESCE(NULLIF(s.display_title, ''), s.title)) LIKE ?
                {archived_clause}
                ORDER BY s.updated_at DESC, s.id DESC
                LIMIT ?
                """,
                (like, limit),
            ).fetchall()
            message_rows = connection.execute(
                f"""
                SELECT
                    s.id AS conversation_id,
                    COALESCE(NULLIF(s.display_title, ''), s.title) AS conversation_title,
                    s.archived AS is_archived,
                    m.id AS message_id,
                    m.role AS role,
                    m.content AS content,
                    m.created_at AS occurred_at
                FROM conversation_messages m
                JOIN conversation_sessions s ON s.id = m.session_id
                WHERE lower(m.content) LIKE ?
                {archived_clause}
                ORDER BY m.created_at DESC, m.id DESC
                LIMIT ?
                """,
                (like, limit),
            ).fetchall()
        for row in title_rows:
            results.append(
                SearchResult(
                    conversation_id=_row_str(row, "conversation_id"),
                    conversation_title=_row_str(row, "conversation_title"),
                    match_type="title",
                    snippet=_row_str(row, "conversation_title"),
                    occurred_at=_datetime_from_text(_row_str(row, "occurred_at")),
                    is_archived=_row_bool(row, "is_archived"),
                )
            )
        for row in message_rows:
            results.append(
                SearchResult(
                    conversation_id=_row_str(row, "conversation_id"),
                    conversation_title=_row_str(row, "conversation_title"),
                    match_type="message",
                    snippet=_snippet(_row_str(row, "content"), normalized),
                    message_id=_row_str(row, "message_id"),
                    role=cast(Any, _row_str(row, "role")),
                    occurred_at=_datetime_from_text(_row_str(row, "occurred_at")),
                    is_archived=_row_bool(row, "is_archived"),
                )
            )
        return sorted(
            results,
            key=lambda item: item.occurred_at or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )[:limit]

    def list_recent_repos(self, *, limit: int = 20) -> list[RecentRepo]:
        """List recent repo profiles for optional context selection."""

        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT id, repo_name, repo_path, detected_stack_summary, inspected_at
                FROM repo_profiles
                ORDER BY inspected_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [
            RecentRepo(
                id=_row_str(row, "id"),
                name=_row_str(row, "repo_name"),
                path=_row_str(row, "repo_path"),
                stack_summary=_row_str(row, "detected_stack_summary"),
                inspected_at=_datetime_from_text(_row_str(row, "inspected_at")),
            )
            for row in rows
        ]

    def count_regular_memories(self) -> int:
        """Count regular memories without exposing their contents."""

        with connect_database(self.database_path) as connection:
            return cast(int, connection.execute("SELECT COUNT(*) FROM memories").fetchone()[0])

    def count_strategic_memories(self) -> int:
        """Count active strategic memories without exposing their contents."""

        with connect_database(self.database_path) as connection:
            return cast(
                int,
                connection.execute(
                    "SELECT COUNT(*) FROM strategic_memories WHERE archived_at IS NULL"
                ).fetchone()[0],
            )

    def _conversation_filters(
        self,
        *,
        query: str,
        include_archived: bool,
        archived_only: bool,
        repo_profile_id: str | None,
        workspace_path: str | None,
    ) -> tuple[str, tuple[Any, ...]]:
        clauses: list[str] = []
        params: list[Any] = []
        if archived_only:
            clauses.append("s.archived = 1")
        elif not include_archived:
            clauses.append("s.archived = 0")
        if repo_profile_id is not None:
            clauses.append("s.repo_profile_id = ?")
            params.append(repo_profile_id)
        if workspace_path is not None:
            clauses.append("s.workspace_path = ?")
            params.append(workspace_path)
        if query.strip():
            clauses.append(
                """
                (
                    lower(COALESCE(NULLIF(s.display_title, ''), s.title)) LIKE ?
                    OR EXISTS (
                        SELECT 1
                        FROM conversation_messages m
                        WHERE m.session_id = s.id AND lower(m.content) LIKE ?
                    )
                )
                """
            )
            like = f"%{query.strip().lower()}%"
            params.extend([like, like])
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        return where, tuple(params)


def _conversation_summary_select() -> str:
    return """
    SELECT
        s.id,
        COALESCE(NULLIF(s.display_title, ''), s.title) AS title,
        s.created_at,
        s.updated_at,
        s.mode,
        s.repo_profile_id,
        r.repo_name,
        s.workspace_path AS workspace_path,
        s.is_pinned,
        s.archived AS is_archived,
        s.last_opened_at,
        s.linked_decision_trace_ids_json,
        (
            SELECT COUNT(*)
            FROM conversation_messages m_count
            WHERE m_count.session_id = s.id
        ) AS message_count,
        COALESCE((
            SELECT m_preview.content
            FROM conversation_messages m_preview
            WHERE m_preview.session_id = s.id
            ORDER BY m_preview.created_at DESC, m_preview.id DESC
            LIMIT 1
        ), '') AS last_message_preview,
        (
            SELECT COUNT(*)
            FROM coding_requests cr
            WHERE cr.conversation_id = s.id
        ) AS coding_request_count,
        (
            SELECT COUNT(*)
            FROM validation_results vr
            WHERE s.repo_profile_id IS NOT NULL AND vr.repo_profile_id = s.repo_profile_id
        ) AS validation_run_count
    FROM conversation_sessions s
    LEFT JOIN repo_profiles r ON r.id = s.repo_profile_id
    """


def _summary_from_row(row: sqlite3.Row) -> ConversationSummary:
    linked_ids = _json_loads_list(_row_str(row, "linked_decision_trace_ids_json"))
    return ConversationSummary(
        id=_row_str(row, "id"),
        title=_row_str(row, "title"),
        created_at=_datetime_from_text(_row_str(row, "created_at")),
        updated_at=_datetime_from_text(_row_str(row, "updated_at")),
        mode=DeliberationMode(_row_str(row, "mode")),
        repo_profile_id=_row_optional_str(row, "repo_profile_id"),
        repo_name=_row_optional_str(row, "repo_name"),
        workspace_path=_row_optional_str(row, "workspace_path"),
        is_pinned=_row_bool(row, "is_pinned"),
        is_archived=_row_bool(row, "is_archived"),
        last_opened_at=_optional_datetime_from_text(_row_optional_str(row, "last_opened_at")),
        message_count=_row_int(row, "message_count"),
        last_message_preview=_preview(_row_str(row, "last_message_preview")),
        linked_decision_count=len(linked_ids),
        coding_request_count=_row_int(row, "coding_request_count"),
        validation_run_count=_row_int(row, "validation_run_count"),
    )


def _studio_message_from_message(message: ConversationMessage) -> StudioMessage:
    provider_model = message.metadata.get("provider_model")
    return StudioMessage(
        id=message.id,
        session_id=message.session_id,
        role=message.role,
        content=message.content,
        created_at=message.created_at,
        intent=message.intent,
        mode=message.mode,
        provider_model=str(provider_model) if provider_model is not None else None,
        metadata=message.metadata,
    )


def _preview(value: str, *, max_length: int = 140) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max_length - 1].rstrip() + "..."


def _snippet(value: str, query: str, *, radius: int = 72) -> str:
    normalized = " ".join(value.split())
    if not normalized:
        return ""
    start = normalized.lower().find(query.lower())
    if start < 0:
        return _preview(normalized, max_length=radius * 2)
    left = max(0, start - radius)
    right = min(len(normalized), start + len(query) + radius)
    prefix = "..." if left > 0 else ""
    suffix = "..." if right < len(normalized) else ""
    return f"{prefix}{normalized[left:right].strip()}{suffix}"


def _datetime_to_text(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _datetime_from_text(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _optional_datetime_from_text(value: str | None) -> datetime | None:
    return _datetime_from_text(value) if value else None


def _json_loads_list(value: str) -> list[str]:
    loaded = json.loads(value)
    if not isinstance(loaded, list):
        return []
    return [str(item) for item in loaded]


def _row_str(row: sqlite3.Row, key: str) -> str:
    return cast(str, row[key])


def _row_optional_str(row: sqlite3.Row, key: str) -> str | None:
    return cast(str | None, row[key])


def _row_int(row: sqlite3.Row, key: str) -> int:
    return int(cast(int | float, row[key]))


def _row_bool(row: sqlite3.Row, key: str) -> bool:
    return bool(_row_int(row, key))
