"""Central objective function for task ordering."""

from __future__ import annotations

from pydantic import BaseModel, Field

from hephaestus.core.config import ObjectiveWeights
from hephaestus.spec.tasks import Task


class ObjectiveBreakdown(BaseModel):
    """Explainable score components for an ordered task list."""

    expected_value: float
    priority: float
    confidence: float
    token_cost: float
    risk_penalty: float
    uncertainty_penalty: float
    dependency_violation_penalty: float
    utility: float
    dependency_violations: int = Field(ge=0)


def score_task_order(
    tasks: list[Task],
    weights: ObjectiveWeights | None = None,
) -> ObjectiveBreakdown:
    """Score an ordered task list with quality, cost, risk, and dependency pressure."""

    weights = weights or ObjectiveWeights()
    expected_value = sum(task.expected_value for task in tasks) * weights.expected_value
    priority = sum(task.priority for task in tasks) * weights.priority
    confidence = sum(_success_proxy(task) for task in tasks) * weights.confidence
    token_cost = sum(task.estimated_total_tokens for task in tasks) * weights.token_cost
    risk_penalty = sum(task.risk for task in tasks) * weights.risk_penalty
    uncertainty_penalty = sum(task.uncertainty for task in tasks) * weights.uncertainty_penalty
    violations = count_dependency_violations(tasks)
    dependency_penalty = violations * weights.dependency_violation_penalty
    utility = (
        expected_value
        + priority
        + confidence
        - token_cost
        - risk_penalty
        - uncertainty_penalty
        - dependency_penalty
    )
    return ObjectiveBreakdown(
        expected_value=expected_value,
        priority=priority,
        confidence=confidence,
        token_cost=token_cost,
        risk_penalty=risk_penalty,
        uncertainty_penalty=uncertainty_penalty,
        dependency_violation_penalty=dependency_penalty,
        utility=utility,
        dependency_violations=violations,
    )


def count_dependency_violations(tasks: list[Task]) -> int:
    """Count dependencies that are missing or appear after the task."""

    seen: set[str] = set()
    task_ids = {task.id for task in tasks}
    violations = 0
    for task in tasks:
        for dependency in task.dependencies:
            if dependency not in task_ids or dependency not in seen:
                violations += 1
        seen.add(task.id)
    return violations


def task_priority_score(task: Task, weights: ObjectiveWeights | None = None) -> float:
    """Score a single ready task for greedy scheduling."""

    weights = weights or ObjectiveWeights()
    return (
        task.expected_value * weights.expected_value
        + task.priority * weights.priority
        + _success_proxy(task) * weights.confidence
        - task.estimated_total_tokens * weights.token_cost
        - task.risk * weights.risk_penalty
        - task.uncertainty * weights.uncertainty_penalty
    )


def _success_proxy(task: Task) -> float:
    return max(0.0, 1.0 - task.uncertainty - task.risk * 0.5)
