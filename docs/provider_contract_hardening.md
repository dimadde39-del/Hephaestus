# Provider Contract Hardening

Phase 5.6A.1.1 hardens live provider-backed greenfield planning after the first TaskForge acceptance run ended as `FAIL_PLAN`.

## First live run diagnosis

Artifacts: `C:\Temp\heph-live-greenfield\artifacts`.

Redacted facts:

- Provider source: `studio:provider_b898e5790cb2`.
- Provider type/model: `deepseek` / `deepseek-v4-flash`.
- Base URL: `https://api.deepseek.com`.
- Local fallback did not occur.
- Three plan-stage provider calls were recorded.
- Usage from the one successful provider response: input `418`, output `717`, cached input `384`.
- Two attempts failed with a provider transport timeout.
- One provider response was received but rejected as an invalid structured plan.
- No plan ID or change ID was created, so prepare/apply/validation did not run.

What can be determined from persisted artifacts:

- The timeout happened while reading the provider response body: `response.read()` raised `TimeoutError` inside Python `http.client` chunked-body reading.
- The previous Studio runtime path used a single `timeout=8` value for saved providers.
- The successful response was rejected after provider completion, before plan persistence.
- Hephaestus did not persist raw final content, raw reasoning content, `finish_reason`, parse status, or Pydantic validation details for that failure.

What cannot be recovered from the first run:

- The exact final content shape.
- Whether the content was syntactically invalid JSON, markdown fenced JSON, prose plus JSON, multiple JSON objects, or schema-invalid JSON.
- The exact Pydantic validation errors.
- `finish_reason` and whether the provider response was truncated.

That diagnostic gap is intentional for secrets/reasoning safety, but it was too coarse for provider contract debugging. Phase 5.6A.1.1 records redacted failure artifacts instead: stage, provider/model, finish reason, content length, content SHA-256, parse status, validation errors, timeout type, latency, usage, retry count, and repair count. Raw final content is still omitted unless explicit local debug mode is added later. Raw reasoning content is never persisted.

## Hardened contract

Plan and manifest calls use JSON mode (`response_format={"type":"json_object"}`) and a system prompt that:

- says `JSON`;
- requires exactly one top-level JSON object;
- forbids markdown fences and prose;
- lists the expected top-level fields;
- includes a compact example validated against the active Pydantic schema;
- explains that `null` and omitted required fields are invalid.

Pydantic validation remains authoritative. JSON mode is only a provider-side formatting aid.

## Parser and repair

The parser pipeline is intentionally narrow:

1. Trim UTF-8 BOM and surrounding whitespace.
2. Attempt direct JSON object parse.
3. If needed, extract exactly one fenced JSON block.
4. Reject multiple top-level objects.
5. Validate with the active Pydantic schema.
6. Persist structured validation errors without raw content.

If parsing or validation fails, Hephaestus performs at most one bounded format-repair call. The repair prompt includes the original final content, exact validation errors, the compact schema example, and JSON schema. It asks the provider to preserve meaning and fix only format/schema shape. It does not pass raw reasoning content and does not regenerate the plan from the original user task.

Failure codes are precise:

- `PLAN_JSON_PARSE_FAILED`
- `PLAN_SCHEMA_VALIDATION_FAILED`
- `PLAN_FORMAT_REPAIR_FAILED`
- corresponding `MANIFEST_*` codes for manifest generation

## Timeout and attempts

Provider telemetry now separates:

- logical provider calls;
- transport attempts;
- format-repair calls.

Transient transport failures can be retried once within the same logical call. Non-transient failures such as authentication errors, insufficient balance, invalid model, or schema validation failures are not retried as a new full generation.

DeepSeek saved-provider runtime no longer forces an 8-second read timeout; the default read timeout is increased and configurable through DeepSeek timeout settings.
