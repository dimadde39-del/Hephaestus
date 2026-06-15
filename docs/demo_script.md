# 60-90 Second Demo Script

This is the current soft reveal demo path. It should feel calm, concrete, and
honest: early, real, local-first, and intentionally scoped.

## 1. What Hephaestus Is

Say:

```text
Hephaestus is a self-improving AI agent for people building ambitious things.
It remembers project context, helps you think, helps you code, validates its
work, and records outcomes so future runs are less forgetful.
```

Show the README top section.

Time: 8-10 seconds.

## 2. Talk With Project Context

Run:

```bash
uv run heph ask "What is this project trying to become?" --repo .
```

Say:

```text
First, it can talk about the project with local context. Conversations are
persisted, and important goals or decisions can become strategic memory when I
choose to save them.
```

Point at:

- the direct answer,
- any repo context shown,
- budget/context metadata if enabled.

Time: 10-12 seconds.

## 3. Validate Locally

Run:

```bash
uv run heph validate run . --yes
```

Say:

```text
Hephaestus can turn repo signals into a validation plan and run supported local
validation commands through its safe tool runtime. This creates real evidence,
not just a simulated readiness label.
```

Point at:

- validation result ID,
- command statuses,
- evidence mode,
- linked outcomes or traces.

Time: 12-15 seconds.

## 4. Propose A Scoped Change

Run:

```bash
uv run heph code propose "Update README wording to mention validation-backed release evidence." --repo .
```

Say:

```text
For small scoped repo changes, it plans the change, proposes a patch, reviews
the scope, and tells me what approval would be needed before anything is
applied.
```

Point at:

- expected files,
- proposed diff,
- risk/review summary,
- approval requirement.

Time: 12-15 seconds.

## 5. Run The Bounded Coding Loop

Run:

```bash
uv run heph code run "Update README wording to mention validation-backed release evidence." --repo . --dry-run
```

Say:

```text
In dry-run mode, the loop stays non-mutating. With explicit approval, it can
apply a scoped patch, create a checkpoint, run validation, and record outcomes.
It is not an unbounded autonomous coder.
```

Time: 10-12 seconds.

## 6. Inspect Results

Run:

```bash
uv run heph code results
```

Say:

```text
The useful part is the record: request, plan, patch, validation status,
checkpoint, outcome, and learning signals. The system keeps evidence instead of
asking me to trust a chat transcript.
```

Time: 8-10 seconds.

## 7. Optional Advanced Engine

Run only if the audience is technical and there is time:

```bash
uv run heph release plan . --pareto --qubo --with-validation --yes
```

Say:

```text
For deeper release planning, Hephaestus can compare tradeoffs, persist decision
traces, and use Pareto/QUBO internals to make complex choices inspectable. That
engine supports the loop; it is not the headline.
```

Time: 10-15 seconds.

## 8. Honest Close

Say:

```text
What works today is conversation memory, repo inspection, safe local tools, real
validation, small scoped coding loops, outcomes, and learning signals. What is
not built yet is full autonomous coding, daemon mode, Studio UI, browser
automation, voice, or deploy/publish/push execution.

The next phase is a persistent Studio interface: readable chat history, run
history, validation evidence, coding-loop results, checkpoints, and outcomes in
one place.
```

Time: 8-10 seconds.

## Do Not Claim

- Do not claim Hephaestus handles full autonomous coding.
- Do not claim local validation proves production readiness.
- Do not claim deploy/publish/push execution.
- Do not imply QUBO means quantum hardware or quantum speedups.
- Do not describe learning as model weight training.
- Do not mention voice, Jarvis, Telegram, daemon, or browser automation as
  current product features.

## Suggested Sequence

```text
README top
ask with repo context
validate run
code propose
code run --dry-run
code results
optional release plan with Pareto/QUBO
limitations and next phase
```
