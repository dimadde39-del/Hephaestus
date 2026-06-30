# Roadmap

Phase 5.6A.1 adds a bounded generalized greenfield coding loop using structured
provider plans and operation manifests. Live model-quality benchmarking remains
open; this phase does not claim Claude Code parity.

Phase 5.6A.1.2 hardens that loop with deterministic validation normalization,
staged manifest validation, one bounded validation-coupled repair call, scoped
rollback cleanup, and opt-in failed-workspace snapshots for benchmark/debug
review.

Hephaestus is a model-agnostic intelligence harness. A model provides raw
intellectual potential; Hephaestus turns it into checked work through context,
planning, tools, validation, repair, outcome evidence, and learning. The public
alpha goal is not to look autonomous before the core is ready. It is to make the
working loop understandable:

```text
context -> planning -> tools -> validation -> repair -> outcome evidence -> learning
```

Optimization, decision traces, Pareto, and QUBO remain part of the technical
spine, but they are not the public headline.

The main benchmark is:

```text
same model without Hephaestus vs same model with Hephaestus
```

Hephaestus should not claim that weak models always beat strong models. The
claim to measure is narrower: on bounded tasks, a strong harness can sometimes
let a weaker model outperform a stronger model without comparable
context/tool/verification support.

Deep learning and governance details live in:

- [Learning stack](learning_stack.md)
- [Experience governance](experience_governance.md)
- [Verifier and reward model](verifier_and_reward_model.md)
- [Personal, project, and global learning](personal_project_global_learning.md)
- [Model adaptation lab](model_adaptation_lab.md)

## Current Sequence

- Phase 5.5A: Studio Foundation + Persistent Chat.
- Phase 5.5B: Agent Workbench.
- Phase 5.5C: Advanced Views + Packaging + Polish.
- Phase 5.6A.0: DeepSeek V4 Flash First Live Smoke.
- Phase 5.6: Coding Quality and Harness Benchmark Program.
- Phase 6A: Context Forge.
- Phase 6B: Experience Ledger and Governance.
- Phase 6C: Cognitive Strategy Engine and User-Controlled Capabilities.
- Phase 6D: Personal, Project and Cross-Project Intelligence.
- Phase 6E: Adaptive Policy Learning on CPU.
- Phase 6F: Skill and Capability Distillation.
- Phase 6G: Reward and Model Adaptation Lab.
- Phase 6H: SWE-RL and Self-Play.
- Phase 6I: Community and Global Learning.
- Phase 7: Always-On Runtime / VPS / Telegram / async work.

Phase 5.5 is mandatory before Phase 5.6. Phase 5.5A establishes the persistent
chat product surface first; Phase 5.5B adds coding-loop, validation, approval,
checkpoint, outcome, and tool-action workbench views; Phase 5.5C completes the
local Studio surface with memory, settings, advanced views, onboarding,
backup/export, and packaging polish.

Phase 5.6A.0 adds a narrow, budgeted DeepSeek V4 Flash path before any parity
program claims: configurable thinking, transient reasoning handling, real
connectivity tests, isolated conversation/repo/coding smoke cases, usage
telemetry, and strict `--live`/call/output/cost guards. It does not establish
Claude Code parity or native autonomous tool calling.

## Complete

### Foundation

- Python 3.12 package managed with `uv`.
- Pydantic v2 schemas.
- Typer/Rich CLI.
- Deterministic spec pipeline.
- Task graph generation and optimizer-compatible tasks.
- Memory store and model provider interface.
- Fake local models and optional DeepSeek provider.
- Safety and tool schemas.

### Persistence

- SQLite database initialization and migrations.
- Persistent memories.
- Run history, run tasks, decisions, and approvals.
- Local state in `.hephaestus/hephaestus.db`.

### Benchmark Reports

- Benchmark fixtures for designed optimizer pressure cases.
- Greedy and simulated annealing comparisons.
- Model routing, context packing, token budget, and approval-gate reporting.
- Persisted benchmark runs.

### Decision Traces

- First-class decision trace records.
- Trace rendering through `heph explain <run_id>`.
- Aggregate explanation stats.
- Structured selected/rejected alternatives, metrics, confidence, and rationale.

### Outcome Learning

- Outcome records linked to decision traces.
- Deterministic reflections.
- Learning signals.
- Failure memory drafts.
- Policy update suggestions kept as reviewable artifacts.

### Decision Quality Profiles

- Decision quality profile suggestions.
- Explicit activation and archive commands.
- Profile application records.
- Active profiles can bias future model routing, context packing, token
  firewall, scheduler, and safety behavior.

