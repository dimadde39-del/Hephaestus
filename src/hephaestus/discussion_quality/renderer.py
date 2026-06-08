"""Rich renderers for discussion quality and research plans."""

from __future__ import annotations

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table

from hephaestus.discussion_quality.schemas import (
    DiscussionQualityEvaluation,
    ResearchPlan,
)


def build_discussion_quality_renderable(
    evaluation: DiscussionQualityEvaluation,
) -> RenderableType:
    """Render discussion quality evaluation."""

    table = Table(title=f"Discussion Quality: {evaluation.rubric_name}")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Evidence", overflow="fold")
    for check in evaluation.checks:
        table.add_row(check.label, "ok" if check.satisfied else "missing", check.evidence or "-")
    return Group(
        Panel(
            f"Score: {evaluation.score:.2f}\n{evaluation.summary}",
            title=evaluation.discussion_type.value,
        ),
        table,
    )


def build_research_plan_renderable(plan: ResearchPlan) -> RenderableType:
    """Render a research plan."""

    return Group(
        Panel(plan.question, title="Research Planning Mode"),
        _list_panel("Needs Verification", plan.needs_verification),
        _list_panel("Likely Sources", plan.likely_sources),
        _list_panel("Search Queries", plan.search_queries),
        _list_panel("Evidence Quality", plan.evidence_quality_expectations),
        _list_panel("What Would Change The Conclusion", plan.what_would_change_conclusion),
        _list_panel("Risks Of Shallow Research", plan.shallow_research_risks),
    )


def _list_panel(title: str, values: list[str]) -> Panel:
    body = "\n".join(f"- {value}" for value in values) if values else "- none"
    return Panel(body, title=title)
