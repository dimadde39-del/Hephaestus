"""Internal deliberation pipeline for conversational responses."""

from __future__ import annotations

from hephaestus.conversation.analysis import extract_question_terms
from hephaestus.conversation.prompts import build_synthesis_prompt, mode_guidance
from hephaestus.conversation.schemas import (
    ConversationIntent,
    ConversationRequest,
    DeliberationMode,
    DeliberationPass,
    DeliberationResult,
    RetrievedConversationContext,
)
from hephaestus.discussion_quality.evaluator import (
    build_research_plan,
    evaluate_discussion_quality,
)
from hephaestus.discussion_quality.schemas import (
    DiscussionQualityEvaluation,
    ResearchPlan,
)
from hephaestus.models import DeepSeekProvider, FakeModelProvider, ModelProvider, ModelRequest


class ConversationDeliberator:
    """Run lightweight internal deliberation passes for one Hephaestus response."""

    def __init__(self, provider: ModelProvider | None = None) -> None:
        self.provider = provider or default_conversation_provider()

    def deliberate(
        self,
        request: ConversationRequest,
        intent: ConversationIntent,
        context: RetrievedConversationContext,
    ) -> DeliberationResult:
        """Run classification-informed deliberation and synthesize a response."""

        assumptions = _map_assumptions(request.prompt, intent, context)
        options = _generate_options(request.prompt, intent, request.mode, context)
        risks = _critic_risks(request.prompt, intent, context)
        tradeoffs = _tradeoffs(intent, context)
        missing_information = _missing_information(intent, context)
        next_moves = _next_moves(intent, request.mode, context)
        recommendation = _recommendation(request.prompt, intent, request.mode, context)
        research_plan = (
            build_research_plan(
                request.prompt,
                intent=intent,
                missing_information=missing_information,
                risks=risks,
            )
            if request.mode == DeliberationMode.RESEARCH
            or intent == ConversationIntent.RESEARCH_PLANNING
            else None
        )
        quality_evaluation = evaluate_discussion_quality(
            intent=intent,
            mode=request.mode,
            assumptions=assumptions,
            options=options,
            risks=risks,
            tradeoffs=tradeoffs,
            missing_information=missing_information,
            recommendation=recommendation,
            next_moves=next_moves,
            research_plan=research_plan,
        )

        passes = _build_passes(
            intent,
            request.mode,
            context,
            assumptions=assumptions,
            options=options,
            risks=risks,
            missing_information=missing_information,
            recommendation=recommendation,
            next_moves=next_moves,
        )

        deterministic = _synthesize_deterministic_response(
            request,
            intent,
            context,
            assumptions=assumptions,
            options=options,
            risks=risks,
            tradeoffs=tradeoffs,
            missing_information=missing_information,
            recommendation=recommendation,
            next_moves=next_moves,
            research_plan=research_plan,
            quality_evaluation=quality_evaluation,
        )
        provider_model = "local/deterministic"
        input_tokens = max(1, len(request.prompt.split()))
        output_tokens = max(1, len(deterministic.split()))
        estimated_cost = 0.0

        if self.provider.name == "fake" or not self.provider.is_available:
            model_response = self.provider.complete(
                ModelRequest(prompt=request.prompt, max_output_tokens=900)
            )
            provider_model = model_response.model
            input_tokens = model_response.input_tokens
            output_tokens = max(output_tokens, model_response.output_tokens)
        else:
            try:
                model_response = self.provider.complete(
                    ModelRequest(
                        prompt=build_synthesis_prompt(
                            request.prompt,
                            mode=request.mode,
                            context=context,
                            assumptions=assumptions,
                            options=options,
                            risks=risks,
                            next_moves=next_moves,
                            research_plan=research_plan,
                            quality_evaluation=quality_evaluation,
                        ),
                        temperature=0.2,
                        max_output_tokens=1_600,
                    )
                )
                deterministic = model_response.text.strip() or deterministic
                provider_model = model_response.model
                input_tokens = model_response.input_tokens
                output_tokens = model_response.output_tokens
                estimated_cost = model_response.estimated_cost
            except Exception as error:
                deterministic = "\n\n".join(
                    [
                        deterministic,
                        (
                            "Provider note: the configured model provider failed, so this "
                            f"response used local deterministic deliberation. Error: {error}"
                        ),
                    ]
                )

        return DeliberationResult(
            intent=intent,
            mode=request.mode,
            passes=passes,
            assumptions=assumptions,
            options=options,
            risks=risks,
            tradeoffs=tradeoffs,
            missing_information=missing_information,
            recommendation=recommendation,
            next_moves=next_moves,
            final_response=deterministic,
            quality_evaluation=quality_evaluation,
            research_plan=research_plan,
            confidence=_confidence(intent, context, request.mode),
            provider_model=provider_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost=estimated_cost,
        )


