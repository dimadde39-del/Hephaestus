"""OpenAI-compatible chat-completions provider."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from collections.abc import Sequence
from contextlib import suppress
from typing import Any, Protocol, cast

from hephaestus.core.config import PrivacyLevel
from hephaestus.models.base import ModelProfile, ModelRequest, ModelResponse

OPENAI_COMPAT_BASE_URL_ENV = "HEPH_OPENAI_COMPAT_BASE_URL"
OPENAI_COMPAT_API_KEY_ENV = "HEPH_OPENAI_COMPAT_API_KEY"
OPENAI_COMPAT_MODEL_ENV = "HEPH_OPENAI_COMPAT_MODEL"
OPENAI_COMPAT_CONTEXT_WINDOW_ENV = "HEPH_OPENAI_COMPAT_CONTEXT_WINDOW"
OPENAI_COMPAT_INPUT_COST_ENV = "HEPH_OPENAI_COMPAT_INPUT_COST_PER_MILLION"
OPENAI_COMPAT_OUTPUT_COST_ENV = "HEPH_OPENAI_COMPAT_OUTPUT_COST_PER_MILLION"


class ProviderRequestError(RuntimeError):
    """Sanitized provider transport error safe for CLI and Studio display."""

    def __init__(self, code: str, message: str, *, status_code: int | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


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
        timeout: float = 60,
        urlopen: UrlOpen | None = None,
    ) -> None:
        raw_base_url = (
            base_url if base_url is not None else os.getenv(OPENAI_COMPAT_BASE_URL_ENV)
        )
        self.base_url = raw_base_url.rstrip("/") if raw_base_url else raw_base_url
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
        self.timeout = timeout
        self._urlopen = urlopen or urllib.request.urlopen

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
        payload = self._build_payload(request, model)

        http_request = urllib.request.Request(
            _chat_completions_url(self.base_url or ""),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        try:
            with self._urlopen(http_request, timeout=self.timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            raise _provider_http_error(error) from None
        except TimeoutError as error:
            raise ProviderRequestError("timeout", "Provider request timed out.") from error
        except urllib.error.URLError as error:
            if isinstance(error.reason, TimeoutError):
                raise ProviderRequestError("timeout", "Provider request timed out.") from error
            raise ProviderRequestError(
                "connection_failed",
                "Could not connect to the provider endpoint.",
            ) from error
        except (json.JSONDecodeError, KeyError, TypeError, ValueError) as error:
            raise ProviderRequestError(
                "invalid_response",
                "Provider returned an invalid chat-completions response.",
            ) from error

        return self._parse_response(data, model=model, request=request)

    def _build_payload(self, request: ModelRequest, model: str) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "model": model,
            "messages": request.messages or [{"role": "user", "content": request.prompt}],
            "temperature": request.temperature,
            "max_tokens": request.max_output_tokens,
            "stream": False,
        }
        if request.require_json:
            payload["response_format"] = {"type": "json_object"}

        return payload

    def _parse_response(
        self,
        data: dict[str, Any],
        *,
        model: str,
        request: ModelRequest,
    ) -> ModelResponse:
        message = cast(dict[str, Any], data["choices"][0]["message"])
        text = str(message.get("content") or "")
        usage = data.get("usage", {})
        input_tokens = int(usage.get("prompt_tokens", 0))
        output_tokens = int(usage.get("completion_tokens", 0))
        prompt_details = usage.get("prompt_tokens_details") or {}
        cached_input_tokens = int(
            usage.get("prompt_cache_hit_tokens", prompt_details.get("cached_tokens", 0))
        )
        profile = self.profiles()[0]
        return ModelResponse(
            text=text,
            model=f"{self.name}/{model}",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost=profile.estimated_cost(input_tokens, output_tokens),
            cached_input_tokens=cached_input_tokens,
            thinking_enabled=bool(request.thinking_enabled),
            reasoning_effort=request.reasoning_effort,
            tool_calls=[
                cast(dict[str, Any], item)
                for item in message.get("tool_calls", [])
                if isinstance(item, dict)
            ],
            reasoning_content=(
                str(message["reasoning_content"])
                if message.get("reasoning_content") is not None
                else None
            ),
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


class UrlResponse(Protocol):
    status: int

    def __enter__(self) -> UrlResponse: ...

    def __exit__(self, *args: object) -> None: ...

    def read(self) -> bytes: ...


class UrlOpen(Protocol):
    def __call__(
        self,
        request: urllib.request.Request,
        *,
        timeout: float,
    ) -> UrlResponse: ...


def _provider_http_error(error: urllib.error.HTTPError) -> ProviderRequestError:
    status = error.code
    body = ""
    with suppress(OSError):
        body = error.read().decode("utf-8", errors="replace").lower()
    if status == 401:
        return ProviderRequestError(
            "unauthorized",
            "Authentication failed (401). Check the provider API key.",
            status_code=status,
        )
    if status == 402 or "insufficient balance" in body or "insufficient_balance" in body:
        return ProviderRequestError(
            "insufficient_balance",
            "Provider balance is insufficient (402).",
            status_code=status,
        )
    if status == 429:
        return ProviderRequestError(
            "rate_limited",
            "Provider rate limit reached (429). Try again later.",
            status_code=status,
        )
    if status == 400 and any(
        marker in body for marker in ("model", "invalid_model", "model_not_found")
    ):
        return ProviderRequestError(
            "invalid_model",
            "The configured model ID is invalid or unavailable.",
            status_code=status,
        )
    return ProviderRequestError(
        "http_error",
        f"Provider request failed with HTTP {status}.",
        status_code=status,
    )
