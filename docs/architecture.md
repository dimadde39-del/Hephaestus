# Architecture

Hephaestus is organized around a local-first core that can grow into a safely
executable agent runtime without forcing paid APIs or a single model provider.

The public alpha architecture is easiest to read as one planning loop:

```text
Repo -> Profile -> Tasks -> Optimizer -> Pareto -> QUBO -> Explain -> Outcomes -> Learning Profiles
```

Phase 5A adds a second, text-first loop:

```text
Input -> Intent Classification -> Context Retrieval -> Deliberation Passes -> Final Response -> Memory Update
```

Phase 5B expands that loop:

```text
Input -> Intent Classification -> Regular + Strategic Memory Recall -> Rubric-Aware Deliberation -> Research Plan or Recommendation -> Strategic Memory Suggestions -> Decision Trace
```

Phase 5D inserts policy before synthesis:

```text
Input -> Policy Profile Evaluation -> Conversation / Benchmark / Boundary Response
```

Phase 5E adds controlled local tools:

```text
Tool Intent -> Risk Classification -> Approval Gate -> Safe Execution -> Observation -> Trace / Outcome
```

Phase 5F connects repo validation to real tool execution:

```text
Repo Validation Plan -> Approved Execution -> Evidence -> Outcome -> Learning -> Release Readiness
```

Phase 5G adds the first controlled coding loop:

```text
Request -> Repo Context -> Scoped Plan -> Patch Proposal -> Review -> Approved Apply -> Real Validation -> Outcome / Learning
```

This is still not full autonomy. It handles small docs, tests, config/help text,
and clear bugfix-style changes. Conversation turns can propose coding plans, but
they do not edit files automatically.

Phase 5.5A adds the first local Studio surface:

```text
Exact Conversation Messages -> Studio API -> Persistent Chat UI -> Reopen -> Continue
```

Studio does not replace old messages with summaries and does not generate an
automatic recap when a conversation opens. It reads the same SQLite
conversation tables as the CLI, displays the original timeline, and lets the
user continue through the existing conversation service.

## Core Modules

- `core`: shared runtime settings, privacy/risk levels, and event schemas.
- `spec`: a deterministic Phase 1 pipeline from user goal to `GoalSpec`, tasks,
  and `ExecutionPlan`.
- `storage`: SQLite initialization, migrations, persistent memories, run history,
  legacy decisions, rich decision traces, and approval records.
- `decision`: typed trace schemas, builders, SQLite trace repository, rendering,
  and aggregate analysis for explainable optimizer behavior.
- `outcomes`: typed outcome records, deterministic reflections, learning
  signals, failure memory drafts, policy update suggestions, SQLite repository,
  and Rich renderers.
- `policy`: user-owned policy profile schemas, built-in freedom modes,
  deterministic request classification, active-profile persistence, concise
  boundary rendering, over-refusal analysis, and policy benchmarks.
- `policy_learning`: decision quality profile schemas, SQLite profile store,
  deterministic learner, profile appliers, renderers, and profile summaries.
- `pareto`: objective vectors, preference profiles, candidate generation,
  Pareto frontier detection, selection, persistence, and Rich renderers.
- `qubo`: binary variables, QUBO terms, constraints, practical formulations,
  local solvers, Ising conversion, SQLite persistence, comparison helpers, and
  Rich renderers.
- `repo`: read-only repository inspection, stack detection, command risk
  classification, validation plan generation, repo-aware tasks, persistence,
  Rich renderers, and benchmark export.
- `tool_runtime`: local filesystem reads/search, shell command classification
  and execution, approval gates, patch proposals, checkpointed patch apply and
  restore, SQLite tool audit records, tool observations, and trace/outcome
  integration.
- `validation`: repo-derived validation execution plans, command classification,
  safe runtime execution, SQLite evidence, release validation summaries,
  command outcomes, learning signals, failure drafts, and Rich renderers.
- `coding_loop`: scoped coding request schemas, repo-aware planner,
  deterministic patch proposal, lightweight review, executor, SQLite
  persistence, renderers, and trace/outcome/learning integration.
- `release`: repo-aware release planning schemas, orchestration, readiness
  analysis, SQLite persistence, and Rich demo renderers.
