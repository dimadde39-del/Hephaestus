# Research Planning

Research mode prepares research. It does not pretend research has already been
done.

Use:

```bash
uv run heph discuss "Research plan: compare Hephaestus positioning against existing open-source agent frameworks." --mode research
```

The output includes:

- what needs to be verified
- likely sources
- search queries
- evidence quality expectations
- what would change the conclusion
- risks of shallow research

## Why This Matters

Agent frameworks, models, pricing, benchmarks, and open-source positioning
change quickly. A useful answer should separate:

- local context and assumptions
- claims that need current external evidence
- source quality expectations
- decision-changing evidence

This mode prepares future web or deep research without crossing the Phase 5C
boundary. Hephaestus does not browse, execute commands, or claim current factual
verification in this phase. Provider-backed synthesis must preserve that
boundary: it can improve wording and reasoning, but it cannot claim live
research happened.

Phase 5F adds real local validation evidence, which is different from external
research. `heph validate run . --yes` can prove local tests or lint passed, but
it does not verify current market facts, current library guidance, security
advisories, or competitor positioning. Research mode should still identify what
needs source-backed verification.

Research-planning quality is covered by deterministic conversation benchmarks:

```bash
uv run heph conversation benchmark run benchmarks/conversation/research_planning.json
```
