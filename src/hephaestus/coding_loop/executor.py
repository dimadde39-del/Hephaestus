"""Controlled apply/validate/rollback loop for repo-aware coding."""

from __future__ import annotations

import subprocess
from datetime import UTC, datetime
from pathlib import Path

from hephaestus.coding_loop.analysis import (
    record_coding_learning_signal,
    record_coding_outcome,
    record_coding_trace,
)
from hephaestus.coding_loop.greenfield import CodingProviderError, GreenfieldCodingExecutor
from hephaestus.coding_loop.operations import apply_manifest
from hephaestus.coding_loop.patcher import CodingPatcher
from hephaestus.coding_loop.planner import CodingPlanner
from hephaestus.coding_loop.repository import CodingLoopRepository
from hephaestus.coding_loop.reviewer import CodingPatchReviewer
from hephaestus.coding_loop.rollback import (
    cleanup_after_rollback,
    cleanup_metadata,
    create_failed_workspace_snapshot,
    snapshot_artifact_root,
)
from hephaestus.coding_loop.schemas import (
    CodingChangeProposal,
    CodingIteration,
    CodingLoopResult,
    CodingLoopStatus,
    CodingPlan,
    CodingRequest,
    CodingReview,
    CodingScopeType,
    CodingValidationSummary,
)
from hephaestus.coding_loop.validation import CodingValidationEngine
from hephaestus.models import ModelProvider
from hephaestus.outcomes import (
    LearningDirection,
    LearningSignalType,
    OutcomeStatus,
)
from hephaestus.storage import RunRecord, RunRepository
from hephaestus.tool_runtime import ToolExecutionStatus, ToolRuntime
from hephaestus.tool_runtime.checkpoint import restore_checkpoint
from hephaestus.tool_runtime.repository import ToolRuntimeRepository
from hephaestus.validation import ValidationExecutor, ValidationStatus
from hephaestus.validation.schemas import ValidationSuiteResult


