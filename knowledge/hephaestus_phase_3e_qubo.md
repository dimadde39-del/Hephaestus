# Hephaestus Phase 3E: QUBO / Ising Formulation Layer

Phase 3E makes Hephaestus' quantum-inspired optimization claim concrete and inspectable.

```text
Hermes learns workflows.
Hephaestus learns decision quality.
```

Core wording:

```text
Hephaestus uses QUBO/Ising-style formulations to make agent decision problems explicit and optimizable. This is quantum-inspired optimization, not a claim of quantum hardware acceleration.
```

## Added

- `src/hephaestus/qubo/`
  - schemas
  - builder
  - formulations
  - solver
  - Ising conversion
  - repository
  - renderer
  - analysis helpers
- SQLite migration 7:
  - `qubo_problems`
  - `qubo_solutions`
- CLI:
  - `heph qubo formulate <fixture> --type context_packing`
  - `heph qubo formulate <fixture> --type model_selection`
  - `heph qubo formulate <fixture> --type budget_strategy`
  - `heph qubo solve <problem_id> --solver exhaustive|greedy|annealing`
  - `heph qubo show <problem_id>`
  - `heph qubo list`
  - `heph qubo compare <fixture>`
  - `heph qubo convert-ising <problem_id>`
- Benchmark `--qubo` support.
- Explain integration for full and summary modes.

## Formulations

Context packing:

- `x_i = 1` includes context item `i`.
- Rewards relevance, importance, criticality, failure memory usefulness, and profile alignment.
- Penalizes token cost, redundancy, missing critical context, and token-budget pressure.

Model selection:

- `x_i = 1` chooses model `i`.
- Rewards quality, confidence, privacy fit, capability match, and profile alignment.
- Penalizes cost, latency, risk, quality-threshold violations, and missing required capabilities.
- Encodes exact-one model selection.

Budget strategy:

- `x_i = 1` chooses one strategy among `frugal`, `balanced`, `rich_context`, `quality_guard`, and `critical_only`.
- Rewards quality preservation, safety, and profile alignment.
- Penalizes cost, token usage, quality risk, and missing critical context.

Task ordering demo:

- `x_{i,p} = 1` assigns task `i` to position `p`.
- Encodes task-once, position-once, and dependency-order penalties.
- Kept intentionally small.

## Solvers

- Exhaustive solver for small problems.
- Greedy binary solver with deterministic repair.
- Seeded simulated annealing QUBO solver.

All solvers are local and classical. They do not call paid APIs.

## Ising

QUBO is converted to Ising with:

```text
x = (1 + s) / 2
```

The conversion exposes spin variables, linear fields, pair couplings, and constant offset. It does not solve Ising separately yet.

## Integration Notes

- Benchmark `--qubo` formulates relevant QUBOs, solves them, persists problems and solutions, and adds QUBO traces.
- `heph explain <run_id>` shows a QUBO table with problem type, variables, solver, selected variables, feasibility, objective value, and why.
- `heph explain <run_id> --summary` includes QUBO problem count, feasible/infeasible solution counts, and best objective value.
- QUBO does not replace Pareto. Pareto exposes tradeoff frontiers; QUBO exposes a binary optimization formulation.

## Known Limits

- Token-budget penalties are practical quadratic approximations.
- The task-ordering formulation is a demo, not a full scheduler.
- No dashboard, daemon, voice, Telegram, browser automation, quantum hardware, or full skill self-growth was added.

## Recommended Next Phase

```text
Phase 4A: Repo Intelligence
```

Repo Intelligence should inspect real local repositories, detect project structure, scripts, package managers, test commands, risk areas, and generate repo-aware tasks for future agent execution.
