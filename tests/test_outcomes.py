import re
from pathlib import Path

from typer.testing import CliRunner

from hephaestus.benchmarks.loader import load_benchmark
from hephaestus.benchmarks.runner import run_benchmark
from hephaestus.cli.main import app
from hephaestus.core.config import RiskLevel
from hephaestus.decision import DecisionAlternative, DecisionMetric, DecisionTraceRepository
from hephaestus.decision.schemas import (
    ContextSelectionDecision,
    ModelRoutingDecision,
    SafetyDecision,
    metric,
)
from hephaestus.outcomes import (
    FailureMemoryDraft,
    LearningDirection,
    LearningSignal,
    LearningSignalType,
    OutcomeEvidence,
    OutcomeMetric,
    OutcomeRecord,
    OutcomeRepository,
    OutcomeStatus,
    PolicyArea,
    PolicyUpdateSuggestion,
    ReflectionRecord,
    evaluate_run_outcomes,
    reflect_run_outcomes,
)
from hephaestus.storage import RunRecord, RunRepository

runner = CliRunner()
FIXTURE_DIR = Path(__file__).resolve().parents[1] / "benchmarks" / "task_graphs"


def test_outcome_reflection_and_learning_schema_validation() -> None:
    outcome = OutcomeRecord(
        run_id="run_test",
        decision_trace_id="trace_test",
        status=OutcomeStatus.FAILURE,
        summary="Selected model missed the threshold.",
        metrics=[OutcomeMetric(name="quality_gap", value=0.12)],
        evidence=[
            OutcomeEvidence(
                evidence_type="benchmark_metric",
                source="pytest",
                content="quality 0.74 < threshold 0.86",
            )
        ],
        severity=0.8,
        confidence=0.9,
        tags=["Failure", "failure", "model"],
    )
    reflection = ReflectionRecord(
        outcome_id=outcome.id,
        run_id=outcome.run_id,
        decision_trace_id=outcome.decision_trace_id,
        what_failed="Model quality missed the threshold.",
        likely_cause="Routing strictness was too low.",
        recommended_change="Increase routing strictness.",
        confidence=0.82,
    )
    signal = LearningSignal(
        run_id=outcome.run_id,
        decision_trace_id=outcome.decision_trace_id,
        outcome_id=outcome.id,
        signal_type=LearningSignalType.MODEL_QUALITY,
        direction=LearningDirection.INCREASE,
        target="model_router.quality_threshold_guard",
        rationale="Failed quality threshold.",
        strength=0.85,
    )
    draft = FailureMemoryDraft(
        run_id=outcome.run_id,
        decision_trace_id=outcome.decision_trace_id,
        outcome_id=outcome.id,
        summary="Quality threshold failure.",
        content="A weak model was selected below threshold.",
        severity=0.8,
        suggested_memory_importance=0.8,
    )
    suggestion = PolicyUpdateSuggestion(
        run_id=outcome.run_id,
        decision_trace_id=outcome.decision_trace_id,
        outcome_id=outcome.id,
        policy_area=PolicyArea.MODEL_ROUTER,
        current_rule="Prefer cheapest valid model.",
        suggested_rule="Reject models below required quality before cost comparison.",
        rationale="Quality failed.",
    )

    assert outcome.tags == ["failure", "model"]
    assert reflection.outcome_id == outcome.id
    assert signal.status.value == "draft"
    assert draft.memory_type == "failure"
    assert suggestion.policy_area == PolicyArea.MODEL_ROUTER


