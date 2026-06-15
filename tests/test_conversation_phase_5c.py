from pathlib import Path

from typer.testing import CliRunner

from hephaestus.cli.main import app
from hephaestus.conversation import (
    ConversationRequest,
    ConversationService,
    DeliberationMode,
    DeliberationResult,
)
from hephaestus.conversation.analysis import propose_memory_candidates
from hephaestus.conversation.prompt_builder import build_conversation_prompt, estimate_tokens
from hephaestus.conversation.schemas import (
    ConversationContextItem,
    ConversationIntent,
    RetrievedConversationContext,
)
from hephaestus.conversation_eval import load_conversation_benchmark, run_conversation_benchmark
from hephaestus.conversation_eval.evaluator import evaluate_conversation_response
from hephaestus.discussion_quality.evaluator import evaluate_discussion_quality
from hephaestus.memory import MemoryItem, MemoryType
from hephaestus.models import DeepSeekProvider, FakeModelProvider, OpenAICompatibleProvider
from hephaestus.strategic_memory import (
    StrategicMemoryItem,
    StrategicMemoryType,
)

runner = CliRunner()
ROOT = Path(__file__).resolve().parents[1]


def test_prompt_builder_includes_mode_rubric_memory_and_repo_context() -> None:
    context = RetrievedConversationContext(
        query="Stress-test this launch.",
        intent=ConversationIntent.IDEA_STRESS_TEST,
        memories=[
            MemoryItem(
                type=MemoryType.PROJECT,
                content="Hephaestus must feel coherent.",
                summary="Coherent OS positioning.",
                tags=["strategy"],
            )
        ],
        strategic_memories=[
            StrategicMemoryItem(
                type=StrategicMemoryType.AMBITION,
                content="Build toward a 20k-star open-source project.",
                summary="20k-star ambition.",
                tags=["ambition"],
            )
        ],
        context_items=[
            ConversationContextItem(
                id="mem-test",
                source="memory",
                summary="Coherent OS positioning.",
                content="Hephaestus must feel coherent.",
                relevance=0.8,
            ),
            ConversationContextItem(
                id="smem-test",
                source="strategic_memory",
                summary="20k-star ambition.",
                content="Build toward a 20k-star open-source project.",
                relevance=0.9,
            ),
            ConversationContextItem(
                id="repo-test",
                source="repo_profile",
                summary="Repo stack: Python uv",
                content="Validation: uv run pytest",
                relevance=0.9,
            ),
        ],
    )
    evaluation = evaluate_discussion_quality(
        intent=ConversationIntent.IDEA_STRESS_TEST,
        mode=DeliberationMode.STRATEGIC,
        assumptions=["The alpha can be framed honestly."],
        options=["Launch a narrow proof."],
        risks=["Users may expect execution."],
        tradeoffs=["Early feedback versus clarity burden."],
        missing_information=["Need proof that users accept scoped execution value."],
        recommendation="Launch only with clear positioning.",
        next_moves=["Run a cheap validation test."],
    )

    assembly = build_conversation_prompt(
        "Stress-test this launch.",
        mode=DeliberationMode.STRATEGIC,
        context=context,
        assumptions=["The alpha can be framed honestly."],
        options=["Launch a narrow proof."],
        risks=["Users may expect execution."],
        tradeoffs=["Early feedback versus clarity burden."],
        missing_information=["Need proof that users accept scoped execution value."],
        recommendation="Launch only with clear positioning.",
        next_moves=["Run a cheap validation test."],
        quality_evaluation=evaluation,
        max_input_tokens=4_000,
    )

    assert "Mode: strategic" in assembly.prompt
    assert "Discussion rubric: Idea Stress Test" in assembly.prompt
    assert "20k-star ambition" in assembly.prompt
    assert "Coherent OS positioning" in assembly.prompt
    assert "Validation: uv run pytest" in assembly.prompt


def test_prompt_builder_trims_lower_priority_context() -> None:
    context = RetrievedConversationContext(
        query="Stress-test launch.",
        intent=ConversationIntent.IDEA_STRESS_TEST,
        context_items=[
            ConversationContextItem(
                id="smem-critical",
                source="strategic_memory",
                summary="Critical strategic memory.",
                content="Critical strategic memory about the decision-quality wedge.",
                relevance=0.95,
            ),
            *[
                ConversationContextItem(
                    id=f"mem-{index}",
                    source="memory",
                    summary=f"Verbose memory {index}",
                    content=" ".join(["low priority memory detail"] * 80),
                    relevance=0.4,
                )
                for index in range(8)
            ],
        ],
    )

    assembly = build_conversation_prompt(
        "Stress-test launch.",
        mode=DeliberationMode.STRATEGIC,
        context=context,
        assumptions=["Assume the launch needs clarity."],
        options=["Launch a narrow proof."],
        risks=["The message can sound abstract."],
        tradeoffs=["Feedback versus clarity burden."],
        missing_information=["Need user evidence."],
        recommendation="Launch only with clear positioning.",
        next_moves=["Validate the README story."],
        max_input_tokens=650,
    )

    assert assembly.context_trimmed
    assert any(item.id == "smem-critical" for item in assembly.selected_context)
    assert any(item.source == "memory" for item in assembly.trimmed_context)


