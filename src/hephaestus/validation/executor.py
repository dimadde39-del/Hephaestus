"""Execute validation plans through the safe tool runtime."""

from __future__ import annotations

import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from hephaestus.decision import DecisionAlternative, DecisionTraceRepository, SafetyDecision, metric
from hephaestus.outcomes import OutcomeEvidence, OutcomeRecord, OutcomeRepository, OutcomeStatus
from hephaestus.storage import RunRecord, RunRepository
from hephaestus.tool_runtime import ShellCommandRequest, ToolExecutionResult, ToolRuntime
from hephaestus.validation.analysis import (
    aggregate_suite_status,
    build_release_validation_summary,
    classify_validation_failure,
    readiness_delta_for_validation,
    suite_evidence_mode,
    summarize_output,
    validation_status_from_tool_result,
    warning_count,
)
from hephaestus.validation.evaluator import (
    build_missing_commands_learning_signal,
    build_validation_failure_memory_draft,
    build_validation_learning_signal,
    build_validation_outcome,
    validation_signal_view,
)
from hephaestus.validation.planner import ValidationPlanner
from hephaestus.validation.repository import ValidationRepository
from hephaestus.validation.schemas import (
    ValidationCommand,
    ValidationCommandType,
    ValidationEvidence,
    ValidationExecutionPlan,
    ValidationExecutionResult,
    ValidationLearningSignal,
    ValidationStatus,
    ValidationSuiteResult,
)


