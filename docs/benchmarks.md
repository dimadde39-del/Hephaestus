# Benchmarks

Hephaestus benchmarks are designed optimizer probes. They run fixed JSON
fixtures through scheduling, routing, context packing, token budget checks, and
approval accounting so the CLI can show what the optimizer decided and why.

The benchmark suite is designed to test optimizer behavior, not to claim
real-world AGI performance.

## Commands

```bash
uv run heph benchmark list
uv run heph benchmark show <benchmark_id>
uv run heph benchmark run
uv run heph benchmark run benchmarks/task_graphs/dependency_trap.json
uv run heph benchmark run --json
```

`heph benchmark run` executes every fixture in `benchmarks/task_graphs/`.
Passing an id, stem, filename, or path runs one fixture.

## What Reports Measure

- Scheduler comparison: greedy score, annealing score, score delta, percentage
  delta, selected scheduler, and dependency violations.
- Model routing: selected model, rejected models, rejection reasons, estimated
  cost, and required quality threshold.
- Context packing: candidate count, selected count, before/after context tokens,
  savings percentage, and critical context preservation.
- Quality and budget guard: aggregate token budget, cost budget, quality
  preservation, approvals required, and estimated cost.

Greedy is included because it is a clear baseline. Simulated annealing explores
more schedules, but it is not automatically better; reports show cases where it
ties or does not improve the score.

## Fixture Intent

- `simple_release`: proves the happy path.
- `dependency_trap`: proves dependency violation accounting on an intentionally
  invalid graph.
- `risky_refactor`: proves risk and approval reporting.
- `token_budget_pressure`: proves budget blocking without lowering quality.
- `model_quality_threshold`: proves a cheap low-quality model is rejected.
- `context_overload`: proves critical context survives token reduction.
- `approval_gate_pressure`: proves approval-required actions are persisted.

## Persistence

Each benchmark run creates a SQLite run with `mode=benchmark`. Tasks are stored
in `run_tasks`, optimizer/router/context/budget decisions are stored in
`run_decisions`, and approval-required actions are stored in `approvals`.

Inspect recent runs with:

```bash
uv run heph runs
uv run heph run show <run_id>
```

## Limitations

These benchmarks are deterministic local fixtures. They do not measure real
provider performance, production reliability, long-running autonomy, dashboard
behavior, browser automation, voice, Telegram, or skill self-growth. They are a
foundation for future richer benchmark suites and solver comparisons.
