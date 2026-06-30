from pathlib import Path

from typer.testing import CliRunner

from hephaestus.cli.main import app
from hephaestus.release import ReleasePlanningOrchestrator, ReleasePlanningRequest
from hephaestus.validation import (
    VALIDATION_TESTS_FAILED,
    VALIDATION_TIMEOUT,
    ValidationCommand,
    ValidationCommandType,
    ValidationExecutionPlan,
    ValidationExecutor,
    ValidationPlanner,
    ValidationRepository,
    ValidationStatus,
    classify_validation_command_type,
)

runner = CliRunner()


def test_validation_schemas_and_command_type_detection() -> None:
    command = ValidationCommand(command="python -m pytest", command_type=ValidationCommandType.TEST)

    assert command.id.startswith("validation_cmd_")
    assert classify_validation_command_type("uv run ruff check .") == ValidationCommandType.LINT
    assert classify_validation_command_type("uv run mypy") == ValidationCommandType.TYPECHECK
    assert classify_validation_command_type("npm run build") == ValidationCommandType.BUILD
    assert classify_validation_command_type("cargo fmt --check") == ValidationCommandType.FORMAT_CHECK


def test_validation_plan_generation_from_repo_fixture(tmp_path: Path) -> None:
    fixture = Path(__file__).resolve().parent / "fixtures" / "repos" / "python_uv"
    plan = ValidationPlanner(tmp_path / "hephaestus.db").build_plan(
        fixture,
        use_latest_profile=False,
    )

    assert [command.command_type for command in plan.commands] == [
        ValidationCommandType.LINT,
        ValidationCommandType.TYPECHECK,
        ValidationCommandType.TEST,
    ]
    assert all(command.requires_approval for command in plan.commands)
    assert all(command.decision_trace_id for command in plan.commands)


def test_validation_dry_run_and_persistence(tmp_path: Path) -> None:
    repo = _python_repo(tmp_path)
    database_path = tmp_path / "hephaestus.db"

    suite = ValidationExecutor(database_path, workspace_path=repo).run(repo, dry_run=True)
    loaded = ValidationRepository(database_path).get_suite_result(suite.id)

    assert suite.status == ValidationStatus.SKIPPED
    assert suite.evidence_mode == "dry_run_no_execution"
    assert suite.skipped_count == len(suite.command_results)
    assert loaded == suite


def test_validation_executes_harmless_command_and_creates_outcomes(tmp_path: Path) -> None:
    repo = _python_repo(tmp_path)
    suite = ValidationExecutor(tmp_path / "hephaestus.db", workspace_path=repo).run(
        repo,
        yes=True,
    )

    assert suite.status == ValidationStatus.PASSED
    assert suite.pass_count == 1
    assert suite.outcome_ids
    assert suite.evidence[0].tool_action_id is not None
    assert suite.evidence[0].tool_execution_result_id is not None


def test_validation_failure_classification_and_learning_signal(tmp_path: Path) -> None:
    repo = _python_repo(tmp_path, failing=True)
    suite = ValidationExecutor(tmp_path / "hephaestus.db", workspace_path=repo).run(
        repo,
        yes=True,
    )

    assert suite.status == ValidationStatus.FAILED
    assert suite.fail_count == 1
    assert suite.evidence[0].failure is not None
    assert suite.evidence[0].failure.classification == VALIDATION_TESTS_FAILED
    assert suite.learning_signal_ids


def test_validation_timeout_behavior(tmp_path: Path) -> None:
    repo = tmp_path / "timeout_repo"
    repo.mkdir()
    plan = ValidationExecutionPlan(
        repo_path=str(repo),
        commands=[
            ValidationCommand(
                command='python -c "import time; time.sleep(2)"',
                command_type=ValidationCommandType.TEST,
                timeout_seconds=1,
            )
        ],
    )

    suite = ValidationExecutor(tmp_path / "hephaestus.db", workspace_path=repo).run(
        repo,
        plan=plan,
        yes=True,
    )

    assert suite.status == ValidationStatus.TIMED_OUT
    assert suite.timed_out_count == 1
    assert suite.evidence[0].failure is not None
    assert suite.evidence[0].failure.classification == VALIDATION_TIMEOUT


def test_release_plan_with_validation_evidence(tmp_path: Path) -> None:
    repo = _python_repo(tmp_path)
    demo = ReleasePlanningOrchestrator(tmp_path / "hephaestus.db").plan(
        ReleasePlanningRequest(
            path=str(repo),
            pareto=True,
            qubo=True,
            with_validation=True,
            validation_yes=True,
        )
    )

    assert demo.result.validation_result_id is not None
    assert demo.result.validation_summary is not None
    assert demo.result.evidence_mode == "real_validation_evidence"
    assert demo.result.validation_summary.status == ValidationStatus.PASSED
    assert demo.result.readiness_score >= 80


def test_release_plan_simulated_evaluate_still_works(tmp_path: Path) -> None:
    repo = _python_repo(tmp_path)
    demo = ReleasePlanningOrchestrator(tmp_path / "hephaestus.db").plan(
        ReleasePlanningRequest(path=str(repo), pareto=True, qubo=True, evaluate=True)
    )

    assert demo.result.validation_result_id is None
    assert demo.result.evidence_mode == "simulated_outcome_evaluation"
    assert demo.result.outcome_ids
    assert demo.result.learning_signal_ids


def test_validation_cli_smoke(tmp_path: Path, monkeypatch) -> None:
    repo = _python_repo(tmp_path)
    monkeypatch.chdir(tmp_path)

    plan = runner.invoke(app, ["validate", "plan", str(repo)])
    dry_run = runner.invoke(app, ["validate", "run", str(repo), "--dry-run"])
    run = runner.invoke(app, ["validate", "run", str(repo), "--yes"])
    results = runner.invoke(app, ["validate", "results"])
    latest = runner.invoke(app, ["validate", "latest", str(repo)])
    release = runner.invoke(
        app,
        ["release", "plan", str(repo), "--pareto", "--qubo", "--with-validation", "--yes"],
    )
    discuss = runner.invoke(
        app,
        [
            "discuss",
            "Can this repo be released?",
            "--repo",
            str(repo),
            "--provider",
            "local",
            "--propose-tools",
        ],
    )

    assert plan.exit_code == 0
    assert "Validation Execution Plan" in plan.output
    assert dry_run.exit_code == 0
    assert "dry_run_no_execution" in dry_run.output
    assert run.exit_code == 0
    assert "real_validation_evidence" in run.output
    assert results.exit_code == 0
    assert "Validation Runs" in results.output
    assert latest.exit_code == 0
    assert "Validation Result" in latest.output
    assert release.exit_code == 0
    assert "real_validation_evidence" in release.output
    assert discuss.exit_code == 0
    assert "validate" in discuss.output
    assert "plan" in discuss.output
    assert "--dry-run" in discuss.output
    assert "--yes" in discuss.output


def _python_repo(tmp_path: Path, *, failing: bool = False) -> Path:
    repo = tmp_path / ("python_fail" if failing else "python_pass")
    repo.mkdir()
    (repo / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                "name = 'validation-fixture'",
                "version = '0.1.0'",
                "dependencies = ['pytest>=8.2']",
                "",
                "[tool.pytest.ini_options]",
                "testpaths = ['tests']",
            ]
        ),
        encoding="utf-8",
    )
    tests_dir = repo / "tests"
    tests_dir.mkdir()
    body = "assert False\n" if failing else "assert True\n"
    (tests_dir / "test_sample.py").write_text(
        f"def test_sample() -> None:\n    {body}",
        encoding="utf-8",
    )
    return repo
