# QUBO / Ising Formulation Layer

Phase 3E makes the quantum-inspired part of Hephaestus explicit and inspectable.

```text
Hephaestus uses QUBO/Ising-style formulations to make agent decision problems explicit and optimizable. This is quantum-inspired optimization, not a claim of quantum hardware acceleration.
```

## What QUBO Means

QUBO means quadratic unconstrained binary optimization. A decision is represented with binary variables:

```text
x_i = 1 means choose or include option i
x_i = 0 means do not choose or include option i
```

The objective is an energy function:

```text
E(x) = constant + linear rewards/penalties + quadratic interactions
```

Hephaestus minimizes that energy locally with deterministic classical solvers. Rewards are encoded as negative coefficients. Penalties are encoded as positive coefficients. Constraints are also stored as explicit records so a solution can be checked and explained after solving.

## Implemented Formulations

Phase 3E adds `src/hephaestus/qubo/` with schemas, formulation builders, solvers, Ising conversion, persistence, renderers, and comparison helpers.

Implemented formulations:

- `context_packing`: variable `x_i` means include context item `i`.
- `model_selection`: variable `x_i` means choose model profile `i`.
- `budget_strategy`: variable `x_i` means choose budget strategy `i`.
- `task_ordering_demo`: variable `x_{i,p}` means assign task `i` to position `p`; this is a small demonstrative formulation, not a full scheduler.

Context packing rewards relevance, importance, criticality, failure-memory usefulness, and profile alignment. It penalizes token cost, redundancy, missing critical context, and token-budget pressure.

Model selection rewards quality, confidence, privacy fit, capability match, and profile alignment. It penalizes cost, latency, risk, quality-threshold violations, and missing required capabilities. The exact-one model choice is encoded as a QUBO penalty.

Budget strategy rewards quality preservation, safety, and profile alignment. It penalizes estimated cost, token usage, quality risk, and missing critical context.

## Solvers

Local solvers are intentionally lightweight:

- `exhaustive`: enumerates all assignments for small problems.
- `greedy`: performs deterministic single-bit descent and simple feasibility repair.
- `annealing`: uses seeded simulated annealing over binary flips.

These are classical solvers. They are useful for tests, fixtures, and inspectable comparisons. They do not claim quantum speedups.

## Ising Conversion

Hephaestus can convert QUBO to Ising form using:

```text
x = (1 + s) / 2
```

Binary variables `x in {0, 1}` become spin variables `s in {-1, +1}`. The CLI can show the resulting linear fields, pair couplings, and constant offset:

```bash
uv run heph qubo convert-ising <problem_id>
```

The Ising conversion is inspectable only in this phase. Hephaestus does not solve Ising separately yet and does not integrate quantum hardware.

## CLI

```bash
uv run heph qubo formulate benchmarks/task_graphs/model_quality_threshold.json --type model_selection
uv run heph qubo solve <problem_id> --solver exhaustive
uv run heph qubo solve <problem_id> --solver greedy
uv run heph qubo solve <problem_id> --solver annealing
uv run heph qubo show <problem_id>
uv run heph qubo list
uv run heph qubo compare benchmarks/task_graphs/model_quality_threshold.json
uv run heph qubo convert-ising <problem_id>
uv run heph benchmark run benchmarks/task_graphs/model_quality_threshold.json --qubo
```

`heph qubo show` displays variables, objective terms, constraints, and the latest solution. `heph qubo compare` persists a run, formulates relevant problems, solves them, compares against baselines, and also creates Pareto reference records for comparison.

## QUBO vs Greedy, Annealing, And Pareto

Greedy is a simple baseline. It makes local choices and is easy to inspect.

Simulated annealing searches an energy landscape with classical random flips. It can explore alternatives that greedy misses.

Pareto exposes tradeoff frontiers across multiple objectives before selection. It is useful when the product question is, "What are the tradeoffs?"

QUBO encodes one selected decision problem into binary variables, objective terms, and penalties. It is useful when the product question is, "What exact binary optimization problem did we solve?"

Pareto and QUBO complement each other. Pareto shows the frontier; QUBO shows the formulation.

## Persistence And Explain

SQLite migration 7 adds:

- `qubo_problems`
- `qubo_solutions`

Problems and solutions are stored as full JSON roundtrips with queryable summary columns. Benchmark runs with `--qubo` persist QUBO problems and solutions, add `phase=qubo` optimization traces, and show QUBO summaries in:

```bash
uv run heph explain <run_id>
uv run heph explain <run_id> --summary
```

## Limitations

- QUBO token-budget penalties are practical quadratic approximations, not a full slack-variable knapsack encoding.
- The task-ordering formulation is a small demo, not a full resource scheduler.
- Solvers are deterministic local baselines without heavy dependencies.
- No quantum hardware integration is present.
- No quantum speedup is claimed.
