"""Rich renderers for outcome learning artifacts."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table

from hephaestus.outcomes.analysis import OutcomeLearningSummary
from hephaestus.outcomes.schemas import (
    FailureMemoryDraft,
    LearningSignal,
    OutcomeRecord,
    PolicyUpdateSuggestion,
    ReflectionRecord,
)


def build_outcome_summary_renderable(summary: OutcomeLearningSummary) -> Table:
    """Build a compact outcome learning summary table."""

    table = Table(title="Outcome Learning Summary")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Outcomes", str(summary.total_outcomes))
    table.add_row("Success", str(summary.success_count))
    table.add_row("Failure", str(summary.failure_count))
    table.add_row("Partial", str(summary.partial_count))
    table.add_row("Unknown", str(summary.unknown_count))
    table.add_row("Reflections", str(summary.reflection_count))
    table.add_row("Learning signals", str(summary.learning_signal_count))
    table.add_row("Failure drafts", str(summary.failure_memory_draft_count))
    table.add_row("Policy suggestions", str(summary.policy_update_suggestion_count))
    return table


def build_outcome_list_renderable(outcomes: Sequence[OutcomeRecord]) -> Table:
    """Build a table of outcomes."""

    table = Table(title="Outcomes")
    table.add_column("ID", no_wrap=True)
    table.add_column("Status")
    table.add_column("Run", no_wrap=True)
    table.add_column("Trace", no_wrap=True)
    table.add_column("Severity", justify="right")
    table.add_column("Confidence", justify="right")
    table.add_column("Summary", overflow="fold")
    if not outcomes:
        table.add_row("none", "-", "-", "-", "-", "-", "No outcomes recorded.")
        return table
    for outcome in outcomes:
        table.add_row(
            outcome.id,
            outcome.status.value,
            outcome.run_id,
            outcome.decision_trace_id,
            f"{outcome.severity:.2f}",
            f"{outcome.confidence:.2f}",
            outcome.summary,
        )
    return table


def build_outcome_show_renderable(
    outcome: OutcomeRecord,
    reflections: Sequence[ReflectionRecord],
    learning_signals: Sequence[LearningSignal],
    failure_memory_drafts: Sequence[FailureMemoryDraft],
    policy_update_suggestions: Sequence[PolicyUpdateSuggestion],
) -> Group:
    """Build a detailed view for one outcome."""

    lines = [
        f"Run: {outcome.run_id}",
        f"Trace: {outcome.decision_trace_id}",
        f"Status: {outcome.status.value}",
        f"Severity: {outcome.severity:.2f}",
        f"Confidence: {outcome.confidence:.2f}",
        f"Tags: {', '.join(outcome.tags) or '-'}",
        "",
        outcome.summary,
    ]
    renderables: list[RenderableType] = [Panel("\n".join(lines), title=f"Outcome {outcome.id}")]
    if reflections:
        renderables.append(_reflection_table(reflections))
    if learning_signals:
        renderables.append(build_learning_signal_table(learning_signals))
    if failure_memory_drafts:
        renderables.append(build_failure_memory_table(failure_memory_drafts))
    if policy_update_suggestions:
        renderables.append(build_policy_update_table(policy_update_suggestions))
    return Group(*renderables)


def build_reflection_report_renderable(
    title: str,
    outcomes: Sequence[OutcomeRecord],
    reflections: Sequence[ReflectionRecord],
    learning_signals: Sequence[LearningSignal],
    failure_memory_drafts: Sequence[FailureMemoryDraft],
    policy_update_suggestions: Sequence[PolicyUpdateSuggestion],
    summary: OutcomeLearningSummary,
) -> Group:
    """Build the grouped output for `heph reflect` and benchmark evaluation."""

    renderables: list[RenderableType] = [
        build_outcome_summary_renderable(summary),
        _outcome_status_table("Successes", outcomes, "success"),
        _outcome_status_table("Failures", outcomes, "failure"),
        _outcome_status_table("Partials", outcomes, "partial"),
    ]
    if reflections:
        renderables.append(_reflection_table(reflections))
    if learning_signals:
        renderables.append(build_learning_signal_table(learning_signals))
    if failure_memory_drafts:
        renderables.append(build_failure_memory_table(failure_memory_drafts))
    if policy_update_suggestions:
        renderables.append(build_policy_update_table(policy_update_suggestions))
    return Group(Panel(title, title="Outcome Learning"), *renderables)


def build_learning_signal_table(signals: Sequence[LearningSignal]) -> Table:
    """Build a table of learning signals."""

    table = Table(title="Learning Signals")
    table.add_column("ID", no_wrap=True)
    table.add_column("Type")
    table.add_column("Direction")
    table.add_column("Target")
    table.add_column("Strength", justify="right")
    table.add_column("Status")
    table.add_column("Rationale", overflow="fold")
    if not signals:
        table.add_row("none", "-", "-", "-", "-", "-", "No learning signals recorded.")
        return table
    for signal in signals:
        table.add_row(
            signal.id,
            signal.signal_type.value,
            signal.direction.value,
            signal.target,
            f"{signal.strength:.2f}",
            signal.status.value,
            signal.rationale,
        )
    return table


def build_failure_memory_table(drafts: Sequence[FailureMemoryDraft]) -> Table:
    """Build a table of failure memory drafts."""

    table = Table(title="Failure Memory Drafts")
    table.add_column("ID", no_wrap=True)
    table.add_column("Run", no_wrap=True)
    table.add_column("Severity", justify="right")
    table.add_column("Importance", justify="right")
    table.add_column("Summary", overflow="fold")
    if not drafts:
        table.add_row("none", "-", "-", "-", "No failure memory drafts recorded.")
        return table
    for draft in drafts:
        table.add_row(
            draft.id,
            draft.run_id,
            f"{draft.severity:.2f}",
            f"{draft.suggested_memory_importance:.2f}",
            draft.summary,
        )
    return table


def build_policy_update_table(suggestions: Sequence[PolicyUpdateSuggestion]) -> Table:
    """Build a table of policy update suggestions."""

    table = Table(title="Policy Update Suggestions")
    table.add_column("ID", no_wrap=True)
    table.add_column("Area")
    table.add_column("Status")
    table.add_column("Suggested Rule", overflow="fold")
    table.add_column("Rationale", overflow="fold")
    if not suggestions:
        table.add_row("none", "-", "-", "No policy update suggestions recorded.", "-")
        return table
    for suggestion in suggestions:
        table.add_row(
            suggestion.id,
            suggestion.policy_area.value,
            suggestion.status.value,
            suggestion.suggested_rule,
            suggestion.rationale,
        )
    return table


def build_trace_outcome_table(
    outcomes_by_trace: Mapping[str, Sequence[OutcomeRecord]],
    reflections_by_trace: Mapping[str, Sequence[ReflectionRecord]],
) -> Table:
    """Build a table linking traces to outcomes and reflections."""

    table = Table(title="Outcome Learning")
    table.add_column("Trace", no_wrap=True)
    table.add_column("Outcome")
    table.add_column("Summary", overflow="fold")
    table.add_column("Reflection", overflow="fold")
    for trace_id, outcomes in outcomes_by_trace.items():
        for outcome in outcomes:
            reflections = reflections_by_trace.get(trace_id, [])
            reflection_text = "; ".join(
                reflection.recommended_change or reflection.what_worked or reflection.what_failed
                for reflection in reflections
                if reflection.outcome_id == outcome.id
            )
            table.add_row(
                trace_id,
                outcome.status.value,
                outcome.summary,
                reflection_text or "-",
            )
    return table


def _reflection_table(reflections: Sequence[ReflectionRecord]) -> Table:
    table = Table(title="Reflections")
    table.add_column("ID", no_wrap=True)
    table.add_column("Trace", no_wrap=True)
    table.add_column("Worked", overflow="fold")
    table.add_column("Failed", overflow="fold")
    table.add_column("Recommended Change", overflow="fold")
    for reflection in reflections:
        table.add_row(
            reflection.id,
            reflection.decision_trace_id,
            reflection.what_worked or "-",
            reflection.what_failed or "-",
            reflection.recommended_change or "-",
        )
    return table


def _outcome_status_table(
    title: str,
    outcomes: Sequence[OutcomeRecord],
    status: str,
) -> Table:
    filtered = [outcome for outcome in outcomes if outcome.status.value == status]
    table = Table(title=title)
    table.add_column("Outcome", no_wrap=True)
    table.add_column("Trace", no_wrap=True)
    table.add_column("Summary", overflow="fold")
    if not filtered:
        table.add_row("none", "-", f"No {status} outcomes.")
        return table
    for outcome in filtered:
        table.add_row(outcome.id, outcome.decision_trace_id, outcome.summary)
    return table
