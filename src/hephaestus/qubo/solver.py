"""Deterministic local solvers for QUBO problems."""

from __future__ import annotations

import math
import random
from collections.abc import Callable
from itertools import product
from typing import Any

from hephaestus.qubo.schemas import QuboConstraintType, QuboProblem, QuboSolution

Assignment = dict[str, int]


def solve(
    problem: QuboProblem,
    *,
    solver_name: str = "exhaustive",
    seed: int = 17,
    iterations: int = 750,
) -> QuboSolution:
    """Solve a QUBO problem with a named local solver."""

    if solver_name == "exhaustive":
        return solve_exhaustive(problem)
    if solver_name == "greedy":
        return solve_greedy(problem, max_passes=max(1, iterations))
    if solver_name == "annealing":
        return solve_annealing(problem, seed=seed, iterations=max(1, iterations))
    raise ValueError(f"Unknown QUBO solver: {solver_name}")


def solve_exhaustive(problem: QuboProblem, *, max_variables: int = 20) -> QuboSolution:
    """Try every binary assignment for small problems."""

    variable_ids = [variable.id for variable in problem.variables]
    if len(variable_ids) > max_variables:
        raise ValueError(
            f"Exhaustive QUBO solve supports at most {max_variables} variables; "
            f"problem has {len(variable_ids)}."
        )

    best_assignment: Assignment | None = None
    best_value = math.inf
    best_violations: list[str] = []
    checked = 0
    for values in product((0, 1), repeat=len(variable_ids)):
        checked += 1
        assignment = dict(zip(variable_ids, values, strict=True))
        value = objective_value(problem, assignment)
        violations = constraint_violations(problem, assignment)
        if _is_better_assignment(
            value,
            violations,
            assignment,
            best_value=best_value,
            best_violations=best_violations,
            best_assignment=best_assignment,
        ):
            best_assignment = assignment
            best_value = value
            best_violations = violations

    if best_assignment is None:
        best_assignment = {variable_id: 0 for variable_id in variable_ids}
        best_value = objective_value(problem, best_assignment)
        best_violations = constraint_violations(problem, best_assignment)

    return _solution(
        problem,
        best_assignment,
        best_value,
        best_violations,
        solver_name="exhaustive",
        iterations=checked,
        explanation=(
            f"Exhaustive solver evaluated {checked} assignments and selected the "
            "lowest-energy feasible assignment when one was available."
        ),
    )


def solve_greedy(problem: QuboProblem, *, max_passes: int = 50) -> QuboSolution:
    """Greedy single-bit descent with a small feasibility repair pass."""

    assignment = _initial_assignment(problem)
    current_value = objective_value(problem, assignment)
    passes = 0
    improved = True
    while improved and passes < max_passes:
        passes += 1
        improved = False
        best_variable = ""
        best_assignment = assignment
        best_value = current_value
        for variable in problem.variables:
            candidate = dict(assignment)
            candidate[variable.id] = 1 - candidate[variable.id]
            value = objective_value(problem, candidate)
            if value < best_value - 1e-12:
                best_variable = variable.id
                best_assignment = candidate
                best_value = value
        if best_variable:
            assignment = best_assignment
            current_value = best_value
            improved = True

    repaired = repair_assignment(problem, assignment)
    repaired_value = objective_value(problem, repaired)
    violations = constraint_violations(problem, repaired)
    return _solution(
        problem,
        repaired,
        repaired_value,
        violations,
        solver_name="greedy",
        iterations=passes,
        explanation=(
            "Greedy solver accepted single-variable flips that lowered QUBO energy, "
            "then applied deterministic repairs for exact-one and simple budget constraints."
        ),
    )


def solve_annealing(
    problem: QuboProblem,
    *,
    seed: int = 17,
    iterations: int = 750,
    initial_temperature: float = 4.0,
    cooling_rate: float = 0.992,
) -> QuboSolution:
    """Seeded simulated annealing over binary assignments."""

    rng = random.Random(seed)
    variable_ids = [variable.id for variable in problem.variables]
    assignment = _initial_assignment(problem)
    current_value = objective_value(problem, assignment)
    best_assignment = dict(assignment)
    best_value = current_value
    temperature = initial_temperature

    if not variable_ids:
        return _solution(
            problem,
            assignment,
            current_value,
            constraint_violations(problem, assignment),
            solver_name="annealing",
            iterations=0,
            explanation="Annealing solver found no variables to optimize.",
        )

    for _ in range(iterations):
        variable_id = rng.choice(variable_ids)
        candidate = dict(assignment)
        candidate[variable_id] = 1 - candidate[variable_id]
        candidate_value = objective_value(problem, candidate)
        delta = candidate_value - current_value
        if delta <= 0 or rng.random() < math.exp(-delta / max(temperature, 0.001)):
            assignment = candidate
            current_value = candidate_value
        if candidate_value < best_value:
            best_assignment = candidate
            best_value = candidate_value
        temperature = max(0.001, temperature * cooling_rate)

    repaired = repair_assignment(problem, best_assignment)
    repaired_value = objective_value(problem, repaired)
    violations = constraint_violations(problem, repaired)
    return _solution(
        problem,
        repaired,
        repaired_value,
        violations,
        solver_name="annealing",
        iterations=iterations,
        explanation=(
            f"Seeded simulated annealing ran {iterations} binary flips with seed {seed}; "
            "it is a classical local search baseline, not quantum hardware execution."
        ),
    )


