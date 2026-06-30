# Reveal Strategy

## Reveal Goal

Make early technical observers think:

```text
This is early, but real.
This is useful before it is fully autonomous.
I want to follow where this goes.
```

The reveal is not a launch campaign. It is a build-in-public start: show the
working local loop, invite practical feedback, and set honest boundaries.

## Target Audiences

- Open-source AI tool builders.
- Devtools engineers.
- Agent framework watchers.
- Local AI and infra tinkerers.
- Engineers interested in memory, validation, explainability, and safety.

## Emphasize

- Model-agnostic intelligence harness for checked AI work.
- Persistent project and conversation memory.
- Help with thinking, planning, and scoped repo work.
- Repo inspection before code changes.
- Patch proposals before apply.
- Approved patch application with checkpoints.
- Real local validation evidence.
- One bounded validation-coupled repair path.
- Outcome records and reviewable learning signals.
- Harness gain: same model raw versus same model with Hephaestus.
- Honest alpha boundary: local-first, scoped, and approval-gated.

## Keep Technical But Lower

- Decision traces with selected and rejected options.
- Pareto tradeoffs instead of a hidden single score.
- QUBO as inspectable binary optimization, solved locally.
- Policy profiles for user-owned execution boundaries.
- Model routing and context packing.
- Experience governance, reward models, CPU controller learning, and adapters
  as future/planned/research work, not current product claims.

These are advanced engine details. They are useful proof for technical readers,
but they should not be the first sentence of the reveal.

## Avoid Emphasizing

- Voice, Jarvis, Telegram, dashboard, daemon, browser automation, or broad
  autonomous editing.
- Claims that Hephaestus can handle large unbounded repo rewrites.
- Claims that local validation proves production readiness.
- Claims that outcome learning means model weights are being trained.
- Claims that reward models, LoRA, DPO, SFT, distillation, CPU-trained
  controller policies, or community/global learning are implemented.
- Claims that weak models always beat strong models.
- Quantum hardware claims or quantum speedup language.
- Star-bait, hype language, or "AGI" framing.
- Broad promises about replacing mature coding agents.

## Likely Objections

### Why not just use ChatGPT or Claude Code?

Use them. They are excellent models and coding tools.

Hephaestus is different because it wraps model calls inside a local agent loop:

```text
context -> planning -> tools -> validation -> repair -> outcome evidence -> learning
```

The goal is not to replace the model. The goal is to make the harness around
the model remember, verify, recover, and improve.

### Is this a coding agent yet?

Partly, in a deliberately bounded way.

Hephaestus can plan a scoped repo change, propose a patch, apply an approved
patch with a checkpoint, run real validation, and record outcomes. It is meant
for small docs, tests, config/help text, and clear replacement workflows.

It is not a full autonomous coding agent. It does not run unbounded repair
loops, deploy, publish, push, or perform large rewrites on its own.

### Why QUBO?

For complex tradeoffs, Hephaestus can compare options instead of blindly taking
the first plausible path.

QUBO is one optional advanced representation for some binary decision problems:
variables, objective terms, constraints, assignments, and score. It is local
classical solving. It is not a quantum hardware claim.

### Is this real or just architecture theater?

What is real today:

- persistent conversations,
- strategic memory,
- local repo inspection,
- safe local tools,
- patch proposals,
- checkpointed approved patch application,
- real validation execution,
- validation-coupled repair,
- validation evidence,
- outcomes and learning signals,
- release planning with validation links,
- local Studio Chat, Workbench, Memory, Settings, provider settings, and data
  backup/export/restore,
- CLI commands that save and inspect artifacts.

What is not real yet:

- full autonomous coding,
- unbounded multi-file self-editing,
- deploy or publish execution,
- production sandboxing,
- daemon/VPS runtime,
- browser automation,
- voice.

Early versions were planning-heavy. The current reveal should show the working
loop first, then explain the architecture.

### What actually works today?

Good starting commands:

```bash
heph ask "What is this project trying to become?"
heph validate run . --yes
heph code run "Update README wording to mention validation-backed release evidence." --repo . --dry-run
```

Advanced release evidence:

```bash
heph release plan . --pareto --qubo --with-validation --yes
```

### Why should people follow now?

Because the early shape is clear: a local agent system that treats memory,
validation evidence, and outcomes as part of the product rather than as hidden
implementation details.

The long-term shape is also clear: governed experience records, project and
personal intelligence, CPU-trained controller policies, skill distillation, and
model adaptation research behind verifier and promotion gates.

The project is early enough for feedback to matter, but real enough to inspect.

## Tone

Use:

- precise,
- calm,
- practical,
- build-in-public,
- honest about limitations.

Avoid:

- "please star",
- "revolutionary",
- "fully autonomous",
- "quantum-powered",
- "Jarvis",
- "soon it will do everything".
