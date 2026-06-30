"""Validation-coupled manifest validation for the coding loop."""

from __future__ import annotations

import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from uuid import uuid4

from hephaestus.coding_loop.schemas import (
    CreateFile,
    DeleteFile,
    MoveFile,
    OperationManifest,
)
from hephaestus.storage import RunRecord, RunRepository
from hephaestus.tool_runtime import ShellCommandRequest, ToolExecutionResult, ToolRuntime
from hephaestus.tool_runtime.schemas import ToolExecutionStatus, ToolRiskLevel
from hephaestus.validation.analysis import (
    VALIDATION_COMMAND_NOT_FOUND,
    VALIDATION_IMPORT_FAILED,
    VALIDATION_NO_TESTS_DISCOVERED,
    VALIDATION_STRUCTURE_FAILED,
    VALIDATION_SYNTAX_FAILED,
    VALIDATION_TESTS_FAILED,
    aggregate_suite_status,
    classify_validation_failure,
    output_indicates_no_tests,
    parse_test_counts,
    readiness_delta_for_validation,
    suite_evidence_mode,
    summarize_output,
    validation_status_from_tool_result,
    warning_count,
)
from hephaestus.validation.planner import build_candidate_validation_plan
from hephaestus.validation.repository import ValidationRepository
from hephaestus.validation.schemas import (
    ValidationCommand,
    ValidationCommandType,
    ValidationEvidence,
    ValidationExecutionPlan,
    ValidationExecutionResult,
    ValidationStatus,
    ValidationSuiteResult,
)


class CodingValidationEngine:
    """Run deterministic, staged validation for an applied operation manifest."""

    def __init__(self, database_path: Path | str | None = None) -> None:
        self.repository = ValidationRepository(database_path)
        self.database_path = self.repository.database_path
        self.run_repository = RunRepository(self.database_path)

    def plan_for_manifest(
        self,
        root: Path | str,
        manifest: OperationManifest,
        *,
        repo_profile_id: str | None = None,
        persist: bool = False,
    ) -> ValidationExecutionPlan:
        """Build the normalized validation plan shown before apply approval."""

        return build_candidate_validation_plan(
            root,
            model_commands=manifest.validation_commands,
            changed_files=_manifest_changed_files(manifest),
            expected_files=manifest.expected_files,
            database_path=self.database_path,
            repo_profile_id=repo_profile_id,
            persist=persist,
        )

    def run(
        self,
        root: Path | str,
        manifest: OperationManifest,
        *,
        plan: ValidationExecutionPlan | None = None,
        yes: bool = True,
    ) -> ValidationSuiteResult:
        """Run structure, syntax/import, and test validation stages."""

        workspace = Path(root).resolve()
        validation_plan = plan or self.plan_for_manifest(workspace, manifest, persist=False)
        run = self.run_repository.save_run(
            RunRecord(
                goal=f"Coding validation for {workspace.name}",
                mode="coding_validation",
                status="running",
            )
        )
        commands = _stage_commands(validation_plan, manifest)
        validation_plan = validation_plan.model_copy(
            update={
                "run_id": run.id,
                "commands": commands,
                "updated_at": datetime.now(UTC),
            }
        )
        self.repository.save_plan(validation_plan)
        suite = self._run_stages(workspace, manifest, validation_plan, yes=yes)
        self.repository.save_suite_result(suite)
        self.run_repository.complete_run(
            run.id,
            estimated_input_tokens=0,
            estimated_output_tokens=0,
            estimated_cost=0.0,
            objective_score=1.0 if suite.status == ValidationStatus.PASSED else 0.0,
            risk_score=0.1 if suite.status == ValidationStatus.PASSED else 0.65,
            summary=suite.summary,
            status="completed",
        )
        return suite

    def _run_stages(
        self,
        workspace: Path,
        manifest: OperationManifest,
        plan: ValidationExecutionPlan,
        *,
        yes: bool,
    ) -> ValidationSuiteResult:
        suite_id = f"validation_result_{uuid4().hex[:12]}"
        started = time.monotonic()
        evidence: list[ValidationEvidence] = []
        structure = _structure_evidence(suite_id, workspace, manifest, plan, plan.commands[0])
        evidence.append(_attach_failure(self.repository, structure))
        if structure.status != ValidationStatus.PASSED:
            return _suite(suite_id, plan, evidence, time.monotonic() - started)

        syntax_command = next(
            (command for command in plan.commands if command.metadata.get("stage") == "syntax"),
            None,
        )
        if syntax_command is not None:
            syntax_evidence = _run_command_evidence(
                suite_id,
                workspace,
                plan,
                syntax_command,
                database_path=self.database_path,
                yes=yes,
            )
            evidence.append(_attach_failure(self.repository, syntax_evidence))
            if syntax_evidence.status != ValidationStatus.PASSED:
                return _suite(suite_id, plan, evidence, time.monotonic() - started)

        test_commands = [command for command in plan.commands if command.command_type == ValidationCommandType.TEST]
        test_files = [str(item) for item in plan.metadata.get("expected_test_locations", [])]
        fallback_commands = [str(item) for item in plan.metadata.get("fallback_commands", [])]
        if test_commands:
            first = test_commands[0]
            first_evidence = _run_test_evidence(
                suite_id,
                workspace,
                plan,
                first,
                test_files=test_files,
                database_path=self.database_path,
                yes=yes,
            )
            if _is_no_tests(first_evidence) and fallback_commands:
                first_evidence = first_evidence.model_copy(
                    update={
                        "status": ValidationStatus.SKIPPED,
                        "metadata": {
                            **first_evidence.metadata,
                            "superseded_by_deterministic_fallback": True,
                        },
                    }
                )
                evidence.append(_attach_failure(self.repository, first_evidence))
                fallback = _fallback_command(plan, fallback_commands[0], order=len(plan.commands) + 1)
                plan = plan.model_copy(update={"commands": [*plan.commands, fallback]})
                self.repository.save_plan(plan)
                fallback_evidence = _run_test_evidence(
                    suite_id,
                    workspace,
                    plan,
                    fallback,
                    test_files=test_files,
                    database_path=self.database_path,
                    yes=yes,
                )
                evidence.append(_attach_failure(self.repository, fallback_evidence))
            else:
                evidence.append(_attach_failure(self.repository, first_evidence))
        return _suite(suite_id, plan, evidence, time.monotonic() - started)


