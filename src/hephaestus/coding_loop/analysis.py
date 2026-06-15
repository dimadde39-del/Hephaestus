"""Decision trace, outcome, and learning helpers for coding loops."""

from __future__ import annotations

from pathlib import Path

from hephaestus.coding_loop.schemas import CodingLoopStatus, CodingRisk
from hephaestus.decision import (
    DecisionAlternative,
    DecisionTraceRepository,
    OptimizationDecision,
    SafetyDecision,
    metric,
)
from hephaestus.outcomes import (
    LearningDirection,
    LearningSignal,
    LearningSignalType,
    OutcomeEvidence,
    OutcomeRecord,
    OutcomeRepository,
    OutcomeStatus,
    outcome_metric,
)


def record_coding_trace(
    database_path: Path | str,
    *,
    run_id: str,
    phase: str,
    selected_option: str,
    rationale: str,
    request_id: str,
    status: CodingLoopStatus | str,
    risk: CodingRisk | str,
    related_ids: list[str] | None = None,
    objective_score: float | None = None,
    confidence: float = 0.78,
    safety: bool = True,
    tags: list[str] | None = None,
) -> SafetyDecision | OptimizationDecision:
    """Persist one coding-loop decision trace."""

    risk_value = risk.value if isinstance(risk, CodingRisk) else risk
    status_value = status.value if isinstance(status, CodingLoopStatus) else status
    trace_tags = ["coding_loop", phase, status_value, risk_value, *(tags or [])]
    trace_common = {
        "run_id": run_id,
        "phase": f"coding_loop:{phase}",
        "selected_option": selected_option,
        "alternatives": [
            DecisionAlternative(
                option_id="unbounded_agentic_edit",
                rejection_reason="Phase 5G only allows scoped, reviewable patch workflows.",
                violated_constraints=["bounded iteration", "approval gate", "rollback"],
                risk=0.8,
            )
        ],
        "rationale": rationale,
        "metrics": [
            metric("coding_request_id", request_id),
            metric("status", status_value),
            metric("risk", risk_value),
        ],
        "objective_score": objective_score,
        "confidence": confidence,
        "constraints_considered": [
            "repo context",
            "declared scope",
            "protected files",
            "approval/trust behavior",
            "real validation evidence",
            "rollback availability",
        ],
        "tags": trace_tags,
        "caused_by": [request_id, *(related_ids or [])],
        "will_affect": ["coding_loop_result", "outcome_learning"],
        "learning_hooks": ["coding_loop_outcome", "validation_result", "approval_precision"],
    }
    trace: SafetyDecision | OptimizationDecision = (
        SafetyDecision(**trace_common) if safety else OptimizationDecision(**trace_common)
    )
    DecisionTraceRepository(database_path).save_trace(trace)
    return trace


def record_coding_outcome(
    database_path: Path | str,
    *,
    run_id: str,
    decision_trace_id: str,
    status: OutcomeStatus,
    summary: str,
    request_id: str,
    severity: float = 0.0,
    confidence: float = 0.78,
    evidence_content: str = "",
    tags: list[str] | None = None,
) -> OutcomeRecord:
    """Persist a coding-loop outcome linked to a trace."""

    outcome = OutcomeRecord(
        run_id=run_id,
        decision_trace_id=decision_trace_id,
        status=status,
        summary=summary,
        metrics=[outcome_metric("coding_loop_severity", severity)],
        evidence=[
            OutcomeEvidence(
                evidence_type="coding_loop",
                source="hephaestus.coding_loop",
                content=evidence_content or summary,
                metadata={"coding_request_id": request_id},
            )
        ],
        severity=severity,
        confidence=confidence,
        tags=["coding-loop", *(tags or [])],
    )
    return OutcomeRepository(database_path).save_outcome(outcome)


def record_coding_learning_signal(
    database_path: Path | str,
    *,
    run_id: str,
    decision_trace_id: str,
    outcome_id: str,
    signal_type: LearningSignalType,
    direction: LearningDirection,
    target: str,
    rationale: str,
    strength: float = 0.5,
    confidence: float = 0.7,
    tags: list[str] | None = None,
) -> LearningSignal:
    """Persist a coding-loop learning signal."""

    signal = LearningSignal(
        run_id=run_id,
        decision_trace_id=decision_trace_id,
        outcome_id=outcome_id,
        signal_type=signal_type,
        direction=direction,
        target=target,
        rationale=rationale,
        strength=strength,
        confidence=confidence,
        tags=["coding-loop", *(tags or [])],
    )
    return OutcomeRepository(database_path).save_learning_signal(signal)
