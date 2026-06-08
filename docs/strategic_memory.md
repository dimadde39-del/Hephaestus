# Strategic Memory

Strategic memory is the long-term context layer for serious discussions. It is
for direction, judgment, and decision quality, not raw chat logs.

## Types

Strategic memory supports:

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

Each item has a scope: `global`, `project`, `repo`, or `conversation`.

## Commands

```bash
uv run heph strategy memory add --type goal --content "Build Hephaestus toward a 20k-star open-source project."
uv run heph strategy memory list
uv run heph strategy memory search "20k"
uv run heph strategy memory show <memory_id>
uv run heph strategy memory archive <memory_id>
uv run heph strategy context
```

`heph strategy context` is the compact answer to: what does Hephaestus know
about my long-term direction?

## Saving Rules

Conversation can suggest strategic memories from durable goals, principles,
roadmap boundaries, assumptions, research questions, and high-impact
recommendations.

Suggestions are not saved by default. Save them with:

```bash
uv run heph discuss "..." --save-memory
uv run heph discuss "..." --save-strategy
```

In chat, use:

```text
/save-memory
```

Potentially sensitive personal details are never silently auto-saved. They may
be suggested only so the user can explicitly decide whether they belong in local
memory.

## Retrieval

Conversation recall uses the prompt, intent, tags, types, project, and optional
repo profile. Strategic memories are rendered as selected context and recorded
in high-impact decision traces.

Simple conflict detection flags obvious tensions, such as a saved roadmap memory
that says to launch before execution and a new candidate that says not to launch
before execution.
