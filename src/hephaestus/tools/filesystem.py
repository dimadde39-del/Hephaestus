"""Filesystem tool definitions."""

from __future__ import annotations

from hephaestus.core.config import RiskLevel
from hephaestus.tools.base import ToolDefinition


def filesystem_tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="filesystem.read",
            description="Read files or list directories inside an approved workspace.",
            input_schema={"path": "string"},
            output_schema={"content": "string"},
            risk_level=RiskLevel.LOW,
            side_effects=[],
        ),
        ToolDefinition(
            name="filesystem.write",
            description="Create or update files inside an approved workspace.",
            input_schema={"path": "string", "content": "string"},
            output_schema={"path": "string"},
            risk_level=RiskLevel.MEDIUM,
            side_effects=["write"],
            requires_approval=True,
        ),
    ]
