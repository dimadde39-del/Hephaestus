"""Rich renderers for strategic memory."""

from __future__ import annotations

from rich.console import Group, RenderableType
from rich.panel import Panel
from rich.table import Table

from hephaestus.strategic_memory.analysis import select_strategic_context
from hephaestus.strategic_memory.schemas import (
    StrategicMemoryConflict,
    StrategicMemoryExtractionResult,
    StrategicMemoryItem,
    StrategicMemoryType,
)


def build_strategic_memory_table(
    memories: list[StrategicMemoryItem],
    *,
    title: str = "Strategic Memories",
) -> Table:
    """Render strategic memories as a compact table."""

    table = Table(title=title)
    table.add_column("ID", no_wrap=True)
    table.add_column("Type")
    table.add_column("Scope")
    table.add_column("Project")
    table.add_column("Tags")
    table.add_column("Summary", overflow="fold")
    for memory in memories:
        table.add_row(
            memory.id,
            memory.type.value,
            memory.scope.value,
            memory.project or "-",
            ", ".join(memory.tags) or "-",
            memory.summary or memory.content,
        )
    return table


def build_strategic_memory_detail(memory: StrategicMemoryItem) -> RenderableType:
    """Render one strategic memory."""

    evidence = "\n".join(f"- {item.content}" for item in memory.evidence) or "- none"
    return Group(
        Panel(
            "\n".join(
                [
                    f"Type: {memory.type.value}",
                    f"Scope: {memory.scope.value}",
                    f"Project: {memory.project or '-'}",
                    f"Repo profile: {memory.repo_profile_id or '-'}",
                    f"Conversation: {memory.conversation_id or '-'}",
                    f"Confidence: {memory.confidence:.2f}",
                    f"Importance: {memory.importance:.2f}",
                    f"Stability: {memory.stability.value}",
                    f"Source: {memory.source.value}",
                    f"Tags: {', '.join(memory.tags) or '-'}",
                    f"Archived: {memory.archived_at.isoformat() if memory.archived_at else '-'}",
                ]
            ),
            title=f"Strategic Memory {memory.id}",
        ),
        Panel(memory.content, title=memory.summary or "Content"),
        Panel(evidence, title="Evidence"),
    )


def build_strategic_context_renderable(memories: list[StrategicMemoryItem]) -> RenderableType:
    """Render the long-term strategic context snapshot."""

    grouped = select_strategic_context(memories)
    parts: list[RenderableType] = [
        Panel(
            "What Hephaestus currently knows about long-term direction.",
            title="Strategic Context",
        )
    ]
    labels: dict[StrategicMemoryType, str] = {
        StrategicMemoryType.GOAL: "Top Goals",
        StrategicMemoryType.AMBITION: "Ambitions",
        StrategicMemoryType.PRINCIPLE: "Principles",
        StrategicMemoryType.CONSTRAINT: "Constraints",
        StrategicMemoryType.ROADMAP_DECISION: "Roadmap Decisions",
        StrategicMemoryType.STRATEGIC_DECISION: "Strategic Decisions",
        StrategicMemoryType.REJECTED_PATH: "Rejected Paths",
        StrategicMemoryType.OPEN_QUESTION: "Open Questions",
    }
    for memory_type, memories_for_type in grouped.items():
        parts.append(
            build_strategic_memory_table(
                memories_for_type,
                title=labels.get(memory_type, memory_type.value.replace("_", " ").title()),
            )
        )
    if len(parts) == 1:
        parts.append(Panel("No strategic memories saved yet.", title="Empty"))
    return Group(*parts)


def build_strategic_memory_suggestions_table(
    result: StrategicMemoryExtractionResult,
) -> Table:
    """Render suggested strategic memory updates."""

    table = Table(title="Suggested Strategic Memory Updates")
    table.add_column("Type")
    table.add_column("Scope")
    table.add_column("Tags")
    table.add_column("Summary", overflow="fold")
    for item in result.items:
        table.add_row(
            item.type.value,
            item.scope.value,
            ", ".join(item.tags) or "-",
            item.summary or item.content,
        )
    return table


def build_conflict_table(conflicts: list[StrategicMemoryConflict]) -> Table:
    """Render strategic memory conflicts."""

    table = Table(title="Strategic Memory Conflicts")
    table.add_column("ID", no_wrap=True)
    table.add_column("Existing")
    table.add_column("Candidate")
    table.add_column("Severity", justify="right")
    table.add_column("Description", overflow="fold")
    for conflict in conflicts:
        table.add_row(
            conflict.id,
            conflict.existing_memory_id,
            conflict.candidate_memory_id or "-",
            f"{conflict.severity:.2f}",
            conflict.description,
        )
    return table
