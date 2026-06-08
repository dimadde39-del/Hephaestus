"""Context retrieval for conversational turns."""

from __future__ import annotations

from pathlib import Path

from hephaestus.conversation.schemas import (
    ConversationContextItem,
    ConversationIntent,
    ConversationRequest,
    RetrievedConversationContext,
)
from hephaestus.memory.schemas import MemoryItem
from hephaestus.repo import (
    RepoProfile,
    RepoProfileRepository,
    inspect_repository,
    repo_stack_summary,
    risk_summary,
    validation_summary,
)
from hephaestus.storage import SqliteMemoryRepository

_INTENT_TAGS: dict[ConversationIntent, tuple[str, ...]] = {
    ConversationIntent.ARCHITECTURE_DISCUSSION: ("architecture", "decision"),
    ConversationIntent.PRODUCT_STRATEGY: ("product", "strategy", "roadmap"),
    ConversationIntent.BUSINESS_STRATEGY: ("business", "strategy"),
    ConversationIntent.IDEA_STRESS_TEST: ("risk", "strategy", "decision"),
    ConversationIntent.ROADMAP_DECISION: ("roadmap", "decision"),
    ConversationIntent.RESEARCH_PLANNING: ("research", "planning"),
    ConversationIntent.RISK_ANALYSIS: ("risk", "failure"),
    ConversationIntent.PERSONAL_CONTEXT: ("preference", "personal"),
    ConversationIntent.DEBUGGING_DISCUSSION: ("failure", "debugging"),
    ConversationIntent.REPO_QUESTION: ("repo", "project", "release"),
    ConversationIntent.GENERAL: (),
}


def retrieve_conversation_context(
    request: ConversationRequest,
    intent: ConversationIntent,
    *,
    memory_repository: SqliteMemoryRepository,
    repo_repository: RepoProfileRepository,
    memory_limit: int = 6,
) -> RetrievedConversationContext:
    """Retrieve relevant memory and optional repo context for one turn."""

    memories: list[MemoryItem] = []
    if request.use_memory:
        memories = _retrieve_memories(
            memory_repository,
            request.prompt,
            intent,
            project=request.project,
            limit=memory_limit,
        )

    repo_profile = _resolve_repo_profile(request.repo_path, repo_repository)
    context_items = [
        *_memory_context_items(memories),
        *(_repo_context_items(repo_profile) if repo_profile is not None else []),
    ]
    return RetrievedConversationContext(
        query=request.prompt,
        intent=intent,
        memories=memories,
        repo_profile=repo_profile,
        context_items=context_items,
    )


def _retrieve_memories(
    repository: SqliteMemoryRepository,
    query: str,
    intent: ConversationIntent,
    *,
    project: str,
    limit: int,
) -> list[MemoryItem]:
    merged: dict[str, MemoryItem] = {}
    for memory in repository.retrieve_top(query, project=project, limit=limit):
        merged[memory.id] = memory
    for tag in _INTENT_TAGS[intent]:
        for memory in repository.retrieve_top(query or tag, tags=[tag], project=project, limit=3):
            merged[memory.id] = memory
    ranked = sorted(
        merged.values(),
        key=lambda item: (item.importance, item.confidence),
        reverse=True,
    )
    return ranked[:limit]


def _resolve_repo_profile(
    repo_path: str | None,
    repository: RepoProfileRepository,
) -> RepoProfile | None:
    if repo_path is None:
        return None

    path = Path(repo_path).resolve()
    latest = repository.latest_profile_for_path(path)
    if latest is not None:
        return latest
    report = inspect_repository(path)
    repository.save_inspection(report)
    return report.profile


def _memory_context_items(memories: list[MemoryItem]) -> list[ConversationContextItem]:
    items: list[ConversationContextItem] = []
    for memory in memories:
        items.append(
            ConversationContextItem(
                id=memory.id,
                source="memory",
                summary=memory.summary or memory.content,
                content=memory.content,
                relevance=min(1.0, 0.45 + memory.importance * 0.35),
                metadata={
                    "type": memory.type.value,
                    "tags": memory.tags,
                    "project": memory.project,
                },
            )
        )
    return items


def _repo_context_items(profile: RepoProfile) -> list[ConversationContextItem]:
    risk_text = risk_summary(profile)
    validation_text = validation_summary(profile)
    task_text = ", ".join(task.id for task in profile.generated_tasks[:8]) or "no generated tasks"
    return [
        ConversationContextItem(
            id=f"{profile.id}:stack",
            source="repo_profile",
            summary=f"{profile.name}: {repo_stack_summary(profile)}",
            content=repo_stack_summary(profile),
            relevance=0.94,
            metadata={"repo_profile_id": profile.id, "kind": "stack"},
        ),
        ConversationContextItem(
            id=f"{profile.id}:validation",
            source="repo_profile",
            summary=f"Validation plan: {validation_text}",
            content=validation_text,
            relevance=0.9,
            metadata={"repo_profile_id": profile.id, "kind": "validation"},
        ),
        ConversationContextItem(
            id=f"{profile.id}:risks",
            source="repo_profile",
            summary=f"Repo risks: {risk_text}",
            content=risk_text,
            relevance=0.88,
            metadata={"repo_profile_id": profile.id, "kind": "risk"},
        ),
        ConversationContextItem(
            id=f"{profile.id}:tasks",
            source="repo_profile",
            summary=f"Generated repo tasks: {task_text}",
            content=task_text,
            relevance=0.82,
            metadata={"repo_profile_id": profile.id, "kind": "tasks"},
        ),
    ]
