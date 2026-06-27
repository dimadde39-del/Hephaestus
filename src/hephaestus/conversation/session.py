"""High-level conversation session orchestration."""

from __future__ import annotations

from pathlib import Path

from hephaestus.conversation.analysis import (
    build_conversation_decision_trace,
    build_persisted_decision_trace,
    propose_memory_candidates,
    should_create_decision_trace,
    title_from_prompt,
)
from hephaestus.conversation.classifier import classify_intent
from hephaestus.conversation.context import retrieve_conversation_context
from hephaestus.conversation.deliberation import ConversationDeliberator
from hephaestus.conversation.prompt_builder import estimate_tokens
from hephaestus.conversation.repository import ConversationRepository
from hephaestus.conversation.schemas import (
    ConversationBudgetReport,
    ConversationDecisionTrace,
    ConversationIntent,
    ConversationMemoryCandidate,
    ConversationMemoryUpdate,
    ConversationMessage,
    ConversationRequest,
    ConversationResponse,
    ConversationRole,
    ConversationSession,
    DeliberationMode,
    DeliberationPass,
    DeliberationResult,
    RetrievedConversationContext,
)
from hephaestus.decision import DecisionTraceRepository
from hephaestus.models import ModelProvider
from hephaestus.policy import PolicyRepository, evaluate_policy_request, render_policy_response
from hephaestus.policy.schemas import PolicyEvaluation
from hephaestus.repo import RepoProfileRepository
from hephaestus.storage import RunRecord, RunRepository, SqliteMemoryRepository
from hephaestus.strategic_memory.extractor import extract_strategic_memories
from hephaestus.strategic_memory.repository import StrategicMemoryRepository
from hephaestus.strategic_memory.schemas import (
    StrategicMemoryConflict,
    StrategicMemoryExtractionResult,
    StrategicMemoryItem,
)


