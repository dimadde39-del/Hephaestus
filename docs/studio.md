# Hephaestus Studio

Studio is the local web interface for persistent Hephaestus chat, readable
agent work inspection, memory control, and local configuration.

```text
Talk in Chat.
Inspect real work in Workbench.
Control durable context in Memory.
Configure local behavior in Settings.
```

Chat remains the default startup route and the primary product surface.
Workbench is a second route family for understanding what the agent did, what
changed, whether validation passed, whether rollback exists, and whether
Hephaestus needs a meaningful decision from the user.
Memory and Settings are deliberately quieter than Chat and Workbench, but they
are first-class routes. Advanced internals are secondary and require deliberate
navigation.

## Install And Run

From a source checkout:

```bash
uv sync --extra studio
uv run heph studio
```

Useful variants:

```bash
uv run heph studio --port 8741
uv run heph studio --host 127.0.0.1
uv run heph studio --no-open
uv run heph studio doctor
```

Default URL:

```text
http://127.0.0.1:8741
```

`heph studio` prints the local URL, active database path, active policy profile,
and configured conversation provider. It opens a browser unless `--no-open` is
passed.

## What Studio Does

- Create conversations.
- Reopen old conversations.
- Display exact chronological user and assistant messages.
- Continue the same conversation through the existing conversation service.
- Search conversation titles, user messages, and assistant messages locally.
- Pin, rename, and archive conversations.
- Select a deliberation mode.
- Attach optional repo context from recent repo profiles.
- Show active policy profile and provider state.
- Inspect coding requests, plans, patch proposals, file diffs, validation runs,
  checkpoints, tool actions, release evidence, outcomes, and trust settings.
- Restore available checkpoints through the Python runtime after one batch
  confirmation.
- Open linked Workbench artifacts from compact chat cards without changing the
  original messages.
- Review, create, edit, archive, restore, and delete regular and strategic
  memories.
- Save or ignore conversation memory suggestions without modal interruption.
- Configure local deterministic, DeepSeek, and OpenAI-compatible providers
  without exposing stored API keys.
- Show restrained model usage estimates, deterministic operations, and provider
  usage.
- Export conversations as exact Markdown or JSON, export memories as JSON, back
  up the SQLite database, and restore compatible backups.
- Inspect advanced decision traces, Pareto frontiers, and QUBO formulations
  through secondary Advanced routes.

## Navigation

The product hierarchy is:

```text
Chat -> Workbench -> Memory -> Settings -> Advanced
```

Current deep-link route families:

```text
/conversations/{session_id}
/workbench
/workbench/coding/{request_id}
/workbench/validation/{result_id}
/workbench/checkpoints/{checkpoint_id}
/workbench/releases/{release_plan_id}
/memory
/memory/{memory_id}
/settings
/settings/models
/settings/policy
/settings/data
/settings/appearance
/advanced/decisions
/advanced/decisions/{trace_id}
/advanced/pareto/{frontier_id}
/advanced/qubo/{problem_id}
```

Browser back/forward follows the route state. Chat remains the default route;
there is no dashboard home page.

## Workbench

Workbench routes are deep-linkable:

```text
/workbench
/workbench/coding
/workbench/coding/{request_id}
/workbench/validation
/workbench/checkpoints
/workbench/tools
/workbench/releases
/workbench/outcomes
/workbench/trust
```

The overview shows active coding work, recent completed work, validation that
needs attention, pending decisions, checkpoints, and latest release evidence.
It deliberately avoids vanity metrics and raw database objects.

Coding detail pages show the original request, linked conversation, plan,
expected files, validation strategy, patch status, a readable unified diff,
validation evidence, result, rollback state, and collapsed advanced details.

Validation detail pages show exact commands, status, exit code, duration,
concise output summaries, and collapsed stdout/stderr. Large output is
truncated by the backend and marked in the UI.

