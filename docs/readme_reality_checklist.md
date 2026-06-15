# README Reality Checklist

Use this checklist before publishing README or launch-copy changes.

## First Screen

- [ ] Does the first screen explain what Hephaestus is in human language?
- [ ] Does it say who it is for?
- [ ] Does it say what it can do today?
- [ ] Does it show a simple way to try it?
- [ ] Does it admit what is not built yet?
- [ ] Does it avoid leading with QUBO, Pareto, policy taxonomies, or decision
  theory?

## Overclaiming

- [ ] No claim of full autonomous coding.
- [ ] No claim of daemon/VPS/background runtime.
- [ ] No claim of browser automation.
- [ ] No voice/Jarvis positioning as current capability.
- [ ] No deploy/publish/push automation claim.
- [ ] No implication that local validation proves production readiness.
- [ ] No uncontrolled self-modification claim.

## Academic-Language Smell

- [ ] QUBO/Pareto appear only after practical value is clear.
- [ ] "Optimization-first" is technical spine, not public headline.
- [ ] "Agent OS" is not the only explanation.
- [ ] "Decision traces" are explained as inspectable records, not mystique.
- [ ] Internal abstractions do not crowd out the user benefit.

## Working Demo

- [ ] There are 2-3 simple start commands near the top.
- [ ] The current loop is visible:

```text
context -> plan -> patch -> validate -> outcome -> memory
```

- [ ] `heph ask` or `uv run heph ask` appears.
- [ ] `heph validate run . --yes` or the `uv run` equivalent appears.
- [ ] `heph code run ... --dry-run` appears.
- [ ] Advanced release planning commands are lower down.

## Honest Status

- [ ] "What works today" is present.
- [ ] "What Hephaestus is not yet" is present.
- [ ] Repo-aware coding is described as small/scoped.
- [ ] Validation is described as real local evidence, not a guarantee.
- [ ] Learning is described as outcomes, memory, and reviewable signals.
- [ ] Future phases do not sound already shipped.

## Reason To Care

- [ ] The README gives a simple reason to care before architecture details.
- [ ] It explains why local memory matters.
- [ ] It explains why validation evidence matters.
- [ ] It explains how outcomes improve future work.
- [ ] It answers "Why not just ChatGPT or Claude Code?"
- [ ] It explains why this is not just Hermes.
- [ ] It distinguishes public promise from technical spine.
- [ ] It avoids attacking competitors.
- [ ] It avoids claiming maturity that does not exist yet.

## Link And Asset Check

- [ ] Image paths render from GitHub.
- [ ] New docs are linked from README if they are public-facing.
- [ ] No stale links point to removed sections.
- [ ] Launch notes, reveal strategy, demo script, and roadmap tell the same
  story.
