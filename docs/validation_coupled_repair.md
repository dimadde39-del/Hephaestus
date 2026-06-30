# Validation-Coupled Repair and Rollback Hygiene

Hephaestus treats model-proposed validation commands as candidates, not as
absolute truth. Before manifest apply, the deterministic validation planner
normalizes commands using changed files, expected files, language/framework
signals, repo structure, local executables, dependency policy, and user
permissions.

For standard-library Python projects with `tests/test_*.py`, generic unittest
discovery is normalized from:

```text
python -m unittest discover -v
```

to:

```text
python -m unittest discover -s tests -p "test_*.py" -v
```

The proposal view shows model-proposed commands, normalized commands,
normalization reasons, expected test locations, validation stages, and timeouts
before the apply approval.

Manifest validation is staged:

1. Structure: expected files, safe paths, non-empty generated files where
   required, and manifest operations versus filesystem state.
2. Syntax/import: bounded Python `compileall` over created or modified Python
   paths.
3. Test discovery: zero-test output such as `Ran 0 tests`, `collected 0 items`,
   or `no tests ran` is classified as `VALIDATION_NO_TESTS_DISCOVERED`.
4. Test execution: exit code, stdout/stderr, duration, parsed discovered,
   passed, failed, and skipped counts are recorded when available.
5. Functional smoke: only safe, bounded, pre-shown commands are eligible.

If deterministic discovery sees test files and the first command discovers no
tests, Hephaestus may try one deterministic fallback inside the same validation
session. It does not start a model regeneration loop.

If syntax/import/test validation still fails and budget allows it, `--allow-one-repair`
permits exactly one provider repair call. The repair receives the approved plan,
current manifest, current diff, created file inventory, bounded validation
evidence, failure classification, and remaining budget. It must return strict
`RepairManifest` JSON with only create, modify, delete, or move operations.
Repair cannot touch `.git` or `.hephaestus`, leave the repository, delete tests
to fake success, empty meaningful assertions, hide the failing command, or
declare success without revalidation.

There is no infinite self-healing loop. Defaults are one validation repair call
and three total provider calls for greenfield plan, manifest, and repair.

Rollback uses scoped before/after inventory, not `git clean -fdx`. It restores
the checkpoint, removes files/directories created by the manifest, removes new
runtime residue such as `__pycache__` and `.pyc`, preserves pre-existing
untracked or ignored files, and records residue status.

`--retain-failed-snapshot` is opt-in. When set, Hephaestus writes a sanitized
`failed-workspace/` outside the target before rollback, plus pre-rollback diff,
file hashes, and validation evidence. Secrets, `.git`, `.hephaestus`, local
databases, and raw reasoning are excluded.

This still is not a native model tool loop. Hephaestus remains a bounded,
approval-driven coding loop with deterministic validation and rollback hygiene.

Validation and repair evidence is part of the broader harness-learning story.
See [Learning stack](learning_stack.md), [Experience governance](experience_governance.md),
and [Verifier and reward model](verifier_and_reward_model.md).
