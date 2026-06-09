"""Schemas for user-owned policy profiles and request evaluation."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

type PolicyValue = bool | int | float | str | None


class PolicyProfileType(StrEnum):
    """Built-in policy profile identifiers."""

    BALANCED = "balanced"
    DEVELOPER = "developer"
    RESEARCH = "research"
    LOCAL_POWER_USER = "local_power_user"
    STRICT = "strict"
    CUSTOM = "custom"


class PolicyDecisionType(StrEnum):
    """User-facing policy decision outcomes."""

    ALLOW = "allow"
    ALLOW_WITH_CONTEXT = "allow_with_context"
    ASK_CLARIFYING_QUESTION = "ask_clarifying_question"
    REQUIRE_APPROVAL = "require_approval"
    REFUSE_BRIEFLY = "refuse_briefly"
    BLOCK = "block"


class PolicyRiskCategory(StrEnum):
    """Deterministic risk and allowance categories."""

    BENIGN_CREATIVE = "benign_creative"
    BENIGN_DEVELOPMENT = "benign_development"
    BENIGN_RESEARCH = "benign_research"
    STRATEGY_DISCUSSION = "strategy_discussion"
    SENSITIVE_PERSONAL_CONTEXT = "sensitive_personal_context"
    LOCAL_FILE_OPERATION = "local_file_operation"
    LOCAL_COMMAND_EXECUTION = "local_command_execution"
    EXTERNAL_SIDE_EFFECT = "external_side_effect"
    DESTRUCTIVE_ACTION = "destructive_action"
    CREDENTIAL_OR_SECRET_EXPOSURE = "credential_or_secret_exposure"
    MALWARE_OR_ABUSE = "malware_or_abuse"
    VIOLENCE_OR_PHYSICAL_HARM = "violence_or_physical_harm"
    EXPLOITATION_OR_HARASSMENT = "exploitation_or_harassment"
    REGULATED_HIGH_RISK = "regulated_high_risk"


class PolicyRefusalStyle(StrEnum):
    """How boundaries should be communicated."""

    BRIEF_DIRECT = "brief_direct"
    EXPLAIN_BOUNDARY = "explain_boundary"
    SAFE_ALTERNATIVE = "safe_alternative"


class PolicyBoundary(BaseModel):
    """A transparent rule attached to a policy profile."""

    model_config = ConfigDict(frozen=True)

    category: PolicyRiskCategory
    decision: PolicyDecisionType
    description: str
    rationale: str = ""
    examples: list[str] = Field(default_factory=list)

    @field_validator("examples", mode="after")
    @classmethod
    def _normalize_examples(cls, values: list[str]) -> list[str]:
        return _normalize_text(values)


class PolicyOverride(BaseModel):
    """A custom profile override for one category or textual rule."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"policy_override_{uuid4().hex[:12]}")
    category: PolicyRiskCategory | None = None
    match_text: str = ""
    decision: PolicyDecisionType
    reason: str = ""


class PolicyProfile(BaseModel):
    """A configurable policy profile for conversation and future tool layers."""

    model_config = ConfigDict(frozen=True)

    id: str
    profile_type: PolicyProfileType
    name: str
    description: str
    recommended: bool = False
    refusal_style: PolicyRefusalStyle = PolicyRefusalStyle.BRIEF_DIRECT
    behavior_guidance: list[str] = Field(default_factory=list)
    benign_task_philosophy: str = ""
    boundaries: list[PolicyBoundary] = Field(default_factory=list)
    overrides: list[PolicyOverride] = Field(default_factory=list)
    custom_settings: dict[str, PolicyValue] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def boundary_by_category(self) -> dict[PolicyRiskCategory, PolicyBoundary]:
        """Return the last configured boundary for each category."""

        return {boundary.category: boundary for boundary in self.boundaries}

    def decision_for_category(
        self,
        category: PolicyRiskCategory,
    ) -> PolicyDecisionType | None:
        """Return the configured decision for a category, if present."""

        boundary = self.boundary_by_category.get(category)
        return boundary.decision if boundary is not None else None


class PolicyDecision(BaseModel):
    """Decision produced by the deterministic evaluator."""

    model_config = ConfigDict(frozen=True)

    decision_type: PolicyDecisionType
    primary_category: PolicyRiskCategory
    categories: list[PolicyRiskCategory] = Field(default_factory=list)
    requires_approval: bool = False
    confidence: float = Field(default=0.75, ge=0, le=1)
    reasons: list[str] = Field(default_factory=list)
    refusal_style: PolicyRefusalStyle = PolicyRefusalStyle.BRIEF_DIRECT
    response: str = ""

    @property
    def is_allowed(self) -> bool:
        """Whether the request should be answered directly."""

        return self.decision_type in {
            PolicyDecisionType.ALLOW,
            PolicyDecisionType.ALLOW_WITH_CONTEXT,
        }

    @property
    def is_blocking(self) -> bool:
        """Whether the request should not be fulfilled."""

        return self.decision_type in {
            PolicyDecisionType.BLOCK,
            PolicyDecisionType.REFUSE_BRIEFLY,
        }


class PolicyClassification(BaseModel):
    """Lexical classification before profile-specific evaluation."""

    model_config = ConfigDict(frozen=True)

    categories: list[PolicyRiskCategory] = Field(default_factory=list)
    evidence: dict[PolicyRiskCategory, list[str]] = Field(default_factory=dict)

    @property
    def primary_category(self) -> PolicyRiskCategory:
        """Return the highest-precedence category."""

        return self.categories[0] if self.categories else PolicyRiskCategory.BENIGN_RESEARCH


class PolicyEvaluation(BaseModel):
    """Persistable policy evaluation for one prompt."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"policy_eval_{uuid4().hex[:12]}")
    prompt: str
    profile_type: PolicyProfileType
    profile_name: str
    decision: PolicyDecision
    classification: PolicyClassification
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    model_refusal_detected: bool = False
    over_refusal_detected: bool = False
    moralizing_detected: bool = False
    notes: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PolicyTestCase(BaseModel):
    """Fixture schema for deterministic policy behavior benchmarks."""

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    prompt: str
    profile: PolicyProfileType = PolicyProfileType.DEVELOPER
    expected_decision: PolicyDecisionType
    expected_categories: list[PolicyRiskCategory] = Field(default_factory=list)
    forbidden_phrases: list[str] = Field(default_factory=list)
    max_refusal_words: int = Field(default=45, gt=0)
    source_path: Path | None = Field(default=None, exclude=True)


class PolicyBenchmarkResult(BaseModel):
    """Result for one policy fixture."""

    model_config = ConfigDict(frozen=True)

    case: PolicyTestCase
    evaluation: PolicyEvaluation
    passed: bool
    failures: list[str] = Field(default_factory=list)


def _normalize_text(values: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for value in values:
        item = value.strip()
        key = item.lower()
        if not item or key in seen:
            continue
        seen.add(key)
        normalized.append(item)
    return normalized
