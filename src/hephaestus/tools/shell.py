"""Shell tool definition."""

from __future__ import annotations

from pydantic import BaseModel

from hephaestus.core.config import RiskLevel
from hephaestus.tools.base import ToolDefinition


class ShellCommand(BaseModel):
    command: str
    cwd: str | None = None


def shell_tool() -> ToolDefinition:
    return ToolDefinition(
        name="shell.run",
        description="Run a local shell command after safety policy evaluation.",
        input_schema={"command": "string", "cwd": "string?"},
        output_schema={"stdout": "string", "stderr": "string", "exit_code": "integer"},
        risk_level=RiskLevel.HIGH,
        side_effects=["process"],
        requires_approval=True,
        timeout_seconds=120,
    )
