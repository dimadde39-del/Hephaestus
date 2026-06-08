"""Deterministic helpers for classifying strategic memory."""

from __future__ import annotations

from hephaestus.conversation.schemas import ConversationIntent
from hephaestus.strategic_memory.schemas import StrategicMemoryType


def classify_strategic_memory_type(text: str) -> StrategicMemoryType:
    """Classify one memory sentence into a strategic memory type."""

    normalized = " ".join(text.lower().split())
    for keyword in ("must not", "do not", "defer", "constraint", "boundary"):
        if keyword in normalized:
            return StrategicMemoryType.CONSTRAINT
    for keyword in ("fear", "worried", "worry", "concern", "afraid"):
        if keyword in normalized:
            return StrategicMemoryType.FEAR
    if "rejected" in normalized or "avoid" in normalized or "not pursue" in normalized:
        return StrategicMemoryType.REJECTED_PATH
    if "roadmap" in normalized or "phase" in normalized or "defer" in normalized:
        return StrategicMemoryType.ROADMAP_DECISION
    if "launch" in normalized or "alpha" in normalized:
        return StrategicMemoryType.LAUNCH_DECISION
    if "position" in normalized or "wedge" in normalized or "category" in normalized:
        return StrategicMemoryType.POSITIONING_DECISION
    if "assume" in normalized or "assumption" in normalized:
        if any(word in normalized for word in ("technical", "architecture", "repo", "code")):
            return StrategicMemoryType.TECHNICAL_ASSUMPTION
        return StrategicMemoryType.BUSINESS_ASSUMPTION
    if "prefer" in normalized or "preference" in normalized or "voice" in normalized:
        return StrategicMemoryType.PREFERENCE
    if "principle" in normalized or "should feel" in normalized:
        return StrategicMemoryType.PRINCIPLE
    if "question" in normalized or normalized.endswith("?"):
        return StrategicMemoryType.OPEN_QUESTION
    if "ambition" in normalized or "20k" in normalized or "stars" in normalized:
        return StrategicMemoryType.AMBITION
    if "goal" in normalized or "build toward" in normalized:
        return StrategicMemoryType.GOAL
    return StrategicMemoryType.STRATEGIC_DECISION


def strategic_tags_for_intent(intent: ConversationIntent) -> list[str]:
    """Return recall tags associated with a conversation intent."""

    tags: dict[ConversationIntent, list[str]] = {
        ConversationIntent.ARCHITECTURE_DISCUSSION: ["architecture", "technical", "decision"],
        ConversationIntent.PRODUCT_STRATEGY: ["product", "strategy", "positioning"],
        ConversationIntent.BUSINESS_STRATEGY: ["business", "strategy", "distribution"],
        ConversationIntent.IDEA_STRESS_TEST: ["risk", "strategy", "stress-test"],
        ConversationIntent.ROADMAP_DECISION: ["roadmap", "decision"],
        ConversationIntent.RESEARCH_PLANNING: ["research", "open-question"],
        ConversationIntent.RISK_ANALYSIS: ["risk", "failure-mode"],
        ConversationIntent.DEBUGGING_DISCUSSION: ["technical", "risk"],
        ConversationIntent.REPO_QUESTION: ["repo", "technical", "roadmap"],
        ConversationIntent.PERSONAL_CONTEXT: ["preference"],
        ConversationIntent.GENERAL: [],
    }
    return tags[intent]


def strategic_types_for_intent(intent: ConversationIntent) -> list[StrategicMemoryType]:
    """Return memory types especially useful for an intent."""

    mapping: dict[ConversationIntent, list[StrategicMemoryType]] = {
        ConversationIntent.PRODUCT_STRATEGY: [
            StrategicMemoryType.GOAL,
            StrategicMemoryType.AMBITION,
            StrategicMemoryType.PRINCIPLE,
            StrategicMemoryType.POSITIONING_DECISION,
            StrategicMemoryType.LAUNCH_DECISION,
            StrategicMemoryType.OPEN_QUESTION,
        ],
        ConversationIntent.BUSINESS_STRATEGY: [
            StrategicMemoryType.BUSINESS_ASSUMPTION,
            StrategicMemoryType.POSITIONING_DECISION,
            StrategicMemoryType.CONSTRAINT,
            StrategicMemoryType.RISK_PATTERN,
        ],
        ConversationIntent.IDEA_STRESS_TEST: [
            StrategicMemoryType.AMBITION,
            StrategicMemoryType.FEAR,
            StrategicMemoryType.RISK_PATTERN,
            StrategicMemoryType.REJECTED_PATH,
            StrategicMemoryType.OPEN_QUESTION,
        ],
        ConversationIntent.ROADMAP_DECISION: [
            StrategicMemoryType.ROADMAP_DECISION,
            StrategicMemoryType.CONSTRAINT,
            StrategicMemoryType.REJECTED_PATH,
            StrategicMemoryType.OPEN_QUESTION,
        ],
        ConversationIntent.ARCHITECTURE_DISCUSSION: [
            StrategicMemoryType.TECHNICAL_ASSUMPTION,
            StrategicMemoryType.PRINCIPLE,
            StrategicMemoryType.CONSTRAINT,
            StrategicMemoryType.LESSON_LEARNED,
        ],
        ConversationIntent.RESEARCH_PLANNING: [
            StrategicMemoryType.OPEN_QUESTION,
            StrategicMemoryType.BUSINESS_ASSUMPTION,
            StrategicMemoryType.TECHNICAL_ASSUMPTION,
        ],
        ConversationIntent.RISK_ANALYSIS: [
            StrategicMemoryType.RISK_PATTERN,
            StrategicMemoryType.FEAR,
            StrategicMemoryType.CONSTRAINT,
        ],
    }
    return mapping.get(intent, [])


def is_potentially_sensitive_personal_context(text: str) -> bool:
    """Return true for personal context that should remain suggestion-only by default."""

    normalized = text.lower()
    sensitive_markers = (
        "my address",
        "phone number",
        "medical",
        "health",
        "diagnosis",
        "therapy",
        "family",
        "relationship",
        "religion",
        "political",
        "income",
        "bank",
        "passport",
        "social security",
    )
    return any(marker in normalized for marker in sensitive_markers)
