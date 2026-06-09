"""Approval gates for safe local tool execution."""

from __future__ import annotations

from hephaestus.tool_runtime.schemas import (
    ToolAction,
    ToolApprovalDecision,
    ToolApprovalRequest,
    ToolApprovalStatus,
    ToolRiskDecision,
)


def build_approval_request(
    action: ToolAction,
    risk_decision: ToolRiskDecision,
) -> ToolApprovalRequest:
    """Build the concise approval request for a risky action."""

    return ToolApprovalRequest(
        action_id=action.id,
        action_type=action.action_type,
        risk_level=risk_decision.risk_level,
        policy_profile=risk_decision.policy.profile_id,
        summary=action.summary or action.command or action.target_path or action.action_type.value,
        reasons=risk_decision.reasons,
    )


def decide_approval(
    request: ToolApprovalRequest,
    *,
    blocked: bool,
    approval_required: bool,
    yes: bool,
    dry_run: bool,
) -> ToolApprovalDecision:
    """Resolve non-interactive approval state for CLI execution."""

    if blocked:
        return ToolApprovalDecision(
            request_id=request.id,
            action_id=request.action_id,
            status=ToolApprovalStatus.BLOCKED,
            approved=False,
            reason="Blocked by tool runtime policy.",
        )
    if dry_run:
        return ToolApprovalDecision(
            request_id=request.id,
            action_id=request.action_id,
            status=ToolApprovalStatus.NOT_REQUIRED,
            approved=True,
            reason="Dry-run only; nothing executed.",
        )
    if not approval_required:
        return ToolApprovalDecision(
            request_id=request.id,
            action_id=request.action_id,
            status=ToolApprovalStatus.NOT_REQUIRED,
            approved=True,
            reason="No approval required for this risk level.",
        )
    if yes:
        return ToolApprovalDecision(
            request_id=request.id,
            action_id=request.action_id,
            status=ToolApprovalStatus.APPROVED,
            approved=True,
            reason="Approved by --yes.",
        )
    return ToolApprovalDecision(
        request_id=request.id,
        action_id=request.action_id,
        status=ToolApprovalStatus.PENDING,
        approved=False,
        reason="Approval required. Re-run with --yes after reviewing the plan.",
    )


def approval_message(decision: ToolApprovalDecision) -> str:
    """Return a short non-moralizing approval message."""

    if decision.status == ToolApprovalStatus.BLOCKED:
        return "Blocked by local tool policy."
    if decision.status == ToolApprovalStatus.PENDING:
        return "Approval required. Re-run with --yes after review."
    if decision.status == ToolApprovalStatus.APPROVED:
        return "Approved."
    return "No approval required."
