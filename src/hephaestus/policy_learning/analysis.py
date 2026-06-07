"""Analysis helpers for decision quality profiles."""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field

from hephaestus.policy_learning.schemas import (
    DecisionQualityProfile,
    ProfileApplicationResult,
    ProfileStatus,
)


class ProfileCount(BaseModel):
    """A counted profile label."""

    model_config = ConfigDict(frozen=True)

    label: str
    count: int = Field(ge=0)


class ProfileSummary(BaseModel):
    """Aggregate profile inventory summary."""

    model_config = ConfigDict(frozen=True)

    total_profiles: int = Field(ge=0)
    draft_count: int = Field(ge=0)
    active_count: int = Field(ge=0)
    archived_count: int = Field(ge=0)
    profiles_by_area: list[ProfileCount] = Field(default_factory=list)
    average_confidence: float = 0.0


class ProfileApplicationSummary(BaseModel):
    """Aggregate profile application summary."""

    model_config = ConfigDict(frozen=True)

    total_applications: int = Field(ge=0)
    applied_count: int = Field(ge=0)
    applications_by_area: list[ProfileCount] = Field(default_factory=list)


def summarize_profiles(
    profiles: Iterable[DecisionQualityProfile],
) -> ProfileSummary:
    """Summarize profile status and area counts."""

    profile_list = list(profiles)
    status_counts = Counter(profile.status for profile in profile_list)
    area_counts = Counter(profile.decision_area.value for profile in profile_list)
    return ProfileSummary(
        total_profiles=len(profile_list),
        draft_count=status_counts[ProfileStatus.DRAFT],
        active_count=status_counts[ProfileStatus.ACTIVE],
        archived_count=status_counts[ProfileStatus.ARCHIVED],
        profiles_by_area=_top_counts(area_counts),
        average_confidence=_average([profile.confidence for profile in profile_list]),
    )


def summarize_profile_applications(
    applications: Iterable[ProfileApplicationResult],
) -> ProfileApplicationSummary:
    """Summarize recorded profile applications."""

    application_list = list(applications)
    area_counts = Counter(application.decision_area.value for application in application_list)
    return ProfileApplicationSummary(
        total_applications=len(application_list),
        applied_count=sum(1 for application in application_list if application.applied),
        applications_by_area=_top_counts(area_counts),
    )


def _top_counts(counter: Counter[str]) -> list[ProfileCount]:
    return [ProfileCount(label=label, count=count) for label, count in counter.most_common()]


def _average(values: list[float]) -> float:
    if not values:
        return 0.0
    return sum(values) / len(values)
