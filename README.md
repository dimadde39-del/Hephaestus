# Hephaestus

Hephaestus is a model-agnostic intelligence harness.

A model provides raw intellectual potential. Hephaestus turns that potential
into checked work through:

```text
context -> planning -> tools -> validation -> repair -> outcome evidence -> learning
```

The benchmark is not "small model beats big model." The benchmark is:

```text
same model without Hephaestus vs same model with Hephaestus
```

On bounded tasks, a good harness can sometimes let a weaker model outperform a
stronger model that lacks comparable context, tools, verification, and recovery.
That is a measurement claim to prove with evidence, not a blanket promise.

Phase 5.6B includes a frozen same-model harness-gain protocol comparing bare
DeepSeek, two-stage prompting, MiMo-Code, and Hephaestus. It makes no winner
claim beyond the measured task set. Protocol 5.6B.5 found mean scores of 52.38,
61.12, 79.88, and 50.62 respectively for bare one-shot, bare two-stage,
MiMo-Code, and Hephaestus; Hephaestus did not improve model quality in this
sample. See the
[harness-gain protocol](docs/benchmarks/harness_gain_protocol.md).

## What It Does Today

- Remembers project context in CLI and Studio conversations.
- Inspects repos, proposes scoped work, and runs approved validation.
- Applies approved patches/manifests with checkpoints, rollback, and one
  bounded validation-coupled repair path.
- Records outcomes, learning signals, policy context, model metadata, and usage
  evidence.

## Alpha Limits

Hephaestus is early. It is not a fully autonomous coding agent, native
open-ended model tool loop, daemon, deployer, browser agent, voice assistant, or
uncontrolled self-modifying system. It does not push, publish, deploy, or run
destructive work on its own. Local side effects require explicit approval.

## Quickstart

From a source checkout:

```bash
git clone https://github.com/dimadde39-del/Hephaestus.git hephaestus
cd hephaestus
uv sync --extra dev
uv run heph doctor
```

Try the practical loop:

```bash
uv run heph ask "What is this project trying to become?" --repo .
uv run heph validate run . --dry-run
uv run heph code run "Update README wording to mention validation-backed evidence." --repo . --dry-run
uv run heph code results
```

Launch Studio:

```bash
uv sync --extra studio
uv run heph studio
uv run heph studio doctor
```

Installed package flow:

```bash
uv tool install "hephaestus[studio]"
heph studio
```

Studio binds to `http://127.0.0.1:8741` by default, stores local state in
`.hephaestus/hephaestus.db`, and falls back to deterministic local mode when no
provider key is configured.

![Hephaestus Studio Workbench](docs/assets/studio/studio-workbench.png)

## Status

| Status | Capability |
|---|---|
| Built | CLI, Studio, local SQLite, memory, repo inspection, safe tools, validation, outcomes, policy profiles, provider settings, backup/export/restore |
| Built | Scoped coding and greenfield manifest loops with approval, checkpoints, validation, one optional repair, rollback, and evidence |
| Partially built | Model routing, context packing, model metadata, skills registry, decision quality profiles, and evidence-fed system learning |
| Planned | Context Forge, Experience Ledger governance, CPU controller learning, selectors, and skill/capability distillation |
| Research | Reward models, SFT, LoRA, QLoRA, DPO, distillation, adapters, SWE-RL, self-play, and community/global learning |

## Future Architecture

Hephaestus treats learning as three levels:

- **Level 1:** system learning without model weight changes. Partially built.
- **Level 2:** CPU-trained controller learning. Planned.
- **Level 3:** model weight adaptation through SFT, LoRA, QLoRA, DPO,
  distillation, and adapters. Research/planned.

Reward models and adapters are not implemented today. Future learned systems
must not replace deterministic verification, weaken tests, bypass permission
boundaries, or turn failed/unknown outcomes into positive examples.

## Model Providers

Hephaestus is provider-agnostic. Local deterministic mode is the offline/test
default. DeepSeek and OpenAI-compatible providers are optional; secrets stay
local and are redacted from normal API responses and exports.

```bash
uv run heph models
uv run heph models test deepseek
uv run heph models smoke deepseek --case coding
```

Smoke commands are network-free until `--live` is added. See
[DeepSeek V4 Flash](docs/deepseek_v4_flash.md),
[live provider smoke](docs/live_provider_smoke.md), and
[model provider conversations](docs/model_provider_conversations.md).

## More Docs

- [Architecture](docs/architecture.md)
- [Roadmap](docs/roadmap.md)
- [Learning stack](docs/learning_stack.md)
- [Experience governance](docs/experience_governance.md)
- [Verifier and reward model](docs/verifier_and_reward_model.md)
- [Personal, project, and global learning](docs/personal_project_global_learning.md)
- [Model adaptation lab](docs/model_adaptation_lab.md)
- [Greenfield coding loop](docs/greenfield_coding_loop.md)
- [Validation-coupled repair](docs/validation_coupled_repair.md)
- [Harness-gain benchmark protocol](docs/benchmarks/harness_gain_protocol.md)
- [Repo-aware coding loop](docs/repo_aware_coding_loop.md)
- [Studio](docs/studio.md)
- [Studio Workbench](docs/studio_workbench.md)
- [Studio trust and approvals](docs/studio_trust_and_approvals.md)
- [Contributor guide](docs/contributor_guide.md)

## Development

```bash
uv sync --extra dev
uv run ruff format .
uv run ruff check .
uv run pytest
uv run mypy
uv run heph doctor
uv run heph validate run . --dry-run
uv run heph release plan . --pareto --qubo --evaluate
```

Contributors should start with [CONTRIBUTING.md](CONTRIBUTING.md) and
[docs/contributor_guide.md](docs/contributor_guide.md). The short version:
improve the loop that helps Hephaestus remember context, plan scoped work, use
tools safely, validate results, recover honestly, and learn from evidence.
