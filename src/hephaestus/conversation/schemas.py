"""Typed schemas for conversational deliberation."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from hephaestus.discussion_quality.schemas import (
    DiscussionQualityEvaluation,
    ResearchPlan,
)
from hephaestus.memory.schemas import MemoryItem, MemoryType
from hephaestus.repo.schemas import RepoProfile
from hephaestus.strategic_memory.schemas import (
    StrategicMemoryExtractionResult,
    StrategicMemoryItem,
)


class ConversationIntent(StrEnum):
    """High-level discussion intent used to steer retrieval and deliberation."""

    GENERAL = "general"
    REPO_QUESTION = "repo_question"
    ARCHITECTURE_DISCUSSION = "architecture_discussion"
    PRODUCT_STRATEGY = "product_strategy"
    BUSINESS_STRATEGY = "business_strategy"
    IDEA_STRESS_TEST = "idea_stress_test"
    ROADMAP_DECISION = "roadmap_decision"
    RESEARCH_PLANNING = "research_planning"
    RISK_ANALYSIS = "risk_analysis"
    PERSONAL_CONTEXT = "personal_context"
    DEBUGGING_DISCUSSION = "debugging_discussion"


class DeliberationMode(StrEnum):
    """Reasoning style, not a personality."""

    BALANCED = "balanced"
    DIRECT = "direct"
    CRITICAL = "critical"
    STRATEGIC = "strategic"
    RESEARCH = "research"
    ARCHITECT = "architect"
    COACH = "coach"
    SKEPTICAL_BUT_FAIR = "skeptical_but_fair"


class ConversationRole(StrEnum):
    """Persisted message roles."""

    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ConversationContextItem(BaseModel):
    """A compact context item selected for a conversation turn."""

    model_config = ConfigDict(frozen=True)

    id: str
    source: str
    summary: str
    content: str
    relevance: float = Field(default=0.5, ge=0, le=1)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievedConversationContext(BaseModel):
    """Memory and repo context selected before deliberation."""

    model_config = ConfigDict(frozen=True, arbitrary_types_allowed=True)

    query: str
    intent: ConversationIntent
    memories: list[MemoryItem] = Field(default_factory=list)
    strategic_memories: list[StrategicMemoryItem] = Field(default_factory=list)
    repo_profile: RepoProfile | None = None
    context_items: list[ConversationContextItem] = Field(default_factory=list)

    @property
    def selected_memory_ids(self) -> list[str]:
        """Return selected memory IDs in retrieval order."""

        return [memory.id for memory in self.memories]

    @property
    def selected_strategic_memory_ids(self) -> list[str]:
        """Return selected strategic memory IDs in retrieval order."""

        return [memory.id for memory in self.strategic_memories]


class ConversationSession(BaseModel):
    """A persisted text conversation."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"conv_{uuid4().hex[:12]}")
    title: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    mode: DeliberationMode = DeliberationMode.BALANCED
    repo_profile_id: str | None = None
    archived: bool = False
    summary: str = ""
    linked_decision_trace_ids: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationMessage(BaseModel):
    """A persisted user or assistant message."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"msg_{uuid4().hex[:12]}")
    session_id: str
    role: ConversationRole
    content: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    intent: ConversationIntent | None = None
    mode: DeliberationMode | None = None
    selected_memory_ids: list[str] = Field(default_factory=list)
    context: list[ConversationContextItem] = Field(default_factory=list)
    decision_trace_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ConversationRequest(BaseModel):
    """A user request entering the conversation pipeline."""

    model_config = ConfigDict(frozen=True)

    prompt: str = Field(min_length=1)
    mode: DeliberationMode = DeliberationMode.BALANCED
    session_id: str | None = None
    repo_path: str | None = None
    use_memory: bool = True
    save_memory: bool = False
    save_strategy: bool = False
    show_context: bool = False
    discussion: bool = False
    project: str = "default"


class DeliberationPass(BaseModel):
    """One internal reasoning pass."""

    model_config = ConfigDict(frozen=True)

    name: str
    purpose: str
    findings: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.7, ge=0, le=1)


class DeliberationResult(BaseModel):
    """Structured output from the internal deliberation pipeline."""

    model_config = ConfigDict(frozen=True)

    intent: ConversationIntent
    mode: DeliberationMode
    passes: list[DeliberationPass] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    options: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    tradeoffs: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    recommendation: str = ""
    next_moves: list[str] = Field(default_factory=list)
    final_response: str
    quality_evaluation: DiscussionQualityEvaluation | None = None
    research_plan: ResearchPlan | None = None
    confidence: float = Field(default=0.7, ge=0, le=1)
    provider_model: str = "local/deterministic"
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    estimated_cost: float = Field(default=0.0, ge=0)


class ConversationMemoryCandidate(BaseModel):
    """A suggested durable memory derived from conversation context."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"memcand_{uuid4().hex[:12]}")
    memory_type: MemoryType = MemoryType.PROJECT
    content: str
    summary: str = ""
    tags: list[str] = Field(default_factory=list)
    project: str = "default"
    confidence: float = Field(default=0.7, ge=0, le=1)
    importance: float = Field(default=0.6, ge=0, le=1)
    rationale: str = ""

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        """Normalize memory tags consistently with MemoryItem."""

        return list(dict.fromkeys(tag.strip().lower() for tag in value if tag.strip()))

    def to_memory_item(self, *, source: str = "conversation") -> MemoryItem:
        """Convert the candidate into a persistent memory item."""

        return MemoryItem(
            type=self.memory_type,
            content=self.content,
            summary=self.summary,
            tags=self.tags,
            project=self.project,
            confidence=self.confidence,
            importance=self.importance,
            source=source,
        )


