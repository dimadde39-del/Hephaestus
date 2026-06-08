# Hephaestus Phase 4A: Repo Intelligence

Phase 4A adds read-only repository intelligence.

Core positioning:

```text
Hermes learns workflows.
Hephaestus learns decision quality.
```

Phase principle:

```text
Hephaestus does not jump straight from prompt to action.
It first inspects the repository, builds a project profile, generates repo-aware tasks, and then lets the decision engine optimize the plan.
```

## Implemented

- Added `src/hephaestus/repo/`.
- Added schemas for repo profiles, file signals, stack summaries, package
  managers, scripts, test commands, CI providers, risk signals, validation
  plans, repo tasks, and inspection reports.
- Added read-only detectors for Node/TypeScript/JavaScript, Python, Rust, Go,
  Docker, GitHub Actions, and GitLab CI.
- Added command risk classification:
  - `safe_readonly`
  - `safe_validation`
  - `medium_risk`
  - `high_risk`
  - `destructive`
  - `external_side_effect`
- Added validation plan generation for common project stacks.
- Added repo-aware release-readiness task generation compatible with the
  existing optimizer `Task` schema.
- Added SQLite migration 8 with:
  - `repo_profiles`
  - `repo_inspections`
- Added `RepoProfileRepository`.
- Added Rich renderers for inspect/show/list/tasks/plan output.
- Added CLI commands:
  - `heph repo inspect .`
  - `heph repo inspect <path>`
  - `heph repo list`
  - `heph repo show <profile_id>`
  - `heph repo tasks <profile_id>`
  - `heph repo plan <profile_id>`
  - `heph repo export-benchmark <profile_id> --output <path>`
- Added benchmark export from `RepoProfile` to `BenchmarkCase`.
- Added fixture repos and tests for Node/Next.js, Python/uv, Rust, Go, risk
  classification, validation plans, task generation, persistence, CLI smoke, and
  benchmark export.

## Safety Notes

Repo inspection does not execute package commands.

It reads manifests and config filenames, classifies commands, and suggests a
validation sequence. Risky commands are represented as approval-gated tasks for
future phases.

Flagged examples include:

- `rm -rf`
- `git push`
- package publish commands
- Docker pushes
- deploy scripts
- `curl | sh`
- commands touching `.env`
- secret-like exports
- suspicious database reset or migration commands

## Product Bridge

Phase 4A prepares:

```text
Repo Intelligence -> Repo-Aware Task Graph -> Optimized Execution Plan -> Safe Real Agent Demo
```

The next recommended phase is:

```text
Phase 4B: Repo-Aware Release Planning Demo
```

Phase 4B should connect:

```bash
heph repo inspect .
heph repo plan <profile_id>
heph optimize --repo-profile <profile_id> --pareto --qubo
heph explain <run_id>
```

with outcome learning in one polished local demo.