- `conversation`: `ask`, `discuss`, and `chat` schemas, intent classifier,
  memory/repo context retrieval, internal deliberation passes, prompts, session
  orchestration, SQLite persistence, Rich renderers, and high-impact trace
  integration.
- `studio`: FastAPI local app, typed schemas, repository/service layer, CLI
  launcher, local-first security helpers, static frontend serving, conversation
  search, metadata updates, provider/policy exposure, and exact-message chat
  APIs for the Next.js Studio client.
- `strategic_memory`: typed strategic memories for goals, ambitions,
  constraints, preferences, principles, assumptions, decisions, rejected paths,
  lessons, and open questions, plus SQLite persistence, recall, conflict
  detection, extraction, and rendering.
- `discussion_quality`: rubrics and deterministic evaluation for idea stress
  tests, business strategy, product strategy, technical architecture, roadmap
  decisions, research planning, and risk analysis.
- `benchmarks`: fixture loading, optimizer execution, report models, Rich output,
  and JSON output.
- `memory`: typed memory records and lexical retrieval behavior.
- `optimize`: task ordering, model routing, context packing, and token budgets.
- `models`: provider-agnostic model profiles, fake provider, optional DeepSeek.
- `tools`: typed tool definitions before execution.
- `safety`: approval gates and policy checks for risky actions.
- `skills`: early registry for reusable procedures.
- `cli`: Typer/Rich commands for demos and validation.

## Flow

```text
User goal
  -> Optional RepoProfile from read-only local inspection
  -> GoalSpec
  -> Task graph
  -> Remembered context
  -> Objective scoring
  -> Greedy baseline
  -> Simulated annealing comparison
  -> Context packing
  -> Model routing
  -> Token firewall
  -> Safety policy
  -> Decision trace
  -> Outcome
  -> Reflection
  -> Learning signal / failure draft
  -> Profile suggestion / active profile bias
  -> Pareto frontier / tradeoff selection
  -> QUBO formulation / local binary solve
  -> Repo-aware benchmark export
  -> Release planning recommendation
  -> Optional approved validation execution
  -> Real validation evidence / release readiness update
  -> Optional scoped coding loop / checkpointed patch
  -> Coding validation / rollback decision
  -> Optional Studio reopening of exact conversation history
  -> Optional safe tool runtime action
  -> Benchmark report / persisted run
  -> ExecutionPlan
```

At the product level this is the current alpha loop expressed as:

```text
Inspect -> Specify -> Optimize -> Explain -> Evaluate -> Learn -> Execute safely with approval
```

Phase 1 intentionally avoids a long-running daemon. The CLI proves the module
boundaries and gives tests a stable surface. Phase 2A adds a local SQLite file at
`.hephaestus/hephaestus.db` so separate CLI invocations can share memory and run
history before any daemon process exists.

## Design Constraints

- Work locally with fake/mock models.
- Route by capabilities and quality threshold, not provider name.
- Treat writes, pushes, publishes, external sends, and destructive commands as
  approval-gated.
- Keep state simple now; introduce SQLite/vector/graph storage later.
- Keep SQLite local and migration-friendly before adding vector or graph storage.
- Make every optimizer return an explanation and a structured decision trace.
- Attach outcomes to decisions before applying any learning behavior.
- Store policy updates as suggestions until reviewed.
- Keep user-owned policy profiles separate from learned decision quality
  profiles: policy profiles define boundaries; learning profiles bias
  optimization decisions.
- Convert learning evidence into explicit decision quality profiles before it
  can influence future decisions.
- Require explicit activation; draft profiles do not silently change behavior.
- Record profile applications so profile influence can be explained later.
- Expose tradeoff frontiers instead of hiding all decisions behind one scalar
  score.
- Make QUBO/Ising-style formulations explicit: variables, objective terms,
  penalties, constraints, selected solution, and baseline comparison.
- Treat quantum-inspired optimization as a formulation style, not a claim of
  quantum hardware acceleration.
- Treat benchmark reports as designed optimizer probes, not real-world AGI
  performance claims.
- Inspect repositories before suggesting real development actions.
- Keep repo intelligence read-only: commands are detected, classified, and
  suggested, not executed.
