"""Execution plan schema."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ExecutionPlan(BaseModel):
    """Selected work order, model/context choices, and optimization score."""

    task_order: list[str] = Field(default_factory=list)
    selected_models: dict[str, str] = Field(default_factory=dict)
    selected_context_items: list[str] = Field(default_factory=list)
    estimated_input_tokens: int = Field(ge=0)
    estimated_output_tokens: int = Field(ge=0)
    estimated_cost: float = Field(ge=0)
    risk_score: float = Field(ge=0, le=1)
    objective_score: float
    explanation: str

    @property
    def estimated_total_tokens(self) -> int:
        return self.estimated_input_tokens + self.estimated_output_tokens
