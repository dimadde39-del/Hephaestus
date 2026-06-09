# Repo Intelligence

Repo intelligence is Hephaestus' bridge from synthetic optimizer fixtures to
real local development workflows. In Phase 5E its command classifier also feeds
the safe tool execution runtime.

```text
Hephaestus does not jump straight from prompt to action.
It first inspects the repository, builds a project profile, generates repo-aware tasks, and then lets the decision engine optimize the plan.
```

## What It Does

`heph repo inspect <path>` performs read-only inspection and produces a
`RepoProfile` plus a persisted `RepoInspectionReport`.

The profile answers:

- What kind of project is this?
- How should it be validated?
- Which files define its structure?
- Which commands are safe to suggest?
- Which commands are risky, destructive, or externally side-effecting?
- What release-readiness tasks should be generated?
- What risks should an agent consider before acting?

## Conversation Integration

`heph ask` and `heph discuss` can use repo intelligence without executing
commands:

```bash
uv run heph ask "What are the release risks in this repo?" --repo .
```

The conversation pipeline reuses the latest profile for the path when one
exists, otherwise it performs the same read-only inspection used by
`heph repo inspect`. The answer can reference detected stack, validation
commands, generated repo tasks, and risk signals. With `--propose-tools`, it can
also print exact `heph tools ...` commands for the user to run manually.

## Safety Model

Repo inspection remains read-only. It reads manifests, lockfiles, configuration
filenames, CI filenames, and package metadata. Phase 5E can execute separately
through `heph tools`, but only after the tool runtime classifies risk and
applies approval policy.

Command categories:

- `safe_readonly`
- `safe_validation`
- `medium_risk`
- `high_risk`
- `destructive`
- `external_side_effect`

Examples of safe validation suggestions include `pnpm test`, `pnpm lint`,
`pnpm build`, `uv run pytest`, `python --version`, `node --version`,
`cargo test`, and `go test ./...`.

Examples of commands that are approval-gated or flagged include `rm -rf`,
`git push`, package publish commands, Docker pushes, deploy scripts, `curl | sh`,
commands touching `.env`, secret-like exports, and suspicious database reset or
migration commands.

## Detected Ecosystems

Node, TypeScript, and JavaScript:

- `package.json`
- `pnpm-lock.yaml`, `yarn.lock`, `package-lock.json`, `bun.lockb`
- `tsconfig.json`
- Next.js, Vite, React, Tailwind, ESLint, Vitest, Jest signals
- scripts, test, lint, build, and dev commands

Python:

- `pyproject.toml`, `requirements.txt`, `uv.lock`, `poetry.lock`, `setup.py`
- uv, Poetry, pip
- pytest, ruff, mypy
- FastAPI, Django, Flask from dependencies

Rust:

- `Cargo.toml`, `Cargo.lock`
- cargo test, check, build, fmt, and clippy suggestions

Go:

- `go.mod`, `go.sum`
- `go test ./...`
- `go build ./...`

Docker and CI:

- Dockerfile and compose files
- `.github/workflows/*.yml`
- `.gitlab-ci.yml`

## Validation Plans

Validation plans are ordered suggestions. They are not executed by repo
inspection.

Examples:

```text
Next.js / pnpm:
1. pnpm lint
2. pnpm test
3. pnpm build

Python / uv:
1. uv run ruff check .
2. uv run mypy
3. uv run pytest

Rust:
1. cargo fmt --check
2. cargo clippy
3. cargo test

Go:
1. go test ./...
2. go build ./...
```

## Repo-Aware Tasks

Profiles generate `RepoTask` records that can be converted into the existing
optimizer `Task` schema:

- `inspect_repo_structure`
- `review_package_scripts`
- `inspect_ci`
- `check_env_risks`
- `run_lint`
- `run_tests`
- `run_build`
- `identify_validation_commands`
- `gate_risky_commands`
- `prepare_release_summary`

Each task carries priority, dependencies, risk, expected value, required
capabilities, estimated tokens, allowed tools, approval requirements, and command
metadata when relevant.

## CLI

```bash
uv run heph repo inspect .
uv run heph repo inspect <path>
uv run heph repo list
uv run heph repo show <profile_id>
uv run heph repo tasks <profile_id>
uv run heph repo plan <profile_id>
uv run heph repo export-benchmark <profile_id> --output benchmarks/repo/<name>.json
```

`heph repo plan <profile_id>` runs the existing task scheduler over repo-aware
tasks and prints the task graph, validation sequence, and approval notes. It
does not execute validation.

## Benchmark Integration

Repo profiles can become benchmark fixtures:

```bash
uv run heph repo export-benchmark <profile_id> --output benchmarks/repo/hephaestus_self.json
uv run heph benchmark run benchmarks/repo/hephaestus_self.json --pareto --qubo
```

This connects:

```text
Repo Intelligence -> Repo-Aware Task Graph -> Optimized Execution Plan -> Safe Real Agent Demo
```

The exported fixture gives the optimizer, Pareto layer, and QUBO layer real
local task graphs without executing repository commands.

## Release Planning Integration

Phase 4B turns repo intelligence into a one-command release planning demo:

```bash
uv run heph release plan . --pareto --qubo --evaluate
uv run heph release plan <path>
uv run heph release plan <path> --profile <profile_id>
uv run heph release list
uv run heph release show <release_run_id>
```

The flow is:

```text
Repo Inspect -> Repo Plan -> Optimize -> Pareto -> QUBO -> Explain -> Evaluate -> Learn
```

If `--profile <profile_id>` is supplied, release planning reuses an existing
repo profile. Otherwise it inspects the path read-only and persists a new
profile. `--latest-profile` can reuse the newest profile for a path when one is
available.

Release planning still does not execute validation commands. It converts
detected validation, CI, env-file, script-risk, and approval signals into a
conservative recommendation such as `needs_validation`. The recommendation
links to `heph explain <run_id>`, `heph repo tasks <profile_id>`, `heph pareto
show <frontier_id>`, and `heph qubo show <problem_id>` when those artifacts
exist.

## Persistence

Repo intelligence uses the local SQLite database:

- `repo_profiles`
- `repo_inspections`
- `release_plans` for Phase 4B release planning results linked back to repo
  profiles.

Rows store the repo path, repo name, stack summary, validation plan, generated
tasks, risk summary, full report JSON, and inspection timestamp.

## Limitations

- CI workflow files are detected by path; full YAML semantics are not parsed.
- Environment file contents are not inspected automatically.
- Dependency detection is manifest-based and may miss dynamically imported
  frameworks.
- Validation plans are suggestions, not proof that commands will pass.
- No dashboard, daemon, browser automation, voice, Telegram, or autonomous code
  editing is included in Phase 4A or 4B.
