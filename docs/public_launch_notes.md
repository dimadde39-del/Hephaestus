# Public Launch Notes

These are soft reveal drafts, not a big launch campaign. The goal is to attract
early watchers, get practical feedback, and make people want to follow updates
as the system matures.

## Positioning Guardrails

- Lead with Hephaestus as a model-agnostic intelligence harness.
- Explain the loop: context, planning, tools, validation, repair, outcome
  evidence, and learning.
- Show working commands before advanced internals.
- Use status labels: Built, Partially built, Planned, Research.
- Do not imply full autonomy, background daemon behavior, deploy/publish/push,
  browser automation, voice, production readiness, or uncontrolled
  self-modification.
- Describe current learning as outcome-based memory, reviewable signals,
  policy profiles, validation evidence, and governed future capability work.
- Do not imply reward models, LoRA, DPO, SFT, distillation, CPU-trained
  controller policies, or community/global learning are implemented.
- Keep Pareto, QUBO, decision traces, and policy profiles visible as advanced
  machinery, not the headline.

## X / Twitter Soft Reveal

### Short Post

```text
Soft reveal: I am building Hephaestus, a model-agnostic intelligence harness.

The model supplies raw potential. Hephaestus wraps it with context, planning, tools, validation, repair, outcome evidence, and learning.

Built today: local memory, repo inspection, validation, scoped coding loops, Studio, and evidence records.

Early alpha. Local-first. Approval-gated. Not a full autonomous daemon.
```

### Thread Version

```text
1/ I am starting a soft reveal for Hephaestus: a model-agnostic intelligence harness for checked AI work.

The practical idea:

same model raw
vs
same model with context, tools, validation, repair, and outcome evidence.

2/ What works today:

- persistent conversations
- strategic/project memory
- repo inspection
- safe local tools
- real validation execution
- scoped coding loops
- provider-backed greenfield manifests
- one bounded validation repair path
- local Studio: Chat, Workbench, Memory, Settings
- outcomes and learning signals

3/ What is not built:

- full autonomous coding
- daemon/VPS runtime
- browser automation
- voice
- deploy/publish/push automation
- reward models as authorities
- LoRA/DPO/SFT/distillation/adapters
- CPU-trained adaptive controller policies
- global/community learning

4/ A few commands:

heph ask "What is this project trying to become?" --repo .
heph validate run . --yes
heph code run "Update README wording to mention validation-backed evidence." --repo . --dry-run
heph studio

5/ Under the hood there are decision traces, Pareto tradeoffs, QUBO formulations, policy profiles, model metadata, and validation evidence.

That machinery supports the harness. It is not the public claim by itself.

6/ The long-term roadmap is governed learning:

Context Forge, Experience Ledger, capability lifecycle, CPU controller learning, skill distillation, reward/model adaptation research, SWE-RL research, and opt-in community/global learning.

7/ I am looking for practical feedback:

What should a local agent remember, verify, and show before you trust it with more autonomy?
```

## Reddit Feedback Post

### Title

```text
I am building a local model-agnostic intelligence harness and would like feedback
```

### Body

```text
I am working on Hephaestus, an early local-first intelligence harness for people building ambitious software projects.

The product goal is not to be a bigger model. It is to improve the loop around the model:

context -> planning -> tools -> validation -> repair -> outcome evidence -> learning

The benchmark I care about is same model raw versus same model with Hephaestus.

What works today:

- persistent conversations
- strategic/project memory
- repo inspection
- scoped patch proposals
- approved patch application with checkpoints
- real local validation execution
- provider-backed greenfield manifests
- one bounded validation-coupled repair path
- rollback cleanup and opt-in failed-workspace snapshots
- Studio Chat, Workbench, Memory, Settings, provider settings, backup/export
- outcomes and learning signals

Try:

heph ask "What is this project trying to become?" --repo .
heph validate run . --yes
heph code run "Update README wording to mention validation-backed evidence." --repo . --dry-run

What it does not do yet:

- full autonomous coding
- large unbounded repo rewrites
- deploy/publish/push execution
- run as a daemon
- browser automation
- voice features
- model-weight training
- reward models as success authorities
- global/community learning

Under the hood, Hephaestus has decision traces, Pareto tradeoff comparison, QUBO/Ising formulations, policy profiles, model metadata, and strategic memory. Those are advanced internals, not the headline. QUBO is local classical optimization over binary variables, not a quantum hardware claim.

I would especially appreciate feedback on:

- whether the current loop is understandable,
- whether the limitations are clear,
- what evidence a local agent should keep after it changes files,
- what would make this worth following as an open-source devtool.
```

## Telegram / Discord Community Message

```text
I am starting a soft reveal for Hephaestus, a local model-agnostic intelligence harness.

It wraps a model with project context, planning, safe tools, validation, bounded repair, outcome evidence, and learning signals.

Current alpha: persistent memory, repo inspection, validation, scoped coding loops, greenfield manifests, Studio, and evidence records.

Still not a full autonomous daemon, deployer, browser agent, voice assistant, reward model system, or model-training lab.

The question I am looking for feedback on:

What should a local agent remember and verify before you trust it with more autonomy?
```

## GitHub Discussion Draft

```text
Title: Soft reveal: Hephaestus public alpha direction

Hephaestus is a model-agnostic intelligence harness.

It turns a model's raw potential into checked work through context, planning, tools, validation, repair, outcome evidence, and learning.

The current public alpha is intentionally scoped and local-first. It can inspect a repo, keep persistent conversations and strategic memory, propose small patches, apply approved changes with checkpoints, run real validation, attempt one bounded validation-coupled repair, roll back failed changes, show evidence in Studio, and record outcomes/learning signals.

It does not do full autonomous coding, deploy, publish, push, run as a daemon, automate browsers, use voice, train model weights, or claim production autonomy.

Good starting commands:

heph ask "What is this project trying to become?" --repo .
heph validate run . --yes
heph code run "Update README wording to mention validation-backed evidence." --repo . --dry-run
heph studio

I am opening this discussion for product, architecture, and positioning feedback. The most useful feedback would be around:

- whether the current loop is clear,
- whether the alpha boundary is trustworthy,
- what validation evidence should be shown first,
- what project memory should feel like in Studio,
- where the roadmap overpromises or underspecifies the hard parts.
```

## Follow-Up Angles

- Why harness gain should compare the same model raw versus the same model with
  context, tools, validation, and recovery.
- Why local project memory changes the feel of AI tooling.
- What validation evidence an agent should keep after a change.
- Why small scoped coding loops are the right alpha boundary.
- How outcome-based learning differs from vague "the model learns" claims.
- Why deterministic verification and reward models must stay separate.
- Why Pareto/QUBO belong under the hood, not in the headline.
- Why Studio evidence should come before always-on autonomy.