See [Studio Workbench](studio_workbench.md) for the full user-facing shape and
[Studio trust and approvals](studio_trust_and_approvals.md) for autonomy modes.

## Memory

Memory shows what Hephaestus believes is worth carrying forward. It combines
regular project memories and strategic memories behind human labels such as
Goal, Constraint, Preference, Principle, Strategic decision, Rejected path,
Lesson learned, Open question, Project fact, and Working style.

List filters cover search, type, scope, repo, and archive state. Detail views
show content, summary, scope, confidence, source, evidence, linked
conversation/work, simple conflict warnings, and history when available.

See [Studio Memory](studio_memory.md).

## Settings

Settings is organized into General, Appearance, Models, Policy and Trust, Data,
and Advanced. Model settings support local deterministic mode, DeepSeek, and
OpenAI-compatible providers including OpenRouter-compatible endpoints.

Secrets are stored locally in the Studio SQLite database and never returned by
normal API responses. Exports exclude secrets.

See [Studio Model Settings](studio_model_settings.md) and
[Studio Backup And Export](studio_backup_and_export.md).

## Onboarding

First run opens a short non-blocking onboarding flow:

1. Welcome.
2. Choose local deterministic mode or configure a provider.
3. Choose a repo/workspace or skip.
4. Choose trust/autonomy mode.
5. Start a conversation.

Skipping onboarding is persisted locally in the browser.

## Persistent History

Studio does not generate a recap when a conversation opens.

```text
persist exact messages -> reopen the same conversation -> read the original timeline -> continue naturally
```

Opening an old chat reads SQLite rows. It does not call a model, spend provider
tokens, or replace old messages with compressed summaries. The user can ask for
a summary later, but that is explicit conversation behavior, not automatic UI
startup behavior.

## Search

Search is deterministic and local in Phase 5.5A. It covers:

- conversation titles;
- user messages;
- assistant messages.

Archived conversations are protected by an explicit filter. Search does not use
a model and does not consume tokens.

## Modes And Repo Context

Studio supports the same deliberation modes as CLI conversation:

```text
balanced, direct, critical, strategic, research, architect, coach, skeptical_but_fair
```

When a conversation has a mode or repo profile, Studio preserves and displays
it. Changing the selector updates conversation metadata and affects future
messages. Studio does not silently attach unrelated repositories.

## Provider States

Studio works without API keys.

- `Local deterministic mode`: no external provider required.
- `DeepSeek`: shown when DeepSeek is configured and selected.
- `OpenAI-compatible: <model>`: shown when OpenAI-compatible settings are
  configured.

Conversation text is sent to a configured external provider only when the user
submits a message. Reopening a conversation is local database reading.

## Local Security Model

- Default host is `127.0.0.1`.
- `0.0.0.0` is never used unless the user explicitly passes it.
- CORS origins are exact local origins, not wildcard.
- Frontend code calls the local Python API; it does not read SQLite directly.
- Protected file contents are not exposed.
- Workbench does not expose arbitrary shell input.
- Destructive/system-level actions remain blocked by runtime policy.
- There is no account system or cloud authentication.

## Development

Backend:

```bash
uv run ruff check .
uv run pytest
uv run mypy
uv run heph studio doctor
uv run heph studio --no-open
```

Frontend:

```bash
cd apps/studio
pnpm install
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

The built static frontend is exported to `apps/studio/out/` and can be served
by the Python backend. Build artifacts and `node_modules` are intentionally not
committed.

See [Studio Packaging](studio_packaging.md) for wheel/sdist validation and
temporary install smoke tests.

## Current Limitations

- No streaming stop/cancel button yet.
- No Electron or Tauri packaging.
- Workbench actions are synchronous with clear loading states rather than fake
  streaming.
- Search is simple SQL rather than FTS.
- Provider key storage is local SQLite with OS file permissions; OS keychain
  integration remains future work.
- Advanced views show structured decision artifacts only, not private
  chain-of-thought.
