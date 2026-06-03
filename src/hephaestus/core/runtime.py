"""Small runtime orchestration helpers for Phase 1."""

from __future__ import annotations

from pydantic import BaseModel

from hephaestus.core.config import DEFAULT_CONFIG, RuntimeConfig
from hephaestus.optimize.context_packer import ContextCandidate, pack_context
from hephaestus.optimize.model_router import ModelRouteRequest, route_model
from hephaestus.optimize.task_scheduler import compare_schedulers
from hephaestus.spec.goal import GoalSpec, build_goal_spec
from hephaestus.spec.plan import ExecutionPlan
from hephaestus.spec.tasks import Task, generate_initial_tasks


class RuntimePlanningResult(BaseModel):
    """Result of turning a user goal into executable Phase 1 planning artifacts."""

    goal_spec: GoalSpec
    tasks: list[Task]
    plan: ExecutionPlan


def create_runtime_plan(
    goal: str,
    context_candidates: list[ContextCandidate] | None = None,
    config: RuntimeConfig = DEFAULT_CONFIG,
) -> RuntimePlanningResult:
    """Create a deterministic plan without requiring a live model call."""

    goal_spec = build_goal_spec(goal)
    tasks = generate_initial_tasks(goal_spec)
    comparison = compare_schedulers(tasks, config.objective_weights)
    context = pack_context(context_candidates or [], token_budget=config.input_token_budget)
    plan = ExecutionPlan(
        task_order=[task.id for task in comparison.best_order],
        selected_models={},
        selected_context_items=[item.id for item in context.selected],
        estimated_input_tokens=sum(task.estimated_input_tokens for task in tasks),
        estimated_output_tokens=sum(task.estimated_output_tokens for task in tasks),
        estimated_cost=0.0,
        risk_score=max((task.risk for task in tasks), default=0.0),
        objective_score=comparison.best_score,
        explanation=comparison.explanation,
    )
    return RuntimePlanningResult(goal_spec=goal_spec, tasks=tasks, plan=plan)


def choose_model_for_task(request: ModelRouteRequest) -> str:
    """Return a stable identifier for the model selected by the router."""

    route = route_model(request)
    return route.profile.identifier
