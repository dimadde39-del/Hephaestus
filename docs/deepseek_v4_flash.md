# DeepSeek V4 Flash

Phase 5.6A.0 makes `deepseek-v4-flash` the DeepSeek default while keeping custom model IDs configurable. DeepSeek uses the existing OpenAI-compatible chat-completions transport; it is not a second provider framework.

## Configuration

The DeepSeek fields are API key, base URL, model, thinking, reasoning effort (`high` or `max`), maximum output tokens, context window, and input/output cost metadata per million tokens.

Defaults are `https://api.deepseek.com`, `deepseek-v4-flash`, thinking enabled, and `high` effort. `max` is opt-in because it may cost more. Cost values are local estimate metadata, not a provider invoice; verify current pricing before changing them.

Environment configuration:

```text
DEEPSEEK_API_KEY
DEEPSEEK_BASE_URL=https://api.deepseek.com
DEEPSEEK_MODEL=deepseek-v4-flash
HEPH_DEEPSEEK_THINKING=enabled
HEPH_DEEPSEEK_REASONING_EFFORT=high
HEPH_DEEPSEEK_MAX_OUTPUT_TOKENS=4096
```

Studio setup is at **Settings → Models → Add provider → DeepSeek**. Paste the key once, verify the base URL and model, save, test the connection, and then choose **Use as default**. The saved key is write-only: API responses, exports, and the UI never return it. Remove the provider to delete its saved key.

The effective priority is:

1. an explicit per-request provider choice;
2. Studio deterministic mode or the saved Studio default for Studio requests using `auto`;
3. environment-configured providers;
4. local deterministic fallback.

CLI dry-run output shows the effective model, URL, thinking settings, limits, and key source without showing the key.

## Thinking and reasoning content

Thinking requests send:

```json
{
  "thinking": {"type": "enabled"},
  "reasoning_effort": "high"
}
```

Sampling controls such as temperature, `top_p`, and presence/frequency penalties are omitted while thinking is enabled. `reasoning_content` is parsed into a transient, serialization-excluded field. It is not rendered, persisted as a conversation message, exported, added to memory, or logged.

If a response contains tool calls, the transport can return `reasoning_content` with the assistant tool-call message only for the immediate continuation request. It is discarded after the turn. Hephaestus still has no native autonomous tool-call agent loop: repository context and bounded actions are assembled by the orchestration layer.
