"""Command and repository risk classification for read-only repo intelligence."""

from __future__ import annotations

import re

from hephaestus.repo.schemas import CommandRiskCategory, RiskSignal, ScriptCommand
from hephaestus.safety.policy import SafetyPolicy

_SAFETY_POLICY = SafetyPolicy()

_DESTRUCTIVE_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\brm\s+-rf\b", re.IGNORECASE), "recursive force delete"),
    (re.compile(r"\bRemove-Item\b.*\b-Recurse\b", re.IGNORECASE), "recursive delete"),
    (re.compile(r"\b(drop|truncate)\s+(database|schema|table)\b", re.IGNORECASE), "database drop"),
    (re.compile(r"\b(db|database|prisma|sequelize|rails)\b.*\b(reset|wipe|drop)\b", re.IGNORECASE), "database reset"),
)

_EXTERNAL_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bgit\s+push\b", re.IGNORECASE), "git push changes remote state"),
    (re.compile(r"\b(npm|pnpm|yarn|bun|uv|poetry|twine|cargo)\s+publish\b", re.IGNORECASE), "package publish"),
    (re.compile(r"\bdocker\s+push\b", re.IGNORECASE), "docker push"),
    (re.compile(r"\b(vercel|netlify|flyctl|railway|render|firebase)\b.*\b(deploy|publish)\b", re.IGNORECASE), "deployment command"),
    (re.compile(r"\b(curl|wget)\b.*\|\s*(sh|bash|powershell|pwsh)\b", re.IGNORECASE), "network script piped to shell"),
    (re.compile(r"\b(export|setx)\b.*(KEY|TOKEN|SECRET|PASSWORD)", re.IGNORECASE), "possible secret export"),
)

_HIGH_RISK_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\.env\b", re.IGNORECASE), "command touches environment files"),
    (re.compile(r"\b(KEY|TOKEN|SECRET|PASSWORD)\b", re.IGNORECASE), "command references secret-like material"),
    (re.compile(r"\b(deploy|release|publish|upload)\b", re.IGNORECASE), "release or deployment workflow"),
    (re.compile(r"\b(db|database|prisma|sequelize|alembic|django-admin)\b.*\bmigrate\b", re.IGNORECASE), "database migration"),
)

_MEDIUM_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\b(install|add|upgrade|update)\b", re.IGNORECASE), "dependency mutation or install"),
    (re.compile(r"\b(dev|serve|start)\b", re.IGNORECASE), "long-running local server"),
    (re.compile(r"\bdocker\s+(build|compose|run|up)\b", re.IGNORECASE), "docker local side effects"),
    (re.compile(r"\b(git\s+commit|git\s+tag)\b", re.IGNORECASE), "local git write"),
)

_VALIDATION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(test|pytest|vitest|jest|ruff|mypy|lint|eslint|clippy|check|fmt\s+--check|tsc|build)\b", re.IGNORECASE),
    re.compile(r"\bgo\s+(test|build)\b", re.IGNORECASE),
    re.compile(r"\bcargo\s+(test|build|check|clippy|fmt)\b", re.IGNORECASE),
)

_READONLY_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b(ls|dir|cat|type|head|tail|grep|rg|find|git\s+status|git\s+log|git\s+diff)\b", re.IGNORECASE),
)


