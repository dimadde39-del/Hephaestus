# Hephaestus Phase 3C Policy Learning

Phase 3C adds policy learning and decision quality profiles.

```text
Learning Signal -> Profile Suggestion -> Decision Quality Profile -> Future Decision Bias
```

## What Changed

- Added `src/hephaestus/policy_learning/` with schemas, profile store, learner,
  appliers, renderers, and analysis helpers.
- Added typed Pydantic records:
  `DecisionQualityProfile`, `ProfileRule`, `ProfileAdjustment`,
  `ProfileEvidence`, `ProfileEvaluation`, and `ProfileApplicationResult`.
- Added SQLite migration 5 with `decision_quality_profiles` and
  `profile_applications`.
- Added learner aggregation over outcomes, reflections, learning signals,
  failure memory drafts, policy update suggestions, and decision traces.
- Added CLI commands:
  `heph profile suggest`, `heph profile list`, `heph profile show`,
  `heph profile activate`, `heph profile archive`, `heph profile active`, and
  `heph profile apply-demo`.
- Integrated active profiles into model routing, context packing, token
  firewall, scheduler weights, benchmark reports, and explain output.
- Added `heph benchmark run --profile <profile_id>` for explicit benchmark
  profile application.

## Principle

Hephaestus does not silently rewrite itself.
It converts outcomes into inspectable decision quality profiles that can be reviewed, activated, and measured.

Profiles are explicit, reversible, and safe. Draft profiles do not influence
future decisions. Activation is an intentional command.

## Application Behavior

- Model router profiles can raise quality thresholds and add model prefer/avoid
  tags.
- Context packer profiles can treat critical context as a hard guard and boost
  failure memories under token pressure.
- Token firewall profiles can make quality preservation stricter before cost or
  token savings.
- Scheduler profiles can increase dependency violation and risk penalties.
- Safety profiles can demonstrate stricter approval gates for external
  side-effect actions.

Each application records before/after values and an effect summary in
`profile_applications`.

## Known Limits

- Profile learning is deterministic and local.
- Profile suggestions are simple aggregations, not statistical causal proofs.
- Safety integration is conservative and demonstrative; there is no always-on
  tool execution engine in this phase.
- Profiles do not rewrite source code, prompts, skills, or policy files.
- No dashboard, voice, Telegram, browser automation, always-on daemon, or full
  skill self-growth was added.

## Recommended Next Phase

Phase 3D: Pareto Optimization + Decision Tradeoff Frontier.

That phase should evaluate multiple competing decision candidates across
quality, cost, latency, risk, privacy, and token usage instead of collapsing
everything into one simple score too early.
