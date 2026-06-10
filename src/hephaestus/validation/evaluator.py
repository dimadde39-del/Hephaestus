"""Outcome and learning integration for validation evidence."""

from __future__ import annotations

from hephaestus.outcomes import (
    FailureMemoryDraft,
    LearningDirection,
    LearningSignal,
    LearningSignalType,
    OutcomeEvidence,
    OutcomeRecord,
    OutcomeStatus,
    outcome_metric,
)
from hephaestus.validation.schemas import (
    ValidationCommandType,
    ValidationEvidence,
    ValidationFailure,
    ValidationLearningSignal,
    ValidationStatus,
)


def outcome_status_from_validation(status: ValidationStatus) -> OutcomeStatus:
    """Map validation status to outcome status."""

    if status == ValidationStatus.PASSED:
        return OutcomeStatus.SUCCESS
    if status in {ValidationStatus.FAILED, ValidationStatus.TIMED_OUT, ValidationStatus.BLOCKED}:
        return OutcomeStatus.FAILURE
    if status in {ValidationStatus.REQUIRES_APPROVAL, ValidationStatus.SKIPPED}:
        return OutcomeStatus.PARTIAL
    return OutcomeStatus.UNKNOWN


def build_validation_outcome(
    evidence: ValidationEvidence,
    *,
    run_id: str,
    decision_trace_id: str,
) -> OutcomeRecord:
    """Create an outcome record from one validation evidence item."""

    status = outcome_status_from_validation(evidence.status)
    return OutcomeRecord(
        run_id=run_id,
        decision_trace_id=decision_trace_id,
        status=status,
        summary=_outcome_summary(evidence),
        metrics=[
            outcome_metric("exit_code", evidence.exit_code),
            outcome_metric("duration_seconds", evidence.duration_seconds, unit="seconds"),
            outcome_metric("warning_count", evidence.warning_count, higher_is_better=False),
            outcome_metric("validation_status", evidence.status.value),
            outcome_metric("command_type", evidence.command_type.value),
        ],
        evidence=[
            OutcomeEvidence(
                evidence_type="validation_command",
                source=evidence.command_type.value,
                content=_evidence_content(evidence),
                metadata={
                    "validation_evidence_id": evidence.id,
                    "validation_result_id": evidence.validation_result_id,
                    "tool_action_id": evidence.tool_action_id,
                    "tool_execution_result_id": evidence.tool_execution_result_id,
                    "command": evidence.command,
                },
            )
        ],
        severity=_outcome_severity(evidence.status),
        confidence=0.88 if evidence.tool_execution_result_id is not None else 0.7,
        tags=["validation", evidence.command_type.value, evidence.status.value],
    )


def build_validation_learning_signal(
    evidence: ValidationEvidence,
    outcome: OutcomeRecord,
    failure: ValidationFailure,
) -> LearningSignal:
    """Create a persisted learning signal for a meaningful validation issue."""

    direction = LearningDirection.INVESTIGATE
    target = f"validation.{evidence.command_type.value}.{failure.classification}"
    if evidence.status in {ValidationStatus.FAILED, ValidationStatus.TIMED_OUT}:
        direction = LearningDirection.INCREASE
        target = f"validation.required_{evidence.command_type.value}_evidence"
    if evidence.status == ValidationStatus.BLOCKED:
        target = "validation.policy_blocked_command_review"
    if evidence.status == ValidationStatus.REQUIRES_APPROVAL:
        target = "validation.approval_gate_followthrough"
    return LearningSignal(
        run_id=outcome.run_id,
        decision_trace_id=outcome.decision_trace_id,
        outcome_id=outcome.id,
        signal_type=LearningSignalType.VALIDATION_STRATEGY,
        direction=direction,
        target=target,
        rationale=failure.summary,
        strength=min(0.9, max(0.45, failure.severity)),
        confidence=outcome.confidence,
        tags=[
            "validation",
            evidence.command_type.value,
            evidence.status.value,
            failure.classification,
        ],
    )


def build_missing_commands_learning_signal(
    *,
    run_id: str,
    decision_trace_id: str,
    outcome_id: str,
    repo_path: str,
) -> LearningSignal:
    """Create a learning signal when no validation commands were found."""

    return LearningSignal(
        run_id=run_id,
        decision_trace_id=decision_trace_id,
        outcome_id=outcome_id,
        signal_type=LearningSignalType.VALIDATION_STRATEGY,
        direction=LearningDirection.INVESTIGATE,
        target="validation.command_detection",
        rationale=f"No supported validation commands were detected for {repo_path}.",
        strength=0.72,
        confidence=0.76,
        tags=["validation", "missing-commands", "outcome-learning"],
    )


