"""Runtime configuration and shared enums."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class PrivacyLevel(StrEnum):
    """Privacy tiers used by tasks, memories, tools, and model profiles."""

    PUBLIC = "public"
    INTERNAL = "internal"
    PRIVATE = "private"
    SECRET = "secret"


class RiskLevel(StrEnum):
    """Risk tiers for tool and action policy decisions."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ObjectiveWeights(BaseModel):
    """Weights for the central optimization objective."""

    expected_value: float = 2.0
    priority: float = 1.4
    confidence: float = 1.1
    token_cost: float = 0.0008
    risk_penalty: float = 3.0
    uncertainty_penalty: float = 1.8
    dependency_violation_penalty: float = 25.0


class RuntimeConfig(BaseModel):
    """Local-first runtime settings."""

    input_token_budget: int = Field(default=12_000, gt=0)
    output_token_budget: int = Field(default=4_000, gt=0)
    max_estimated_cost: float = Field(default=1.0, ge=0)
    required_quality: float = Field(default=0.72, ge=0, le=1)
    objective_weights: ObjectiveWeights = Field(default_factory=ObjectiveWeights)


DEFAULT_CONFIG = RuntimeConfig()
