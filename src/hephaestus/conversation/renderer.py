"""Rich renderers for conversation sessions and responses."""

from __future__ import annotations

from rich.console import Group, RenderableType
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table

from hephaestus.conversation.schemas import (
    ConversationMemoryCandidate,
    ConversationMemoryUpdate,
    ConversationMessage,
    ConversationResponse,
    ConversationSession,
    RetrievedConversationContext,
)


def build_conversation_response_renderable(response: ConversationResponse) -> RenderableType:
    """Render a conversation response with trace and memory suggestions."""

    parts: list[RenderableType] = [
        Panel(
            (
                f"Session: {response.session_id}\n"
                f"Intent: {response.intent.value}\n"
                f"Mode: {response.mode.value}"
            ),
            title=f"Hephaestus: {response.intent.value} / {response.mode.value}",
        ),
        Markdown(response.answer),
    ]
    if response.decision_trace is not None:
        trace = response.decision_trace
        parts.append(
            Panel(
                "\n".join(
                    [
                        f"Recommendation: {trace.recommendation}",
                        f"Confidence: {trace.confidence:.2f}",
                        f"Next: {trace.suggested_next_move or '-'}",
                        f"Decision trace: {trace.decision_trace_id or 'not persisted'}",
                    ]
                ),
                title="Conversation Decision Trace",
            )
        )
    if response.memory_candidates:
        parts.append(build_memory_candidate_table(response.memory_candidates))
    if response.memory_updates:
        parts.append(build_memory_update_table(response.memory_updates))
    parts.append(
        Panel(
            (
                f"Model: {response.provider_model}\n"
                f"Tokens: {response.input_tokens} input / {response.output_tokens} output\n"
                f"Estimated cost: ${response.estimated_cost:.6f}"
            ),
            title="Provider",
        )
    )
    return Group(*parts)


def build_memory_candidate_table(
    candidates: list[ConversationMemoryCandidate],
) -> Table:
    """Render suggested memory updates."""

    table = Table(title="Suggested Memory Updates")
    table.add_column("Type")
    table.add_column("Tags")
    table.add_column("Summary")
    table.add_column("Rationale")
    for candidate in candidates:
        table.add_row(
            candidate.memory_type.value,
            ", ".join(candidate.tags) or "-",
            candidate.summary or candidate.content,
            candidate.rationale or "-",
        )
    return table


def build_memory_update_table(updates: list[ConversationMemoryUpdate]) -> Table:
    """Render persisted memory update suggestions."""

    table = Table(title="Memory Update Status")
    table.add_column("ID", no_wrap=True)
    table.add_column("Status")
    table.add_column("Memory")
    table.add_column("Summary")
    for update in updates:
        table.add_row(
            update.id,
            update.status,
            update.memory_id or "-",
            update.candidate.summary or update.candidate.content,
        )
    return table


def build_conversation_sessions_table(sessions: list[ConversationSession]) -> Table:
    """Render recent conversation sessions."""

    table = Table(title="Conversations")
    table.add_column("ID", no_wrap=True)
    table.add_column("Mode")
    table.add_column("Updated")
    table.add_column("Repo")
    table.add_column("Title", overflow="fold")
    table.add_column("Traces", justify="right")
    for session in sessions:
        table.add_row(
            session.id,
            session.mode.value,
            session.updated_at.isoformat(timespec="seconds"),
            session.repo_profile_id or "-",
            session.title,
            str(len(session.linked_decision_trace_ids)),
        )
    return table


def build_conversation_show_renderable(
    session: ConversationSession,
    messages: list[ConversationMessage],
    updates: list[ConversationMemoryUpdate],
) -> RenderableType:
    """Render one conversation session and its messages."""

    message_table = Table(title=f"Conversation {session.id}")
    message_table.add_column("When")
    message_table.add_column("Role")
    message_table.add_column("Intent")
    message_table.add_column("Message", overflow="fold")
    for message in messages:
        message_table.add_row(
            message.created_at.isoformat(timespec="seconds"),
            message.role.value,
            message.intent.value if message.intent is not None else "-",
            message.content,
        )
    parts: list[RenderableType] = [
        Panel(
            "\n".join(
                [
                    f"Title: {session.title}",
                    f"Mode: {session.mode.value}",
                    f"Repo profile: {session.repo_profile_id or '-'}",
                    f"Archived: {'yes' if session.archived else 'no'}",
                    "Decision traces: "
                    + (", ".join(session.linked_decision_trace_ids) or "-"),
                ]
            ),
            title="Conversation Session",
        ),
        message_table,
    ]
    if updates:
        parts.append(build_memory_update_table(updates))
    return Group(*parts)


def build_context_table(context: RetrievedConversationContext) -> Table:
    """Render selected memory and repo context."""

    table = Table(title="Selected Conversation Context")
    table.add_column("Source")
    table.add_column("ID")
    table.add_column("Summary", overflow="fold")
    for item in context.context_items:
        table.add_row(item.source, item.id, item.summary)
    return table
