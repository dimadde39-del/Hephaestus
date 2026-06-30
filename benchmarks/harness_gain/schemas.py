"""Schemas shared by the harness-gain orchestrator, runners, and reports."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ArmId(StrEnum):
    BARE_ONE_SHOT = "bare_one_shot"
    BARE_TWO_STAGE = "bare_two_stage"
    MIMOCODE = "mimocode"
    HEPHAESTUS = "hephaestus"


class FailureCode(StrEnum):
    PROVIDER_AUTH_FAILURE = "PROVIDER_AUTH_FAILURE"
    PROVIDER_TIMEOUT = "PROVIDER_TIMEOUT"
    PROVIDER_COMPATIBILITY_FAILURE = "PROVIDER_COMPATIBILITY_FAILURE"
    FORMAT_FAILURE = "FORMAT_FAILURE"
    PLAN_FAILURE = "PLAN_FAILURE"
    MANIFEST_FAILURE = "MANIFEST_FAILURE"
    TOOL_FAILURE = "TOOL_FAILURE"
    PERMISSION_FAILURE = "PERMISSION_FAILURE"
    VALIDATION_FAILURE = "VALIDATION_FAILURE"
    HIDDEN_VALIDATION_FAILURE = "HIDDEN_VALIDATION_FAILURE"
    SCOPE_VIOLATION = "SCOPE_VIOLATION"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    PROCESS_TIMEOUT = "PROCESS_TIMEOUT"
    HARNESS_CRASH = "HARNESS_CRASH"


INFRASTRUCTURE_FAILURES = {
    FailureCode.PROVIDER_AUTH_FAILURE,
    FailureCode.PROVIDER_TIMEOUT,
    FailureCode.PROVIDER_COMPATIBILITY_FAILURE,
    FailureCode.PERMISSION_FAILURE,
    FailureCode.PROCESS_TIMEOUT,
    FailureCode.HARNESS_CRASH,
}


class CheckResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    category: str
    passed: bool
    weight: float = Field(ge=0)
    detail: str = ""


class ValidationResult(BaseModel):
    model_config = ConfigDict(extra="allow")

    passed: bool
    checks: list[CheckResult] = Field(default_factory=list)
    command: str = ""
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    duration_seconds: float = 0.0


class ProviderUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str = "deepseek-v4-flash"
    provider: str = "deepseek"
    logical_provider_calls: int = 0
    transport_attempts: int = 0
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    estimated_cost: float = 0.0
    repair_calls: int = 0
    protocol_mismatch: list[str] = Field(default_factory=list)


class RunnerResult(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    declared_success: bool = False
    failure_code: FailureCode | None = None
    failure_detail: str = ""
    usage: ProviderUsage = Field(default_factory=ProviderUsage)
    stdout: str = ""
    stderr: str = ""
    session_export: dict[str, Any] = Field(default_factory=dict)
    hidden_target: Path | None = None
    self_validation: ValidationResult | None = None


class RunRecord(BaseModel):
    model_config = ConfigDict(extra="allow")

    protocol_version: str
    phase: str
    run_id: str
    task_id: str
    arm_id: ArmId
    run_index: int
    fixture_sha256: str
    prompt_sha256: str
    model: str = "deepseek-v4-flash"
    provider: str = "deepseek"
    base_url: str = "https://api.deepseek.com"
    harness_version: str
    start_time: datetime
    end_time: datetime
    wall_time: float
    logical_provider_calls: int
    transport_attempts: int
    input_tokens: int
    cached_tokens: int
    output_tokens: int
    estimated_cost: float
    files_created: int
    files_modified: int
    files_deleted: int
    loc_added: int
    loc_deleted: int
    self_validation: bool
    hidden_validation: bool
    repair_calls: int
    human_intervention: int = 0
    scope_violations: int = 0
    declared_success: bool
    exact_pass: bool
    hidden_check_pass_rate: float
    functional_score: float
    requirement_score: float
    safety_score: float
    verifier_adjusted_score: float
    false_success: bool
    infrastructure_failure: bool
    protocol_mismatch: list[str] = Field(default_factory=list)
    final_status: str
    failure_code: FailureCode | None = None
    failure_detail: str = ""


class ScheduledRun(BaseModel):
    task_id: str
    arm_id: ArmId
    run_index: int