class CodingLoopExecutor:
    """Plan, propose, review, apply, validate, and optionally rollback."""

    def __init__(
        self,
        database_path: Path | str | None = None,
        *,
        provider_override: ModelProvider | None = None,
        provider_source: str = "injected",
    ) -> None:
        self.repository = CodingLoopRepository(database_path)
        self.database_path = self.repository.database_path
        self.provider_override = provider_override
        self.provider_source = provider_source
        self.planner = CodingPlanner(self.database_path)
        self.patcher = CodingPatcher(self.database_path)
        self.reviewer = CodingPatchReviewer(self.database_path)
        self.run_repository = RunRepository(self.database_path)

    def plan(
        self,
        user_request: str,
        *,
        repo_path: Path | str = ".",
        scope: CodingScopeType | None = None,
        conversation_id: str | None = None,
    ) -> tuple[CodingRequest, CodingPlan]:
        """Create a coding request and plan."""

        return self.planner.plan(
            user_request,
            repo_path=repo_path,
            scope=scope,
            conversation_id=conversation_id,
        )

    def propose(
        self,
        user_request: str,
        *,
        repo_path: Path | str = ".",
        scope: CodingScopeType | None = None,
    ) -> tuple[CodingRequest, CodingPlan, CodingChangeProposal]:
        """Plan and create a patch proposal without applying it."""

        request, plan = self.plan(user_request, repo_path=repo_path, scope=scope)
        if plan.scope_too_large:
            result = self._scope_blocked_result(request, plan)
            self.repository.save_result(result)
            raise ValueError(plan.summary)
        change = self.patcher.propose(plan)
        return request, plan, change

    def apply_change(
        self,
        change_id: str,
        *,
        yes: bool = False,
        dry_run: bool = False,
        no_validate: bool = False,
        rollback_on_failure: bool = False,
        allow_one_repair: bool = False,
        retain_failed_snapshot: bool = False,
        artifact_root: Path | str | None = None,
    ) -> CodingLoopResult:
        """Apply a previously proposed coding change."""

        change = self.repository.get_change_proposal(change_id)
        if change is None:
            raise ValueError(f"Coding change not found: {change_id}")
        plan = self.repository.get_plan(change.plan_id)
        if plan is None:
            raise ValueError(f"Coding plan not found for change: {change.plan_id}")
        request = self.repository.get_request(change.request_id)
        if request is None:
            raise ValueError(f"Coding request not found for change: {change.request_id}")
        if change.manifest is not None:
            return self._apply_manifest_change(
                request,
                plan,
                change,
                yes=yes,
                dry_run=dry_run,
                no_validate=no_validate,
                rollback_on_failure=rollback_on_failure,
                allow_one_repair=allow_one_repair,
                retain_failed_snapshot=retain_failed_snapshot,
                artifact_root=artifact_root,
            )
        review = self.reviewer.review(plan, change, validation_enabled=not no_validate)
        return self._execute_reviewed_change(
            request,
            plan,
            change,
            review,
            yes=yes,
            dry_run=dry_run,
            no_validate=no_validate,
            rollback_on_failure=rollback_on_failure,
            allow_one_repair=allow_one_repair,
        )

    def _apply_manifest_change(
        self,
        request: CodingRequest,
        plan: CodingPlan,
        change: CodingChangeProposal,
        *,
        yes: bool,
        dry_run: bool,
        no_validate: bool,
        rollback_on_failure: bool,
        allow_one_repair: bool,
        retain_failed_snapshot: bool,
        artifact_root: Path | str | None,
    ) -> CodingLoopResult:
        if not yes:
            return self.repository.save_result(
                self._blocked_result(
                    request,
                    plan,
                    status=CodingLoopStatus.REQUIRES_APPROVAL,
                    summary="Manifest application requires explicit approval.",
                    outcome_summary="Structured operations were not applied without approval.",
                )
            )
        if dry_run:
            return self.repository.save_result(
                self._blocked_result(
                    request,
                    plan,
                    status=CodingLoopStatus.PATCH_PROPOSED,
                    summary="Manifest preflight completed; dry-run made no changes.",
                    outcome_summary="Structured manifest was reviewed without applying it.",
                )
            )
        if change.manifest is None:
            raise ValueError("Structured manifest is missing.")
        applied = apply_manifest(plan.repo_path, change.manifest)
        ToolRuntimeRepository(self.database_path).save_checkpoint(applied.checkpoint)
        validation = _validation_not_run("validation disabled")
        status = CodingLoopStatus.COMPLETED
        validation_id: str | None = None
        validation_ids: list[str] = []
        repair_attempted = False
        repair_result = "not_attempted"
        repair_checkpoint_id: str | None = None
        cleanup_info: dict[str, object] | None = None
        snapshot_info: dict[str, str] | None = None
        if not no_validate:
            engine = CodingValidationEngine(self.database_path)
            validation_plan = engine.plan_for_manifest(
                plan.repo_path,
                change.manifest,
                repo_profile_id=plan.repo_profile_id,
                persist=True,
            )
            suite = engine.run(plan.repo_path, change.manifest, plan=validation_plan, yes=True)
            validation = _validation_summary(suite)
            validation_id = suite.id
            validation_ids.append(suite.id)
            status = (
                CodingLoopStatus.COMPLETED
                if suite.status == ValidationStatus.PASSED and suite.pass_count > 0
                else CodingLoopStatus.VALIDATION_FAILED
            )
            final_suite = suite
            repair_inventory = None
            if status == CodingLoopStatus.VALIDATION_FAILED and allow_one_repair:
                repair_attempted = True
                try:
                    repair_manifest = GreenfieldCodingExecutor(
                        self.database_path,
                        provider_override=self.provider_override,
                        provider_source=self.provider_source,
                    ).repair(
                        request_id=request.id,
                        plan_id=plan.id,
                        change_id=change.id,
                        validation=suite,
                        current_diff=_git_diff(Path(plan.repo_path)),
                        created_file_inventory=applied.files_touched,
                        approved=True,
                    )
                    repaired = apply_manifest(plan.repo_path, repair_manifest)
                    repair_inventory = repaired.inventory
                    repair_checkpoint_id = repaired.checkpoint.id
                    ToolRuntimeRepository(self.database_path).save_checkpoint(repaired.checkpoint)
                    final_suite = engine.run(plan.repo_path, change.manifest, plan=validation_plan, yes=True)
                    validation = _validation_summary(final_suite)
                    validation_id = final_suite.id
                    validation_ids.append(final_suite.id)
                    status = (
                        CodingLoopStatus.COMPLETED
                        if final_suite.status == ValidationStatus.PASSED and final_suite.pass_count > 0
                        else CodingLoopStatus.VALIDATION_FAILED
                    )
                    repair_result = "validation_passed" if status == CodingLoopStatus.COMPLETED else "validation_failed"
                except (CodingProviderError, PermissionError, ValueError, FileNotFoundError) as error:
                    repair_result = f"failed: {error}"
                    final_suite = suite
            if status == CodingLoopStatus.VALIDATION_FAILED and rollback_on_failure:
                if retain_failed_snapshot:
                    snapshot = create_failed_workspace_snapshot(
                        plan.repo_path,
                        snapshot_artifact_root(artifact_root, final_suite.id),
                        suite=final_suite,
                    )
                    snapshot_info = {
                        "snapshot_path": snapshot.snapshot_path,
                        "diff_path": snapshot.diff_path,
                        "hashes_path": snapshot.hashes_path,
                        "validation_path": snapshot.validation_path,
                    }
                restored = restore_checkpoint(applied.checkpoint)
                ToolRuntimeRepository(self.database_path).save_checkpoint(restored)
                inventories = [applied.inventory]
                if repair_inventory is not None:
                    inventories.append(repair_inventory)
                cleanup = cleanup_after_rollback(plan.repo_path, inventories)
                cleanup_info = cleanup_metadata(cleanup)
                status = CodingLoopStatus.ROLLED_BACK
        iteration = CodingIteration(
            request_id=request.id,
            plan_id=plan.id,
            change_id=change.id,
            status=status,
            summary=(
                "Structured manifest applied and validation passed."
                if status == CodingLoopStatus.COMPLETED
                else validation.summary
            ),
            checkpoint_id=applied.checkpoint.id,
            validation_result_id=validation_id,
            rollback_checkpoint_id=applied.checkpoint.id if status == CodingLoopStatus.ROLLED_BACK else None,
            metadata={
                "manifest_files": applied.files_touched,
                "normalized_validation_plan": change.metadata.get("normalized_validation_plan"),
                "initial_validation_result_id": validation_ids[0] if validation_ids else None,
                "final_validation_result_id": validation_id,
                "repair_attempted": repair_attempted,
                "repair_result": repair_result,
                "repair_checkpoint_id": repair_checkpoint_id,
                "rollback_cleanup": cleanup_info,
                "failed_snapshot": snapshot_info,
            },
        )
        self.repository.save_iteration(iteration)
        return self.repository.save_result(
            CodingLoopResult(
                request_id=request.id,
                plan_id=plan.id,
                change_id=change.id,
                repo_path=plan.repo_path,
                repo_profile_id=plan.repo_profile_id,
                conversation_id=plan.conversation_id,
                run_id=plan.run_id,
                active_policy_profile=plan.active_policy_profile,
                user_request=request.user_request,
                scope_type=plan.scope.scope_type,
                risk=change.risk,
                status=status,
                summary=iteration.summary,
                iteration_ids=[iteration.id],
                checkpoint_ids=[
                    value for value in [applied.checkpoint.id, repair_checkpoint_id] if value
                ],
                validation_result_ids=validation_ids,
                validation=validation,
                metadata=iteration.metadata,
            )
        )

    def run(
        self,
        user_request: str,
        *,
        repo_path: Path | str = ".",
        dry_run: bool = False,
        yes: bool = False,
        max_iterations: int = 1,
        no_validate: bool = False,
        rollback_on_failure: bool = False,
        scope: CodingScopeType | None = None,
        allow_one_repair: bool = False,
    ) -> CodingLoopResult:
        """Run the first bounded coding loop iteration."""

        if max_iterations < 1:
            raise ValueError("max_iterations must be at least 1")
        request, plan = self.plan(user_request, repo_path=repo_path, scope=scope)
        if plan.scope_too_large:
            result = self._scope_blocked_result(request, plan)
            return self.repository.save_result(result)
        try:
            change = self.patcher.propose(plan)
        except (FileNotFoundError, PermissionError, ValueError) as error:
            result = self._blocked_result(
                request,
                plan,
                status=CodingLoopStatus.BLOCKED,
                summary=str(error),
                outcome_summary="Patch proposal could not be generated.",
            )
            return self.repository.save_result(result)

        review = self.reviewer.review(plan, change, validation_enabled=not no_validate)
        if dry_run:
            iteration = CodingIteration(
                request_id=request.id,
                plan_id=plan.id,
                change_id=change.id,
                review_id=review.id,
                status=CodingLoopStatus.PATCH_PROPOSED if review.approved else CodingLoopStatus.BLOCKED,
                summary="Dry-run only; patch was proposed and reviewed but not applied.",
                decision_trace_ids=[value for value in [review.decision_trace_id] if value is not None],
                metadata={"review": review.model_dump(mode="json")},
            )
            self.repository.save_iteration(iteration)
            result = self._result_from_parts(
                request,
                plan,
                change,
                iteration,
                status=iteration.status,
                summary=iteration.summary,
                validation=_validation_not_run("dry-run only; validation was not executed"),
            )
            return self.repository.save_result(result)

        return self._execute_reviewed_change(
            request,
            plan,
            change,
            review,
            yes=yes,
            dry_run=False,
            no_validate=no_validate,
            rollback_on_failure=rollback_on_failure,
            allow_one_repair=allow_one_repair,
        )

    def _execute_reviewed_change(
        self,
        request: CodingRequest,
        plan: CodingPlan,
        change: CodingChangeProposal,
        review: CodingReview,
        *,
        yes: bool,
        dry_run: bool,
        no_validate: bool,
        rollback_on_failure: bool,
        allow_one_repair: bool = False,
    ) -> CodingLoopResult:
        change = change.model_copy(
            update={
                "review_id": review.id,
                "metadata": {**change.metadata, "review": review.model_dump(mode="json")},
                "updated_at": datetime.now(UTC),
            }
        )
        self.repository.save_change_proposal(change)
        if review.blocked:
            iteration = self._blocked_iteration(
                request,
                plan,
                change,
                review,
                summary=review.summary,
            )
            self.repository.save_iteration(iteration)
            result = self._result_from_parts(
                request,
                plan,
                change,
                iteration,
                status=CodingLoopStatus.BLOCKED,
                summary=review.summary,
                validation=_validation_not_run("patch review blocked apply"),
            )
            return self.repository.save_result(result)
        if not yes and not dry_run:
            iteration = CodingIteration(
                request_id=request.id,
                plan_id=plan.id,
                change_id=change.id,
                review_id=review.id,
                status=CodingLoopStatus.REQUIRES_APPROVAL,
                summary="Patch application requires --yes.",
                decision_trace_ids=[value for value in [review.decision_trace_id] if value is not None],
                metadata={"review": review.model_dump(mode="json")},
            )
            self.repository.save_iteration(iteration)
            self._approval_missing_outcome(plan, change)
            result = self._result_from_parts(
                request,
                plan,
                change,
                iteration,
                status=CodingLoopStatus.REQUIRES_APPROVAL,
                summary="Patch proposal reviewed. Re-run with --yes to apply.",
                validation=_validation_not_run("approval missing"),
            )
            return self.repository.save_result(result)

        patch_id = change.patch_set.patch_ids[0] if change.patch_set.patch_ids else ""
        runtime = ToolRuntime(self.database_path, workspace_path=plan.repo_path)
        _tool_plan, action, tool_result, apply_result = runtime.apply_patch(
            patch_id,
            yes=yes,
            dry_run=dry_run,
        )
        checkpoint_id = tool_result.checkpoint_id
        status = _status_from_apply(tool_result.status)
        iteration = CodingIteration(
            request_id=request.id,
            plan_id=plan.id,
            change_id=change.id,
            review_id=review.id,
            status=status,
            summary=tool_result.stdout_summary or status.value,
            apply_tool_action_id=action.id,
            apply_tool_result_id=tool_result.id,
            checkpoint_id=checkpoint_id,
            decision_trace_ids=[
                value
                for value in [review.decision_trace_id, action.decision_trace_id]
                if value is not None
            ],
            outcome_ids=[value for value in [action.outcome_id] if value is not None],
            metadata={
                "review": review.model_dump(mode="json"),
                "apply_result": apply_result.model_dump(mode="json") if apply_result is not None else None,
            },
        )
        if tool_result.status != ToolExecutionStatus.SUCCEEDED:
            self.repository.save_iteration(iteration)
            result = self._result_from_parts(
                request,
                plan,
                change,
                iteration,
                status=status,
                summary=tool_result.stdout_summary or "Patch was not applied.",
                validation=_validation_not_run("patch was not applied"),
            )
            return self.repository.save_result(result)

        patch_trace = record_coding_trace(
            self.database_path,
            run_id=_run_id(plan, self.run_repository),
            phase="patch_applied",
            selected_option=patch_id,
            rationale="Patch was applied through the safe tool runtime after review and approval.",
            request_id=request.id,
            status=CodingLoopStatus.PATCH_APPLIED,
            risk=change.risk,
            related_ids=[change.id, action.id, patch_id],
            objective_score=1.0,
            tags=["patch_applied"],
        )
        patch_outcome = record_coding_outcome(
            self.database_path,
            run_id=patch_trace.run_id,
            decision_trace_id=patch_trace.id,
            status=OutcomeStatus.SUCCESS,
            summary=f"Patch applied for coding request {request.id}.",
            request_id=request.id,
            evidence_content=tool_result.stdout_summary,
            tags=["patch-applied"],
        )
        iteration = iteration.model_copy(
            update={
                "decision_trace_ids": [*iteration.decision_trace_ids, patch_trace.id],
                "outcome_ids": [*iteration.outcome_ids, patch_outcome.id],
                "updated_at": datetime.now(UTC),
            }
        )

        validation = _validation_not_run("validation disabled by --no-validate")
        if not no_validate:
            iteration = iteration.model_copy(
                update={
                    "status": CodingLoopStatus.VALIDATION_RUNNING,
                    "summary": "Patch applied; validation running.",
                    "updated_at": datetime.now(UTC),
                }
            )
            self.repository.save_iteration(iteration)
            suite = ValidationExecutor(self.database_path, workspace_path=plan.repo_path).run(
                plan.repo_path,
                yes=yes,
                dry_run=False,
                stop_on_failure=False,
            )
            validation = _validation_summary(suite)
            iteration = iteration.model_copy(
                update={
                    "validation_result_id": suite.id,
                    "status": (
                        CodingLoopStatus.VALIDATION_PASSED
                        if suite.status == ValidationStatus.PASSED
                        else CodingLoopStatus.VALIDATION_FAILED
                    ),
                    "summary": suite.summary,
                    "outcome_ids": [*iteration.outcome_ids, *suite.outcome_ids],
                    "learning_signal_ids": [*iteration.learning_signal_ids, *suite.learning_signal_ids],
                    "decision_trace_ids": [
                        *iteration.decision_trace_ids,
                        *suite.decision_trace_ids,
                    ],
                    "updated_at": datetime.now(UTC),
                }
            )
            iteration = self._record_validation_coding_outcome(
                request,
                plan,
                change,
                iteration,
                suite,
            )
            if suite.status != ValidationStatus.PASSED and rollback_on_failure and checkpoint_id:
                iteration = self._rollback_after_failure(
                    request,
                    plan,
                    change,
                    iteration,
                    checkpoint_id,
                )
        else:
            iteration = iteration.model_copy(
                update={
                    "status": CodingLoopStatus.COMPLETED,
                    "summary": "Patch applied; validation skipped by --no-validate.",
                    "updated_at": datetime.now(UTC),
                }
            )

        self.repository.save_iteration(iteration)
        final_status = _final_status(iteration.status, validation)
        result = self._result_from_parts(
            request,
            plan,
            change,
            iteration,
            status=final_status,
            summary=_final_summary(iteration, validation),
            validation=validation,
        )
        return self.repository.save_result(result)

    def _record_validation_coding_outcome(
        self,
        request: CodingRequest,
        plan: CodingPlan,
        change: CodingChangeProposal,
        iteration: CodingIteration,
        suite: ValidationSuiteResult,
    ) -> CodingIteration:
        passed = suite.status == ValidationStatus.PASSED
        trace = record_coding_trace(
            self.database_path,
            run_id=_run_id(plan, self.run_repository),
            phase="validation_result",
            selected_option=suite.status.value,
            rationale=suite.summary,
            request_id=request.id,
            status=(
                CodingLoopStatus.VALIDATION_PASSED
                if passed
                else CodingLoopStatus.VALIDATION_FAILED
            ),
            risk=change.risk,
            related_ids=[change.id, suite.id],
            objective_score=1.0 if passed else 0.0,
            safety=False,
            tags=["validation"],
        )
        outcome = record_coding_outcome(
            self.database_path,
            run_id=trace.run_id,
            decision_trace_id=trace.id,
            status=OutcomeStatus.SUCCESS if passed else OutcomeStatus.FAILURE,
            summary=suite.summary,
            request_id=request.id,
            severity=0.0 if passed else 0.65,
            evidence_content=suite.summary,
            tags=["validation-passed" if passed else "validation-failed"],
        )
        learning_signal_ids = list(iteration.learning_signal_ids)
        if not passed:
            signal = record_coding_learning_signal(
                self.database_path,
                run_id=trace.run_id,
                decision_trace_id=trace.id,
                outcome_id=outcome.id,
                signal_type=LearningSignalType.VALIDATION_STRATEGY,
                direction=LearningDirection.INVESTIGATE,
                target="coding_loop_validation",
                rationale="A coding-loop patch failed validation and should inform future patch scope.",
                strength=0.7,
                tags=["validation-failure"],
            )
            learning_signal_ids.append(signal.id)
        return iteration.model_copy(
            update={
                "outcome_ids": [*iteration.outcome_ids, outcome.id],
                "learning_signal_ids": learning_signal_ids,
                "decision_trace_ids": [*iteration.decision_trace_ids, trace.id],
                "updated_at": datetime.now(UTC),
            }
        )

    def _rollback_after_failure(
        self,
        request: CodingRequest,
        plan: CodingPlan,
        change: CodingChangeProposal,
        iteration: CodingIteration,
        checkpoint_id: str,
    ) -> CodingIteration:
        runtime = ToolRuntime(self.database_path, workspace_path=plan.repo_path)
        _restore_plan, action, result, _restored = runtime.restore_checkpoint(
            checkpoint_id,
            yes=True,
            dry_run=False,
        )
        trace = record_coding_trace(
            self.database_path,
            run_id=_run_id(plan, self.run_repository),
            phase="rollback_decision",
            selected_option="restore_checkpoint",
            rationale="Validation failed and --rollback-on-failure was set, so the checkpoint was restored.",
            request_id=request.id,
            status=CodingLoopStatus.ROLLED_BACK,
            risk=change.risk,
            related_ids=[change.id, checkpoint_id, action.id],
            objective_score=1.0 if result.status == ToolExecutionStatus.RESTORED else 0.0,
            tags=["rollback"],
        )
        outcome = record_coding_outcome(
            self.database_path,
            run_id=trace.run_id,
            decision_trace_id=trace.id,
            status=(
                OutcomeStatus.SUCCESS
                if result.status == ToolExecutionStatus.RESTORED
                else OutcomeStatus.FAILURE
            ),
            summary=result.stdout_summary or f"Rollback attempted for {checkpoint_id}.",
            request_id=request.id,
            severity=0.0 if result.status == ToolExecutionStatus.RESTORED else 0.7,
            evidence_content=result.stdout_summary,
            tags=["rollback"],
        )
        return iteration.model_copy(
            update={
                "status": CodingLoopStatus.ROLLED_BACK,
                "summary": result.stdout_summary or "Rollback performed.",
                "rollback_tool_action_id": action.id,
                "rollback_checkpoint_id": checkpoint_id,
                "outcome_ids": [*iteration.outcome_ids, outcome.id],
                "decision_trace_ids": [*iteration.decision_trace_ids, trace.id],
                "updated_at": datetime.now(UTC),
            }
        )

    def _scope_blocked_result(
        self,
        request: CodingRequest,
        plan: CodingPlan,
    ) -> CodingLoopResult:
        return self._blocked_result(
            request,
            plan,
            status=CodingLoopStatus.SCOPE_TOO_LARGE,
            summary=plan.summary,
            outcome_summary="Scope blocked because the request is too large for Phase 5G.",
        )

    def _blocked_result(
        self,
        request: CodingRequest,
        plan: CodingPlan,
        *,
        status: CodingLoopStatus,
        summary: str,
        outcome_summary: str,
    ) -> CodingLoopResult:
        run_id = _run_id(plan, self.run_repository)
        trace = record_coding_trace(
            self.database_path,
            run_id=run_id,
            phase=status.value,
            selected_option=status.value,
            rationale=summary,
            request_id=request.id,
            status=status,
            risk=plan.scope.risk,
            related_ids=[plan.id],
            objective_score=0.0,
            tags=[status.value],
        )
        outcome = record_coding_outcome(
            self.database_path,
            run_id=run_id,
            decision_trace_id=trace.id,
            status=OutcomeStatus.PARTIAL if status == CodingLoopStatus.SCOPE_TOO_LARGE else OutcomeStatus.FAILURE,
            summary=outcome_summary,
            request_id=request.id,
            severity=0.5,
            evidence_content=summary,
            tags=[status.value],
        )
        signal = record_coding_learning_signal(
            self.database_path,
            run_id=run_id,
            decision_trace_id=trace.id,
            outcome_id=outcome.id,
            signal_type=LearningSignalType.TASK_ORDERING,
            direction=LearningDirection.INVESTIGATE,
            target="coding_loop_scope",
            rationale="The coding loop needs a narrower request before patching.",
            strength=0.45,
            tags=["scope"],
        )
        return CodingLoopResult(
            request_id=request.id,
            plan_id=plan.id,
            repo_path=plan.repo_path,
            repo_profile_id=plan.repo_profile_id,
            conversation_id=plan.conversation_id,
            run_id=run_id,
            active_policy_profile=plan.active_policy_profile,
            user_request=plan.user_request,
            scope_type=plan.scope.scope_type,
            risk=plan.scope.risk,
            status=status,
            summary=summary,
            outcome_ids=[outcome.id],
            learning_signal_ids=[signal.id],
            decision_trace_ids=[trace.id, *plan.decision_trace_ids],
            validation=_validation_not_run("scope blocked before validation"),
        )

    def _blocked_iteration(
        self,
        request: CodingRequest,
        plan: CodingPlan,
        change: CodingChangeProposal,
        review: CodingReview,
        *,
        summary: str,
    ) -> CodingIteration:
        return CodingIteration(
            request_id=request.id,
            plan_id=plan.id,
            change_id=change.id,
            review_id=review.id,
            status=CodingLoopStatus.BLOCKED,
            summary=summary,
            decision_trace_ids=[value for value in [review.decision_trace_id] if value is not None],
            metadata={"review": review.model_dump(mode="json")},
        )

    def _approval_missing_outcome(
        self,
        plan: CodingPlan,
        change: CodingChangeProposal,
    ) -> None:
        run_id = _run_id(plan, self.run_repository)
        trace = record_coding_trace(
            self.database_path,
            run_id=run_id,
            phase="approval_missing",
            selected_option="requires_approval",
            rationale="Patch application was not attempted because --yes was not provided.",
            request_id=plan.request_id,
            status=CodingLoopStatus.REQUIRES_APPROVAL,
            risk=change.risk,
            related_ids=[change.id],
            objective_score=0.5,
            tags=["approval"],
        )
        record_coding_outcome(
            self.database_path,
            run_id=run_id,
            decision_trace_id=trace.id,
            status=OutcomeStatus.PARTIAL,
            summary="Patch proposal is waiting for explicit approval.",
            request_id=plan.request_id,
            severity=0.2,
            tags=["approval-missing"],
        )

    def _result_from_parts(
        self,
        request: CodingRequest,
        plan: CodingPlan,
        change: CodingChangeProposal,
        iteration: CodingIteration,
        *,
        status: CodingLoopStatus,
        summary: str,
        validation: CodingValidationSummary,
    ) -> CodingLoopResult:
        checkpoint_ids = [value for value in [iteration.checkpoint_id, iteration.rollback_checkpoint_id] if value]
        tool_action_ids = [
            *change.patch_set.tool_action_ids,
            *[
                value
                for value in [iteration.apply_tool_action_id, iteration.rollback_tool_action_id]
                if value
            ],
        ]
        validation_ids = [value for value in [validation.validation_result_id] if value is not None]
        return CodingLoopResult(
            request_id=request.id,
            plan_id=plan.id,
            change_id=change.id,
            repo_path=plan.repo_path,
            repo_profile_id=plan.repo_profile_id,
            conversation_id=plan.conversation_id,
            run_id=_run_id(plan, self.run_repository),
            active_policy_profile=plan.active_policy_profile,
            user_request=plan.user_request,
            scope_type=plan.scope.scope_type,
            risk=plan.scope.risk,
            status=status,
            summary=summary,
            iteration_ids=[iteration.id],
            patch_ids=change.patch_set.patch_ids,
            tool_action_ids=tool_action_ids,
            checkpoint_ids=checkpoint_ids,
            validation_result_ids=validation_ids,
            outcome_ids=[
                *change.outcome_ids,
                *iteration.outcome_ids,
                *validation.outcome_ids,
            ],
            learning_signal_ids=[
                *iteration.learning_signal_ids,
                *validation.learning_signal_ids,
            ],
            decision_trace_ids=[
                *plan.decision_trace_ids,
                *change.decision_trace_ids,
                *iteration.decision_trace_ids,
                *validation.decision_trace_ids,
            ],
            validation=validation,
        )


