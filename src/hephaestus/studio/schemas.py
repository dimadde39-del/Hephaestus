"""Typed schemas for the local Studio API."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from hephaestus.conversation.schemas import (
    ConversationIntent,
    ConversationRole,
    DeliberationMode,
)


class StudioStatus(StrEnum):
    """Small health status vocabulary for Studio responses."""

    OK = "ok"
    WARN = "warn"
    ERROR = "error"


class StudioHealthResponse(BaseModel):
    """Health response for the local Studio API."""

    model_config = ConfigDict(frozen=True)

    status: StudioStatus = StudioStatus.OK
    database_path: str
    static_assets_available: bool
    provider_label: str
    policy_profile: str


class StudioConfigResponse(BaseModel):
    """Non-secret local Studio configuration."""

    model_config = ConfigDict(frozen=True)

    app_name: str = "Hephaestus Studio"
    version: str
    database_path: str
    default_host: str
    default_port: int
    default_url: str
    static_assets_available: bool
    active_policy_profile: str
    provider_label: str
    local_mode_available: bool = True


class ConversationSummary(BaseModel):
    """Conversation metadata shown in the Studio sidebar."""

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    created_at: datetime
    updated_at: datetime
    mode: DeliberationMode
    repo_profile_id: str | None = None
    repo_name: str | None = None
    workspace_path: str | None = None
    is_pinned: bool = False
    is_archived: bool = False
    last_opened_at: datetime | None = None
    message_count: int = Field(default=0, ge=0)
    last_message_preview: str = ""
    linked_decision_count: int = Field(default=0, ge=0)
    coding_request_count: int = Field(default=0, ge=0)
    validation_run_count: int = Field(default=0, ge=0)


class ConversationDetail(BaseModel):
    """Full conversation metadata for the active Studio pane."""

    model_config = ConfigDict(frozen=True)

    conversation: ConversationSummary
    regular_memory_count: int = Field(default=0, ge=0)
    strategic_memory_count: int = Field(default=0, ge=0)
    linked_artifact_count: int = Field(default=0, ge=0)


class StudioMessage(BaseModel):
    """A persisted message as displayed by Studio."""

    model_config = ConfigDict(frozen=True)

    id: str
    session_id: str
    role: ConversationRole
    content: str
    created_at: datetime
    intent: ConversationIntent | None = None
    mode: DeliberationMode | None = None
    provider_model: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationListResponse(BaseModel):
    """Paginated conversation list response."""

    model_config = ConfigDict(frozen=True)

    conversations: list[ConversationSummary]
    limit: int
    offset: int
    total: int


class CreateConversationRequest(BaseModel):
    """Create an empty Studio conversation."""

    model_config = ConfigDict(frozen=True)

    title: str | None = Field(default=None, max_length=120)
    mode: DeliberationMode = DeliberationMode.BALANCED
    repo_profile_id: str | None = None
    workspace_path: str | None = None


class UpdateConversationRequest(BaseModel):
    """Patch mutable conversation metadata."""

    model_config = ConfigDict(frozen=True)

    title: str | None = Field(default=None, min_length=1, max_length=120)
    mode: DeliberationMode | None = None
    repo_profile_id: str | None = None
    workspace_path: str | None = None


class PinConversationRequest(BaseModel):
    """Pin or unpin a conversation."""

    model_config = ConfigDict(frozen=True)

    is_pinned: bool = True


class ArchiveConversationRequest(BaseModel):
    """Archive or restore a conversation."""

    model_config = ConfigDict(frozen=True)

    is_archived: bool = True


class PostMessageRequest(BaseModel):
    """Post one exact user message into an existing conversation."""

    model_config = ConfigDict(frozen=True)

    content: str = Field(min_length=1)
    mode: DeliberationMode | None = None
    repo_profile_id: str | None = None
    workspace_path: str | None = None
    provider: str = "auto"


class PostMessageResponse(BaseModel):
    """Result after the conversation service persists a user and agent turn."""

    model_config = ConfigDict(frozen=True)

    conversation: ConversationSummary
    messages: list[StudioMessage]
    assistant_message_id: str
    provider_model: str
    selected_memory_count: int = Field(default=0, ge=0)
    selected_strategic_memory_count: int = Field(default=0, ge=0)


class SearchResult(BaseModel):
    """A deterministic local search hit."""

    model_config = ConfigDict(frozen=True)

    conversation_id: str
    conversation_title: str
    match_type: str
    snippet: str
    message_id: str | None = None
    role: ConversationRole | None = None
    occurred_at: datetime | None = None
    is_archived: bool = False


class SearchResponse(BaseModel):
    """Search response across titles and messages."""

    model_config = ConfigDict(frozen=True)

    query: str
    results: list[SearchResult]


class ModeOption(BaseModel):
    """Mode selector option."""

    model_config = ConfigDict(frozen=True)

    value: DeliberationMode
    label: str
    description: str


class PolicyProfileResponse(BaseModel):
    """Active policy profile summary."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    profile_type: str
    description: str


class ProviderStatusItem(BaseModel):
    """Provider availability summary without secrets."""

    model_config = ConfigDict(frozen=True)

    provider: str
    label: str
    available: bool
    detail: str
    profile_count: int = Field(default=0, ge=0)
    local: bool = False


class ProviderStatusResponse(BaseModel):
    """Provider status shown by Studio."""

    model_config = ConfigDict(frozen=True)

    active_label: str
    active_provider: str
    statuses: list[ProviderStatusItem]


class RecentRepo(BaseModel):
    """A recent repository profile option."""

    model_config = ConfigDict(frozen=True)

    id: str
    name: str
    path: str
    stack_summary: str
    inspected_at: datetime


class StudioError(BaseModel):
    """Actionable Studio API error payload."""

    model_config = ConfigDict(frozen=True)

    code: str
    message: str