- Keep release planning honest about evidence: `--evaluate` is simulated, while
  `--with-validation --yes` produces real validation evidence through the safe
  runtime.
- Keep coding-loop work scoped: low-risk docs/tests/config changes can proceed
  with `--yes`; oversized refactors and vague architecture rewrites become
  plans, not automatic edits.
- Keep chat non-mutating: `--propose-code` prints a coding plan and next command
  but does not apply patches.
- Keep conversation text-only in Phase 5A: reason about code, architecture,
  strategy, research, and product decisions without editing files, executing
  commands, browsing, or pretending autonomy exists.
- Keep strategic memory explicit: suggest conversation-derived memories, but
  save them only when the user passes `--save-memory`, `--save-strategy`, or
  uses chat `/save-memory`.
- Keep research planning honest: plan what to verify, but do not claim live
  research or current web facts.
- Keep freedom UX explicit: benign creative, development, research, and strategy
  work is allowed; destructive or external side effects require approval;
  genuinely harmful requests are blocked briefly.
- Keep Studio local-first: bind to `127.0.0.1` by default, avoid wildcard CORS,
  serve protected files only through explicit safe APIs, and show provider and
  policy status without turning the chat UI into an internals dashboard.
- Keep continuity literal: persistent chat history is exact messages,
  chronological reopening, search, and continuation. Automatic summaries,
  daily recaps, and hidden compression are future opt-in features at most, not
  Phase 5.5A behavior.

## Conversation Architecture

Phase 5A adds `conversation_sessions`, `conversation_messages`, and
`conversation_memory_updates`. Phase 5B adds `strategic_memories`,
`strategic_memory_conflicts`, and `strategic_memory_recalls`. Phase 5D adds
`policy_settings`, `policy_custom_profiles`, and `policy_evaluations`. The
package keeps the external UX as one Hephaestus while using lightweight internal
roles:

```text
ContextScout -> MemoryRetriever -> AssumptionMapper -> EvidenceChecker -> SecondOrderThinker -> OptionGenerator -> Critic -> RecommendationSynthesizer
```

These are structured deliberation passes, not external sub-agent swarms. The
pipeline classifies intent, evaluates the active policy profile, retrieves
persistent memories by lexical relevance and intent tags, optionally loads or
creates a repo profile for `--repo`, maps assumptions, considers options,
critiques risks, synthesizes a final response, and proposes memory updates.
Blocked policy requests short-circuit locally. Approval-gated requests remain
discussion-only until Phase 5E adds tool execution.

High-impact intents such as product strategy, business strategy, architecture
discussion, roadmap decisions, idea stress tests, research planning, and risk
analysis create conversation-linked optimization traces. The trace records
assumptions, options, recommendation, confidence, next move, memory used,
strategic memory used, strategic memories suggested, rubric name, and rubric
score so later outcome learning can evaluate discussion quality.

## Studio Architecture

Phase 5.5A adds `apps/studio/` and `src/hephaestus/studio/`. The frontend is a
Next.js App Router static export that calls the local Python API. The backend is
a FastAPI app launched by `heph studio`, mounted on loopback by default, and
able to serve the exported frontend when `apps/studio/out` exists.

The Studio backend reuses existing repositories instead of creating a separate
database:

```text
Next.js Studio
  -> FastAPI /api
  -> StudioService
  -> ConversationService + ConversationRepository
  -> conversation_sessions / conversation_messages
```

SQLite migration 16 adds only missing Studio metadata to
`conversation_sessions`: `display_title`, `is_pinned`, `last_opened_at`, and
`workspace_path`. Studio reuses the existing `archived` and `repo_profile_id`
columns instead of adding duplicates. Message bodies remain in
`conversation_messages`.

The primary Studio API surface is:

```text
/api/health
/api/config
/api/conversations
/api/conversations/{session_id}
/api/conversations/{session_id}/messages
/api/search
/api/modes
/api/policy/active
/api/providers/status
/api/repos/recent
```

Search is deterministic local SQL over titles, user messages, and agent
messages. Posting a message persists the exact user text, calls the existing
conversation orchestrator with the selected mode and optional repo context, and
then returns the exact persisted assistant message. Opening a conversation only
reads stored data; it does not call a model.

