"""SQLite schema migrations."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

SCHEMA_VERSION = 3

MIGRATION_1 = """
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    content TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    tags TEXT NOT NULL DEFAULT '[]',
    project TEXT NOT NULL DEFAULT 'default',
    confidence REAL NOT NULL,
    importance REAL NOT NULL,
    created_at TEXT NOT NULL,
    last_verified_at TEXT,
    source TEXT NOT NULL DEFAULT 'user'
);

CREATE INDEX IF NOT EXISTS idx_memories_project_type
ON memories(project, type);

CREATE INDEX IF NOT EXISTS idx_memories_created_at
ON memories(created_at);

CREATE TABLE IF NOT EXISTS runs (
    id TEXT PRIMARY KEY,
    goal TEXT NOT NULL,
    mode TEXT NOT NULL,
    started_at TEXT NOT NULL,
    completed_at TEXT,
    status TEXT NOT NULL,
    estimated_input_tokens INTEGER NOT NULL DEFAULT 0,
    estimated_output_tokens INTEGER NOT NULL DEFAULT 0,
    estimated_cost REAL NOT NULL DEFAULT 0,
    objective_score REAL NOT NULL DEFAULT 0,
    risk_score REAL NOT NULL DEFAULT 0,
    summary TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_runs_started_at
ON runs(started_at DESC);

CREATE TABLE IF NOT EXISTS run_tasks (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    task_id TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    selected_order INTEGER NOT NULL,
    priority INTEGER NOT NULL,
    risk REAL NOT NULL,
    expected_value REAL NOT NULL,
    dependencies TEXT NOT NULL DEFAULT '[]',
    required_capabilities TEXT NOT NULL DEFAULT '[]',
    requires_approval INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_run_tasks_run_id
ON run_tasks(run_id, selected_order);

CREATE TABLE IF NOT EXISTS run_decisions (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    decision_type TEXT NOT NULL,
    selected_option TEXT NOT NULL,
    rejected_options TEXT NOT NULL DEFAULT '[]',
    objective_score REAL,
    estimated_cost REAL,
    rationale TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_run_decisions_run_id
ON run_decisions(run_id, created_at);

CREATE TABLE IF NOT EXISTS approvals (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    action_type TEXT NOT NULL,
    action_description TEXT NOT NULL,
    risk_level TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    resolved_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_approvals_run_id
ON approvals(run_id, created_at);
"""

MIGRATION_2 = """
CREATE TABLE IF NOT EXISTS decision_traces (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    parent_id TEXT REFERENCES decision_traces(id) ON DELETE SET NULL,
    decision_type TEXT NOT NULL,
    phase TEXT NOT NULL DEFAULT 'runtime',
    timestamp TEXT NOT NULL,
    selected_option TEXT NOT NULL,
    rationale TEXT NOT NULL DEFAULT '',
    objective_score REAL,
    confidence REAL NOT NULL,
    alternatives_json TEXT NOT NULL DEFAULT '[]',
    metrics_json TEXT NOT NULL DEFAULT '[]',
    constraints_json TEXT NOT NULL DEFAULT '[]',
    tags_json TEXT NOT NULL DEFAULT '[]',
    caused_by_json TEXT NOT NULL DEFAULT '[]',
    will_affect_json TEXT NOT NULL DEFAULT '[]',
    learning_hooks_json TEXT NOT NULL DEFAULT '[]',
    outcome_id TEXT,
    failure_memory_id TEXT,
    policy_update_id TEXT,
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_decision_traces_run_id
ON decision_traces(run_id, timestamp);

CREATE INDEX IF NOT EXISTS idx_decision_traces_type
ON decision_traces(decision_type);
"""

_DECISION_TRACE_COLUMNS: dict[str, str] = {
    "parent_id": "TEXT REFERENCES decision_traces(id) ON DELETE SET NULL",
    "phase": "TEXT NOT NULL DEFAULT 'runtime'",
    "alternatives_json": "TEXT NOT NULL DEFAULT '[]'",
    "metrics_json": "TEXT NOT NULL DEFAULT '[]'",
    "constraints_json": "TEXT NOT NULL DEFAULT '[]'",
    "tags_json": "TEXT NOT NULL DEFAULT '[]'",
    "caused_by_json": "TEXT NOT NULL DEFAULT '[]'",
    "will_affect_json": "TEXT NOT NULL DEFAULT '[]'",
    "learning_hooks_json": "TEXT NOT NULL DEFAULT '[]'",
    "outcome_id": "TEXT",
    "failure_memory_id": "TEXT",
    "policy_update_id": "TEXT",
    "raw_json": "TEXT NOT NULL DEFAULT '{}'",
}


def run_migrations(connection: sqlite3.Connection) -> None:
    """Apply all known SQLite migrations idempotently."""

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    applied_versions = {
        row[0] for row in connection.execute("SELECT version FROM schema_migrations").fetchall()
    }
    if 1 not in applied_versions:
        connection.executescript(MIGRATION_1)
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (1, datetime.now(UTC).isoformat()),
        )
    if 2 not in applied_versions:
        connection.executescript(MIGRATION_2)
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (2, datetime.now(UTC).isoformat()),
        )
    if 3 not in applied_versions:
        _migrate_decision_traces_v3(connection)
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (3, datetime.now(UTC).isoformat()),
        )
    connection.commit()


def _migrate_decision_traces_v3(connection: sqlite3.Connection) -> None:
    """Add future-learning trace columns to databases created during early Phase 3A."""

    table = connection.execute(
        "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'decision_traces'"
    ).fetchone()
    if table is None:
        connection.executescript(MIGRATION_2)

    existing_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(decision_traces)").fetchall()
    }
    for column, definition in _DECISION_TRACE_COLUMNS.items():
        if column not in existing_columns:
            connection.execute(f"ALTER TABLE decision_traces ADD COLUMN {column} {definition}")

    refreshed_columns = {
        row[1] for row in connection.execute("PRAGMA table_info(decision_traces)").fetchall()
    }
    if "alternatives" in refreshed_columns:
        connection.execute(
            """
            UPDATE decision_traces
            SET alternatives_json = alternatives
            WHERE alternatives_json = '[]' AND alternatives IS NOT NULL
            """
        )
    if "metrics" in refreshed_columns:
        connection.execute(
            """
            UPDATE decision_traces
            SET metrics_json = metrics
            WHERE metrics_json = '[]' AND metrics IS NOT NULL
            """
        )
    if "constraints_considered" in refreshed_columns:
        connection.execute(
            """
            UPDATE decision_traces
            SET constraints_json = constraints_considered
            WHERE constraints_json = '[]' AND constraints_considered IS NOT NULL
            """
        )
