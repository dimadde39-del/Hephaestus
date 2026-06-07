# Policy Learning

Phase 3C adds controlled policy learning through decision quality profiles.

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

## Safety Boundary

Profiles are not unsafe self-modification. They are reviewed configuration
records with evidence, source IDs, rules, status, and application logs. A profile
can be archived when it is no longer wanted.

This is how Hephaestus starts saying:

```text
Given past outcomes, this kind of decision should be more conservative next time.
```
