# Personal, Project, And Global Learning

Hephaestus separates learning by scope. The same evidence can be useful at
different levels, but permissions and confidentiality differ.

Status:

- **Built / partially built:** project-local memory, strategic memory, outcomes,
  policy profiles, and local provider settings.
- **Planned:** richer project intelligence, personal capability controls, and
  cross-project abstraction transfer.
- **Research:** opt-in global/community learning and personal/project adapters.

## Project Intelligence

Project intelligence is repo-specific:

- architecture and module map.
- conventions.
- recurring failures.
- validation strategies.
- local skills.
- release and coding outcomes.
- dependency and tooling constraints.

It should help Hephaestus work better in one repository without leaking private
details elsewhere.

## Personal Intelligence

Personal intelligence is user-specific:

- goals.
- preferences.
- working style.
- risk tolerance.
- autonomy settings.
- preferred providers and budgets.
- optional personal adapters.

Personal facts require explicit controls. They should not become project or
global training data by accident.

## Global Intelligence

Global intelligence covers reusable, non-confidential abstractions:

- general strategies.
- anonymized aggregate evidence.
- generic skills.
- model capability profiles.
- validation heuristics.
- common failure modes.

Global/community learning is explicit opt-in.

## Scope Rules

- Repository context permission is not training permission.
- Private code and personal facts never enter global learning by default.
- Cross-project transfer moves abstractions, not confidential details.
- Global/community learning is explicit opt-in.
- Project-local evidence can influence project-local memory and strategies
  without granting permission for model training.
- Personal preferences can guide the harness without being shared globally.

## Cross-Project Transfer

Safe transfer examples:

- "Python stdlib projects with `tests/test_*.py` should prefer explicit
  unittest discovery."
- "A validation strategy that saw zero tests should try at most one safe
  deterministic fallback."
- "A high-risk operation requires approval and rollback evidence."

Unsafe transfer examples:

- copying private source code into another project.
- turning personal facts into global examples.
- training a public adapter from private repository data without permission.

## See Also

- [Learning stack](learning_stack.md)
- [Experience governance](experience_governance.md)
- [Verifier and reward model](verifier_and_reward_model.md)
- [Model adaptation lab](model_adaptation_lab.md)
- [Roadmap](roadmap.md)