def _stage_commands(
    plan: ValidationExecutionPlan,
    manifest: OperationManifest,
) -> list[ValidationCommand]:
    commands: list[ValidationCommand] = [
        ValidationCommand(
            plan_id=plan.id,
            repo_profile_id=plan.repo_profile_id,
            command="heph internal validate-structure",
            command_type=ValidationCommandType.CUSTOM,
            source="deterministic_structure_stage",
            order=1,
            risk_level=ToolRiskLevel.SAFE_VALIDATION,
            requires_approval=False,
            reasons=["verify manifest operations match filesystem state before running commands"],
            metadata={"stage": "structure"},
        )
    ]
    python_paths = _python_paths(manifest)
    if python_paths:
        commands.append(
            ValidationCommand(
                plan_id=plan.id,
                repo_profile_id=plan.repo_profile_id,
                command="python -m compileall -q " + " ".join(_quote(path) for path in python_paths),
                command_type=ValidationCommandType.BUILD,
                source="deterministic_syntax_stage",
                framework="python-compileall",
                order=2,
                risk_level=ToolRiskLevel.SAFE_VALIDATION,
                requires_approval=True,
                reasons=["compile created and modified Python files before running tests"],
                timeout_seconds=60,
                metadata={"stage": "syntax", "python_paths": python_paths},
            )
        )
    for command in plan.commands:
        if command.command_type == ValidationCommandType.TEST:
            commands.append(
                command.model_copy(
                    update={
                        "order": len(commands) + 1,
                        "metadata": {**command.metadata, "stage": "tests"},
                    }
                )
            )
    return commands


def _structure_evidence(
    suite_id: str,
    workspace: Path,
    manifest: OperationManifest,
    plan: ValidationExecutionPlan,
    command: ValidationCommand,
) -> ValidationEvidence:
    errors: list[str] = []
    for expected in manifest.expected_files:
        target = _safe_path(workspace, expected)
        if not target.exists():
            errors.append(f"Expected file is missing: {expected}")
        elif target.is_file() and target.stat().st_size == 0 and not expected.endswith("__init__.py"):
            created = _create_operation_for(manifest, expected)
            if created is not None and created.content:
                errors.append(f"Expected non-empty file is empty: {expected}")
    for operation in manifest.operations:
        if isinstance(operation, MoveFile):
            source = _safe_path(workspace, operation.source_path)
            destination = _safe_path(workspace, operation.destination_path)
            if source.exists():
                errors.append(f"Move source still exists: {operation.source_path}")
            if not destination.is_file():
                errors.append(f"Move destination missing: {operation.destination_path}")
        elif isinstance(operation, DeleteFile):
            target = _safe_path(workspace, operation.path)
            if target.exists():
                errors.append(f"Deleted path still exists: {operation.path}")
        else:
            target = _safe_path(workspace, operation.path)
            if not target.is_file():
                errors.append(f"Manifest path missing: {operation.path}")
    status = ValidationStatus.PASSED if not errors else ValidationStatus.FAILED
    return ValidationEvidence(
        validation_result_id=suite_id,
        plan_id=plan.id,
        command_id=command.id,
        repo_path=plan.repo_path,
        repo_profile_id=plan.repo_profile_id,
        command=command.command,
        command_type=command.command_type,
        status=status,
        exit_code=0 if status == ValidationStatus.PASSED else 1,
        stdout_summary="Structure validation passed." if not errors else "; ".join(errors),
        failure_classification=None if not errors else VALIDATION_STRUCTURE_FAILED,
        metadata={"stage": "structure", "errors": errors},
    )


