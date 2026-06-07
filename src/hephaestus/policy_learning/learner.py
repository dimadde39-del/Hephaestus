"""Aggregate learning artifacts into draft decision quality profiles."""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from hephaestus.decision.repository import DecisionTraceRepository
from hephaestus.decision.schemas import DecisionTraceVariant, DecisionType
from hephaestus.outcomes.repository import OutcomeRepository
from hephaestus.outcomes.schemas import (
    FailureMemoryDraft,
    LearningDirection,
    LearningSignal,
    LearningSignalType,
    OutcomeRecord,
    PolicyArea,
    PolicyUpdateSuggestion,
    ReflectionRecord,
)
from hephaestus.policy_learning.profile_store import ProfileStore
from hephaestus.policy_learning.schemas import (
    AdjustmentOperation,
    DecisionArea,
    DecisionQualityProfile,
    ProfileAdjustment,
    ProfileEvaluation,
    ProfileEvidence,
    ProfileEvidenceType,
    ProfileRule,
    ProfileRuleType,
)


@dataclass(frozen=True)
class _AreaCorpus:
    area: DecisionArea
    signals: list[LearningSignal]
    outcomes: list[OutcomeRecord]
    reflections: list[ReflectionRecord]
    failure_drafts: list[FailureMemoryDraft]
    policy_suggestions: list[PolicyUpdateSuggestion]
    traces: list[DecisionTraceVariant]


_SIGNAL_AREA_MAP: dict[LearningSignalType, DecisionArea] = {
    LearningSignalType.MODEL_QUALITY: DecisionArea.MODEL_ROUTER,
    LearningSignalType.CONTEXT_STRATEGY: DecisionArea.CONTEXT_PACKER,
    LearningSignalType.BUDGET_STRATEGY: DecisionArea.TOKEN_FIREWALL,
    LearningSignalType.SAFETY_POLICY: DecisionArea.SAFETY,
    LearningSignalType.TASK_ORDERING: DecisionArea.SCHEDULER,
    LearningSignalType.OPTIMIZER_WEIGHT: DecisionArea.OPTIMIZER,
    LearningSignalType.MEMORY_RETRIEVAL: DecisionArea.MEMORY_RETRIEVAL,
}

_POLICY_AREA_MAP: dict[PolicyArea, DecisionArea] = {
    PolicyArea.MODEL_ROUTER: DecisionArea.MODEL_ROUTER,
    PolicyArea.CONTEXT_PACKER: DecisionArea.CONTEXT_PACKER,
    PolicyArea.TOKEN_FIREWALL: DecisionArea.TOKEN_FIREWALL,
    PolicyArea.SAFETY: DecisionArea.SAFETY,
    PolicyArea.SCHEDULER: DecisionArea.SCHEDULER,
    PolicyArea.MEMORY: DecisionArea.MEMORY_RETRIEVAL,
}

_TRACE_AREA_MAP: dict[DecisionType, DecisionArea] = {
    DecisionType.MODEL_ROUTING: DecisionArea.MODEL_ROUTER,
    DecisionType.CONTEXT_SELECTION: DecisionArea.CONTEXT_PACKER,
    DecisionType.BUDGET: DecisionArea.TOKEN_FIREWALL,
    DecisionType.SAFETY: DecisionArea.SAFETY,
    DecisionType.TASK_SELECTION: DecisionArea.SCHEDULER,
    DecisionType.OPTIMIZATION: DecisionArea.OPTIMIZER,
}


