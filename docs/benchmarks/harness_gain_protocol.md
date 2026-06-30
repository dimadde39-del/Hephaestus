# Harness Gain Protocol

Phase 5.6B protocol `5.6B.3` measures the contribution of a coding harness while
holding the provider and model fixed: DeepSeek `deepseek-v4-flash` at
`https://api.deepseek.com`.

The four arms are direct one-shot, direct two-stage plan→implementation,
MiMo-Code 0.1.4, and the official Hephaestus coding flow. Four deterministic
Python 3.12 stdlib tasks are used, with two main repetitions and a mandatory
four-run pilot. Run ordering is randomized with seed `56062026`.

Scoring, budgets, failure taxonomy, isolation rules, and exact commands are
frozen in [the executable protocol](../../benchmarks/harness_gain/protocol.md).
Live outputs live under `C:\Temp\hephaestus-harness-gain` and are not committed.

The protocol supports a bounded statement of the form:

> On protocol 5.6B.3, this task set, this model, this budget, and this sample
> size, the observed score difference was X.

It does not support a universal claim that one harness is always better.
