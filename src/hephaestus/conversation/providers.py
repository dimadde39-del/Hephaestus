"""Provider discovery and routing for conversation synthesis."""

from __future__ import annotations

import os
from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from hephaestus.conversation.schemas import ConversationIntent, DeliberationMode
from hephaestus.core.config import PrivacyLevel
from hephaestus.models import (
    DeepSeekProvider,
    FakeModelProvider,
    ModelProfile,
    ModelProvider,
    OpenAICompatibleProvider,
)
from hephaestus.optimize.model_router import ModelRoute, ModelRouteRequest, route_model

CONVERSATION_PROVIDER_ENV = "HEPH_CONVERSATION_PROVIDER"
CONVERSATION_PROVIDER_AUTO = "auto"
CONVERSATION_PROVIDER_LOCAL = "local"
CONVERSATION_PROVIDER_REAL = "real"

CONVERSATION_ROLES = {
    "conversation",
    "summarization",
    "strategic_reasoning",
    "research_planning",
    "repo_question",
    "memory_extraction",
}


class ConversationProviderStatus(BaseModel):
    """Configuration status for a conversation-capable provider."""

    model_config = ConfigDict(frozen=True)

    provider: str
    available: bool
    detail: str = ""
    profile_count: int = Field(default=0, ge=0)


@dataclass(frozen=True)
class ConversationProviderPlan:
    """Selected provider/profile pair for one conversation model call."""

    provider: ModelProvider
    route: ModelRoute
    provider_mode: str

    @property
    def profile(self) -> ModelProfile:
        return self.route.profile

    @property
    def is_real_provider(self) -> bool:
        return self.profile.provider != "local"


def list_conversation_providers() -> list[ModelProvider]:
    """Return providers in deterministic preference order."""

    return [
        FakeModelProvider(),
        DeepSeekProvider(),
        OpenAICompatibleProvider(),
    ]


def conversation_provider_statuses() -> list[ConversationProviderStatus]:
    """Return provider configuration status for CLI visibility."""

    statuses: list[ConversationProviderStatus] = []
    for provider in list_conversation_providers():
        profiles = list(provider.profiles())
        statuses.append(
            ConversationProviderStatus(
                provider=_provider_display_name(provider),
                available=provider.is_available,
                detail=_provider_detail(provider),
                profile_count=len(profiles),
            )
        )
    return statuses


def conversation_model_profiles(*, include_unavailable: bool = True) -> list[ModelProfile]:
    """Return model profiles relevant to conversation routing."""

    profiles: list[ModelProfile] = []
    for provider in list_conversation_providers():
        if provider.is_available or include_unavailable or provider.name == "fake":
            profiles.extend(_conversation_profiles(provider.profiles()))
    return profiles


def select_conversation_provider(
    *,
    intent: ConversationIntent,
    mode: DeliberationMode,
    input_tokens: int,
    output_tokens: int,
    provider_mode: str | None = None,
) -> ConversationProviderPlan:
    """Route a conversation synthesis call to a configured provider."""

    requested_mode = _normalized_provider_mode(provider_mode)
    providers = list_conversation_providers()
    candidate_providers = _candidate_providers(providers, requested_mode)
    request = ModelRouteRequest(
        required_capabilities=_required_capabilities(intent, mode),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        quality_threshold=_quality_threshold(mode),
        privacy_level=PrivacyLevel.INTERNAL,
        needs_tools=False,
        needs_json=False,
        preferred_model_tags=_preferred_tags(intent, mode),
        profiles=[
            profile
            for provider in candidate_providers
            for profile in _conversation_profiles(provider.profiles())
        ],
    )
    route = route_model(request)
    provider = _provider_for_profile(candidate_providers, route.profile)
    return ConversationProviderPlan(
        provider=provider,
        route=route,
        provider_mode=requested_mode,
    )


def _candidate_providers(
    providers: Sequence[ModelProvider],
    provider_mode: str,
) -> list[ModelProvider]:
    local = [provider for provider in providers if _is_local_provider(provider)]
    real = [provider for provider in providers if provider.is_available and not _is_local_provider(provider)]

    if provider_mode in {CONVERSATION_PROVIDER_LOCAL, "fake"}:
        return local
    if provider_mode == CONVERSATION_PROVIDER_REAL:
        return real or local
    if provider_mode not in {CONVERSATION_PROVIDER_AUTO, ""}:
        named = [
            provider
            for provider in providers
            if provider.is_available and provider.name.lower() == provider_mode
        ]
        if named:
            return named
    return real or local


