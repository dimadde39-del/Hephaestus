"""Risk classification for local tool actions."""

from __future__ import annotations

from pathlib import Path

from hephaestus.policy.schemas import PolicyProfile, PolicyProfileType
from hephaestus.repo.risk import classify_command
from hephaestus.repo.schemas import CommandRiskCategory
from hephaestus.tool_runtime.schemas import (
    ToolAction,
    ToolActionType,
    ToolApprovalPolicy,
    ToolRiskDecision,
    ToolRiskLevel,
)


def classify_tool_action(
    action_type: ToolActionType,
    *,
    policy_profile: PolicyProfile,
    command: str = "",
    target_path: str = "",
    protected_path: bool = False,
) -> ToolRiskDecision:
    """Classify one action and apply the active policy profile."""

    policy = approval_policy_from_profile(policy_profile)
    risk_level, reasons = _base_risk(
        action_type,
        command=command,
        target_path=target_path,
        protected_path=protected_path,
    )
    approval_required, blocked, policy_decision = _apply_policy(
        action_type,
        risk_level,
        policy,
    )
    if protected_path:
        reasons.append("protected file content is not printed by default")
    if blocked:
        reasons.append("blocked by active tool approval policy")
    elif approval_required:
        reasons.append("approval required by active tool approval policy")
    return ToolRiskDecision(
        risk_level=risk_level,
        approval_required=approval_required,
        blocked=blocked,
        reasons=list(dict.fromkeys(reasons)),
        policy=policy,
        policy_decision=policy_decision,
    )


def classify_action_instance(
    action: ToolAction,
    *,
    policy_profile: PolicyProfile,
    protected_path: bool = False,
) -> ToolRiskDecision:
    """Classify an already constructed action."""

    return classify_tool_action(
        action.action_type,
        policy_profile=policy_profile,
        command=action.command,
        target_path=action.target_path,
        protected_path=protected_path,
    )


def approval_policy_from_profile(profile: PolicyProfile) -> ToolApprovalPolicy:
    """Resolve tool runtime defaults from the active Phase 5D policy profile."""

    profile_type = profile.profile_type
    if profile_type == PolicyProfileType.RESEARCH:
        return ToolApprovalPolicy(
            profile_id=profile.id,
            profile_name=profile.name,
            allow_safe_validation=False,
            require_approval_for_validation=True,
            notes=["Research profile allows read-only exploration and approval-gates execution."],
        )
    if profile_type == PolicyProfileType.STRICT:
        return ToolApprovalPolicy(
            profile_id=profile.id,
            profile_name=profile.name,
            allow_safe_validation=False,
            require_approval_for_validation=True,
            block_high_risk=True,
            block_external_side_effects=True,
            notes=["Strict profile blocks high-risk and external side-effect tool actions."],
        )
    return ToolApprovalPolicy(
        profile_id=profile.id,
        profile_name=profile.name,
        notes=["Local development profile keeps benign work direct and approval-gates side effects."],
    )


def risk_from_command_category(category: CommandRiskCategory) -> ToolRiskLevel:
    """Map repo intelligence command risk to tool runtime risk."""

    return {
        CommandRiskCategory.SAFE_READONLY: ToolRiskLevel.SAFE_READONLY,
        CommandRiskCategory.SAFE_VALIDATION: ToolRiskLevel.SAFE_VALIDATION,
        CommandRiskCategory.MEDIUM_RISK: ToolRiskLevel.MEDIUM_RISK,
        CommandRiskCategory.HIGH_RISK: ToolRiskLevel.HIGH_RISK,
        CommandRiskCategory.DESTRUCTIVE: ToolRiskLevel.DESTRUCTIVE,
        CommandRiskCategory.EXTERNAL_SIDE_EFFECT: ToolRiskLevel.EXTERNAL_SIDE_EFFECT,
    }[category]


def risk_rank(level: ToolRiskLevel) -> int:
    """Return a sortable risk rank."""

    return {
        ToolRiskLevel.SAFE_READONLY: 0,
        ToolRiskLevel.SAFE_VALIDATION: 1,
        ToolRiskLevel.MEDIUM_RISK: 2,
        ToolRiskLevel.HIGH_RISK: 3,
        ToolRiskLevel.EXTERNAL_SIDE_EFFECT: 4,
        ToolRiskLevel.DESTRUCTIVE: 5,
    }[level]


def _base_risk(
    action_type: ToolActionType,
    *,
    command: str,
    target_path: str,
    protected_path: bool,
) -> tuple[ToolRiskLevel, list[str]]:
    if action_type == ToolActionType.RUN_COMMAND:
        category, reasons, _requires_approval = classify_command(command)
        return risk_from_command_category(category), reasons
    if action_type in {
        ToolActionType.LIST_DIRECTORY,
        ToolActionType.SEARCH_FILES,
    }:
        return ToolRiskLevel.SAFE_READONLY, ["read-only filesystem inspection"]
    if action_type == ToolActionType.READ_FILE:
        if protected_path or _looks_protected(target_path):
            return ToolRiskLevel.HIGH_RISK, ["path looks like a protected secret or credential file"]
        return ToolRiskLevel.SAFE_READONLY, ["read-only file inspection"]
    if action_type == ToolActionType.PROPOSE_PATCH:
        return ToolRiskLevel.SAFE_READONLY, ["patch proposal only; no file mutation"]
    if action_type == ToolActionType.CREATE_CHECKPOINT:
        return ToolRiskLevel.SAFE_READONLY, ["checkpoint captures local rollback metadata"]
    if action_type in {ToolActionType.APPLY_PATCH, ToolActionType.RESTORE_CHECKPOINT}:
        return ToolRiskLevel.MEDIUM_RISK, ["writes local files inside the workspace"]
    return ToolRiskLevel.MEDIUM_RISK, ["unrecognized action type"]


def _apply_policy(
    action_type: ToolActionType,
    risk_level: ToolRiskLevel,
    policy: ToolApprovalPolicy,
) -> tuple[bool, bool, str]:
    if risk_level == ToolRiskLevel.DESTRUCTIVE:
        return True, policy.block_destructive, "block" if policy.block_destructive else "require_approval"
    if risk_level == ToolRiskLevel.EXTERNAL_SIDE_EFFECT:
        if policy.block_external_side_effects:
            return True, True, "block"
        return policy.require_approval_for_external, False, "require_approval"
    if risk_level == ToolRiskLevel.HIGH_RISK:
        if policy.block_high_risk:
            return True, True, "block"
        return policy.require_approval_for_high, False, "require_approval"
    if risk_level == ToolRiskLevel.MEDIUM_RISK:
        return policy.require_approval_for_medium, False, "require_approval"
    if risk_level == ToolRiskLevel.SAFE_VALIDATION:
        if action_type == ToolActionType.RUN_COMMAND and policy.require_approval_for_validation:
            return True, False, "require_approval"
        return False, False, "allow"
    return False, False, "allow"


def _looks_protected(path: str) -> bool:
    name = Path(path).name.lower()
    lowered = path.lower()
    if name == ".env" or name.startswith(".env."):
        return True
    if name in {"id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"}:
        return True
    if name.endswith((".pem", ".key", ".p12", ".pfx", ".kdbx")):
        return True
    return any(token in lowered for token in ("credential", "secret", "token", "password"))
