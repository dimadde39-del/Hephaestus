"""Provider-backed structured planning and manifest preparation."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel

from hephaestus.coding_loop.planner import CodingPlanner
from hephaestus.coding_loop.provider_contract import (
    StructuredParseFailure,
    format_repair_prompt,
    parse_structured_response,
    provider_contract_system_prompt,
)
from hephaestus.coding_loop.repository import CodingLoopRepository
from hephaestus.coding_loop.schemas import (
    CodingBudget,
    CodingChangeProposal,
    CodingPatchSet,
    CodingRisk,
    CodingScopeType,
    CodingTaskIntent,
    CodingWorkflowMode,
    OperationManifest,
    ProviderProjectPlan,
)
from hephaestus.conversation.providers import list_conversation_providers
from hephaestus.models import (
    DeepSeekProvider,
    FakeModelProvider,
    ModelProvider,
    ModelRequest,
    ProviderRequestError,
)
from hephaestus.models.base import ModelResponse
from hephaestus.storage.sqlite import connect_database


class CodingProviderError(RuntimeError):
    pass


class GreenfieldCodingExecutor:
    def __init__(
        self,
        database_path: Path | str | None = None,
        *,
        provider_override: ModelProvider | None = None,
        provider_source: str = "injected",
    ) -> None:
        self.repository = CodingLoopRepository(database_path)
        self.database_path = self.repository.database_path
        self.planner = CodingPlanner(self.database_path)
        self.provider_override = provider_override
        self.provider_source = provider_source

    def plan(
        self,
        user_request: str,
        *,
        repo_path: Path | str,
        provider: str = "auto",
        workflow_mode: CodingWorkflowMode = CodingWorkflowMode.PLAN,
        max_calls: int = 3,
        max_network_attempts: int | None = None,
        max_format_repair_calls: int = 1,
        max_output_tokens: int = 4096,
        estimated_cost_cap: float = 0.05,
    ) -> tuple[Any, Any]:
        request, base_plan = self.planner.plan(
            user_request,
            repo_path=repo_path,
            provider=provider,
        )
        intent = classify_task_intent(user_request, Path(repo_path), workflow_mode)
        budget = CodingBudget(
            max_calls=max_calls,
            max_network_attempts=max_network_attempts or max_calls * 2,
            max_format_repair_calls=max_format_repair_calls,
            max_output_tokens=max_output_tokens,
            estimated_cost_cap=estimated_cost_cap,
        )
        selected, source = self._resolve_provider(provider)
        project_plan, response, budget = self._project_plan(
            selected,
            source,
            request.id,
            user_request,
            Path(repo_path),
            intent,
            budget,
        )
        request = request.model_copy(
            update={
                "provider": provider,
                "task_intent": intent,
                "workflow_mode": workflow_mode,
                "budget": budget,
                "metadata": {
                    **request.metadata,
                    "provider_source": source,
                    "provider_name": selected.name,
                    "provider_model": response.model,
                },
                "updated_at": datetime.now(UTC),
            }
        )
        self.repository.create_coding_request(request)
        expected = [item.path for item in project_plan.proposed_files]
        plan = base_plan.model_copy(
            update={
                "summary": project_plan.task_summary,
                "likely_files": expected,
                "validation_commands": project_plan.validation_commands,
                "patch_proposal_possible": True,
                "scope_too_large": False,
                "provider_plan": project_plan,
                "provider_name": selected.name,
                "provider_model": response.model,
                "provider_source": source,
                "budget": budget,
                "scope": base_plan.scope.model_copy(
                    update={
                        "scope_type": (
                            CodingScopeType.GREENFIELD
                            if intent == CodingTaskIntent.GREENFIELD_PROJECT
                            else base_plan.scope.scope_type
                        ),
                        "risk": CodingRisk.MEDIUM,
                        "likely_files": expected,
                        "too_large": False,
                    }
                ),
                "updated_at": datetime.now(UTC),
            }
        )
        self.repository.save_plan(plan)
        return request, plan

    def prepare(self, plan_id: str, *, approved: bool) -> CodingChangeProposal:
        if not approved:
            raise PermissionError("Plan approval is required before manifest generation.")
        plan = self.repository.get_plan(plan_id)
        if plan is None:
            raise ValueError(f"Coding plan not found: {plan_id}")
        request = self.repository.get_request(plan.request_id)
        if request is None:
            raise ValueError(f"Coding request not found: {plan.request_id}")
        selected, source = self._resolve_provider(request.provider)
        prompt = _manifest_prompt(plan.provider_plan, Path(plan.repo_path))
        manifest, response, budget = self._structured_completion(
            provider=selected,
            source=source,
            request_id=request.id,
            stage="manifest",
            prompt=prompt,
            budget=request.budget,
            schema=OperationManifest,
            label="manifest",
        )
        request = request.model_copy(update={"budget": budget, "updated_at": datetime.now(UTC)})
        self.repository.create_coding_request(request)
        change = CodingChangeProposal(
            request_id=request.id,
            plan_id=plan.id,
            repo_path=plan.repo_path,
            repo_profile_id=plan.repo_profile_id,
            active_policy_profile=plan.active_policy_profile,
            summary=manifest.task_summary,
            risk=CodingRisk.MEDIUM,
            scope_type=plan.scope.scope_type,
            patch_set=CodingPatchSet(files_touched=_manifest_files(manifest)),
            validation_commands=manifest.validation_commands,
            checkpoint_plan=plan.checkpoint_plan,
            manifest=manifest,
            metadata={
                "provider": selected.name,
                "provider_model": response.model,
                "provider_source": source,
                "budget": budget.model_dump(mode="json"),
            },
        )
        return self.repository.save_change_proposal(change)

    def _project_plan(
        self,
        provider: ModelProvider,
        source: str,
        request_id: str,
        task: str,
        root: Path,
        intent: CodingTaskIntent,
        budget: CodingBudget,
    ) -> tuple[ProviderProjectPlan, ModelResponse, CodingBudget]:
        if provider.name == "fake":
            plan = ProviderProjectPlan(
                task_summary=f"Deterministic simulation plan for: {task.strip()[:160]}",
                architecture=["Local simulation does not invent implementation files."],
                proposed_files=[],
                implementation_approach=["Choose a real coding provider to generate a manifest."],
                tests=[],
                validation_commands=[],
                assumptions=["No network provider was selected."],
                risks=["Simulation cannot implement arbitrary code."],
            )
            response = ModelResponse(
                text=plan.model_dump_json(),
                model="local/fake-structured",
                input_tokens=max(1, len(task) // 4),
                output_tokens=max(1, len(plan.model_dump_json()) // 4),
                estimated_cost=0,
            )
            self._record_call(request_id, "plan", provider, source, response, True, "")
            return plan, response, _updated_budget(budget, response)
        prompt = _plan_prompt(task, root, intent)
        plan, response, budget = self._structured_completion(
            provider=provider,
            source=source,
            request_id=request_id,
            stage="plan",
            prompt=prompt,
            budget=budget,
            schema=ProviderProjectPlan,
            label="plan",
        )
        return plan, response, budget

    def _structured_completion(
        self,
        *,
        provider: ModelProvider,
        source: str,
        request_id: str,
        stage: str,
        prompt: str,
        budget: CodingBudget,
        schema: type[BaseModel],
        label: str,
    ) -> tuple[Any, ModelResponse, CodingBudget]:
        response = self._complete(
            provider,
            source,
            request_id,
            stage,
            prompt,
            budget,
            schema=schema,
            label=label,
        )
        budget = _updated_budget(budget, response)
        try:
            parsed = parse_structured_response(response.text, schema, label)
            self._record_contract_event(request_id, stage, provider, source, response, parsed.status, [])
            return parsed.value, response, budget
        except StructuredParseFailure as failure:
            self._record_contract_failure(request_id, stage, provider, source, response, failure)
            if budget.format_repair_calls >= budget.max_format_repair_calls:
                raise CodingProviderError(f"{failure.failure_code}: {failure.message}") from failure
            repair_prompt = format_repair_prompt(
                schema=schema,
                label=label,
                original_content=response.text,
                failure=failure,
            )
            repair_response = self._complete(
                provider,
                source,
                request_id,
                f"{stage}_format_repair",
                repair_prompt,
                budget,
                schema=schema,
                label=label,
                max_output_tokens=min(budget.max_output_tokens, 2048 if label == "plan" else 4096),
                is_repair=True,
            )
            budget = _updated_budget(budget, repair_response, is_repair=True)
            try:
                parsed = parse_structured_response(repair_response.text, schema, label)
                self._record_contract_event(
                    request_id,
                    f"{stage}_format_repair",
                    provider,
                    source,
                    repair_response,
                    parsed.status,
                    [],
                )
                return parsed.value, repair_response, budget
            except StructuredParseFailure as repair_failure:
                self._record_contract_failure(
                    request_id,
                    f"{stage}_format_repair",
                    provider,
                    source,
                    repair_response,
                    repair_failure,
                )
                code = f"{label.upper()}_FORMAT_REPAIR_FAILED"
                raise CodingProviderError(f"{code}: {repair_failure.message}") from repair_failure

    def _complete(
        self,
        provider: ModelProvider,
        source: str,
        request_id: str,
        stage: str,
        prompt: str,
        budget: CodingBudget,
        *,
        schema: type[BaseModel],
        label: str,
        max_output_tokens: int | None = None,
        is_repair: bool = False,
    ) -> ModelResponse:
        if budget.calls >= budget.max_calls:
            raise CodingProviderError("Provider call budget exhausted.")
        remaining_attempts = budget.max_network_attempts - budget.transport_attempts
        if remaining_attempts <= 0:
            raise CodingProviderError("Provider network attempt budget exhausted.")
        profile = provider.profiles()[0]
        output_limit = max_output_tokens or budget.max_output_tokens
        projected = profile.estimated_cost(max(1, len(prompt) // 4), output_limit)
        if budget.estimated_cost + projected > budget.estimated_cost_cap:
            raise CodingProviderError("Estimated cost cap would be exceeded.")
        try:
            response = provider.complete(
                ModelRequest(
                    prompt=prompt,
                    system_prompt=provider_contract_system_prompt(schema, label),
                    max_output_tokens=output_limit,
                    require_json=True,
                    thinking_enabled=True,
                    reasoning_effort="high",
                    max_transport_attempts=min(2, remaining_attempts),
                    call_kind="format_repair" if is_repair else stage,
                )
            )
        except ProviderRequestError as error:
            self._record_call(
                request_id,
                stage,
                provider,
                source,
                None,
                False,
                error.code,
                timeout_type=error.timeout_type,
                attempts=[attempt.model_dump(mode="json") for attempt in error.attempts],
                raw={
                    "logical_call_kind": "format_repair" if is_repair else stage,
                    "transient": error.transient,
                    "status_code": error.status_code,
                },
            )
            raise
        except Exception as error:
            self._record_call(request_id, stage, provider, source, None, False, type(error).__name__)
            raise
        self._record_call(request_id, stage, provider, source, response, True, "")
        return response

    def _resolve_provider(self, requested: str) -> tuple[ModelProvider, str]:
        from hephaestus.studio.experience import StudioExperienceRepository

        if self.provider_override is not None:
            return self.provider_override, self.provider_source
        experience = StudioExperienceRepository(self.database_path)
        if requested.startswith("provider_"):
            selected = experience.runtime_provider(requested)
            if selected is None:
                raise CodingProviderError(f"Studio provider is unavailable: {requested}")
            return selected, f"studio:{requested}"
        if requested == "local":
            return FakeModelProvider(), "local"
        if requested == "deepseek":
            for config in experience.list_providers().providers:
                if config.provider_type == "deepseek":
                    selected = experience.runtime_provider(config.id)
                    if selected is not None:
                        return selected, f"studio:{config.id}"
            selected = DeepSeekProvider()
            if selected.is_available:
                return selected, "environment"
            raise CodingProviderError("DeepSeek provider is not configured.")
        default = experience.default_coding_provider()
        if default is not None:
            return default[0], f"studio:{default[1]}"
        real = [
            item
            for item in list_conversation_providers()
            if item.name != "fake" and item.is_available
        ]
        if real:
            return real[0], "environment"
        if requested == "real":
            raise CodingProviderError("A real coding provider is required but none is configured.")
        return FakeModelProvider(), "local-fallback"

    def _record_call(
        self,
        request_id: str,
        stage: str,
        provider: ModelProvider,
        source: str,
        response: ModelResponse | None,
        success: bool,
        error_code: str,
        *,
        timeout_type: str | None = None,
        attempts: list[dict[str, Any]] | None = None,
        raw: dict[str, Any] | None = None,
    ) -> None:
        model = response.model if response is not None else provider.profiles()[0].model
        content = response.text if response is not None else ""
        content_sha = sha256(content.encode("utf-8")).hexdigest() if content else ""
        response_attempts = (
            [attempt.model_dump(mode="json") for attempt in response.transport_attempts]
            if response is not None
            else attempts or []
        )
        latency_ms = sum(int(item.get("latency_ms", 0)) for item in response_attempts)
        raw_json = {
            "finish_reason": response.finish_reason if response is not None else None,
            "response_truncated": response.response_truncated if response is not None else False,
            "transport_attempts": response_attempts,
            "usage_source": response.usage_source if response is not None else "missing",
            "cost_metadata_source": (
                response.cost_metadata_source if response is not None else provider.profiles()[0].cost_metadata_source
            ),
            "pricing_version": (
                response.pricing_version if response is not None else provider.profiles()[0].pricing_version
            ),
            **(raw or {}),
        }
        call_id = f"coding_call_{uuid4().hex[:12]}"
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO coding_model_calls (
                    id, request_id, stage, provider, model, source, input_tokens,
                    output_tokens, cached_input_tokens, estimated_cost, success,
                    error_code, created_at, finish_reason, content_length, content_sha256,
                    timeout_type, latency_ms, cost_metadata_source, pricing_version,
                    transport_attempts_json, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    call_id,
                    request_id,
                    stage,
                    provider.name,
                    model,
                    source,
                    response.input_tokens if response else 0,
                    response.output_tokens if response else 0,
                    response.cached_input_tokens if response else 0,
                    response.estimated_cost if response else 0,
                    int(success),
                    error_code,
                    datetime.now(UTC).isoformat(),
                    (response.finish_reason or "") if response is not None else "",
                    len(content),
                    content_sha,
                    timeout_type or "",
                    latency_ms,
                    response.cost_metadata_source
                    if response is not None
                    else provider.profiles()[0].cost_metadata_source,
                    response.pricing_version
                    if response is not None and response.pricing_version is not None
                    else provider.profiles()[0].pricing_version or "",
                    json.dumps(response_attempts, ensure_ascii=False, separators=(",", ":")),
                    json.dumps(raw_json, ensure_ascii=False, separators=(",", ":")),
                ),
            )

    def _record_contract_event(
        self,
        request_id: str,
        stage: str,
        provider: ModelProvider,
        source: str,
        response: ModelResponse,
        parse_status: str,
        validation_errors: list[dict[str, Any]],
    ) -> None:
        self._record_contract_row(
            request_id=request_id,
            stage=f"{stage}_contract",
            provider=provider,
            source=source,
            response=response,
            success=True,
            error_code="",
            parse_status=parse_status,
            validation_errors=validation_errors,
        )

    def _record_contract_failure(
        self,
        request_id: str,
        stage: str,
        provider: ModelProvider,
        source: str,
        response: ModelResponse,
        failure: StructuredParseFailure,
    ) -> None:
        self._record_contract_row(
            request_id=request_id,
            stage=f"{stage}_contract",
            provider=provider,
            source=source,
            response=response,
            success=False,
            error_code=failure.failure_code,
            parse_status=failure.status,
            validation_errors=failure.validation_errors,
        )

    def _record_contract_row(
        self,
        *,
        request_id: str,
        stage: str,
        provider: ModelProvider,
        source: str,
        response: ModelResponse,
        success: bool,
        error_code: str,
        parse_status: str,
        validation_errors: list[dict[str, Any]],
    ) -> None:
        content = response.text
        content_sha = sha256(content.encode("utf-8")).hexdigest()
        raw_json = {
            "parse_status": parse_status,
            "validation_errors": validation_errors,
            "finish_reason": response.finish_reason,
            "response_truncated": response.response_truncated,
        }
        with connect_database(self.database_path) as connection:
            connection.execute(
                """
                INSERT INTO coding_model_calls (
                    id, request_id, stage, provider, model, source, input_tokens,
                    output_tokens, cached_input_tokens, estimated_cost, success,
                    error_code, created_at, finish_reason, content_length, content_sha256,
                    json_parse_status, validation_errors_json, latency_ms,
                    cost_metadata_source, pricing_version, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    f"coding_call_{uuid4().hex[:12]}",
                    request_id,
                    stage,
                    provider.name,
                    response.model,
                    source,
                    0,
                    0,
                    0,
                    0,
                    int(success),
                    error_code,
                    datetime.now(UTC).isoformat(),
                    response.finish_reason or "",
                    len(content),
                    content_sha,
                    parse_status,
                    json.dumps(validation_errors, ensure_ascii=False, separators=(",", ":")),
                    0,
                    response.cost_metadata_source,
                    response.pricing_version or "",
                    json.dumps(raw_json, ensure_ascii=False, separators=(",", ":")),
                ),
            )


