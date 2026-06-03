"""Greedy dependency-aware task scheduling."""

from __future__ import annotations

from pydantic import BaseModel

from hephaestus.core.config import ObjectiveWeights
from hephaestus.optimize.objective import ObjectiveBreakdown, score_task_order, task_priority_score
from hephaestus.spec.tasks import Task


class SchedulerResult(BaseModel):
    """Common scheduler result."""

    order: list[Task]
    score: float
    breakdown: ObjectiveBreakdown
    explanation: str


def schedule_greedy(
    tasks: list[Task],
    weights: ObjectiveWeights | None = None,
) -> SchedulerResult:
    """Build a task order by repeatedly picking the highest-value ready task."""

    weights = weights or ObjectiveWeights()
    remaining = {task.id: task for task in tasks}
    completed: set[str] = set()
    order: list[Task] = []

    while remaining:
        ready = [
            task
            for task in remaining.values()
            if all(dependency in completed for dependency in task.dependencies)
        ]
        if not ready:
            ready = list(remaining.values())
        chosen = max(ready, key=lambda task: (task_priority_score(task, weights), -task.risk))
        order.append(chosen)
        completed.add(chosen.id)
        del remaining[chosen.id]

    breakdown = score_task_order(order, weights)
    return SchedulerResult(
        order=order,
        score=breakdown.utility,
        breakdown=breakdown,
        explanation=(
            "Greedy baseline selected the highest-scoring dependency-ready task at each step."
        ),
    )
