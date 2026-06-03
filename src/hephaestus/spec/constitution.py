"""Project constitution for deterministic planning decisions."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ConstitutionPrinciple(BaseModel):
    """One rule that constrains runtime planning."""

    name: str
    description: str


class Constitution(BaseModel):
    """A compact constitution inspired by spec-driven development workflows."""

    principles: list[ConstitutionPrinciple] = Field(default_factory=list)

    def as_constraints(self) -> list[str]:
        """Return principle descriptions as plain planning constraints."""

        return [principle.description for principle in self.principles]


DEFAULT_CONSTITUTION = Constitution(
    principles=[
        ConstitutionPrinciple(
            name="local-first",
            description="Prefer local, cheap, deterministic execution before paid services.",
        ),
        ConstitutionPrinciple(
            name="quality-preserving-cost",
            description="Reduce token and model cost only when required quality is preserved.",
        ),
        ConstitutionPrinciple(
            name="approval-for-risk",
            description="Require approval for writes, destructive commands, publishing, and pushes.",
        ),
        ConstitutionPrinciple(
            name="model-agnostic",
            description="Plan against capabilities instead of hardcoding one model provider.",
        ),
    ]
)
