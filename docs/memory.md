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

## CLI

```bash
uv run heph db init
uv run heph db path
uv run heph memory add --type failure --content "Validation failed because tests were missing"
uv run heph memory search tests
uv run heph memory list
```

Memory records persist across separate CLI invocations because they are written
to SQLite instead of a process-local store.

## Roadmap

- Hybrid lexical/vector retrieval.
- Memory decay and verification timestamps.
- Graph links between decisions, failures, tasks, and skills.
- Promotion from repeated successful memories into procedural skills.
