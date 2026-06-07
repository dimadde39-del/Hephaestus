"""Renderers for decision explanations and statistics."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table

from hephaestus.decision.analysis import CountMetric, DecisionStats, DecisionSummary
from hephaestus.decision.schemas import (
    DecisionAlternative,
    DecisionMetric,
    DecisionTraceVariant,
    DecisionType,
    MetricValue,
)
from hephaestus.outcomes.renderer import build_trace_outcome_table
from hephaestus.outcomes.schemas import OutcomeRecord, ReflectionRecord
from hephaestus.policy_learning.renderer import build_profile_application_table
from hephaestus.policy_learning.schemas import ProfileApplicationResult

_SECTION_ORDER = [
    DecisionType.OPTIMIZATION,
    DecisionType.TASK_SELECTION,
    DecisionType.MODEL_ROUTING,
    DecisionType.CONTEXT_SELECTION,
    DecisionType.BUDGET,
    DecisionType.SAFETY,
]

_SECTION_TITLES = {
    DecisionType.TASK_SELECTION: "Task Selection Decisions",
    DecisionType.MODEL_ROUTING: "Model Routing Decisions",
    DecisionType.CONTEXT_SELECTION: "Context Decisions",
    DecisionType.BUDGET: "Budget Decisions",
    DecisionType.SAFETY: "Safety Decisions",
    DecisionType.OPTIMIZATION: "Optimization Decisions",
}


def build_run_explanation_renderable(
    run_id: str,
    traces: Sequence[DecisionTraceVariant],
    outcomes_by_trace: Mapping[str, Sequence[OutcomeRecord]] | None = None,
    reflections_by_trace: Mapping[str, Sequence[ReflectionRecord]] | None = None,
    profile_applications: Sequence[ProfileApplicationResult] | None = None,
) -> Group:
    """Build a Rich grouped explanation for one run."""

    if not traces:
        return Group(Panel("No decision traces recorded for this run.", title=f"Run {run_id}"))

    renderables: list[RenderableType] = [
        Panel(
            (
                f"Decision traces: {len(traces)}\nRun: {run_id}\n"
                "Includes selected options, rejected alternatives, constraints, quality, "
                "cost, objective score, and confidence."
            ),
            title="Explainable Decision Trace",
        )
    ]
    grouped: dict[DecisionType, list[DecisionTraceVariant]] = defaultdict(list)
    for trace in traces:
        grouped[trace.decision_type].append(trace)

    for decision_type in _SECTION_ORDER:
        section = grouped.get(decision_type, [])
        if section:
            renderables.append(_trace_table(_SECTION_TITLES[decision_type], section))
    if outcomes_by_trace and any(outcomes_by_trace.values()):
        renderables.append(
            build_trace_outcome_table(
                outcomes_by_trace,
                reflections_by_trace or {},
            )
        )
    if profile_applications:
        renderables.append(build_profile_application_table(profile_applications))
    return Group(*renderables)


def build_decision_summary_renderable(run_id: str, summary: DecisionSummary) -> Group:
    """Build a Rich summary for one run."""

    overview = Table(title=f"Decision Summary: {run_id}")
    overview.add_column("Metric")
    overview.add_column("Value", justify="right")
    overview.add_row("Total decisions", str(summary.total_decisions))
    overview.add_row("Average confidence", f"{summary.average_confidence:.2f}")
    overview.add_row("Average objective score", f"{summary.average_objective_score:.2f}")
    overview.add_row("Token savings", f"{summary.token_savings:.0f}")
    overview.add_row("Approvals required", str(summary.approvals_required))

    type_table = _count_table("Decisions By Type", summary.decisions_by_type)
    rejection_table = _count_table("Top Rejection Reasons", summary.top_rejection_reasons)
    constraint_table = _count_table("Top Constraints", summary.top_constraints)
    return Group(overview, type_table, rejection_table, constraint_table)


def build_decision_stats_renderable(stats: DecisionStats) -> Group:
    """Build Rich aggregate decision statistics."""

    overview = Table(title="Decision Statistics")
    overview.add_column("Metric")
    overview.add_column("Value", justify="right")
    overview.add_row("Total runs", str(stats.total_runs))
    overview.add_row("Total traces", str(stats.total_traces))
    overview.add_row("Average confidence", f"{stats.average_confidence:.2f}")
    overview.add_row("Average objective score", f"{stats.average_objective_score:.2f}")
    overview.add_row("Average token savings", f"{stats.average_token_savings:.2f}")
    return Group(
        overview,
        _count_table("Traces By Type", stats.traces_by_type),
        _count_table("Most Common Selected Models", stats.most_common_selected_models),
        _count_table("Most Common Rejected Models", stats.most_common_rejected_models),
        _count_table("Most Common Rejection Reasons", stats.most_common_rejection_reasons),
        _count_table("Most Common Approval Triggers", stats.most_common_approval_triggers),
        _count_table("Top Constraints", stats.top_constraints),
    )


def render_run_explanation(run_id: str, traces: Sequence[DecisionTraceVariant]) -> str:
    """Render a full decision explanation for one run as plain text."""

    lines = ["Run:", run_id]
    if not traces:
        lines.extend(["", "No decision traces recorded for this run."])
        return "\n".join(lines)

    grouped: dict[DecisionType, list[DecisionTraceVariant]] = defaultdict(list)
    for trace in traces:
        grouped[trace.decision_type].append(trace)

    for decision_type in _SECTION_ORDER:
        section = grouped.get(decision_type, [])
        if not section:
            continue
        lines.extend(["", f"## {_SECTION_TITLES[decision_type]}"])
        for trace in section:
            lines.extend(_render_trace(trace))
    return "\n".join(lines)


def render_decision_summary(run_id: str, summary: DecisionSummary) -> str:
    """Render a compact per-run summary as plain text."""

    lines = [
        "Run:",
        run_id,
        "",
        "Decision Summary",
        f"Total decisions: {summary.total_decisions}",
        f"Average confidence: {summary.average_confidence:.2f}",
        f"Average objective score: {summary.average_objective_score:.2f}",
        f"Token savings: {summary.token_savings:.0f}",
        f"Approvals required: {summary.approvals_required}",
        "",
        "Decisions by type:",
    ]
    lines.extend(_render_counts(summary.decisions_by_type))
    lines.append("")
    lines.append("Top rejection reasons:")
    lines.extend(_render_counts(summary.top_rejection_reasons))
    lines.append("")
    lines.append("Top constraints:")
    lines.extend(_render_counts(summary.top_constraints))
    return "\n".join(lines)


def render_decision_stats(stats: DecisionStats) -> str:
    """Render aggregate decision statistics as plain text."""

    lines = [
        "Decision Statistics",
        f"Total runs: {stats.total_runs}",
        f"Total traces: {stats.total_traces}",
        f"Average token savings: {stats.average_token_savings:.2f}",
        f"Average confidence: {stats.average_confidence:.2f}",
        f"Average objective score: {stats.average_objective_score:.2f}",
        "",
        "Traces by type:",
    ]
    lines.extend(_render_counts(stats.traces_by_type))
    lines.append("")
    lines.append("Most common selected models:")
    lines.extend(_render_counts(stats.most_common_selected_models))
    lines.append("")
    lines.append("Most common rejected models:")
    lines.extend(_render_counts(stats.most_common_rejected_models))
    lines.append("")
    lines.append("Most common rejection reasons:")
    lines.extend(_render_counts(stats.most_common_rejection_reasons))
    lines.append("")
    lines.append("Most common approval triggers:")
    lines.extend(_render_counts(stats.most_common_approval_triggers))
    return "\n".join(lines)


def _trace_table(title: str, traces: Sequence[DecisionTraceVariant]) -> Table:
    table = Table(title=title)
    table.add_column("Trace", no_wrap=True)
    table.add_column("Phase")
    table.add_column("Selected")
    table.add_column("Why", overflow="fold")
    table.add_column("Rejected / Alternatives", overflow="fold")
    table.add_column("Constraints", overflow="fold")
    table.add_column("Score", justify="right")
    table.add_column("Conf.", justify="right")
    for trace in traces:
        table.add_row(
            trace.id,
            trace.phase,
            trace.selected_option,
            trace.rationale,
            _alternatives_text(trace.alternatives) or "-",
            ", ".join(trace.constraints_considered) or "-",
            f"{trace.objective_score:.2f}" if trace.objective_score is not None else "-",
            f"{trace.confidence:.2f}",
        )
    return table


def _count_table(title: str, counts: Sequence[CountMetric]) -> Table:
    table = Table(title=title)
    table.add_column("Label")
    table.add_column("Count", justify="right")
    if not counts:
        table.add_row("none", "0")
        return table
    for item in counts:
        table.add_row(item.label, str(item.count))
    return table


def _render_trace(trace: DecisionTraceVariant) -> list[str]:
    lines = [
        "",
        "Trace:",
        trace.id,
        "",
        "Phase:",
        trace.phase,
        "",
        "Selected:",
        trace.selected_option,
        "",
        "Reason:",
        trace.rationale or "-",
    ]
    if trace.alternatives:
        lines.extend(["", "Alternatives:"])
        lines.extend(_render_alternative(alternative) for alternative in trace.alternatives)
    if trace.objective_score is not None:
        lines.extend(["", f"Objective score: {trace.objective_score:.2f}"])
    lines.extend(["", f"Confidence: {trace.confidence:.2f}"])
    if trace.metrics:
        lines.extend(["", "Metrics:"])
        lines.extend(_render_metric(metric_item) for metric_item in trace.metrics)
    if trace.constraints_considered:
        lines.extend(["", "Constraints considered:"])
        lines.extend(trace.constraints_considered)
    if trace.learning_hooks:
        lines.extend(["", "Learning hooks:"])
        lines.extend(trace.learning_hooks)
    return lines


def _render_alternative(alternative: DecisionAlternative) -> str:
    details = []
    if alternative.score is not None:
        details.append(f"score={alternative.score:.2f}")
    if alternative.expected_quality is not None:
        details.append(f"expected_quality={alternative.expected_quality:.2f}")
    if alternative.would_have_cost is not None:
        details.append(f"would_have_cost={alternative.would_have_cost:.6g}")
    reason = alternative.rejection_reason or "not selected"
    suffix = f" ({'; '.join(details)})" if details else ""
    return f"{alternative.label}: {reason}{suffix}"


def _alternatives_text(alternatives: Sequence[DecisionAlternative]) -> str:
    return "; ".join(_render_alternative(alternative) for alternative in alternatives)


def _render_metric(metric_item: DecisionMetric) -> str:
    unit = f" {metric_item.unit}" if metric_item.unit else ""
    return f"{metric_item.name}={_metric_text(metric_item.value)}{unit}"


def _render_counts(counts: Sequence[CountMetric]) -> list[str]:
    if not counts:
        return ["- none"]
    return [f"{item.label}: {item.count}" for item in counts]


def _metric_text(value: MetricValue) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)