def objective_value(problem: QuboProblem, assignment: Assignment) -> float:
    """Evaluate QUBO energy for one binary assignment."""

    value = problem.constant_offset
    for term in problem.linear_terms:
        variable_id = term.variable_ids[0]
        value += term.coefficient * _bit(assignment, variable_id)
    for term in problem.quadratic_terms:
        first, second = term.variable_ids
        value += term.coefficient * _bit(assignment, first) * _bit(assignment, second)
    return value


def constraint_violations(problem: QuboProblem, assignment: Assignment) -> list[str]:
    """Return human-readable constraint violations for one assignment."""

    violations: list[str] = []
    for constraint in problem.constraints:
        values = [_bit(assignment, variable_id) for variable_id in constraint.variable_ids]
        selected_count = sum(values)
        if constraint.constraint_type == QuboConstraintType.EXACTLY_ONE and selected_count != 1:
            violations.append(f"{constraint.description} (selected {selected_count}, expected 1)")
        elif constraint.constraint_type == QuboConstraintType.AT_MOST_ONE and selected_count > 1:
            violations.append(f"{constraint.description} (selected {selected_count}, expected <= 1)")
        elif constraint.constraint_type == QuboConstraintType.REQUIRED_VARIABLES:
            missing = [
                variable_id
                for variable_id in constraint.variable_ids
                if _bit(assignment, variable_id) != 1
            ]
            if missing:
                violations.append(f"{constraint.description} (missing {', '.join(missing)})")
        elif constraint.constraint_type == QuboConstraintType.TOKEN_BUDGET:
            _append_token_budget_violation(constraint.metadata, assignment, violations, constraint.description)
        elif constraint.constraint_type == QuboConstraintType.MAX_ITEM_COUNT:
            max_count = _metadata_int(constraint.metadata, "max_count")
            if max_count is not None and selected_count > max_count:
                violations.append(f"{constraint.description} (selected {selected_count}, max {max_count})")
        elif constraint.constraint_type == QuboConstraintType.REQUIRED_CAPABILITY:
            invalid = [
                variable_id
                for variable_id in _metadata_list(constraint.metadata, "invalid_variables")
                if _bit(assignment, variable_id) == 1
            ]
            if invalid:
                violations.append(f"{constraint.description} (invalid: {', '.join(invalid)})")
        elif constraint.constraint_type == QuboConstraintType.QUALITY_THRESHOLD:
            threshold = _metadata_float(constraint.metadata, "threshold")
            quality_by_variable = _metadata_float_map(constraint.metadata, "quality_by_variable")
            if threshold is not None:
                low_quality = [
                    variable_id
                    for variable_id, quality in quality_by_variable.items()
                    if _bit(assignment, variable_id) == 1 and quality < threshold
                ]
                if low_quality:
                    violations.append(
                        f"{constraint.description} (below threshold: {', '.join(low_quality)})"
                    )
        elif constraint.constraint_type == QuboConstraintType.TASK_ASSIGNED_ONCE and selected_count != 1:
            violations.append(f"{constraint.description} (assigned {selected_count} times)")
        elif constraint.constraint_type == QuboConstraintType.POSITION_FILLED_ONCE and selected_count != 1:
            violations.append(f"{constraint.description} (filled by {selected_count} tasks)")
        elif constraint.constraint_type == QuboConstraintType.DEPENDENCY_ORDER:
            dependency_pairs = _metadata_dependency_pairs(constraint.metadata)
            positions = _assigned_positions(problem, assignment)
            for dependent_id, prerequisite_id in dependency_pairs:
                dependent_position = positions.get(dependent_id)
                prerequisite_position = positions.get(prerequisite_id)
                if (
                    dependent_position is not None
                    and prerequisite_position is not None
                    and prerequisite_position >= dependent_position
                ):
                    violations.append(
                        f"{constraint.description} ({prerequisite_id} not before {dependent_id})"
                    )
    return violations


