"""Deterministic readiness analysis for repo-aware release planning."""

from __future__ import annotations

from hephaestus.benchmarks.schemas import BenchmarkResult
from hephaestus.release.schemas import (
    ReleaseReadinessSignal,
    ReleaseRecommendation,
    ReleaseRecommendationStatus,
    ReleaseRisk,
)
from hephaestus.repo.analysis import risk_summary
from hephaestus.repo.schemas import CommandRiskCategory, RepoProfile

READINESS_SCORE_DESCRIPTION = (
    "Release readiness is a deterministic planning-readiness score from 0 to 100. "
    "It uses coarse whole-number weights for detected validation, CI, safety gates, "
    "optimizer evidence, Pareto evidence, and QUBO evidence. It does not mean commands "
    "passed, because Phase 4B intentionally does not execute repository commands."
)


def build_readiness_signals(
    profile: RepoProfile,
    benchmark_result: BenchmarkResult,
    *,
    pareto_requested: bool,
    qubo_requested: bool,
) -> list[ReleaseReadinessSignal]:
    """Build coarse, deterministic readiness signals for a release planning run."""

    validation_commands = profile.validation_plan.command_texts
    test_commands = [command.command for command in profile.test_commands]
    build_commands = [command.command for command in profile.build_commands]
    lint_commands = [command.command for command in profile.lint_commands]
    approval_tasks = [task.id for task in profile.generated_tasks if task.requires_approval]
    high_risks = [
        signal.summary
        for signal in profile.risk_signals
        if signal.level
        in {
            CommandRiskCategory.HIGH_RISK,
            CommandRiskCategory.EXTERNAL_SIDE_EFFECT,
            CommandRiskCategory.DESTRUCTIVE,
        }
    ]
    pareto_ok = bool(benchmark_result.pareto_selections) and all(
        selection.valid_candidate_count > 0 for selection in benchmark_result.pareto_selections
    )
    qubo_ok = bool(benchmark_result.qubo_comparisons) and all(
        comparison.feasible for comparison in benchmark_result.qubo_comparisons
    )

    return [
        _signal(
            "repo_profile",
            "Repo profile confidence",
            profile.confidence >= 0.65,
            10,
            f"profile confidence {profile.confidence:.2f}",
            [profile.path],
        ),
        _signal(
            "validation_commands",
            "Validation commands detected",
            bool(validation_commands),
            15,
            "safe validation commands were detected" if validation_commands else "no safe validation commands detected",
            validation_commands,
        ),
        _signal(
            "test_commands",
            "Test command detected",
            bool(test_commands),
            10,
            "test command detected" if test_commands else "no test command detected",
            test_commands,
        ),
        _signal(
            "build_or_lint",
            "Build or lint command detected",
            bool(build_commands or lint_commands),
            10,
            "build/lint command detected" if build_commands or lint_commands else "no build or lint command detected",
            [*lint_commands, *build_commands],
        ),
        _signal(
            "ci",
            "CI detected",
            bool(profile.ci_providers),
            10,
            "CI configuration detected" if profile.ci_providers else "no CI provider detected",
            [path for provider in profile.ci_providers for path in provider.config_paths],
        ),
        _signal(
            "env_safety",
            "Environment-file posture",
            not profile.env_files_detected,
            5,
            "no env files detected"
            if not profile.env_files_detected
            else "env files detected by name only; contents were not inspected",
            profile.env_files_detected,
        ),
        _signal(
            "risk_posture",
            "High-risk script posture",
            not high_risks,
            15,
            "no high-risk release scripts detected"
            if not high_risks
            else "high-risk, destructive, or external side-effect scripts require review",
            high_risks,
        ),
        _signal(
            "approval_gates",
            "Approval gate posture",
            not approval_tasks,
            10,
            "no approval-gated release tasks"
            if not approval_tasks
            else "approval-gated actions are present and must not run automatically",
            approval_tasks,
        ),
        _signal(
            "optimizer",
            "Optimizer proof persisted",
            benchmark_result.run_id is not None and benchmark_result.scheduler.best_order != [],
            10,
            "optimizer run persisted" if benchmark_result.run_id else "optimizer run was not persisted",
            [benchmark_result.run_id or ""],
        ),
        _signal(
            "pareto",
            "Pareto feasibility",
            pareto_ok,
            5,
            "Pareto frontier generated with valid candidates"
            if pareto_ok
            else (
                "Pareto was requested but did not produce valid frontiers"
                if pareto_requested
                else "Pareto not requested for this run"
            ),
            [selection.frontier.id for selection in benchmark_result.pareto_selections],
        ),
        _signal(
            "qubo",
            "QUBO feasibility",
            qubo_ok,
            5,
            "QUBO formulations solved feasibly"
            if qubo_ok
            else (
                "QUBO was requested but did not produce feasible solutions"
                if qubo_requested
                else "QUBO not requested for this run"
            ),
            [comparison.problem_id for comparison in benchmark_result.qubo_comparisons],
        ),
    ]


def readiness_score(signals: list[ReleaseReadinessSignal]) -> int:
    """Return the deterministic whole-number readiness score."""

    return min(100, sum(signal.score for signal in signals))


def build_release_risks(profile: RepoProfile) -> list[ReleaseRisk]:
    """Convert repo risk signals and approval-gated tasks into release risks."""

    risks = [
        ReleaseRisk(
            level=signal.level,
            category=signal.category,
            summary=signal.summary,
            evidence=signal.evidence,
            mitigation=signal.mitigation,
            requires_approval=signal.level
            in {
                CommandRiskCategory.HIGH_RISK,
                CommandRiskCategory.EXTERNAL_SIDE_EFFECT,
                CommandRiskCategory.DESTRUCTIVE,
            },
        )
        for signal in profile.risk_signals
    ]
    for task in profile.generated_tasks:
        if task.requires_approval:
            risks.append(
                ReleaseRisk(
                    level=task.command_classification or CommandRiskCategory.HIGH_RISK,
                    category="approval",
                    summary=f"Task {task.id} requires approval before execution.",
                    evidence=[task.command] if task.command else [task.description],
                    mitigation="Keep the task in planning mode until explicit approval exists.",
                    requires_approval=True,
                )
            )
    return risks