def test_outcome_persistence_roundtrip_and_trace_link(tmp_path) -> None:
    database_path = tmp_path / "hephaestus.db"
    run_repository = RunRepository(database_path)
    trace_repository = DecisionTraceRepository(database_path)
    outcome_repository = OutcomeRepository(database_path)
    run = run_repository.save_run(RunRecord(goal="Outcome persistence", mode="test"))
    trace = trace_repository.save_trace(
        ModelRoutingDecision(
            run_id=run.id,
            selected_option="local/fake-weak",
            rationale="Synthetic weak route.",
            metrics=[
                metric("quality_threshold", 0.86),
                metric("selected_quality", 0.7),
            ],
            objective_score=0.7,
        )
    )
    outcome = outcome_repository.save_outcome(
        OutcomeRecord(
            run_id=run.id,
            decision_trace_id=trace.id,
            status=OutcomeStatus.FAILURE,
            summary="Selected quality was below threshold.",
            severity=0.8,
        )
    )
    reflection = outcome_repository.save_reflection(
        ReflectionRecord(
            outcome_id=outcome.id,
            run_id=run.id,
            decision_trace_id=trace.id,
            what_failed="Quality threshold missed.",
        )
    )
    signal = outcome_repository.save_learning_signal(
        LearningSignal(
            run_id=run.id,
            decision_trace_id=trace.id,
            outcome_id=outcome.id,
            signal_type=LearningSignalType.MODEL_QUALITY,
            direction=LearningDirection.INCREASE,
            target="model_router.quality_threshold_guard",
            rationale="Quality failed.",
        )
    )
    draft = outcome_repository.save_failure_memory_draft(
        FailureMemoryDraft(
            run_id=run.id,
            decision_trace_id=trace.id,
            outcome_id=outcome.id,
            summary="Quality failure.",
            content="The selected model missed the benchmark threshold.",
        )
    )
    suggestion = outcome_repository.save_policy_update_suggestion(
        PolicyUpdateSuggestion(
            run_id=run.id,
            decision_trace_id=trace.id,
            outcome_id=outcome.id,
            policy_area=PolicyArea.MODEL_ROUTER,
            current_rule="Route cheapest valid model.",
            suggested_rule="Reject below-threshold models first.",
            rationale="Quality failed.",
        )
    )

    linked_trace = trace_repository.get_trace(trace.id)

    assert outcome_repository.get_outcome(outcome.id) == outcome
    assert outcome_repository.list_outcomes_by_run(run.id) == [outcome]
    assert outcome_repository.list_outcomes_by_decision_trace(trace.id) == [outcome]
    assert outcome_repository.list_reflections(outcome_id=outcome.id) == [reflection]
    assert outcome_repository.list_learning_signals(outcome_id=outcome.id) == [signal]
    assert outcome_repository.list_failure_memory_drafts(outcome_id=outcome.id) == [draft]
    assert outcome_repository.list_policy_update_suggestions(outcome_id=outcome.id) == [suggestion]
    assert linked_trace is not None
    assert linked_trace.outcome_id == outcome.id
    assert linked_trace.failure_memory_id == draft.id
    assert linked_trace.policy_update_id == suggestion.id


def test_context_failure_creates_failure_memory_draft(tmp_path) -> None:
    database_path = tmp_path / "hephaestus.db"
    run_repository = RunRepository(database_path)
    trace_repository = DecisionTraceRepository(database_path)
    outcome_repository = OutcomeRepository(database_path)
    run = run_repository.save_run(RunRecord(goal="Context failure", mode="benchmark"))
    trace_repository.save_trace(
        ContextSelectionDecision(
            run_id=run.id,
            selected_option="noncritical-note",
            alternatives=[
                DecisionAlternative(
                    option_id="critical-policy",
                    rejection_reason="dropped under token pressure",
                    metrics=[DecisionMetric(name="critical", value=True)],
                )
            ],
            rationale="Synthetic context failure.",
            metrics=[
                metric("tokens_after", 600),
                metric("token_budget", 1000),
            ],
            objective_score=0.4,
        )
    )

    batch = evaluate_run_outcomes(
        run.id,
        repository=outcome_repository,
        trace_repository=trace_repository,
    )

    assert batch.outcomes[0].status == OutcomeStatus.FAILURE
    assert batch.failure_memory_drafts
    assert "critical" in batch.failure_memory_drafts[0].content.lower()


