"""Strategic memory recall helpers."""

from __future__ import annotations

from hephaestus.conversation.schemas import ConversationIntent
from hephaestus.strategic_memory.classifier import (
    strategic_tags_for_intent,
    strategic_types_for_intent,
)
from hephaestus.strategic_memory.repository import StrategicMemoryRepository
from hephaestus.strategic_memory.schemas import StrategicMemoryRecall


def retrieve_strategic_memories(
    query: str,
    intent: ConversationIntent,
    *,
    repository: StrategicMemoryRepository,
    project: str | None,
    repo_profile_id: str | None = None,
    limit: int = 6,
) -> StrategicMemoryRecall:
    """Recall strategic memories by query, intent tags, and strategic types."""

    tags = strategic_tags_for_intent(intent)
    types = strategic_types_for_intent(intent)
    recall = repository.recall(
        query=query,
        tags=tags,
        types=types,
        project=project,
        repo_profile_id=repo_profile_id,
        limit=limit,
        metadata={"intent": intent.value},
    )
    repository.save_recall_event(recall)
    return recall
