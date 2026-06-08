import re
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from hephaestus.benchmarks.loader import load_benchmark
from hephaestus.benchmarks.runner import run_benchmark
from hephaestus.cli.main import app
from hephaestus.core.config import DEFAULT_CONFIG
from hephaestus.optimize.model_router import ModelRouteRequest
from hephaestus.pareto import (
    ParetoRepository,
    compute_frontier,
    generate_context_packing_candidates,
    generate_model_routing_candidates,
    generate_scheduler_candidates,
    get_preference_profile,
    is_dominated,
    rank_frontier,
    select_candidate,
)
from hephaestus.pareto.schemas import CandidateType, DecisionCandidate, ObjectiveVector
from hephaestus.storage import RunRecord, RunRepository

runner = CliRunner()
FIXTURE_DIR = Path(__file__).resolve().parents[1] / "benchmarks" / "task_graphs"


def test_objective_vector_validation() -> None:
    vector = ObjectiveVector(
        quality=0.8,
        cost=0.01,
        latency=0.2,
        risk=0.1,
        privacy=1.0,
        token_usage=500,
        confidence=0.82,
        safety=0.9,
        profile_alignment=0.7,
    )

    assert vector.value_for(get_preference_profile("balanced").priorities[0]) == 0.8
    with pytest.raises(ValidationError):
        ObjectiveVector(quality=1.2)


def test_dominance_and_frontier_computation() -> None:
    dominated = _candidate("dominated", quality=0.7, cost=2.0, safety=0.7, risk=0.3)
    dominant = _candidate("dominant", quality=0.8, cost=1.0, safety=0.8, risk=0.2)
    tradeoff = _candidate("tradeoff", quality=0.95, cost=3.0, safety=0.9, risk=0.15)

    assert is_dominated(dominated, dominant)
    assert not is_dominated(tradeoff, dominant)

    frontier = compute_frontier([dominated, dominant, tradeoff])

    assert [candidate.id for candidate in frontier] == ["dominant", "tradeoff"]


def test_preference_profile_ranking() -> None:
    cheap = _candidate("cheap", quality=0.72, cost=0.01, safety=0.82, risk=0.18)
    strong = _candidate("strong", quality=0.92, cost=0.5, safety=0.88, risk=0.12)

    frugal_ranked = rank_frontier([cheap, strong], get_preference_profile("frugal"))
    quality_ranked = rank_frontier([cheap, strong], get_preference_profile("quality_first"))

    assert frugal_ranked[0].candidate.id == "cheap"
    assert quality_ranked[0].candidate.id == "strong"


def test_model_routing_candidate_generation_and_selection() -> None:
    case = load_benchmark("model_quality_threshold", directory=FIXTURE_DIR)
    task = case.tasks[0]
    request = ModelRouteRequest(
        required_capabilities=task.required_capabilities,
        input_tokens=task.estimated_input_tokens,
        output_tokens=task.estimated_output_tokens,
        quality_threshold=case.quality_threshold,
        privacy_level=task.privacy_level,
        needs_json=True,
        profiles=case.model_profiles,
    )

    candidates = generate_model_routing_candidates(request, task_id=task.id)
    selection = select_candidate(candidates, get_preference_profile("balanced"))

    assert len(candidates) == 2
    assert any(
        candidate.label.endswith("local/fake-cheap-small")
        and not candidate.constraints_satisfied
        and any("quality" in violation for violation in candidate.violated_constraints)
        for candidate in candidates
    )
    assert selection.selected_candidate.label.endswith("local/fake-quality-strong")


def test_context_packing_candidate_generation() -> None:
    case = load_benchmark("context_overload", directory=FIXTURE_DIR)

    candidates = generate_context_packing_candidates(
        case.context_candidates,
        case.context_token_budget,
    )

    assert {candidate.metadata["strategy"] for candidate in candidates} == {
        "minimal",
        "balanced",
        "rich",
        "critical_only",
        "failure_memory_heavy",
    }
    rich = next(candidate for candidate in candidates if candidate.metadata["strategy"] == "rich")
    assert {"benchmark-principle", "quality-rule"}.issubset(
        set(rich.metadata["selected_context_ids"])
    )


def test_scheduler_candidate_comparison() -> None:
    case = load_benchmark("simple_release", directory=FIXTURE_DIR)

    candidates = generate_scheduler_candidates(case.tasks, DEFAULT_CONFIG.objective_weights)

    assert {candidate.label for candidate in candidates} == {"greedy", "annealing"}
    assert all(candidate.candidate_type == CandidateType.TASK_ORDER for candidate in candidates)
    assert all("order" in candidate.metadata for candidate in candidates)


