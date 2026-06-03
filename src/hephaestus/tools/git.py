"""Git tool definitions."""

from __future__ import annotations

from hephaestus.core.config import RiskLevel
from hephaestus.tools.base import ToolDefinition


def git_tools() -> list[ToolDefinition]:
    return [
        ToolDefinition(
            name="git.status",
            description="Inspect repository state.",
            input_schema={"path": "string"},
            output_schema={"status": "string"},
            risk_level=RiskLevel.LOW,
        ),
        ToolDefinition(
            name="git.commit",
            description="Create a git commit.",
            input_schema={"message": "string"},
            output_schema={"commit": "string"},
            risk_level=RiskLevel.HIGH,
            side_effects=["git-history"],
            requires_approval=True,
        ),
        ToolDefinition(
            name="git.push",
            description="Push commits to a remote.",
            input_schema={"remote": "string", "branch": "string"},
            output_schema={"remote": "string"},
            risk_level=RiskLevel.CRITICAL,
            side_effects=["external-send", "git-history"],
            requires_approval=True,
        ),
    ]