def _run_id(plan: CodingPlan, run_repository: RunRepository) -> str:
    if plan.run_id is not None:
        return plan.run_id
    return run_repository.save_run(
        RunRecord(goal=f"Coding loop: {plan.user_request}", mode="coding_loop")
    ).id


def _git_diff(root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "diff", "--no-ext-diff", "--", "."],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return completed.stdout


def _status_from_apply(status: ToolExecutionStatus) -> CodingLoopStatus:
    if status == ToolExecutionStatus.SUCCEEDED:
        return CodingLoopStatus.PATCH_APPLIED
    if status == ToolExecutionStatus.DRY_RUN:
        return CodingLoopStatus.PATCH_PROPOSED
    if status == ToolExecutionStatus.APPROVAL_REQUIRED:
        return CodingLoopStatus.REQUIRES_APPROVAL
    return CodingLoopStatus.BLOCKED


def _validation_summary(suite: ValidationSuiteResult) -> CodingValidationSummary:
    return CodingValidationSummary(
        validation_result_id=suite.id,
        validation_plan_id=suite.plan_id,
        status=suite.status.value,
        command_count=len(suite.command_results),
        pass_count=suite.pass_count,
        fail_count=suite.fail_count + suite.timed_out_count,
        skipped_count=suite.skipped_count,
        blocked_count=suite.blocked_count,
        requires_approval_count=suite.requires_approval_count,
        summary=suite.summary,
        evidence_mode=suite.evidence_mode,
        decision_trace_ids=suite.decision_trace_ids,
        outcome_ids=suite.outcome_ids,
        learning_signal_ids=suite.learning_signal_ids,
    )