class ConversationMemoryUpdate(BaseModel):
    """A suggested or saved memory update linked to a conversation turn."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"conv_memupd_{uuid4().hex[:12]}")
    session_id: str
    message_id: str | None = None
    candidate: ConversationMemoryCandidate
    status: str = "suggested"
    memory_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ConversationDecisionTrace(BaseModel):
    """Conversation-facing summary of a persisted decision trace."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"convtrace_{uuid4().hex[:12]}")
    session_id: str
    run_id: str | None = None
    decision_trace_id: str | None = None
    intent: ConversationIntent
    mode: DeliberationMode
    key_assumptions: list[str] = Field(default_factory=list)
    options_considered: list[str] = Field(default_factory=list)
    recommendation: str
    confidence: float = Field(default=0.7, ge=0, le=1)
    suggested_next_move: str = ""
    memory_used: list[str] = Field(default_factory=list)
    strategic_memory_used: list[str] = Field(default_factory=list)
    strategic_memories_suggested: list[str] = Field(default_factory=list)
    discussion_quality_rubric: str | None = None
    discussion_quality_score: float | None = Field(default=None, ge=0, le=1)


class ConversationResponse(BaseModel):
    """The complete response returned by `ask`, `discuss`, or chat."""

    model_config = ConfigDict(frozen=True)

    session_id: str
    message_id: str
    intent: ConversationIntent
    mode: DeliberationMode
    answer: str
    deliberation: DeliberationResult
    selected_memory_ids: list[str] = Field(default_factory=list)
    selected_strategic_memory_ids: list[str] = Field(default_factory=list)
    selected_context: list[ConversationContextItem] = Field(default_factory=list)
    memory_candidates: list[ConversationMemoryCandidate] = Field(default_factory=list)
    memory_updates: list[ConversationMemoryUpdate] = Field(default_factory=list)
    strategic_memory_extraction: StrategicMemoryExtractionResult | None = None
    strategic_memory_candidates: list[StrategicMemoryItem] = Field(default_factory=list)
    strategic_memory_updates: list[StrategicMemoryItem] = Field(default_factory=list)
    decision_trace: ConversationDecisionTrace | None = None
    provider_model: str = "local/deterministic"
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    estimated_cost: float = Field(default=0.0, ge=0)
