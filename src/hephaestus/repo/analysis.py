"""Analysis helpers for repository profiles and optimizer integration."""

from __future__ import annotations

import re

from hephaestus.benchmarks.schemas import BenchmarkCase
from hephaestus.optimize.context_packer import ContextCandidate
from hephaestus.optimize.token_firewall import TokenBudget
from hephaestus.repo.detectors import DetectionResult
from hephaestus.repo.schemas import (
    CommandRiskCategory,
    ProjectStack,
    RepoProfile,
    TestCommand,
    ValidationPlan,
)
from hephaestus.spec.tasks import Task


def build_project_stack(detection: DetectionResult) -> ProjectStack:
    """Build a high-level stack summary from raw detector output."""

    ecosystems = [manager.ecosystem for manager in detection.package_managers]
    tools = [
        *detection.tools,
        *[manager.name for manager in detection.package_managers],
        *(["Docker"] if detection.docker_detected else []),
        *[provider.provider for provider in detection.ci_providers],
    ]
    return ProjectStack(
        languages=detection.languages,
        frameworks=detection.frameworks,
        tools=tools,
        primary_ecosystems=list(dict.fromkeys(ecosystems)),
        confidence=profile_confidence(detection),
    )


def build_validation_plan(detection: DetectionResult) -> ValidationPlan:
    """Create an ordered validation command plan from detected signals."""

    commands: list[TestCommand] = []
    languages = set(detection.languages)
    if "Python" in languages or "Rust" in languages:
        commands.extend(_safe_commands(detection.lint_commands))
        commands.extend(_safe_commands(detection.test_commands))
    elif "Go" in languages:
        commands.extend(_safe_commands(detection.test_commands))
        commands.extend(_safe_commands(detection.build_commands))
    else:
        commands.extend(_safe_commands(detection.lint_commands))
        commands.extend(_safe_commands(detection.test_commands))
        commands.extend(_safe_commands(detection.build_commands))

    if "JavaScript" in languages or "TypeScript" in languages:
        node_commands = [
            *_safe_commands(detection.lint_commands),
            *_safe_commands(detection.test_commands),
            *_safe_commands(detection.build_commands),
        ]
        commands = _dedupe_commands([*commands, *node_commands])
    else:
        commands = _dedupe_commands(commands)

    notes: list[str] = []
    if not commands:
        notes.append("No safe validation commands were detected.")
    if detection.risk_signals:
        notes.append("Risk signals should be reviewed before moving from suggestion to execution.")
    if detection.env_files_detected:
        notes.append("Environment file names were detected; contents were not inspected.")

    return ValidationPlan(
        commands=commands,
        notes=notes,
        confidence=min(0.95, 0.45 + 0.12 * len(commands) + 0.08 * len(detection.package_managers)),
    )


def profile_confidence(detection: DetectionResult) -> float:
    """Return a coarse confidence score for a repo profile."""

    score = 0.25
    if detection.file_signals:
        score += min(0.25, len(detection.file_signals) * 0.025)
    if detection.package_managers:
        score += 0.2
    if detection.languages:
        score += 0.15
    if detection.test_commands or detection.lint_commands or detection.build_commands:
        score += 0.1
    if detection.ci_providers:
        score += 0.05
    return min(0.98, score)


def repo_tasks_to_optimizer_tasks(profile: RepoProfile) -> list[Task]:
    """Convert generated repo tasks into optimizer-ready tasks."""

    return [task.to_task() for task in profile.generated_tasks]


def repo_profile_to_benchmark_case(profile: RepoProfile) -> BenchmarkCase:
    """Convert a repo profile into the current benchmark fixture schema."""

    tasks = repo_tasks_to_optimizer_tasks(profile)
    context_candidates = _context_candidates(profile)
    return BenchmarkCase(
        id=f"repo_{_slug(profile.name)}",
        title=f"{profile.name} Repo Release Readiness",
        description=(
            "Repo-aware benchmark exported from read-only repository intelligence. "
            "The fixture optimizes release-readiness tasks without executing repository commands."
        ),
        goal=f"Prepare {profile.name} for release using repo-aware validation and risk gates.",
        tasks=tasks,
        context_candidates=context_candidates,
        context_token_budget=1_800,
        token_budget=TokenBudget(
            max_input_tokens=14_000,
            max_output_tokens=4_000,
            max_cost=0.25,
            quality_threshold=0.78,
        ),
        quality_threshold=0.78,
        expected_constraints=[
            "Do not execute repo commands during inspection.",
            "Prioritize safe validation commands before release summary.",
            "Approval-gate risky scripts, deploys, publishes, and environment-file access.",
        ],
        notes=[
            "Generated by heph repo export-benchmark.",
            "Repo commands are suggestions for future execution phases.",
        ],
        tags=[
            "repo-intelligence",
            "release-readiness",
            *_slug_list(profile.detected_languages),
            *_slug_list(profile.detected_frameworks),
        ],
    )


