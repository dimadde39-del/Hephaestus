# Contributor Guide

This guide gives new contributors the project context behind
[CONTRIBUTING.md](../CONTRIBUTING.md).

## The Product Bet

Most agent demos jump from prompt to action. Hephaestus focuses on the part
before action: decision quality.

```text
Hermes learns workflows.
Hephaestus learns decision quality.
```

That means the core system should be able to answer:

- What did it inspect?
- What plan did it generate?
- What alternatives did it compare?
- What tradeoffs did it expose?
- Why did it choose this option?
- What happened afterward?
- What should future decisions learn?

## Current Priorities

- Make the release planning demo easy to run and explain.
- Strengthen repo-aware task generation and validation planning.
- Improve decision traces and explanation quality.
- Improve deterministic outcome learning.
- Keep policy learning reviewable and reversible.
- Prepare for safe validation execution later.

## Deferred Work

The following are intentionally not current priorities:

- Voice features.
- Telegram/Discord bots.
- Dashboards.
- Browser automation.
- Autonomous repo editing.
- Daemon behavior.
- Broad integration marketplaces.

If a contribution touches one of these, it should first explain why it is needed
for core decision quality now.

## Development Commands

```bash
uv sync --extra dev
uv run ruff format .
uv run ruff check .
uv run pytest
uv run mypy
uv run heph doctor
uv run heph release plan . --pareto --qubo --evaluate
uv run heph release list
uv run heph runs
```

## Design Expectations

- Prefer explicit Pydantic schemas for persisted artifacts.
- Keep SQLite migrations simple and local-first.
- Keep CLI output readable for people who are not already familiar with the
  internals.
- Make unsafe or simulated behavior visible in the output.
- Add explanations near the decision, not as an afterthought.
- Keep future execution gated by risk classification and approval records.

## Good First Issue Areas

- Improve docs clarity with real command output.
- Add tests around edge cases in repo inspection.
- Improve wording in Rich renderers without changing behavior.
- Add small benchmark fixtures that stress one clear optimizer behavior.
- Add examples that show how to inspect saved artifacts.