def suggest_profiles(
    *,
    database_path: Path | str | None = None,
    outcome_repository: OutcomeRepository | None = None,
    trace_repository: DecisionTraceRepository | None = None,
    profile_store: ProfileStore | None = None,
    persist: bool = True,
) -> ProfileEvaluation:
    """Read learning artifacts and persist draft profile suggestions."""

    outcomes = outcome_repository or OutcomeRepository(database_path)
    traces = trace_repository or DecisionTraceRepository(outcomes.database_path)
    store = profile_store or ProfileStore(outcomes.database_path)
    profiles = generate_profile_suggestions(
        outcomes=outcomes.list_outcomes(),
        reflections=outcomes.list_reflections(),
        learning_signals=outcomes.list_learning_signals(),
        failure_memory_drafts=outcomes.list_failure_memory_drafts(),
        policy_update_suggestions=outcomes.list_policy_update_suggestions(),
        decision_traces=traces.list_traces(),
    )
    saved = [store.save_profile(profile) for profile in profiles] if persist else profiles
    evidence_count = sum(len(profile.evidence) for profile in saved)
    confidence = _average([profile.confidence for profile in saved])
    return ProfileEvaluation(
        profiles_created=len(saved),
        evidence_count=evidence_count,
        confidence=confidence,
        profiles=saved,
        summary=(
            f"Created {len(saved)} draft decision quality profile(s) from "
            f"{evidence_count} evidence item(s)."
        ),
    )


def generate_profile_suggestions(
    *,
    outcomes: Iterable[OutcomeRecord],
    reflections: Iterable[ReflectionRecord],
    learning_signals: Iterable[LearningSignal],
    failure_memory_drafts: Iterable[FailureMemoryDraft],
    policy_update_suggestions: Iterable[PolicyUpdateSuggestion],
    decision_traces: Iterable[DecisionTraceVariant],
) -> list[DecisionQualityProfile]:
    """Create draft profile suggestions from in-memory learning artifacts."""

    corpora = _build_corpora(
        outcomes=list(outcomes),
        reflections=list(reflections),
        learning_signals=list(learning_signals),
        failure_memory_drafts=list(failure_memory_drafts),
        policy_update_suggestions=list(policy_update_suggestions),
        decision_traces=list(decision_traces),
    )
    profiles: list[DecisionQualityProfile] = []
    for area in DecisionArea:
        corpus = corpora.get(area)
        if corpus is None or not _has_evidence(corpus):
            continue
        profiles.append(_profile_for_corpus(corpus))
    return profiles


def _build_corpora(
    *,
    outcomes: list[OutcomeRecord],
    reflections: list[ReflectionRecord],
    learning_signals: list[LearningSignal],
    failure_memory_drafts: list[FailureMemoryDraft],
    policy_update_suggestions: list[PolicyUpdateSuggestion],
    decision_traces: list[DecisionTraceVariant],
) -> dict[DecisionArea, _AreaCorpus]:
    signals_by_area: dict[DecisionArea, list[LearningSignal]] = defaultdict(list)
    suggestions_by_area: dict[DecisionArea, list[PolicyUpdateSuggestion]] = defaultdict(list)
    traces_by_area: dict[DecisionArea, list[DecisionTraceVariant]] = defaultdict(list)
    outcome_ids_by_area: dict[DecisionArea, set[str]] = defaultdict(set)
    trace_ids_by_area: dict[DecisionArea, set[str]] = defaultdict(set)

    for signal in learning_signals:
        area = _SIGNAL_AREA_MAP[signal.signal_type]
        signals_by_area[area].append(signal)
        outcome_ids_by_area[area].add(signal.outcome_id)
        trace_ids_by_area[area].add(signal.decision_trace_id)

    for suggestion in policy_update_suggestions:
        area = _POLICY_AREA_MAP[suggestion.policy_area]
        suggestions_by_area[area].append(suggestion)
        outcome_ids_by_area[area].add(suggestion.outcome_id)
        trace_ids_by_area[area].add(suggestion.decision_trace_id)

    for trace in decision_traces:
        trace_area = _TRACE_AREA_MAP.get(trace.decision_type)
        if trace_area is None:
            continue
        traces_by_area[trace_area].append(trace)
        if trace.outcome_id is not None:
            outcome_ids_by_area[trace_area].add(trace.outcome_id)
        trace_ids_by_area[trace_area].add(trace.id)

    outcomes_by_id = {outcome.id: outcome for outcome in outcomes}
    reflections_by_area: dict[DecisionArea, list[ReflectionRecord]] = defaultdict(list)
    drafts_by_area: dict[DecisionArea, list[FailureMemoryDraft]] = defaultdict(list)
    for area, ids in outcome_ids_by_area.items():
        for reflection in reflections:
            if reflection.outcome_id in ids:
                reflections_by_area[area].append(reflection)
        for draft in failure_memory_drafts:
            if draft.outcome_id in ids:
                drafts_by_area[area].append(draft)

    corpora: dict[DecisionArea, _AreaCorpus] = {}
    for area in DecisionArea:
        area_outcomes = [
            outcome
            for outcome_id, outcome in outcomes_by_id.items()
            if outcome_id in outcome_ids_by_area[area]
        ]
        area_traces = [
            trace
            for trace in traces_by_area[area]
            if trace.id in trace_ids_by_area[area] or trace.outcome_id in outcome_ids_by_area[area]
        ]
        corpora[area] = _AreaCorpus(
            area=area,
            signals=signals_by_area[area],
            outcomes=area_outcomes,
            reflections=reflections_by_area[area],
            failure_drafts=drafts_by_area[area],
            policy_suggestions=suggestions_by_area[area],
            traces=area_traces,
        )
    return corpora


