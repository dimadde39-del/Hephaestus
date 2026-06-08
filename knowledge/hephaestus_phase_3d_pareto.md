# Hephaestus Phase 3D Pareto Optimization

Phase 3D adds Pareto optimization and decision tradeoff frontiers.

## What Changed

- Added `src/hephaestus/pareto/` with schemas, frontier logic, candidate
  scoring, selection, persistence, rendering, and benchmark analysis helpers.
- Added Pydantic schemas for `DecisionCandidate`, `ObjectiveVector`,
  `ObjectiveDimension`, `ParetoFrontier`, `ParetoComparison`,
  `TradeoffExplanation`, `ParetoSelectionResult`, and `PreferenceProfile`.
- Added built-in preference profiles: `balanced`, `frugal`, `quality_first`,
  `privacy_first`, `safety_first`, and `speed_first`.
- Added SQLite migration 6 with `pareto_frontiers`, `pareto_candidates`, and
  `pareto_selections`.
- Added CLI commands:
  `heph pareto profiles`, `heph pareto compare`, `heph pareto list`, and
  `heph pareto show`.
- Added benchmark `--pareto` support.
- Added explain integration for full and summary views.
- Added profile-aware scoring hooks for model risk/alignment, context
  failure-memory emphasis, scheduler weights, and safety-oriented selection.

## Principle

Hephaestus does not hide tradeoffs behind a single magic score.
It exposes the decision frontier and explains why a candidate was selected.

## Flow

```text
Generate candidates -> score multiple objectives -> identify Pareto frontier -> select final candidate -> explain tradeoff
```

## Preference Profiles vs Learned Profiles

- Preference profile: a current selection mode used to rank a frontier.
- Decision quality profile: a learned, reviewed, activatable profile derived
  from outcomes and learning signals.

Both can coexist. Learned profiles can shape candidate scoring; Pareto
preference profiles decide which valid frontier candidate wins.

## Known Limits

- Candidate generation is intentionally modest.
- No QUBO/Ising solver was implemented.
- No dashboard, voice, Telegram, browser automation, always-on daemon, or full
  skill self-growth was added.

## Recommended Next Phase

Phase 3E: QUBO/Ising Formulation Layer.

That phase should convert context packing and task scheduling into explicit
QUBO-style formulations and compare them against greedy, annealing, and
Pareto-selected approaches.
