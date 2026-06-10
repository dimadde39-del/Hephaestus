"""Rich renderers for tool runtime CLI output."""

from __future__ import annotations

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from hephaestus.tool_runtime.schemas import (
    CheckpointRecord,
    FilesystemListResult,
    FilesystemReadResult,
    FilesystemSearchResult,
    PatchProposal,
    ToolAction,
    ToolApprovalDecision,
    ToolExecutionPlan,
    ToolExecutionResult,
    ToolObservation,
    ToolProposal,
)


def build_tool_plan_renderable(plan: ToolExecutionPlan) -> RenderableType:
    """Render a classified tool execution plan."""

    decision = plan.risk_decision
    return Panel(
        "\n".join(
            [
                f"Action: {plan.action.action_type.value}",
                f"Risk: {decision.risk_level.value}",
                f"Policy: {decision.policy.profile_id}",
                f"Approval: {'yes' if plan.approval_required else 'no'}",
                f"Blocked: {'yes' if plan.blocked else 'no'}",
                f"Dry run: {'yes' if plan.dry_run else 'no'}",
                "Reasons: " + (", ".join(decision.reasons) or "-"),
            ]
        ),
        title="Tool Execution Plan",
    )


def build_tool_result_renderable(action: ToolAction, result: ToolExecutionResult) -> RenderableType:
    """Render a tool action result."""

    parts: list[RenderableType] = [
        Panel(
            "\n".join(
                [
                    f"Action: {action.id}",
                    f"Type: {action.action_type.value}",
                    f"Status: {result.status.value}",
                    f"Risk: {action.risk_level.value}",
                    f"Approval: {action.approval_status.value}",
                    f"Exit code: {result.exit_code if result.exit_code is not None else '-'}",
                    f"Checkpoint: {result.checkpoint_id or '-'}",
                    f"Decision trace: {result.decision_trace_id or '-'}",
                    f"Outcome: {result.outcome_id or '-'}",
                ]
            ),
            title="Tool Result",
        )
    ]
    if result.stdout:
        parts.append(Panel(result.stdout, title="stdout"))
    if result.stderr:
        parts.append(Panel(result.stderr, title="stderr"))
    if not result.stdout and result.stdout_summary:
        parts.append(Panel(result.stdout_summary, title="Observation"))
    return Group(*parts)


def build_filesystem_list_table(result: FilesystemListResult) -> Table:
    """Render directory entries."""

    table = Table(title=f"Directory: {result.path}")
    table.add_column("Path")
    table.add_column("Type")
    table.add_column("Size", justify="right")
    table.add_column("Protected")
    for entry in result.entries:
        table.add_row(
            entry.path,
            "dir" if entry.is_dir else "file",
            str(entry.size_bytes) if entry.is_file else "-",
            "yes" if entry.protected else "no",
        )
    return table


def build_filesystem_read_renderable(result: FilesystemReadResult) -> RenderableType:
    """Render a file read result."""

    if result.content is None:
        return Panel(
            "\n".join(
                [
                    result.message or "No content returned.",
                    f"Path: {result.path}",
                    f"Size: {result.metadata.size_bytes}",
                    f"Protected: {'yes' if result.protected else 'no'}",
                ]
            ),
            title="File Metadata",
        )
    return Panel(result.content, title=f"File: {result.path}")


def build_filesystem_search_table(result: FilesystemSearchResult) -> Table:
    """Render search matches."""

    table = Table(title=f"Search: {result.query}")
    table.add_column("Path")
    table.add_column("Line", justify="right")
    table.add_column("Text", overflow="fold")
    for match in result.matches:
        table.add_row(match.path, str(match.line_number), match.line)
    if not result.matches:
        table.add_row("-", "-", "No matches.")
    if result.skipped_protected:
        table.caption = "Protected files skipped: " + ", ".join(result.skipped_protected)
    return table


def build_patch_proposal_renderable(proposal: PatchProposal) -> RenderableType:
    """Render a stored patch proposal."""

    return Group(
        Panel(
            "\n".join(
                [
                    f"Patch: {proposal.id}",
                    f"Path: {proposal.path}",
                    f"Status: {proposal.status}",
                    f"Apply: heph tools patch apply {proposal.id} --yes",
                ]
            ),
            title="Patch Proposal",
        ),
        Syntax(proposal.diff, "diff", word_wrap=True),
    )


