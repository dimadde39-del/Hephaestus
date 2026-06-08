"""Typed schemas for repository intelligence."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

from hephaestus.core.config import PrivacyLevel
from hephaestus.spec.tasks import Task


class CommandRiskCategory(StrEnum):
    """Repo command safety categories used before any command is executed."""

    SAFE_READONLY = "safe_readonly"
    SAFE_VALIDATION = "safe_validation"
    MEDIUM_RISK = "medium_risk"
    HIGH_RISK = "high_risk"
    DESTRUCTIVE = "destructive"
    EXTERNAL_SIDE_EFFECT = "external_side_effect"


class RepoFileSignal(BaseModel):
    """A file-level signal discovered during read-only inspection."""

    model_config = ConfigDict(frozen=True)

    path: str
    signal_type: str
    detected_as: str
    confidence: float = Field(default=0.8, ge=0, le=1)
    notes: list[str] = Field(default_factory=list)


class ProjectStack(BaseModel):
    """High-level project stack inferred from repository signals."""

    model_config = ConfigDict(frozen=True)

    languages: list[str] = Field(default_factory=list)
    frameworks: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    primary_ecosystems: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)

    @field_validator("languages", "frameworks", "tools", "primary_ecosystems")
    @classmethod
    def deduplicate_ordered(cls, value: list[str]) -> list[str]:
        """Keep stack lists stable and duplicate-free."""

        return list(dict.fromkeys(value))


class PackageManagerInfo(BaseModel):
    """Detected package manager or build tool."""

    model_config = ConfigDict(frozen=True)

    name: str
    ecosystem: str
    manifest_path: str = ""
    lockfile_path: str = ""
    command_prefix: str = ""
    confidence: float = Field(default=0.8, ge=0, le=1)


class ScriptCommand(BaseModel):
    """A script or command discovered in repository metadata."""

    model_config = ConfigDict(frozen=True)

    name: str
    command: str
    source: str
    package_manager: str = ""
    raw_command: str = ""
    classification: CommandRiskCategory = CommandRiskCategory.MEDIUM_RISK
    reasons: list[str] = Field(default_factory=list)
    requires_approval: bool = False


class TestCommand(BaseModel):
    """A suggested validation command."""

    model_config = ConfigDict(frozen=True)

    command: str
    source: str
    framework: str = ""
    classification: CommandRiskCategory = CommandRiskCategory.SAFE_VALIDATION
    reasons: list[str] = Field(default_factory=list)
    requires_approval: bool = False


class CiProviderInfo(BaseModel):
    """Detected CI provider configuration."""

    model_config = ConfigDict(frozen=True)

    provider: str
    config_paths: list[str] = Field(default_factory=list)
    workflow_names: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.8, ge=0, le=1)


class RiskSignal(BaseModel):
    """A repo-level risk the agent should consider before acting."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"risk_{uuid4().hex[:10]}")
    level: CommandRiskCategory
    category: str
    summary: str
    evidence: list[str] = Field(default_factory=list)
    mitigation: str = ""


class ValidationPlan(BaseModel):
    """Ordered validation suggestions derived from repo signals."""

    model_config = ConfigDict(frozen=True)

    commands: list[TestCommand] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)

    @property
    def command_texts(self) -> list[str]:
        """Return plain command strings in suggested order."""

        return [command.command for command in self.commands]


class RepoTask(BaseModel):
    """Repo-aware task that can be converted into the existing optimizer Task schema."""

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    description: str
    priority: int = Field(ge=0, le=10)
    dependencies: list[str] = Field(default_factory=list)
    risk: float = Field(ge=0, le=1)
    expected_value: float = Field(ge=0, le=10)
    uncertainty: float = Field(default=0.25, ge=0, le=1)
    required_capabilities: list[str] = Field(default_factory=list)
    estimated_input_tokens: int = Field(ge=0)
    estimated_output_tokens: int = Field(ge=0)
    allowed_tools: list[str] = Field(default_factory=list)
    requires_approval: bool = False
    command: str = ""
    command_classification: CommandRiskCategory | None = None
    rationale: str = ""

    @field_validator("dependencies", "required_capabilities", "allowed_tools")
    @classmethod
    def deduplicate_ordered(cls, value: list[str]) -> list[str]:
        """Keep ordered list fields stable and duplicate-free."""

        return list(dict.fromkeys(value))

    def to_task(self) -> Task:
        """Convert to the optimizer's task schema."""

        metadata: dict[str, str] = {}
        if self.command:
            metadata["repo_command"] = self.command
        if self.command_classification is not None:
            metadata["command_classification"] = self.command_classification.value
        if self.rationale:
            metadata["rationale"] = self.rationale
        return Task(
            id=self.id,
            title=self.title,
            description=self.description,
            priority=self.priority,
            dependencies=self.dependencies,
            risk=self.risk,
            expected_value=self.expected_value,
            uncertainty=self.uncertainty,
            required_capabilities=set(self.required_capabilities),
            privacy_level=PrivacyLevel.PRIVATE,
            estimated_input_tokens=self.estimated_input_tokens,
            estimated_output_tokens=self.estimated_output_tokens,
            allowed_tools=self.allowed_tools,
            requires_approval=self.requires_approval,
            metadata=metadata,
        )


class RepoProfile(BaseModel):
    """Complete read-only profile of a local repository."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"repo_{uuid4().hex[:12]}")
    path: str
    name: str
    detected_languages: list[str] = Field(default_factory=list)
    detected_frameworks: list[str] = Field(default_factory=list)
    package_managers: list[PackageManagerInfo] = Field(default_factory=list)
    scripts: list[ScriptCommand] = Field(default_factory=list)
    test_commands: list[TestCommand] = Field(default_factory=list)
    build_commands: list[TestCommand] = Field(default_factory=list)
    lint_commands: list[TestCommand] = Field(default_factory=list)
    ci_providers: list[CiProviderInfo] = Field(default_factory=list)
    docker_detected: bool = False
    env_files_detected: list[str] = Field(default_factory=list)
    risk_signals: list[RiskSignal] = Field(default_factory=list)
    validation_plan: ValidationPlan = Field(default_factory=ValidationPlan)
    generated_tasks: list[RepoTask] = Field(default_factory=list)
    confidence: float = Field(default=0.5, ge=0, le=1)
    inspected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    file_signals: list[RepoFileSignal] = Field(default_factory=list)
    stack: ProjectStack = Field(default_factory=ProjectStack)

    @field_validator("detected_languages", "detected_frameworks", "env_files_detected")
    @classmethod
    def deduplicate_ordered(cls, value: list[str]) -> list[str]:
        """Keep profile summary lists stable and duplicate-free."""

        return list(dict.fromkeys(value))


class RepoInspectionReport(BaseModel):
    """A persisted inspection report plus compact summary text."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(default_factory=lambda: f"inspection_{uuid4().hex[:12]}")
    profile: RepoProfile
    summary: str
    detected_stack_summary: str = ""
    validation_summary: str = ""
    risk_summary: str = ""
    limitations: list[str] = Field(default_factory=list)
    inspected_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
