# Discussion Quality

Hephaestus should help the user think better, not merely answer. Phase 5B adds
explicit rubrics for high-impact discussions.

## Rubrics

Built-in discussion types:

- `idea_stress_test`
- `business_strategy`
- `product_strategy`
- `technical_architecture`
- `roadmap_decision`
- `research_planning`
- `risk_analysis`

Example idea stress-test checks:

- strongest argument for
- strongest argument against
- hidden assumptions
- failure modes
- cheap validation test
- what would change the recommendation
- next best move

Example technical architecture checks:

- requirements
- constraints
- failure modes
- complexity risk
- maintainability
- testability
- migration path
- observability

## Behavior

For strategic discussions, Hephaestus usually surfaces:

- position
- confidence
- strongest support
- strongest objection
- missing information
- risks
- next move

This is guidance, not a rigid template. A short factual `ask` should still stay
short. A high-impact `discuss` should pressure-test assumptions and name what
would change the recommendation.

## No Fake Contrarianism

The critic role exists to improve judgment. It should challenge weak premises
when useful, preserve what is strong, and avoid disagreeing just to sound smart.

## Phase 5C Evaluation

Conversation benchmarks now evaluate rubric-shaped output deterministically.
They check for recommendation, assumptions, risks, missing information, next
move, research-boundary honesty, strategic memory usage, repo context usage, and
anti-patterns such as blind agreement, fake certainty, unsupported claims,
generic advice, moralizing, and contrarianism for its own sake.

Run:

```bash
uv run heph conversation benchmark list
uv run heph conversation benchmark run
```
