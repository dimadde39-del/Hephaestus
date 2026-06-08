"""Rich renderers for Pareto frontiers."""

from __future__ import annotations

from collections.abc import Sequence

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table

from hephaestus.pareto.schemas import (
    DecisionCandidate,
    ObjectiveDimension,
    ObjectiveVector,
    ParetoFrontier,
    ParetoSelectionResult,
    PreferenceProfile,
    direction_for,
)
from hephaestus.pareto.selector import builtin_preference_profiles


def build_preference_profiles_table() -> Table:
    """Render built-in preference profiles."""

    table = Table(title="Pareto Preference Profiles")
    table.add_column("ID", no_wrap=True)
    table.add_column("Priorities")
    table.add_column("Thresholds")
    table.add_column("Description", overflow="fold")
    for profile in builtin_preference_profiles().values():
        thresholds = [
            f"{dimension.value}>={value:.2f}"
            for dimension, value in profile.minimum_thresholds.items()
        ]
        thresholds.extend(
            f"{dimension.value}<={value:.2f}"
            for dimension, value in profile.maximum_thresholds.items()
        )
        table.add_row(
            profile.id,
            ", ".join(dimension.value for dimension in profile.priorities) or "-",
            ", ".join(thresholds) or "-",
            profile.description,
        )
    return table


def build_selection_renderable(selection: ParetoSelectionResult) -> Group:
    """Render one complete Pareto selection result."""

    frontier = selection.frontier
    renderables: list[RenderableType] = [
        Panel(
            "\n".join(
                [
                    f"Preference: {selection.preference_profile.id}",
                    f"Candidates: {len(frontier.candidates)}",
                    f"Valid candidates considered: {selection.valid_candidate_count}",
                    f"Frontier candidates: {len(frontier.frontier_candidate_ids)}",
                    f"Dominated candidates: {selection.dominated_candidate_count}",
                    f"Selected: {selection.selected_candidate.label}",
                ]
            ),
            title=frontier.title or f"Pareto Frontier {frontier.id}",
        ),
        _candidate_table(frontier.candidates, frontier.frontier_candidate_ids, selection),
        _comparison_table(frontier),
        _tradeoff_panel(selection),
    ]
    return Group(*renderables)


def build_frontier_list_table(frontiers: Sequence[ParetoFrontier]) -> Table:
    """Render persisted frontier summaries."""

    table = Table(title="Pareto Frontiers")
    table.add_column("ID", no_wrap=True)
    table.add_column("Run", no_wrap=True)
    table.add_column("Type")
    table.add_column("Preference")
    table.add_column("Counts")
    table.add_column("Selected", overflow="fold")
    table.add_column("Created")
    if not frontiers:
        table.add_row("none", "-", "-", "-", "candidates=0; frontier=0; dominated=0", "-", "-")
        return table
    for frontier in frontiers:
        selected = frontier.selected_candidate
        table.add_row(
            frontier.id,
            frontier.run_id or "-",
            frontier.candidate_type.value if frontier.candidate_type is not None else "mixed",
            frontier.preference_profile_id,
            (
                f"candidates={len(frontier.candidates)}; "
                f"frontier={len(frontier.frontier_candidate_ids)}; "
                f"dominated={len(frontier.dominated_candidate_ids)}"
            ),
            selected.label if selected is not None else "-",
            frontier.created_at.isoformat(timespec="seconds"),
        )
    return table


def build_frontier_detail_renderable(
    frontier: ParetoFrontier,
    selection: ParetoSelectionResult | None = None,
) -> Group:
    """Render a persisted frontier with or without its selection record."""

    if selection is not None:
        return build_selection_renderable(selection)
    renderables: list[RenderableType] = [
        Panel(
            "\n".join(
                [
                    f"Run: {frontier.run_id or '-'}",
                    f"Preference: {frontier.preference_profile_id}",
                    f"Candidates: {len(frontier.candidates)}",
                    f"Frontier: {len(frontier.frontier_candidate_ids)}",
                    f"Selected: {frontier.selected_candidate_id or '-'}",
                ]
            ),
            title=frontier.title or f"Pareto Frontier {frontier.id}",
        ),
        _candidate_table(frontier.candidates, frontier.frontier_candidate_ids, selection),
        _comparison_table(frontier),
    ]
    if frontier.tradeoff_explanation is not None:
        renderables.append(
            Panel(frontier.tradeoff_explanation.summary, title="Tradeoff Explanation")
        )
    return Group(*renderables)


def build_pareto_summary_table(selections: Sequence[ParetoSelectionResult]) -> Table:
    """Render a compact explain/benchmark summary table."""

    table = Table(title="Pareto Frontier")
    table.add_column("Frontier", no_wrap=True)
    table.add_column("Type")
    table.add_column("Counts")
    table.add_column("Selected", overflow="fold")
    table.add_column("Preference")
    if not selections:
        table.add_row("none", "-", "candidates=0; frontier=0; dominated=0", "-", "-")
        return table
    for selection in selections:
        frontier = selection.frontier
        table.add_row(
            frontier.id,
            frontier.candidate_type.value if frontier.candidate_type is not None else "mixed",
            (
                f"candidates={len(frontier.candidates)}; "
                f"frontier={len(frontier.frontier_candidate_ids)}; "
                f"dominated={selection.dominated_candidate_count}"
            ),
            selection.selected_candidate.label,
            selection.preference_profile.id,
        )
    return table


