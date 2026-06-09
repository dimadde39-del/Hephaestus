# Policy and Freedom UX

Hephaestus is local-first and user-owned. Phase 5D turns that from a prompt
principle into a product layer: policy profiles, deterministic request
evaluation, active-profile persistence, concise boundaries, over-refusal
detection, and policy benchmarks.

The short version:

- Help with benign creative, development, research, product, and strategy tasks.
- Do not moralize, over-apologize, or refuse because work is harsh, ambitious,
  edgy, direct, or non-corporate.
- Require explicit approval for destructive local actions and external side
  effects.
- Block genuinely harmful requests: credential theft, malware, abuse evasion,
  targeted harassment, exploitation, and real-world violence.
- Keep boundaries transparent and configurable.

This is what "same practical freedom as Hermes" means in Hephaestus: normal
user-owned work should feel open and direct. It does not mean Hephaestus helps
with abuse or pretends tool execution is ready before it is.

## Commands

```bash
uv run heph policy profiles
uv run heph policy active
uv run heph policy set developer
uv run heph policy show developer
uv run heph policy evaluate "make a README banner for my AI project"
uv run heph policy evaluate "run rm -rf /" --profile developer
uv run heph policy benchmark list
uv run heph policy benchmark run
```

`balanced` is the unset default. The docs recommend `developer` for open-source
power users:

```bash
uv run heph policy set developer
```

## Built-In Profiles

- `developer`: recommended for Hephaestus. Allows benign dev, creative,
  research, direct copy, harsh critique, defensive security explanation, and
  strategy work. Approval-gates side effects. Blocks actual abuse.
- `research`: more permissive for analysis, theory, defensive security,
  dual-use explanation, and architecture. It separates analysis from execution.
- `local_power_user`: assumes the user owns the local environment and avoids
  unnecessary clarifying questions for normal local work.
- `strict`: conservative for demos, classrooms, and enterprise-like contexts.
- `balanced`: default when nothing is configured.

## Conversation Integration

`heph ask`, `heph discuss`, and `heph chat` load the active policy profile and
evaluate the user prompt before model synthesis. The prompt sent to a provider
includes the active profile name, decision, refusal style, benign-work
philosophy, and boundary rules.

Allowed prompts are explicitly marked as allowed so model-backed mode is less
likely to over-refuse. If a provider refuses a clearly benign allowed request,
Hephaestus flags over-refusal and falls back to local deterministic synthesis.

Blocked prompts short-circuit locally with a concise refusal. Approval-gated
prompts can still be discussed, but Hephaestus will not execute anything in
Phase 5D.

## Why Before Tool Execution

Safe Tool Execution Runtime comes next because tools need policy boundaries
before they get hands. Phase 5D defines the user-owned freedom layer and the
approval vocabulary. Phase 5E can then add controlled filesystem tools, shell
wrappers, checkpoints, rollback, observations, and outcome learning without
inventing policy in the middle of execution.
