"""Analysis helpers for QUBO formulation, solving, and comparison."""

from __future__ import annotations

from collections.abc import Sequence

from hephaestus.benchmarks.schemas import BenchmarkCase
from hephaestus.decision.schemas import DecisionAlternative, OptimizationDecision, metric
from hephaestus.models import fake_model_profiles
from hephaestus.optimize.context_packer import pack_context
from hephaestus.optimize.model_router import ModelRouteRequest, ModelRoutingError, route_model
from hephaestus.policy_learning.schemas import DecisionQualityProfile
from hephaestus.qubo.formulations import formulate_benchmark_case
from hephaestus.qubo.repository import QuboRepository
from hephaestus.qubo.schemas import (
    BinaryVariable,
    QuboComparisonResult,
    QuboProblem,
    QuboProblemType,
    QuboSolution,
)
from hephaestus.qubo.solver import objective_value, solve

DEFAULT_BENCHMARK_QUBO_TYPES: tuple[QuboProblemType, ...] = (
    QuboProblemType.CONTEXT_PACKING,
    QuboProblemType.MODEL_SELECTION,
    QuboProblemType.BUDGET_STRATEGY,
)


def compare_benchmark_with_qubo(
    case: BenchmarkCase,
    *,
    repository: QuboRepository | None = None,
    run_id: str | None = None,
    active_profiles: Sequence[DecisionQualityProfile] | None = None,
    source_decision_trace_ids: Sequence[str] | None = None,
    solver_name: str = "exhaustive",
    seed: int = 17,
    iterations: int = 750,
    problem_types: Sequence[QuboProblemType] = DEFAULT_BENCHMARK_QUBO_TYPES,
    notes: Sequence[str] | None = None,
) -> list[QuboComparisonResult]:
    """Formulate, solve, optionally persist, and compare fixture QUBOs."""

    comparisons: list[QuboComparisonResult] = []
    for problem_type in problem_types:
        if problem_type == QuboProblemType.CONTEXT_PACKING and not case.context_candidates:
            continue
        if problem_type == QuboProblemType.MODEL_SELECTION and not case.tasks:
            continue
        report = formulate_benchmark_case(
            case,
            problem_type,
            run_id=run_id,
            active_profiles=active_profiles,
            source_decision_trace_ids=source_decision_trace_ids,
        )
        problem = report.problem
        solution = solve(problem, solver_name=solver_name, seed=seed, iterations=iterations)
        if repository is not None:
            repository.save_problem(problem)
            repository.save_solution(solution, problem)
        comparisons.append(
            _comparison_for_problem(
                case,
                problem,
                solution,
                solver_name=solver_name,
                notes=[*report.notes, *list(notes or [])],
            )
        )
    return comparisons


def build_qubo_solution_trace(
    comparison: QuboComparisonResult,
    problem: QuboProblem,
    solution: QuboSolution,
    run_id: str,
    *,
    parent_id: str | None = None,
) -> OptimizationDecision:
    """Represent a QUBO solve as an explainable optimization trace."""

    return OptimizationDecision(
        run_id=run_id,
        phase="qubo",
        selected_option=comparison.qubo_selected,
        alternatives=[
            DecisionAlternative(
                option_id="baseline",
                option_name=comparison.baseline_selected,
                score=0.0,
                rejection_reason=(
                    "QUBO encoded the selected decision surface as binary energy "
                    "rather than using the baseline heuristic directly."
                ),
            )
        ],
        rationale=(
            f"QUBO {problem.problem_type.value} solved with {solution.solver_name}; "
            f"feasible={solution.feasible}; objective={solution.objective_value:.3f}."
        ),
        metrics=[
            metric("qubo_problem_id", problem.id),
            metric("qubo_solution_id", solution.id),
            metric("problem_type", problem.problem_type.value),
            metric("variable_count", len(problem.variables)),
            metric("linear_terms", len(problem.linear_terms)),
            metric("quadratic_terms", len(problem.quadratic_terms)),
            metric("constraint_count", len(problem.constraints)),
            metric("objective_value", solution.objective_value, higher_is_better=False),
            metric("feasible", solution.feasible),
        ],
        objective_score=-solution.objective_value,
        confidence=0.86 if solution.feasible else 0.58,
        constraints_considered=[constraint.description for constraint in problem.constraints],
        tags=["qubo", problem.problem_type.value, "quantum-inspired-classical"],
        caused_by=[f"qubo_problem:{problem.id}", *problem.source_decision_trace_ids],
        will_affect=["benchmark_report", "explainability", "optimization_comparison"],
        learning_hooks=[
            "qubo_solution_outcome",
            "formulation_penalty_learning",
            "decision_quality_learning",
        ],
        parent_id=parent_id,
    )


