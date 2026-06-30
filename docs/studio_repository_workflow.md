# Studio Repository Workflow

Studio Chat remains non-mutating. Select a repository and choose:

- **Chat** for conversation only;
- **Plan** for a provider-backed structured plan;
- **Build** for plan approval, manifest preview, explicit apply, and validation.

Build never silently changes files. Workbench shows provider usage, planned
files, structured operations, risks, validation, checkpoints, and outcomes.
Conversation-default providers are not automatically coding defaults.

For structured manifests, Studio surfaces the normalized validation plan before
apply approval: model-proposed commands, deterministic commands, reasons,
expected test locations, stage count, and timeouts. Validation may use one
deterministic discovery fallback when zero tests are found despite known test
files.

Manual repair remains explicit. API/CLI semantics are: approve one repair,
rollback now, or keep the failed workspace. The bounded repair path is available
through `allow_one_repair`; rollback cleanup is scoped to affected paths; failed
workspace snapshots are opt-in and sanitized. Native model tool looping is still
absent.