def _run_command_evidence(
    suite_id: str,
    workspace: Path,
    plan: ValidationExecutionPlan,
    command: ValidationCommand,
    *,
    database_path: Path,
    yes: bool,
) -> ValidationEvidence:
    runtime = ToolRuntime(database_path, workspace_path=workspace)
    _tool_plan, action, result = runtime.run_command(
        ShellCommandRequest(
            command=command.command,
            cwd=str(workspace),
            timeout_seconds=command.timeout_seconds,
            yes=yes,
            require_approval=not yes,
        )
    )
    status = validation_status_from_tool_result(result)
    stdout_summary = result.stdout_summary or summarize_output(result.stdout)
    stderr_summary = result.stderr_summary or summarize_output(result.stderr)
    classification = _command_failure_classification(command, result)
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
        tool_action_id=action.id,
        tool_execution_result_id=result.id,
        warning_count=warning_count(result.stdout, result.stderr),
        output_truncated=result.output_truncated,
        failure_classification=classification if status != ValidationStatus.PASSED else None,
        metadata={
            "stage": command.metadata.get("stage", "command"),
            "cwd": str(workspace),
            "stdout": result.stdout,
            "stderr": result.stderr,
        },
    )


def _run_test_evidence(
    suite_id: str,
    workspace: Path,
    plan: ValidationExecutionPlan,
    command: ValidationCommand,
    *,
    test_files: list[str],
    database_path: Path,
    yes: bool,
) -> ValidationEvidence:
    evidence = _run_command_evidence(
        suite_id,
        workspace,
        plan,
        command,
        database_path=database_path,
        yes=yes,
    )
    stdout = str(evidence.metadata.get("stdout", ""))
    stderr = str(evidence.metadata.get("stderr", ""))
    counts = parse_test_counts(stdout, stderr)
    discovered = counts.get("discovered")
    if discovered is None and evidence.status == ValidationStatus.PASSED and test_files and not output_indicates_no_tests(stdout, stderr):
        discovered = len(test_files)
        counts["discovered"] = discovered
        counts["discovered_inferred_from_test_files"] = discovered
    if discovered == 0 or output_indicates_no_tests(stdout, stderr):
        return evidence.model_copy(
            update={
                "status": ValidationStatus.FAILED,
                "failure_classification": VALIDATION_NO_TESTS_DISCOVERED,
                "metadata": {
                    **evidence.metadata,
                    "stage": "test_discovery",
                    "test_counts": counts,
                    "expected_test_files": test_files,
                },
            }
        )
    if evidence.status != ValidationStatus.PASSED:
        classification = (
            VALIDATION_IMPORT_FAILED
            if _looks_like_import_failure(stdout, stderr)
            else VALIDATION_TESTS_FAILED
        )
        return evidence.model_copy(
            update={
                "failure_classification": classification,
                "metadata": {
                    **evidence.metadata,
                    "stage": "test_execution",
                    "test_counts": counts,
                    "expected_test_files": test_files,
                },
            }
        )
    return evidence.model_copy(
        update={
            "metadata": {
                **evidence.metadata,
                "stage": "test_execution",
                "test_counts": counts,
                "expected_test_files": test_files,
            }
        }
    )


def _suite(
    suite_id: str,
    plan: ValidationExecutionPlan,
    evidence: list[ValidationEvidence],
    duration_seconds: float,
) -> ValidationSuiteResult:
    counts = Counter(item.status for item in evidence)
    command_results = [_command_result(item) for item in evidence]
    status = aggregate_suite_status(evidence)
    summary = _summary(status, evidence)
    suite = ValidationSuiteResult(
        id=suite_id,
        plan_id=plan.id,
        repo_path=plan.repo_path,
        repo_profile_id=plan.repo_profile_id,
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
        summary=summary,
    )
    return suite.model_copy(
        update={
            "evidence_mode": suite_evidence_mode(suite),
            "readiness_impact": readiness_delta_for_validation(suite),
        }
    )


