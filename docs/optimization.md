# Optimization

The optimization core is the center of Hephaestus. It is used to decide task
order, model routing, context packing, tool choice, autonomy/risk, and token
budget allocation.

## Objective Function

Phase 1 uses a weighted utility function:

```text
utility =
  + expected_value
  + priority
  + success/confidence proxy
  - token_cost
  - risk_penalty
  - uncertainty_penalty
  - dependency_violation_penalty
```

Weights live in `ObjectiveWeights` and can be tuned without changing task
schemas.

## Greedy Baseline

The greedy scheduler repeatedly chooses the highest-scoring task whose
dependencies are already complete. This gives a stable, explainable baseline and
keeps dependency handling clear.

## Simulated Annealing

The annealing scheduler starts from the greedy order, explores swaps, and accepts
some worse intermediate states according to temperature. Dependency violations
are allowed during search but receive a large penalty, so valid plans tend to
win.

This is quantum-inspired in the practical sense: the runtime treats planning as
an energy landscape and searches for lower-cost/higher-utility configurations.

## Future QUBO / Ising Direction

Later versions can represent ordering, model selection, context inclusion, and
tool choices as binary variables:

- `x_task_position`
- `x_model_for_task`
- `x_context_included`
- `x_tool_allowed`

Hard constraints become large penalties; soft preferences become weighted terms.
That opens the door to QUBO/Ising solvers, annealing benchmarks, and hybrid
classical/quantum-inspired planning.

## Where Optimization Applies

- Task order.
- Model routing.
- Context packing.
- Tool choice.
- Risk and autonomy decisions.
- Token budget allocation.
- Future multi-agent task allocation.
- Future skill promotion.

## Run History

`heph optimize <scenario.json>` now saves each optimization run to local SQLite
at `.hephaestus/hephaestus.db`. A run captures:

- scheduled tasks and selected order,
- greedy and simulated annealing scheduler results,
- model routing decisions and rejected options,
- context packing selections and exclusions,
- token budget evaluation,
- pending approvals for approval-gated tasks.

The CLI prints the saved run ID:

```text
Saved run: run_...
View with: heph run show run_...
```

Durable run history is intentionally in place before always-on mode so future
daemon, dashboard, and benchmark features can inspect what happened across
processes.
