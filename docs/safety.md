# Safety

Hephaestus treats tool execution as a policy decision before it becomes an
action.

## Phase 1 Rules

- Read-only actions are allowed by default.
- Writes require policy checks and approval.
- Destructive shell commands require approval and are blocked until approved.
- `git commit`, `git push`, and package publish commands require approval.
- Commands touching `.env`, exporting secrets, or piping `curl`/`wget` into a
  shell require approval.
- External sending actions are approval-gated.

## Current Dangerous Command Examples

- `rm -rf`
- `git push`
- `npm publish`
- commands touching `.env`
- commands exporting secrets
- `curl ... | sh`
- `wget ... | bash`

## Future Sandbox Plan

- Workspace allowlists.
- Read/write path scopes.
- Dry-run previews for mutating tools.
- Secret redaction in audit logs.
- Interactive approval workflows.
- Containerized or microVM execution for untrusted tools.

