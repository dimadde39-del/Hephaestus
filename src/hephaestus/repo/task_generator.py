"""Repo-aware task generation for release-readiness planning."""

from __future__ import annotations

from hephaestus.repo.schemas import CommandRiskCategory, RepoProfile, RepoTask, TestCommand


def generate_repo_tasks(profile: RepoProfile) -> list[RepoTask]:
    """Generate optimizer-compatible repo tasks from a profile."""

    tasks: list[RepoTask] = [
        RepoTask(
            id="inspect_repo_structure",
            title="Inspect repo structure",
            description="Review detected manifests, config files, CI files, Docker files, and stack signals.",
            priority=9,
            dependencies=[],
            risk=0.04,
            expected_value=8.5,
            uncertainty=0.12,
            required_capabilities=["repository-inspection"],
            estimated_input_tokens=900,
            estimated_output_tokens=350,
            allowed_tools=["filesystem"],
            rationale="Repo profile was generated through read-only file inspection.",
        ),
        RepoTask(
            id="review_package_scripts",
            title="Review package scripts",
            description="Inspect detected scripts and classify safe validation versus risky side-effect commands.",
            priority=8,
            dependencies=["inspect_repo_structure"],
            risk=0.08,
            expected_value=8.0,
            uncertainty=0.18,
            required_capabilities=["repository-inspection", "safety"],
            estimated_input_tokens=850,
            estimated_output_tokens=350,
            allowed_tools=["filesystem"],
            rationale=f"{len(profile.scripts)} package scripts were classified.",
        ),
    ]

    if profile.ci_providers:
        tasks.append(
            RepoTask(
                id="inspect_ci",
                title="Inspect CI",
                description="Review detected CI configuration and compare it with local validation suggestions.",
                priority=7,
                dependencies=["inspect_repo_structure"],
                risk=0.06,
                expected_value=7.2,
                uncertainty=0.2,
                required_capabilities=["repository-inspection", "planning"],
                estimated_input_tokens=700,
                estimated_output_tokens=300,
                allowed_tools=["filesystem"],
                rationale=", ".join(provider.provider for provider in profile.ci_providers),
            )
        )
    else:
        tasks.append(
            RepoTask(
                id="inspect_ci",
                title="Inspect CI",
                description="Record that no CI provider was detected and local validation carries more weight.",
                priority=6,
                dependencies=["inspect_repo_structure"],
                risk=0.08,
                expected_value=6.5,
                uncertainty=0.28,
                required_capabilities=["repository-inspection", "planning"],
                estimated_input_tokens=500,
                estimated_output_tokens=250,
                allowed_tools=["filesystem"],
                rationale="No GitHub Actions or GitLab CI configuration was detected.",
            )
        )

    if profile.env_files_detected or profile.risk_signals:
        tasks.append(
            RepoTask(
                id="check_env_risks",
                title="Check environment risks",
                description="Account for environment files, secrets-adjacent commands, and release/deploy script risks.",
                priority=8,
                dependencies=["inspect_repo_structure", "review_package_scripts"],
                risk=0.32 if profile.env_files_detected else 0.22,
                expected_value=7.8,
                uncertainty=0.24,
                required_capabilities=["safety", "repository-inspection"],
                estimated_input_tokens=780,
                estimated_output_tokens=360,
                allowed_tools=["filesystem"],
                rationale=", ".join(signal.summary for signal in profile.risk_signals[:3]),
            )
        )

    validation_dependency = "review_package_scripts"
    lint_commands = _commands_for_kind(profile.validation_plan.commands, "lint")
    if lint_commands:
        tasks.append(_validation_task("run_lint", "Run lint", lint_commands, [validation_dependency]))
        validation_dependency = "run_lint"

    test_commands = _commands_for_kind(profile.validation_plan.commands, "test")
    if test_commands:
        tasks.append(_validation_task("run_tests", "Run tests", test_commands, [validation_dependency]))
        validation_dependency = "run_tests"

    build_commands = _commands_for_kind(profile.validation_plan.commands, "build")
    if build_commands:
        tasks.append(_validation_task("run_build", "Run build", build_commands, [validation_dependency]))
        validation_dependency = "run_build"

    if not lint_commands and not test_commands and not build_commands:
        tasks.append(
            RepoTask(
                id="identify_validation_commands",
                title="Identify validation commands",
                description="No safe validation command was detected; inspect docs and manifests before release.",
                priority=8,
                dependencies=["review_package_scripts"],
                risk=0.1,
                expected_value=7.4,
                uncertainty=0.35,
                required_capabilities=["repository-inspection", "planning"],
                estimated_input_tokens=700,
                estimated_output_tokens=300,
                allowed_tools=["filesystem"],
            )
        )
        validation_dependency = "identify_validation_commands"

    if _has_approval_worthy_risk(profile):
        tasks.append(
            RepoTask(
                id="gate_risky_commands",
                title="Gate risky commands",
                description="Require approval before any deploy, publish, destructive, secret-touching, or external side-effect command.",
                priority=10,
                dependencies=["review_package_scripts"],
                risk=0.68,
                expected_value=7.2,
                uncertainty=0.12,
                required_capabilities=["safety"],
                estimated_input_tokens=480,
                estimated_output_tokens=240,
                allowed_tools=[],
                requires_approval=True,
                command_classification=CommandRiskCategory.HIGH_RISK,
                rationale="Risky commands were detected and must remain approval-gated.",
            )
        )

    summary_dependencies = [validation_dependency, "inspect_ci"]
    if any(task.id == "check_env_risks" for task in tasks):
        summary_dependencies.append("check_env_risks")
    if any(task.id == "gate_risky_commands" for task in tasks):
        summary_dependencies.append("gate_risky_commands")
    tasks.append(
        RepoTask(
            id="prepare_release_summary",
            title="Prepare release summary",
            description="Summarize stack, validation plan, unresolved risks, and recommended next release-readiness steps.",
            priority=7,
            dependencies=list(dict.fromkeys(summary_dependencies)),
            risk=0.06,
            expected_value=8.8,
            uncertainty=0.16,
            required_capabilities=["analysis", "writing", "planning"],
            estimated_input_tokens=1_100,
            estimated_output_tokens=800,
            allowed_tools=[],
            rationale="Final task translates inspection and optimized validation order into a release-readiness narrative.",
        )
    )
    return tasks


