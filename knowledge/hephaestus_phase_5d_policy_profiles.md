# Hephaestus Phase 5D: User-Owned Policy Profiles

Phase 5D adds the policy profile layer before safe tool execution.

Built:

- `src/hephaestus/policy/` with schemas, built-in profiles, classifier,
  evaluator, repository, renderer, and benchmark analysis helpers.
- SQLite migration 12 for active policy settings, custom profiles, and policy
  evaluations.
- `heph policy profiles/active/set/show/evaluate`.
- `heph policy benchmark list/run`.
- Conversation integration for active policy profiles, prompt guidance,
  approval boundaries, blocked-request short-circuiting, and over-refusal
  detection.
- Policy fixtures for benign creative work, harsh critique, defensive security,
  local development, destructive approval gating, and explicit abuse blocking.

Product correction:

- Phase 5D is not Safe Tool Execution Runtime.
- Safe Tool Execution Runtime is Phase 5E.

Recommended next phase:

```text
Phase 5E: Safe Tool Execution Runtime
```

That phase should add controlled local filesystem tools, a shell command
wrapper, approval gates, checkpoints, rollback, observations, and outcome
learning.
