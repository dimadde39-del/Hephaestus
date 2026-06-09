# Roadmap

Hephaestus is building toward an optimization-first agent OS: local-first,
explainable, memory-backed, and careful about execution. The public alpha goal
is not to look autonomous before the core is ready. It is to make decision
quality understandable.

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

## Upcoming

### Phase 5F: Real Validation Execution + Outcome Learning

- Execute repo validation plans through the Phase 5E runtime.
- Convert real command results into outcome records.
- Update learning signals from repeated validation failures.
- Make release planning evidence-based rather than simulated.
- Keep deploy, publish, destructive, and external-side-effect commands gated.

### Soft Reveal Execution

- Post the first X/Twitter soft reveal.
- Prepare one Reddit feedback post.
- Prepare one or two Telegram/Discord community messages.
- Observe responses and repeated objections.
- Gather feedback into roadmap notes before the larger public alpha push.

### Safe Validation Execution

- Execute only approved low-risk validation commands.
- Capture command output, exit codes, duration, and environment constraints.
- Store real validation outcomes against decision traces.
- Keep deploy, publish, destructive, and external side-effect commands gated.

### Repo-Aware Outcome Learning From Real Commands

- Turn real validation results into outcome records.
- Connect failures back to decision traces and repo profiles.
- Improve learning signals with command evidence.
- Keep policy/profile updates reviewable before activation.

### Dashboard Later

- Local web dashboard for decision traces, Pareto frontiers, QUBO problems,
  memories, approvals, and run history.
- Not part of the current alpha.

### Voice Much Later

- Voice/Jarvis-style features are intentionally deferred until the decision
  core, execution safety, and learning loop are mature.

## Deferred On Purpose

- Autonomous code editing.
- Always-on daemon behavior.
- Browser or desktop automation.
- Telegram bot integrations.
- Dashboard-first product work.
- Random integrations that do not improve decision quality.

The current priority is clear: core decision quality, repo-aware planning,
explainability, learning memory, and safe execution later.
