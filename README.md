# Hephaestus

An open-source forge for always-on, self-improving AI agents.

Hephaestus explores optimization-first agent execution: what to do next, which
model to use, what context to include, which tools to call, and when to ask for
approval.

This repository is an early Phase 0 / Phase 1 foundation. It is not a production
agent OS yet, not a chatbot wrapper, and not a claim of AGI. It is a typed,
testable Python core for spec-driven planning, local memory, model routing,
context packing, token budgeting, safe tool gating, and a working CLI demo.

## Core Loop

```text
Observe -> Understand -> Remember -> Specify -> Plan -> Optimize -> Act -> Reflect -> Grow
```

## Architecture

```text
CLI
 |-- Spec layer: constitution, goals, tasks, execution plans
 |-- Memory layer: episodic, semantic, project, failure, decision records
 |-- Optimization core
 |    |-- central objective function
 |    |-- greedy task scheduler
 |    |-- simulated annealing scheduler
 |    |-- model router
 |    |-- context packer
 |    `-- token firewall
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

## Quickstart

```bash
uv sync --extra dev
uv run heph --help
uv run heph doctor
uv run heph plan "prepare this repo for release"
uv run heph optimize examples/repo_release_demo.json
uv run heph models
uv run heph memory add --type failure --content "Validation failed because tests were missing"
uv run heph memory search tests
uv run heph budget demo
```

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
uv run heph doctor
uv run heph optimize examples/repo_release_demo.json
```

## Current Status

Built:

- Typed Pydantic schemas for tasks, models, memories, tools, and plans.
- Deterministic goal-to-task spec pipeline.
- In-memory memory store with lexical retrieval.
- Fake model provider and optional DeepSeek provider.
- Greedy and simulated annealing task schedulers.
- Quality-preserving model router.
- Context packing optimizer.
- Token firewall.
- Safety policy for risky tools and shell commands.
- Typer/Rich CLI.

Not built yet:

- Persistent SQLite memory.
- Live always-on daemon.
- Browser/desktop/voice/Telegram automation.
- Full self-improving skill promotion.
- Production sandbox execution.
- Optimization benchmarks.

