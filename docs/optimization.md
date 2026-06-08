# Optimization

The optimization core is the center of Hephaestus. It is used to decide task
order, model routing, context packing, tool choice, autonomy/risk, and token
budget allocation.

## Objective Function

Phase 1 uses a weighted utility function:

```text
utility =
  + expected_value
  + priority
  + success/confidence proxy
  - token_cost
  - risk_penalty
  - uncertainty_penalty
  - dependency_violation_penalty
```

Weights live in `ObjectiveWeights` and can be tuned without changing task
schemas.

Active scheduler decision quality profiles can adjust objective weights at run
time. Profile applications are recorded so a later explanation can show exactly
which dependency or risk penalty changed.

## Greedy Baseline

The greedy scheduler repeatedly chooses the highest-scoring task whose
dependencies are already complete. This gives a stable, explainable baseline and
keeps dependency handling clear.

Greedy remains in benchmark reports even when simulated annealing wins because
it is the honest baseline: simple, explainable, and easy to reason about.

Phase 3A records the selected greedy-derived task order as a
`task_selection` decision trace with the annealing order as an alternative.

## Simulated Annealing

The annealing scheduler starts from the greedy order, explores swaps, and accepts
some worse intermediate states according to temperature. Dependency violations
are allowed during search but receive a large penalty, so valid plans tend to
win.

This is quantum-inspired in the practical sense: the runtime treats planning as
an energy landscape and searches for lower-cost/higher-utility configurations.

Annealing is not treated as automatically better. Benchmarks report the greedy
score, annealing score, absolute delta, percentage delta, dependency violations,
and the selected schedule. If annealing does not improve the objective, that is
shown directly.

The scheduler comparison also emits an `optimization` trace that records the
winning scheduler, score delta, objective score, and constraints considered.

## Pareto Frontiers

Phase 3D adds multi-objective comparison before the final recommendation.
Instead of only saying `best score = 84.2`, Hephaestus can show which candidate
is cheapest, highest quality, safest, fastest, or best balanced.

```text
Generate candidates -> score multiple objectives -> identify Pareto frontier -> select final candidate -> explain tradeoff
```

The current dimensions are quality, cost, latency, risk, privacy, token usage,
confidence, safety, and profile alignment. Quality, confidence, safety, privacy,
and profile alignment are maximized. Cost, latency, risk, and token usage are
minimized.

Built-in preference profiles rank a frontier:

- `balanced`: moderate weights across all objectives.
- `frugal`: cost and token reduction with quality/safety thresholds.
- `quality_first`: quality and confidence.
- `privacy_first`: local/private choices and low exposure risk.
- `safety_first`: safety, risk reduction, and approval-preserving choices.
- `speed_first`: latency and simpler plans.

Hephaestus does not hide tradeoffs behind a single magic score.
It exposes the decision frontier and explains why a candidate was selected.

## Future QUBO / Ising Direction

Later versions can represent ordering, model selection, context inclusion, and
tool choices as binary variables:

- `x_task_position`
- `x_model_for_task`
- `x_context_included`
- `x_tool_allowed`

Hard constraints become large penalties; soft preferences become weighted terms.
That opens the door to QUBO/Ising solvers, annealing benchmarks, and hybrid
classical/quantum-inspired planning.

Pareto frontiers prepare that layer by making the decision surface explicit:
the future formulation can convert context inclusion and task ordering
candidates into binary variables, then compare QUBO/Ising output against greedy,
annealing, and Pareto-selected approaches.

## Where Optimization Applies

- Task order.
- Model routing.
- Context packing.
- Tool choice.
- Risk and autonomy decisions.
- Token budget allocation.
- Active decision quality profile application.
- Pareto frontier selection across competing objectives.
- Future multi-agent task allocation.
- Future skill promotion.

## Run History

`heph optimize <scenario.json>` now saves each optimization run to local SQLite
at `.hephaestus/hephaestus.db`. A run captures:

- scheduled tasks and selected order,
- greedy and simulated annealing scheduler results,
- model routing decisions and rejected options,
- context packing selections and exclusions,
- token budget evaluation,
- pending approvals for approval-gated tasks,
- rich decision traces for scheduler, router, context, budget, and safety
  choices.

The CLI prints the saved run ID:

```text
Saved run: run_...
View with: heph run show run_...
Explain with: heph explain run_...
```

Durable run history is intentionally in place before always-on mode so future
daemon, dashboard, and benchmark features can inspect what happened across
processes.

## Benchmark Reports

`heph benchmark run` executes each fixture through the same optimizer pieces used
by `heph optimize`:

- greedy and simulated annealing scheduling,
- model routing with rejection reasons,
- context packing with before/after token counts,
- aggregate token and cost budget checks,
- approval counting for risky actions.

Benchmark runs are saved with `mode=benchmark`, and the resulting `heph run show`
output includes scheduler decisions, model route decisions, rejected options,
context packing, quality guard, token budget decisions, pending approvals, and
rich decision traces. Benchmark reports include decision count, top decision
type, top decision rationale, the most common rejection reason, quality
preserved status, and token savings summary.

By default benchmark runs use active decision quality profiles from the local
SQLite database. You can also pass an explicit profile:

```bash
uv run heph benchmark run benchmarks/task_graphs/model_quality_threshold.json --profile <profile_id>
```

Reports include profile application counts and a table of threshold/weight or
context strategy changes caused by profiles.
With `--pareto`, reports also include selected frontier candidates and tradeoff
explanations.

## Explainability

Optimization without explainability is hard to trust and hard to improve. The
same objective score can hide a quality rejection, a token-pressure tradeoff, an
approval gate, or a context exclusion. Phase 3A therefore records typed decision
traces for the major optimizer surfaces:

- `task_selection`: selected task order and scheduler alternatives.
- `model_routing`: selected model, rejected models, quality thresholds, cost,
  and capability/privacy/tool constraints.
- `context_selection`: included context, excluded context, token savings, and
  critical-context constraints.
- `budget`: token, cost, and quality budget outcomes.
- `safety`: approval-required actions and safety-policy triggers.
- `optimization`: objective comparison between strategies.

Rejected options are structured alternatives with scores, rejection reasons,
violated constraints, would-have cost, expected quality, and risk when those are
known. Trace metrics are typed records rather than prose-only logs. Each trace
also carries learning hooks plus nullable outcome, failure-memory, and
policy-update links.

Use `heph explain <run_id>` for a full trace, `heph explain <run_id> --summary`
for counts and rejection reasons, and `heph explain stats` for aggregate
decision statistics across persisted runs.

Hephaestus does not only optimize decisions. It records why each decision was
made so future versions can learn from outcomes.

Phase 3C closes the loop by letting active profiles bias future model routing,
context packing, token firewall, and scheduler inputs. The bias is explicit and
reversible: profiles must be activated, profile applications are persisted, and
`heph explain <run_id>` shows the effect.

The benchmark suite is designed to test optimizer behavior, not to claim
real-world AGI performance.
