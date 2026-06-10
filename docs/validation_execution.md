# Validation Execution

Phase 5F turns repo validation from suggested commands into real evidence.

```text
repo validation plan -> approved execution -> command results -> outcomes -> learning signals
```

## Commands

```bash
uv run heph validate plan .
uv run heph validate run . --dry-run
uv run heph validate run . --yes
uv run heph validate run . --only lint
uv run heph validate run . --only test
uv run heph validate run . --only typecheck
uv run heph validate run . --stop-on-failure --yes
uv run heph validate results
uv run heph validate latest .
uv run heph validate show <validation_result_id>
```

## Planning

`heph validate plan <path>` loads or creates a repo profile, then converts
supported repo validation signals into a `ValidationExecutionPlan`.

Supported command types:

- `lint`
- `test`
- `typecheck`
- `build`
- `format_check`
- `security_check`
- `custom`

The planner detects commands from Python/uv, Node package scripts, Rust Cargo,
and Go modules. It does not invent unsupported commands. Commands are classified
through the tool runtime risk classifier and marked as approval-gated or blocked.

## Execution

`heph validate run <path> --dry-run` records the plan and tool runtime dry-run
results without executing repository commands.

`heph validate run <path> --yes` executes approved validation commands through
`ToolRuntime.run_command`. Each command captures:

- status,
- exit code,
- stdout/stderr summaries,
- duration,
- timeout state,
- output truncation,
- linked tool action ID,
- linked tool execution result ID.

Without `--yes`, validation records `requires_approval` evidence instead of
pretending the command passed.

## Evidence

Validation statuses:

- `passed`
- `failed`
- `skipped`
- `timed_out`
- `blocked`
- `requires_approval`
- `unknown`

Each command creates `ValidationEvidence`. The suite creates a
`ValidationSuiteResult`, pass/fail counts, evidence mode, and readiness impact.

Evidence modes:

- `real_validation_evidence`
- `dry_run_no_execution`
- `approval_gated_no_execution`
- `no_validation_evidence`

## Outcomes And Learning

Every validation command gets an outcome record. Failures, timeouts, blocked
commands, and approval-required commands can produce validation strategy learning
signals. Repeated meaningful failures can draft failure memories.

Learning is intentionally conservative: Hephaestus does not spam records for
every line of output, and it does not auto-activate policy/profile changes.

## Limitations

- This is not an autonomous coding loop.
- Hephaestus does not edit files to fix validation failures in Phase 5F.
- Deploy, publish, push, destructive, and external side-effect commands are not
  validation commands.
- Command detection is manifest/config based and may miss project-specific docs.
- Passing local validation does not prove external release safety.
