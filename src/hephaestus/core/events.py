"""Events for the Observe -> Understand -> Remember loop."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class EventType(StrEnum):
    OBSERVATION = "observation"
    GOAL_RECEIVED = "goal_received"
    PLAN_CREATED = "plan_created"
    ACTION_EVALUATED = "action_evaluated"
    RESULT_REFLECTED = "result_reflected"


class RuntimeEvent(BaseModel):
    """A typed event that can later be persisted to local state."""

    type: EventType
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