def repair_assignment(problem: QuboProblem, assignment: Assignment) -> Assignment:
    """Apply deterministic repairs for constraints that have obvious local fixes."""

    repaired = dict(assignment)
    required_variables = _required_variables(problem)
    invalid_variables = _invalid_variables(problem)
    for variable_id in invalid_variables - required_variables:
        repaired[variable_id] = 0
    for constraint in problem.constraints:
        if constraint.constraint_type in {
            QuboConstraintType.EXACTLY_ONE,
            QuboConstraintType.TASK_ASSIGNED_ONCE,
            QuboConstraintType.POSITION_FILLED_ONCE,
        }:
            valid_group = [
                variable_id
                for variable_id in constraint.variable_ids
                if variable_id not in invalid_variables or variable_id in required_variables
            ]
            repaired = _repair_exactly_one(
                problem,
                repaired,
                valid_group or constraint.variable_ids,
            )
        elif constraint.constraint_type == QuboConstraintType.REQUIRED_VARIABLES:
            for variable_id in constraint.variable_ids:
                repaired[variable_id] = 1
    for constraint in problem.constraints:
        if constraint.constraint_type == QuboConstraintType.MAX_ITEM_COUNT:
            max_count = _metadata_int(constraint.metadata, "max_count")
            if max_count is not None:
                repaired = _repair_max_count(problem, repaired, constraint.variable_ids, max_count)
        elif constraint.constraint_type == QuboConstraintType.TOKEN_BUDGET:
            repaired = _repair_token_budget(
                problem,
                repaired,
                constraint.metadata,
                protected_variables=required_variables,
            )
    return repaired


def _solution(
    problem: QuboProblem,
    assignment: Assignment,
    value: float,
    violations: list[str],
    *,
    solver_name: str,
    iterations: int,
    explanation: str,
) -> QuboSolution:
    selected = [variable.id for variable in problem.variables if _bit(assignment, variable.id) == 1]
    return QuboSolution(
        problem_id=problem.id,
        selected_variables=selected,
        objective_value=value,
        constraint_violations=violations,
        feasible=not violations,
        solver_name=solver_name,
        iterations=iterations,
        explanation=explanation,
        variable_values={variable.id: _bit(assignment, variable.id) for variable in problem.variables},
    )


def _is_better_assignment(
    value: float,
    violations: list[str],
    assignment: Assignment,
    *,
    best_value: float,
    best_violations: list[str],
    best_assignment: Assignment | None,
) -> bool:
    if best_assignment is None:
        return True
    feasible = not violations
    best_feasible = not best_violations
    if feasible and not best_feasible:
        return True
    if feasible == best_feasible and value < best_value - 1e-12:
        return True
    if feasible == best_feasible and abs(value - best_value) <= 1e-12:
        return _selected_key(assignment) < _selected_key(best_assignment)
    return False


def _selected_key(assignment: Assignment) -> tuple[str, ...]:
    return tuple(sorted(variable_id for variable_id, value in assignment.items() if value == 1))


def _initial_assignment(problem: QuboProblem) -> Assignment:
    assignment = {variable.id: 0 for variable in problem.variables}
    for constraint in problem.constraints:
        if constraint.constraint_type == QuboConstraintType.EXACTLY_ONE and constraint.variable_ids:
            assignment[constraint.variable_ids[0]] = 1
    for variable_id in _required_variables(problem):
        assignment[variable_id] = 1
    return assignment


def _repair_exactly_one(
    problem: QuboProblem,
    assignment: Assignment,
    variable_ids: list[str],
) -> Assignment:
    if not variable_ids:
        return assignment
    selected = [variable_id for variable_id in variable_ids if _bit(assignment, variable_id) == 1]
    if len(selected) == 1:
        return assignment

    best_assignment = dict(assignment)
    best_value = math.inf
    for variable_id in variable_ids:
        candidate = dict(assignment)
        for group_variable_id in variable_ids:
            candidate[group_variable_id] = 1 if group_variable_id == variable_id else 0
        value = objective_value(problem, candidate)
        if value < best_value:
            best_assignment = candidate
            best_value = value
    return best_assignment


def _repair_max_count(
    problem: QuboProblem,
    assignment: Assignment,
    variable_ids: list[str],
    max_count: int,
) -> Assignment:
    repaired = dict(assignment)
    while sum(_bit(repaired, variable_id) for variable_id in variable_ids) > max_count:
        removable = [variable_id for variable_id in variable_ids if _bit(repaired, variable_id) == 1]
        variable_id = _best_removal(problem, repaired, removable)
        if not variable_id:
            break
        repaired[variable_id] = 0
    return repaired


