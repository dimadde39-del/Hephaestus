"""Studio-facing memory, settings, providers, usage, advanced views, and data export."""

from __future__ import annotations

import json
import shutil
import sqlite3
from collections.abc import Mapping
from datetime import UTC, datetime, timedelta
from pathlib import Path
from time import perf_counter
from typing import Any, cast
from uuid import uuid4

from hephaestus.conversation.repository import ConversationRepository
from hephaestus.conversation.schemas import ConversationMemoryUpdate
from hephaestus.decision.repository import DecisionTraceRepository
from hephaestus.decision.schemas import DecisionAlternative, DecisionMetric, DecisionTraceVariant
from hephaestus.memory.schemas import MemoryType
from hephaestus.models import (
    DeepSeekProvider,
    FakeModelProvider,
    ModelProvider,
    ModelRequest,
    OpenAICompatibleProvider,
    ProviderRequestError,
)
from hephaestus.pareto.repository import ParetoRepository
from hephaestus.pareto.schemas import DecisionCandidate, ObjectiveDimension, ParetoFrontier
from hephaestus.qubo.repository import QuboRepository
from hephaestus.qubo.schemas import QuboProblem, QuboSolution
from hephaestus.storage.migrations import SCHEMA_VERSION
from hephaestus.storage.sqlite import connect_database, init_database
from hephaestus.strategic_memory.repository import StrategicMemoryRepository
from hephaestus.strategic_memory.schemas import (
    StrategicMemoryEvidence,
    StrategicMemoryItem,
    StrategicMemoryScope,
    StrategicMemorySource,
    StrategicMemoryStability,
    StrategicMemoryType,
)
from hephaestus.studio.schemas import (
    AdvancedArtifactSummary,
    AdvancedDecisionDetail,
    AdvancedDecisionListResponse,
    AdvancedDecisionSummary,
    AdvancedParetoCandidate,
    AdvancedParetoDetail,
    AdvancedQuboDetail,
    AdvancedQuboVariable,
    BackupResponse,
    ConversationExportRequest,
    ExportResponse,
    RestoreBackupResponse,
    StudioLink,
    StudioMemoryCreateRequest,
    StudioMemoryDeleteRequest,
    StudioMemoryDetail,
    StudioMemoryEvidence,
    StudioMemoryHistoryItem,
    StudioMemoryKind,
    StudioMemoryListResponse,
    StudioMemoryPatchRequest,
    StudioMemoryScope,
    StudioMemoryState,
    StudioMemorySuggestion,
    StudioMemorySuggestionListResponse,
    StudioMemorySuggestionSaveRequest,
    StudioMemorySummary,
    StudioProviderConfig,
    StudioProviderListResponse,
    StudioProviderStatus,
    StudioProviderTestResponse,
    StudioProviderUpsertRequest,
    StudioSettings,
    StudioSettingsPatchRequest,
    StudioSettingsResponse,
    StudioUsageAggregate,
    StudioUsageEvent,
    StudioUsageResponse,
)

MEMORY_TYPE_LABELS: dict[str, str] = {
    "goal": "Goal",
    "constraint": "Constraint",
    "preference": "Preference",
    "principle": "Principle",
    "strategic_decision": "Strategic decision",
    "rejected_path": "Rejected path",
    "lesson_learned": "Lesson learned",
    "open_question": "Open question",
    "project_fact": "Project fact",
    "working_style": "Working style",
}

_REGULAR_MEMORY_TYPES: dict[str, MemoryType] = {
    "project_fact": MemoryType.PROJECT,
    "working_style": MemoryType.PROCEDURAL,
    "lesson_learned": MemoryType.FAILURE,
    "rejected_path": MemoryType.DECISION,
    "preference": MemoryType.SEMANTIC,
    "constraint": MemoryType.SEMANTIC,
    "goal": MemoryType.PROJECT,
    "open_question": MemoryType.PROJECT,
    "principle": MemoryType.SEMANTIC,
    "strategic_decision": MemoryType.DECISION,
}

_STRATEGIC_MEMORY_TYPES: dict[str, StrategicMemoryType] = {
    "goal": StrategicMemoryType.GOAL,
    "constraint": StrategicMemoryType.CONSTRAINT,
    "preference": StrategicMemoryType.PREFERENCE,
    "principle": StrategicMemoryType.PRINCIPLE,
    "strategic_decision": StrategicMemoryType.STRATEGIC_DECISION,
    "rejected_path": StrategicMemoryType.REJECTED_PATH,
    "lesson_learned": StrategicMemoryType.LESSON_LEARNED,
    "open_question": StrategicMemoryType.OPEN_QUESTION,
    "project_fact": StrategicMemoryType.TECHNICAL_ASSUMPTION,
    "working_style": StrategicMemoryType.PREFERENCE,
}


