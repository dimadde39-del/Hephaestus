"""Helpers for constructing QUBO problems without hiding the formulation."""

from __future__ import annotations

from itertools import combinations
from typing import Any

from hephaestus.qubo.schemas import (
    BinaryVariable,
    QuboConstraint,
    QuboConstraintType,
    QuboObjective,
    QuboProblem,
    QuboProblemType,
    QuboTerm,
)


class QuboBuilder:
    """Incrementally build an inspectable QUBO problem."""

    def __init__(
        self,
        *,
        problem_type: QuboProblemType,
        run_id: str | None = None,
        source_benchmark_id: str | None = None,
        source_frontier_id: str | None = None,
        source_decision_trace_ids: list[str] | None = None,
        tags: list[str] | None = None,
        objective: QuboObjective | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.problem_type = problem_type
        self.run_id = run_id
        self.source_benchmark_id = source_benchmark_id
        self.source_frontier_id = source_frontier_id
        self.source_decision_trace_ids = list(source_decision_trace_ids or [])
        self.tags = list(tags or [])
        self.objective = objective or QuboObjective()
        self.metadata = dict(metadata or {})
        self.variables: dict[str, BinaryVariable] = {}
        self.linear_coefficients: dict[str, float] = {}
        self.linear_reasons: dict[str, list[str]] = {}
        self.quadratic_coefficients: dict[tuple[str, str], float] = {}
        self.quadratic_reasons: dict[tuple[str, str], list[str]] = {}
        self.constraints: list[QuboConstraint] = []
        self.penalty_weights: dict[str, float] = {}
        self.constant_offset = 0.0

    def add_variable(
        self,
        variable_id: str,
        *,
        label: str = "",
        description: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> BinaryVariable:
        """Register one binary variable."""

        variable = BinaryVariable(
            id=variable_id,
            label=label,
            description=description,
            metadata=dict(metadata or {}),
        )
        self.variables[variable_id] = variable
        return variable

    def add_linear(self, variable_id: str, coefficient: float, *, reason: str = "") -> None:
        """Add a linear coefficient for one variable."""

        self._require_variable(variable_id)
        self.linear_coefficients[variable_id] = self.linear_coefficients.get(variable_id, 0.0) + coefficient
        if reason:
            self.linear_reasons.setdefault(variable_id, []).append(reason)

    def add_quadratic(
        self,
        first_variable_id: str,
        second_variable_id: str,
        coefficient: float,
        *,
        reason: str = "",
    ) -> None:
        """Add a quadratic coefficient between two variables."""

        self._require_variable(first_variable_id)
        self._require_variable(second_variable_id)
        if first_variable_id == second_variable_id:
            self.add_linear(first_variable_id, coefficient, reason=reason)
            return
        key = _pair_key(first_variable_id, second_variable_id)
        self.quadratic_coefficients[key] = self.quadratic_coefficients.get(key, 0.0) + coefficient
        if reason:
            self.quadratic_reasons.setdefault(key, []).append(reason)

    def add_constraint(self, constraint: QuboConstraint) -> None:
        """Attach a constraint record to the problem."""

        for variable_id in constraint.variable_ids:
            self._require_variable(variable_id)
        self.constraints.append(constraint)
        if constraint.penalty_weight:
            self.penalty_weights[constraint.id] = constraint.penalty_weight

    def add_exactly_one(
        self,
        variable_ids: list[str],
        *,
        weight: float,
        description: str,
        constraint_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Encode weight * (sum(x_i) - 1)^2."""

        for variable_id in variable_ids:
            self._require_variable(variable_id)
        self.constant_offset += weight
        for variable_id in variable_ids:
            self.add_linear(variable_id, -weight, reason=f"{constraint_id}: exact-one linear")
        for first, second in combinations(variable_ids, 2):
            self.add_quadratic(first, second, 2.0 * weight, reason=f"{constraint_id}: exact-one pair")
        self.add_constraint(
            QuboConstraint(
                id=constraint_id,
                constraint_type=QuboConstraintType.EXACTLY_ONE,
                description=description,
                variable_ids=variable_ids,
                operator="=",
                target_value=1.0,
                penalty_weight=weight,
                metadata=dict(metadata or {}),
            )
        )

    def add_required_variable(
        self,
        variable_id: str,
        *,
        weight: float,
        description: str,
        constraint_id: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Encode weight * (1 - x_i)^2 for a required variable."""

        self._require_variable(variable_id)
        self.constant_offset += weight
        self.add_linear(variable_id, -weight, reason=f"{constraint_id}: required variable")
        self.add_constraint(
            QuboConstraint(
                id=constraint_id,
                constraint_type=QuboConstraintType.REQUIRED_VARIABLES,
                description=description,
                variable_ids=[variable_id],
                operator="=",
                target_value=1.0,
                penalty_weight=weight,
                metadata=dict(metadata or {}),
            )
        )

    def build(self) -> QuboProblem:
        """Create the immutable QUBO problem model."""

        linear_terms = [
            QuboTerm(
                variable_ids=(variable_id,),
                coefficient=coefficient,
                reason="; ".join(self.linear_reasons.get(variable_id, [])),
            )
            for variable_id, coefficient in sorted(self.linear_coefficients.items())
            if abs(coefficient) > 1e-12
        ]
        quadratic_terms = [
            QuboTerm(
                variable_ids=variable_ids,
                coefficient=coefficient,
                reason="; ".join(self.quadratic_reasons.get(variable_ids, [])),
            )
            for variable_ids, coefficient in sorted(self.quadratic_coefficients.items())
            if abs(coefficient) > 1e-12
        ]
        return QuboProblem(
            run_id=self.run_id,
            problem_type=self.problem_type,
            variables=list(self.variables.values()),
            linear_terms=linear_terms,
            quadratic_terms=quadratic_terms,
            constraints=self.constraints,
            penalty_weights=self.penalty_weights,
            constant_offset=self.constant_offset,
            objective=self.objective,
            source_benchmark_id=self.source_benchmark_id,
            source_frontier_id=self.source_frontier_id,
            source_decision_trace_ids=self.source_decision_trace_ids,
            tags=self.tags,
            metadata=self.metadata,
        )

    def _require_variable(self, variable_id: str) -> None:
        if variable_id not in self.variables:
            raise ValueError(f"Unknown QUBO variable: {variable_id}")


def safe_variable_id(prefix: str, raw_id: str) -> str:
    """Create a stable variable ID from user or fixture text."""

    normalized = "".join(
        character.lower() if character.isalnum() else "_"
        for character in raw_id.strip()
    ).strip("_")
    while "__" in normalized:
        normalized = normalized.replace("__", "_")
    return f"{prefix}_{normalized or 'item'}"


def _pair_key(first: str, second: str) -> tuple[str, str]:
    return (first, second) if first <= second else (second, first)
