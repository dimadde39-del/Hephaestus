# Hephaestus Phase 2B Benchmarks

Phase 2B adds an executable benchmark layer for optimizer proof reports.

## What Changed

- Added `hephaestus.benchmarks` with typed benchmark cases, result summaries,
  fixture loading, runner logic, Rich reporting, and JSON output.
- Added `heph benchmark list`, `heph benchmark show`, and `heph benchmark run`.
- Expanded `benchmarks/task_graphs/` to seven designed fixtures.
- Persisted benchmark runs using the existing SQLite run history with
  `mode=benchmark`.
- Added docs for benchmark intent, fixture coverage, persistence, and
  limitations.

## Principle

The benchmark suite is designed to test optimizer behavior, not to claim
real-world AGI performance.

The suite supports the core claim that Hephaestus does not blindly minimize
cost. It preserves quality thresholds first, then optimizes task order, context,
model choice, risk, and token usage.

## Known Limits

- Fixtures are deterministic and local.
- No paid model API is required.
- No dashboard, daemon, voice, Telegram, browser automation, or skill
  self-growth is included in this phase.
