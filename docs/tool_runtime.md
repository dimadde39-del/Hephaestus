# Safe Tool Execution Runtime

Phase 5E gives Hephaestus controlled local hands.

The runtime follows:

```text
think -> explain -> classify risk -> ask approval -> execute safely -> observe output -> learn
```

It is not a full autonomous coding loop. Conversations can propose tool actions,
but they do not run tools automatically.

## Commands

```bash
uv run heph tools list .
uv run heph tools read README.md
uv run heph tools search "Hephaestus" --path README.md
uv run heph tools run "python --version" --dry-run
uv run heph tools run "python --version" --yes
uv run heph tools patch propose README.md --find "old" --replace "new"
uv run heph tools patch apply <patch_id> --yes
uv run heph tools actions
uv run heph tools action show <action_id>
uv run heph tools checkpoint list
uv run heph tools checkpoint show <checkpoint_id>
uv run heph tools checkpoint restore <checkpoint_id> --yes
```

## Risk Levels

The runtime reuses repo intelligence command categories:

- `safe_readonly`: file listing, normal reads, search, read-only shell inspection.
- `safe_validation`: test, lint, typecheck, build-check, and version commands.
- `medium_risk`: local mutation, installs, git commit/tag, Docker local work.
- `high_risk`: secret-like access, migrations, release workflows.
- `destructive`: obvious deletion, wipes, database drops or resets.
- `external_side_effect`: push, publish, deploy, upload, or network script execution.

## Read And Write Rules

Filesystem tools stay inside the resolved workspace unless an internal caller
explicitly opts out. Protected files such as `.env`, private keys, token files,
credential files, and SSH keys are detected by metadata. Their contents are not
printed by default.

Writing is patch-based in Phase 5E. Hephaestus proposes a deterministic diff,
stores the proposal, then applies it only after approval. Patch application
creates a checkpoint first.

## Shell Runtime

Shell commands are classified before execution. Safe read-only and safe
validation commands can run directly; `--dry-run` records the plan without
execution. Medium, high, and external-side-effect commands require approval.
Obvious destructive commands are blocked in Phase 5E.

Every shell result captures stdout, stderr, exit code, timeout state, truncation
state, a tool observation, and decision/outcome links where practical.

## Persistence

Tool actions are stored in SQLite:

- `tool_actions`
- `tool_approvals`
- `tool_execution_results`
- `tool_observations`
- `tool_checkpoints`

Records include risk level, active policy profile, workspace, command or path,
approval status, execution status, output summaries, touched files, optional
checkpoint, decision trace, outcome, conversation, run, and repo profile links.

## Boundaries

Phase 5E is a runtime foundation. It does not autonomously edit a repo, browse,
deploy, publish, push, run as a daemon, or turn chat into an execution loop.
Phase 5F can use this runtime to execute real validation plans and turn results
into stronger outcome learning.
