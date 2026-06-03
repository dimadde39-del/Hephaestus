"""In-memory skill registry."""

from __future__ import annotations

import builtins

from hephaestus.skills.schemas import SkillDefinition


class InMemorySkillRegistry:
    def __init__(self) -> None:
        self._skills: dict[str, SkillDefinition] = {}

    def add(self, skill: SkillDefinition) -> SkillDefinition:
        self._skills[skill.name] = skill
        return skill

    def list(self) -> builtins.list[SkillDefinition]:
        return sorted(self._skills.values(), key=lambda skill: skill.name)

    def find_by_capability(self, capability: str) -> builtins.list[SkillDefinition]:
        return [skill for skill in self.list() if capability in skill.capabilities]
