"""SQLite schema migrations."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

SCHEMA_VERSION = 7

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

MIGRATION_4 = """
CREATE TABLE IF NOT EXISTS outcomes (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    decision_trace_id TEXT NOT NULL REFERENCES decision_traces(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    observed_at TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    metrics_json TEXT NOT NULL DEFAULT '[]',
    evidence_json TEXT NOT NULL DEFAULT '[]',
    severity REAL NOT NULL DEFAULT 0,
    confidence REAL NOT NULL DEFAULT 0.7,
    tags_json TEXT NOT NULL DEFAULT '[]',
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_outcomes_run_id
ON outcomes(run_id, observed_at);

CREATE INDEX IF NOT EXISTS idx_outcomes_decision_trace_id
ON outcomes(decision_trace_id, observed_at);

CREATE TABLE IF NOT EXISTS reflections (
    id TEXT PRIMARY KEY,
    outcome_id TEXT NOT NULL REFERENCES outcomes(id) ON DELETE CASCADE,
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    decision_trace_id TEXT NOT NULL REFERENCES decision_traces(id) ON DELETE CASCADE,
    what_worked TEXT NOT NULL DEFAULT '',
    what_failed TEXT NOT NULL DEFAULT '',
    likely_cause TEXT NOT NULL DEFAULT '',
    recommended_change TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL DEFAULT 0.7,
    tags_json TEXT NOT NULL DEFAULT '[]',
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_reflections_run_id
ON reflections(run_id);

CREATE INDEX IF NOT EXISTS idx_reflections_outcome_id
ON reflections(outcome_id);

CREATE TABLE IF NOT EXISTS learning_signals (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    decision_trace_id TEXT NOT NULL REFERENCES decision_traces(id) ON DELETE CASCADE,
    outcome_id TEXT NOT NULL REFERENCES outcomes(id) ON DELETE CASCADE,
    signal_type TEXT NOT NULL,
    direction TEXT NOT NULL,
    target TEXT NOT NULL,
    rationale TEXT NOT NULL DEFAULT '',
    strength REAL NOT NULL DEFAULT 0.5,
    confidence REAL NOT NULL DEFAULT 0.7,
    status TEXT NOT NULL DEFAULT 'draft',
    tags_json TEXT NOT NULL DEFAULT '[]',
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_learning_signals_run_id
ON learning_signals(run_id);

CREATE INDEX IF NOT EXISTS idx_learning_signals_type_status
ON learning_signals(signal_type, status);

CREATE TABLE IF NOT EXISTS failure_memory_drafts (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    decision_trace_id TEXT NOT NULL REFERENCES decision_traces(id) ON DELETE CASCADE,
    outcome_id TEXT NOT NULL REFERENCES outcomes(id) ON DELETE CASCADE,
    memory_type TEXT NOT NULL DEFAULT 'failure',
    summary TEXT NOT NULL DEFAULT '',
    content TEXT NOT NULL DEFAULT '',
    tags_json TEXT NOT NULL DEFAULT '[]',
    confidence REAL NOT NULL DEFAULT 0.7,
    severity REAL NOT NULL DEFAULT 0.5,
    suggested_memory_importance REAL NOT NULL DEFAULT 0.6,
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_failure_memory_drafts_run_id
ON failure_memory_drafts(run_id);

CREATE INDEX IF NOT EXISTS idx_failure_memory_drafts_outcome_id
ON failure_memory_drafts(outcome_id);

CREATE TABLE IF NOT EXISTS policy_update_suggestions (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    decision_trace_id TEXT NOT NULL REFERENCES decision_traces(id) ON DELETE CASCADE,
    outcome_id TEXT NOT NULL REFERENCES outcomes(id) ON DELETE CASCADE,
    policy_area TEXT NOT NULL,
    current_rule TEXT NOT NULL DEFAULT '',
    suggested_rule TEXT NOT NULL DEFAULT '',
    rationale TEXT NOT NULL DEFAULT '',
    confidence REAL NOT NULL DEFAULT 0.7,
    status TEXT NOT NULL DEFAULT 'draft',
    tags_json TEXT NOT NULL DEFAULT '[]',
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_policy_update_suggestions_run_id
ON policy_update_suggestions(run_id);

CREATE INDEX IF NOT EXISTS idx_policy_update_suggestions_area_status
ON policy_update_suggestions(policy_area, status);
"""

MIGRATION_5 = """
CREATE TABLE IF NOT EXISTS decision_quality_profiles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    decision_area TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    rules_json TEXT NOT NULL DEFAULT '[]',
    evidence_json TEXT NOT NULL DEFAULT '[]',
    confidence REAL NOT NULL DEFAULT 0.5,
    source_learning_signal_ids_json TEXT NOT NULL DEFAULT '[]',
    source_outcome_ids_json TEXT NOT NULL DEFAULT '[]',
    source_policy_suggestion_ids_json TEXT NOT NULL DEFAULT '[]',
    tags_json TEXT NOT NULL DEFAULT '[]',
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_decision_quality_profiles_status_area
ON decision_quality_profiles(status, decision_area);

CREATE TABLE IF NOT EXISTS profile_applications (
    id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES decision_quality_profiles(id) ON DELETE CASCADE,
    profile_name TEXT NOT NULL,
    decision_area TEXT NOT NULL,
    run_id TEXT REFERENCES runs(id) ON DELETE SET NULL,
    trace_id TEXT REFERENCES decision_traces(id) ON DELETE SET NULL,
    target TEXT NOT NULL DEFAULT '',
    applied INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    effect_summary TEXT NOT NULL DEFAULT '',
    before_json TEXT NOT NULL DEFAULT '{}',
    after_json TEXT NOT NULL DEFAULT '{}',
    adjustments_json TEXT NOT NULL DEFAULT '[]',
    notes_json TEXT NOT NULL DEFAULT '[]',
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_profile_applications_run_id
ON profile_applications(run_id, created_at);

CREATE INDEX IF NOT EXISTS idx_profile_applications_profile_id
ON profile_applications(profile_id, created_at);
"""

MIGRATION_6 = """
CREATE TABLE IF NOT EXISTS pareto_frontiers (
    id TEXT PRIMARY KEY,
    run_id TEXT REFERENCES runs(id) ON DELETE SET NULL,
    title TEXT NOT NULL DEFAULT '',
    candidate_type TEXT NOT NULL DEFAULT '',
    preference_profile_id TEXT NOT NULL,
    selected_candidate_id TEXT,
    candidate_count INTEGER NOT NULL DEFAULT 0,
    frontier_count INTEGER NOT NULL DEFAULT 0,
    dominated_count INTEGER NOT NULL DEFAULT 0,
    tradeoff_summary TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_pareto_frontiers_run_id
ON pareto_frontiers(run_id, created_at);

CREATE INDEX IF NOT EXISTS idx_pareto_frontiers_preference
ON pareto_frontiers(preference_profile_id, created_at);

CREATE TABLE IF NOT EXISTS pareto_candidates (
    id TEXT PRIMARY KEY,
    frontier_id TEXT NOT NULL REFERENCES pareto_frontiers(id) ON DELETE CASCADE,
    candidate_id TEXT NOT NULL,
    run_id TEXT REFERENCES runs(id) ON DELETE SET NULL,
    candidate_type TEXT NOT NULL,
    label TEXT NOT NULL,
    constraints_satisfied INTEGER NOT NULL DEFAULT 1,
    objective_vector_json TEXT NOT NULL DEFAULT '{}',
    violated_constraints_json TEXT NOT NULL DEFAULT '[]',
    estimated_cost REAL NOT NULL DEFAULT 0,
    estimated_tokens INTEGER NOT NULL DEFAULT 0,
    rationale TEXT NOT NULL DEFAULT '',
    source_decision_trace_ids_json TEXT NOT NULL DEFAULT '[]',
    source_profile_ids_json TEXT NOT NULL DEFAULT '[]',
    tags_json TEXT NOT NULL DEFAULT '[]',
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_pareto_candidates_frontier_id
ON pareto_candidates(frontier_id, candidate_type);

CREATE INDEX IF NOT EXISTS idx_pareto_candidates_run_id
ON pareto_candidates(run_id, candidate_type);

CREATE TABLE IF NOT EXISTS pareto_selections (
    id TEXT PRIMARY KEY,
    frontier_id TEXT NOT NULL UNIQUE REFERENCES pareto_frontiers(id) ON DELETE CASCADE,
    run_id TEXT REFERENCES runs(id) ON DELETE SET NULL,
    selected_candidate_id TEXT NOT NULL,
    preference_profile_id TEXT NOT NULL,
    preference_profile_json TEXT NOT NULL DEFAULT '{}',
    ranked_candidate_ids_json TEXT NOT NULL DEFAULT '[]',
    candidate_scores_json TEXT NOT NULL DEFAULT '{}',
    tradeoff_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_pareto_selections_run_id
ON pareto_selections(run_id, created_at);
"""

MIGRATION_7 = """
CREATE TABLE IF NOT EXISTS qubo_problems (
    id TEXT PRIMARY KEY,
    run_id TEXT REFERENCES runs(id) ON DELETE SET NULL,
    problem_type TEXT NOT NULL,
    source_benchmark_id TEXT,
    source_frontier_id TEXT,
    source_decision_trace_ids_json TEXT NOT NULL DEFAULT '[]',
    variable_count INTEGER NOT NULL DEFAULT 0,
    linear_term_count INTEGER NOT NULL DEFAULT 0,
    quadratic_term_count INTEGER NOT NULL DEFAULT 0,
    constraint_count INTEGER NOT NULL DEFAULT 0,
    tags_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_qubo_problems_run_id
ON qubo_problems(run_id, created_at);

CREATE INDEX IF NOT EXISTS idx_qubo_problems_type
ON qubo_problems(problem_type, created_at);

CREATE TABLE IF NOT EXISTS qubo_solutions (
    id TEXT PRIMARY KEY,
    problem_id TEXT NOT NULL REFERENCES qubo_problems(id) ON DELETE CASCADE,
    run_id TEXT REFERENCES runs(id) ON DELETE SET NULL,
    solver_name TEXT NOT NULL,
    objective_value REAL NOT NULL,
    feasible INTEGER NOT NULL DEFAULT 0,
    iterations INTEGER NOT NULL DEFAULT 0,
    selected_variables_json TEXT NOT NULL DEFAULT '[]',
    constraint_violations_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_qubo_solutions_problem_id
ON qubo_solutions(problem_id, created_at);

CREATE INDEX IF NOT EXISTS idx_qubo_solutions_run_id
ON qubo_solutions(run_id, created_at);
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
    if 4 not in applied_versions:
        connection.executescript(MIGRATION_4)
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (4, datetime.now(UTC).isoformat()),
        )
    if 5 not in applied_versions:
        connection.executescript(MIGRATION_5)
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (5, datetime.now(UTC).isoformat()),
        )
    if 6 not in applied_versions:
        connection.executescript(MIGRATION_6)
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (6, datetime.now(UTC).isoformat()),
        )
    if 7 not in applied_versions:
        connection.executescript(MIGRATION_7)
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (7, datetime.now(UTC).isoformat()),
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
