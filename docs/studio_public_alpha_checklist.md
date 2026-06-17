# Studio Public Alpha Checklist

Use this checklist before presenting Studio as public-alpha ready.

## Fresh Install

- Build frontend static assets.
- Build wheel and sdist.
- Install the wheel into a temporary isolated environment.
- Run `heph --help`.
- Run `heph studio doctor`.
- Launch `heph studio --no-open`, verify health/static load, then stop it.

## Product Flow

- First-run onboarding appears once and can be skipped.
- Local deterministic mode works without API keys.
- Provider setup works with a fake endpoint and redacts secrets.
- Persistent chat creates, reopens, searches, pins, renames, archives, and
  continues exact messages.
- Workbench shows coding work, validation evidence, checkpoints, releases,
  outcomes, and meaningful approvals.
- Memory supports search, detail, edit, archive, restore, delete, conflicts,
  and suggestion review.
- Backup/export/restore works with a fixture database.
- Incompatible backup restore is refused.

## Cross-Platform

- Windows paths render and package validation passes.
- Linux/macOS localhost behavior is documented.
- Browser-served app remains the supported local packaging path.

## Accessibility

- Keyboard navigation reaches primary routes, memory filters, provider forms,
  export/restore controls, and advanced tables.
- Focus rings are visible.
- Status uses words, not color alone.
- Pareto and QUBO have table/plain-language alternatives.
- Narrow viewport remains usable.

## Performance

- Initial Studio load is acceptable from packaged static assets.
- Conversation list and Workbench lists load without blocking the shell.
- Large validation output and diffs are truncated/collapsible.
- Memory search remains local and deterministic.
- Advanced charts are small and paired with tables.

## Security

- Studio binds to localhost by default.
- No `.env` files or API keys are committed.
- Provider keys are redacted from normal APIs, screenshots, and exports.
- Exports exclude secrets.
- Destructive/system-level actions remain blocked.

## Screenshots

- `studio-memory.png`
- `studio-provider-settings.png`
- `studio-model-usage.png`
- `studio-decision-trace.png`
- `studio-pareto.png`
- `studio-qubo.png`
- `studio-onboarding.png`
- `studio-data-backup.png`

Use fixture data only.

## Known Limitations

- No daemon or 24/7 runtime.
- No Telegram, voice, cloud VM, browser automation, deploy, or Git push.
- No adaptive multi-model routing yet.
- No Skill Forge, Capability Forge, RLM, or Context Forge yet.
- No public Claude Code parity claim until Phase 5.6 benchmark evidence exists.

## Demo Flow

1. Open Studio.
2. Skip or complete onboarding.
3. Start in local deterministic mode.
4. Open an existing conversation.
5. Inspect linked Workbench work.
6. Review and edit a memory.
7. Configure a fake provider.
8. Export a conversation.
9. Create a backup.
10. Open Advanced only after the practical flow is clear.
