"""Named response quality targets for conversation benchmarks."""

from __future__ import annotations

QUALITY_PROFILES: dict[str, tuple[str, ...]] = {
    "strategic": (
        "position_or_recommendation",
        "assumptions",
        "risks",
        "missing_information",
        "next_move",
        "no_fake_certainty",
    ),
    "research": (
        "assumptions",
        "missing_information",
        "next_move",
        "research_planning_boundary",
        "no_fake_certainty",
    ),
    "architecture": (
        "position_or_recommendation",
        "assumptions",
        "risks",
        "missing_information",
        "next_move",
        "no_fake_certainty",
    ),
    "stress_test": (
        "position_or_recommendation",
        "assumptions",
        "risks",
        "missing_information",
        "next_move",
        "no_blind_agreement",
        "no_fake_certainty",
    ),
    "repo_question": (
        "position_or_recommendation",
        "assumptions",
        "risks",
        "missing_information",
        "next_move",
        "repo_context_used",
        "no_fake_certainty",
    ),
}


def checks_for_quality_profile(profile: str) -> list[str]:
    """Return expected check keys for a named quality target."""

    return list(QUALITY_PROFILES.get(profile, QUALITY_PROFILES["strategic"]))
