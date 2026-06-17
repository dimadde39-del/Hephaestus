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

## Strategic Memory

Phase 5B adds a separate strategic memory layer for long-term direction and
non-code decision quality. Strategic memory types include:

- `goal`
- `ambition`
- `constraint`
- `fear`
- `risk_pattern`
- `preference`
- `principle`
- `strategic_decision`
- `roadmap_decision`
- `positioning_decision`
- `launch_decision`
- `business_assumption`
- `technical_assumption`
- `rejected_path`
- `lesson_learned`
- `open_question`

Strategic memories have a scope: `global`, `project`, `repo`, or
`conversation`. They also record confidence, importance, stability, source,
tags, and evidence. Use:

```bash
uv run heph strategy memory add --type goal --content "Build Hephaestus toward a 20k-star open-source project."
uv run heph strategy memory list
uv run heph strategy memory search "20k"
uv run heph strategy memory show <memory_id>
uv run heph strategy memory archive <memory_id>
uv run heph strategy context
```

`heph strategy context` answers the question: what does Hephaestus currently
know about the long-term direction?

Conversation-derived strategic memories are suggestions unless explicitly
saved with `--save-memory`, `--save-strategy`, or chat `/save-memory`.
Project goals, roadmap decisions, technical preferences, and open-source
strategy can be suggested normally. Potentially sensitive personal details are
not auto-saved and should only be persisted by explicit user choice.

## Studio Memory

Studio adds a first-class Memory area for reviewing and correcting what
Hephaestus believes:

- search and filter regular and strategic memories;
- inspect content, summary, scope, type, confidence, source, evidence, links,
  conflicts, and history when available;
- create and edit memories;
- archive, restore, and delete with explicit confirmation;
- review suggestions from conversations and outcomes with Save, Edit, or
  Ignore.

Studio uses human labels such as Goal, Constraint, Preference, Principle,
Strategic decision, Rejected path, Lesson learned, Open question, Project fact,
and Working style. It does not show embeddings or raw database payloads.

See [Studio Memory](studio_memory.md).

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
