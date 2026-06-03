"""Hephaestus CLI."""

from __future__ import annotations

import os
import platform
import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from hephaestus import __version__
from hephaestus.benchmarks import load_all_benchmarks, load_benchmark, run_benchmark
from hephaestus.benchmarks.reporter import (
    print_benchmark_list,
    print_benchmark_result,
    print_benchmark_show,
    results_to_json,
)
from hephaestus.core.config import DEFAULT_CONFIG, PrivacyLevel, RiskLevel
from hephaestus.memory import MemoryItem, MemoryType
from hephaestus.models import DeepSeekProvider, ModelProfile, fake_model_profiles
from hephaestus.optimize.context_packer import ContextCandidate, pack_context
from hephaestus.optimize.model_router import ModelRouteRequest, ModelRoutingError, route_model
from hephaestus.optimize.task_scheduler import compare_schedulers
from hephaestus.optimize.token_firewall import BudgetDecision, TokenBudget, evaluate_budget
from hephaestus.spec.goal import build_goal_spec
from hephaestus.spec.tasks import Task, generate_initial_tasks
from hephaestus.storage import (
    ApprovalRecord,
    RunDecisionRecord,
    RunRecord,
    RunRepository,
    RunTaskRecord,
    SqliteMemoryRepository,
    get_default_database_path,
    init_database,
)

console = Console()

app = typer.Typer(
    name="heph",
    help="Hephaestus: an optimization-first agent runtime foundation.",
    no_args_is_help=True,
)
memory_app = typer.Typer(help="Persistent local memory commands.", no_args_is_help=True)
budget_app = typer.Typer(help="Token and cost budget commands.", no_args_is_help=True)
db_app = typer.Typer(help="Local SQLite database commands.", no_args_is_help=True)
run_app = typer.Typer(help="Run history commands.", no_args_is_help=True)
benchmark_app = typer.Typer(help="Optimizer benchmark commands.", no_args_is_help=True)
app.add_typer(memory_app, name="memory")
app.add_typer(budget_app, name="budget")
app.add_typer(db_app, name="db")
app.add_typer(run_app, name="run")
app.add_typer(benchmark_app, name="benchmark")


class DemoScenario(BaseModel):
    tasks: list[Task]
    model_profiles: list[ModelProfile] = Field(default_factory=list)
    context_candidates: list[ContextCandidate] = Field(default_factory=list)
    quality_threshold: float = Field(default=0.76, ge=0, le=1)
    context_token_budget: int = Field(default=2_000, gt=0)
    token_budget: TokenBudget = Field(
        default_factory=lambda: TokenBudget(
            max_input_tokens=10_000,
            max_output_tokens=4_000,
            max_cost=0.25,
            quality_threshold=0.76,
        )
    )


@app.callback(invoke_without_command=True)
def main(
    version: Annotated[
        bool,
        typer.Option("--version", help="Show the Hephaestus version and exit."),
    ] = False,
) -> None:
    """CLI callback."""

    if version:
        console.print(f"Hephaestus {__version__}")
        raise typer.Exit


@app.command()
def doctor() -> None:
    """Check local environment and optional provider configuration."""

    table = Table(title="Hephaestus Doctor")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")

    python_ok = sys.version_info >= (3, 12)
    table.add_row(
        "Python",
        "ok" if python_ok else "warn",
        f"{platform.python_version()} ({'>=3.12 required'})",
    )
    table.add_row("Package", "ok", f"hephaestus {__version__}")
    deepseek_available = bool(os.getenv("DEEPSEEK_API_KEY"))
    table.add_row(
        "DeepSeek",
        "configured" if deepseek_available else "optional",
        "DEEPSEEK_API_KEY is set"
        if deepseek_available
        else "Set DEEPSEEK_API_KEY to enable API calls",
    )
    table.add_row(
        "Local config",
        "ok",
        (
            f"{DEFAULT_CONFIG.input_token_budget} input token budget, "
            f"quality threshold {DEFAULT_CONFIG.required_quality:.2f}"
        ),
    )
    console.print(table)


@db_app.command("init")
def db_init() -> None:
    """Initialize the local SQLite database."""

    path = init_database()
    console.print(f"Initialized database: {path}")


@db_app.command("path")
def db_path() -> None:
    """Show the default local SQLite database path."""

    console.print(str(get_default_database_path()))


