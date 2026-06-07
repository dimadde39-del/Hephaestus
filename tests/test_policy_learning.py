import re
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hephaestus.benchmarks.loader import load_benchmark
from hephaestus.benchmarks.runner import run_benchmark
from hephaestus.cli.main import app
from hephaestus.core.config import DEFAULT_CONFIG
from hephaestus.decision import DecisionTraceRepository, ModelRoutingDecision, metric
from hephaestus.models import fake_model_profiles
from hephaestus.optimize.context_packer import ContextCandidate, pack_context
from hephaestus.optimize.model_router import ModelRouteRequest, route_model
from hephaestus.outcomes import (
    LearningDirection,
    LearningSignal,
    LearningSignalType,
    OutcomeRecord,
    OutcomeRepository,
    OutcomeStatus,
)
from hephaestus.policy_learning import (
    AdjustmentOperation,
    DecisionArea,
    DecisionQualityProfile,
    ProfileAdjustment,
    ProfileApplicationResult,
    ProfileEvidence,
    ProfileEvidenceType,
    ProfileRule,
    ProfileRuleType,
    ProfileStatus,
    ProfileStore,
    apply_context_packer_profiles,
    apply_failure_memory_context_boost,
    apply_model_router_profiles,
    apply_scheduler_profiles,
    suggest_profiles,
)
from hephaestus.storage import RunRecord, RunRepository

runner = CliRunner()
FIXTURE_DIR = Path(__file__).resolve().parents[1] / "benchmarks" / "task_graphs"


def test_profile_schema_validation() -> None:
    profile = _model_router_profile(tags=["Quality", "quality"])

    assert profile.tags == ["quality"]
    assert profile.rules[0].decision_area == DecisionArea.MODEL_ROUTER

    with pytest.raises(ValueError):
        DecisionQualityProfile(
            name="bad",
            decision_area=DecisionArea.MODEL_ROUTER,
            rules=[
                ProfileRule(
                    decision_area=DecisionArea.SAFETY,
                    rule_type=ProfileRuleType.SAFETY_GATE,
                    target="safety.approval",
                )
            ],
        )


def test_profile_persistence_activation_archive_and_application(tmp_path) -> None:
    store = ProfileStore(tmp_path / "hephaestus.db")
    profile = store.save_profile(_model_router_profile())

    assert store.get_profile(profile.id) == profile
    assert store.list_profiles(status=ProfileStatus.DRAFT) == [profile]

    activated = store.activate_profile(profile.id)
    assert activated is not None
    assert activated.status == ProfileStatus.ACTIVE
    assert store.list_active_profiles() == [activated]

    application = store.record_profile_application(
        ProfileApplicationResult(
            profile_id=activated.id,
            profile_name=activated.name,
            decision_area=activated.decision_area,
            target="model_router",
            effect_summary="required_quality_threshold increased from 0.86 to 0.90",
            before={"quality_threshold": 0.86},
            after={"quality_threshold": 0.9},
        )
    )
    assert store.list_profile_applications(profile_id=activated.id) == [application]

    archived = store.archive_profile(profile.id)
    assert archived is not None
    assert archived.status == ProfileStatus.ARCHIVED
    assert store.list_active_profiles() == []


def test_profile_suggestion_from_learning_signals(tmp_path) -> None:
    database_path = tmp_path / "hephaestus.db"
    run_repository = RunRepository(database_path)
    trace_repository = DecisionTraceRepository(database_path)
    outcome_repository = OutcomeRepository(database_path)
    run = run_repository.save_run(RunRecord(goal="Profile suggestion", mode="test"))
    trace = trace_repository.save_trace(
        ModelRoutingDecision(
            run_id=run.id,
            selected_option="local/fake-small",
            rationale="Synthetic quality failure.",
            metrics=[metric("quality_threshold", 0.86), metric("selected_quality", 0.72)],
        )
    )
    outcome = outcome_repository.save_outcome(
        OutcomeRecord(
            run_id=run.id,
            decision_trace_id=trace.id,
            status=OutcomeStatus.FAILURE,
            summary="Cheap model missed quality threshold.",
            severity=0.85,
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
            rationale="Quality failed before cost should matter.",
            strength=0.9,
        )
    )

    evaluation = suggest_profiles(database_path=database_path)

    assert evaluation.profiles_created == 1
    profile = evaluation.profiles[0]
    assert profile.decision_area == DecisionArea.MODEL_ROUTER
    assert profile.status == ProfileStatus.DRAFT
    assert signal.id in profile.source_learning_signal_ids
    assert profile.rules[0].minimum_quality_score == 0.88


