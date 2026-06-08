# Memory

Hephaestus stores typed memory records in local SQLite while preserving the Phase
1 lexical retrieval behavior. The default database path is:

```text
.hephaestus/hephaestus.db
```

The path is relative to the current working directory. `heph db init` initializes
the database explicitly; memory commands also initialize it automatically.

## Memory Types

- `episodic`: events and experiences from specific runs.
- `semantic`: durable facts and concepts.
- `project`: repo-specific architecture, conventions, and decisions.
- `failure`: known bugs, failed attempts, and validation lessons.
- `decision`: choices made with rationale.
- `procedural`: reserved for future skills and repeatable workflows.

## Retrieval

Retrieval currently uses lexical scoring over content, summary, and tags, boosted
by confidence and importance. No vector database is required.

Conversation turns retrieve memories by text relevance, project namespace, and
intent-related tags. Product strategy discussions bias toward strategy and
roadmap memories, while debugging discussions bias toward failure memories.

Conversation memory updates are conservative. `heph ask` and `heph discuss`
show suggested updates by default, but durable memories are saved only when
`--save-memory` is passed or when `/save-memory` is used in chat.

## CLI

```bash
uv run heph db init
uv run heph db path
uv run heph memory add --type failure --content "Validation failed because tests were missing"
uv run heph memory search tests
uv run heph memory list
uv run heph ask "Remember that voice features are deferred until the core is mature." --save-memory
uv run heph learn failures
uv run heph learn promote-failure <failure_draft_id>
```

Memory records persist across separate CLI invocations because they are written
to SQLite instead of a process-local store.

## Failure Memory Drafts

Phase 3B does not automatically promote every failure into durable memory.
Instead, outcome evaluation can create `FailureMemoryDraft` records that contain
the run, decision trace, outcome, summary, content, tags, confidence, severity,
and suggested importance.

Drafts are listed with:

```bash
uv run heph learn failures
```

Promotion is explicit:

```bash
uv run heph learn promote-failure <failure_draft_id>
```

Promotion creates a normal persistent `MemoryItem` with `type=failure` and
links the decision trace to the promoted memory ID. This keeps the learning
path auditable and avoids automatic self-modification.

## Roadmap

- Hybrid lexical/vector retrieval.
- Memory decay and verification timestamps.
- Graph links between decisions, failures, tasks, and skills.
- Promotion from repeated successful memories into procedural skills.
- Repeated outcome signals that adjust retrieval strategy after review.
