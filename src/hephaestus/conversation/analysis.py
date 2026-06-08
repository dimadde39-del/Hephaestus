"""Analysis helpers for conversation deliberation and traces."""

from __future__ import annotations

import re

from hephaestus.conversation.schemas import (
    ConversationDecisionTrace,
    ConversationIntent,
    ConversationMemoryCandidate,
    DeliberationResult,
)
from hephaestus.decision import DecisionAlternative, OptimizationDecision, metric
from hephaestus.memory import MemoryType

HIGH_IMPACT_INTENTS: set[ConversationIntent] = {
    ConversationIntent.ARCHITECTURE_DISCUSSION,
    ConversationIntent.PRODUCT_STRATEGY,
    ConversationIntent.BUSINESS_STRATEGY,
    ConversationIntent.IDEA_STRESS_TEST,
    ConversationIntent.ROADMAP_DECISION,
}


def title_from_prompt(prompt: str, *, max_length: int = 72) -> str:
    """Create a stable human title for a conversation session."""

    normalized = " ".join(prompt.split())
    if len(normalized) <= max_length:
        return normalized or "Conversation"
    return normalized[: max_length - 1].rstrip() + "..."


def should_create_decision_trace(intent: ConversationIntent) -> bool:
    """Return whether a discussion should be traceable as a decision-quality artifact."""

    return intent in HIGH_IMPACT_INTENTS


def propose_memory_candidates(
    prompt: str,
    result: DeliberationResult,
    *,
    project: str,
) -> list[ConversationMemoryCandidate]:
    """Suggest conservative durable memories from user context and recommendations."""

    candidates: list[ConversationMemoryCandidate] = []
    lowered = prompt.lower()
    if "20k" in lowered or "20,000" in lowered or "stars" in lowered:
        candidates.append(
            ConversationMemoryCandidate(
                memory_type=MemoryType.PROJECT,
                content="Project ambition: build Hephaestus toward a 20k-star open-source project.",
                summary="Hephaestus aims for 20k GitHub stars.",
                tags=["project", "strategy", "open-source", "goal"],
                project=project,
                confidence=0.84,
                importance=0.86,
                rationale="The user stated or revisited a durable project ambition.",
            )
        )
    if "voice" in lowered and ("defer" in lowered or "later" in lowered or "mature" in lowered):
        candidates.append(
            ConversationMemoryCandidate(
                memory_type=MemoryType.DECISION,
                content="Voice/Jarvis features are deferred until the Hephaestus core is mature.",
                summary="Voice features are deferred.",
                tags=["roadmap", "decision", "voice"],
                project=project,
                confidence=0.8,
                importance=0.78,
                rationale="The prompt reinforced a roadmap boundary.",
            )
        )
    if "honest" in lowered or "not a yes-man" in lowered or "think several steps ahead" in lowered:
        candidates.append(
            ConversationMemoryCandidate(
                memory_type=MemoryType.PROCEDURAL,
                content=(
                    "The user prefers honest, non-patronizing strategic reasoning that "
                    "challenges weak assumptions when useful."
                ),
                summary="User prefers honest strategic reasoning.",
                tags=["preference", "conversation", "strategy"],
                project=project,
                confidence=0.78,
                importance=0.76,
                rationale="The prompt contains a stable interaction preference.",
            )
        )
    if result.recommendation and result.intent in HIGH_IMPACT_INTENTS:
        candidates.append(
            ConversationMemoryCandidate(
                memory_type=MemoryType.DECISION,
                content=f"Conversation recommendation: {result.recommendation}",
                summary="Conversation produced a high-impact recommendation.",
                tags=["decision", result.intent.value, result.mode.value],
                project=project,
                confidence=result.confidence,
                importance=0.72,
                rationale="High-impact conversations can become reviewable decision memory.",
            )
        )
    return _dedupe_candidates(candidates)


def build_conversation_decision_trace(
    session_id: str,
    result: DeliberationResult,
) -> ConversationDecisionTrace:
    """Create the conversation-facing decision trace summary."""

    return ConversationDecisionTrace(
        session_id=session_id,
        intent=result.intent,
        mode=result.mode,
        key_assumptions=result.assumptions[:6],
        options_considered=result.options[:6],
        recommendation=result.recommendation or "No strong recommendation.",
        confidence=result.confidence,
        suggested_next_move=result.next_moves[0] if result.next_moves else "",
    )


def build_persisted_decision_trace(
    run_id: str,
    summary: ConversationDecisionTrace,
) -> OptimizationDecision:
    """Represent a high-impact conversation as an optimization decision trace."""

    return OptimizationDecision(
        run_id=run_id,
        phase="conversation",
        selected_option=summary.recommendation,
        alternatives=[
            DecisionAlternative(
                option_id=f"option_{index}",
                option_name=option,
                rejection_reason="Considered during conversation deliberation.",
            )
            for index, option in enumerate(summary.options_considered, start=1)
        ],
        rationale=summary.recommendation,
        metrics=[
            metric("conversation_confidence", summary.confidence),
            metric("assumption_count", len(summary.key_assumptions)),
            metric("option_count", len(summary.options_considered)),
            metric("intent", summary.intent.value),
            metric("mode", summary.mode.value),
        ],
        objective_score=summary.confidence,
        confidence=summary.confidence,
        constraints_considered=[
            "honesty",
            "non-patronizing usefulness",
            "uncertainty",
            "decision quality",
        ],
        tags=["conversation", summary.intent.value, summary.mode.value],
        caused_by=[summary.session_id],
        will_affect=["memory_updates", "roadmap_reasoning", "future_discussions"],
        learning_hooks=["conversation_outcome", "strategic_recommendation_quality"],
    )


def extract_question_terms(prompt: str) -> list[str]:
    """Return compact content terms for deterministic synthesis."""

    words = re.findall(r"[a-zA-Z0-9][a-zA-Z0-9_-]{2,}", prompt.lower())
    stop = {
        "the",
        "and",
        "for",
        "that",
        "this",
        "with",
        "what",
        "want",
        "about",
        "before",
        "because",
        "should",
    }
    return [word for word in words if word not in stop][:12]


def _dedupe_candidates(
    candidates: list[ConversationMemoryCandidate],
) -> list[ConversationMemoryCandidate]:
    seen: set[str] = set()
    deduped: list[ConversationMemoryCandidate] = []
    for candidate in candidates:
        key = candidate.content.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(candidate)
    return deduped
