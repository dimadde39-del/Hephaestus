"""Deterministic discussion quality evaluation and research planning."""

from __future__ import annotations

from hephaestus.conversation.schemas import ConversationIntent, DeliberationMode
from hephaestus.discussion_quality.rubrics import discussion_type_for_intent, get_rubric
from hephaestus.discussion_quality.schemas import (
    DiscussionQualityCheckResult,
    DiscussionQualityEvaluation,
    ResearchPlan,
)


def evaluate_discussion_quality(
    *,
    intent: ConversationIntent,
    mode: DeliberationMode,
    assumptions: list[str],
    options: list[str],
    risks: list[str],
    tradeoffs: list[str],
    missing_information: list[str],
    recommendation: str,
    next_moves: list[str],
    research_plan: ResearchPlan | None = None,
) -> DiscussionQualityEvaluation:
    """Evaluate a discussion result against its rubric."""

    discussion_type = discussion_type_for_intent(intent, mode)
    rubric = get_rubric(discussion_type)
    evidence_by_key = _evidence_map(
        assumptions=assumptions,
        options=options,
        risks=risks,
        tradeoffs=tradeoffs,
        missing_information=missing_information,
        recommendation=recommendation,
        next_moves=next_moves,
        research_plan=research_plan,
    )
    checks: list[DiscussionQualityCheckResult] = []
    for expected in rubric.expected_checks:
        evidence = evidence_by_key.get(expected.key, "")
        checks.append(
            DiscussionQualityCheckResult(
                key=expected.key,
                label=expected.label,
                satisfied=bool(evidence),
                evidence=evidence,
            )
        )
    satisfied = sum(1 for check in checks if check.satisfied)
    score = satisfied / len(checks) if checks else 1.0
    missing = [check.label for check in checks if not check.satisfied]
    return DiscussionQualityEvaluation(
        discussion_type=discussion_type,
        rubric_name=rubric.name,
        checks=checks,
        score=score,
        missing_checks=missing,
        summary=(
            f"{rubric.name}: {satisfied}/{len(checks)} expected checks satisfied."
            if checks
            else f"{rubric.name}: no checks defined."
        ),
    )


def build_research_plan(
    prompt: str,
    *,
    intent: ConversationIntent,
    missing_information: list[str],
    risks: list[str],
) -> ResearchPlan:
    """Build a research plan without claiming current external facts."""

    normalized = " ".join(prompt.split())
    question = normalized or "Research question"
    core_topic = _topic_fragment(question)
    needs = [
        *missing_information,
        "Current external facts, comparable projects, and user expectations need verification.",
    ]
    likely_sources = [
        "Primary project repositories and documentation",
        "Release notes, benchmark reports, and architecture docs",
        "User discussions, issue trackers, and adoption signals",
        "Independent technical comparisons where available",
    ]
    if intent == ConversationIntent.BUSINESS_STRATEGY:
        likely_sources.extend(["Pricing pages", "Customer interviews", "Market reports"])
    search_queries = [
        f"{core_topic} open source agent framework comparison",
        f"{core_topic} architecture documentation decision traces memory",
        f"{core_topic} GitHub issues user pain points",
        f"{core_topic} benchmarks evaluations limitations",
    ]
    return ResearchPlan(
        question=question,
        needs_verification=_dedupe(needs),
        likely_sources=_dedupe(likely_sources),
        search_queries=_dedupe(search_queries),
        evidence_quality_expectations=[
            "Prefer primary sources for claims about project capabilities.",
            "Separate current facts from marketing language and old release notes.",
            "Record dates because agent-framework capabilities change quickly.",
            "Treat anecdotal user comments as signals, not proof.",
        ],
        what_would_change_conclusion=[
            "A direct competitor already owns the same positioning with stronger proof.",
            "Users consistently reject the scoped execution and approval boundary.",
            "Primary docs show capabilities that make the proposed wedge less distinctive.",
            "Benchmark evidence contradicts the claimed decision-quality advantage.",
        ],
        shallow_research_risks=[
            "Mistaking README claims for verified capabilities.",
            "Comparing stale versions of fast-moving projects.",
            "Overweighting GitHub stars without checking usage, issues, and demos.",
            *risks[:2],
        ],
    )