def _repair_token_budget(
    problem: QuboProblem,
    assignment: Assignment,
    metadata: dict[str, Any],
    *,
    protected_variables: set[str],
) -> Assignment:
    token_costs = _metadata_int_map(metadata, "token_cost_by_variable")
    budget = _metadata_int(metadata, "budget")
    if budget is None or not token_costs:
        return assignment
    repaired = dict(assignment)

    def used_tokens() -> int:
        return sum(cost for variable_id, cost in token_costs.items() if _bit(repaired, variable_id) == 1)

    while used_tokens() > budget:
        removable = [
            variable_id
            for variable_id in token_costs
            if _bit(repaired, variable_id) == 1 and variable_id not in protected_variables
        ]
        variable_id = _best_removal(problem, repaired, removable)
        if not variable_id:
            break
        repaired[variable_id] = 0
    return repaired


def _best_removal(problem: QuboProblem, assignment: Assignment, candidates: list[str]) -> str:
    best_variable = ""
    best_value = math.inf
    for variable_id in candidates:
        candidate = dict(assignment)
        candidate[variable_id] = 0
        value = objective_value(problem, candidate)
        if value < best_value:
            best_variable = variable_id
            best_value = value
    return best_variable


def _required_variables(problem: QuboProblem) -> set[str]:
    required: set[str] = set()
    for constraint in problem.constraints:
        if constraint.constraint_type == QuboConstraintType.REQUIRED_VARIABLES:
            required.update(constraint.variable_ids)
    return required


def _invalid_variables(problem: QuboProblem) -> set[str]:
    invalid: set[str] = set()
    for constraint in problem.constraints:
        if constraint.constraint_type == QuboConstraintType.REQUIRED_CAPABILITY:
            invalid.update(_metadata_list(constraint.metadata, "invalid_variables"))
        elif constraint.constraint_type == QuboConstraintType.QUALITY_THRESHOLD:
            threshold = _metadata_float(constraint.metadata, "threshold")
            quality_by_variable = _metadata_float_map(constraint.metadata, "quality_by_variable")
            if threshold is None:
                continue
            invalid.update(
                variable_id
                for variable_id, quality in quality_by_variable.items()
                if quality < threshold
            )
    return invalid


def _append_token_budget_violation(
    metadata: dict[str, Any],
    assignment: Assignment,
    violations: list[str],
    description: str,
) -> None:
    token_costs = _metadata_int_map(metadata, "token_cost_by_variable")
    budget = _metadata_int(metadata, "budget")
    if budget is None:
        return
    used = sum(cost for variable_id, cost in token_costs.items() if _bit(assignment, variable_id) == 1)
    if used > budget:
        violations.append(f"{description} (used {used}, budget {budget})")


def _assigned_positions(problem: QuboProblem, assignment: Assignment) -> dict[str, int]:
    positions: dict[str, int] = {}
    for variable in problem.variables:
        if _bit(assignment, variable.id) != 1:
            continue
        task_id = variable.metadata.get("task_id")
        position = variable.metadata.get("position")
        if isinstance(task_id, str) and isinstance(position, int):
            positions[task_id] = position
    return positions


def _metadata_dependency_pairs(metadata: dict[str, Any]) -> list[tuple[str, str]]:
    pairs = metadata.get("dependency_pairs", [])
    if not isinstance(pairs, list):
        return []
    normalized: list[tuple[str, str]] = []
    for item in pairs:
        if (
            isinstance(item, list | tuple)
            and len(item) == 2
            and isinstance(item[0], str)
            and isinstance(item[1], str)
        ):
            normalized.append((item[0], item[1]))
    return normalized


def _metadata_int(metadata: dict[str, Any], key: str) -> int | None:
    value = metadata.get(key)
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _metadata_float(metadata: dict[str, Any], key: str) -> float | None:
    value = metadata.get(key)
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value)
        except ValueError:
            return None
    return None


def _metadata_list(metadata: dict[str, Any], key: str) -> list[str]:
    value = metadata.get(key, [])
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _metadata_int_map(metadata: dict[str, Any], key: str) -> dict[str, int]:
    return _metadata_map(metadata, key, int)


def _metadata_float_map(metadata: dict[str, Any], key: str) -> dict[str, float]:
    return _metadata_map(metadata, key, float)


def _metadata_map(
    metadata: dict[str, Any],
    key: str,
    converter: Callable[[Any], Any],
) -> dict[str, Any]:
    value = metadata.get(key, {})
    if not isinstance(value, dict):
        return {}
    converted: dict[str, Any] = {}
    for map_key, map_value in value.items():
        try:
            converted[str(map_key)] = converter(map_value)
        except (TypeError, ValueError):
            continue
    return converted


def _bit(assignment: Assignment, variable_id: str) -> int:
    return 1 if assignment.get(variable_id, 0) else 0
