# Hephaestus Phase 2A Persistence

Phase 2A adds durable local state without turning Hephaestus into an always-on
daemon. The default database is:

```text
.hephaestus/hephaestus.db
```

The path is relative to the current working directory and is ignored by git.

## What Persists

- Memories: typed records with content, summary, tags, project, confidence,
  importance, verification time, and source.
- Runs: one row per CLI optimization run.
- Run tasks: selected task order and task metadata.
- Run decisions: scheduler, router, context packing, and budget choices.
- Approvals: pending approval-required actions discovered during optimization.

## Why It Matters

Always-on mode needs a durable substrate before it can safely loop in the
background. SQLite gives the CLI repeatable state across invocations, lets tests
verify run history, and prepares a stable source for future dashboard,
benchmark, skill growth, and daemon work.
