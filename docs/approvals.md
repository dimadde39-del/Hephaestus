# Tool Approvals

Hephaestus keeps approval gates short and practical.

The runtime does not moralize about local development work. It classifies the
action, shows the reason, then either runs, waits for `--yes`, or blocks the
action.

## Defaults

- Read-only filesystem actions run without approval.
- Safe validation commands can run locally through `heph tools run ... --yes`.
- Repo validation suites require explicit `--yes` before execution; without it,
  `heph validate run .` records approval-required evidence instead of pretending
  validation passed.
- Patch application requires approval and creates a checkpoint first.
- Medium and high-risk commands require approval.
- External side effects require approval or are blocked by stricter profiles.
- Obvious destructive commands are blocked in Phase 5E.

Use:

```bash
uv run heph tools run "python --version" --dry-run
uv run heph tools run "python --version" --yes
uv run heph validate run . --dry-run
uv run heph validate run . --yes
uv run heph tools patch apply <patch_id> --yes
```

`--require-approval` forces the approval gate even when an action is otherwise
safe. `--dry-run` never executes or writes.

## Policy Profiles

The active Phase 5D policy profile changes the gate:

- `developer`: allows benign local development; approval-gates side effects.
- `research`: favors analysis/read-only exploration; execution is more gated.
- `local_power_user`: fewer clarifying pauses; destructive/external effects stay gated.
- `strict`: more conservative, blocking high-risk and external actions.
- `balanced`: default practical behavior.

Approval decisions are persisted in `tool_approvals` and linked back to the tool
action.

Validation approval decisions are additionally reflected in
`validation_evidence` and release readiness. A missing `--yes` produces
`requires_approval`; it does not count as real passing validation evidence.
