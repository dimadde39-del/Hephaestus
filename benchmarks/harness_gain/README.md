# DeepSeek harness-gain benchmark

Protocol `5.6B.1` compares the same `deepseek-v4-flash` model in four modes:
bare one-shot, bare plan→implementation, MiMo-Code 0.1.4, and Hephaestus.

Live state is deliberately outside git at
`C:\Temp\hephaestus-harness-gain`. No live provider call is made by pytest.

```powershell
uv run python -m benchmarks.harness_gain.orchestrator prepare
uv run python -m benchmarks.harness_gain.orchestrator pilot
uv run python -m benchmarks.harness_gain.orchestrator main
uv run python -m benchmarks.harness_gain.orchestrator report
```

The pilot must produce `reports\pilot-validation.json` with `passed: true`
before the main command runs. Existing run directories are never overwritten.

See [protocol.md](protocol.md) and
[the public protocol documentation](../../docs/benchmarks/harness_gain_protocol.md).

