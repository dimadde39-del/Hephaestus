# Release Planning Demo

Use Hephaestus itself as the demo target:

```bash
uv run heph release plan . --pareto --qubo --evaluate
```

The command runs this local flow:

```text
Repo Inspect -> Repo Plan -> Optimize -> Pareto -> QUBO -> Explain -> Evaluate -> Learn
```

What happens:

- Hephaestus inspects the repository read-only.
- It persists a repo profile and generated release-readiness tasks.
- It converts the tasks into the existing optimizer-compatible format.
- It persists an optimizer run with `mode=release`.
- `--pareto` persists tradeoff frontiers.
- `--qubo` persists QUBO problems and local solver results.
- `--evaluate` generates simulated outcomes, reflections, and learning signals.
- It saves a `release_plans` row with all linked artifact IDs.

Sample output shape:

```text
Repo-Aware Release Planning
Release plan: release_...
Repo profile: repo_...
Optimizer run: run_...
Readiness score: 80/100
Recommendation: needs_validation

Demo Flow
Repo Inspect -> Repo Plan -> Optimize -> Pareto -> QUBO -> Explain -> Evaluate -> Learn

Release Recommendation
Recommendation: needs_validation

Why:
- lint/build/test commands were detected but not executed.
- CI configuration was detected.
- QUBO formulated 3 problem(s), 3 feasible.
- simulated outcomes and learning signals were generated from decision traces.
```

Inspect linked artifacts:

```bash
uv run heph release list
uv run heph release show <release_run_id>
uv run heph repo tasks <profile_id>
uv run heph run show <optimizer_run_id>
uv run heph explain <optimizer_run_id>
uv run heph pareto show <frontier_id>
uv run heph qubo show <problem_id>
uv run heph outcome list --run <optimizer_run_id>
uv run heph learn signals --run <optimizer_run_id>
```

Important boundary:

```text
Hephaestus does not run blindly.
It inspects the repository, builds a release plan, exposes tradeoffs, formulates optimizations, explains decisions, and records learning signals before execution is ever allowed.
```

Phase 4B does not execute validation commands, publish packages, deploy, edit
code, or run destructive commands. The recommendation is a planning
recommendation, not proof that a release passed.