def _profile_for_corpus(corpus: _AreaCorpus) -> DecisionQualityProfile:
    evidence = _evidence_for_corpus(corpus)
    source_signal_ids = [signal.id for signal in corpus.signals]
    source_outcome_ids = [outcome.id for outcome in corpus.outcomes]
    source_policy_ids = [suggestion.id for suggestion in corpus.policy_suggestions]
    confidence = _profile_confidence(evidence)
    return DecisionQualityProfile(
        name=_profile_name(corpus.area),
        decision_area=corpus.area,
        description=_profile_description(corpus.area),
        rules=_rules_for_corpus(corpus),
        evidence=evidence,
        confidence=confidence,
        source_learning_signal_ids=source_signal_ids,
        source_outcome_ids=source_outcome_ids,
        source_policy_suggestion_ids=source_policy_ids,
        tags=[corpus.area.value, "policy-learning", *_corpus_tags(corpus)],
    )


def _rules_for_corpus(corpus: _AreaCorpus) -> list[ProfileRule]:
    if corpus.area == DecisionArea.MODEL_ROUTER:
        return [_model_router_rule(corpus)]
    if corpus.area == DecisionArea.CONTEXT_PACKER:
        return [_context_packer_rule()]
    if corpus.area == DecisionArea.TOKEN_FIREWALL:
        return [_token_firewall_rule(corpus)]
    if corpus.area == DecisionArea.SCHEDULER:
        return [_scheduler_rule()]
    if corpus.area == DecisionArea.SAFETY:
        return [_safety_rule()]
    if corpus.area == DecisionArea.MEMORY_RETRIEVAL:
        return [_memory_retrieval_rule()]
    return [_optimizer_rule()]


