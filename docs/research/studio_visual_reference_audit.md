# Studio Visual Reference Audit

Phase: 5.5A.1 Studio Visual Reset  
Date: 2026-06-16  
Selected primary direction: **Codex-inspired neutral agent workspace**

This audit uses current public product references and screenshots to guide Hephaestus Studio without copying proprietary branding, illustrations, exact component geometry, or pixel-perfect styling. The goal is a calm local agent workspace with ChatGPT-level conversation readability and a restrained Hephaestus identity.

## Sources Reviewed

- OpenAI Codex app docs and screenshots: <https://developers.openai.com/codex/app>
- OpenAI Codex feature update: <https://openai.com/index/codex-for-almost-everything/>
- ChatGPT desktop page: <https://chatgpt.com/features/desktop/>
- ChatGPT web and desktop release notes/help screenshots:
  - <https://help.openai.com/en/articles/6825453-chatgpt-release-notes>
  - <https://help.openai.com/en/articles/10169521-projects-in-chatgpt>
  - <https://help.openai.com/en/articles/10128477-chatgpt-enterprise-edu-release-notes>
  - <https://help.openai.com/en/articles/9703738-chatgpt-macos-app-release-notes>
  - <https://help.openai.com/en/articles/9295245-chatgpt-macos-app-screenshot-tool>
- Hermes Agent desktop docs: <https://hermes-agent.nousresearch.com/docs/user-guide/desktop>
- Hermes Workspace public screenshots: <https://github.com/outsourc-e/hermes-workspace>
- Linear public product page and screenshot content: <https://linear.app/>
- Raycast public product pages and screenshots: <https://www.raycast.com/> and <https://www.raycast.com/new>

## 1. OpenAI Codex Desktop App

### Layout Structure

Codex presents a compact project/thread sidebar, a dominant conversation/work area, and an optional right-side review/details pane. The center column remains the primary reading and action surface. The right pane is useful when there is a concrete artifact such as a diff, file preview, source list, or review state.

### Sidebar Behavior

The sidebar is quiet and utilitarian. It includes a small product mark, New thread, search/automation/plugin actions, pinned items, project folders, thread lists, and settings near the bottom. The visual weight is low, with active rows indicated by subtle background and small state text rather than large decorative badges.

### Conversation Density

Message density is moderate. User prompts may appear compactly, but assistant output reads more like a document than a chat bubble. Generated work summaries and file changes appear as compact structured blocks inside the central column.

### Typography

Codex uses neutral UI typography with small metadata labels, readable body copy, and monospace only where code/diffs require it. Headings are compact rather than marketing-sized.

### Spacing

Spacing is tight in navigation and artifact areas but more generous in the conversation column. The interface feels designed for long working sessions, not a landing page.

### Composer Design

The composer sits at the bottom of the center column as a rounded input surface with model/mode controls integrated into the same control zone. Secondary controls are present but subdued.

### Project/Task Organization

Projects and threads are first-class sidebar concepts. Worktree/project context is visible, but not allowed to dominate the message surface.

### Right-Panel Behavior

The right panel is contextual. It can show review, sources, artifacts, previews, or summaries. It should not become a permanent observability console by default.

### Artifact Presentation

Artifacts are compact and operational: diffs, files, sources, previews, and change summaries. The presentation is structured but not decorative.

### Color Usage

The Codex screenshots use mostly neutral light surfaces with low-contrast borders. Accent colors are sparse and meaningful, mostly for state changes, diffs, or compact status.

### Useful for Hephaestus

- Three-zone structure: compact sidebar, dominant center conversation, optional details drawer.
- Thread/project organization without dashboard density.
- Bottom composer with integrated controls.
- Compact artifact rows instead of decorative cards.
- Right drawer as optional supporting context, not the main product.

### Should Not Be Copied

- Exact sidebar hierarchy, icons, dimensions, or OpenAI/Codex branding.
- Pixel-perfect composer layout.
- Codex-specific Git/review affordances before Phase 5.5B calls for them.
- Automatic summary panes or source panels that alter Hephaestus conversation persistence semantics.

## 2. ChatGPT Desktop/Web Conversation UI

### Layout Structure

ChatGPT prioritizes a single readable conversation column with a sidebar for recent/pinned/project organization. Tool surfaces such as Canvas or app companion views appear contextually rather than replacing the conversation.

