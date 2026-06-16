# Product Positioning

## Public Promise

```text
Hephaestus is a self-improving AI agent for people building ambitious things.
It remembers your context, helps you think, helps you code, validates its work,
and improves from real outcomes.
```

This is the public-facing identity. It should appear before advanced internals.

## Target Users

- Builders working on ambitious software projects.
- Open-source maintainers who want local project memory and validation evidence.
- Devtool and agent-runtime people who care about inspectable agent behavior.
- Technical founders or solo builders who need strategy, coding help, and
  continuity across sessions.
- Researchers and tinkerers who want to inspect how agent decisions are made.

## Feature Hierarchy

### Layer 1: Emotional/Public Promise

- You can talk to it.
- It remembers.
- It helps you think.
- It can work on your repo.
- It validates what happened.
- It gets less forgetful over time.

### Layer 2: Practical Capabilities

- Persistent conversations.
- Studio persistent chat for reopening exact message history.
- Strategic memory.
- Repo inspection.
- Safe local tools.
- Patch proposals.
- Approved patch apply with checkpoints.
- Real validation execution.
- Outcomes and learning signals.

### Layer 3: Developer Workflow

```text
context -> plan -> patch -> validate -> outcome -> memory
```

Example commands:

```bash
heph studio
heph ask "What is this project trying to become?"
heph validate run . --yes
heph code run "Update README wording to mention validation-backed release evidence." --repo . --dry-run
```

### Layer 4: Advanced Internals

- Decision traces.
- Pareto frontiers.
- QUBO/Ising formulations.
- Policy profiles.
- Strategic memory.
- Model routing.
- Context packing.

These are proof points for technical users. They should support the practical
story rather than replace it.

## What To Say

- Hephaestus is early, local-first, scoped, and approval-gated.
- It is useful today for conversation memory, repo inspection, validation, and
  small scoped coding loops.
- Learning means outcome-based memory, reviewable signals, and future
  capability improvements with evidence.
- Local validation is real evidence, not a production guarantee.
- The advanced engine exists to make tradeoffs inspectable.

## What Not To Say

- Do not lead with "optimization-first agent OS."
- Do not make QUBO/Pareto the headline.
- Do not imply full autonomous coding.
- Do not imply daemon/VPS, browser automation, voice, deploy, publish, or push
  support exists today.
- Do not imply Studio already has full coding-loop, validation, approval,
  checkpoint, outcome, Pareto, or QUBO workbench views. Phase 5.5A is persistent
  chat first.
- Do not describe learning as model weight training.
- Do not imply local validation proves external release safety.
- Do not call it a replacement for mature coding tools.

## Internal vs External Language

| External | Internal / Advanced |
|---|---|
| remembers context | memory store, strategic memory, recall events |
| helps you think | deliberation modes, discussion quality rubrics |
| helps you code | repo-aware coding loop, patch proposal, patch review |
| validates work | validation planner, safe tool runtime, evidence mode |
| improves from outcomes | outcomes, reflections, learning signals |
| compares tradeoffs | Pareto frontier, objective scoring |
| inspectable decisions | decision traces, selected/rejected alternatives |
| scoped local approval | policy profiles, safety decisions, checkpoints |
| advanced optimization | QUBO/Ising formulation, local solver |

Studio copy should stay especially concrete:

```text
Open yesterday's conversation.
Read the original messages.
Continue where you stopped.
```

Do not describe Studio continuity as automatic summarization. The current
product mechanism is exact persisted messages, searchable history, and normal
continuation through the same conversation system.

Use the external term first. Add the internal term only when the reader needs
implementation detail.

## Relationship to Hermes

Hephaestus should learn from Hermes. Hermes showed that people want agents that
remember them, grow with them, and carry work forward instead of starting from
zero every session.

Do not position Hephaestus as a cheap clone or a rival to dunk on. The shared
ambition is self-improving agency. The differentiator is the center of gravity:
Hephaestus is about evidence-backed work.

Use this line when the comparison needs to be direct:

```text
Hermes learns workflows.
Hephaestus learns why workflows succeed, then forges better ones.
```

Public messaging can lead with companion-like self-improvement, but it must
quickly show the evidence-backed loop:

```text
repo context -> scoped patch -> checkpoint -> validation -> outcome -> learning
```

That is the distinction: repo-aware coding, validation-backed work, checkpoints,
outcome learning, and decision-quality improvement. Hephaestus is still early
and should not claim full always-on companion maturity yet.

## Explaining QUBO/Pareto Without Looking Ridiculous

Say:

```text
For complex tradeoffs, Hephaestus can compare options instead of blindly taking
the first plausible path.
```

Then explain:

- Pareto shows tradeoffs across objectives such as quality, cost, latency, risk,
  privacy, safety, and profile alignment.
- QUBO encodes some choices as local binary optimization problems with visible
  variables, terms, constraints, and assignments.
- Both are optional advanced inspection tools.
- QUBO is local classical solving, not a quantum hardware claim.

Do not say:

- "Quantum-powered."
- "Revolutionary optimizer."
- "Solves agent autonomy."
- "The QUBO layer is the product."

## Answering Criticism

### "Is this architecture theater?"

Calm answer:

```text
Early versions were planning-heavy. The current alpha now has real local
validation and a repo-aware coding loop for small scoped changes. Evidence can
come from actual commands, not only simulated outcomes. The internals exist to
support practical behavior: remember context, propose scoped work, validate it,
record what happened, and improve the next loop.
```

### "Why not just ChatGPT or Claude Code?"

```text
Use them. They are excellent models and coding tools.

Hephaestus wraps model calls inside a local agent loop:
context -> plan -> patch -> validate -> outcome -> memory.

The goal is not to replace the model. The goal is to make the agent around the
model remember, verify, and improve.
```

### "Is it autonomous?"

```text
No, not fully. It has a bounded repo-aware coding loop for small scoped changes,
with approval gates, checkpoints, validation, and outcomes. It does not run as a
daemon, push code, deploy, or perform unbounded rewrites.
```

### "Does it really learn?"

```text
Learning means persisted outcomes, reflections, reviewable learning signals,
memory updates, and future capability proposals. It does not mean hidden model
weight training or uncontrolled self-modification.
```

## One-Sentence Versions

Short:

```text
Hephaestus is a self-improving AI agent that remembers context, helps you think
and code, validates work, and improves from outcomes.
```

Practical:

```text
Hephaestus wraps AI conversations and coding help in a local loop: context,
plan, patch, validation, outcome, and memory.
```

Technical:

```text
Hephaestus is a local-first agent runtime with persistent memory, safe tools,
repo-aware coding loops, validation evidence, decision traces, tradeoff
analysis, and outcome-based learning.
```
