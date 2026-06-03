# Benchmark Fixtures

Phase 2B turns the task graph fixtures into an executable optimizer benchmark
suite:

```bash
uv run heph benchmark list
uv run heph benchmark show model_quality_threshold
uv run heph benchmark run benchmarks/task_graphs/simple_release.json
uv run heph benchmark run
```

Each fixture is a JSON object with benchmark metadata, tasks, model profiles,
context candidates, token budget, and quality thresholds. The runner preserves
compatibility with the older demo-shaped JSON format by filling missing
benchmark metadata from the filename.

The benchmark suite is designed to test optimizer behavior, not to claim
real-world AGI performance.

## Fixtures

- `simple_release.json`: a healthy baseline for the benchmark runner.
- `dependency_trap.json`: a deliberately invalid cyclic gate that proves
  dependency violations are counted honestly.
- `risky_refactor.json`: high-risk refactor tasks and approval pressure.
- `token_budget_pressure.json`: quality-preserving routing with aggregate token
  pressure.
- `model_quality_threshold.json`: cheap model rejected because quality is too
  low.
- `context_overload.json`: critical context included while low-value context is
  excluded.
- `approval_gate_pressure.json`: safe read-only actions separated from
  approval-required commit/push-like actions.
