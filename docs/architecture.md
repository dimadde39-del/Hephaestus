# Architecture

Hephaestus is organized around a local-first core that can grow into an
always-on runtime without forcing paid APIs or a single model provider.

## Core Modules

- `core`: shared runtime settings, privacy/risk levels, and event schemas.
- `spec`: a deterministic Phase 1 pipeline from user goal to `GoalSpec`, tasks,
  and `ExecutionPlan`.
- `storage`: SQLite initialization, migrations, persistent memories, run history,
  decisions, and approval records.
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
  -> Objective scoring
  -> Greedy baseline
  -> Simulated annealing comparison
  -> Context packing
  -> Model routing
  -> Token firewall
  -> Safety policy
  -> ExecutionPlan
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
- Make every optimizer return an explanation.
