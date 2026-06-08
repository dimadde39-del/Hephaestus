# Reveal Strategy

## Reveal Goal

Make early technical observers think:

```text
This is early, but real.
This is different from generic agent wrappers.
I want to follow where this goes.
```

The reveal is not a launch campaign. It is a build-in-public start: show the
working planning loop, invite architecture feedback, and set honest boundaries.

## Target Audiences

- Open-source AI tool builders.
- Devtools engineers.
- Agent framework watchers.
- LocalLLaMA and infra tinkerers.
- Engineers interested in explainability, optimization, and safety.

## Emphasize

- Optimization-first agent OS.
- Planning before action.
- Read-only repo inspection.
- Release-readiness planning without command execution.
- Pareto tradeoffs instead of a hidden single score.
- QUBO as inspectable binary optimization, solved locally.
- Decision traces with selected and rejected options.
- Learning signals that stay reviewable before they influence future behavior.
- Honest alpha boundary: local-first and planning-only.

## Avoid Emphasizing

- Voice, Jarvis, Telegram, dashboard, daemon, browser automation, or autonomous
  editing.
- Claims that the system executes validation commands.
- Claims that simulated outcomes prove real tests or builds passed.
- Quantum hardware claims or quantum speedup language.
- Star-bait, hype language, or "AGI" framing.
- Broad promises about replacing coding agents.

## Likely Objections

### Why not just use Hermes?

Hermes and Hephaestus have different jobs.

```text
Hermes learns workflows.
Hephaestus learns decision quality.
```

Hermes is about carrying work through repeatable workflows. Hephaestus is about
making the decision surface inspectable before an agent acts: options,
constraints, tradeoffs, rationale, outcomes, and learning signals.

### Is this a coding agent yet?

No. The current alpha is planning-only. It can inspect a repo, generate
release-readiness tasks, optimize the plan, expose Pareto/QUBO artifacts,
explain decisions, and simulate outcome learning. It does not autonomously edit
code or execute repository commands.

That boundary is intentional. The next serious feature area is safe validation
execution, not broad autonomy.

### Why QUBO?

QUBO is useful here because it turns some choices into inspectable binary
decision problems: variables, objective terms, constraints, assignments, and
energy. It is a way to make decision quality concrete and auditable.

This is local classical solving. It is not a quantum hardware claim.

### Is this real or just architecture theater?

What is real today:

- local repo inspection,
- persisted repo profiles,
- generated release tasks,
- optimizer runs,
- Pareto frontiers,
- QUBO formulations and local solutions,
- decision traces,
- deterministic simulated outcomes,
- learning signals and profile suggestions,
- CLI commands that save and inspect artifacts.

What is not real yet:

- autonomous code edits,
- validation command execution,
- deploy or publish execution,
- production sandboxing,
- dashboard,
- daemon,
- voice or chat interface.

The reveal should show the working CLI first, then the architecture.

### What actually works today?

The demo command works locally:

```bash
uv run heph release plan . --pareto --qubo --evaluate
```

It inspects this repository, plans release-readiness work, compares tradeoffs,
formulates QUBO problems, explains the optimizer run, persists artifacts, and
creates simulated learning signals.

### Why should people follow now?

Because the early shape is clear and unusual: an agent system that treats
decision quality as the product, not a hidden implementation detail. The project
is early enough for feedback to matter, but real enough to inspect.

## Tone

Use:

- precise,
- calm,
- build-in-public,
- architecture-feedback oriented,
- honest about limitations.

Avoid:

- "please star",
- "revolutionary",
- "fully autonomous",
- "quantum-powered",
- "Jarvis",
- "soon it will do everything".
