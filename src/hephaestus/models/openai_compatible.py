"""OpenAI-compatible chat-completions provider."""

from __future__ import annotations

import json
import os
import urllib.request
from collections.abc import Sequence
from typing import Any

from hephaestus.core.config import PrivacyLevel
from hephaestus.models.base import ModelProfile, ModelRequest, ModelResponse

OPENAI_COMPAT_BASE_URL_ENV = "HEPH_OPENAI_COMPAT_BASE_URL"
OPENAI_COMPAT_API_KEY_ENV = "HEPH_OPENAI_COMPAT_API_KEY"
OPENAI_COMPAT_MODEL_ENV = "HEPH_OPENAI_COMPAT_MODEL"
OPENAI_COMPAT_CONTEXT_WINDOW_ENV = "HEPH_OPENAI_COMPAT_CONTEXT_WINDOW"
OPENAI_COMPAT_INPUT_COST_ENV = "HEPH_OPENAI_COMPAT_INPUT_COST_PER_MILLION"
OPENAI_COMPAT_OUTPUT_COST_ENV = "HEPH_OPENAI_COMPAT_OUTPUT_COST_PER_MILLION"


class OpenAICompatibleProvider:
    """Provider for OpenAI-compatible chat-completion APIs, including OpenRouter."""

    name = "openai-compatible"

    def __init__(
        self,
        *,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        context_window: int | None = None,
        input_cost_per_million: float | None = None,
        output_cost_per_million: float | None = None,
    ) -> None:
        self.base_url = base_url if base_url is not None else os.getenv(OPENAI_COMPAT_BASE_URL_ENV)
        self.api_key = api_key if api_key is not None else os.getenv(OPENAI_COMPAT_API_KEY_ENV)
        self.model = model if model is not None else os.getenv(OPENAI_COMPAT_MODEL_ENV)
        self.context_window: int = context_window or _int_env(
            OPENAI_COMPAT_CONTEXT_WINDOW_ENV,
            default=128_000,
        )
        self.input_cost_per_million: float = (
            input_cost_per_million
            if input_cost_per_million is not None
            else _float_env(OPENAI_COMPAT_INPUT_COST_ENV, default=0.0)
        )
        self.output_cost_per_million: float = (
            output_cost_per_million
            if output_cost_per_million is not None
            else _float_env(OPENAI_COMPAT_OUTPUT_COST_ENV, default=0.0)
        )

    @property
    def is_available(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)

    def profiles(self) -> Sequence[ModelProfile]:
        model = self.model or "unconfigured"
        return [
            ModelProfile(
                provider=self.name,
                model=model,
                capabilities={
                    "analysis",
                    "coding",
                    "general",
                    "planning",
                    "reasoning",
                    "repository-inspection",
                    "safety",
                    "writing",
                },
                context_window=max(1, self.context_window),
                input_cost_per_million=max(0.0, self.input_cost_per_million),
                output_cost_per_million=max(0.0, self.output_cost_per_million),
                latency_score=0.55,
                quality_scores={
                    "analysis": 0.88,
                    "coding": 0.86,
                    "general": 0.86,
                    "planning": 0.88,
                    "reasoning": 0.88,
                    "repository-inspection": 0.84,
                    "safety": 0.84,
                    "writing": 0.86,
                },
                privacy_level=PrivacyLevel.INTERNAL,
                supports_tools=False,
                supports_json=True,
                supports_streaming=False,
                intended_roles={
                    "conversation",
                    "repo_question",
                    "strategic_reasoning",
                    "research_planning",
                    "summarization",
                    "memory_extraction",
                },
            )
        ]

    def complete(self, request: ModelRequest) -> ModelResponse:
        if not self.is_available:
            raise RuntimeError(
                "OpenAI-compatible provider unavailable. Set "
                f"{OPENAI_COMPAT_BASE_URL_ENV}, {OPENAI_COMPAT_API_KEY_ENV}, and "
                f"{OPENAI_COMPAT_MODEL_ENV}."
            )

        model = request.model or self.model
        if model is None:
            raise RuntimeError(f"{OPENAI_COMPAT_MODEL_ENV} is required.")
        payload: dict[str, Any] = {
            "model": model,
            "messages": [{"role": "user", "content": request.prompt}],
            "temperature": request.temperature,
            "max_tokens": request.max_output_tokens,
            "stream": False,
        }
        if request.require_json:
            payload["response_format"] = {"type": "json_object"}

        http_request = urllib.request.Request(
            _chat_completions_url(self.base_url or ""),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(http_request, timeout=60) as response:
            data = json.loads(response.read().decode("utf-8"))

        text = data["choices"][0]["message"]["content"]
        usage = data.get("usage", {})
        input_tokens = int(usage.get("prompt_tokens", 0))
        output_tokens = int(usage.get("completion_tokens", 0))
        profile = self.profiles()[0]
        return ModelResponse(
            text=text,
            model=f"{self.name}/{model}",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost=profile.estimated_cost(input_tokens, output_tokens),
        )


def _chat_completions_url(base_url: str) -> str:
    stripped = base_url.rstrip("/")
    if stripped.endswith("/chat/completions"):
        return stripped
    if stripped.endswith("/v1"):
        return f"{stripped}/chat/completions"
    return f"{stripped}/v1/chat/completions"


def _int_env(name: str, *, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _float_env(name: str, *, default: float) -> float:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default
