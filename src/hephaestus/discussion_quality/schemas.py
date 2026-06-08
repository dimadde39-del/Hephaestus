"""Schemas for discussion quality rubrics and research planning."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field


class DiscussionType(StrEnum):
    """Discussion families with explicit quality rubrics."""

    IDEA_STRESS_TEST = "idea_stress_test"
    BUSINESS_STRATEGY = "business_strategy"
    PRODUCT_STRATEGY = "product_strategy"
    TECHNICAL_ARCHITECTURE = "technical_architecture"
    ROADMAP_DECISION = "roadmap_decision"
    RESEARCH_PLANNING = "research_planning"
    RISK_ANALYSIS = "risk_analysis"
    GENERAL = "general"


class RubricCheck(BaseModel):
    """One expected check in a discussion rubric."""

    model_config = ConfigDict(frozen=True)

    key: str
    label: str
    description: str = ""


class DiscussionRubric(BaseModel):
    """A named rubric for a discussion family."""

    model_config = ConfigDict(frozen=True)

    discussion_type: DiscussionType
    name: str
    expected_checks: list[RubricCheck] = Field(default_factory=list)

    @property
    def expected_keys(self) -> list[str]:
        """Return expected check keys in rubric order."""

        return [check.key for check in self.expected_checks]


class DiscussionQualityCheckResult(BaseModel):
    """Evaluation result for one rubric check."""

    model_config = ConfigDict(frozen=True)

    key: str
    label: str
    satisfied: bool
    evidence: str = ""


class DiscussionQualityEvaluation(BaseModel):
    """How well one discussion response satisfies its rubric."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"dq_{uuid4().hex[:12]}")
    discussion_type: DiscussionType
    rubric_name: str
    checks: list[DiscussionQualityCheckResult] = Field(default_factory=list)
    score: float = Field(default=0.0, ge=0, le=1)
    missing_checks: list[str] = Field(default_factory=list)
    summary: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ResearchPlan(BaseModel):
    """A plan for future research, without pretending research has been done."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"research_plan_{uuid4().hex[:12]}")
    question: str
    needs_verification: list[str] = Field(default_factory=list)
    likely_sources: list[str] = Field(default_factory=list)
    search_queries: list[str] = Field(default_factory=list)
    evidence_quality_expectations: list[str] = Field(default_factory=list)
    what_would_change_conclusion: list[str] = Field(default_factory=list)
    shallow_research_risks: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
