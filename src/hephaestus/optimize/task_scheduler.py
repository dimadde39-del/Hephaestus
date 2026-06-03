"""Scheduler comparison helpers."""

from __future__ import annotations

from pydantic import BaseModel

from hephaestus.core.config import ObjectiveWeights
from hephaestus.optimize.annealing import schedule_with_annealing
from hephaestus.optimize.greedy import SchedulerResult, schedule_greedy
from hephaestus.spec.tasks import Task


class SchedulerComparison(BaseModel):
    greedy: SchedulerResult
    annealed: SchedulerResult
    best_order: list[Task]
    best_score: float
    explanation: str


def compare_schedulers(
    tasks: list[Task],
    weights: ObjectiveWeights | None = None,
) -> SchedulerComparison:
    greedy = schedule_greedy(tasks, weights)
    annealed = schedule_with_annealing(tasks, weights)
    best = annealed if annealed.score >= greedy.score else greedy
    delta = annealed.score - greedy.score
    return SchedulerComparison(
        greedy=greedy,
        annealed=annealed,
        best_order=best.order,
        best_score=best.score,
        explanation=(
            f"Greedy score {greedy.score:.2f}; annealing score {annealed.score:.2f}; "
            f"delta {delta:+.2f}. Selected {best.explanation}"
        ),
    )
