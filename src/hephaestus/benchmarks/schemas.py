"""Typed benchmark schemas."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from hephaestus.models import ModelProfile
from hephaestus.optimize.context_packer import ContextCandidate
from hephaestus.optimize.token_firewall import BudgetDecision, TokenBudget
from hephaestus.spec.tasks import Task


class BenchmarkCase(BaseModel):
    """A benchmark fixture that exercises optimizer behavior."""

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    description: str = ""
    goal: str = ""
    tasks: list[Task]
    model_profiles: list[ModelProfile] = Field(default_factory=list)
    context_candidates: list[ContextCandidate] = Field(default_factory=list)
    context_token_budget: int = Field(default=2_000, gt=0)
    token_budget: TokenBudget = Field(
        default_factory=lambda: TokenBudget(
            max_input_tokens=10_000,
            max_output_tokens=4_000,
            max_cost=0.25,
            quality_threshold=0.76,
        )
    )
    quality_threshold: float = Field(default=0.76, ge=0, le=1)
    quality_thresholds: dict[str, float] = Field(default_factory=dict)
    expected_constraints: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    source_path: Path | None = Field(default=None, exclude=True)


class RejectedModelSummary(BaseModel):
    """A model rejected during benchmark routing."""

    identifier: str
    reason: str


class ModelRouteSummary(BaseModel):
    """Routing proof for one scheduled task."""

    task_id: str
    selected_model: str
    selected_quality: float | None = Field(default=None, ge=0, le=1)
    required_quality_threshold: float = Field(ge=0, le=1)
    estimated_cost: float = Field(ge=0)
    rejected_models: list[RejectedModelSummary] = Field(default_factory=list)
    error: str = ""

    @property
    def quality_preserved(self) -> bool:
        return (
            self.selected_quality is not None
            and not self.error
            and self.selected_quality >= self.required_quality_threshold
        )


class SchedulerBenchmarkSummary(BaseModel):
    """Scheduler comparison metrics."""

    greedy_score: float
    annealing_score: float
    score_delta: float
    score_delta_percent: float
    greedy_dependency_violations: int = Field(ge=0)
    annealing_dependency_violations: int = Field(ge=0)
    best_scheduler: str
    best_score: float
    greedy_order: list[str] = Field(default_factory=list)
    annealing_order: list[str] = Field(default_factory=list)
    best_order: list[str] = Field(default_factory=list)


class ContextBenchmarkSummary(BaseModel):
    """Context packing proof metrics."""

    candidate_count: int = Field(ge=0)
    selected_count: int = Field(ge=0)
    excluded_count: int = Field(ge=0)
    tokens_before: int = Field(ge=0)
    tokens_after: int = Field(ge=0)
    token_savings_percent: float
    critical_items_included: bool
    selected_context_ids: list[str] = Field(default_factory=list)
    excluded_context: list[str] = Field(default_factory=list)


class BenchmarkResult(BaseModel):
    """Complete optimizer proof report for one benchmark case."""

    case: BenchmarkCase
    run_id: str | None = None
    scheduler: SchedulerBenchmarkSummary
    model_routes: list[ModelRouteSummary] = Field(default_factory=list)
    context: ContextBenchmarkSummary
    budget: BudgetDecision
    approval_required_count: int = Field(ge=0)
    estimated_input_tokens: int = Field(ge=0)
    estimated_output_tokens: int = Field(ge=0)
    estimated_cost: float = Field(ge=0)
    quality_preserved: bool
    summary: str
    decision_count: int = Field(default=0, ge=0)
    top_decision_type: str = ""
    top_decision_rationale: str = ""
    most_common_rejection_reason: str = ""
    token_savings_summary: str = ""
