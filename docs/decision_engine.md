# Explainable Decision Engine

Phase 3A makes important Hephaestus decisions inspectable, traceable, and
auditable. Phase 3B attaches outcomes and reflections to those decisions. The
goal is not better UI. The goal is optimizer transparency and decision-quality
learning.

Hephaestus does not only optimize or explain decisions.
It records why each decision was made, whether it worked, and what should be
learned from the result.

Users and future runtime systems should be able to answer:

- Why was this task selected or delayed?
- Why was this model chosen or rejected?
- Why was context included or removed?
- Why did the token firewall approve, block, or intervene?
- Why did a safety gate require approval?
- Did the decision succeed, fail, partially succeed, or remain unknown?
- What learning signal or failure draft came from the outcome?

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
uv run heph outcome add <decision_trace_id> --status failure --summary "..."
uv run heph reflect <run_id>
uv run heph learn signals
```

`heph explain <run_id>` groups traces into task, model, context, budget, safety,
and optimization sections. `--summary` reports total decisions, decisions by
type, top rejection reasons, top constraints, average confidence, average
objective score, token savings, and approvals required. When outcomes are
present, `explain` also shows linked outcomes and reflections, and `--summary`
includes outcome and learning artifact counts. `stats` aggregates
trace counts, model selections, rejected models, rejection reasons, approval
triggers, token savings, confidence, and objective score across all saved runs.

## Outcome Attachments

Phase 3B adds the companion record types in `hephaestus.outcomes.schemas`:

- `OutcomeRecord`
- `OutcomeMetric`
- `OutcomeEvidence`
- `ReflectionRecord`
- `LearningSignal`
- `FailureMemoryDraft`
- `PolicyUpdateSuggestion`

The stable loop is:

```text
Decision -> Outcome -> Reflection -> Memory Draft -> Learning Signal
```

Outcomes can be manually attached with `heph outcome add`, or generated
deterministically for benchmark traces with `heph benchmark run --evaluate` and
`heph reflect <run_id>`.

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

With `--evaluate`, benchmark runs also persist simulated outcomes:

- model-quality decisions succeed when selected quality meets the required
  threshold and fail when it does not,
- context decisions fail if critical context is missing,
- budget decisions fail when quality is violated and partially succeed under
  unresolved token/cost pressure,
- safety decisions fail when high-risk actions are allowed without approval.

## Future Connection

The decision engine is infrastructure for later phases:

- Repeated outcomes can tune model routing thresholds and context strategy
  profiles.
- Failure memory drafts can be explicitly promoted to durable `failure`
  memories.
- Policy suggestions can point back to the decisions that motivated them through
  `policy_update_id`.
- QUBO/Ising optimization can emit comparable traces for binary-variable
  choices and constraint penalties.
- Self-evaluation can score whether rationales match outcomes.
- Skill growth can identify repeated rejection reasons and approval triggers.
- Dashboards can visualize trace trees and aggregate optimizer behavior.
- Autonomous runtime loops can decide when they need more context, stronger
  models, human approval, or a different strategy.

The important principle is stable: Hephaestus should not only optimize. It
should be able to explain what it optimized for, observe whether that decision
worked, and learn from the result without unsafe automatic self-modification.
