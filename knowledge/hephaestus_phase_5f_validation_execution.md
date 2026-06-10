# Hephaestus Phase 5F: Real Validation Execution + Outcome Learning

Phase 5F connects repo intelligence, the safe tool runtime, outcomes, learning,
and release planning.

Core loop:

```text
repo validation plan -> approved execution -> real command results -> outcomes -> learning signals -> release readiness evidence
```

## What Changed

- Added `src/hephaestus/validation/`.
- Added validation schemas, planner, executor, evaluator, repository, renderer,
  and analysis helpers.
- Added SQLite migration 14:
  - `validation_plans`
  - `validation_commands`
  - `validation_results`
  - `validation_evidence`
  - `release_validation_summaries`
- Added `heph validate plan/run/results/show/latest`.
- Added release planning integration:
  - `heph release plan . --with-validation --yes`
  - evidence mode labels
  - readiness score adjustment from real validation results
- Added validation strategy learning signals and repeated-failure memory drafts.
- Updated conversation tool proposals to suggest validation plan, dry-run, and
  approved execution.

## Boundaries

Phase 5F is not a coding loop. It does not apply patches, edit files to fix
tests, deploy, publish, push, run browser automation, run a daemon, or turn chat
into automatic execution.

It only executes supported validation commands after explicit `--yes`, through
the safe tool runtime.

## Product Principle

Hephaestus should stop pretending validation happened.

If release readiness is evidence-based, the system should know whether tests,
lint, type checks, builds, warnings, failures, timeouts, and approval gates were
observed.

## Next Phase

Recommended next phase:

```text
Phase 5G: Repo-Aware Coding Loop
```

That phase should propose patches, apply approved changes with checkpoints, run
validation, observe failures, iterate within explicit limits, and learn from real
coding outcomes.

After Phase 5G:

```text
Phase 5.5: Hephaestus Studio / Persistent Interface Layer
```

Studio should provide persistent chat history, run history, decision traces,
validation evidence, approvals, checkpoints, Pareto/QUBO/outcome views, and
readable past conversations before Phase 6 Skill Forge.
