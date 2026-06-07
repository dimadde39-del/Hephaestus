# Hephaestus Phase 3B Outcome Learning

Phase 3B adds outcome tracking, deterministic reflection, failure memory drafts,
learning signals, and policy update suggestions.

```text
Hephaestus does not only explain decisions.
It observes whether decisions worked, records outcomes, and turns failures into learning signals.
```

## What Changed

- Added `src/hephaestus/outcomes/` with schemas, evaluator, repository,
  renderer, and analysis helpers.
- Added typed Pydantic records:
  `OutcomeRecord`, `OutcomeMetric`, `OutcomeEvidence`, `ReflectionRecord`,
  `LearningSignal`, `FailureMemoryDraft`, and `PolicyUpdateSuggestion`.
- Added SQLite migration 4 with `outcomes`, `reflections`,
  `learning_signals`, `failure_memory_drafts`, and
  `policy_update_suggestions`.
- Linked outcomes back to `decision_traces.outcome_id`, and linked failure
  drafts/policy suggestions through the existing future-learning fields.
- Added deterministic benchmark/trace evaluators for model quality, context
  packing, budget pressure, safety approval gates, and score-based optimizer
  choices.
- Added CLI commands:
  `heph outcome add`, `heph outcome list`, `heph outcome show`,
  `heph reflect`, `heph learn signals`, `heph learn failures`,
  `heph learn policies`, and `heph learn promote-failure`.
- Added `heph benchmark run --evaluate`.
- Updated `heph explain <run_id>` and `--summary` to show linked outcomes and
  outcome-learning counts.

## Principle

The stable loop is:

```text
Decision -> Outcome -> Reflection -> Memory Draft -> Learning Signal -> Better Future Decision
```

Phase 3B deliberately stores learning evidence as drafts and suggestions. It
does not auto-apply policy updates or silently rewrite core behavior.

## Evaluation Rules

- Model routing success: selected quality is greater than or equal to required
  quality threshold.
- Model routing failure: no route or selected quality below threshold.
- Context success: critical context preserved and budget respected.
- Context failure: critical context missing or budget exceeded.
- Budget success: token, cost, and quality constraints all satisfied.
- Budget failure: quality threshold violated.
- Budget partial: quality preserved but token or cost pressure remains.
- Safety success: risky action requires approval.
- Safety failure: high-risk action allowed without approval, creating a policy
  update suggestion.

## CLI Examples

```bash
uv run heph benchmark run benchmarks/task_graphs/model_quality_threshold.json --evaluate
uv run heph reflect run_xxxxx
uv run heph learn signals
uv run heph learn failures
uv run heph learn policies
uv run heph outcome add trace_xxxxx --status success --summary "Manual outcome"
```

## Known Limits

- Outcomes are deterministic/simulated for current benchmark and optimize-style
  flows.
- There is no live tool execution engine yet that observes real tool results.
- Failure drafts are not promoted automatically.
- Policy suggestions are not auto-applied.
- There is no dashboard, daemon, Telegram, browser automation, or full skill
  self-growth in this phase.

## Recommended Next Phase

Phase 3C: Policy Learning + Decision Quality Profiles.

That phase should use accumulated outcomes and learning signals to tune model
routing thresholds, context strategy profiles, scheduler weights, and reviewed
safety policy suggestions without unsafe automatic self-modification.
