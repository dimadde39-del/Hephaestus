# Contributor Guide

Greenfield coding tests use scripted/fake HTTP transports. Pytest and CI must
never call a live provider, persist raw reasoning, or write outside their
temporary target repository.

This guide gives new contributors the project context behind
[CONTRIBUTING.md](../CONTRIBUTING.md).

## The Product Bet

Hephaestus is a model-agnostic intelligence harness. Most agent demos jump from
prompt to action and then lose the trail. Hephaestus focuses on the loop around
the model:

```text
context -> planning -> tools -> validation -> repair -> outcome evidence -> learning
```

That means the core system should be able to answer:

- What did it inspect?
- What context or memory shaped the work?
- What plan did it generate?
- What alternatives did it compare?
- What tradeoffs did it expose?
- Why did it choose this option?
- What patch or command was proposed?
- What validation evidence exists?
- Was repair attempted, and was it bounded?
- What happened afterward?
- What should future decisions learn?

Benchmark language should compare:

```text
same model without Hephaestus vs same model with Hephaestus
```

Do not claim that a weaker model always beats a stronger one. On bounded tasks,
a good harness can sometimes let a weaker model outperform a stronger model
without comparable context/tool/verification support; that still requires
evidence.

## Current Priorities

- Keep the README and public docs product-first and honest.
- Make the current conversation, validation, and coding-loop demos easy to run.
- Strengthen repo-aware scoped change planning.
- Improve validation evidence, outcomes, and learning signals.
- Improve decision traces and explanation quality without making them the public
  headline.
- Keep policy learning reviewable and reversible.
- Keep Studio chat excellent: exact persisted messages, searchable history,
  local provider clarity, and no automatic recap on reopen.
- Keep Studio complete and quiet: Chat first, Workbench second, Memory third,
  Settings fourth, Advanced deliberately secondary.
- Strengthen memory control, provider settings, backup/export, accessibility,
  packaging, and public-alpha validation.
- Prepare Phase 5.6 coding-quality benchmarks before making Claude Code parity
  claims.
- Treat Phase 6 as the learning-stack program: Context Forge, Experience
  Ledger governance, cognitive strategies, personal/project/global boundaries,
  CPU controller learning, skill distillation, reward/model adaptation research,
  SWE-RL/self-play research, and opt-in community/global learning.
- Keep status labels explicit: Built, Partially built, Planned, Research.
- Keep all provider tests offline. Live smoke commands must require `--live`,
  use isolated databases/workspaces, redact secrets and raw reasoning, and
  enforce call/output/estimated-cost limits.

## Deferred Work

The following are intentionally not current priorities:

- Reward models as production authorities.
- SFT, LoRA, QLoRA, DPO, distillation, or adapters.
- CPU-trained adaptive controller policies.
- Global/community learning without explicit opt-in governance.
- Voice features.
- Telegram/Discord bots.
- Always-on daemon work.
- Browser automation.
- Full autonomous repo editing.
- Broad integration marketplaces.

If a contribution touches one of these, it should first explain why it is needed
for core decision quality now.

## Development Commands

```bash
uv sync --extra dev
uv run ruff format .
uv run ruff check .
uv run pytest
uv run mypy
uv run heph doctor
uv run heph studio doctor
uv run heph models test deepseek
uv run heph models smoke deepseek --case coding
uv run heph validate run . --dry-run
uv run heph code run "Update README wording to mention validation-backed release evidence." --repo . --dry-run
uv run heph release plan . --pareto --qubo --with-validation --yes
```

Studio frontend commands:

```bash
cd apps/studio
pnpm install
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

Do not put provider keys in committed `.env` files, fixtures, test snapshots,
logs, or issue reports. Fake HTTP responses must cover provider success and
failure paths. A live smoke result is evidence for connectivity and the bounded
tested flow only; it is not coding parity evidence.

## Design Expectations

- Prefer explicit Pydantic schemas for persisted artifacts.
- Keep SQLite migrations simple and local-first.
- Keep CLI output readable for people who are not already familiar with the
  internals.
- Make unsafe or simulated behavior visible in the output.
- Add explanations near the decision, not as an afterthought.
- Keep future execution gated by risk classification and approval records.
- In Studio, prefer the chat timeline and conversation history over dashboard
  surfaces. Advanced internals should be linked deliberately, not dumped into
  the first screen.
- Never add automatic conversation summaries as the default continuity
  mechanism. Exact message history is the Phase 5.5A contract.
- Never expose provider secrets through API responses, exports, screenshots, or
  docs.
- For advanced views, show structured decision artifacts only. Do not expose
  private chain-of-thought.
- Repository context permission is not training permission.
- Private code and personal facts must not enter global learning by default.
- Reward models must never replace deterministic verification.
- Self-evaluation alone must not create positive training labels.
- Hidden tests, holdouts, permission boundaries, audit logs, rollback
  mechanisms, dataset governance, and promotion gates must not be modified by
  the learning system.
- Do not delete tests, weaken assertions, hide failing commands, or select
  easier tasks merely to improve metrics.
- Claims about coding parity require reproducible benchmark evidence: same
  model, same repo snapshot, same task, same budget, hidden validation,
  multiple runs, and median results.

## Learning Architecture Docs

- [Learning stack](learning_stack.md)
- [Experience governance](experience_governance.md)
- [Verifier and reward model](verifier_and_reward_model.md)
- [Personal, project, and global learning](personal_project_global_learning.md)
- [Model adaptation lab](model_adaptation_lab.md)

## Good First Issue Areas

- Improve docs clarity with real command output.
- Add tests around edge cases in repo inspection.
- Improve wording in Rich renderers without changing behavior.
- Add small benchmark fixtures that stress one clear optimizer behavior.
- Add examples that show how to inspect saved artifacts.
- Add focused Studio UI tests for persistent chat, search, and conversation
  metadata without adding mocked production behavior.
- Add focused Studio tests for memory suggestions, provider redaction,
  backup/restore, degraded states, accessibility-critical keyboard flows, and
  narrow viewport behavior.
