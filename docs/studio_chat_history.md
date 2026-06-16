# Studio Chat History

Studio continuity is exact-message continuity.

```text
persist exact messages
-> reopen the same conversation
-> read the original timeline
-> continue naturally
```

That is the Phase 5.5A product contract.

## What Is Stored

Hephaestus stores conversations in SQLite:

- `conversation_sessions`: session metadata;
- `conversation_messages`: chronological user and assistant messages;
- `conversation_memory_updates`: suggested memory changes.

Studio adds session metadata such as display title, pin/archive state, last
opened time, workspace path, and repo profile ID. It does not duplicate message
bodies.

## What Happens On Open

When the user opens `/conversations/{session_id}`, Studio:

1. loads session metadata;
2. loads exact chronological messages;
3. marks the session as last opened;
4. restores local UI state such as scroll position where practical.

It does not call a model. It does not generate a recap. It does not replace the
timeline with a compressed memory.

## What Happens On Send

When the user sends a new message, Studio:

1. persists the exact user text;
2. calls the existing Hephaestus conversation service with the selected mode,
   active policy profile, optional repo context, and provider choice;
3. persists the exact assistant response;
4. refreshes the visible timeline.

If a provider fails, the error is shown as a retryable send state. Prior
messages remain intact.

## Titles

Empty conversations use a neutral empty title. The first user message creates a
deterministic concise title without a model call. Manual renames are preserved
and are not overwritten by later messages.

## Search

Studio search is local and deterministic:

- title matches;
- user message matches;
- assistant message matches.

Search results show the matching conversation and snippet. Archived
conversations require an explicit filter. Search does not consume provider
tokens.

## What Not To Add By Default

Do not add these as automatic behavior:

- daily summaries;
- "where you left off" cards;
- mandatory session recaps;
- hidden replacement of old messages with compressed context;
- model calls just because a user opened a conversation;
- summaries that appear before the original messages.

An explicit future command like "summarize this conversation" can be useful, but
it should be user-triggered and should never replace the original stored
messages.

## CLI Compatibility

Studio and CLI share the same storage. Existing CLI sessions appear in Studio,
and Studio-created sessions remain available through CLI conversation commands.
This keeps continuity independent of the current UI surface.