def _comparison_for_problem(
    case: BenchmarkCase,
    problem: QuboProblem,
    solution: QuboSolution,
    *,
    solver_name: str,
    notes: list[str],
) -> QuboComparisonResult:
    if problem.problem_type == QuboProblemType.CONTEXT_PACKING:
        return _context_comparison(case, problem, solution, solver_name=solver_name, notes=notes)
    if problem.problem_type == QuboProblemType.MODEL_SELECTION:
        return _model_comparison(case, problem, solution, solver_name=solver_name, notes=notes)
    if problem.problem_type == QuboProblemType.BUDGET_STRATEGY:
        return _budget_comparison(case, problem, solution, solver_name=solver_name, notes=notes)
    return _generic_comparison(case, problem, solution, solver_name=solver_name, notes=notes)


def _context_comparison(
    case: BenchmarkCase,
    problem: QuboProblem,
    solution: QuboSolution,
    *,
    solver_name: str,
    notes: list[str],
) -> QuboComparisonResult:
    baseline = pack_context(case.context_candidates, case.context_token_budget)
    baseline_ids = [item.id for item in baseline.selected]
    qubo_ids = _selected_source_ids(problem, solution)
    baseline_objective = objective_value(problem, _assignment_for_source_ids(problem, baseline_ids))
    token_cost_by_source = {
        variable.metadata.get("source_id", variable.label): int(variable.metadata.get("token_cost", 0))
        for variable in problem.variables
    }
    baseline_tokens = sum(token_cost_by_source.get(source_id, 0) for source_id in baseline_ids)
    qubo_tokens = sum(token_cost_by_source.get(source_id, 0) for source_id in qubo_ids)
    return QuboComparisonResult(
        fixture_id=case.id,
        problem_type=problem.problem_type,
        problem_id=problem.id,
        solution_id=solution.id,
        solver_name=solver_name,
        baseline_selected=", ".join(baseline_ids) or "none",
        qubo_selected=", ".join(qubo_ids) or "none",
        objective_difference=solution.objective_value - baseline_objective,
        feasible=solution.feasible,
        token_comparison={"baseline": float(baseline_tokens), "qubo": float(qubo_tokens)},
        notes=notes,
    )


def _model_comparison(
    case: BenchmarkCase,
    problem: QuboProblem,
    solution: QuboSolution,
    *,
    solver_name: str,
    notes: list[str],
) -> QuboComparisonResult:
    task = sorted(case.tasks, key=lambda item: (-item.priority, item.id))[0]
    profiles = case.model_profiles or list(fake_model_profiles())
    threshold = case.quality_thresholds.get(task.id, case.quality_threshold)
    baseline_selected = "unrouted"
    baseline_quality = 0.0
    baseline_cost = 0.0
    try:
        route = route_model(
            ModelRouteRequest(
                required_capabilities=task.required_capabilities,
                input_tokens=task.estimated_input_tokens,
                output_tokens=task.estimated_output_tokens,
                quality_threshold=threshold,
                privacy_level=task.privacy_level,
                needs_tools=bool(task.allowed_tools),
                needs_json=True,
                profiles=profiles,
            )
        )
        baseline_selected = route.profile.identifier
        baseline_quality = route.quality
        baseline_cost = route.estimated_cost
    except ModelRoutingError as error:
        notes = [*notes, str(error)]
    qubo_selected_variables = _selected_variables(problem, solution)
    qubo_selected = ", ".join(variable.label for variable in qubo_selected_variables) or "none"
    qubo_quality = max(
        (float(variable.metadata.get("quality", 0.0)) for variable in qubo_selected_variables),
        default=0.0,
    )
    qubo_cost = sum(float(variable.metadata.get("estimated_cost", 0.0)) for variable in qubo_selected_variables)
    baseline_objective = objective_value(problem, _assignment_for_labels(problem, [baseline_selected]))
    return QuboComparisonResult(
        fixture_id=case.id,
        problem_type=problem.problem_type,
        problem_id=problem.id,
        solution_id=solution.id,
        solver_name=solver_name,
        baseline_selected=baseline_selected,
        qubo_selected=qubo_selected,
        objective_difference=solution.objective_value - baseline_objective,
        feasible=solution.feasible,
        cost_comparison={"baseline": baseline_cost, "qubo": qubo_cost},
        quality_comparison={"baseline": baseline_quality, "qubo": qubo_quality},
        notes=notes,
    )


