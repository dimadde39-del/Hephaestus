# Phase 5.5B: Hephaestus Agent Workbench

Date: 2026-06-16

## Product Decision

Studio now has two primary navigation destinations:

```text
Chat
Workbench
```

Chat remains the default startup route and the primary product experience.
Workbench is a readable control/inspection surface for the real work
Hephaestus performs.

The key message is:

```text
Talk in Chat.
Inspect real work in Workbench.
```

## Backend

`src/hephaestus/studio/workbench.py` projects existing runtime records into
typed Studio responses. It reuses existing repositories and orchestrators for:

- coding requests, plans, changes, and apply;
- validation planning and execution;
- tool actions and checkpoint restore;
- release plans;
- outcomes and learning signals;
- local trust settings and policy mapping.

The frontend never queries SQLite directly.

SQLite migration 17 adds `studio_trust_settings`.

## Frontend

`apps/studio` adds feature folders:

- `features/workbench`
- `features/coding`
- `features/diffs`
- `features/validation`
- `features/checkpoints`
- `features/tools`
- `features/releases`
- `features/outcomes`
- `features/trust`

The Workbench inherits the Phase 5.5A.1 visual system: neutral surfaces,
restrained borders, readable type, compact status indicators, and ember only as
a small accent.

## Workbench Views

Implemented:

- overview;
- coding list/detail;
- structured diff viewer;
- validation list/detail;
- checkpoint list/detail with restore confirmation;
- tool action timeline/detail;
- release list/detail with advanced optimization collapsed;
- outcome list/detail in human language;
- trust settings;
- pending meaningful decisions;
- compact chat artifact cards.

## Boundaries

Studio can create a coding plan, propose a scoped change, run validation dry-run
or approved validation, apply an existing patch proposal, and restore a
checkpoint.

Studio does not expose arbitrary shell input, dependency installation, Git
push, deploy, publish, external messaging, or fake streaming cancellation.

## Validation Notes

Backend and frontend tests cover the new typed API projections, linked
conversation behavior, redaction, destructive blocking, trust persistence,
patch application, validation execution, navigation, diff rendering, checkpoint
restore dialog, trust settings, and chat artifact cards.

## Next Phase

Phase 5.5C should add advanced views and packaging polish:

- memory management UX;
- provider/model settings;
- advanced decision trace viewer;
- Pareto visualization;
- QUBO visualization;
- model economy visibility;
- onboarding;
- packaging/install polish;
- final consistency and release readiness.

Advanced internals should remain secondary to Chat and Workbench.
