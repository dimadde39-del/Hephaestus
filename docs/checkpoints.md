# Checkpoints And Rollback

Phase 5E adds lightweight rollback for files changed by Hephaestus.
Phase 5G uses the same checkpoint mechanism before applying coding-loop patches.

Before applying a patch, the runtime stores the original contents, file hash,
timestamp, workspace path, and action id for every touched file. Restore only
uses files captured by that checkpoint.

## Commands

```bash
uv run heph tools checkpoint list
uv run heph tools checkpoint show <checkpoint_id>
uv run heph tools checkpoint restore <checkpoint_id> --yes
uv run heph code run "Update README wording to mention validation-backed release evidence." --repo . --yes --rollback-on-failure
```

Restore is local-file rollback, not a full git reset. If a file existed at
checkpoint time, it is recreated with the captured content. If it did not exist,
restore removes the file that Hephaestus created.

## Limits

Checkpoints are intentionally narrow:

- They cover files touched by Hephaestus tool actions.
- They do not restore arbitrary user edits outside that file set.
- They do not rewrite git history.
- They do not replace normal source control.

This is enough for Phase 5E patch safety and gives future autonomous coding work
a practical rollback foundation.

## Coding Loop Rollback

Before `heph code apply` or non-dry-run `heph code run` writes a patch, the tool
runtime captures a checkpoint for the touched files. The coding-loop result
links the checkpoint id.

When validation fails and `--rollback-on-failure` is set, Hephaestus restores
that checkpoint, records a rollback outcome, and writes a decision trace
explaining why rollback was selected. Without the flag, the failed validation is
recorded and the user decides the next step.

Rollback is intentionally narrow. It restores the files Hephaestus touched; it
does not hide unrelated user edits or rewrite git history.

## Studio Workbench

Studio Workbench shows checkpoints at `/workbench/checkpoints` and detail pages
at `/workbench/checkpoints/{checkpoint_id}`.

The list shows creation time, associated coding request, files covered,
availability, and restored state. The detail view shows covered files, original
hashes, related patch, validation result, restore history, and whether protected
paths are involved.

Restore from Studio uses the same Python runtime as the CLI. It asks for one
confirmation for the whole checkpoint, summarizes affected files, notes whether
later changes may be overwritten, and never restores outside the checkpoint's
captured file scope.
