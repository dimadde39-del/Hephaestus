import re
from pathlib import Path

from typer.testing import CliRunner

from hephaestus.cli.main import app
from hephaestus.conversation import (
    ConversationMemoryCandidate,
    ConversationMemoryUpdate,
    ConversationMessage,
    ConversationRepository,
    ConversationRequest,
    ConversationRole,
    ConversationService,
    ConversationSession,
    DeliberationMode,
    classify_intent,
)
from hephaestus.conversation.schemas import ConversationIntent
from hephaestus.decision import DecisionTraceRepository
from hephaestus.memory import MemoryItem, MemoryType
from hephaestus.storage import SqliteMemoryRepository

runner = CliRunner()
FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "repos"


def test_conversation_schema_validation_and_modes() -> None:
    request = ConversationRequest(
        prompt="Stress-test this roadmap before launch.",
        mode=DeliberationMode.SKEPTICAL_BUT_FAIR,
    )
    candidate = ConversationMemoryCandidate(
        content="Voice is deferred until the core is mature.",
        tags=["Roadmap", "voice", "roadmap"],
    )

    assert request.mode == DeliberationMode.SKEPTICAL_BUT_FAIR
    assert DeliberationMode("strategic") == DeliberationMode.STRATEGIC
    assert candidate.tags == ["roadmap", "voice"]


def test_intent_classifier() -> None:
    assert classify_intent("What are the release risks in this repo?") in {
        ConversationIntent.REPO_QUESTION,
        ConversationIntent.RISK_ANALYSIS,
    }
    assert classify_intent("Stress-test whether this idea is too abstract.") == (
        ConversationIntent.IDEA_STRESS_TEST
    )
    assert classify_intent("Should this architecture use a separate repository layer?") == (
        ConversationIntent.ARCHITECTURE_DISCUSSION
    )


def test_conversation_repository_session_message_and_memory_roundtrip(tmp_path) -> None:
    repository = ConversationRepository(tmp_path / "hephaestus.db")
    session = repository.create_session(
        ConversationSession(title="Conversation repo test", mode=DeliberationMode.STRATEGIC)
    )
    message = repository.add_message(
        ConversationMessage(
            session_id=session.id,
            role=ConversationRole.USER,
            content="Help me think through the roadmap.",
            intent=ConversationIntent.ROADMAP_DECISION,
            mode=DeliberationMode.STRATEGIC,
        )
    )
    update = repository.save_memory_update(
        ConversationMemoryUpdate(
            session_id=session.id,
            message_id=message.id,
            candidate=ConversationMemoryCandidate(
                content="Roadmap decisions should preserve the decision-quality wedge.",
                summary="Preserve decision-quality wedge.",
                tags=["roadmap", "strategy"],
            ),
        )
    )
    linked = repository.link_decision_trace(session.id, "trace_test")

    assert repository.get_session(session.id) is not None
    assert repository.list_sessions()[0].id == session.id
    assert repository.list_messages(session.id)[0] == message
    assert repository.list_memory_updates(session.id)[0] == update
    assert linked is not None
    assert linked.linked_decision_trace_ids == ["trace_test"]


def test_conversation_service_uses_memory_and_creates_high_impact_trace(tmp_path) -> None:
    database_path = tmp_path / "hephaestus.db"
    SqliteMemoryRepository(database_path).add(
        MemoryItem(
            type=MemoryType.PROJECT,
            content="Hephaestus aims to become a 20k-star open-source decision-quality OS.",
            summary="20k-star open-source goal.",
            tags=["project", "strategy", "open-source"],
            importance=0.9,
            confidence=0.9,
        )
    )
    service = ConversationService(database_path)
    response = service.respond(
        ConversationRequest(
            prompt=(
                "I want Hephaestus to reach 20k stars, but I worry it is too abstract "
                "before it can execute code. Be honest."
            ),
            mode=DeliberationMode.STRATEGIC,
            save_memory=True,
        )
    )

    assert response.intent in {
        ConversationIntent.IDEA_STRESS_TEST,
        ConversationIntent.PRODUCT_STRATEGY,
    }
    assert response.selected_memory_ids
    assert response.memory_updates
    assert all(update.status == "saved" for update in response.memory_updates)
    assert response.decision_trace is not None
    assert response.decision_trace.run_id is not None
    traces = DecisionTraceRepository(database_path).list_traces(
        run_id=response.decision_trace.run_id
    )
    assert len(traces) == 1
    assert traces[0].phase == "conversation"
    assert "Provider note" in response.answer


def test_conversation_service_repo_context_with_fixture(tmp_path) -> None:
    service = ConversationService(tmp_path / "hephaestus.db")
    response = service.respond(
        ConversationRequest(
            prompt="What are the release risks in this repo?",
            mode=DeliberationMode.STRATEGIC,
            repo_path=str(FIXTURE_ROOT / "python_uv"),
        )
    )

    assert response.selected_context
    assert any(item.source == "repo_profile" for item in response.selected_context)
    assert "uv run pytest" in response.answer
    assert "Risk signals" in response.answer


def test_conversation_cli_smoke(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    ask_result = runner.invoke(app, ["ask", "What is Hephaestus trying to become?"])
    discuss_result = runner.invoke(
        app,
        [
            "discuss",
            "Stress-test the idea of launching Hephaestus before it can execute code.",
            "--mode",
            "strategic",
        ],
    )
    list_result = runner.invoke(app, ["conversations"])
    session_match = re.search(r"conv_[a-f0-9]+", list_result.output)
    session_id = session_match.group(0) if session_match else ""
    show_result = runner.invoke(app, ["conversation", "show", session_id])

    assert ask_result.exit_code == 0
    assert "optimization-first agent OS" in ask_result.output
    assert discuss_result.exit_code == 0
    assert "idea_stress_test" in discuss_result.output
    assert list_result.exit_code == 0
    assert session_match is not None
    assert show_result.exit_code == 0
    assert "Conversation Session" in show_result.output
