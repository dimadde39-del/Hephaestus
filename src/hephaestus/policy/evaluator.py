"""Policy profile evaluator and concise boundary rendering."""

from __future__ import annotations

from hephaestus.policy.classifier import classify_policy_request
from hephaestus.policy.profiles import default_policy_profile, get_builtin_policy_profile
from hephaestus.policy.schemas import (
    PolicyBenchmarkResult,
    PolicyClassification,
    PolicyDecision,
    PolicyDecisionType,
    PolicyEvaluation,
    PolicyProfile,
    PolicyProfileType,
    PolicyRefusalStyle,
    PolicyRiskCategory,
    PolicyTestCase,
)

_BLOCKING_CATEGORIES = {
    PolicyRiskCategory.CREDENTIAL_OR_SECRET_EXPOSURE,
    PolicyRiskCategory.MALWARE_OR_ABUSE,
    PolicyRiskCategory.VIOLENCE_OR_PHYSICAL_HARM,
    PolicyRiskCategory.EXPLOITATION_OR_HARASSMENT,
}

_APPROVAL_CATEGORIES = {
    PolicyRiskCategory.LOCAL_FILE_OPERATION,
    PolicyRiskCategory.LOCAL_COMMAND_EXECUTION,
    PolicyRiskCategory.EXTERNAL_SIDE_EFFECT,
    PolicyRiskCategory.DESTRUCTIVE_ACTION,
}


def evaluate_policy_request(
    prompt: str,
    *,
    profile: PolicyProfile | PolicyProfileType | str | None = None,
) -> PolicyEvaluation:
    """Evaluate a prompt against a policy profile."""

    resolved_profile = _resolve_profile(profile)
    classification = classify_policy_request(prompt)
    decision = _decision_for_classification(classification, resolved_profile)
    return PolicyEvaluation(
        prompt=prompt,
        profile_type=resolved_profile.profile_type,
        profile_name=resolved_profile.name,
        decision=decision,
        classification=classification,
    )


def render_policy_response(evaluation: PolicyEvaluation) -> str:
    """Return a concise local policy response for non-allow decisions."""

    decision = evaluation.decision
    if decision.response:
        return decision.response
    if decision.decision_type == PolicyDecisionType.REQUIRE_APPROVAL:
        return (
            "That needs explicit approval because it has local or external side effects. "
            "I can discuss the plan and risks, but I will not execute it here."
        )
    if decision.decision_type == PolicyDecisionType.ASK_CLARIFYING_QUESTION:
        return (
            "I need the user-owned context before going further. Is this for defensive, "
            "authorized, or personal-use work?"
        )
    if decision.is_blocking:
        return (
            "I cannot help with credential theft, malware, abuse, targeted harassment, "
            "exploitation, or real-world harm."
        )
    return "Allowed. I can help directly."


def evaluate_policy_test_case(case: PolicyTestCase) -> PolicyBenchmarkResult:
    """Evaluate a policy benchmark fixture."""

    evaluation = evaluate_policy_request(case.prompt, profile=case.profile)
    failures: list[str] = []
    decision = evaluation.decision
    if decision.decision_type != case.expected_decision:
        failures.append(
            f"expected {case.expected_decision.value}, got {decision.decision_type.value}"
        )
    categories = set(decision.categories)
    for category in case.expected_categories:
        if category not in categories:
            failures.append(f"missing category {category.value}")
    response = render_policy_response(evaluation)
    lowered = response.lower()
    for phrase in case.forbidden_phrases:
        if phrase.lower() in lowered:
            failures.append(f"forbidden phrase present: {phrase}")
    if decision.is_blocking or decision.requires_approval:
        word_count = len(response.split())
        if word_count > case.max_refusal_words:
            failures.append(f"boundary response too long: {word_count} words")
    return PolicyBenchmarkResult(
        case=case,
        evaluation=evaluation,
        passed=not failures,
        failures=failures,
    )


def policy_prompt_guidance(evaluation: PolicyEvaluation) -> str:
    """Build prompt text describing active policy behavior."""

    decision = evaluation.decision
    lines = [
        "Active policy profile:",
        f"- Name: {evaluation.profile_name} ({evaluation.profile_type.value})",
        f"- Decision: {decision.decision_type.value}",
        f"- Primary category: {decision.primary_category.value}",
        f"- Refusal style: {decision.refusal_style.value}",
        "- Philosophy: for benign creative, development, research, strategy, and user-owned local work, help directly.",
        "- Do not moralize, over-apologize, or refuse because a task is harsh, ambitious, edgy, direct, or non-corporate.",
        "- Refuse only when the request asks for genuinely harmful action.",
    ]
    if decision.requires_approval:
        lines.append("- This request may be discussed, but execution requires explicit approval.")
    if decision.is_blocking:
        lines.append("- This request crosses a blocked boundary; keep the refusal brief.")
    elif decision.is_allowed:
        lines.append("- This request is allowed; do not refuse or add safety theater.")
    return "\n".join(lines)


