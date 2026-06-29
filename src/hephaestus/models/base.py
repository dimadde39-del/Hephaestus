"""Model provider abstractions."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from hephaestus.core.config import PrivacyLevel

QualityScore = Annotated[float, Field(ge=0, le=1)]


class ModelProfile(BaseModel):
    """Capabilities, costs, quality, and safety properties for a model."""

    model_config = ConfigDict(frozen=True)

    provider: str
    model: str
    capabilities: set[str] = Field(default_factory=set)
    context_window: int = Field(gt=0)
    input_cost_per_million: float = Field(ge=0)
    cached_input_cost_per_million: float | None = Field(default=None, ge=0)
    output_cost_per_million: float = Field(ge=0)
    cost_metadata_source: str = "unknown"
    pricing_version: str | None = None
    latency_score: QualityScore = 0.5
    quality_scores: dict[str, QualityScore] = Field(default_factory=dict)
    privacy_level: PrivacyLevel = PrivacyLevel.INTERNAL
    supports_tools: bool = False
    supports_json: bool = False
    supports_streaming: bool = False
    intended_roles: set[str] = Field(default_factory=set)

    @property
    def identifier(self) -> str:
        return f"{self.provider}/{self.model}"

    def estimated_cost(
        self,
        input_tokens: int,
        output_tokens: int,
        *,
        cached_input_tokens: int = 0,
    ) -> float:
        uncached_input_tokens = max(0, input_tokens - cached_input_tokens)
        cached_rate = (
            self.cached_input_cost_per_million
            if self.cached_input_cost_per_million is not None
            else self.input_cost_per_million
        )
        return (
            uncached_input_tokens / 1_000_000 * self.input_cost_per_million
            + cached_input_tokens / 1_000_000 * cached_rate
            + output_tokens / 1_000_000 * self.output_cost_per_million
        )

    def quality_for(self, required_capabilities: set[str]) -> float:
        """Return the weakest relevant quality score for required capabilities."""

        if not required_capabilities:
            return self.quality_scores.get("general", 0.0)

        scores: list[float] = []
        for capability in required_capabilities:
            if capability in self.quality_scores:
                scores.append(self.quality_scores[capability])
            elif capability in self.capabilities:
                scores.append(self.quality_scores.get("general", 0.0))
            else:
                scores.append(0.0)
        return min(scores)

    def can_handle(self, required_capabilities: set[str], required_privacy: PrivacyLevel) -> bool:
        return required_capabilities.issubset(self.capabilities) and _privacy_allows(
            self.privacy_level, required_privacy
        )


class ModelRequest(BaseModel):
    """A provider-agnostic completion request."""

    prompt: str
    model: str | None = None
    temperature: float = Field(default=0.0, ge=0, le=2)
    max_output_tokens: int = Field(default=1_000, gt=0)
    require_json: bool = False
    thinking_enabled: bool | None = None
    reasoning_effort: str | None = None
    messages: list[dict[str, Any]] | None = None
    system_prompt: str | None = None
    max_transport_attempts: int = Field(default=1, ge=1, le=3)
    call_kind: str = "completion"


class ModelTransportAttempt(BaseModel):
    """One HTTP/network attempt for a logical model call."""

    model_config = ConfigDict(frozen=True)

    attempt_index: int = Field(ge=1)
    success: bool
    error_code: str = ""
    timeout_type: str | None = None
    status_code: int | None = None
    latency_ms: int = Field(default=0, ge=0)
    transient: bool = False


class ModelResponse(BaseModel):
    """A provider-agnostic completion response."""

    text: str
    model: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated_cost: float = Field(ge=0)
    cached_input_tokens: int = Field(default=0, ge=0)
    usage_source: str = "provider"
    cost_metadata_source: str = "unknown"
    pricing_version: str | None = None
    finish_reason: str | None = None
    response_truncated: bool = False
    transport_attempts: list[ModelTransportAttempt] = Field(default_factory=list)
    thinking_enabled: bool = False
    reasoning_effort: str | None = None
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    reasoning_content: str | None = Field(default=None, exclude=True, repr=False)


class ModelProvider(Protocol):
    """Protocol implemented by local, fake, and API-backed providers."""

    @property
    def name(self) -> str: ...

    @property
    def is_available(self) -> bool: ...

    def profiles(self) -> Sequence[ModelProfile]: ...

    def complete(self, request: ModelRequest) -> ModelResponse: ...


def _privacy_allows(model_privacy: PrivacyLevel, required_privacy: PrivacyLevel) -> bool:
    order = {
        PrivacyLevel.PUBLIC: 0,
        PrivacyLevel.INTERNAL: 1,
        PrivacyLevel.PRIVATE: 2,
        PrivacyLevel.SECRET: 3,
    }
    return order[model_privacy] >= order[required_privacy]