def repo_stack_summary(profile: RepoProfile) -> str:
    """Build a compact stack summary string for persistence and CLI tables."""

    languages = ", ".join(profile.detected_languages) or "unknown languages"
    frameworks = ", ".join(profile.detected_frameworks) or "no framework detected"
    managers = ", ".join(
        f"{manager.ecosystem}:{manager.name}" for manager in profile.package_managers
    ) or "no package manager"
    return f"{languages}; {frameworks}; {managers}"


def validation_summary(profile: RepoProfile) -> str:
    """Build a compact validation plan summary."""

    return " -> ".join(profile.validation_plan.command_texts) or "no validation commands detected"


def risk_summary(profile: RepoProfile) -> str:
    """Build a compact risk summary."""

    if not profile.risk_signals:
        return "no repo risk signals detected"
    counts: dict[str, int] = {}
    for signal in profile.risk_signals:
        counts[signal.level.value] = counts.get(signal.level.value, 0) + 1
    return ", ".join(f"{level}: {count}" for level, count in sorted(counts.items()))


def inspection_summary(profile: RepoProfile) -> str:
    """Build human-readable report summary text."""

    return "\n".join(
        [
            f"Repository: {profile.name}",
            f"Path: {profile.path}",
            f"Stack: {repo_stack_summary(profile)}",
            f"Validation: {validation_summary(profile)}",
            f"Risks: {risk_summary(profile)}",
            f"Generated tasks: {len(profile.generated_tasks)}",
        ]
    )


def _safe_commands(commands: list[TestCommand]) -> list[TestCommand]:
    return [
        command
        for command in commands
        if command.classification
        in {CommandRiskCategory.SAFE_VALIDATION, CommandRiskCategory.SAFE_READONLY}
        and not command.requires_approval
    ]


def _dedupe_commands(commands: list[TestCommand]) -> list[TestCommand]:
    seen: set[str] = set()
    deduped: list[TestCommand] = []
    for command in commands:
        if command.command in seen:
            continue
        seen.add(command.command)
        deduped.append(command)
    return deduped


def _context_candidates(profile: RepoProfile) -> list[ContextCandidate]:
    risk_content = "; ".join(signal.summary for signal in profile.risk_signals[:6])
    validation_content = "; ".join(profile.validation_plan.command_texts)
    stack_content = repo_stack_summary(profile)
    candidates = [
        ContextCandidate(
            id="repo-stack-profile",
            content=stack_content,
            relevance=0.94,
            importance=0.9,
            token_cost=260,
            critical=True,
            metadata={"repo_name": profile.name},
        ),
        ContextCandidate(
            id="repo-validation-plan",
            content=validation_content or "No safe validation commands detected.",
            relevance=0.92,
            importance=0.88,
            token_cost=320,
            critical=True,
            metadata={"validation_commands": profile.validation_plan.command_texts},
        ),
        ContextCandidate(
            id="repo-risk-signals",
            content=risk_content or "No repo risk signals detected.",
            relevance=0.88,
            importance=0.86 if profile.risk_signals else 0.55,
            token_cost=360,
            critical=bool(profile.risk_signals),
            metadata={"risk_count": len(profile.risk_signals)},
        ),
        ContextCandidate(
            id="repo-intelligence-principle",
            content=(
                "Hephaestus does not jump straight from prompt to action. "
                "It inspects, profiles, generates tasks, and optimizes before execution."
            ),
            relevance=0.86,
            importance=0.9,
            token_cost=260,
            critical=True,
        ),
    ]
    if len(profile.file_signals) > 8:
        candidates.append(
            ContextCandidate(
                id="repo-file-signal-summary",
                content=", ".join(signal.path for signal in profile.file_signals[:20]),
                relevance=0.68,
                importance=0.52,
                token_cost=420,
                critical=False,
            )
        )
    return candidates


def _slug(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return normalized or "repository"


def _slug_list(values: list[str]) -> list[str]:
    return [_slug(value) for value in values if value]
