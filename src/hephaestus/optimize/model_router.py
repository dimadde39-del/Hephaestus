"""Quality-preserving model routing."""

from __future__ import annotations

from pydantic import BaseModel, Field

from hephaestus.core.config import PrivacyLevel
from hephaestus.models.base import ModelProfile


class RejectedModel(BaseModel):
    identifier: str
    reason: str


class ModelRouteRequest(BaseModel):
    """Routing request for one task or model call."""

    required_capabilities: set[str] = Field(default_factory=set)
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    quality_threshold: float = Field(default=0.72, ge=0, le=1)
    privacy_level: PrivacyLevel = PrivacyLevel.INTERNAL
    needs_tools: bool = False
    needs_json: bool = False
    preferred_model_tags: set[str] = Field(default_factory=set)
    avoided_model_tags: set[str] = Field(default_factory=set)
    profiles: list[ModelProfile]


class ModelRoute(BaseModel):
    profile: ModelProfile
    estimated_cost: float = Field(ge=0)
    quality: float = Field(ge=0, le=1)
    rejected: list[RejectedModel] = Field(default_factory=list)
    explanation: str


class ModelRoutingError(ValueError):
    """Raised when no model can satisfy quality/safety constraints."""


def route_model(request: ModelRouteRequest) -> ModelRoute:
    """Select the cheapest valid model that satisfies quality constraints."""

    rejected: list[RejectedModel] = []
    candidates: list[tuple[int, float, float, ModelProfile]] = []
    total_tokens = request.input_tokens + request.output_tokens

    for profile in request.profiles:
        reason = _rejection_reason(profile, request, total_tokens)
        if reason:
            rejected.append(RejectedModel(identifier=profile.identifier, reason=reason))
            continue
        quality = profile.quality_for(request.required_capabilities)
        if quality < request.quality_threshold:
            rejected.append(
                RejectedModel(
                    identifier=profile.identifier,
                    reason=(
                        f"quality {quality:.2f} below threshold {request.quality_threshold:.2f}"
                    ),
                )
            )
            continue
        cost = profile.estimated_cost(request.input_tokens, request.output_tokens)
        preference_rank = 0 if _matches_any_tag(profile, request.preferred_model_tags) else 1
        candidates.append((preference_rank, cost, -quality, profile))

    if not candidates:
        reasons = "; ".join(f"{item.identifier}: {item.reason}" for item in rejected)
        raise ModelRoutingError(f"No model satisfied routing constraints. Rejections: {reasons}")

    _, cost, negative_quality, selected = sorted(candidates, key=lambda item: item[:3])[0]
    quality = -negative_quality
    return ModelRoute(
        profile=selected,
        estimated_cost=cost,
        quality=quality,
        rejected=rejected,
        explanation=(
            f"Selected {selected.identifier}: cheapest valid model at ${cost:.6f} "
            f"with quality {quality:.2f} >= {request.quality_threshold:.2f}."
        ),
    )


def _rejection_reason(
    profile: ModelProfile,
    request: ModelRouteRequest,
    total_tokens: int,
) -> str | None:
    if not request.required_capabilities.issubset(profile.capabilities):
        missing = sorted(request.required_capabilities - profile.capabilities)
        return f"missing capabilities: {', '.join(missing)}"
    avoided_tags = _matched_tags(profile, request.avoided_model_tags)
    if avoided_tags:
        return f"avoided by active profile: {', '.join(avoided_tags)}"
    if total_tokens > profile.context_window:
        return f"context window {profile.context_window} below {total_tokens} tokens"
    if request.needs_tools and not profile.supports_tools:
        return "tool support required"
    if request.needs_json and not profile.supports_json:
        return "JSON support required"
    if not profile.can_handle(request.required_capabilities, request.privacy_level):
        return f"privacy level {profile.privacy_level} cannot handle {request.privacy_level}"
    return None


def _matches_any_tag(profile: ModelProfile, tags: set[str]) -> bool:
    return bool(_matched_tags(profile, tags))


def _matched_tags(profile: ModelProfile, tags: set[str]) -> list[str]:
    if not tags:
        return []
    normalized = {tag.lower() for tag in tags}
    profile_tags = _profile_tags(profile)
    return sorted(normalized.intersection(profile_tags))


def _profile_tags(profile: ModelProfile) -> set[str]:
    return {
        profile.identifier.lower(),
        profile.provider.lower(),
        profile.model.lower(),
        f"provider:{profile.provider}".lower(),
        f"model:{profile.model}".lower(),
        *{capability.lower() for capability in profile.capabilities},
    }
