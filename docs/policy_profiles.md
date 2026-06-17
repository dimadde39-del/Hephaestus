# Policy Profiles

Policy profiles are Hephaestus's configurable freedom boundary. They decide how
the conversation layer treats benign work, approval-gated side effects, and
genuinely harmful requests. Phase 5E also uses the active profile when local
tool actions are classified.

## Profile Types

- `balanced`: default if nothing is configured.
- `developer`: recommended for Hephaestus users building local/open-source
  projects.
- `research`: analysis-first profile for theory, defensive security, and
  architecture.
- `local_power_user`: fewer clarifying questions for user-owned local
  development.
- `strict`: conservative profile for demos, classrooms, and enterprise-like
  contexts.
- `custom`: schema-supported custom profiles for future editing flows.

## Decisions

- `allow`: help directly.
- `allow_with_context`: help, while naming relevant limits.
- `ask_clarifying_question`: ask for missing user-owned or defensive context.
- `require_approval`: do not execute or cause side effects without explicit
  approval.
- `refuse_briefly`: short boundary response.
- `block`: do not help with the harmful request.

## Risk Categories

Benign categories include creative work, development, research, and strategy
discussion. Approval-gated categories include local file operations, command
execution, external side effects, and destructive actions. Blocked categories
include credential theft, malware/abuse, violence, exploitation, and targeted
harassment.

## Persistence

The active profile is stored in `.hephaestus/hephaestus.db` in
`policy_settings`. Custom profiles and policy evaluations are stored in the same
local SQLite database. If no active profile is configured, Hephaestus uses
`balanced`.

## CLI

```bash
uv run heph policy profiles
uv run heph policy active
uv run heph policy set developer
uv run heph policy show developer
uv run heph policy evaluate "be brutally honest about this roadmap"
uv run heph policy benchmark run
```

Use `developer` for the intended open-source power-user experience.

## Tool Runtime Integration

`heph tools` records the active profile on every action. The profile affects
whether safe validation can run directly, whether medium/high-risk work needs
approval, and whether external or destructive actions are blocked.

The default remains practical: normal local development can move, while
file-changing, external, and destructive actions stay explicit.

## Studio Trust Settings

Studio Workbench adds local trust settings at `/workbench/trust`.

Modes:

- `Manual`
- `Developer`
- `Local Power User`
- `Strict`

These modes map to existing policy profiles and implemented runtime behavior.
They can automatically allow safe analysis such as repo reads, search, repo
metadata inspection, coding plans, patch proposals, checkpoints, and safe
validation. Low-risk documentation or code patch application can be enabled
only when the corresponding rule is implemented and allowed.

Medium-risk work still requires meaningful confirmation. External side effects
such as dependency installation, Git push, deploy, publish, or external messages
remain explicit or blocked. Trust settings cannot override hard destructive
blocks.

Preferences are stored locally in `studio_trust_settings` and displayed with
their effective behavior so the UI is not decorative.
