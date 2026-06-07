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


def pack_context(
    candidates: list[ContextCandidate],
    token_budget: int,
    *,
    preserve_critical_context: bool = True,
    failure_memory_importance_boost: float = 0.0,
    compression_aggressiveness: float = 1.0,
) -> ContextPackResult:
    """Select the highest-value context under a token budget."""

    selected: list[ContextCandidate] = []
    excluded: list[ExcludedContext] = []
    used_tokens = 0

    if preserve_critical_context:
        critical_items = sorted(
            [item for item in candidates if item.critical],
            key=lambda item: (
                item.token_cost,
                -_context_value(
                    item,
                    failure_memory_importance_boost=failure_memory_importance_boost,
                ),
            ),
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
    else:
        remaining = list(candidates)

    selected_ids = {item.id for item in selected}
    ranked_remaining = sorted(
        remaining,
        key=lambda item: (
            _context_density(
                item,
                failure_memory_importance_boost=failure_memory_importance_boost,
                compression_aggressiveness=compression_aggressiveness,
            ),
            _context_value(
                item,
                failure_memory_importance_boost=failure_memory_importance_boost,
            ),
        ),
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

    score = sum(
        _context_value(
            item,
            failure_memory_importance_boost=failure_memory_importance_boost,
        )
        for item in selected
    )
    profile_note = (
        f" Failure-memory boost {failure_memory_importance_boost:.2f}; "
        f"compression aggressiveness {compression_aggressiveness:.2f}."
        if failure_memory_importance_boost > 0 or compression_aggressiveness < 1.0
        else ""
    )
    return ContextPackResult(
        selected=selected,
        excluded=excluded,
        used_tokens=used_tokens,
        score=score,
        explanation=(
            f"Packed {len(selected)} of {len(candidates)} items into {used_tokens}/"
            f"{token_budget} tokens, preserving critical context when it fit."
            f"{profile_note}"
        ),
    )


def _context_value(
    item: ContextCandidate,
    *,
    failure_memory_importance_boost: float = 0.0,
) -> float:
    importance = item.importance
    if _is_failure_memory_context(item):
        importance = min(1.0, importance + failure_memory_importance_boost)
    return item.relevance * 2.0 + importance * 1.5 + (1.0 if item.critical else 0.0)


def _context_density(
    item: ContextCandidate,
    *,
    failure_memory_importance_boost: float = 0.0,
    compression_aggressiveness: float = 1.0,
) -> float:
    value = _context_value(
        item,
        failure_memory_importance_boost=failure_memory_importance_boost,
    )
    low_relevance_penalty = max(0.0, 0.5 - item.relevance) * max(0.0, 1.0 - compression_aggressiveness)
    return max(0.0, value - low_relevance_penalty) / max(1, item.token_cost)


def _is_failure_memory_context(item: ContextCandidate) -> bool:
    metadata = item.metadata
    tags_value = metadata.get("tags", [])
    tags = {str(tag).lower() for tag in tags_value} if isinstance(tags_value, list) else set()
    memory_type = str(metadata.get("memory_type", "")).lower()
    return item.id.lower().startswith("failure") or memory_type == "failure" or "failure" in tags
