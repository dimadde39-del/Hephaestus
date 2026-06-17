"""SQLite schema migrations."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime

SCHEMA_VERSION = 17

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

MIGRATION_8 = """
CREATE TABLE IF NOT EXISTS repo_profiles (
    id TEXT PRIMARY KEY,
    repo_path TEXT NOT NULL,
    repo_name TEXT NOT NULL,
    detected_stack_summary TEXT NOT NULL DEFAULT '',
    validation_plan_json TEXT NOT NULL DEFAULT '{}',
    generated_tasks_json TEXT NOT NULL DEFAULT '[]',
    risk_summary_json TEXT NOT NULL DEFAULT '[]',
    inspected_at TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_repo_profiles_path_inspected
ON repo_profiles(repo_path, inspected_at DESC);

CREATE INDEX IF NOT EXISTS idx_repo_profiles_inspected
ON repo_profiles(inspected_at DESC);

CREATE TABLE IF NOT EXISTS repo_inspections (
    id TEXT PRIMARY KEY,
    profile_id TEXT NOT NULL REFERENCES repo_profiles(id) ON DELETE CASCADE,
    repo_path TEXT NOT NULL,
    repo_name TEXT NOT NULL,
    inspected_at TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    detected_stack_summary TEXT NOT NULL DEFAULT '',
    validation_summary TEXT NOT NULL DEFAULT '',
    risk_summary TEXT NOT NULL DEFAULT '',
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_repo_inspections_profile_id
ON repo_inspections(profile_id, inspected_at DESC);

CREATE INDEX IF NOT EXISTS idx_repo_inspections_path
ON repo_inspections(repo_path, inspected_at DESC);
"""

MIGRATION_9 = """
CREATE TABLE IF NOT EXISTS release_plans (
    id TEXT PRIMARY KEY,
    repo_profile_id TEXT NOT NULL REFERENCES repo_profiles(id) ON DELETE CASCADE,
    goal TEXT NOT NULL,
    optimizer_run_id TEXT NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    readiness_score INTEGER NOT NULL DEFAULT 0,
    recommendation_status TEXT NOT NULL DEFAULT 'unknown',
    recommendation_summary TEXT NOT NULL DEFAULT '',
    pareto_frontier_ids_json TEXT NOT NULL DEFAULT '[]',
    qubo_problem_ids_json TEXT NOT NULL DEFAULT '[]',
    decision_trace_ids_json TEXT NOT NULL DEFAULT '[]',
    outcome_ids_json TEXT NOT NULL DEFAULT '[]',
    learning_signal_ids_json TEXT NOT NULL DEFAULT '[]',
    raw_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_release_plans_repo_profile
ON release_plans(repo_profile_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_release_plans_optimizer_run
ON release_plans(optimizer_run_id);

CREATE INDEX IF NOT EXISTS idx_release_plans_created
ON release_plans(created_at DESC);
"""

MIGRATION_10 = """
CREATE TABLE IF NOT EXISTS conversation_sessions (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    mode TEXT NOT NULL,
    repo_profile_id TEXT REFERENCES repo_profiles(id) ON DELETE SET NULL,
    archived INTEGER NOT NULL DEFAULT 0,
    summary TEXT NOT NULL DEFAULT '',
    linked_decision_trace_ids_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_conversation_sessions_updated
ON conversation_sessions(archived, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_conversation_sessions_repo_profile
ON conversation_sessions(repo_profile_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS conversation_messages (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES conversation_sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    created_at TEXT NOT NULL,
    intent TEXT,
    mode TEXT,
    selected_memory_ids_json TEXT NOT NULL DEFAULT '[]',
    context_json TEXT NOT NULL DEFAULT '[]',
    decision_trace_id TEXT REFERENCES decision_traces(id) ON DELETE SET NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_conversation_messages_session
ON conversation_messages(session_id, created_at);

CREATE INDEX IF NOT EXISTS idx_conversation_messages_trace
ON conversation_messages(decision_trace_id);

CREATE TABLE IF NOT EXISTS conversation_memory_updates (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES conversation_sessions(id) ON DELETE CASCADE,
    message_id TEXT REFERENCES conversation_messages(id) ON DELETE SET NULL,
    memory_id TEXT REFERENCES memories(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'suggested',
    candidate_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_conversation_memory_updates_session
ON conversation_memory_updates(session_id, created_at);

CREATE INDEX IF NOT EXISTS idx_conversation_memory_updates_memory
ON conversation_memory_updates(memory_id);
"""

MIGRATION_11 = """
CREATE TABLE IF NOT EXISTS strategic_memories (
    id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    scope TEXT NOT NULL,
    project TEXT,
    repo_profile_id TEXT REFERENCES repo_profiles(id) ON DELETE SET NULL,
    conversation_id TEXT REFERENCES conversation_sessions(id) ON DELETE SET NULL,
    content TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    evidence_json TEXT NOT NULL DEFAULT '[]',
    confidence REAL NOT NULL DEFAULT 0.7,
    importance REAL NOT NULL DEFAULT 0.6,
    stability TEXT NOT NULL,
    source TEXT NOT NULL,
    tags_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    archived_at TEXT,
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_strategic_memories_project_type
ON strategic_memories(project, type, archived_at);

CREATE INDEX IF NOT EXISTS idx_strategic_memories_scope
ON strategic_memories(scope, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_strategic_memories_repo
ON strategic_memories(repo_profile_id, updated_at DESC);

CREATE TABLE IF NOT EXISTS strategic_memory_conflicts (
    id TEXT PRIMARY KEY,
    existing_memory_id TEXT NOT NULL REFERENCES strategic_memories(id) ON DELETE CASCADE,
    candidate_memory_id TEXT,
    conflict_type TEXT NOT NULL,
    description TEXT NOT NULL,
    severity REAL NOT NULL DEFAULT 0.5,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TEXT NOT NULL,
    resolved_at TEXT,
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_strategic_memory_conflicts_status
ON strategic_memory_conflicts(status, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_strategic_memory_conflicts_existing
ON strategic_memory_conflicts(existing_memory_id, status);

CREATE TABLE IF NOT EXISTS strategic_memory_recalls (
    id TEXT PRIMARY KEY,
    query TEXT NOT NULL DEFAULT '',
    tags_json TEXT NOT NULL DEFAULT '[]',
    types_json TEXT NOT NULL DEFAULT '[]',
    scopes_json TEXT NOT NULL DEFAULT '[]',
    selected_memory_ids_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    metadata_json TEXT NOT NULL DEFAULT '{}',
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_strategic_memory_recalls_created
ON strategic_memory_recalls(created_at DESC);
"""

MIGRATION_12 = """
CREATE TABLE IF NOT EXISTS policy_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS policy_custom_profiles (
    id TEXT PRIMARY KEY,
    profile_type TEXT NOT NULL,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_policy_custom_profiles_type
ON policy_custom_profiles(profile_type, updated_at DESC);

CREATE TABLE IF NOT EXISTS policy_evaluations (
    id TEXT PRIMARY KEY,
    prompt TEXT NOT NULL,
    profile_type TEXT NOT NULL,
    profile_name TEXT NOT NULL,
    decision_type TEXT NOT NULL,
    primary_category TEXT NOT NULL,
    categories_json TEXT NOT NULL DEFAULT '[]',
    requires_approval INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    over_refusal_detected INTEGER NOT NULL DEFAULT 0,
    moralizing_detected INTEGER NOT NULL DEFAULT 0,
    notes_json TEXT NOT NULL DEFAULT '[]',
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_policy_evaluations_created
ON policy_evaluations(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_policy_evaluations_decision
ON policy_evaluations(decision_type, primary_category, created_at DESC);
"""

MIGRATION_13 = """
CREATE TABLE IF NOT EXISTS tool_actions (
    id TEXT PRIMARY KEY,
    action_type TEXT NOT NULL,
    workspace_path TEXT NOT NULL,
    command_text TEXT NOT NULL DEFAULT '',
    target_path TEXT NOT NULL DEFAULT '',
    summary TEXT NOT NULL DEFAULT '',
    risk_level TEXT NOT NULL,
    active_policy_profile TEXT NOT NULL DEFAULT '',
    approval_status TEXT NOT NULL DEFAULT 'not_required',
    execution_status TEXT NOT NULL DEFAULT 'planned',
    stdout_summary TEXT NOT NULL DEFAULT '',
    stderr_summary TEXT NOT NULL DEFAULT '',
    exit_code INTEGER,
    files_touched_json TEXT NOT NULL DEFAULT '[]',
    checkpoint_id TEXT,
    decision_trace_id TEXT REFERENCES decision_traces(id) ON DELETE SET NULL,
    outcome_id TEXT REFERENCES outcomes(id) ON DELETE SET NULL,
    conversation_id TEXT REFERENCES conversation_sessions(id) ON DELETE SET NULL,
    run_id TEXT REFERENCES runs(id) ON DELETE SET NULL,
    repo_profile_id TEXT REFERENCES repo_profiles(id) ON DELETE SET NULL,
    patch_id TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_tool_actions_created
ON tool_actions(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_tool_actions_workspace
ON tool_actions(workspace_path, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_tool_actions_patch
ON tool_actions(patch_id);

CREATE TABLE IF NOT EXISTS tool_approvals (
    id TEXT PRIMARY KEY,
    action_id TEXT NOT NULL REFERENCES tool_actions(id) ON DELETE CASCADE,
    risk_level TEXT NOT NULL,
    policy_profile TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL,
    approved INTEGER NOT NULL DEFAULT 0,
    reason TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    decided_at TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_tool_approvals_action
ON tool_approvals(action_id, created_at);

CREATE TABLE IF NOT EXISTS tool_execution_results (
    id TEXT PRIMARY KEY,
    action_id TEXT NOT NULL REFERENCES tool_actions(id) ON DELETE CASCADE,
    status TEXT NOT NULL,
    stdout_summary TEXT NOT NULL DEFAULT '',
    stderr_summary TEXT NOT NULL DEFAULT '',
    exit_code INTEGER,
    files_touched_json TEXT NOT NULL DEFAULT '[]',
    checkpoint_id TEXT,
    decision_trace_id TEXT REFERENCES decision_traces(id) ON DELETE SET NULL,
    outcome_id TEXT REFERENCES outcomes(id) ON DELETE SET NULL,
    duration_seconds REAL NOT NULL DEFAULT 0,
    timed_out INTEGER NOT NULL DEFAULT 0,
    output_truncated INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_tool_execution_results_action
ON tool_execution_results(action_id, created_at);

CREATE TABLE IF NOT EXISTS tool_observations (
    id TEXT PRIMARY KEY,
    action_id TEXT NOT NULL REFERENCES tool_actions(id) ON DELETE CASCADE,
    result_id TEXT REFERENCES tool_execution_results(id) ON DELETE SET NULL,
    observation_type TEXT NOT NULL,
    summary TEXT NOT NULL DEFAULT '',
    signal TEXT NOT NULL DEFAULT '',
    severity REAL NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_tool_observations_action
ON tool_observations(action_id, created_at);

CREATE TABLE IF NOT EXISTS tool_checkpoints (
    id TEXT PRIMARY KEY,
    action_id TEXT REFERENCES tool_actions(id) ON DELETE SET NULL,
    workspace_path TEXT NOT NULL,
    files_touched_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    restored_at TEXT,
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_tool_checkpoints_created
ON tool_checkpoints(created_at DESC);

CREATE INDEX IF NOT EXISTS idx_tool_checkpoints_action
ON tool_checkpoints(action_id, created_at);
"""

MIGRATION_14 = """
CREATE TABLE IF NOT EXISTS validation_plans (
    id TEXT PRIMARY KEY,
    repo_path TEXT NOT NULL,
    repo_profile_id TEXT REFERENCES repo_profiles(id) ON DELETE SET NULL,
    release_plan_id TEXT REFERENCES release_plans(id) ON DELETE SET NULL,
    run_id TEXT REFERENCES runs(id) ON DELETE SET NULL,
    command_count INTEGER NOT NULL DEFAULT 0,
    confidence REAL NOT NULL DEFAULT 0.5,
    status TEXT NOT NULL DEFAULT 'planned',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_validation_plans_repo
ON validation_plans(repo_path, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_validation_plans_release
ON validation_plans(release_plan_id, created_at DESC);

CREATE TABLE IF NOT EXISTS validation_commands (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL REFERENCES validation_plans(id) ON DELETE CASCADE,
    repo_profile_id TEXT REFERENCES repo_profiles(id) ON DELETE SET NULL,
    command_text TEXT NOT NULL,
    command_type TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT '',
    risk_level TEXT NOT NULL,
    requires_approval INTEGER NOT NULL DEFAULT 0,
    blocked INTEGER NOT NULL DEFAULT 0,
    execution_order INTEGER NOT NULL DEFAULT 1,
    decision_trace_id TEXT REFERENCES decision_traces(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_validation_commands_plan
ON validation_commands(plan_id, execution_order);

CREATE INDEX IF NOT EXISTS idx_validation_commands_type
ON validation_commands(command_type, created_at DESC);

CREATE TABLE IF NOT EXISTS validation_results (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL REFERENCES validation_plans(id) ON DELETE CASCADE,
    repo_path TEXT NOT NULL,
    repo_profile_id TEXT REFERENCES repo_profiles(id) ON DELETE SET NULL,
    release_plan_id TEXT REFERENCES release_plans(id) ON DELETE SET NULL,
    run_id TEXT REFERENCES runs(id) ON DELETE SET NULL,
    status TEXT NOT NULL,
    command_count INTEGER NOT NULL DEFAULT 0,
    pass_count INTEGER NOT NULL DEFAULT 0,
    fail_count INTEGER NOT NULL DEFAULT 0,
    skipped_count INTEGER NOT NULL DEFAULT 0,
    timed_out_count INTEGER NOT NULL DEFAULT 0,
    blocked_count INTEGER NOT NULL DEFAULT 0,
    requires_approval_count INTEGER NOT NULL DEFAULT 0,
    warning_count INTEGER NOT NULL DEFAULT 0,
    readiness_impact INTEGER NOT NULL DEFAULT 0,
    evidence_mode TEXT NOT NULL DEFAULT 'no_validation_evidence',
    summary TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_validation_results_repo
ON validation_results(repo_path, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_validation_results_release
ON validation_results(release_plan_id, created_at DESC);

CREATE TABLE IF NOT EXISTS validation_evidence (
    id TEXT PRIMARY KEY,
    validation_result_id TEXT REFERENCES validation_results(id) ON DELETE CASCADE,
    plan_id TEXT NOT NULL REFERENCES validation_plans(id) ON DELETE CASCADE,
    command_id TEXT NOT NULL REFERENCES validation_commands(id) ON DELETE CASCADE,
    repo_path TEXT NOT NULL,
    repo_profile_id TEXT REFERENCES repo_profiles(id) ON DELETE SET NULL,
    command_text TEXT NOT NULL,
    command_type TEXT NOT NULL,
    status TEXT NOT NULL,
    exit_code INTEGER,
    stdout_summary TEXT NOT NULL DEFAULT '',
    stderr_summary TEXT NOT NULL DEFAULT '',
    duration_seconds REAL NOT NULL DEFAULT 0,
    tool_action_id TEXT REFERENCES tool_actions(id) ON DELETE SET NULL,
    tool_execution_result_id TEXT REFERENCES tool_execution_results(id) ON DELETE SET NULL,
    outcome_id TEXT REFERENCES outcomes(id) ON DELETE SET NULL,
    decision_trace_id TEXT REFERENCES decision_traces(id) ON DELETE SET NULL,
    failure_classification TEXT,
    warning_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_validation_evidence_result
ON validation_evidence(validation_result_id, created_at);

CREATE INDEX IF NOT EXISTS idx_validation_evidence_repo_status
ON validation_evidence(repo_path, command_type, status, created_at DESC);

CREATE TABLE IF NOT EXISTS release_validation_summaries (
    id TEXT PRIMARY KEY,
    release_plan_id TEXT REFERENCES release_plans(id) ON DELETE SET NULL,
    validation_result_id TEXT NOT NULL REFERENCES validation_results(id) ON DELETE CASCADE,
    repo_path TEXT NOT NULL,
    repo_profile_id TEXT REFERENCES repo_profiles(id) ON DELETE SET NULL,
    status TEXT NOT NULL,
    evidence_based INTEGER NOT NULL DEFAULT 0,
    simulated INTEGER NOT NULL DEFAULT 0,
    readiness_score_before INTEGER,
    readiness_score_after INTEGER,
    readiness_score_delta INTEGER NOT NULL DEFAULT 0,
    pass_count INTEGER NOT NULL DEFAULT 0,
    fail_count INTEGER NOT NULL DEFAULT 0,
    timed_out_count INTEGER NOT NULL DEFAULT 0,
    blocked_count INTEGER NOT NULL DEFAULT 0,
    requires_approval_count INTEGER NOT NULL DEFAULT 0,
    skipped_count INTEGER NOT NULL DEFAULT 0,
    warning_count INTEGER NOT NULL DEFAULT 0,
    summary TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_release_validation_summaries_release
ON release_validation_summaries(release_plan_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_release_validation_summaries_result
ON release_validation_summaries(validation_result_id);
"""

MIGRATION_15 = """
CREATE TABLE IF NOT EXISTS coding_requests (
    id TEXT PRIMARY KEY,
    repo_path TEXT NOT NULL,
    repo_profile_id TEXT REFERENCES repo_profiles(id) ON DELETE SET NULL,
    conversation_id TEXT REFERENCES conversation_sessions(id) ON DELETE SET NULL,
    run_id TEXT REFERENCES runs(id) ON DELETE SET NULL,
    active_policy_profile TEXT NOT NULL DEFAULT '',
    user_request TEXT NOT NULL,
    scope_type TEXT NOT NULL DEFAULT 'unknown',
    risk TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'planned',
    plan_summary TEXT NOT NULL DEFAULT '',
    likely_files_json TEXT NOT NULL DEFAULT '[]',
    patch_ids_json TEXT NOT NULL DEFAULT '[]',
    tool_action_ids_json TEXT NOT NULL DEFAULT '[]',
    checkpoint_ids_json TEXT NOT NULL DEFAULT '[]',
    validation_result_ids_json TEXT NOT NULL DEFAULT '[]',
    outcome_ids_json TEXT NOT NULL DEFAULT '[]',
    decision_trace_ids_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_coding_requests_repo_created
ON coding_requests(repo_path, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_coding_requests_status
ON coding_requests(status, created_at DESC);

CREATE TABLE IF NOT EXISTS coding_plans (
    id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL REFERENCES coding_requests(id) ON DELETE CASCADE,
    repo_path TEXT NOT NULL,
    repo_profile_id TEXT REFERENCES repo_profiles(id) ON DELETE SET NULL,
    conversation_id TEXT REFERENCES conversation_sessions(id) ON DELETE SET NULL,
    run_id TEXT REFERENCES runs(id) ON DELETE SET NULL,
    active_policy_profile TEXT NOT NULL DEFAULT '',
    user_request TEXT NOT NULL,
    scope_type TEXT NOT NULL DEFAULT 'unknown',
    risk TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'planned',
    summary TEXT NOT NULL DEFAULT '',
    likely_files_json TEXT NOT NULL DEFAULT '[]',
    validation_commands_json TEXT NOT NULL DEFAULT '[]',
    validation_plan_id TEXT REFERENCES validation_plans(id) ON DELETE SET NULL,
    patch_proposal_possible INTEGER NOT NULL DEFAULT 0,
    scope_too_large INTEGER NOT NULL DEFAULT 0,
    requires_approval INTEGER NOT NULL DEFAULT 1,
    decision_trace_ids_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_coding_plans_request
ON coding_plans(request_id, created_at DESC);

CREATE TABLE IF NOT EXISTS coding_changes (
    id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL REFERENCES coding_requests(id) ON DELETE CASCADE,
    plan_id TEXT NOT NULL REFERENCES coding_plans(id) ON DELETE CASCADE,
    repo_path TEXT NOT NULL,
    repo_profile_id TEXT REFERENCES repo_profiles(id) ON DELETE SET NULL,
    active_policy_profile TEXT NOT NULL DEFAULT '',
    scope_type TEXT NOT NULL DEFAULT 'unknown',
    risk TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'patch_proposed',
    summary TEXT NOT NULL DEFAULT '',
    files_touched_json TEXT NOT NULL DEFAULT '[]',
    patch_ids_json TEXT NOT NULL DEFAULT '[]',
    tool_action_ids_json TEXT NOT NULL DEFAULT '[]',
    review_id TEXT,
    decision_trace_ids_json TEXT NOT NULL DEFAULT '[]',
    outcome_ids_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_coding_changes_request
ON coding_changes(request_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_coding_changes_plan
ON coding_changes(plan_id, created_at DESC);

CREATE TABLE IF NOT EXISTS coding_iterations (
    id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL REFERENCES coding_requests(id) ON DELETE CASCADE,
    plan_id TEXT REFERENCES coding_plans(id) ON DELETE SET NULL,
    change_id TEXT REFERENCES coding_changes(id) ON DELETE SET NULL,
    review_id TEXT,
    status TEXT NOT NULL DEFAULT 'planned',
    summary TEXT NOT NULL DEFAULT '',
    apply_tool_action_id TEXT REFERENCES tool_actions(id) ON DELETE SET NULL,
    apply_tool_result_id TEXT REFERENCES tool_execution_results(id) ON DELETE SET NULL,
    checkpoint_id TEXT REFERENCES tool_checkpoints(id) ON DELETE SET NULL,
    validation_result_id TEXT REFERENCES validation_results(id) ON DELETE SET NULL,
    rollback_tool_action_id TEXT REFERENCES tool_actions(id) ON DELETE SET NULL,
    rollback_checkpoint_id TEXT REFERENCES tool_checkpoints(id) ON DELETE SET NULL,
    outcome_ids_json TEXT NOT NULL DEFAULT '[]',
    learning_signal_ids_json TEXT NOT NULL DEFAULT '[]',
    decision_trace_ids_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_coding_iterations_request
ON coding_iterations(request_id, created_at DESC);

CREATE TABLE IF NOT EXISTS coding_loop_results (
    id TEXT PRIMARY KEY,
    request_id TEXT NOT NULL REFERENCES coding_requests(id) ON DELETE CASCADE,
    plan_id TEXT REFERENCES coding_plans(id) ON DELETE SET NULL,
    change_id TEXT REFERENCES coding_changes(id) ON DELETE SET NULL,
    repo_path TEXT NOT NULL,
    repo_profile_id TEXT REFERENCES repo_profiles(id) ON DELETE SET NULL,
    conversation_id TEXT REFERENCES conversation_sessions(id) ON DELETE SET NULL,
    run_id TEXT REFERENCES runs(id) ON DELETE SET NULL,
    active_policy_profile TEXT NOT NULL DEFAULT '',
    user_request TEXT NOT NULL,
    scope_type TEXT NOT NULL DEFAULT 'unknown',
    risk TEXT NOT NULL DEFAULT 'medium',
    status TEXT NOT NULL DEFAULT 'planned',
    summary TEXT NOT NULL DEFAULT '',
    iteration_ids_json TEXT NOT NULL DEFAULT '[]',
    patch_ids_json TEXT NOT NULL DEFAULT '[]',
    tool_action_ids_json TEXT NOT NULL DEFAULT '[]',
    checkpoint_ids_json TEXT NOT NULL DEFAULT '[]',
    validation_result_ids_json TEXT NOT NULL DEFAULT '[]',
    outcome_ids_json TEXT NOT NULL DEFAULT '[]',
    learning_signal_ids_json TEXT NOT NULL DEFAULT '[]',
    decision_trace_ids_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_coding_results_request
ON coding_loop_results(request_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_coding_results_repo_created
ON coding_loop_results(repo_path, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_coding_results_status
ON coding_loop_results(status, created_at DESC);
"""

MIGRATION_16 = """
ALTER TABLE conversation_sessions
ADD COLUMN display_title TEXT NOT NULL DEFAULT '';

ALTER TABLE conversation_sessions
ADD COLUMN is_pinned INTEGER NOT NULL DEFAULT 0;

ALTER TABLE conversation_sessions
ADD COLUMN last_opened_at TEXT;

ALTER TABLE conversation_sessions
ADD COLUMN workspace_path TEXT;

CREATE INDEX IF NOT EXISTS idx_conversation_sessions_studio_activity
ON conversation_sessions(is_pinned DESC, archived, updated_at DESC);

CREATE INDEX IF NOT EXISTS idx_conversation_sessions_last_opened
ON conversation_sessions(last_opened_at DESC);

CREATE INDEX IF NOT EXISTS idx_conversation_sessions_workspace
ON conversation_sessions(workspace_path, updated_at DESC);
"""

MIGRATION_17 = """
CREATE TABLE IF NOT EXISTS studio_trust_settings (
    id TEXT PRIMARY KEY,
    mode TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_studio_trust_settings_updated
ON studio_trust_settings(updated_at DESC);
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
    if 8 not in applied_versions:
        connection.executescript(MIGRATION_8)
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (8, datetime.now(UTC).isoformat()),
        )
    if 9 not in applied_versions:
        connection.executescript(MIGRATION_9)
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (9, datetime.now(UTC).isoformat()),
        )
    if 10 not in applied_versions:
        connection.executescript(MIGRATION_10)
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (10, datetime.now(UTC).isoformat()),
        )
    if 11 not in applied_versions:
        connection.executescript(MIGRATION_11)
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (11, datetime.now(UTC).isoformat()),
        )
    if 12 not in applied_versions:
        connection.executescript(MIGRATION_12)
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (12, datetime.now(UTC).isoformat()),
        )
    if 13 not in applied_versions:
        connection.executescript(MIGRATION_13)
        connection.execute(
            "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (13, datetime.now(UTC).isoformat()),
        )
    if 14 not in applied_versions:
        connection.executescript(MIGRATION_14)
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (14, datetime.now(UTC).isoformat()),
        )
    if 15 not in applied_versions:
        connection.executescript(MIGRATION_15)
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (15, datetime.now(UTC).isoformat()),
        )
    if 16 not in applied_versions:
        connection.executescript(MIGRATION_16)
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (16, datetime.now(UTC).isoformat()),
        )
    if 17 not in applied_versions:
        connection.executescript(MIGRATION_17)
        connection.execute(
            "INSERT OR IGNORE INTO schema_migrations(version, applied_at) VALUES (?, ?)",
            (17, datetime.now(UTC).isoformat()),
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
