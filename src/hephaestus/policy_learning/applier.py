"""Apply active decision quality profiles to optimizer inputs."""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from hephaestus.core.config import ObjectiveWeights, RiskLevel
from hephaestus.optimize.context_packer import ContextCandidate
from hephaestus.optimize.model_router import ModelRouteRequest
from hephaestus.optimize.token_firewall import TokenBudget
from hephaestus.policy_learning.profile_store import ProfileStore
from hephaestus.policy_learning.schemas import (
    AdjustmentOperation,
    DecisionArea,
    DecisionQualityProfile,
    ProfileAdjustment,
    ProfileApplicationResult,
    ProfileRule,
    ProfileStatus,
)


class ContextPackerProfileSettings(BaseModel):
    """Effective context packing knobs derived from active profiles."""

    model_config = ConfigDict(frozen=True)

    preserve_critical_context: bool = True
    failure_memory_importance_boost: float = Field(default=0.0, ge=0, le=1)
    compression_aggressiveness: float = Field(default=1.0, ge=0, le=1)


def profiles_for_execution(
    store: ProfileStore,
    profile_ids: Iterable[str] | None = None,
) -> list[DecisionQualityProfile]:
    """Load explicit profiles or the active profile set for an execution."""

    if profile_ids is None:
        return store.list_active_profiles()
    profiles: list[DecisionQualityProfile] = []
    for profile_id in profile_ids:
        profile = store.get_profile(profile_id)
        if profile is not None:
            profiles.append(profile)
    return profiles


def apply_model_router_profiles(
    request: ModelRouteRequest,
    profiles: Iterable[DecisionQualityProfile],
    *,
    run_id: str | None = None,
    trace_id: str | None = None,
    store: ProfileStore | None = None,
) -> tuple[ModelRouteRequest, list[ProfileApplicationResult]]:
    """Adjust model routing thresholds and model tag preferences."""

    adjusted = request
    applications: list[ProfileApplicationResult] = []
    for profile in _area_profiles(profiles, DecisionArea.MODEL_ROUTER):
        before = {
            "quality_threshold": adjusted.quality_threshold,
            "preferred_model_tags": sorted(adjusted.preferred_model_tags),
            "avoided_model_tags": sorted(adjusted.avoided_model_tags),
        }
        threshold = adjusted.quality_threshold
        preferred_tags = set(adjusted.preferred_model_tags)
        avoided_tags = set(adjusted.avoided_model_tags)
        applied_adjustments: list[ProfileAdjustment] = []
        for rule in profile.rules:
            threshold, rule_adjustments = _apply_quality_threshold_rule(threshold, rule)
            applied_adjustments.extend(rule_adjustments)
            preferred_tags.update(rule.prefer_model_tags)
            avoided_tags.update(rule.avoid_model_tags)
            applied_adjustments.extend(
                _model_tag_adjustments(rule, before_preferred=preferred_tags, before_avoided=avoided_tags)
            )
        adjusted = adjusted.model_copy(
            update={
                "quality_threshold": min(1.0, threshold),
                "preferred_model_tags": preferred_tags,
                "avoided_model_tags": avoided_tags,
            }
        )
        after = {
            "quality_threshold": adjusted.quality_threshold,
            "preferred_model_tags": sorted(adjusted.preferred_model_tags),
            "avoided_model_tags": sorted(adjusted.avoided_model_tags),
        }
        application = _application(
            profile,
            run_id=run_id,
            trace_id=trace_id,
            target="model_router",
            before=before,
            after=after,
            adjustments=applied_adjustments,
            effect_summary=_threshold_effect(before, after),
        )
        _record(store, application)
        applications.append(application)
    return adjusted, applications


