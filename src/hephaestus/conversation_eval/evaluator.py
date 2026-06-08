"""Deterministic evaluators for conversation benchmark responses."""

from __future__ import annotations

from hephaestus.conversation.schemas import ConversationResponse, DeliberationMode
from hephaestus.conversation_eval.profiles import checks_for_quality_profile
from hephaestus.conversation_eval.schemas import (
    ConversationBenchmarkFixture,
    ConversationEvaluationCheck,
    ConversationEvaluationResult,
)


def evaluate_conversation_response(
    fixture: ConversationBenchmarkFixture,
    response: ConversationResponse,
) -> ConversationEvaluationResult:
    """Evaluate a conversation response using deterministic guardrail checks."""

    text = response.answer.lower()
    checks = [
        _run_check(key, fixture, response, text)
        for key in _expected_check_keys(fixture)
    ]
    anti_patterns = _detect_anti_patterns(fixture, response.answer)
    warnings = _warnings(fixture, response)
    passed = sum(1 for check in checks if check.passed)
    score = passed / len(checks) if checks else 1.0
    if anti_patterns:
        score = max(0.0, score - min(0.3, 0.1 * len(anti_patterns)))
    return ConversationEvaluationResult(
        benchmark_id=fixture.id,
        title=fixture.title,
        mode=fixture.mode,
        score=score,
        checks=checks,
        warnings=warnings,
        anti_patterns_detected=anti_patterns,
        provider_model=response.provider_model,
    )


def _expected_check_keys(fixture: ConversationBenchmarkFixture) -> list[str]:
    keys = [
        *checks_for_quality_profile(fixture.quality_profile),
        *fixture.required_qualities,
    ]
    if fixture.strategic_memory_context:
        keys.append("strategic_memory_used")
    if fixture.repo_context_required:
        keys.append("repo_context_used")
    return list(dict.fromkeys(keys))


def _run_check(
    key: str,
    fixture: ConversationBenchmarkFixture,
    response: ConversationResponse,
    text: str,
) -> ConversationEvaluationCheck:
    labels: dict[str, str] = {
        "position_or_recommendation": "Includes position or recommendation",
        "assumptions": "Includes assumptions",
        "risks": "Includes risks",
        "missing_information": "Includes missing information",
        "next_move": "Includes next move",
        "research_planning_boundary": "Does not claim live research in research mode",
        "no_blind_agreement": "Does not blindly agree",
        "no_fake_certainty": "Does not produce fake certainty",
        "strategic_memory_used": "Uses strategic memory when provided",
        "repo_context_used": "Uses repo context when required",
    }
    passed = False
    evidence = ""
    if key == "position_or_recommendation":
        passed = bool(response.deliberation.recommendation) or any(
            marker in text for marker in ("recommendation:", "position:", "i would")
        )
        evidence = response.deliberation.recommendation
    elif key == "assumptions":
        passed = bool(response.deliberation.assumptions) or "assumption" in text
        evidence = _first(response.deliberation.assumptions)
    elif key == "risks":
        passed = bool(response.deliberation.risks) or "risk" in text
        evidence = _first(response.deliberation.risks)
    elif key == "missing_information":
        passed = bool(response.deliberation.missing_information) or "missing information" in text
        evidence = _first(response.deliberation.missing_information)
    elif key == "next_move":
        passed = bool(response.deliberation.next_moves) or "next move" in text
        evidence = _first(response.deliberation.next_moves)
    elif key == "research_planning_boundary":
        passed = not _claims_live_research(text)
        evidence = "No live research claim detected." if passed else "Live research claim detected."
    elif key == "no_blind_agreement":
        passed = "blind agreement" not in _detect_anti_patterns(fixture, response.answer)
        evidence = "Risks present." if response.deliberation.risks else ""
    elif key == "no_fake_certainty":
        passed = "fake certainty" not in _detect_anti_patterns(fixture, response.answer)
        evidence = "No certainty markers detected." if passed else "Certainty marker detected."
    elif key == "strategic_memory_used":
        passed = bool(response.selected_strategic_memory_ids) or any(
            memory.summary.lower() in text or memory.content.lower() in text
            for memory in fixture.strategic_memory_context
            if memory.summary or memory.content
        )
        evidence = ", ".join(response.selected_strategic_memory_ids)
    elif key == "repo_context_used":
        passed = any(item.source == "repo_profile" for item in response.selected_context) or (
            not fixture.repo_context_required
        )
        evidence = ", ".join(
            item.id for item in response.selected_context if item.source == "repo_profile"
        )
    else:
        passed = key.replace("_", " ") in text
        evidence = "Custom textual check."
    return ConversationEvaluationCheck(
        key=key,
        label=labels.get(key, key.replace("_", " ").title()),
        passed=passed,
        evidence=evidence,
    )


def _detect_anti_patterns(
    fixture: ConversationBenchmarkFixture,
    answer: str,
) -> list[str]:
    text = answer.lower()
    detected: list[str] = []
    requested = set(fixture.anti_patterns)
    if (
        "blind agreement" in requested
        and any(marker in text for marker in ("perfect plan", "absolutely right", "no downside"))
        and "risk" not in text
    ):
        detected.append("blind agreement")
    if "fake certainty" in requested and any(
        marker in text
        for marker in ("guaranteed", "definitely succeed", "certain to", "no uncertainty")
    ):
        detected.append("fake certainty")
    if "unsupported claims" in requested and any(
        marker in text for marker in ("studies show", "latest research proves", "everyone knows")
    ):
        detected.append("unsupported claims")
    if "generic advice" in requested and "hephaestus" not in text and len(answer.split()) < 80:
        detected.append("generic advice")
    if "moralizing" in requested and any(
        marker in text for marker in ("as an ai", "i cannot assist with that benign")
    ):
        detected.append("moralizing")
    if "contrarianism for its own sake" in requested and (
        "this is simply wrong" in text and "strongest support" not in text
    ):
        detected.append("contrarianism for its own sake")
    if fixture.mode == DeliberationMode.RESEARCH and _claims_live_research(text):
        detected.append("unsupported live research claim")
    return list(dict.fromkeys(detected))


def _claims_live_research(text: str) -> bool:
    return any(
        marker in text
        for marker in (
            "i researched",
            "i searched the web",
            "current web results",
            "according to the latest sources",
        )
    )


def _warnings(
    fixture: ConversationBenchmarkFixture,
    response: ConversationResponse,
) -> list[str]:
    warnings: list[str] = []
    if fixture.expected_rubric and response.deliberation.quality_evaluation is not None:
        actual = response.deliberation.quality_evaluation.rubric_name
        if actual != fixture.expected_rubric:
            warnings.append(f"Expected rubric {fixture.expected_rubric}; got {actual}.")
    if response.budget.context_trimmed:
        warnings.extend(response.budget.trimming_notes)
    return warnings


def _first(values: list[str]) -> str:
    return values[0] if values else ""