def default_conversation_provider() -> ModelProvider:
    """Prefer configured DeepSeek, otherwise use deterministic fake provider."""

    deepseek = DeepSeekProvider()
    if deepseek.is_available:
        return deepseek
    return FakeModelProvider()


def _context_findings(
    intent: ConversationIntent,
    context: RetrievedConversationContext,
) -> list[str]:
    findings = [f"Intent classified as {intent.value}."]
    if context.repo_profile is not None:
        findings.append(f"Repo profile selected: {context.repo_profile.name}.")
    else:
        findings.append("No repository profile is attached to this turn.")
    findings.append(f"Selected {len(context.memories)} relevant memories.")
    return findings


def _memory_findings(context: RetrievedConversationContext) -> list[str]:
    findings: list[str] = []
    if context.memories:
        findings.extend(memory.summary or memory.content for memory in context.memories[:5])
    if context.strategic_memories:
        findings.extend(
            f"Strategic: {memory.summary or memory.content}"
            for memory in context.strategic_memories[:5]
        )
    if not findings:
        return ["No durable memories were relevant enough to select."]
    return findings


def _build_passes(
    intent: ConversationIntent,
    mode: DeliberationMode,
    context: RetrievedConversationContext,
    *,
    assumptions: list[str],
    options: list[str],
    risks: list[str],
    missing_information: list[str],
    recommendation: str,
    next_moves: list[str],
) -> list[DeliberationPass]:
    base = [
        DeliberationPass(
            name="ContextScout",
            purpose="Identify the discussion shape and available grounding context.",
            findings=_context_findings(intent, context),
            confidence=0.78,
        ),
        DeliberationPass(
            name="MemoryRetriever",
            purpose="Bring relevant durable and strategic memories into the turn.",
            findings=_memory_findings(context),
            confidence=0.74 if context.memories or context.strategic_memories else 0.58,
        ),
        DeliberationPass(
            name="AssumptionMapper",
            purpose="Separate stated facts from assumptions and uncertainties.",
            findings=assumptions,
            confidence=0.74,
        ),
    ]
    if _uses_high_impact_pipeline(intent, mode):
        return [
            *base,
            DeliberationPass(
                name="EvidenceChecker",
                purpose="Separate available evidence from claims that still need verification.",
                findings=_evidence_findings(intent, context, missing_information),
                confidence=0.7,
            ),
            DeliberationPass(
                name="SecondOrderThinker",
                purpose="Look at downstream effects if the recommendation is followed.",
                findings=_second_order_effects(intent, recommendation),
                confidence=0.72,
            ),
            DeliberationPass(
                name="OptionGenerator",
                purpose="Generate viable options before recommending one.",
                findings=options,
                confidence=0.76,
            ),
            DeliberationPass(
                name="Critic",
                purpose="Challenge weak assumptions without being contrarian.",
                findings=risks,
                confidence=0.76,
            ),
            DeliberationPass(
                name="RecommendationSynthesizer",
                purpose="Convert assumptions, options, objections, and evidence gaps into next moves.",
                findings=[recommendation, *next_moves[:3]],
                confidence=0.78,
            ),
        ]
    return [
        *base,
        DeliberationPass(
            name="Critic",
            purpose="Challenge weak assumptions without being contrarian.",
            findings=risks,
            confidence=0.76,
        ),
        DeliberationPass(
            name="Strategist",
            purpose="Generate practical options and next moves.",
            findings=[*options[:4], *next_moves[:3]],
            confidence=0.78,
        ),
    ]