def apply_context_packer_profiles(
    profiles: Iterable[DecisionQualityProfile],
    *,
    run_id: str | None = None,
    trace_id: str | None = None,
    store: ProfileStore | None = None,
) -> tuple[ContextPackerProfileSettings, list[ProfileApplicationResult]]:
    """Build effective context packing settings from profiles."""

    settings = ContextPackerProfileSettings()
    applications: list[ProfileApplicationResult] = []
    profile_list = list(profiles)
    for profile in [
        *_area_profiles(profile_list, DecisionArea.CONTEXT_PACKER),
        *_area_profiles(profile_list, DecisionArea.MEMORY_RETRIEVAL),
    ]:
        before = settings.model_dump()
        preserve_critical = settings.preserve_critical_context
        failure_boost = settings.failure_memory_importance_boost
        compression = settings.compression_aggressiveness
        applied_adjustments: list[ProfileAdjustment] = []
        for rule in profile.rules:
            for adjustment in rule.adjustments:
                if adjustment.target == "critical_context_policy":
                    preserve_critical = True
                    applied_adjustments.append(adjustment)
                elif adjustment.target == "failure_memory_importance":
                    failure_boost = min(
                        1.0,
                        failure_boost + _float_value(adjustment.value),
                    )
                    applied_adjustments.append(adjustment)
                elif adjustment.target == "compression_aggressiveness":
                    compression = max(
                        0.0,
                        compression - _float_value(adjustment.value),
                    )
                    applied_adjustments.append(adjustment)
        settings = ContextPackerProfileSettings(
            preserve_critical_context=preserve_critical,
            failure_memory_importance_boost=failure_boost,
            compression_aggressiveness=compression,
        )
        after = settings.model_dump()
        application = _application(
            profile,
            run_id=run_id,
            trace_id=trace_id,
            target="context_packer",
            before=before,
            after=after,
            adjustments=applied_adjustments,
            effect_summary=(
                "critical context treated as hard constraint; "
                f"failure memory boost {before['failure_memory_importance_boost']:.2f} "
                f"-> {after['failure_memory_importance_boost']:.2f}"
            ),
        )
        _record(store, application)
        applications.append(application)
    return settings, applications


def apply_token_firewall_profiles(
    budget: TokenBudget,
    profiles: Iterable[DecisionQualityProfile],
    *,
    run_id: str | None = None,
    trace_id: str | None = None,
    store: ProfileStore | None = None,
) -> tuple[TokenBudget, list[ProfileApplicationResult]]:
    """Adjust token firewall budget settings from profiles."""

    adjusted = budget
    applications: list[ProfileApplicationResult] = []
    for profile in _area_profiles(profiles, DecisionArea.TOKEN_FIREWALL):
        before = adjusted.model_dump()
        threshold = adjusted.quality_threshold
        applied_adjustments: list[ProfileAdjustment] = []
        for rule in profile.rules:
            threshold, rule_adjustments = _apply_quality_threshold_rule(threshold, rule)
            applied_adjustments.extend(rule_adjustments)
        adjusted = adjusted.model_copy(update={"quality_threshold": min(1.0, threshold)})
        after = adjusted.model_dump()
        application = _application(
            profile,
            run_id=run_id,
            trace_id=trace_id,
            target="token_firewall",
            before=before,
            after=after,
            adjustments=applied_adjustments,
            effect_summary=_threshold_effect(before, after),
        )
        _record(store, application)
        applications.append(application)
    return adjusted, applications


def apply_scheduler_profiles(
    weights: ObjectiveWeights,
    profiles: Iterable[DecisionQualityProfile],
    *,
    run_id: str | None = None,
    trace_id: str | None = None,
    store: ProfileStore | None = None,
) -> tuple[ObjectiveWeights, list[ProfileApplicationResult]]:
    """Adjust scheduler objective weights from profiles."""

    adjusted = weights
    applications: list[ProfileApplicationResult] = []
    profile_list = list(profiles)
    for profile in [
        *_area_profiles(profile_list, DecisionArea.SCHEDULER),
        *_area_profiles(profile_list, DecisionArea.OPTIMIZER),
    ]:
        before = adjusted.model_dump()
        updates: dict[str, float] = {}
        applied_adjustments: list[ProfileAdjustment] = []
        for rule in profile.rules:
            for adjustment in rule.adjustments:
                if adjustment.target not in {
                    "dependency_violation_penalty",
                    "risk_penalty",
                    "uncertainty_penalty",
                }:
                    continue
                current = float(getattr(adjusted, adjustment.target))
                updates[adjustment.target] = _apply_numeric(current, adjustment)
                applied_adjustments.append(adjustment)
        adjusted = adjusted.model_copy(update=updates)
        after = adjusted.model_dump()
        application = _application(
            profile,
            run_id=run_id,
            trace_id=trace_id,
            target="scheduler",
            before=before,
            after=after,
            adjustments=applied_adjustments,
            effect_summary=_weight_effect(before, after),
        )
        _record(store, application)
        applications.append(application)
    return adjusted, applications


