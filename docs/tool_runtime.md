# Safe Tool Execution Runtime

Phase 5E gives Hephaestus controlled local hands.

The runtime follows:

```text
think -> explain -> classify risk -> ask approval -> execute safely -> observe output -> learn
```

It is the execution substrate for Phase 5G's controlled coding loop. The runtime
can apply a reviewed patch and create a checkpoint, but it does not decide on
its own what to edit. Conversations can propose tool or coding actions, but they
do not run tools automatically.

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
uv run heph validate plan .
uv run heph validate run . --dry-run
uv run heph validate run . --yes
uv run heph code plan "Update README wording to mention validation-backed release evidence." --repo .
uv run heph code propose "Update README wording to mention validation-backed release evidence." --repo .
uv run heph code run "Update README wording to mention validation-backed release evidence." --repo . --dry-run
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

## Validation Runtime

Phase 5F routes repo-derived validation commands through this same shell
runtime. `heph validate run . --dry-run` records what would run without
executing. `heph validate run . --yes` executes only the supported validation
commands selected from repo intelligence, such as lint, test, typecheck, build,
format-check, and security-check commands.

Validation execution stores:

- the tool action and tool execution result,
- command stdout/stderr summaries,
- exit code, duration, timeout, and truncation state,
- a validation evidence record,
- a validation outcome,
- learning signals for meaningful failures or missing commands.

Destructive commands are not validation commands and remain blocked.

## Coding Loop Runtime Use

Phase 5G uses the same runtime rather than adding a second file mutation path.

The coding loop:

- plans with repo intelligence and policy context,
- creates a deterministic patch proposal without writing files,
- reviews the patch against scope and protected-file rules,
- applies the stored tool-runtime patch only with `--yes`,
- relies on runtime checkpoint creation before the file write,
- runs validation through `heph validate` internals,
- optionally restores the checkpoint when validation fails.

Low-risk docs, tests, and config/help text can be batched under one `--yes`.
Medium-risk work still requires clearer explicit approval. Destructive or
external-side-effect behavior remains blocked by the runtime policy layer.

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

Phase 5E is a runtime foundation. Phase 5F uses it for approved validation.
Phase 5G uses it for small scoped coding loops. It still does not browse,
deploy, publish, push, run as a daemon, or turn chat into an execution loop.

## Studio Workbench

Studio Workbench translates tool runtime records into a user-readable timeline
at `/workbench/tools`.

Examples:

- `Read README.md`
- `Searched 14 files`
- `Created checkpoint`
- `Applied patch to 2 files`
- `Ran uv run pytest`
- `Restored checkpoint`

Exact paths, commands, stdout, stderr, action ids, and outcome ids are available
in detail views but do not dominate the timeline. Protected-file contents and
secrets are redacted before they reach the UI.
