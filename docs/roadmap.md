# Roadmap

## v0.1 Core Runtime

- Typed schemas.
- Deterministic spec pipeline.
- Memory repository.
- Fake models.
- Optimizer baselines.
- CLI demo.

## v0.2 Spec / Task Graph

- Richer constraints.
- Task graph validation.
- Generated implementation plans.
- SQLite run history capture.
- Persistent local memory.
- Benchmark fixture preparation.

## v0.3 Quantum Planner Benchmarks

- Benchmark suites for task order and model/context decisions.
- Reporting over `benchmarks/task_graphs/` fixtures.
- Persisted benchmark runs in SQLite run history.
- Explainable decision traces for task selection, model routing, context
  selection, token budgets, safety gates, and optimizer comparisons.
- Outcome tracking and failure-learning foundations.
- Deterministic benchmark outcome evaluation with draft learning artifacts.
- QUBO/Ising formulations.
- Simulated annealing tuning.
- Comparison against greedy and naive baselines.

## v0.4 Policy Learning + Decision Quality Profiles

- Added explicit decision quality profiles for model routing, context packing,
  token firewall, scheduler, safety, memory retrieval, and optimizer decisions.
- Added profile suggestions from accumulated outcomes, reflections, learning
  signals, failure drafts, policy suggestions, and decision traces.
- Added profile activation/archive and profile application records.
- Added profile-aware model routing thresholds, context failure-memory boosts,
  token firewall threshold adjustments, scheduler weight adjustments, and
  safety approval demo behavior.
- Kept policy updates reviewed and non-automatic by default.
- Preserved the loop:

```text
Learning Signal -> Profile Suggestion -> Decision Quality Profile -> Future Decision Bias
```

## v0.5 Pareto Optimization + Decision Tradeoff Frontier

- Added candidate generation for model routing, context packing, and scheduler
  strategies.
- Added objective vectors across quality, cost, latency, risk, privacy, token
  usage, confidence, safety, and profile alignment.
- Added built-in Pareto preference profiles: `balanced`, `frugal`,
  `quality_first`, `privacy_first`, `safety_first`, and `speed_first`.
- Added frontier detection, preference ranking, tradeoff explanations, SQLite
  persistence, CLI commands, benchmark `--pareto`, and explain integration.
- Preserved the principle:

```text
Hephaestus does not hide tradeoffs behind a single magic score.
It exposes the decision frontier and explains why a candidate was selected.
```

## v0.6 QUBO / Ising Formulation Layer

- Added QUBO schemas for binary variables, linear/quadratic terms, constraints,
  objectives, problems, solutions, formulation reports, comparisons, and Ising
  problems.
- Added practical formulations for context packing, model selection, budget
  strategy, and a small task-ordering demo.
- Added local exhaustive, greedy, and seeded simulated annealing QUBO solvers.
- Added QUBO to Ising conversion using `x = (1 + s) / 2`.
- Added SQLite persistence for `qubo_problems` and `qubo_solutions`.
- Added `heph qubo ...` CLI commands, benchmark `--qubo`, explain integration,
  and Pareto comparison notes.
- Preserved the principle:

```text
Hephaestus uses QUBO/Ising-style formulations to make agent decision problems explicit and optimizable. This is quantum-inspired optimization, not a claim of quantum hardware acceleration.
```

## v0.7 Repo Intelligence

- Added read-only local repository inspection.
- Added Node/TypeScript/JavaScript, Python, Rust, Go, Docker, GitHub Actions,
  and GitLab CI signal detection.
- Added package manager, script, validation command, environment file, and risk
  signal schemas.
- Added safe command classification for validation, medium risk, high risk,
  destructive commands, and external side effects.
- Added validation plan generation and repo-aware release-readiness task graphs.
- Added SQLite persistence for `repo_profiles` and `repo_inspections`.
- Added `heph repo inspect/list/show/tasks/plan/export-benchmark`.
- Added benchmark export so real repo tasks can run through optimizer, Pareto,
  and QUBO proof reports.
- Preserved the principle:

```text
Hephaestus does not jump straight from prompt to action.
It first inspects the repository, builds a project profile, generates repo-aware tasks, and then lets the decision engine optimize the plan.
```

## v0.8 Repo-Aware Release Planning Demo

- Connect repo inspection, repo planning, optimizer, Pareto, QUBO, explain, and
  outcome learning into one polished local demo.
- Keep execution safe and approval-gated.
- Target flow:

```bash
heph repo inspect .
heph repo plan <profile_id>
heph optimize --repo-profile <profile_id> --pareto --qubo
heph explain <run_id>
```

## v0.9 Token Firewall

- Per-run and per-project budgets.
- Cost ledgers.
- Provider-specific model catalogs.
- Quality regression checks.

## v0.10 Memory Monster

- Hybrid search.
- Graph memory.
- Verification and decay.
- Failure-to-decision learning.

## v0.11 Skill Growth

- Skill registry.
- Skill validation.
- Promotion from repeated memories.
- Safety review before using generated skills.

## v0.12 Dashboard

- Local web dashboard.
- Plan visualizations.
- Decision trace trees and aggregate decision stats.
- Budget reports.
- Memory inspection.
- Approval queue.

## v1.0 Always-On Agent OS

- Event daemon.
- Safe tool execution.
- Multi-agent allocation.
- Persistent skills and memory.
- Production-ready policy and audit.
