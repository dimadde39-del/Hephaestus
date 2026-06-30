"""Arm B: direct structured plan then direct manifest, without tools or feedback."""

from __future__ import annotations

from pathlib import Path

from benchmarks.harness_gain.runners.common import (
    apply_bare_manifest,
    repository_snapshot,
    resolve_deepseek_provider,
    usage_from_responses,
)
from benchmarks.harness_gain.schemas import FailureCode, RunnerResult
from hephaestus.coding_loop.schemas import OperationManifest, ProviderProjectPlan
from hephaestus.models import ModelProvider, ModelRequest, ProviderRequestError


def run(prompt: str, target: Path, provider: ModelProvider | None = None) -> RunnerResult:
    selected = provider or resolve_deepseek_provider()
    snapshot = repository_snapshot(target)
    responses = []
    try:
        plan_response = selected.complete(
            ModelRequest(
                prompt=f"TASK:\n{prompt}\n\nFULL REPOSITORY SNAPSHOT:\n{snapshot}",
                system_prompt=(
                    "Return exactly one JSON implementation plan, without markdown or tools. Schema: "
                    f"{ProviderProjectPlan.model_json_schema()}"
                ),
                max_output_tokens=4096,
                require_json=True,
                thinking_enabled=True,
                reasoning_effort="high",
                max_transport_attempts=2,
                call_kind="benchmark_bare_plan",
            )
        )
        responses.append(plan_response)
        plan = ProviderProjectPlan.model_validate_json(plan_response.text)
    except ProviderRequestError as error:
        return _provider_failure(error)
    except Exception as error:  # noqa: BLE001 - strict plan parser
        return RunnerResult(
            failure_code=FailureCode.PLAN_FAILURE,
            failure_detail=str(error),
            usage=usage_from_responses(responses),
        )
    try:
        manifest_response = selected.complete(
            ModelRequest(
                prompt=(
                    f"TASK:\n{prompt}\n\nFULL REPOSITORY SNAPSHOT:\n{snapshot}\n\n"
                    f"APPROVED IMPLEMENTATION PLAN:\n{plan.model_dump_json()}"
                ),
                system_prompt=(
                    "Return exactly one JSON file-operation manifest, without markdown or tools. "
                    f"Schema: {OperationManifest.model_json_schema()}"
                ),
                max_output_tokens=4096,
                require_json=True,
                thinking_enabled=True,
                reasoning_effort="high",
                max_transport_attempts=2,
                call_kind="benchmark_bare_manifest",
            )
        )
        responses.append(manifest_response)
    except ProviderRequestError as error:
        result = _provider_failure(error)
        result.usage = usage_from_responses(responses)
        return result
    usage = usage_from_responses(responses)
    result = apply_bare_manifest(target, manifest_response.text, usage)
    result.session_export["plan"] = plan.model_dump(mode="json")
    return result


def _provider_failure(error: ProviderRequestError) -> RunnerResult:
    code = FailureCode.PROVIDER_TIMEOUT if error.timeout_type else FailureCode.PROVIDER_COMPATIBILITY_FAILURE
    if error.status_code in {401, 403}:
        code = FailureCode.PROVIDER_AUTH_FAILURE
    return RunnerResult(failure_code=code, failure_detail=error.code)