class ValidationExecutor:
    """Run validation commands with approval gates and durable evidence."""

    def __init__(
        self,
        database_path: Path | str | None = None,
        *,
        workspace_path: Path | str = ".",
    ) -> None:
        self.repository = ValidationRepository(database_path)
        self.database_path = self.repository.database_path
        self.workspace_path = Path(workspace_path).resolve()
        self.run_repository = RunRepository(self.database_path)
        self.trace_repository = DecisionTraceRepository(self.database_path)
        self.outcome_repository = OutcomeRepository(self.database_path)

    def run(
        self,
        path: Path | str,
        *,
        plan: ValidationExecutionPlan | None = None,
        only: set[ValidationCommandType] | None = None,
        dry_run: bool = False,
        yes: bool = False,
        stop_on_failure: bool = False,
        release_plan_id: str | None = None,
        readiness_score_before: int | None = None,
    ) -> ValidationSuiteResult:
        """Execute or dry-run a validation plan."""

        root = Path(path).resolve()
        validation_plan = plan or ValidationPlanner(self.database_path).build_plan(
            root,
            release_plan_id=release_plan_id,
            persist=True,
        )
        release_id = release_plan_id or validation_plan.release_plan_id
        run = self.run_repository.save_run(
            RunRecord(
                goal=f"Validation run for {root.name}",
                mode="validation_run",
                status="running",
            )
        )
        validation_plan = validation_plan.model_copy(
            update={
                "run_id": run.id,
                "release_plan_id": release_id,
                "updated_at": datetime.now(UTC),
            }
        )
        self.repository.save_plan(validation_plan)

        started = time.monotonic()
        suite_id = f"validation_result_{uuid4().hex[:12]}"
        evidence_items: list[ValidationEvidence] = []
        command_results: list[ValidationExecutionResult] = []
        learning_views: list[ValidationLearningSignal] = []
        learning_signal_ids: list[str] = []
        failure_memory_draft_ids: list[str] = []
        outcome_ids: list[str] = []
        trace_ids: list[str] = []
        signal_keys: set[tuple[str, str]] = set()
        previous_failure = False

        if not validation_plan.commands:
            trace = self._missing_commands_trace(run.id, validation_plan)
            self.trace_repository.save_trace(trace)
            outcome = self.outcome_repository.save_outcome(
                OutcomeRecord(
                    run_id=run.id,
                    decision_trace_id=trace.id,
                    status=OutcomeStatus.FAILURE,
                    summary=f"No supported validation commands were detected for {root}.",
                    evidence=[
                        OutcomeEvidence(
                            evidence_type="validation_plan",
                            source="validation_planner",
                            content="No supported validation commands were detected.",
                            metadata={"validation_plan_id": validation_plan.id},
                        )
                    ],
                    severity=0.55,
                    confidence=0.76,
                    tags=["validation", "missing-commands"],
                )
            )
            signal = self.outcome_repository.save_learning_signal(
                build_missing_commands_learning_signal(
                    run_id=run.id,
                    decision_trace_id=trace.id,
                    outcome_id=outcome.id,
                    repo_path=str(root),
                )
            )
            learning_views.append(validation_signal_view(signal))
            learning_signal_ids.append(signal.id)
            outcome_ids.append(outcome.id)
            trace_ids.append(trace.id)

        runtime = ToolRuntime(self.database_path, workspace_path=root)
        for command in validation_plan.commands:
            should_skip = _should_skip_command(command, only=only, previous_failure=previous_failure)
            if should_skip:
                evidence = self._static_evidence(
                    suite_id,
                    validation_plan,
                    command,
                    status=ValidationStatus.SKIPPED,
                    summary="Skipped by --only filter or --stop-on-failure.",
                )
            elif command.blocked:
                evidence = self._static_evidence(
                    suite_id,
                    validation_plan,
                    command,
                    status=ValidationStatus.BLOCKED,
                    summary="Command blocked by validation safety policy.",
                )
            else:
                _plan, action, tool_result = runtime.run_command(
                    ShellCommandRequest(
                        command=command.command,
                        cwd=str(root),
                        timeout_seconds=command.timeout_seconds,
                        dry_run=dry_run,
                        yes=yes,
                        require_approval=not yes,
                    )
                )
                evidence = self._evidence_from_tool_result(
                    suite_id,
                    validation_plan,
                    command,
                    action_id=action.id,
                    result=tool_result,
                )

            evidence = self._attach_failure(evidence)
            trace = self._command_trace(run.id, command, evidence)
            self.trace_repository.save_trace(trace)
            outcome = self.outcome_repository.save_outcome(
                build_validation_outcome(evidence, run_id=run.id, decision_trace_id=trace.id)
            )
            evidence = evidence.model_copy(
                update={
                    "decision_trace_id": trace.id,
                    "outcome_id": outcome.id,
                }
            )
            if evidence.failure is not None and evidence.status != ValidationStatus.SKIPPED:
                key = (evidence.command_type.value, evidence.failure.classification)
                if key not in signal_keys:
                    signal = self.outcome_repository.save_learning_signal(
                        build_validation_learning_signal(evidence, outcome, evidence.failure)
                    )
                    draft_id: str | None = None
                    if evidence.failure.repeated_count >= 2:
                        draft = self.outcome_repository.save_failure_memory_draft(
                            build_validation_failure_memory_draft(
                                evidence,
                                outcome,
                                evidence.failure,
                            )
                        )
                        draft_id = draft.id
                        failure_memory_draft_ids.append(draft.id)
                    learning_views.append(
                        validation_signal_view(
                            signal,
                            evidence=evidence,
                            failure_memory_draft_id=draft_id,
                        )
                    )
                    learning_signal_ids.append(signal.id)
                    signal_keys.add(key)
            evidence_items.append(evidence)
            command_results.append(_command_result_from_evidence(evidence))
            outcome_ids.append(outcome.id)
            trace_ids.append(trace.id)

            if (
                stop_on_failure
                and evidence.status in {ValidationStatus.FAILED, ValidationStatus.TIMED_OUT}
            ):
                previous_failure = True

        suite = _build_suite_result(
            suite_id=suite_id,
            plan=validation_plan,
            evidence=evidence_items,
            command_results=command_results,
            duration_seconds=time.monotonic() - started,
            outcome_ids=outcome_ids,
            learning_views=learning_views,
            learning_signal_ids=learning_signal_ids,
            failure_memory_draft_ids=failure_memory_draft_ids,
            decision_trace_ids=trace_ids,
        )
        self.repository.save_suite_result(suite)
        if release_id is not None:
            self.repository.save_release_summary(
                build_release_validation_summary(
                    suite,
                    release_plan_id=release_id,
                    readiness_score_before=readiness_score_before,
                )
            )
        self.run_repository.complete_run(
            run.id,
            estimated_input_tokens=0,
            estimated_output_tokens=0,
            estimated_cost=0.0,
            objective_score=_suite_objective_score(suite),
            risk_score=_suite_risk_score(suite),
            summary=suite.summary,
            status="completed",
        )
        return suite

    def _static_evidence(
        self,
        suite_id: str,
        plan: ValidationExecutionPlan,
        command: ValidationCommand,
        *,
        status: ValidationStatus,
        summary: str,
    ) -> ValidationEvidence:
        return ValidationEvidence(
            validation_result_id=suite_id,
            plan_id=plan.id,
            command_id=command.id,
            repo_path=plan.repo_path,
            repo_profile_id=plan.repo_profile_id,
            command=command.command,
            command_type=command.command_type,
            status=status,
            stdout_summary=summary,
            failure_classification=(
                "policy_blocked" if status == ValidationStatus.BLOCKED else None
            ),
        )

    def _evidence_from_tool_result(
        self,
        suite_id: str,
        plan: ValidationExecutionPlan,
        command: ValidationCommand,
        *,
        action_id: str,
        result: ToolExecutionResult,
    ) -> ValidationEvidence:
        status = validation_status_from_tool_result(result)
        stdout_summary = result.stdout_summary or summarize_output(result.stdout)
        stderr_summary = result.stderr_summary or summarize_output(result.stderr)
        return ValidationEvidence(
            validation_result_id=suite_id,
            plan_id=plan.id,
            command_id=command.id,
            repo_path=plan.repo_path,
            repo_profile_id=plan.repo_profile_id,
            command=command.command,
            command_type=command.command_type,
            status=status,
            exit_code=result.exit_code,
            stdout_summary=stdout_summary,
            stderr_summary=stderr_summary,
            duration_seconds=result.duration_seconds,
            tool_action_id=action_id,
            tool_execution_result_id=result.id,
            warning_count=warning_count(result.stdout, result.stderr),
            output_truncated=result.output_truncated,
            failure_classification=(
                "warnings_detected"
                if status == ValidationStatus.PASSED
                and warning_count(result.stdout, result.stderr) > 0
                else None
            ),
        )

    def _attach_failure(self, evidence: ValidationEvidence) -> ValidationEvidence:
        first_pass = classify_validation_failure(evidence, previous_count=0)
        if first_pass is None:
            return evidence
        previous_count = self.repository.count_failure_pattern(
            repo_path=evidence.repo_path,
            command=evidence.command,
            command_type=evidence.command_type.value,
            failure_classification=first_pass.classification,
        )
        failure = classify_validation_failure(evidence, previous_count=previous_count)
        return evidence.model_copy(
            update={
                "failure_classification": failure.classification if failure is not None else None,
                "failure": failure,
            }
        )

    def _command_trace(
        self,
        run_id: str,
        command: ValidationCommand,
        evidence: ValidationEvidence,
    ) -> SafetyDecision:
        status = evidence.status.value
        return SafetyDecision(
            run_id=run_id,
            phase="validation_execution",
            selected_option=f"{status}: {command.command}",
            alternatives=[
                DecisionAlternative(
                    option_id="pretend_validation_passed",
                    rejection_reason="Release readiness must use observed command evidence.",
                    violated_constraints=["real validation evidence", "auditability"],
                    risk=0.85,
                )
            ],
            rationale=_trace_rationale(command, evidence),
            metrics=[
                metric("validation_plan_id", evidence.plan_id),
                metric("validation_evidence_id", evidence.id),
                metric("command_id", command.id),
                metric("command_type", command.command_type.value),
                metric("status", evidence.status.value),
                metric("exit_code", evidence.exit_code),
                metric("duration_seconds", evidence.duration_seconds),
                metric("tool_action_id", evidence.tool_action_id),
                metric("tool_execution_result_id", evidence.tool_execution_result_id),
                metric("failure_classification", evidence.failure_classification),
                metric("warning_count", evidence.warning_count),
            ],
            objective_score=1.0 if evidence.status == ValidationStatus.PASSED else 0.0,
            confidence=0.9 if evidence.tool_execution_result_id is not None else 0.72,
            constraints_considered=[
                "tool runtime result",
                "exit code",
                "timeout",
                "approval gate",
                "release evidence quality",
            ],
            tags=["validation", "execution", command.command_type.value, evidence.status.value],
            caused_by=[command.id, *( [evidence.tool_action_id] if evidence.tool_action_id else [] )],
            will_affect=["outcome_learning", "release_readiness"],
            learning_hooks=["validation_command_outcome", "failure_pattern_detection"],
            parent_id=command.decision_trace_id,
        )

    def _missing_commands_trace(
        self,
        run_id: str,
        plan: ValidationExecutionPlan,
    ) -> SafetyDecision:
        return SafetyDecision(
            run_id=run_id,
            phase="validation_execution",
            selected_option="missing_validation_commands",
            alternatives=[],
            rationale="No supported validation commands were available to execute.",
            metrics=[
                metric("validation_plan_id", plan.id),
                metric("repo_path", plan.repo_path),
                metric("command_count", 0),
            ],
            objective_score=0.0,
            confidence=0.76,
            constraints_considered=["supported repo validation commands"],
            tags=["validation", "missing-commands"],
            caused_by=[plan.id],
            will_affect=["release_readiness", "learning_signals"],
            learning_hooks=["missing_validation_commands"],
        )


