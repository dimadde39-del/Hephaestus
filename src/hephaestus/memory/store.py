"""In-memory repository for Phase 1."""

from __future__ import annotations

import builtins
from collections.abc import Iterable

from hephaestus.memory.schemas import MemoryItem


class InMemoryMemoryStore:
    """A small repository that can later be swapped for SQLite/vector storage."""

    def __init__(self, initial_items: Iterable[MemoryItem] | None = None) -> None:
        self._items: dict[str, MemoryItem] = {}
        for item in initial_items or []:
            self.add(item)

    def add(self, item: MemoryItem) -> MemoryItem:
        self._items[item.id] = item
        return item

    def list(self, project: str | None = None) -> builtins.list[MemoryItem]:
        items = list(self._items.values())
        if project is not None:
            items = [item for item in items if item.project == project]
        return sorted(items, key=lambda item: item.created_at)

    def search(
        self,
        query: str = "",
        *,
        tags: Iterable[str] | None = None,
        project: str | None = None,
    ) -> builtins.list[MemoryItem]:
        query_terms = _terms(query)
        required_tags = {tag.lower() for tag in tags or []}
        matches: builtins.list[MemoryItem] = []
        for item in self.list(project=project):
            if required_tags and not required_tags.issubset(set(item.tags)):
                continue
            text = item.searchable_text
            if query_terms and not all(term in text for term in query_terms):
                continue
            matches.append(item)
        return matches

    def retrieve_top(
        self,
        query: str,
        *,
        limit: int = 5,
        tags: Iterable[str] | None = None,
        project: str | None = None,
    ) -> builtins.list[MemoryItem]:
        candidates = self.search("", tags=tags, project=project)
        scored = [(score_memory(item, query), item) for item in candidates]
        ranked = sorted(scored, key=lambda pair: pair[0], reverse=True)
        return [item for score, item in ranked[:limit] if score > 0]


def score_memory(item: MemoryItem, query: str) -> float:
    """Simple lexical relevance plus confidence/importance scoring."""

    terms = _terms(query)
    if not terms:
        return item.importance + item.confidence
    text = item.searchable_text
    content_hits = sum(1 for term in terms if term in text)
    tag_hits = sum(1 for term in terms if term in item.tags)
    return content_hits * 1.5 + tag_hits * 2.5 + item.importance * 1.2 + item.confidence * 0.8


def _terms(query: str) -> builtins.list[str]:
    return [part.lower() for part in query.split() if part.strip()]
