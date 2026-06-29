"""Application services for Hephaestus Studio."""

from __future__ import annotations

from pathlib import Path

from hephaestus import __version__
from hephaestus.conversation.analysis import title_from_prompt
from hephaestus.conversation.providers import (
    conversation_provider_statuses,
)
from hephaestus.conversation.schemas import ConversationRequest, DeliberationMode
from hephaestus.conversation.session import ConversationService
from hephaestus.models import ModelProvider
from hephaestus.policy.repository import PolicyRepository
from hephaestus.repo.repository import RepoProfileRepository
from hephaestus.storage.sqlite import get_default_database_path
from hephaestus.studio.experience import StudioExperienceRepository
from hephaestus.studio.repository import EMPTY_CONVERSATION_TITLE, StudioRepository
from hephaestus.studio.schemas import (
    AdvancedDecisionDetail,
    AdvancedDecisionListResponse,
    AdvancedParetoDetail,
    AdvancedQuboDetail,
    ArchiveConversationRequest,
    BackupResponse,
    ConversationDetail,
    ConversationExportRequest,
    ConversationListResponse,
    ConversationSummary,
    CreateConversationRequest,
    ExportResponse,
    ModeOption,
    PinConversationRequest,
    PolicyProfileResponse,
    PostMessageRequest,
    PostMessageResponse,
    ProviderStatusItem,
    ProviderStatusResponse,
    RecentRepo,
    RestoreBackupResponse,
    SearchResponse,
    StudioConfigResponse,
    StudioHealthResponse,
    StudioMemoryCreateRequest,
    StudioMemoryDeleteRequest,
    StudioMemoryDetail,
    StudioMemoryListResponse,
    StudioMemoryPatchRequest,
    StudioMemoryScope,
    StudioMemoryState,
    StudioMemorySuggestionListResponse,
    StudioMemorySuggestionSaveRequest,
    StudioMessage,
    StudioProviderConfig,
    StudioProviderListResponse,
    StudioProviderPatchRequest,
    StudioProviderTestResponse,
    StudioProviderUpsertRequest,
    StudioSettingsPatchRequest,
    StudioSettingsResponse,
    StudioUsageResponse,
    UpdateConversationRequest,
)
from hephaestus.studio.security import studio_url
from hephaestus.studio.workbench import WorkbenchService


