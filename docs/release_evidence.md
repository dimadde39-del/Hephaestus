# Release Evidence

Phase 5F makes release readiness evidence-aware.

Release planning now distinguishes three states:

- `no_validation_evidence`: a plan exists, but validation has not run.
- `simulated_outcome_evaluation`: `--evaluate` generated deterministic outcomes
  over decision traces, but no repo validation command passed or failed.
- `real_validation_evidence`: approved validation commands ran through the safe
  tool runtime and produced command results.

## Simulated Evaluation

```bash
uv run heph release plan . --pareto --qubo --evaluate
```

This path is still useful for showing optimizer traces, Pareto/QUBO artifacts,
simulated outcomes, and learning signals. It does not mean tests passed.

## Real Validation

```bash
uv run heph release plan . --pareto --qubo --with-validation --yes
```

This path:

- creates the release plan,
- runs the validation plan through the safe tool runtime,
- links validation evidence to the release plan,
- creates outcomes and learning signals,
- adjusts readiness from real command results.

## Readiness Impact

Passing validation can increase readiness. Warnings reduce that positive impact.
Failed, timed-out, blocked, or approval-required validation downgrades readiness.

Recommendation behavior:

- passed validation can produce `mostly_ready` or `ready`,
- failed or timed-out validation produces `blocked`,
- approval-gated validation produces `needs_validation`,
- missing commands produce weaker readiness and a learning signal.

## Inspecting Evidence

```bash
uv run heph release show <release_plan_id>
uv run heph validate show <validation_result_id>
uv run heph validate results
uv run heph explain <validation_run_id>
```

Release plans link to validation results when available. Validation results link
to tool actions, tool execution results, outcomes, learning signals, and decision
traces.

## Coding Loop Evidence

Phase 5G also uses validation evidence after approved repo patches:

```bash
uv run heph code run "Update README wording to mention validation-backed release evidence." --repo . --yes
uv run heph code show <coding_request_id>
```

Coding-loop evidence is scoped to the change request rather than a full release
recommendation. It records the patch proposal, review, apply action,
checkpoint, validation result, optional rollback, outcomes, learning signals,
and decision traces. A passing coding-loop validation result is useful release
evidence, but it does not replace a release plan or external CI.

## Known Limits

Real local validation is strong evidence, not a guarantee. It does not inspect
unrun CI jobs, external services, deploy permissions, package registry state,
current advisories, or production environment behavior.
