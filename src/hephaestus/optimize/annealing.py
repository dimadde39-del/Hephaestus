"""Simulated annealing scheduler."""

from __future__ import annotations

import math
import random

from hephaestus.core.config import ObjectiveWeights
from hephaestus.optimize.greedy import SchedulerResult, schedule_greedy
from hephaestus.optimize.objective import score_task_order
from hephaestus.spec.tasks import Task


def schedule_with_annealing(
    tasks: list[Task],
    weights: ObjectiveWeights | None = None,
    *,
    iterations: int = 500,
    initial_temperature: float = 6.0,
    cooling_rate: float = 0.985,
    seed: int = 17,
) -> SchedulerResult:
    """Optimize task ordering with a small simulated annealing loop."""

    if not tasks:
        return schedule_greedy(tasks, weights)

    weights = weights or ObjectiveWeights()
    rng = random.Random(seed)
    current = schedule_greedy(tasks, weights).order
    current_score = score_task_order(current, weights).utility
    best = list(current)
    best_score = current_score
    temperature = initial_temperature

    for _ in range(iterations):
        candidate = _neighbor(current, rng)
        candidate_score = score_task_order(candidate, weights).utility
        if _accept(candidate_score, current_score, temperature, rng):
            current = candidate
            current_score = candidate_score
        if candidate_score > best_score:
            best = candidate
            best_score = candidate_score
        temperature = max(0.001, temperature * cooling_rate)

    breakdown = score_task_order(best, weights)
    return SchedulerResult(
        order=best,
        score=breakdown.utility,
        breakdown=breakdown,
        explanation=(
            "Simulated annealing explored task-order swaps while dependency violations carried "
            "a large objective penalty."
        ),
    )


def _neighbor(order: list[Task], rng: random.Random) -> list[Task]:
    candidate = list(order)
    if len(candidate) < 2:
        return candidate
    first, second = rng.sample(range(len(candidate)), 2)
    candidate[first], candidate[second] = candidate[second], candidate[first]
    return candidate


def _accept(
    candidate_score: float,
    current_score: float,
    temperature: float,
    rng: random.Random,
) -> bool:
    if candidate_score >= current_score:
        return True
    probability = math.exp((candidate_score - current_score) / max(temperature, 0.001))
    return rng.random() < probability