def build_pareto_summary_panel(selections: Sequence[ParetoSelectionResult]) -> Panel:
    """Render compact summary metrics for explain --summary."""

    dominated = sum(selection.dominated_candidate_count for selection in selections)
    selected = len(selections)
    preferences = sorted({selection.preference_profile.id for selection in selections})
    candidates = sum(len(selection.frontier.candidates) for selection in selections)
    return Panel(
        "\n".join(
            [
                f"Pareto frontiers count: {len(selections)}",
                f"Candidate count: {candidates}",
                f"Dominated candidates count: {dominated}",
                f"Selected candidates count: {selected}",
                "Preference profiles used: " + (", ".join(preferences) or "none"),
            ]
        ),
        title="Pareto Summary",
    )


def _candidate_table(
    candidates: Sequence[DecisionCandidate],
    frontier_ids: Sequence[str],
    selection: ParetoSelectionResult | None,
) -> Table:
    frontier_id_set = set(frontier_ids)
    selected_id = selection.selected_candidate.id if selection is not None else ""
    scores = selection.candidate_scores if selection is not None else {}
    table = Table(title="Pareto Candidates")
    table.add_column("Candidate", overflow="fold")
    table.add_column("Role")
    table.add_column("Valid")
    table.add_column("Objectives", overflow="fold")
    table.add_column("Score", justify="right")
    table.add_column("Why", overflow="fold")
    for candidate in candidates:
        vector = candidate.objective_vector
        role = "selected" if candidate.id == selected_id else "frontier" if candidate.id in frontier_id_set else "dominated"
        if not candidate.constraints_satisfied:
            role = "invalid"
        table.add_row(
            candidate.label,
            role,
            "yes" if candidate.constraints_satisfied else "no",
            _objective_text(vector),
            f"{scores[candidate.id]:.3f}" if candidate.id in scores else "-",
            candidate.rationale,
        )
    return table


def _comparison_table(frontier: ParetoFrontier) -> Table:
    table = Table(title="Dominance")
    table.add_column("Candidate", no_wrap=True)
    table.add_column("Status")
    table.add_column("Dominated By")
    table.add_column("Dominates")
    table.add_column("Reason", overflow="fold")
    label_by_id = {candidate.id: candidate.label for candidate in frontier.candidates}
    for comparison in frontier.comparisons:
        table.add_row(
            label_by_id.get(comparison.candidate_id, comparison.candidate_id),
            "frontier" if comparison.is_frontier else "dominated",
            ", ".join(label_by_id.get(item, item) for item in comparison.dominated_by) or "-",
            ", ".join(label_by_id.get(item, item) for item in comparison.dominates) or "-",
            comparison.reason,
        )
    return table


def _tradeoff_panel(selection: ParetoSelectionResult) -> Panel:
    explanation = selection.tradeoff_explanation
    lines = [explanation.summary]
    if explanation.advantages:
        lines.extend(["", "Advantages:"])
        lines.extend(f"- {item}" for item in explanation.advantages)
    if explanation.tradeoffs:
        lines.extend(["", "Tradeoffs:"])
        lines.extend(f"- {item}" for item in explanation.tradeoffs)
    if explanation.rejected_candidate_notes:
        lines.extend(["", "Rejected or lower-ranked candidates:"])
        lines.extend(f"- {item}" for item in explanation.rejected_candidate_notes)
    return Panel("\n".join(lines), title="Tradeoff")


def _objective_text(objective: ObjectiveVector) -> str:
    return (
        f"q={objective.quality:.2f}; cost=${objective.cost:.6f}; "
        f"lat={objective.latency:.2f}; risk={objective.risk:.2f}; "
        f"privacy={objective.privacy:.2f}; tokens={objective.token_usage:.0f}; "
        f"safety={objective.safety:.2f}; profile={objective.profile_alignment:.2f}"
    )


def preference_profile_detail(profile: PreferenceProfile) -> str:
    """Return text detail for a preference profile."""

    weights = ", ".join(
        f"{dimension.value}={profile.weights[dimension]:.2f}"
        for dimension in ObjectiveDimension
        if dimension in profile.weights
    )
    directions = ", ".join(
        f"{dimension.value}:{direction_for(dimension).value}" for dimension in ObjectiveDimension
    )
    return "\n".join(
        [
            profile.description,
            f"Priorities: {', '.join(dimension.value for dimension in profile.priorities) or '-'}",
            f"Weights: {weights}",
            f"Directions: {directions}",
        ]
    )
