import re
from pathlib import Path

from typer.testing import CliRunner

from hephaestus.cli.main import app
from hephaestus.release import (
    ReleasePlanningOrchestrator,
    ReleasePlanningRequest,
    ReleasePlanRepository,
    ReleaseRecommendation,
    ReleaseRecommendationStatus,
    build_readiness_signals,
    generate_release_recommendation,
    readiness_score,
)
from hephaestus.repo import inspect_repository

runner = CliRunner()
FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "repos"


def test_release_planning_schemas_and_score(tmp_path) -> None:
    profile = inspect_repository(FIXTURE_ROOT / "python_uv").profile
    demo = ReleasePlanningOrchestrator(tmp_path / "hephaestus.db").plan(
        ReleasePlanningRequest(path=str(FIXTURE_ROOT / "python_uv"))
    )
    signals = build_readiness_signals(
        profile,
        demo.benchmark_result,
        pareto_requested=False,
        qubo_requested=False,
    )

    recommendation = ReleaseRecommendation(
        status=ReleaseRecommendationStatus.NEEDS_VALIDATION,
        summary="Validation has not run.",
        why=["commands are only detected"],
    )

    assert demo.request.preference == "balanced"
    assert demo.result.generated_tasks
    assert demo.result.validation_plan.command_texts
    assert demo.result.optimizer_run_id.startswith("run_")
    assert readiness_score(signals) <= 100
    assert recommendation.status == ReleaseRecommendationStatus.NEEDS_VALIDATION


def test_release_recommendation_generation_for_risky_repo(tmp_path) -> None:
    demo = ReleasePlanningOrchestrator(tmp_path / "hephaestus.db").plan(
        ReleasePlanningRequest(path=str(FIXTURE_ROOT / "node_next"), pareto=True, qubo=True)
    )
    recommendation = generate_release_recommendation(
        demo.repo_profile,
        demo.benchmark_result,
        demo.result.readiness_signals,
        evaluated=False,
    )

    assert recommendation.status == ReleaseRecommendationStatus.NEEDS_VALIDATION
    assert any("not executed" in reason for reason in recommendation.why)
    assert any(risk.requires_approval for risk in recommendation.risks)
    assert demo.result.pareto_frontier_ids
    assert demo.result.qubo_problem_ids


def test_release_orchestrator_persistence_roundtrip(tmp_path) -> None:
    database_path = tmp_path / "hephaestus.db"
    orchestrator = ReleasePlanningOrchestrator(database_path)
    demo = orchestrator.plan(
        ReleasePlanningRequest(
            path=str(FIXTURE_ROOT / "python_uv"),
            pareto=True,
            qubo=True,
            evaluate=True,
        )
    )
    repository = ReleasePlanRepository(database_path)

    loaded = repository.get_release_plan(demo.result.id)
    latest_for_profile = repository.latest_release_plan_for_repo_profile(demo.repo_profile.id)
    latest_for_path = repository.latest_release_plan_for_path(FIXTURE_ROOT / "python_uv")
    listed = repository.list_release_plans()

    assert loaded == demo.result
    assert latest_for_profile is not None
    assert latest_for_profile.id == demo.result.id
    assert latest_for_path is not None
    assert latest_for_path.id == demo.result.id
    assert listed[0].id == demo.result.id
    assert demo.result.optimizer_run_id.startswith("run_")
    assert demo.result.pareto_frontier_ids
    assert demo.result.qubo_problem_ids
    assert demo.result.outcome_ids
    assert demo.result.learning_signal_ids
    assert demo.result.decision_trace_ids


def test_release_cli_plan_list_show(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    fixture = FIXTURE_ROOT / "python_uv"

    plan_result = runner.invoke(app, ["release", "plan", str(fixture)])
    release_match = re.search(r"Saved release plan: (release_[a-f0-9]+)", plan_result.output)
    release_id = release_match.group(1) if release_match else ""
    run_match = re.search(r"Explain with: heph explain (run_[a-f0-9]+)", plan_result.output)

    list_result = runner.invoke(app, ["release", "list"])
    show_result = runner.invoke(app, ["release", "show", release_id])

    assert plan_result.exit_code == 0
    assert release_match is not None
    assert run_match is not None
    assert "Release Recommendation" in plan_result.output
    assert "needs_validation" in plan_result.output
    assert list_result.exit_code == 0
    assert release_id in list_result.output
    assert show_result.exit_code == 0
    assert "Inspect decision trace: heph explain" in show_result.output
    assert "View repo tasks: heph repo tasks" in show_result.output


def test_release_cli_complete_demo_flow(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    fixture = FIXTURE_ROOT / "python_uv"

    plan_result = runner.invoke(
        app,
        ["release", "plan", str(fixture), "--pareto", "--qubo", "--evaluate"],
    )
    release_match = re.search(r"Saved release plan: (release_[a-f0-9]+)", plan_result.output)
    release_id = release_match.group(1) if release_match else ""
    plan = ReleasePlanRepository(tmp_path / ".hephaestus" / "hephaestus.db").get_release_plan(
        release_id
    )

    assert plan_result.exit_code == 0
    assert release_match is not None
    assert plan is not None
    assert plan.optimizer_run_id.startswith("run_")
    assert plan.pareto_frontier_ids
    assert plan.qubo_problem_ids
    assert plan.outcome_ids
    assert plan.learning_signal_ids
    assert "Pareto" in plan_result.output
    assert "QUBO" in plan_result.output
    assert "Learn" in plan_result.output


def test_release_cli_uses_existing_repo_profile(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    fixture = FIXTURE_ROOT / "node_next"
    inspect_result = runner.invoke(app, ["repo", "inspect", str(fixture)])
    profile_match = re.search(r"Saved repo profile: (repo_[a-f0-9]+)", inspect_result.output)
    profile_id = profile_match.group(1) if profile_match else ""

    plan_result = runner.invoke(
        app,
        ["release", "plan", str(fixture), "--profile", profile_id],
    )

    assert inspect_result.exit_code == 0
    assert profile_match is not None
    assert plan_result.exit_code == 0
    assert f"Saved repo profile: {profile_id}" in plan_result.output
    assert "publish/deploy/destructive scripts require approval" in plan_result.output


def test_release_docs_commands_are_documented() -> None:
    root = Path(__file__).resolve().parents[1]
    readme = (root / "README.md").read_text(encoding="utf-8")
    demo = (root / "examples" / "release_plan_demo.md").read_text(encoding="utf-8")

    assert "heph release plan . --pareto --qubo --evaluate" in readme
    assert "heph release plan . --pareto --qubo --evaluate" in demo
    assert "heph release show <release_run_id>" in demo
