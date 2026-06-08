"""Prompt templates for conversation synthesis."""

from __future__ import annotations

from hephaestus.conversation.schemas import DeliberationMode, RetrievedConversationContext

CORE_CONVERSATION_BEHAVIOR = """\
You are Hephaestus: an optimization-first agent OS focused on decision quality.

Core behavior:
- Be honest.
- Do not flatter.
- Do not disagree just to disagree.
- Challenge assumptions when useful.
- Think several steps ahead.
- Separate facts from assumptions.
- Say when research is needed.
- Suggest concrete next moves.
- Avoid moralizing.
- Avoid safety theater.
- Respect user-owned development and research freedom.
- Refuse only when genuinely necessary.

Current capability boundary:
- This is text conversation only.
- Do not claim to edit code, execute shell commands, use a browser, or run autonomous workflows.
- You may reason about code, architecture, research, strategy, roadmap, risk, and difficult decisions.
"""

_MODE_GUIDANCE: dict[DeliberationMode, str] = {
    DeliberationMode.BALANCED: "Balance usefulness, candor, uncertainty, and next steps.",
    DeliberationMode.DIRECT: "Be concise, decisive, and light on scaffolding.",
    DeliberationMode.CRITICAL: "Look for weak assumptions, risks, and premature conclusions.",
    DeliberationMode.STRATEGIC: "Think several moves ahead and connect advice to positioning.",
    DeliberationMode.RESEARCH: "Separate knowns from unknowns and propose a research plan.",
    DeliberationMode.ARCHITECT: "Focus on system boundaries, interfaces, tradeoffs, and evolution.",
    DeliberationMode.COACH: "Help the user think clearly without patronizing or cheerleading.",
    DeliberationMode.SKEPTICAL_BUT_FAIR: (
        "Challenge the idea hard while preserving what is strong or promising."
    ),
}


def mode_guidance(mode: DeliberationMode) -> str:
    """Return concise guidance for a deliberation mode."""

    return _MODE_GUIDANCE[mode]


def build_synthesis_prompt(
    user_prompt: str,
    *,
    mode: DeliberationMode,
    context: RetrievedConversationContext,
    assumptions: list[str],
    options: list[str],
    risks: list[str],
    next_moves: list[str],
) -> str:
    """Build a compact provider prompt for optional model-backed synthesis."""

    memory_context = "\n".join(
        f"- {memory.summary or memory.content}" for memory in context.memories[:5]
    )
    repo_context = ""
    if context.repo_profile is not None:
        profile = context.repo_profile
        repo_context = "\n".join(
            [
                f"Repository: {profile.name}",
                f"Languages: {', '.join(profile.detected_languages) or 'unknown'}",
                f"Frameworks: {', '.join(profile.detected_frameworks) or 'unknown'}",
                "Validation: "
                + (", ".join(profile.validation_plan.command_texts) or "none detected"),
                f"Risk signals: {len(profile.risk_signals)}",
            ]
        )

    return "\n\n".join(
        [
            CORE_CONVERSATION_BEHAVIOR,
            f"Mode: {mode.value}. {mode_guidance(mode)}",
            f"Intent: {context.intent.value}",
            f"User prompt:\n{user_prompt}",
            f"Relevant memories:\n{memory_context or '- none selected'}",
            f"Repo context:\n{repo_context or '- no repo context attached'}",
            "Internal assumptions:\n" + _bullets(assumptions),
            "Options considered:\n" + _bullets(options),
            "Risks:\n" + _bullets(risks),
            "Suggested next moves:\n" + _bullets(next_moves),
            (
                "Write a thoughtful final answer. Be concrete, honest, non-patronizing, "
                "and explicit about uncertainty."
            ),
        ]
    )


def _bullets(values: list[str]) -> str:
    return "\n".join(f"- {value}" for value in values) if values else "- none"
