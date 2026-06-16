"""FastAPI routes for the local Studio backend."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Body, HTTPException, Query, Request, status

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
    ProviderStatusResponse,
    RecentRepo,
    SearchResponse,
    StudioConfigResponse,
    StudioError,
    StudioHealthResponse,
    StudioMessage,
    UpdateConversationRequest,
)
from hephaestus.studio.services import StudioService

router = APIRouter()


def get_studio_service(request: Request) -> StudioService:
    """Return the Studio service stored on the FastAPI app."""

    service = getattr(request.app.state, "studio_service", None)
    if not isinstance(service, StudioService):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=StudioError(
                code="STUDIO_NOT_CONFIGURED",
                message="Studio service was not configured.",
            ).model_dump(),
        )
    return service


@router.get("/health", response_model=StudioHealthResponse)
def health(request: Request) -> StudioHealthResponse:
    """Check the local Studio API and database."""

    return get_studio_service(request).health()


@router.get("/config", response_model=StudioConfigResponse)
def config(request: Request) -> StudioConfigResponse:
    """Return non-secret local configuration."""

    return get_studio_service(request).config()


@router.get("/conversations", response_model=ConversationListResponse)
def list_conversations(
    request: Request,
    q: Annotated[str, Query(description="Text search across titles and messages.")] = "",
    include_archived: Annotated[
        bool,
        Query(description="Include archived conversations in the list."),
    ] = False,
    archived_only: Annotated[
        bool,
        Query(description="Show only archived conversations."),
    ] = False,
    repo_profile_id: Annotated[str | None, Query()] = None,
    workspace_path: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ConversationListResponse:
    """List conversations, pinned first, then latest activity."""

    return get_studio_service(request).list_conversations(
        query=q,
        include_archived=include_archived,
        archived_only=archived_only,
        repo_profile_id=repo_profile_id,
        workspace_path=workspace_path,
        limit=limit,
        offset=offset,
    )


@router.post(
    "/conversations",
    response_model=ConversationSummary,
    status_code=status.HTTP_201_CREATED,
)
def create_conversation(
    request: Request,
    payload: CreateConversationRequest,
) -> ConversationSummary:
    """Create an empty persistent conversation."""

    return get_studio_service(request).create_conversation(payload)


@router.get("/conversations/{session_id}", response_model=ConversationDetail)
def get_conversation(request: Request, session_id: str) -> ConversationDetail:
    """Open a conversation without creating an automatic recap."""

    detail = get_studio_service(request).conversation_detail(session_id)
    if detail is None:
        raise _not_found(session_id)
    return detail


@router.get("/conversations/{session_id}/messages", response_model=list[StudioMessage])
def list_messages(request: Request, session_id: str) -> list[StudioMessage]:
    """Return exact persisted messages in chronological order."""

    messages = get_studio_service(request).list_messages(session_id)
    if messages is None:
        raise _not_found(session_id)
    return messages


@router.post("/conversations/{session_id}/messages", response_model=PostMessageResponse)
def post_message(
    request: Request,
    session_id: str,
    payload: PostMessageRequest,
) -> PostMessageResponse:
    """Persist the user message and assistant response through the conversation system."""

    try:
        return get_studio_service(request).post_message(session_id, payload)
    except KeyError as error:
        raise _not_found(session_id) from error
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=StudioError(code="INVALID_MESSAGE", message=str(error)).model_dump(),
        ) from error
    except RuntimeError as error:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=StudioError(code="MESSAGE_FAILED", message=str(error)).model_dump(),
        ) from error


@router.patch("/conversations/{session_id}", response_model=ConversationSummary)
def update_conversation(
    request: Request,
    session_id: str,
    payload: UpdateConversationRequest,
) -> ConversationSummary:
    """Rename a conversation or update its active mode/repo context."""

    summary = get_studio_service(request).update_conversation(session_id, payload)
    if summary is None:
        raise _not_found(session_id)
    return summary


@router.post("/conversations/{session_id}/pin", response_model=ConversationSummary)
def pin_conversation(
    request: Request,
    session_id: str,
    payload: Annotated[PinConversationRequest | None, Body()] = None,
) -> ConversationSummary:
    """Pin or unpin a conversation."""

    summary = get_studio_service(request).pin_conversation(
        session_id,
        payload or PinConversationRequest(),
    )
    if summary is None:
        raise _not_found(session_id)
    return summary


@router.post("/conversations/{session_id}/archive", response_model=ConversationSummary)
def archive_conversation(
    request: Request,
    session_id: str,
    payload: Annotated[ArchiveConversationRequest | None, Body()] = None,
) -> ConversationSummary:
    """Archive or restore a conversation."""

    summary = get_studio_service(request).archive_conversation(
        session_id,
        payload or ArchiveConversationRequest(),
    )
    if summary is None:
        raise _not_found(session_id)
    return summary


@router.get("/search", response_model=SearchResponse)
def search(
    request: Request,
    q: Annotated[str, Query(min_length=1)],
    include_archived: Annotated[bool, Query()] = False,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> SearchResponse:
    """Search titles, user messages, and assistant messages locally."""

    return get_studio_service(request).search(
        query=q,
        include_archived=include_archived,
        limit=limit,
    )


@router.get("/modes", response_model=list[ModeOption])
def modes(request: Request) -> list[ModeOption]:
    """Return supported conversational modes."""

    return get_studio_service(request).modes()


@router.get("/policy/active", response_model=PolicyProfileResponse)
def active_policy(request: Request) -> PolicyProfileResponse:
    """Return the active user-owned policy profile."""

    return get_studio_service(request).active_policy()


@router.get("/providers/status", response_model=ProviderStatusResponse)
def providers_status(request: Request) -> ProviderStatusResponse:
    """Return non-secret provider configuration status."""

    return get_studio_service(request).provider_status()


@router.get("/repos/recent", response_model=list[RecentRepo])
def recent_repos(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[RecentRepo]:
    """Return recent repo profiles for optional conversation context."""

    return get_studio_service(request).recent_repos(limit=limit)


def _not_found(session_id: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=StudioError(
            code="CONVERSATION_NOT_FOUND",
            message=f"Conversation not found: {session_id}",
        ).model_dump(),
    )
