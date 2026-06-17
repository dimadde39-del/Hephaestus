# Studio Model Settings

Settings -> Models is the local provider and usage surface. It is intentionally
restrained: configure a provider, test it, choose a default, and understand
rough usage.

![Studio Provider Settings](assets/studio/studio-provider-settings.png)

## Providers

Supported paths:

- Local deterministic mode
- DeepSeek
- OpenAI-compatible
- OpenRouter through OpenAI-compatible base URL/model settings

Provider rows show name, model, base URL, configured state, connectivity state,
intended roles, optional context window, optional cost metadata, and default
conversation provider.

Status language:

```text
Configured
Not configured
Connection failed
Local mode
```

## Secret Handling

Stored API keys are never returned by normal API responses. Secret inputs are
write-only after save. Exports exclude provider secrets.

Current storage approach: provider secrets are stored in the local Studio
SQLite database and protected by OS file permissions. OS keychain integration is
future work.

## Usage Economy

![Studio Model Usage](assets/studio/studio-model-usage.png)

The usage view shows:

- estimated model calls this week;
- deterministic operations;
- estimated input and output tokens;
- estimated cost when metadata exists;
- context trimming;
- provider/model used;
- task type and linked success/failure where available.

Heuristic token and cost values are estimates. Preferred user-facing messages:

```text
Solved without a model call
One model call used
Context trimmed to fit budget
Estimated cost: ...
```

Adaptive multi-model routing is not implemented in Phase 5.5C.

## API

```text
GET    /api/providers
POST   /api/providers
PATCH  /api/providers/{provider_id}
DELETE /api/providers/{provider_id}
POST   /api/providers/{provider_id}/test
GET    /api/usage
```
