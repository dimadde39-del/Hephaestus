# Hephaestus Phase 5.5A: Studio Foundation + Persistent Chat

Phase 5.5A adds the first local Hephaestus Studio product surface.

## Product Promise

```text
Open yesterday's conversation.
Read the original messages.
Continue where you stopped.
```

The first Studio experience is persistent chat, not an internals dashboard.

## Implemented

- `heph studio` CLI command with `--port`, `--host`, and `--no-open`.
- `heph studio doctor` for optional dependencies, frontend build availability,
  database access, provider status, policy profile, port availability, and
  static assets.
- FastAPI backend under `src/hephaestus/studio/`.
- Next.js App Router frontend under `apps/studio/`.
- SQLite migration 16 for missing conversation metadata:
  - `display_title`;
  - `is_pinned`;
  - `last_opened_at`;
  - `workspace_path`.
- Reuse of existing `archived` and `repo_profile_id` conversation columns.
- Persistent exact-message timeline over existing `conversation_messages`.
- Conversation creation, reopening, continuing, renaming, pinning, archiving,
  and local SQL search.
- Deterministic initial titles from first user messages without model calls.
- Mode selector and optional repo selector.
- Active policy, provider state, memory counts, and lightweight linked artifact
  indicators.
- Local deterministic provider fallback when no API key is configured.
- Static frontend export served by the Python backend with deep-link fallback.
- Screenshots:
  - `docs/assets/studio/studio-chat.png`
  - `docs/assets/studio/studio-history.png`
  - `docs/assets/studio/studio-search.png`

## Continuity Principle

Studio does not generate automatic recaps. Opening a conversation reads the
stored timeline and returns it as-is. Summary generation can be a future
explicit user action, but it is not the main continuity mechanism.

## Security

- Defaults to `127.0.0.1:8741`.
- Avoids wildcard CORS.
- Frontend uses local typed API endpoints instead of direct SQLite access.
- Protected files are not exposed.
- Conversation data is sent externally only when the user sends a message and a
  configured real provider is selected.

## Phase Boundary

Deferred to Phase 5.5B:

- coding request workbench;
- patch diffs;
- validation run evidence;
- approvals and trust rules;
- checkpoints and rollback;
- outcomes;
- tool action history;
- release plan views.

Deferred to Phase 5.5C:

- decision trace UI;
- Pareto frontiers;
- QUBO/Ising views;
- learning internals;
- model economy analytics;
- packaging polish beyond static frontend serving.

## Validation Notes

Validated on 2026-06-16 with:

```bash
uv run ruff check .
uv run pytest
uv run mypy
uv run heph --help
uv run heph doctor
uv run heph studio doctor
cd apps/studio
pnpm install
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

Results:

- Python: `162 passed`, with one upstream FastAPI/Starlette TestClient
  deprecation warning.
- Frontend: `9 passed`.
- Studio smoke: `uv run heph studio --no-open` started on
  `http://127.0.0.1:8741` and returned healthy status.
- Manual inspection confirmed exact-message reopening, restart persistence,
  local search, deep-link reload, deterministic local provider status, CLI
  readback, no automatic summary insertion, no browser console errors, and
  narrow viewport chat usability.
