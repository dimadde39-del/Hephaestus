"""Integration helpers for tool runtime traces, outcomes, and proposals."""

from __future__ import annotations

from pathlib import Path

from hephaestus.decision import DecisionAlternative, DecisionTraceRepository, SafetyDecision, metric
from hephaestus.outcomes import (
    OutcomeEvidence,
    OutcomeRecord,
    OutcomeRepository,
    OutcomeStatus,
    outcome_metric,
)
from hephaestus.policy.schemas import PolicyProfile
from hephaestus.repo import RepoProfile
from hephaestus.storage import RunRecord, RunRepository
from hephaestus.tool_runtime.classifier import classify_tool_action
from hephaestus.tool_runtime.schemas import (
    ToolAction,
    ToolActionType,
    ToolExecutionResult,
    ToolExecutionStatus,
    ToolProposal,
    ToolRiskDecision,
    ToolRiskLevel,
)


def record_tool_decision_and_outcome(
    database_path: Path | str,
    action: ToolAction,
    risk_decision: ToolRiskDecision,
    result: ToolExecutionResult,
) -> tuple[ToolAction, ToolExecutionResult]:
    """Create a safety decision trace and minimal outcome for an important tool result."""

    run_repository = RunRepository(database_path)
    trace_repository = DecisionTraceRepository(database_path)
    outcome_repository = OutcomeRepository(database_path)
    run = run_repository.save_run(
        RunRecord(
            goal=f"Tool action: {action.summary or action.action_type.value}",
            mode="tool_runtime",
        )
    )
    trace = SafetyDecision(
        run_id=run.id,
        phase="tool_runtime",
        selected_option=_selected_option(action, result),
        alternatives=[
            DecisionAlternative(
                option_id="execute_without_gate",
                rejection_reason="Tool runtime records risk and approval before execution.",
                violated_constraints=["approval policy", "auditability"],
                risk=_risk_value(risk_decision.risk_level),
            )
        ],
        rationale=", ".join(risk_decision.reasons) or "Tool action classified before execution.",
        metrics=[
            metric("action_id", action.id),
            metric("action_type", action.action_type.value),
            metric("risk_level", risk_decision.risk_level.value),
            metric("approval_required", risk_decision.approval_required),
            metric("blocked", risk_decision.blocked),
            metric("policy_profile", risk_decision.policy.profile_id),
            metric("execution_status", result.status.value),
            metric("exit_code", result.exit_code),
        ],
        objective_score=1.0 if result.status == ToolExecutionStatus.SUCCEEDED else 0.0,
        confidence=0.86,
        constraints_considered=[
            "workspace boundary",
            "policy profile",
            "risk classification",
            "approval gate",
        ],
        tags=["tool-runtime", action.action_type.value, risk_decision.risk_level.value],
        caused_by=[action.id],
        will_affect=["tool_observations", "outcome_learning"],
        learning_hooks=["tool_result_outcome", "risk_policy_precision"],
    )
    trace_repository.save_trace(trace)
    status = _outcome_status(result.status)
    outcome = outcome_repository.save_outcome(
        OutcomeRecord(
            run_id=run.id,
            decision_trace_id=trace.id,
            status=status,
            summary=_outcome_summary(action, result),
            metrics=[
                outcome_metric("exit_code", result.exit_code),
                outcome_metric("duration_seconds", result.duration_seconds, unit="seconds"),
                outcome_metric("timed_out", result.timed_out),
                outcome_metric("output_truncated", result.output_truncated),
            ],
            evidence=[
                OutcomeEvidence(
                    evidence_type="tool_output",
                    source=action.action_type.value,
                    content=_compact_output(result),
                    metadata={"action_id": action.id},
                )
            ],
            severity=0.0 if status == OutcomeStatus.SUCCESS else 0.55,
            confidence=0.82,
            tags=["tool-runtime", action.action_type.value],
        )
    )
    run_repository.complete_run(
        run.id,
        estimated_input_tokens=0,
        estimated_output_tokens=0,
        estimated_cost=0.0,
        objective_score=1.0 if status == OutcomeStatus.SUCCESS else 0.0,
        risk_score=_risk_value(risk_decision.risk_level),
        summary=outcome.summary,
        status="completed",
    )
    updated_action = action.model_copy(
        update={
            "run_id": run.id,
            "decision_trace_id": trace.id,
            "outcome_id": outcome.id,
        }
    )
    updated_result = result.model_copy(
        update={
            "decision_trace_id": trace.id,
            "outcome_id": outcome.id,
        }
    )
    return updated_action, updated_result


