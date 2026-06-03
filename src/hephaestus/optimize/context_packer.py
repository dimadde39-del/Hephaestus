"""Context packing optimizer."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ContextCandidate(BaseModel):
    """A possible context item for a model call."""

    model_config = ConfigDict(frozen=True)

    id: str
    content: str = ""
    relevance: float = Field(ge=0, le=1)
    importance: float = Field(ge=0, le=1)
    token_cost: int = Field(ge=0)
    critical: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExcludedContext(BaseModel):
    id: str
    reason: str


class ContextPackResult(BaseModel):
    selected: list[ContextCandidate]
    excluded: list[ExcludedContext]
    used_tokens: int = Field(ge=0)
    score: float
    explanation: str


def pack_context(candidates: list[ContextCandidate], token_budget: int) -> ContextPackResult:
    """Select the highest-value context under a token budget."""

    selected: list[ContextCandidate] = []
    excluded: list[ExcludedContext] = []
    used_tokens = 0

    critical_items = sorted(
        [item for item in candidates if item.critical],
        key=lambda item: (item.token_cost, -_context_value(item)),
    )
    remaining = [item for item in candidates if not item.critical]

    for item in critical_items:
        if used_tokens + item.token_cost <= token_budget:
            selected.append(item)
            used_tokens += item.token_cost
        else:
            excluded.append(
                ExcludedContext(id=item.id, reason="critical item did not fit token budget")
            )

    selected_ids = {item.id for item in selected}
    ranked_remaining = sorted(
        remaining,
        key=lambda item: (_context_density(item), _context_value(item)),
        reverse=True,
    )
    for item in ranked_remaining:
        if item.id in selected_ids:
            continue
        if used_tokens + item.token_cost <= token_budget:
            selected.append(item)
            selected_ids.add(item.id)
            used_tokens += item.token_cost
        else:
            excluded.append(ExcludedContext(id=item.id, reason="lower value than packed context"))

    score = sum(_context_value(item) for item in selected)
    return ContextPackResult(
        selected=selected,
        excluded=excluded,
        used_tokens=used_tokens,
        score=score,
        explanation=(
            f"Packed {len(selected)} of {len(candidates)} items into {used_tokens}/"
            f"{token_budget} tokens, preserving critical context when it fit."
        ),
    )


def _context_value(item: ContextCandidate) -> float:
    return item.relevance * 2.0 + item.importance * 1.5 + (1.0 if item.critical else 0.0)


def _context_density(item: ContextCandidate) -> float:
    return _context_value(item) / max(1, item.token_cost)
