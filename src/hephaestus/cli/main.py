"""Hephaestus CLI."""

from __future__ import annotations

import json
import os
import platform
import sys
from pathlib import Path
from typing import Annotated, Any

import typer
from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from hephaestus import __version__
from hephaestus.core.config import DEFAULT_CONFIG, PrivacyLevel
from hephaestus.memory import InMemoryMemoryStore, MemoryItem, MemoryType
from hephaestus.models import DeepSeekProvider, ModelProfile, fake_model_profiles
from hephaestus.optimize.context_packer import ContextCandidate, pack_context
from hephaestus.optimize.model_router import ModelRouteRequest, ModelRoutingError, route_model
from hephaestus.optimize.task_scheduler import compare_schedulers
from hephaestus.optimize.token_firewall import TokenBudget, evaluate_budget
from hephaestus.spec.goal import build_goal_spec
from hephaestus.spec.tasks import Task, generate_initial_tasks

console = Console()

app = typer.Typer(
    name="heph",
    help="Hephaestus: an optimization-first agent runtime foundation.",
    no_args_is_help=True,
)
memory_app = typer.Typer(help="Process-local memory commands.", no_args_is_help=True)
budget_app = typer.Typer(help="Token and cost budget commands.", no_args_is_help=True)
app.add_typer(memory_app, name="memory")
app.add_typer(budget_app, name="budget")


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
    comparison = compare_schedulers(scenario.tasks, DEFAULT_CONFIG.objective_weights)
    context = pack_context(scenario.context_candidates, scenario.context_token_budget)

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
            console.print(f"[red]{error}[/red]")
            continue
        total_cost += route.estimated_cost
        selected_routes.append((task, route.profile, route.quality))
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

    console.print(
        Panel(
            "\n".join(
                [
                    comparison.explanation,
                    context.explanation,
                    f"Estimated tokens: {total_input} input + {total_output} output",
                    f"Estimated routed cost: ${total_cost:.6f}",
                    "Approval-needed tasks: " + (", ".join(approval_tasks) or "none"),
                    budget_decision.explanation
                    if budget_decision
                    else "No routed model for budget check.",
                ]
            ),
            title="Summary",
        )
    )


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


@memory_app.command("add")
def memory_add(
    type_: Annotated[MemoryType, typer.Option("--type", help="Memory type.")],
    content: Annotated[str, typer.Option("--content", help="Memory content.")],
    summary: Annotated[str, typer.Option("--summary", help="Short summary.")] = "",
    tag: Annotated[list[str] | None, typer.Option("--tag", help="Repeatable tag.")] = None,
    project: Annotated[str, typer.Option("--project", help="Project namespace.")] = "default",
) -> None:
    """Add a memory to the process-local store."""

    item = MemoryItem(
        type=type_,
        content=content,
        summary=summary,
        tags=tag or [],
        project=project,
    )
    store = _demo_memory_store()
    store.add(item)
    console.print(
        f"Added {item.type.value} memory {item.id} with tags: {', '.join(item.tags) or '-'}"
    )
    console.print(
        "[dim]Phase 1 CLI memory is process-local; persistent storage arrives later.[/dim]"
    )


@memory_app.command("search")
def memory_search(
    query: Annotated[str, typer.Argument(help="Text query.")],
    project: Annotated[str | None, typer.Option("--project", help="Project namespace.")] = None,
) -> None:
    """Search process-local demo memories."""

    store = _demo_memory_store()
    results = store.retrieve_top(query, project=project)
    table = Table(title="Memory Search")
    table.add_column("ID")
    table.add_column("Type")
    table.add_column("Tags")
    table.add_column("Summary")
    for item in results:
        table.add_row(item.id, item.type.value, ", ".join(item.tags), item.summary or item.content)
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


def _demo_memory_store() -> InMemoryMemoryStore:
    return InMemoryMemoryStore(
        [
            MemoryItem(
                type=MemoryType.PROJECT,
                content="Hephaestus is optimization-first and model-agnostic.",
                summary="Optimization-first project direction.",
                tags=["hephaestus", "optimization", "architecture"],
                project="hephaestus",
                importance=0.9,
            ),
            MemoryItem(
                type=MemoryType.FAILURE,
                content="Do not require paid APIs for tests or demos.",
                summary="Tests must run without paid APIs.",
                tags=["testing", "models", "cost"],
                project="hephaestus",
                importance=0.8,
            ),
        ]
    )


def _json_dump(data: Any) -> str:
    return json.dumps(data, indent=2, sort_keys=True)


if __name__ == "__main__":
    app()
