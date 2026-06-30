# Phase 5.6B: Harness Gain

Phase 5.6B adds a reproducible, same-model comparison of raw DeepSeek,
plan→implementation prompting, MiMo-Code, and Hephaestus. The protocol is
versioned, seeded, artifact-complete, hidden-validator-backed, and budgeted.

The important learning boundary is epistemic: self-tests are evidence, not the
success label. Exact pass and verifier-adjusted score come from deterministic
hidden validation. Provider, transport, permission, timeout, and harness
failures remain visible but are not silently converted into poor coding scores.

Live targets, sessions, failed snapshots, and reports are stored outside git at
`C:\Temp\hephaestus-harness-gain`. Participant outputs are immutable after each
run.

## Outcome

Protocol `5.6B.5` completed 32 main runs after preserving invalid earlier
protocol attempts. Mean verifier-adjusted scores were 52.38 one-shot, 61.12
two-stage, 50.62 Hephaestus, and 79.88 MiMo-Code. Exact passes were 0/8, 0/8,
0/8, and 4/8 respectively.

The result falsified the hoped-for Hephaestus gain on this task set:
`HG_one_shot=-1.75`, `HG_two_stage=-10.50`, and
`Competitive_gap=-29.25`. Hephaestus did show the lowest false-success rate
(0%) because deterministic validation and rollback prevented it from claiming
success after failed work.

MiMo-Code's advantage was expensive: 2.64M input/output tokens, 107 observed
calls, $0.0517, and 90.86s median versus Hephaestus's 55k tokens, 16 calls,
$0.0120, and 40.04s median. MiMo's call/token budget parity was not
pre-enforceable and remains a protocol mismatch.

The main implementation lesson is that validation alone cannot rescue frequent
structured-output failures. Hephaestus needs a stronger bounded contract path
before another quality benchmark, but these benchmark outputs must remain
unchanged.
