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

### Policy Profiles

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

## Upcoming

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

### Strategy and Research Deliberation Modes

- Add deliberation modes for uncertain planning and research-heavy decisions.
- Make assumptions, alternatives, and uncertainty explicit.
- Preserve the same trace/outcome/learning architecture.

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
