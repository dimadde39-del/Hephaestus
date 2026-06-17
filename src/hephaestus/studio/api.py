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
from hephaestus.studio.workbench import (
    CheckpointDetailResponse,
    CheckpointRestoreRequest,
    CheckpointSummary,
    CodingApplyRequest,
    CodingDetailResponse,
    CodingListResponse,
    CodingPlanRequest,
    CodingProposeRequest,
    OutcomeDetailResponse,
    OutcomeListResponse,
    ReleaseDetailResponse,
    ReleaseListResponse,
    ToolActionDetailResponse,
    ToolActionSummary,
    TrustPatchRequest,
    TrustSettingsResponse,
    ValidationDetailResponse,
    ValidationListResponse,
    ValidationPlanRequest,
    ValidationPlanResponse,
    ValidationRunRequest,
    WorkbenchOverviewResponse,
)

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


@router.get("/workbench/overview", response_model=WorkbenchOverviewResponse)
def workbench_overview(request: Request) -> WorkbenchOverviewResponse:
    """Return practical current Workbench activity."""

    return get_studio_service(request).workbench.overview()


@router.get("/coding", response_model=CodingListResponse)
def list_coding(
    request: Request,
    status_filter: Annotated[str | None, Query(alias="status")] = None,
    repo: Annotated[str | None, Query()] = None,
    conversation: Annotated[str | None, Query()] = None,
    q: Annotated[str, Query()] = "",
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> CodingListResponse:
    """List existing coding requests with deterministic local search."""

    return get_studio_service(request).workbench.list_coding(
        status_filter=status_filter,
        repo=repo,
        conversation=conversation,
        query=q,
        limit=limit,
    )


@router.post("/coding/plan", response_model=CodingDetailResponse)
def create_coding_plan(
    request: Request,
    payload: CodingPlanRequest,
) -> CodingDetailResponse:
    """Create a coding plan through the Python orchestrator."""

    try:
        return get_studio_service(request).workbench.create_coding_plan(payload)
    except (FileNotFoundError, NotADirectoryError, ValueError) as error:
        raise _bad_workbench_request("CODING_PLAN_FAILED", str(error)) from error


@router.post("/coding/propose", response_model=CodingDetailResponse)
def propose_coding_change(
    request: Request,
    payload: CodingProposeRequest,
) -> CodingDetailResponse:
    """Create a scoped patch proposal through the Python orchestrator."""

    try:
        return get_studio_service(request).workbench.propose_coding_change(payload)
    except (FileNotFoundError, NotADirectoryError, PermissionError, ValueError) as error:
        raise _bad_workbench_request("CODING_PROPOSE_FAILED", str(error)) from error


@router.post("/coding/{change_id}/apply", response_model=CodingDetailResponse)
def apply_coding_change(
    request: Request,
    change_id: str,
    payload: Annotated[CodingApplyRequest | None, Body()] = None,
) -> CodingDetailResponse:
    """Apply an existing patch proposal as one reviewed batch."""

    try:
        return get_studio_service(request).workbench.apply_coding_change(
            change_id,
            payload or CodingApplyRequest(),
        )
    except (PermissionError, ValueError) as error:
        raise _bad_workbench_request("CODING_APPLY_FAILED", str(error)) from error


@router.get("/coding/{request_id}", response_model=CodingDetailResponse)
def get_coding(request: Request, request_id: str) -> CodingDetailResponse:
    """Return one readable coding request detail."""

    detail = get_studio_service(request).workbench.get_coding(request_id)
    if detail is None:
        raise _workbench_not_found("CODING_NOT_FOUND", request_id)
    return detail


@router.get("/validation", response_model=ValidationListResponse)
def list_validation(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> ValidationListResponse:
    """List validation runs."""

    return get_studio_service(request).workbench.list_validation(limit=limit)


@router.post("/validation/plan", response_model=ValidationPlanResponse)
def plan_validation(
    request: Request,
    payload: ValidationPlanRequest,
) -> ValidationPlanResponse:
    """Create a validation plan from repo intelligence."""

    try:
        return get_studio_service(request).workbench.plan_validation(payload)
    except (FileNotFoundError, NotADirectoryError, ValueError) as error:
        raise _bad_workbench_request("VALIDATION_PLAN_FAILED", str(error)) from error


@router.post("/validation/run", response_model=ValidationDetailResponse)
def run_validation(
    request: Request,
    payload: ValidationRunRequest,
) -> ValidationDetailResponse:
    """Run or dry-run validation through the Python runtime."""

    try:
        return get_studio_service(request).workbench.run_validation(payload)
    except (FileNotFoundError, NotADirectoryError, ValueError) as error:
        raise _bad_workbench_request("VALIDATION_RUN_FAILED", str(error)) from error


@router.get("/validation/{result_id}", response_model=ValidationDetailResponse)
def get_validation(request: Request, result_id: str) -> ValidationDetailResponse:
    """Return validation result detail."""

    detail = get_studio_service(request).workbench.get_validation(result_id)
    if detail is None:
        raise _workbench_not_found("VALIDATION_NOT_FOUND", result_id)
    return detail


@router.get("/tools/actions", response_model=list[ToolActionSummary])
def list_tool_actions(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[ToolActionSummary]:
    """List user-readable tool actions."""

    return get_studio_service(request).workbench.list_tool_actions(limit=limit)


@router.get("/tools/actions/{action_id}", response_model=ToolActionDetailResponse)
def get_tool_action(request: Request, action_id: str) -> ToolActionDetailResponse:
    """Return one tool action detail."""

    detail = get_studio_service(request).workbench.get_tool_action(action_id)
    if detail is None:
        raise _workbench_not_found("TOOL_ACTION_NOT_FOUND", action_id)
    return detail


@router.get("/checkpoints", response_model=list[CheckpointSummary])
def list_checkpoints(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[CheckpointSummary]:
    """List rollback checkpoints."""

    return get_studio_service(request).workbench.list_checkpoints(limit=limit)


@router.get("/checkpoints/{checkpoint_id}", response_model=CheckpointDetailResponse)
def get_checkpoint(request: Request, checkpoint_id: str) -> CheckpointDetailResponse:
    """Return checkpoint detail."""

    detail = get_studio_service(request).workbench.get_checkpoint(checkpoint_id)
    if detail is None:
        raise _workbench_not_found("CHECKPOINT_NOT_FOUND", checkpoint_id)
    return detail


@router.post("/checkpoints/{checkpoint_id}/restore", response_model=CheckpointDetailResponse)
def restore_checkpoint(
    request: Request,
    checkpoint_id: str,
    payload: Annotated[CheckpointRestoreRequest | None, Body()] = None,
) -> CheckpointDetailResponse:
    """Restore a checkpoint as one confirmed action."""

    try:
        return get_studio_service(request).workbench.restore_checkpoint(
            checkpoint_id,
            payload or CheckpointRestoreRequest(),
        )
    except (PermissionError, ValueError) as error:
        raise _bad_workbench_request("CHECKPOINT_RESTORE_FAILED", str(error)) from error


@router.get("/releases", response_model=ReleaseListResponse)
def list_releases(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> ReleaseListResponse:
    """List release evidence."""

    return get_studio_service(request).workbench.list_releases(limit=limit)


@router.get("/releases/{release_plan_id}", response_model=ReleaseDetailResponse)
def get_release(request: Request, release_plan_id: str) -> ReleaseDetailResponse:
    """Return release plan evidence detail."""

    detail = get_studio_service(request).workbench.get_release(release_plan_id)
    if detail is None:
        raise _workbench_not_found("RELEASE_NOT_FOUND", release_plan_id)
    return detail


@router.get("/outcomes", response_model=OutcomeListResponse)
def list_outcomes(
    request: Request,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> OutcomeListResponse:
    """List outcome records in human language."""

    return get_studio_service(request).workbench.list_outcomes(limit=limit)


@router.get("/outcomes/{outcome_id}", response_model=OutcomeDetailResponse)
def get_outcome(request: Request, outcome_id: str) -> OutcomeDetailResponse:
    """Return one outcome detail."""

    detail = get_studio_service(request).workbench.get_outcome(outcome_id)
    if detail is None:
        raise _workbench_not_found("OUTCOME_NOT_FOUND", outcome_id)
    return detail


@router.get("/trust", response_model=TrustSettingsResponse)
def get_trust(request: Request) -> TrustSettingsResponse:
    """Return local trust and autonomy settings."""

    return get_studio_service(request).workbench.trust_settings()


@router.patch("/trust", response_model=TrustSettingsResponse)
def update_trust(request: Request, payload: TrustPatchRequest) -> TrustSettingsResponse:
    """Update local trust and autonomy settings."""

    return get_studio_service(request).workbench.update_trust(payload)


def _not_found(session_id: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=StudioError(
            code="CONVERSATION_NOT_FOUND",
            message=f"Conversation not found: {session_id}",
        ).model_dump(),
    )


def _workbench_not_found(code: str, identifier: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=StudioError(
            code=code,
            message=f"Workbench record not found: {identifier}",
        ).model_dump(),
    )


def _bad_workbench_request(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=StudioError(code=code, message=message).model_dump(),
    )
