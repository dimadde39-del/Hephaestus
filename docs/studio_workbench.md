# Hephaestus Studio Workbench

Phase 5.5B adds Workbench to Studio.

```text
Chat answers what we are working on.
Workbench answers what the agent is doing, what changed, whether it worked,
whether it can be undone, and whether it needs a real decision from the user.
```

Chat remains the default route and the primary product surface.

## Routes

```text
/workbench
/workbench/coding
/workbench/coding/{request_id}
/workbench/validation
/workbench/validation/{result_id}
/workbench/checkpoints
/workbench/checkpoints/{checkpoint_id}
/workbench/tools
/workbench/tools/{action_id}
/workbench/releases
/workbench/releases/{release_plan_id}
/workbench/outcomes
/workbench/outcomes/{outcome_id}
/workbench/trust
```

Deep links and browser navigation are preserved.

## Overview

The overview shows practical current work:

- active coding work;
- recent completed coding work;
- recent validation runs;
- failed validation requiring attention;
- pending meaningful user decisions;
- recent checkpoints;
- latest release evidence.

It intentionally avoids vanity analytics, raw JSON, and advanced optimization
metrics.

## Coding

The coding list supports deterministic local search and filters for status,
repo, and linked conversation. Rows show request title, repo/workspace, scope,
risk, status, files touched, validation result, checkpoint state, linked
conversation, and timestamps.

The coding detail view shows:

- original request and linked conversation;
- repo, scope, risk, and trust profile;
- concise plan, expected files, validation strategy, rollback behavior, and
  current state;
- proposed/applied files, patch status, review result, and diff viewer;
- validation commands and evidence;
- result, practical next step, checkpoint availability, and rollback state;
- advanced identifiers collapsed by default.

## Diff Viewer

Diffs render as structured unified diffs rather than one large preformatted
block. The viewer includes:

- changed file list;
- file collapse;
- line numbers;
- additions and deletions;
- copy patch;
- proposed/applied state;
- protected-file warning;
- large-diff indicator.

Large diffs are truncated by the backend before rendering.

## Validation

Validation list and detail pages show real or dry-run evidence without loading
huge output by default.

Each command shows type, exact command, risk, status, exit code, duration,
summary, linked tool action, linked outcome, and readiness effect. Stdout and
stderr stay collapsed until opened.

## Checkpoints And Rollback

Checkpoint detail pages summarize covered files, original hashes, related
patch, validation result, restore warnings, and restore history.

Studio restore uses the same Python runtime as the CLI. The UI asks once for
the whole checkpoint and restores only files captured by that checkpoint.

## Tool Actions

The tool timeline translates internal records into plain language:

- `Read README.md`
- `Searched 14 files`
- `Created checkpoint`
- `Applied patch to 2 files`
- `Ran uv run pytest`
- `Restored checkpoint`

Exact paths, commands, stdout, stderr, IDs, and links live in expandable/detail
sections. Protected file contents and secret-like output are redacted.

## Release Evidence

Release views show repo, readiness, evidence mode, validation status, blockers,
recommendation, linked work, and created time. Detail pages show practical
release summary, validation evidence, blockers, next actions, and related
coding requests.

Pareto and QUBO details are under "Advanced optimization details" and collapsed
by default.

## Outcomes

Outcome views use human language:

```text
Patch applied successfully.
All validation commands passed.
Hephaestus will reuse this validation order for similar work in this repo.
```

"What Hephaestus learned" appears only when there is a meaningful behavioral
implication.

## Chat Integration

Conversation messages can include compact Workbench artifact cards for coding
requests, patch proposals, validation results, checkpoints, and release plans.
Cards are secondary to the conversation and link to Workbench. Original message
content is unchanged.

Workbench detail pages show "Open linked conversation" when an artifact has a
conversation link.

## Launching Work

Studio can call existing Python orchestrators for selected operations:

- create coding plan;
- propose scoped change;
- run validation dry-run;
- run approved validation;
- apply existing patch proposal;
- restore checkpoint.

Studio does not expose arbitrary shell input, deploy, dependency installation,
Git push, or external messaging in this phase.