def _uses_high_impact_pipeline(intent: ConversationIntent, mode: DeliberationMode) -> bool:
    return mode in {
        DeliberationMode.STRATEGIC,
        DeliberationMode.CRITICAL,
        DeliberationMode.RESEARCH,
        DeliberationMode.ARCHITECT,
        DeliberationMode.SKEPTICAL_BUT_FAIR,
    } or intent in {
        ConversationIntent.ARCHITECTURE_DISCUSSION,
        ConversationIntent.PRODUCT_STRATEGY,
        ConversationIntent.BUSINESS_STRATEGY,
        ConversationIntent.IDEA_STRESS_TEST,
        ConversationIntent.ROADMAP_DECISION,
        ConversationIntent.RESEARCH_PLANNING,
        ConversationIntent.RISK_ANALYSIS,
    }


def _evidence_findings(
    intent: ConversationIntent,
    context: RetrievedConversationContext,
    missing_information: list[str],
) -> list[str]:
    findings: list[str] = []
    if context.memories:
        findings.append(f"{len(context.memories)} regular memories are available as local context.")
    if context.strategic_memories:
        findings.append(
            f"{len(context.strategic_memories)} strategic memories are available as local context."
        )
    if context.repo_profile is not None:
        findings.append("Repo context is based on read-only inspection, not command execution.")
    if intent == ConversationIntent.RESEARCH_PLANNING:
        findings.append("No live research has been performed; this turn should plan verification.")
    findings.extend(missing_information[:3])
    return findings or ["No external evidence has been verified in this turn."]


def _second_order_effects(intent: ConversationIntent, recommendation: str) -> list[str]:
    if intent == ConversationIntent.IDEA_STRESS_TEST:
        return [
            "If the idea launches early, positioning clarity becomes more important than breadth.",
            "If the idea waits too long, the project loses real feedback on the decision-quality wedge.",
        ]
    if intent == ConversationIntent.ROADMAP_DECISION:
        return [
            "A roadmap choice also changes user expectations and future validation burden.",
            "Deferred work should remain visible so the project does not look incomplete by accident.",
        ]
    if intent == ConversationIntent.ARCHITECTURE_DISCUSSION:
        return [
            "Architecture choices made now will constrain later execution, browser, and voice layers.",
            "Good boundaries reduce future migration cost when real tools arrive.",
        ]
    return [
        f"Following the recommendation changes future defaults: {recommendation}",
        "The next move should produce evidence, not just a more elaborate plan.",
    ]


def _map_assumptions(
    prompt: str,
    intent: ConversationIntent,
    context: RetrievedConversationContext,
) -> list[str]:
    lowered = prompt.lower()
    assumptions: list[str] = []
    if "worried" in lowered or "concern" in lowered:
        assumptions.append("The concern may be valid, but its severity depends on user expectations.")
    if "20k" in lowered or "stars" in lowered:
        assumptions.append("GitHub stars require a crisp public story plus proof that the system works.")
    if "before it can execute code" in lowered or "can't execute code" in lowered:
        assumptions.append("A planning-only launch can work if the demo makes the execution boundary explicit.")
    if context.repo_profile is not None:
        assumptions.append("Repo-aware advice is based on read-only profile signals, not command execution.")
    if context.strategic_memories:
        assumptions.append("Strategic advice is conditioned on recalled long-term project context.")
    if intent == ConversationIntent.ARCHITECTURE_DISCUSSION:
        assumptions.append("Architecture quality depends on boundaries that survive later execution features.")
    if intent == ConversationIntent.RESEARCH_PLANNING:
        assumptions.append("Research is needed where claims depend on current external evidence.")
    if not assumptions:
        terms = ", ".join(extract_question_terms(prompt)[:5])
        assumptions.append(
            f"The useful answer should focus on {terms or 'the stated question'} and name uncertainty."
        )
    return assumptions


