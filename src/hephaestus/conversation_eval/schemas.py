"""Schemas for deterministic conversation benchmark evaluation."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, field_validator

from hephaestus.conversation.schemas import DeliberationMode


class BenchmarkMemoryContext(BaseModel):
    """Regular memory context seeded before a benchmark run."""

    model_config = ConfigDict(frozen=True)

    type: str = "project"
    content: str
    summary: str = ""
    tags: list[str] = Field(default_factory=list)
    importance: float = Field(default=0.75, ge=0, le=1)
    confidence: float = Field(default=0.8, ge=0, le=1)

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(tag.strip().lower() for tag in value if tag.strip()))


class BenchmarkStrategicMemoryContext(BaseModel):
    """Strategic memory context seeded before a benchmark run."""

    model_config = ConfigDict(frozen=True)

    type: str = "principle"
    content: str
    summary: str = ""
    tags: list[str] = Field(default_factory=list)
    importance: float = Field(default=0.82, ge=0, le=1)
    confidence: float = Field(default=0.82, ge=0, le=1)
    stability: str = "long_term"

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: list[str]) -> list[str]:
        return list(dict.fromkeys(tag.strip().lower() for tag in value if tag.strip()))


class ConversationBenchmarkFixture(BaseModel):
    """One deterministic benchmark case for conversation quality."""

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    prompt: str
    mode: DeliberationMode = DeliberationMode.BALANCED
    expected_rubric: str = "General Useful Discussion"
    quality_profile: str = "strategic"
    required_sections: list[str] = Field(default_factory=list)
    required_qualities: list[str] = Field(default_factory=list)
    anti_patterns: list[str] = Field(default_factory=list)
    memory_context: list[BenchmarkMemoryContext] = Field(default_factory=list)
    strategic_memory_context: list[BenchmarkStrategicMemoryContext] = Field(default_factory=list)
    repo_context_required: bool = False
    repo_path: str | None = None
    source_path: Path | None = Field(default=None, exclude=True)


class ConversationEvaluationCheck(BaseModel):
    """One deterministic response quality check."""

    model_config = ConfigDict(frozen=True)

    key: str
    label: str
    passed: bool
    evidence: str = ""


class ConversationEvaluationResult(BaseModel):
    """Result of evaluating one conversation benchmark response."""

    model_config = ConfigDict(frozen=True)

    benchmark_id: str
    title: str
    mode: DeliberationMode
    score: float = Field(ge=0, le=1)
    checks: list[ConversationEvaluationCheck] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    anti_patterns_detected: list[str] = Field(default_factory=list)
    provider_model: str = "local/deterministic"

    @property
    def passed_checks(self) -> list[ConversationEvaluationCheck]:
        return [check for check in self.checks if check.passed]

    @property
    def failed_checks(self) -> list[ConversationEvaluationCheck]:
        return [check for check in self.checks if not check.passed]
