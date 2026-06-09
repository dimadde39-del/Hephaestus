"""Built-in policy profiles for user-owned freedom."""

from __future__ import annotations

from hephaestus.policy.schemas import (
    PolicyBoundary,
    PolicyDecisionType,
    PolicyProfile,
    PolicyProfileType,
    PolicyRefusalStyle,
    PolicyRiskCategory,
)


def built_in_policy_profiles() -> list[PolicyProfile]:
    """Return all built-in policy profiles in display order."""

    return [
        developer_profile(),
        balanced_profile(),
        research_profile(),
        local_power_user_profile(),
        strict_profile(),
    ]


def built_in_policy_profile_map() -> dict[PolicyProfileType, PolicyProfile]:
    """Return built-in profiles keyed by profile type."""

    return {profile.profile_type: profile for profile in built_in_policy_profiles()}


def get_builtin_policy_profile(profile_type: PolicyProfileType | str) -> PolicyProfile | None:
    """Resolve a built-in profile by enum or value."""

    normalized = (
        profile_type if isinstance(profile_type, PolicyProfileType) else PolicyProfileType(profile_type)
    )
    if normalized == PolicyProfileType.CUSTOM:
        return None
    return built_in_policy_profile_map().get(normalized)


def default_policy_profile() -> PolicyProfile:
    """Return the safe unset default profile."""

    return balanced_profile()


def developer_profile() -> PolicyProfile:
    """Recommended policy profile for open-source builders and local development."""

    return PolicyProfile(
        id=PolicyProfileType.DEVELOPER.value,
        profile_type=PolicyProfileType.DEVELOPER,
        name="Developer",
        recommended=True,
        description=(
            "Recommended for Hephaestus power users: practical freedom for benign "
            "creative, development, research, and strategy work with clear approval "
            "gates for side effects."
        ),
        refusal_style=PolicyRefusalStyle.BRIEF_DIRECT,
        benign_task_philosophy=(
            "For benign creative, development, research, strategy, and user-owned "
            "local work, help directly. Do not refuse because a task is harsh, "
            "ambitious, edgy, direct, or non-corporate."
        ),
        behavior_guidance=[
            "Help directly with benign user-owned work.",
            "Avoid corporate-style moralizing and over-apology.",
            "Allow harsh critique, direct copy, and uncomfortable strategic risk discussion.",
            "Require approval for destructive local actions or external side effects.",
            "Block credential theft, malware, abuse evasion, targeted harassment, exploitation, and real-world harm.",
        ],
        boundaries=_base_boundaries(
            sensitive_decision=PolicyDecisionType.ALLOW_WITH_CONTEXT,
            regulated_decision=PolicyDecisionType.ALLOW_WITH_CONTEXT,
        ),
    )


def balanced_profile() -> PolicyProfile:
    """Default policy profile when the user has not chosen one."""

    return PolicyProfile(
        id=PolicyProfileType.BALANCED.value,
        profile_type=PolicyProfileType.BALANCED,
        name="Balanced",
        description=(
            "Default profile: permissive for normal creative, development, research, "
            "and strategy work while preserving visible approval gates."
        ),
        refusal_style=PolicyRefusalStyle.BRIEF_DIRECT,
        benign_task_philosophy=(
            "Assume benign creative, development, research, product, and strategy "
            "work is allowed unless the request clearly asks for harm or side effects."
        ),
        behavior_guidance=[
            "Help with normal user-owned work.",
            "Ask only when the request is truly ambiguous or high-impact.",
            "Keep refusals short and specific.",
        ],
        boundaries=_base_boundaries(
            sensitive_decision=PolicyDecisionType.ALLOW_WITH_CONTEXT,
            regulated_decision=PolicyDecisionType.ASK_CLARIFYING_QUESTION,
        ),
    )


def research_profile() -> PolicyProfile:
    """Profile for analysis, theory, and defensive security research."""

    boundaries = _base_boundaries(
        sensitive_decision=PolicyDecisionType.ALLOW_WITH_CONTEXT,
        regulated_decision=PolicyDecisionType.ALLOW_WITH_CONTEXT,
    )
    return PolicyProfile(
        id=PolicyProfileType.RESEARCH.value,
        profile_type=PolicyProfileType.RESEARCH,
        name="Research",
        description=(
            "More permissive for analysis, theory, defensive security, and architecture; "
            "still blocks operational abuse."
        ),
        refusal_style=PolicyRefusalStyle.EXPLAIN_BOUNDARY,
        benign_task_philosophy=(
            "Analysis and defensive research should be supported. Distinguish theory "
            "and explanation from operational abuse."
        ),
        behavior_guidance=[
            "Permit analysis, architecture, defensive security, and dual-use explanation.",
            "Separate analysis from execution when risk is meaningful.",
            "Block operational abuse and evasion.",
        ],
        boundaries=boundaries,
    )


