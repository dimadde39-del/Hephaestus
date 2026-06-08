# Conversation

Phase 5A adds a real text interface:

```bash
uv run heph ask "What is Hephaestus trying to become?"
uv run heph discuss "Stress-test launching before code execution exists." --mode strategic
uv run heph chat
```

This is not voice, shell execution, browser automation, or autonomous code
editing. It is a memory-grounded thinking interface for code, architecture,
research, product, strategy, roadmap, and difficult decisions.

## Commands

```bash
uv run heph ask "..." --mode strategic
uv run heph ask "..." --repo .
uv run heph ask "..." --save-memory
uv run heph ask "..." --no-memory
uv run heph discuss "..." --mode critical
uv run heph chat --repo .
uv run heph chat --session <session_id>
uv run heph conversations
uv run heph conversation show <session_id>
```

`ask` is a one-shot turn. `discuss` is tuned for longer plans or ideas and
returns more structured analysis. `chat` persists an interactive session and
supports `/exit`, `/memory`, `/mode <mode>`, `/repo <path>`, `/summary`, and
`/save-memory`.

## Pipeline

```text
Input -> Intent Classification -> Context Retrieval -> Deliberation Passes -> Final Response -> Memory Update
```

Internal passes are lightweight roles:

- `ContextScout`
- `MemoryRetriever`
- `AssumptionMapper`
- `Critic`
- `Strategist`
- `Synthesizer`

They are not expensive recursive sub-agent swarms. The external product remains
one Hephaestus.

## Memory

Conversation retrieves persistent memories by lexical relevance, project, and
intent tags. It suggests durable memory updates for important goals, preferences,
roadmap boundaries, and high-impact recommendations.

By default, suggestions are not saved. Use `--save-memory` or chat
`/save-memory` to persist them.

## Repo Context

With `--repo`, conversation loads the latest repo profile for the path or runs a
read-only inspection if none exists. It can discuss stack, validation commands,
risk signals, and generated repo-aware tasks. It still does not execute
commands.

## Providers

If `DEEPSEEK_API_KEY` is set, Hephaestus can use the optional DeepSeek provider
for synthesis. If no provider is configured, it falls back to deterministic
local mode and says so. Tests and normal local development do not require paid
APIs.

## Decision Traces

High-impact discussion types create conversation-linked decision traces:
architecture, product strategy, business strategy, idea stress tests, and
roadmap decisions. Traces record assumptions, options, recommendation,
confidence, and next move.
