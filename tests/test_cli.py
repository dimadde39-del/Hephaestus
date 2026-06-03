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


def test_cli_optimize_demo_smoke() -> None:
    demo_path = Path("examples/repo_release_demo.json")

    result = runner.invoke(app, ["optimize", str(demo_path)])

    assert result.exit_code == 0
    assert "Optimization" in result.output
    assert "Model Routing" in result.output
