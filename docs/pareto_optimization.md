# Pareto Optimization

Phase 3D adds a decision tradeoff frontier to Hephaestus.

```text
Hermes learns workflows.
Hephaestus learns decision quality.
```

Hephaestus does not hide tradeoffs behind a single magic score.
It exposes the decision frontier and explains why a candidate was selected.

## Why One Score Is Not Enough

A scalar score can say one option won, but it can hide what the system gave up:

- a cheap model may miss the quality threshold,
- a rich context pack may preserve quality but use more tokens,
- a safer plan may require more approval pressure,
- a fast plan may be less robust.

Phase 3D keeps those dimensions visible before selecting a final candidate.

## What A Pareto Frontier Means

A candidate is Pareto-dominated when another candidate is at least as good on
every relevant objective and strictly better on at least one. The Pareto
frontier is the set of candidates that are not dominated.

Hephaestus maximizes:

- quality,
- confidence,
- safety,
- privacy,
- profile alignment.

It minimizes:

- cost,
- latency,
- risk,
- token usage.

## Flow

```text
Generate candidates
  -> score objective vectors
  -> remove invalid candidates unless none are valid
  -> compute non-dominated frontier
  -> rank frontier by preference profile
  -> persist selection
  -> explain tradeoff
```

Candidate types include model routes, context packs, task orders, budget
strategies, safety strategies, and optimizer plans.

## Preference Profiles

Preference profiles are selection modes, not learned policy. Built-ins are:

- `balanced`: moderate weights across objectives.
- `frugal`: cost and token reduction with quality/safety thresholds.
- `quality_first`: quality and confidence.
- `privacy_first`: privacy and low exposure risk.
- `safety_first`: safety, risk reduction, and approval-preserving behavior.
- `speed_first`: latency and simpler plans.

Decision quality profiles from Phase 3C are different. They are learned,
reviewed, activatable records derived from outcomes. Active decision quality
profiles can influence candidate scoring, while the Pareto preference profile
chooses among frontier candidates.

## CLI

```bash
uv run heph pareto profiles
uv run heph pareto compare benchmarks/task_graphs/model_quality_threshold.json
uv run heph pareto compare benchmarks/task_graphs/context_overload.json --preference balanced
uv run heph pareto list
uv run heph pareto show <frontier_id>
uv run heph benchmark run benchmarks/task_graphs/model_quality_threshold.json --pareto
uv run heph release plan . --pareto --qubo --evaluate
uv run heph qubo compare benchmarks/task_graphs/model_quality_threshold.json
```

`heph explain <run_id>` shows persisted Pareto selections when present.
`--summary` includes frontier count, dominated candidate count, selected
candidate count, and preference profiles used.

In Phase 4B, `heph release plan . --pareto` generates Pareto frontiers from
repo-aware release tasks before producing the release recommendation. This keeps
the public demo honest: the user can inspect which tradeoffs were considered
instead of only seeing one scalar readiness score.

## Persistence

SQLite migration 6 adds:

- `pareto_frontiers`,
- `pareto_candidates`,
- `pareto_selections`.

The repository stores compact JSON for full model roundtrips and queryable
columns for run ID, candidate type, preference, selected candidate, candidate
count, frontier count, dominated count, and tradeoff summary.

## Relationship To QUBO

Pareto and QUBO solve different explainability problems.

Pareto exposes a tradeoff frontier before scalar selection. It answers:

```text
Which candidates are non-dominated, and what tradeoff did we choose?
```

QUBO encodes one selected decision surface as binary optimization energy. It
answers:

```text
What are the variables, objective terms, penalties, constraints, and selected binary solution?
```

`heph qubo compare <fixture>` persists QUBO problems and also creates Pareto
reference frontiers from the same fixture so the two views can be inspected
together.

## Limitations

- Candidate generation is practical and local, not exhaustive.
- Objective values are deterministic estimates, not live provider telemetry.
- Preference profiles are fixed built-ins in this phase.
- Pareto comparisons are per decision surface; cross-surface global optimization
  remains future work.
- No dashboard, voice, Telegram, browser automation, always-on daemon, full
  skill self-growth, quantum hardware, or quantum speedup claim was added.