@app.command()
def plan(
    goal: Annotated[str, typer.Argument(help="User goal to turn into a spec/task graph.")],
) -> None:
    """Create a deterministic spec and initial task graph."""

    goal_spec = build_goal_spec(goal)
    tasks = generate_initial_tasks(goal_spec)
    comparison = compare_schedulers(tasks, DEFAULT_CONFIG.objective_weights)

    console.print(Panel(goal_spec.intent, title=goal_spec.title))
    task_table = Table(title="Initial Tasks")
    task_table.add_column("Order")
    task_table.add_column("Task")
    task_table.add_column("Priority", justify="right")
    task_table.add_column("Risk", justify="right")
    task_table.add_column("Approval")
    for index, task in enumerate(comparison.best_order, start=1):
        task_table.add_row(
            str(index),
            task.id,
            str(task.priority),
            f"{task.risk:.2f}",
            "yes" if task.requires_approval else "no",
        )
    console.print(task_table)
    console.print(comparison.explanation)


@app.command()
def optimize(
    path: Annotated[
        Path,
        typer.Argument(help="Path to a demo JSON file with tasks, models, and context."),
    ],
) -> None:
    """Compare greedy and annealing plans, then route models and pack context."""

    scenario = DemoScenario.model_validate_json(path.read_text(encoding="utf-8"))
    run_repository = RunRepository()
    run = run_repository.save_run(RunRecord(goal=f"Optimize {path}", mode="optimize"))
    comparison = compare_schedulers(scenario.tasks, DEFAULT_CONFIG.objective_weights)
    context = pack_context(scenario.context_candidates, scenario.context_token_budget)
    run_repository.save_run_tasks(
        RunTaskRecord(
            run_id=run.id,
            task_id=task.id,
            title=task.title,
            description=task.description,
            selected_order=index,
            priority=task.priority,
            risk=task.risk,
            expected_value=task.expected_value,
            dependencies=task.dependencies,
            required_capabilities=sorted(task.required_capabilities),
            requires_approval=task.requires_approval,
        )
        for index, task in enumerate(comparison.best_order, start=1)
    )
    for task in comparison.best_order:
        if task.requires_approval:
            run_repository.save_approval(
                ApprovalRecord(
                    run_id=run.id,
                    action_type="task",
                    action_description=task.description,
                    risk_level=_risk_level_from_score(task.risk),
                )
            )
    run_repository.save_decision(
        RunDecisionRecord(
            run_id=run.id,
            decision_type="scheduler_greedy",
            selected_option=_task_order_text(comparison.greedy.order),
            objective_score=comparison.greedy.score,
            rationale=comparison.greedy.explanation,
        )
    )
    run_repository.save_decision(
        RunDecisionRecord(
            run_id=run.id,
            decision_type="scheduler_annealing",
            selected_option=_task_order_text(comparison.annealed.order),
            objective_score=comparison.annealed.score,
            rationale=comparison.annealed.explanation,
        )
    )
    run_repository.save_decision(
        RunDecisionRecord(
            run_id=run.id,
            decision_type="context_packing",
            selected_option=", ".join(item.id for item in context.selected) or "none",
            rejected_options=[f"{item.id}: {item.reason}" for item in context.excluded],
            objective_score=context.score,
            rationale=context.explanation,
        )
    )

    console.print(Panel("Naive greedy vs simulated annealing", title="Optimization"))
    schedule_table = Table()
    schedule_table.add_column("Scheduler")
    schedule_table.add_column("Score", justify="right")
    schedule_table.add_column("Dependency Violations", justify="right")
    schedule_table.add_column("Order")
    schedule_table.add_row(
        "greedy",
        f"{comparison.greedy.score:.2f}",
        str(comparison.greedy.breakdown.dependency_violations),
        " -> ".join(task.id for task in comparison.greedy.order),
    )
    schedule_table.add_row(
        "annealing",
        f"{comparison.annealed.score:.2f}",
        str(comparison.annealed.breakdown.dependency_violations),
        " -> ".join(task.id for task in comparison.annealed.order),
    )
    console.print(schedule_table)

    profiles = scenario.model_profiles or fake_model_profiles()
    route_table = Table(title="Model Routing")
    route_table.add_column("Task")
    route_table.add_column("Model")
    route_table.add_column("Quality", justify="right")
    route_table.add_column("Cost", justify="right")
    total_input = 0
    total_output = 0
    total_cost = 0.0
    selected_routes: list[tuple[Task, ModelProfile, float]] = []
    for task in comparison.best_order:
        total_input += task.estimated_input_tokens
        total_output += task.estimated_output_tokens
        try:
            route = route_model(
                ModelRouteRequest(
                    required_capabilities=task.required_capabilities,
                    input_tokens=task.estimated_input_tokens,
                    output_tokens=task.estimated_output_tokens,
                    quality_threshold=scenario.quality_threshold,
                    privacy_level=task.privacy_level,
                    needs_tools=bool(task.allowed_tools),
                    needs_json=True,
                    profiles=profiles,
                )
            )
        except ModelRoutingError as error:
            route_table.add_row(task.id, "unrouted", "-", "-", style="red")
            run_repository.save_decision(
                RunDecisionRecord(
                    run_id=run.id,
                    decision_type=f"model_route:{task.id}",
                    selected_option="unrouted",
                    rejected_options=[str(error)],
                    estimated_cost=0.0,
                    rationale=str(error),
                )
            )
            console.print(f"[red]{error}[/red]")
            continue
        total_cost += route.estimated_cost
        selected_routes.append((task, route.profile, route.quality))
        run_repository.save_decision(
            RunDecisionRecord(
                run_id=run.id,
                decision_type=f"model_route:{task.id}",
                selected_option=route.profile.identifier,
                rejected_options=[
                    f"{rejected.identifier}: {rejected.reason}" for rejected in route.rejected
                ],
                objective_score=route.quality,
                estimated_cost=route.estimated_cost,
                rationale=route.explanation,
            )
        )
        route_table.add_row(
            task.id,
            route.profile.identifier,
            f"{route.quality:.2f}",
            f"${route.estimated_cost:.6f}",
        )
    console.print(route_table)

    context_table = Table(title="Context Packing")
    context_table.add_column("Selected")
    context_table.add_column("Tokens", justify="right")
    context_table.add_column("Critical")
    for item in context.selected:
        context_table.add_row(item.id, str(item.token_cost), "yes" if item.critical else "no")
    console.print(context_table)

    approval_tasks = [task.id for task in comparison.best_order if task.requires_approval]
    budget_decision = None
    if selected_routes:
        task, profile, quality = selected_routes[0]
        budget_decision = evaluate_budget(
            input_tokens=task.estimated_input_tokens,
            output_tokens=task.estimated_output_tokens,
            selected_model=profile,
            selected_quality=quality,
            budget=scenario.token_budget,
        )
        run_repository.save_decision(
            RunDecisionRecord(
                run_id=run.id,
                decision_type="token_budget",
                selected_option="approved" if budget_decision.approved else "blocked",
                rejected_options=_budget_rejections(budget_decision),
                estimated_cost=budget_decision.estimated_cost,
                rationale=budget_decision.explanation,
            )
        )

    summary_lines = [
        comparison.explanation,
        context.explanation,
        f"Estimated tokens: {total_input} input + {total_output} output",
        f"Estimated routed cost: ${total_cost:.6f}",
        "Approval-needed tasks: " + (", ".join(approval_tasks) or "none"),
        budget_decision.explanation if budget_decision else "No routed model for budget check.",
    ]
    run_repository.complete_run(
        run.id,
        estimated_input_tokens=total_input,
        estimated_output_tokens=total_output,
        estimated_cost=total_cost,
        objective_score=comparison.best_score,
        risk_score=max((task.risk for task in comparison.best_order), default=0.0),
        summary="\n".join(summary_lines),
    )

    console.print(
        Panel(
            "\n".join(summary_lines),
            title="Summary",
        )
    )
    console.print(f"Saved run: {run.id}")
    console.print(f"View with: heph run show {run.id}")


