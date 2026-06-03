"""Model provider abstractions."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Annotated, Protocol

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
    output_cost_per_million: float = Field(ge=0)
    latency_score: QualityScore = 0.5
    quality_scores: dict[str, QualityScore] = Field(default_factory=dict)
    privacy_level: PrivacyLevel = PrivacyLevel.INTERNAL
    supports_tools: bool = False
    supports_json: bool = False

    @property
    def identifier(self) -> str:
        return f"{self.provider}/{self.model}"

    def estimated_cost(self, input_tokens: int, output_tokens: int) -> float:
        return (
            input_tokens / 1_000_000 * self.input_cost_per_million
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


class ModelResponse(BaseModel):
    """A provider-agnostic completion response."""

    text: str
    model: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    estimated_cost: float = Field(ge=0)


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
