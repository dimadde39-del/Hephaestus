# Hephaestus Phase 5A: Conversation

Phase 5A adds the conversational agent interface:

```bash
heph ask "..."
heph discuss "..."
heph chat
```

The feature gives Hephaestus a text-first way to handle messy human context,
strategy questions, architecture discussions, roadmap concerns, and repo-aware
release risk analysis.

Implemented package:

```text
src/hephaestus/conversation/
  schemas.py
  classifier.py
  context.py
  deliberation.py
  prompts.py
  session.py
  repository.py
  renderer.py
  analysis.py
```

Pipeline:

```text
Input -> Intent Classification -> Context Retrieval -> Deliberation Passes -> Final Response -> Memory Update
```

Important boundaries:

- No voice.
- No autonomous code editing.
- No shell execution.
- No browser automation.
- No fake claim of production autonomy.

Memory behavior is conservative. Conversation suggests durable memory updates,
but only saves them with `--save-memory` or chat `/save-memory`.

Repo context is read-only. `--repo` loads or creates a repo profile and grounds
the answer in stack, validation, generated tasks, and risk signals.

High-impact conversations create `phase=conversation` decision traces so future
outcome learning can evaluate strategic and architecture advice.

Recommended next phase:

```text
Phase 5B: Strategic Memory + Research/Discussion Quality Framework
```