def generate_release_recommendation(
    profile: RepoProfile,
    benchmark_result: BenchmarkResult,
    signals: list[ReleaseReadinessSignal],
    *,
    evaluated: bool,
) -> ReleaseRecommendation:
    """Generate an honest recommendation from deterministic release signals."""

    score = readiness_score(signals)
    risks = build_release_risks(profile)
    validation_commands = profile.validation_plan.command_texts
    high_or_external_risks = [
        risk
        for risk in risks
        if risk.level
        in {
            CommandRiskCategory.HIGH_RISK,
            CommandRiskCategory.EXTERNAL_SIDE_EFFECT,
            CommandRiskCategory.DESTRUCTIVE,
        }
    ]
    has_test = bool(profile.test_commands)
    has_build_or_lint = bool(profile.build_commands or profile.lint_commands)
    has_ci = bool(profile.ci_providers)
    pareto_missing = not benchmark_result.pareto_selections
    qubo_missing = not benchmark_result.qubo_comparisons

    why = _recommendation_reasons(
        profile,
        benchmark_result,
        evaluated=evaluated,
    )
    next_steps = [
        "Review the generated task order before approving any execution.",
        "Run validation commands manually or in a future approved execution phase.",
        "Inspect approval-gated release or deploy scripts before any side effects.",
    ]

    if not profile.detected_languages and not profile.package_managers:
        return ReleaseRecommendation(
            status=ReleaseRecommendationStatus.UNKNOWN,
            summary="Hephaestus could not infer enough repository structure to recommend a release path.",
            why=why,
            next_steps=["Add or inspect project manifests before release planning."],
            risks=risks,
        )

    if not validation_commands and high_or_external_risks:
        return ReleaseRecommendation(
            status=ReleaseRecommendationStatus.BLOCKED,
            summary="Release planning is blocked until validation evidence and risky commands are reviewed.",
            why=why,
            next_steps=[
                "Identify safe validation commands.",
                "Review risky scripts and keep them approval-gated.",
            ],
            risks=risks,
        )

    if (
        score >= 85
        and validation_commands
        and has_test
        and has_build_or_lint
        and has_ci
        and not high_or_external_risks
        and not profile.env_files_detected
        and not pareto_missing
        and not qubo_missing
    ):
        return ReleaseRecommendation(
            status=ReleaseRecommendationStatus.MOSTLY_READY,
            summary=(
                "The release plan has strong planning evidence, but commands were not executed "
                "in Phase 4B."
            ),
            why=why,
            next_steps=next_steps,
            risks=risks,
        )

    if validation_commands:
        return ReleaseRecommendation(
            status=ReleaseRecommendationStatus.NEEDS_VALIDATION,
            summary=(
                "Hephaestus found a plausible release-readiness path, but validation has not "
                "been executed yet."
            ),
            why=why,
            next_steps=next_steps,
            risks=risks,
        )

    return ReleaseRecommendation(
        status=ReleaseRecommendationStatus.UNKNOWN,
        summary="Hephaestus needs stronger validation signals before release planning is meaningful.",
        why=why,
        next_steps=[
            "Identify test, lint, or build commands.",
            "Add CI or document manual validation expectations.",
        ],
        risks=risks,
    )


def release_risk_summary(profile: RepoProfile) -> str:
    """Return a compact release risk summary."""

    return risk_summary(profile)


def _signal(
    signal_id: str,
    label: str,
    present: bool,
    weight: int,
    rationale: str,
    evidence: list[str],
) -> ReleaseReadinessSignal:
    return ReleaseReadinessSignal(
        id=signal_id,
        label=label,
        present=present,
        weight=weight,
        score=weight if present else 0,
        rationale=rationale,
        evidence=evidence,
    )


def _recommendation_reasons(
    profile: RepoProfile,
    benchmark_result: BenchmarkResult,
    *,
    evaluated: bool,
) -> list[str]:
    reasons: list[str] = []
    if profile.validation_plan.command_texts:
        reasons.append("lint/build/test commands were detected but not executed.")
    else:
        reasons.append("no safe validation commands were detected.")
    if profile.env_files_detected:
        reasons.append("env files were detected by name; contents were not inspected.")
    if profile.ci_providers:
        reasons.append("CI configuration was detected.")
    else:
        reasons.append("no CI provider was detected.")
    if profile.test_commands:
        reasons.append("test command detected.")
    else:
        reasons.append("no test command found.")
    approval_tasks = [task.id for task in profile.generated_tasks if task.requires_approval]
    if approval_tasks:
        reasons.append("publish/deploy/destructive scripts require approval before execution.")
    if benchmark_result.pareto_selections:
        reasons.append(f"Pareto compared {len(benchmark_result.pareto_selections)} decision frontier(s).")
    if benchmark_result.qubo_comparisons:
        feasible = sum(1 for comparison in benchmark_result.qubo_comparisons if comparison.feasible)
        reasons.append(
            f"QUBO formulated {len(benchmark_result.qubo_comparisons)} problem(s), {feasible} feasible."
        )
    if evaluated:
        reasons.append("simulated outcomes and learning signals were generated from decision traces.")
    else:
        reasons.append("outcome evaluation was skipped for this run.")
    return reasons
