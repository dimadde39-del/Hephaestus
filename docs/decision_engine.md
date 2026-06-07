# Explainable Decision Engine

Phase 3A makes important Hephaestus decisions inspectable, traceable, and
auditable. The goal is not better UI. The goal is optimizer transparency.

Hephaestus does not only optimize decisions.
It records why each decision was made so future versions can learn from outcomes.

Users and future runtime systems should be able to answer:

- Why was this task selected or delayed?
- Why was this model chosen or rejected?
- Why was context included or removed?
- Why did the token firewall approve, block, or intervene?
- Why did a safety gate require approval?

## Decision Types

Decision traces are Pydantic records in `hephaestus.decision.schemas`:

- `TaskSelectionDecision`
- `ModelRoutingDecision`
- `ContextSelectionDecision`
- `BudgetDecision`
- `SafetyDecision`
- `OptimizationDecision`

Every trace includes:

- `id`
- `run_id`
- `decision_type`
- `timestamp`
- `phase`
- `selected_option`
- `alternatives`
- `rationale`
- `metrics`
- `objective_score`
- `confidence`
- `constraints_considered`
- `tags`
- `caused_by`
- `will_affect`
- `learning_hooks`
- nullable `outcome_id`, `failure_memory_id`, and `policy_update_id`
- optional `parent_id` for trace trees

Alternatives are structured `DecisionAlternative` records, not loose log
strings. Rejected options can record option ID/name, score, rejection reason,
violated constraints, metric evidence, would-have cost, expected quality, and
risk. Metrics are structured `DecisionMetric` records with a name, value,
optional unit, description, and directionality.

## Persistence

Phase 3A keeps the older `run_decisions` table intact and adds
`decision_traces` for richer audit records. The new repository lives at
`hephaestus.decision.repository.DecisionTraceRepository`.

Supported operations:

- save one or many traces,
- list traces by run,
- filter traces by decision type,
- reconstruct parent/child trace trees,
- aggregate all persisted traces for stats.

## CLI

```bash
uv run heph explain <run_id>
uv run heph explain <run_id> --summary
uv run heph explain stats
```

`heph explain <run_id>` groups traces into task, model, context, budget, safety,
and optimization sections. `--summary` reports total decisions, decisions by
type, top rejection reasons, top constraints, average confidence, average
objective score, token savings, and approvals required. `stats` aggregates
trace counts, model selections, rejected models, rejection reasons, approval
triggers, token savings, confidence, and objective score across all saved runs.

## Why Explainability Matters

Optimization without explainability can improve a score while hiding the reason.
That is dangerous for agent systems because the reason is often the product:

- a cheap model might fail the quality threshold,
- a memory might be excluded under token pressure,
- an approval gate might prevent an unsafe external action,
- an annealing result might win only because the greedy baseline violated a
  dependency.

Structured traces make these tradeoffs measurable. They also make regressions
visible: if a future optimizer selects a different model, drops more context, or
requires more approvals, the trace layer can explain what changed.

## Benchmark Integration

Benchmark runs automatically generate decision traces. Reports include:

- decision count,
- top decision type,
- top decision rationale,
- most common rejection reason,
- quality preserved status,
- token savings summary.

Persisted benchmark runs can be inspected with both `heph run show <run_id>` and
`heph explain <run_id>`.

## Future Connection

The decision engine is infrastructure for later phases:

- Outcome tracking can attach real outcomes directly to `decision_traces.id`.
- Failure learning can create memories and attach them through
  `failure_memory_id`.
- Policy changes can point back to the decisions that motivated them through
  `policy_update_id`.
- QUBO/Ising optimization can emit comparable traces for binary-variable
  choices and constraint penalties.
- Self-evaluation can score whether rationales match outcomes.
- Skill growth can identify repeated rejection reasons and approval triggers.
- Dashboards can visualize trace trees and aggregate optimizer behavior.
- Autonomous runtime loops can decide when they need more context, stronger
  models, human approval, or a different strategy.

The important principle is stable: Hephaestus should not only optimize. It
should be able to explain what it optimized for and what it gave up.
