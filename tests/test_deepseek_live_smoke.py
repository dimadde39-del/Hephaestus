from __future__ import annotations

import io
import json
import sqlite3
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import pytest
from typer.testing import CliRunner

from hephaestus.cli.main import app
from hephaestus.models import DeepSeekProvider, ModelRequest, ProviderRequestError
from hephaestus.models.live_smoke import (
    LiveSmokeConfig,
    SmokeCase,
    _CallBudget,
    run_live_smoke,
)
from hephaestus.storage.migrations import _migrate_deepseek_pricing_metadata
from hephaestus.studio.experience import StudioExperienceRepository
from hephaestus.studio.schemas import (
    StudioProviderPatchRequest,
    StudioProviderStatus,
    StudioProviderUpsertRequest,
)


class FakeResponse:
    status = 200

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self.payload).encode()


def _provider(
    captured: list[dict[str, Any]],
    *,
    content: str = "OK",
    reasoning_content: str = "private chain of thought",
    tool_calls: list[dict[str, Any]] | None = None,
) -> DeepSeekProvider:
    def urlopen(request: urllib.request.Request, *, timeout: float) -> FakeResponse:
        assert timeout > 0
        captured.append(json.loads(bytes(request.data or b"{}")))
        return FakeResponse(
            {
                "choices": [
                    {
                        "message": {
                            "content": content,
                            "reasoning_content": reasoning_content,
                            "tool_calls": tool_calls or [],
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 120,
                    "completion_tokens": 30,
                    "prompt_cache_hit_tokens": 20,
                },
            }
        )

    return DeepSeekProvider(api_key="test", urlopen=urlopen)


def test_v4_flash_defaults_and_custom_override(monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_MODEL", raising=False)
    default = DeepSeekProvider(api_key="test")
    custom = DeepSeekProvider(api_key="test", model="deepseek-custom")

    assert default.model == "deepseek-v4-flash"
    assert default.base_url == "https://api.deepseek.com"
    assert default.thinking_enabled is True
    assert default.reasoning_effort == "high"
    assert custom.profiles()[0].model == "deepseek-custom"


def test_base_url_normalization_and_thinking_payloads() -> None:
    captured: list[dict[str, Any]] = []
    provider = _provider(captured)
    provider.base_url = "https://api.deepseek.com///".rstrip("/")

    provider.complete(ModelRequest(prompt="hi", max_output_tokens=9))
    provider.complete(
        ModelRequest(prompt="hi", max_output_tokens=9, thinking_enabled=False)
    )

    enabled, disabled = captured
    assert enabled["thinking"] == {"type": "enabled"}
    assert enabled["reasoning_effort"] == "high"
    assert "temperature" not in enabled
    assert "top_p" not in enabled
    assert "presence_penalty" not in enabled
    assert "frequency_penalty" not in enabled
    assert "thinking" not in disabled
    assert disabled["temperature"] == 0.0


@pytest.mark.parametrize("effort", ["high", "max"])
def test_reasoning_effort_values(effort: str) -> None:
    captured: list[dict[str, Any]] = []
    provider = DeepSeekProvider(api_key="test", reasoning_effort=effort, urlopen=_provider(captured)._urlopen)

    provider.complete(ModelRequest(prompt="hi"))

    assert captured[0]["reasoning_effort"] == effort


def test_reasoning_content_is_transient_and_tool_continuation_retains_it() -> None:
    captured: list[dict[str, Any]] = []
    tool_call = {
        "id": "call_1",
        "type": "function",
        "function": {"name": "read_file", "arguments": "{\"path\":\"README.md\"}"},
    }
    provider = _provider(captured, content="", tool_calls=[tool_call])
    request = ModelRequest(prompt="Inspect README")

    first = provider.complete(request)
    serialized = first.model_dump()
    assert first.reasoning_content == "private chain of thought"
    assert "reasoning_content" not in serialized
    assert "private chain of thought" not in repr(first)

    provider.complete_tool_continuation(
        request,
        first,
        [{"role": "tool", "tool_call_id": "call_1", "content": "Hephaestus"}],
    )
    assistant = captured[1]["messages"][1]
    assert assistant["reasoning_content"] == "private chain of thought"
    assert assistant["tool_calls"] == [tool_call]


def test_usage_metadata_parsing() -> None:
    provider = _provider([])
    response = provider.complete(ModelRequest(prompt="hi"))

    assert response.text == "OK"
    assert response.input_tokens == 120
    assert response.output_tokens == 30
    assert response.cached_input_tokens == 20
    assert response.estimated_cost > 0


@pytest.mark.parametrize(
    ("status", "body", "code"),
    [
        (401, b"unauthorized", "unauthorized"),
        (402, b"insufficient balance", "insufficient_balance"),
        (429, b"rate limit", "rate_limited"),
        (400, b'{"error":{"message":"invalid model"}}', "invalid_model"),
    ],
)
def test_sanitized_provider_errors(status: int, body: bytes, code: str) -> None:
    def failing(request: urllib.request.Request, *, timeout: float) -> FakeResponse:
        raise urllib.error.HTTPError(
            request.full_url,
            status,
            "provider failure",
            hdrs=None,
            fp=io.BytesIO(body),
        )

    provider = DeepSeekProvider(api_key="secret-never-returned", urlopen=failing)
    with pytest.raises(ProviderRequestError) as caught:
        provider.complete(ModelRequest(prompt="hi"))

    assert caught.value.code == code
    assert "secret-never-returned" not in str(caught.value)


def test_timeout_is_sanitized() -> None:
    def timeout(request: urllib.request.Request, *, timeout: float) -> FakeResponse:
        raise TimeoutError

    provider = DeepSeekProvider(api_key="test", urlopen=timeout)
    with pytest.raises(ProviderRequestError, match="timed out") as caught:
        provider.complete(ModelRequest(prompt="hi"))
    assert caught.value.code == "connect_timeout"


def test_no_network_without_live_and_preflight_is_redacted(tmp_path) -> None:
    calls: list[dict[str, Any]] = []
    result = run_live_smoke(
        LiveSmokeConfig(case=SmokeCase.CODING),
        provider=_provider(calls),
        artifact_root=tmp_path,
    )

    assert result.calls == 0
    assert calls == []
    assert result.api_key_source == "DEEPSEEK_API_KEY"
    assert '"api_key"' not in result.model_dump_json()


def test_cli_dry_run_never_calls_network(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "fake-key")

    def forbidden(*args: object, **kwargs: object) -> FakeResponse:
        raise AssertionError("network transport must not run without --live")

    monkeypatch.setattr(urllib.request, "urlopen", forbidden)
    result = CliRunner().invoke(
        app,
        ["models", "smoke", "deepseek", "--case", "conversation", "--json"],
    )

    assert result.exit_code == 0
    assert '"calls": 0' in result.output
    assert "fake-key" not in result.output


def test_call_limit_and_estimated_cost_stop() -> None:
    provider = _provider([])
    limited = _CallBudget(
        LiveSmokeConfig(live=True, max_calls=1, max_output_tokens=1),
        provider,
    )
    limited.complete(ModelRequest(prompt="one", max_output_tokens=1))
    with pytest.raises(RuntimeError, match="call limit"):
        limited.complete(ModelRequest(prompt="two", max_output_tokens=1))

    capped = _CallBudget(
        LiveSmokeConfig(live=True, estimated_cost_cap=0.000001),
        provider,
    )
    with pytest.raises(RuntimeError, match="cost cap"):
        capped.complete(ModelRequest(prompt="too expensive", max_output_tokens=4096))


def test_conversation_smoke_isolated_usage_and_reasoning(tmp_path) -> None:
    provider = _provider([], content="Hephaestus is a validation-backed local agent.")
    normal_db = tmp_path / "normal.db"
    result = run_live_smoke(
        LiveSmokeConfig(case=SmokeCase.CONVERSATION, live=True),
        provider=provider,
        artifact_root=tmp_path / "artifacts",
    )

    assert result.calls == 1
    assert result.details["conversation_persisted"] is True
    assert result.details["raw_reasoning_persisted"] is False
    assert not normal_db.exists()
    artifact = Path(result.artifact_path or "").read_text(encoding="utf-8")
    assert "private chain of thought" not in artifact


def test_coding_fixture_is_reset_and_normal_database_is_not_used(tmp_path) -> None:
    source_file = (
        Path(__file__).parents[1]
        / "src"
        / "hephaestus"
        / "fixtures"
        / "slugify_smoke"
        / "slugify.py"
    )
    before = source_file.read_text(encoding="utf-8")
    replacement = before.replace(
        'return re.sub(r"[^a-z0-9]", separator, value.lower()).strip(separator)',
        'return re.sub(r"[^a-z0-9]+", separator, value.lower()).strip(separator)',
    )
    test_file = (
        Path(__file__).parents[1]
        / "src"
        / "hephaestus"
        / "fixtures"
        / "slugify_smoke"
        / "test_slugify.py"
    )
    test_before = test_file.read_text(encoding="utf-8")
    test_after = test_before.replace(
        "\n\nif __name__",
        '\n\n    def test_collapses_repeated_separators(self) -> None:\n'
        '        self.assertEqual(slugify("Hello   World"), "hello-world")\n\n'
        "if __name__",
    )
    payload = json.dumps(
        {
            "patches": [
                {"path": "slugify.py", "find": before, "replace": replacement},
                {"path": "test_slugify.py", "find": test_before, "replace": test_after},
            ]
        }
    )
    result = run_live_smoke(
        LiveSmokeConfig(
            case=SmokeCase.CODING,
            live=True,
            apply_coding_patch=True,
        ),
        provider=_provider([], content=payload),
        artifact_root=tmp_path / "artifacts",
    )

    assert result.details["validation"]["status"] == "passed"
    assert result.details["fixture_source_unchanged"] is True
    assert source_file.read_text(encoding="utf-8") == before
    assert not (tmp_path / ".hephaestus" / "hephaestus.db").exists()


def test_studio_provider_form_and_secret_behavior(tmp_path) -> None:
    repository = StudioExperienceRepository(tmp_path / "studio.db")
    created = repository.create_provider(
        StudioProviderUpsertRequest(
            provider_type="deepseek",
            name="DeepSeek",
            model="deepseek-v4-flash",
            base_url="https://api.deepseek.com",
            api_key="studio-secret",
            thinking_enabled=True,
            reasoning_effort="high",
            max_output_tokens=4096,
        )
    )

    assert created.configured is True
    assert created.thinking_enabled is True
    assert created.api_key_source == "Studio database"
    assert "studio-secret" not in created.model_dump_json()
    with sqlite3.connect(tmp_path / "studio.db") as connection:
        row = connection.execute(
            "SELECT reasoning_effort, max_output_tokens FROM studio_provider_configs"
        ).fetchone()
    assert row == ("high", 4096)


def test_studio_connection_success_uses_saved_model(tmp_path, monkeypatch) -> None:
    captured: list[dict[str, Any]] = []
    fake = _provider(captured)
    monkeypatch.setattr(urllib.request, "urlopen", fake._urlopen)
    repository = StudioExperienceRepository(tmp_path / "studio.db")
    created = repository.create_provider(
        StudioProviderUpsertRequest(
            provider_type="deepseek",
            name="DeepSeek",
            model="deepseek-v4-flash",
            base_url="https://api.deepseek.com",
            api_key="studio-secret",
        )
    )

    tested = repository.test_provider(created.id)

    assert tested is not None
    assert tested.status == StudioProviderStatus.CONNECTED
    assert tested.model == "deepseek-v4-flash"
    assert captured[0]["model"] == "deepseek-v4-flash"
    assert captured[0]["max_tokens"] == 4
    assert captured[0]["thinking"] == {"type": "enabled"}
    assert captured[0]["reasoning_effort"] == "high"


def test_deepseek_config_is_canonicalized_and_partial_edit_preserves_type(tmp_path) -> None:
    repository = StudioExperienceRepository(tmp_path / "studio.db")
    created = repository.create_provider(
        StudioProviderUpsertRequest(
            provider_type="openai-compatible",
            name="Legacy DeepSeek",
            model="deepseek-v4-flash",
            base_url="https://api.deepseek.com/",
            api_key="write-only",
        )
    )
    updated = repository.update_provider(
        created.id,
        StudioProviderPatchRequest(name="Renamed DeepSeek"),
    )

    assert created.provider_type == "deepseek"
    assert updated is not None
    assert updated.provider_type == "deepseek"
    assert updated.name == "Renamed DeepSeek"
    assert "write-only" not in updated.model_dump_json()
    assert repository.runtime_provider(created.id).name == "deepseek"  # type: ignore[union-attr]


def test_deepseek_migration_is_strict_and_audited_without_secret(tmp_path) -> None:
    database_path = tmp_path / "studio.db"
    repository = StudioExperienceRepository(database_path)
    matching = repository.create_provider(
        StudioProviderUpsertRequest(
            provider_type="openai-compatible",
            name="Will migrate",
            model="custom-model",
            base_url="https://example.test",
            api_key="never-log-this",
        )
    )
    custom = repository.create_provider(
        StudioProviderUpsertRequest(
            provider_type="openai-compatible",
            name="Custom",
            model="deepseek-v4-flash",
            base_url="https://proxy.example.test",
            api_key="another-secret",
        )
    )
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            UPDATE studio_provider_configs
            SET provider_type='openai-compatible', base_url='https://api.deepseek.com/v1',
                model='deepseek-v4-flash'
            WHERE id=?
            """,
            (matching.id,),
        )
        connection.execute("DELETE FROM schema_migrations WHERE version=20")
        connection.commit()

    migrated = StudioExperienceRepository(database_path)
    assert migrated.get_provider(matching.id).provider_type == "deepseek"  # type: ignore[union-attr]
    assert migrated.get_provider(custom.id).provider_type == "openai-compatible"  # type: ignore[union-attr]
    with sqlite3.connect(database_path) as connection:
        event = connection.execute(
            """
            SELECT provider_id, old_provider_type, new_provider_type, normalized_host, model
            FROM studio_provider_migration_events WHERE provider_id=?
            """,
            (matching.id,),
        ).fetchone()
        audit_text = "\n".join(
            str(row)
            for row in connection.execute(
                "SELECT * FROM studio_provider_migration_events"
            ).fetchall()
        )
    assert event == (
        matching.id,
        "openai-compatible",
        "deepseek",
        "api.deepseek.com",
        "deepseek-v4-flash",
    )
    assert "never-log-this" not in audit_text


def test_deepseek_zero_cost_metadata_migrates_without_overwriting_custom_prices(tmp_path) -> None:
    database_path = tmp_path / "studio.db"
    repository = StudioExperienceRepository(database_path)
    zero_cost = repository.create_provider(
        StudioProviderUpsertRequest(
            provider_type="deepseek",
            name="Zero cost",
            model="deepseek-v4-flash",
            base_url="https://api.deepseek.com",
            api_key="secret",
        )
    )
    custom = repository.create_provider(
        StudioProviderUpsertRequest(
            provider_type="deepseek",
            name="Custom cost",
            model="deepseek-v4-flash",
            base_url="https://api.deepseek.com",
            api_key="secret",
            input_cost_per_million=9.0,
            cached_input_cost_per_million=8.0,
            output_cost_per_million=7.0,
        )
    )
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            UPDATE studio_provider_configs
            SET input_cost_per_million=0, cached_input_cost_per_million=0,
                output_cost_per_million=0, pricing_metadata_source='', pricing_version=''
            WHERE id=?
            """,
            (zero_cost.id,),
        )
        _migrate_deepseek_pricing_metadata(connection)
        connection.commit()

    migrated = StudioExperienceRepository(database_path)
    migrated_zero = migrated.get_provider(zero_cost.id)
    migrated_custom = migrated.get_provider(custom.id)

    assert migrated_zero is not None
    assert migrated_zero.input_cost_per_million == 0.14
    assert migrated_zero.cached_input_cost_per_million == 0.0028
    assert migrated_zero.output_cost_per_million == 0.28
    assert migrated_zero.pricing_metadata_source == "provider-catalog:deepseek"
    assert migrated_custom is not None
    assert migrated_custom.input_cost_per_million == 9.0
    assert migrated_custom.cached_input_cost_per_million == 8.0
    assert migrated_custom.output_cost_per_million == 7.0


@pytest.mark.parametrize(
    ("failure", "expected_status"),
    [
        (
            urllib.error.HTTPError(
                "https://api.deepseek.com",
                401,
                "unauthorized",
                hdrs=None,
                fp=io.BytesIO(b"unauthorized"),
            ),
            StudioProviderStatus.CONNECTION_FAILED,
        ),
        (
            urllib.error.HTTPError(
                "https://api.deepseek.com",
                402,
                "payment required",
                hdrs=None,
                fp=io.BytesIO(b"insufficient balance"),
            ),
            StudioProviderStatus.INSUFFICIENT_BALANCE,
        ),
        (
            urllib.error.HTTPError(
                "https://api.deepseek.com",
                400,
                "bad request",
                hdrs=None,
                fp=io.BytesIO(b"invalid model"),
            ),
            StudioProviderStatus.CONNECTION_FAILED,
        ),
        (TimeoutError(), StudioProviderStatus.CONNECTION_FAILED),
    ],
)
def test_studio_connection_failure_states(
    tmp_path,
    monkeypatch,
    failure: Exception,
    expected_status: StudioProviderStatus,
) -> None:
    def failing(request: urllib.request.Request, *, timeout: float) -> FakeResponse:
        raise failure

    monkeypatch.setattr(urllib.request, "urlopen", failing)
    repository = StudioExperienceRepository(tmp_path / "studio.db")
    created = repository.create_provider(
        StudioProviderUpsertRequest(
            provider_type="deepseek",
            name="DeepSeek",
            api_key="studio-secret",
        )
    )

    tested = repository.test_provider(created.id)

    assert tested is not None
    assert tested.status == expected_status
    assert "studio-secret" not in tested.model_dump_json()