### Pareto Frontier

- Multi-objective candidates for model routing, context packing, and scheduler
  choices.
- Built-in preference profiles such as `balanced`, `frugal`, `quality_first`,
  `privacy_first`, `safety_first`, and `speed_first`.
- Persisted frontiers and selections.
- CLI list/show/compare commands.

### QUBO and Ising

- QUBO schemas for variables, terms, constraints, objectives, problems, and
  solutions.
- Context packing, model selection, budget strategy, and task-ordering demo
  formulations.
- Local exhaustive, greedy, and seeded annealing solvers.
- QUBO to Ising conversion.
- CLI formulation, solve, list, show, compare, and convert commands.

### Repo Intelligence

- Read-only local repository inspection.
- Detection for Python, Node/TypeScript/JavaScript, Rust, Go, Docker, GitHub
  Actions, and GitLab CI signals.
- Package manager, script, validation command, env-file, and risk signals.
- Safe command classification.
- Repo-aware release-readiness task generation.
- Benchmark export from real repo profiles.

### Release Planning Demo

- `heph release plan/list/show`.
- End-to-end local demo:

```text
Repo Inspect -> Repo Plan -> Optimize -> Pareto -> QUBO -> Explain -> Evaluate -> Learn
```

- Release plans link repo profiles, optimizer runs, decision traces, Pareto
  frontiers, QUBO problems, simulated outcomes, and learning signals.
- Execution remains deferred: validation, deploy, publish, destructive, and
  external side-effect commands are not run.

### Public Alpha Readiness Polish

- README hero rewritten around a 30-second public explanation.
- Demo-first quickstart and walkthrough.
- Contributor guide and issue templates.
- Public roadmap cleanup.
- Brand and mascot direction.
- Soft reveal launch copy drafts.
- GitHub metadata suggestions.

### Phase 4D: Soft Reveal Pack

- Polished screenshots of the current CLI demo.
- Demo screenshot pack linked from README and walkthrough docs.
- One-minute demo script.
- Terminal recording plan.
- Final first posts for X/Twitter, Reddit, Telegram/Discord, and GitHub
  Discussions.
- Reveal strategy notes and launch checklist.
- GitHub setup guidance tied to the actual brand and demo assets.

### Phase 5A: Conversational Agent Interface

- `heph ask`, `heph discuss`, and `heph chat`.
- Persisted conversation sessions, messages, and memory update suggestions.
- Intent classification for repo questions, architecture, product strategy,
  business strategy, stress tests, roadmap decisions, research planning, risk,
  personal context, and debugging discussions.
- Deliberation modes: balanced, direct, critical, strategic, research,
  architect, coach, and skeptical-but-fair.
- Internal deliberation passes without multi-process agent swarms.
- Memory retrieval and conservative memory update suggestions.
- Optional repo context through `--repo` using read-only repo profiles.
- High-impact discussion traces linked to the decision engine.
- Fake/local deterministic mode when no real provider is configured.

### Phase 5B: Strategic Memory + Research/Discussion Quality Framework

- Strategic memory package for goals, ambitions, constraints, fears, risk
  patterns, preferences, principles, strategic decisions, roadmap decisions,
  positioning decisions, launch decisions, business assumptions, technical
  assumptions, rejected paths, lessons learned, and open questions.
- SQLite persistence for strategic memories, simple conflicts, and recall
  events.
- `heph strategy memory add/list/search/show/archive` and `heph strategy context`.
- Conversation recall of strategic memory for strategy, architecture, research,
  roadmap, and risk discussions.
- Save-controlled strategic memory suggestions through `--save-memory`,
  `--save-strategy`, and chat `/save-memory`.
- Discussion-quality rubrics for idea stress tests, business strategy, product
  strategy, technical architecture, roadmap decisions, research planning, and
  risk analysis.
- Research planning mode that prepares verification without pretending live web
  research has happened.
- High-impact traces enriched with assumptions, options, recommendation,
  confidence, memory used, strategic memories suggested, and rubric metadata.

### Phase 5C: Real Model Provider Conversation Quality

- Conversation provider routing across deterministic local mode, DeepSeek, and
  OpenAI-compatible APIs.
- OpenRouter-compatible usage through the OpenAI-compatible path.
- Conversation model profile metadata for JSON, streaming, context windows,
  cost estimates, and intended roles.
- Prompt assembly with behavior/policy standards, mode guidance, rubrics,
  strategic memory, repo context, session context, regular memory, and explicit
  fact/assumption/recommendation separation.
