# Generalized Greenfield Coding Loop

Hephaestus can plan and apply bounded multi-file work in empty or existing
repositories through a strict provider-generated JSON plan and operation
manifest.

```text
heph code plan "Create a small Python CLI" --repo . --provider real
heph code prepare <plan-id> --yes
heph code apply <change-id> --yes --rollback-on-failure
```

The first approval permits manifest generation; the second permits filesystem
changes and displayed validation commands. Create, modify, delete, and move
operations are preflighted together, checkpointed, and confined to the selected
repository. Exact find/replace remains available for trivial legacy changes.

Validation commands from the model are candidates. Before apply, Hephaestus
shows the deterministic normalized validation plan, including normalization
reasons, expected test locations, stages, and timeouts. Python stdlib projects
with `tests/test_*.py` use explicit unittest discovery instead of relying on
generic `python -m unittest discover -v`.

`--allow-one-repair` permits one bounded provider repair after genuine
validation failure, followed by one revalidation. It is not an unbounded
self-healing loop. `--rollback-on-failure` restores the checkpoint and performs
scoped cleanup of new runtime residue such as `__pycache__` and `.pyc`.
`--retain-failed-snapshot` is an opt-in benchmark/debug feature that saves a
sanitized failed workspace outside the target before rollback.

This is not a native model tool loop or Claude Code equivalent. Model quality
still needs live benchmark evidence. Raw reasoning is never persisted.