def _evidence_map(
    *,
    assumptions: list[str],
    options: list[str],
    risks: list[str],
    tradeoffs: list[str],
    missing_information: list[str],
    recommendation: str,
    next_moves: list[str],
    research_plan: ResearchPlan | None,
) -> dict[str, str]:
    support = options[0] if options else recommendation
    objection = risks[0] if risks else ""
    validation = _first_containing(next_moves, ("validate", "proof", "test", "research"))
    change = (
        research_plan.what_would_change_conclusion[0]
        if research_plan is not None and research_plan.what_would_change_conclusion
        else (missing_information[0] if missing_information else "")
    )
    sources = (
        research_plan.likely_sources[0]
        if research_plan is not None and research_plan.likely_sources
        else ""
    )
    queries = (
        research_plan.search_queries[0] if research_plan is not None and research_plan.search_queries else ""
    )
    evidence_quality = (
        research_plan.evidence_quality_expectations[0]
        if research_plan is not None and research_plan.evidence_quality_expectations
        else ""
    )
    shallow_risk = (
        research_plan.shallow_research_risks[0]
        if research_plan is not None and research_plan.shallow_research_risks
        else ""
    )
    return {
        "strongest_argument_for": support,
        "strongest_argument_against": objection,
        "hidden_assumptions": assumptions[0] if assumptions else "",
        "failure_modes": objection,
        "cheap_validation_test": validation,
        "change_recommendation": change,
        "next_best_move": next_moves[0] if next_moves else "",
        "customer": _first_containing(missing_information + assumptions, ("customer", "audience", "user")),
        "pain": _first_containing(risks + assumptions, ("pain", "problem", "expect")),
        "distribution": _first_containing(missing_information + next_moves, ("distribution", "channel", "launch")),
        "competition": _first_containing(missing_information + tradeoffs, ("competition", "competitor", "alternative")),
        "unit_economics": _first_containing(missing_information + risks, ("cost", "pricing", "economics")),
        "operational_complexity": _first_containing(risks + tradeoffs, ("operational", "complexity", "scale")),
        "regulatory_risk": _first_containing(risks + missing_information, ("regulatory", "compliance")),
        "proof_plan": validation or change,
        "user": _first_containing(missing_information + assumptions, ("user", "audience", "customer")),
        "wedge": _first_containing(options + recommendation.splitlines(), ("wedge", "decision", "proof")),
        "positioning": _first_containing(options + assumptions, ("position", "category", "story")),
        "activation": _first_containing(next_moves + risks, ("demo", "value", "activation")),
        "retention": _first_containing(risks + missing_information, ("return", "retention", "repeated")),
        "roadmap_tradeoff": tradeoffs[0] if tradeoffs else "",
        "requirements": assumptions[0] if assumptions else "",
        "constraints": _first_containing(assumptions + risks, ("constraint", "boundary", "must")),
        "complexity_risk": _first_containing(risks + tradeoffs, ("complex", "abstraction", "broad")),
        "maintainability": _first_containing(tradeoffs + next_moves, ("maintain", "boundary", "module")),
        "testability": validation,
        "migration_path": _first_containing(next_moves + options, ("later", "phase", "evolve", "migration")),
        "observability": _first_containing(next_moves + risks, ("trace", "visible", "observe", "signal")),
        "goal": _first_containing(assumptions + recommendation.splitlines(), ("goal", "ambition", "stars")),
        "sequence": _first_containing(tradeoffs + next_moves, ("early", "waiting", "before", "after")),
        "dependencies": _first_containing(missing_information + next_moves, ("prerequisite", "depends", "before")),
        "opportunity_cost": _first_containing(tradeoffs, ("delay", "cost", "waiting")),
        "risk": objection,
        "validation": validation,
        "next_move": next_moves[0] if next_moves else "",
        "claims_to_verify": research_plan.needs_verification[0] if research_plan else "",
        "likely_sources": sources,
        "search_queries": queries,
        "evidence_quality": evidence_quality,
        "change_conclusion": change,
        "shallow_research_risk": shallow_risk,
        "asset_or_goal": recommendation,
        "threats": objection,
        "likelihood": _first_containing(risks, ("may", "could", "likely", "expect")),
        "impact": _first_containing(risks, ("risk", "fail", "dilute", "burden")),
        "mitigations": next_moves[0] if next_moves else "",
        "tripwires": _first_containing(next_moves + missing_information, ("signal", "objection", "review")),
        "residual_risk": missing_information[0] if missing_information else "",
        "answer": recommendation,
        "assumptions": assumptions[0] if assumptions else "",
        "uncertainty": missing_information[0] if missing_information else "",
    }


def _first_containing(values: list[str], needles: tuple[str, ...]) -> str:
    for value in values:
        lowered = value.lower()
        if any(needle in lowered for needle in needles):
            return value
    return values[0] if values else ""


def _topic_fragment(question: str) -> str:
    words = [part.strip(".,:;!?()[]{}").lower() for part in question.split()]
    stop = {"the", "and", "for", "with", "before", "should", "compare", "research", "plan"}
    useful = [word for word in words if len(word) > 2 and word not in stop]
    return " ".join(useful[:6]) or "agent framework"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
    return deduped
