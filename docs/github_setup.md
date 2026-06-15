# GitHub Setup Suggestions

These suggestions are for the public alpha soft reveal.

## Repository Description

Use this in the GitHub About box:

```text
Self-improving AI agent that remembers context, helps think and code, validates work, and learns from outcomes.
```

## Website / Links

If there is no project website yet, leave the website field empty or point it to
the GitHub repository. Do not link to a placeholder landing page.

Useful links to feature in README or Discussions:

- [product positioning](product_positioning.md)
- [release evidence](release_evidence.md)
- [repo-aware coding loop](repo_aware_coding_loop.md)
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
ai-coding
local-first
validation
memory
explainable-ai
decision-traces
optimization
pareto
qubo
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

Keep the README to 1-2 images. Use the rest in walkthroughs and social updates.

## Pinned Demo Commands

Lead with the practical agent loop:

```bash
heph ask "What is this project trying to become?"
heph validate run . --yes
heph code run "Update README wording to mention validation-backed release evidence." --repo . --dry-run
```

Suggested pinned copy:

```text
Try the local agent loop: talk with project context, run validation, propose scoped repo changes, and inspect outcomes.
```

Advanced technical readers can also try:

```bash
heph release plan . --pareto --qubo --with-validation --yes
```

## Discussions

Enable GitHub Discussions if you want a low-friction place to collect early
product and architecture feedback.

Suggested first Discussion:

```text
Soft reveal: Hephaestus public alpha direction
```

Use the draft in [docs/public_launch_notes.md](public_launch_notes.md). Pin it
while the soft reveal is active.

## What To Pin Or Feature

Feature these in order:

1. README current loop commands.
2. Validation/coding-loop evidence docs.
3. Public alpha roadmap.
4. Release planning screenshot for advanced internals.
5. GitHub Discussion feedback thread, if enabled.

Avoid pinning speculative feature mockups. The public reveal should lead with
the working CLI.

## Suggested First Release Tag

If tagging the soft reveal:

```text
v0.1.0-self-improving-agent-alpha
```

Alternative later tags:

- `v0.2.0-studio-alpha`
- `v0.3.0-skill-forge-alpha`
- `v0.4.0-always-on-runtime-alpha`

Avoid tag names that imply production autonomy before the visibility and
approval surfaces exist.

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
- [ ] No dashboard, voice, daemon, browser automation, or full autonomous coding claims in metadata.
