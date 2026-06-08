"""Conservative strategic memory extraction from conversations."""

from __future__ import annotations

from hephaestus.conversation.schemas import ConversationIntent, DeliberationResult
from hephaestus.strategic_memory.classifier import is_potentially_sensitive_personal_context
from hephaestus.strategic_memory.schemas import (
    StrategicMemoryEvidence,
    StrategicMemoryExtractionResult,
    StrategicMemoryItem,
    StrategicMemoryScope,
    StrategicMemorySource,
    StrategicMemoryStability,
    StrategicMemoryType,
)


def extract_strategic_memories(
    prompt: str,
    result: DeliberationResult,
    *,
    project: str,
    repo_profile_id: str | None = None,
    conversation_id: str | None = None,
) -> StrategicMemoryExtractionResult:
    """Suggest strategic memories without saving them."""

    lowered = prompt.lower()
    items: list[StrategicMemoryItem] = []
    sensitive_suggestions: list[str] = []
    evidence = [
        StrategicMemoryEvidence(
            source="conversation_prompt",
            content=_trim_evidence(prompt),
            source_id=conversation_id,
            confidence=0.82,
        )
    ]

    if "20k" in lowered or "20,000" in lowered or "stars" in lowered:
        items.append(
            StrategicMemoryItem(
                type=StrategicMemoryType.AMBITION,
                scope=StrategicMemoryScope.PROJECT,
                project=project,
                repo_profile_id=repo_profile_id,
                conversation_id=conversation_id,
                content="Build Hephaestus toward a 20k-star open-source project.",
                summary="Hephaestus has a 20k-star open-source ambition.",
                evidence=evidence,
                confidence=0.86,
                importance=0.9,
                stability=StrategicMemoryStability.LONG_TERM,
                source=StrategicMemorySource.CONVERSATION_INFERRED,
                tags=["strategy", "open-source", "ambition", "project"],
            )
        )
    if "voice" in lowered and any(word in lowered for word in ("defer", "later", "mature")):
        items.append(
            StrategicMemoryItem(
                type=StrategicMemoryType.ROADMAP_DECISION,
                scope=StrategicMemoryScope.PROJECT,
                project=project,
                repo_profile_id=repo_profile_id,
                conversation_id=conversation_id,
                content="Voice/Jarvis features remain deferred until the core is mature.",
                summary="Voice features are deferred until the core matures.",
                evidence=evidence,
                confidence=0.84,
                importance=0.82,
                stability=StrategicMemoryStability.MEDIUM_TERM,
                source=StrategicMemorySource.CONVERSATION_INFERRED,
                tags=["roadmap", "voice", "constraint"],
            )
        )
    if "not a yes-man" in lowered or "be honest" in lowered or "think several steps ahead" in lowered:
        items.append(
            StrategicMemoryItem(
                type=StrategicMemoryType.PRINCIPLE,
                scope=StrategicMemoryScope.PROJECT,
                project=project,
                repo_profile_id=repo_profile_id,
                conversation_id=conversation_id,
                content=(
                    "Hephaestus should be honest, non-patronizing, useful, and willing "
                    "to challenge weak assumptions without fake contrarianism."
                ),
                summary="Hephaestus should be honest, non-patronizing, and assumption-aware.",
                evidence=evidence,
                confidence=0.82,
                importance=0.84,
                stability=StrategicMemoryStability.LONG_TERM,
                source=StrategicMemorySource.CONVERSATION_INFERRED,
                tags=["principle", "conversation", "honesty", "strategy"],
            )
        )
    if "command execution" in lowered or "execute code" in lowered:
        items.append(
            StrategicMemoryItem(
                type=StrategicMemoryType.ROADMAP_DECISION,
                scope=StrategicMemoryScope.PROJECT,
                project=project,
                repo_profile_id=repo_profile_id,
                conversation_id=conversation_id,
                content=(
                    "Command execution should remain deferred until the core decision-quality "
                    "and memory layers are mature."
                ),
                summary="Command execution is deferred behind core maturity.",
                evidence=evidence,
                confidence=0.76,
                importance=0.76,
                stability=StrategicMemoryStability.MEDIUM_TERM,
                source=StrategicMemorySource.CONVERSATION_INFERRED,
                tags=["roadmap", "execution", "constraint"],
            )
        )
    if result.recommendation and result.intent in _HIGH_IMPACT_INTENTS:
        items.append(
            StrategicMemoryItem(
                type=_decision_type_for_intent(result.intent),
                scope=StrategicMemoryScope.CONVERSATION,
                project=project,
                repo_profile_id=repo_profile_id,
                conversation_id=conversation_id,
                content=f"High-impact discussion recommendation: {result.recommendation}",
                summary=result.recommendation,
                evidence=evidence,
                confidence=result.confidence,
                importance=0.72,
                stability=StrategicMemoryStability.MEDIUM_TERM,
                source=StrategicMemorySource.CONVERSATION_INFERRED,
                tags=["decision", result.intent.value, result.mode.value],
            )
        )
    if result.intent == ConversationIntent.RESEARCH_PLANNING:
        items.append(
            StrategicMemoryItem(
                type=StrategicMemoryType.OPEN_QUESTION,
                scope=StrategicMemoryScope.PROJECT,
                project=project,
                repo_profile_id=repo_profile_id,
                conversation_id=conversation_id,
                content=f"Research question to verify: {prompt}",
                summary="Research question needs external verification.",
                evidence=evidence,
                confidence=0.74,
                importance=0.7,
                stability=StrategicMemoryStability.TEMPORARY,
                source=StrategicMemorySource.CONVERSATION_INFERRED,
                tags=["research", "open-question", result.intent.value],
            )
        )

    if is_potentially_sensitive_personal_context(prompt):
        sensitive_suggestions.append(
            "Prompt contains potentially sensitive personal context; suggestion requires explicit save."
        )

    return StrategicMemoryExtractionResult(
        prompt=prompt,
        items=_dedupe_items(items),
        sensitive_suggestions=sensitive_suggestions,
        requires_explicit_save=True,
        rationale=(
            "Strategic memories are suggested from durable goals, principles, roadmap "
            "boundaries, assumptions, and high-impact recommendations."
        ),
    )


