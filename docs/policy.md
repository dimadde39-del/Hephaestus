# Policy and Freedom UX

Hephaestus is local-first and user-owned. Policy is a product layer, not a
public headline: it helps the agent stay useful for normal work while keeping
local side effects explicit.

The short version:

- Help with benign creative, development, research, product, and strategy tasks.
- Do not moralize, over-apologize, or refuse because work is harsh, ambitious,
  edgy, direct, or non-corporate.
- Require explicit approval for destructive local actions and external side
  effects.
- Allow harmless repo inspection, planning, validation dry-runs, and patch
  proposal generation without approval spam.
- Block genuinely harmful requests: credential theft, malware, abuse evasion,
  targeted harassment, exploitation, and real-world violence.
- Keep boundaries transparent and configurable.

This supports the public product promise: Hephaestus should remember context,
help people think and code, validate work, and improve from outcomes without
pretending every request needs a lecture or every side effect is safe.

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
prompts can still be discussed. When execution happens through `heph tools`, the
runtime records the active profile, risk level, approval decision, result, and
observation.

## Studio Integration

`heph studio` exposes the same active policy profile in the local web UI. The
context drawer shows the profile name and type so the user can see which
boundary is active while chatting, but Studio does not turn policy evaluations
into the main timeline.

Studio stays local-first:

- it binds to `127.0.0.1` by default;
- it avoids wildcard CORS;
- it serves conversations through typed local APIs instead of direct frontend
  SQLite access;
- it does not expose protected file contents;
- it sends conversation text only to the configured provider when the user
  submits a message;
- it works in deterministic local mode without API keys.

Changing the active policy profile through CLI commands affects Studio because
both surfaces use the same SQLite policy repository.

## Coding Loop Integration

`heph code plan` and `heph code propose` are local analysis/proposal actions and
do not require approval. `heph code apply` and non-dry-run `heph code run`
modify files and require explicit `--yes`.

Low-risk docs, tests, and config/help text can batch the safe internal steps:

```text
planned low-risk local change -> checkpoint -> apply -> validate -> record outcome
```

Medium-risk changes require clearer explicit approval. High-risk, destructive,
external-side-effect, protected-file, and oversized changes are blocked or
converted into plan-only output. The boundary should be short and concrete, not
moralizing.

## Why This Matters

Self-improvement in Hephaestus means memory, outcomes, validation evidence,
skills, and capabilities improve with approval and evidence. It does not mean
uncontrolled self-modification or invisible policy drift.

Policy profiles make that boundary inspectable:

- `developer`: benign local development stays direct; side effects need approval.
- `research`: read-only analysis is easy; execution is approval-gated more often.
- `local_power_user`: fewer clarifying pauses, same destructive/external gates.
- `strict`: high-risk and external-side-effect actions are more likely blocked.

This keeps the UX practically free for normal work while making local side
effects explicit and auditable.
