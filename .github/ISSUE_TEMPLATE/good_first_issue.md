---
name: Good first issue
about: Propose a scoped starter task
title: "[Good first issue] "
labels: good first issue
assignees: ""
---

## Task

Describe the small, scoped improvement.

## Area

Choose one:

- Docs clarity.
- CLI wording.
- Repo inspection test.
- Benchmark fixture.
- Explanation rendering.
- Contributor onboarding.

## Why it helps

Explain how this improves public alpha readiness or the core decision loop.

## Suggested validation

```bash
uv run ruff check .
uv run pytest
uv run heph doctor
uv run heph release plan . --pareto --qubo --evaluate
```