_HIGH_IMPACT_INTENTS: set[ConversationIntent] = {
    ConversationIntent.ARCHITECTURE_DISCUSSION,
    ConversationIntent.PRODUCT_STRATEGY,
    ConversationIntent.BUSINESS_STRATEGY,
    ConversationIntent.IDEA_STRESS_TEST,
    ConversationIntent.ROADMAP_DECISION,
    ConversationIntent.RISK_ANALYSIS,
}


def _decision_type_for_intent(intent: ConversationIntent) -> StrategicMemoryType:
    if intent == ConversationIntent.ROADMAP_DECISION:
        return StrategicMemoryType.ROADMAP_DECISION
    if intent == ConversationIntent.PRODUCT_STRATEGY:
        return StrategicMemoryType.POSITIONING_DECISION
    if intent == ConversationIntent.BUSINESS_STRATEGY:
        return StrategicMemoryType.STRATEGIC_DECISION
    if intent == ConversationIntent.ARCHITECTURE_DISCUSSION:
        return StrategicMemoryType.TECHNICAL_ASSUMPTION
    return StrategicMemoryType.STRATEGIC_DECISION


def _dedupe_items(items: list[StrategicMemoryItem]) -> list[StrategicMemoryItem]:
    seen: set[str] = set()
    deduped: list[StrategicMemoryItem] = []
    for item in items:
        key = f"{item.type.value}:{item.content.lower()}"
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    return deduped


def _trim_evidence(prompt: str, *, max_length: int = 500) -> str:
    normalized = " ".join(prompt.split())
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max_length - 1].rstrip() + "..."
