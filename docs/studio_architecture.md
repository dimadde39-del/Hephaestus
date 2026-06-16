# Studio Architecture

Phase 5.5A adds a local web app without creating a second conversation system.

```text
apps/studio Next.js static export
  -> src/hephaestus/studio FastAPI API
  -> existing Hephaestus repositories and orchestration
  -> .hephaestus/hephaestus.db
```

## Frontend

The frontend lives in `apps/studio/` and uses:

- Next.js App Router static export;
- strict TypeScript;
- Tailwind CSS v4;
- restrained Framer Motion;
- Lucide icons;
- React Markdown with GFM and highlighted code blocks;
- Vitest and Testing Library.

The app shell is organized around:

- conversation sidebar;
- message timeline;
- composer;
- collapsible context drawer;
- search panel;
- typed API client.

The visual direction follows the Hephaestus brand: charcoal and iron surfaces,
bronze and forge gold accents, ember warmth, restrained cyan, and small Talos
usage. It is a chat product, not an analytics dashboard.

## Backend

The backend lives in `src/hephaestus/studio/`:

- `app.py`: FastAPI app factory, CORS, static frontend serving, SPA deep-link
  fallback.
- `api.py`: typed API routes.
- `schemas.py`: request and response schemas.
- `services.py`: Studio orchestration and provider/policy/repo exposure.
- `repository.py`: conversation metadata, message reads, search, memory counts,
  and artifact counts over SQLite.
- `launcher.py`: `heph studio` runtime and `heph studio doctor`.
- `security.py`: loopback defaults, precise CORS origins, static asset path
  resolution.

The backend calls `ConversationService` to continue chats. It does not duplicate
message storage and the frontend never queries SQLite directly.

## API Surface

Phase 5.5A exposes:

```text
GET  /api/health
GET  /api/config
GET  /api/conversations
POST /api/conversations
GET  /api/conversations/{session_id}
GET  /api/conversations/{session_id}/messages
POST /api/conversations/{session_id}/messages
PATCH /api/conversations/{session_id}
POST /api/conversations/{session_id}/pin
POST /api/conversations/{session_id}/archive
GET  /api/search
GET  /api/modes
GET  /api/policy/active
GET  /api/providers/status
GET  /api/repos/recent
```

Posting a message:

1. validates the request;
2. updates selected mode/repo metadata when provided;
3. persists the exact user message through the existing conversation service;
4. invokes the configured provider or deterministic local fallback;
5. persists and returns the exact assistant response;
6. returns actionable errors without replacing prior messages.

Opening a conversation only reads stored session and message data.

## Database

Studio reuses:

- `conversation_sessions`;
- `conversation_messages`;
- `conversation_memory_updates`;
- regular memory tables;
- strategic memory tables;
- repo profile tables;
- policy tables.

SQLite migration 16 adds missing Studio metadata columns to
`conversation_sessions`:

- `display_title`;
- `is_pinned`;
- `last_opened_at`;
- `workspace_path`.

Studio reuses existing `archived` and `repo_profile_id` columns for archive and
repo-context behavior instead of adding duplicate fields.

Messages are not copied into a Studio-only table.

## Static Frontend Serving

`pnpm build` exports the frontend to `apps/studio/out/`. When that directory is
present, the Python backend serves it. App routes such as
`/conversations/{session_id}` fall back to `index.html` so browser reload and
deep links work.

If static assets are missing, `heph studio doctor` reports it. Developers can
still run the Next dev server against the Python API.

## Local-First Security

Defaults:

```text
host: 127.0.0.1
port: 8741
```

Security boundaries:

- no public bind unless the user passes a public host;
- no wildcard CORS;
- no protected file content exposure;
- no account system or cloud auth;
- no model call for opening or searching history;
- no data sent externally except submitted messages sent to the configured
  provider.

## Phase Boundary

Phase 5.5A intentionally stops at persistent chat. Phase 5.5B should add
workbench views for coding requests, patch diffs, validation runs, approvals,
checkpoints, rollback, outcomes, tool actions, and release plans. Phase 5.5C
can add advanced decision trace, Pareto, QUBO, learning, and packaging polish.