def _generate_options(
    prompt: str,
    intent: ConversationIntent,
    mode: DeliberationMode,
    context: RetrievedConversationContext,
) -> list[str]:
    if intent == ConversationIntent.REPO_QUESTION and context.repo_profile is not None:
        return [
            "Use the latest repo profile to reason about validation, stack, and release risk.",
            "Inspect the repo again if the profile may be stale.",
            "Turn the risks into a release-readiness plan before execution features exist.",
        ]
    if intent == ConversationIntent.IDEA_STRESS_TEST:
        return [
            "Launch the concept now as an explainable planning OS.",
            "Delay launch until real execution exists.",
            "Launch a narrow proof: repo intelligence plus decision traces plus honest limitations.",
        ]
    if intent == ConversationIntent.PRODUCT_STRATEGY:
        return [
            "Double down on decision quality as the wedge.",
            "Move quickly into execution to satisfy practical users.",
            "Publish a transparent alpha that treats non-execution as a deliberate safety boundary.",
        ]
    if intent == ConversationIntent.BUSINESS_STRATEGY:
        return [
            "Validate the customer pain and distribution path before widening scope.",
            "Position the project around decision quality first, then test commercial extensions later.",
            "Keep open-source trust high by making boundaries and incentives explicit.",
        ]
    if intent == ConversationIntent.ARCHITECTURE_DISCUSSION:
        return [
            "Keep conversation, memory, repo intelligence, and execution as separate modules.",
            "Use internal deliberation passes now and defer external sub-agent swarms.",
            "Persist traces for high-impact discussions so later learning can evaluate them.",
        ]
    if mode == DeliberationMode.DIRECT:
        return ["Answer the main question, name the biggest risk, and give the next move."]
    return [
        "Answer directly from current context.",
        "Identify assumptions and missing information.",
        "Offer concrete next moves rather than vague encouragement.",
    ]


def _critic_risks(
    prompt: str,
    intent: ConversationIntent,
    context: RetrievedConversationContext,
) -> list[str]:
    lowered = prompt.lower()
    risks: list[str] = []
    if "abstract" in lowered or intent == ConversationIntent.IDEA_STRESS_TEST:
        risks.append("The project can sound abstract if the demo does not show a concrete before/after.")
    if "execute code" in lowered:
        risks.append("Users may expect agent OS to execute actions; the alpha must frame planning clearly.")
    if intent == ConversationIntent.PRODUCT_STRATEGY:
        risks.append("A broad agent OS story can dilute the wedge unless the first use case is sharp.")
    if intent == ConversationIntent.BUSINESS_STRATEGY:
        risks.append("Business strategy can become speculative without customer, distribution, and pricing proof.")
    if intent == ConversationIntent.REPO_QUESTION and context.repo_profile is not None:
        if context.repo_profile.risk_signals:
            risks.append("Repo risk signals exist and should be reviewed before any execution phase.")
        if not context.repo_profile.validation_plan.commands:
            risks.append("No safe validation commands were detected, which weakens release confidence.")
    if not risks:
        risks.append("The main risk is acting on an under-specified premise without validating it.")
    return risks


def _tradeoffs(
    intent: ConversationIntent,
    context: RetrievedConversationContext,
) -> list[str]:
    if intent == ConversationIntent.REPO_QUESTION and context.repo_profile is not None:
        return [
            "Reusing the latest repo profile is fast, but re-inspection is safer after code changes.",
            "Planning-only analysis is safe and explainable, but it cannot prove commands pass.",
        ]
    if intent in {
        ConversationIntent.PRODUCT_STRATEGY,
        ConversationIntent.IDEA_STRESS_TEST,
        ConversationIntent.ROADMAP_DECISION,
    }:
        return [
            "Launching early gets feedback, but it raises the burden of clarity around limitations.",
            "Waiting for execution improves practical value, but delays learning from positioning.",
        ]
    return [
        "More certainty usually requires more context or research.",
        "More directness is faster, but can hide assumptions if the question is strategic.",
    ]


