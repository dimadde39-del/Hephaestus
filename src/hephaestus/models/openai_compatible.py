"""OpenAI-compatible chat-completions provider."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from contextlib import suppress
from typing import Any, Protocol, cast

import httpx
from pydantic import BaseModel, ConfigDict, Field

from hephaestus.core.config import PrivacyLevel
from hephaestus.models.base import (
    ModelProfile,
    ModelRequest,
    ModelResponse,
    ModelTransportAttempt,
)

OPENAI_COMPAT_BASE_URL_ENV = "HEPH_OPENAI_COMPAT_BASE_URL"
OPENAI_COMPAT_API_KEY_ENV = "HEPH_OPENAI_COMPAT_API_KEY"
OPENAI_COMPAT_MODEL_ENV = "HEPH_OPENAI_COMPAT_MODEL"
OPENAI_COMPAT_CONTEXT_WINDOW_ENV = "HEPH_OPENAI_COMPAT_CONTEXT_WINDOW"
OPENAI_COMPAT_INPUT_COST_ENV = "HEPH_OPENAI_COMPAT_INPUT_COST_PER_MILLION"
OPENAI_COMPAT_OUTPUT_COST_ENV = "HEPH_OPENAI_COMPAT_OUTPUT_COST_PER_MILLION"


class ProviderRequestError(RuntimeError):
    """Sanitized provider transport error safe for CLI and Studio display."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status_code: int | None = None,
        timeout_type: str | None = None,
        transient: bool = False,
        attempts: list[ModelTransportAttempt] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.timeout_type = timeout_type
        self.transient = transient
        self.attempts = attempts or []