- One-call model-backed final synthesis when real providers are configured and
  selected.
- Token/context budget reports and deterministic context trimming.
- Conversation quality benchmark fixtures and deterministic evaluator package.
- `heph conversation benchmark list/run`.
- Improved memory candidate summaries and stability labels.

### Phase 5D: User-Owned Freedom / Policy Profiles

- First-class `hephaestus.policy` package with schemas, built-in profiles,
  deterministic classifier/evaluator, repository, renderer, and analysis
  helpers.
- Built-in profiles: `balanced`, `developer`, `research`, `local_power_user`,
  `strict`, and schema support for `custom`.
- SQLite active policy profile state, custom profile storage, and transparent
  policy evaluation history.
- `heph policy profiles/active/set/show/evaluate`.
- `heph policy benchmark list/run`.
- Conversation prompt integration with active profile name, decision, refusal
  style, benign-work philosophy, and over-refusal detection.
- Concise blocking for genuinely harmful requests and approval boundaries for
  destructive/local/external side effects.
- Documentation for user-owned freedom and policy profiles.

### Phase 5E: Safe Tool Execution Runtime

- First-class `hephaestus.tool_runtime` package with schemas, classifier,
  approvals, filesystem tools, shell runtime, patch proposals, checkpoints,
  SQLite repository, renderers, and analysis helpers.
- SQLite tool tables for actions, approvals, results, observations, and
  checkpoints.
- `heph tools list/read/search/run`, `heph tools patch propose/apply`,
  `heph tools actions`, `heph tools action show`, and
  `heph tools checkpoint list/show/restore`.
- Protected file detection for `.env`, credential, token, private-key, and SSH
  key material.
- Dry-run command planning, risk classification, approval gates, stdout/stderr
  capture, timeouts, output truncation, and observations.
- Checkpoint creation before patch application and restore for files changed by
  Hephaestus.
- Policy-profile-aware execution decisions and reuse of repo command risk
  classification.
- Minimal decision trace and outcome links for important tool actions.
- `--propose-tools` on `heph ask` and `heph discuss` for manual next-step plans
  without chat auto-execution.

### Phase 5F: Real Validation Execution + Outcome Learning

- First-class `hephaestus.validation` package with schemas, planner, executor,
  evaluator, repository, renderer, and analysis helpers.
- SQLite tables for validation plans, commands, suite results, evidence, and
  release validation summaries.
- `heph validate plan/run/results/show/latest`.
- Repo-derived validation command detection for lint, test, typecheck, build,
  format-check, security-check, and custom validation commands.
- Approved execution through the Phase 5E safe tool runtime with stdout/stderr
  summaries, exit codes, durations, timeouts, and approval-required states.
- Per-command validation outcomes, validation strategy learning signals, and
  repeated-failure memory drafts.
- Release planning integration through `heph release plan . --with-validation --yes`.
- Evidence mode labels for simulated outcome evaluation, real validation
  evidence, dry-run, and approval-gated execution.
- Conversation tool proposals now suggest `heph validate plan`, dry-run, and
  approved validation commands without auto-running them.

### Phase 5G: Repo-Aware Coding Loop

- First-class `hephaestus.coding_loop` package with schemas, planner, patcher,
  reviewer, executor, repository, renderers, and analysis helpers.
- SQLite tables for coding requests, plans, changes, iterations, and results.
- `heph code plan/propose/apply/run/results/show`.
- Repo-aware planning over repo intelligence, validation plans, active policy
  profile, and strategic memory recall.
- Deterministic single-file patch proposals for small docs/tests/config/help
  text and exact replacement workflows.
- Lightweight patch review for request match, expected files, protected files,
  scope drift, obvious secrets, and validation availability.
- Approved patch application through the safe tool runtime with checkpoint
  creation.
- Validation through Phase 5F after apply, with validation result links.
- Optional checkpoint restore with `--rollback-on-failure`.
- Coding-loop decision traces, outcomes, and learning signals for scope blocks,
  patch proposals, apply decisions, validation, rollback, and final result.
- `--propose-code` on `heph ask`, `heph discuss`, and `heph chat`; chat also
  supports `/propose-code <request>`.
- Still bounded: no daemon, no deploy/publish/push, no destructive actions, no
  dependency installs without explicit approval, and no unbounded repair loop.

### Phase 5G.5: README Reality / Product Positioning Pass

- Public README repositioned around self-improving agent value: memory,
  thinking, coding, validation, outcomes, and project continuity.
- What works today and what is not built yet are stated near the top.
- Practical commands and the current coding/validation loop are shown before
  advanced engine internals.
