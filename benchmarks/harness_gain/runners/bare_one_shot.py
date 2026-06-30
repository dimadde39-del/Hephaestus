"""Arm A: one direct provider call followed by strict manifest application."""

from __future__ import annotations

from pathlib import Path

from benchmarks.harness_gain.runners.common import (
    apply_bare_manifest,
    repository_snapshot,
    resolve_deepseek_provider,
    usage_from_responses,
)
from benchmarks.harness_gain.schemas import FailureCode, RunnerResult
from hephaestus.coding_loop.schemas import OperationManifest
from hephaestus.models import ModelProvider, ModelRequest, ProviderRequestError


def system_prompt() -> str:
    schema = OperationManifest.model_json_schema()
    return (
        "You are a one-shot coding model. Return exactly one JSON object matching this schema; "
        "no markdown, commentary, or tools. Use only CreateFile/create, ModifyFile/modify, "
        f"DeleteFile/delete, and MoveFile/move operations. Schema: {schema}"
    )


def run(prompt: str, target: Path, provider: ModelProvider | None = None) -> RunnerResult:
    selected = provider or resolve_deepseek_provider()
    request = ModelRequest(
        prompt=f"TASK:\n{prompt}\n\nFULL REPOSITORY SNAPSHOT:\n{repository_snapshot(target)}",
        system_prompt=system_prompt(),
        max_output_tokens=4096,
        require_json=True,
        thinking_enabled=True,
        reasoning_effort="high",
        max_transport_attempts=2,
        call_kind="benchmark_bare_one_shot",
    )
    try:
        response = selected.complete(request)
    except ProviderRequestError as error:
        code = FailureCode.PROVIDER_TIMEOUT if error.timeout_type else FailureCode.PROVIDER_COMPATIBILITY_FAILURE
        if error.status_code in {401, 403}:
            code = FailureCode.PROVIDER_AUTH_FAILURE
        return RunnerResult(failure_code=code, failure_detail=error.code)
    usage = usage_from_responses([response])
    result = apply_bare_manifest(target, response.text, usage)
    result.session_export["finish_reason"] = response.finish_reason
    result.session_export["response_truncated"] = response.response_truncated
    return result

