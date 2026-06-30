"""Runner utilities shared without adding agentic behavior to bare arms."""

from __future__ import annotations

import json
from hashlib import sha256
from pathlib import Path
from typing import Any

from benchmarks.harness_gain.schemas import FailureCode, ProviderUsage, RunnerResult
from hephaestus.coding_loop.operations import apply_manifest
from hephaestus.coding_loop.schemas import OperationManifest
from hephaestus.models import ModelProvider
from hephaestus.studio.experience import StudioExperienceRepository


def resolve_deepseek_provider() -> ModelProvider:
    repository = StudioExperienceRepository()
    for config in repository.list_providers().providers:
        if (
            config.provider_type == "deepseek"
            and config.model == "deepseek-v4-flash"
            and config.base_url.rstrip("/") == "https://api.deepseek.com"
        ):
            provider = repository.runtime_provider(config.id)
            if provider is not None:
                return provider
    raise RuntimeError("Canonical Studio DeepSeek provider is not configured.")


def repository_snapshot(root: Path) -> str:
    sections: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".git" in path.parts or path.name == "hephaestus.db":
            continue
        relative = path.relative_to(root).as_posix()
        content = path.read_text(encoding="utf-8", errors="replace")
        digest = sha256(path.read_bytes()).hexdigest()
        sections.append(f"--- FILE: {relative}\nSHA256: {digest}\n{content}\n--- END FILE")
    return "\n\n".join(sections) if sections else "(empty repository)"


def parse_manifest(text: str) -> OperationManifest:
    return OperationManifest.model_validate_json(text)


def apply_bare_manifest(root: Path, text: str, usage: ProviderUsage) -> RunnerResult:
    try:
        manifest = parse_manifest(text)
    except Exception as error:  # noqa: BLE001 - classify strict provider format
        return RunnerResult(
            failure_code=FailureCode.FORMAT_FAILURE,
            failure_detail=str(error),
            usage=usage,
            session_export={"parse_status": "invalid"},
        )
    try:
        apply_manifest(root, manifest)
    except PermissionError as error:
        return RunnerResult(
            failure_code=FailureCode.PERMISSION_FAILURE,
            failure_detail=str(error),
            usage=usage,
            session_export={"manifest": manifest.model_dump(mode="json")},
        )
    except Exception as error:  # noqa: BLE001 - manifest application taxonomy
        return RunnerResult(
            failure_code=FailureCode.MANIFEST_FAILURE,
            failure_detail=str(error),
            usage=usage,
            session_export={"manifest": manifest.model_dump(mode="json")},
        )
    return RunnerResult(
        declared_success=True,
        usage=usage,
        session_export={"manifest": manifest.model_dump(mode="json")},
    )


def usage_from_responses(responses: list[Any], *, repair_calls: int = 0) -> ProviderUsage:
    return ProviderUsage(
        logical_provider_calls=len(responses),
        transport_attempts=sum(max(1, len(item.transport_attempts)) for item in responses),
        input_tokens=sum(item.input_tokens for item in responses),
        cached_tokens=sum(item.cached_input_tokens for item in responses),
        output_tokens=sum(item.output_tokens for item in responses),
        estimated_cost=sum(item.estimated_cost for item in responses),
        repair_calls=repair_calls,
    )


def json_object(text: str) -> dict[str, Any]:
    parsed = json.loads(text)
    if not isinstance(parsed, dict):
        raise ValueError("Expected a JSON object.")
    return parsed