def _model_router_rule(corpus: _AreaCorpus) -> ProfileRule:
    failure_or_increase = [
        signal
        for signal in corpus.signals
        if signal.direction in {LearningDirection.INCREASE, LearningDirection.AVOID}
        or "failure" in signal.tags
    ]
    threshold_delta = 0.04 if failure_or_increase else 0.02
    prefer_targets = _unique_text(
        signal.target
        for signal in corpus.signals
        if signal.direction == LearningDirection.PREFER and "/" in signal.target
    )
    avoid_targets = _unique_text(
        signal.target
        for signal in corpus.signals
        if signal.direction == LearningDirection.AVOID and "/" in signal.target
    )
    adjustments = [
        ProfileAdjustment(
            target="quality_threshold",
            operation=AdjustmentOperation.INCREASE,
            value=threshold_delta,
            rationale="Past model routing outcomes indicate quality should dominate cost.",
        )
    ]
    if prefer_targets:
        adjustments.append(
            ProfileAdjustment(
                target="preferred_model_tags",
                operation=AdjustmentOperation.PREFER,
                value=", ".join(prefer_targets),
                rationale="Successful outcomes preferred these model identifiers.",
            )
        )
    if avoid_targets:
        adjustments.append(
            ProfileAdjustment(
                target="avoided_model_tags",
                operation=AdjustmentOperation.AVOID,
                value=", ".join(avoid_targets),
                rationale="Outcomes suggested avoiding these model identifiers.",
            )
        )
    return ProfileRule(
        decision_area=DecisionArea.MODEL_ROUTER,
        rule_type=ProfileRuleType.QUALITY_THRESHOLD,
        target="model_router.quality_threshold_guard",
        conditions={"task_risk": "medium_or_higher"},
        adjustments=adjustments,
        minimum_quality_score=0.88 if failure_or_increase else None,
        max_failure_rate=0.25,
        prefer_model_tags=prefer_targets,
        avoid_model_tags=avoid_targets,
        rationale=(
            "For risky or quality-sensitive tasks, require stronger evidence of model "
            "quality before comparing cost."
        ),
    )


def _context_packer_rule() -> ProfileRule:
    return ProfileRule(
        decision_area=DecisionArea.CONTEXT_PACKER,
        rule_type=ProfileRuleType.CONTEXT_PRESERVATION,
        target="context_packer.critical_context_policy",
        conditions={"token_pressure": "true"},
        adjustments=[
            ProfileAdjustment(
                target="critical_context_policy",
                operation=AdjustmentOperation.REQUIRE,
                value=True,
                rationale="Critical context failures should become hard constraints.",
            ),
            ProfileAdjustment(
                target="failure_memory_importance",
                operation=AdjustmentOperation.INCREASE,
                value=0.15,
                rationale="Failure memories should be harder to drop under pressure.",
            ),
            ProfileAdjustment(
                target="compression_aggressiveness",
                operation=AdjustmentOperation.DECREASE,
                value=0.1,
                rationale="Low-relevance summaries should lose before critical context.",
            ),
        ],
        hard_constraint=True,
        rationale="Treat critical context as a quality guard, not merely a soft score boost.",
    )


def _token_firewall_rule(corpus: _AreaCorpus) -> ProfileRule:
    failures = [outcome for outcome in corpus.outcomes if outcome.status.value == "failure"]
    return ProfileRule(
        decision_area=DecisionArea.TOKEN_FIREWALL,
        rule_type=ProfileRuleType.TOKEN_COMPRESSION,
        target="token_firewall.quality_preservation",
        conditions={"quality_threshold": "high"},
        adjustments=[
            ProfileAdjustment(
                target="quality_threshold",
                operation=AdjustmentOperation.INCREASE,
                value=0.02 if failures else 0.01,
                rationale="Budget savings should not undercut quality preservation.",
            ),
            ProfileAdjustment(
                target="compression_aggressiveness",
                operation=AdjustmentOperation.DECREASE,
                value=0.15,
                rationale="Compression should relax when quality risk is high.",
            ),
            ProfileAdjustment(
                target="quality_preservation",
                operation=AdjustmentOperation.REQUIRE,
                value=True,
                rationale="Cost savings apply only after quality constraints pass.",
            ),
        ],
        hard_constraint=True,
        rationale="Prefer cost savings only after quality preservation is satisfied.",
    )


