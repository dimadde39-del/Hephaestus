import sqlite3
from pathlib import Path

from typer.testing import CliRunner

from hephaestus.cli.main import app
from hephaestus.coding_loop import (
    CodingChangeProposal,
    CodingLoopExecutor,
    CodingLoopRepository,
    CodingLoopStatus,
    CodingPatch,
    CodingPatchReviewer,
    CodingPatchSet,
    CodingPlanner,
    CodingRequest,
    CodingRisk,
    CodingScopeType,
)
from hephaestus.policy import PolicyRepository
from hephaestus.tool_runtime import ToolRuntimeRepository

runner = CliRunner()


def test_coding_schemas() -> None:
    request = CodingRequest(repo_path=".", user_request="Update README wording.")

    assert request.id.startswith("coding_request_")
    assert CodingLoopStatus.PLANNED.value == "planned"
    assert CodingScopeType.DOCS.value == "docs"
    assert CodingRisk.LOW.value == "low"


def test_coding_planner_and_persistence(tmp_path: Path) -> None:
    repo = _python_repo(tmp_path)
    database_path = tmp_path / "hephaestus.db"

    request, plan = CodingPlanner(database_path).plan(
        "Update README intro to mention validation-backed release evidence.",
        repo_path=repo,
    )
    loaded = CodingLoopRepository(database_path).latest_plan_for_request(request.id)

    assert plan.scope.scope_type == CodingScopeType.DOCS
    assert plan.scope.risk == CodingRisk.LOW
    assert "README.md" in plan.likely_files
    assert plan.validation_commands
    assert plan.patch_proposal_possible is True
    assert loaded == plan


def test_oversized_scope_detection(tmp_path: Path) -> None:
    repo = _python_repo(tmp_path)
    _request, plan = CodingPlanner(tmp_path / "hephaestus.db").plan(
        "Rewrite the entire architecture across all files.",
        repo_path=repo,
    )

    assert plan.scope_too_large is True
    assert plan.status == CodingLoopStatus.SCOPE_TOO_LARGE
    assert plan.patch_proposal_possible is False


def test_deterministic_docs_patch_proposal_and_review(tmp_path: Path) -> None:
    repo = _python_repo(tmp_path)
    executor = CodingLoopExecutor(tmp_path / "hephaestus.db")

    _request, plan, change = executor.propose(
        "Update README intro to mention validation-backed release evidence.",
        repo_path=repo,
    )
    review = CodingPatchReviewer(tmp_path / "hephaestus.db").review(plan, change)

    assert change.patch_set.patch_ids
    assert "validation-backed release evidence" in change.patch_set.diff.lower()
    assert review.approved is True
    assert review.blocked is False
    assert review.decision_trace_id is not None


def test_patch_apply_checkpoint_validation_success_and_outcomes(tmp_path: Path) -> None:
    repo = _python_repo(tmp_path)
    original = (repo / "README.md").read_text(encoding="utf-8")
    executor = CodingLoopExecutor(tmp_path / "hephaestus.db")
    _request, _plan, change = executor.propose(
        "Update README intro to mention validation-backed release evidence.",
        repo_path=repo,
    )

    result = executor.apply_change(change.id, yes=True)

    assert result.status == CodingLoopStatus.COMPLETED
    assert result.checkpoint_ids
    assert result.validation.status == "passed"
    assert result.outcome_ids
    assert result.decision_trace_ids
    assert (repo / "README.md").read_text(encoding="utf-8") != original


def test_rollback_on_validation_failure_creates_learning_signal(tmp_path: Path) -> None:
    repo = _python_repo(tmp_path, failing=True)
    original = (repo / "README.md").read_text(encoding="utf-8")
    executor = CodingLoopExecutor(tmp_path / "hephaestus.db")

    result = executor.run(
        "Update README intro to mention validation-backed release evidence.",
        repo_path=repo,
        yes=True,
        rollback_on_failure=True,
    )

    assert result.status == CodingLoopStatus.ROLLED_BACK
    assert result.checkpoint_ids
    assert result.validation.status == "failed"
    assert result.learning_signal_ids
    assert (repo / "README.md").read_text(encoding="utf-8") == original


def test_coding_loop_results_and_show(tmp_path: Path) -> None:
    repo = _python_repo(tmp_path)
    repository = CodingLoopRepository(tmp_path / "hephaestus.db")
    result = CodingLoopExecutor(tmp_path / "hephaestus.db").run(
        "Update README intro to mention validation-backed release evidence.",
        repo_path=repo,
        dry_run=True,
    )

    results = repository.list_results()
    detail = repository.show_result(result.request_id)

    assert results[0].id == result.id
    assert detail.request is not None
    assert detail.plan is not None
    assert detail.change is not None
    assert detail.result == result


