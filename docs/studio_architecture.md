# Studio Architecture

Phase 5.5A added a local chat app without creating a second conversation
system. Phase 5.5B adds Workbench projections over the existing runtime records
without creating a second agent runtime.

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
- Workbench feature folders for coding, diffs, validation, checkpoints, tool
  actions, release evidence, outcomes, and trust settings.

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
- `workbench.py`: typed Workbench projections over coding-loop, validation,
  tool-runtime, checkpoint, release, outcome, and policy records.
- `repository.py`: conversation metadata, message reads, search, memory counts,
  and artifact counts over SQLite.
- `launcher.py`: `heph studio` runtime and `heph studio doctor`.
- `security.py`: loopback defaults, precise CORS origins, static asset path
  resolution.

The backend calls `ConversationService` to continue chats and existing Python
orchestrators to plan/propose/apply coding work, run validation, and restore
checkpoints. It does not duplicate message storage or runtime logic, and the
frontend never queries SQLite directly.

## API Surface

Studio exposes the chat API plus Workbench API:

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
GET  /api/workbench/overview
GET  /api/coding
GET  /api/coding/{request_id}
POST /api/coding/plan
POST /api/coding/propose
POST /api/coding/{change_id}/apply
GET  /api/validation
GET  /api/validation/{result_id}
POST /api/validation/plan
POST /api/validation/run
GET  /api/checkpoints
GET  /api/checkpoints/{checkpoint_id}
POST /api/checkpoints/{checkpoint_id}/restore
GET  /api/tools/actions
GET  /api/tools/actions/{action_id}
GET  /api/releases
GET  /api/releases/{release_plan_id}
GET  /api/outcomes
GET  /api/outcomes/{outcome_id}
GET  /api/trust
PATCH /api/trust
```

Posting a message:

1. validates the request;
2. updates selected mode/repo metadata when provided;
3. persists the exact user message through the existing conversation service;
4. invokes the configured provider or deterministic local fallback;
5. persists and returns the exact assistant response;
6. returns actionable errors without replacing prior messages.

Opening a conversation only reads stored session and message data.

Workbench reads typed projections from existing repositories. It translates
runtime artifacts into user-readable records such as "Applied patch to 2 files"
instead of exposing raw SQLite rows or internal JSON. Advanced details are
available, but collapsed by default.

## Database

Studio reuses:

- `conversation_sessions`;
- `conversation_messages`;
- `conversation_memory_updates`;
- regular memory tables;
- strategic memory tables;
- repo profile tables;
- policy tables.
- coding-loop tables.
- validation tables.
- tool-runtime action/checkpoint tables.
- release planning tables.
- outcome and learning tables.

SQLite migration 16 adds missing Studio metadata columns to
`conversation_sessions`:

- `display_title`;
- `is_pinned`;
- `last_opened_at`;
- `workspace_path`.

Studio reuses existing `archived` and `repo_profile_id` columns for archive and
repo-context behavior instead of adding duplicate fields.

Messages are not copied into a Studio-only table.

SQLite migration 17 adds `studio_trust_settings` for local Workbench autonomy
preferences. These preferences map to existing policy profiles and implemented
runtime actions; they cannot override hard destructive blocks.

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

Phase 5.5B intentionally stops at practical Workbench visibility and selected
safe actions. It does not add deploy, dependency installation, Git push,
external messaging, arbitrary shell input, or fake streaming cancellation.
Phase 5.5C can add advanced decision trace, Pareto, QUBO, memory management,
provider/model settings, model economy visibility, onboarding, and packaging
polish.
