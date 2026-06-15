# Roadmap

Hephaestus is building toward a self-improving local AI agent for people
building ambitious things: memory-backed, repo-aware, validation-aware, and
careful about execution. The public alpha goal is not to look autonomous before
the core is ready. It is to make the working loop understandable:

```text
context -> plan -> patch -> validate -> outcome -> memory
```

Optimization, decision traces, Pareto, and QUBO remain part of the technical
spine, but they are not the public headline.

## Current Sequence

- Phase 5G.5: README Reality / Product Positioning Pass.
- Phase 5.5: Hephaestus Studio / Persistent Interface Layer.
- Phase 6A: Personal Context + Project Memory UX.
- Phase 6B: Skill Forge.
- Phase 6C: Skill Evaluation + Quarantine.
- Phase 6D: Adaptive Work Router / Model Economy.
- Phase 6E: Capability Gap Detector.
- Phase 6F: Capability Forge.
- Phase 7: Always-On Runtime / VPS / Telegram / async work.

Phase 5.5 is mandatory before Phase 6. Persistent readable chat history and
run history must come before broader skill and autonomy work.

## Complete

### Foundation

- Python 3.12 package managed with `uv`.
- Pydantic v2 schemas.
- Typer/Rich CLI.
- Deterministic spec pipeline.
- Task graph generation and optimizer-compatible tasks.
- Memory store and model provider interface.
- Fake local models and optional DeepSeek provider.
- Safety and tool schemas.

### Persistence

- SQLite database initialization and migrations.
- Persistent memories.
- Run history, run tasks, decisions, and approvals.
- Local state in `.hephaestus/hephaestus.db`.

### Benchmark Reports

- Benchmark fixtures for designed optimizer pressure cases.
- Greedy and simulated annealing comparisons.
- Model routing, context packing, token budget, and approval-gate reporting.
- Persisted benchmark runs.

### Decision Traces

- First-class decision trace records.
- Trace rendering through `heph explain <run_id>`.
- Aggregate explanation stats.
- Structured selected/rejected alternatives, metrics, confidence, and rationale.

### Outcome Learning

- Outcome records linked to decision traces.
- Deterministic reflections.
- Learning signals.
- Failure memory drafts.
- Policy update suggestions kept as reviewable artifacts.

### Decision Quality Profiles

- Decision quality profile suggestions.
- Explicit activation and archive commands.
- Profile application records.
- Active profiles can bias future model routing, context packing, token
  firewall, scheduler, and safety behavior.

### Pareto Frontier

- Multi-objective candidates for model routing, context packing, and scheduler
  choices.
- Built-in preference profiles such as `balanced`, `frugal`, `quality_first`,
  `privacy_first`, `safety_first`, and `speed_first`.
- Persisted frontiers and selections.
- CLI list/show/compare commands.

### QUBO and Ising

- QUBO schemas for variables, terms, constraints, objectives, problems, and
  solutions.
- Context packing, model selection, budget strategy, and task-ordering demo
  formulations.
- Local exhaustive, greedy, and seeded annealing solvers.
- QUBO to Ising conversion.
- CLI formulation, solve, list, show, compare, and convert commands.

### Repo Intelligence

- Read-only local repository inspection.
- Detection for Python, Node/TypeScript/JavaScript, Rust, Go, Docker, GitHub
  Actions, and GitLab CI signals.
- Package manager, script, validation command, env-file, and risk signals.
- Safe command classification.
- Repo-aware release-readiness task generation.
- Benchmark export from real repo profiles.

### Release Planning Demo

- `heph release plan/list/show`.
- End-to-end local demo:

```text
Repo Inspect -> Repo Plan -> Optimize -> Pareto -> QUBO -> Explain -> Evaluate -> Learn
```

- Release plans link repo profiles, optimizer runs, decision traces, Pareto
  frontiers, QUBO problems, simulated outcomes, and learning signals.
- Execution remains deferred: validation, deploy, publish, destructive, and
  external side-effect commands are not run.

### Public Alpha Readiness Polish

- README hero rewritten around a 30-second public explanation.
- Demo-first quickstart and walkthrough.
- Contributor guide and issue templates.
- Public roadmap cleanup.
- Brand and mascot direction.
- Soft reveal launch copy drafts.
- GitHub metadata suggestions.

### Phase 4D: Soft Reveal Pack

- Polished screenshots of the current CLI demo.
- Demo screenshot pack linked from README and walkthrough docs.
- One-minute demo script.
- Terminal recording plan.
- Final first posts for X/Twitter, Reddit, Telegram/Discord, and GitHub
  Discussions.
- Reveal strategy notes and launch checklist.
- GitHub setup guidance tied to the actual brand and demo assets.

### Phase 5A: Conversational Agent Interface

- `heph ask`, `heph discuss`, and `heph chat`.
- Persisted conversation sessions, messages, and memory update suggestions.
- Intent classification for repo questions, architecture, product strategy,
  business strategy, stress tests, roadmap decisions, research planning, risk,
  personal context, and debugging discussions.
