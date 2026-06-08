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
uv run heph benchmark run benchmarks/task_graphs/model_quality_threshold.json --evaluate
uv run heph benchmark run benchmarks/task_graphs/model_quality_threshold.json --pareto
uv run heph benchmark run benchmarks/task_graphs/model_quality_threshold.json --qubo
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
- Decision trace summary: trace count, top decision type, top rationale, most
  common rejection reason, and token savings summary.
- Outcome learning with `--evaluate`: outcome counts, deterministic reflections,
  learning signals, failure memory drafts, and policy update suggestions.
- Pareto comparison with `--pareto`: candidate counts, frontier counts,
  dominated candidates, selected candidates, preference profile, and tradeoff
  explanation.
- QUBO comparison with `--qubo`: formulated problem types, baseline selections,
  QUBO selections, objective deltas, feasibility, and persisted problem/solution
  records.

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
`run_decisions`, rich explainable traces are stored in `decision_traces`, and
approval-required actions are stored in `approvals`.

When `--evaluate` is passed, benchmark traces also create rows in `outcomes`,
`reflections`, `learning_signals`, `failure_memory_drafts`, and
`policy_update_suggestions`. The records remain local SQLite data and do not
auto-apply policy changes.

When `--pareto` is passed, benchmark runs also write `pareto_frontiers`,
`pareto_candidates`, and `pareto_selections`, plus `phase=pareto` optimization
traces. These records can be inspected with:

```bash
uv run heph pareto list
uv run heph pareto show <frontier_id>
uv run heph explain <run_id>
uv run heph explain <run_id> --summary
```

When `--qubo` is passed, benchmark runs also write `qubo_problems` and
`qubo_solutions`, plus `phase=qubo` optimization traces. These records can be
inspected with:

```bash
uv run heph qubo list
uv run heph qubo show <problem_id>
uv run heph qubo solve <problem_id> --solver annealing
uv run heph qubo convert-ising <problem_id>
uv run heph explain <run_id>
uv run heph explain <run_id> --summary
```

Inspect recent runs with:

```bash
uv run heph runs
uv run heph run show <run_id>
uv run heph explain <run_id>
uv run heph explain <run_id> --summary
uv run heph reflect <run_id>
uv run heph learn signals
uv run heph learn failures
uv run heph learn policies
```

Benchmark traces use the same decision engine as optimization demos. That means
model-quality threshold fixtures preserve the rejected-model rationale, context
overload fixtures preserve token savings and excluded context reasons, and
approval-gate fixtures preserve safety decisions.
QUBO benchmark traces preserve the binary formulation evidence: variables,
objective terms, constraints, solver, selected variables, feasibility, and
objective value.

## Deterministic Outcome Evaluation

Benchmark outcome evaluation is intentionally simple and reproducible:

- model quality succeeds when the selected model quality is greater than or
  equal to the required threshold,
- context packing succeeds when critical context is preserved and the token
  budget is respected,
- budget checks succeed when token, cost, and quality constraints are all met,
  fail when quality is violated, and partially succeed when quality is preserved
  but token or cost pressure remains,
- safety checks succeed when risky actions require approval and fail when a
  high-risk action is allowed without approval.

This makes the benchmark suite a small learning laboratory: it can show that a
decision was explainable and then record whether that decision worked.

## Limitations

These benchmarks are deterministic local fixtures. They do not measure real
provider performance, production reliability, long-running autonomy, dashboard
behavior, browser automation, voice, Telegram, or skill self-growth. They are a
foundation for future richer benchmark suites and solver comparisons.
