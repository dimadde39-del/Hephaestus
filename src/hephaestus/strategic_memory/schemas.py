"""Typed schemas for durable strategic memory."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrategicMemoryType(StrEnum):
    """Strategic memory categories that shape non-code discussions."""

    GOAL = "goal"
    AMBITION = "ambition"
    CONSTRAINT = "constraint"
    FEAR = "fear"
    RISK_PATTERN = "risk_pattern"
    PREFERENCE = "preference"
    PRINCIPLE = "principle"
    STRATEGIC_DECISION = "strategic_decision"
    ROADMAP_DECISION = "roadmap_decision"
    POSITIONING_DECISION = "positioning_decision"
    LAUNCH_DECISION = "launch_decision"
    BUSINESS_ASSUMPTION = "business_assumption"
    TECHNICAL_ASSUMPTION = "technical_assumption"
    REJECTED_PATH = "rejected_path"
    LESSON_LEARNED = "lesson_learned"
    OPEN_QUESTION = "open_question"


class StrategicMemoryScope(StrEnum):
    """How widely a strategic memory applies."""

    GLOBAL = "global"
    PROJECT = "project"
    REPO = "repo"
    CONVERSATION = "conversation"


class StrategicMemoryStability(StrEnum):
    """Expected lifetime of a strategic memory."""

    TEMPORARY = "temporary"
    MEDIUM_TERM = "medium_term"
    LONG_TERM = "long_term"


class StrategicMemorySource(StrEnum):
    """Where a strategic memory came from."""

    USER_EXPLICIT = "user_explicit"
    CONVERSATION_INFERRED = "conversation_inferred"
    OUTCOME_LEARNING = "outcome_learning"
    DECISION_TRACE = "decision_trace"
    MANUAL = "manual"


class StrategicMemoryEvidence(BaseModel):
    """Evidence attached to a strategic memory."""

    model_config = ConfigDict(frozen=True)

    source: str = ""
    content: str
    kind: str = "conversation"
    source_id: str | None = None
    confidence: float = Field(default=0.7, ge=0, le=1)


class StrategicMemoryItem(BaseModel):
    """A durable item of strategy, ambition, preference, or decision context."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"smem_{uuid4().hex[:12]}")
    type: StrategicMemoryType
    scope: StrategicMemoryScope = StrategicMemoryScope.PROJECT
    project: str | None = "default"
    repo_profile_id: str | None = None
    conversation_id: str | None = None
    content: str = Field(min_length=1)
    summary: str = ""
    evidence: list[StrategicMemoryEvidence] = Field(default_factory=list)
    confidence: float = Field(default=0.7, ge=0, le=1)
    importance: float = Field(default=0.6, ge=0, le=1)
    stability: StrategicMemoryStability = StrategicMemoryStability.MEDIUM_TERM
    source: StrategicMemorySource = StrategicMemorySource.CONVERSATION_INFERRED
    tags: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    archived_at: datetime | None = None

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        """Normalize tags for stable recall and display."""

        return list(dict.fromkeys(tag.strip().lower() for tag in value if tag.strip()))

    @property
    def searchable_text(self) -> str:
        """Return text used by lexical recall."""

        evidence_text = " ".join(item.content for item in self.evidence)
        return " ".join(
            [
                self.type.value,
                self.scope.value,
                self.content,
                self.summary,
                evidence_text,
                " ".join(self.tags),
            ]
        ).lower()


class StrategicMemoryConflict(BaseModel):
    """A simple detected tension between strategic memories."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"smem_conflict_{uuid4().hex[:12]}")
    existing_memory_id: str
    candidate_memory_id: str | None = None
    conflict_type: str = "semantic_tension"
    description: str
    severity: float = Field(default=0.5, ge=0, le=1)
    status: str = "open"
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    resolved_at: datetime | None = None


class StrategicMemoryExtractionResult(BaseModel):
    """Suggested strategic memory updates from a conversation turn."""

    model_config = ConfigDict(frozen=True)

    prompt: str
    items: list[StrategicMemoryItem] = Field(default_factory=list)
    conflicts: list[StrategicMemoryConflict] = Field(default_factory=list)
    sensitive_suggestions: list[str] = Field(default_factory=list)
    requires_explicit_save: bool = True
    rationale: str = ""


class StrategicMemoryRecall(BaseModel):
    """A recall event and the strategic memories selected for a turn."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"smem_recall_{uuid4().hex[:12]}")
    query: str = ""
    tags: list[str] = Field(default_factory=list)
    types: list[StrategicMemoryType] = Field(default_factory=list)
    scopes: list[StrategicMemoryScope] = Field(default_factory=list)
    memory_ids: list[str] = Field(default_factory=list)
    memories: list[StrategicMemoryItem] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("tags")
    @classmethod
    def normalize_recall_tags(cls, value: list[str]) -> list[str]:
        """Normalize recall tags."""

        return list(dict.fromkeys(tag.strip().lower() for tag in value if tag.strip()))