def test_active_model_router_profile_adjusts_quality_threshold() -> None:
    profile = _model_router_profile(status=ProfileStatus.ACTIVE)
    request = ModelRouteRequest(
        required_capabilities={"analysis"},
        input_tokens=1_600,
        output_tokens=900,
        quality_threshold=0.86,
        needs_json=True,
        profiles=fake_model_profiles(),
    )

    adjusted, applications = apply_model_router_profiles(request, [profile])
    route = route_model(adjusted)

    assert adjusted.quality_threshold == pytest.approx(0.9)
    assert route.profile.identifier == "local/fake-strong"
    assert applications[0].effect_summary == "required_quality_threshold increased from 0.86 to 0.90"


def test_active_context_profile_preserves_failure_context() -> None:
    profile = _context_profile()
    candidates = [
        ContextCandidate(
            id="critical-policy",
            relevance=0.9,
            importance=0.9,
            token_cost=250,
            critical=True,
        ),
        ContextCandidate(
            id="failure-memory",
            relevance=0.7,
            importance=0.5,
            token_cost=250,
            metadata={"memory_type": "failure", "tags": ["failure"]},
        ),
        ContextCandidate(
            id="summary",
            relevance=0.8,
            importance=0.3,
            token_cost=250,
        ),
    ]

    settings, applications = apply_context_packer_profiles([profile])
    result = pack_context(
        apply_failure_memory_context_boost(candidates, settings),
        500,
        preserve_critical_context=settings.preserve_critical_context,
        failure_memory_importance_boost=settings.failure_memory_importance_boost,
        compression_aggressiveness=settings.compression_aggressiveness,
    )

    assert settings.failure_memory_importance_boost == pytest.approx(0.15)
    assert [item.id for item in result.selected] == ["critical-policy", "failure-memory"]
    assert applications[0].decision_area == DecisionArea.CONTEXT_PACKER


def test_active_scheduler_profile_adjusts_objective_weights() -> None:
    profile = _scheduler_profile()

    weights, applications = apply_scheduler_profiles(DEFAULT_CONFIG.objective_weights, [profile])

    assert weights.dependency_violation_penalty == pytest.approx(35.0)
    assert weights.risk_penalty == pytest.approx(3.5)
    assert "dependency_violation_penalty" in applications[0].effect_summary


def test_benchmark_applies_active_profile_and_records_application(tmp_path) -> None:
    database_path = tmp_path / "hephaestus.db"
    store = ProfileStore(database_path)
    profile = store.save_profile(_model_router_profile())
    store.activate_profile(profile.id)
    repository = RunRepository(database_path)
    case = load_benchmark("model_quality_threshold", directory=FIXTURE_DIR)

    result = run_benchmark(case, repository=repository)

    assert result.run_id is not None
    assert profile.id in result.active_profile_ids
    assert result.profile_applications
    assert result.model_routes[0].required_quality_threshold == pytest.approx(0.9)
    assert store.list_profile_applications(run_id=result.run_id)