def test_pareto_persistence_roundtrip(tmp_path) -> None:
    database_path = tmp_path / "hephaestus.db"
    run = RunRepository(database_path).save_run(RunRecord(goal="Pareto roundtrip", mode="test"))
    selection = select_candidate(
        [
            _candidate("cheap", quality=0.72, cost=0.01, safety=0.82, risk=0.18),
            _candidate("strong", quality=0.92, cost=0.5, safety=0.88, risk=0.12),
        ],
        get_preference_profile("balanced"),
        run_id=run.id,
        title="roundtrip frontier",
    )
    repository = ParetoRepository(database_path)

    repository.save_selection(selection)

    assert repository.get_selection(selection.frontier.id) == selection
    assert repository.get_frontier(selection.frontier.id) == selection.frontier
    assert repository.list_frontiers(run_id=run.id) == [selection.frontier]
    assert repository.list_candidates(selection.frontier.id) == selection.frontier.candidates


def test_cli_pareto_profiles_compare_list_and_show(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    fixture = FIXTURE_DIR / "model_quality_threshold.json"

    profiles = runner.invoke(app, ["pareto", "profiles"])
    compared = runner.invoke(app, ["pareto", "compare", str(fixture), "--preference", "balanced"])
    frontier_match = re.search(r"(frontier_[a-f0-9]+)", compared.output)
    frontier_id = frontier_match.group(1) if frontier_match else ""
    listed = runner.invoke(app, ["pareto", "list"])
    shown = runner.invoke(app, ["pareto", "show", frontier_id])

    assert profiles.exit_code == 0
    assert "Pareto Preference Profiles" in profiles.output
    assert "quality_first" in profiles.output
    assert compared.exit_code == 0
    assert "Pareto Candidates" in compared.output
    assert "Tradeoff" in compared.output
    assert frontier_match is not None
    assert listed.exit_code == 0
    assert frontier_id in listed.output
    assert shown.exit_code == 0
    assert "Dominance" in shown.output


def test_benchmark_run_with_pareto_persists_and_reports(tmp_path) -> None:
    database_path = tmp_path / "hephaestus.db"
    repository = RunRepository(database_path)
    case = load_benchmark("model_quality_threshold", directory=FIXTURE_DIR)

    result = run_benchmark(case, repository=repository, pareto=True)

    assert result.run_id is not None
    assert result.pareto_selections
    assert "Pareto frontiers:" in result.summary
    persisted = ParetoRepository(database_path).list_selections_by_run(result.run_id)
    assert {selection.frontier.id: selection for selection in persisted} == {
        selection.frontier.id: selection for selection in result.pareto_selections
    }


def test_cli_benchmark_pareto_and_explain_integration(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    fixture = FIXTURE_DIR / "model_quality_threshold.json"

    benchmark = runner.invoke(app, ["benchmark", "run", str(fixture), "--pareto"])
    run_match = re.search(r"Saved run: (run_[a-f0-9]+)", benchmark.output)
    run_id = run_match.group(1) if run_match else ""
    explained = runner.invoke(app, ["explain", run_id])
    explained_summary = runner.invoke(app, ["explain", run_id, "--summary"])

    assert benchmark.exit_code == 0
    assert "Pareto Frontier" in benchmark.output
    assert run_match is not None
    assert explained.exit_code == 0
    assert "Pareto Frontier" in explained.output
    assert "Tradeoff" in explained.output
    assert explained_summary.exit_code == 0
    assert "Pareto Summary" in explained_summary.output
    assert "Dominated candidates count" in explained_summary.output


def _candidate(
    candidate_id: str,
    *,
    quality: float,
    cost: float,
    safety: float,
    risk: float,
) -> DecisionCandidate:
    return DecisionCandidate(
        id=candidate_id,
        candidate_type=CandidateType.MODEL_ROUTE,
        label=candidate_id,
        objective_vector=ObjectiveVector(
            quality=quality,
            cost=cost,
            latency=cost,
            risk=risk,
            privacy=1.0,
            token_usage=cost * 1000,
            confidence=quality,
            safety=safety,
            profile_alignment=0.7,
        ),
        estimated_cost=cost,
        estimated_tokens=int(cost * 1000),
        rationale=f"{candidate_id} candidate",
    )
