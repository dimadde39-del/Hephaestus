# Checkpoints And Rollback

Phase 5E adds lightweight rollback for files changed by Hephaestus.

Before applying a patch, the runtime stores the original contents, file hash,
timestamp, workspace path, and action id for every touched file. Restore only
uses files captured by that checkpoint.

## Commands

```bash
uv run heph tools checkpoint list
uv run heph tools checkpoint show <checkpoint_id>
uv run heph tools checkpoint restore <checkpoint_id> --yes
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
