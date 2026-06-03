# Research Notes

Research was limited to high-level concepts and public documentation. No code was
copied.

## Spec Kit

Source: https://github.com/github/spec-kit

Takeaways:

- Spec-driven development benefits from explicit governing principles before
  implementation.
- A useful workflow separates constitution, specification, planning, task
  generation, implementation, and analysis.
- Hephaestus reuses the discipline, not the code or file structure.

Reuse decision:

- Reuse conceptually: constitution, goal spec, task graph, validation gates.
- Do not copy implementation code.

## agentmemory

Source: https://github.com/rohitg00/agentmemory

Takeaways:

- Memory for agents should be structured, searchable, and lifecycle-aware.
- Confidence, importance, project scope, and retrieval quality matter more than
  dumping full transcripts into every prompt.
- Hephaestus should distinguish project, failure, decision, semantic, and
  episodic memory from the beginning.

Reuse decision:

- Reuse conceptually: typed memory records and retrieval discipline.
- Do not copy implementation code.

## BigSet

Source: https://github.com/tinyfish-io/bigset

Takeaways:

- Natural-language-to-live-dataset is useful inspiration for future world memory:
  a user describes what they need, agents gather sources, normalize data, verify
  it, and refresh it over time.
- The repository is AGPL-3.0, so code reuse would be restrictive for this MIT
  project.

Reuse decision:

- Document as future inspiration for a live-data/world-memory layer.
- Do not integrate or copy code in Phase 1.

## Hermes Agent / OpenClaw Concepts

Sources:

- https://github.com/NousResearch/hermes-agent
- https://hermes-agent.nousresearch.com/docs/
- https://openclaw.ai/

Takeaways:

- Always-on agents combine persistent memory, tool access, schedules, messaging
  gateways, and reusable skills.
- Skills are best treated as procedural memory: repeatable workflows with
  guardrails, not random prompt snippets.
- High autonomy raises safety requirements. Tool scope, approval gates, and audit
  trails need to be part of the architecture, not late patches.

Reuse decision:

- Learn from the always-on + memory + skills loop.
- Do not clone or rebrand their code.
- Differentiate Hephaestus around optimization-first planning and
  quality-preserving token control.

## DeepSeek Provider Notes

Source: https://api-docs.deepseek.com/quick_start/pricing

DeepSeek is optional. Current example rates are isolated in the provider and docs
because provider pricing changes. Tests and demos must run without live API
calls.

