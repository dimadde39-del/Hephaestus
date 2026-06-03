"""Tool schema."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from hephaestus.core.config import RiskLevel


class ToolDefinition(BaseModel):
    """Describes a tool before the runtime is allowed to execute it."""

    model_config = ConfigDict(frozen=True)

    name: str
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    risk_level: RiskLevel = RiskLevel.LOW
    side_effects: list[str] = Field(default_factory=list)
    requires_approval: bool = False
    timeout_seconds: int = Field(default=30, gt=0)


class ToolExecutionResult(BaseModel):
    """Normalized tool result shape for later audit logging."""

    tool_name: str
    ok: bool
    output: str
    error: str | None = None
