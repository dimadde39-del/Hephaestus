"""QUBO to Ising conversion."""

from __future__ import annotations

from hephaestus.qubo.schemas import IsingProblem, IsingTerm, QuboProblem


def qubo_to_ising(problem: QuboProblem) -> IsingProblem:
    """Convert a QUBO problem to Ising form using x = (1 + s) / 2."""

    linear: dict[str, float] = {}
    quadratic: dict[tuple[str, str], float] = {}
    constant = problem.constant_offset

    for term in problem.linear_terms:
        variable_id = term.variable_ids[0]
        coefficient = term.coefficient
        constant += coefficient / 2.0
        linear[variable_id] = linear.get(variable_id, 0.0) + coefficient / 2.0

    for term in problem.quadratic_terms:
        first, second = term.variable_ids
        coefficient = term.coefficient
        key = _pair_key(first, second)
        constant += coefficient / 4.0
        linear[first] = linear.get(first, 0.0) + coefficient / 4.0
        linear[second] = linear.get(second, 0.0) + coefficient / 4.0
        quadratic[key] = quadratic.get(key, 0.0) + coefficient / 4.0

    return IsingProblem(
        qubo_problem_id=problem.id,
        variables=[variable.id for variable in problem.variables],
        linear_terms=[
            IsingTerm(variable_ids=(variable_id,), coefficient=coefficient)
            for variable_id, coefficient in sorted(linear.items())
            if abs(coefficient) > 1e-12
        ],
        quadratic_terms=[
            IsingTerm(variable_ids=variable_ids, coefficient=coefficient)
            for variable_ids, coefficient in sorted(quadratic.items())
            if abs(coefficient) > 1e-12
        ],
        constant_offset=constant,
    )


def _pair_key(first: str, second: str) -> tuple[str, str]:
    return (first, second) if first <= second else (second, first)