- QUBO, Pareto, decision traces, policy profiles, strategic memory, and model
  routing are described as advanced machinery, not the primary pitch.
- Public launch notes, reveal strategy, demo script, brand docs, freedom/policy
  docs, and GitHub-facing setup notes align around the same message.
- Product positioning and README reality checklist docs capture the new rules.

### Phase 5.5A: Studio Foundation + Persistent Chat

- Local `heph studio` launcher with loopback default binding, browser opening,
  port/host options, and `heph studio doctor`.
- FastAPI Studio backend under `src/hephaestus/studio/` with typed endpoints
  for health, config, conversations, messages, search, modes, active policy,
  provider status, and recent repos.
- Next.js Studio app under `apps/studio/` with a polished persistent chat
  layout: conversation sidebar, timeline, composer, search panel, and context
  drawer.
- Existing CLI conversations appear in Studio, and Studio-created sessions
  remain readable through existing CLI conversation commands.
- Exact-message continuity: reopen a conversation, read the original
  chronological timeline, and continue without automatic summaries or recaps.
- Conversation metadata for deterministic titles, manual rename, pin/archive,
  last opened time, optional workspace path, and optional repo profile.
- Local SQL search across conversation titles, user messages, and agent
  messages, with archived conversations behind an explicit filter.
- Mode, repo, active policy, and provider state are visible without leading the
  UI with internals.
- Screenshots and Studio documentation added under `docs/assets/studio/` and
  `docs/studio*.md`.

### Phase 5.5B: Hephaestus Agent Workbench

- Studio main navigation now has Chat and Workbench, with Chat still the
  default startup route.
- Workbench overview shows active coding work, recent completed work, recent
  validation, failed validation requiring attention, meaningful pending
  decisions, recent checkpoints, and latest release evidence.
- Coding request list/detail views expose request context, repo, scope, risk,
  status, files touched, validation result, checkpoint state, linked
  conversation, plans, patches, and result.
- Diff viewer supports changed file lists, unified diff rendering, additions
  and deletions, line numbers, file collapse, copy patch, large-diff indicators,
  proposed/applied state, and protected-file warnings.
- Validation list/detail views show real commands, statuses, exit codes,
  durations, evidence, output summaries, and collapsed stdout/stderr.
- Checkpoint list/detail views show covered files, hashes, validation links,
  restore history, and one-confirmation restore through the Python runtime.
- Tool action timeline translates internal actions into user-readable events.
- Local trust settings persist Studio autonomy mode and map to existing policy
  profiles and implemented runtime behavior.
- Pending decisions are limited to meaningful approvals such as patch apply,
  validation retry, and checkpoint restore.
- Release evidence and outcomes are shown in practical language, with advanced
  optimization details collapsed by default.
- Compact chat artifact cards link conversations to Workbench without replacing
  exact message history.

### Phase 5.5C: Studio Advanced Views + Packaging + Polish

- Main Studio navigation is complete: Chat, Workbench, Memory, Settings, with
  Advanced as deliberate secondary access.
- Memory area manages regular and strategic memories with search, type/scope
  filters, repo filters, archive state, detail editing, evidence, links,
  conflict warnings, archive/restore/delete, and suggestion review.
- Settings covers General, Appearance, Models, Policy and Trust, Data, and
  Advanced local details.
- Provider/model settings support local deterministic, DeepSeek, and
  OpenAI-compatible providers, including OpenRouter-compatible base URLs,
  connectivity tests, role metadata, context windows, and cost metadata.
- Secrets remain local and are redacted from normal API responses and exports.
- Usage/economy view shows model calls, deterministic operations, estimated
  tokens/cost, context trimming, provider usage, and no-model operations.
- Advanced views expose structured decision traces, Pareto frontiers, and QUBO
  formulations without private chain-of-thought or raw JSON by default.
- First-run onboarding is short and skippable.
- Data management supports conversation export, memory export, full database
  backup, compatible restore, and incompatible-schema rejection.
- Package build includes static frontend assets when `apps/studio/out` exists;
  doctor commands report missing assets with guidance.
- Public-alpha checklist, screenshots, and focused accessibility/performance
  notes are documented.

## Upcoming

### Phase 5.6: Coding Quality And Harness Benchmark Program

Phase 5.6 remains the coding-quality and harness benchmark program. It should
establish reproducible evidence before making parity or superiority claims.

Required controls:

- same model.
- same repo snapshot.
- same task.
- same budget.
- hidden validation.
- multiple runs.
- median results.

Harness Gain Evaluation compares:

