"""Prompt assembly and context budgeting for conversations."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field

from hephaestus.conversation.schemas import (
    ConversationBudgetReport,
    ConversationContextItem,
    ConversationMessage,
    DeliberationMode,
    RetrievedConversationContext,
)
from hephaestus.discussion_quality.schemas import (
    DiscussionQualityEvaluation,
    ResearchPlan,
)
from hephaestus.policy import policy_prompt_guidance
from hephaestus.policy.schemas import PolicyEvaluation

SYSTEM_BEHAVIOR_STANDARD = """\
You are Hephaestus: an optimization-first agent OS focused on explainable decision quality.

Behavior standard:
- Be maximally honest, non-patronizing, and useful.
- Think several steps ahead.
- Separate facts, assumptions, uncertainty, and recommendations when relevant.
- Challenge weak assumptions when useful.
- Do not be a yes-man.
- Do not disagree merely to sound contrarian.
- Propose alternatives and concrete next moves.
"""

FREEDOM_POLICY_STANDARD = """\
Freedom and policy UX:
- Treat benign user-owned creative, development, research, product, and strategy work as allowed.
- Avoid corporate-style moralizing and unnecessary refusal theater.
- Keep boundaries transparent and configurable.
- Still avoid genuinely harmful behavior.

Current capability boundary:
- This turn is text conversation only.
- Do not claim to execute commands, edit files, browse, automate a browser, or run autonomous workflows.
- You may reason about code, architecture, research, product, strategy, roadmap, and difficult decisions.
"""

_MODE_GUIDANCE: dict[DeliberationMode, str] = {
    DeliberationMode.BALANCED: "Balance usefulness, candor, uncertainty, and next steps.",
    DeliberationMode.DIRECT: "Be concise, decisive, and light on scaffolding.",
    DeliberationMode.CRITICAL: "Look for weak assumptions, risks, and premature conclusions.",
    DeliberationMode.STRATEGIC: "Think several moves ahead and connect advice to positioning.",
    DeliberationMode.RESEARCH: "Separate knowns from unknowns and propose a research plan.",
    DeliberationMode.ARCHITECT: "Focus on boundaries, interfaces, tradeoffs, and evolution.",
    DeliberationMode.COACH: "Help the user think clearly without patronizing or cheerleading.",
    DeliberationMode.SKEPTICAL_BUT_FAIR: (
        "Challenge the idea hard while preserving what is strong or promising."
    ),
}


class PromptAssembly(BaseModel):
    """Assembled prompt plus deterministic context-budget metadata."""

    model_config = ConfigDict(frozen=True)

    prompt: str
    input_tokens: int = Field(ge=0)
    output_token_budget: int = Field(gt=0)
    selected_context: list[ConversationContextItem] = Field(default_factory=list)
    trimmed_context: list[ConversationContextItem] = Field(default_factory=list)
    trimming_notes: list[str] = Field(default_factory=list)

    @property
    def context_trimmed(self) -> bool:
        return bool(self.trimmed_context)

    @property
    def selected_memory_ids(self) -> list[str]:
        return [item.id for item in self.selected_context if item.source == "memory"]

    @property
    def selected_strategic_memory_ids(self) -> list[str]:
        return [
            item.id for item in self.selected_context if item.source == "strategic_memory"
        ]

    def budget_report(
        self,
        *,
        provider_model: str,
        selected_provider: str,
        selected_model: str,
        context_window: int,
        estimated_output_tokens: int,
        estimated_cost: float,
        prompt_token_budget: int,
    ) -> ConversationBudgetReport:
        """Create a response-facing budget report."""

        return ConversationBudgetReport(
            provider_model=provider_model,
            selected_provider=selected_provider,
            selected_model=selected_model,
            estimated_input_tokens=self.input_tokens,
            estimated_output_tokens=estimated_output_tokens,
            output_token_budget=self.output_token_budget,
            context_window=context_window,
            prompt_token_budget=prompt_token_budget,
            estimated_cost=estimated_cost,
            context_trimmed=self.context_trimmed,
            trimming_notes=self.trimming_notes,
            selected_context_count=len(self.selected_context),
            selected_memory_count=len(self.selected_memory_ids),
            selected_strategic_memory_count=len(self.selected_strategic_memory_ids),
        )


@dataclass(frozen=True)
class _ContextBlock:
    item: ConversationContextItem
    text: str
    priority: int
    token_cost: int


def mode_guidance(mode: DeliberationMode) -> str:
    """Return concise guidance for a deliberation mode."""

    return _MODE_GUIDANCE[mode]


def estimate_tokens(text: str) -> int:
    """Estimate tokens without depending on provider tokenizers."""

    normalized = " ".join(text.split())
    if not normalized:
        return 0
    return max(1, (len(normalized) + 3) // 4)


def build_conversation_prompt(
    user_prompt: str,
    *,
    mode: DeliberationMode,
    context: RetrievedConversationContext,
    recent_messages: list[ConversationMessage] | None = None,
    assumptions: list[str],
    options: list[str],
    risks: list[str],
    tradeoffs: list[str],
    missing_information: list[str],
    recommendation: str,
    next_moves: list[str],
    research_plan: ResearchPlan | None = None,
    quality_evaluation: DiscussionQualityEvaluation | None = None,
    policy_evaluation: PolicyEvaluation | None = None,
    max_input_tokens: int = 6_000,
    output_token_budget: int = 1_200,
) -> PromptAssembly:
    """Build a provider prompt with deterministic context trimming."""

    fixed_sections = _fixed_sections(
        user_prompt,
        mode=mode,
        context=context,
        assumptions=assumptions,
        options=options,
        risks=risks,
        tradeoffs=tradeoffs,
        missing_information=missing_information,
        recommendation=recommendation,
        next_moves=next_moves,
        research_plan=research_plan,
        quality_evaluation=quality_evaluation,
        policy_evaluation=policy_evaluation,
    )
    final_instruction = _final_instruction(context.intent, mode, research_plan)
    fixed_text = "\n\n".join(
        [
            SYSTEM_BEHAVIOR_STANDARD,
            FREEDOM_POLICY_STANDARD,
            *fixed_sections,
            final_instruction,
        ]
    )
    fixed_tokens = estimate_tokens(fixed_text)
    available_context_tokens = max(0, max_input_tokens - fixed_tokens - 96)

    selected_blocks: list[_ContextBlock] = []
    trimmed_blocks: list[_ContextBlock] = []
    used_context_tokens = 0
    for block in _ranked_context_blocks(context, recent_messages or []):
        if used_context_tokens + block.token_cost <= available_context_tokens:
            selected_blocks.append(block)
            used_context_tokens += block.token_cost
        else:
            trimmed_blocks.append(block)

    context_sections = _context_sections([block.item for block in selected_blocks])
    prompt = "\n\n".join(
        [
            SYSTEM_BEHAVIOR_STANDARD,
            FREEDOM_POLICY_STANDARD,
            *context_sections,
            *fixed_sections,
            final_instruction,
        ]
    )
    trimming_notes = _trimming_notes(trimmed_blocks, available_context_tokens)
    return PromptAssembly(
        prompt=prompt,
        input_tokens=estimate_tokens(prompt),
        output_token_budget=output_token_budget,
        selected_context=[block.item for block in selected_blocks],
        trimmed_context=[block.item for block in trimmed_blocks],
        trimming_notes=trimming_notes,
    )


def _fixed_sections(
    user_prompt: str,
    *,
    mode: DeliberationMode,
    context: RetrievedConversationContext,
    assumptions: list[str],
    options: list[str],
    risks: list[str],
    tradeoffs: list[str],
    missing_information: list[str],
    recommendation: str,
    next_moves: list[str],
    research_plan: ResearchPlan | None,
    quality_evaluation: DiscussionQualityEvaluation | None,
    policy_evaluation: PolicyEvaluation | None,
) -> list[str]:
    sections = [
        f"Mode: {mode.value}. {mode_guidance(mode)}",
        f"Intent: {context.intent.value}",
        _rubric_section(quality_evaluation),
        _policy_section(policy_evaluation),
        "User message:\n" + user_prompt,
        "Internal deterministic context:\n"
        + "\n".join(
            [
                "Assumptions:\n" + _bullets(assumptions),
                "Options considered:\n" + _bullets(options),
                "Risks:\n" + _bullets(risks),
                "Tradeoffs:\n" + _bullets(tradeoffs),
                "Missing information:\n" + _bullets(missing_information),
                "Recommendation seed:\n" + (recommendation or "- none"),
                "Next moves:\n" + _bullets(next_moves),
            ]
        ),
    ]
    if research_plan is not None:
        sections.append(_research_section(research_plan))
    return sections


def _policy_section(evaluation: PolicyEvaluation | None) -> str:
    if evaluation is None:
        return (
            "Active policy profile: balanced. Help directly with benign user-owned "
            "work; refuse only genuinely harmful action."
        )
    return policy_prompt_guidance(evaluation)


def _ranked_context_blocks(
    context: RetrievedConversationContext,
    recent_messages: list[ConversationMessage],
) -> list[_ContextBlock]:
    items = [
        *_session_context_items(recent_messages),
        *context.context_items,
    ]
    blocks = [_context_block(item, index) for index, item in enumerate(items)]
    return sorted(blocks, key=lambda block: (-block.priority, -block.item.relevance, block.item.id))


def _context_block(item: ConversationContextItem, index: int) -> _ContextBlock:
    text = f"[{item.source}] {item.summary}\n{item.content}"
    return _ContextBlock(
        item=item,
        text=text,
        priority=_source_priority(item.source) + index,
        token_cost=estimate_tokens(text),
    )


def _source_priority(source: str) -> int:
    if source == "strategic_memory":
        return 40_000
    if source == "repo_profile":
        return 30_000
    if source == "session":
        return 20_000
    if source == "memory":
        return 10_000
    return 1_000


def _session_context_items(messages: list[ConversationMessage]) -> list[ConversationContextItem]:
    recent = messages[-6:]
    items: list[ConversationContextItem] = []
    for index, message in enumerate(recent):
        role = message.role.value
        summary = _trim(f"{role}: {message.content}", max_length=180)
        items.append(
            ConversationContextItem(
                id=message.id,
                source="session",
                summary=summary,
                content=_trim(message.content, max_length=700),
                relevance=0.72 + index * 0.02,
                metadata={"role": role},
            )
        )
    return items


def _context_sections(items: list[ConversationContextItem]) -> list[str]:
    if not items:
        return ["Selected context:\n- none selected"]
    sections: list[str] = []
    for source, title in [
        ("strategic_memory", "Selected strategic memory"),
        ("repo_profile", "Repository context"),
        ("session", "Recent session context"),
        ("memory", "Selected regular memory"),
    ]:
        source_items = [item for item in items if item.source == source]
        if source_items:
            sections.append(f"{title}:\n" + _bullets(_item_text(item) for item in source_items))
    other_items = [
        item
        for item in items
        if item.source not in {"strategic_memory", "repo_profile", "session", "memory"}
    ]
    if other_items:
        sections.append("Other selected context:\n" + _bullets(_item_text(item) for item in other_items))
    return sections


def _item_text(item: ConversationContextItem) -> str:
    content = item.content if item.content != item.summary else ""
    if content:
        return f"{item.summary} :: {_trim(content, max_length=700)}"
    return item.summary


def _rubric_section(evaluation: DiscussionQualityEvaluation | None) -> str:
    if evaluation is None:
        return "Discussion rubric: general usefulness, honesty, assumptions, risks, and next move."
    labels = ", ".join(check.label for check in evaluation.checks) or "no explicit checks"
    return (
        f"Discussion rubric: {evaluation.rubric_name}. "
        f"Expected checks: {labels}. Deterministic pre-score: {evaluation.score:.2f}."
    )


def _research_section(plan: ResearchPlan) -> str:
    return "\n".join(
        [
            "Research planning context:",
            "Do not claim live research has been performed in this turn.",
            "Claims to verify:\n" + _bullets(plan.needs_verification),
            "Likely sources:\n" + _bullets(plan.likely_sources),
            "Search queries:\n" + _bullets(plan.search_queries),
            "Evidence quality:\n" + _bullets(plan.evidence_quality_expectations),
            "What would change the conclusion:\n"
            + _bullets(plan.what_would_change_conclusion),
        ]
    )


def _final_instruction(
    intent: object,
    mode: DeliberationMode,
    research_plan: ResearchPlan | None,
) -> str:
    research_warning = (
        " In research mode, present a research plan and avoid implying that current web "
        "research or live source verification has already happened."
        if research_plan is not None or mode == DeliberationMode.RESEARCH
        else ""
    )
    return (
        "Write the final answer now. Be clear enough to be useful without dumping the "
        "whole hidden process. When relevant, include: position/recommendation, facts, "
        "assumptions, risks, missing information, and next move. Use selected memory and "
        f"context when it materially changes the answer. Intent is {intent}.{research_warning}"
    )


def _trimming_notes(blocks: list[_ContextBlock], available_context_tokens: int) -> list[str]:
    if not blocks:
        return []
    by_source: dict[str, int] = {}
    for block in blocks:
        by_source[block.item.source] = by_source.get(block.item.source, 0) + 1
    summary = ", ".join(f"{source}:{count}" for source, count in sorted(by_source.items()))
    return [
        f"Trimmed {len(blocks)} lower-priority context item(s) within "
        f"{available_context_tokens} available context tokens ({summary})."
    ]


def _bullets(values: Iterable[str]) -> str:
    listed = list(values)
    return "\n".join(f"- {value}" for value in listed) if listed else "- none"


def _trim(value: str, *, max_length: int) -> str:
    normalized = " ".join(value.split())
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max_length - 1].rstrip() + "..."