## Repo Intelligence Architecture

Phase 4A adds `repo_profiles` and `repo_inspections` tables. Profiles store the
full Pydantic JSON plus summary columns for repo path, repo name, detected
stack, validation plan, generated tasks, risk summary, and inspection time.

The repo flow is:

```text
local repo path
  -> read manifests and config filenames
  -> detect languages, frameworks, package managers, scripts, Docker, and CI
  -> classify commands as safe validation, medium risk, high risk, destructive, or external side effect
  -> generate a ValidationPlan
  -> generate RepoTask records compatible with spec.Task
  -> persist RepoProfile / RepoInspectionReport
  -> optionally export a BenchmarkCase
```

Hephaestus does not jump straight from prompt to action.
It first inspects the repository, builds a project profile, generates repo-aware
tasks, and then lets the decision engine optimize the plan.

## Release Planning Architecture

Phase 4B adds `release_plans` and `src/hephaestus/release/`. Phase 5F links it
to validation execution when requested. The release layer
does not introduce a new optimizer. It composes existing systems:

```text
repo inspect/load profile
  -> generate repo-aware release tasks
  -> convert profile into BenchmarkCase
  -> run optimizer proof with mode=release
  -> optionally persist Pareto frontiers
  -> optionally persist QUBO problems and solutions
  -> persist decision traces
  -> optionally evaluate simulated outcomes and learning signals
  -> optionally run approved validation through the tool runtime
  -> link validation evidence, outcomes, and learning signals
  -> compute deterministic readiness score
  -> persist ReleasePlanningResult
```

`release_plans` stores the release result ID, repo profile ID, goal, linked
optimizer run ID, coarse readiness score, recommendation status/summary, JSON
IDs for Pareto, QUBO, decision traces, outcomes, learning signals, full raw
Pydantic JSON, and creation time.

`src/hephaestus/validation/` owns the execution side:

```text
load or inspect repo profile
  -> build ValidationExecutionPlan from supported repo commands
  -> classify each command with the tool runtime policy
  -> require approval unless --yes
  -> execute with ToolRuntime.run_command
  -> persist ValidationEvidence and ValidationSuiteResult
  -> create outcomes, validation learning signals, and repeated-failure drafts
  -> optionally persist ReleaseValidationSummary
```

SQLite migration 14 adds `validation_plans`, `validation_commands`,
`validation_results`, `validation_evidence`, and
`release_validation_summaries`.

Hephaestus does not run blindly.
It inspects the repository, builds a release plan, exposes tradeoffs, formulates
optimizations, explains decisions, and records learning signals before execution
is ever allowed.

## Decision Trace Architecture

Phase 3A keeps the existing `run_decisions` table for compatibility and adds
`decision_traces` for richer audit records. A trace records:

- `decision_type`: task selection, model routing, context selection, budget,
  safety, or optimization.
- `selected_option` and structured `DecisionAlternative` records.
- `rationale`, typed metrics, confidence, objective score, and constraints
  considered.
- phase, tags, caused-by links, downstream effects, and learning hooks.
- nullable `outcome_id`, `failure_memory_id`, and `policy_update_id` links for
  future learning.
- `parent_id` for reconstructing trace trees.

Builders in `hephaestus.decision.builder` translate scheduler, router, context,
budget, and safety outputs into typed Pydantic records. The CLI reads those
records through `heph explain <run_id>`, `heph explain <run_id> --summary`, and
`heph explain stats`.

Hephaestus does not only optimize decisions. It records why each decision was
made so future versions can learn from outcomes.

## Outcome Learning Architecture

Phase 3B adds `outcomes`, `reflections`, `learning_signals`,
`failure_memory_drafts`, and `policy_update_suggestions` tables. Each outcome
links to a `decision_traces.id`, then updates the trace's nullable
`outcome_id`. Failure drafts and policy suggestions can also link back through
`failure_memory_id` and `policy_update_id`.

The evaluator is deterministic for current benchmark and optimize-style traces:
model routing checks selected quality against the required threshold, context
selection checks critical context preservation and token budget, budget decisions
check quality/token/cost constraints, and safety decisions check approval gates
for risky actions.

