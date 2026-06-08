# Hephaestus Phase 5B: Strategic Memory + Research/Discussion Quality

Phase 5B makes conversation useful beyond code by adding strategic memory,
rubric-backed discussion quality, and honest research planning.

## Added

- `src/hephaestus/strategic_memory/`
  - Pydantic schemas for strategic memory items, evidence, conflicts,
    extraction results, recalls, scopes, stability, and sources.
  - SQLite repository with save, list, search, get, archive, recall event
    persistence, and simple conflict detection.
  - Conservative extraction from conversations.
  - Rich renderers for lists, details, suggestions, conflicts, and strategic
    context.
- `src/hephaestus/discussion_quality/`
  - Rubrics for idea stress tests, business strategy, product strategy,
    technical architecture, roadmap decisions, research planning, and risk
    analysis.
  - Deterministic rubric evaluation.
  - Research plan schema and generator.
- SQLite migration 11:
  - `strategic_memories`
  - `strategic_memory_conflicts`
  - `strategic_memory_recalls`
- CLI:
  - `heph strategy memory add`
  - `heph strategy memory list`
  - `heph strategy memory search`
  - `heph strategy memory show`
  - `heph strategy memory archive`
  - `heph strategy context`
- Conversation integration:
  - `ask`, `discuss`, and `chat` retrieve strategic memory.
  - `--show-context` shows selected context.
  - `--save-strategy` saves strategic suggestions.
  - `--save-memory` and chat `/save-memory` save both regular and strategic
    memory suggestions.
  - High-impact traces record memory used, strategic memory used, suggested
    strategic memories, rubric name, and rubric score.

## Boundaries

- No dashboard.
- No voice.
- No Telegram.
- No browser automation.
- No autonomous code editing.
- No shell execution.
- Research mode plans verification but does not pretend to have done live
  research.

## Product Meaning

Hephaestus now has a durable way to remember long-term direction and a concrete
way to evaluate discussion quality. A user can bring a plan and ask for honest
pressure testing; Hephaestus can classify the discussion, recall strategic
context, identify assumptions and missing information, generate options,
stress-test the recommendation, and suggest what should be remembered.

## Next

Phase 5C should focus on real model provider conversation quality: provider
routing, DeepSeek/OpenAI-compatible support, response quality evaluation, and
conversation benchmark fixtures without requiring paid APIs by default.
