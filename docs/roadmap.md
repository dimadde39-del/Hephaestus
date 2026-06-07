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

- Use accumulated outcomes and learning signals to tune decision profiles.
- Track model-routing quality profiles by task type and threshold.
- Tune context strategy profiles for critical-context preservation.
- Suggest scheduler weight adjustments from repeated task-order outcomes.
- Keep policy updates reviewed and non-automatic by default.
- Preserve the loop:

```text
Decision -> Outcome -> Reflection -> Memory Draft -> Learning Signal -> Reviewed Policy Update
```

## v0.5 Token Firewall

- Per-run and per-project budgets.
- Cost ledgers.
- Provider-specific model catalogs.
- Quality regression checks.

## v0.6 Memory Monster

- Hybrid search.
- Graph memory.
- Verification and decay.
- Failure-to-decision learning.

## v0.7 Skill Growth

- Skill registry.
- Skill validation.
- Promotion from repeated memories.
- Safety review before using generated skills.

## v0.8 Dashboard

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
