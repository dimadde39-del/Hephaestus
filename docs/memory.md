# Memory

Phase 1 uses an in-memory repository with typed records. It is deliberately
simple so the behavior is easy to test and swap later.

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

## Roadmap

- SQLite persistence for local durability.
- Hybrid lexical/vector retrieval.
- Memory decay and verification timestamps.
- Graph links between decisions, failures, tasks, and skills.
- Promotion from repeated successful memories into procedural skills.