- Deliberation modes: balanced, direct, critical, strategic, research,
  architect, coach, and skeptical-but-fair.
- Internal deliberation passes without multi-process agent swarms.
- Memory retrieval and conservative memory update suggestions.
- Optional repo context through `--repo` using read-only repo profiles.
- High-impact discussion traces linked to the decision engine.
- Fake/local deterministic mode when no real provider is configured.

### Phase 5B: Strategic Memory + Research/Discussion Quality Framework

- Strategic memory package for goals, ambitions, constraints, fears, risk
  patterns, preferences, principles, strategic decisions, roadmap decisions,
  positioning decisions, launch decisions, business assumptions, technical
  assumptions, rejected paths, lessons learned, and open questions.
- SQLite persistence for strategic memories, simple conflicts, and recall
  events.
- `heph strategy memory add/list/search/show/archive` and `heph strategy context`.
- Conversation recall of strategic memory for strategy, architecture, research,
  roadmap, and risk discussions.
- Save-controlled strategic memory suggestions through `--save-memory`,
  `--save-strategy`, and chat `/save-memory`.
- Discussion-quality rubrics for idea stress tests, business strategy, product
  strategy, technical architecture, roadmap decisions, research planning, and
  risk analysis.
- Research planning mode that prepares verification without pretending live web
  research has happened.
- High-impact traces enriched with assumptions, options, recommendation,
  confidence, memory used, strategic memories suggested, and rubric metadata.

### Phase 5C: Real Model Provider Conversation Quality

- Conversation provider routing across deterministic local mode, DeepSeek, and
  OpenAI-compatible APIs.
- OpenRouter-compatible usage through the OpenAI-compatible path.
- Conversation model profile metadata for JSON, streaming, context windows,
  cost estimates, and intended roles.
- Prompt assembly with behavior/policy standards, mode guidance, rubrics,
  strategic memory, repo context, session context, regular memory, and explicit
  fact/assumption/recommendation separation.
- One-call model-backed final synthesis when real providers are configured and
  selected.
- Token/context budget reports and deterministic context trimming.
- Conversation quality benchmark fixtures and deterministic evaluator package.
- `heph conversation benchmark list/run`.
- Improved memory candidate summaries and stability labels.

### Phase 5D: User-Owned Freedom / Policy Profiles

- First-class `hephaestus.policy` package with schemas, built-in profiles,
  deterministic classifier/evaluator, repository, renderer, and analysis
  helpers.
- Built-in profiles: `balanced`, `developer`, `research`, `local_power_user`,
  `strict`, and schema support for `custom`.
- SQLite active policy profile state, custom profile storage, and transparent
  policy evaluation history.
- `heph policy profiles/active/set/show/evaluate`.
- `heph policy benchmark list/run`.
- Conversation prompt integration with active profile name, decision, refusal
  style, benign-work philosophy, and over-refusal detection.
- Concise blocking for genuinely harmful requests and approval boundaries for
  destructive/local/external side effects.
- Documentation for user-owned freedom and policy profiles.

### Phase 5E: Safe Tool Execution Runtime

- First-class `hephaestus.tool_runtime` package with schemas, classifier,
  approvals, filesystem tools, shell runtime, patch proposals, checkpoints,
  SQLite repository, renderers, and analysis helpers.
- SQLite tool tables for actions, approvals, results, observations, and
  checkpoints.
- `heph tools list/read/search/run`, `heph tools patch propose/apply`,
  `heph tools actions`, `heph tools action show`, and
  `heph tools checkpoint list/show/restore`.
- Protected file detection for `.env`, credential, token, private-key, and SSH
  key material.
- Dry-run command planning, risk classification, approval gates, stdout/stderr
  capture, timeouts, output truncation, and observations.
- Checkpoint creation before patch application and restore for files changed by
  Hephaestus.
- Policy-profile-aware execution decisions and reuse of repo command risk
  classification.
- Minimal decision trace and outcome links for important tool actions.
- `--propose-tools` on `heph ask` and `heph discuss` for manual next-step plans
  without chat auto-execution.

### Phase 5F: Real Validation Execution + Outcome Learning

- First-class `hephaestus.validation` package with schemas, planner, executor,
  evaluator, repository, renderer, and analysis helpers.
- SQLite tables for validation plans, commands, suite results, evidence, and
  release validation summaries.
- `heph validate plan/run/results/show/latest`.
- Repo-derived validation command detection for lint, test, typecheck, build,
  format-check, security-check, and custom validation commands.
- Approved execution through the Phase 5E safe tool runtime with stdout/stderr
  summaries, exit codes, durations, timeouts, and approval-required states.
- Per-command validation outcomes, validation strategy learning signals, and
  repeated-failure memory drafts.
- Release planning integration through `heph release plan . --with-validation --yes`.
- Evidence mode labels for simulated outcome evaluation, real validation
  evidence, dry-run, and approval-gated execution.
