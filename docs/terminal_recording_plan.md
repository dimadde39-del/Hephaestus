# Terminal Recording Plan

Use this for the first soft reveal GIF or short video. The goal is a readable
terminal demo, not a flashy trailer.

## Terminal Setup

- Size: 120 columns by 34-40 rows for video; 96 columns by 42-48 rows for
  static screenshots.
- Font: Cascadia Mono, JetBrains Mono, Fira Code, Menlo, or Consolas.
- Font size: 16-18 px for 1080p video; 18-20 px for screenshots.
- Theme: dark charcoal background, light foreground, one warm accent color.
- Window chrome: keep it simple; avoid translucent backgrounds.
- Shell prompt: short path if possible, for example `hephaestus>`.
- Recording crop: terminal only, with no desktop clutter.

## Command Sequence

Run from the repository root:

```bash
uv run heph doctor
uv run heph repo inspect .
uv run heph release plan . --pareto --qubo --evaluate
uv run heph release list
uv run heph runs
uv run heph explain <optimizer_run_id> --summary
uv run heph pareto show <frontier_id>
uv run heph qubo show <problem_id>
uv run heph learn signals --run <optimizer_run_id>
```

Use the IDs printed by `release plan` for the follow-up commands.

## Pacing

- Pause 1 second after each command is typed.
- Pause 2-3 seconds on the release plan summary panel.
- Pause 2 seconds on the readiness recommendation.
- Pause 2 seconds on the linked artifacts panel so viewers can see that data
  was persisted.
- Use `explain --summary` in the main video. The full trace is too dense for a
  short reveal.

## Zoom Points

Zoom in only if the recording platform compresses text heavily:

- the `needs_validation` recommendation,
- the readiness signals table,
- the linked artifact IDs,
- the top rejection reasons in `explain --summary`,
- the selected QUBO assignment.

## Screenshot Sources

Use these images in docs and social cards:

- `docs/assets/demo/release-plan-demo.png`: main end-to-end demo.
- `docs/assets/demo/repo-inspect-demo.png`: read-only repo intelligence.
- `docs/assets/demo/pareto-demo.png`: tradeoff frontier.
- `docs/assets/demo/qubo-demo.png`: QUBO formulation.
- `docs/assets/demo/explain-demo.png`: decision summary and learning loop.

## Suggested Video Flow

```text
0:00  README hero or terminal title
0:05  repo inspect
0:15  release plan
0:45  explain --summary
0:55  pareto show
1:05  qubo show
1:15  learning signals
1:25  limitations and next step
```

Keep the final asset under 90 seconds. For GIFs, consider a 35-45 second cut
that focuses only on `release plan`, `explain --summary`, and `qubo show`.

## Helper Script

Print the recommended command sequence:

```bash
python scripts/demo/run_soft_reveal_demo.py
```

Run the main sequence and let the script print parsed follow-up IDs:

```bash
python scripts/demo/run_soft_reveal_demo.py --run
```

The helper does not capture images and does not add dependencies. It only keeps
the reveal flow easy to repeat.
