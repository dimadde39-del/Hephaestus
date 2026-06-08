# Release Plan Demo

The release planning demo is the fastest way to understand Hephaestus today.
It uses the current repository as the target and runs the planning loop without
executing repo commands.

```bash
uv run heph release plan . --pareto --qubo --evaluate
```

## Flow

```text
Repo Inspect -> Repo Plan -> Optimize -> Pareto -> QUBO -> Explain -> Evaluate -> Learn
```

At a high level, expect:

```text
Repo inspected
Release tasks generated
Pareto tradeoffs compared
QUBO problems formulated
Decision traces saved
Outcomes evaluated
Learning signals created
```

## Annotated Output

### Repo-Aware Release Planning

This panel gives you the IDs that tie the demo together:

```text
Release plan: release_...
Repo profile: repo_...
Optimizer run: run_...
Readiness score: 80/100
Recommendation: needs_validation
```

The readiness score is deterministic and coarse. It is not proof that a release
passed. In the current alpha, `needs_validation` is the honest default when the
repo has validation commands that Hephaestus has detected but not executed.

### Demo Flow

This table shows which artifacts were created at each stage:

```text
Repo Inspect    repo_...                      1
Repo Plan       generated release tasks       N
Optimize        run_...                       1
Pareto          frontier_...                  N
QUBO            qubo_...                      N
Explain         trace_...                     N
Evaluate        outcome_...                   N
Learn           signal_...                    N
```

### Readiness Signals

This table explains why the recommendation was conservative. Signals include
repo profile confidence, detected validation commands, tests, build/lint
commands, CI files, env-file posture, approval gates, optimizer persistence,
Pareto feasibility, and QUBO feasibility.

### Release Task Plan

This table contains generated repo-aware tasks. The command column shows
detected validation or package-script commands when available. The approval
column shows tasks that future execution phases must gate.

### Release Recommendation

The recommendation panel summarizes the status, why Hephaestus chose it, and
what should happen next. Typical alpha reasons include:

```text
- lint/build/test commands were detected but not executed.
- CI configuration was detected.
- env files were detected by name; contents were not inspected.
- publish/deploy/destructive scripts require approval before execution.
```

### Linked Artifacts

The final panel gives follow-up commands for inspecting what was saved.

## What Is Real

- Repository inspection reads local files and filenames read-only.
- Repo profiles are persisted in SQLite.
- Release-readiness tasks are generated from detected repo signals.
- Optimizer runs, tasks, decisions, approvals, and decision traces are persisted.
- Pareto frontiers compare real candidate objective vectors.
- QUBO problems are formulated and solved locally with classical solvers.
- Release plans link the saved repo, run, Pareto, QUBO, trace, outcome, and
  learning artifacts.

## What Is Simulated

- `--evaluate` creates deterministic outcomes from decision traces.
- Reflections and learning signals are generated from those simulated outcomes.
- No validation commands are executed.
- No code is edited.
- No package is published.
- No deployment is attempted.
- QUBO/Ising support is local classical optimization, not quantum hardware.

## Inspect The Linked Run

List saved release plans:

```bash
uv run heph release list
```

Open a release plan:

```bash
uv run heph release show <release_run_id>
```

List recent optimizer runs:

```bash
uv run heph runs
```

Inspect the optimizer run linked from the release plan:

```bash
uv run heph run show <optimizer_run_id>
```

Explain the decision trace:

```bash
uv run heph explain <optimizer_run_id>
uv run heph explain <optimizer_run_id> --summary
```

List persisted Pareto frontiers:

```bash
uv run heph pareto list
```

Open a frontier:

```bash
uv run heph pareto show <frontier_id>
```

List persisted QUBO problems:

```bash
uv run heph qubo list
```

Open a QUBO problem:

```bash
uv run heph qubo show <problem_id>
```

Inspect simulated outcome learning:

```bash
uv run heph outcome list --run <optimizer_run_id>
uv run heph learn signals --run <optimizer_run_id>
```

## Boundary

Hephaestus does not run blindly. The current demo proves the planning and
explanation loop:

```text
Inspect first.
Optimize honestly.
Explain every important decision.
Learn from outcomes.
Execute safely later.
```
