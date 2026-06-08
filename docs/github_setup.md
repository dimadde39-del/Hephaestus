# GitHub Setup Suggestions

These suggestions are for the public alpha soft reveal.

## Repository Description

Use this in the GitHub About box:

```text
Optimization-first agent OS with explainable decisions, repo-aware planning, Pareto/QUBO tradeoffs, and learning memory.
```

## Website / Links

If there is no project website yet, leave the website field empty or point it to
the GitHub repository. Do not link to a placeholder landing page.

Useful links to feature in README or Discussions:

- [release plan walkthrough](../examples/release_plan_demo.md)
- [demo script](demo_script.md)
- [demo screenshot pack](assets/demo/README.md)
- [roadmap](roadmap.md)
- [contributor guide](contributor_guide.md)

## Topics

Use 10-15 focused topics:

```text
ai-agent
agentic-ai
llm
developer-tools
optimization
pareto
qubo
ising
explainable-ai
decision-traces
ai-coding
python
cli
open-source
```

## Social Preview

Upload:

```text
docs/assets/brand/hephaestus-social-preview.png
```

Reminder: GitHub caches social previews. After upload, check the preview in an
incognito browser or wait a few minutes before judging the result.

## README Images To Highlight

Primary:

```text
docs/assets/brand/hephaestus-readme-hero.png
docs/assets/demo/release-plan-demo.png
```

Secondary, for docs or posts:

```text
docs/assets/demo/repo-inspect-demo.png
docs/assets/demo/pareto-demo.png
docs/assets/demo/qubo-demo.png
docs/assets/demo/explain-demo.png
```

Keep the README to 1-2 images. Use the rest in the walkthrough and social
updates.

## Pinned Demo Command

Use the release planning demo in the README and repository profile:

```bash
uv run heph release plan . --pareto --qubo --evaluate
```

Suggested pinned copy:

```text
Run the local planning demo: inspect a repo, generate release tasks, compare Pareto tradeoffs, formulate QUBO problems, explain decisions, and create learning signals.
```

## Discussions

Enable GitHub Discussions if you want a low-friction place to collect early
architecture feedback.

Suggested first Discussion:

```text
Soft reveal: Hephaestus public alpha direction
```

Use the draft in [docs/public_launch_notes.md](public_launch_notes.md). Pin it
while the soft reveal is active.

## What To Pin Or Feature

Feature these in order:

1. README demo command.
2. Release planning screenshot.
3. Public alpha roadmap.
4. GitHub Discussion feedback thread, if enabled.

Avoid pinning speculative feature mockups. The public reveal should lead with
the working CLI.

## Suggested First Release Tag

If tagging the soft reveal:

```text
v0.1.0-soft-reveal
```

Alternative later tags:

- `v0.2.0-safe-validation-alpha`
- `v0.3.0-real-outcome-learning`
- `v0.4.0-deliberation-modes`

Avoid tag names that imply production autonomy before safe execution exists.

## Repository Settings Checklist

- [ ] About description set.
- [ ] Topics set.
- [ ] Social preview uploaded.
- [ ] README image links checked.
- [ ] Issues enabled.
- [ ] Discussions enabled if feedback threads are desired.
- [ ] Default branch is `main`.
- [ ] License visible.
- [ ] First discussion or release notes draft ready.
- [ ] No dashboard, voice, daemon, or autonomous editing claims in metadata.
