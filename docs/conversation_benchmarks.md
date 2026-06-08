# Conversation Benchmarks

Phase 5C adds deterministic conversation-quality benchmarks under:

```text
benchmarks/conversation/
```

Fixtures cover:

- idea stress test;
- roadmap decision;
- research planning;
- repo question;
- business strategy.

Run:

```bash
uv run heph conversation benchmark list
uv run heph conversation benchmark run benchmarks/conversation/idea_stress_test.json
uv run heph conversation benchmark run
```

Benchmarks use the local deterministic provider by default. Real providers are
opt-in:

```bash
uv run heph conversation benchmark run --provider real
uv run heph conversation benchmark run --live
```

## Fixture Shape

Each fixture includes:

- prompt;
- deliberation mode;
- expected rubric;
- quality profile;
- regular memory context;
- strategic memory context;
- repo context requirement when needed;
- anti-patterns to avoid.

Anti-patterns include blind agreement, fake certainty, unsupported claims,
generic advice, moralizing, and contrarianism for its own sake.

## Evaluator

The evaluator checks guardrail quality, not true intelligence. It looks for:

- position or recommendation when appropriate;
- assumptions;
- risks;
- missing information;
- next move;
- research planning boundary;
- no blind agreement in stress-test mode;
- no fake certainty;
- strategic memory usage when provided;
- repo context usage when required.

Results show benchmark id/title, mode, score, passed checks, failed checks,
warnings, and detected anti-patterns.

## Quality Profiles

Named targets are:

- `strategic`
- `research`
- `architecture`
- `stress_test`
- `repo_question`

These profiles map to expected deterministic checks and align with
deliberation modes/rubrics.
