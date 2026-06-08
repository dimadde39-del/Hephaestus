"""SQLite persistence for conversation sessions and messages."""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from hephaestus.conversation.schemas import (
    ConversationMemoryUpdate,
    ConversationMessage,
    ConversationSession,
    DeliberationMode,
)
from hephaestus.storage.sqlite import connect_database, init_database


class ConversationRepository:
    """Persist conversation sessions, messages, memory updates, and trace links."""

    def __init__(self, database_path: Path | str | None = None) -> None:
        self.database_path = init_database(database_path)

    def create_session(self, session: ConversationSession) -> ConversationSession:
        """Create or replace a conversation session."""

        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO conversation_sessions (
                    id, title, created_at, updated_at, mode, repo_profile_id, archived,
                    summary, linked_decision_trace_ids_json, metadata_json, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at,
                    mode = excluded.mode,
                    repo_profile_id = excluded.repo_profile_id,
                    archived = excluded.archived,
                    summary = excluded.summary,
                    linked_decision_trace_ids_json = excluded.linked_decision_trace_ids_json,
                    metadata_json = excluded.metadata_json,
                    raw_json = excluded.raw_json
                """,
                _session_values(session),
            )
        return session

    def list_sessions(
        self,
        *,
        limit: int = 20,
        include_archived: bool = False,
    ) -> list[ConversationSession]:
        """List recent conversation sessions."""

        where = "" if include_archived else "WHERE archived = 0"
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                f"""
                SELECT raw_json FROM conversation_sessions
                {where}
                ORDER BY updated_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [ConversationSession.model_validate_json(_row_str(row, "raw_json")) for row in rows]

    def get_session(self, session_id: str) -> ConversationSession | None:
        """Read one conversation session."""

        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT raw_json FROM conversation_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            return None
        return ConversationSession.model_validate_json(_row_str(row, "raw_json"))

    def update_session_mode(
        self,
        session_id: str,
        mode: DeliberationMode,
    ) -> ConversationSession | None:
        """Update a session's active deliberation mode."""

        session = self.get_session(session_id)
        if session is None:
            return None
        updated = session.model_copy(update={"mode": mode, "updated_at": datetime.now(UTC)})
        self.create_session(updated)
        return updated

    def set_session_repo_profile(
        self,
        session_id: str,
        repo_profile_id: str,
    ) -> ConversationSession | None:
        """Attach a repo profile ID to a session."""

        session = self.get_session(session_id)
        if session is None:
            return None
        updated = session.model_copy(
            update={"repo_profile_id": repo_profile_id, "updated_at": datetime.now(UTC)}
        )
        self.create_session(updated)
        return updated

    def add_message(self, message: ConversationMessage) -> ConversationMessage:
        """Persist a conversation message."""

        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO conversation_messages (
                    id, session_id, role, content, created_at, intent, mode,
                    selected_memory_ids_json, context_json, decision_trace_id,
                    metadata_json, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                _message_values(message),
            )
        self._touch_session(message.session_id)
        return message

    def list_messages(self, session_id: str) -> list[ConversationMessage]:
        """List messages in one session."""

        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT raw_json FROM conversation_messages
                WHERE session_id = ?
                ORDER BY created_at, id
                """,
                (session_id,),
            ).fetchall()
        return [ConversationMessage.model_validate_json(_row_str(row, "raw_json")) for row in rows]

    def save_response(self, message: ConversationMessage) -> ConversationMessage:
        """Persist an assistant response message."""

        return self.add_message(message)

    def save_memory_update(
        self,
        update: ConversationMemoryUpdate,
    ) -> ConversationMemoryUpdate:
        """Persist a suggested or saved conversation memory update."""

        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO conversation_memory_updates (
                    id, session_id, message_id, memory_id, status, candidate_json,
                    created_at, raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    update.id,
                    update.session_id,
                    update.message_id,
                    update.memory_id,
                    update.status,
                    update.candidate.model_dump_json(),
                    _datetime_to_text(update.created_at),
                    update.model_dump_json(),
                ),
            )
        self._touch_session(update.session_id)
        return update

    def list_memory_updates(
        self,
        session_id: str,
    ) -> list[ConversationMemoryUpdate]:
        """List memory updates generated by one session."""

        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT raw_json FROM conversation_memory_updates
                WHERE session_id = ?
                ORDER BY created_at, id
                """,
                (session_id,),
            ).fetchall()
        return [
            ConversationMemoryUpdate.model_validate_json(_row_str(row, "raw_json"))
            for row in rows
        ]

    def link_decision_trace(
        self,
        session_id: str,
        decision_trace_id: str,
        *,
        message_id: str | None = None,
    ) -> ConversationSession | None:
        """Link a persisted decision trace to a conversation session and optional message."""

        session = self.get_session(session_id)
        if session is None:
            return None
        trace_ids = list(dict.fromkeys([*session.linked_decision_trace_ids, decision_trace_id]))
        updated = session.model_copy(
            update={
                "linked_decision_trace_ids": trace_ids,
                "updated_at": datetime.now(UTC),
            }
        )
        self.create_session(updated)
        if message_id is not None:
            self._set_message_decision_trace(message_id, decision_trace_id)
        return updated

    def archive_session(self, session_id: str) -> ConversationSession | None:
        """Archive a conversation session."""

        session = self.get_session(session_id)
        if session is None:
            return None
        updated = session.model_copy(update={"archived": True, "updated_at": datetime.now(UTC)})
        self.create_session(updated)
        return updated

    def _touch_session(self, session_id: str) -> None:
        session = self.get_session(session_id)
        if session is None:
            return
        self.create_session(session.model_copy(update={"updated_at": datetime.now(UTC)}))

    def _set_message_decision_trace(self, message_id: str, decision_trace_id: str) -> None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT raw_json FROM conversation_messages WHERE id = ?",
                (message_id,),
            ).fetchone()
            if row is None:
                return
            message = ConversationMessage.model_validate_json(_row_str(row, "raw_json"))
            updated = message.model_copy(update={"decision_trace_id": decision_trace_id})
            connection.execute(
                """
                UPDATE conversation_messages
                SET decision_trace_id = ?, raw_json = ?
                WHERE id = ?
                """,
                (decision_trace_id, updated.model_dump_json(), message_id),
            )


def _session_values(session: ConversationSession) -> tuple[Any, ...]:
    return (
        session.id,
        session.title,
        _datetime_to_text(session.created_at),
        _datetime_to_text(session.updated_at),
        session.mode.value,
        session.repo_profile_id,
        int(session.archived),
        session.summary,
        _json_dumps(session.linked_decision_trace_ids),
        _json_dumps(session.metadata),
        session.model_dump_json(),
    )


def _message_values(message: ConversationMessage) -> tuple[Any, ...]:
    return (
        message.id,
        message.session_id,
        message.role.value,
        message.content,
        _datetime_to_text(message.created_at),
        message.intent.value if message.intent is not None else None,
        message.mode.value if message.mode is not None else None,
        _json_dumps(message.selected_memory_ids),
        _json_dumps([item.model_dump(mode="json") for item in message.context]),
        message.decision_trace_id,
        _json_dumps(message.metadata),
        message.model_dump_json(),
    )


def _datetime_to_text(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _row_str(row: sqlite3.Row, key: str) -> str:
    return cast(str, row[key])
