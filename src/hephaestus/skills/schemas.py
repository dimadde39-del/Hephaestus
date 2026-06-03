"""Skill schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SkillDefinition(BaseModel):
    name: str
    description: str
    capabilities: set[str] = Field(default_factory=set)
    promoted_from_memory_ids: list[str] = Field(default_factory=list)