class StudioService:
    """Coordinate Studio API calls with existing Hephaestus conversation services."""

    def __init__(
        self,
        database_path: Path | str | None = None,
        *,
        provider: ModelProvider | None = None,
        static_assets_available: bool = False,
    ) -> None:
        self.database_path = (
            Path(database_path) if database_path is not None else get_default_database_path()
        )
        self.repository = StudioRepository(self.database_path)
        self.provider_override = provider
        self.conversation_service = ConversationService(self.database_path, provider=provider)
        self.policy_repository = PolicyRepository(self.database_path)
        self.repo_repository = RepoProfileRepository(self.database_path)
        self.workbench = WorkbenchService(self.database_path)
        self.experience = StudioExperienceRepository(self.database_path)
        self.static_assets_available = static_assets_available

    def health(self) -> StudioHealthResponse:
        """Return local health without exposing secrets or file contents."""

        active_policy = self.policy_repository.get_active_profile()
        return StudioHealthResponse(
            database_path=str(self.database_path),
            static_assets_available=self.static_assets_available,
            provider_label=self.provider_status().active_label,
            policy_profile=active_policy.name,
        )

    def config(self, *, host: str = "127.0.0.1", port: int = 8741) -> StudioConfigResponse:
        """Return non-secret local Studio configuration."""

        active_policy = self.policy_repository.get_active_profile()
        return StudioConfigResponse(
            version=__version__,
            database_path=str(self.database_path),
            default_host=host,
            default_port=port,
            default_url=f"http://{host}:{port}",
            static_assets_available=self.static_assets_available,
            active_policy_profile=active_policy.name,
            provider_label=self.provider_status().active_label,
        )

    def list_conversations(
        self,
        *,
        query: str = "",
        include_archived: bool = False,
        archived_only: bool = False,
        repo_profile_id: str | None = None,
        workspace_path: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> ConversationListResponse:
        """List conversations for the sidebar."""

        conversations, total = self.repository.list_conversations(
            query=query,
            include_archived=include_archived,
            archived_only=archived_only,
            repo_profile_id=repo_profile_id,
            workspace_path=workspace_path,
            limit=limit,
            offset=offset,
        )
        return ConversationListResponse(
            conversations=conversations,
            limit=limit,
            offset=offset,
            total=total,
        )

    def create_conversation(self, request: CreateConversationRequest) -> ConversationSummary:
        """Create an empty persistent conversation."""

        title = _normalized_title(request.title) or EMPTY_CONVERSATION_TITLE
        return self.repository.create_conversation(
            title=title,
            mode=request.mode,
            repo_profile_id=request.repo_profile_id,
            workspace_path=request.workspace_path,
            manual_title=request.title is not None and bool(request.title.strip()),
        )

    def conversation_detail(self, session_id: str) -> ConversationDetail | None:
        """Open a conversation without generating a summary or recap."""

        summary = self.repository.touch_opened(session_id)
        if summary is None:
            return None
        return ConversationDetail(
            conversation=summary,
            regular_memory_count=self.repository.count_regular_memories(),
            strategic_memory_count=self.repository.count_strategic_memories(),
            linked_artifact_count=(
                summary.linked_decision_count
                + summary.coding_request_count
                + summary.validation_run_count
            ),
        )

    def list_messages(self, session_id: str) -> list[StudioMessage] | None:
        """Return exact persisted messages for a session."""

        if self.repository.get_session(session_id) is None:
            return None
        return self.repository.list_messages(session_id)

    def post_message(
        self,
        session_id: str,
        request: PostMessageRequest,
    ) -> PostMessageResponse:
        """Persist a user message, invoke the existing conversation pipeline, and return the turn."""

        if not request.content.strip():
            raise ValueError("Message content cannot be blank.")
        session = self.repository.get_session(session_id)
        if session is None:
            raise KeyError(session_id)
        mode = request.mode or session.mode
        repo_path = self._repo_path_for_request(request)
        workspace_path = request.workspace_path
        self.repository.patch_context(
            session_id,
            mode=mode,
            repo_profile_id=request.repo_profile_id,
            workspace_path=workspace_path,
            repo_profile_id_provided="repo_profile_id" in request.model_fields_set,
            workspace_path_provided="workspace_path" in request.model_fields_set,
        )
        self._maybe_set_initial_title(session_id, request.content)
        provider_override = (
            self.provider_override
            if self.provider_override is not None
            else self.experience.default_provider()
            if request.provider == "auto"
            else None
        )
        conversation_service = ConversationService(
            self.database_path,
            provider=provider_override,
        )
        response = conversation_service.respond(
            ConversationRequest(
                prompt=request.content,
                mode=mode,
                session_id=session_id,
                repo_path=repo_path,
                provider=request.provider,
            )
        )
        summary = self.repository.get_summary(session_id)
        if summary is None:
            raise RuntimeError("Conversation disappeared after message persistence.")
        messages = self.repository.list_messages(session_id)
        self.experience.record_conversation_usage(
            conversation_id=session_id,
            message_id=response.message_id,
            provider_model=response.provider_model,
            estimated_input_tokens=response.input_tokens,
            estimated_output_tokens=response.output_tokens,
            estimated_cost=response.estimated_cost,
            context_trimmed=response.budget.context_trimmed,
            input_tokens=response.input_tokens,
            output_tokens=response.output_tokens,
            cached_input_tokens=response.cached_input_tokens,
            thinking_enabled=response.thinking_enabled,
            reasoning_effort=response.reasoning_effort,
            success=response.provider_success,
        )
        return PostMessageResponse(
            conversation=summary,
            messages=messages,
            assistant_message_id=response.message_id,
            provider_model=response.provider_model,
            selected_memory_count=len(response.selected_memory_ids),
            selected_strategic_memory_count=len(response.selected_strategic_memory_ids),
        )

    def update_conversation(
        self,
        session_id: str,
        request: UpdateConversationRequest,
    ) -> ConversationSummary | None:
        """Patch editable conversation metadata."""

        summary: ConversationSummary | None = self.repository.get_summary(session_id)
        if summary is None:
            return None
        if request.title is not None:
            summary = self.repository.rename_conversation(
                session_id,
                _normalized_title(request.title) or EMPTY_CONVERSATION_TITLE,
                manual=True,
            )
        repo_profile_id_provided = "repo_profile_id" in request.model_fields_set
        workspace_path_provided = "workspace_path" in request.model_fields_set
        if request.mode is not None or repo_profile_id_provided or workspace_path_provided:
            summary = self.repository.patch_context(
                session_id,
                mode=request.mode,
                repo_profile_id=request.repo_profile_id,
                workspace_path=request.workspace_path,
                repo_profile_id_provided=repo_profile_id_provided,
                workspace_path_provided=workspace_path_provided,
            )
        return summary

    def pin_conversation(
        self,
        session_id: str,
        request: PinConversationRequest,
    ) -> ConversationSummary | None:
        """Pin or unpin a conversation."""

        return self.repository.set_pin(session_id, is_pinned=request.is_pinned)

    def archive_conversation(
        self,
        session_id: str,
        request: ArchiveConversationRequest,
    ) -> ConversationSummary | None:
        """Archive or restore a conversation."""

        return self.repository.set_archive(session_id, is_archived=request.is_archived)

    def search(
        self,
        *,
        query: str,
        include_archived: bool = False,
        limit: int = 30,
    ) -> SearchResponse:
        """Search conversation titles and exact messages locally."""

        return SearchResponse(
            query=query,
            results=self.repository.search(query, include_archived=include_archived, limit=limit),
        )

    def modes(self) -> list[ModeOption]:
        """Return supported conversational modes."""

        return [
            ModeOption(
                value=DeliberationMode.BALANCED,
                label="Balanced",
                description="Default: useful reasoning with moderate detail.",
            ),
            ModeOption(
                value=DeliberationMode.DIRECT,
                label="Direct",
                description="Shorter, practical answers with less exploration.",
            ),
            ModeOption(
                value=DeliberationMode.CRITICAL,
                label="Critical",
                description="Sharper review of risks, weak assumptions, and tradeoffs.",
            ),
            ModeOption(
                value=DeliberationMode.STRATEGIC,
                label="Strategic",
                description="Longer-horizon project, product, and sequencing thinking.",
            ),
            ModeOption(
                value=DeliberationMode.RESEARCH,
                label="Research",
                description="Structured research planning without inventing facts.",
            ),
            ModeOption(
                value=DeliberationMode.ARCHITECT,
                label="Architect",
                description="System design, interfaces, and technical constraints.",
            ),
            ModeOption(
                value=DeliberationMode.COACH,
                label="Coach",
                description="Supportive reflection with practical next moves.",
            ),
            ModeOption(
                value=DeliberationMode.SKEPTICAL_BUT_FAIR,
                label="Skeptical but fair",
                description="Honest pressure-testing without default pessimism.",
            ),
        ]

    def active_policy(self) -> PolicyProfileResponse:
        """Expose the active policy profile without policy internals."""

        profile = self.policy_repository.get_active_profile()
        return PolicyProfileResponse(
            id=profile.id,
            name=profile.name,
            profile_type=profile.profile_type.value,
            description=profile.description,
        )

    def provider_status(self) -> ProviderStatusResponse:
        """Expose provider status without secrets."""

        statuses = [
            ProviderStatusItem(
                provider=status.provider,
                label=_provider_label(status.provider),
                available=status.available,
                detail=status.detail,
                profile_count=status.profile_count,
                local=status.provider == "local/fake",
            )
            for status in conversation_provider_statuses()
        ]
        active = next(
            (status for status in statuses if status.available and not status.local),
            statuses[0],
        )
        return ProviderStatusResponse(
            active_label=active.label,
            active_provider=active.provider,
            statuses=statuses,
        )

    def recent_repos(self, *, limit: int = 20) -> list[RecentRepo]:
        """Return recent repo profiles for optional context attachment."""

        return self.repository.list_recent_repos(limit=limit)

    def list_memories(
        self,
        *,
        query: str = "",
        type_filter: str | None = None,
        scope: StudioMemoryScope | None = None,
        project: str | None = None,
        repo_profile_id: str | None = None,
        source: str | None = None,
        stability: str | None = None,
        state: StudioMemoryState = StudioMemoryState.ACTIVE,
        limit: int = 200,
    ) -> StudioMemoryListResponse:
        """List Studio-visible memories."""

        return self.experience.list_memories(
            query=query,
            type_filter=type_filter,
            scope=scope,
            project=project,
            repo_profile_id=repo_profile_id,
            source=source,
            stability=stability,
            state=state,
            limit=limit,
        )

    def get_memory(self, memory_id: str) -> StudioMemoryDetail | None:
        """Return one Studio-visible memory."""

        return self.experience.get_memory(memory_id)

    def create_memory(self, request: StudioMemoryCreateRequest) -> StudioMemoryDetail:
        """Create a memory from Studio."""

        return self.experience.create_memory(request)

    def patch_memory(
        self,
        memory_id: str,
        request: StudioMemoryPatchRequest,
    ) -> StudioMemoryDetail | None:
        """Patch a memory from Studio."""

        return self.experience.patch_memory(memory_id, request)

    def archive_memory(self, memory_id: str) -> StudioMemoryDetail | None:
        """Archive one memory."""

        return self.experience.archive_memory(memory_id)

    def restore_memory(self, memory_id: str) -> StudioMemoryDetail | None:
        """Restore one archived memory."""

        return self.experience.restore_memory(memory_id)

    def delete_memory(
        self,
        memory_id: str,
        request: StudioMemoryDeleteRequest,
    ) -> bool:
        """Permanently delete one memory."""

        return self.experience.delete_memory(memory_id, request)

    def list_memory_suggestions(self) -> StudioMemorySuggestionListResponse:
        """List pending memory suggestions."""

        return self.experience.list_memory_suggestions()

    def save_memory_suggestion(
        self,
        suggestion_id: str,
        request: StudioMemorySuggestionSaveRequest,
    ) -> StudioMemoryDetail | None:
        """Save a reviewed memory suggestion."""

        return self.experience.save_memory_suggestion(suggestion_id, request)

    def ignore_memory_suggestion(self, suggestion_id: str) -> bool:
        """Ignore a pending memory suggestion."""

        return self.experience.ignore_memory_suggestion(suggestion_id)

    def providers(self) -> StudioProviderListResponse:
        """Return redacted provider configuration."""

        return self.experience.list_providers()

    def create_provider(self, request: StudioProviderUpsertRequest) -> StudioProviderConfig:
        """Create a provider configuration."""

        return self.experience.create_provider(request)

    def update_provider(
        self,
        provider_id: str,
        request: StudioProviderPatchRequest,
    ) -> StudioProviderConfig | None:
        """Update a provider configuration."""

        return self.experience.update_provider(provider_id, request)

    def delete_provider(self, provider_id: str) -> bool:
        """Remove a provider configuration."""

        return self.experience.delete_provider(provider_id)

    def test_provider(self, provider_id: str) -> StudioProviderTestResponse | None:
        """Test a provider configuration."""

        return self.experience.test_provider(provider_id)

    def settings(self, *, host: str = "127.0.0.1", port: int = 8741) -> StudioSettingsResponse:
        """Return Studio settings."""

        return self.experience.get_settings(
            database_path=str(self.database_path),
            local_api_url=studio_url(host, port),
            static_assets_available=self.static_assets_available,
        )

    def patch_settings(
        self,
        request: StudioSettingsPatchRequest,
        *,
        host: str = "127.0.0.1",
        port: int = 8741,
    ) -> StudioSettingsResponse:
        """Patch Studio settings."""

        return self.experience.patch_settings(
            request,
            database_path=str(self.database_path),
            local_api_url=studio_url(host, port),
            static_assets_available=self.static_assets_available,
        )

    def usage(self, *, limit: int = 100) -> StudioUsageResponse:
        """Return model usage and economy data."""

        return self.experience.usage(limit=limit)

    def decisions(
        self,
        *,
        category: str | None = None,
        repo: str | None = None,
        limit: int = 100,
    ) -> AdvancedDecisionListResponse:
        """Return secondary decision traces."""

        return self.experience.list_decisions(category=category, repo=repo, limit=limit)

    def decision_detail(self, trace_id: str) -> AdvancedDecisionDetail | None:
        """Return one secondary decision trace."""

        return self.experience.decision_detail(trace_id)

    def pareto_detail(self, frontier_id: str) -> AdvancedParetoDetail | None:
        """Return one Pareto frontier detail."""

        return self.experience.pareto_detail(frontier_id)

    def qubo_detail(self, problem_id: str) -> AdvancedQuboDetail | None:
        """Return one QUBO detail."""

        return self.experience.qubo_detail(problem_id)

    def export_conversation(
        self,
        conversation_id: str,
        request: ConversationExportRequest,
    ) -> ExportResponse | None:
        """Export one conversation."""

        return self.experience.export_conversation(conversation_id, request)

    def export_memories(self) -> ExportResponse:
        """Export memories."""

        return self.experience.export_memories()

    def backup(self) -> BackupResponse:
        """Create a database backup."""

        return self.experience.backup_database()

    def restore(self, *, backup_path: str, confirm: bool) -> RestoreBackupResponse:
        """Restore a compatible backup."""

        return self.experience.restore_database(backup_path, confirm=confirm)

    def _repo_path_for_request(self, request: PostMessageRequest) -> str | None:
        if request.workspace_path is not None:
            return request.workspace_path
        if request.repo_profile_id is None:
            return None
        profile = self.repo_repository.get_profile(request.repo_profile_id)
        if profile is None:
            raise ValueError(f"Repo profile not found: {request.repo_profile_id}")
        return profile.path

    def _maybe_set_initial_title(self, session_id: str, prompt: str) -> None:
        session = self.repository.get_session(session_id)
        if session is None:
            return
        if session.metadata.get("manual_title"):
            return
        if self.repository.message_count(session_id) > 0:
            return
        if session.title != EMPTY_CONVERSATION_TITLE and session.title.strip():
            return
        self.repository.rename_conversation(
            session_id,
            title_from_prompt(prompt),
            manual=False,
        )


def _provider_label(provider: str) -> str:
    if provider == "local/fake":
        return "Local deterministic mode"
    if provider == "deepseek":
        return "DeepSeek"
    if provider == "openai-compatible":
        return "OpenAI-compatible"
    return provider


def _normalized_title(value: str | None) -> str:
    if value is None:
        return ""
    return " ".join(value.split())[:120]
