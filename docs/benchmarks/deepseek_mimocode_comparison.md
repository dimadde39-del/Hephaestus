# DeepSeek: Hephaestus and MiMo-Code comparison

Status: protocol `5.6B.5` complete.

This comparison uses the same DeepSeek V4 Flash model in four arms so that
model quality is not confounded with harness quality. MiMo-Code is invoked only
through the preconfigured 0.1.4 wrapper. Hephaestus uses its official bounded
plan, manifest, validation, one-repair, rollback, and retained-snapshot flow.

The canonical reports are:

```text
C:\Temp\hephaestus-harness-gain\reports\summary.md
C:\Temp\hephaestus-harness-gain\reports\results.csv
C:\Temp\hephaestus-harness-gain\reports\results.json
C:\Temp\hephaestus-harness-gain\reports\failures.md
C:\Temp\hephaestus-harness-gain\reports\methodology.md
```

No winning claim belongs in repository documentation until the pilot and main
benchmark are complete and their limitations are stated.

## Main result

On protocol `5.6B.5`, task set `taskforge_greenfield, ttl_cache_bugfix,
csv_export_feature, config_refactor`, model `deepseek-v4-flash`, per-run budget
600 seconds / three calls / 12,288 output tokens / $0.03 / one repair, and
sample size 8 per arm:

| Arm | Mean | Median | Min–max | SD | Exact | Mean hidden-check pass | Cost | Median time |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Bare One-Shot | 52.38 | 51.00 | 10–95 | 34.88 | 0/8 | 58.0% | $0.009136 | 28.29s |
| Bare Two-Stage | 61.12 | 66.00 | 18–94 | 31.27 | 0/8 | 66.3% | $0.012657 | 38.80s |
| Hephaestus | 50.62 | 51.00 | 10–88 | 32.72 | 0/8 | 56.3% | $0.011959 | 40.04s |
| MiMo-Code | 79.88 | 97.50 | 28–100 | 32.29 | 4/8 | 83.8% | $0.051694 | 90.86s |

The 95% Wilson interval for exact pass is 0–32.4% for each zero-pass arm and
21.5–78.5% for MiMo-Code. There were no main-track infrastructure failures.

Verifier-adjusted harness deltas:

- Hephaestus − Bare One-Shot: `-1.75`.
- Hephaestus − Bare Two-Stage: `-10.50`.
- MiMo-Code − Bare Two-Stage: `+18.75`.
- Hephaestus − MiMo-Code: `-29.25`.

## Task-level result

| Task | One-Shot | Two-Stage | Hephaestus | MiMo-Code |
|---|---:|---:|---:|---:|
| TaskForge | 52.5 | 87.5 | 45.5 | 97.5 |
| TTL cache | 51.0 | 51.0 | 51.0 | 100.0 |
| CSV export | 18.0 | 18.0 | 18.0 | 28.0 |
| Config refactor | 88.0 | 88.0 | 88.0 | 94.0 |

MiMo-Code was strongest on TTL cache (2/2 exact), and achieved one exact pass
each on TaskForge and config refactor. It was not exact on CSV export. MiMo used
2,638,278 total input/output tokens and 107 observed calls; its pre-enforced
call/token parity is therefore explicitly marked as a protocol mismatch.

Hephaestus used 55,022 total input/output tokens, 16 calls, and one repair call.
The repair did not produce an exact pass. Hephaestus had zero false successes,
while false-success rates were 37.5% for one-shot, 25% for two-stage, and 50%
for MiMo-Code. In this task set, verification improved honesty but did not
improve Hephaestus's verifier-adjusted implementation score.

The global live spend, including four preserved invalid pilots and one
preserved incomplete main run, was `$0.177201`; the final main track cost was
`$0.085446`.

These results do not support a universal product ranking. They show that on
this small deterministic task set, with this model and budget, MiMo-Code
substantially outperformed the other arms but used much more context, calls,
cost, and time. The sample is too small to generalize beyond the frozen tasks.
