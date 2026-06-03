"""Basic safety policy for tools and shell commands."""

from __future__ import annotations

import re
from dataclasses import dataclass

from pydantic import BaseModel, Field

from hephaestus.core.config import RiskLevel
from hephaestus.tools.base import ToolDefinition


class SafetyDecision(BaseModel):
    """Policy outcome before executing an action."""

    allowed: bool
    requires_approval: bool = False
    risk_level: RiskLevel = RiskLevel.LOW
    reasons: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class DangerousPattern:
    pattern: re.Pattern[str]
    reason: str


class SafetyPolicy:
    """Phase 1 policy: read-only is allowed, risky side effects are approval-gated."""

    def __init__(self) -> None:
        self._dangerous_patterns = [
            DangerousPattern(re.compile(r"\brm\s+-rf\b", re.IGNORECASE), "recursive force delete"),
            DangerousPattern(
                re.compile(r"\bRemove-Item\b.*\b-Recurse\b", re.IGNORECASE),
                "recursive PowerShell delete",
            ),
            DangerousPattern(re.compile(r"\bgit\s+push\b", re.IGNORECASE), "git push"),
            DangerousPattern(re.compile(r"\bgit\s+commit\b", re.IGNORECASE), "git commit"),
            DangerousPattern(re.compile(r"\bnpm\s+publish\b", re.IGNORECASE), "package publish"),
            DangerousPattern(
                re.compile(r"\b(pip|uv)\s+publish\b", re.IGNORECASE), "package publish"
            ),
            DangerousPattern(re.compile(r"\.env\b", re.IGNORECASE), "command touches .env"),
            DangerousPattern(
                re.compile(r"\b(export|setx)\b.*(KEY|TOKEN|SECRET|PASSWORD)", re.IGNORECASE),
                "possible secret export",
            ),
            DangerousPattern(
                re.compile(r"\b(curl|wget)\b.*\|\s*(sh|bash|powershell|pwsh)", re.IGNORECASE),
                "network script piped to shell",
            ),
        ]

    def evaluate_tool(self, tool: ToolDefinition) -> SafetyDecision:
        if not tool.side_effects and not tool.requires_approval:
            return SafetyDecision(allowed=True, risk_level=tool.risk_level)
        reasons = ["tool has side effects"] if tool.side_effects else []
        if tool.requires_approval:
            reasons.append("tool requires approval")
        return SafetyDecision(
            allowed=False,
            requires_approval=True,
            risk_level=tool.risk_level,
            reasons=reasons,
        )

    def evaluate_shell_command(self, command: str) -> SafetyDecision:
        reasons = [
            dangerous.reason
            for dangerous in self._dangerous_patterns
            if dangerous.pattern.search(command)
        ]
        if reasons:
            return SafetyDecision(
                allowed=False,
                requires_approval=True,
                risk_level=RiskLevel.CRITICAL,
                reasons=reasons,
            )

        write_like = re.search(
            r"\b(del|erase|move|mv|cp|copy|touch|mkdir|new-item|set-content|add-content)\b",
            command,
            re.IGNORECASE,
        )
        if write_like:
            return SafetyDecision(
                allowed=False,
                requires_approval=True,
                risk_level=RiskLevel.MEDIUM,
                reasons=["command may write to the filesystem"],
            )
        return SafetyDecision(allowed=True, risk_level=RiskLevel.LOW)