def classify_task_intent(
    task: str,
    root: Path,
    workflow_mode: CodingWorkflowMode,
) -> CodingTaskIntent:
    lowered = task.lower()
    implementation_files = [
        path
        for path in root.rglob("*")
        if path.is_file()
        and ".git" not in path.parts
        and path.suffix.lower() in {".py", ".js", ".ts", ".tsx", ".go", ".rs", ".java"}
    ]
    if workflow_mode == CodingWorkflowMode.BUILD and not implementation_files:
        return CodingTaskIntent.GREENFIELD_PROJECT
    if any(term in lowered for term in ("создай", "new project", "greenfield")) and not implementation_files:
        return CodingTaskIntent.GREENFIELD_PROJECT
    if any(term in lowered for term in ("исправ", "fix", "bug")):
        return CodingTaskIntent.BUGFIX
    if any(term in lowered for term in ("test", "тест")):
        return CodingTaskIntent.TESTS
    if any(term in lowered for term in ("docs", "readme", "документ")):
        return CodingTaskIntent.DOCUMENTATION
    return CodingTaskIntent.FEATURE


def _updated_budget(
    budget: CodingBudget,
    response: ModelResponse,
    *,
    is_repair: bool = False,
) -> CodingBudget:
    return budget.model_copy(
        update={
            "calls": budget.calls + 1,
            "transport_attempts": budget.transport_attempts + len(response.transport_attempts),
            "format_repair_calls": budget.format_repair_calls + (1 if is_repair else 0),
            "input_tokens": budget.input_tokens + response.input_tokens,
            "output_tokens": budget.output_tokens + response.output_tokens,
            "cached_input_tokens": budget.cached_input_tokens + response.cached_input_tokens,
            "estimated_cost": budget.estimated_cost + response.estimated_cost,
            "cost_metadata_source": response.cost_metadata_source,
            "pricing_version": response.pricing_version,
        }
    )


