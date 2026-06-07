# Hephaestus Phase 3A Decision Engine

Phase 3A adds explainable decision traces for optimizer behavior.

```text
Hephaestus does not only optimize decisions.
It records why each decision was made so future versions can learn from outcomes.
```

## What Changed

- Added `src/hephaestus/decision/` with schemas, builders, repository,
  renderer, and analysis helpers.
- Added six typed Pydantic trace models:
  `TaskSelectionDecision`, `ModelRoutingDecision`,
  `ContextSelectionDecision`, `BudgetDecision`, `SafetyDecision`, and
  `OptimizationDecision`.
- Added structured `DecisionAlternative` and `DecisionMetric` records.
- Added SQLite migration 3 with richer `decision_traces` columns.
- Kept existing `run_decisions` intact for compatibility.
- Added `heph explain <run_id>`, `heph explain <run_id> --summary`, and
  `heph explain stats`.
- Updated optimize and benchmark flows to persist rich traces.
- Updated benchmark reports with decision count, top decision type, top
  rationale, common rejection reason, quality status, and token savings summary.

## Principle

Every important optimizer decision should record:

- what was selected,
- what alternatives were rejected,
- why the choice was made,
- which metrics mattered,
- which constraints were considered,
- confidence and objective score.
- tags, caused-by links, downstream effects, and learning hooks.
- nullable `outcome_id`, `failure_memory_id`, and `policy_update_id`.

Optimization without explainability is insufficient because future autonomous
systems need measurable reasons, not just final scores.

## Persistence

`DecisionTraceRepository` supports saving traces, listing traces by run,
filtering by decision type, fetching by ID, aggregating stats, and
reconstructing parent/child trace trees. Traces link to `runs.id` through
`run_id`.

## CLI Examples

```bash
uv run heph explain run_xxxxx
uv run heph explain run_xxxxx --summary
uv run heph explain stats
```

## Known Limits

- Trace generation is wired into current CLI optimize and benchmark flows, not a
  long-running daemon.
- Safety traces cover approval records and policy-compatible builders; there is
  not yet a live execution engine that records every tool call.
- Trace trees are simple parent/child links, not a graph database.
- Aggregates are intentionally simple counters and averages.

## Recommended Next Phase

Phase 3B: Outcome Tracking + Failure Learning.

That phase should attach real outcomes to decision IDs and create failure
memories when decisions lead to bad results.