def _conversation_profiles(profiles: Sequence[ModelProfile]) -> list[ModelProfile]:
    return [
        profile
        for profile in profiles
        if not profile.intended_roles or "conversation" in profile.intended_roles
    ]


def _provider_for_profile(
    providers: Sequence[ModelProvider],
    profile: ModelProfile,
) -> ModelProvider:
    for provider in providers:
        if _is_local_provider(provider) and profile.provider == "local":
            return provider
        if provider.name == profile.provider:
            return provider
    raise ValueError(f"No provider instance found for selected profile: {profile.identifier}")


def _required_capabilities(
    intent: ConversationIntent,
    mode: DeliberationMode,
) -> set[str]:
    capabilities = {"general", "writing"}
    if mode in {
        DeliberationMode.STRATEGIC,
        DeliberationMode.CRITICAL,
        DeliberationMode.RESEARCH,
        DeliberationMode.ARCHITECT,
        DeliberationMode.SKEPTICAL_BUT_FAIR,
    }:
        capabilities.update({"analysis", "planning"})
    if intent == ConversationIntent.REPO_QUESTION:
        capabilities.update({"analysis", "repository-inspection"})
    if intent in {
        ConversationIntent.IDEA_STRESS_TEST,
        ConversationIntent.ROADMAP_DECISION,
        ConversationIntent.PRODUCT_STRATEGY,
        ConversationIntent.BUSINESS_STRATEGY,
        ConversationIntent.RISK_ANALYSIS,
    }:
        capabilities.update({"analysis", "planning"})
    return capabilities


def _preferred_tags(intent: ConversationIntent, mode: DeliberationMode) -> set[str]:
    tags = {"role:conversation"}
    if intent == ConversationIntent.REPO_QUESTION:
        tags.add("role:repo_question")
    if mode == DeliberationMode.RESEARCH or intent == ConversationIntent.RESEARCH_PLANNING:
        tags.add("role:research_planning")
    if mode in {
        DeliberationMode.STRATEGIC,
        DeliberationMode.CRITICAL,
        DeliberationMode.SKEPTICAL_BUT_FAIR,
    }:
        tags.add("role:strategic_reasoning")
    return tags


def _quality_threshold(mode: DeliberationMode) -> float:
    if mode in {
        DeliberationMode.STRATEGIC,
        DeliberationMode.CRITICAL,
        DeliberationMode.RESEARCH,
        DeliberationMode.ARCHITECT,
        DeliberationMode.SKEPTICAL_BUT_FAIR,
    }:
        return 0.84
    if mode == DeliberationMode.DIRECT:
        return 0.72
    return 0.76


def _normalized_provider_mode(provider_mode: str | None) -> str:
    raw = provider_mode if provider_mode is not None else os.getenv(CONVERSATION_PROVIDER_ENV)
    return (raw or CONVERSATION_PROVIDER_AUTO).strip().lower()


def _is_local_provider(provider: ModelProvider) -> bool:
    return provider.name == "fake"


def _provider_display_name(provider: ModelProvider) -> str:
    if _is_local_provider(provider):
        return "local/fake"
    return provider.name


def _provider_detail(provider: ModelProvider) -> str:
    if _is_local_provider(provider):
        return "deterministic local fallback; no API key required"
    if provider.name == "deepseek":
        if isinstance(provider, DeepSeekProvider):
            key = "DEEPSEEK_API_KEY" if provider.is_available else "no API key"
            thinking = (
                f"thinking={provider.reasoning_effort}"
                if provider.thinking_enabled
                else "thinking=disabled"
            )
            return (
                f"{key}; model={provider.model}; base_url={provider.base_url}; {thinking}; "
                f"max_output_tokens={provider.max_output_tokens}"
            )
        return "DEEPSEEK_API_KEY is set" if provider.is_available else "set DEEPSEEK_API_KEY"
    if provider.name == "openai-compatible":
        return (
            "HEPH_OPENAI_COMPAT_* provider is configured"
            if provider.is_available
            else "set HEPH_OPENAI_COMPAT_BASE_URL/API_KEY/MODEL"
        )
    return "configured" if provider.is_available else "not configured"
