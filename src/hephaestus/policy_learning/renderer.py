"""Rich renderers for decision quality profiles."""

from __future__ import annotations

from collections.abc import Sequence

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table

from hephaestus.policy_learning.analysis import (
    ProfileApplicationSummary,
    ProfileSummary,
    summarize_profile_applications,
    summarize_profiles,
)
from hephaestus.policy_learning.schemas import (
    DecisionQualityProfile,
    ProfileApplicationResult,
    ProfileEvaluation,
)


def build_profile_suggest_renderable(evaluation: ProfileEvaluation) -> Group:
    """Build output for profile suggestion generation."""

    renderables: list[RenderableType] = [
        Panel(evaluation.summary, title="Policy Learning"),
        build_profile_list_renderable(evaluation.profiles, title="Profiles Created"),
    ]
    if evaluation.profiles:
        renderables.append(_source_table(evaluation.profiles))
    return Group(*renderables)


def build_profile_list_renderable(
    profiles: Sequence[DecisionQualityProfile],
    *,
    title: str = "Decision Quality Profiles",
) -> Table:
    """Build a compact profile list table."""

    table = Table(title=title)
    table.add_column("ID", no_wrap=True)
    table.add_column("Area")
    table.add_column("Status")
    table.add_column("Confidence", justify="right")
    table.add_column("Evidence", justify="right")
    table.add_column("Name")
    if not profiles:
        table.add_row("none", "-", "-", "-", "0", "No profiles recorded.")
        return table
    for profile in profiles:
        table.add_row(
            profile.id,
            profile.decision_area.value,
            profile.status.value,
            f"{profile.confidence:.2f}",
            str(len(profile.evidence)),
            profile.name,
        )
    return table


def build_profile_show_renderable(profile: DecisionQualityProfile) -> Group:
    """Build a detailed profile view."""

    lines = [
        f"Name: {profile.name}",
        f"Area: {profile.decision_area.value}",
        f"Status: {profile.status.value}",
        f"Confidence: {profile.confidence:.2f}",
        f"Created: {profile.created_at.isoformat(timespec='seconds')}",
        f"Updated: {profile.updated_at.isoformat(timespec='seconds')}",
        f"Tags: {', '.join(profile.tags) or '-'}",
        "",
        profile.description or "No description.",
    ]
    return Group(
        Panel("\n".join(lines), title=f"Profile {profile.id}"),
        _rule_table(profile),
        _evidence_table(profile),
        _source_detail_table(profile),
    )


def build_profile_summary_renderable(profiles: Sequence[DecisionQualityProfile]) -> Group:
    """Build summary tables for a profile inventory."""

    summary = summarize_profiles(profiles)
    return Group(_profile_summary_table(summary), build_profile_list_renderable(profiles))


def build_profile_application_table(
    applications: Sequence[ProfileApplicationResult],
    *,
    title: str = "Profile Applications",
) -> Table:
    """Build a table of recorded profile applications."""

    table = Table(title=title)
    table.add_column("Profile", no_wrap=True)
    table.add_column("Area")
    table.add_column("Target")
    table.add_column("Applied")
    table.add_column("Effect", overflow="fold")
    table.add_column("Reason", overflow="fold")
    if not applications:
        table.add_row("none", "-", "-", "-", "No profile applications recorded.", "-")
        return table
    for application in applications:
        table.add_row(
            application.profile_id,
            application.decision_area.value,
            application.target or "-",
            "yes" if application.applied else "no",
            application.effect_summary or "-",
            "; ".join(application.notes) or application.profile_name,
        )
    return table


def build_profile_application_summary_renderable(
    applications: Sequence[ProfileApplicationResult],
) -> Table:
    """Build a compact profile application count table."""

    summary = summarize_profile_applications(applications)
    return _profile_application_summary_table(summary)


def _rule_table(profile: DecisionQualityProfile) -> Table:
    table = Table(title="Profile Rules")
    table.add_column("Rule")
    table.add_column("Type")
    table.add_column("Target")
    table.add_column("Structured Settings", overflow="fold")
    table.add_column("Rationale", overflow="fold")
    if not profile.rules:
        table.add_row("none", "-", "-", "-", "No rules recorded.")
        return table
    for rule in profile.rules:
        settings = [
            f"hard_constraint={rule.hard_constraint}",
            f"require_approval={rule.require_approval}",
        ]
        if rule.minimum_quality_score is not None:
            settings.append(f"minimum_quality_score={rule.minimum_quality_score:.2f}")
        if rule.max_failure_rate is not None:
            settings.append(f"max_failure_rate={rule.max_failure_rate:.2f}")
        if rule.prefer_model_tags:
            settings.append("prefer=" + ", ".join(rule.prefer_model_tags))
        if rule.avoid_model_tags:
            settings.append("avoid=" + ", ".join(rule.avoid_model_tags))
        settings.extend(
            f"{adjustment.target} {adjustment.operation.value} {adjustment.value}"
            for adjustment in rule.adjustments
        )
        table.add_row(
            rule.id,
            rule.rule_type.value,
            rule.target,
            "; ".join(settings),
            rule.rationale or "-",
        )
    return table


def _evidence_table(profile: DecisionQualityProfile) -> Table:
    table = Table(title="Profile Evidence")
    table.add_column("Type")
    table.add_column("Source", no_wrap=True)
    table.add_column("Weight", justify="right")
    table.add_column("Confidence", justify="right")
    table.add_column("Summary", overflow="fold")
    if not profile.evidence:
        table.add_row("none", "-", "-", "-", "No evidence recorded.")
        return table
    for item in profile.evidence:
        table.add_row(
            item.evidence_type.value,
            item.source_id,
            f"{item.weight:.2f}",
            f"{item.confidence:.2f}",
            item.summary,
        )
    return table


def _source_table(profiles: Sequence[DecisionQualityProfile]) -> Table:
    table = Table(title="Profile Sources")
    table.add_column("Profile")
    table.add_column("Area")
    table.add_column("Source Signals")
    table.add_column("Source Outcomes")
    for profile in profiles:
        table.add_row(
            profile.id,
            profile.decision_area.value,
            ", ".join(profile.source_learning_signal_ids) or "-",
            ", ".join(profile.source_outcome_ids) or "-",
        )
    return table


def _source_detail_table(profile: DecisionQualityProfile) -> Table:
    table = Table(title="Source Artifacts")
    table.add_column("Learning Signals", overflow="fold")
    table.add_column("Outcomes", overflow="fold")
    table.add_column("Policy Suggestions", overflow="fold")
    table.add_row(
        ", ".join(profile.source_learning_signal_ids) or "-",
        ", ".join(profile.source_outcome_ids) or "-",
        ", ".join(profile.source_policy_suggestion_ids) or "-",
    )
    return table


def _profile_summary_table(summary: ProfileSummary) -> Table:
    table = Table(title="Profile Summary")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Total profiles", str(summary.total_profiles))
    table.add_row("Draft", str(summary.draft_count))
    table.add_row("Active", str(summary.active_count))
    table.add_row("Archived", str(summary.archived_count))
    table.add_row("Average confidence", f"{summary.average_confidence:.2f}")
    return table


def _profile_application_summary_table(summary: ProfileApplicationSummary) -> Table:
    table = Table(title="Profile Applications Summary")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Profile applications", str(summary.total_applications))
    table.add_row("Applied", str(summary.applied_count))
    for item in summary.applications_by_area:
        table.add_row(f"Area: {item.label}", str(item.count))
    return table
