# Experience Governance

Experience governance controls which observed work can influence memory,
skills, controller policies, reward models, adapters, and public benchmark
claims.

Status: **Planned**, with **partially built** foundations in outcomes, learning
signals, policy profiles, validation evidence, provider usage records, and
rollback artifacts.

## Governed Experience Record

Each durable experience should carry:

- provenance: source task, conversation, tool run, coding run, provider,
  command, repo snapshot, and artifact IDs.
- permission records: what the user allowed for context, storage, training, and
  sharing.
- validation confidence: hidden tests, visible tests, lint/typecheck/build,
  exit codes, user acceptance, rollback result, and reviewer confidence.
- deduplication identity: content hash, diff hash, task fingerprint, and source
  IDs.
- staleness metadata: repo age, dependency age, model version, policy version,
  and validation date.
- contamination markers: known benchmark leakage, hidden-test exposure,
  prompt-response leakage, or untrusted labels.
- retention and deletion policy.
- dataset version and rollback history.

## Dataset States

```text
clean
suspect
contaminated
rejected
expired
```

- **clean:** permissioned, deduplicated, current, and verified enough for its
  intended use.
- **suspect:** useful for review but not promotion or training.
- **contaminated:** known leakage, invalid permission, hidden-test exposure, or
  label corruption.
- **rejected:** reviewed and excluded.
- **expired:** formerly acceptable but too stale for the target use.

Failed runs and unknown outcomes are retained as evidence, not silently
converted into positive examples.

## Capability Lifecycle

Every learned or generated capability follows the same lifecycle:

```text
need detected -> candidate -> quarantine -> offline A/B benchmark -> regression tests
-> shadow mode -> canary -> approval -> active -> monitor
-> restrict/update/deprecate/delete
```

This applies to:

- skills.
- policy models.
- reward models.
- adapters.
- validation strategies.
- generated capabilities.

Quarantine means the capability can be inspected and tested but cannot steer
normal work. Promotion requires evidence and approval appropriate to the risk.

## Reward-Hacking Protections

The learning system must not modify or bypass:

- hidden benchmarks.
- holdout datasets.
- permission boundaries.
- audit logs.
- rollback mechanisms.
- dataset governance.
- promotion gates.

It must not delete tests, weaken assertions, hide failing commands, select
easier tasks, or mark unknown outcomes as success to improve metrics.

## Rollback and Deletion

Governance must support rollback at two levels:

- target workspace rollback after failed execution.
- dataset rollback when an experience, label, capability, or adapter is later
  found suspect or contaminated.

Deletion requests must remove or disable future use according to the permission
record. Global/community datasets must be opt-in and versioned so removal can
be audited.

## See Also

- [Learning stack](learning_stack.md)
- [Verifier and reward model](verifier_and_reward_model.md)
- [Personal, project, and global learning](personal_project_global_learning.md)
- [Model adaptation lab](model_adaptation_lab.md)
- [Validation-coupled repair](validation_coupled_repair.md)
