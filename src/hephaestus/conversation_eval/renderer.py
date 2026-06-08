"""Rich rendering helpers for conversation benchmark evaluation."""

from __future__ import annotations

from rich.console import Console, Group, RenderableType
from rich.panel import Panel
from rich.table import Table

from hephaestus.conversation_eval.schemas import (
    ConversationBenchmarkFixture,
    ConversationEvaluationResult,
)


def print_conversation_benchmark_list(
    console: Console,
    fixtures: list[ConversationBenchmarkFixture],
) -> None:
    """Print available conversation benchmark fixtures."""

    table = Table(title="Conversation Benchmarks")
    table.add_column("ID")
    table.add_column("Mode")
    table.add_column("Profile")
    table.add_column("Title")
    for fixture in fixtures:
        table.add_row(
            fixture.id,
            fixture.mode.value,
            fixture.quality_profile,
            fixture.title,
        )
    console.print(table)


def build_conversation_benchmark_result_renderable(
    result: ConversationEvaluationResult,
) -> RenderableType:
    """Render one conversation benchmark result."""

    check_table = Table(title="Checks")
    check_table.add_column("Status")
    check_table.add_column("Check")
    check_table.add_column("Evidence", overflow="fold")
    for check in result.checks:
        check_table.add_row(
            "pass" if check.passed else "fail",
            check.label,
            check.evidence or "-",
        )
    warnings = "\n".join(f"- {warning}" for warning in result.warnings) or "- none"
    anti_patterns = (
        "\n".join(f"- {pattern}" for pattern in result.anti_patterns_detected)
        or "- none"
    )
    return Group(
        Panel(
            "\n".join(
                [
                    f"Benchmark: {result.benchmark_id}",
                    f"Title: {result.title}",
                    f"Mode: {result.mode.value}",
                    f"Provider: {result.provider_model}",
                    f"Score: {result.score:.2f}",
                    f"Passed: {len(result.passed_checks)}",
                    f"Failed: {len(result.failed_checks)}",
                ]
            ),
            title="Conversation Benchmark Result",
        ),
        check_table,
        Panel(warnings, title="Warnings"),
        Panel(anti_patterns, title="Anti-patterns Detected"),
    )


def build_conversation_benchmark_summary_table(
    results: list[ConversationEvaluationResult],
) -> Table:
    """Render a compact table for multiple benchmark results."""

    table = Table(title="Conversation Benchmark Summary")
    table.add_column("ID")
    table.add_column("Mode")
    table.add_column("Score", justify="right")
    table.add_column("Failed", justify="right")
    table.add_column("Anti-patterns", overflow="fold")
    for result in results:
        table.add_row(
            result.benchmark_id,
            result.mode.value,
            f"{result.score:.2f}",
            str(len(result.failed_checks)),
            ", ".join(result.anti_patterns_detected) or "-",
        )
    return table
