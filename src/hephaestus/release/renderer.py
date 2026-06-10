"""Rich renderers for release planning results."""

from __future__ import annotations

from rich.console import Group
from rich.panel import Panel
from rich.table import Table

from hephaestus.release.analysis import READINESS_SCORE_DESCRIPTION
from hephaestus.release.schemas import ReleaseDemoRun, ReleasePlanningResult


def build_release_demo_renderable(demo: ReleaseDemoRun) -> Group:
    """Render a freshly generated release planning demo run."""

    return Group(
        _summary_panel(demo.result, repo_path=demo.repo_profile.path),
        _flow_table(demo.result),
        build_readiness_table(demo.result),
        build_release_tasks_table(demo.result),
        build_recommendation_panel(demo.result),
        build_release_links_panel(demo.result),
    )


def build_release_show_renderable(plan: ReleasePlanningResult) -> Group:
    """Render a persisted release plan."""

    return Group(
        _summary_panel(plan),
        _flow_table(plan),
        build_readiness_table(plan),
        build_release_tasks_table(plan),
        build_recommendation_panel(plan),
        build_release_links_panel(plan),
    )


def build_release_list_table(plans: list[ReleasePlanningResult]) -> Table:
    """Render recent release planning results."""

    table = Table(title="Release Plans")
    table.add_column("ID", no_wrap=True)
    table.add_column("Status")
    table.add_column("Score", justify="right")
    table.add_column("Optimizer Run", no_wrap=True)
    for plan in plans:
        table.add_row(
            plan.id,
            plan.recommendation.status.value,
            f"{plan.readiness_score}/100",
            plan.optimizer_run_id,
        )
    if not plans:
        table.add_row("-", "-", "-", "-")
    return table


def build_readiness_table(plan: ReleasePlanningResult) -> Table:
    """Render deterministic readiness score inputs."""

    table = Table(title="Readiness Signals")
    table.add_column("Signal")
    table.add_column("Present")
    table.add_column("Score", justify="right")
    table.add_column("Why")
    table.add_column("Evidence")
    for signal in plan.readiness_signals:
        table.add_row(
            signal.label,
            "yes" if signal.present else "no",
            f"{signal.score}/{signal.weight}",
            signal.rationale,
            ", ".join(signal.evidence[:3]) or "-",
        )
    if not plan.readiness_signals:
        table.add_row("-", "-", "-", "No readiness signals recorded.", "-")
    return table


def build_release_tasks_table(plan: ReleasePlanningResult) -> Table:
    """Render generated and optimized release tasks."""

    table = Table(title="Release Task Plan")
    table.add_column("Task", no_wrap=True)
    table.add_column("Priority", justify="right")
    table.add_column("Risk", justify="right")
    table.add_column("Approval")
    table.add_column("Command")
    order = plan.task_plan.optimized_task_order if plan.task_plan is not None else []
    order_positions = {task_id: index for index, task_id in enumerate(order, start=1)}
    tasks = sorted(
        plan.generated_tasks,
        key=lambda task: (order_positions.get(task.id, 999), task.id),
    )
    for task in tasks:
        task_label = (
            f"{order_positions[task.id]}. {task.id}" if task.id in order_positions else task.id
        )
        table.add_row(
            task_label,
            str(task.priority),
            f"{task.risk:.2f}",
            "yes" if task.requires_approval else "no",
            task.command or "-",
        )
    if not tasks:
        table.add_row("-", "-", "-", "-", "-")
    return table


def build_recommendation_panel(plan: ReleasePlanningResult) -> Panel:
    """Render final recommendation and rationale."""

    lines = [
        f"Recommendation: {plan.recommendation.status.value}",
        "",
        plan.recommendation.summary,
        "",
        "Why:",
        *[f"- {reason}" for reason in plan.recommendation.why],
    ]
    if plan.recommendation.next_steps:
        lines.extend(["", "Next:", *[f"- {step}" for step in plan.recommendation.next_steps]])
    return Panel("\n".join(lines), title="Release Recommendation")


def build_release_links_panel(plan: ReleasePlanningResult) -> Panel:
    """Render commands that inspect linked artifacts."""

    lines = [
        f"View release plan: heph release show {plan.id}",
        f"View repo tasks: heph repo tasks {plan.repo_profile_id}",
        f"Inspect optimizer run: heph run show {plan.optimizer_run_id}",
        f"Inspect decision trace: heph explain {plan.optimizer_run_id}",
    ]
    if plan.pareto_frontier_ids:
        lines.append(f"View Pareto: heph pareto show {plan.pareto_frontier_ids[0]}")
    if plan.qubo_problem_ids:
        lines.append(f"View QUBO: heph qubo show {plan.qubo_problem_ids[0]}")
    if plan.outcome_ids:
        lines.append(f"View outcomes: heph outcome list --run {plan.optimizer_run_id}")
    if plan.learning_signal_ids:
        lines.append(f"View learning signals: heph learn signals --run {plan.optimizer_run_id}")
    if plan.validation_result_id:
        lines.append(f"View validation: heph validate show {plan.validation_result_id}")
    return Panel("\n".join(lines), title="Linked Artifacts")


def _summary_panel(plan: ReleasePlanningResult, *, repo_path: str = "") -> Panel:
    lines = [
        f"Release plan: {plan.id}",
        f"Repo profile: {plan.repo_profile_id}",
        *( [f"Repo path: {repo_path}"] if repo_path else [] ),
        f"Optimizer run: {plan.optimizer_run_id}",
        f"Readiness score: {plan.readiness_score}/100",
        f"Recommendation: {plan.recommendation.status.value}",
        f"Evidence mode: {plan.evidence_mode}",
        "",
        READINESS_SCORE_DESCRIPTION,
    ]
    if plan.validation_summary is not None:
        lines.extend(
            [
                "",
                f"Validation result: {plan.validation_summary.validation_result_id}",
                f"Validation status: {plan.validation_summary.status.value}",
                f"Readiness delta: {plan.validation_summary.readiness_score_delta:+d}",
            ]
        )
    return Panel("\n".join(lines), title="Repo-Aware Release Planning")


def _flow_table(plan: ReleasePlanningResult) -> Table:
    table = Table(title="Demo Flow")
    table.add_column("Stage")
    table.add_column("Artifact")
    table.add_column("Count", justify="right")
    table.add_row("Repo Inspect", plan.repo_profile_id, "1")
    table.add_row("Repo Plan", "generated release tasks", str(len(plan.generated_tasks)))
    table.add_row("Optimize", plan.optimizer_run_id, "1")
    table.add_row("Pareto", ", ".join(plan.pareto_frontier_ids[:2]) or "-", str(len(plan.pareto_frontier_ids)))
    table.add_row("QUBO", ", ".join(plan.qubo_problem_ids[:2]) or "-", str(len(plan.qubo_problem_ids)))
    table.add_row("Validate", plan.validation_result_id or "-", "1" if plan.validation_result_id else "0")
    table.add_row("Explain", ", ".join(plan.decision_trace_ids[:2]) or "-", str(len(plan.decision_trace_ids)))
    table.add_row("Evaluate", ", ".join(plan.outcome_ids[:2]) or "-", str(len(plan.outcome_ids)))
    table.add_row(
        "Learn",
        ", ".join(plan.learning_signal_ids[:2]) or "-",
        str(len(plan.learning_signal_ids)),
    )
    return table