def _scheduler_rule() -> ProfileRule:
    return ProfileRule(
        decision_area=DecisionArea.SCHEDULER,
        rule_type=ProfileRuleType.SCHEDULER_WEIGHT,
        target="scheduler.objective_weights",
        adjustments=[
            ProfileAdjustment(
                target="dependency_violation_penalty",
                operation=AdjustmentOperation.INCREASE,
                value=10.0,
                rationale="Dependency violations correlate with failed or fragile runs.",
            ),
            ProfileAdjustment(
                target="risk_penalty",
                operation=AdjustmentOperation.INCREASE,
                value=0.5,
                rationale="Destructive or release-adjacent tasks deserve a higher penalty.",
            ),
            ProfileAdjustment(
                target="validation_before_release",
                operation=AdjustmentOperation.PREFER,
                value=True,
                rationale="Validation should precede release, publish, or push actions.",
            ),
        ],
        rationale="Increase penalties that keep dependency and release ordering conservative.",
    )


def _safety_rule() -> ProfileRule:
    return ProfileRule(
        decision_area=DecisionArea.SAFETY,
        rule_type=ProfileRuleType.SAFETY_GATE,
        target="safety.approval_gate",
        adjustments=[
            ProfileAdjustment(
                target="approval_required_for_external_side_effects",
                operation=AdjustmentOperation.REQUIRE,
                value=True,
                rationale="External side effects should be explicit approval gates.",
            ),
            ProfileAdjustment(
                target="unknown_shell_commands",
                operation=AdjustmentOperation.SET,
                value="manual_approval",
                rationale="Unknown shell commands should escalate when risk is unclear.",
            ),
        ],
        hard_constraint=True,
        require_approval=True,
        rationale="Require explicit approval for external side effects and unknown risk.",
    )


def _memory_retrieval_rule() -> ProfileRule:
    return ProfileRule(
        decision_area=DecisionArea.MEMORY_RETRIEVAL,
        rule_type=ProfileRuleType.MEMORY_RETRIEVAL,
        target="memory_retrieval.failure_memory_weight",
        adjustments=[
            ProfileAdjustment(
                target="failure_memory_importance",
                operation=AdjustmentOperation.INCREASE,
                value=0.15,
                rationale="Failure memories should surface for similar future decisions.",
            )
        ],
        rationale="Make relevant failures more visible during future context retrieval.",
    )


def _optimizer_rule() -> ProfileRule:
    return ProfileRule(
        decision_area=DecisionArea.OPTIMIZER,
        rule_type=ProfileRuleType.OPTIMIZER_BIAS,
        target="optimizer.quality_bias",
        adjustments=[
            ProfileAdjustment(
                target="quality_weight",
                operation=AdjustmentOperation.INCREASE,
                value=0.1,
                rationale="Optimizer choices should preserve decision quality before savings.",
            ),
            ProfileAdjustment(
                target="risk_penalty",
                operation=AdjustmentOperation.INCREASE,
                value=0.25,
                rationale="Risk should be more visible in candidate scoring.",
            ),
        ],
        rationale="Bias optimizer candidates toward quality-preserving tradeoffs.",
    )