def run_validation_plan(
    path: Path | str,
    *,
    database_path: Path | str | None = None,
    plan: ValidationExecutionPlan | None = None,
    only: set[ValidationCommandType] | None = None,
    dry_run: bool = False,
    yes: bool = False,
    stop_on_failure: bool = False,
    release_plan_id: str | None = None,
    readiness_score_before: int | None = None,
) -> ValidationSuiteResult:
    """Convenience wrapper for validation execution."""

    return ValidationExecutor(database_path, workspace_path=path).run(
        path,
        plan=plan,
        only=only,
        dry_run=dry_run,
        yes=yes,
        stop_on_failure=stop_on_failure,
        release_plan_id=release_plan_id,
        readiness_score_before=readiness_score_before,
    )


def _should_skip_command(
    command: ValidationCommand,
    *,
    only: set[ValidationCommandType] | None,
    previous_failure: bool,
) -> bool:
    if previous_failure:
        return True
    if only is None:
        return False
    return command.command_type not in only


def _command_result_from_evidence(evidence: ValidationEvidence) -> ValidationExecutionResult:
    return ValidationExecutionResult(
        plan_id=evidence.plan_id,
        command_id=evidence.command_id,
        command=evidence.command,
        command_type=evidence.command_type,
        status=evidence.status,
        evidence_id=evidence.id,
        exit_code=evidence.exit_code,
        stdout_summary=evidence.stdout_summary,
        stderr_summary=evidence.stderr_summary,
        duration_seconds=evidence.duration_seconds,
        tool_action_id=evidence.tool_action_id,
        tool_execution_result_id=evidence.tool_execution_result_id,
        outcome_id=evidence.outcome_id,
        decision_trace_id=evidence.decision_trace_id,
        failure=evidence.failure,
        created_at=evidence.created_at,
    )