def _missing_information(
    intent: ConversationIntent,
    context: RetrievedConversationContext,
) -> list[str]:
    missing: list[str] = []
    if intent == ConversationIntent.REPO_QUESTION and context.repo_profile is None:
        missing.append("No repository profile was attached; run with --repo for grounded repo advice.")
    if intent in {ConversationIntent.PRODUCT_STRATEGY, ConversationIntent.BUSINESS_STRATEGY}:
        missing.append("Target audience, distribution channel, and proof demo are not fully specified.")
    if intent == ConversationIntent.RESEARCH_PLANNING:
        missing.append("External sources should be checked before making current factual claims.")
        missing.append("Source dates, primary evidence, and comparison criteria are not verified yet.")
    if intent == ConversationIntent.ARCHITECTURE_DISCUSSION:
        missing.append("Operational observability and migration path may need sharper proof.")
    if not missing:
        missing.append("The answer may need follow-up context before becoming an execution plan.")
    return missing


def _next_moves(
    intent: ConversationIntent,
    mode: DeliberationMode,
    context: RetrievedConversationContext,
) -> list[str]:
    if intent == ConversationIntent.REPO_QUESTION and context.repo_profile is not None:
        return [
            "Review detected validation commands and repo risk signals.",
            "Convert the highest-risk gap into the next roadmap task.",
            "Keep execution deferred until an approval-gated command runner exists.",
        ]
    if intent == ConversationIntent.IDEA_STRESS_TEST:
        return [
            "Write the launch story around a concrete decision-quality demo.",
            "Name the non-execution boundary directly in the README and demo.",
            "Collect objections and turn repeated ones into Phase 5B memory/research work.",
        ]
    if mode == DeliberationMode.RESEARCH:
        return [
            "List the claims that need evidence.",
            "Identify primary sources, direct comparisons, and date-sensitive facts.",
            "Store findings as memory only after review.",
        ]
    return [
        "Decide what would change the recommendation.",
        "Run the smallest safe validation of that uncertainty.",
        "Save durable project preferences as memory if they should shape future answers.",
    ]


def _recommendation(
    prompt: str,
    intent: ConversationIntent,
    mode: DeliberationMode,
    context: RetrievedConversationContext,
) -> str:
    lowered = prompt.lower()
    if "what is hephaestus trying to become" in lowered:
        return (
            "Hephaestus is trying to become an optimization-first agent OS that improves "
            "decision quality before action: local-first, memory-grounded, repo-aware, "
            "explainable, and honest about uncertainty."
        )
    if intent == ConversationIntent.REPO_QUESTION and context.repo_profile is not None:
        return (
            "Treat release risk as a profile-grounded planning problem first: validate the "
            "detected stack, review risk signals, and do not imply command execution yet."
        )
    if intent == ConversationIntent.IDEA_STRESS_TEST:
        return (
            "Launch only if the alpha is framed as decision-quality infrastructure, not as "
            "an execution agent; otherwise the abstraction criticism will land."
        )
    if intent == ConversationIntent.PRODUCT_STRATEGY:
        return (
            "Keep the wedge narrow: decision quality for repo, roadmap, and strategy work "
            "before expanding into execution or voice."
        )
    if intent == ConversationIntent.BUSINESS_STRATEGY:
        return (
            "Do not overfit the business story before evidence: validate customer pain, "
            "distribution, and willingness to adopt the decision-quality wedge."
        )
    if intent == ConversationIntent.ARCHITECTURE_DISCUSSION:
        return (
            "Protect the core boundaries now: conversation should feed memory and traces, "
            "while execution remains a later approval-gated layer."
        )
    if mode == DeliberationMode.DIRECT:
        return "Answer the central question plainly, then give the next practical move."
    if mode == DeliberationMode.RESEARCH:
        return (
            "Treat this as a research-planning turn: define what must be verified, "
            "where to look, and what evidence would change the conclusion."
        )
    return "Use the current context to make the next decision clearer, not just more elaborate."