def test_policy_profile_aware_planning_and_no_approval_spam(tmp_path: Path) -> None:
    repo = _python_repo(tmp_path)
    database_path = tmp_path / "hephaestus.db"
    PolicyRepository(database_path).set_active_profile("research")

    _request, plan = CodingPlanner(database_path).plan(
        "Update README intro to mention validation-backed release evidence.",
        repo_path=repo,
    )

    assert plan.active_policy_profile == "research"
    with sqlite3.connect(database_path) as connection:
        row = connection.execute("SELECT COUNT(*) FROM tool_approvals").fetchone()
    assert row is not None
    assert row[0] == 0


def test_protected_file_review_blocks() -> None:
    change = CodingChangeProposal(
        request_id="coding_request_test",
        plan_id="coding_plan_test",
        repo_path=".",
        summary="Unsafe proposal",
        risk=CodingRisk.LOW,
        scope_type=CodingScopeType.DOCS,
        patch_set=CodingPatchSet(
            patches=[CodingPatch(path=".env", diff="+SECRET_TOKEN=abc123")],
            files_touched=[".env"],
            diff="+SECRET_TOKEN=abc123",
            patch_ids=["patch_test"],
        ),
    )
    request = CodingRequest(repo_path=".", user_request="Update .env", requested_scope=CodingScopeType.DOCS)
    planner = CodingPlanner()
    plan = planner.build_plan(request.model_copy(update={"repo_path": str(Path(".").resolve())}), persist=False)

    review = CodingPatchReviewer().review(plan.model_copy(update={"likely_files": [".env"]}), change)

    assert review.blocked is True
    assert ".env" in review.protected_files


def test_coding_cli_smoke_and_conversation_propose_code(tmp_path: Path, monkeypatch) -> None:
    repo = _python_repo(tmp_path)
    monkeypatch.chdir(tmp_path)

    plan = runner.invoke(
        app,
        [
            "code",
            "plan",
            "Update README intro to mention validation-backed release evidence.",
            "--repo",
            str(repo),
        ],
    )
    propose = runner.invoke(
        app,
        [
            "code",
            "propose",
            "Update README intro to mention validation-backed release evidence.",
            "--repo",
            str(repo),
        ],
    )
    run = runner.invoke(
        app,
        [
            "code",
            "run",
            "Update README intro to mention validation-backed release evidence.",
            "--repo",
            str(repo),
            "--dry-run",
        ],
    )
    results = runner.invoke(app, ["code", "results"])
    discuss = runner.invoke(
        app,
        [
            "discuss",
            "Propose a small safe README improvement.",
            "--repo",
            str(repo),
            "--provider",
            "local",
            "--propose-code",
        ],
    )

    assert plan.exit_code == 0
    assert "Repo-Aware Coding Plan" in plan.output
    assert propose.exit_code == 0
    assert "Patch Proposal" in propose.output
    assert run.exit_code == 0
    assert "dry-run only" in run.output.lower()
    assert results.exit_code == 0
    assert "Coding Loop Results" in results.output
    assert discuss.exit_code == 0
    assert "Proposed Coding Loop" in discuss.output
    assert "heph code propose" in discuss.output


def test_patch_apply_through_tool_runtime_checkpoint(tmp_path: Path) -> None:
    repo = _python_repo(tmp_path)
    executor = CodingLoopExecutor(tmp_path / "hephaestus.db")
    _request, _plan, change = executor.propose(
        "Update README intro to mention validation-backed release evidence.",
        repo_path=repo,
    )
    result = executor.apply_change(change.id, yes=True, no_validate=True)

    checkpoint = ToolRuntimeRepository(tmp_path / "hephaestus.db").get_checkpoint(
        result.checkpoint_ids[0]
    )

    assert result.status == CodingLoopStatus.COMPLETED
    assert checkpoint is not None
    assert checkpoint.files_touched == ["README.md"]


def _python_repo(tmp_path: Path, *, failing: bool = False) -> Path:
    repo = tmp_path / ("coding_fail" if failing else "coding_pass")
    repo.mkdir()
    (repo / "README.md").write_text(
        "Hephaestus is a self-improving AI agent.\n",
        encoding="utf-8",
    )
    (repo / "pyproject.toml").write_text(
        "\n".join(
            [
                "[project]",
                "name = 'coding-loop-fixture'",
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