def test_cli_profile_flow_benchmark_and_explain(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    fixture = FIXTURE_DIR / "model_quality_threshold.json"

    evaluated = runner.invoke(app, ["benchmark", "run", str(fixture), "--evaluate"])
    suggest = runner.invoke(app, ["profile", "suggest"])
    profile_match = re.search(r"(profile_[a-f0-9]+)", suggest.output)
    profile_id = profile_match.group(1) if profile_match else ""
    listed = runner.invoke(app, ["profile", "list"])
    shown = runner.invoke(app, ["profile", "show", profile_id])
    activated = runner.invoke(app, ["profile", "activate", profile_id])
    active = runner.invoke(app, ["profile", "active"])
    demo = runner.invoke(app, ["profile", "apply-demo", profile_id])
    benchmark = runner.invoke(app, ["benchmark", "run", str(fixture)])
    run_match = re.search(r"Saved run: (run_[a-f0-9]+)", benchmark.output)
    run_id = run_match.group(1) if run_match else ""
    explained = runner.invoke(app, ["explain", run_id])
    explained_summary = runner.invoke(app, ["explain", run_id, "--summary"])
    archived = runner.invoke(app, ["profile", "archive", profile_id])

    assert evaluated.exit_code == 0
    assert suggest.exit_code == 0
    assert "Profiles Created" in suggest.output
    assert profile_match is not None
    assert listed.exit_code == 0
    assert "Decision Quality Profiles" in listed.output
    assert shown.exit_code == 0
    assert "Profile Rules" in shown.output
    assert activated.exit_code == 0
    assert "Activated profile" in activated.output
    assert active.exit_code == 0
    assert profile_id in active.output
    assert demo.exit_code == 0
    assert "Profile Applied" in demo.output
    assert benchmark.exit_code == 0
    assert "Profile Applications" in benchmark.output
    assert run_match is not None
    assert explained.exit_code == 0
    assert "Profile Applications" in explained.output
    assert explained_summary.exit_code == 0
    assert "Profile Applications Summary" in explained_summary.output
    assert archived.exit_code == 0
    assert "Archived profile" in archived.output


def _model_router_profile(
    *,
    tags: list[str] | None = None,
    status: ProfileStatus = ProfileStatus.DRAFT,
) -> DecisionQualityProfile:
    return DecisionQualityProfile(
        name="Model router quality guard",
        decision_area=DecisionArea.MODEL_ROUTER,
        status=status,
        rules=[
            ProfileRule(
                decision_area=DecisionArea.MODEL_ROUTER,
                rule_type=ProfileRuleType.QUALITY_THRESHOLD,
                target="model_router.quality_threshold_guard",
                minimum_quality_score=0.9,
                max_failure_rate=0.25,
                adjustments=[
                    ProfileAdjustment(
                        target="quality_threshold",
                        operation=AdjustmentOperation.INCREASE,
                        value=0.04,
                    )
                ],
            )
        ],
        evidence=[
            ProfileEvidence(
                evidence_type=ProfileEvidenceType.LEARNING_SIGNAL,
                source_id="signal_test",
                summary="Cheap model failed quality threshold.",
            )
        ],
        confidence=0.82,
        tags=tags or ["quality"],
    )


def _context_profile() -> DecisionQualityProfile:
    return DecisionQualityProfile(
        name="Context critical preservation guard",
        decision_area=DecisionArea.CONTEXT_PACKER,
        status=ProfileStatus.ACTIVE,
        rules=[
            ProfileRule(
                decision_area=DecisionArea.CONTEXT_PACKER,
                rule_type=ProfileRuleType.CONTEXT_PRESERVATION,
                target="context_packer.critical_context_policy",
                hard_constraint=True,
                adjustments=[
                    ProfileAdjustment(
                        target="failure_memory_importance",
                        operation=AdjustmentOperation.INCREASE,
                        value=0.15,
                    ),
                    ProfileAdjustment(
                        target="compression_aggressiveness",
                        operation=AdjustmentOperation.DECREASE,
                        value=0.1,
                    ),
                ],
            )
        ],
        confidence=0.8,
    )


def _scheduler_profile() -> DecisionQualityProfile:
    return DecisionQualityProfile(
        name="Scheduler dependency and risk guard",
        decision_area=DecisionArea.SCHEDULER,
        status=ProfileStatus.ACTIVE,
        rules=[
            ProfileRule(
                decision_area=DecisionArea.SCHEDULER,
                rule_type=ProfileRuleType.SCHEDULER_WEIGHT,
                target="scheduler.objective_weights",
                adjustments=[
                    ProfileAdjustment(
                        target="dependency_violation_penalty",
                        operation=AdjustmentOperation.INCREASE,
                        value=10.0,
                    ),
                    ProfileAdjustment(
                        target="risk_penalty",
                        operation=AdjustmentOperation.INCREASE,
                        value=0.5,
                    ),
                ],
            )
        ],
        confidence=0.8,
    )
