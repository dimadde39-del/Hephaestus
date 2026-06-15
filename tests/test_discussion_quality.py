from hephaestus.conversation import ConversationIntent, DeliberationMode
from hephaestus.discussion_quality.evaluator import build_research_plan, evaluate_discussion_quality
from hephaestus.discussion_quality.rubrics import get_rubric
from hephaestus.discussion_quality.schemas import DiscussionType


def test_discussion_rubric_validation() -> None:
    idea = get_rubric(DiscussionType.IDEA_STRESS_TEST)
    business = get_rubric(DiscussionType.BUSINESS_STRATEGY)
    architecture = get_rubric(DiscussionType.TECHNICAL_ARCHITECTURE)

    assert "strongest_argument_for" in idea.expected_keys
    assert "unit_economics" in business.expected_keys
    assert "migration_path" in architecture.expected_keys


def test_idea_stress_test_rubric_output() -> None:
    evaluation = evaluate_discussion_quality(
        intent=ConversationIntent.IDEA_STRESS_TEST,
        mode=DeliberationMode.STRATEGIC,
        assumptions=["The demo can make the scoped execution boundary clear."],
        options=["Launch a narrow proof around the self-improving agent loop."],
        risks=["Users may expect command execution and reject the alpha."],
        tradeoffs=["Launching early gets feedback but raises clarity burden."],
        missing_information=["Need user reaction to a scoped execution demo."],
        recommendation="Launch only with explicit positioning.",
        next_moves=["Run a cheap validation test with the README and demo script."],
    )

    assert evaluation.discussion_type == DiscussionType.IDEA_STRESS_TEST
    assert evaluation.score >= 0.85
    assert not evaluation.missing_checks


def test_business_strategy_rubric_output() -> None:
    evaluation = evaluate_discussion_quality(
        intent=ConversationIntent.BUSINESS_STRATEGY,
        mode=DeliberationMode.STRATEGIC,
        assumptions=["Target customer and user audience are open-source agent builders."],
        options=["Validate customer pain and distribution before pricing."],
        risks=[
            "Operational complexity and regulatory compliance risk are unknown.",
            "Pricing and unit economics need proof.",
        ],
        tradeoffs=["Competition and alternative frameworks may already own the category."],
        missing_information=[
            "Customer, pain, distribution channel, competition, unit economics, and regulatory risk are not validated."
        ],
        recommendation="Validate the business story before widening scope.",
        next_moves=["Create a proof plan with interviews and adoption signals."],
    )

    assert evaluation.discussion_type == DiscussionType.BUSINESS_STRATEGY
    assert evaluation.score >= 0.75
    assert "Business Strategy" in evaluation.summary


def test_research_plan_schema_output() -> None:
    plan = build_research_plan(
        "Research plan: compare Hephaestus positioning against agent frameworks.",
        intent=ConversationIntent.RESEARCH_PLANNING,
        missing_information=["Comparable projects and current capabilities are unknown."],
        risks=["README claims may overstate capabilities."],
    )

    assert plan.needs_verification
    assert plan.search_queries
    assert "primary sources" in " ".join(plan.evidence_quality_expectations).lower()
