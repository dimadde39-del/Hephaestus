"""Deterministic outcome evaluators for benchmark and optimization traces."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from hephaestus.decision.repository import DecisionTraceRepository
from hephaestus.decision.schemas import (
    DecisionAlternative,
    DecisionMetric,
    DecisionTraceVariant,
    DecisionType,
    MetricValue,
)
from hephaestus.outcomes.repository import OutcomeRepository
from hephaestus.outcomes.schemas import (
    FailureMemoryDraft,
    LearningDirection,
    LearningSignal,
    LearningSignalType,
    OutcomeEvidence,
    OutcomeMetric,
    OutcomeRecord,
    OutcomeStatus,
    PolicyArea,
    PolicyUpdateSuggestion,
    ReflectionRecord,
    outcome_metric,
)


class OutcomeEvaluationBatch(BaseModel):
    """Outcome learning artifacts produced or loaded for one run."""

    model_config = ConfigDict(frozen=True)

    outcomes: list[OutcomeRecord] = Field(default_factory=list)
    reflections: list[ReflectionRecord] = Field(default_factory=list)
    learning_signals: list[LearningSignal] = Field(default_factory=list)
    failure_memory_drafts: list[FailureMemoryDraft] = Field(default_factory=list)
    policy_update_suggestions: list[PolicyUpdateSuggestion] = Field(default_factory=list)


def evaluate_run_outcomes(
    run_id: str,
    *,
    repository: OutcomeRepository | None = None,
    trace_repository: DecisionTraceRepository | None = None,
) -> OutcomeEvaluationBatch:
    """Evaluate missing outcomes for a run and persist all generated artifacts."""

    outcome_repository = repository or OutcomeRepository()
    traces = _trace_repository(trace_repository, outcome_repository).list_traces(run_id=run_id)
    existing_trace_ids = {
        outcome.decision_trace_id
        for outcome in outcome_repository.list_outcomes_by_run(run_id)
    }
    batch = OutcomeEvaluationBatch()
    for trace in traces:
        if trace.id in existing_trace_ids:
            continue
        outcome = outcome_repository.save_outcome(_evaluate_trace_outcome(trace))
        reflection = outcome_repository.save_reflection(reflect_on_outcome(trace, outcome))
        artifacts = _learning_artifacts_for_outcome(trace, outcome, reflection)
        saved_signals = [
            outcome_repository.save_learning_signal(signal)
            for signal in artifacts.learning_signals
        ]
        saved_drafts = [
            outcome_repository.save_failure_memory_draft(draft)
            for draft in artifacts.failure_memory_drafts
        ]
        saved_suggestions = [
            outcome_repository.save_policy_update_suggestion(suggestion)
            for suggestion in artifacts.policy_update_suggestions
        ]
        batch = OutcomeEvaluationBatch(
            outcomes=[*batch.outcomes, outcome],
            reflections=[*batch.reflections, reflection],
            learning_signals=[*batch.learning_signals, *saved_signals],
            failure_memory_drafts=[*batch.failure_memory_drafts, *saved_drafts],
            policy_update_suggestions=[*batch.policy_update_suggestions, *saved_suggestions],
        )
    return batch


def reflect_run_outcomes(
    run_id: str,
    *,
    repository: OutcomeRepository | None = None,
    trace_repository: DecisionTraceRepository | None = None,
) -> OutcomeEvaluationBatch:
    """Ensure a run has outcomes, reflections, and derived learning artifacts."""

    outcome_repository = repository or OutcomeRepository()
    resolved_trace_repository = _trace_repository(trace_repository, outcome_repository)
    evaluate_run_outcomes(
        run_id,
        repository=outcome_repository,
        trace_repository=resolved_trace_repository,
    )
    traces = {trace.id: trace for trace in resolved_trace_repository.list_traces(run_id=run_id)}
    for outcome in outcome_repository.list_outcomes_by_run(run_id):
        trace = traces.get(outcome.decision_trace_id)
        if trace is None:
            continue
        _ensure_outcome_artifacts(outcome_repository, trace, outcome)
    return _batch_for_run(outcome_repository, run_id)


def reflect_on_outcome(
    trace: DecisionTraceVariant,
    outcome: OutcomeRecord,
) -> ReflectionRecord:
    """Create a deterministic reflection for one trace/outcome pair."""

    if outcome.status == OutcomeStatus.SUCCESS:
        worked = _success_reflection(trace, outcome)
        failed = ""
        likely_cause = _success_cause(trace)
        recommended = _success_recommendation(trace, outcome)
    elif outcome.status == OutcomeStatus.FAILURE:
        worked = ""
        failed = _failure_reflection(trace, outcome)
        likely_cause = _failure_cause(trace, outcome)
        recommended = _failure_recommendation(trace, outcome)
    elif outcome.status == OutcomeStatus.PARTIAL:
        worked = _partial_worked(trace, outcome)
        failed = _partial_failed(trace, outcome)
        likely_cause = _partial_cause(trace)
        recommended = _partial_recommendation(trace)
    else:
        worked = ""
        failed = ""
        likely_cause = "The outcome is not yet observable from current benchmark evidence."
        recommended = "Collect a concrete success or failure signal before changing policy."
    return ReflectionRecord(
        outcome_id=outcome.id,
        run_id=outcome.run_id,
        decision_trace_id=outcome.decision_trace_id,
        what_worked=worked,
        what_failed=failed,
        likely_cause=likely_cause,
        recommended_change=recommended,
        confidence=min(trace.confidence, outcome.confidence),
        tags=[*outcome.tags, "reflection", trace.decision_type.value],
    )


def _ensure_outcome_artifacts(
    repository: OutcomeRepository,
    trace: DecisionTraceVariant,
    outcome: OutcomeRecord,
) -> None:
    reflections = repository.list_reflections(outcome_id=outcome.id)
    reflection = reflections[0] if reflections else repository.save_reflection(reflect_on_outcome(trace, outcome))
    artifacts = _learning_artifacts_for_outcome(trace, outcome, reflection)
    if not repository.list_learning_signals(outcome_id=outcome.id):
        for signal in artifacts.learning_signals:
            repository.save_learning_signal(signal)
    if not repository.list_failure_memory_drafts(outcome_id=outcome.id):
        for draft in artifacts.failure_memory_drafts:
            repository.save_failure_memory_draft(draft)
    if not repository.list_policy_update_suggestions(outcome_id=outcome.id):
        for suggestion in artifacts.policy_update_suggestions:
            repository.save_policy_update_suggestion(suggestion)


def _batch_for_run(repository: OutcomeRepository, run_id: str) -> OutcomeEvaluationBatch:
    outcomes = repository.list_outcomes_by_run(run_id)
    return OutcomeEvaluationBatch(
        outcomes=outcomes,
        reflections=repository.list_reflections(run_id=run_id),
        learning_signals=repository.list_learning_signals(run_id=run_id),
        failure_memory_drafts=repository.list_failure_memory_drafts(run_id=run_id),
        policy_update_suggestions=repository.list_policy_update_suggestions(run_id=run_id),
    )


def _evaluate_trace_outcome(trace: DecisionTraceVariant) -> OutcomeRecord:
    if trace.decision_type == DecisionType.MODEL_ROUTING:
        return _evaluate_model_routing(trace)
    if trace.decision_type == DecisionType.CONTEXT_SELECTION:
        return _evaluate_context_selection(trace)
    if trace.decision_type == DecisionType.BUDGET:
        return _evaluate_budget(trace)
    if trace.decision_type == DecisionType.SAFETY:
        return _evaluate_safety(trace)
    if trace.decision_type in {DecisionType.TASK_SELECTION, DecisionType.OPTIMIZATION}:
        return _evaluate_score_choice(trace)
    return _outcome(
        trace,
        status=OutcomeStatus.UNKNOWN,
        summary="No deterministic evaluator exists for this decision type yet.",
        severity=0.0,
        metrics=[],
        confidence=0.45,
    )


def _evaluate_model_routing(trace: DecisionTraceVariant) -> OutcomeRecord:
    selected_quality = _float_metric(trace.metrics, "selected_quality")
    quality_threshold = _float_metric(trace.metrics, "quality_threshold")
    if trace.selected_option == "unrouted" or selected_quality is None or quality_threshold is None:
        return _outcome(
            trace,
            status=OutcomeStatus.FAILURE,
            summary="Model routing did not produce a valid model for the required threshold.",
            severity=0.8,
            metrics=[
                outcome_metric("selected_quality", selected_quality),
                outcome_metric("quality_threshold", quality_threshold),
            ],
            confidence=0.82,
        )
    if selected_quality >= quality_threshold:
        return _outcome(
            trace,
            status=OutcomeStatus.SUCCESS,
            summary=(
                f"Selected {trace.selected_option} with quality {selected_quality:.2f}, "
                f"meeting threshold {quality_threshold:.2f}."
            ),
            severity=0.0,
            metrics=[
                outcome_metric("selected_quality", selected_quality, higher_is_better=True),
                outcome_metric("quality_threshold", quality_threshold),
                outcome_metric("quality_margin", selected_quality - quality_threshold, higher_is_better=True),
            ],
            confidence=0.9,
        )
    return _outcome(
        trace,
        status=OutcomeStatus.FAILURE,
        summary=(
            f"Selected {trace.selected_option} with quality {selected_quality:.2f}, "
            f"below threshold {quality_threshold:.2f}."
        ),
        severity=0.85,
        metrics=[
            outcome_metric("selected_quality", selected_quality, higher_is_better=True),
            outcome_metric("quality_threshold", quality_threshold),
            outcome_metric("quality_gap", quality_threshold - selected_quality, higher_is_better=False),
        ],
        confidence=0.9,
    )


def _evaluate_context_selection(trace: DecisionTraceVariant) -> OutcomeRecord:
    missing_critical = sum(
        1 for alternative in trace.alternatives if _alternative_bool_metric(alternative, "critical")
    )
    tokens_after = _float_metric(trace.metrics, "tokens_after")
    token_budget = _float_metric(trace.metrics, "token_budget")
    within_budget = (
        tokens_after is not None
        and token_budget is not None
        and tokens_after <= token_budget
    )
    status = OutcomeStatus.SUCCESS if missing_critical == 0 and within_budget else OutcomeStatus.FAILURE
    summary = (
        "Critical context was preserved under the token budget."
        if status == OutcomeStatus.SUCCESS
        else f"Context packing dropped {missing_critical} critical item(s) or exceeded the budget."
    )
    return _outcome(
        trace,
        status=status,
        summary=summary,
        severity=0.75 if status == OutcomeStatus.FAILURE else 0.0,
        metrics=[
            outcome_metric("missing_critical_context", missing_critical, higher_is_better=False),
            outcome_metric("tokens_after", tokens_after, unit="tokens"),
            outcome_metric("token_budget", token_budget, unit="tokens"),
            outcome_metric("within_context_budget", within_budget),
        ],
        confidence=0.84,
    )


def _evaluate_budget(trace: DecisionTraceVariant) -> OutcomeRecord:
    quality_ok = _bool_metric(trace.metrics, "meets_quality_threshold")
    token_ok = _bool_metric(trace.metrics, "within_token_budget")
    cost_ok = _bool_metric(trace.metrics, "within_cost_budget")
    if quality_ok is False:
        return _outcome(
            trace,
            status=OutcomeStatus.FAILURE,
            summary="Budget strategy preserved savings or limits but violated the quality threshold.",
            severity=0.82,
            metrics=[
                outcome_metric("meets_quality_threshold", quality_ok),
                outcome_metric("within_token_budget", token_ok),
                outcome_metric("within_cost_budget", cost_ok),
            ],
            confidence=0.88,
        )
    if token_ok is True and cost_ok is True and quality_ok is True:
        return _outcome(
            trace,
            status=OutcomeStatus.SUCCESS,
            summary="Budget guard kept token, cost, and quality constraints satisfied.",
            severity=0.0,
            metrics=[
                outcome_metric("meets_quality_threshold", quality_ok),
                outcome_metric("within_token_budget", token_ok),
                outcome_metric("within_cost_budget", cost_ok),
                outcome_metric("savings_vs_baseline", _float_metric(trace.metrics, "savings_vs_baseline"), unit="USD"),
                outcome_metric("token_savings", _float_metric(trace.metrics, "token_savings"), unit="tokens"),
            ],
            confidence=0.88,
        )
    return _outcome(
        trace,
        status=OutcomeStatus.PARTIAL,
        summary="Budget guard preserved quality but reported a token or cost budget pressure point.",
        severity=0.35,
        metrics=[
            outcome_metric("meets_quality_threshold", quality_ok),
            outcome_metric("within_token_budget", token_ok),
            outcome_metric("within_cost_budget", cost_ok),
        ],
        confidence=0.82,
    )


def _evaluate_safety(trace: DecisionTraceVariant) -> OutcomeRecord:
    approval_required = _bool_metric(trace.metrics, "approval_required")
    risk_level = str(_metric(trace.metrics, "risk_level") or "")
    high_risk = risk_level in {"high", "critical"}
    selected = trace.selected_option.lower()
    if approval_required is True or selected.startswith("approval_required"):
        return _outcome(
            trace,
            status=OutcomeStatus.SUCCESS,
            summary="Risky action was routed through an explicit approval gate.",
            severity=0.0,
            metrics=[
                outcome_metric("approval_required", approval_required),
                outcome_metric("risk_level", risk_level),
            ],
            confidence=0.88,
        )
    if high_risk:
        return _outcome(
            trace,
            status=OutcomeStatus.FAILURE,
            summary="A high-risk action was not protected by an approval requirement.",
            severity=0.9,
            metrics=[
                outcome_metric("approval_required", approval_required),
                outcome_metric("risk_level", risk_level),
            ],
            confidence=0.86,
        )
    return _outcome(
        trace,
        status=OutcomeStatus.SUCCESS,
        summary="Low or medium risk action satisfied the current safety policy.",
        severity=0.0,
        metrics=[
            outcome_metric("approval_required", approval_required),
            outcome_metric("risk_level", risk_level),
        ],
        confidence=0.72,
    )


def _evaluate_score_choice(trace: DecisionTraceVariant) -> OutcomeRecord:
    selected_score = trace.objective_score
    best_alternative = max(
        (alternative.score for alternative in trace.alternatives if alternative.score is not None),
        default=None,
    )
    if selected_score is None or best_alternative is None:
        return _outcome(
            trace,
            status=OutcomeStatus.UNKNOWN,
            summary="Decision outcome needs runtime evidence beyond the current score comparison.",
            severity=0.0,
            metrics=[outcome_metric("selected_score", selected_score)],
            confidence=0.5,
        )
    if selected_score >= best_alternative:
        return _outcome(
            trace,
            status=OutcomeStatus.SUCCESS,
            summary="Selected option matched or beat the scored alternatives.",
            severity=0.0,
            metrics=[
                outcome_metric("selected_score", selected_score, higher_is_better=True),
                outcome_metric("best_alternative_score", best_alternative, higher_is_better=True),
            ],
            confidence=0.78,
        )
    return _outcome(
        trace,
        status=OutcomeStatus.FAILURE,
        summary="Selected option scored below an available alternative.",
        severity=0.7,
        metrics=[
            outcome_metric("selected_score", selected_score, higher_is_better=True),
            outcome_metric("best_alternative_score", best_alternative, higher_is_better=True),
        ],
        confidence=0.78,
    )


def _learning_artifacts_for_outcome(
    trace: DecisionTraceVariant,
    outcome: OutcomeRecord,
    reflection: ReflectionRecord,
) -> OutcomeEvaluationBatch:
    signals: list[LearningSignal] = []
    drafts: list[FailureMemoryDraft] = []
    suggestions: list[PolicyUpdateSuggestion] = []
    if trace.decision_type == DecisionType.MODEL_ROUTING:
        signals.append(_model_signal(trace, outcome))
    elif trace.decision_type == DecisionType.CONTEXT_SELECTION:
        signals.append(_context_signal(outcome))
    elif trace.decision_type == DecisionType.BUDGET:
        signals.append(_budget_signal(outcome))
    elif trace.decision_type == DecisionType.SAFETY:
        signals.append(_safety_signal(outcome))
        if outcome.status == OutcomeStatus.FAILURE:
            suggestions.append(_safety_policy_suggestion(trace, outcome))
    elif trace.decision_type == DecisionType.TASK_SELECTION:
        signals.append(_task_order_signal(trace, outcome))
    elif trace.decision_type == DecisionType.OPTIMIZATION:
        signals.append(_optimizer_signal(trace, outcome))

    if outcome.status == OutcomeStatus.FAILURE:
        drafts.append(_failure_memory_draft(trace, outcome, reflection))
    return OutcomeEvaluationBatch(
        learning_signals=signals,
        failure_memory_drafts=drafts,
        policy_update_suggestions=suggestions,
    )


def _model_signal(trace: DecisionTraceVariant, outcome: OutcomeRecord) -> LearningSignal:
    if outcome.status == OutcomeStatus.SUCCESS:
        direction = LearningDirection.PREFER
        target = trace.selected_option
        rationale = f"Model {trace.selected_option} met the quality threshold in outcome {outcome.id}."
        strength = 0.72
    else:
        direction = LearningDirection.INCREASE
        target = "model_router.quality_threshold_guard"
        rationale = "A model routing outcome failed the required quality threshold."
        strength = 0.86
    return _signal(
        trace,
        outcome,
        signal_type=LearningSignalType.MODEL_QUALITY,
        direction=direction,
        target=target,
        rationale=rationale,
        strength=strength,
    )


def _context_signal(outcome: OutcomeRecord) -> LearningSignal:
    trace_id = outcome.decision_trace_id
    if outcome.status == OutcomeStatus.SUCCESS:
        direction = LearningDirection.PREFER
        target = "context_packer.preserve_critical_context"
        rationale = "Critical context survived token pressure."
        strength = 0.68
    else:
        direction = LearningDirection.INCREASE
        target = "context_packer.critical_context_penalty"
        rationale = "Critical context was missing or context budget was exceeded."
        strength = 0.84
    return LearningSignal(
        run_id=outcome.run_id,
        decision_trace_id=trace_id,
        outcome_id=outcome.id,
        signal_type=LearningSignalType.CONTEXT_STRATEGY,
        direction=direction,
        target=target,
        rationale=rationale,
        strength=strength,
        confidence=outcome.confidence,
        tags=["context", "outcome-learning", outcome.status.value],
    )


def _budget_signal(outcome: OutcomeRecord) -> LearningSignal:
    if outcome.status == OutcomeStatus.SUCCESS:
        direction = LearningDirection.PREFER
        target = "token_firewall.quality_preserving_budget_guard"
        rationale = "Budget guard kept cost, tokens, and quality aligned."
        strength = 0.62
    elif outcome.status == OutcomeStatus.FAILURE:
        direction = LearningDirection.DECREASE
        target = "budget_strategy.aggressiveness"
        rationale = "Savings or limits were too aggressive because quality failed."
        strength = 0.82
    else:
        direction = LearningDirection.INVESTIGATE
        target = "token_firewall.limit_profile"
        rationale = "Budget pressure occurred while quality was preserved."
        strength = 0.55
    return LearningSignal(
        run_id=outcome.run_id,
        decision_trace_id=outcome.decision_trace_id,
        outcome_id=outcome.id,
        signal_type=LearningSignalType.BUDGET_STRATEGY,
        direction=direction,
        target=target,
        rationale=rationale,
        strength=strength,
        confidence=outcome.confidence,
        tags=["budget", "outcome-learning", outcome.status.value],
    )


def _safety_signal(outcome: OutcomeRecord) -> LearningSignal:
    if outcome.status == OutcomeStatus.SUCCESS:
        direction = LearningDirection.PREFER
        target = "safety.approval_gate_for_risky_actions"
        rationale = "Risky action required approval before side effects."
        strength = 0.7
    else:
        direction = LearningDirection.INCREASE
        target = "safety.approval_requirement_strictness"
        rationale = "High-risk action was not gated by approval."
        strength = 0.9
    return LearningSignal(
        run_id=outcome.run_id,
        decision_trace_id=outcome.decision_trace_id,
        outcome_id=outcome.id,
        signal_type=LearningSignalType.SAFETY_POLICY,
        direction=direction,
        target=target,
        rationale=rationale,
        strength=strength,
        confidence=outcome.confidence,
        tags=["safety", "outcome-learning", outcome.status.value],
    )


def _task_order_signal(trace: DecisionTraceVariant, outcome: OutcomeRecord) -> LearningSignal:
    direction = LearningDirection.PREFER if outcome.status == OutcomeStatus.SUCCESS else LearningDirection.INVESTIGATE
    return _signal(
        trace,
        outcome,
        signal_type=LearningSignalType.TASK_ORDERING,
        direction=direction,
        target=trace.selected_option,
        rationale="Task ordering outcome reinforces or questions the selected scheduler order.",
        strength=0.5 if outcome.status == OutcomeStatus.SUCCESS else 0.68,
    )


def _optimizer_signal(trace: DecisionTraceVariant, outcome: OutcomeRecord) -> LearningSignal:
    direction = LearningDirection.PREFER if outcome.status == OutcomeStatus.SUCCESS else LearningDirection.INVESTIGATE
    return _signal(
        trace,
        outcome,
        signal_type=LearningSignalType.OPTIMIZER_WEIGHT,
        direction=direction,
        target=trace.selected_option,
        rationale="Optimizer score comparison produced a traceable outcome.",
        strength=0.5 if outcome.status == OutcomeStatus.SUCCESS else 0.68,
    )


def _signal(
    trace: DecisionTraceVariant,
    outcome: OutcomeRecord,
    *,
    signal_type: LearningSignalType,
    direction: LearningDirection,
    target: str,
    rationale: str,
    strength: float,
) -> LearningSignal:
    return LearningSignal(
        run_id=outcome.run_id,
        decision_trace_id=outcome.decision_trace_id,
        outcome_id=outcome.id,
        signal_type=signal_type,
        direction=direction,
        target=target,
        rationale=rationale,
        strength=strength,
        confidence=outcome.confidence,
        tags=[trace.decision_type.value, "outcome-learning", outcome.status.value],
    )


def _failure_memory_draft(
    trace: DecisionTraceVariant,
    outcome: OutcomeRecord,
    reflection: ReflectionRecord,
) -> FailureMemoryDraft:
    summary = f"{trace.decision_type.value} failure: {outcome.summary}"
    content = "\n".join(
        [
            f"Decision trace {trace.id} selected {trace.selected_option}.",
            f"Outcome: {outcome.summary}",
            f"Likely cause: {reflection.likely_cause or 'unknown'}",
            f"Recommended change: {reflection.recommended_change or 'investigate'}",
        ]
    )
    return FailureMemoryDraft(
        run_id=outcome.run_id,
        decision_trace_id=outcome.decision_trace_id,
        outcome_id=outcome.id,
        summary=summary,
        content=content,
        tags=[trace.decision_type.value, "failure", "outcome-learning"],
        confidence=outcome.confidence,
        severity=outcome.severity,
        suggested_memory_importance=max(0.55, outcome.severity),
    )


def _safety_policy_suggestion(
    trace: DecisionTraceVariant,
    outcome: OutcomeRecord,
) -> PolicyUpdateSuggestion:
    action = str(_metric(trace.metrics, "action") or trace.selected_option)
    return PolicyUpdateSuggestion(
        run_id=outcome.run_id,
        decision_trace_id=outcome.decision_trace_id,
        outcome_id=outcome.id,
        policy_area=PolicyArea.SAFETY,
        current_rule="High-risk actions should require approval when policy identifies risk.",
        suggested_rule=f"Require explicit approval before allowing high-risk action: {action}.",
        rationale=outcome.summary,
        confidence=outcome.confidence,
        tags=["safety", "policy-suggestion", "outcome-learning"],
    )


def _outcome(
    trace: DecisionTraceVariant,
    *,
    status: OutcomeStatus,
    summary: str,
    severity: float,
    metrics: list[OutcomeMetric],
    confidence: float,
) -> OutcomeRecord:
    evidence = OutcomeEvidence(
        evidence_type="decision_trace",
        source=trace.phase,
        content=trace.rationale,
        metadata={
            "decision_type": trace.decision_type.value,
            "selected_option": trace.selected_option,
        },
    )
    return OutcomeRecord(
        run_id=trace.run_id,
        decision_trace_id=trace.id,
        status=status,
        summary=summary,
        metrics=metrics,
        evidence=[evidence],
        severity=severity,
        confidence=min(1.0, (trace.confidence + confidence) / 2),
        tags=[trace.decision_type.value, status.value, "simulated-outcome"],
    )


def _success_reflection(trace: DecisionTraceVariant, outcome: OutcomeRecord) -> str:
    if trace.decision_type == DecisionType.MODEL_ROUTING:
        return "Quality guard selected a model that met the required threshold."
    if trace.decision_type == DecisionType.CONTEXT_SELECTION:
        return "Critical context was preserved while reducing prompt size."
    if trace.decision_type == DecisionType.BUDGET:
        return "Budget guard preserved quality while respecting token and cost limits."
    if trace.decision_type == DecisionType.SAFETY:
        return "Approval gate protected a risky action before side effects."
    return f"The selected option produced a {outcome.status.value} outcome."


def _success_cause(trace: DecisionTraceVariant) -> str:
    return f"{trace.decision_type.value} constraints were evaluated before minimizing cost or effort."


def _success_recommendation(trace: DecisionTraceVariant, outcome: OutcomeRecord) -> str:
    if trace.decision_type == DecisionType.MODEL_ROUTING:
        threshold = _float_metric(trace.metrics, "quality_threshold")
        suffix = f" for quality >= {threshold:.2f}" if threshold is not None else ""
        return f"Prefer {trace.selected_option}{suffix} when similar constraints recur."
    return f"Keep the current {trace.decision_type.value} rule as a draft positive signal."


def _failure_reflection(trace: DecisionTraceVariant, outcome: OutcomeRecord) -> str:
    if trace.decision_type == DecisionType.MODEL_ROUTING:
        return "Model router violated or failed to satisfy the quality threshold."
    if trace.decision_type == DecisionType.CONTEXT_SELECTION:
        return "Context packing lost critical information or exceeded its budget."
    if trace.decision_type == DecisionType.BUDGET:
        return "Budget strategy became too aggressive for the quality guard."
    if trace.decision_type == DecisionType.SAFETY:
        return "Safety policy failed to require approval for a high-risk action."
    return outcome.summary


def _failure_cause(trace: DecisionTraceVariant, outcome: OutcomeRecord) -> str:
    if trace.decision_type == DecisionType.MODEL_ROUTING:
        return "Quality threshold strictness was insufficient for the selected route."
    if trace.decision_type == DecisionType.CONTEXT_SELECTION:
        return "Critical context did not carry enough penalty under token pressure."
    if trace.decision_type == DecisionType.BUDGET:
        return "Token or cost savings outweighed quality preservation."
    if trace.decision_type == DecisionType.SAFETY:
        return "Risk classification did not force an approval gate."
    return outcome.summary


def _failure_recommendation(trace: DecisionTraceVariant, outcome: OutcomeRecord) -> str:
    if trace.decision_type == DecisionType.MODEL_ROUTING:
        return "Increase model routing strictness around required quality thresholds."
    if trace.decision_type == DecisionType.CONTEXT_SELECTION:
        return "Increase critical context preservation weight before dropping context."
    if trace.decision_type == DecisionType.BUDGET:
        return "Reduce budget aggressiveness when quality threshold risk appears."
    if trace.decision_type == DecisionType.SAFETY:
        return "Draft a reviewed safety rule requiring approval for this risk profile."
    return f"Investigate why {trace.selected_option} produced {outcome.status.value}."


def _partial_worked(trace: DecisionTraceVariant, outcome: OutcomeRecord) -> str:
    if trace.decision_type == DecisionType.BUDGET:
        return "Quality threshold stayed intact."
    return f"Some constraints succeeded: {outcome.summary}"


def _partial_failed(trace: DecisionTraceVariant, outcome: OutcomeRecord) -> str:
    if trace.decision_type == DecisionType.BUDGET:
        return "Token or cost pressure remained unresolved."
    return outcome.summary


def _partial_cause(trace: DecisionTraceVariant) -> str:
    return f"{trace.decision_type.value} traded one objective successfully while another stayed pressured."


def _partial_recommendation(trace: DecisionTraceVariant) -> str:
    if trace.decision_type == DecisionType.BUDGET:
        return "Investigate a less aggressive token or cost limit profile."
    return f"Collect more evidence before changing {trace.decision_type.value} behavior."


def _trace_repository(
    trace_repository: DecisionTraceRepository | None,
    outcome_repository: OutcomeRepository,
) -> DecisionTraceRepository:
    return trace_repository or DecisionTraceRepository(outcome_repository.database_path)


def _metric(metrics: list[DecisionMetric], name: str) -> MetricValue:
    for item in metrics:
        if item.name == name:
            return item.value
    return None


def _float_metric(metrics: list[DecisionMetric], name: str) -> float | None:
    value = _metric(metrics, name)
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(value)
    except ValueError:
        return None


def _bool_metric(metrics: list[DecisionMetric], name: str) -> bool | None:
    value = _metric(metrics, name)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        if value.lower() == "true":
            return True
        if value.lower() == "false":
            return False
    return None


def _alternative_bool_metric(alternative: DecisionAlternative, name: str) -> bool:
    value = _metric(alternative.metrics, name)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() == "true"
    return False