def _resolve_profile(
    profile: PolicyProfile | PolicyProfileType | str | None,
) -> PolicyProfile:
    if profile is None:
        return default_policy_profile()
    if isinstance(profile, PolicyProfile):
        return profile
    resolved = get_builtin_policy_profile(profile)
    if resolved is None:
        return default_policy_profile()
    return resolved


def _decision_for_classification(
    classification: PolicyClassification,
    profile: PolicyProfile,
) -> PolicyDecision:
    primary = classification.primary_category
    categories = classification.categories
    category_set = set(categories)
    reasons = _reasons(classification)

    blocking = category_set & _BLOCKING_CATEGORIES
    if blocking:
        category = _first_by_order(categories, blocking)
        return PolicyDecision(
            decision_type=PolicyDecisionType.BLOCK,
            primary_category=category,
            categories=categories,
            confidence=0.92,
            reasons=reasons,
            refusal_style=profile.refusal_style,
            response=_blocking_response(profile.refusal_style),
        )

    approval = category_set & _APPROVAL_CATEGORIES
    if approval:
        category = _first_by_order(categories, approval)
        return PolicyDecision(
            decision_type=PolicyDecisionType.REQUIRE_APPROVAL,
            primary_category=category,
            categories=categories,
            requires_approval=True,
            confidence=0.88,
            reasons=reasons,
            refusal_style=profile.refusal_style,
            response=_approval_response(category),
        )

    configured_decision = profile.decision_for_category(primary)
    decision_type = configured_decision or PolicyDecisionType.ALLOW
    if decision_type == PolicyDecisionType.ASK_CLARIFYING_QUESTION:
        return PolicyDecision(
            decision_type=decision_type,
            primary_category=primary,
            categories=categories,
            confidence=0.72,
            reasons=reasons,
            refusal_style=profile.refusal_style,
            response=(
                "I need the user-owned context before going further. Is this for "
                "authorized, defensive, or personal-use work?"
            ),
        )
    if decision_type == PolicyDecisionType.ALLOW_WITH_CONTEXT:
        return PolicyDecision(
            decision_type=decision_type,
            primary_category=primary,
            categories=categories,
            confidence=0.8,
            reasons=reasons,
            refusal_style=profile.refusal_style,
        )
    return PolicyDecision(
        decision_type=PolicyDecisionType.ALLOW,
        primary_category=primary,
        categories=categories,
        confidence=0.84,
        reasons=reasons,
        refusal_style=profile.refusal_style,
    )


def _first_by_order(
    ordered_categories: list[PolicyRiskCategory],
    candidates: set[PolicyRiskCategory],
) -> PolicyRiskCategory:
    for category in ordered_categories:
        if category in candidates:
            return category
    return ordered_categories[0]


def _reasons(classification: PolicyClassification) -> list[str]:
    reasons: list[str] = []
    for category in classification.categories:
        evidence = classification.evidence.get(category, [])
        if evidence:
            reasons.append(f"{category.value}: {', '.join(evidence[:3])}")
        else:
            reasons.append(category.value)
    return reasons


def _approval_response(category: PolicyRiskCategory) -> str:
    if category == PolicyRiskCategory.EXTERNAL_SIDE_EFFECT:
        return (
            "That needs explicit approval because it affects something outside the local "
            "conversation. I can discuss the plan and risks, but I will not send, push, publish, or deploy here."
        )
    if category == PolicyRiskCategory.DESTRUCTIVE_ACTION:
        return (
            "That needs explicit approval because it is destructive. I can discuss the "
            "safe plan and rollback checks, but I will not execute it here."
        )
    return (
        "That needs explicit approval because it changes local files, commands, or "
        "environment state. I can discuss the plan and risks, but I will not execute it here."
    )


def _blocking_response(style: PolicyRefusalStyle) -> str:
    if style == PolicyRefusalStyle.SAFE_ALTERNATIVE:
        return (
            "I cannot help with credential theft, malware, abuse, targeted harassment, "
            "exploitation, or real-world harm. I can help with defensive analysis."
        )
    if style == PolicyRefusalStyle.EXPLAIN_BOUNDARY:
        return (
            "I cannot help with credential theft, malware, abuse, targeted harassment, "
            "exploitation, or real-world harm."
        )
    return "I cannot help with credential theft, malware, abuse, exploitation, harassment, or real-world harm."
