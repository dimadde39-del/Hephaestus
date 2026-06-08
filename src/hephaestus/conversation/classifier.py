"""Deterministic conversation intent classifier."""

from __future__ import annotations

from hephaestus.conversation.schemas import ConversationIntent

_INTENT_KEYWORDS: dict[ConversationIntent, tuple[str, ...]] = {
    ConversationIntent.DEBUGGING_DISCUSSION: (
        "bug",
        "debug",
        "failure",
        "failing",
        "error",
        "traceback",
        "broken",
        "regression",
    ),
    ConversationIntent.ARCHITECTURE_DISCUSSION: (
        "architecture",
        "architect",
        "module",
        "boundary",
        "interface",
        "schema",
        "database",
        "system design",
        "abstraction",
    ),
    ConversationIntent.PRODUCT_STRATEGY: (
        "product",
        "users",
        "launch",
        "stars",
        "github stars",
        "20k",
        "positioning",
        "roadmap",
        "alpha",
        "market",
    ),
    ConversationIntent.BUSINESS_STRATEGY: (
        "business",
        "pricing",
        "revenue",
        "funding",
        "go-to-market",
        "monetize",
        "company",
    ),
    ConversationIntent.IDEA_STRESS_TEST: (
        "stress-test",
        "stress test",
        "poke holes",
        "honest",
        "weakness",
        "too abstract",
        "challenge",
        "assumption",
    ),
    ConversationIntent.ROADMAP_DECISION: (
        "roadmap",
        "phase",
        "next phase",
        "prioritize",
        "should we build",
        "sequence",
        "defer",
    ),
    ConversationIntent.RESEARCH_PLANNING: (
        "research",
        "literature",
        "benchmark",
        "compare",
        "study",
        "investigate",
        "unknown",
    ),
    ConversationIntent.RISK_ANALYSIS: (
        "risk",
        "risks",
        "danger",
        "failure mode",
        "what could go wrong",
        "tradeoff",
        "release risk",
    ),
    ConversationIntent.PERSONAL_CONTEXT: (
        "i feel",
        "i'm worried",
        "i am worried",
        "anxious",
        "ambition",
        "motivation",
        "personal",
        "burnout",
    ),
    ConversationIntent.REPO_QUESTION: (
        "repo",
        "repository",
        "codebase",
        "this project",
        "this repo",
        "release risks in this repo",
        "validation",
        "test suite",
    ),
}

_TIE_BREAK_ORDER = [
    ConversationIntent.DEBUGGING_DISCUSSION,
    ConversationIntent.IDEA_STRESS_TEST,
    ConversationIntent.ROADMAP_DECISION,
    ConversationIntent.ARCHITECTURE_DISCUSSION,
    ConversationIntent.PRODUCT_STRATEGY,
    ConversationIntent.BUSINESS_STRATEGY,
    ConversationIntent.RESEARCH_PLANNING,
    ConversationIntent.RISK_ANALYSIS,
    ConversationIntent.REPO_QUESTION,
    ConversationIntent.PERSONAL_CONTEXT,
]


def classify_intent(text: str) -> ConversationIntent:
    """Classify conversation intent with stable keyword scoring."""

    normalized = " ".join(text.lower().split())
    if not normalized:
        return ConversationIntent.GENERAL

    scores: dict[ConversationIntent, int] = {}
    for intent, keywords in _INTENT_KEYWORDS.items():
        score = sum(2 if " " in keyword else 1 for keyword in keywords if keyword in normalized)
        if score:
            scores[intent] = score

    if not scores:
        return ConversationIntent.GENERAL

    def score_key(intent: ConversationIntent) -> tuple[int, int]:
        return (
            scores[intent],
            len(_TIE_BREAK_ORDER) - _TIE_BREAK_ORDER.index(intent)
            if intent in _TIE_BREAK_ORDER
            else 0,
        )

    return max(scores, key=score_key)
