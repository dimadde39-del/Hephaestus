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
uv run heph studio
uv run heph ask "What is Hephaestus trying to become?" --show-budget
uv run heph discuss "Stress-test this plan." --mode strategic --provider local
uv run heph conversation benchmark run --provider local
uv run heph conversation benchmark run --provider real
```

## Studio Provider Status

Studio uses the same provider routing as CLI conversation commands. The main UI
shows a restrained provider indicator and Settings -> Models provides the full
local configuration surface:

- `Local deterministic mode` when no API key is configured or local fallback is
  selected.
- `DeepSeek` when `DEEPSEEK_API_KEY` is configured and selected by auto routing.
- `OpenAI-compatible: <model>` when the OpenAI-compatible settings are present.
- `OpenRouter` through the OpenAI-compatible base URL/model path.

Opening an existing conversation never calls a provider. A provider is only used
when the user submits a new message. If no real provider is configured, Studio
still works with deterministic local responses and explains that limitation in
provider status instead of repeating warnings under every message.

Settings -> Models can:

- add or update a provider;
- test connectivity;
- choose the default conversation provider/model;
- remove a configuration;
- return to local deterministic mode;
- store optional context-window and cost metadata;
- reserve future role fields for coding and review providers.

Normal API responses never return stored API keys. Studio stores provider
secrets in the local SQLite database and relies on OS file permissions in this
phase. OS keychain integration remains future work.

## DeepSeek

Set:

```bash
DEEPSEEK_API_KEY=...
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
HEPH_DEEPSEEK_THINKING=enabled
HEPH_DEEPSEEK_REASONING_EFFORT=high
HEPH_DEEPSEEK_MAX_OUTPUT_TOKENS=4096
```

Then `heph ask` and `heph discuss` in `auto` mode can route to DeepSeek.
`heph doctor` and `heph models` show whether DeepSeek is configured.
Custom model IDs remain supported. DeepSeek uses the same OpenAI-compatible
transport as the generic provider path.

Thinking omits sampling parameters and parses `reasoning_content` only into a
transient, serialization-excluded field. Raw reasoning is not shown, persisted,
exported, added to memory, or logged. It is carried only through an immediate
tool-call continuation when one exists. The current repo/coding path remains
orchestration-prepared; it is not a native autonomous tool-call loop.

Use `heph models test deepseek` or `heph models smoke deepseek ...` for a
network-free preflight. A real request always requires `--live`; see
[Live provider smoke](live_provider_smoke.md).

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

## Studio Usage Economy

Settings -> Models includes a restrained usage view:

- model calls this week;
- deterministic operations;
- estimated input/output tokens;
- provider-reported input/output and cached input tokens when available;
- thinking enabled/disabled and reasoning effort;
- estimated cost when metadata is configured;
- provider/model used;
- task type and success/failure where linked.

The UI labels heuristic values as estimates. It uses practical messages such
as:

```text
Solved without a model call
One model call used
Context trimmed to fit budget
Estimated cost: ...
```

When DeepSeek reports completion tokens that combine visible completion and
reasoning work, Hephaestus stores that provider-reported value as-is. It does
not count the `reasoning_content` text as separately visible output.

Adaptive multi-model routing is not implemented yet; the data model prepares
for a later Adaptive Work Router / Model Economy phase.

## Limitations

Studio remains text-first and Workbench-bounded. It does not browse, run a
daemon, perform autonomous workflows, or adaptively route between multiple
models. Research mode prepares a research plan; it does not claim live research
unless a later phase adds an explicit research tool.
