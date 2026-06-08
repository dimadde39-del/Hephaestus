"""Rich renderers for repository intelligence."""

from __future__ import annotations

from rich.console import Group
from rich.panel import Panel
from rich.table import Table

from hephaestus.repo.analysis import repo_stack_summary, risk_summary, validation_summary
from hephaestus.repo.schemas import RepoInspectionReport, RepoProfile
from hephaestus.spec.tasks import Task


def build_repo_inspection_renderable(report: RepoInspectionReport) -> Group:
    """Render a complete repository inspection report."""

    profile = report.profile
    return Group(
        Panel(
            "\n".join(
                [
                    f"Profile ID: {profile.id}",
                    f"Path: {profile.path}",
                    f"Confidence: {profile.confidence:.2f}",
                    "",
                    "Hephaestus does not jump straight from prompt to action.",
                    "It first inspects the repository, builds a project profile, generates repo-aware tasks, and then lets the decision engine optimize the plan.",
                ]
            ),
            title=f"Repository: {profile.name}",
        ),
        build_repo_stack_table(profile),
        build_script_table(profile),
        build_validation_table(profile),
        build_risk_table(profile),
        build_repo_tasks_table(profile),
    )


def build_repo_profile_list_table(profiles: list[RepoProfile]) -> Table:
    """Render persisted repo profiles."""

    table = Table(title="Repo Profiles")
    table.add_column("ID", no_wrap=True)
    table.add_column("Name")
    table.add_column("Stack")
    table.add_column("Validation")
    table.add_column("Risks")
    table.add_column("Inspected")
    for profile in profiles:
        table.add_row(
            profile.id,
            profile.name,
            repo_stack_summary(profile),
            validation_summary(profile),
            risk_summary(profile),
            profile.inspected_at.isoformat(timespec="seconds"),
        )
    return table


def build_repo_show_renderable(profile: RepoProfile) -> Group:
    """Render one persisted repo profile."""

    return Group(
        Panel(
            "\n".join(
                [
                    f"ID: {profile.id}",
                    f"Path: {profile.path}",
                    f"Inspected: {profile.inspected_at.isoformat(timespec='seconds')}",
                    f"Confidence: {profile.confidence:.2f}",
                ]
            ),
            title=f"Repo Profile: {profile.name}",
        ),
        build_repo_stack_table(profile),
        build_script_table(profile),
        build_validation_table(profile),
        build_risk_table(profile),
    )


def build_repo_stack_table(profile: RepoProfile) -> Table:
    """Render detected stack information."""

    table = Table(title="Detected Stack")
    table.add_column("Signal")
    table.add_column("Value")
    table.add_row("Languages", ", ".join(profile.detected_languages) or "-")
    table.add_row("Frameworks", ", ".join(profile.detected_frameworks) or "-")
    table.add_row(
        "Package managers",
        ", ".join(f"{manager.ecosystem}:{manager.name}" for manager in profile.package_managers)
        or "-",
    )
    table.add_row(
        "CI",
        ", ".join(provider.provider for provider in profile.ci_providers) or "-",
    )
    table.add_row("Docker", "yes" if profile.docker_detected else "no")
    table.add_row("Env files", ", ".join(profile.env_files_detected) or "-")
    return table


def build_script_table(profile: RepoProfile) -> Table:
    """Render detected scripts and risk classifications."""

    table = Table(title="Package Scripts")
    table.add_column("Name")
    table.add_column("Suggested")
    table.add_column("Raw")
    table.add_column("Risk")
    table.add_column("Approval")
    scripts = profile.scripts[:18]
    for script in scripts:
        table.add_row(
            script.name,
            script.command,
            script.raw_command or "-",
            script.classification.value,
            "yes" if script.requires_approval else "no",
        )
    if len(profile.scripts) > len(scripts):
        table.add_row("...", f"+{len(profile.scripts) - len(scripts)} more", "-", "-", "-")
    if not profile.scripts:
        table.add_row("-", "-", "-", "-", "-")
    return table


def build_validation_table(profile: RepoProfile) -> Table:
    """Render suggested validation sequence."""

    table = Table(title="Validation Plan")
    table.add_column("Order", justify="right")
    table.add_column("Command")
    table.add_column("Source")
    table.add_column("Risk")
    table.add_column("Approval")
    for index, command in enumerate(profile.validation_plan.commands, start=1):
        table.add_row(
            str(index),
            command.command,
            command.source,
            command.classification.value,
            "yes" if command.requires_approval else "no",
        )
    if not profile.validation_plan.commands:
        table.add_row("-", "No safe validation commands detected.", "-", "-", "-")
    return table


def build_risk_table(profile: RepoProfile) -> Table:
    """Render repo risk signals."""

    table = Table(title="Risk Signals")
    table.add_column("Level")
    table.add_column("Category")
    table.add_column("Summary")
    table.add_column("Evidence")
    for signal in profile.risk_signals:
        table.add_row(
            signal.level.value,
            signal.category,
            signal.summary,
            ", ".join(signal.evidence[:3]) or "-",
        )
    if not profile.risk_signals:
        table.add_row("-", "-", "No repo risk signals detected.", "-")
    return table


def build_repo_tasks_table(profile: RepoProfile) -> Table:
    """Render generated repo-aware tasks."""

    table = Table(title="Generated Repo Tasks")
    table.add_column("Task", no_wrap=True)
    table.add_column("Priority", justify="right")
    table.add_column("Risk", justify="right")
    table.add_column("Deps")
    table.add_column("Approval")
    table.add_column("Command")
    for task in profile.generated_tasks:
        table.add_row(
            task.id,
            str(task.priority),
            f"{task.risk:.2f}",
            ", ".join(task.dependencies) or "-",
            "yes" if task.requires_approval else "no",
            task.command or "-",
        )
    return table


def build_repo_plan_renderable(
    profile: RepoProfile,
    ordered_tasks: list[Task],
    explanation: str,
) -> Group:
    """Render an optimization-ready repo task graph."""

    table = Table(title="Repo-Aware Optimized Task Graph")
    table.add_column("Order", justify="right")
    table.add_column("Task", no_wrap=True)
    table.add_column("Priority", justify="right")
    table.add_column("Risk", justify="right")
    table.add_column("Deps")
    table.add_column("Approval")
    for index, task in enumerate(ordered_tasks, start=1):
        table.add_row(
            str(index),
            task.id,
            str(task.priority),
            f"{task.risk:.2f}",
            ", ".join(task.dependencies) or "-",
            "yes" if task.requires_approval else "no",
        )
    approval_notes = [
        f"{task.id}: approval required before {task.description}"
        for task in ordered_tasks
        if task.requires_approval
    ]
    return Group(
        Panel(
            "\n".join(
                [
                    f"Profile: {profile.id}",
                    f"Validation: {validation_summary(profile)}",
                    "Future phases will execute safely only after explicit policy and approval checks.",
                ]
            ),
            title=f"Repo Plan: {profile.name}",
        ),
        table,
        Panel(
            "\n".join(approval_notes) or "No approval-gated tasks in this plan.",
            title="Approval Notes",
        ),
        Panel(explanation, title="Optimizer"),
    )