def test_quality_threshold_success_creates_positive_learning_signal(tmp_path) -> None:
    database_path = tmp_path / "hephaestus.db"
    repository = RunRepository(database_path)
    case = load_benchmark("model_quality_threshold", directory=FIXTURE_DIR)
    result = run_benchmark(case, repository=repository)
    assert result.run_id is not None

    batch = reflect_run_outcomes(
        result.run_id,
        repository=OutcomeRepository(database_path),
        trace_repository=DecisionTraceRepository(database_path),
    )

    signals = [
        signal
        for signal in batch.learning_signals
        if signal.signal_type == LearningSignalType.MODEL_QUALITY
    ]
    assert any(signal.direction == LearningDirection.PREFER for signal in signals)
    assert any(signal.target == "local/fake-quality-strong" for signal in signals)


def test_risky_action_without_approval_creates_policy_suggestion(tmp_path) -> None:
    database_path = tmp_path / "hephaestus.db"
    run_repository = RunRepository(database_path)
    trace_repository = DecisionTraceRepository(database_path)
    outcome_repository = OutcomeRepository(database_path)
    run = run_repository.save_run(RunRecord(goal="Safety failure", mode="test"))
    trace_repository.save_trace(
        SafetyDecision(
            run_id=run.id,
            selected_option="allowed: push release branch",
            rationale="Synthetic unsafe allow.",
            metrics=[
                metric("approval_required", False),
                metric("risk_level", RiskLevel.HIGH.value),
                metric("action", "push release branch"),
            ],
            objective_score=1.0,
            tags=["safety"],
        )
    )

    batch = reflect_run_outcomes(
        run.id,
        repository=outcome_repository,
        trace_repository=trace_repository,
    )

    assert batch.outcomes[0].status == OutcomeStatus.FAILURE
    assert batch.policy_update_suggestions
    assert batch.policy_update_suggestions[0].policy_area == PolicyArea.SAFETY


def test_cli_outcome_reflect_learn_and_explain_integration(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    fixture = FIXTURE_DIR / "model_quality_threshold.json"
    benchmark_result = runner.invoke(app, ["benchmark", "run", str(fixture), "--evaluate"])
    run_id_match = re.search(r"Saved run: (run_[a-f0-9]+)", benchmark_result.output)
    run_id = run_id_match.group(1) if run_id_match else ""
    database_path = tmp_path / ".hephaestus" / "hephaestus.db"
    traces = DecisionTraceRepository(database_path).list_traces(run_id=run_id)
    trace_id = traces[0].id if traces else ""

    outcome_add = runner.invoke(
        app,
        [
            "outcome",
            "add",
            trace_id,
            "--status",
            "success",
            "--summary",
            "Manual confirmation succeeded.",
        ],
    )
    outcome_id_match = re.search(r"Added outcome (outcome_[a-f0-9]+)", outcome_add.output)
    outcome_id = outcome_id_match.group(1) if outcome_id_match else ""
    outcome_list = runner.invoke(app, ["outcome", "list"])
    outcome_show = runner.invoke(app, ["outcome", "show", outcome_id])
    explain = runner.invoke(app, ["explain", run_id])
    explain_summary = runner.invoke(app, ["explain", run_id, "--summary"])
    reflect = runner.invoke(app, ["reflect", run_id])
    learn_signals = runner.invoke(app, ["learn", "signals"])
    learn_failures = runner.invoke(app, ["learn", "failures"])
    learn_policies = runner.invoke(app, ["learn", "policies"])

    assert benchmark_result.exit_code == 0
    assert run_id_match is not None
    assert "Outcome Learning Summary" in benchmark_result.output
    assert "Learning Signals" in benchmark_result.output
    assert outcome_add.exit_code == 0
    assert outcome_id_match is not None
    assert outcome_list.exit_code == 0
    assert "Outcomes" in outcome_list.output
    assert outcome_show.exit_code == 0
    assert "Manual confirmation succeeded." in outcome_show.output
    assert explain.exit_code == 0
    assert "Outcome Learning" in explain.output
    assert explain_summary.exit_code == 0
    assert "Outcome Learning Summary" in explain_summary.output
    assert reflect.exit_code == 0
    assert "Reflections" in reflect.output
    assert learn_signals.exit_code == 0
    assert "Learning Signals" in learn_signals.output
    assert learn_failures.exit_code == 0
    assert "Failure Memory Drafts" in learn_failures.output
    assert learn_policies.exit_code == 0
    assert "Policy Update Suggestions" in learn_policies.output