### Sidebar Behavior

OpenAI release notes describe a redesigned sidebar with floating behavior, limited recent conversations in the main sidebar, an infinite flyout for older conversations, pinned GPTs below conversations, and settings at the bottom. On mobile, the sidebar floats and auto-closes when switching threads.

### Conversation Density

The central conversation uses generous rhythm. User messages are visually distinct, but assistant messages are primarily document-like. Long answers remain readable because width, line height, and paragraph spacing are prioritized.

### Typography

ChatGPT uses plain readable UI typography. Message copy is normal sans-serif. Monospace appears only for code and technical snippets.

### Spacing

The conversation column has a comfortable max width and strong vertical breathing room. The composer sits in a bottom fade/anchored region and does not crowd messages.

### Composer Design

Recent public notes emphasize consolidating tools into a single menu/dropdown to reduce clutter. The composer keeps a clear input affordance, attachment/tools affordance, and send/voice actions.

### Project/Task Organization

Projects provide a stable sidebar grouping and allow moving chats into a project. The organizing model is understandable to non-admin users.

### Right-Panel Behavior

Canvas and companion windows can sit alongside the conversation, but the default chat remains simple. Side views are task-specific and should not be permanently dense.

### Artifact Presentation

Artifacts such as files, images, and canvas surfaces are contextual attachments or side surfaces. They do not replace exact conversation history.

### Color Usage

Color is restrained. Light/dark modes rely on neutral backgrounds, subtle borders, and limited semantic state colors.

### Useful for Hephaestus

- Conversation readability as a first-order requirement.
- Distinct user/assistant messages without heavy cards on every message.
- Clear New chat, search, projects/recent/pinned patterns.
- Bottom composer that feels comfortable to type into.
- Mobile sidebar behavior that avoids permanent multi-column density.

### Should Not Be Copied

- ChatGPT branding, exact message spacing, model picker behavior, or proprietary tool menus.
- Memory/project semantics that do not exist in Hephaestus.
- Automatic summaries, context resume cards, or any transformation of exact stored messages.

## 3. Hermes Agent UI

### Layout Structure

Hermes Desktop is documented as a native app over the same CLI/gateway/session state. Hermes Workspace public screenshots show a centered empty chat, a bottom composer, and settings/provider screens with strong dark-green styling.

### Sidebar Behavior

Hermes Workspace screenshots emphasize settings sections and agent/provider configuration more than quiet conversation browsing. The settings UI is more control-room oriented than Hephaestus should be.

### Conversation Density

The chat empty state is sparse, but the wider product direction leans toward agent tools, memory, skills, inspector, and observability. This can become visually heavy.

### Typography

Typography is legible but more stylized in the screenshots, with stronger contrast between headings, labels, and technical controls.

### Spacing

Large centered empty states are roomy. Settings/provider grids are denser and more panel-driven.

### Composer Design

The public chat screenshot shows a large bottom composer with visible shortcut hints and provider/model details. This is useful as a local-agent precedent, but it has more exposed internals than Hephaestus should show by default.

### Project/Task Organization

Hermes emphasizes agent sessions, memory, skills, provider setup, and jobs. This is useful for later Workbench scope, but too advanced for the default Studio chat.

### Right-Panel Behavior

The broader Hermes workspace includes inspector/observability concepts. Those belong in future Workbench views, not in the default chat shell.

### Artifact Presentation

Artifacts and tools are exposed as agent capabilities. Hephaestus should make artifacts compact and secondary until a Workbench screen needs richer presentation.

### Color Usage

Hermes screenshots use a dark green/cream/gold identity with visible glows and strong themed backgrounds. This is memorable but too visually dominant for the requested Hephaestus reset.

### Useful for Hephaestus

- Local-agent continuity across CLI and desktop surfaces.
- Bottom composer with provider/model context.
- Subtle starter actions in an empty conversation.

### Should Not Be Copied

- Strong themed background color, glow, large mascot/avatar treatment, or control-room density.
- Provider grids and observability panels in the default chat view.
- Shortcut-heavy composer text that makes the app feel more like a terminal wrapper than a calm reading surface.

## 4. Linear

### Layout Structure

