# Repo-Aware Coding Loop

Phase 5G gives Hephaestus its first controlled coding loop.

```text
Hephaestus can now plan a scoped repo change, propose a patch, apply it with
approval/trust rules, run real validation, and learn from the result.
```

This is not full autonomy. It is a small, practical loop for low-risk repo
changes where the target is clear.

## Commands

```bash
uv run heph code plan "Update README intro to mention validation-backed release evidence." --repo .
uv run heph code propose "Update README intro to mention validation-backed release evidence." --repo .
uv run heph code apply <coding_change_id> --yes
uv run heph code run "Update README intro to mention validation-backed release evidence." --repo . --dry-run
uv run heph code run "Update README intro to mention validation-backed release evidence." --repo . --yes --max-iterations 1
uv run heph code run "Update README intro to mention validation-backed release evidence." --repo . --yes --rollback-on-failure
uv run heph code results
uv run heph code show <coding_request_id>
```

## Workflow

```text
request
-> repo context
-> scoped plan
-> patch proposal
-> lightweight review
-> apply with approval
-> real validation
-> outcome and learning
-> optional rollback
```

`plan` never writes files. `propose` creates a stored diff but does not apply it.
`apply` applies a previously proposed patch after `--yes`. `run` performs the
bounded loop, defaulting to one iteration.

## What It Handles

Phase 5G is meant for:

- docs edits,
- README refinements,
- simple typo or exact text replacement,
- small test additions to existing test files,
- small config/help text changes,
- small bugfixes when target files are clear.

It is not meant for:

- large architecture rewrites,
- dependency installs,
- uncontrolled multi-file edits,
- deploy, publish, push, or external side effects,
- destructive file operations,
- endless autonomous repair loops.

If the request is too broad, Hephaestus returns a plan and asks for narrower
scope.

## Patch Proposals

The deterministic proposer supports exact find/replace and small append/update
patterns for docs, tests, config/help text, and clear bugfix requests. Provider
backed proposals may be used later when a real provider is configured, but
deterministic local mode remains the default testable path.

Every proposal shows:

- files touched,
- diff,
- risk,
- checkpoint behavior,
- validation plan,
- approval requirement.

## Validation And Learning

After apply, validation runs through Phase 5F unless `--no-validate` is passed.
The coding-loop result links validation evidence, outcomes, learning signals,
decision traces, tool actions, and checkpoints.

Passing validation can complete the loop. Failing validation creates a failure
outcome and useful learning signal. With `--rollback-on-failure`, Hephaestus
restores the checkpoint and records why it rolled back.

## Conversation

Conversation remains non-mutating:

```bash
uv run heph discuss "Improve the README launch section." --repo . --propose-code
uv run heph chat --repo .
```

In chat, `/propose-code <request>` prints a coding plan and next command. It
does not apply patches.

## Storage

Phase 5G adds SQLite records for:

- `coding_requests`,
- `coding_plans`,
- `coding_changes`,
- `coding_iterations`,
- `coding_loop_results`.

Use `heph code show <coding_request_id>` to inspect the request, plan, patch,
review summary, validation, outcomes, traces, and checkpoint links.
