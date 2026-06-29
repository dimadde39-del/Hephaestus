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

This is not a native model tool loop or Claude Code equivalent. Model quality
still needs live benchmark evidence. Raw reasoning is never persisted.