def build_validation_failure_memory_draft(
    evidence: ValidationEvidence,
    outcome: OutcomeRecord,
    failure: ValidationFailure,
) -> FailureMemoryDraft:
    """Draft a failure memory for a repeated validation failure pattern."""

    content = "\n".join(
        [
            f"Validation command: {evidence.command}",
            f"Command type: {evidence.command_type.value}",
            f"Failure classification: {failure.classification}",
            f"Repeated count: {failure.repeated_count}",
            f"Evidence: {evidence.stdout_summary or evidence.stderr_summary or evidence.status.value}",
            "Recommendation: inspect the command output before trusting release readiness.",
        ]
    )
    return FailureMemoryDraft(
        run_id=outcome.run_id,
        decision_trace_id=outcome.decision_trace_id,
        outcome_id=outcome.id,
        summary=f"Repeated {failure.classification}: {evidence.command}",
        content=content,
        tags=["validation", evidence.command_type.value, "failure", failure.classification],
        confidence=outcome.confidence,
        severity=failure.severity,
        suggested_memory_importance=max(0.6, failure.severity),
    )


def validation_signal_view(
    signal: LearningSignal,
    *,
    evidence: ValidationEvidence | None = None,
    failure_memory_draft_id: str | None = None,
) -> ValidationLearningSignal:
    """Convert an outcome learning signal into validation-facing metadata."""

    command_type: ValidationCommandType | None = None
    command: str | None = None
    severity = signal.strength
    if evidence is not None:
        command_type = evidence.command_type
        command = evidence.command
        if evidence.failure is not None:
            severity = evidence.failure.severity
    return ValidationLearningSignal(
        signal_type=signal.signal_type.value,
        summary=signal.rationale,
        rationale=signal.target,
        command_type=command_type,
        command=command,
        severity=severity,
        confidence=signal.confidence,
        outcome_id=signal.outcome_id,
        learning_signal_id=signal.id,
        failure_memory_draft_id=failure_memory_draft_id,
        tags=signal.tags,
    )


def _outcome_summary(evidence: ValidationEvidence) -> str:
    if evidence.status == ValidationStatus.PASSED:
        suffix = f" with {evidence.warning_count} warning(s)" if evidence.warning_count else ""
        return f"Validation passed: {evidence.command}{suffix}"
    if evidence.status == ValidationStatus.FAILED:
        return f"Validation failed: {evidence.command}"
    if evidence.status == ValidationStatus.TIMED_OUT:
        return f"Validation timed out: {evidence.command}"
    if evidence.status == ValidationStatus.BLOCKED:
        return f"Validation blocked: {evidence.command}"
    if evidence.status == ValidationStatus.REQUIRES_APPROVAL:
        return f"Validation requires approval: {evidence.command}"
    if evidence.status == ValidationStatus.SKIPPED:
        return f"Validation skipped: {evidence.command}"
    return f"Validation status unknown: {evidence.command}"


def _evidence_content(evidence: ValidationEvidence) -> str:
    parts = [
        f"command: {evidence.command}",
        f"status: {evidence.status.value}",
    ]
    if evidence.exit_code is not None:
        parts.append(f"exit_code: {evidence.exit_code}")
    if evidence.stdout_summary:
        parts.append(f"stdout: {evidence.stdout_summary}")
    if evidence.stderr_summary:
        parts.append(f"stderr: {evidence.stderr_summary}")
    if evidence.failure_classification:
        parts.append(f"failure: {evidence.failure_classification}")
    return "\n".join(parts)


def _outcome_severity(status: ValidationStatus) -> float:
    return {
        ValidationStatus.PASSED: 0.0,
        ValidationStatus.FAILED: 0.72,
        ValidationStatus.TIMED_OUT: 0.68,
        ValidationStatus.BLOCKED: 0.56,
        ValidationStatus.REQUIRES_APPROVAL: 0.36,
        ValidationStatus.SKIPPED: 0.12,
        ValidationStatus.UNKNOWN: 0.3,
    }[status]
