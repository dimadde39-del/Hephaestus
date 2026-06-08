"""Discussion quality rubrics."""

from __future__ import annotations

from hephaestus.conversation.schemas import ConversationIntent, DeliberationMode
from hephaestus.discussion_quality.schemas import (
    DiscussionRubric,
    DiscussionType,
    RubricCheck,
)


def list_rubrics() -> list[DiscussionRubric]:
    """Return all built-in discussion rubrics."""

    return list(_RUBRICS.values())


def get_rubric(discussion_type: DiscussionType) -> DiscussionRubric:
    """Return a rubric by type."""

    return _RUBRICS.get(discussion_type, _RUBRICS[DiscussionType.GENERAL])


def discussion_type_for_intent(
    intent: ConversationIntent,
    mode: DeliberationMode,
) -> DiscussionType:
    """Map conversation intent/mode to a discussion rubric."""

    if mode == DeliberationMode.RESEARCH or intent == ConversationIntent.RESEARCH_PLANNING:
        return DiscussionType.RESEARCH_PLANNING
    mapping: dict[ConversationIntent, DiscussionType] = {
        ConversationIntent.IDEA_STRESS_TEST: DiscussionType.IDEA_STRESS_TEST,
        ConversationIntent.BUSINESS_STRATEGY: DiscussionType.BUSINESS_STRATEGY,
        ConversationIntent.PRODUCT_STRATEGY: DiscussionType.PRODUCT_STRATEGY,
        ConversationIntent.ARCHITECTURE_DISCUSSION: DiscussionType.TECHNICAL_ARCHITECTURE,
        ConversationIntent.ROADMAP_DECISION: DiscussionType.ROADMAP_DECISION,
        ConversationIntent.RISK_ANALYSIS: DiscussionType.RISK_ANALYSIS,
        ConversationIntent.REPO_QUESTION: DiscussionType.TECHNICAL_ARCHITECTURE,
    }
    return mapping.get(intent, DiscussionType.GENERAL)


def _checks(items: list[tuple[str, str, str]]) -> list[RubricCheck]:
    return [RubricCheck(key=key, label=label, description=description) for key, label, description in items]