def _synthesize_deterministic_response(
    request: ConversationRequest,
    intent: ConversationIntent,
    context: RetrievedConversationContext,
    *,
    assumptions: list[str],
    options: list[str],
    risks: list[str],
    tradeoffs: list[str],
    missing_information: list[str],
    recommendation: str,
    next_moves: list[str],
    research_plan: ResearchPlan | None,
    quality_evaluation: DiscussionQualityEvaluation | None,
) -> str:
    provider_note = (
        "Provider note: no real model provider is configured, so this response uses "
        "local deterministic deliberation. Set DEEPSEEK_API_KEY to enable optional "
        "model-backed synthesis."
    )
    repo_line = ""
    if context.repo_profile is not None:
        profile = context.repo_profile
        repo_line = "\n".join(
            [
                "",
                "Repo context:",
                f"- Profile: {profile.name} ({profile.id})",
                f"- Stack: {', '.join(profile.detected_languages) or 'unknown'}; "
                f"{', '.join(profile.detected_frameworks) or 'no framework detected'}",
                "- Validation: "
                + (", ".join(profile.validation_plan.command_texts) or "none detected"),
                f"- Risk signals: {len(profile.risk_signals)}",
            ]
        )

    memory_line = ""
    memory_items: list[str] = []
    if context.memories:
        memory_items.extend(memory.summary or memory.content for memory in context.memories[:4])
    if context.strategic_memories:
        memory_items.extend(
            f"Strategic: {memory.summary or memory.content}"
            for memory in context.strategic_memories[:4]
        )
    if memory_items:
        memory_line = "\n\nSelected memory:\n" + "\n".join(f"- {item}" for item in memory_items)

    strategic_position = ""
    if _uses_high_impact_pipeline(intent, request.mode):
        strategic_position = "\n".join(
            [
                f"Position: {recommendation}",
                f"Confidence: {_confidence(intent, context, request.mode):.2f}",
                f"Strongest support: {options[0] if options else recommendation}",
                f"Strongest objection: {risks[0] if risks else 'No strong objection identified.'}",
                "Missing information: " + (missing_information[0] if missing_information else "-"),
                "Next move: " + (next_moves[0] if next_moves else "-"),
            ]
        )

    research_plan_section = ""
    if research_plan is not None:
        plan = research_plan
        research_plan_section = "\n\n".join(
            [
                "Research plan, not researched facts:",
                "What needs verification:\n" + _bullets(plan.needs_verification),
                "Likely sources:\n" + _bullets(plan.likely_sources),
                "Search queries:\n" + _bullets(plan.search_queries),
                "Evidence quality expectations:\n"
                + _bullets(plan.evidence_quality_expectations),
                "What would change the conclusion:\n"
                + _bullets(plan.what_would_change_conclusion),
                "Risks of shallow research:\n" + _bullets(plan.shallow_research_risks),
            ]
        )

    quality_line = ""
    if quality_evaluation is not None:
        evaluation = quality_evaluation
        quality_line = (
            f"Discussion quality: {evaluation.rubric_name} "
            f"({evaluation.score:.2f}). {evaluation.summary}"
        )

    sections = [
        provider_note,
        f"Intent: {intent.value}. Mode: {request.mode.value} ({mode_guidance(request.mode)})",
        strategic_position,
        f"Recommendation: {recommendation}",
        repo_line.strip(),
        memory_line.strip(),
        research_plan_section,
        "Assumptions:\n" + _bullets(assumptions),
        "Options:\n" + _bullets(options),
        "Risks and tradeoffs:\n" + _bullets([*risks, *tradeoffs]),
        "Missing information:\n" + _bullets(missing_information),
        "Next moves:\n" + _bullets(next_moves),
        quality_line,
    ]
    if request.discussion:
        sections.insert(
            3,
            (
                "Read: this is a discussion, so the useful output is a structured analysis "
                "with pressure on assumptions, not a one-line answer."
            ),
        )
    return "\n\n".join(section for section in sections if section)


def _confidence(
    intent: ConversationIntent,
    context: RetrievedConversationContext,
    mode: DeliberationMode,
) -> float:
    confidence = 0.66
    if context.memories:
        confidence += 0.05
    if context.repo_profile is not None:
        confidence += 0.08
    if intent in {ConversationIntent.GENERAL, ConversationIntent.PERSONAL_CONTEXT}:
        confidence -= 0.03
    if mode in {DeliberationMode.CRITICAL, DeliberationMode.SKEPTICAL_BUT_FAIR}:
        confidence += 0.03
    return min(0.88, max(0.45, confidence))


def _bullets(values: list[str]) -> str:
    return "\n".join(f"- {value}" for value in values) if values else "- none"