def classify_command(command: str) -> tuple[CommandRiskCategory, list[str], bool]:
    """Classify a command suggestion without executing it."""

    normalized = " ".join(command.strip().split())
    reasons: list[str] = []
    for pattern, reason in _DESTRUCTIVE_PATTERNS:
        if pattern.search(normalized):
            reasons.append(reason)
    if reasons:
        return CommandRiskCategory.DESTRUCTIVE, reasons, True

    for pattern, reason in _EXTERNAL_PATTERNS:
        if pattern.search(normalized):
            reasons.append(reason)
    if reasons:
        return CommandRiskCategory.EXTERNAL_SIDE_EFFECT, reasons, True

    for pattern, reason in _HIGH_RISK_PATTERNS:
        if pattern.search(normalized):
            reasons.append(reason)
    if reasons:
        return CommandRiskCategory.HIGH_RISK, reasons, True

    for pattern, reason in _MEDIUM_PATTERNS:
        if pattern.search(normalized):
            reasons.append(reason)
    if reasons:
        return CommandRiskCategory.MEDIUM_RISK, reasons, False

    policy_decision = _SAFETY_POLICY.evaluate_shell_command(normalized)
    if policy_decision.requires_approval:
        return CommandRiskCategory.MEDIUM_RISK, list(policy_decision.reasons), True

    if any(pattern.search(normalized) for pattern in _VALIDATION_PATTERNS):
        return CommandRiskCategory.SAFE_VALIDATION, ["validation command"], False

    if any(pattern.search(normalized) for pattern in _READONLY_PATTERNS):
        return CommandRiskCategory.SAFE_READONLY, ["read-only command"], False

    return CommandRiskCategory.MEDIUM_RISK, ["unrecognized command; suggest only with review"], False


def classify_script(
    *,
    name: str,
    command: str,
    source: str,
    package_manager: str = "",
    raw_command: str = "",
) -> ScriptCommand:
    """Build a classified ScriptCommand from detected script metadata."""

    raw = raw_command or command
    command_classification, command_reasons, command_requires_approval = classify_command(command)
    raw_classification, raw_reasons, raw_requires_approval = classify_command(raw)
    if _risk_rank(raw_classification) > _risk_rank(command_classification):
        classification = raw_classification
        reasons = raw_reasons
    else:
        classification = command_classification
        reasons = command_reasons
    return ScriptCommand(
        name=name,
        command=command,
        source=source,
        package_manager=package_manager,
        raw_command=raw,
        classification=classification,
        reasons=list(dict.fromkeys([*reasons, *_script_name_reasons(name)])),
        requires_approval=(
            command_requires_approval
            or raw_requires_approval
            or classification
            in {
                CommandRiskCategory.HIGH_RISK,
                CommandRiskCategory.DESTRUCTIVE,
                CommandRiskCategory.EXTERNAL_SIDE_EFFECT,
            }
        ),
    )


def build_command_risk_signals(scripts: list[ScriptCommand]) -> list[RiskSignal]:
    """Return risk signals for scripts that are not safe validation/read-only commands."""

    risky = [
        script
        for script in scripts
        if script.classification
        in {
            CommandRiskCategory.HIGH_RISK,
            CommandRiskCategory.DESTRUCTIVE,
            CommandRiskCategory.EXTERNAL_SIDE_EFFECT,
        }
    ]
    return [
        RiskSignal(
            level=script.classification,
            category="script_command",
            summary=f"Script '{script.name}' is classified as {script.classification.value}.",
            evidence=[script.command, script.raw_command, *script.reasons],
            mitigation="Require explicit approval before execution and inspect the raw script body.",
        )
        for script in risky
    ]


def _script_name_reasons(name: str) -> list[str]:
    lowered = name.lower()
    reasons: list[str] = []
    if any(keyword in lowered for keyword in ("deploy", "publish", "release")):
        reasons.append("script name indicates release or deployment")
    if any(keyword in lowered for keyword in ("reset", "wipe", "destroy")):
        reasons.append("script name indicates destructive workflow")
    return reasons


def _risk_rank(category: CommandRiskCategory) -> int:
    return {
        CommandRiskCategory.SAFE_READONLY: 0,
        CommandRiskCategory.SAFE_VALIDATION: 1,
        CommandRiskCategory.MEDIUM_RISK: 2,
        CommandRiskCategory.HIGH_RISK: 3,
        CommandRiskCategory.EXTERNAL_SIDE_EFFECT: 4,
        CommandRiskCategory.DESTRUCTIVE: 5,
    }[category]