_RUBRICS: dict[DiscussionType, DiscussionRubric] = {
    DiscussionType.IDEA_STRESS_TEST: DiscussionRubric(
        discussion_type=DiscussionType.IDEA_STRESS_TEST,
        name="Idea Stress Test",
        expected_checks=_checks(
            [
                ("strongest_argument_for", "Strongest argument for", "Name why the idea might work."),
                (
                    "strongest_argument_against",
                    "Strongest argument against",
                    "Name the best objection, not a strawman.",
                ),
                ("hidden_assumptions", "Hidden assumptions", "Expose premises that may be wrong."),
                ("failure_modes", "Failure modes", "Identify concrete ways the idea could fail."),
                ("cheap_validation_test", "Cheap validation test", "Suggest the smallest useful test."),
                (
                    "change_recommendation",
                    "What would change the recommendation",
                    "Define decision-changing evidence.",
                ),
                ("next_best_move", "Next best move", "Give a practical next action."),
            ]
        ),
    ),
    DiscussionType.BUSINESS_STRATEGY: DiscussionRubric(
        discussion_type=DiscussionType.BUSINESS_STRATEGY,
        name="Business Strategy",
        expected_checks=_checks(
            [
                ("customer", "Customer", "Identify who has the problem."),
                ("pain", "Pain", "Explain the painful job or unmet need."),
                ("distribution", "Distribution", "Consider how users will find it."),
                ("competition", "Competition", "Compare alternatives and incumbents."),
                ("unit_economics", "Unit economics", "Consider cost, pricing, or leverage."),
                (
                    "operational_complexity",
                    "Operational complexity",
                    "Name operational burdens or scaling issues.",
                ),
                ("regulatory_risk", "Regulatory risk", "Check regulatory or compliance exposure."),
                ("proof_plan", "Proof plan", "Define evidence needed before commitment."),
            ]
        ),
    ),
    DiscussionType.PRODUCT_STRATEGY: DiscussionRubric(
        discussion_type=DiscussionType.PRODUCT_STRATEGY,
        name="Product Strategy",
        expected_checks=_checks(
            [
                ("user", "User", "Identify the target user."),
                ("wedge", "Wedge", "Clarify the initial compelling use case."),
                ("positioning", "Positioning", "Name the category and contrast."),
                ("activation", "Activation", "Explain the first moment of value."),
                ("retention", "Retention", "Explain why users return."),
                ("proof_plan", "Proof plan", "Define what proves the product claim."),
                ("roadmap_tradeoff", "Roadmap tradeoff", "Connect sequencing to strategy."),
            ]
        ),
    ),
    DiscussionType.TECHNICAL_ARCHITECTURE: DiscussionRubric(
        discussion_type=DiscussionType.TECHNICAL_ARCHITECTURE,
        name="Technical Architecture",
        expected_checks=_checks(
            [
                ("requirements", "Requirements", "State what the architecture must satisfy."),
                ("constraints", "Constraints", "Name boundaries and non-goals."),
                ("failure_modes", "Failure modes", "Identify what breaks or degrades."),
                ("complexity_risk", "Complexity risk", "Avoid unnecessary abstraction."),
                ("maintainability", "Maintainability", "Consider future change and ownership."),
                ("testability", "Testability", "Plan how behavior will be verified."),
                ("migration_path", "Migration path", "Show how to evolve safely."),
                ("observability", "Observability", "Expose how failures become visible."),
            ]
        ),
    ),
    DiscussionType.ROADMAP_DECISION: DiscussionRubric(
        discussion_type=DiscussionType.ROADMAP_DECISION,
        name="Roadmap Decision",
        expected_checks=_checks(
            [
                ("goal", "Goal", "Connect the decision to the larger goal."),
                ("sequence", "Sequence", "Explain why now or later."),
                ("dependencies", "Dependencies", "Name prerequisites."),
                ("opportunity_cost", "Opportunity cost", "Name what gets delayed."),
                ("risk", "Risk", "Identify downside and uncertainty."),
                ("validation", "Validation", "Define the proof point."),
                ("next_move", "Next move", "Give the next decision or action."),
            ]
        ),
    ),
    DiscussionType.RESEARCH_PLANNING: DiscussionRubric(
        discussion_type=DiscussionType.RESEARCH_PLANNING,
        name="Research Planning",
        expected_checks=_checks(
            [
                ("claims_to_verify", "Claims to verify", "List what needs evidence."),
                ("likely_sources", "Likely sources", "Name source categories."),
                ("search_queries", "Search queries", "Prepare concrete search strings."),
                (
                    "evidence_quality",
                    "Evidence quality expectations",
                    "Define what counts as good evidence.",
                ),
                (
                    "change_conclusion",
                    "What would change the conclusion",
                    "Name disconfirming evidence.",
                ),
                ("shallow_research_risk", "Risk of shallow research", "Warn against weak evidence."),
            ]
        ),
    ),
    DiscussionType.RISK_ANALYSIS: DiscussionRubric(
        discussion_type=DiscussionType.RISK_ANALYSIS,
        name="Risk Analysis",
        expected_checks=_checks(
            [
                ("asset_or_goal", "Asset or goal", "Name what is at risk."),
                ("threats", "Threats", "Identify plausible threats or failures."),
                ("likelihood", "Likelihood", "Estimate likelihood qualitatively."),
                ("impact", "Impact", "Estimate severity."),
                ("mitigations", "Mitigations", "Suggest practical mitigations."),
                ("tripwires", "Tripwires", "Define early warning signs."),
                ("residual_risk", "Residual risk", "Name what remains uncertain."),
            ]
        ),
    ),
    DiscussionType.GENERAL: DiscussionRubric(
        discussion_type=DiscussionType.GENERAL,
        name="General Useful Discussion",
        expected_checks=_checks(
            [
                ("answer", "Answer", "Address the question directly."),
                ("assumptions", "Assumptions", "Name key assumptions."),
                ("uncertainty", "Uncertainty", "Name missing information."),
                ("next_move", "Next move", "Suggest a useful next move."),
            ]
        ),
    ),
}