def _evidence_for_corpus(corpus: _AreaCorpus) -> list[ProfileEvidence]:
    evidence: list[ProfileEvidence] = []
    evidence.extend(
        ProfileEvidence(
            evidence_type=ProfileEvidenceType.LEARNING_SIGNAL,
            source_id=signal.id,
            summary=signal.rationale,
            weight=signal.strength,
            confidence=signal.confidence,
            tags=[signal.signal_type.value, signal.direction.value, *signal.tags],
        )
        for signal in corpus.signals
    )
    evidence.extend(
        ProfileEvidence(
            evidence_type=ProfileEvidenceType.OUTCOME,
            source_id=outcome.id,
            summary=outcome.summary,
            weight=max(outcome.severity, 0.35),
            confidence=outcome.confidence,
            severity=outcome.severity,
            observed_at=outcome.observed_at,
            tags=[outcome.status.value, *outcome.tags],
        )
        for outcome in corpus.outcomes
    )
    evidence.extend(
        ProfileEvidence(
            evidence_type=ProfileEvidenceType.REFLECTION,
            source_id=reflection.id,
            summary=reflection.recommended_change
            or reflection.likely_cause
            or reflection.what_failed
            or reflection.what_worked,
            weight=0.55,
            confidence=reflection.confidence,
            tags=[*reflection.tags, "reflection"],
        )
        for reflection in corpus.reflections
    )
    evidence.extend(
        ProfileEvidence(
            evidence_type=ProfileEvidenceType.FAILURE_MEMORY_DRAFT,
            source_id=draft.id,
            summary=draft.summary,
            weight=max(draft.severity, 0.45),
            confidence=draft.confidence,
            severity=draft.severity,
            tags=[*draft.tags, "failure-memory-draft"],
        )
        for draft in corpus.failure_drafts
    )
    evidence.extend(
        ProfileEvidence(
            evidence_type=ProfileEvidenceType.POLICY_SUGGESTION,
            source_id=suggestion.id,
            summary=suggestion.suggested_rule,
            weight=0.7,
            confidence=suggestion.confidence,
            tags=[suggestion.policy_area.value, *suggestion.tags],
        )
        for suggestion in corpus.policy_suggestions
    )
    return evidence


def _profile_name(area: DecisionArea) -> str:
    return {
        DecisionArea.MODEL_ROUTER: "Model router quality guard",
        DecisionArea.CONTEXT_PACKER: "Context critical preservation guard",
        DecisionArea.TOKEN_FIREWALL: "Token firewall quality preservation guard",
        DecisionArea.SCHEDULER: "Scheduler dependency and risk guard",
        DecisionArea.SAFETY: "Safety approval strictness guard",
        DecisionArea.MEMORY_RETRIEVAL: "Memory retrieval failure recall guard",
        DecisionArea.OPTIMIZER: "Optimizer quality bias guard",
    }[area]


def _profile_description(area: DecisionArea) -> str:
    return {
        DecisionArea.MODEL_ROUTER: (
            "Use past routing outcomes to make quality thresholds more conservative "
            "before minimizing model cost."
        ),
        DecisionArea.CONTEXT_PACKER: (
            "Treat critical context and failure memories as quality-preserving context."
        ),
        DecisionArea.TOKEN_FIREWALL: (
            "Reduce aggressive compression when quality thresholds are at risk."
        ),
        DecisionArea.SCHEDULER: (
            "Increase dependency and risk penalties for fragile task ordering patterns."
        ),
        DecisionArea.SAFETY: (
            "Escalate external side effects and unclear shell risk into explicit approval."
        ),
        DecisionArea.MEMORY_RETRIEVAL: (
            "Surface relevant failure memories more strongly for similar decisions."
        ),
        DecisionArea.OPTIMIZER: (
            "Bias optimizer choices toward quality-preserving candidates."
        ),
    }[area]


def _profile_confidence(evidence: list[ProfileEvidence]) -> float:
    if not evidence:
        return 0.0
    weighted = [item.weight * item.confidence for item in evidence]
    base = sum(weighted) / len(weighted)
    support_bonus = min(0.18, len(evidence) * 0.025)
    return min(0.95, base + support_bonus)


def _corpus_tags(corpus: _AreaCorpus) -> list[str]:
    tags: list[str] = []
    for signal in corpus.signals:
        tags.extend(signal.tags)
        tags.append(signal.signal_type.value)
    for outcome in corpus.outcomes:
        tags.extend(outcome.tags)
        tags.append(outcome.status.value)
    for suggestion in corpus.policy_suggestions:
        tags.extend(suggestion.tags)
        tags.append(suggestion.policy_area.value)
    return tags


def _has_evidence(corpus: _AreaCorpus) -> bool:
    return bool(
        corpus.signals
        or corpus.policy_suggestions
        or corpus.failure_drafts
        or corpus.outcomes
        or corpus.reflections
    )


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)


def _unique_text(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    unique: list[str] = []
    for value in values:
        normalized = value.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    return unique
