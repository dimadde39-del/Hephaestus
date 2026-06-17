from datetime import UTC, datetime

from hephaestus.core.config import RiskLevel
from hephaestus.memory import MemoryItem, MemoryType
from hephaestus.safety.approval import ApprovalStatus
from hephaestus.storage import (
    ApprovalRecord,
    RunDecisionRecord,
    RunRecord,
    RunRepository,
    RunTaskRecord,
    SqliteMemoryRepository,
    connect_database,
    init_database,
)


def test_db_initialization_is_idempotent(tmp_path) -> None:
    database_path = tmp_path / "hephaestus.db"

    assert init_database(database_path) == database_path
    assert init_database(database_path) == database_path

    with connect_database(database_path) as connection:
        migration_count = connection.execute("SELECT count(*) FROM schema_migrations").fetchone()
        memory_table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'memories'"
        ).fetchone()
        trace_table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'decision_traces'"
        ).fetchone()
        pareto_table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'pareto_frontiers'"
        ).fetchone()
        qubo_table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'qubo_problems'"
        ).fetchone()
        repo_table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'repo_profiles'"
        ).fetchone()
        release_table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'release_plans'"
        ).fetchone()
        conversation_table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'conversation_sessions'"
        ).fetchone()
        strategic_memory_table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'strategic_memories'"
        ).fetchone()
        strategic_conflict_table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'strategic_memory_conflicts'"
        ).fetchone()
        strategic_recall_table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'strategic_memory_recalls'"
        ).fetchone()
        policy_settings_table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'policy_settings'"
        ).fetchone()
        tool_actions_table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'tool_actions'"
        ).fetchone()
        validation_plans_table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'validation_plans'"
        ).fetchone()
        coding_requests_table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'coding_requests'"
        ).fetchone()
        coding_results_table = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'coding_loop_results'"
        ).fetchone()
        conversation_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(conversation_sessions)")
        }

    assert migration_count[0] == 17
    assert memory_table[0] == "memories"
    assert trace_table[0] == "decision_traces"
    assert pareto_table[0] == "pareto_frontiers"
    assert qubo_table[0] == "qubo_problems"
    assert repo_table[0] == "repo_profiles"
    assert release_table[0] == "release_plans"
    assert conversation_table[0] == "conversation_sessions"
    assert strategic_memory_table[0] == "strategic_memories"
    assert strategic_conflict_table[0] == "strategic_memory_conflicts"
    assert strategic_recall_table[0] == "strategic_memory_recalls"
    assert policy_settings_table[0] == "policy_settings"
    assert tool_actions_table[0] == "tool_actions"
    assert validation_plans_table[0] == "validation_plans"
    assert coding_requests_table[0] == "coding_requests"
    assert coding_results_table[0] == "coding_loop_results"
    assert {
        "display_title",
        "is_pinned",
        "archived",
        "last_opened_at",
        "workspace_path",
        "repo_profile_id",
    }.issubset(conversation_columns)


def test_memory_persists_across_repository_instances(tmp_path) -> None:
    database_path = tmp_path / "hephaestus.db"
    verified_at = datetime(2026, 1, 2, 3, 4, tzinfo=UTC)
    item = MemoryItem(
        type=MemoryType.FAILURE,
        content="Persistent SQLite memory caught a validation failure.",
        summary="SQLite memory failure.",
        tags=["Tests", "sqlite", "tests"],
        project="hephaestus",
        confidence=0.95,
        importance=0.85,
        last_verified_at=verified_at,
        source="pytest",
    )

    SqliteMemoryRepository(database_path).add(item)
    repository = SqliteMemoryRepository(database_path)
    results = repository.retrieve_top("sqlite validation", project="hephaestus")

    assert len(results) == 1
    assert results[0].id == item.id
    assert results[0].tags == ["tests", "sqlite"]
    assert results[0].last_verified_at == verified_at
    assert results[0].source == "pytest"


def test_run_history_roundtrips_json_fields(tmp_path) -> None:
    database_path = tmp_path / "hephaestus.db"
    repository = RunRepository(database_path)
    run = repository.save_run(RunRecord(goal="Optimize benchmark", mode="optimize"))
    task = repository.save_run_task(
        RunTaskRecord(
            run_id=run.id,
            task_id="run-validation",
            title="Run validation",
            description="Run validation commands.",
            selected_order=1,
            priority=9,
            risk=0.2,
            expected_value=9.0,
            dependencies=["inspect-scripts"],
            required_capabilities=["shell", "testing"],
            requires_approval=True,
        )
    )
    decision = repository.save_decision(
        RunDecisionRecord(
            run_id=run.id,
            decision_type="model_route:run-validation",
            selected_option="local/fake-balanced",
            rejected_options=["local/fake-small: missing capabilities"],
            objective_score=0.82,
            estimated_cost=0.0,
            rationale="Selected a local model.",
        )
    )
    approval = repository.save_approval(
        ApprovalRecord(
            run_id=run.id,
            action_type="task",
            action_description="Run validation commands.",
            risk_level=RiskLevel.MEDIUM,
        )
    )
    repository.complete_run(
        run.id,
        estimated_input_tokens=1200,
        estimated_output_tokens=700,
        estimated_cost=0.0,
        objective_score=42.5,
        risk_score=0.2,
        summary="Run completed.",
    )

    detail = repository.get_run(run.id)

    assert detail is not None
    assert detail.run.status == "completed"
    assert detail.run.summary == "Run completed."
    assert detail.tasks[0] == task
    assert detail.tasks[0].dependencies == ["inspect-scripts"]
    assert detail.tasks[0].required_capabilities == ["shell", "testing"]
    assert detail.decisions[0] == decision
    assert detail.decisions[0].rejected_options == ["local/fake-small: missing capabilities"]
    assert detail.approvals[0] == approval
    assert detail.approvals[0].status == ApprovalStatus.PENDING
