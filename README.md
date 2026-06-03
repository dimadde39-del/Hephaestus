# Hephaestus

An open-source forge for always-on, self-improving AI agents.

Hephaestus explores optimization-first agent execution: what to do next, which
model to use, what context to include, which tools to call, and when to ask for
approval.

This repository is an early optimization-first agent runtime. It is not a
production agent OS yet, not a chatbot wrapper, and not a claim of AGI. It is a
typed, testable Python core for spec-driven planning, persistent local memory,
model routing, context packing, token budgeting, safe tool gating, benchmark
proof reports, and a working CLI demo.

## Core Loop

```text
Observe -> Understand -> Remember -> Specify -> Plan -> Optimize -> Act -> Reflect -> Grow
```

## Architecture

```text
CLI
 |-- Spec layer: constitution, goals, tasks, execution plans
 |-- Storage layer: SQLite memory, run history, decisions, approvals
 |-- Memory layer: episodic, semantic, project, failure, decision records
 |-- Optimization core
 |    |-- central objective function
 |    |-- greedy task scheduler
 |    |-- simulated annealing scheduler
 |    |-- model router
 |    |-- context packer
 |    `-- token firewall
 |-- Benchmark layer: fixtures, runner, reports, persisted proof runs
 |-- Model layer: provider interface, fake local provider, optional DeepSeek
 |-- Tool layer: typed tool definitions
 `-- Safety layer: approval gates, risky command policy, audit schemas
```

## Why Optimization-First Agents Matter

Agents spend most of their quality budget before they call a tool. They decide
what to do, what to remember, what to ignore, which model to use, and how much
risk to take. If those choices are random or cheapest-first, the agent can waste
tokens, miss critical context, or take unsafe actions.

Hephaestus treats planning as an optimization problem from the beginning. Phase 1
uses explainable greedy and simulated annealing baselines. Later phases can add
QUBO/Ising formulations, benchmarks, and multi-agent allocation.

## Quality-Preserving Token Optimization

The token firewall and router follow one rule:

```text
Cheap when possible. Strong when necessary. Local/private when required.
```

The model router minimizes estimated cost only after filtering for capabilities,
privacy, context window, tool/JSON support, and quality threshold. A cheap model
that cannot meet the threshold is rejected.

## Benchmark Proof Reports

Phase 2B adds benchmark commands that exercise the optimizer on designed task
graphs:

```bash
uv run heph benchmark list
uv run heph benchmark show model_quality_threshold
uv run heph benchmark run benchmarks/task_graphs/simple_release.json
uv run heph benchmark run
uv run heph benchmark run --json
```

Each benchmark compares greedy scheduling with simulated annealing, routes
models under quality thresholds, packs context under token pressure, checks
aggregate token/cost budgets, counts approval-gated tasks, and saves a
`mode=benchmark` run. Use `heph run show <run_id>` to inspect persisted tasks,
decisions, rejected models, context packing, budget decisions, and approvals.

The benchmark suite is designed to test optimizer behavior, not to claim
real-world AGI performance.

## Quickstart

```bash
uv sync --extra dev
uv run heph --help
uv run heph doctor
uv run heph db init
uv run heph db path
uv run heph plan "prepare this repo for release"
uv run heph optimize examples/repo_release_demo.json
uv run heph benchmark list
uv run heph benchmark run benchmarks/task_graphs/simple_release.json
uv run heph runs
uv run heph models
uv run heph memory add --type failure --content "Validation failed because tests were missing"
uv run heph memory search tests
uv run heph memory list
uv run heph budget demo
```

By default, durable local state is stored in:

```text
.hephaestus/hephaestus.db
```

The path is relative to the current working directory. Memory commands
auto-initialize the database, and `heph optimize ...` saves a run record with
tasks, scheduler decisions, model routing decisions, context packing, budget
evaluation, and pending approval markers. Use `heph run show <run_id>` to inspect
a saved run. Benchmark commands use the same durable run history with
`mode=benchmark`.

Optional DeepSeek API calls are disabled unless `DEEPSEEK_API_KEY` is set:

```bash
export DEEPSEEK_API_KEY="..."
```

On PowerShell:

```powershell
$env:DEEPSEEK_API_KEY = "..."
```

Tests do not require paid APIs.

## Development

```bash
uv run ruff format .
uv run ruff check .
uv run pytest
uv run mypy
uv run heph doctor
uv run heph db init
uv run heph optimize examples/repo_release_demo.json
uv run heph benchmark run benchmarks/task_graphs/simple_release.json
```

## Current Status

Built:

- Typed Pydantic schemas for tasks, models, memories, tools, and plans.
- Deterministic goal-to-task spec pipeline.
- SQLite-backed persistent memory with lexical retrieval.
- SQLite-backed optimization run history.
- Fake model provider and optional DeepSeek provider.
- Greedy and simulated annealing task schedulers.
- Quality-preserving model router.
- Context packing optimizer.
- Token firewall.
- Safety policy for risky tools and shell commands.
- Benchmark runner and optimizer proof reports.
- Typer/Rich CLI.

Not built yet:

- Live always-on daemon.
- Browser/desktop/voice/Telegram automation.
- Full self-improving skill promotion.
- Production sandbox execution.
