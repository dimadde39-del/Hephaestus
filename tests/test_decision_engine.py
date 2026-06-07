import re
from pathlib import Path

from typer.testing import CliRunner

from hephaestus.benchmarks.loader import load_benchmark
from hephaestus.cli.main import app
from hephaestus.core.config import DEFAULT_CONFIG
from hephaestus.decision import (
    DecisionAlternative,
    DecisionMetric,
    DecisionTraceBuilder,
    DecisionTraceRepository,
    DecisionType,
    aggregate_decision_stats,
    build_budget_decision,
    build_context_selection_decision,
    build_model_routing_decision,
    build_optimization_decision,
    build_task_selection_decision,
    render_run_explanation,
    summarize_decisions,
)
from hephaestus.models import fake_model_profiles
from hephaestus.optimize.context_packer import pack_context
from hephaestus.optimize.model_router import ModelRouteRequest, route_model
from hephaestus.optimize.task_scheduler import compare_schedulers
from hephaestus.optimize.token_firewall import TokenBudget, evaluate_budget
from hephaestus.storage import RunRecord, RunRepository

runner = CliRunner()
FIXTURE_DIR = Path(__file__).resolve().parents[1] / "benchmarks" / "task_graphs"


def test_decision_trace_schema_validation() -> None:
    alternative = DecisionAlternative(
        option_id="local/fake-cheap-small",
        score=0.72,
        rejection_reason="quality threshold violation",
        violated_constraints=["quality threshold"],
        metrics=[DecisionMetric(name="required_quality", value=0.86)],
        would_have_cost=0.001,
        expected_quality=0.72,
        risk=0.28,
    )

    assert alternative.option_id == "local/fake-cheap-small"
    assert alternative.violated_constraints == ["quality threshold"]
    assert alternative.metrics[0].name == "required_quality"


def test_decision_creation_from_scheduler_comparison() -> None:
    case = load_benchmark("dependency_trap", directory=FIXTURE_DIR)
    comparison = compare_schedulers(case.tasks, DEFAULT_CONFIG.objective_weights)
    builder = DecisionTraceBuilder("run_test")

    optimization = builder.optimization(comparison)
    task_selection = builder.task_selection(
        comparison,
        parent_id=optimization.id,
    )

    assert optimization.decision_type == DecisionType.OPTIMIZATION
    assert task_selection.decision_type == DecisionType.TASK_SELECTION
    assert task_selection.parent_id == optimization.id
    assert task_selection.selected_option
    assert task_selection.alternatives
    assert task_selection.metric_map["selected_task_count"] == len(case.tasks)
    assert "task_order_outcome" in task_selection.learning_hooks
    assert task_selection.outcome_id is None
    assert task_selection.failure_memory_id is None
    assert task_selection.policy_update_id is None


def test_model_context_and_budget_builders_generate_structured_traces() -> None:
    case = load_benchmark("model_quality_threshold", directory=FIXTURE_DIR)
    task = case.tasks[0]
    profiles = case.model_profiles or fake_model_profiles()
    route_request = ModelRouteRequest(
        required_capabilities=task.required_capabilities,
        input_tokens=task.estimated_input_tokens,
        output_tokens=task.estimated_output_tokens,
        quality_threshold=case.quality_threshold,
        privacy_level=task.privacy_level,
        needs_tools=bool(task.allowed_tools),
        needs_json=True,
        profiles=profiles,
    )
    route = route_model(route_request)
    model_trace = build_model_routing_decision("run_test", route_request, route, task_id=task.id)
    context_result = pack_context(case.context_candidates, case.context_token_budget)
    context_trace = build_context_selection_decision(
        "run_test",
        case.context_candidates,
        context_result,
        case.context_token_budget,
    )
    budget = TokenBudget(
        max_input_tokens=task.estimated_input_tokens + 100,
        max_output_tokens=task.estimated_output_tokens + 100,
        max_cost=1.0,
        quality_threshold=case.quality_threshold,
    )
    budget_evaluation = evaluate_budget(
        input_tokens=task.estimated_input_tokens,
        output_tokens=task.estimated_output_tokens,
        selected_model=route.profile,
        selected_quality=route.quality,
        budget=budget,
    )
    budget_trace = build_budget_decision("run_test", budget_evaluation, budget)

    assert model_trace.decision_type == DecisionType.MODEL_ROUTING
    assert model_trace.alternatives[0].option_id
    assert model_trace.alternatives[0].rejection_reason
    assert model_trace.metric_map["quality_threshold"] == case.quality_threshold
    assert "model_quality_outcome" in model_trace.learning_hooks
    assert context_trace.decision_type == DecisionType.CONTEXT_SELECTION
    assert context_trace.metric_map["token_budget"] == case.context_token_budget
    assert all(alternative.option_id for alternative in context_trace.alternatives)
    assert budget_trace.decision_type == DecisionType.BUDGET
    assert budget_trace.metric_map["within_token_budget"] is True


