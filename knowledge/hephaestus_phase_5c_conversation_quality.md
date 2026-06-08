# Hephaestus Phase 5C: Real Model Provider Conversation Quality

Phase 5C makes conversation quality provider-aware, prompt-budgeted, and
measurable without requiring paid APIs by default.

## Implemented

- Deterministic local provider remains the default for tests and conversation
  benchmarks.
- CLI `ask` and `discuss` use provider mode `auto`, so configured real providers
  can synthesize final answers.
- DeepSeek is detected through `DEEPSEEK_API_KEY`.
- OpenAI-compatible providers are detected through:
  - `HEPH_OPENAI_COMPAT_BASE_URL`
  - `HEPH_OPENAI_COMPAT_API_KEY`
  - `HEPH_OPENAI_COMPAT_MODEL`
- OpenRouter-compatible usage works through the OpenAI-compatible path.
- Model profiles now include `supports_streaming` and `intended_roles`.
- Conversation prompt assembly lives in
  `src/hephaestus/conversation/prompt_builder.py`.
- Context budget order is strategic memory, repo context, recent session
  messages, then regular memory.
- Budget reports expose provider/model, estimated tokens, output budget,
  context window, selected context counts, trimming notes, and estimated cost.
- Model-backed conversation uses one synthesis call by default.
- Conversation benchmarks live under `benchmarks/conversation/`.
- Deterministic evaluation package lives under
  `src/hephaestus/conversation_eval/`.
- CLI:
  - `heph conversation benchmark list`
  - `heph conversation benchmark run`
  - `heph conversation benchmark run benchmarks/conversation/idea_stress_test.json`
- Memory suggestions now summarize long content and include stability labels.

## Boundaries

Phase 5C does not add dashboards, voice, Telegram, browser automation, shell
execution, autonomous code editing, daemon behavior, or live research.

Research mode remains a planning mode. It identifies claims to verify, likely
sources, search queries, evidence quality expectations, and what would change
the conclusion.

## Next Recommended Phase

Phase 5D should be Safe Tool Execution Runtime: approval-gated command
execution, dry-run planning, output observation, rollback/checkpoint design, and
real outcome learning from validation commands.