def apply_safety_profiles(
    action: str,
    *,
    base_requires_approval: bool,
    risk_level: RiskLevel,
    profiles: Iterable[DecisionQualityProfile],
    run_id: str | None = None,
    trace_id: str | None = None,
    store: ProfileStore | None = None,
) -> tuple[bool, list[ProfileApplicationResult]]:
    """Apply safety profile approval gates to a proposed action."""

    requires_approval = base_requires_approval
    applications: list[ProfileApplicationResult] = []
    for profile in _area_profiles(profiles, DecisionArea.SAFETY):
        before = {
            "requires_approval": requires_approval,
            "risk_level": risk_level.value,
            "action": action,
        }
        applied_adjustments: list[ProfileAdjustment] = []
        for rule in profile.rules:
            if rule.require_approval and _looks_like_side_effect(action):
                requires_approval = True
            for adjustment in rule.adjustments:
                if adjustment.target in {
                    "approval_required_for_external_side_effects",
                    "unknown_shell_commands",
                }:
                    applied_adjustments.append(adjustment)
        after = {
            "requires_approval": requires_approval,
            "risk_level": risk_level.value,
            "action": action,
        }
        application = _application(
            profile,
            run_id=run_id,
            trace_id=trace_id,
            target="safety",
            before=before,
            after=after,
            adjustments=applied_adjustments,
            effect_summary=(
                "approval required"
                if requires_approval and not before["requires_approval"]
                else "safety approval requirement unchanged"
            ),
        )
        _record(store, application)
        applications.append(application)
    return requires_approval, applications


def apply_failure_memory_context_boost(
    candidates: list[ContextCandidate],
    settings: ContextPackerProfileSettings,
) -> list[ContextCandidate]:
    """Return candidates with failure memory importance boosted for packing."""

    if settings.failure_memory_importance_boost <= 0:
        return candidates
    adjusted: list[ContextCandidate] = []
    for candidate in candidates:
        if _is_failure_memory_context(candidate):
            adjusted.append(
                candidate.model_copy(
                    update={
                        "importance": min(
                            1.0,
                            candidate.importance
                            + settings.failure_memory_importance_boost,
                        )
                    }
                )
            )
        else:
            adjusted.append(candidate)
    return adjusted


def _area_profiles(
    profiles: Iterable[DecisionQualityProfile],
    area: DecisionArea,
) -> list[DecisionQualityProfile]:
    return [
        profile
        for profile in profiles
        if profile.decision_area == area and profile.status != ProfileStatus.ARCHIVED
    ]


def _apply_quality_threshold_rule(
    threshold: float,
    rule: ProfileRule,
) -> tuple[float, list[ProfileAdjustment]]:
    applied: list[ProfileAdjustment] = []
    adjusted = threshold
    for adjustment in rule.adjustments:
        if adjustment.target != "quality_threshold":
            continue
        adjusted = _apply_numeric(adjusted, adjustment)
        applied.append(adjustment)
    if rule.minimum_quality_score is not None and adjusted < rule.minimum_quality_score:
        adjusted = rule.minimum_quality_score
        applied.append(
            ProfileAdjustment(
                target="minimum_quality_score",
                operation=AdjustmentOperation.SET,
                value=rule.minimum_quality_score,
                rationale=rule.rationale,
            )
        )
    return adjusted, applied


