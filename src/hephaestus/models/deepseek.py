"""Optional DeepSeek provider."""

from __future__ import annotations

import json
import os
import urllib.request
from collections.abc import Sequence
from typing import Any

from hephaestus.core.config import PrivacyLevel
from hephaestus.models.base import ModelProfile, ModelRequest, ModelResponse

DEEPSEEK_API_KEY_ENV = "DEEPSEEK_API_KEY"
DEEPSEEK_BASE_URL = "https://api.deepseek.com/chat/completions"


class DeepSeekProvider:
    """Optional provider that is inactive until DEEPSEEK_API_KEY is set."""

    name = "deepseek"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key if api_key is not None else os.getenv(DEEPSEEK_API_KEY_ENV)

    @property
    def is_available(self) -> bool:
        return bool(self.api_key)

    def profiles(self) -> Sequence[ModelProfile]:
        return [
            ModelProfile(
                provider="deepseek",
                model="deepseek-v4-flash",
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
                context_window=1_000_000,
                input_cost_per_million=0.14,
                output_cost_per_million=0.28,
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
            ),
            ModelProfile(
                provider="deepseek",
                model="deepseek-v4-pro",
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
                context_window=1_000_000,
                input_cost_per_million=0.435,
                output_cost_per_million=0.87,
                latency_score=0.55,
                quality_scores={
                    "analysis": 0.9,
                    "coding": 0.88,
                    "general": 0.88,
                    "planning": 0.9,
                    "reasoning": 0.9,
                    "repository-inspection": 0.88,
                    "safety": 0.86,
                    "tool-use": 0.86,
                    "writing": 0.88,
                },
                privacy_level=PrivacyLevel.INTERNAL,
                supports_tools=True,
                supports_json=True,
            ),
        ]

    def complete(self, request: ModelRequest) -> ModelResponse:
        if not self.api_key:
            raise RuntimeError(
                f"DeepSeek provider unavailable. Set {DEEPSEEK_API_KEY_ENV} to enable it."
            )

        model = request.model or "deepseek-v4-flash"
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
            DEEPSEEK_BASE_URL,
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
        profile = next(profile for profile in self.profiles() if profile.model == model)
        return ModelResponse(
            text=text,
            model=f"deepseek/{model}",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost=profile.estimated_cost(input_tokens, output_tokens),
        )
