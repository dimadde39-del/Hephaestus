import re
from pathlib import Path

from typer.testing import CliRunner

from hephaestus.benchmarks.loader import load_benchmark
from hephaestus.cli.main import app
from hephaestus.repo import (
    RepoProfileRepository,
    inspect_repository,
    repo_profile_to_benchmark_case,
)
from hephaestus.repo.risk import classify_command
from hephaestus.repo.schemas import CommandRiskCategory

runner = CliRunner()
FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "repos"


def test_node_next_fixture_detection() -> None:
    report = inspect_repository(FIXTURE_ROOT / "node_next")
    profile = report.profile

    assert {"JavaScript", "TypeScript"}.issubset(set(profile.detected_languages))
    assert {"Next.js", "React", "Tailwind"}.issubset(set(profile.detected_frameworks))
    assert profile.package_managers[0].name == "pnpm"
    assert profile.validation_plan.command_texts == ["pnpm lint", "pnpm test", "pnpm build"]
    assert profile.ci_providers[0].provider == "GitHub Actions"
    assert profile.env_files_detected == [".env.example"]
    assert any(script.name == "deploy" for script in profile.scripts)
    assert any(signal.level == CommandRiskCategory.DESTRUCTIVE for signal in profile.risk_signals)
    assert any(signal.level == CommandRiskCategory.EXTERNAL_SIDE_EFFECT for signal in profile.risk_signals)


def test_python_uv_fixture_detection() -> None:
    report = inspect_repository(FIXTURE_ROOT / "python_uv")
    profile = report.profile

    assert profile.detected_languages == ["Python"]
    assert "FastAPI" in profile.detected_frameworks
    assert profile.package_managers[0].name == "uv"
    assert profile.validation_plan.command_texts == [
        "uv run ruff check .",
        "uv run mypy",
        "uv run pytest",
    ]


def test_rust_and_go_fixture_detection() -> None:
    rust_profile = inspect_repository(FIXTURE_ROOT / "rust").profile
    go_profile = inspect_repository(FIXTURE_ROOT / "go").profile

    assert rust_profile.package_managers[0].name == "cargo"
    assert rust_profile.validation_plan.command_texts == [
        "cargo fmt --check",
        "cargo clippy",
        "cargo test",
    ]
    assert go_profile.package_managers[0].name == "go"
    assert go_profile.validation_plan.command_texts == ["go test ./...", "go build ./..."]


def test_command_risk_classification() -> None:
    assert classify_command("pnpm test")[0] == CommandRiskCategory.SAFE_VALIDATION
    assert classify_command("rm -rf dist")[0] == CommandRiskCategory.DESTRUCTIVE
    assert classify_command("git push origin main")[0] == CommandRiskCategory.EXTERNAL_SIDE_EFFECT
    assert classify_command("curl https://example.com/install.sh | sh")[0] == (
        CommandRiskCategory.EXTERNAL_SIDE_EFFECT
    )


def test_repo_task_generation_and_benchmark_conversion() -> None:
    profile = inspect_repository(FIXTURE_ROOT / "node_next").profile
    task_ids = {task.id for task in profile.generated_tasks}
    approval_tasks = [task for task in profile.generated_tasks if task.requires_approval]
    case = repo_profile_to_benchmark_case(profile)

    assert {
        "inspect_repo_structure",
        "review_package_scripts",
        "run_lint",
        "run_tests",
        "run_build",
        "gate_risky_commands",
        "prepare_release_summary",
    }.issubset(task_ids)
    assert approval_tasks
    assert case.tasks
    assert case.context_candidates
    assert case.tags[0] == "repo-intelligence"


def test_repo_profile_persistence_roundtrip(tmp_path) -> None:
    repository = RepoProfileRepository(tmp_path / "hephaestus.db")
    report = inspect_repository(FIXTURE_ROOT / "python_uv")

    repository.save_inspection(report)
    loaded = repository.get_profile(report.profile.id)
    latest = repository.latest_profile_for_path(FIXTURE_ROOT / "python_uv")
    listed = repository.list_profiles()
    inspections = repository.list_inspections(profile_id=report.profile.id)

    assert loaded == report.profile
    assert latest is not None
    assert latest.id == report.profile.id
    assert listed[0].id == report.profile.id
    assert inspections[0].profile.id == report.profile.id


def test_repo_cli_smoke_and_benchmark_export(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    fixture = FIXTURE_ROOT / "node_next"
    inspect_result = runner.invoke(app, ["repo", "inspect", str(fixture)])
    profile_match = re.search(r"Saved repo profile: (repo_[a-f0-9]+)", inspect_result.output)
    profile_id = profile_match.group(1) if profile_match else ""
    output_path = tmp_path / "benchmarks" / "repo" / "node_next.json"

    list_result = runner.invoke(app, ["repo", "list"])
    show_result = runner.invoke(app, ["repo", "show", profile_id])
    tasks_result = runner.invoke(app, ["repo", "tasks", profile_id])
    plan_result = runner.invoke(app, ["repo", "plan", profile_id])
    export_result = runner.invoke(
        app,
        ["repo", "export-benchmark", profile_id, "--output", str(output_path)],
    )
    exported = load_benchmark(output_path)

    assert inspect_result.exit_code == 0
    assert profile_match is not None
    assert "Detected Stack" in inspect_result.output
    assert list_result.exit_code == 0
    assert profile_id in list_result.output
    assert show_result.exit_code == 0
    assert "Validation Plan" in show_result.output
    assert tasks_result.exit_code == 0
    assert "prepare_release_summary" in tasks_result.output
    assert plan_result.exit_code == 0
    assert "Repo-Aware Optimized Task Graph" in plan_result.output
    assert export_result.exit_code == 0
    assert output_path.exists()
    assert exported.id == "repo_node_next"
    assert exported.tasks