Learning signals and policy suggestions are draft artifacts. They are evidence
for future tuning, not automatic self-modification.

## Policy Learning Architecture

Phase 3C adds `decision_quality_profiles` and `profile_applications`. Profiles
are scoped to one decision area: `model_router`, `context_packer`,
`token_firewall`, `scheduler`, `safety`, `memory_retrieval`, or `optimizer`.
Rules are structured Pydantic records with typed adjustments plus human
rationale.

The learner aggregates outcomes, reflections, learning signals, failure memory
drafts, policy suggestions, and decision traces into draft profiles. Activation
is explicit through `heph profile activate <profile_id>`, and archiving is
available through `heph profile archive <profile_id>`.

Active profiles can bias future optimizer inputs:

- model router profiles raise quality thresholds and add prefer/avoid tags,
- context profiles preserve critical context and boost failure memories,
- token firewall profiles make quality preservation stricter,
- scheduler profiles increase dependency and risk penalties,
- safety profiles can require approval for external side effects.

Hephaestus does not silently rewrite itself.
It converts outcomes into inspectable decision quality profiles that can be reviewed, activated, and measured.

## QUBO / Ising Architecture

Phase 3E adds `qubo_problems` and `qubo_solutions` tables. The QUBO repository
stores full Pydantic JSON for exact roundtrips and summary columns for problem
type, run ID, source benchmark/frontier IDs, variable counts, term counts,
constraint counts, solver name, objective value, and feasibility.

The QUBO flow is:

```text
load benchmark fixture
  -> formulate binary variables and objective terms
  -> persist QUBO problem
  -> solve locally with exhaustive, greedy, or annealing solver
  -> persist QUBO solution
  -> compare against baseline and Pareto references
  -> emit phase=qubo optimization traces
```

The Ising converter uses `x = (1 + s) / 2` and exposes spin variables, linear
fields, pair couplings, and constant offset. It is inspectable conversion only;
there is no quantum hardware integration.

## Pareto Architecture

Phase 3D adds `pareto_frontiers`, `pareto_candidates`, and
`pareto_selections` tables. The package keeps a compact JSON roundtrip for full
fidelity while also exposing queryable columns for run ID, candidate type,
preference profile, selected candidate, candidate count, frontier count, and
dominated count.

The Pareto flow is:

```text
generate candidates
  -> score objective vectors
  -> remove invalid candidates unless none are valid
  -> compute non-dominated frontier
  -> rank frontier with a preference profile
  -> persist selection and explain the tradeoff
```

Preference profiles are not learned policies. They are current selection modes
such as `balanced`, `frugal`, and `safety_first`. Active decision quality
profiles from Phase 3C can still affect scoring by raising model risk, boosting
failure-memory context, changing scheduler weights, or increasing safety
importance.

## Benchmark Persistence

The benchmark layer deliberately reuses the generic run history schema. A
benchmark creates a run with `mode=benchmark`, stores scheduled tasks in
`run_tasks`, stores scheduler/router/context/budget/quality decisions in
`run_decisions`, stores richer typed traces in `decision_traces`, and stores
approval-required actions in `approvals`.

This keeps the storage boundary simple while making benchmark runs visible in
the same `heph runs` and `heph run show <id>` views used by optimization demos.
Use `heph explain <id>` for the trace tree and rejection analysis.
Use `heph benchmark run --evaluate` or `heph reflect <id>` to attach simulated
outcomes and learning artifacts to benchmark traces.
Active profiles are used by benchmark runs by default, and explicit profiles can
be supplied with `heph benchmark run --profile <profile_id>`.
With `--pareto`, benchmark runs also persist frontiers and optimization traces
that mention the selected tradeoff candidate.
With `--qubo`, benchmark runs persist QUBO problems and solutions, add
`phase=qubo` optimization traces, and include QUBO summaries in
`heph explain <id>` and `heph explain <id> --summary`.

Release planning reuses the same runner with `mode=release`, so `heph runs`,
`heph run show <id>`, and `heph explain <id>` work without a separate release
run-history schema.
