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

- Convert context packing and task scheduling problems into explicit binary
  variables.
- Compare QUBO-style formulations against greedy, annealing, and Pareto-selected
  approaches.
- Keep constraints inspectable and map solver output back into decision traces.

## v0.7 Token Firewall

- Per-run and per-project budgets.
- Cost ledgers.
- Provider-specific model catalogs.
- Quality regression checks.

## v0.8 Memory Monster

- Hybrid search.
- Graph memory.
- Verification and decay.
- Failure-to-decision learning.

## v0.9 Skill Growth

- Skill registry.
- Skill validation.
- Promotion from repeated memories.
- Safety review before using generated skills.

## v0.10 Dashboard

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
