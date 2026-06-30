# Phase 5.6A.1.2: Validation-Coupled Repair and Rollback Hygiene

Implemented deterministic validation normalization for greenfield manifests:
model-proposed commands are candidates, and Python stdlib projects with
`tests/test_*.py` use explicit unittest discovery.

Added staged manifest validation for structure, Python compileall, test
discovery, and test execution. Zero-test output is classified as
`VALIDATION_NO_TESTS_DISCOVERED`, not ordinary test failure.

Added one bounded validation repair path behind `--allow-one-repair`. Repair
uses strict `RepairManifest` JSON, shares the provider budget, cannot delete or
disable tests to fake success, and must pass revalidation before the coding loop
reports success.

Added scoped rollback inventory cleanup. Failed validation rollback removes new
manifest files, newly created directories, `__pycache__`, `.pyc`, and temporary
validation residue while preserving pre-existing untracked or ignored files.

Added opt-in `--retain-failed-snapshot` support for benchmark/debug evaluation:
the snapshot is outside the target and excludes secrets, `.git`, `.hephaestus`,
SQLite databases, and raw reasoning.

The native model tool loop remains absent; this is still an approval-gated,
bounded manifest apply/validate/repair/rollback loop.
