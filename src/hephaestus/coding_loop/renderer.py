"""Rich renderers for repo-aware coding loop records."""

from __future__ import annotations

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.syntax import Syntax
from rich.table import Table

from hephaestus.coding_loop.schemas import (
    CodingChangeProposal,
    CodingLoopDetail,
    CodingLoopResult,
    CodingPlan,
)


def build_coding_plan_renderable(plan: CodingPlan) -> RenderableType:
    """Render a coding plan."""

    return Group(
        Panel(
            "\n".join(
                [
                    f"Request: {plan.request_id}",
                    f"Plan: {plan.id}",
                    f"Repo: {plan.repo_path}",
                    f"Scope: {plan.scope.scope_type.value}",
                    f"Risk: {plan.scope.risk.value}",
                    f"Status: {plan.status.value}",
                    f"Provider: {plan.provider_name} / {plan.provider_model}",
                    f"Source: {plan.provider_source}",
                    (
                        f"Usage: {plan.budget.calls} calls, "
                        f"{plan.budget.transport_attempts} transport attempts, "
                        f"{plan.budget.format_repair_calls} format repairs, "
                        f"{plan.budget.validation_repair_calls} validation repairs, "
                        f"{plan.budget.input_tokens}/{plan.budget.output_tokens} tokens, "
                        f"{_cost_text(plan.budget.estimated_cost, plan.budget.cost_metadata_source)}"
                    ),
                    f"Patch possible: {'yes' if plan.patch_proposal_possible else 'no'}",
                    f"Approval: {plan.approval_behavior}",
                    "",
                    plan.summary,
                ]
            ),
            title="Repo-Aware Coding Plan",
        ),
        _plan_files_table(plan),
        _plan_steps_table(plan),
        _validation_panel(plan),
        _next_command_panel(plan),
    )


def build_coding_change_renderable(change: CodingChangeProposal) -> RenderableType:
    """Render a coding patch proposal."""

    return Group(
        Panel(
            "\n".join(
                [
                    f"Change: {change.id}",
                    f"Request: {change.request_id}",
                    f"Plan: {change.plan_id}",
                    f"Scope: {change.scope_type.value}",
                    f"Risk: {change.risk.value}",
                    f"Approval required: {'yes' if change.approval_required else 'no'}",
                    f"Files: {', '.join(change.patch_set.files_touched) or '-'}",
                    "",
                    change.summary,
                ]
            ),
            title="Patch Proposal",
        ),
        Syntax(
            change.patch_set.diff
            or (
                change.manifest.model_dump_json(indent=2)
                if change.manifest is not None
                else "(no diff)"
            ),
            "json" if change.manifest is not None else "diff",
            word_wrap=True,
        ),
        _normalized_validation_panel(change),
        Panel(
            "\n".join(
                [
                    f"Patch ids: {', '.join(change.patch_set.patch_ids) or '-'}",
                    f"Tool actions: {', '.join(change.patch_set.tool_action_ids) or '-'}",
                    "Apply: heph code apply " + change.id + " --yes",
                ]
            ),
            title="Proposal Links",
        ),
    )


def build_coding_results_table(results: list[CodingLoopResult]) -> Table:
    """Render recent coding loop results."""

    table = Table(title="Coding Loop Results")
    table.add_column("ID", no_wrap=True)
    table.add_column("Request", no_wrap=True)
    table.add_column("Status")
    table.add_column("Scope")
    table.add_column("Risk")
    table.add_column("Validation")
    table.add_column("Summary", overflow="fold")
    for result in results:
        table.add_row(
            result.id,
            result.request_id,
            result.status.value,
            result.scope_type.value,
            result.risk.value,
            result.validation.status,
            result.summary,
        )
    if not results:
        table.add_row("-", "-", "-", "-", "-", "-", "No coding loop results yet.")
    return table


