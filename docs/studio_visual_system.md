# Hephaestus Studio Visual System

Phase: 5.5A.1 Studio Visual Reset  
Primary direction: **Codex-inspired neutral agent workspace**

## Reference Direction

The reset follows the audit in [studio_visual_reference_audit.md](research/studio_visual_reference_audit.md). Codex is the primary structural reference: compact sidebar, dominant conversation column, optional details drawer. ChatGPT is the primary readability reference for long conversation history. Linear and Raycast inform restraint, density, and input/search polish. Hermes informs local-agent continuity, but its stronger themed control-room treatment is intentionally not adopted.

## Design Principles

- Chat is the default product surface.
- The center conversation column dominates the layout.
- Hephaestus identity appears through the small Talos mark, product naming, restrained ember accent, and quiet empty states.
- Message history stays exact and readable. The UI must not replace it with summaries or resume cards.
- Advanced agent internals should stay out of the default chat shell.
- Metadata is secondary. It should help orientation without feeling like an observability console.
- Light and dark themes share the same layout, type scale, and semantic tokens.

## Theme Tokens

The token system lives in `apps/studio/app/globals.css`.

- Background: `--color-background`
- Surface: `--color-surface`
- Elevated surface: `--color-surface-raised`
- Subtle surface: `--color-surface-subtle`
- Borders: `--color-border`, `--color-border-strong`
- Text: `--color-text-primary`, `--color-text-secondary`, `--color-text-muted`
- Accent: `--color-accent`, `--color-accent-strong`, `--color-accent-muted`
- Minor identity accent: `--color-bronze`
- Status: `--color-success`, `--color-warning`, `--color-danger`
- Code: `--color-code-background`, `--color-code-border`
- Focus: `--color-focus-ring`
- Spacing: `--space-1` through `--space-8`
- Radius: `--radius-xs`, `--radius-sm`, `--radius-md`, `--radius-lg`, `--radius-pill`
- Shadow: `--shadow-soft`, `--shadow-panel`

Dark mode uses neutral near-black and graphite surfaces with restrained ember. Light mode uses warm off-white, white, and soft gray surfaces with the same accent family.

## Layout

The shell has three regions:

- Compact sidebar: New chat, search, pinned conversations, recent conversations, archived toggle, settings.
- Conversation column: header, readable message timeline, bottom composer.
- Details drawer: collapsible context, repo, mode, provider, policy, and compact artifact counts.

The sidebar can collapse into a rail. The details drawer can collapse entirely. On medium and narrow screens, drawers become overlays so the conversation column remains the primary surface.

## Typography

Studio uses normal modern UI sans-serif type for navigation, messages, and controls. Monospace is reserved for code blocks, inline code, commands, and technical identifiers. Message copy uses comfortable line height and a constrained width so long conversations remain readable.

## Conversation UI

User messages are compact and softly surfaced. Assistant messages read like documents, without a heavy border around every response. Message copy actions appear quietly on hover/focus. Timestamps stay secondary. Code blocks use integrated neutral surfaces and compact copy controls.

The empty state uses a small Talos mark and concise starter prompts:

- Discuss an idea
- Open a repo
- Plan a change
- Review recent work

## What Was Not Copied

- OpenAI/Codex or ChatGPT branding, exact dimensions, composer geometry, or proprietary illustrations.
- ChatGPT automatic summaries, memory/project semantics, or resume cards.
- Hermes themed glows, strong green/gold control-room styling, and large avatar treatment.
- Linear issue-tracker density or enterprise dashboard organization.
- Raycast launcher-first layout, red identity system, or keycap-heavy visuals.

## Workbench Extension

Phase 5.5B Workbench screens extend this system rather than introducing a new
visual language.

- Keep chat readable and central when conversation is present.
- Put plans, diffs, validation evidence, checkpoints, tool actions, outcomes,
  and release evidence in dedicated Workbench panels.
- Use the existing theme tokens for all new surfaces.
- Use semantic color only for real status: green for success, red for errors or blocked actions, warning for caution.
- Keep artifact presentation compact until a user opens a deeper view.
- Avoid bronze/orange fields, glowing cards, terminal labels, and permanent three-column density.
- Keep advanced decision traces, Pareto, QUBO, outcome IDs, and raw technical
  metadata collapsed by default.
- Chat artifact cards stay compact and secondary to the original conversation
  text.

Workbench is allowed to be denser than Chat, but it should still read as a calm
local agent workspace: neutral surfaces, readable typography, restrained
borders, and monospace only for code, commands, paths, and technical IDs.
