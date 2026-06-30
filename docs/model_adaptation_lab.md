# Model Adaptation Lab

The Model Adaptation Lab is the long-term research and evaluation track for
controller learning, reward models, adapters, and promotion gates.

Nothing in this document is implemented as base-model weight training today.

## Status

- **Built:** model-provider abstraction, model metadata, cost estimates, JSON
  reliability flags, context windows, provider usage records, deterministic
  local/fake providers, DeepSeek, and OpenAI-compatible provider paths.
- **Partially built:** routing and context packing primitives, policy profiles,
  validation evidence, outcome records, and learning signals.
- **Planned:** CPU-trained controller learning for strategy, model, tool,
  validation, skill, uncertainty, cost, and risk selection.
- **Research:** reward models, SFT, LoRA, QLoRA, DPO, distillation, SWE-RL,
  self-play, personal adapters, project adapters, and task adapters.

## CPU-Trained Controller Learning

Planned controller models improve the harness layer:

- contextual bandits.
- small ranking/classification models.
- strategy router.
- model selector.
- tool selector.
- validation planner.
- skill utility predictor.
- uncertainty estimator.
- cost model.
- risk model.
- active-learning policy.

These systems choose how Hephaestus uses context, tools, validation, and model
providers. They do not change the base LLM weights.

## Model Weight Adaptation

Research/planned adaptation techniques:

- SFT.
- LoRA.
- QLoRA.
- DPO.
- distillation.
- personal adapters.
- project adapters.
- task adapters.

Adapters can only be trained from governed, permissioned, validated datasets.
Self-evaluation alone is not a positive label. Failed and unknown outcomes must
remain failed or unknown unless later verifier evidence changes the record.

## Model Capability Profiles

Each model should have an evolving capability profile:

- coding.
- planning.
- tool reliability.
- JSON reliability.
- context reliability.
- vision.
- latency.
- cost.
- known failure modes.

The harness should adapt to the selected model. For example, a model with weak
JSON reliability may need stricter schema prompts and repair budgets; a model
with strong planning but weak tool reliability may need more deterministic
validation and smaller operation manifests.

## Promotion Gates

Candidate controllers, reward models, adapters, and distilled skills follow
the capability lifecycle:

```text
need detected -> candidate -> quarantine -> offline A/B benchmark -> regression tests
-> shadow mode -> canary -> approval -> active -> monitor
-> restrict/update/deprecate/delete
```

Hidden benchmarks, holdouts, audit logs, permission boundaries, rollback
mechanisms, and dataset governance are outside the learner's control.

## See Also

- [Learning stack](learning_stack.md)
- [Experience governance](experience_governance.md)
- [Verifier and reward model](verifier_and_reward_model.md)
- [Personal, project, and global learning](personal_project_global_learning.md)
- [Model provider conversations](model_provider_conversations.md)
