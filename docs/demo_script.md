# 60-90 Second Demo Script

This is the exact soft reveal demo path. It is meant to feel calm, concrete,
and honest: early, real, and intentionally planning-only.

## 1. What Hephaestus Is

Say:

```text
Hephaestus is an optimization-first agent OS. The current alpha does not edit
code or execute repo commands. It inspects a repo, plans before acting, exposes
tradeoffs, explains decisions, and records learning signals from simulated
outcomes.
```

Show the README hero or first terminal frame.

Time: 8-10 seconds.

## 2. Repo Inspection

Run:

```bash
uv run heph repo inspect .
```

Say:

```text
First it reads the repository locally. It detects stack signals, validation
commands, risk signals, and repo-aware tasks. This is read-only inspection.
```

Point at:

- detected package manager,
- validation commands,
- risk signals,
- generated repo tasks.

Time: 10-12 seconds.

## 3. Release Plan

Run:

```bash
uv run heph release plan . --pareto --qubo --evaluate
```

Say:

```text
This is the main demo. Hephaestus turns repo signals into a release-readiness
plan, runs the optimizer, compares Pareto tradeoffs, formulates QUBO problems,
saves decision traces, simulates outcomes, and creates learning signals.
```

Point at:

- release plan ID,
- optimizer run ID,
- readiness score,
- `needs_validation`,
- linked artifacts.

Time: 25-30 seconds.

## 4. Pareto Tradeoffs

Use the first frontier ID from the release output.

Run:

```bash
uv run heph pareto show <frontier_id>
```

Optional standalone comparison:

```bash
uv run heph pareto compare examples/repo_release_demo.json
```

Say:

```text
The system does not hide everything behind one score. Pareto frontiers expose
what was selected, what was dominated, and what tradeoffs were accepted.
```

Time: 8-10 seconds.

## 5. QUBO Formulation

Use the first QUBO problem ID from the release output.

Run:

```bash
uv run heph qubo show <problem_id>
```

Say:

```text
Some decision surfaces are also encoded as QUBO problems. This is local
classical solving, not a quantum hardware claim. The point is inspectable binary
optimization: variables, objective terms, constraints, and the selected
assignment.
```

Time: 8-10 seconds.

## 6. Explainability

Use the optimizer run ID from the release output.

Run:

```bash
uv run heph explain <optimizer_run_id> --summary
```

Say:

```text
Every important decision gets a trace: selected option, rejected alternatives,
constraints, confidence, and rationale. The summary is short for the demo; the
full trace is available with the same command without `--summary`.
```

Time: 8-10 seconds.

## 7. Learning Signals

Use the optimizer run ID from the release output.

Run:

```bash
uv run heph learn signals --run <optimizer_run_id>
```

Say:

```text
Because this alpha does not execute commands yet, outcomes are deterministic
simulations over decision traces. The useful part is the shape of the loop:
decisions create outcomes, outcomes create reviewable learning signals.
```

Time: 8-10 seconds.

## 8. Honest Close

Say:

```text
What works today is repo inspection, planning, optimization, Pareto/QUBO
inspection, explanations, persistence, and simulated learning signals. What is
not built yet is autonomous editing, command execution, dashboard, daemon, or
voice. The next serious step is safe validation execution.
```

Time: 8-10 seconds.

## Do Not Claim

- Do not claim Hephaestus autonomously edits code.
- Do not claim tests or builds passed unless you ran them separately.
- Do not claim production autonomy.
- Do not imply QUBO means quantum hardware or quantum speedups.
- Do not mention voice, Jarvis, Telegram, dashboard, daemon, or browser
  automation as near-term reveal features.

## Suggested Sequence

```text
README hero
repo inspect
release plan
pareto show or compare
qubo show
explain --summary
learn signals
limitations and next step
```