def local_power_user_profile() -> PolicyProfile:
    """Profile for users operating in their own local environment."""

    return PolicyProfile(
        id=PolicyProfileType.LOCAL_POWER_USER.value,
        profile_type=PolicyProfileType.LOCAL_POWER_USER,
        name="Local Power User",
        description=(
            "Assumes the user owns their local environment and wants fewer clarifying "
            "questions for local development, with approval gates for destructive or "
            "external actions."
        ),
        refusal_style=PolicyRefusalStyle.BRIEF_DIRECT,
        benign_task_philosophy=(
            "Treat local development and local repo work as user-owned by default. "
            "Do not slow normal work with unnecessary permission theater."
        ),
        behavior_guidance=[
            "Assume local context is user-owned unless the prompt says otherwise.",
            "Avoid unnecessary clarifying questions for local dev tasks.",
            "Still require approval for destructive local actions and external side effects.",
        ],
        boundaries=_base_boundaries(
            sensitive_decision=PolicyDecisionType.ALLOW_WITH_CONTEXT,
            regulated_decision=PolicyDecisionType.ALLOW_WITH_CONTEXT,
        ),
    )


def strict_profile() -> PolicyProfile:
    """Conservative profile for demos, classrooms, and enterprise-like contexts."""

    return PolicyProfile(
        id=PolicyProfileType.STRICT.value,
        profile_type=PolicyProfileType.STRICT,
        name="Strict",
        description=(
            "Conservative profile for demos, classrooms, and enterprise-like contexts. "
            "It asks more questions around sensitive, regulated, and dual-use areas."
        ),
        refusal_style=PolicyRefusalStyle.EXPLAIN_BOUNDARY,
        benign_task_philosophy=(
            "Normal benign work is still allowed, but sensitive and dual-use prompts "
            "should be framed carefully."
        ),
        behavior_guidance=[
            "Allow clearly benign work.",
            "Ask clarifying questions for sensitive, regulated, or ambiguous dual-use work.",
            "Keep boundaries factual and short.",
        ],
        boundaries=_base_boundaries(
            sensitive_decision=PolicyDecisionType.ASK_CLARIFYING_QUESTION,
            regulated_decision=PolicyDecisionType.ASK_CLARIFYING_QUESTION,
        ),
    )


def _base_boundaries(
    *,
    sensitive_decision: PolicyDecisionType,
    regulated_decision: PolicyDecisionType,
) -> list[PolicyBoundary]:
    allow = PolicyDecisionType.ALLOW
    approval = PolicyDecisionType.REQUIRE_APPROVAL
    block = PolicyDecisionType.BLOCK
    return [
        PolicyBoundary(
            category=PolicyRiskCategory.BENIGN_CREATIVE,
            decision=allow,
            description="Creative and brand work is allowed.",
            examples=["README banner", "mascot prompt", "direct launch copy"],
        ),
        PolicyBoundary(
            category=PolicyRiskCategory.BENIGN_DEVELOPMENT,
            decision=allow,
            description="Normal local development and open-source configuration is allowed.",
            examples=["write code for a local repo", "configure an open-source tool"],
        ),
        PolicyBoundary(
            category=PolicyRiskCategory.BENIGN_RESEARCH,
            decision=allow,
            description="Benign research, explanation, and defensive security discussion is allowed.",
            examples=["explain SQL injection defensively", "phishing awareness training"],
        ),
        PolicyBoundary(
            category=PolicyRiskCategory.STRATEGY_DISCUSSION,
            decision=allow,
            description="Harsh critique, roadmap stress tests, and direct strategy are allowed.",
            examples=["be brutally honest", "stress-test this startup idea"],
        ),
        PolicyBoundary(
            category=PolicyRiskCategory.SENSITIVE_PERSONAL_CONTEXT,
            decision=sensitive_decision,
            description="Sensitive personal context should be handled with care, not moral theater.",
        ),
        PolicyBoundary(
            category=PolicyRiskCategory.LOCAL_FILE_OPERATION,
            decision=approval,
            description="Actual local file mutations require explicit approval before execution.",
        ),
        PolicyBoundary(
            category=PolicyRiskCategory.LOCAL_COMMAND_EXECUTION,
            decision=approval,
            description="Shell commands that change files or environment require approval.",
        ),
        PolicyBoundary(
            category=PolicyRiskCategory.EXTERNAL_SIDE_EFFECT,
            decision=approval,
            description="External messages, deploys, publishes, and pushes require approval.",
        ),
        PolicyBoundary(
            category=PolicyRiskCategory.DESTRUCTIVE_ACTION,
            decision=approval,
            description="Destructive local actions require explicit approval and safeguards.",
        ),
        PolicyBoundary(
            category=PolicyRiskCategory.CREDENTIAL_OR_SECRET_EXPOSURE,
            decision=block,
            description="Credential theft, secret exfiltration, and account compromise are blocked.",
        ),
        PolicyBoundary(
            category=PolicyRiskCategory.MALWARE_OR_ABUSE,
            decision=block,
            description="Malware, abuse automation, and evasion for abuse are blocked.",
        ),
        PolicyBoundary(
            category=PolicyRiskCategory.VIOLENCE_OR_PHYSICAL_HARM,
            decision=block,
            description="Real-world violence or physical harm is blocked.",
        ),
        PolicyBoundary(
            category=PolicyRiskCategory.EXPLOITATION_OR_HARASSMENT,
            decision=block,
            description="Exploitation, doxxing, and targeted harassment are blocked.",
        ),
        PolicyBoundary(
            category=PolicyRiskCategory.REGULATED_HIGH_RISK,
            decision=regulated_decision,
            description="Regulated high-risk domains need context and clear boundaries.",
        ),
    ]