class StudioExperienceRepository:
    """Persistence and projection helpers for Phase 5.5C Studio views."""

    def __init__(self, database_path: Path | str | None = None) -> None:
        self.database_path = init_database(database_path)
        self.conversations = ConversationRepository(self.database_path)
        self.strategic_memories = StrategicMemoryRepository(self.database_path)
        self.decisions = DecisionTraceRepository(self.database_path)
        self.pareto = ParetoRepository(self.database_path)
        self.qubo = QuboRepository(self.database_path)

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
        """List regular and strategic memories through one user-facing model."""

        details = [
            *self._regular_memory_details(),
            *self._strategic_memory_details(),
        ]
        filtered = [
            memory
            for memory in details
            if _memory_matches(
                memory,
                query=query,
                type_filter=type_filter,
                scope=scope,
                project=project,
                repo_profile_id=repo_profile_id,
                source=source,
                stability=stability,
                state=state,
            )
        ]
        filtered.sort(
            key=lambda memory: (
                memory.archived,
                -memory.importance,
                memory.updated_at,
            ),
            reverse=False,
        )
        pending = self.list_memory_suggestions().total
        summaries: list[StudioMemorySummary] = [
            StudioMemorySummary.model_validate(memory.model_dump())
            for memory in filtered[:limit]
        ]
        return StudioMemoryListResponse(
            memories=summaries,
            total=len(filtered),
            filters={
                "query": query or None,
                "type": type_filter,
                "scope": scope.value if scope is not None else None,
                "project": project,
                "repo_profile_id": repo_profile_id,
                "source": source,
                "stability": stability,
                "state": state.value,
            },
            suggestions_pending=pending,
        )

    def get_memory(self, memory_id: str) -> StudioMemoryDetail | None:
        """Return one memory by ID."""

        for memory in [*self._regular_memory_details(), *self._strategic_memory_details()]:
            if memory.id == memory_id:
                return memory
        return None

    def create_memory(self, request: StudioMemoryCreateRequest) -> StudioMemoryDetail:
        """Create either a regular or strategic memory."""

        if request.kind == StudioMemoryKind.REGULAR:
            return self._create_regular_memory(request)
        item = StrategicMemoryItem(
            type=_strategic_type(request.type),
            scope=StrategicMemoryScope(request.scope.value),
            project=request.project,
            repo_profile_id=request.repo_profile_id,
            conversation_id=request.conversation_id,
            content=request.content,
            summary=request.summary,
            evidence=[
                StrategicMemoryEvidence(
                    source=evidence.source,
                    content=evidence.content,
                    kind=evidence.kind,
                    source_id=evidence.source_id,
                    confidence=evidence.confidence,
                )
                for evidence in request.evidence
            ],
            confidence=request.confidence,
            importance=request.importance,
            stability=_strategic_stability(request.stability),
            source=_strategic_source(request.source),
            tags=request.tags,
        )
        saved = self.strategic_memories.save_memory(item)
        detail = self.get_memory(saved.id)
        if detail is None:
            raise RuntimeError("Created memory could not be loaded.")
        return detail

    def patch_memory(
        self,
        memory_id: str,
        request: StudioMemoryPatchRequest,
    ) -> StudioMemoryDetail | None:
        """Patch a memory and optionally mark simple conflicts resolved."""

        current = self.get_memory(memory_id)
        if current is None:
            return None
        if current.kind == StudioMemoryKind.REGULAR:
            self._patch_regular_memory(memory_id, request)
        else:
            item = self.strategic_memories.get_memory(memory_id)
            if item is None:
                return None
            updated = item.model_copy(
                update={
                    "type": _strategic_type(request.type) if request.type else item.type,
                    "scope": StrategicMemoryScope(request.scope.value)
                    if request.scope
                    else item.scope,
                    "project": request.project if "project" in request.model_fields_set else item.project,
                    "repo_profile_id": request.repo_profile_id
                    if "repo_profile_id" in request.model_fields_set
                    else item.repo_profile_id,
                    "conversation_id": request.conversation_id
                    if "conversation_id" in request.model_fields_set
                    else item.conversation_id,
                    "content": request.content if request.content is not None else item.content,
                    "summary": request.summary if request.summary is not None else item.summary,
                    "confidence": request.confidence
                    if request.confidence is not None
                    else item.confidence,
                    "importance": request.importance
                    if request.importance is not None
                    else item.importance,
                    "stability": _strategic_stability(request.stability)
                    if request.stability
                    else item.stability,
                    "source": _strategic_source(request.source)
                    if request.source
                    else item.source,
                    "evidence": [
                        StrategicMemoryEvidence(
                            source=evidence.source,
                            content=evidence.content,
                            kind=evidence.kind,
                            source_id=evidence.source_id,
                            confidence=evidence.confidence,
                        )
                        for evidence in request.evidence
                    ]
                    if request.evidence is not None
                    else item.evidence,
                    "tags": request.tags if request.tags is not None else item.tags,
                    "updated_at": datetime.now(UTC),
                }
            )
            self.strategic_memories.save_memory(updated)
        if request.resolve_conflicts:
            self._resolve_memory_conflicts(memory_id)
        return self.get_memory(memory_id)

    def archive_memory(self, memory_id: str) -> StudioMemoryDetail | None:
        """Archive a memory without deleting data."""

        current = self.get_memory(memory_id)
        if current is None:
            return None
        now = _datetime_to_text(datetime.now(UTC))
        if current.kind == StudioMemoryKind.REGULAR:
            with connect_database(self.database_path) as connection:
                connection.execute(
                    "UPDATE memories SET archived_at = ?, updated_at = ? WHERE id = ?",
                    (now, now, memory_id),
                )
        else:
            self.strategic_memories.archive_memory(memory_id)
        return self.get_memory(memory_id)

    def restore_memory(self, memory_id: str) -> StudioMemoryDetail | None:
        """Restore an archived memory."""

        current = self.get_memory(memory_id)
        if current is None:
            return None
        now = datetime.now(UTC)
        if current.kind == StudioMemoryKind.REGULAR:
            with connect_database(self.database_path) as connection:
                connection.execute(
                    "UPDATE memories SET archived_at = NULL, updated_at = ? WHERE id = ?",
                    (_datetime_to_text(now), memory_id),
                )
        else:
            item = self.strategic_memories.get_memory(memory_id)
            if item is None:
                return None
            self.strategic_memories.save_memory(
                item.model_copy(update={"archived_at": None, "updated_at": now})
            )
        return self.get_memory(memory_id)

    def delete_memory(
        self,
        memory_id: str,
        request: StudioMemoryDeleteRequest,
    ) -> bool:
        """Permanently delete a memory after explicit confirmation."""

        if not request.confirm:
            raise ValueError("Permanent deletion requires confirmation.")
        current = self.get_memory(memory_id)
        if current is None:
            return False
        table = "memories" if current.kind == StudioMemoryKind.REGULAR else "strategic_memories"
        with connect_database(self.database_path) as connection:
            connection.execute(f"DELETE FROM {table} WHERE id = ?", (memory_id,))
        return True

    def list_memory_suggestions(self) -> StudioMemorySuggestionListResponse:
        """List pending memory suggestions from conversation outcomes."""

        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT u.raw_json, s.display_title, s.title
                FROM conversation_memory_updates u
                LEFT JOIN conversation_sessions s ON s.id = u.session_id
                WHERE u.status = 'suggested'
                ORDER BY u.created_at DESC, u.id DESC
                """
            ).fetchall()
        suggestions: list[StudioMemorySuggestion] = []
        for row in rows:
            update = ConversationMemoryUpdate.model_validate_json(_row_str(row, "raw_json"))
            candidate = update.candidate
            proposed_type = candidate.memory_type.value
            if proposed_type not in MEMORY_TYPE_LABELS:
                proposed_type = "project_fact"
            title = _row_optional_str(row, "display_title") or _row_optional_str(row, "title")
            suggestions.append(
                StudioMemorySuggestion(
                    id=update.id,
                    proposed_memory=candidate.content,
                    why_it_may_matter=candidate.rationale
                    or "This may help Hephaestus remember useful project context.",
                    proposed_type=proposed_type,
                    proposed_type_label=memory_type_label(proposed_type),
                    proposed_scope=StudioMemoryScope.PROJECT,
                    proposed_stability=candidate.stability,
                    source="conversation",
                    source_link=StudioLink(
                        label=title or update.session_id,
                        href=f"/conversations/{update.session_id}",
                    ),
                    confidence=candidate.confidence,
                    importance=candidate.importance,
                    status=update.status,
                    created_at=update.created_at,
                )
            )
        return StudioMemorySuggestionListResponse(suggestions=suggestions, total=len(suggestions))

    def save_memory_suggestion(
        self,
        suggestion_id: str,
        request: StudioMemorySuggestionSaveRequest,
    ) -> StudioMemoryDetail | None:
        """Save a pending memory suggestion after explicit review."""

        update = self._get_memory_update(suggestion_id)
        if update is None or update.status != "suggested":
            return None
        if request.edited_memory is not None:
            memory = self.create_memory(request.edited_memory)
        else:
            candidate = update.candidate
            memory = self.create_memory(
                StudioMemoryCreateRequest(
                    kind=StudioMemoryKind.REGULAR,
                    type="project_fact",
                    content=candidate.content,
                    summary=candidate.summary,
                    project=candidate.project,
                    confidence=candidate.confidence,
                    importance=candidate.importance,
                    stability=candidate.stability,
                    source="conversation",
                    tags=candidate.tags,
                )
            )
        self._set_memory_update_status(suggestion_id, "saved", memory.id)
        return memory

    def ignore_memory_suggestion(self, suggestion_id: str) -> bool:
        """Mark a memory suggestion ignored."""

        update = self._get_memory_update(suggestion_id)
        if update is None:
            return False
        self._set_memory_update_status(suggestion_id, "ignored", update.memory_id)
        return True

    def list_providers(self) -> StudioProviderListResponse:
        """Return local provider configurations without secrets."""

        local = self._local_provider_config()
        providers = [local, *self._stored_provider_configs()]
        default = next(
            (provider for provider in providers if provider.default_for_conversation),
            local,
        )
        return StudioProviderListResponse(
            providers=providers,
            default_provider_id=default.id,
            local_mode=local,
            storage_note=(
                "Provider secrets are stored in the local Studio SQLite database and never "
                "returned by API responses. Use OS file permissions to protect the database."
            ),
        )

    def create_provider(self, request: StudioProviderUpsertRequest) -> StudioProviderConfig:
        """Create a local provider configuration."""

        provider_id = f"provider_{uuid4().hex[:12]}"
        self._save_provider(provider_id, request, existing_secret=None)
        provider = self.get_provider(provider_id)
        if provider is None:
            raise RuntimeError("Created provider could not be loaded.")
        return provider

    def get_provider(self, provider_id: str) -> StudioProviderConfig | None:
        """Read one redacted provider configuration."""

        if provider_id == "local":
            return self._local_provider_config()
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM studio_provider_configs WHERE id = ?",
                (provider_id,),
            ).fetchone()
        return self._provider_from_row(row) if row is not None else None

    def update_provider(
        self,
        provider_id: str,
        request: StudioProviderUpsertRequest,
    ) -> StudioProviderConfig | None:
        """Update a provider while preserving secrets when no new key is supplied."""

        if provider_id == "local":
            self._set_default_provider("local")
            return self._local_provider_config()
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT api_key_secret FROM studio_provider_configs WHERE id = ?",
                (provider_id,),
            ).fetchone()
        if row is None:
            return None
        existing_secret = _row_optional_str(row, "api_key_secret")
        self._save_provider(provider_id, request, existing_secret=existing_secret)
        return self.get_provider(provider_id)

    def delete_provider(self, provider_id: str) -> bool:
        """Remove a provider configuration."""

        if provider_id == "local":
            self._set_default_provider("local")
            return True
        with connect_database(self.database_path) as connection:
            cursor = connection.execute(
                "DELETE FROM studio_provider_configs WHERE id = ?",
                (provider_id,),
            )
        if self.list_providers().default_provider_id == provider_id:
            self._set_default_provider("local")
        return cursor.rowcount > 0

    def test_provider(self, provider_id: str) -> StudioProviderTestResponse | None:
        """Perform a safe connectivity/configuration test."""

        if provider_id == "local":
            return StudioProviderTestResponse(
                id="local",
                status=StudioProviderStatus.LOCAL_MODE,
                message="Local deterministic mode is available and does not need a network key.",
                provider="local",
                model="deterministic",
                latency_ms=0,
            )
        row = self._provider_secret_row(provider_id)
        if row is None:
            return None
        provider_type = _row_str(row, "provider_type")
        name = _row_str(row, "name")
        base_url = _row_str(row, "base_url")
        model = _row_str(row, "model")
        api_key = _row_optional_str(row, "api_key_secret")
        if provider_type != "local" and not api_key:
            response = StudioProviderTestResponse(
                id=provider_id,
                status=StudioProviderStatus.NOT_CONFIGURED,
                message=f"{name} needs an API key before it can be used.",
                provider=provider_type,
                model=model,
                latency_ms=0,
            )
            self._update_provider_status(provider_id, response.status, response.message)
            return response
        if provider_type in {"openai-compatible", "deepseek"} and (not base_url or not model):
            response = StudioProviderTestResponse(
                id=provider_id,
                status=StudioProviderStatus.NOT_CONFIGURED,
                message="Provider configuration needs a base URL and model.",
                provider=provider_type,
                model=model,
                latency_ms=0,
            )
            self._update_provider_status(provider_id, response.status, response.message)
            return response
        if base_url.startswith("fake://"):
            response = StudioProviderTestResponse(
                id=provider_id,
                status=StudioProviderStatus.CONFIGURED,
                message="Fake provider endpoint accepted for local validation.",
                provider=provider_type,
                model=model,
                latency_ms=0,
            )
            self._update_provider_status(provider_id, response.status, response.message)
            return response
        provider = self._provider_from_secret_row(row)
        started = perf_counter()
        try:
            provider.complete(
                ModelRequest(
                    prompt="Reply OK.",
                    model=model,
                    max_output_tokens=4,
                    thinking_enabled=False,
                )
            )
        except ProviderRequestError as error:
            status = (
                StudioProviderStatus.INSUFFICIENT_BALANCE
                if error.code == "insufficient_balance"
                else StudioProviderStatus.CONNECTION_FAILED
            )
            response = StudioProviderTestResponse(
                id=provider_id,
                status=status,
                message=str(error),
                provider=provider_type,
                model=model,
                latency_ms=max(0, round((perf_counter() - started) * 1000)),
            )
        except (OSError, TimeoutError, ValueError) as error:
            response = StudioProviderTestResponse(
                id=provider_id,
                status=StudioProviderStatus.CONNECTION_FAILED,
                message=f"Connection failed: {_safe_error(error)}",
                provider=provider_type,
                model=model,
                latency_ms=max(0, round((perf_counter() - started) * 1000)),
            )
        else:
            response = StudioProviderTestResponse(
                id=provider_id,
                status=StudioProviderStatus.CONNECTED,
                message="Provider responded to a minimal chat-completions probe.",
                provider=provider_type,
                model=model,
                latency_ms=max(0, round((perf_counter() - started) * 1000)),
            )
        self._update_provider_status(provider_id, response.status, response.message)
        return response

    def get_settings(
        self,
        *,
        database_path: str,
        local_api_url: str,
        static_assets_available: bool,
    ) -> StudioSettingsResponse:
        """Read Studio settings with local context."""

        return StudioSettingsResponse(
            settings=self._read_settings(),
            database_path=database_path,
            schema_version=SCHEMA_VERSION,
            local_api_url=local_api_url,
            static_assets_available=static_assets_available,
        )

    def patch_settings(
        self,
        request: StudioSettingsPatchRequest,
        *,
        database_path: str,
        local_api_url: str,
        static_assets_available: bool,
    ) -> StudioSettingsResponse:
        """Patch persisted Studio settings."""

        current = self._read_settings()
        updates = request.model_dump(exclude_unset=True)
        next_settings = current.model_copy(update=updates)
        self._write_settings(next_settings)
        return self.get_settings(
            database_path=database_path,
            local_api_url=local_api_url,
            static_assets_available=static_assets_available,
        )

    def record_conversation_usage(
        self,
        *,
        conversation_id: str | None,
        message_id: str | None,
        provider_model: str,
        estimated_input_tokens: int,
        estimated_output_tokens: int,
        estimated_cost: float,
        context_trimmed: bool,
        success: bool = True,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        cached_input_tokens: int = 0,
        thinking_enabled: bool = False,
        reasoning_effort: str | None = None,
        usage_source: str = "provider",
        task_type: str = "conversation",
    ) -> None:
        """Record one user-facing usage event."""

        provider, model = _split_provider_model(provider_model)
        deterministic = provider in {"local", "fake"} or "local/" in provider_model
        if deterministic:
            usage_source = "estimated"
        summary = (
            "Solved without a model call"
            if deterministic
            else "One model call used"
        )
        if context_trimmed:
            summary = f"{summary}; context trimmed to fit budget"
        event = {
            "id": f"usage_{uuid4().hex[:12]}",
            "conversation_id": conversation_id,
            "message_id": message_id,
            "run_id": None,
            "task_type": task_type,
            "provider": provider,
            "model": model,
            "provider_model": provider_model,
            "estimated_input_tokens": estimated_input_tokens,
            "estimated_output_tokens": estimated_output_tokens,
            "estimated_cost": estimated_cost,
            "input_tokens": (
                input_tokens if input_tokens is not None else estimated_input_tokens
            ),
            "output_tokens": (
                output_tokens if output_tokens is not None else estimated_output_tokens
            ),
            "cached_input_tokens": cached_input_tokens,
            "thinking_enabled": thinking_enabled,
            "reasoning_effort": reasoning_effort,
            "usage_source": usage_source,
            "deterministic": deterministic,
            "context_trimmed": context_trimmed,
            "success": success,
            "summary": summary,
            "created_at": datetime.now(UTC),
        }
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO studio_usage_events (
                    id, conversation_id, message_id, run_id, task_type, provider, model,
                    provider_model, estimated_input_tokens, estimated_output_tokens,
                    estimated_cost, deterministic, context_trimmed, success, summary,
                    created_at, raw_json, input_tokens, output_tokens, cached_input_tokens,
                    thinking_enabled, reasoning_effort, usage_source
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event["id"],
                    conversation_id,
                    message_id,
                    None,
                    task_type,
                    provider,
                    model,
                    provider_model,
                    estimated_input_tokens,
                    estimated_output_tokens,
                    estimated_cost,
                    int(deterministic),
                    int(context_trimmed),
                    int(success),
                    summary,
                    _datetime_to_text(cast(datetime, event["created_at"])),
                    _json_dumps(_json_ready(event)),
                    event["input_tokens"],
                    event["output_tokens"],
                    cached_input_tokens,
                    int(thinking_enabled),
                    reasoning_effort,
                    usage_source,
                ),
            )

    def usage(self, *, limit: int = 100) -> StudioUsageResponse:
        """Return model usage events and simple aggregates."""

        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT e.*, COALESCE(NULLIF(s.display_title, ''), s.title) AS conversation_title
                FROM studio_usage_events e
                LEFT JOIN conversation_sessions s ON s.id = e.conversation_id
                ORDER BY e.created_at DESC, e.id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        events = [self._usage_event_from_row(row) for row in rows]
        week_start = datetime.now(UTC) - timedelta(days=7)
        weekly = [event for event in events if event.created_at >= week_start]
        provider_usage: dict[str, int] = {}
        for event in events:
            provider_usage[event.provider] = provider_usage.get(event.provider, 0) + 1
        aggregate = StudioUsageAggregate(
            estimated_model_calls_this_week=sum(1 for event in weekly if not event.deterministic),
            deterministic_operations=sum(1 for event in events if event.deterministic),
            estimated_cost=sum(event.estimated_cost for event in events),
            cost_per_validated_successful_coding_task=self._cost_per_successful_coding_task(
                events
            ),
            provider_usage=provider_usage,
        )
        return StudioUsageResponse(aggregate=aggregate, events=events)

    def list_decisions(
        self,
        *,
        category: str | None = None,
        repo: str | None = None,
        limit: int = 100,
    ) -> AdvancedDecisionListResponse:
        """List safe decision artifacts plus secondary advanced artifacts."""

        traces = self.decisions.list_traces()
        summaries = [
            self._decision_summary(trace)
            for trace in traces
            if _decision_category_matches(trace, category) and _repo_matches(repo)
        ]
        summaries.sort(key=lambda item: item.occurred_at, reverse=True)
        return AdvancedDecisionListResponse(
            decisions=summaries[:limit],
            total=len(summaries),
            pareto_frontiers=[
                AdvancedArtifactSummary(
                    id=frontier.id,
                    title=frontier.title or "Pareto frontier",
                    kind="pareto",
                    created_at=frontier.created_at,
                    linked_work=[],
                )
                for frontier in self.pareto.list_frontiers(limit=12)
            ],
            qubo_problems=[
                AdvancedArtifactSummary(
                    id=problem.id,
                    title=problem.objective.description or problem.problem_type.value,
                    kind="qubo",
                    created_at=problem.created_at,
                    linked_work=[],
                )
                for problem in self.qubo.list_problems(limit=12)
            ],
        )

    def decision_detail(self, trace_id: str) -> AdvancedDecisionDetail | None:
        """Return one decision detail without exposing private reasoning."""

        trace = self.decisions.get_trace(trace_id)
        if trace is None:
            return None
        summary = self._decision_summary(trace)
        return AdvancedDecisionDetail(
            **summary.model_dump(),
            alternatives=[_alternative_text(item) for item in trace.alternatives],
            reasons=_split_reason_text(trace.rationale),
            assumptions=_public_text_items(trace.constraints_considered),
            evidence=[_metric_text(metric) for metric in trace.metrics],
            linked_work=_decision_links(trace),
            later_evidence_supported=_later_evidence_supported(trace.outcome_id),
            developer_payload={
                "caused_by": trace.caused_by,
                "phase": trace.phase,
                "tags": trace.tags,
                "will_affect": trace.will_affect,
                "learning_hooks": trace.learning_hooks,
            },
        )

    def pareto_detail(self, frontier_id: str) -> AdvancedParetoDetail | None:
        """Return one readable Pareto frontier."""

        frontier = self.pareto.get_frontier(frontier_id)
        if frontier is None:
            return None
        dimensions = frontier.dimensions[:2] or [
            ObjectiveDimension.QUALITY,
            ObjectiveDimension.COST,
        ]
        if len(dimensions) == 1:
            dimensions.append(ObjectiveDimension.COST)
        objective_x, objective_y = dimensions[0], dimensions[1]
        return AdvancedParetoDetail(
            id=frontier.id,
            title=frontier.title or "Pareto frontier",
            objective_x=objective_x.value,
            objective_y=objective_y.value,
            selected_candidate_id=frontier.selected_candidate_id,
            preference_profile=frontier.preference_profile_id,
            explanation=_pareto_explanation(frontier),
            tradeoffs=frontier.tradeoff_explanation.tradeoffs
            if frontier.tradeoff_explanation is not None
            else [],
            candidates=[
                _pareto_candidate(candidate, frontier, objective_x, objective_y)
                for candidate in frontier.candidates
            ],
            created_at=frontier.created_at,
        )

    def qubo_detail(self, problem_id: str) -> AdvancedQuboDetail | None:
        """Return one readable QUBO problem and latest local solver result."""

        problem = self.qubo.get_problem(problem_id)
        if problem is None:
            return None
        solution = self.qubo.get_latest_solution(problem_id)
        selected = set(solution.selected_variables if solution is not None else [])
        return AdvancedQuboDetail(
            id=problem.id,
            purpose=problem.objective.description or _problem_type_label(problem.problem_type.value),
            problem_type=problem.problem_type.value,
            solver_used=solution.solver_name if solution is not None else "not solved",
            selected_solution=_selected_solution_text(problem, solution),
            objective_value=solution.objective_value if solution is not None else None,
            feasible=solution.feasible if solution is not None else None,
            variables=[
                AdvancedQuboVariable(
                    id=variable.id,
                    label=variable.label or variable.id,
                    selected=variable.id in selected,
                )
                for variable in problem.variables
            ],
            constraints=[constraint.description for constraint in problem.constraints],
            comparison_with_heuristic=_heuristic_comparison(problem, solution),
            explanation=(
                "This is a classical/local binary optimization formulation. It does "
                "not imply quantum advantage."
            ),
            mathematical_details={
                "objective_sense": problem.objective.sense.value,
                "linear_terms": len(problem.linear_terms),
                "quadratic_terms": len(problem.quadratic_terms),
                "constant_offset": problem.constant_offset,
            },
            created_at=problem.created_at,
        )

    def export_conversation(
        self,
        conversation_id: str,
        request: ConversationExportRequest,
    ) -> ExportResponse | None:
        """Export exact conversation messages without model-generated summaries."""

        session = self.conversations.get_session(conversation_id)
        if session is None:
            return None
        messages = self.conversations.list_messages(conversation_id)
        export_format = request.format.lower()
        if export_format == "json":
            content = json.dumps(
                [message.model_dump(mode="json") for message in messages],
                indent=2,
                sort_keys=True,
            )
            suffix = "json"
        else:
            content = "\n\n".join(
                [
                    f"## {message.role.value} - {_datetime_to_text(message.created_at)}\n\n"
                    f"{message.content}"
                    for message in messages
                ]
            )
            suffix = "md"
            export_format = "markdown"
        return ExportResponse(
            filename=f"{_safe_filename(session.title or session.id)}.{suffix}",
            format=export_format,
            content=content,
        )

    def export_memories(self) -> ExportResponse:
        """Export all memories as JSON without secrets or embeddings."""

        memories = [
            memory.model_dump(mode="json")
            for memory in [*self._regular_memory_details(), *self._strategic_memory_details()]
        ]
        return ExportResponse(
            filename="hephaestus-memories.json",
            format="json",
            content=json.dumps(memories, indent=2, sort_keys=True),
        )

    def backup_database(self) -> BackupResponse:
        """Create a local SQLite database backup."""

        backup_dir = self.database_path.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        created_at = datetime.now(UTC)
        backup_path = backup_dir / f"hephaestus-backup-{created_at.strftime('%Y%m%d-%H%M%S')}.db"
        with sqlite3.connect(self.database_path) as source, sqlite3.connect(backup_path) as target:
            source.backup(target)
        return BackupResponse(
            path=str(backup_path),
            schema_version=self._schema_version(backup_path),
            created_at=created_at,
            size_bytes=backup_path.stat().st_size,
        )

    def restore_database(self, backup_path: str, *, confirm: bool) -> RestoreBackupResponse:
        """Restore a compatible SQLite backup after explicit confirmation."""

        if not confirm:
            raise ValueError("Restore requires explicit confirmation.")
        source = Path(backup_path)
        if not source.exists() or not source.is_file():
            raise FileNotFoundError(f"Backup not found: {backup_path}")
        backup_schema = self._schema_version(source)
        if backup_schema != SCHEMA_VERSION:
            raise ValueError(
                f"Backup schema {backup_schema} is not compatible with Studio schema {SCHEMA_VERSION}."
            )
        if source.resolve() == self.database_path.resolve():
            raise ValueError("Refusing to restore a database over itself.")
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, self.database_path)
        return RestoreBackupResponse(
            restored=True,
            message="Backup restored. Reload Studio to refresh open views.",
            schema_version=backup_schema,
        )

    def _regular_memory_details(self) -> list[StudioMemoryDetail]:
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT m.*, r.repo_name, COALESCE(NULLIF(s.display_title, ''), s.title) AS conversation_title
                FROM memories m
                LEFT JOIN repo_profiles r ON r.id = m.repo_profile_id
                LEFT JOIN conversation_sessions s ON s.id = m.conversation_id
                ORDER BY COALESCE(m.updated_at, m.created_at) DESC, m.id DESC
                """
            ).fetchall()
        return [self._regular_memory_from_row(row) for row in rows]

    def _strategic_memory_details(self) -> list[StudioMemoryDetail]:
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT
                    sm.raw_json,
                    r.repo_name,
                    COALESCE(NULLIF(s.display_title, ''), s.title) AS conversation_title,
                    (
                        SELECT COUNT(*)
                        FROM strategic_memory_conflicts c
                        WHERE c.existing_memory_id = sm.id AND c.status = 'open'
                    ) AS conflict_count
                FROM strategic_memories sm
                LEFT JOIN repo_profiles r ON r.id = sm.repo_profile_id
                LEFT JOIN conversation_sessions s ON s.id = sm.conversation_id
                ORDER BY sm.updated_at DESC, sm.id DESC
                """
            ).fetchall()
        return [self._strategic_memory_from_row(row) for row in rows]

    def _regular_memory_from_row(self, row: sqlite3.Row) -> StudioMemoryDetail:
        memory_type = _row_str(row, "human_type") or _regular_human_type(_row_str(row, "type"))
        created_at = _datetime_from_text(_row_str(row, "created_at"))
        updated_at = _optional_datetime_from_text(_row_optional_str(row, "updated_at")) or created_at
        evidence = [
            StudioMemoryEvidence.model_validate(item)
            for item in _json_loads_list_of_dicts(_row_str(row, "evidence_json"))
        ]
        conversation_id = _row_optional_str(row, "conversation_id")
        conversation_title = _row_optional_str(row, "conversation_title")
        return StudioMemoryDetail(
            id=_row_str(row, "id"),
            kind=StudioMemoryKind.REGULAR,
            type=memory_type,
            type_label=memory_type_label(memory_type),
            summary=_row_str(row, "summary") or _preview(_row_str(row, "content")),
            content=_row_str(row, "content"),
            scope=StudioMemoryScope(_row_str(row, "scope")),
            project=_row_optional_str(row, "project"),
            repo_profile_id=_row_optional_str(row, "repo_profile_id"),
            repo_name=_row_optional_str(row, "repo_name"),
            source=_row_str(row, "source"),
            confidence=_row_float(row, "confidence"),
            importance=_row_float(row, "importance"),
            stability=_row_str(row, "stability"),
            created_at=created_at,
            updated_at=updated_at,
            archived=_row_optional_str(row, "archived_at") is not None,
            linked_conversation_id=conversation_id,
            linked_conversation=StudioLink(
                label=conversation_title or conversation_id or "Conversation",
                href=f"/conversations/{conversation_id}",
            )
            if conversation_id is not None
            else None,
            linked_work=[],
            evidence=evidence,
            conflict_warnings=[],
            conflict_count=0,
            history=[
                StudioMemoryHistoryItem(at=created_at, event="Created"),
                StudioMemoryHistoryItem(at=updated_at, event="Updated"),
            ],
        )

    def _strategic_memory_from_row(self, row: sqlite3.Row) -> StudioMemoryDetail:
        item = StrategicMemoryItem.model_validate_json(_row_str(row, "raw_json"))
        memory_type = _strategic_human_type(item.type)
        conflicts = self._conflict_warnings(item.id)
        return StudioMemoryDetail(
            id=item.id,
            kind=StudioMemoryKind.STRATEGIC,
            type=memory_type,
            type_label=memory_type_label(memory_type),
            summary=item.summary or _preview(item.content),
            content=item.content,
            scope=StudioMemoryScope(item.scope.value),
            project=item.project,
            repo_profile_id=item.repo_profile_id,
            repo_name=_row_optional_str(row, "repo_name"),
            source=item.source.value,
            confidence=item.confidence,
            importance=item.importance,
            stability=item.stability.value,
            created_at=item.created_at,
            updated_at=item.updated_at,
            archived=item.archived_at is not None,
            linked_conversation_id=item.conversation_id,
            linked_conversation=StudioLink(
                label=_row_optional_str(row, "conversation_title")
                or item.conversation_id
                or "Conversation",
                href=f"/conversations/{item.conversation_id}",
            )
            if item.conversation_id is not None
            else None,
            linked_work=[],
            evidence=[
                StudioMemoryEvidence(
                    source=evidence.source,
                    content=evidence.content,
                    kind=evidence.kind,
                    source_id=evidence.source_id,
                    confidence=evidence.confidence,
                )
                for evidence in item.evidence
            ],
            conflict_warnings=conflicts,
            conflict_count=_row_int(row, "conflict_count"),
            history=[
                StudioMemoryHistoryItem(at=item.created_at, event="Created"),
                StudioMemoryHistoryItem(at=item.updated_at, event="Updated"),
            ],
        )

    def _create_regular_memory(self, request: StudioMemoryCreateRequest) -> StudioMemoryDetail:
        memory_id = f"mem_{uuid4().hex[:12]}"
        now = _datetime_to_text(datetime.now(UTC))
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO memories (
                    id, type, content, summary, tags, project, confidence, importance,
                    created_at, last_verified_at, source, updated_at, archived_at, scope,
                    repo_profile_id, conversation_id, evidence_json, stability, human_type
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?, NULL, ?, ?, ?, ?, ?, ?)
                """,
                (
                    memory_id,
                    _regular_type(request.type).value,
                    request.content,
                    request.summary,
                    _json_dumps(request.tags),
                    request.project or "default",
                    request.confidence,
                    request.importance,
                    now,
                    request.source,
                    now,
                    request.scope.value,
                    request.repo_profile_id,
                    request.conversation_id,
                    _json_dumps([item.model_dump(mode="json") for item in request.evidence]),
                    request.stability,
                    request.type,
                ),
            )
        detail = self.get_memory(memory_id)
        if detail is None:
            raise RuntimeError("Created memory could not be loaded.")
        return detail

    def _patch_regular_memory(self, memory_id: str, request: StudioMemoryPatchRequest) -> None:
        updates: dict[str, object] = {"updated_at": _datetime_to_text(datetime.now(UTC))}
        if request.type is not None:
            updates["human_type"] = request.type
            updates["type"] = _regular_type(request.type).value
        for field in (
            "content",
            "summary",
            "project",
            "repo_profile_id",
            "conversation_id",
            "confidence",
            "importance",
            "stability",
            "source",
        ):
            if field in request.model_fields_set:
                updates[field] = getattr(request, field)
        if request.scope is not None:
            updates["scope"] = request.scope.value
        if request.evidence is not None:
            updates["evidence_json"] = _json_dumps(
                [item.model_dump(mode="json") for item in request.evidence]
            )
        if request.tags is not None:
            updates["tags"] = _json_dumps(request.tags)
        columns = ", ".join(f"{column} = ?" for column in updates)
        with connect_database(self.database_path) as connection:
            connection.execute(
                f"UPDATE memories SET {columns} WHERE id = ?",
                (*updates.values(), memory_id),
            )

    def _conflict_warnings(self, memory_id: str) -> list[str]:
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT description FROM strategic_memory_conflicts
                WHERE existing_memory_id = ? AND status = 'open'
                ORDER BY severity DESC, created_at DESC
                """,
                (memory_id,),
            ).fetchall()
        return [_row_str(row, "description") for row in rows]

    def _resolve_memory_conflicts(self, memory_id: str) -> None:
        now = _datetime_to_text(datetime.now(UTC))
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                UPDATE strategic_memory_conflicts
                SET status = 'resolved', resolved_at = ?
                WHERE existing_memory_id = ? AND status = 'open'
                """,
                (now, memory_id),
            )

    def _get_memory_update(self, update_id: str) -> ConversationMemoryUpdate | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT raw_json FROM conversation_memory_updates WHERE id = ?",
                (update_id,),
            ).fetchone()
        if row is None:
            return None
        return ConversationMemoryUpdate.model_validate_json(_row_str(row, "raw_json"))

    def _set_memory_update_status(
        self,
        update_id: str,
        status: str,
        memory_id: str | None,
    ) -> None:
        update = self._get_memory_update(update_id)
        if update is None:
            return
        updated = update.model_copy(update={"status": status, "memory_id": memory_id})
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                UPDATE conversation_memory_updates
                SET status = ?, memory_id = ?, raw_json = ?
                WHERE id = ?
                """,
                (status, memory_id, updated.model_dump_json(), update_id),
            )

    def _local_provider_config(self) -> StudioProviderConfig:
        settings = self._read_settings()
        now = datetime.now(UTC)
        return StudioProviderConfig(
            id="local",
            provider_type="local",
            name="Local deterministic",
            model="deterministic",
            base_url="",
            configured=True,
            status=StudioProviderStatus.LOCAL_MODE,
            status_label="Local mode",
            status_detail="Runs deterministic local deliberation without an API key.",
            intended_roles=["conversation", "fallback", "testing"],
            context_window=6000,
            input_cost_per_million=0.0,
            output_cost_per_million=0.0,
            thinking_enabled=False,
            reasoning_effort="high",
            max_output_tokens=4000,
            effective_source="local",
            api_key_source="not required",
            default_for_conversation=settings.deterministic_mode
            or not any(provider.default_for_conversation for provider in self._stored_provider_configs()),
            created_at=now,
            updated_at=now,
        )

    def _stored_provider_configs(self) -> list[StudioProviderConfig]:
        with connect_database(self.database_path) as connection:
            rows = connection.execute(
                """
                SELECT * FROM studio_provider_configs
                ORDER BY default_for_conversation DESC, updated_at DESC, id DESC
                """
            ).fetchall()
        return [self._provider_from_row(row) for row in rows]

    def _provider_from_row(self, row: sqlite3.Row) -> StudioProviderConfig:
        status = StudioProviderStatus(_row_str(row, "status"))
        return StudioProviderConfig(
            id=_row_str(row, "id"),
            provider_type=_row_str(row, "provider_type"),
            name=_row_str(row, "name"),
            model=_row_str(row, "model"),
            base_url=_row_str(row, "base_url"),
            configured=bool(_row_optional_str(row, "api_key_secret"))
            or _row_str(row, "provider_type") == "local",
            status=status,
            status_label=_provider_status_label(status),
            status_detail=_row_str(row, "status_detail"),
            intended_roles=_json_loads_str_list(_row_str(row, "intended_roles_json")),
            context_window=_row_optional_int(row, "context_window"),
            input_cost_per_million=_row_optional_float(row, "input_cost_per_million"),
            output_cost_per_million=_row_optional_float(row, "output_cost_per_million"),
            thinking_enabled=_row_bool(row, "thinking_enabled"),
            reasoning_effort=_row_str(row, "reasoning_effort") or "high",
            max_output_tokens=_row_optional_int(row, "max_output_tokens"),
            effective_source="studio",
            api_key_source="Studio database" if _row_optional_str(row, "api_key_secret") else "not configured",
            default_for_conversation=_row_bool(row, "default_for_conversation"),
            created_at=_datetime_from_text(_row_str(row, "created_at")),
            updated_at=_datetime_from_text(_row_str(row, "updated_at")),
        )

    def _save_provider(
        self,
        provider_id: str,
        request: StudioProviderUpsertRequest,
        *,
        existing_secret: str | None,
    ) -> None:
        now = _datetime_to_text(datetime.now(UTC))
        if request.default_for_conversation:
            self._set_default_provider(provider_id)
        secret = request.api_key if request.api_key is not None else existing_secret
        configured = bool(secret) or request.provider_type == "local"
        status = (
            StudioProviderStatus.CONFIGURED
            if configured
            else StudioProviderStatus.NOT_CONFIGURED
        )
        raw = {
            "id": provider_id,
            "provider_type": request.provider_type,
            "name": request.name,
            "model": request.model,
            "base_url": request.base_url,
            "context_window": request.context_window,
            "input_cost_per_million": request.input_cost_per_million,
            "output_cost_per_million": request.output_cost_per_million,
            "thinking_enabled": request.thinking_enabled,
            "reasoning_effort": request.reasoning_effort,
            "max_output_tokens": request.max_output_tokens,
            "intended_roles": request.intended_roles,
            "default_for_conversation": request.default_for_conversation,
        }
        with connect_database(self.database_path) as connection:
            existing = connection.execute(
                "SELECT created_at FROM studio_provider_configs WHERE id = ?",
                (provider_id,),
            ).fetchone()
            connection.execute(
                """
                INSERT OR REPLACE INTO studio_provider_configs (
                    id, provider_type, name, model, base_url, api_key_secret,
                    context_window, input_cost_per_million, output_cost_per_million,
                    intended_roles_json, default_for_conversation, status, status_detail,
                    created_at, updated_at, raw_json, thinking_enabled, reasoning_effort,
                    max_output_tokens
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    provider_id,
                    request.provider_type,
                    request.name,
                    request.model,
                    request.base_url.rstrip("/"),
                    secret,
                    request.context_window,
                    request.input_cost_per_million,
                    request.output_cost_per_million,
                    _json_dumps(request.intended_roles),
                    int(request.default_for_conversation),
                    status.value,
                    "Configured" if configured else "Missing API key or required fields.",
                    _row_str(existing, "created_at") if existing is not None else now,
                    now,
                    _json_dumps(raw),
                    int(request.thinking_enabled),
                    request.reasoning_effort,
                    request.max_output_tokens,
                ),
            )

    def _set_default_provider(self, provider_id: str) -> None:
        with connect_database(self.database_path) as connection:
            connection.execute("UPDATE studio_provider_configs SET default_for_conversation = 0")
            if provider_id != "local":
                connection.execute(
                    "UPDATE studio_provider_configs SET default_for_conversation = 1 WHERE id = ?",
                    (provider_id,),
                )

    def _provider_secret_row(self, provider_id: str) -> sqlite3.Row | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT * FROM studio_provider_configs WHERE id = ?",
                (provider_id,),
            ).fetchone()
        return cast(sqlite3.Row | None, row)

    def _update_provider_status(
        self,
        provider_id: str,
        status: StudioProviderStatus,
        detail: str,
    ) -> None:
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                UPDATE studio_provider_configs
                SET status = ?, status_detail = ?, updated_at = ?
                WHERE id = ?
                """,
                (status.value, detail, _datetime_to_text(datetime.now(UTC)), provider_id),
            )

    def default_provider(self) -> ModelProvider | None:
        """Return the saved Studio default; environment routing remains the fallback."""

        if self._read_settings().deterministic_mode:
            return FakeModelProvider()
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT * FROM studio_provider_configs
                WHERE default_for_conversation = 1
                ORDER BY updated_at DESC LIMIT 1
                """
            ).fetchone()
        if row is None:
            return None
        provider = self._provider_from_secret_row(row)
        return provider if provider.is_available else None

    def _provider_from_secret_row(self, row: sqlite3.Row) -> ModelProvider:
        provider_type = _row_str(row, "provider_type")
        base_url = _row_str(row, "base_url")
        api_key = _row_optional_str(row, "api_key_secret")
        model = _row_str(row, "model")
        context_window = _row_optional_int(row, "context_window")
        input_cost = _row_optional_float(row, "input_cost_per_million")
        output_cost = _row_optional_float(row, "output_cost_per_million")
        if provider_type == "deepseek":
            return DeepSeekProvider(
                base_url=base_url,
                api_key=api_key,
                model=model,
                context_window=context_window,
                input_cost_per_million=input_cost,
                output_cost_per_million=output_cost,
                thinking_enabled=_row_bool(row, "thinking_enabled"),
                reasoning_effort=_row_str(row, "reasoning_effort") or "high",
                max_output_tokens=_row_optional_int(row, "max_output_tokens"),
                timeout=8,
            )
        return OpenAICompatibleProvider(
            base_url=base_url,
            api_key=api_key,
            model=model,
            context_window=context_window,
            input_cost_per_million=input_cost,
            output_cost_per_million=output_cost,
            timeout=8,
        )

    def _read_settings(self) -> StudioSettings:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                "SELECT value_json FROM studio_settings WHERE key = 'settings'"
            ).fetchone()
        if row is None:
            return StudioSettings()
        return StudioSettings.model_validate_json(_row_str(row, "value_json"))

    def _write_settings(self, settings: StudioSettings) -> None:
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO studio_settings (key, value_json, updated_at)
                VALUES ('settings', ?, ?)
                """,
                (settings.model_dump_json(), _datetime_to_text(datetime.now(UTC))),
            )

    def _usage_event_from_row(self, row: sqlite3.Row) -> StudioUsageEvent:
        conversation_id = _row_optional_str(row, "conversation_id")
        title = _row_optional_str(row, "conversation_title")
        deterministic = _row_bool(row, "deterministic")
        context_trimmed = _row_bool(row, "context_trimmed")
        summary = _row_str(row, "summary")
        if not summary:
            summary = "Solved without a model call" if deterministic else "One model call used"
        if context_trimmed and "Context trimmed" not in summary:
            summary = f"{summary}; Context trimmed to fit budget"
        cost = _row_float(row, "estimated_cost")
        if cost > 0:
            summary = f"{summary}; Estimated cost: ${cost:.6f}"
        return StudioUsageEvent(
            id=_row_str(row, "id"),
            task_type=_row_str(row, "task_type"),
            provider=_row_str(row, "provider"),
            model=_row_str(row, "model"),
            provider_model=_row_str(row, "provider_model"),
            message=summary,
            estimated_input_tokens=_row_int(row, "estimated_input_tokens"),
            estimated_output_tokens=_row_int(row, "estimated_output_tokens"),
            input_tokens=_row_int(row, "input_tokens"),
            output_tokens=_row_int(row, "output_tokens"),
            cached_input_tokens=_row_int(row, "cached_input_tokens"),
            estimated_cost=cost,
            thinking_enabled=_row_bool(row, "thinking_enabled"),
            reasoning_effort=_row_optional_str(row, "reasoning_effort"),
            usage_source=_row_str(row, "usage_source"),
            deterministic=deterministic,
            context_trimmed=context_trimmed,
            success=_row_bool(row, "success"),
            linked_conversation=StudioLink(
                label=title or conversation_id or "Conversation",
                href=f"/conversations/{conversation_id}",
            )
            if conversation_id is not None
            else None,
            created_at=_datetime_from_text(_row_str(row, "created_at")),
        )

    def _cost_per_successful_coding_task(self, events: list[StudioUsageEvent]) -> float | None:
        with connect_database(self.database_path) as connection:
            row = connection.execute(
                """
                SELECT COUNT(*) AS count
                FROM coding_requests
                WHERE status IN ('completed', 'validated', 'succeeded')
                """
            ).fetchone()
        count = _row_int(row, "count") if row is not None else 0
        if count <= 0:
            return None
        return sum(event.estimated_cost for event in events) / count

    def _decision_summary(self, trace: DecisionTraceVariant) -> AdvancedDecisionSummary:
        return AdvancedDecisionSummary(
            id=trace.id,
            decision_type=trace.decision_type.value,
            decision=_decision_title(trace),
            selected_option=trace.selected_option,
            confidence=trace.confidence,
            outcome=trace.outcome_id,
            repo=None,
            occurred_at=trace.timestamp,
            href=f"/advanced/decisions/{trace.id}",
        )

    def _schema_version(self, database_path: Path) -> int:
        with sqlite3.connect(database_path) as connection:
            row = connection.execute(
                "SELECT MAX(version) FROM schema_migrations"
            ).fetchone()
        if row is None or row[0] is None:
            raise ValueError("Backup does not contain Hephaestus schema metadata.")
        return int(row[0])


def memory_type_label(value: str) -> str:
    """Return a human-readable memory type label."""

    return MEMORY_TYPE_LABELS.get(value, value.replace("_", " ").title())


def _memory_matches(
    memory: StudioMemoryDetail,
    *,
    query: str,
    type_filter: str | None,
    scope: StudioMemoryScope | None,
    project: str | None,
    repo_profile_id: str | None,
    source: str | None,
    stability: str | None,
    state: StudioMemoryState,
) -> bool:
    if state == StudioMemoryState.ACTIVE and memory.archived:
        return False
    if state == StudioMemoryState.ARCHIVED and not memory.archived:
        return False
    if type_filter and memory.type != type_filter:
        return False
    if scope is not None and memory.scope != scope:
        return False
    if project and memory.project != project:
        return False
    if repo_profile_id and memory.repo_profile_id != repo_profile_id:
        return False
    if source and memory.source != source:
        return False
    if stability and memory.stability != stability:
        return False
    terms = [term.lower() for term in query.split() if term.strip()]
    if terms:
        text = " ".join(
            [
                memory.type_label,
                memory.summary,
                memory.content,
                memory.source,
                memory.project or "",
                memory.repo_name or "",
            ]
        ).lower()
        return all(term in text for term in terms)
    return True


def _regular_type(value: str) -> MemoryType:
    return _REGULAR_MEMORY_TYPES.get(value, MemoryType.PROJECT)


def _regular_human_type(value: str) -> str:
    if value == MemoryType.PROCEDURAL.value:
        return "working_style"
    if value == MemoryType.FAILURE.value:
        return "lesson_learned"
    if value == MemoryType.DECISION.value:
        return "strategic_decision"
    if value == MemoryType.SEMANTIC.value:
        return "project_fact"
    return "project_fact"


def _strategic_type(value: str | None) -> StrategicMemoryType:
    if value is None:
        return StrategicMemoryType.TECHNICAL_ASSUMPTION
    return _STRATEGIC_MEMORY_TYPES.get(value, StrategicMemoryType.TECHNICAL_ASSUMPTION)


def _strategic_human_type(value: StrategicMemoryType) -> str:
    reverse = {schema_type: human_type for human_type, schema_type in _STRATEGIC_MEMORY_TYPES.items()}
    return reverse.get(value, "project_fact")


def _strategic_stability(value: str | None) -> StrategicMemoryStability:
    try:
        return StrategicMemoryStability(value or StrategicMemoryStability.MEDIUM_TERM.value)
    except ValueError:
        return StrategicMemoryStability.MEDIUM_TERM


def _strategic_source(value: str | None) -> StrategicMemorySource:
    source = (value or "manual").lower()
    if source == "conversation":
        return StrategicMemorySource.CONVERSATION_INFERRED
    try:
        return StrategicMemorySource(source)
    except ValueError:
        return StrategicMemorySource.MANUAL


def _provider_status_label(status: StudioProviderStatus) -> str:
    labels = {
        StudioProviderStatus.CONFIGURED: "Configured",
        StudioProviderStatus.TESTING: "Testing",
        StudioProviderStatus.CONNECTED: "Connected",
        StudioProviderStatus.NOT_CONFIGURED: "Not configured",
        StudioProviderStatus.CONNECTION_FAILED: "Connection failed",
        StudioProviderStatus.INSUFFICIENT_BALANCE: "Insufficient balance",
        StudioProviderStatus.LOCAL_MODE: "Local mode",
    }
    return labels[status]


def _chat_completions_url(base_url: str) -> str:
    stripped = base_url.rstrip("/")
    if stripped.endswith("/chat/completions"):
        return stripped
    if stripped.endswith("/v1"):
        return f"{stripped}/chat/completions"
    return f"{stripped}/v1/chat/completions"


def _split_provider_model(provider_model: str) -> tuple[str, str]:
    if "/" not in provider_model:
        return provider_model, ""
    provider, model = provider_model.split("/", 1)
    return provider, model


def _decision_category_matches(trace: DecisionTraceVariant, category: str | None) -> bool:
    if category is None:
        return True
    normalized = category.lower()
    if normalized == "conversation":
        return trace.phase == "conversation" or "conversation" in trace.tags
    if normalized == "coding":
        return any("coding" in item for item in [trace.phase, *trace.tags, *trace.will_affect])
    if normalized == "validation":
        return any("validation" in item for item in [trace.phase, *trace.tags, *trace.will_affect])
    if normalized == "release":
        return any("release" in item for item in [trace.phase, *trace.tags, *trace.will_affect])
    if normalized == "policy":
        return trace.decision_type.value == "safety" or "policy" in trace.tags
    if normalized == "tool":
        return "tool" in trace.phase or "tool" in trace.tags
    return True


def _repo_matches(repo: str | None) -> bool:
    return repo is None or bool(repo)


def _decision_title(trace: DecisionTraceVariant) -> str:
    return trace.rationale.splitlines()[0][:160] if trace.rationale else trace.decision_type.value


def _alternative_text(alternative: DecisionAlternative) -> str:
    reason = alternative.rejection_reason or "Not selected."
    return f"{alternative.label}: {reason}"


def _metric_text(metric: DecisionMetric) -> str:
    unit = f" {metric.unit}" if metric.unit else ""
    return f"{metric.name}: {metric.value}{unit}"


def _split_reason_text(value: str) -> list[str]:
    parts = [part.strip(" -") for part in value.replace("\n", ". ").split(".") if part.strip()]
    return parts or [value]


def _public_text_items(values: list[str]) -> list[str]:
    technical_prefixes = (
        "checkpoint_",
        "frontier_",
        "outcome_",
        "provider_",
        "qubo_",
        "run_",
        "trace_",
    )
    return [
        value
        for value in values
        if value and not value.startswith(technical_prefixes) and ":" not in value[:24]
    ]


def _decision_links(trace: DecisionTraceVariant) -> list[StudioLink]:
    links: list[StudioLink] = []
    if trace.outcome_id:
        links.append(StudioLink(label="Outcome", href=f"/workbench/outcomes/{trace.outcome_id}"))
    return links


def _later_evidence_supported(outcome_id: str | None) -> str:
    return "unknown" if outcome_id is None else "linked outcome available"


def _pareto_candidate(
    candidate: DecisionCandidate,
    frontier: ParetoFrontier,
    x_dimension: ObjectiveDimension,
    y_dimension: ObjectiveDimension,
) -> AdvancedParetoCandidate:
    return AdvancedParetoCandidate(
        id=candidate.id,
        label=candidate.label,
        x=candidate.objective_vector.value_for(x_dimension),
        y=candidate.objective_vector.value_for(y_dimension),
        is_frontier=candidate.id in set(frontier.frontier_candidate_ids),
        selected=candidate.id == frontier.selected_candidate_id,
        rationale=candidate.rationale,
        objectives={
            key: float(value)
            for key, value in candidate.objective_vector.model_dump().items()
            if isinstance(value, int | float)
        },
    )


def _pareto_explanation(frontier: ParetoFrontier) -> str:
    frame = (
        "These were the strongest non-dominated options. Choosing one requires a "
        "tradeoff between these objectives."
    )
    if frontier.tradeoff_explanation is not None:
        return f"{frame} {frontier.tradeoff_explanation.summary}"
    return frame


def _selected_solution_text(problem: QuboProblem, solution: QuboSolution | None) -> str:
    if solution is None:
        return "No solver result has been recorded for this formulation."
    labels = [
        variable.label or variable.id
        for variable in problem.variables
        if variable.id in set(solution.selected_variables)
    ]
    return ", ".join(labels) if labels else "No variables selected."


def _heuristic_comparison(problem: QuboProblem, solution: QuboSolution | None) -> str | None:
    baseline = problem.metadata.get("heuristic_result")
    if baseline is None or solution is None:
        return None
    return f"Heuristic baseline: {baseline}; QUBO objective: {solution.objective_value:.3f}."


def _problem_type_label(value: str) -> str:
    return value.replace("_", " ").title()


def _safe_filename(value: str) -> str:
    normalized = "".join(character if character.isalnum() else "-" for character in value.lower())
    return "-".join(part for part in normalized.split("-") if part)[:80] or "conversation"


def _preview(value: str, *, max_length: int = 140) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max_length - 1].rstrip() + "..."


def _safe_error(error: BaseException) -> str:
    text = str(error)
    return text[:180] if text else error.__class__.__name__


def _json_ready(value: Mapping[str, object]) -> dict[str, object]:
    ready = dict(value)
    created_at = ready.get("created_at")
    if isinstance(created_at, datetime):
        ready["created_at"] = _datetime_to_text(created_at)
    return ready


def _json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _json_loads_str_list(value: str) -> list[str]:
    loaded = json.loads(value)
    if not isinstance(loaded, list):
        return []
    return [str(item) for item in loaded]


def _json_loads_list_of_dicts(value: str) -> list[dict[str, object]]:
    loaded = json.loads(value)
    if not isinstance(loaded, list):
        return []
    return [cast(dict[str, object], item) for item in loaded if isinstance(item, dict)]


def _datetime_to_text(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    return value.astimezone(UTC).isoformat()


def _datetime_from_text(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _optional_datetime_from_text(value: str | None) -> datetime | None:
    return _datetime_from_text(value) if value else None


def _row_str(row: sqlite3.Row, key: str) -> str:
    return cast(str, row[key])


def _row_optional_str(row: sqlite3.Row, key: str) -> str | None:
    return cast(str | None, row[key])


def _row_int(row: sqlite3.Row, key: str) -> int:
    return int(cast(int | float, row[key]))


def _row_optional_int(row: sqlite3.Row, key: str) -> int | None:
    value = cast(int | None, row[key])
    return int(value) if value is not None else None


def _row_float(row: sqlite3.Row, key: str) -> float:
    return float(cast(int | float, row[key]))


def _row_optional_float(row: sqlite3.Row, key: str) -> float | None:
    value = cast(int | float | None, row[key])
    return float(value) if value is not None else None


def _row_bool(row: sqlite3.Row, key: str) -> bool:
    return bool(_row_int(row, key))
