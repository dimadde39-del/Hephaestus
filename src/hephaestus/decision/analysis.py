"""Aggregate analysis helpers for persisted decision traces."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field

from hephaestus.decision.schemas import (
    DecisionMetric,
    DecisionTraceVariant,
    DecisionType,
    MetricValue,
)


class CountMetric(BaseModel):
    """A counted label for summary and stats output."""

    model_config = ConfigDict(frozen=True)

    label: str
    count: int = Field(ge=0)


class DecisionSummary(BaseModel):
    """Per-run decision summary."""

    model_config = ConfigDict(frozen=True)

    total_decisions: int = Field(ge=0)
    decisions_by_type: list[CountMetric] = Field(default_factory=list)
    task_decisions: int = Field(ge=0)
    model_decisions: int = Field(ge=0)
    context_decisions: int = Field(ge=0)
    budget_decisions: int = Field(ge=0)
    safety_decisions: int = Field(ge=0)
    optimization_decisions: int = Field(ge=0)
    top_rejection_reasons: list[CountMetric] = Field(default_factory=list)
    top_constraints: list[CountMetric] = Field(default_factory=list)
    average_confidence: float = 0.0
    average_objective_score: float = 0.0
    token_savings: float = 0.0
    approvals_required: int = Field(default=0, ge=0)


class DecisionStats(BaseModel):
    """Aggregate stats across all persisted decision traces."""

    model_config = ConfigDict(frozen=True)

    total_runs: int = Field(ge=0)
    total_traces: int = Field(ge=0)
    total_decisions: int = Field(ge=0)
    traces_by_type: list[CountMetric] = Field(default_factory=list)
    most_common_selected_models: list[CountMetric] = Field(default_factory=list)
    most_common_model_selections: list[CountMetric] = Field(default_factory=list)
    most_common_rejected_models: list[CountMetric] = Field(default_factory=list)
    most_common_model_rejections: list[CountMetric] = Field(default_factory=list)
    most_common_rejection_reasons: list[CountMetric] = Field(default_factory=list)
    most_common_approval_triggers: list[CountMetric] = Field(default_factory=list)
    top_constraints: list[CountMetric] = Field(default_factory=list)
    common_context_exclusion_reasons: list[CountMetric] = Field(default_factory=list)
    average_token_savings: float = 0.0
    average_confidence: float = 0.0
    average_objective_score: float = 0.0


def summarize_decisions(traces: Iterable[DecisionTraceVariant]) -> DecisionSummary:
    """Summarize the decision mix for a single run."""

    trace_list = list(traces)
    counts = Counter(trace.decision_type for trace in trace_list)
    objective_scores = [
        trace.objective_score for trace in trace_list if trace.objective_score is not None
    ]
    return DecisionSummary(
        total_decisions=len(trace_list),
        decisions_by_type=_type_counts(counts),
        task_decisions=counts[DecisionType.TASK_SELECTION],
        model_decisions=counts[DecisionType.MODEL_ROUTING],
        context_decisions=counts[DecisionType.CONTEXT_SELECTION],
        budget_decisions=counts[DecisionType.BUDGET],
        safety_decisions=counts[DecisionType.SAFETY],
        optimization_decisions=counts[DecisionType.OPTIMIZATION],
        top_rejection_reasons=_top_counts(_rejection_reasons(trace_list)),
        top_constraints=_top_counts(_constraints(trace_list)),
        average_confidence=_average([trace.confidence for trace in trace_list]),
        average_objective_score=_average(objective_scores),
        token_savings=sum(_numeric_metric(_metric(trace.metrics, "token_savings")) or 0.0 for trace in trace_list),
        approvals_required=sum(1 for trace in trace_list if _approval_required(trace)),
    )


def aggregate_decision_stats(traces: Iterable[DecisionTraceVariant]) -> DecisionStats:
    """Aggregate simple operational stats across all runs."""

    trace_list = list(traces)
    type_counter = Counter(trace.decision_type for trace in trace_list)
    selected_models: Counter[str] = Counter()
    rejected_models: Counter[str] = Counter()
    approval_triggers: Counter[str] = Counter()
    context_exclusion_reasons: Counter[str] = Counter()
    token_savings: list[float] = []
    objective_scores: list[float] = []

    for trace in trace_list:
        if trace.decision_type == DecisionType.MODEL_ROUTING:
            if trace.selected_option != "unrouted":
                selected_models[trace.selected_option] += 1
            for alternative in trace.alternatives:
                rejected_models[alternative.option_id] += 1
        if trace.decision_type == DecisionType.SAFETY and _approval_required(trace):
            approval_trigger = str(_metric(trace.metrics, "action") or trace.selected_option)
            approval_triggers[approval_trigger] += 1
        if trace.decision_type == DecisionType.CONTEXT_SELECTION:
            for alternative in trace.alternatives:
                reason = alternative.rejection_reason
                if reason:
                    context_exclusion_reasons[reason] += 1
        savings = _numeric_metric(_metric(trace.metrics, "token_savings"))
        if savings is not None:
            token_savings.append(savings)
        if trace.objective_score is not None:
            objective_scores.append(trace.objective_score)

    model_selections = _top_counts(selected_models)
    model_rejections = _top_counts(rejected_models)
    return DecisionStats(
        total_runs=len({trace.run_id for trace in trace_list}),
        total_traces=len(trace_list),
        total_decisions=len(trace_list),
        traces_by_type=_type_counts(type_counter),
        most_common_selected_models=model_selections,
        most_common_model_selections=model_selections,
        most_common_rejected_models=model_rejections,
        most_common_model_rejections=model_rejections,
        most_common_rejection_reasons=_top_counts(_rejection_reasons(trace_list)),
        most_common_approval_triggers=_top_counts(approval_triggers),
        top_constraints=_top_counts(_constraints(trace_list)),
        common_context_exclusion_reasons=_top_counts(context_exclusion_reasons),
        average_token_savings=_average(token_savings),
        average_confidence=_average([trace.confidence for trace in trace_list]),
        average_objective_score=_average(objective_scores),
    )


def most_common_rejection_reason(traces: Iterable[DecisionTraceVariant]) -> str:
    """Return the most frequent rejection reason label, if any."""

    top = _top_counts(_rejection_reasons(list(traces)), limit=1)
    return top[0].label if top else ""


def most_common_rationale(traces: Iterable[DecisionTraceVariant]) -> str:
    """Return the most frequent non-empty rationale, if any."""

    rationale_counts = Counter(trace.rationale for trace in traces if trace.rationale)
    top = rationale_counts.most_common(1)
    return top[0][0] if top else ""


def _type_counts(counter: Counter[DecisionType]) -> list[CountMetric]:
    return [
        CountMetric(label=decision_type.value, count=counter[decision_type])
        for decision_type in DecisionType
        if counter[decision_type] > 0
    ]


def _rejection_reasons(traces: Iterable[DecisionTraceVariant]) -> Counter[str]:
    reasons: Counter[str] = Counter()
    for trace in traces:
        for alternative in trace.alternatives:
            if alternative.rejection_reason:
                reasons[alternative.rejection_reason] += 1
    return reasons


def _constraints(traces: Iterable[DecisionTraceVariant]) -> Counter[str]:
    constraints: Counter[str] = Counter()
    for trace in traces:
        constraints.update(trace.constraints_considered)
        for alternative in trace.alternatives:
            constraints.update(alternative.violated_constraints)
    return constraints


def _top_counts(counter: Counter[str], *, limit: int = 5) -> list[CountMetric]:
    return [CountMetric(label=label, count=count) for label, count in counter.most_common(limit)]


def _approval_required(trace: DecisionTraceVariant) -> bool:
    return trace.decision_type == DecisionType.SAFETY and (
        _metric(trace.metrics, "approval_required") is True
        or trace.selected_option.startswith("approval_required")
    )


def _metric(metrics: Iterable[DecisionMetric], name: str) -> MetricValue:
    for item in metrics:
        if item.name == name:
            return item.value
    return None


def _numeric_metric(value: MetricValue | None) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(value)
    except ValueError:
        return None


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)
