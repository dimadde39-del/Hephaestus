# Soft Reveal Checklist

Use this as the execution checklist before the first public post.

## Repository

- [ ] README hero image renders.
- [ ] README intro says self-improving agent, early alpha, local-first, and
  approval-gated.
- [ ] README shows what works today.
- [ ] README shows what is not built yet.
- [ ] README current-loop commands are obvious.
- [ ] Contributor docs are linked.
- [ ] Roadmap makes Phase 5.5 mandatory before Phase 6.
- [ ] GitHub repository description is set.
- [ ] GitHub topics are set.
- [ ] GitHub social preview image is uploaded.
- [ ] Discussions are enabled if feedback threads are desired.

## Demo

- [ ] `uv sync` works on a clean clone.
- [ ] `uv run heph doctor` works.
- [ ] `uv run heph ask "What is this project trying to become?" --repo .` works.
- [ ] `uv run heph validate run . --yes` works.
- [ ] `uv run heph code propose "Update README wording to mention validation-backed release evidence." --repo .` works.
- [ ] `uv run heph code run "Update README wording to mention validation-backed release evidence." --repo . --dry-run` works.
- [ ] `uv run heph code results` works.
- [ ] Advanced demo: `uv run heph release plan . --pareto --qubo --with-validation --yes` works.
- [ ] Advanced demo IDs can be inspected with `heph explain`, `heph pareto`, and `heph qubo`.

## Assets

- [ ] README hero image ready.
- [ ] GitHub social preview ready.
- [ ] Demo screenshots ready in `docs/assets/demo/`.
- [ ] Main screenshot selected for README or docs.
- [ ] Screenshot pack linked from README and docs.
- [ ] Terminal recording plan reviewed.
- [ ] 60-90 second demo script rehearsed once.

## Copy

- [ ] X/Twitter short post drafted.
- [ ] X/Twitter thread drafted.
- [ ] X/Twitter progress update variant drafted.
- [ ] Reddit feedback post drafted.
- [ ] Telegram/Discord short message drafted.
- [ ] Telegram/Discord longer message drafted.
- [ ] GitHub Discussion introduction drafted.

## Positioning

- [ ] Target communities selected.
- [ ] First post order decided.
- [ ] Objection answers reviewed.
- [ ] Honest limitation notes ready.
- [ ] No claims of full autonomous coding.
- [ ] No claims of deploy/publish/push execution.
- [ ] No claims that local validation proves production readiness.
- [ ] No vague "the model learns" claims.
- [ ] No quantum speedup language.
- [ ] No voice/Jarvis positioning.
- [ ] QUBO/Pareto appear only as advanced internals.

## Suggested Post Order

1. X/Twitter soft reveal.
2. GitHub Discussion intro, if Discussions are enabled.
3. One Telegram or Discord community message.
4. Reddit feedback post after the first comments clarify wording.
5. Follow-up X/Twitter progress update with one screenshot.

## After Posting

- [ ] Save useful feedback into roadmap notes.
- [ ] Track repeated objections.
- [ ] Clarify README wording if people misunderstand the boundary.
- [ ] Pick the next small credibility milestone.
- [ ] Avoid reacting by adding broad product scope too early.
