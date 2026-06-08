# Deliberation Modes

Deliberation modes are reasoning styles, not personalities.

- `balanced`: default mix of candor, usefulness, uncertainty, and next steps.
- `direct`: concise answer, biggest risk, next move.
- `critical`: pressure-test assumptions and premature conclusions.
- `strategic`: think several moves ahead and connect advice to positioning.
- `research`: separate knowns from unknowns and propose a research path.
- `architect`: focus on boundaries, interfaces, tradeoffs, and evolution.
- `coach`: help the user think clearly without patronizing or cheerleading.
- `skeptical_but_fair`: challenge hard while preserving what is strong.

Examples:

```bash
uv run heph ask "What are the release risks?" --mode critical --repo .
uv run heph discuss "Should we launch before execution exists?" --mode strategic
uv run heph discuss "Plan research for comparing agent OS projects." --mode research
```

Modes influence deliberation emphasis, provider-routing requirements, quality
thresholds, and benchmark expectations. They do not change the safety boundary:
Phase 5C remains text-only and does not execute commands, edit code, browse, or
pretend live research happened.

## Rubric-Aware Discussions

High-impact discussions use explicit quality rubrics:

- `idea_stress_test`
- `business_strategy`
- `product_strategy`
- `technical_architecture`
- `roadmap_decision`
- `research_planning`
- `risk_analysis`

Strategic discussions usually include a position, confidence, strongest support,
strongest objection, missing information, risks, and next move. Hephaestus can
be skeptical, but the goal is useful pressure, not performative disagreement.

Research mode produces a research plan: claims to verify, likely sources,
search queries, evidence quality expectations, what would change the conclusion,
and risks of shallow research.

In Phase 5C, deterministic deliberation still identifies intent, assumptions,
options, risks, missing information, rubric, and memory context first. If a real
provider is configured through `auto` mode, only the final synthesis is
model-backed by default. This keeps cost controlled and preserves deterministic
tests.