def _budget_comparison(
    case: BenchmarkCase,
    problem: QuboProblem,
    solution: QuboSolution,
    *,
    solver_name: str,
    notes: list[str],
) -> QuboComparisonResult:
    baseline_label = "balanced"
    qubo_selected_variables = _selected_variables(problem, solution)
    qubo_selected = ", ".join(variable.label for variable in qubo_selected_variables) or "none"
    baseline_objective = objective_value(problem, _assignment_for_labels(problem, [baseline_label]))
    baseline_tokens = _strategy_metric(problem, baseline_label, "token_usage")
    qubo_tokens = sum(float(variable.metadata.get("token_usage", 0.0)) for variable in qubo_selected_variables)
    baseline_cost = _strategy_metric(problem, baseline_label, "estimated_cost")
    qubo_cost = sum(float(variable.metadata.get("estimated_cost", 0.0)) for variable in qubo_selected_variables)
    baseline_quality = _strategy_metric(problem, baseline_label, "quality_preservation")
    qubo_quality = max(
        (float(variable.metadata.get("quality_preservation", 0.0)) for variable in qubo_selected_variables),
        default=0.0,
    )
    return QuboComparisonResult(
        fixture_id=case.id,
        problem_type=problem.problem_type,
        problem_id=problem.id,
        solution_id=solution.id,
        solver_name=solver_name,
        baseline_selected=baseline_label,
        qubo_selected=qubo_selected,
        objective_difference=solution.objective_value - baseline_objective,
        feasible=solution.feasible,
        token_comparison={"baseline": baseline_tokens, "qubo": qubo_tokens},
        cost_comparison={"baseline": baseline_cost, "qubo": qubo_cost},
        quality_comparison={"baseline": baseline_quality, "qubo": qubo_quality},
        notes=notes,
    )


def _generic_comparison(
    case: BenchmarkCase,
    problem: QuboProblem,
    solution: QuboSolution,
    *,
    solver_name: str,
    notes: list[str],
) -> QuboComparisonResult:
    return QuboComparisonResult(
        fixture_id=case.id,
        problem_type=problem.problem_type,
        problem_id=problem.id,
        solution_id=solution.id,
        solver_name=solver_name,
        baseline_selected="not available",
        qubo_selected=", ".join(variable.label for variable in _selected_variables(problem, solution)) or "none",
        objective_difference=solution.objective_value,
        feasible=solution.feasible,
        notes=notes,
    )


def _selected_variables(problem: QuboProblem, solution: QuboSolution) -> list[BinaryVariable]:
    selected_ids = set(solution.selected_variables)
    return [variable for variable in problem.variables if variable.id in selected_ids]


def _selected_source_ids(problem: QuboProblem, solution: QuboSolution) -> list[str]:
    source_ids: list[str] = []
    for variable in _selected_variables(problem, solution):
        source_ids.append(str(variable.metadata.get("source_id", variable.label or variable.id)))
    return source_ids


def _assignment_for_source_ids(problem: QuboProblem, source_ids: Sequence[str]) -> dict[str, int]:
    source_id_set = set(source_ids)
    assignment: dict[str, int] = {}
    for variable in problem.variables:
        source_id = str(variable.metadata.get("source_id", variable.label or variable.id))
        assignment[variable.id] = 1 if source_id in source_id_set else 0
    return assignment


def _assignment_for_labels(problem: QuboProblem, labels: Sequence[str]) -> dict[str, int]:
    label_set = set(labels)
    return {
        variable.id: 1 if variable.label in label_set else 0
        for variable in problem.variables
    }


def _strategy_metric(problem: QuboProblem, label: str, key: str) -> float:
    for variable in problem.variables:
        if variable.label == label:
            value = variable.metadata.get(key, 0.0)
            if isinstance(value, bool) or value is None:
                return 0.0
            if isinstance(value, int | float):
                return float(value)
            if isinstance(value, str):
                try:
                    return float(value)
                except ValueError:
                    return 0.0
    return 0.0