def _summary(status: ValidationStatus, evidence: list[ValidationEvidence]) -> str:
    initial_failure = next((item.failure_classification for item in evidence if item.failure_classification), "")
    fallback_used = any(item.metadata.get("superseded_by_deterministic_fallback") for item in evidence)
    counts = Counter(item.status for item in evidence)
    parts = [
        f"Validation {status.value}: {counts[ValidationStatus.PASSED]} passed, {counts[ValidationStatus.FAILED]} failed, {counts[ValidationStatus.SKIPPED]} skipped.",
    ]
    if initial_failure:
        parts.append(f"Initial failure: {initial_failure}.")
    if fallback_used:
        parts.append("Deterministic discovery fallback used.")
    return " ".join(parts)


def _command_result(evidence: ValidationEvidence) -> ValidationExecutionResult:
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
    )


def _attach_failure(repository: ValidationRepository, evidence: ValidationEvidence) -> ValidationEvidence:
    first = classify_validation_failure(evidence, previous_count=0)
    if first is None:
        return evidence
    previous_count = repository.count_failure_pattern(
        repo_path=evidence.repo_path,
        command=evidence.command,
        command_type=evidence.command_type.value,
        failure_classification=first.classification,
    )
    failure = classify_validation_failure(evidence, previous_count=previous_count)
    return evidence.model_copy(
        update={
            "failure_classification": failure.classification if failure is not None else None,
            "failure": failure,
        }
    )


def _fallback_command(plan: ValidationExecutionPlan, command: str, *, order: int) -> ValidationCommand:
    return ValidationCommand(
        plan_id=plan.id,
        repo_profile_id=plan.repo_profile_id,
        command=command,
        command_type=ValidationCommandType.TEST,
        source="deterministic_discovery_fallback",
        framework="python-unittest",
        order=order,
        risk_level=ToolRiskLevel.SAFE_VALIDATION,
        requires_approval=True,
        reasons=["single deterministic fallback after no tests were discovered"],
        metadata={"stage": "test_execution", "fallback": True},
    )


def _command_failure_classification(command: ValidationCommand, result: ToolExecutionResult) -> str | None:
    if result.status == ToolExecutionStatus.TIMED_OUT:
        return None
    output = "\n".join([result.stdout, result.stderr])
    if result.status == ToolExecutionStatus.FAILED and "not recognized" in output.lower():
        return VALIDATION_COMMAND_NOT_FOUND
    if command.metadata.get("stage") == "syntax":
        return VALIDATION_SYNTAX_FAILED
    return None


def _is_no_tests(evidence: ValidationEvidence) -> bool:
    return evidence.failure_classification == VALIDATION_NO_TESTS_DISCOVERED


def _looks_like_import_failure(stdout: str, stderr: str) -> bool:
    return (
        "ModuleNotFoundError" in stdout
        or "ModuleNotFoundError" in stderr
        or "ImportError" in stdout
        or "ImportError" in stderr
    )


def _manifest_changed_files(manifest: OperationManifest) -> list[str]:
    files: list[str] = []
    for operation in manifest.operations:
        if isinstance(operation, MoveFile):
            files.append(operation.destination_path)
        else:
            files.append(operation.path)
    return list(dict.fromkeys(files))


def _python_paths(manifest: OperationManifest) -> list[str]:
    return [path for path in _manifest_changed_files(manifest) if path.endswith(".py")]


def _safe_path(workspace: Path, raw_path: str) -> Path:
    pure = PurePosixPath(raw_path.replace("\\", "/"))
    if pure.is_absolute() or ".." in pure.parts or not pure.parts or ":" in pure.parts[0]:
        raise PermissionError(f"Unsafe validation path: {raw_path}")
    resolved = workspace.joinpath(*pure.parts).resolve(strict=False)
    try:
        resolved.relative_to(workspace)
    except ValueError as error:
        raise PermissionError(f"Validation path escapes repository: {raw_path}") from error
    return resolved


def _create_operation_for(manifest: OperationManifest, path: str) -> CreateFile | None:
    for operation in manifest.operations:
        if isinstance(operation, CreateFile) and operation.path == path:
            return operation
    return None


def _quote(path: str) -> str:
    if "\\" not in path and "'" not in path and '"' not in path and " " not in path:
        return path
    return '"' + path.replace('"', '\\"') + '"'
