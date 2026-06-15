# Coding Loop Safety

The Phase 5G coding loop is designed to avoid approval spam while still keeping
file writes explicit and reversible where practical.

## Approval Behavior

No approval is required for:

- repo inspection,
- reading normal repo files,
- searching files,
- planning,
- patch proposal,
- dry-run validation.

Approval or `--yes` is required for:

- applying patches,
- modifying files,
- running validation commands when the active policy requires it,
- restoring checkpoints,
- medium/high-risk local actions.

Blocked by default:

- destructive commands,
- protected secret-like files,
- filesystem operations outside the workspace,
- external side effects,
- mass deletion,
- deploy/publish/push workflows.

## Review Checks

Before apply, Hephaestus reviews the patch for:

- match with the user request,
- expected files,
- protected files,
- obvious secrets in added lines,
- scope drift,
- high-risk or oversized work,
- validation availability.

If review fails, the apply step is blocked with a short reason. No lecture, no
pretend safety theater.

## Checkpoints

Patch application uses the Phase 5E tool runtime. Before writing, the runtime
captures a checkpoint for the touched files. A checkpoint stores the original
content, hash, timestamp, workspace path, and action id.

`--rollback-on-failure` restores that checkpoint when validation fails.

## Policy Profiles

The active Phase 5D policy profile shapes approval behavior:

- `developer` keeps benign local development direct and approval-gates side
  effects.
- `research` approval-gates execution more often.
- `local_power_user` avoids unnecessary pauses for normal local work.
- `strict` blocks more high-risk and external-side-effect actions.

The coding loop records the active policy profile on requests, plans, changes,
and results.

## Limits

The loop defaults to one iteration. If validation fails, Hephaestus records the
failure and may suggest the next step, but it does not blindly keep editing.

This phase is not a daemon, cloud VM, browser agent, release bot, or capability
forge. It is the first practical patch/validate/learn loop.