class ProviderTimeouts(BaseModel):
    """Provider HTTP timeout settings in seconds."""

    model_config = ConfigDict(frozen=True)

    connect: float = Field(default=10.0, gt=0)
    read: float = Field(default=60.0, gt=0)
    write: float = Field(default=30.0, gt=0)
    pool: float = Field(default=10.0, gt=0)

    @classmethod
    def from_single(cls, timeout: float) -> ProviderTimeouts:
        return cls(connect=timeout, read=timeout, write=timeout, pool=timeout)


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
        cached_input_cost_per_million: float | None = None,
        output_cost_per_million: float | None = None,
        timeout: float = 60,
        timeouts: ProviderTimeouts | None = None,
        urlopen: UrlOpen | None = None,
        cost_metadata_source: str = "unknown",
        pricing_version: str | None = None,
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
        self.cached_input_cost_per_million = cached_input_cost_per_million
        self.output_cost_per_million: float = (
            output_cost_per_million
            if output_cost_per_million is not None
            else _float_env(OPENAI_COMPAT_OUTPUT_COST_ENV, default=0.0)
        )
        self.timeouts = timeouts or ProviderTimeouts.from_single(timeout)
        self.timeout = self.timeouts.read
        self._urlopen = (
            None
            if urlopen is None and os.getenv("HEPH_PROVIDER_TRANSPORT", "").lower() == "httpx"
            else urlopen or urllib.request.urlopen
        )
        self.cost_metadata_source = cost_metadata_source
        self.pricing_version = pricing_version

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
                cached_input_cost_per_million=(
                    max(0.0, self.cached_input_cost_per_million)
                    if self.cached_input_cost_per_million is not None
                    else None
                ),
                output_cost_per_million=max(0.0, self.output_cost_per_million),
                cost_metadata_source=self.cost_metadata_source,
                pricing_version=self.pricing_version,
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
        attempts: list[ModelTransportAttempt] = []
        max_attempts = min(request.max_transport_attempts, 2)
        for attempt_index in range(1, max_attempts + 1):
            started = time.monotonic()
            try:
                data = self._request_json(payload)
            except ProviderRequestError as error:
                latency_ms = _elapsed_ms(started)
                attempts.append(
                    ModelTransportAttempt(
                        attempt_index=attempt_index,
                        success=False,
                        error_code=error.code,
                        timeout_type=error.timeout_type,
                        status_code=error.status_code,
                        latency_ms=latency_ms,
                        transient=error.transient,
                    )
                )
                if not error.transient or attempt_index >= max_attempts:
                    error.attempts = attempts
                    raise error
                continue
            attempts.append(
                ModelTransportAttempt(
                    attempt_index=attempt_index,
                    success=True,
                    latency_ms=_elapsed_ms(started),
                )
            )
            return self._parse_response(data, model=model, request=request, attempts=attempts)
        raise ProviderRequestError(
            "transport_failed",
            "Provider request failed before receiving a response.",
            transient=True,
            attempts=attempts,
        )

    def _build_payload(self, request: ModelRequest, model: str) -> dict[str, Any]:
        messages = request.messages
        if messages is None:
            messages = []
            if request.system_prompt:
                messages.append({"role": "system", "content": request.system_prompt})
            messages.append({"role": "user", "content": request.prompt})
        payload: dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_output_tokens,
            "stream": False,
        }
        if request.require_json:
            payload["response_format"] = {"type": "json_object"}

        return payload

    def _request_json(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self._urlopen is not None:
            return self._request_json_urlopen(payload)
        return self._request_json_httpx(payload)

    def _request_json_urlopen(self, payload: dict[str, Any]) -> dict[str, Any]:
        urlopen = self._urlopen
        if urlopen is None:
            raise ProviderRequestError("transport_failed", "Provider transport is unavailable.")
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
            with urlopen(http_request, timeout=self.timeouts.read) as response:
                try:
                    body = response.read()
                except TimeoutError as error:
                    raise ProviderRequestError(
                        "read_timeout",
                        "Provider response read timed out.",
                        timeout_type="read",
                        transient=True,
                    ) from error
        except urllib.error.HTTPError as error:
            raise _provider_http_error(error) from None
        except TimeoutError as error:
            raise ProviderRequestError(
                "connect_timeout",
                "Provider connection timed out.",
                timeout_type="connect",
                transient=True,
            ) from error
        except urllib.error.URLError as error:
            if isinstance(error.reason, TimeoutError):
                raise ProviderRequestError(
                    "connect_timeout",
                    "Provider connection timed out.",
                    timeout_type="connect",
                    transient=True,
                ) from error
            raise ProviderRequestError(
                "connection_failed",
                "Could not connect to the provider endpoint.",
                transient=True,
            ) from error
        return _response_json_from_bytes(body)

    def _request_json_httpx(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        timeout = httpx.Timeout(
            connect=self.timeouts.connect,
            read=self.timeouts.read,
            write=self.timeouts.write,
            pool=self.timeouts.pool,
        )
        try:
            with httpx.Client(timeout=timeout) as client:
                response = client.post(
                    _chat_completions_url(self.base_url or ""),
                    content=json.dumps(payload).encode("utf-8"),
                    headers=headers,
                )
                if response.is_error:
                    raise _provider_http_error_from_status(response.status_code, response.text)
                return _response_json_from_bytes(response.content)
        except ProviderRequestError:
            raise
        except httpx.ConnectTimeout as error:
            raise ProviderRequestError(
                "connect_timeout",
                "Provider connection timed out.",
                timeout_type="connect",
                transient=True,
            ) from error
        except httpx.ReadTimeout as error:
            raise ProviderRequestError(
                "read_timeout",
                "Provider response read timed out.",
                timeout_type="read",
                transient=True,
            ) from error
        except httpx.WriteTimeout as error:
            raise ProviderRequestError(
                "write_timeout",
                "Provider request write timed out.",
                timeout_type="write",
                transient=True,
            ) from error
        except httpx.PoolTimeout as error:
            raise ProviderRequestError(
                "pool_timeout",
                "Provider connection pool timed out.",
                timeout_type="pool",
                transient=True,
            ) from error
        except (httpx.RemoteProtocolError, httpx.ReadError) as error:
            raise ProviderRequestError(
                "incomplete_response",
                "Provider response was incomplete or disconnected.",
                transient=True,
            ) from error
        except httpx.ConnectError as error:
            raise ProviderRequestError(
                "connection_failed",
                "Could not connect to the provider endpoint.",
                transient=True,
            ) from error
        except OSError as error:
            if getattr(error, "errno", None) in {12, 23, 24, 55}:
                raise ProviderRequestError(
                    "insufficient_system_resource",
                    "Local system resources were insufficient for the provider request.",
                ) from error
            raise ProviderRequestError(
                "connection_failed",
                "Could not connect to the provider endpoint.",
                transient=True,
            ) from error

    def _parse_response(
        self,
        data: dict[str, Any],
        *,
        model: str,
        request: ModelRequest,
        attempts: list[ModelTransportAttempt],
    ) -> ModelResponse:
        choice = cast(dict[str, Any], data["choices"][0])
        message = cast(dict[str, Any], choice["message"])
        text = str(message.get("content") or "")
        finish_reason = (
            str(choice["finish_reason"]) if choice.get("finish_reason") is not None else None
        )
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
            estimated_cost=profile.estimated_cost(
                input_tokens,
                output_tokens,
                cached_input_tokens=cached_input_tokens,
            ),
            cached_input_tokens=cached_input_tokens,
            usage_source="provider" if usage else "missing",
            cost_metadata_source=profile.cost_metadata_source,
            pricing_version=profile.pricing_version,
            finish_reason=finish_reason,
            response_truncated=finish_reason == "length",
            transport_attempts=attempts,
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
        body = error.read().decode("utf-8", errors="replace")
    return _provider_http_error_from_status(status, body)


def _provider_http_error_from_status(status: int, body_text: str) -> ProviderRequestError:
    body = body_text.lower()
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
            transient=True,
        )
    if status == 400 and any(
        marker in body for marker in ("model", "invalid_model", "model_not_found")
    ):
        return ProviderRequestError(
            "invalid_model",
            "The configured model ID is invalid or unavailable.",
            status_code=status,
        )
    if 500 <= status <= 599:
        return ProviderRequestError(
            "provider_server_error",
            f"Provider request failed with HTTP {status}.",
            status_code=status,
            transient=True,
        )
    return ProviderRequestError(
        "http_error",
        f"Provider request failed with HTTP {status}.",
        status_code=status,
    )


def _response_json_from_bytes(body: bytes) -> dict[str, Any]:
    try:
        text = body.decode("utf-8-sig", errors="replace").strip()
        if _looks_like_sse(text):
            text = _json_text_from_sse(text)
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ProviderRequestError(
            "invalid_response",
            "Provider returned an invalid chat-completions response.",
        ) from error
    if not isinstance(data, dict):
        raise ProviderRequestError(
            "invalid_response",
            "Provider returned an invalid chat-completions response.",
        )
    return data


def _looks_like_sse(text: str) -> bool:
    first = next((line.strip() for line in text.splitlines() if line.strip()), "")
    return first.startswith("data:") or first.startswith(":")


def _json_text_from_sse(text: str) -> str:
    data_lines: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith(":"):
            continue
        if not line.startswith("data:"):
            continue
        data = line.removeprefix("data:").strip()
        if data == "[DONE]":
            continue
        data_lines.append(data)
    if len(data_lines) != 1:
        raise ProviderRequestError(
            "invalid_response",
            "Provider returned an invalid streaming response.",
        )
    return data_lines[0]


def _elapsed_ms(started: float) -> int:
    return max(0, int((time.monotonic() - started) * 1000))
