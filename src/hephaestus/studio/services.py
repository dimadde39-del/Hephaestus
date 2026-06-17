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
from hephaestus.studio.repository import EMPTY_CONVERSATION_TITLE, StudioRepository
from hephaestus.studio.schemas import (
    ArchiveConversationRequest,
    ConversationDetail,
    ConversationListResponse,
    ConversationSummary,
    CreateConversationRequest,
    ModeOption,
    PinConversationRequest,
    PolicyProfileResponse,
    PostMessageRequest,
    PostMessageResponse,
    ProviderStatusItem,
    ProviderStatusResponse,
    RecentRepo,
    SearchResponse,
    StudioConfigResponse,
    StudioHealthResponse,
    StudioMessage,
    UpdateConversationRequest,
)
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
        self.conversation_service = ConversationService(self.database_path, provider=provider)
        self.policy_repository = PolicyRepository(self.database_path)
        self.repo_repository = RepoProfileRepository(self.database_path)
        self.workbench = WorkbenchService(self.database_path)
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
        response = self.conversation_service.respond(
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