def _plan_prompt(task: str, root: Path, intent: CodingTaskIntent) -> str:
    files = sorted(
        str(path.relative_to(root)).replace("\\", "/")
        for path in root.rglob("*")
        if path.is_file() and ".git" not in path.parts
    )[:200]
    return (
        "Return JSON only matching ProviderProjectPlan with keys task_summary, architecture, "
        "proposed_files[{path,purpose}], implementation_approach, tests, validation_commands, "
        "assumptions, risks. Do not include reasoning. "
        f"Intent: {intent.value}\nRepository files: {files}\nTask:\n{task}"
    )


def _manifest_prompt(plan: ProviderProjectPlan | None, root: Path) -> str:
    state: list[dict[str, Any]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".git" in path.parts:
            continue
        relative = str(path.relative_to(root)).replace("\\", "/")
        if path.stat().st_size <= 64 * 1024:
            state.append(
                {
                    "path": relative,
                    "sha256": __import__("hashlib").sha256(path.read_bytes()).hexdigest(),
                    "content": path.read_text(encoding="utf-8", errors="replace"),
                }
            )
    return (
        "Return JSON only matching OperationManifest. Operations are discriminated by operation: "
        "create, modify, delete, move. Use UTF-8 full content for creates. For modify use mode "
        "replace with content or unified_diff with unified_diff, and include expected_sha256. "
        "Do not touch .git, .hephaestus, secrets, or paths outside the repository. "
        f"Approved plan: {json.dumps(plan.model_dump(mode='json') if plan else {})}\n"
        f"Current repository: {json.dumps(state)}"
    )


def _manifest_files(manifest: OperationManifest) -> list[str]:
    result: list[str] = []
    for operation in manifest.operations:
        if hasattr(operation, "path"):
            result.append(operation.path)
        else:
            result.extend([operation.source_path, operation.destination_path])
    return list(dict.fromkeys(result))
