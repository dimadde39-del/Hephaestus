"""Memory schemas."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator


class MemoryType(StrEnum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    PROJECT = "project"
    FAILURE = "failure"
    DECISION = "decision"
    PROCEDURAL = "procedural"


class MemoryItem(BaseModel):
    """A durable memory record shape; Phase 1 stores it in memory."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"mem-{uuid4().hex[:8]}")
    type: MemoryType
    content: str
    summary: str = ""
    tags: list[str] = Field(default_factory=list)
    project: str = "default"
    confidence: float = Field(default=0.7, ge=0, le=1)
    importance: float = Field(default=0.5, ge=0, le=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    last_verified_at: datetime | None = None
    source: str = "user"

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(tag.strip().lower() for tag in value if tag.strip()))

    @property
    def searchable_text(self) -> str:
        return " ".join([self.content, self.summary, " ".join(self.tags)]).lower()
