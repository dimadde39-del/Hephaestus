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