@app.command("models")
def list_models() -> None:
    """Show local fake models and optional DeepSeek configuration."""

    deepseek = DeepSeekProvider()
    profiles = [*fake_model_profiles(), *deepseek.profiles()]
    table = Table(title="Model Profiles")
    table.add_column("Provider")
    table.add_column("Model")
    table.add_column("Available")
    table.add_column("Context", justify="right")
    table.add_column("In / Out $ per 1M")
    table.add_column("Tools")
    table.add_column("JSON")
    for profile in profiles:
        available = "yes"
        if profile.provider == "deepseek":
            available = "yes" if deepseek.is_available else "needs key"
        table.add_row(
            profile.provider,
            profile.model,
            available,
            str(profile.context_window),
            f"{profile.input_cost_per_million:g} / {profile.output_cost_per_million:g}",
            "yes" if profile.supports_tools else "no",
            "yes" if profile.supports_json else "no",
        )
    console.print(table)


@benchmark_app.command("list")
def benchmark_list() -> None:
    """List available benchmark fixtures."""

    cases = load_all_benchmarks()
    print_benchmark_list(console, cases)


@benchmark_app.command("show")
def benchmark_show(
    benchmark_id: Annotated[str, typer.Argument(help="Benchmark id, file stem, or path.")],
) -> None:
    """Show benchmark fixture metadata without running it."""

    try:
        case = load_benchmark(benchmark_id)
    except (FileNotFoundError, ValueError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error
    print_benchmark_show(console, case)


@benchmark_app.command("run")
def benchmark_run(
    target: Annotated[
        str | None,
        typer.Argument(help="Optional benchmark id, file stem, filename, or JSON path."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print machine-readable JSON instead of Rich tables."),
    ] = False,
) -> None:
    """Run one benchmark fixture, or all fixtures when no target is supplied."""

    try:
        cases = [load_benchmark(target)] if target is not None else load_all_benchmarks()
    except (FileNotFoundError, ValueError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error

    results = [run_benchmark(case) for case in cases]
    if json_output:
        typer.echo(results_to_json(results))
        return

    for result in results:
        print_benchmark_result(console, result)


@memory_app.command("add")
def memory_add(
    type_: Annotated[MemoryType, typer.Option("--type", help="Memory type.")],
    content: Annotated[str, typer.Option("--content", help="Memory content.")],
    summary: Annotated[str, typer.Option("--summary", help="Short summary.")] = "",
    tag: Annotated[list[str] | None, typer.Option("--tag", help="Repeatable tag.")] = None,
    project: Annotated[str, typer.Option("--project", help="Project namespace.")] = "default",
    confidence: Annotated[
        float,
        typer.Option("--confidence", min=0.0, max=1.0, help="Memory confidence."),
    ] = 0.7,
    importance: Annotated[
        float,
        typer.Option("--importance", min=0.0, max=1.0, help="Memory importance."),
    ] = 0.5,
    source: Annotated[str, typer.Option("--source", help="Memory source.")] = "user",
) -> None:
    """Add a memory to the persistent local store."""

    item = MemoryItem(
        type=type_,
        content=content,
        summary=summary,
        tags=tag or [],
        project=project,
        confidence=confidence,
        importance=importance,
        source=source,
    )
    store = SqliteMemoryRepository()
    store.add(item)
    console.print(
        f"Added {item.type.value} memory {item.id} with tags: {', '.join(item.tags) or '-'}"
    )
    console.print(f"[dim]Stored in {store.database_path}[/dim]")


@memory_app.command("search")
def memory_search(
    query: Annotated[str, typer.Argument(help="Text query.")],
    project: Annotated[str | None, typer.Option("--project", help="Project namespace.")] = None,
    limit: Annotated[int, typer.Option("--limit", min=1, help="Maximum results.")] = 5,
) -> None:
    """Search persistent local memories."""

    store = SqliteMemoryRepository()
    results = store.retrieve_top(query, project=project, limit=limit)
    _print_memory_table("Memory Search", results)


@memory_app.command("list")
def memory_list(
    project: Annotated[str | None, typer.Option("--project", help="Project namespace.")] = None,
) -> None:
    """List persistent local memories."""

    store = SqliteMemoryRepository()
    _print_memory_table("Memory List", store.list(project=project))


@app.command("runs")
def list_runs(
    limit: Annotated[int, typer.Option("--limit", min=1, help="Maximum runs to show.")] = 10,
) -> None:
    """List recent persisted runs."""

    repository = RunRepository()
    runs = repository.list_recent_runs(limit=limit)
    table = Table(title="Recent Runs")
    table.add_column("ID", no_wrap=True)
    table.add_column("Mode")
    table.add_column("Status")
    table.add_column("Started")
    table.add_column("Goal", overflow="fold")
    table.add_column("Score", justify="right")
    table.add_column("Cost", justify="right")
    for run in runs:
        table.add_row(
            run.id,
            run.mode,
            run.status,
            _format_datetime(run.started_at),
            run.goal,
            f"{run.objective_score:.2f}",
            f"${run.estimated_cost:.6f}",
        )
    console.print(table)


@run_app.command("show")
def run_show(
    run_id: Annotated[str, typer.Argument(help="Run ID to inspect.")],
) -> None:
    """Show a persisted run with tasks, decisions, and approvals."""

    repository = RunRepository()
    detail = repository.get_run(run_id)
    if detail is None:
        console.print(f"[red]Run not found: {run_id}[/red]")
        raise typer.Exit(1)

    run = detail.run
    console.print(
        Panel(
            "\n".join(
                [
                    f"Goal: {run.goal}",
                    f"Mode: {run.mode}",
                    f"Status: {run.status}",
                    f"Started: {_format_datetime(run.started_at)}",
                    f"Completed: {_format_datetime(run.completed_at)}",
                    f"Estimated tokens: {run.estimated_input_tokens} input + "
                    f"{run.estimated_output_tokens} output",
                    f"Estimated cost: ${run.estimated_cost:.6f}",
                    f"Objective score: {run.objective_score:.2f}",
                    f"Risk score: {run.risk_score:.2f}",
                    "",
                    run.summary or "No summary recorded.",
                ]
            ),
            title=f"Run {run.id}",
        )
    )

    task_table = Table(title="Run Tasks")
    task_table.add_column("Order", justify="right")
    task_table.add_column("Task")
    task_table.add_column("Priority", justify="right")
    task_table.add_column("Risk", justify="right")
    task_table.add_column("Approval")
    for task in detail.tasks:
        task_table.add_row(
            str(task.selected_order),
            task.task_id,
            str(task.priority),
            f"{task.risk:.2f}",
            "yes" if task.requires_approval else "no",
        )
    console.print(task_table)

    decision_table = Table(title="Run Decisions")
    decision_table.add_column("Type")
    decision_table.add_column("Selected")
    decision_table.add_column("Rejected")
    decision_table.add_column("Score", justify="right")
    decision_table.add_column("Cost", justify="right")
    for decision in detail.decisions:
        decision_table.add_row(
            decision.decision_type,
            decision.selected_option,
            ", ".join(decision.rejected_options) or "-",
            f"{decision.objective_score:.2f}" if decision.objective_score is not None else "-",
            f"${decision.estimated_cost:.6f}" if decision.estimated_cost is not None else "-",
        )
    console.print(decision_table)

    if detail.approvals:
        approval_table = Table(title="Approvals")
        approval_table.add_column("ID")
        approval_table.add_column("Action")
        approval_table.add_column("Risk")
        approval_table.add_column("Status")
        for approval in detail.approvals:
            approval_table.add_row(
                approval.id,
                approval.action_type,
                approval.risk_level.value,
                approval.status.value,
            )
        console.print(approval_table)


def _print_memory_table(title: str, memories: list[MemoryItem]) -> None:
    table = Table(title=title)
    table.add_column("ID", no_wrap=True)
    table.add_column("Type")
    table.add_column("Project")
    table.add_column("Tags")
    table.add_column("Summary")
    for item in memories:
        table.add_row(
            item.id,
            item.type.value,
            item.project,
            ", ".join(item.tags),
            item.summary or item.content,
        )
    console.print(table)


@budget_app.command("demo")
def budget_demo() -> None:
    """Show quality-preserving token/cost optimization without a live API call."""

    profiles = DeepSeekProvider().profiles()
    route = route_model(
        ModelRouteRequest(
            required_capabilities={"planning", "reasoning"},
            input_tokens=8_000,
            output_tokens=1_500,
            quality_threshold=0.85,
            privacy_level=PrivacyLevel.INTERNAL,
            needs_tools=False,
            needs_json=True,
            profiles=list(profiles),
        )
    )
    baseline = next(profile for profile in profiles if profile.model == "deepseek-v4-pro")
    decision = evaluate_budget(
        input_tokens=8_000,
        output_tokens=1_500,
        selected_model=route.profile,
        selected_quality=route.quality,
        budget=TokenBudget(
            max_input_tokens=12_000,
            max_output_tokens=4_000,
            max_cost=0.05,
            quality_threshold=0.85,
        ),
        baseline_model=baseline,
    )
    console.print(Panel(decision.explanation, title="Budget Demo"))
    console.print(
        "Principle: cheap when possible, strong when necessary, local/private when required."
    )


def _task_order_text(tasks: list[Task]) -> str:
    return " -> ".join(task.id for task in tasks)


def _risk_level_from_score(score: float) -> RiskLevel:
    if score >= 0.75:
        return RiskLevel.CRITICAL
    if score >= 0.5:
        return RiskLevel.HIGH
    if score >= 0.25:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def _budget_rejections(decision: BudgetDecision) -> list[str]:
    rejected: list[str] = []
    if not decision.within_token_budget:
        rejected.append("token budget exceeded")
    if not decision.within_cost_budget:
        rejected.append("cost budget exceeded")
    if not decision.meets_quality_threshold:
        rejected.append("quality threshold missed")
    return rejected


def _format_datetime(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.isoformat(timespec="seconds")


if __name__ == "__main__":
    app()
