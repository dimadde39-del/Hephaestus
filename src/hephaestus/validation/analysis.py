"""Deterministic analysis helpers for validation execution."""

from __future__ import annotations

import re

from hephaestus.tool_runtime.schemas import ToolExecutionResult, ToolExecutionStatus
from hephaestus.validation.schemas import (
    ReleaseValidationSummary,
    ValidationCommandType,
    ValidationEvidence,
    ValidationFailure,
    ValidationStatus,
    ValidationSuiteResult,
)

_COMMAND_TYPE_ORDER: dict[ValidationCommandType, int] = {
    ValidationCommandType.FORMAT_CHECK: 1,
    ValidationCommandType.LINT: 2,
    ValidationCommandType.TYPECHECK: 3,
    ValidationCommandType.TEST: 4,
    ValidationCommandType.BUILD: 5,
    ValidationCommandType.SECURITY_CHECK: 6,
    ValidationCommandType.CUSTOM: 7,
}


def command_type_order(command_type: ValidationCommandType) -> int:
    """Return stable execution order for command categories."""

    return _COMMAND_TYPE_ORDER[command_type]


def classify_validation_command_type(
    command: str,
    *,
    framework: str = "",
    source: str = "",
    name: str = "",
) -> ValidationCommandType:
    """Infer the validation command type from repo metadata."""

    text = f"{name} {framework} {source} {command}".lower()
    if any(token in text for token in ("audit", "security", "pip-audit", "cargo audit", "gosec")):
        return ValidationCommandType.SECURITY_CHECK
    if "fmt --check" in text or "format" in text or "ruff format --check" in text:
        return ValidationCommandType.FORMAT_CHECK
    if any(token in text for token in ("typecheck", "type-check", "mypy", "tsc", "pyright")):
        return ValidationCommandType.TYPECHECK
    if any(token in text for token in ("test", "pytest", "vitest", "jest", "cargo test", "go test")):
        return ValidationCommandType.TEST
    if "build" in text or "cargo check" in text or "go build" in text:
        return ValidationCommandType.BUILD
    if any(token in text for token in ("lint", "ruff", "eslint", "clippy")):
        return ValidationCommandType.LINT
    return ValidationCommandType.CUSTOM


def summarize_output(value: str, *, limit: int = 500) -> str:
    """Compact tool output for tables, outcomes, and SQLite columns."""

    normalized = " ".join(value.split())
    if len(normalized) <= limit:
        return normalized
    return normalized[: max(0, limit - 3)].rstrip() + "..."


def validation_status_from_tool_result(result: ToolExecutionResult) -> ValidationStatus:
    """Map Phase 5E tool runtime status to validation status."""

    if result.status == ToolExecutionStatus.SUCCEEDED:
        return ValidationStatus.PASSED
    if result.status == ToolExecutionStatus.FAILED:
        return ValidationStatus.FAILED
    if result.status == ToolExecutionStatus.TIMED_OUT:
        return ValidationStatus.TIMED_OUT
    if result.status == ToolExecutionStatus.BLOCKED:
        return ValidationStatus.BLOCKED
    if result.status == ToolExecutionStatus.APPROVAL_REQUIRED:
        return ValidationStatus.REQUIRES_APPROVAL
    if result.status == ToolExecutionStatus.DRY_RUN:
        return ValidationStatus.SKIPPED
    return ValidationStatus.UNKNOWN


def warning_count(stdout: str, stderr: str) -> int:
    """Count warning-like lines without treating them as failures."""

    text = "\n".join([stdout, stderr])
    return sum(1 for line in text.splitlines() if re.search(r"\bwarning\b", line, re.IGNORECASE))


def classify_validation_failure(
    evidence: ValidationEvidence,
    *,
    previous_count: int = 0,
) -> ValidationFailure | None:
    """Classify a failed, blocked, timed out, or approval-gated validation result."""

    if evidence.status == ValidationStatus.PASSED:
        return None
    if evidence.status == ValidationStatus.SKIPPED and evidence.failure_classification is None:
        return None

    classification = evidence.failure_classification or _failure_classification(evidence)
    output_excerpt = evidence.stderr_summary or evidence.stdout_summary
    repeated_count = max(1, previous_count + 1)
    return ValidationFailure(
        evidence_id=evidence.id,
        command=evidence.command,
        command_type=evidence.command_type,
        classification=classification,
        summary=_failure_summary(evidence, classification),
        pattern_key=f"{evidence.repo_path}:{evidence.command_type.value}:{classification}:{_normalize_command(evidence.command)}",
        repeated_count=repeated_count,
        severity=_failure_severity(evidence.status),
        output_excerpt=output_excerpt,
    )


def aggregate_suite_status(evidence: list[ValidationEvidence]) -> ValidationStatus:
    """Return a suite status from command evidence."""

    if not evidence:
        return ValidationStatus.UNKNOWN
    statuses = [item.status for item in evidence]
    if any(status == ValidationStatus.FAILED for status in statuses):
        return ValidationStatus.FAILED
    if any(status == ValidationStatus.TIMED_OUT for status in statuses):
        return ValidationStatus.TIMED_OUT
    if any(status == ValidationStatus.BLOCKED for status in statuses):
        return ValidationStatus.BLOCKED
    if any(status == ValidationStatus.REQUIRES_APPROVAL for status in statuses):
        return ValidationStatus.REQUIRES_APPROVAL
    if all(status == ValidationStatus.SKIPPED for status in statuses):
        return ValidationStatus.SKIPPED
    if all(status in {ValidationStatus.PASSED, ValidationStatus.SKIPPED} for status in statuses):
        return ValidationStatus.PASSED
    return ValidationStatus.UNKNOWN


