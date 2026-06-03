"""Task schema and deterministic task generation."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from hephaestus.core.config import PrivacyLevel


class Task(BaseModel):
    """A typed unit of work for the optimizer and runtime."""

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    description: str
    priority: int = Field(ge=0, le=10)
    dependencies: list[str] = Field(default_factory=list)
    risk: float = Field(ge=0, le=1)
    expected_value: float = Field(ge=0, le=10)
    uncertainty: float = Field(ge=0, le=1)
    required_capabilities: set[str] = Field(default_factory=set)
    privacy_level: PrivacyLevel = PrivacyLevel.INTERNAL
    estimated_input_tokens: int = Field(ge=0)
    estimated_output_tokens: int = Field(ge=0)
    allowed_tools: list[str] = Field(default_factory=list)
    requires_approval: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("dependencies", "allowed_tools")
    @classmethod
    def deduplicate_ordered(cls, value: list[str]) -> list[str]:
        """Keep stable order while preventing duplicate dependency/tool names."""

        return list(dict.fromkeys(value))

    @property
    def estimated_total_tokens(self) -> int:
        return self.estimated_input_tokens + self.estimated_output_tokens


def generate_initial_tasks(goal_spec: Any) -> list[Task]:
    """Create rule-based initial tasks for a goal spec."""

    title = getattr(goal_spec, "title", "").lower()
    if "release" in title:
        return _release_readiness_tasks()
    return _generic_tasks()


def _release_readiness_tasks() -> list[Task]:
    return [
        Task(
            id="inspect-repository",
            title="Inspect repository",
            description="Map files, git status, project metadata, and current branch state.",
            priority=9,
            dependencies=[],
            risk=0.05,
            expected_value=8.0,
            uncertainty=0.2,
            required_capabilities={"repository-inspection"},
            estimated_input_tokens=800,
            estimated_output_tokens=300,
            allowed_tools=["filesystem", "git"],
        ),
        Task(
            id="detect-package-manager",
            title="Detect package manager",
            description="Identify Python, Node, or other package managers and their scripts.",
            priority=8,
            dependencies=["inspect-repository"],
            risk=0.05,
            expected_value=7.0,
            uncertainty=0.2,
            required_capabilities={"repository-inspection"},
            estimated_input_tokens=650,
            estimated_output_tokens=250,
            allowed_tools=["filesystem"],
        ),
        Task(
            id="inspect-scripts",
            title="Inspect validation scripts",
            description="Locate test, lint, format, build, and release commands.",
            priority=8,
            dependencies=["detect-package-manager"],
            risk=0.08,
            expected_value=7.5,
            uncertainty=0.25,
            required_capabilities={"repository-inspection", "planning"},
            estimated_input_tokens=900,
            estimated_output_tokens=350,
            allowed_tools=["filesystem"],
        ),
        Task(
            id="run-validation",
            title="Run validation",
            description="Run the safest available validation commands and capture results.",
            priority=9,
            dependencies=["inspect-scripts"],
            risk=0.18,
            expected_value=9.0,
            uncertainty=0.35,
            required_capabilities={"shell", "testing"},
            estimated_input_tokens=1_200,
            estimated_output_tokens=700,
            allowed_tools=["shell"],
        ),
        Task(
            id="summarize-release-readiness",
            title="Summarize release readiness",
            description="Explain validation results, open risks, and recommended release actions.",
            priority=7,
            dependencies=["run-validation"],
            risk=0.08,
            expected_value=8.5,
            uncertainty=0.2,
            required_capabilities={"analysis", "writing"},
            estimated_input_tokens=1_000,
            estimated_output_tokens=800,
            allowed_tools=[],
        ),
        Task(
            id="approval-before-commit",
            title="Ask approval before commit",
            description="Gate any commit, push, or publish action behind explicit approval.",
            priority=10,
            dependencies=["summarize-release-readiness"],
            risk=0.65,
            expected_value=6.0,
            uncertainty=0.15,
            required_capabilities={"git", "safety"},
            estimated_input_tokens=300,
            estimated_output_tokens=200,
            allowed_tools=["git"],
            requires_approval=True,
        ),
    ]


def _generic_tasks() -> list[Task]:
    return [
        Task(
            id="understand-goal",
            title="Understand goal",
            description="Normalize the user request into constraints and success criteria.",
            priority=8,
            dependencies=[],
            risk=0.03,
            expected_value=7.0,
            uncertainty=0.25,
            required_capabilities={"analysis"},
            estimated_input_tokens=500,
            estimated_output_tokens=250,
        ),
        Task(
            id="plan-work",
            title="Plan work",
            description="Build a dependency-aware task graph and identify validation gates.",
            priority=7,
            dependencies=["understand-goal"],
            risk=0.05,
            expected_value=7.5,
            uncertainty=0.3,
            required_capabilities={"planning"},
            estimated_input_tokens=650,
            estimated_output_tokens=300,
        ),
        Task(
            id="approval-check",
            title="Approval check",
            description="Require approval before any write, publish, or external send action.",
            priority=9,
            dependencies=["plan-work"],
            risk=0.4,
            expected_value=5.0,
            uncertainty=0.1,
            required_capabilities={"safety"},
            estimated_input_tokens=250,
            estimated_output_tokens=150,
            requires_approval=True,
        ),
    ]
