import re
from pathlib import Path

from typer.testing import CliRunner

from hephaestus.cli.main import app

runner = CliRunner()


def test_cli_doctor_smoke() -> None:
    result = runner.invoke(app, ["doctor"])

    assert result.exit_code == 0
    assert "Hephaestus Doctor" in result.output


def test_cli_plan_smoke() -> None:
    result = runner.invoke(app, ["plan", "prepare this repo for release"])

    assert result.exit_code == 0
    assert "inspect-repository" in result.output
    assert "approval-before-commit" in result.output


def test_cli_optimize_demo_smoke(tmp_path, monkeypatch) -> None:
    demo_path = Path(__file__).resolve().parents[1] / "examples" / "repo_release_demo.json"

    monkeypatch.chdir(tmp_path)
    result = runner.invoke(app, ["optimize", str(demo_path)])

    assert result.exit_code == 0
    assert "Optimization" in result.output
    assert "Model Routing" in result.output
    assert "Saved run: run_" in result.output


def test_cli_db_memory_and_run_history_smoke(tmp_path, monkeypatch) -> None:
    demo_path = Path(__file__).resolve().parents[1] / "examples" / "repo_release_demo.json"

    monkeypatch.chdir(tmp_path)
    init_result = runner.invoke(app, ["db", "init"])
    path_result = runner.invoke(app, ["db", "path"])
    add_result = runner.invoke(
        app,
        [
            "memory",
            "add",
            "--type",
            "failure",
            "--content",
            "test persistent memory",
            "--tag",
            "persistent",
        ],
    )
    search_result = runner.invoke(app, ["memory", "search", "persistent"])
    list_result = runner.invoke(app, ["memory", "list"])
    optimize_result = runner.invoke(app, ["optimize", str(demo_path)])
    run_id_match = re.search(r"Saved run: (run_[a-f0-9]+)", optimize_result.output)
    run_id = run_id_match.group(1) if run_id_match else ""
    runs_result = runner.invoke(app, ["runs"])
    show_result = runner.invoke(app, ["run", "show", run_id])

    assert init_result.exit_code == 0
    assert "Initialized database" in init_result.output
    assert path_result.exit_code == 0
    assert ".hephaestus" in path_result.output
    assert add_result.exit_code == 0
    assert "Added failure memory" in add_result.output
    assert search_result.exit_code == 0
    assert "test persistent memory" in search_result.output
    assert list_result.exit_code == 0
    assert "Memory List" in list_result.output
    assert optimize_result.exit_code == 0
    assert run_id_match is not None
    assert runs_result.exit_code == 0
    assert run_id in runs_result.output
    assert show_result.exit_code == 0
    assert "Run Tasks" in show_result.output
    assert "Run Decisions" in show_result.output