def _model_tag_adjustments(
    rule: ProfileRule,
    *,
    before_preferred: set[str],
    before_avoided: set[str],
) -> list[ProfileAdjustment]:
    adjustments: list[ProfileAdjustment] = []
    if rule.prefer_model_tags and before_preferred:
        adjustments.append(
            ProfileAdjustment(
                target="preferred_model_tags",
                operation=AdjustmentOperation.PREFER,
                value=", ".join(rule.prefer_model_tags),
                rationale=rule.rationale,
            )
        )
    if rule.avoid_model_tags and before_avoided:
        adjustments.append(
            ProfileAdjustment(
                target="avoided_model_tags",
                operation=AdjustmentOperation.AVOID,
                value=", ".join(rule.avoid_model_tags),
                rationale=rule.rationale,
            )
        )
    return adjustments


def _apply_numeric(current: float, adjustment: ProfileAdjustment) -> float:
    value = _float_value(adjustment.value)
    if adjustment.operation == AdjustmentOperation.INCREASE:
        return current + value
    if adjustment.operation == AdjustmentOperation.DECREASE:
        return current - value
    if adjustment.operation == AdjustmentOperation.MULTIPLY:
        return current * value
    if adjustment.operation == AdjustmentOperation.SET:
        return value
    return current


def _application(
    profile: DecisionQualityProfile,
    *,
    run_id: str | None,
    trace_id: str | None,
    target: str,
    before: dict[str, Any],
    after: dict[str, Any],
    adjustments: list[ProfileAdjustment],
    effect_summary: str,
) -> ProfileApplicationResult:
    return ProfileApplicationResult(
        profile_id=profile.id,
        profile_name=profile.name,
        decision_area=profile.decision_area,
        run_id=run_id,
        trace_id=trace_id,
        target=target,
        applied=before != after or bool(adjustments),
        effect_summary=effect_summary,
        before=before,
        after=after,
        adjustments_applied=adjustments,
        notes=[profile.description] if profile.description else [],
    )


def _record(store: ProfileStore | None, application: ProfileApplicationResult) -> None:
    if store is not None:
        store.record_profile_application(application)


def _threshold_effect(before: dict[str, Any], after: dict[str, Any]) -> str:
    before_threshold = _safe_float(before.get("quality_threshold"))
    after_threshold = _safe_float(after.get("quality_threshold"))
    if before_threshold is not None and after_threshold is not None and before_threshold != after_threshold:
        return (
            "required_quality_threshold increased from "
            f"{before_threshold:.2f} to {after_threshold:.2f}"
        )
    return "quality threshold unchanged"


def _weight_effect(before: dict[str, Any], after: dict[str, Any]) -> str:
    changed = [
        f"{key} {float(before[key]):.2f} -> {float(after[key]):.2f}"
        for key in sorted(before)
        if key in after and isinstance(before[key], int | float) and before[key] != after[key]
    ]
    return "; ".join(changed) if changed else "scheduler weights unchanged"


def _float_value(value: object) -> float:
    if isinstance(value, bool) or value is None:
        return 0.0
    if isinstance(value, int | float):
        return float(value)
    if not isinstance(value, str):
        return 0.0
    try:
        return float(value)
    except ValueError:
        return 0.0


def _safe_float(value: object) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, int | float):
        return float(value)
    if not isinstance(value, str):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _looks_like_side_effect(action: str) -> bool:
    lowered = action.lower()
    markers = [
        "push",
        "publish",
        "deploy",
        "delete",
        "remove",
        "write",
        "external",
        "shell",
        "commit",
    ]
    return any(marker in lowered for marker in markers)


def _is_failure_memory_context(candidate: ContextCandidate) -> bool:
    metadata = candidate.metadata
    tags_value = metadata.get("tags", [])
    tags = {str(tag).lower() for tag in tags_value} if isinstance(tags_value, list) else set()
    memory_type = str(metadata.get("memory_type", "")).lower()
    return (
        candidate.id.lower().startswith("failure")
        or memory_type == "failure"
        or "failure" in tags
    )