- Conversation tool proposals now suggest `heph validate plan`, dry-run, and
  approved validation commands without auto-running them.

### Phase 5G: Repo-Aware Coding Loop

- First-class `hephaestus.coding_loop` package with schemas, planner, patcher,
  reviewer, executor, repository, renderers, and analysis helpers.
- SQLite tables for coding requests, plans, changes, iterations, and results.
- `heph code plan/propose/apply/run/results/show`.
- Repo-aware planning over repo intelligence, validation plans, active policy
  profile, and strategic memory recall.
- Deterministic single-file patch proposals for small docs/tests/config/help
  text and exact replacement workflows.
- Lightweight patch review for request match, expected files, protected files,
  scope drift, obvious secrets, and validation availability.
- Approved patch application through the safe tool runtime with checkpoint
  creation.
- Validation through Phase 5F after apply, with validation result links.
- Optional checkpoint restore with `--rollback-on-failure`.
- Coding-loop decision traces, outcomes, and learning signals for scope blocks,
  patch proposals, apply decisions, validation, rollback, and final result.
- `--propose-code` on `heph ask`, `heph discuss`, and `heph chat`; chat also
  supports `/propose-code <request>`.
- Still bounded: no daemon, no deploy/publish/push, no destructive actions, no
  dependency installs without explicit approval, and no unbounded repair loop.

### Phase 5G.5: README Reality / Product Positioning Pass

- Public README repositioned around self-improving agent value: memory,
  thinking, coding, validation, outcomes, and project continuity.
- What works today and what is not built yet are stated near the top.
- Practical commands and the current coding/validation loop are shown before
  advanced engine internals.
- QUBO, Pareto, decision traces, policy profiles, strategic memory, and model
  routing are described as advanced machinery, not the primary pitch.
- Public launch notes, reveal strategy, demo script, brand docs, freedom/policy
  docs, and GitHub-facing setup notes align around the same message.
- Product positioning and README reality checklist docs capture the new rules.

## Upcoming

### Phase 5.5: Hephaestus Studio / Persistent Interface Layer

- Beautiful persistent interface for readable chat history, run history,
  coding-loop results, validation evidence, outcomes, checkpoints, approvals,
  decision traces, and advanced Pareto/QUBO views.
- Core principle: persistent readable chat history, not automatic context
  summaries. Users should be able to open the same chat tomorrow, read exact
  previous messages, inspect runs visually, and continue naturally.
- This interface layer is mandatory before Phase 6.

### Phase 6A: Personal Context + Project Memory UX

- Make user/project memory visible, editable, searchable, and reviewable in
  Studio.
- Separate exact chat history, saved memories, strategic memories, outcomes, and
  learning signals.
- Let users inspect why context was recalled instead of relying on opaque
  summaries.

### Phase 6B: Skill Forge

- Add a user-approved workflow for creating reusable local skills from repeated
  project work.
- Keep skill creation evidence-backed: source runs, validation, examples, and
  approval history should be inspectable.

### Phase 6C: Skill Evaluation + Quarantine

- Evaluate skills against deterministic fixtures and real validation where
  possible.
- Quarantine weak, risky, stale, or failing skills before they influence future
  work.

### Phase 6D: Adaptive Work Router / Model Economy

- Route tasks across local deterministic behavior and configured model
  providers based on cost, risk, context size, quality needs, and policy.
- Make routing decisions explainable and measurable.

### Phase 6E: Capability Gap Detector

- Detect repeated failure patterns, missing skills, missing context, weak
  validation coverage, and tool gaps.
- Turn gaps into reviewable improvement proposals, not automatic self-edits.

### Phase 6F: Capability Forge

- Convert approved capability proposals into bounded improvements with
  checkpoints, validation, and rollback.
- Keep self-improvement evidence-based and reversible.

### Phase 7: Always-On Runtime / VPS / Telegram / Async Work

- Introduce long-running or remote execution only after Studio, memory UX,
  skills, evaluation, quarantine, and capability governance exist.
- Explore VPS, Telegram, async work queues, and background tasks with explicit
  user controls.
- Do not make always-on autonomy the public promise before it has trustworthy
  visibility and approval surfaces.

### Soft Reveal Execution

- Post the first X/Twitter soft reveal.
- Prepare one Reddit feedback post.
- Prepare one or two Telegram/Discord community messages.
- Observe responses and repeated objections.
- Gather feedback into roadmap notes before the larger public alpha push.

### Voice Much Later

- Voice/Jarvis-style features are intentionally deferred until the decision
  core, execution safety, and learning loop are mature.

## Deferred On Purpose

- Fully autonomous code editing.
- Always-on daemon behavior.
- Browser or desktop automation.
- Telegram bot integrations.
- Random integrations that do not improve decision quality.

The current priority is clear: persistent interface, readable history,
validation-backed coding loops, evidence, memory, and careful improvement.