def build_coding_result_renderable(result: CodingLoopResult) -> RenderableType:
    """Render a coding loop result."""

    return Group(
        _result_panel(result),
        _validation_result_panel(result),
        _linked_artifacts_panel(result),
    )


def build_coding_show_renderable(detail: CodingLoopDetail) -> RenderableType:
    """Render a request/result detail view."""

    parts: list[RenderableType] = []
    if detail.request is not None:
        request = detail.request
        parts.append(
            Panel(
                "\n".join(
                    [
                        f"Request: {request.id}",
                        f"Repo: {request.repo_path}",
                        f"Repo profile: {request.repo_profile_id or '-'}",
                        f"Policy: {request.active_policy_profile or '-'}",
                        f"Conversation: {request.conversation_id or '-'}",
                        "",
                        request.user_request,
                    ]
                ),
                title="Coding Request",
            )
        )
    if detail.plan is not None:
        parts.append(build_coding_plan_renderable(detail.plan))
    if detail.change is not None:
        parts.append(build_coding_change_renderable(detail.change))
    if detail.iteration is not None:
        iteration = detail.iteration
        review_summary = ""
        review = iteration.metadata.get("review")
        if isinstance(review, dict):
            findings = review.get("findings")
            if isinstance(findings, list):
                review_summary = "\nReview: " + "; ".join(str(item) for item in findings)
        parts.append(
            Panel(
                "\n".join(
                    [
                        f"Iteration: {iteration.id}",
                        f"Status: {iteration.status.value}",
                        f"Checkpoint: {iteration.checkpoint_id or '-'}",
                        f"Rollback: {iteration.rollback_checkpoint_id or '-'}",
                        f"Validation: {iteration.validation_result_id or '-'}",
                        "",
                        iteration.summary + review_summary,
                    ]
                ),
                title="Iteration",
            )
        )
    if detail.result is not None:
        parts.append(build_coding_result_renderable(detail.result))
    if not parts:
        parts.append(Panel("No coding loop record found.", title="Coding Loop"))
    return Group(*parts)


def build_coding_conversation_proposal(plan: CodingPlan) -> RenderableType:
    """Render a non-executing coding proposal for conversation commands."""

    command = (
        f'heph code propose "{plan.user_request}" --repo "{plan.repo_path}"'
        if plan.patch_proposal_possible and not plan.scope_too_large
        else f'heph code plan "{plan.user_request}" --repo "{plan.repo_path}"'
    )
    return Group(
        Panel(
            "\n".join(
                [
                    "No files were changed.",
                    f"Scope: {plan.scope.scope_type.value}",
                    f"Risk: {plan.scope.risk.value}",
                    f"Patch possible: {'yes' if plan.patch_proposal_possible else 'no'}",
                    f"Likely files: {', '.join(plan.likely_files) or '-'}",
                    f"Validation: {', '.join(plan.validation_commands) or 'none detected'}",
                    "",
                    f"Next command: {command}",
                ]
            ),
            title="Proposed Coding Loop",
        )
    )


def _plan_files_table(plan: CodingPlan) -> Table:
    table = Table(title="Likely Files")
    table.add_column("Path", overflow="fold")
    for path in plan.likely_files:
        table.add_row(path)
    if not plan.likely_files:
        table.add_row("No clear target file.")
    return table


def _plan_steps_table(plan: CodingPlan) -> Table:
    table = Table(title="Loop Steps")
    table.add_column("Order", justify="right")
    table.add_column("Step")
    table.add_column("Approval")
    table.add_column("Summary", overflow="fold")
    for step in plan.steps:
        table.add_row(
            str(step.order),
            step.title,
            "yes" if step.requires_approval else "no",
            step.summary,
        )
    return table


def _validation_panel(plan: CodingPlan) -> Panel:
    return Panel(
        "\n".join(plan.validation_commands) or "No validation commands detected.",
        title=f"Validation Plan {plan.validation_plan_id or ''}".strip(),
    )


