# Conversation

Phase 5A adds a real text interface, and Phase 5B makes it more useful for
strategy, architecture, product, research, roadmap, and high-stakes decision
discussions:

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
uv run heph ask "..." --show-context
uv run heph ask "..." --no-memory
uv run heph discuss "..." --mode critical
uv run heph discuss "..." --mode strategic --save-strategy
uv run heph discuss "Research plan: compare agent frameworks." --mode research
uv run heph chat --repo .
uv run heph chat --session <session_id>
uv run heph conversations
uv run heph conversation show <session_id>
```

`ask` is a one-shot turn. `discuss` is tuned for longer plans or ideas and
returns more structured analysis. `chat` persists an interactive session and
supports `/exit`, `/memory`, `/mode <mode>`, `/repo <path>`, `/summary`, and
`/save-memory`. In Phase 5B, `/save-memory` saves both normal memory candidates
and strategic memory candidates from the last response.

## Pipeline

```text
Input -> Intent Classification -> Context Retrieval -> Rubric-Aware Deliberation -> Final Response -> Memory Suggestions
```

Internal passes are lightweight roles:

- `ContextScout`
- `MemoryRetriever`
- `AssumptionMapper`
- `EvidenceChecker`
- `SecondOrderThinker`
- `OptionGenerator`
- `Critic`
- `RecommendationSynthesizer`

They are not expensive recursive sub-agent swarms. The external product remains
one Hephaestus.

## Memory And Strategic Context

Conversation retrieves regular persistent memories by lexical relevance,
project, and intent tags. Phase 5B also retrieves strategic memory: goals,
ambitions, constraints, preferences, principles, strategic decisions, roadmap
decisions, rejected paths, assumptions, lessons, risk patterns, and open
questions.

By default, suggestions are not saved. Use `--save-memory`, `--save-strategy`,
or chat `/save-memory` to persist them. Potentially sensitive personal context
stays suggestion-only unless the user explicitly saves it.

Use:

```bash
uv run heph strategy context
uv run heph strategy memory list
uv run heph strategy memory search "launch"
```

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
roadmap decisions. Research planning and risk analysis can also be traced.
Traces record assumptions, options, recommendation, confidence, memory used,
strategic memory used, suggested strategic memories, and the discussion-quality
rubric used.