def _build_suite_result(
    *,
    suite_id: str,
    plan: ValidationExecutionPlan,
    evidence: list[ValidationEvidence],
    command_results: list[ValidationExecutionResult],
    duration_seconds: float,
    outcome_ids: list[str],
    learning_views: list[ValidationLearningSignal],
    learning_signal_ids: list[str],
    failure_memory_draft_ids: list[str],
    decision_trace_ids: list[str],
) -> ValidationSuiteResult:
    counts = Counter(item.status for item in evidence)
    status = aggregate_suite_status(evidence)
    suite = ValidationSuiteResult(
        id=suite_id,
        plan_id=plan.id,
        repo_path=plan.repo_path,
        repo_profile_id=plan.repo_profile_id,
        release_plan_id=plan.release_plan_id,
        run_id=plan.run_id,
        status=status,
        command_results=command_results,
        evidence=evidence,
        pass_count=counts[ValidationStatus.PASSED],
        fail_count=counts[ValidationStatus.FAILED],
        skipped_count=counts[ValidationStatus.SKIPPED],
        timed_out_count=counts[ValidationStatus.TIMED_OUT],
        blocked_count=counts[ValidationStatus.BLOCKED],
        requires_approval_count=counts[ValidationStatus.REQUIRES_APPROVAL],
        unknown_count=counts[ValidationStatus.UNKNOWN],
        warning_count=sum(item.warning_count for item in evidence),
        duration_seconds=duration_seconds,
        outcome_ids=outcome_ids,
        learning_signals=learning_views,
        learning_signal_ids=learning_signal_ids,
        failure_memory_draft_ids=failure_memory_draft_ids,
        decision_trace_ids=decision_trace_ids,
        summary=_suite_summary(status, evidence),
    )
    return suite.model_copy(
        update={
            "evidence_mode": suite_evidence_mode(suite),
            "readiness_impact": readiness_delta_for_validation(suite),
        }
    )


