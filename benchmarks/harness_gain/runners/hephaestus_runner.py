"""Arm D: official Hephaestus structured coding flow."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from benchmarks.harness_gain.runners.common import resolve_deepseek_provider
from benchmarks.harness_gain.schemas import (
    FailureCode,
    ProviderUsage,
    RunnerResult,
    ValidationResult,
)
from hephaestus.coding_loop import CodingLoopExecutor
from hephaestus.coding_loop.greenfield import CodingProviderError, GreenfieldCodingExecutor
from hephaestus.coding_loop.schemas import CodingLoopStatus, CodingWorkflowMode
from hephaestus.models import ModelProvider, ProviderRequestError


def run(
    prompt: str,
    target: Path,
    runtime_root: Path,
    provider: ModelProvider | None = None,
) -> RunnerResult:
    runtime_root.mkdir(parents=True, exist_ok=True)
    database = runtime_root / "hephaestus-benchmark.db"
    selected = provider or resolve_deepseek_provider()
    greenfield = GreenfieldCodingExecutor(
        database,
        provider_override=selected,
        provider_source="benchmark-studio-deepseek",
    )
    try:
        request, plan = greenfield.plan(
            prompt,
            repo_path=target,
            provider="deepseek",
            workflow_mode=CodingWorkflowMode.BUILD,
            max_calls=3,
            max_network_attempts=6,
            max_format_repair_calls=0,
            max_output_tokens=4096,
            estimated_cost_cap=0.03,
        )
        change = greenfield.prepare(plan.id, approved=True)
        result = CodingLoopExecutor(
            database,
            provider_override=selected,
            provider_source="benchmark-studio-deepseek",
        ).apply_change(
            change.id,
            yes=True,
            rollback_on_failure=True,
            allow_one_repair=True,
            retain_failed_snapshot=True,
            artifact_root=runtime_root / "failed",
        )
    except ProviderRequestError as error:
        return RunnerResult(
            failure_code=_provider_code(error),
            failure_detail=error.code,
            usage=_read_usage(database),
        )
    except CodingProviderError as error:
        code = FailureCode.BUDGET_EXCEEDED if "budget" in str(error).lower() else FailureCode.FORMAT_FAILURE
        return RunnerResult(failure_code=code, failure_detail=str(error), usage=_read_usage(database))
    except (PermissionError, FileNotFoundError, ValueError) as error:
        return RunnerResult(
            failure_code=FailureCode.MANIFEST_FAILURE,
            failure_detail=str(error),
            usage=_read_usage(database),
        )
    hidden_target = target
    failed_snapshot = result.metadata.get("failed_snapshot")
    if isinstance(failed_snapshot, dict) and failed_snapshot.get("snapshot_path"):
        hidden_target = Path(str(failed_snapshot["snapshot_path"]))
    validation = ValidationResult(
        passed=result.validation.status == "passed",
        command="Hephaestus deterministic validation plan",
        exit_code=0 if result.validation.status == "passed" else 1,
        duration_seconds=0,
        stdout=result.validation.summary,
    )
    declared = result.status == CodingLoopStatus.COMPLETED
    return RunnerResult(
        declared_success=declared,
        failure_code=None if declared else FailureCode.VALIDATION_FAILURE,
        failure_detail="" if declared else result.summary,
        usage=_read_usage(database),
        hidden_target=hidden_target,
        self_validation=validation,
        session_export={
            "request_id": request.id,
            "plan_id": plan.id,
            "change_id": change.id,
            "result_id": result.id,
            "status": result.status.value,
            "provider": plan.provider_name,
            "model": plan.provider_model,
            "provider_source": plan.provider_source,
            "budget": _budget_export(database, request.id),
            "validation": result.validation.model_dump(mode="json"),
            "repair_attempted": result.metadata.get("repair_attempted", False),
            "repair_result": result.metadata.get("repair_result", "not_attempted"),
        },
    )


def _read_usage(database: Path) -> ProviderUsage:
    if not database.exists():
        return ProviderUsage()
    with sqlite3.connect(database) as connection:
        row = connection.execute(
            """
            SELECT COUNT(*), COALESCE(SUM(input_tokens), 0),
                   COALESCE(SUM(cached_input_tokens), 0), COALESCE(SUM(output_tokens), 0),
                   COALESCE(SUM(estimated_cost), 0), COALESCE(SUM(latency_ms >= 0), 0),
                   COALESCE(SUM(stage = 'validation_repair'), 0)
            FROM coding_model_calls
            WHERE stage NOT LIKE '%_contract'
            """
        ).fetchone()
        attempts = connection.execute(
            """
            SELECT transport_attempts_json FROM coding_model_calls
            WHERE stage NOT LIKE '%_contract'
            """
        ).fetchall()
    import json

    transport_attempts = sum(len(json.loads(item[0] or "[]")) for item in attempts)
    assert row is not None
    return ProviderUsage(
        logical_provider_calls=int(row[0]),
        transport_attempts=transport_attempts,
        input_tokens=int(row[1]),
        cached_tokens=int(row[2]),
        output_tokens=int(row[3]),
        estimated_cost=float(row[4]),
        repair_calls=int(row[6]),
    )


def _budget_export(database: Path, request_id: str) -> dict[str, object]:
    if not database.exists():
        return {}
    with sqlite3.connect(database) as connection:
        row = connection.execute(
            "SELECT raw_json FROM coding_requests WHERE id = ?",
            (request_id,),
        ).fetchone()
    if row is None:
        return {}
    import json

    return dict(json.loads(row[0]).get("budget", {}))


def _provider_code(error: ProviderRequestError) -> FailureCode:
    if error.status_code in {401, 403}:
        return FailureCode.PROVIDER_AUTH_FAILURE
    if error.timeout_type:
        return FailureCode.PROVIDER_TIMEOUT
    return FailureCode.PROVIDER_COMPATIBILITY_FAILURE
