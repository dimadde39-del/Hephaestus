"""Rich and JSON benchmark reporting."""

from __future__ import annotations

from pydantic import TypeAdapter
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from hephaestus.benchmarks.schemas import BenchmarkCase, BenchmarkResult
from hephaestus.pareto.renderer import build_pareto_summary_table
from hephaestus.policy_learning.renderer import build_profile_application_table


def print_benchmark_list(console: Console, cases: list[BenchmarkCase]) -> None:
    """Print discovered benchmarks."""

    table = Table(title="Benchmark Fixtures")
    table.add_column("ID", no_wrap=True)
    table.add_column("Title")
    table.add_column("Tasks", justify="right")
    table.add_column("Tags")
    for case in cases:
        table.add_row(case.id, case.title, str(len(case.tasks)), ", ".join(case.tags) or "-")
    console.print(table)


def print_benchmark_show(console: Console, case: BenchmarkCase) -> None:
    """Print benchmark metadata without executing it."""

    lines = [
        case.description or "No description.",
        "",
        f"Goal: {case.goal or '-'}",
        f"Tasks: {len(case.tasks)}",
        f"Models: {len(case.model_profiles) or 'default fake profiles'}",
        f"Context candidates: {len(case.context_candidates)}",
        f"Context token budget: {case.context_token_budget}",
        f"Quality threshold: {case.quality_threshold:.2f}",
        f"Tags: {', '.join(case.tags) or '-'}",
    ]
    if case.expected_constraints:
        lines.extend(["", "Expected constraints:"])
        lines.extend(f"- {constraint}" for constraint in case.expected_constraints)
    if case.notes:
        lines.extend(["", "Notes:"])
        lines.extend(f"- {note}" for note in case.notes)
    console.print(Panel("\n".join(lines), title=f"{case.id}: {case.title}"))


def print_benchmark_result(console: Console, result: BenchmarkResult) -> None:
    """Print one complete benchmark result."""

    console.print(Panel(result.case.description, title=f"Benchmark: {result.case.id}"))
    schedule_table = Table(title="Scheduler Comparison")
    schedule_table.add_column("Scheduler")
    schedule_table.add_column("Score", justify="right")
    schedule_table.add_column("Dependency Violations", justify="right")
    schedule_table.add_column("Order")
    schedule_table.add_row(
        "greedy",
        f"{result.scheduler.greedy_score:.2f}",
        str(result.scheduler.greedy_dependency_violations),
        " -> ".join(result.scheduler.greedy_order),
    )
    schedule_table.add_row(
        "annealing",
        f"{result.scheduler.annealing_score:.2f}",
        str(result.scheduler.annealing_dependency_violations),
        " -> ".join(result.scheduler.annealing_order),
    )
    console.print(schedule_table)
    console.print(
        f"Delta: {result.scheduler.score_delta:+.2f} "
        f"({result.scheduler.score_delta_percent:+.2f}%). "
        f"Selected: {result.scheduler.best_scheduler}."
    )

    route_table = Table(title="Model Routing")
    route_table.add_column("Task")
    route_table.add_column("Selected")
    route_table.add_column("Quality", justify="right")
    route_table.add_column("Required", justify="right")
    route_table.add_column("Rejected")
    route_table.add_column("Cost", justify="right")
    for route in result.model_routes:
        rejected = "; ".join(
            f"{item.identifier}: {item.reason}" for item in route.rejected_models
        )
        route_table.add_row(
            route.task_id,
            route.selected_model,
            f"{route.selected_quality:.2f}" if route.selected_quality is not None else "-",
            f"{route.required_quality_threshold:.2f}",
            rejected or "-",
            f"${route.estimated_cost:.6f}",
        )
    console.print(route_table)

    context_table = Table(title="Context")
    context_table.add_column("Candidates", justify="right")
    context_table.add_column("Selected", justify="right")
    context_table.add_column("Tokens Before", justify="right")
    context_table.add_column("Tokens After", justify="right")
    context_table.add_column("Savings", justify="right")
    context_table.add_column("Critical Included")
    context_table.add_row(
        str(result.context.candidate_count),
        str(result.context.selected_count),
        str(result.context.tokens_before),
        str(result.context.tokens_after),
        f"{result.context.token_savings_percent:.1f}%",
        "yes" if result.context.critical_items_included else "no",
    )
    console.print(context_table)

    guard_table = Table(title="Quality And Budget Guard")
    guard_table.add_column("Required Quality")
    guard_table.add_column("Preserved")
    guard_table.add_column("Token Budget")
    guard_table.add_column("Cost Budget")
    guard_table.add_column("Approvals", justify="right")
    guard_table.add_column("Estimated Cost", justify="right")
    guard_table.add_row(
        f"{result.case.quality_threshold:.2f}",
        "yes" if result.quality_preserved else "no",
        "ok" if result.budget.within_token_budget else "blocked",
        "ok" if result.budget.within_cost_budget else "blocked",
        str(result.approval_required_count),
        f"${result.estimated_cost:.6f}",
    )
    console.print(guard_table)

    decision_table = Table(title="Decision Trace")
    decision_table.add_column("Decisions", justify="right")
    decision_table.add_column("Top Type")
    decision_table.add_column("Top Rationale")
    decision_table.add_column("Most Common Rejection")
    decision_table.add_column("Token Savings")
    decision_table.add_column("Profiles", justify="right")
    decision_table.add_row(
        str(result.decision_count),
        result.top_decision_type or "-",
        result.top_decision_rationale or "-",
        result.most_common_rejection_reason or "-",
        result.token_savings_summary or "-",
        str(len(result.profile_applications)),
    )
    console.print(decision_table)
    if result.profile_applications:
        console.print(build_profile_application_table(result.profile_applications))
    if result.pareto_selections:
        console.print(build_pareto_summary_table(result.pareto_selections))
        for selection in result.pareto_selections:
            console.print(selection.tradeoff_explanation.summary)
    console.print(Panel(result.summary, title="Summary"))
    if result.run_id is not None:
        console.print(f"Saved run: {result.run_id}")
        console.print(f"View with: heph run show {result.run_id}")
        console.print(f"Explain with: heph explain {result.run_id}")


def results_to_json(results: list[BenchmarkResult]) -> str:
    """Serialize benchmark results for machine-readable output."""

    adapter = TypeAdapter(list[BenchmarkResult])
    return adapter.dump_json(results, indent=2).decode("utf-8")