def suite_evidence_mode(suite: ValidationSuiteResult) -> str:
    """Describe whether release readiness rests on real validation evidence."""

    if suite.status in {ValidationStatus.PASSED, ValidationStatus.FAILED, ValidationStatus.TIMED_OUT}:
        return "real_validation_evidence"
    if suite.status in {ValidationStatus.BLOCKED, ValidationStatus.REQUIRES_APPROVAL}:
        return "approval_gated_no_execution"
    if suite.status == ValidationStatus.SKIPPED:
        return "dry_run_no_execution"
    return "no_validation_evidence"


def readiness_delta_for_validation(suite: ValidationSuiteResult) -> int:
    """Return a bounded readiness score adjustment from real validation evidence."""

    if not suite.command_results:
        return -15
    if suite.status == ValidationStatus.PASSED:
        return 10 if suite.warning_count == 0 else 5
    if suite.status == ValidationStatus.FAILED:
        return -25
    if suite.status == ValidationStatus.TIMED_OUT:
        return -20
    if suite.status in {ValidationStatus.BLOCKED, ValidationStatus.REQUIRES_APPROVAL}:
        return -10
    if suite.status == ValidationStatus.SKIPPED:
        return 0
    return -5


def adjusted_readiness_score(base_score: int, suite: ValidationSuiteResult) -> int:
    """Apply validation evidence to a release readiness score."""

    delta = readiness_delta_for_validation(suite)
    if suite.status in {
        ValidationStatus.FAILED,
        ValidationStatus.TIMED_OUT,
        ValidationStatus.BLOCKED,
        ValidationStatus.REQUIRES_APPROVAL,
    }:
        return max(0, min(base_score, 75) + delta)
    return max(0, min(100, base_score + delta))


def build_release_validation_summary(
    suite: ValidationSuiteResult,
    *,
    release_plan_id: str | None = None,
    readiness_score_before: int | None = None,
) -> ReleaseValidationSummary:
    """Build the release-facing summary for a validation suite."""

    delta = readiness_delta_for_validation(suite)
    readiness_after = (
        adjusted_readiness_score(readiness_score_before, suite)
        if readiness_score_before is not None
        else None
    )
    evidence_mode = suite_evidence_mode(suite)
    evidence_based = evidence_mode == "real_validation_evidence"
    return ReleaseValidationSummary(
        release_plan_id=release_plan_id or suite.release_plan_id,
        validation_result_id=suite.id,
        repo_path=suite.repo_path,
        repo_profile_id=suite.repo_profile_id,
        status=suite.status,
        evidence_based=evidence_based,
        simulated=False,
        readiness_score_before=readiness_score_before,
        readiness_score_after=readiness_after,
        readiness_score_delta=delta,
        pass_count=suite.pass_count,
        fail_count=suite.fail_count,
        timed_out_count=suite.timed_out_count,
        blocked_count=suite.blocked_count,
        requires_approval_count=suite.requires_approval_count,
        skipped_count=suite.skipped_count,
        warning_count=suite.warning_count,
        summary=suite.summary,
        outcome_ids=suite.outcome_ids,
        learning_signal_ids=suite.learning_signal_ids,
        decision_trace_ids=suite.decision_trace_ids,
    )


def _failure_classification(evidence: ValidationEvidence) -> str:
    if evidence.status == ValidationStatus.TIMED_OUT:
        return "timeout"
    if evidence.status == ValidationStatus.BLOCKED:
        return "policy_blocked"
    if evidence.status == ValidationStatus.REQUIRES_APPROVAL:
        return "approval_required"
    if evidence.status == ValidationStatus.SKIPPED:
        return "skipped"
    if evidence.command_type == ValidationCommandType.TEST:
        return "test_failure"
    if evidence.command_type == ValidationCommandType.LINT:
        return "lint_failure"
    if evidence.command_type == ValidationCommandType.TYPECHECK:
        return "typecheck_failure"
    if evidence.command_type == ValidationCommandType.BUILD:
        return "build_failure"
    if evidence.command_type == ValidationCommandType.FORMAT_CHECK:
        return "format_check_failure"
    if evidence.command_type == ValidationCommandType.SECURITY_CHECK:
        return "security_check_failure"
    return "nonzero_exit"


def _failure_summary(evidence: ValidationEvidence, classification: str) -> str:
    if evidence.status == ValidationStatus.REQUIRES_APPROVAL:
        return f"Validation command requires approval before execution: {evidence.command}"
    if evidence.status == ValidationStatus.BLOCKED:
        return f"Validation command was blocked by policy: {evidence.command}"
    if evidence.status == ValidationStatus.TIMED_OUT:
        return f"Validation command timed out: {evidence.command}"
    if evidence.status == ValidationStatus.SKIPPED:
        return f"Validation command was skipped: {evidence.command}"
    return f"{classification.replace('_', ' ')} in `{evidence.command}`"


def _failure_severity(status: ValidationStatus) -> float:
    return {
        ValidationStatus.FAILED: 0.72,
        ValidationStatus.TIMED_OUT: 0.68,
        ValidationStatus.BLOCKED: 0.56,
        ValidationStatus.REQUIRES_APPROVAL: 0.38,
        ValidationStatus.SKIPPED: 0.18,
        ValidationStatus.UNKNOWN: 0.3,
        ValidationStatus.PASSED: 0.0,
    }[status]


def _normalize_command(command: str) -> str:
    return re.sub(r"\s+", " ", command.strip().lower())
