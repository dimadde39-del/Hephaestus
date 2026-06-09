"""Rich renderers for policy profiles and evaluations."""

from __future__ import annotations

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table

from hephaestus.policy.evaluator import render_policy_response
from hephaestus.policy.schemas import (
    PolicyBenchmarkResult,
    PolicyEvaluation,
    PolicyProfile,
)


def build_policy_profiles_table(
    profiles: list[PolicyProfile],
    *,
    active_profile_id: str,
) -> Table:
    """Render all policy profiles."""

    table = Table(title="Policy Profiles")
    table.add_column("Active")
    table.add_column("ID")
    table.add_column("Recommended")
    table.add_column("Refusal")
    table.add_column("Description", overflow="fold")
    for profile in profiles:
        table.add_row(
            "yes" if profile.id == active_profile_id else "",
            profile.id,
            "yes" if profile.recommended else "",
            profile.refusal_style.value,
            profile.description,
        )
    return table


def build_active_policy_panel(profile: PolicyProfile) -> Panel:
    """Render active policy profile."""

    return Panel(
        "\n".join(
            [
                f"Active profile: {profile.id}",
                f"Name: {profile.name}",
                f"Recommended: {'yes' if profile.recommended else 'no'}",
                f"Refusal style: {profile.refusal_style.value}",
                profile.description,
            ]
        ),
        title="Active Policy Profile",
    )


def build_policy_profile_renderable(profile: PolicyProfile) -> RenderableType:
    """Render one profile with boundaries."""

    boundary_table = Table(title="Policy Boundaries")
    boundary_table.add_column("Category")
    boundary_table.add_column("Decision")
    boundary_table.add_column("Description", overflow="fold")
    for boundary in profile.boundaries:
        boundary_table.add_row(
            boundary.category.value,
            boundary.decision.value,
            boundary.description,
        )
    guidance = "\n".join(f"- {item}" for item in profile.behavior_guidance) or "- none"
    return Group(
        Panel(
            "\n".join(
                [
                    f"ID: {profile.id}",
                    f"Type: {profile.profile_type.value}",
                    f"Name: {profile.name}",
                    f"Recommended: {'yes' if profile.recommended else 'no'}",
                    f"Refusal style: {profile.refusal_style.value}",
                    "",
                    profile.description,
                    "",
                    "Benign task philosophy:",
                    profile.benign_task_philosophy or "-",
                    "",
                    "Behavior guidance:",
                    guidance,
                ]
            ),
            title=f"Policy Profile: {profile.id}",
        ),
        boundary_table,
    )


def build_policy_evaluation_renderable(evaluation: PolicyEvaluation) -> RenderableType:
    """Render one policy evaluation."""

    decision = evaluation.decision
    categories = ", ".join(category.value for category in decision.categories)
    reasons = "\n".join(f"- {reason}" for reason in decision.reasons) or "- none"
    return Group(
        Panel(
            "\n".join(
                [
                    f"Profile: {evaluation.profile_name} ({evaluation.profile_type.value})",
                    f"Decision: {decision.decision_type.value}",
                    f"Primary category: {decision.primary_category.value}",
                    f"Categories: {categories or '-'}",
                    f"Requires approval: {'yes' if decision.requires_approval else 'no'}",
                    f"Confidence: {decision.confidence:.2f}",
                    "",
                    "Reasons:",
                    reasons,
                ]
            ),
            title="Policy Evaluation",
        ),
        Panel(render_policy_response(evaluation), title="Policy Response"),
    )


def build_policy_benchmark_list_table(results: list[PolicyBenchmarkResult]) -> Table:
    """Render policy benchmark results."""

    table = Table(title="Policy Benchmark Results")
    table.add_column("Status")
    table.add_column("ID")
    table.add_column("Expected")
    table.add_column("Actual")
    table.add_column("Failures", overflow="fold")
    for result in results:
        table.add_row(
            "pass" if result.passed else "fail",
            result.case.id,
            result.case.expected_decision.value,
            result.evaluation.decision.decision_type.value,
            "; ".join(result.failures) or "-",
        )
    return table


def build_policy_benchmark_fixture_table(cases: list[str]) -> Table:
    """Render available policy benchmark fixture identifiers."""

    table = Table(title="Policy Benchmarks")
    table.add_column("ID")
    for case_id in cases:
        table.add_row(case_id)
    return table