def _validation_task(
    task_id: str,
    title: str,
    commands: list[TestCommand],
    dependencies: list[str],
) -> RepoTask:
    command_text = "; ".join(command.command for command in commands)
    max_risk = max((_risk_for_command(command) for command in commands), default=0.16)
    return RepoTask(
        id=task_id,
        title=title,
        description=f"Suggested validation command(s): {command_text}",
        priority=9 if task_id == "run_tests" else 8,
        dependencies=dependencies,
        risk=max_risk,
        expected_value=9.0 if task_id == "run_tests" else 8.2,
        uncertainty=0.28 if task_id == "run_tests" else 0.22,
        required_capabilities=["shell", "testing", "safety"],
        estimated_input_tokens=900,
        estimated_output_tokens=500,
        allowed_tools=["shell"],
        command=command_text,
        command_classification=CommandRiskCategory.SAFE_VALIDATION,
        rationale="Command is suggested only; Phase 4A does not execute repository validation.",
    )


def _commands_for_kind(commands: list[TestCommand], kind: str) -> list[TestCommand]:
    result: list[TestCommand] = []
    for command in commands:
        lowered = f"{command.command} {command.framework}".lower()
        matches_lint = kind == "lint" and any(
            keyword in lowered for keyword in ("lint", "ruff", "mypy", "eslint", "clippy", "fmt --check", "tsc")
        )
        matches_test = kind == "test" and any(
            keyword in lowered for keyword in ("test", "pytest", "vitest", "jest")
        )
        matches_build = kind == "build" and "build" in lowered
        if matches_lint or matches_test or matches_build:
            result.append(command)
    return result


def _risk_for_command(command: TestCommand) -> float:
    return {
        CommandRiskCategory.SAFE_READONLY: 0.05,
        CommandRiskCategory.SAFE_VALIDATION: 0.16,
        CommandRiskCategory.MEDIUM_RISK: 0.35,
        CommandRiskCategory.HIGH_RISK: 0.62,
        CommandRiskCategory.EXTERNAL_SIDE_EFFECT: 0.75,
        CommandRiskCategory.DESTRUCTIVE: 0.9,
    }[command.classification]


def _has_approval_worthy_risk(profile: RepoProfile) -> bool:
    risky_categories = {
        CommandRiskCategory.HIGH_RISK,
        CommandRiskCategory.EXTERNAL_SIDE_EFFECT,
        CommandRiskCategory.DESTRUCTIVE,
    }
    return any(signal.level in risky_categories for signal in profile.risk_signals) or any(
        script.classification in risky_categories for script in profile.scripts
    )