def _validation_not_run(summary: str) -> CodingValidationSummary:
    return CodingValidationSummary(status="not_run", summary=summary)


def _final_status(
    iteration_status: CodingLoopStatus,
    validation: CodingValidationSummary,
) -> CodingLoopStatus:
    if iteration_status == CodingLoopStatus.ROLLED_BACK:
        return CodingLoopStatus.ROLLED_BACK
    if validation.status == ValidationStatus.PASSED.value:
        return CodingLoopStatus.COMPLETED
    if validation.status in {
        ValidationStatus.FAILED.value,
        ValidationStatus.TIMED_OUT.value,
        ValidationStatus.BLOCKED.value,
        ValidationStatus.REQUIRES_APPROVAL.value,
    }:
        return CodingLoopStatus.VALIDATION_FAILED
    if iteration_status == CodingLoopStatus.COMPLETED:
        return CodingLoopStatus.COMPLETED
    return iteration_status


def _final_summary(
    iteration: CodingIteration,
    validation: CodingValidationSummary,
) -> str:
    if iteration.status == CodingLoopStatus.ROLLED_BACK:
        return "Validation failed and the checkpoint was restored."
    if validation.status == ValidationStatus.PASSED.value:
        return "Patch applied and validation passed."
    if validation.status == "not_run":
        return iteration.summary
    return validation.summary
