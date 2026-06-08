# Outcome Learning

Phase 3B adds outcome tracking and failure-learning foundations. Phase 3C uses
those artifacts as evidence for decision quality profiles.

```text
Hephaestus does not only explain decisions.
It observes whether decisions worked, records outcomes, and turns failures into learning signals.
```

## Core Loop

```text
Decision -> Outcome -> Reflection -> Memory Draft -> Learning Signal -> Better Future Decision
```

Phase 3A answered:

```text
I selected this option because...
```

Phase 3B starts answering:

```text
This decision led to success, failure, partial success, or unknown result because...
```

## Records

The `hephaestus.outcomes` package defines:

- `OutcomeRecord`: observed or simulated success, failure, partial, or unknown
  result attached to a `decision_traces.id`.
- `OutcomeMetric`: typed measured evidence for an outcome.
- `OutcomeEvidence`: benchmark, manual, or future runtime evidence.
- `ReflectionRecord`: what worked, what failed, likely cause, and recommended
  change.
- `LearningSignal`: draft signal for model quality, context strategy, budget
  strategy, safety policy, task ordering, optimizer weights, or memory
  retrieval.
- `FailureMemoryDraft`: a failure-shaped memory candidate that can later be
  promoted explicitly.
- `PolicyUpdateSuggestion`: a reviewed, non-applied suggested policy change.

## Persistence

SQLite migration 4 adds:

- `outcomes`
- `reflections`
- `learning_signals`
- `failure_memory_drafts`
- `policy_update_suggestions`

When an outcome is saved, the linked decision trace receives `outcome_id`.
Failure drafts and policy suggestions can also update `failure_memory_id` and
`policy_update_id` so `heph explain <run_id>` can show the learning links.

## Evaluation

Current evaluation is deterministic and local:

- model quality succeeds when selected quality meets the required threshold,
- context packing succeeds when critical context is preserved under budget,
- budget decisions succeed when quality, token, and cost constraints are met,
- budget decisions partially succeed when quality is preserved but token/cost
  pressure remains,
- safety decisions succeed when risky actions require approval,
- high-risk actions without approval create policy update suggestions.

This is simulated outcome learning for benchmark and optimize-style traces. It
does not require DeepSeek or any paid API.

## CLI

```bash
uv run heph benchmark run benchmarks/task_graphs/model_quality_threshold.json --evaluate
uv run heph release plan . --pareto --qubo --evaluate
uv run heph outcome add <decision_trace_id> --status success --summary "Worked after review"
uv run heph outcome list
uv run heph outcome show <outcome_id>
uv run heph reflect <run_id>
uv run heph learn signals
uv run heph learn failures
uv run heph learn policies
uv run heph learn promote-failure <failure_draft_id>
```

`heph reflect <run_id>` evaluates missing benchmark outcomes, ensures
reflections exist, and lists successes, failures, partials, learning signals,
failure memory drafts, and policy suggestions.

Phase 4B uses the same evaluator when `heph release plan . --evaluate` is
enabled. These are simulated outcomes over decision traces, not proof that repo
commands passed. They create learning signals about task ordering, model
routing, context, budget, safety, Pareto/QUBO-style optimization traces, and
other explainable decisions that the release run produced.

## Failure Drafts Are Not Automatic Memory

Failure memory drafts are intentionally not promoted by default. Promotion is
explicit through `heph learn promote-failure <failure_draft_id>`, which creates a
normal persistent memory with `type=failure`.

This keeps the system auditable: failures become candidates for memory, not
silent rewrites of future behavior.

## Policy Suggestions Are Not Auto-Applied

Learning signals and policy update suggestions are draft evidence. They can
recommend stricter model routing, stronger critical-context preservation, lower
budget aggressiveness, or tighter safety approval gates, but Phase 3B does not
silently rewrite core behavior.

That boundary matters because Hephaestus is optimizing decision quality, not
performing unsafe self-modification.

## From Artifacts To Profiles

Learning artifacts are useful evidence, but they are passive until they can
influence a future decision in a controlled way. Phase 3C adds this reviewed
loop:

```text
Learning Signal -> Profile Suggestion -> Decision Quality Profile -> Future Decision Bias
```

`heph profile suggest` reads outcomes, reflections, learning signals, failure
memory drafts, policy suggestions, and decision traces. It creates draft
profiles for decision areas such as model routing, context packing, token
firewall, scheduler, safety, memory retrieval, and optimizer bias.

Draft profiles do not change behavior. A user must run
`heph profile activate <profile_id>` before a profile can influence future
benchmark or optimize runs. Profile applications are recorded and shown in
`heph explain <run_id>`.

Hephaestus does not silently rewrite itself.
It converts outcomes into inspectable decision quality profiles that can be reviewed, activated, and measured.

## Future Use

Phase 3B creates the data needed for:

- model performance learning,
- context strategy learning,
- budget strategy tuning,
- scheduler weight tuning,
- safety policy review,
- future skill evaluation,
- future optimizer tuning.

The recommended next phase is:

```text
Phase 3D: Pareto Optimization + Decision Tradeoff Frontier
```

That phase should compare decision candidates across quality, cost, latency,
risk, privacy, and token usage before collapsing tradeoffs into one score.
