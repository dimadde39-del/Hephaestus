import json
from pathlib import Path

from typer.testing import CliRunner

from hephaestus.benchmarks.loader import load_benchmark
from hephaestus.benchmarks.reporter import results_to_json
from hephaestus.benchmarks.runner import (
    calculate_score_delta,
    calculate_score_delta_percent,
    calculate_token_savings_percent,
    critical_context_included,
    run_all_benchmarks,
    run_benchmark,
)
from hephaestus.cli.main import app
from hephaestus.decision import DecisionTraceRepository
from hephaestus.optimize.context_packer import ContextCandidate
from hephaestus.storage import RunRepository

runner = CliRunner()
FIXTURE_DIR = Path(__file__).resolve().parents[1] / "benchmarks" / "task_graphs"


def test_benchmark_fixture_loading_by_id_and_path() -> None:
    by_id = load_benchmark("simple_release", directory=FIXTURE_DIR)
    by_path = load_benchmark(FIXTURE_DIR / "simple_release.json")

    assert by_id.id == "simple_release"
    assert by_path.id == "simple_release"
    assert by_id.title == "Simple Release"
    assert by_id.tasks


def test_running_single_benchmark_without_persistence() -> None:
    case = load_benchmark("simple_release", directory=FIXTURE_DIR)

    result = run_benchmark(case, persist=False)

    assert result.run_id is None
    assert result.scheduler.best_scheduler in {"greedy", "annealing"}
    assert result.context.tokens_before > result.context.tokens_after
    assert result.quality_preserved is True
    assert result.decision_count > 0
    assert result.top_decision_type
    assert result.token_savings_summary.startswith("saved ")


def test_running_all_benchmarks_without_persistence() -> None:
    results = run_all_benchmarks(directory=FIXTURE_DIR, persist=False)

    assert len(results) == 7
    assert {result.case.id for result in results} >= {
        "approval_gate_pressure",
        "context_overload",
        "dependency_trap",
        "model_quality_threshold",
        "risky_refactor",
        "simple_release",
        "token_budget_pressure",
    }


def test_report_calculation_helpers() -> None:
    assert calculate_score_delta(50.0, 60.0) == 10.0
    assert calculate_score_delta_percent(50.0, 10.0) == 20.0
    assert calculate_score_delta_percent(0.0, 10.0) == 0.0
    assert calculate_token_savings_percent(1000, 400) == 60.0

    critical = ContextCandidate(
        id="critical",
        relevance=1.0,
        importance=1.0,
        token_cost=200,
        critical=True,
    )
    selected = [critical]
    assert critical_context_included([critical], selected, token_budget=400) is True


def test_model_rejection_due_to_quality_threshold() -> None:
    case = load_benchmark("model_quality_threshold", directory=FIXTURE_DIR)

    result = run_benchmark(case, persist=False)
    route = result.model_routes[0]

    assert route.selected_model == "local/fake-quality-strong"
    assert route.selected_quality is not None
    assert route.selected_quality >= 0.86
    assert any(
        rejected.identifier == "local/fake-cheap-small" and "quality" in rejected.reason
        for rejected in route.rejected_models
    )


def test_critical_context_inclusion() -> None:
    case = load_benchmark("context_overload", directory=FIXTURE_DIR)

    result = run_benchmark(case, persist=False)

    assert result.context.critical_items_included is True
    assert {"benchmark-principle", "quality-rule"}.issubset(result.context.selected_context_ids)
    assert result.context.token_savings_percent > 50.0


def test_dependency_violation_counting() -> None:
    case = load_benchmark("dependency_trap", directory=FIXTURE_DIR)

    result = run_benchmark(case, persist=False)

    assert result.scheduler.greedy_dependency_violations >= 1
    assert result.scheduler.annealing_dependency_violations >= 1


def test_benchmark_run_persisted_to_sqlite(tmp_path) -> None:
    repository = RunRepository(tmp_path / "hephaestus.db")
    case = load_benchmark("approval_gate_pressure", directory=FIXTURE_DIR)

    result = run_benchmark(case, repository=repository)

    assert result.run_id is not None
    assert result.decision_count > 0
    assert result.top_decision_type
    assert result.top_decision_rationale
    assert result.token_savings_summary
    detail = repository.get_run(result.run_id)
    traces = DecisionTraceRepository(tmp_path / "hephaestus.db").list_traces(
        run_id=result.run_id
    )
    assert detail is not None
    assert detail.run.mode == "benchmark"
    assert detail.run.status == "completed"
    assert len(detail.tasks) == len(case.tasks)
    assert len(detail.approvals) == 2
    assert len(traces) == result.decision_count
    assert {decision.decision_type for decision in detail.decisions} >= {
        "scheduler_greedy",
        "scheduler_annealing",
        "scheduler_comparison",
        "context_packing",
        "quality_guard",
        "token_budget",
    }


def test_results_to_json() -> None:
    case = load_benchmark("simple_release", directory=FIXTURE_DIR)
    result = run_benchmark(case, persist=False)

    payload = results_to_json([result])

    assert '"simple_release"' in payload
    assert '"quality_preserved": true' in payload


def test_cli_benchmark_list_smoke() -> None:
    result = runner.invoke(app, ["benchmark", "list"])

    assert result.exit_code == 0
    assert "Benchmark Fixtures" in result.output
    assert "simple_release" in result.output


def test_cli_benchmark_run_single_smoke(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    fixture = FIXTURE_DIR / "simple_release.json"

    result = runner.invoke(app, ["benchmark", "run", str(fixture)])

    assert result.exit_code == 0
    assert "Benchmark: simple_release" in result.output
    assert "Decision Trace" in result.output
    assert "Top Type" in result.output
    assert "Saved run: run_" in result.output


def test_cli_benchmark_run_json_smoke(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["benchmark", "run", "model_quality_threshold", "--json"])

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload[0]["case"]["id"] == "model_quality_threshold"
    assert payload[0]["model_routes"][0]["selected_model"] == "local/fake-quality-strong"
    assert payload[0]["top_decision_type"]


def test_cli_benchmark_run_all_smoke(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["benchmark", "run"])

    assert result.exit_code == 0
    assert "Benchmark: simple_release" in result.output
    assert "Benchmark: approval_gate_pressure" in result.output
    assert "Saved run: run_" in result.output
