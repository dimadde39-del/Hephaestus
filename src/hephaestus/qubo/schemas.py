"""Typed schemas for QUBO and Ising-style formulations."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class QuboProblemType(StrEnum):
    """Decision surfaces supported by the QUBO formulation layer."""

    CONTEXT_PACKING = "context_packing"
    MODEL_SELECTION = "model_selection"
    TASK_SELECTION = "task_selection"
    TASK_ORDERING_DEMO = "task_ordering_demo"
    BUDGET_STRATEGY = "budget_strategy"


class QuboConstraintType(StrEnum):
    """Inspectable constraint categories used by formulations and solvers."""

    EXACTLY_ONE = "exactly_one"
    AT_MOST_ONE = "at_most_one"
    TOKEN_BUDGET = "token_budget"
    REQUIRED_VARIABLES = "required_variables"
    MAX_ITEM_COUNT = "max_item_count"
    REQUIRED_CAPABILITY = "required_capability"
    QUALITY_THRESHOLD = "quality_threshold"
    TASK_ASSIGNED_ONCE = "task_assigned_once"
    POSITION_FILLED_ONCE = "position_filled_once"
    DEPENDENCY_ORDER = "dependency_order"


class QuboObjectiveSense(StrEnum):
    """Optimization direction for a QUBO problem."""

    MINIMIZE = "minimize"


class BinaryVariable(BaseModel):
    """A binary decision variable x in {0, 1}."""

    model_config = ConfigDict(frozen=True)

    id: str
    label: str = ""
    description: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class QuboTerm(BaseModel):
    """A linear or quadratic coefficient in the QUBO energy."""

    model_config = ConfigDict(frozen=True)

    variable_ids: tuple[str, ...]
    coefficient: float
    reason: str = ""

    @field_validator("variable_ids", mode="after")
    @classmethod
    def _validate_variables(cls, variable_ids: tuple[str, ...]) -> tuple[str, ...]:
        if len(variable_ids) not in {1, 2}:
            raise ValueError("QUBO terms must be linear or quadratic")
        if len(set(variable_ids)) != len(variable_ids):
            raise ValueError("QUBO term variables must be distinct")
        if any(not variable_id.strip() for variable_id in variable_ids):
            raise ValueError("QUBO term variable IDs cannot be empty")
        return variable_ids


class QuboConstraint(BaseModel):
    """A human-readable constraint and the penalty used to encode it."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"constraint_{uuid4().hex[:12]}")
    constraint_type: QuboConstraintType
    description: str
    variable_ids: list[str] = Field(default_factory=list)
    operator: str = ""
    target_value: float | None = None
    penalty_weight: float = Field(default=0.0, ge=0.0)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("variable_ids", mode="after")
    @classmethod
    def _dedupe_variable_ids(cls, values: list[str]) -> list[str]:
        seen: set[str] = set()
        normalized: list[str] = []
        for value in values:
            variable_id = value.strip()
            if not variable_id or variable_id in seen:
                continue
            seen.add(variable_id)
            normalized.append(variable_id)
        return normalized


class QuboObjective(BaseModel):
    """Narrative summary of the QUBO objective."""

    model_config = ConfigDict(frozen=True)

    sense: QuboObjectiveSense = QuboObjectiveSense.MINIMIZE
    description: str = ""
    reward_summary: list[str] = Field(default_factory=list)
    penalty_summary: list[str] = Field(default_factory=list)


class QuboProblem(BaseModel):
    """A complete binary optimization problem."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"qubo_{uuid4().hex[:12]}")
    run_id: str | None = None
    problem_type: QuboProblemType
    variables: list[BinaryVariable]
    linear_terms: list[QuboTerm] = Field(default_factory=list)
    quadratic_terms: list[QuboTerm] = Field(default_factory=list)
    constraints: list[QuboConstraint] = Field(default_factory=list)
    penalty_weights: dict[str, float] = Field(default_factory=dict)
    constant_offset: float = 0.0
    objective: QuboObjective = Field(default_factory=QuboObjective)
    source_benchmark_id: str | None = None
    source_frontier_id: str | None = None
    source_decision_trace_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @model_validator(mode="after")
    def _validate_references(self) -> QuboProblem:
        variable_ids = [variable.id for variable in self.variables]
        if len(set(variable_ids)) != len(variable_ids):
            raise ValueError("QUBO variable IDs must be unique")
        known = set(variable_ids)
        for term in [*self.linear_terms, *self.quadratic_terms]:
            unknown = set(term.variable_ids) - known
            if unknown:
                raise ValueError(f"QUBO term references unknown variables: {sorted(unknown)}")
        for constraint in self.constraints:
            unknown = set(constraint.variable_ids) - known
            if unknown:
                raise ValueError(
                    f"QUBO constraint {constraint.id} references unknown variables: "
                    f"{sorted(unknown)}"
                )
        return self


class QuboSolution(BaseModel):
    """A local solver result for a QUBO problem."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"qubo_solution_{uuid4().hex[:12]}")
    problem_id: str
    selected_variables: list[str] = Field(default_factory=list)
    objective_value: float
    constraint_violations: list[str] = Field(default_factory=list)
    feasible: bool
    solver_name: str
    iterations: int = Field(ge=0)
    explanation: str
    variable_values: dict[str, int] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class IsingTerm(BaseModel):
    """A linear or quadratic Ising coefficient over spin variables s in {-1, +1}."""

    model_config = ConfigDict(frozen=True)

    variable_ids: tuple[str, ...]
    coefficient: float
    reason: str = ""

    @field_validator("variable_ids", mode="after")
    @classmethod
    def _validate_variables(cls, variable_ids: tuple[str, ...]) -> tuple[str, ...]:
        if len(variable_ids) not in {1, 2}:
            raise ValueError("Ising terms must be linear or quadratic")
        if len(set(variable_ids)) != len(variable_ids):
            raise ValueError("Ising term variables must be distinct")
        return variable_ids


class IsingProblem(BaseModel):
    """An inspectable Ising transformation of a QUBO problem."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"ising_{uuid4().hex[:12]}")
    qubo_problem_id: str
    variables: list[str]
    linear_terms: list[IsingTerm] = Field(default_factory=list)
    quadratic_terms: list[IsingTerm] = Field(default_factory=list)
    constant_offset: float = 0.0
    convention: str = "x = (1 + s) / 2"
    explanation: str = (
        "Binary variables x in {0,1} are converted to spin variables s in {-1,+1} "
        "using x = (1 + s) / 2."
    )


class FormulationReport(BaseModel):
    """Summary returned when a fixture is formulated as QUBO."""

    model_config = ConfigDict(frozen=True)

    problem: QuboProblem
    summary: str
    variable_count: int = Field(ge=0)
    linear_term_count: int = Field(ge=0)
    quadratic_term_count: int = Field(ge=0)
    constraint_count: int = Field(ge=0)
    notes: list[str] = Field(default_factory=list)


class QuboComparisonResult(BaseModel):
    """Comparison between a QUBO solution and an existing baseline."""

    model_config = ConfigDict(frozen=True)

    fixture_id: str
    problem_type: QuboProblemType
    problem_id: str
    solution_id: str | None = None
    solver_name: str
    baseline_selected: str
    qubo_selected: str
    objective_difference: float
    feasible: bool
    token_comparison: dict[str, float] = Field(default_factory=dict)
    cost_comparison: dict[str, float] = Field(default_factory=dict)
    quality_comparison: dict[str, float] = Field(default_factory=dict)
    notes: list[str] = Field(default_factory=list)