def _normalized_validation_panel(change: CodingChangeProposal) -> Panel:
    plan = change.metadata.get("normalized_validation_plan")
    if not isinstance(plan, dict):
        return Panel("Validation commands will be normalized before execution.", title="Normalized Validation")
    proposed = [str(item) for item in plan.get("model_proposed_commands", [])]
    normalized = [str(item) for item in plan.get("deterministic_normalized_commands", [])]
    reasons = [str(item) for item in plan.get("normalization_reasons", [])]
    locations = [str(item) for item in plan.get("expected_test_locations", [])]
    stages = [str(item) for item in plan.get("validation_stages", [])]
    timeouts = plan.get("timeouts", {})
    timeout_lines = (
        [f"{command}: {seconds}s" for command, seconds in timeouts.items()]
        if isinstance(timeouts, dict)
        else []
    )
    lines = [
        "Model-proposed validation commands:",
        *_lines_or_none(proposed),
        "",
        "Deterministic normalized commands:",
        *_lines_or_none(normalized),
        "",
        "Reasons:",
        *_lines_or_none(reasons),
        "",
        "Expected test locations:",
        *_lines_or_none(locations),
        "",
        f"Estimated validation stages: {len(stages)}",
        *[f"- {item}" for item in stages],
        "",
        "Timeouts:",
        *(timeout_lines or ["- default"]),
    ]
    return Panel("\n".join(lines), title="Normalized Validation")


def _lines_or_none(values: list[str]) -> list[str]:
    return [f"- {item}" for item in values] or ["- none"]


def _next_command_panel(plan: CodingPlan) -> Panel:
    if plan.scope_too_large:
        text = "Narrow the request, then run `heph code plan ...` again."
    elif plan.patch_proposal_possible:
        text = f'heph code propose "{plan.user_request}" --repo "{plan.repo_path}"'
    else:
        text = "Provide a clearer target file or exact find/replace text."
    return Panel(text, title="Next")


def _cost_text(estimated_cost: float, metadata_source: str) -> str:
    if estimated_cost == 0 and metadata_source == "unknown":
        return "Cost unknown"
    return f"${estimated_cost:.6f}"


def _result_panel(result: CodingLoopResult) -> Panel:
    return Panel(
        "\n".join(
            [
                f"Result: {result.id}",
                f"Request: {result.request_id}",
                f"Status: {result.status.value}",
                f"Scope: {result.scope_type.value}",
                f"Risk: {result.risk.value}",
                f"Repo: {result.repo_path}",
                "",
                result.summary,
            ]
        ),
        title="Coding Loop Result",
    )


def _validation_result_panel(result: CodingLoopResult) -> Panel:
    validation = result.validation
    return Panel(
        "\n".join(
            [
                f"Validation result: {validation.validation_result_id or '-'}",
                f"Status: {validation.status}",
                f"Evidence mode: {validation.evidence_mode}",
                f"Commands: {validation.command_count}",
                f"Passed: {validation.pass_count}",
                f"Failed/timed out: {validation.fail_count}",
                f"Skipped: {validation.skipped_count}",
                f"Blocked: {validation.blocked_count}",
                "",
                validation.summary or "-",
            ]
        ),
        title="Validation",
    )


def _linked_artifacts_panel(result: CodingLoopResult) -> Panel:
    lines = [
        f"Patch ids: {', '.join(result.patch_ids) or '-'}",
        f"Tool actions: {', '.join(result.tool_action_ids) or '-'}",
        f"Checkpoints: {', '.join(result.checkpoint_ids) or '-'}",
        f"Validation results: {', '.join(result.validation_result_ids) or '-'}",
        f"Outcomes: {', '.join(result.outcome_ids) or '-'}",
        f"Learning signals: {', '.join(result.learning_signal_ids) or '-'}",
        f"Decision traces: {', '.join(result.decision_trace_ids) or '-'}",
        f"Show: heph code show {result.request_id}",
    ]
    return Panel("\n".join(lines), title="Linked Artifacts")
