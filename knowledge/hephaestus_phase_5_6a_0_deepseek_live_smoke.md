# Phase 5.6A.0 — DeepSeek V4 Flash first live smoke

## Audit before the phase

- DeepSeek already used the provider protocol and could make a single chat-completions request, but its endpoint and defaults lived directly in the provider.
- `deepseek-v4-flash` already existed as the request/profile default. The code was not tied to `deepseek-chat`; neither `deepseek-chat` nor `deepseek-reasoner` was a default.
- `ModelRequest.model` could override the model for an individual call, but DeepSeek had no environment/Studio model or base-URL configuration and custom IDs could fail profile lookup during accounting.
- The shared OpenAI-compatible provider supported configurable model/base URL and basic token usage, but not cached tokens, `reasoning_content`, thinking payloads, or sanitized provider errors.
- Thinking mode and reasoning effort were not implemented. `reasoning_content` was neither parsed nor intentionally handled.
- Conversation synthesis consumed real provider text and persisted only visible content.
- `heph doctor` and `heph models` exposed provider availability; `heph ask` and `heph discuss` routed through `local`/`auto`/`real` modes. There was no guarded provider-specific live-smoke command.
- The coding loop locally inspected the repo and could ask a provider for bounded JSON find/replace. This was orchestration-prepared context, not a native tool-call loop.
- Studio stored write-only provider secrets and displayed configs, but a saved default was not connected to conversation routing. DeepSeek “test” only checked local configuration and did not contact the provider.
- Usage stored estimates but had no thinking, reasoning-effort, cached-token, or provider-reported usage fields.

## Phase result

DeepSeek now subclasses the shared OpenAI-compatible transport. The effective configuration supports custom model IDs, normalized base URLs, thinking, `high`/`max` effort, output/context limits, and cost metadata. Studio defaults participate in Studio `auto` routing; explicit choices and deterministic mode retain priority.

`reasoning_content` is transient and excluded from serialization. A helper preserves it only across an immediate tool-call continuation. No native autonomous tool loop is claimed.

`heph models` remains backward-compatible as the group callback, with `models test` and `models smoke` subcommands. Live execution requires `--live`, uses explicit call/output/cost guards, and isolates databases, conversation tags, workspaces, and artifacts. Coding uses only a bundled disposable dependency-free fixture.

Provider and smoke tests use captured fake HTTP responses. They cover payloads, reasoning redaction, errors, usage, limits, data isolation, fixture reset, and Studio secret behavior without internet access.
