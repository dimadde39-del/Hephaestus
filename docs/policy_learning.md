# Policy Learning

Phase 3C adds controlled policy learning through decision quality profiles.
This is Level 1 harness learning. It does not train base LLM weights and it is
separate from planned CPU-trained controller policies and research-only reward
models/adapters. See [Learning stack](learning_stack.md) and
[Model adaptation lab](model_adaptation_lab.md).

```text
Hermes learns workflows.
Hephaestus learns decision quality.
```

Outcome artifacts are useful, but passive. A learning signal can say a decision
failed; a profile can say what should be more conservative next time.

```text
Learning Signal -> Profile Suggestion -> Decision Quality Profile -> Future Decision Bias
```

Hephaestus does not silently rewrite itself.
It converts outcomes into inspectable decision quality profiles that can be reviewed, activated, and measured.

## Records

The `hephaestus.policy_learning` package defines:

- `DecisionQualityProfile`
- `ProfileRule`
- `ProfileAdjustment`
- `ProfileEvidence`
- `ProfileEvaluation`
- `ProfileApplicationResult`

Profiles have `draft`, `active`, or `archived` status. Rules are structured and
typed; rationale fields explain why a rule exists.

Decision areas:

- `model_router`
- `context_packer`
- `token_firewall`
- `scheduler`
- `safety`
- `memory_retrieval`
- `optimizer`

## Persistence

SQLite migration 5 adds:

- `decision_quality_profiles`
- `profile_applications`

Rules and evidence are stored as JSON inside `decision_quality_profiles`.
Applications record before/after inputs, effect summaries, and the profile that
caused the change.

## CLI

```bash
uv run heph profile suggest
uv run heph profile list
uv run heph profile show <profile_id>
uv run heph profile activate <profile_id>
uv run heph profile archive <profile_id>
uv run heph profile active
uv run heph profile apply-demo <profile_id>
```

`profile suggest` creates draft profiles. It does not activate them.

## Application

Active profiles can influence future decisions in small, inspectable ways:

- model router: adjust required quality threshold and prefer/avoid model tags,
- context packer: preserve critical context and boost failure memories,
- token firewall: make quality preservation stricter before savings,
- scheduler: increase dependency violation and risk penalties,
- safety: require approval for external side effects in the safe demo path.

Benchmark runs use active profiles by default and can also accept:

```bash
uv run heph benchmark run benchmarks/task_graphs/model_quality_threshold.json --profile <profile_id>
```

`heph explain <run_id>` shows profile applications. `--summary` includes a
profile application count.

## Preference Profiles vs Decision Quality Profiles

Phase 3D adds Pareto preference profiles. They are not learned policies.

- Preference profile: the current selection mode for ranking a Pareto frontier,
  for example `balanced`, `frugal`, `quality_first`, `privacy_first`,
  `safety_first`, or `speed_first`.
- Decision quality profile: a learned, reviewed, activatable rule derived from
  outcomes, reflections, learning signals, and failure evidence.

Both can operate in one run. Active decision quality profiles can adjust model
risk, context failure-memory importance, scheduler weights, or safety emphasis.
The selected Pareto preference then chooses among valid frontier candidates.

## Safety Boundary

Profiles are not unsafe self-modification. They are reviewed configuration
records with evidence, source IDs, rules, status, and application logs. A profile
can be archived when it is no longer wanted.

Pareto preference profiles are fixed, inspectable selection modes. They do not
learn by themselves and they do not rewrite decision quality profiles.

This is how Hephaestus starts saying:

```text
Given past outcomes, this kind of decision should be more conservative next time.
```