Linear uses a compact sidebar plus a dense but highly organized main content area. The public product screenshots show workspace navigation, issue details, activity, metadata, and agent-related work in disciplined columns.

### Sidebar Behavior

The sidebar is hierarchical and scannable: inbox/my issues/reviews, workspace sections, projects, favorites. It avoids large branding and makes the active item obvious.

### Conversation Density

Linear is not a chat product, but its activity streams are concise and well-spaced. It proves dense productivity UI can feel calm when typography, borders, and color are restrained.

### Typography

Linear uses small, precise labels with a strong hierarchy. Body text is clear, metadata is muted, and labels do not shout.

### Spacing

Spacing is compact but consistent. Rows, metadata chips, and side details use predictable rhythm.

### Composer Design

Composer is not the core reference here. The useful pattern is action entry points staying compact and near the work item.

### Project/Task Organization

Linear is excellent at separating workspace, project, issue, status, priority, cycle, and activity without turning every item into a visual event.

### Right-Panel Behavior

Issue metadata lives in a supporting area. It is visible when useful but visually secondary to the main issue/activity content.

### Artifact Presentation

Artifacts and linked agent activity appear in context as compact activity updates, labels, and metadata.

### Color Usage

Linear relies on neutral surfaces, low-contrast lines, and semantic color sparingly. It avoids decorative saturation.

### Useful for Hephaestus

- Compact sidebar hierarchy.
- Calm metadata treatment.
- Low-noise status and activity presentation.
- Confidence that dense UI can still feel mature.

### Should Not Be Copied

- Issue tracker mental model or enterprise dashboard density.
- Linear branding, exact iconography, row styling, or project taxonomy.
- Permanent metadata columns that make chat feel secondary.

## 5. Raycast

### Layout Structure

Raycast is a focused desktop utility centered on a command surface. Public screenshots emphasize a compact, keyboard-first window with dense rows, immediate search, and clean action affordances.

### Sidebar Behavior

Raycast does not primarily use a persistent sidebar in the same way as Codex or ChatGPT. The relevant pattern is fast command access and disciplined visual hierarchy.

### Conversation Density

Raycast is not a conversation UI. Its density is useful for command/search surfaces but should not drive message design.

### Typography

Raycast uses crisp UI typography with compact metadata and strong scanning rhythm. It does not rely on themed typography to communicate quality.

### Spacing

Spacing is tight and precise. It feels native and fast. This is useful for command menus, search panels, and settings rows, not for long-form message reading.

### Composer Design

The command palette input is a useful reference for polished focus states, shortcut-first interaction, and avoiding visual clutter around a primary input.

### Project/Task Organization

Raycast organizes by commands/extensions/actions, which is not directly applicable to Studio conversations. The useful lesson is keeping secondary actions discoverable without showing everything at once.

### Right-Panel Behavior

Raycast often uses detail panes/previews only when a selected result needs them. This supports the Hephaestus choice to keep the right drawer optional.

### Artifact Presentation

Previews are compact and action-oriented. This is relevant for future artifact presentation in Workbench, but not for adding dashboards in this phase.

### Color Usage

Raycast uses neutral/dark command surfaces with a restrained red brand accent. It demonstrates that a product can have a recognizable identity without saturating the entire workspace.

### Useful for Hephaestus

- High-polish search and command affordances.
- Keyboard-first density where appropriate.
- Native utility restraint.
- Brand accent used sparingly.

### Should Not Be Copied

- Launcher-first product structure.
- Red brand treatment, keycap visuals, or exact command palette styling.
- Dense command rows as the default message-reading rhythm.

## Direction Decision

The selected direction is **Codex-inspired neutral agent workspace**.

Hephaestus should inherit:

- Codex's product structure: compact sidebar, dominant thread, optional details drawer.
- ChatGPT's conversation readability: message history should feel pleasant to read the next day.
- Linear's calm metadata discipline.
- Raycast's polished input/search restraint.
- Hermes' local-agent continuity, but not its stronger themed control-room presentation.

Hephaestus should avoid:

- Cyberpunk/terminal styling.
- Forge game theming.
- Dashboard/observability density in the default chat.
- Large mascot or hero branding inside the working application.
- Gradients, glow, bronze fields, uppercase labels, and hardcoded themed color scatter.
