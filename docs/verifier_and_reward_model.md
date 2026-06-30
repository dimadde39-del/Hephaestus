# Deterministic Verifier And Reward Model

Hephaestus separates high-confidence verification from learned estimation.

Status:

- **Built / partially built:** deterministic validation evidence, command
  results, rollback evidence, outcomes, learning signals, and user-visible
  approval records.
- **Research:** learned reward models for subjective or incomplete dimensions.

## Deterministic Verifier

The deterministic verifier layer produces high-confidence evidence from:

- hidden tests.
- exit codes.
- lint, typecheck, test, and build results.
- regressions.
- filesystem and permission invariants.
- real user acceptance or rejection.
- real cost and latency.
- rollback and recovery outcomes.

Deterministic evidence is not always complete, but when it exists it has higher
authority than self-evaluation or a learned preference estimate.

## Reward Model

A reward model is a learned estimate for dimensions that are incomplete,
subjective, or expensive to verify directly:

- architecture quality.
- plan quality.
- scope-drift risk.
- expected user acceptance.
- strategy utility.
- likely future success.

Reward model output can prioritize review, choose a safer strategy, or suggest
which candidate deserves more validation. It cannot declare success by itself.

## Rules

- Reward models never replace deterministic verification.
- Self-evaluation alone cannot create positive training labels.
- Hidden tests and holdouts cannot be modified by the learning system.
- Failed runs and unknown outcomes cannot silently become positive examples.
- A failing command remains failing even if a model predicts the work is good.
- Promotion requires evidence from the deterministic verifier or explicit human
  acceptance appropriate to the risk.

## No Reward Hacking

The learning system must not:

- delete tests or weaken assertions.
- bypass validation commands.
- hide a failing command.
- select easier tasks merely to improve metrics.
- modify hidden benchmarks or holdout datasets.
- cross permission boundaries.
- rewrite audit logs or rollback records.

## Practical Use

Today, Hephaestus stores deterministic validation evidence and learning signals.
Future reward models can rank candidate strategies or identify risky plans, but
the final outcome must still be grounded in verifier evidence and governance.

## See Also

- [Learning stack](learning_stack.md)
- [Experience governance](experience_governance.md)
- [Personal, project, and global learning](personal_project_global_learning.md)
- [Model adaptation lab](model_adaptation_lab.md)
- [Validation-coupled repair](validation_coupled_repair.md)
