# Live provider smoke

The DeepSeek smoke proves only a minimal configured request, persistent response, repository context, bounded proposal, validation evidence, and usage/cost record. It does not prove Claude Code parity, autonomous tool use, or general coding quality.

No command makes a network request unless `--live` is present. Tests and CI use fake transports only.

## Dry-run and connection

```bash
uv run heph models test deepseek
uv run heph models smoke deepseek --case conversation
uv run heph models smoke deepseek --case repo-read --repo .
uv run heph models smoke deepseek --case coding
```

The dry-run prints model, base URL, key source, maximum calls, maximum output tokens, and a conservative cost estimate.

The cheapest first live check is:

```bash
uv run heph models test deepseek --live --max-output-tokens 8 --estimated-cost-cap 0.005
```

It sends one tiny prompt, disables thinking for that probe, uses no tools or repository context, and creates no conversation or memory.

## Conversation and repository cases

```bash
uv run heph models smoke deepseek --case conversation --live \
  --max-calls 1 --max-output-tokens 1024 --estimated-cost-cap 0.01

uv run heph models smoke deepseek --case repo-read --repo . --live \
  --max-calls 1 --max-output-tokens 1536 --estimated-cost-cap 0.02
```

Both use an isolated temporary SQLite database and a smoke-prefixed conversation. Repo-read hashes the selected repository before and after, passes a bounded relative-path manifest, rejects nonexistent cited paths, and never modifies files.

## Disposable coding case

Live coding defaults to proposal-only:

```bash
uv run heph models smoke deepseek --case coding --live \
  --max-calls 1 --max-output-tokens 2048 --estimated-cost-cap 0.02
```

To apply and validate the proposal, add `--apply`. Application is permitted only in a temporary copy of the bundled `slugify` fixture:

```bash
uv run heph models smoke deepseek --case coding --live --apply \
  --max-calls 1 --max-output-tokens 2048 --estimated-cost-cap 0.02
```

The fixture has no external dependencies. The smoke records a plan, bounded diff, validation command/result, and outcome. The source fixture is hashed to prove it stayed unchanged. The temporary workspace and smoke database are deleted unless `--keep-workspace` is supplied.

## Budget and artifacts

Defaults are three calls, 4096 output tokens per call, `high` effort, and a `$0.05` estimated cap. The cap is an estimate, not a banking guarantee. Before each request, the runner checks its call count and conservative projected cost; it stops before a request that would exceed the configured estimate.

Each live result prints provider, model, calls, input/output/cached tokens when reported, estimated cost, elapsed time, result, and workspace status. Redacted JSON is available with `--json`. Smoke artifacts live under `.hephaestus/smoke-artifacts`; they do not include API keys or raw reasoning. Smoke databases and outcomes are not imported into normal memory, policy learning, or skill generation.