def build_tool_actions_table(actions: list[ToolAction]) -> Table:
    """Render recent tool actions."""

    table = Table(title="Tool Actions")
    table.add_column("ID", no_wrap=True)
    table.add_column("Type")
    table.add_column("Risk")
    table.add_column("Approval")
    table.add_column("Status")
    table.add_column("Summary", overflow="fold")
    for action in actions:
        table.add_row(
            action.id,
            action.action_type.value,
            action.risk_level.value,
            action.approval_status.value,
            action.execution_status.value,
            action.summary or action.command or action.target_path,
        )
    return table


def build_tool_action_detail(
    action: ToolAction,
    approvals: list[ToolApprovalDecision],
    results: list[ToolExecutionResult],
    observations: list[ToolObservation],
) -> RenderableType:
    """Render one action and its child records."""

    parts: list[RenderableType] = [
        Panel(
            "\n".join(
                [
                    f"Type: {action.action_type.value}",
                    f"Workspace: {action.workspace_path}",
                    f"Command: {action.command or '-'}",
                    f"Path: {action.target_path or '-'}",
                    f"Risk: {action.risk_level.value}",
                    f"Policy: {action.active_policy_profile}",
                    f"Approval: {action.approval_status.value}",
                    f"Execution: {action.execution_status.value}",
                    f"Checkpoint: {action.checkpoint_id or '-'}",
                    f"Decision trace: {action.decision_trace_id or '-'}",
                    f"Outcome: {action.outcome_id or '-'}",
                ]
            ),
            title=f"Tool Action {action.id}",
        )
    ]
    if approvals:
        table = Table(title="Approvals")
        table.add_column("ID")
        table.add_column("Status")
        table.add_column("Reason", overflow="fold")
        for approval in approvals:
            table.add_row(approval.id, approval.status.value, approval.reason)
        parts.append(table)
    if results:
        table = Table(title="Results")
        table.add_column("ID")
        table.add_column("Status")
        table.add_column("Exit")
        table.add_column("Summary", overflow="fold")
        for result in results:
            table.add_row(
                result.id,
                result.status.value,
                str(result.exit_code) if result.exit_code is not None else "-",
                result.stdout_summary or result.stderr_summary or "-",
            )
        parts.append(table)
    if observations:
        table = Table(title="Observations")
        table.add_column("Type")
        table.add_column("Signal")
        table.add_column("Summary", overflow="fold")
        for observation in observations:
            table.add_row(
                observation.observation_type,
                observation.signal,
                observation.summary,
            )
        parts.append(table)
    return Group(*parts)


def build_checkpoint_table(checkpoints: list[CheckpointRecord]) -> Table:
    """Render checkpoints."""

    table = Table(title="Tool Checkpoints")
    table.add_column("ID", no_wrap=True)
    table.add_column("Action")
    table.add_column("Files", overflow="fold")
    table.add_column("Created")
    table.add_column("Restored")
    for checkpoint in checkpoints:
        table.add_row(
            checkpoint.id,
            checkpoint.action_id or "-",
            ", ".join(checkpoint.files_touched) or "-",
            checkpoint.created_at.isoformat(timespec="seconds"),
            checkpoint.restored_at.isoformat(timespec="seconds") if checkpoint.restored_at else "-",
        )
    return table


def build_checkpoint_detail(checkpoint: CheckpointRecord) -> RenderableType:
    """Render checkpoint details."""

    table = Table(title=f"Checkpoint {checkpoint.id}")
    table.add_column("Path")
    table.add_column("Existed")
    table.add_column("Hash")
    for snapshot in checkpoint.files:
        table.add_row(
            snapshot.path,
            "yes" if snapshot.existed else "no",
            snapshot.hash_sha256 or "-",
        )
    return Group(
        Panel(
            "\n".join(
                [
                    f"Workspace: {checkpoint.workspace_path}",
                    f"Action: {checkpoint.action_id or '-'}",
                    f"Created: {checkpoint.created_at.isoformat(timespec='seconds')}",
                    f"Restored: {checkpoint.restored_at.isoformat(timespec='seconds') if checkpoint.restored_at else '-'}",
                ]
            ),
            title="Checkpoint Metadata",
        ),
        table,
    )


def build_tool_proposals_table(proposals: list[ToolProposal]) -> Table:
    """Render conversation tool proposals."""

    table = Table(title="Proposed Tool Actions")
    table.add_column("Order", justify="right")
    table.add_column("Action")
    table.add_column("Risk")
    table.add_column("Approval")
    table.add_column("Summary", overflow="fold")
    table.add_column("Command", overflow="fold")
    for proposal in proposals:
        table.add_row(
            str(proposal.order),
            proposal.action_type.value,
            proposal.risk_level.value,
            "blocked" if proposal.blocked else ("yes" if proposal.approval_required else "no"),
            proposal.summary,
            proposal.exact_cli_command,
        )
    return table
