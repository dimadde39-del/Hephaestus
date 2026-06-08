"""Analysis helpers for strategic memory."""

from __future__ import annotations

from collections import defaultdict

from hephaestus.strategic_memory.schemas import (
    StrategicMemoryItem,
    StrategicMemoryType,
)

CONTEXT_TYPES: tuple[StrategicMemoryType, ...] = (
    StrategicMemoryType.GOAL,
    StrategicMemoryType.AMBITION,
    StrategicMemoryType.PRINCIPLE,
    StrategicMemoryType.CONSTRAINT,
    StrategicMemoryType.ROADMAP_DECISION,
    StrategicMemoryType.STRATEGIC_DECISION,
    StrategicMemoryType.REJECTED_PATH,
    StrategicMemoryType.OPEN_QUESTION,
)


def group_memories_by_type(
    memories: list[StrategicMemoryItem],
) -> dict[StrategicMemoryType, list[StrategicMemoryItem]]:
    """Group active memories by type, ordered by importance."""

    grouped: dict[StrategicMemoryType, list[StrategicMemoryItem]] = defaultdict(list)
    for memory in memories:
        grouped[memory.type].append(memory)
    return {
        memory_type: sorted(items, key=lambda item: item.importance, reverse=True)
        for memory_type, items in grouped.items()
    }


def select_strategic_context(
    memories: list[StrategicMemoryItem],
    *,
    per_type: int = 5,
) -> dict[StrategicMemoryType, list[StrategicMemoryItem]]:
    """Select the long-term context shown by `heph strategy context`."""

    grouped = group_memories_by_type([memory for memory in memories if memory.archived_at is None])
    return {
        memory_type: grouped.get(memory_type, [])[:per_type]
        for memory_type in CONTEXT_TYPES
        if grouped.get(memory_type)
    }


def strategic_context_summary(memories: list[StrategicMemoryItem]) -> str:
    """Return a compact plain text summary of strategic context."""

    grouped = select_strategic_context(memories, per_type=3)
    lines: list[str] = []
    for memory_type, items in grouped.items():
        label = memory_type.value.replace("_", " ").title()
        lines.append(f"{label}:")
        for item in items:
            lines.append(f"- {item.summary or item.content}")
    return "\n".join(lines) if lines else "No strategic context saved yet."


def normalize_conflict_text(text: str) -> set[str]:
    """Normalize text into rough semantic terms for conflict checks."""

    return {
        part.strip(".,:;!?()[]{}\"'").lower()
        for part in text.split()
        if len(part.strip(".,:;!?()[]{}\"'")) >= 3
    }
