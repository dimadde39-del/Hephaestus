"""Fake deterministic provider used by tests and local demos."""

from __future__ import annotations

from collections.abc import Sequence

from hephaestus.core.config import PrivacyLevel
from hephaestus.models.base import ModelProfile, ModelRequest, ModelResponse


def fake_model_profiles() -> list[ModelProfile]:
    """Profiles with clear tradeoffs for routing tests and CLI demos."""

    return [
        ModelProfile(
            provider="local",
            model="fake-small",
            capabilities={"general", "repository-inspection", "planning", "writing"},
            context_window=8_192,
            input_cost_per_million=0.0,
            output_cost_per_million=0.0,
            latency_score=0.9,
            quality_scores={
                "general": 0.64,
                "repository-inspection": 0.7,
                "planning": 0.62,
                "writing": 0.66,
            },
            privacy_level=PrivacyLevel.SECRET,
            supports_json=True,
            intended_roles={
                "conversation",
                "summarization",
                "memory_extraction",
            },
        ),
        ModelProfile(
            provider="local",
            model="fake-balanced",
            capabilities={
                "analysis",
                "general",
                "git",
                "planning",
                "repository-inspection",
                "safety",
                "shell",
                "testing",
                "writing",
            },
            context_window=32_768,
            input_cost_per_million=0.0,
            output_cost_per_million=0.0,
            latency_score=0.7,
            quality_scores={
                "analysis": 0.78,
                "general": 0.76,
                "git": 0.75,
                "planning": 0.78,
                "repository-inspection": 0.8,
                "safety": 0.82,
                "shell": 0.74,
                "testing": 0.76,
                "writing": 0.77,
            },
            privacy_level=PrivacyLevel.SECRET,
            supports_tools=True,
            supports_json=True,
            intended_roles={
                "conversation",
                "repo_question",
                "strategic_reasoning",
                "research_planning",
                "summarization",
                "memory_extraction",
            },
        ),
        ModelProfile(
            provider="local",
            model="fake-strong",
            capabilities={
                "analysis",
                "coding",
                "general",
                "git",
                "planning",
                "reasoning",
                "repository-inspection",
                "safety",
                "shell",
                "testing",
                "writing",
            },
            context_window=131_072,
            input_cost_per_million=0.0,
            output_cost_per_million=0.0,
            latency_score=0.45,
            quality_scores={
                "analysis": 0.9,
                "coding": 0.88,
                "general": 0.88,
                "git": 0.88,
                "planning": 0.9,
                "reasoning": 0.9,
                "repository-inspection": 0.9,
                "safety": 0.92,
                "shell": 0.86,
                "testing": 0.88,
                "writing": 0.87,
            },
            privacy_level=PrivacyLevel.SECRET,
            supports_tools=True,
            supports_json=True,
            intended_roles={
                "conversation",
                "repo_question",
                "strategic_reasoning",
                "research_planning",
                "summarization",
                "memory_extraction",
            },
        ),
    ]


class FakeModelProvider:
    """Deterministic local provider that never calls a network API."""

    name = "fake"
    is_available = True

    def profiles(self) -> Sequence[ModelProfile]:
        return fake_model_profiles()

    def complete(self, request: ModelRequest) -> ModelResponse:
        model = request.model or "fake-balanced"
        text = f"[fake:{model}] deterministic response for: {request.prompt[:80]}"
        input_tokens = max(1, len(request.prompt.split()))
        output_tokens = min(request.max_output_tokens, max(8, len(text.split())))
        return ModelResponse(
            text=text,
            model=f"local/{model}",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost=0.0,
        )
