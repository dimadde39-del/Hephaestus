import re
from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from hephaestus.benchmarks.loader import load_benchmark
from hephaestus.benchmarks.runner import run_benchmark
from hephaestus.cli.main import app
from hephaestus.qubo.builder import QuboBuilder
from hephaestus.qubo.formulations import (
    formulate_budget_strategy,
    formulate_context_packing,
    formulate_model_selection,
)
from hephaestus.qubo.ising import qubo_to_ising
from hephaestus.qubo.repository import QuboRepository
from hephaestus.qubo.schemas import (
    BinaryVariable,
    QuboConstraintType,
    QuboObjective,
    QuboProblemType,
    QuboTerm,
)
from hephaestus.qubo.solver import solve_annealing, solve_exhaustive, solve_greedy
from hephaestus.storage import RunRecord, RunRepository

runner = CliRunner()
FIXTURE_DIR = Path(__file__).resolve().parents[1] / "benchmarks" / "task_graphs"


def test_qubo_schema_validation() -> None:
    variable = BinaryVariable(id="x_a", label="A")
    term = QuboTerm(variable_ids=("x_a",), coefficient=-1.0)

    assert variable.id == "x_a"
    assert term.coefficient == -1.0
    with pytest.raises(ValidationError):
        QuboTerm(variable_ids=("x_a", "x_b", "x_c"), coefficient=1.0)


def test_context_packing_formulation_variables_and_constraints() -> None:
    case = load_benchmark("context_overload", directory=FIXTURE_DIR)

    report = formulate_context_packing(case)
    problem = report.problem

    assert problem.problem_type == QuboProblemType.CONTEXT_PACKING
    assert len(problem.variables) == len(case.context_candidates)
    assert any(
        constraint.constraint_type == QuboConstraintType.TOKEN_BUDGET
        for constraint in problem.constraints
    )
    assert any(
        constraint.constraint_type == QuboConstraintType.REQUIRED_VARIABLES
        for constraint in problem.constraints
    )


def test_model_selection_formulation_exact_one_constraint() -> None:
    case = load_benchmark("model_quality_threshold", directory=FIXTURE_DIR)

    report = formulate_model_selection(case)
    problem = report.problem

    assert len(problem.variables) == 2
    assert any(
        constraint.constraint_type == QuboConstraintType.EXACTLY_ONE
        for constraint in problem.constraints
    )
    assert any(
        constraint.constraint_type == QuboConstraintType.QUALITY_THRESHOLD
        for constraint in problem.constraints
    )


def test_budget_strategy_formulation() -> None:
    case = load_benchmark("token_budget_pressure", directory=FIXTURE_DIR)

    report = formulate_budget_strategy(case)

    assert report.problem.problem_type == QuboProblemType.BUDGET_STRATEGY
    assert {variable.label for variable in report.problem.variables} == {
        "frugal",
        "balanced",
        "rich_context",
        "quality_guard",
        "critical_only",
    }


def test_exhaustive_solver_correctness_on_small_problem() -> None:
    builder = QuboBuilder(
        problem_type=QuboProblemType.BUDGET_STRATEGY,
        objective=QuboObjective(description="tiny test"),
    )
    builder.add_variable("x_a", label="A")
    builder.add_variable("x_b", label="B")
    builder.add_linear("x_a", -1.0)
    builder.add_linear("x_b", -2.0)
    builder.add_exactly_one(
        ["x_a", "x_b"],
        weight=5.0,
        description="choose one",
        constraint_id="choose_one",
    )
    solution = solve_exhaustive(builder.build())

    assert solution.feasible is True
    assert solution.selected_variables == ["x_b"]


def test_greedy_solver_returns_feasible_solution_where_possible() -> None:
    case = load_benchmark("model_quality_threshold", directory=FIXTURE_DIR)
    problem = formulate_model_selection(case).problem

    solution = solve_greedy(problem)

    assert solution.feasible is True
    assert len(solution.selected_variables) == 1


def test_annealing_solver_is_deterministic_with_seed() -> None:
    case = load_benchmark("model_quality_threshold", directory=FIXTURE_DIR)
    problem = formulate_model_selection(case).problem

    first = solve_annealing(problem, seed=123, iterations=100)
    second = solve_annealing(problem, seed=123, iterations=100)

    assert first.selected_variables == second.selected_variables
    assert first.objective_value == second.objective_value


