# Conversation

Phase 5A adds a real text interface, Phase 5B makes it more useful for
strategy, architecture, product, research, roadmap, and high-stakes decision
discussions, Phase 5C makes provider-backed conversation quality explicit, and
Phase 5D adds active policy profiles so benign user-owned work is helped
directly while genuinely harmful requests stay bounded. Phase 5E lets
conversation turns propose safe tool actions for the user to run manually.
Phase 5F adds validation-specific proposals without allowing chat to auto-run
validation. Phase 5G adds coding-plan proposals without allowing chat to edit
files automatically.

```bash
uv run heph ask "What is Hephaestus trying to become?"
uv run heph ask "What is Hephaestus trying to become?" --show-budget
uv run heph discuss "Stress-test launching before code execution exists." --mode strategic --show-context
uv run heph chat
uv run heph policy set developer
uv run heph discuss "Propose a safe validation plan for this repo." --repo . --propose-tools
uv run heph discuss "Propose a small safe README improvement." --repo . --propose-code
```

This is not voice, browser automation, or autonomous code editing. Chat does
not execute tools. It can suggest exact `heph validate ...`, `heph tools ...`,
and `heph code ...` commands with risk classification and approval notes.

## Commands

```bash
uv run heph ask "..." --mode strategic
uv run heph ask "..." --repo .
uv run heph ask "..." --save-memory
uv run heph ask "..." --show-context
uv run heph ask "..." --show-budget
uv run heph ask "..." --provider local
uv run heph ask "..." --no-memory
uv run heph ask "..." --repo . --propose-tools
uv run heph ask "..." --repo . --propose-code
uv run heph discuss "..." --mode critical
uv run heph discuss "..." --mode strategic --save-strategy
uv run heph discuss "Research plan: compare agent frameworks." --mode research
uv run heph discuss "Propose a validation plan." --repo . --propose-tools
uv run heph discuss "Improve the README launch section." --repo . --propose-code
uv run heph chat --repo .
uv run heph chat --repo . --propose-code
uv run heph chat --session <session_id>
uv run heph conversations
uv run heph conversation show <session_id>
uv run heph conversation benchmark list
uv run heph conversation benchmark run
```

`ask` is a one-shot turn. `discuss` is tuned for longer plans or ideas and
returns more structured analysis. `chat` persists an interactive session and
supports `/exit`, `/memory`, `/mode <mode>`, `/repo <path>`, `/summary`, and
`/save-memory`. It also supports `/propose-code <request>` for a planning-only
coding loop proposal. In Phase 5B, `/save-memory` saves both normal memory
candidates and strategic memory candidates from the last response.

## Pipeline

```text
Input -> Intent Classification -> Policy Evaluation -> Context Retrieval -> Prompt Budgeting -> Rubric-Aware Deliberation -> One Synthesis Call -> Memory Suggestions
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

## Tool Proposals

`--propose-tools` appends a deterministic table of proposed actions:

- action type;
- risk level;
- whether approval is needed;
- recommended order;
- exact `heph tools ...` commands.
- validation-specific commands such as `heph validate plan .`,
  `heph validate run . --dry-run`, and `heph validate run . --yes`.

The conversation service never runs those commands. The user stays in control,
can inspect a dry run before executing anything, and must explicitly approve
validation execution with `--yes`.

## Code Proposals

`--propose-code` appends a repo-aware coding plan:

- intended scope and risk,
- likely files,
- whether a deterministic patch proposal is possible,
- validation commands,
- exact next `heph code ...` command.

It does not propose from vague large requests as if they were safe. Oversized
requests become plan-only and ask the user to narrow scope. Normal chat never
applies patches; use `heph code propose`, `heph code apply --yes`, or
`heph code run --yes` explicitly.

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

For release questions, `--propose-tools` suggests the validation evidence path:

```bash
uv run heph validate plan .
uv run heph validate run . --dry-run
uv run heph validate run . --yes
```

## Prompt And Context Budget

Prompt assembly includes the behavior standard, freedom/policy boundary,
active policy profile and decision, selected mode, discussion rubric, strategic
memory, repo context, recent session messages, regular memory, deterministic
assumptions/options/risks, and the user message. Strategic memory is prioritized
first, then repo summary, recent session context, and regular memory.
Lower-priority context is trimmed when the budget is exceeded; the current user
message is never silently dropped.

Allowed benign creative, development, research, and strategy prompts are marked
as allowed in the provider prompt so the model should help directly instead of
over-refusing. Blocked prompts short-circuit locally with a concise boundary.
Approval-gated prompts can be discussed, but Hephaestus still does not execute
tools in this phase.

Use `--show-budget` to display estimated input tokens, output budget, selected
provider/model, context window, selected memory counts, and trimming notes.

## Providers

User-facing `ask` and `discuss` default to provider mode `auto`: use a
configured real provider when available, otherwise deterministic local mode.
Programmatic tests and conversation benchmarks default to `local`.

Supported real-provider paths:

- `DEEPSEEK_API_KEY`
- `HEPH_OPENAI_COMPAT_BASE_URL`
- `HEPH_OPENAI_COMPAT_API_KEY`
- `HEPH_OPENAI_COMPAT_MODEL`

OpenRouter-compatible usage works through the OpenAI-compatible path. See
[model provider conversations](model_provider_conversations.md).

## Benchmarks

Conversation benchmarks live in `benchmarks/conversation/` and run without live
APIs by default:

```bash
uv run heph conversation benchmark list
uv run heph conversation benchmark run benchmarks/conversation/idea_stress_test.json
uv run heph conversation benchmark run
uv run heph policy benchmark run
```

See [conversation benchmarks](conversation_benchmarks.md).

## Decision Traces

High-impact discussion types create conversation-linked decision traces:
architecture, product strategy, business strategy, idea stress tests, and
roadmap decisions. Research planning and risk analysis can also be traced.
Traces record assumptions, options, recommendation, confidence, memory used,
strategic memory used, suggested strategic memories, and the discussion-quality
rubric used.

Policy evaluations are recorded separately in the local SQLite policy tables and
also attached to conversation response metadata.
