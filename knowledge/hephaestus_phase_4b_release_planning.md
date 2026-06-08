# Hephaestus Phase 4B: Repo-Aware Release Planning Demo

Phase 4B connects the Phase 4A repo intelligence layer to the optimizer,
explainability, Pareto, QUBO, outcome learning, and persistence layers.

Core positioning:

```text
Hermes learns workflows.
Hephaestus learns decision quality.
```

Phase principle:

```text
Hephaestus does not run blindly.
It inspects the repository, builds a release plan, exposes tradeoffs, formulates optimizations, explains decisions, and records learning signals before execution is ever allowed.
```

## Implemented

- Added `src/hephaestus/release/`.
- Added schemas:
  - `ReleasePlanningRequest`
  - `ReleaseReadinessSignal`
  - `ReleaseRisk`
  - `ReleaseTaskPlan`
  - `ReleasePlanningResult`
  - `ReleaseDemoRun`
  - `ReleaseRecommendation`
- Added deterministic readiness analysis and conservative recommendation
  generation.
- Added release planner helpers that reuse repo profile to benchmark conversion.
- Added release orchestrator:
  - inspect repo or load profile,
  - generate repo-aware release tasks,
  - run existing benchmark optimizer pipeline with `mode=release`,
  - optionally run Pareto,
  - optionally run QUBO,
  - persist decision traces,
  - optionally evaluate simulated outcomes,
  - collect learning signals,
  - persist release plan.
- Added SQLite migration 9 with `release_plans`.
- Added `ReleasePlanRepository` with save/list/get/latest-by-profile/latest-by-path.
- Added Rich renderers for release plan, release list, readiness signals,
  task plan, recommendation, and linked artifacts.
- Added CLI:
  - `heph release plan .`
  - `heph release plan <path>`
  - `heph release plan . --pareto --qubo --evaluate`
  - `heph release plan . --profile <profile_id>`
  - `heph release plan . --preference balanced`
  - `heph release list`
  - `heph release show <release_run_id>`
- Added tests for schemas, recommendation generation, orchestrator, persistence,
  CLI, repo-profile integration, optimizer/QUBO/Pareto/outcome/learning links,
  and docs command strings.
- Added docs:
  - `docs/release_planning.md`
  - README release demo section
  - architecture/repo/optimization/Pareto/QUBO/outcome/roadmap updates
  - `examples/release_plan_demo.md`

## Safety Notes

Phase 4B does not execute repo commands.

It detects validation, build, lint, deploy, publish, destructive, env-related,
and external side-effect commands. Those commands are planning evidence, not
execution evidence. Risky actions remain approval-gated.

## Product Bridge

Phase 4B prepares:

```text
Remember deeply.
Specify clearly.
Optimize honestly.
Act safely later.
Explain everything.
Learn continuously.
```

The next recommended phase is:

```text
Phase 4C: Public Alpha Readiness Polish
```

That phase should improve README hero, CLI output polish, demo examples, project
identity, mascot direction, GitHub social preview plan, and installation/onboard
flow without adding distracting voice, integration, dashboard, or autonomous
editing features.
