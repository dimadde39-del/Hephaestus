"""Rich renderers for validation plans and results."""

from __future__ import annotations

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table

from hephaestus.validation.schemas import ValidationExecutionPlan, ValidationSuiteResult


def build_validation_plan_renderable(plan: ValidationExecutionPlan) -> RenderableType:
    """Render a validation execution plan."""

    return Group(
        Panel(
            "\n".join(
                [
                    f"Plan: {plan.id}",
                    f"Repo: {plan.repo_path}",
                    f"Repo profile: {plan.repo_profile_id or '-'}",
                    f"Release plan: {plan.release_plan_id or '-'}",
                    f"Commands: {len(plan.commands)}",
                    f"Confidence: {plan.confidence:.2f}",
                    "",
                    "Run dry: heph validate run . --dry-run",
                    "Run approved: heph validate run . --yes",
                ]
            ),
            title="Validation Execution Plan",
        ),
        _plan_commands_table(plan),
        Panel("\n".join(plan.notes) or "No notes.", title="Plan Notes"),
    )


def build_validation_suite_renderable(suite: ValidationSuiteResult) -> RenderableType:
    """Render a completed validation suite result."""

    return Group(
        _suite_summary_panel(suite),
        _suite_commands_table(suite),
        _learning_table(suite),
        _suite_links_panel(suite),
    )


def build_validation_results_table(results: list[ValidationSuiteResult]) -> Table:
    """Render recent validation runs."""

    table = Table(title="Validation Runs")
    table.add_column("ID", no_wrap=True)
    table.add_column("Status")
    table.add_column("Repo", overflow="fold")
    table.add_column("Commands", justify="right")
    table.add_column("Passed", justify="right")
    table.add_column("Failed", justify="right")
    table.add_column("Created")
    for result in results:
        table.add_row(
            result.id,
            result.status.value,
            result.repo_path,
            str(len(result.command_results)),
            str(result.pass_count),
            str(result.fail_count + result.timed_out_count + result.blocked_count),
            result.created_at.isoformat(timespec="seconds"),
        )
    if not results:
        table.add_row("-", "-", "-", "-", "-", "-", "-")
    return table


def build_validation_show_renderable(suite: ValidationSuiteResult) -> RenderableType:
    """Render one validation result with evidence details."""

    return build_validation_suite_renderable(suite)


def _plan_commands_table(plan: ValidationExecutionPlan) -> Table:
    table = Table(title="Commands")
    table.add_column("Order", justify="right")
    table.add_column("Type")
    table.add_column("Command", overflow="fold")
    table.add_column("Risk")
    table.add_column("Approval")
    table.add_column("Source")
    table.add_column("Trace", overflow="fold")
    for command in plan.commands:
        table.add_row(
            str(command.order),
            command.command_type.value,
            command.command,
            command.risk_level.value,
            "blocked" if command.blocked else ("yes" if command.requires_approval else "no"),
            command.source or "-",
            command.decision_trace_id or "-",
        )
    if not plan.commands:
        table.add_row("-", "-", "No supported validation commands detected.", "-", "-", "-", "-")
    return table


def _suite_summary_panel(suite: ValidationSuiteResult) -> Panel:
    return Panel(
        "\n".join(
            [
                f"Result: {suite.id}",
                f"Plan: {suite.plan_id}",
                f"Repo: {suite.repo_path}",
                f"Status: {suite.status.value}",
                f"Evidence mode: {suite.evidence_mode}",
                f"Readiness impact: {suite.readiness_impact:+d}",
                f"Duration: {suite.duration_seconds:.2f}s",
                "",
                suite.summary,
            ]
        ),
        title="Validation Result",
    )


def _suite_commands_table(suite: ValidationSuiteResult) -> Table:
    table = Table(title="Command Evidence")
    table.add_column("Type")
    table.add_column("Status")
    table.add_column("Exit")
    table.add_column("Command", overflow="fold")
    table.add_column("Output", overflow="fold")
    table.add_column("Tool")
    table.add_column("Outcome")
    for result in suite.command_results:
        output = result.stderr_summary or result.stdout_summary or "-"
        if result.failure is not None:
            output = f"{result.failure.classification}: {output}"
        table.add_row(
            result.command_type.value,
            result.status.value,
            str(result.exit_code) if result.exit_code is not None else "-",
            result.command,
            output,
            result.tool_action_id or "-",
            result.outcome_id or "-",
        )
    if not suite.command_results:
        table.add_row("-", "-", "-", "No validation commands.", "-", "-", "-")
    return table


def _learning_table(suite: ValidationSuiteResult) -> Table:
    table = Table(title="Validation Learning Signals")
    table.add_column("Signal")
    table.add_column("Command")
    table.add_column("Summary", overflow="fold")
    table.add_column("Linked")
    for signal in suite.learning_signals:
        table.add_row(
            signal.signal_type,
            signal.command or "-",
            signal.summary,
            signal.learning_signal_id or signal.failure_memory_draft_id or "-",
        )
    if not suite.learning_signals:
        table.add_row("-", "-", "No validation learning signal created.", "-")
    return table


def _suite_links_panel(suite: ValidationSuiteResult) -> Panel:
    lines = [
        f"Show result: heph validate show {suite.id}",
        "Latest for repo: heph validate latest .",
    ]
    if suite.release_plan_id is not None:
        lines.append(f"Release plan: heph release show {suite.release_plan_id}")
    if suite.outcome_ids:
        lines.append(f"First outcome: heph outcome show {suite.outcome_ids[0]}")
    if suite.decision_trace_ids and suite.run_id is not None:
        lines.append(f"Decision trace: heph explain {suite.run_id}")
    return Panel("\n".join(lines), title="Linked Artifacts")
