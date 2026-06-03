"""Memory retrieval helpers."""

from __future__ import annotations

from hephaestus.memory.schemas import MemoryItem
from hephaestus.memory.store import InMemoryMemoryStore


def retrieve_relevant_memories(
    store: InMemoryMemoryStore,
    query: str,
    *,
    limit: int = 5,
    project: str | None = None,
) -> list[MemoryItem]:
    """Retrieve the most relevant memories using the Phase 1 lexical scorer."""

    return store.retrieve_top(query, limit=limit, project=project)
