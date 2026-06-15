# Contributor Guide

This guide gives new contributors the project context behind
[CONTRIBUTING.md](../CONTRIBUTING.md).

## The Product Bet

Most agent demos jump from prompt to action and then lose the trail.
Hephaestus focuses on the local loop around the model:

```text
context -> plan -> patch -> validate -> outcome -> memory
```

That means the core system should be able to answer:

- What did it inspect?
- What context or memory shaped the work?
- What plan did it generate?
- What alternatives did it compare?
- What tradeoffs did it expose?
- Why did it choose this option?
- What patch or command was proposed?
- What validation evidence exists?
- What happened afterward?
- What should future decisions learn?

## Current Priorities

- Keep the README and public docs product-first and honest.
- Make the current conversation, validation, and coding-loop demos easy to run.
- Strengthen repo-aware scoped change planning.
- Improve validation evidence, outcomes, and learning signals.
- Improve decision traces and explanation quality without making them the public
  headline.
- Keep policy learning reviewable and reversible.
- Prepare the persistent Studio interface before Phase 6.

## Deferred Work

The following are intentionally not current priorities:

- Voice features.
- Telegram/Discord bots.
- Always-on daemon work.
- Browser automation.
- Full autonomous repo editing.
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
uv run heph validate run . --dry-run
uv run heph code run "Update README wording to mention validation-backed release evidence." --repo . --dry-run
uv run heph release plan . --pareto --qubo --with-validation --yes
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
