"""End-to-end repo-aware release planning orchestration."""

from __future__ import annotations

from pathlib import Path

from hephaestus.benchmarks import run_benchmark
from hephaestus.decision import DecisionTraceRepository
from hephaestus.outcomes import OutcomeRepository, reflect_run_outcomes
from hephaestus.release.analysis import (
    build_readiness_signals,
    generate_release_recommendation,
    readiness_score,
    release_risk_summary,
)
from hephaestus.release.planner import (
    build_release_benchmark_case,
    build_release_task_plan,
    ensure_release_tasks,
)
from hephaestus.release.repository import ReleasePlanRepository
from hephaestus.release.schemas import (
    ReleaseDemoRun,
    ReleasePlanningRequest,
    ReleasePlanningResult,
)
from hephaestus.repo import RepoProfile, RepoProfileRepository, inspect_repository
from hephaestus.storage import RunRepository
from hephaestus.validation import ValidationExecutor
from hephaestus.validation.analysis import adjusted_readiness_score
from hephaestus.validation.repository import ValidationRepository


class ReleasePlanningError(Exception):
    """Raised when release planning cannot proceed."""


class ReleasePlanningOrchestrator:
    """Compose repo intelligence, optimization, explanation, and learning."""

    def __init__(self, database_path: Path | str | None = None) -> None:
        self.release_repository = ReleasePlanRepository(database_path)
        self.database_path = self.release_repository.database_path
        self.repo_repository = RepoProfileRepository(self.database_path)
        self.run_repository = RunRepository(self.database_path)
        self.trace_repository = DecisionTraceRepository(self.database_path)
        self.outcome_repository = OutcomeRepository(self.database_path)
        self.validation_repository = ValidationRepository(self.database_path)

    def plan(self, request: ReleasePlanningRequest) -> ReleaseDemoRun:
        """Run the complete release planning flow and persist the result."""

        profile = self._resolve_profile(request)
        profile = ensure_release_tasks(profile)
        self.repo_repository.save_profile(profile)
        case = build_release_benchmark_case(profile, request.goal)
        benchmark_result = run_benchmark(
            case,
            repository=self.run_repository,
            pareto=request.pareto,
            pareto_preference=request.preference,
            qubo=request.qubo,
            run_mode="release",
            run_label="Release plan",
        )
        if benchmark_result.run_id is None:
            raise ReleasePlanningError("Release planning did not persist an optimizer run.")

        if request.evaluate:
            reflect_run_outcomes(
                benchmark_result.run_id,
                repository=self.outcome_repository,
                trace_repository=self.trace_repository,
            )

        traces = self.trace_repository.list_traces(run_id=benchmark_result.run_id)
        outcomes = self.outcome_repository.list_outcomes_by_run(benchmark_result.run_id)
        learning_signals = self.outcome_repository.list_learning_signals(
            run_id=benchmark_result.run_id
        )
        signals = build_readiness_signals(
            profile,
            benchmark_result,
            pareto_requested=request.pareto,
            qubo_requested=request.qubo,
        )
        recommendation = generate_release_recommendation(
            profile,
            benchmark_result,
            signals,
            evaluated=request.evaluate,
        )
        base_readiness_score = readiness_score(signals)
        plan_result = ReleasePlanningResult(
            repo_profile_id=profile.id,
            goal=request.goal,
            generated_tasks=profile.generated_tasks,
            validation_plan=profile.validation_plan,
            risk_summary=release_risk_summary(profile),
            optimizer_run_id=benchmark_result.run_id,
            pareto_frontier_ids=[
                selection.frontier.id for selection in benchmark_result.pareto_selections
            ],
            qubo_problem_ids=[
                comparison.problem_id for comparison in benchmark_result.qubo_comparisons
            ],
            decision_trace_ids=[trace.id for trace in traces],
            outcome_ids=[outcome.id for outcome in outcomes],
            learning_signal_ids=[signal.id for signal in learning_signals],
            evidence_mode=(
                "simulated_outcome_evaluation"
                if request.evaluate
                else "no_validation_evidence"
            ),
            readiness_score=base_readiness_score,
            recommendation=recommendation,
            readiness_signals=signals,
            task_plan=build_release_task_plan(
                profile,
                optimized_task_order=benchmark_result.scheduler.best_order,
            ),
        )
        self.release_repository.save_release_plan(plan_result)

        if request.with_validation:
            validation_suite = ValidationExecutor(
                self.database_path,
                workspace_path=profile.path,
            ).run(
                profile.path,
                release_plan_id=plan_result.id,
                dry_run=False,
                yes=request.validation_yes,
                readiness_score_before=base_readiness_score,
            )
            validation_summary = self.validation_repository.latest_release_summary(
                release_plan_id=plan_result.id
            )
            if validation_summary is None:
                validation_summary = self.validation_repository.latest_release_summary(
                    validation_result_id=validation_suite.id
                )
            signals = build_readiness_signals(
                profile,
                benchmark_result,
                pareto_requested=request.pareto,
                qubo_requested=request.qubo,
                validation_summary=validation_summary,
            )
            validation_score = (
                validation_summary.readiness_score_after
                if validation_summary is not None
                and validation_summary.readiness_score_after is not None
                else adjusted_readiness_score(base_readiness_score, validation_suite)
            )
            recommendation = generate_release_recommendation(
                profile,
                benchmark_result,
                signals,
                evaluated=request.evaluate,
                validation_summary=validation_summary,
            )
            plan_result = plan_result.model_copy(
                update={
                    "validation_result_id": validation_suite.id,
                    "validation_summary": validation_summary,
                    "evidence_mode": validation_suite.evidence_mode,
                    "readiness_score": validation_score,
                    "recommendation": recommendation,
                    "readiness_signals": signals,
                    "outcome_ids": [
                        *plan_result.outcome_ids,
                        *validation_suite.outcome_ids,
                    ],
                    "learning_signal_ids": [
                        *plan_result.learning_signal_ids,
                        *validation_suite.learning_signal_ids,
                    ],
                    "decision_trace_ids": [
                        *plan_result.decision_trace_ids,
                        *validation_suite.decision_trace_ids,
                    ],
                }
            )
        self.release_repository.save_release_plan(plan_result)
        return ReleaseDemoRun(
            request=request,
            repo_profile=profile,
            result=plan_result,
            benchmark_result=benchmark_result,
        )

    def _resolve_profile(self, request: ReleasePlanningRequest) -> RepoProfile:
        if request.profile_id is not None:
            profile = self.repo_repository.get_profile(request.profile_id)
            if profile is None:
                raise ReleasePlanningError(f"Repo profile not found: {request.profile_id}")
            return profile

        path = Path(request.path).resolve()
        if request.use_latest_profile:
            latest = self.repo_repository.latest_profile_for_path(path)
            if latest is not None:
                return latest

        try:
            report = inspect_repository(path)
        except (FileNotFoundError, NotADirectoryError) as error:
            raise ReleasePlanningError(str(error)) from error
        self.repo_repository.save_inspection(report)
        return report.profile