def test_qubo_to_ising_conversion_expected_structure() -> None:
    builder = QuboBuilder(problem_type=QuboProblemType.BUDGET_STRATEGY)
    builder.add_variable("x_a", label="A")
    builder.add_variable("x_b", label="B")
    builder.constant_offset = 1.0
    builder.add_linear("x_a", 2.0)
    builder.add_quadratic("x_a", "x_b", 4.0)

    ising = qubo_to_ising(builder.build())
    linear = {term.variable_ids[0]: term.coefficient for term in ising.linear_terms}
    quadratic = {term.variable_ids: term.coefficient for term in ising.quadratic_terms}

    assert ising.constant_offset == 3.0
    assert linear == {"x_a": 2.0, "x_b": 1.0}
    assert quadratic == {("x_a", "x_b"): 1.0}


def test_qubo_persistence_roundtrip(tmp_path) -> None:
    database_path = tmp_path / "hephaestus.db"
    run = RunRepository(database_path).save_run(RunRecord(goal="QUBO", mode="test"))
    case = load_benchmark("model_quality_threshold", directory=FIXTURE_DIR)
    problem = formulate_model_selection(case, run_id=run.id).problem
    solution = solve_exhaustive(problem)
    repository = QuboRepository(database_path)

    repository.save_problem(problem)
    repository.save_solution(solution, problem)

    assert repository.get_problem(problem.id) == problem
    assert repository.get_latest_solution(problem.id) == solution
    assert repository.list_problems(run_id=run.id) == [problem]
    assert repository.list_solutions_for_problem(problem.id) == [solution]


def test_cli_qubo_formulate_list_show_solve_convert_and_compare(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    fixture = FIXTURE_DIR / "model_quality_threshold.json"

    formulated = runner.invoke(
        app,
        ["qubo", "formulate", str(fixture), "--type", "model_selection"],
    )
    problem_match = re.search(r"(qubo_[a-f0-9]+)", formulated.output)
    problem_id = problem_match.group(1) if problem_match else ""
    listed = runner.invoke(app, ["qubo", "list"])
    shown = runner.invoke(app, ["qubo", "show", problem_id])
    solved = runner.invoke(app, ["qubo", "solve", problem_id, "--solver", "exhaustive"])
    converted = runner.invoke(app, ["qubo", "convert-ising", problem_id])
    compared = runner.invoke(app, ["qubo", "compare", str(fixture)])

    assert formulated.exit_code == 0
    assert "QUBO Formulation" in formulated.output
    assert problem_match is not None
    assert listed.exit_code == 0
    assert problem_id in listed.output
    assert shown.exit_code == 0
    assert "QUBO Objective Terms" in shown.output
    assert solved.exit_code == 0
    assert "local/fake-quality-strong" in solved.output
    assert converted.exit_code == 0
    assert "Ising Problem" in converted.output
    assert compared.exit_code == 0
    assert "QUBO Comparison" in compared.output
    assert "model_selection" in compared.output


def test_benchmark_run_with_qubo_persists_and_reports(tmp_path) -> None:
    database_path = tmp_path / "hephaestus.db"
    repository = RunRepository(database_path)
    case = load_benchmark("model_quality_threshold", directory=FIXTURE_DIR)

    result = run_benchmark(case, repository=repository, qubo=True)

    assert result.run_id is not None
    assert result.qubo_comparisons
    assert "QUBO formulations:" in result.summary
    problems = QuboRepository(database_path).list_problems(run_id=result.run_id)
    assert len(problems) == len(result.qubo_comparisons)


def test_cli_benchmark_qubo_and_explain_integration(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    fixture = FIXTURE_DIR / "model_quality_threshold.json"

    benchmark = runner.invoke(app, ["benchmark", "run", str(fixture), "--qubo"])
    run_match = re.search(r"Saved run: (run_[a-f0-9]+)", benchmark.output)
    run_id = run_match.group(1) if run_match else ""
    explained = runner.invoke(app, ["explain", run_id])
    explained_summary = runner.invoke(app, ["explain", run_id, "--summary"])

    assert benchmark.exit_code == 0
    assert "QUBO Comparison" in benchmark.output
    assert run_match is not None
    assert explained.exit_code == 0
    assert "QUBO" in explained.output
    assert "model_selection" in explained.output
    assert explained_summary.exit_code == 0
    assert "QUBO Summary" in explained_summary.output
    assert "Feasible solutions count" in explained_summary.output
