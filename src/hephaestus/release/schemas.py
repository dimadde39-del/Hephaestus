"""Typed schemas for repo-aware release planning demos."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from hephaestus.benchmarks.schemas import BenchmarkResult
from hephaestus.repo.schemas import CommandRiskCategory, RepoProfile, RepoTask, ValidationPlan
from hephaestus.validation.schemas import ReleaseValidationSummary


class ReleaseRecommendationStatus(StrEnum):
    """Coarse recommendation states for a release planning run."""

    READY = "ready"
    MOSTLY_READY = "mostly_ready"
    NEEDS_VALIDATION = "needs_validation"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class ReleasePlanningRequest(BaseModel):
    """Input for a repo-aware release planning run."""

    model_config = ConfigDict(frozen=True)

    path: str = "."
    goal: str = "Prepare this repository for a safe public release."
    profile_id: str | None = None
    use_latest_profile: bool = False
    preference: str = "balanced"
    pareto: bool = False
    qubo: bool = False
    evaluate: bool = False
    with_validation: bool = False
    validation_yes: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ReleaseReadinessSignal(BaseModel):
    """One deterministic input to the release readiness score."""

    model_config = ConfigDict(frozen=True)

    id: str
    label: str
    present: bool
    weight: int = Field(ge=0)
    score: int = Field(ge=0)
    rationale: str
    evidence: list[str] = Field(default_factory=list)

    @field_validator("evidence")
    @classmethod
    def deduplicate_evidence(cls, value: list[str]) -> list[str]:
        """Keep evidence stable and duplicate-free."""

        return list(dict.fromkeys(item for item in value if item))


class ReleaseRisk(BaseModel):
    """A release-specific risk derived from repo intelligence and planning evidence."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"release_risk_{uuid4().hex[:10]}")
    level: CommandRiskCategory
    category: str
    summary: str
    evidence: list[str] = Field(default_factory=list)
    mitigation: str = ""
    requires_approval: bool = False


class ReleaseTaskPlan(BaseModel):
    """Compact release task plan derived from generated repo tasks and optimizer output."""

    model_config = ConfigDict(frozen=True)

    repo_profile_id: str
    generated_task_ids: list[str] = Field(default_factory=list)
    optimized_task_order: list[str] = Field(default_factory=list)
    approval_task_ids: list[str] = Field(default_factory=list)
    validation_commands: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ReleaseRecommendation(BaseModel):
    """Human-readable release planning recommendation."""

    model_config = ConfigDict(frozen=True)

    status: ReleaseRecommendationStatus
    summary: str
    why: list[str] = Field(default_factory=list)
    next_steps: list[str] = Field(default_factory=list)
    risks: list[ReleaseRisk] = Field(default_factory=list)


class ReleasePlanningResult(BaseModel):
    """Persisted result of the repo-aware release planning demo flow."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"release_{uuid4().hex[:12]}")
    repo_profile_id: str
    goal: str
    generated_tasks: list[RepoTask]
    validation_plan: ValidationPlan
    risk_summary: str
    optimizer_run_id: str
    pareto_frontier_ids: list[str] = Field(default_factory=list)
    qubo_problem_ids: list[str] = Field(default_factory=list)
    decision_trace_ids: list[str] = Field(default_factory=list)
    outcome_ids: list[str] = Field(default_factory=list)
    learning_signal_ids: list[str] = Field(default_factory=list)
    validation_result_id: str | None = None
    validation_summary: ReleaseValidationSummary | None = None
    evidence_mode: str = "simulated_outcome_evaluation"
    readiness_score: int = Field(ge=0, le=100)
    recommendation: ReleaseRecommendation
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    readiness_signals: list[ReleaseReadinessSignal] = Field(default_factory=list)
    task_plan: ReleaseTaskPlan | None = None


class ReleaseDemoRun(BaseModel):
    """Full in-memory result returned by the release planning orchestrator."""

    model_config = ConfigDict(frozen=True)

    request: ReleasePlanningRequest
    repo_profile: RepoProfile
    result: ReleasePlanningResult
    benchmark_result: BenchmarkResult
