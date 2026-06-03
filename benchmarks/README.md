# Benchmark Fixtures

Phase 2A only prepares clean task graph fixtures. These JSON files use the same
schema as `examples/repo_release_demo.json`, so they can be exercised with:

```bash
uv run heph optimize benchmarks/task_graphs/simple_release.json
```

Future benchmark phases can add reporting, repeated runs, and scheduler/model
comparison summaries on top of these stable inputs.
