# Architecture

Hephaestus is organized around a local-first core that can grow into an
always-on runtime without forcing paid APIs or a single model provider.

## Core Modules

- `core`: shared runtime settings, privacy/risk levels, and event schemas.
- `spec`: a deterministic Phase 1 pipeline from user goal to `GoalSpec`, tasks,
  and `ExecutionPlan`.
- `storage`: SQLite initialization, migrations, persistent memories, run history,
  legacy decisions, rich decision traces, and approval records.
- `decision`: typed trace schemas, builders, SQLite trace repository, rendering,
  and aggregate analysis for explainable optimizer behavior.
- `benchmarks`: fixture loading, optimizer execution, report models, Rich output,
  and JSON output.
- `memory`: typed memory records and lexical retrieval behavior.
- `optimize`: task ordering, model routing, context packing, and token budgets.
- `models`: provider-agnostic model profiles, fake provider, optional DeepSeek.
- `tools`: typed tool definitions before execution.
- `safety`: approval gates and policy checks for risky actions.
- `skills`: early registry for reusable procedures.
- `cli`: Typer/Rich commands for demos and validation.

## Flow

```text
User goal
  -> GoalSpec
  -> Task graph
  -> Remembered context
  -> Objective scoring
  -> Greedy baseline
  -> Simulated annealing comparison
  -> Context packing
  -> Model routing
  -> Token firewall
  -> Safety policy
  -> Decision trace
  -> Benchmark report / persisted run
  -> ExecutionPlan
```

At the product level this is the same loop expressed as:

```text
Observe -> Remember -> Specify -> Optimize -> Act -> Explain -> Learn
```

Phase 1 intentionally avoids a long-running daemon. The CLI proves the module
boundaries and gives tests a stable surface. Phase 2A adds a local SQLite file at
`.hephaestus/hephaestus.db` so separate CLI invocations can share memory and run
history before any always-on process exists.

## Design Constraints

- Work locally with fake/mock models.
- Route by capabilities and quality threshold, not provider name.
- Treat writes, pushes, publishes, external sends, and destructive commands as
  approval-gated.
- Keep state simple now; introduce SQLite/vector/graph storage later.
- Keep SQLite local and migration-friendly before adding vector or graph storage.
- Make every optimizer return an explanation and a structured decision trace.
- Treat benchmark reports as designed optimizer probes, not real-world AGI
  performance claims.

## Decision Trace Architecture

Phase 3A keeps the existing `run_decisions` table for compatibility and adds
`decision_traces` for richer audit records. A trace records:

- `decision_type`: task selection, model routing, context selection, budget,
  safety, or optimization.
- `selected_option` and structured `DecisionAlternative` records.
- `rationale`, typed metrics, confidence, objective score, and constraints
  considered.
- phase, tags, caused-by links, downstream effects, and learning hooks.
- nullable `outcome_id`, `failure_memory_id`, and `policy_update_id` links for
  future learning.
- `parent_id` for reconstructing trace trees.

Builders in `hephaestus.decision.builder` translate scheduler, router, context,
budget, and safety outputs into typed Pydantic records. The CLI reads those
records through `heph explain <run_id>`, `heph explain <run_id> --summary`, and
`heph explain stats`.

Hephaestus does not only optimize decisions. It records why each decision was
made so future versions can learn from outcomes.

## Benchmark Persistence

The benchmark layer deliberately reuses the generic run history schema. A
benchmark creates a run with `mode=benchmark`, stores scheduled tasks in
`run_tasks`, stores scheduler/router/context/budget/quality decisions in
`run_decisions`, stores richer typed traces in `decision_traces`, and stores
approval-required actions in `approvals`.

This keeps the storage boundary simple while making benchmark runs visible in
the same `heph runs` and `heph run show <id>` views used by optimization demos.
Use `heph explain <id>` for the trace tree and rejection analysis.
