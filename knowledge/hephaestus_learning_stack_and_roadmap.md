# Hephaestus Learning Stack And Roadmap Update

Updated the public product and architecture framing around Hephaestus as a
model-agnostic intelligence harness:

```text
context -> planning -> tools -> validation -> repair -> outcome evidence -> learning
```

The main benchmark is same model without Hephaestus versus the same model with
Hephaestus. The docs avoid claiming that weak models always beat strong models;
they state the narrower bounded-task claim that a strong harness can sometimes
let a weaker model outperform a stronger model without comparable
context/tool/verification support.

## Status Boundaries

- **Built:** local CLI and Studio surfaces, memory, strategic memory, repo
  inspection, safe tools, validation execution, scoped coding, greenfield
  plan/manifest flow, one bounded validation repair, rollback cleanup, outcomes,
  learning signals, policy profiles, model metadata, provider settings, and
  usage evidence.
- **Partially built:** system learning without model weight changes through
  memory, outcomes, learning signals, policy profiles, validation evidence,
  model routing primitives, context packing, and the skills registry.
- **Planned:** Context Forge, Experience Ledger governance, cognitive strategy
  engine, personal/project/cross-project intelligence, CPU-trained controller
  learning, and skill/capability distillation.
- **Research:** reward models, SFT, LoRA, QLoRA, DPO, distillation, adapters,
  SWE-RL, self-play, and opt-in community/global learning.

## New Public Docs

- `docs/learning_stack.md`
- `docs/experience_governance.md`
- `docs/verifier_and_reward_model.md`
- `docs/personal_project_global_learning.md`
- `docs/model_adaptation_lab.md`

Updated README, roadmap, architecture, provider, Studio workflow, contributor,
and positioning docs to use explicit status labels and to avoid presenting
reward models, model weight adaptation, CPU policy learning, or global learning
as implemented.

## Governance Rules Captured

- Repository context permission is not training permission.
- Private code and personal facts do not enter global learning by default.
- Reward models never replace deterministic verification.
- Self-evaluation alone cannot create positive training labels.
- Hidden tests, holdouts, permission boundaries, audit logs, rollback
  mechanisms, dataset governance, and promotion gates cannot be modified by the
  learning system.
- Failed and unknown outcomes cannot silently become positive examples.