def test_fake_provider_conversation_synthesis_and_budget(tmp_path) -> None:
    service = ConversationService(tmp_path / "hephaestus.db", provider=FakeModelProvider())

    response = service.respond(
        ConversationRequest(
            prompt="What is Hephaestus trying to become?",
            mode=DeliberationMode.BALANCED,
            show_budget=True,
        )
    )

    assert response.provider_model.startswith("local/fake")
    assert response.budget.estimated_input_tokens > 0
    assert "self-improving local AI agent" in response.answer


def test_openai_compatible_provider_config_detection(monkeypatch) -> None:
    monkeypatch.setenv("HEPH_OPENAI_COMPAT_BASE_URL", "https://openrouter.ai/api/v1")
    monkeypatch.setenv("HEPH_OPENAI_COMPAT_API_KEY", "test-key")
    monkeypatch.setenv("HEPH_OPENAI_COMPAT_MODEL", "openai/gpt-test")

    provider = OpenAICompatibleProvider()
    profile = provider.profiles()[0]

    assert provider.is_available
    assert profile.provider == "openai-compatible"
    assert profile.model == "openai/gpt-test"
    assert "conversation" in profile.intended_roles


def test_deepseek_provider_detection_without_live_call(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")

    provider = DeepSeekProvider()

    assert provider.is_available
    assert provider.profiles()


def test_conversation_token_estimate() -> None:
    assert estimate_tokens("abcd") == 1
    assert estimate_tokens("a" * 41) >= 10
    assert estimate_tokens("") == 0


def test_memory_save_quality_summarizes_long_recommendations() -> None:
    result = DeliberationResult(
        intent=ConversationIntent.IDEA_STRESS_TEST,
        mode=DeliberationMode.STRATEGIC,
        recommendation=" ".join(["Launch only with clear positioning"] * 40),
        final_response="",
    )

    candidates = propose_memory_candidates(
        "Stress-test this launch idea.",
        result,
        project="default",
    )

    assert candidates
    assert all(len(candidate.content) <= 320 for candidate in candidates)
    assert all(len(candidate.summary) <= 140 for candidate in candidates)
    assert all(candidate.stability in {"temporary", "medium_term", "long_term"} for candidate in candidates)


def test_conversation_benchmark_fixture_loading_and_evaluation() -> None:
    fixture = load_conversation_benchmark("idea_stress_test")
    result = run_conversation_benchmark(fixture, provider="local")

    assert fixture.expected_rubric == "Idea Stress Test"
    assert result.benchmark_id == "idea_stress_test"
    assert result.score >= 0.7
    assert not result.anti_patterns_detected


def test_conversation_evaluator_detects_guardrail_checks(tmp_path) -> None:
    fixture = load_conversation_benchmark("research_planning")
    service = ConversationService(tmp_path / "hephaestus.db", provider=FakeModelProvider())
    response = service.respond(
        ConversationRequest(
            prompt=fixture.prompt,
            mode=fixture.mode,
            provider="local",
            discussion=True,
        )
    )

    result = evaluate_conversation_response(fixture, response)

    assert any(check.key == "research_planning_boundary" and check.passed for check in result.checks)
    assert not result.anti_patterns_detected


def test_phase_5c_cli_smoke(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)

    ask_result = runner.invoke(
        app,
        [
            "ask",
            "What is Hephaestus trying to become?",
            "--show-budget",
            "--provider",
            "local",
        ],
    )
    discuss_result = runner.invoke(
        app,
        [
            "discuss",
            "Stress-test launching before command execution.",
            "--mode",
            "strategic",
            "--show-context",
            "--provider",
            "local",
        ],
    )
    list_result = runner.invoke(app, ["conversation", "benchmark", "list"])
    run_one_result = runner.invoke(
        app,
        [
            "conversation",
            "benchmark",
            "run",
            str(ROOT / "benchmarks" / "conversation" / "idea_stress_test.json"),
        ],
    )
    run_all_result = runner.invoke(app, ["conversation", "benchmark", "run"])

    assert ask_result.exit_code == 0
    assert "Conversation Budget" in ask_result.output
    assert discuss_result.exit_code == 0
    assert "Selected Conversation Context" in discuss_result.output
    assert list_result.exit_code == 0
    assert "Conversation Benchmarks" in list_result.output
    assert run_one_result.exit_code == 0
    assert "idea_stress_test" in run_one_result.output
    assert run_all_result.exit_code == 0
    assert "Conversation Benchmark Summary" in run_all_result.output
