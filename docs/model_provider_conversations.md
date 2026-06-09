# Model Provider Conversations

Phase 5C makes conversation synthesis provider-aware without making paid APIs
mandatory. Phase 5D adds active policy profiles so provider-backed answers do
not over-refuse benign user-owned work.

## Modes

Conversation has three practical provider modes:

- `local`: deterministic fake/local provider. This is the test and benchmark
  default.
- `auto`: use a configured real provider if one is available, otherwise fall
  back to local deterministic mode.
- `real`: prefer configured real providers, falling back to local only when no
  real provider is usable.

CLI examples:

```bash
uv run heph ask "What is Hephaestus trying to become?" --show-budget
uv run heph discuss "Stress-test this plan." --mode strategic --provider local
uv run heph conversation benchmark run --provider local
uv run heph conversation benchmark run --provider real
```

## DeepSeek

Set:

```bash
DEEPSEEK_API_KEY=...
```

Then `heph ask` and `heph discuss` in `auto` mode can route to DeepSeek.
`heph doctor` and `heph models` show whether DeepSeek is configured.

## OpenAI-Compatible / OpenRouter

Set:

```bash
HEPH_OPENAI_COMPAT_BASE_URL=https://openrouter.ai/api/v1
HEPH_OPENAI_COMPAT_API_KEY=...
HEPH_OPENAI_COMPAT_MODEL=openai/gpt-4.1
```

Optional metadata:

```bash
HEPH_OPENAI_COMPAT_CONTEXT_WINDOW=128000
HEPH_OPENAI_COMPAT_INPUT_COST_PER_MILLION=2.0
HEPH_OPENAI_COMPAT_OUTPUT_COST_PER_MILLION=8.0
```

The provider calls a chat-completions-compatible endpoint. If the base URL ends
with `/v1`, Hephaestus appends `/chat/completions`.

## Prompt Assembly

The conversation prompt includes:

- Hephaestus behavior standard.
- Freedom/policy UX boundary.
- Active policy profile name, decision, refusal style, and benign-work guidance.
- Selected deliberation mode.
- Discussion rubric context.
- Strategic memory first.
- Repo summary when `--repo` is used.
- Recent session context.
- Regular memory.
- User message.
- Deterministic assumptions, risks, options, recommendation seed, and next
  moves.

The prompt explicitly asks the provider to separate facts, assumptions,
uncertainty, and recommendations when useful.

For benign creative, development, research, or strategy requests classified as
allowed, the prompt says to help directly, avoid moralizing, and not refuse just
because the task is harsh, ambitious, edgy, or non-corporate. If a configured
provider still refuses a clearly benign allowed request, Hephaestus flags
over-refusal and falls back to local deterministic synthesis.

## Budgeting

Conversation budget reports show:

- selected provider/model;
- estimated input tokens;
- output token budget;
- context window;
- selected regular memory count;
- selected strategic memory count;
- whether context was trimmed;
- estimated cost.

Use:

```bash
uv run heph ask "..." --show-budget
```

## Limitations

Phase 5D is still text-only. It does not execute shell commands, edit files,
browse, run a daemon, or perform autonomous workflows. Research mode prepares a
research plan; it does not claim live research unless a later phase adds an
explicit research tool.
