# Repo-Aware Release Planning

Phase 4B creates the first polished local demo candidate for Hephaestus.

```text
Repo Inspect -> Repo Plan -> Optimize -> Pareto -> QUBO -> Explain -> Evaluate -> Learn
```

```text
Hephaestus does not run blindly.
It inspects the repository, builds a release plan, exposes tradeoffs, formulates optimizations, explains decisions, and records learning signals before execution is ever allowed.
```

## What It Does

`heph release plan <path>` composes existing systems:

- repo inspection or repo profile loading,
- repo-aware release task generation,
- conversion into the benchmark-compatible optimizer format,
- scheduler/model/context/budget optimization,
- optional Pareto frontiers,
- optional QUBO formulations and local solves,
- decision trace persistence,
- optional simulated outcome evaluation,
- learning signal generation,
- conservative release recommendation persistence.

The public demo command is:

```bash
uv run heph release plan . --pareto --qubo --evaluate
```

## What Is Real

Phase 4B uses real local repository inspection data. It reads manifests,
lockfiles, package metadata, config filenames, CI filenames, and environment
file names. It persists real SQLite records for:

- repo profiles,
- optimizer runs,
- run tasks,
- decisions,
- decision traces,
- Pareto frontiers,
- QUBO problems and solutions,
- outcomes,
- learning signals,
- release planning results.

The optimizer, Pareto comparison, QUBO formulation, and decision explanation are
real local deterministic systems.

## What Is Simulated

Outcome evaluation is simulated over decision traces. It can say a model route
met its quality threshold or a safety trace preserved approval gates. It cannot
say `pytest`, `pnpm build`, deployment, publishing, or any repository command
actually succeeded, because Phase 4B does not execute those commands.

Release readiness is therefore planning readiness, not release proof.

## Why Command Execution Is Deferred

Release planning is intentionally pre-execution. The system should inspect,
specify, optimize, expose tradeoffs, explain, and learn before tool execution is
ever allowed.

Commands are detected and classified as:

- `safe_readonly`,
- `safe_validation`,
- `medium_risk`,
- `high_risk`,
- `destructive`,
- `external_side_effect`.

Validation commands are suggestions. Deploy, publish, destructive, secret-like,
or external side-effect commands remain approval-gated.

## Readiness Score

The readiness score is a deterministic integer from 0 to 100. It uses coarse
whole-number weights for:

- repo profile confidence,
- validation commands detected,
- test command detected,
- build or lint command detected,
- CI detected,
- environment-file posture,
- high-risk script posture,
- approval gate posture,
- optimizer run persistence,
- Pareto feasibility,
- QUBO feasibility.

It avoids fake precision and does not claim commands passed.

## Recommendation Status

Release recommendations can be:

- `ready`
- `mostly_ready`
- `needs_validation`
- `blocked`
- `unknown`

The common honest status in Phase 4B is `needs_validation`, because even a
strong plan still has not executed validation.

Example reasons:

```text
Recommendation: needs_validation

Why:
- lint/build/test commands were detected but not executed.
- env files were detected by name; contents were not inspected.
- CI configuration was detected.
- no test command found.
- publish/deploy/destructive scripts require approval before execution.
```

## CLI

```bash
uv run heph release plan .
uv run heph release plan <path>
uv run heph release plan . --pareto --qubo --evaluate
uv run heph release plan . --profile <profile_id>
uv run heph release plan . --preference balanced
uv run heph release list
uv run heph release show <release_run_id>
```

`--profile <profile_id>` refers to a repo profile from `heph repo inspect`, not a
decision quality profile. Active decision quality profiles still influence the
underlying optimizer through the existing benchmark runner.

## Explain Integration

`heph release show <release_run_id>` links to:

```bash
uv run heph repo tasks <profile_id>
uv run heph run show <optimizer_run_id>
uv run heph explain <optimizer_run_id>
uv run heph pareto show <frontier_id>
uv run heph qubo show <problem_id>
uv run heph outcome list --run <optimizer_run_id>
uv run heph learn signals --run <optimizer_run_id>
```

## Persistence

SQLite migration 9 adds `release_plans`.

Each row stores:

- release plan ID,
- repo profile ID,
- goal,
- linked optimizer run ID,
- readiness score,
- recommendation status and summary,
- Pareto frontier IDs JSON,
- QUBO problem IDs JSON,
- decision trace IDs JSON,
- outcome IDs JSON,
- learning signal IDs JSON,
- full raw Pydantic JSON,
- creation time.

## Public Demo Positioning

Phase 4B is the first demo that shows the Hephaestus philosophy end to end:

```text
Remember deeply.
Specify clearly.
Optimize honestly.
Act safely later.
Explain everything.
Learn continuously.
```

It prepares the project for public-alpha polish without adding dashboard,
voice, Telegram, browser automation, always-on daemon behavior, or autonomous
code editing.