def propose_tool_actions(
    prompt: str,
    *,
    policy_profile: PolicyProfile,
    repo_profile: RepoProfile | None = None,
    repo_path: Path | str | None = None,
) -> list[ToolProposal]:
    """Build deterministic tool proposals for conversation output without execution."""

    workspace = Path(repo_path or ".")
    proposals: list[ToolProposal] = []
    order = 1
    proposals.append(
        _proposal(
            order,
            action_type=ToolActionType.LIST_DIRECTORY,
            summary="Inspect the workspace top level.",
            risk_level=ToolRiskLevel.SAFE_READONLY,
            approval_required=False,
            exact_cli_command=f'heph tools list "{workspace}"',
            reasons=["read-only workspace inspection"],
        )
    )
    order += 1
    if repo_profile is not None and repo_profile.validation_plan.commands:
        proposals.append(
            _proposal(
                order,
                action_type=ToolActionType.RUN_COMMAND,
                summary="Build an evidence plan for release validation commands.",
                risk_level=ToolRiskLevel.SAFE_READONLY,
                approval_required=False,
                exact_cli_command=f"heph validate plan {workspace}",
                reasons=[
                    "collects detected lint, test, typecheck, and build commands",
                    "does not execute repository commands",
                ],
            )
        )
        order += 1
        proposals.append(
            _proposal(
                order,
                action_type=ToolActionType.RUN_COMMAND,
                summary="Dry-run validation to show approvals and command evidence shape.",
                risk_level=ToolRiskLevel.SAFE_VALIDATION,
                approval_required=False,
                exact_cli_command=f"heph validate run {workspace} --dry-run",
                reasons=[
                    "records planned validation without running commands",
                    "shows how results would affect release readiness",
                ],
            )
        )
        order += 1
        validation_decision = classify_tool_action(
            ToolActionType.RUN_COMMAND,
            policy_profile=policy_profile,
            command=repo_profile.validation_plan.commands[0].command,
        )
        proposals.append(
            _proposal(
                order,
                action_type=ToolActionType.RUN_COMMAND,
                summary="Run approved validation and turn tool results into release evidence.",
                risk_level=validation_decision.risk_level,
                approval_required=True,
                blocked=validation_decision.blocked,
                exact_cli_command=f"heph validate run {workspace} --yes",
                reasons=[
                    "executes safe validation commands through the tool runtime",
                    "captures stdout/stderr summaries, outcomes, and learning signals",
                    "release readiness is upgraded or downgraded from real evidence",
                ],
            )
        )
        order += 1
        for command in repo_profile.validation_plan.commands[:5]:
            decision = classify_tool_action(
                ToolActionType.RUN_COMMAND,
                policy_profile=policy_profile,
                command=command.command,
            )
            proposals.append(
                _proposal(
                    order,
                    action_type=ToolActionType.RUN_COMMAND,
                    summary=f"Validate with `{command.command}`.",
                    risk_level=decision.risk_level,
                    approval_required=decision.approval_required,
                    blocked=decision.blocked,
                    exact_cli_command=f'heph tools run "{command.command}" --dry-run',
                    reasons=decision.reasons,
                )
            )
            order += 1
        return proposals
    decision = classify_tool_action(
        ToolActionType.RUN_COMMAND,
        policy_profile=policy_profile,
        command="python --version",
    )
    proposals.append(
        _proposal(
            order,
            action_type=ToolActionType.RUN_COMMAND,
            summary="Check local Python availability.",
            risk_level=decision.risk_level,
            approval_required=decision.approval_required,
            blocked=decision.blocked,
            exact_cli_command='heph tools run "python --version" --dry-run',
            reasons=decision.reasons,
        )
    )
    return proposals


def _proposal(
    order: int,
    *,
    action_type: ToolActionType,
    summary: str,
    risk_level: ToolRiskLevel,
    approval_required: bool,
    exact_cli_command: str,
    reasons: list[str],
    blocked: bool = False,
) -> ToolProposal:
    return ToolProposal(
        order=order,
        action_type=action_type,
        summary=summary,
        risk_level=risk_level,
        approval_required=approval_required,
        blocked=blocked,
        exact_cli_command=exact_cli_command,
        reasons=reasons,
    )


def _selected_option(action: ToolAction, result: ToolExecutionResult) -> str:
    if result.status == ToolExecutionStatus.BLOCKED:
        return f"blocked: {action.action_type.value}"
    if result.status == ToolExecutionStatus.APPROVAL_REQUIRED:
        return f"approval_required: {action.action_type.value}"
    return f"{result.status.value}: {action.action_type.value}"


def _outcome_status(status: ToolExecutionStatus) -> OutcomeStatus:
    if status in {ToolExecutionStatus.SUCCEEDED, ToolExecutionStatus.RESTORED}:
        return OutcomeStatus.SUCCESS
    if status in {ToolExecutionStatus.FAILED, ToolExecutionStatus.TIMED_OUT, ToolExecutionStatus.BLOCKED}:
        return OutcomeStatus.FAILURE
    if status in {ToolExecutionStatus.APPROVAL_REQUIRED, ToolExecutionStatus.DRY_RUN}:
        return OutcomeStatus.PARTIAL
    return OutcomeStatus.UNKNOWN


def _outcome_summary(action: ToolAction, result: ToolExecutionResult) -> str:
    subject = action.command or action.target_path or action.action_type.value
    if result.status == ToolExecutionStatus.SUCCEEDED:
        return f"Tool action succeeded: {subject}"
    if result.status == ToolExecutionStatus.TIMED_OUT:
        return f"Tool action timed out: {subject}"
    if result.status == ToolExecutionStatus.APPROVAL_REQUIRED:
        return f"Tool action paused for approval: {subject}"
    if result.status == ToolExecutionStatus.BLOCKED:
        return f"Tool action blocked: {subject}"
    return f"Tool action finished with status {result.status.value}: {subject}"


def _compact_output(result: ToolExecutionResult) -> str:
    parts = []
    if result.stdout_summary:
        parts.append(f"stdout: {result.stdout_summary}")
    if result.stderr_summary:
        parts.append(f"stderr: {result.stderr_summary}")
    return "\n".join(parts) or result.status.value


def _risk_value(risk_level: ToolRiskLevel) -> float:
    return {
        ToolRiskLevel.SAFE_READONLY: 0.05,
        ToolRiskLevel.SAFE_VALIDATION: 0.15,
        ToolRiskLevel.MEDIUM_RISK: 0.4,
        ToolRiskLevel.HIGH_RISK: 0.7,
        ToolRiskLevel.EXTERNAL_SIDE_EFFECT: 0.85,
        ToolRiskLevel.DESTRUCTIVE: 1.0,
    }[risk_level]
