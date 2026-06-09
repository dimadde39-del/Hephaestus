# Policy Profiles

Policy profiles are Hephaestus's configurable freedom boundary. They decide how
the conversation layer treats benign work, approval-gated side effects, and
genuinely harmful requests.

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
