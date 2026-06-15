# Phase 5G: Repo-Aware Coding Loop

Phase 5G adds Hephaestus' first controlled coding loop:

```text
request -> repo context -> scoped plan -> patch proposal -> review -> apply with approval -> validation -> outcome/learning -> optional rollback
```

This is not full autonomy. It is limited to small scoped repo changes where
files are clear and validation can provide evidence.

## Implemented

- `hephaestus.coding_loop` package:
  - `schemas.py`
  - `planner.py`
  - `patcher.py`
  - `reviewer.py`
  - `executor.py`
  - `repository.py`
  - `renderer.py`
  - `analysis.py`
- SQLite migration v15:
  - `coding_requests`
  - `coding_plans`
  - `coding_changes`
  - `coding_iterations`
  - `coding_loop_results`
- CLI:
  - `heph code plan`
  - `heph code propose`
  - `heph code apply`
  - `heph code run`
  - `heph code results`
  - `heph code show`
- Conversation:
  - `--propose-code` on `ask`, `discuss`, and `chat`
  - `/propose-code <request>` inside chat

## Safety Boundary

Safe planning, repo inspection, and patch proposal do not require approval.
File mutation requires `--yes`. Destructive actions, protected files, external
side effects, and oversized requests are blocked or converted to plan-only
output.

The default `--max-iterations` is `1`. There is no endless autonomous repair
loop.

## Validation And Rollback

After patch apply, validation runs through Phase 5F unless `--no-validate` is
passed. If validation fails and `--rollback-on-failure` is set, Hephaestus
restores the Phase 5E checkpoint and records a rollback trace/outcome.

## Evidence

Coding-loop records link:

- repo profile,
- active policy profile,
- plan,
- patch proposal,
- tool patch/action ids,
- checkpoint ids,
- validation result ids,
- outcome ids,
- learning signal ids,
- decision trace ids.

## Next Required Phase

Do not move directly to Phase 6. The next phase is:

```text
Phase 5G.5: README Reality / Product Positioning Pass
```

Purpose:

- lead with self-improving agent value, not internal optimization machinery;
- show what works today;
- show the coding loop;
- separate public value from advanced internals;
- make the README feel like a product.
