# Protocol 5.6B.1

## Frozen comparison

- Provider: DeepSeek.
- Model: `deepseek-v4-flash`.
- Endpoint: `https://api.deepseek.com`.
- Seed: `56062026`.
- Tasks: TaskForge greenfield, TTL cache bugfix, CSV export, config refactor.
- Arms: bare one-shot, bare two-stage, MiMo-Code, Hephaestus.
- Pilot: TaskForge × four arms × one repetition.
- Main: four tasks × four arms × two repetitions.

Every run receives the exact task prompt, an identical fixture hash for its
task, a new git repository, and a new session directory. Hidden validators are
copied to the external live root and run on disposable copies; their contents
are never included in participant prompts or targets.

## Budgets

Primary envelope: 600 seconds, at most three logical calls, at most 12,288
output tokens, at most $0.03 estimated cost, and at most one validation repair.
One-shot and two-stage arms are further limited to one and two calls. MiMo
call/token limits are observed rather than pre-enforced and are reported as a
protocol mismatch. Global live spend stops before the projected next run would
reach $0.60.

## Arms

Bare one-shot receives task plus full text snapshot in one direct provider
request and must emit a strict operation manifest. Bare two-stage emits a
strict plan, then a strict manifest from task, snapshot, and plan. Neither arm
has tools, feedback, memory, repair, or a reviewer.

MiMo runs only through the supplied PowerShell wrapper, with `build`, JSON
format, pure mode, a fresh target, and an isolated per-run home/session. The
wrapper fixes `deepseek-bench/deepseek-v4-flash`.

Hephaestus uses its official provider-backed plan → prepare → apply →
deterministic validation → optional one repair → outcome path. Plan, manifest,
and one repair have benchmark approval. Final validation failure rolls back
after retaining a failed snapshot; hidden validation uses that snapshot.

## Evaluation

Hidden validation is deterministic and LLM-free. Weighted scores are
functional correctness 70, explicit requirement coverage 20, and scope/safety
10. Exact pass requires every hidden check and no scope violation.
Infrastructure failures are separated from coding-quality denominators.
False success means the arm declared success while hidden validation failed.

No participant output is edited, repaired, continued, or deleted by the
benchmark operator.