def _suite_summary(status: ValidationStatus, evidence: list[ValidationEvidence]) -> str:
    if not evidence:
        return "No validation commands were available to execute."
    counts = Counter(item.status for item in evidence)
    return (
        f"Validation {status.value}: "
        f"{counts[ValidationStatus.PASSED]} passed, "
        f"{counts[ValidationStatus.FAILED]} failed, "
        f"{counts[ValidationStatus.TIMED_OUT]} timed out, "
        f"{counts[ValidationStatus.REQUIRES_APPROVAL]} require approval, "
        f"{counts[ValidationStatus.BLOCKED]} blocked, "
        f"{counts[ValidationStatus.SKIPPED]} skipped."
    )


def _trace_rationale(command: ValidationCommand, evidence: ValidationEvidence) -> str:
    if evidence.status == ValidationStatus.PASSED:
        return f"`{command.command}` exited successfully and is counted as real validation evidence."
    if evidence.status == ValidationStatus.FAILED:
        return f"`{command.command}` exited nonzero and downgraded release readiness."
    if evidence.status == ValidationStatus.TIMED_OUT:
        return f"`{command.command}` timed out before producing a passing validation result."
    if evidence.status == ValidationStatus.REQUIRES_APPROVAL:
        return f"`{command.command}` was not executed because explicit --yes approval was missing."
    if evidence.status == ValidationStatus.BLOCKED:
        return f"`{command.command}` was blocked by validation/tool safety policy."
    if evidence.status == ValidationStatus.SKIPPED:
        return f"`{command.command}` was skipped, so it is not real validation evidence."
    return f"`{command.command}` produced unknown validation status."


def _suite_objective_score(suite: ValidationSuiteResult) -> float:
    total = len(suite.command_results)
    if total == 0:
        return 0.0
    return suite.pass_count / total


def _suite_risk_score(suite: ValidationSuiteResult) -> float:
    total = len(suite.command_results)
    if total == 0:
        return 0.5
    bad = (
        suite.fail_count
        + suite.timed_out_count
        + suite.blocked_count
        + suite.requires_approval_count
    )
    return min(1.0, bad / total)