def test_decision_persistence_filtering_and_tree_roundtrip(tmp_path) -> None:
    database_path = tmp_path / "hephaestus.db"
    run_repository = RunRepository(database_path)
    trace_repository = DecisionTraceRepository(database_path)
    run = run_repository.save_run(RunRecord(goal="Trace a run", mode="test"))
    case = load_benchmark("simple_release", directory=FIXTURE_DIR)
    comparison = compare_schedulers(case.tasks, DEFAULT_CONFIG.objective_weights)
    optimization = build_optimization_decision(run.id, comparison)
    task_selection = build_task_selection_decision(
        run.id,
        comparison,
        parent_id=optimization.id,
    )

    trace_repository.save_traces([optimization, task_selection])

    traces = trace_repository.list_traces(run_id=run.id)
    task_traces = trace_repository.list_traces(
        run_id=run.id,
        decision_type=DecisionType.TASK_SELECTION,
    )
    fetched = trace_repository.get_trace(optimization.id)
    tree = trace_repository.get_trace_tree(run.id)
    explanation = render_run_explanation(run.id, traces)
    summary = summarize_decisions(traces)
    stats = aggregate_decision_stats(traces)

    assert len(traces) == 2
    assert task_traces == [task_selection]
    assert fetched == optimization
    assert len(tree) == 1
    assert tree[0].decision == optimization
    assert tree[0].children[0].decision == task_selection
    assert "## Task Selection Decisions" in explanation
    assert summary.total_decisions == 2
    assert summary.task_decisions == 1
    assert summary.average_confidence > 0
    assert stats.total_traces == 2
    assert trace_repository.list_traces_by_run(run.id) == traces
    assert trace_repository.list_traces_by_type(DecisionType.OPTIMIZATION) == [optimization]


def test_cli_explain_full_summary_and_stats(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    fixture = FIXTURE_DIR / "model_quality_threshold.json"
    benchmark_result = runner.invoke(app, ["benchmark", "run", str(fixture)])
    run_id_match = re.search(r"Saved run: (run_[a-f0-9]+)", benchmark_result.output)
    run_id = run_id_match.group(1) if run_id_match else ""

    explain_result = runner.invoke(app, ["explain", run_id])
    summary_result = runner.invoke(app, ["explain", run_id, "--summary"])
    stats_result = runner.invoke(app, ["explain", "stats"])

    assert benchmark_result.exit_code == 0
    assert run_id_match is not None
    assert explain_result.exit_code == 0
    assert "Model Routing Decisions" in explain_result.output
    assert "quality" in explain_result.output
    assert summary_result.exit_code == 0
    assert "Decision Summary" in summary_result.output
    assert "Decisions By Type" in summary_result.output
    assert stats_result.exit_code == 0
    assert "Decision Statistics" in stats_result.output
    assert "Most Common Selected Models" in stats_result.output