```text
same model raw
vs
same model with Hephaestus
```

Metrics:

- successful completion.
- hidden tests.
- regressions.
- recovery after failure.
- human intervention.
- latency.
- tokens and cost per successful task.
- unnecessary files and LOC.
- scope violations.
- verifier confidence.

Hephaestus must not publicly claim Claude Code parity, general model
superiority, or "weak model always beats strong model" until benchmark evidence
supports the specific claim.

### Phase 6A: Context Forge

- Build better context selection across repo state, conversations, strategic
  memory, validation history, and outcome evidence.
- Explain why context was included or excluded.
- Keep context permission separate from training permission.

### Phase 6B: Experience Ledger And Governance

- Introduce governed experience records with provenance, permission records,
  validation confidence, deduplication, staleness, contamination, retention,
  deletion, dataset versioning, and rollback.
- Track dataset states: `clean`, `suspect`, `contaminated`, `rejected`, and
  `expired`.
- Keep failed and unknown outcomes as evidence, not silent positives.

### Phase 6C: Cognitive Strategy Engine And User-Controlled Capabilities

- Turn repeated strategies into reviewable capabilities with explicit approval,
  quarantine, and monitoring.
- Ask clarifying questions only when expected value of information is greater
  than interruption cost.
- Keep strategy changes reversible and visible.

### Phase 6D: Personal, Project And Cross-Project Intelligence

- Separate project intelligence, personal intelligence, and global intelligence.
- Transfer abstractions across projects without transferring confidential
  details.
- Keep global/community learning explicit opt-in.

### Phase 6E: Adaptive Policy Learning On CPU

- Train controller-layer policies on CPU: contextual bandits, small rankers,
  classifiers, strategy routers, model selectors, tool selectors, validation
  planners, uncertainty estimators, and cost/risk models.
- Improve the harness/controller layer, not base LLM weights.

### Phase 6F: Skill And Capability Distillation

- Distill repeated validated work into reusable skills and generated
  capabilities.
- Apply the lifecycle: need detected, candidate, quarantine, offline A/B
  benchmark, regression tests, shadow mode, canary, approval, active, monitor,
  restrict/update/deprecate/delete.

### Phase 6G: Reward And Model Adaptation Lab

- Research reward models for subjective estimates such as architecture quality,
  scope-drift risk, strategy utility, and likely future success.
- Research SFT, LoRA, QLoRA, DPO, distillation, and personal/project/task
  adapters.
- Train adapters only from governed, permissioned, validated datasets.

### Phase 6H: SWE-RL And Self-Play

- Explore software-engineering reinforcement learning and self-play only behind
  deterministic verifier, holdout, governance, and promotion gates.
- Prevent reward hacking: no benchmark mutation, no test deletion, no weakened
  assertions, no permission bypass, and no audit-log rewriting.

### Phase 6I: Community And Global Learning

- Explore anonymized aggregate evidence, generic skills, shared model
  capability profiles, and validation heuristics.
- Require explicit opt-in for community/global learning.
- Move abstractions, not private code, personal facts, or confidential project
  details.

### Phase 7: Always-On Runtime / VPS / Telegram / Async Work

- Introduce long-running or remote execution only after Studio, memory UX,
  governance, skills, evaluation, quarantine, and capability lifecycle controls
  exist.
- Explore VPS, Telegram, async work queues, and background tasks with explicit
  user controls.
- Do not make always-on autonomy the public promise before it has trustworthy
  visibility and approval surfaces.

### Phase 7: Always-On Runtime / VPS / Telegram / Async Work

- Introduce long-running or remote execution only after Studio, memory UX,
  skills, evaluation, quarantine, and capability governance exist.
- Explore VPS, Telegram, async work queues, and background tasks with explicit
  user controls.
- Do not make always-on autonomy the public promise before it has trustworthy
  visibility and approval surfaces.

### Soft Reveal Execution

- Post the first X/Twitter soft reveal.
- Prepare one Reddit feedback post.
- Prepare one or two Telegram/Discord community messages.
- Observe responses and repeated objections.
- Gather feedback into roadmap notes before the larger public alpha push.

### Voice Much Later

- Voice/Jarvis-style features are intentionally deferred until the decision
  core, execution safety, and learning loop are mature.

## Deferred On Purpose

- Fully autonomous code editing.
- Always-on daemon behavior.
- Browser or desktop automation.
- Telegram bot integrations.
- Random integrations that do not improve decision quality.

The current priority is clear: persistent interface, readable history,
validation-backed coding loops, evidence, memory, and careful improvement.
