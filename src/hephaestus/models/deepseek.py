"""DeepSeek provider over the shared OpenAI-compatible transport."""

from __future__ import annotations

import os
from collections.abc import Sequence
from typing import Any

from hephaestus.core.config import PrivacyLevel
from hephaestus.models.base import ModelProfile, ModelRequest, ModelResponse
from hephaestus.models.openai_compatible import OpenAICompatibleProvider, UrlOpen

DEEPSEEK_API_KEY_ENV = "DEEPSEEK_API_KEY"
DEEPSEEK_BASE_URL_ENV = "DEEPSEEK_BASE_URL"
DEEPSEEK_MODEL_ENV = "DEEPSEEK_MODEL"
DEEPSEEK_THINKING_ENV = "HEPH_DEEPSEEK_THINKING"
DEEPSEEK_REASONING_EFFORT_ENV = "HEPH_DEEPSEEK_REASONING_EFFORT"
DEEPSEEK_MAX_OUTPUT_TOKENS_ENV = "HEPH_DEEPSEEK_MAX_OUTPUT_TOKENS"
DEEPSEEK_DEFAULT_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_DEFAULT_MODEL = "deepseek-v4-flash"
DEEPSEEK_DEFAULT_CONTEXT_WINDOW = 1_000_000
DEEPSEEK_DEFAULT_INPUT_COST_PER_MILLION = 0.14
DEEPSEEK_DEFAULT_OUTPUT_COST_PER_MILLION = 0.28
VALID_REASONING_EFFORTS = {"high", "max"}


class DeepSeekProvider(OpenAICompatibleProvider):
    """Optional provider that is inactive until DEEPSEEK_API_KEY is set."""

    name = "deepseek"

    def __init__(
        self,
        api_key: str | None = None,
        *,
        base_url: str | None = None,
        model: str | None = None,
        thinking_enabled: bool | None = None,
        reasoning_effort: str | None = None,
        max_output_tokens: int | None = None,
        context_window: int | None = None,
        input_cost_per_million: float | None = None,
        output_cost_per_million: float | None = None,
        timeout: float = 60,
        urlopen: UrlOpen | None = None,
    ) -> None:
        resolved_effort = (
            reasoning_effort
            if reasoning_effort is not None
            else os.getenv(DEEPSEEK_REASONING_EFFORT_ENV, "high")
        ).strip().lower()
        if resolved_effort not in VALID_REASONING_EFFORTS:
            raise ValueError("DeepSeek reasoning_effort must be 'high' or 'max'.")
        self.thinking_enabled = (
            thinking_enabled
            if thinking_enabled is not None
            else _enabled_env(DEEPSEEK_THINKING_ENV, default=True)
        )
        self.reasoning_effort = resolved_effort
        self.max_output_tokens = max_output_tokens or _positive_int_env(
            DEEPSEEK_MAX_OUTPUT_TOKENS_ENV, default=4096
        )
        super().__init__(
            base_url=base_url or os.getenv(DEEPSEEK_BASE_URL_ENV, DEEPSEEK_DEFAULT_BASE_URL),
            api_key=api_key if api_key is not None else os.getenv(DEEPSEEK_API_KEY_ENV),
            model=model or os.getenv(DEEPSEEK_MODEL_ENV, DEEPSEEK_DEFAULT_MODEL),
            context_window=context_window or DEEPSEEK_DEFAULT_CONTEXT_WINDOW,
            input_cost_per_million=(
                input_cost_per_million
                if input_cost_per_million is not None
                else DEEPSEEK_DEFAULT_INPUT_COST_PER_MILLION
            ),
            output_cost_per_million=(
                output_cost_per_million
                if output_cost_per_million is not None
                else DEEPSEEK_DEFAULT_OUTPUT_COST_PER_MILLION
            ),
            timeout=timeout,
            urlopen=urlopen,
        )

    def profiles(self) -> Sequence[ModelProfile]:
        return [
            ModelProfile(
                provider="deepseek",
                model=self.model or DEEPSEEK_DEFAULT_MODEL,
                capabilities={
                    "analysis",
                    "coding",
                    "general",
                    "planning",
                    "reasoning",
                    "repository-inspection",
                    "safety",
                    "tool-use",
                    "writing",
                },
                context_window=self.context_window,
                input_cost_per_million=self.input_cost_per_million,
                output_cost_per_million=self.output_cost_per_million,
                latency_score=0.7,
                quality_scores={
                    "analysis": 0.86,
                    "coding": 0.84,
                    "general": 0.84,
                    "planning": 0.85,
                    "reasoning": 0.86,
                    "repository-inspection": 0.84,
                    "safety": 0.82,
                    "tool-use": 0.82,
                    "writing": 0.84,
                },
                privacy_level=PrivacyLevel.INTERNAL,
                supports_tools=True,
                supports_json=True,
                supports_streaming=True,
                intended_roles={
                    "conversation",
                    "repo_question",
                    "summarization",
                    "memory_extraction",
                },
            ),
        ]

    def complete(self, request: ModelRequest) -> ModelResponse:
        effective = request.model_copy(
            update={
                "model": request.model or self.model,
                "max_output_tokens": min(request.max_output_tokens, self.max_output_tokens),
                "thinking_enabled": (
                    self.thinking_enabled
                    if request.thinking_enabled is None
                    else request.thinking_enabled
                ),
                "reasoning_effort": request.reasoning_effort or self.reasoning_effort,
            }
        )
        return super().complete(effective)

    def _build_payload(self, request: ModelRequest, model: str) -> dict[str, object]:
        payload = super()._build_payload(request, model)
        if request.thinking_enabled:
            payload.pop("temperature", None)
            payload.pop("top_p", None)
            payload.pop("presence_penalty", None)
            payload.pop("frequency_penalty", None)
            payload["thinking"] = {"type": "enabled"}
            payload["reasoning_effort"] = request.reasoning_effort or self.reasoning_effort
        return payload

    def complete_tool_continuation(
        self,
        request: ModelRequest,
        previous: ModelResponse,
        tool_messages: list[dict[str, Any]],
    ) -> ModelResponse:
        """Continue one tool-call turn while keeping reasoning transient."""

        if not previous.tool_calls:
            raise ValueError("Tool continuation requires assistant tool_calls.")
        assistant: dict[str, Any] = {
            "role": "assistant",
            "content": previous.text or None,
            "tool_calls": previous.tool_calls,
        }
        if previous.reasoning_content:
            assistant["reasoning_content"] = previous.reasoning_content
        messages = [
            *(request.messages or [{"role": "user", "content": request.prompt}]),
            assistant,
            *tool_messages,
        ]
        return self.complete(request.model_copy(update={"messages": messages}))


def _enabled_env(name: str, *, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on", "enabled"}


def _positive_int_env(name: str, *, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default
