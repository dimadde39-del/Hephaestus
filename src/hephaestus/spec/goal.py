"""Goal specification pipeline."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from pydantic import BaseModel, Field

from hephaestus.spec.constitution import DEFAULT_CONSTITUTION


class GoalSpec(BaseModel):
    """A deterministic spec produced from a user goal."""

    id: str = Field(default_factory=lambda: f"goal-{uuid4().hex[:8]}")
    raw_goal: str
    title: str
    intent: str
    constraints: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


def build_goal_spec(goal: str) -> GoalSpec:
    """Build a simple rule-based goal spec for Phase 1."""

    normalized = " ".join(goal.strip().split()).lower()
    constraints = DEFAULT_CONSTITUTION.as_constraints()

    if any(keyword in normalized for keyword in ("release", "publish", "ship")):
        return GoalSpec(
            raw_goal=goal,
            title="Prepare repository for release",
            intent="Assess release readiness, validate the project, and gate risky publish actions.",
            constraints=constraints
            + [
                "Do not publish, push, or commit without an approval-gated task.",
                "Prefer inspection and validation before mutation.",
            ],
            success_criteria=[
                "Repository structure and package manager are identified.",
                "Validation commands have been selected or run.",
                "Release readiness is summarized with risks and next actions.",
                "Any commit or push is represented as approval-required.",
            ],
        )

    return GoalSpec(
        raw_goal=goal,
        title=goal.strip()[:80] or "Untitled goal",
        intent="Turn the user goal into inspectable tasks that can be optimized before action.",
        constraints=constraints,
        success_criteria=[
            "Goal is decomposed into typed tasks.",
            "Task ordering respects dependencies.",
            "Risky actions are approval-gated.",
        ],
    )
