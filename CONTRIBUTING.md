# Contributing To Hephaestus

Thanks for taking a look. Hephaestus is early, so the most valuable
contributions are the ones that make the core decision loop clearer, safer, and
more testable.

## Setup

```bash
git clone https://github.com/dimadde39-del/Hephaestus.git hephaestus
cd hephaestus
uv sync --extra dev
uv run heph doctor
```

## Validation

Run these before opening a pull request:

```bash
uv run ruff check .
uv run pytest
uv run mypy
uv run heph --help
uv run heph doctor
uv run heph release plan . --pareto --qubo --evaluate
```

For docs-only changes, still run at least `uv run ruff check .`,
`uv run pytest`, and the release planning demo if the docs mention CLI output.

## Project Philosophy

Hephaestus is not trying to look autonomous before it can reason well. The core
principle is:

```text
Inspect -> Plan -> Optimize -> Explain -> Evaluate -> Learn -> Execute safely later
```

Good contributions usually improve one of these areas:

- Core decision quality.
- Repo-aware planning.
- Explainable decision traces.
- Learning memory and reviewable policy profiles.
- Pareto and QUBO transparency.
- Safety foundations for future execution.
- Documentation that makes the demo easier to understand.

## What Not To Build Yet

Please do not add these as drive-by features:

- Voice or Jarvis-style interfaces.
- Telegram, Discord, Slack, or other chat integrations.
- Dashboards.
- Browser or desktop automation.
- Autonomous editing.
- Random provider or SaaS integrations.
- Production command execution.

Those may matter later, but the current priority is decision quality and safe
planning. Integrations should wait until they have a clear role in the decision
loop.

## Pull Request Shape

- Keep changes scoped.
- Add or update tests when behavior changes.
- Prefer typed schemas and explicit persistence over ad hoc dictionaries.
- Keep CLI output honest about what is real, simulated, or deferred.
- Do not claim production autonomy, quantum speedups, or executed validation
  unless the code actually does it.

## Useful Docs

- [README](README.md)
- [Architecture](docs/architecture.md)
- [Roadmap](docs/roadmap.md)
- [Learning stack](docs/learning_stack.md)
- [Experience governance](docs/experience_governance.md)
- [Verifier and reward model](docs/verifier_and_reward_model.md)
- [Personal, project, and global learning](docs/personal_project_global_learning.md)
- [Model adaptation lab](docs/model_adaptation_lab.md)
- [Contributor guide](docs/contributor_guide.md)
- [Release planning demo](examples/release_plan_demo.md)
