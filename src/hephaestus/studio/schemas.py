"""Typed schemas for the local Studio API."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

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


class StudioLink(BaseModel):
    """A safe user-facing link to another Studio route."""

    model_config = ConfigDict(frozen=True)

    label: str
    href: str


class StudioMemoryKind(StrEnum):
    """Memory storage surfaces shown by Studio."""

    REGULAR = "regular"
    STRATEGIC = "strategic"


class StudioMemoryScope(StrEnum):
    """User-facing memory scope vocabulary."""

    GLOBAL = "global"
    PROJECT = "project"
    REPO = "repo"
    CONVERSATION = "conversation"


class StudioMemoryState(StrEnum):
    """Archive state filter for memory list queries."""

    ACTIVE = "active"
    ARCHIVED = "archived"
    ALL = "all"


class StudioMemoryEvidence(BaseModel):
    """Evidence displayed on a memory detail view."""

    model_config = ConfigDict(frozen=True)

    source: str = ""
    content: str
    kind: str = "conversation"
    source_id: str | None = None
    confidence: float = Field(default=0.7, ge=0, le=1)


class StudioMemoryHistoryItem(BaseModel):
    """A lightweight memory history entry when the database can infer one."""

    model_config = ConfigDict(frozen=True)

    at: datetime
    event: str
    detail: str = ""


class StudioMemorySummary(BaseModel):
    """Memory list item normalized across regular and strategic memory stores."""

    model_config = ConfigDict(frozen=True)

    id: str
    kind: StudioMemoryKind
    type: str
    type_label: str
    summary: str
    scope: StudioMemoryScope
    project: str | None = None
    repo_profile_id: str | None = None
    repo_name: str | None = None
    source: str
    confidence: float = Field(ge=0, le=1)
    importance: float = Field(ge=0, le=1)
    stability: str
    created_at: datetime
    updated_at: datetime
    archived: bool = False
    linked_conversation_id: str | None = None
    conflict_count: int = Field(default=0, ge=0)


class StudioMemoryDetail(StudioMemorySummary):
    """Full inspectable memory detail without embeddings or raw database payloads."""

    content: str
    evidence: list[StudioMemoryEvidence] = Field(default_factory=list)
    linked_conversation: StudioLink | None = None
    linked_work: list[StudioLink] = Field(default_factory=list)
    conflict_warnings: list[str] = Field(default_factory=list)
    history: list[StudioMemoryHistoryItem] = Field(default_factory=list)


class StudioMemoryListResponse(BaseModel):
    """Filtered memory list response."""

    model_config = ConfigDict(frozen=True)

    memories: list[StudioMemorySummary]
    total: int
    filters: dict[str, str | None]
    suggestions_pending: int = Field(default=0, ge=0)


class StudioMemoryCreateRequest(BaseModel):
    """Create a Studio-visible memory."""

    model_config = ConfigDict(frozen=True)

    kind: StudioMemoryKind = StudioMemoryKind.STRATEGIC
    type: str = "project_fact"
    content: str = Field(min_length=1)
    summary: str = ""
    scope: StudioMemoryScope = StudioMemoryScope.PROJECT
    project: str | None = "default"
    repo_profile_id: str | None = None
    conversation_id: str | None = None
    confidence: float = Field(default=0.75, ge=0, le=1)
    importance: float = Field(default=0.6, ge=0, le=1)
    stability: str = "medium_term"
    source: str = "manual"
    evidence: list[StudioMemoryEvidence] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)


class StudioMemoryPatchRequest(BaseModel):
    """Patch mutable memory metadata."""

    model_config = ConfigDict(frozen=True)

    type: str | None = None
    content: str | None = Field(default=None, min_length=1)
    summary: str | None = None
    scope: StudioMemoryScope | None = None
    project: str | None = None
    repo_profile_id: str | None = None
    conversation_id: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    importance: float | None = Field(default=None, ge=0, le=1)
    stability: str | None = None
    source: str | None = None
    evidence: list[StudioMemoryEvidence] | None = None
    tags: list[str] | None = None
    resolve_conflicts: bool = False


class StudioMemoryDeleteRequest(BaseModel):
    """Explicit confirmation for permanent memory deletion."""

    model_config = ConfigDict(frozen=True)

    confirm: bool = False


class StudioMemorySuggestion(BaseModel):
    """A pending memory suggestion requiring explicit user action."""

    model_config = ConfigDict(frozen=True)

    id: str
    proposed_memory: str
    why_it_may_matter: str
    proposed_type: str
    proposed_type_label: str
    proposed_scope: StudioMemoryScope
    proposed_stability: str
    source: str
    source_link: StudioLink | None = None
    confidence: float = Field(ge=0, le=1)
    importance: float = Field(ge=0, le=1)
    status: str
    created_at: datetime


class StudioMemorySuggestionListResponse(BaseModel):
    """Pending memory suggestion list."""

    model_config = ConfigDict(frozen=True)

    suggestions: list[StudioMemorySuggestion]
    total: int


class StudioMemorySuggestionSaveRequest(BaseModel):
    """Save a suggestion, optionally edited by the user."""

    model_config = ConfigDict(frozen=True)

    edited_memory: StudioMemoryCreateRequest | None = None


class StudioProviderStatus(StrEnum):
    """Provider configuration status shown in Studio."""

    CONFIGURED = "configured"
    TESTING = "testing"
    CONNECTED = "connected"
    NOT_CONFIGURED = "not_configured"
    CONNECTION_FAILED = "connection_failed"
    INSUFFICIENT_BALANCE = "insufficient_balance"
    LOCAL_MODE = "local_mode"


class StudioProviderConfig(BaseModel):
    """Redacted provider/model configuration."""

    model_config = ConfigDict(frozen=True)

    id: str
    provider_type: str
    name: str
    model: str
    base_url: str
    configured: bool
    status: StudioProviderStatus
    status_label: str
    status_detail: str
    intended_roles: list[str] = Field(default_factory=list)
    context_window: int | None = None
    input_cost_per_million: float | None = None
    output_cost_per_million: float | None = None
    thinking_enabled: bool = False
    reasoning_effort: str = "high"
    max_output_tokens: int | None = None
    effective_source: str = "studio"
    api_key_source: str = "not configured"
    default_for_conversation: bool = False
    created_at: datetime
    updated_at: datetime


class StudioProviderListResponse(BaseModel):
    """Provider settings response."""

    model_config = ConfigDict(frozen=True)

    providers: list[StudioProviderConfig]
    default_provider_id: str
    local_mode: StudioProviderConfig
    storage_note: str


class StudioProviderUpsertRequest(BaseModel):
    """Create or update a local provider configuration."""

    model_config = ConfigDict(frozen=True)

    provider_type: str = "openai-compatible"
    name: str = Field(min_length=1, max_length=80)
    model: str = ""
    base_url: str = ""
    api_key: str | None = Field(default=None, max_length=4096)
    context_window: int | None = Field(default=None, ge=1)
    input_cost_per_million: float | None = Field(default=None, ge=0)
    output_cost_per_million: float | None = Field(default=None, ge=0)
    thinking_enabled: bool = False
    reasoning_effort: str = Field(default="high", pattern="^(high|max)$")
    max_output_tokens: int | None = Field(default=None, ge=1)
    intended_roles: list[str] = Field(default_factory=lambda: ["conversation"])
    default_for_conversation: bool = False

    @model_validator(mode="before")
    @classmethod
    def apply_deepseek_defaults(cls, value: Any) -> Any:
        """Apply provider-specific defaults without overriding explicit choices."""

        if not isinstance(value, dict) or value.get("provider_type") != "deepseek":
            return value
        configured = dict(value)
        configured["model"] = configured.get("model") or "deepseek-v4-flash"
        configured["base_url"] = configured.get("base_url") or "https://api.deepseek.com"
        configured.setdefault("thinking_enabled", True)
        if configured.get("max_output_tokens") is None:
            configured["max_output_tokens"] = 4096
        if configured.get("context_window") is None:
            configured["context_window"] = 1_000_000
        return configured


class StudioProviderTestResponse(BaseModel):
    """Result of a provider connectivity test."""

    model_config = ConfigDict(frozen=True)

    id: str
    status: StudioProviderStatus
    message: str
    provider: str
    model: str
    latency_ms: int = Field(ge=0)


class StudioSettings(BaseModel):
    """Studio settings excluding secrets."""

    model_config = ConfigDict(frozen=True)

    startup_route: str = "/"
    recent_repo_behavior: str = "remember"
    browser_auto_open: bool = True
    appearance: str = "system"
    reduced_motion: bool = False
    density: str = "comfortable"
    active_policy_profile: str = "balanced"
    debug_logging: bool = False
    developer_details: bool = False
    deterministic_mode: bool = False


class StudioSettingsResponse(BaseModel):
    """Settings plus local API/database context."""

    model_config = ConfigDict(frozen=True)

    settings: StudioSettings
    database_path: str
    schema_version: int
    local_api_url: str
    static_assets_available: bool


class StudioSettingsPatchRequest(BaseModel):
    """Patch persisted Studio settings."""

    model_config = ConfigDict(frozen=True)

    startup_route: str | None = None
    recent_repo_behavior: str | None = None
    browser_auto_open: bool | None = None
    appearance: str | None = None
    reduced_motion: bool | None = None
    density: str | None = None
    active_policy_profile: str | None = None
    debug_logging: bool | None = None
    developer_details: bool | None = None
    deterministic_mode: bool | None = None


class StudioUsageEvent(BaseModel):
    """One user-facing model economy event."""

    model_config = ConfigDict(frozen=True)

    id: str
    task_type: str
    provider: str
    model: str
    provider_model: str
    message: str
    estimated_input_tokens: int = Field(ge=0)
    estimated_output_tokens: int = Field(ge=0)
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    cached_input_tokens: int = Field(default=0, ge=0)
    estimated_cost: float = Field(ge=0)
    thinking_enabled: bool = False
    reasoning_effort: str | None = None
    usage_source: str = "estimated"
    deterministic: bool
    context_trimmed: bool
    success: bool
    linked_conversation: StudioLink | None = None
    created_at: datetime


class StudioUsageAggregate(BaseModel):
    """Simple usage totals without vanity analytics."""

    model_config = ConfigDict(frozen=True)

    estimated_model_calls_this_week: int = Field(ge=0)
    deterministic_operations: int = Field(ge=0)
    estimated_cost: float = Field(ge=0)
    cost_per_validated_successful_coding_task: float | None = None
    provider_usage: dict[str, int] = Field(default_factory=dict)


class StudioUsageResponse(BaseModel):
    """Model usage and economy response."""

    model_config = ConfigDict(frozen=True)

    aggregate: StudioUsageAggregate
    events: list[StudioUsageEvent]
    estimate_note: str = "Token and cost values are estimates unless the provider returned usage."


class AdvancedArtifactSummary(BaseModel):
    """Common summary for secondary advanced artifacts."""

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    kind: str
    created_at: datetime
    linked_work: list[StudioLink] = Field(default_factory=list)


class AdvancedDecisionSummary(BaseModel):
    """Decision trace list item."""

    model_config = ConfigDict(frozen=True)

    id: str
    decision_type: str
    decision: str
    selected_option: str
    confidence: float = Field(ge=0, le=1)
    outcome: str | None = None
    repo: str | None = None
    occurred_at: datetime
    href: str


class AdvancedDecisionListResponse(BaseModel):
    """Filtered decision trace list."""

    model_config = ConfigDict(frozen=True)

    decisions: list[AdvancedDecisionSummary]
    total: int
    pareto_frontiers: list[AdvancedArtifactSummary] = Field(default_factory=list)
    qubo_problems: list[AdvancedArtifactSummary] = Field(default_factory=list)


class AdvancedDecisionDetail(AdvancedDecisionSummary):
    """Safe structured decision artifact without private chain-of-thought."""

    alternatives: list[str] = Field(default_factory=list)
    reasons: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    linked_work: list[StudioLink] = Field(default_factory=list)
    later_evidence_supported: str = "unknown"
    developer_payload: dict[str, Any] | None = None


class AdvancedParetoCandidate(BaseModel):
    """Candidate point for the Pareto viewer."""

    model_config = ConfigDict(frozen=True)

    id: str
    label: str
    x: float
    y: float
    is_frontier: bool
    selected: bool
    rationale: str = ""
    objectives: dict[str, float] = Field(default_factory=dict)


class AdvancedParetoDetail(BaseModel):
    """Readable Pareto frontier detail."""

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    objective_x: str
    objective_y: str
    selected_candidate_id: str | None
    preference_profile: str
    explanation: str
    tradeoffs: list[str] = Field(default_factory=list)
    candidates: list[AdvancedParetoCandidate] = Field(default_factory=list)
    created_at: datetime


class AdvancedQuboVariable(BaseModel):
    """Human-readable QUBO variable."""

    model_config = ConfigDict(frozen=True)

    id: str
    label: str
    selected: bool


class AdvancedQuboDetail(BaseModel):
    """Readable QUBO problem and local solver result."""

    model_config = ConfigDict(frozen=True)

    id: str
    purpose: str
    problem_type: str
    solver_used: str
    selected_solution: str
    objective_value: float | None = None
    feasible: bool | None = None
    variables: list[AdvancedQuboVariable] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    comparison_with_heuristic: str | None = None
    explanation: str
    mathematical_details: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class ConversationExportRequest(BaseModel):
    """Conversation export format request."""

    model_config = ConfigDict(frozen=True)

    format: str = "markdown"


class ExportResponse(BaseModel):
    """Inline export response safe to save from the UI."""

    model_config = ConfigDict(frozen=True)

    filename: str
    format: str
    content: str
    includes_secrets: bool = False


class BackupResponse(BaseModel):
    """Database backup response."""

    model_config = ConfigDict(frozen=True)

    path: str
    schema_version: int
    created_at: datetime
    size_bytes: int


class RestoreBackupRequest(BaseModel):
    """Restore a compatible local backup."""

    model_config = ConfigDict(frozen=True)

    backup_path: str
    confirm: bool = False


class RestoreBackupResponse(BaseModel):
    """Restore result."""

    model_config = ConfigDict(frozen=True)

    restored: bool
    message: str
    schema_version: int