class ConversationService:
    """Coordinate conversation persistence, retrieval, deliberation, and traces."""

    def __init__(
        self,
        database_path: Path | str | None = None,
        *,
        provider: ModelProvider | None = None,
    ) -> None:
        self.repository = ConversationRepository(database_path)
        self.database_path = self.repository.database_path
        self.memory_repository = SqliteMemoryRepository(self.database_path)
        self.strategic_memory_repository = StrategicMemoryRepository(self.database_path)
        self.repo_repository = RepoProfileRepository(self.database_path)
        self.policy_repository = PolicyRepository(self.database_path)
        self.run_repository = RunRepository(self.database_path)
        self.trace_repository = DecisionTraceRepository(self.database_path)
        self.deliberator = ConversationDeliberator(provider)

    def respond(self, request: ConversationRequest) -> ConversationResponse:
        """Handle one user message and persist the result."""

        session = self._resolve_session(request)
        effective_request = self._request_with_session_repo(request, session)
        intent = classify_intent(effective_request.prompt)
        recent_messages = self.repository.list_messages(session.id)
        if session.mode != effective_request.mode:
            updated_session = self.repository.update_session_mode(session.id, effective_request.mode)
            if updated_session is not None:
                session = updated_session

        user_message = self.repository.add_message(
            ConversationMessage(
                session_id=session.id,
                role=ConversationRole.USER,
                content=effective_request.prompt,
                intent=intent,
                mode=effective_request.mode,
            )
        )
        policy_profile = self.policy_repository.get_active_profile()
        policy_evaluation = evaluate_policy_request(
            effective_request.prompt,
            profile=policy_profile,
        )
        if policy_evaluation.decision.is_blocking:
            return self._respond_with_policy_boundary(
                session.id,
                user_message.id,
                effective_request,
                intent,
                policy_evaluation,
            )
        context = retrieve_conversation_context(
            effective_request,
            intent,
            memory_repository=self.memory_repository,
            strategic_memory_repository=self.strategic_memory_repository,
            repo_repository=self.repo_repository,
        )
        if context.repo_profile is not None:
            updated_session = self.repository.set_session_repo_profile(
                session.id,
                context.repo_profile.id,
            )
            if updated_session is not None:
                session = updated_session

        deliberation = self.deliberator.deliberate(
            effective_request,
            intent,
            context,
            recent_messages=recent_messages,
            policy_evaluation=policy_evaluation,
        )
        policy_evaluation = deliberation.policy_evaluation or policy_evaluation
        self.policy_repository.record_evaluation(policy_evaluation)
        memory_candidates = propose_memory_candidates(
            effective_request.prompt,
            deliberation,
            project=effective_request.project,
        )
        strategic_extraction = self._extract_strategic_memory_updates(
            effective_request,
            deliberation,
            session_id=session.id,
            repo_profile_id=context.repo_profile.id if context.repo_profile is not None else None,
        )
        decision_trace = self._maybe_create_decision_trace(
            session.id,
            deliberation,
            context,
            strategic_extraction,
        )

        selected_memory_ids = [
            item.id for item in deliberation.selected_context if item.source == "memory"
        ]
        selected_strategic_memory_ids = [
            item.id
            for item in deliberation.selected_context
            if item.source == "strategic_memory"
        ]
        assistant_message = ConversationMessage(
            session_id=session.id,
            role=ConversationRole.ASSISTANT,
            content=deliberation.final_response,
            intent=intent,
            mode=effective_request.mode,
            selected_memory_ids=selected_memory_ids,
            context=deliberation.selected_context,
            decision_trace_id=(
                decision_trace.decision_trace_id if decision_trace is not None else None
            ),
            metadata={
                "provider_model": deliberation.provider_model,
                "reply_to": user_message.id,
                "policy_evaluation_id": policy_evaluation.id,
                "policy_profile": policy_evaluation.profile_type.value,
                "policy_decision": policy_evaluation.decision.decision_type.value,
                "policy_over_refusal_detected": policy_evaluation.over_refusal_detected,
            },
        )
        assistant_message = self.repository.save_response(assistant_message)
        if decision_trace is not None and decision_trace.decision_trace_id is not None:
            self.repository.link_decision_trace(
                session.id,
                decision_trace.decision_trace_id,
                message_id=assistant_message.id,
            )

        memory_updates = self._save_memory_updates(
            session.id,
            assistant_message.id,
            memory_candidates,
            save_memory=effective_request.save_memory,
        )
        strategic_memory_updates = self._save_strategic_memory_updates(
            strategic_extraction,
            save_memory=effective_request.save_memory or effective_request.save_strategy,
        )

        return ConversationResponse(
            session_id=session.id,
            message_id=assistant_message.id,
            intent=intent,
            mode=effective_request.mode,
            answer=deliberation.final_response,
            deliberation=deliberation,
            selected_memory_ids=selected_memory_ids,
            selected_strategic_memory_ids=selected_strategic_memory_ids,
            selected_context=deliberation.selected_context,
            memory_candidates=memory_candidates,
            memory_updates=memory_updates,
            strategic_memory_extraction=strategic_extraction,
            strategic_memory_candidates=strategic_extraction.items,
            strategic_memory_updates=strategic_memory_updates,
            decision_trace=decision_trace,
            policy_evaluation=policy_evaluation,
            provider_model=deliberation.provider_model,
            input_tokens=deliberation.input_tokens,
            output_tokens=deliberation.output_tokens,
            cached_input_tokens=deliberation.cached_input_tokens,
            thinking_enabled=deliberation.thinking_enabled,
            reasoning_effort=deliberation.reasoning_effort,
            provider_success=deliberation.provider_success,
            estimated_cost=deliberation.estimated_cost,
            budget=deliberation.budget,
        )

    def _respond_with_policy_boundary(
        self,
        session_id: str,
        user_message_id: str,
        request: ConversationRequest,
        intent: ConversationIntent,
        policy_evaluation: PolicyEvaluation,
    ) -> ConversationResponse:
        response_text = render_policy_response(policy_evaluation)
        output_tokens = estimate_tokens(response_text)
        budget = ConversationBudgetReport(
            provider_model="local/policy",
            selected_provider="local",
            selected_model="policy",
            estimated_input_tokens=estimate_tokens(request.prompt),
            estimated_output_tokens=output_tokens,
            output_token_budget=request.output_token_budget,
            context_window=request.context_token_budget,
            prompt_token_budget=request.context_token_budget,
        )
        deliberation = DeliberationResult(
            intent=intent,
            mode=request.mode,
            passes=[
                DeliberationPass(
                    name="PolicyEvaluator",
                    purpose="Apply the active user-owned policy profile before synthesis.",
                    findings=policy_evaluation.decision.reasons,
                    confidence=policy_evaluation.decision.confidence,
                )
            ],
            assumptions=["The request crosses a blocked policy boundary."],
            options=["Refuse briefly.", "Offer safer defensive discussion if useful."],
            risks=["Fulfilling the request would enable harm."],
            tradeoffs=["Short refusal preserves clarity without moral theater."],
            missing_information=[],
            recommendation="Refuse briefly and stay available for defensive or benign alternatives.",
            next_moves=["Ask for a defensive or benign version of the task."],
            final_response=response_text,
            policy_evaluation=policy_evaluation,
            confidence=policy_evaluation.decision.confidence,
            provider_model="local/policy",
            input_tokens=budget.estimated_input_tokens,
            output_tokens=output_tokens,
            budget=budget,
        )
        self.policy_repository.record_evaluation(policy_evaluation)
        assistant_message = self.repository.save_response(
            ConversationMessage(
                session_id=session_id,
                role=ConversationRole.ASSISTANT,
                content=response_text,
                intent=intent,
                mode=request.mode,
                metadata={
                    "provider_model": "local/policy",
                    "reply_to": user_message_id,
                    "policy_evaluation_id": policy_evaluation.id,
                    "policy_profile": policy_evaluation.profile_type.value,
                    "policy_decision": policy_evaluation.decision.decision_type.value,
                },
            )
        )
        return ConversationResponse(
            session_id=session_id,
            message_id=assistant_message.id,
            intent=intent,
            mode=request.mode,
            answer=response_text,
            deliberation=deliberation,
            policy_evaluation=policy_evaluation,
            provider_model="local/policy",
            input_tokens=budget.estimated_input_tokens,
            output_tokens=output_tokens,
            budget=budget,
        )

    def list_sessions(self, *, limit: int = 20) -> list[ConversationSession]:
        """List recent conversation sessions."""

        return self.repository.list_sessions(limit=limit)

    def get_session(self, session_id: str) -> ConversationSession | None:
        """Read one session."""

        return self.repository.get_session(session_id)

    def list_messages(self, session_id: str) -> list[ConversationMessage]:
        """List messages for one session."""

        return self.repository.list_messages(session_id)

    def set_mode(self, session_id: str, mode: DeliberationMode) -> ConversationSession | None:
        """Update a chat session mode."""

        return self.repository.update_session_mode(session_id, mode)

    def _resolve_session(self, request: ConversationRequest) -> ConversationSession:
        if request.session_id is not None:
            session = self.repository.get_session(request.session_id)
            if session is None:
                raise ValueError(f"Conversation session not found: {request.session_id}")
            return session

        session = ConversationSession(
            title=title_from_prompt(request.prompt),
            mode=request.mode,
        )
        return self.repository.create_session(session)

    def _request_with_session_repo(
        self,
        request: ConversationRequest,
        session: ConversationSession,
    ) -> ConversationRequest:
        if request.repo_path is not None or session.repo_profile_id is None:
            return request
        profile = self.repo_repository.get_profile(session.repo_profile_id)
        if profile is None:
            return request
        return request.model_copy(update={"repo_path": profile.path})

    def _maybe_create_decision_trace(
        self,
        session_id: str,
        result: DeliberationResult,
        context: RetrievedConversationContext,
        strategic_extraction: StrategicMemoryExtractionResult,
    ) -> ConversationDecisionTrace | None:
        if not should_create_decision_trace(result.intent):
            return None

        summary = build_conversation_decision_trace(
            session_id,
            result,
            context,
            strategic_extraction,
        )
        run = self.run_repository.save_run(
            RunRecord(
                goal=f"Conversation: {summary.intent.value}",
                mode="conversation",
            )
        )
        trace = build_persisted_decision_trace(run.id, summary)
        self.trace_repository.save_trace(trace)
        self.run_repository.complete_run(
            run.id,
            estimated_input_tokens=result.input_tokens,
            estimated_output_tokens=result.output_tokens,
            estimated_cost=result.estimated_cost,
            objective_score=result.confidence,
            risk_score=max(0.0, 1.0 - result.confidence),
            summary=summary.recommendation,
        )
        return summary.model_copy(
            update={
                "run_id": run.id,
                "decision_trace_id": trace.id,
            }
        )

    def _extract_strategic_memory_updates(
        self,
        request: ConversationRequest,
        result: DeliberationResult,
        *,
        session_id: str,
        repo_profile_id: str | None,
    ) -> StrategicMemoryExtractionResult:
        extraction = extract_strategic_memories(
            request.prompt,
            result,
            project=request.project,
            repo_profile_id=repo_profile_id,
            conversation_id=session_id,
        )
        conflicts: list[StrategicMemoryConflict] = []
        for item in extraction.items:
            conflicts.extend(self.strategic_memory_repository.detect_simple_conflicts(item))
        return extraction.model_copy(update={"conflicts": conflicts})

    def _save_memory_updates(
        self,
        session_id: str,
        message_id: str,
        candidates: list[ConversationMemoryCandidate],
        *,
        save_memory: bool,
    ) -> list[ConversationMemoryUpdate]:
        updates: list[ConversationMemoryUpdate] = []
        for candidate in candidates:
            memory_id: str | None = None
            status = "suggested"
            if save_memory:
                memory = self.memory_repository.add(candidate.to_memory_item())
                memory_id = memory.id
                status = "saved"
            update = self.repository.save_memory_update(
                ConversationMemoryUpdate(
                    session_id=session_id,
                    message_id=message_id,
                    candidate=candidate,
                    status=status,
                    memory_id=memory_id,
                )
            )
            updates.append(update)
        return updates

    def _save_strategic_memory_updates(
        self,
        extraction: StrategicMemoryExtractionResult,
        *,
        save_memory: bool,
    ) -> list[StrategicMemoryItem]:
        if not save_memory:
            return []
        saved: list[StrategicMemoryItem] = []
        for item in extraction.items:
            saved.append(self.strategic_memory_repository.save_memory(item))
        return saved
