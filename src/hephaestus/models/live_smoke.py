"""Budgeted, isolated live-provider smoke orchestration."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from time import perf_counter
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from hephaestus.conversation import (
    ConversationRequest,
    ConversationResponse,
    ConversationService,
    ConversationSession,
    DeliberationMode,
)
from hephaestus.conversation.repository import ConversationRepository
from hephaestus.models.base import ModelProvider, ModelRequest, ModelResponse
from hephaestus.models.deepseek import DeepSeekProvider
from hephaestus.repo import inspect_repository
from hephaestus.studio.experience import StudioExperienceRepository

CONVERSATION_PROMPT = """Explain what Hephaestus is trying to become, what already works,
and what its biggest unproven assumption is.

Do not modify files."""

REPO_READ_PROMPT = """Inspect the selected repository without modifying it.

Identify:
1. the main entry point,
2. where model providers are implemented,
3. where the coding loop is implemented,
4. the validation path,
5. one likely architectural risk.

Reference exact file paths."""

CODING_PROMPT = """Fix slugify so repeated separators collapse into one,
leading and trailing separators are removed,
and existing behavior remains intact.

Add focused tests.
Do not add dependencies.
Run the relevant tests."""


class SmokeCase(StrEnum):
    CONNECTION = "connection"
    CONVERSATION = "conversation"
    REPO_READ = "repo-read"
    CODING = "coding"


class LiveSmokeConfig(BaseModel):
    """Safe limits and isolation controls for one smoke run."""

    model_config = ConfigDict(frozen=True)

    case: SmokeCase = SmokeCase.CONNECTION
    live: bool = False
    repo_path: Path = Path(".")
    max_calls: int = Field(default=3, ge=1)
    max_output_tokens: int = Field(default=4096, ge=1)
    estimated_cost_cap: float = Field(default=0.05, gt=0)
    keep_workspace: bool = False
    apply_coding_patch: bool = False


class LiveSmokeResult(BaseModel):
    """Redacted smoke result safe to print or persist."""

    model_config = ConfigDict(frozen=True)

    smoke_id: str
    case: SmokeCase
    live: bool
    provider: str
    model: str
    base_url: str
    api_key_source: str
    calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cached_input_tokens: int = 0
    estimated_cost: float = 0.0
    conservative_preflight_estimate: float = 0.0
    elapsed_seconds: float = 0.0
    result: str
    workspace_status: str
    workspace_path: str | None = None
    artifact_path: str | None = None
    details: dict[str, Any] = Field(default_factory=dict)


class _CallBudget:
    def __init__(self, config: LiveSmokeConfig, provider: DeepSeekProvider) -> None:
        self.config = config
        self.provider = provider
        self.calls = 0
        self.input_tokens = 0
        self.output_tokens = 0
        self.cached_input_tokens = 0
        self.estimated_cost = 0.0

    def conservative_estimate(self, *, input_tokens_per_call: int = 20_000) -> float:
        profile = self.provider.profiles()[0]
        return self.config.max_calls * profile.estimated_cost(
            input_tokens_per_call,
            self.config.max_output_tokens,
        )

    def complete(self, request: ModelRequest) -> ModelResponse:
        if self.calls >= self.config.max_calls:
            raise RuntimeError("Live smoke provider call limit reached.")
        if self.estimated_cost >= self.config.estimated_cost_cap:
            raise RuntimeError("Estimated cost cap reached before the next provider call.")
        estimated_input = max(1, len(request.prompt) // 4)
        profile = self.provider.profiles()[0]
        projected = profile.estimated_cost(estimated_input, request.max_output_tokens)
        if self.estimated_cost + projected > self.config.estimated_cost_cap:
            raise RuntimeError(
                "Conservative next-call estimate would exceed the configured cost cap."
            )
        self.calls += 1
        response = self.provider.complete(request)
        self.input_tokens += response.input_tokens
        self.output_tokens += response.output_tokens
        self.cached_input_tokens += response.cached_input_tokens
        self.estimated_cost += response.estimated_cost
        return response


def run_live_smoke(
    config: LiveSmokeConfig,
    *,
    provider: DeepSeekProvider | None = None,
    artifact_root: Path | None = None,
) -> LiveSmokeResult:
    """Run one smoke case, or return its network-free preflight."""

    selected = provider or DeepSeekProvider()
    profile = selected.profiles()[0]
    smoke_id = f"deepseek-smoke-{uuid4().hex[:12]}"
    budget = _CallBudget(config, selected)
    preflight = budget.conservative_estimate()
    common = {
        "smoke_id": smoke_id,
        "case": config.case,
        "provider": selected.name,
        "model": profile.model,
        "base_url": selected.base_url or "",
        "api_key_source": "DEEPSEEK_API_KEY" if selected.api_key else "not configured",
        "conservative_preflight_estimate": preflight,
    }
    if not config.live:
        return LiveSmokeResult(
            **common,
            live=False,
            result="dry-run: no network request performed",
            workspace_status="not created",
            details={
                "maximum_provider_requests": config.max_calls,
                "maximum_output_tokens": config.max_output_tokens,
                "estimated_cost_cap": config.estimated_cost_cap,
                "thinking_enabled": selected.thinking_enabled,
                "reasoning_effort": selected.reasoning_effort,
            },
        )
    if not selected.is_available:
        raise RuntimeError("DeepSeek is not configured. Set DEEPSEEK_API_KEY.")

    started = perf_counter()
    workspace = Path(tempfile.mkdtemp(prefix="hephaestus-deepseek-smoke-"))
    smoke_db = workspace / "smoke.db"
    artifact_dir = artifact_root or Path.cwd() / ".hephaestus" / "smoke-artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = artifact_dir / f"{smoke_id}.json"
    details: dict[str, Any] = {
        "database_isolated": True,
        "raw_reasoning_persisted": False,
        "maximum_provider_requests": config.max_calls,
        "maximum_output_tokens": config.max_output_tokens,
        "estimated_cost_cap": config.estimated_cost_cap,
    }
    result_label = "failed"
    try:
        if config.case == SmokeCase.CONNECTION:
            connection_response = budget.complete(
                ModelRequest(
                    prompt="Reply OK.",
                    model=profile.model,
                    max_output_tokens=min(8, config.max_output_tokens),
                    thinking_enabled=False,
                )
            )
            result_label = (
                "connected"
                if connection_response.text.strip()
                else "connected (empty content)"
            )
        elif config.case == SmokeCase.CONVERSATION:
            conversation_response = _conversation_smoke(selected, budget, smoke_db)
            details.update(
                {
                    "conversation_persisted": True,
                    "provider_model": conversation_response.provider_model,
                    "usage_recorded": True,
                }
            )
            result_label = "conversation response persisted"
        elif config.case == SmokeCase.REPO_READ:
            repo_details = _repo_read_smoke(
                selected,
                budget,
                smoke_db,
                config.repo_path.resolve(),
            )
            details.update(repo_details)
            result_label = "repository response persisted and paths checked"
        else:
            coding_details = _coding_smoke(
                selected,
                budget,
                smoke_db,
                workspace,
                apply_patch=config.apply_coding_patch,
            )
            details.update(coding_details)
            result_label = (
                "coding patch applied and validated"
                if config.apply_coding_patch
                else "coding proposal saved; patch not applied"
            )
    except Exception:
        failed_artifact = {
            "smoke_id": smoke_id,
            "case": config.case.value,
            "provider": selected.name,
            "model": profile.model,
            "calls": budget.calls,
            "input_tokens": budget.input_tokens,
            "output_tokens": budget.output_tokens,
            "cached_input_tokens": budget.cached_input_tokens,
            "estimated_cost": budget.estimated_cost,
            "result": "failed",
            "details": {
                **details,
                "error": "Smoke execution failed; see the sanitized CLI error.",
            },
            "created_at": datetime.now(UTC).isoformat(),
        }
        artifact_path.write_text(
            json.dumps(failed_artifact, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        if not config.keep_workspace:
            shutil.rmtree(workspace, ignore_errors=True)
        raise
    finally:
        elapsed = perf_counter() - started

    artifact = {
        "smoke_id": smoke_id,
        "case": config.case.value,
        "provider": selected.name,
        "model": profile.model,
        "calls": budget.calls,
        "input_tokens": budget.input_tokens,
        "output_tokens": budget.output_tokens,
        "cached_input_tokens": budget.cached_input_tokens,
        "estimated_cost": budget.estimated_cost,
        "result": result_label,
        "details": details,
        "created_at": datetime.now(UTC).isoformat(),
    }
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True), encoding="utf-8")
    kept = config.keep_workspace
    result = LiveSmokeResult(
        **common,
        live=True,
        calls=budget.calls,
        input_tokens=budget.input_tokens,
        output_tokens=budget.output_tokens,
        cached_input_tokens=budget.cached_input_tokens,
        estimated_cost=budget.estimated_cost,
        elapsed_seconds=elapsed,
        result=result_label,
        workspace_status="kept" if kept else "deleted",
        workspace_path=str(workspace) if kept else None,
        artifact_path=str(artifact_path),
        details=details,
    )
    if not kept:
        shutil.rmtree(workspace, ignore_errors=True)
    return result


def _conversation_smoke(
    provider: ModelProvider,
    budget: _CallBudget,
    database_path: Path,
) -> ConversationResponse:
    metered = _MeteredProvider(provider, budget)
    service = ConversationService(database_path, provider=metered)
    session = _smoke_session(database_path, "conversation")
    response = service.respond(
        ConversationRequest(
            prompt=CONVERSATION_PROMPT,
            mode=DeliberationMode.DIRECT,
            provider="deepseek",
            session_id=session.id,
            save_memory=False,
            output_token_budget=budget.config.max_output_tokens,
        )
    )
    if budget.calls != 1 or not response.provider_success:
        raise RuntimeError("Configured provider did not complete the conversation smoke request.")
    StudioExperienceRepository(database_path).record_conversation_usage(
        conversation_id=response.session_id,
        message_id=response.message_id,
        provider_model=response.provider_model,
        estimated_input_tokens=response.input_tokens,
        estimated_output_tokens=response.output_tokens,
        estimated_cost=response.estimated_cost,
        context_trimmed=response.budget.context_trimmed,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        cached_input_tokens=response.cached_input_tokens,
        thinking_enabled=response.thinking_enabled,
        reasoning_effort=response.reasoning_effort,
        task_type="smoke:conversation",
    )
    return response


def _repo_read_smoke(
    provider: ModelProvider,
    budget: _CallBudget,
    database_path: Path,
    repo_path: Path,
) -> dict[str, Any]:
    if not repo_path.is_dir():
        raise NotADirectoryError(f"Repository path is not a directory: {repo_path}")
    before = _workspace_digest(repo_path)
    report = inspect_repository(repo_path)
    manifest = _repo_manifest(repo_path)
    prompt = (
        f"{REPO_READ_PROMPT}\n\n"
        "The orchestration layer collected this repository manifest. Cite only these paths:\n"
        + "\n".join(f"- {path}" for path in manifest)
    )
    metered = _MeteredProvider(provider, budget)
    service = ConversationService(database_path, provider=metered)
    session = _smoke_session(database_path, "repo-read")
    response = service.respond(
        ConversationRequest(
            prompt=prompt,
            mode=DeliberationMode.DIRECT,
            provider="deepseek",
            session_id=session.id,
            repo_path=repo_path,
            save_memory=False,
            output_token_budget=budget.config.max_output_tokens,
        )
    )
    if budget.calls != 1 or not response.provider_success:
        raise RuntimeError("Configured provider did not complete the repository smoke request.")
    StudioExperienceRepository(database_path).record_conversation_usage(
        conversation_id=response.session_id,
        message_id=response.message_id,
        provider_model=response.provider_model,
        estimated_input_tokens=response.input_tokens,
        estimated_output_tokens=response.output_tokens,
        estimated_cost=response.estimated_cost,
        context_trimmed=response.budget.context_trimmed,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        cached_input_tokens=response.cached_input_tokens,
        thinking_enabled=response.thinking_enabled,
        reasoning_effort=response.reasoning_effort,
        task_type="smoke:repo-read",
    )
    after = _workspace_digest(repo_path)
    referenced = _referenced_paths(response.answer, manifest)
    invalid = [path for path in referenced if path not in set(manifest)]
    if before != after:
        raise RuntimeError("Repository changed during read-only smoke.")
    if invalid:
        raise RuntimeError(f"Provider referenced paths outside the repository manifest: {invalid}")
    if not referenced:
        raise RuntimeError("Provider response did not reference an existing repository path.")
    return {
        "repo_context_passed": True,
        "repo_profile": report.profile.name,
        "manifest_path_count": len(manifest),
        "referenced_paths": referenced,
        "files_modified": False,
        "response_sha256": hashlib.sha256(response.answer.encode()).hexdigest(),
        "usage_recorded": True,
    }


def _coding_smoke(
    provider: ModelProvider,
    budget: _CallBudget,
    database_path: Path,
    smoke_workspace: Path,
    *,
    apply_patch: bool,
) -> dict[str, Any]:
    source = Path(__file__).resolve().parents[1] / "fixtures" / "slugify_smoke"
    fixture = smoke_workspace / "slugify-fixture"
    shutil.copytree(source, fixture)
    source_digest = _workspace_digest(source)
    prompt = "\n\n".join(
        [
            CODING_PROMPT,
            "Return JSON only: {\"patches\":[{\"path\":\"...\",\"find\":\"...\",\"replace\":\"...\"}]}",
            "Every find string must exactly match current file content. Allowed files: "
            "slugify.py, test_slugify.py.",
            *[
                f"FILE {path.name}\n```\n{path.read_text(encoding='utf-8')}\n```"
                for path in (fixture / "slugify.py", fixture / "test_slugify.py")
            ],
        ]
    )
    response = budget.complete(
        ModelRequest(
            prompt=prompt,
            max_output_tokens=budget.config.max_output_tokens,
            require_json=True,
        )
    )
    StudioExperienceRepository(database_path).record_conversation_usage(
        conversation_id=None,
        message_id=None,
        provider_model=response.model,
        estimated_input_tokens=response.input_tokens,
        estimated_output_tokens=response.output_tokens,
        estimated_cost=response.estimated_cost,
        context_trimmed=False,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        cached_input_tokens=response.cached_input_tokens,
        thinking_enabled=response.thinking_enabled,
        reasoning_effort=response.reasoning_effort,
        task_type="smoke:coding",
    )
    patches = _parse_coding_patches(response.text, fixture)
    diff_lines: list[str] = []
    for patch in patches:
        target = fixture / patch["path"]
        old = target.read_text(encoding="utf-8")
        new = old.replace(patch["find"], patch["replace"], 1)
        diff_lines.append(f"--- a/{patch['path']}\n+++ b/{patch['path']}")
        diff_lines.append(f"-{patch['find']}\n+{patch['replace']}")
        if apply_patch:
            target.write_text(new, encoding="utf-8")
    validation: dict[str, Any] = {
        "status": "not_run",
        "command": f"{sys.executable} -m unittest discover -s . -p test_*.py",
    }
    if apply_patch:
        completed = subprocess.run(
            [sys.executable, "-m", "unittest", "discover", "-s", ".", "-p", "test_*.py"],
            cwd=fixture,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        validation = {
            "status": "passed" if completed.returncode == 0 else "failed",
            "command": f"{sys.executable} -m unittest discover -s . -p test_*.py",
            "return_code": completed.returncode,
        }
        if completed.returncode != 0:
            raise RuntimeError("Disposable fixture validation failed.")
    if _workspace_digest(source) != source_digest:
        raise RuntimeError("Source fixture changed during coding smoke.")
    return {
        "plan": {
            "task": CODING_PROMPT,
            "allowed_files": ["slugify.py", "test_slugify.py"],
            "dependencies_allowed": False,
        },
        "diff": "\n".join(diff_lines),
        "validation": validation,
        "outcome": "proposal" if not apply_patch else "validated_success",
        "fixture_source_unchanged": True,
        "normal_database_used": False,
        "database_path": database_path.name,
        "usage_recorded": True,
    }


class _MeteredProvider:
    """ModelProvider adapter that applies one shared smoke call budget."""

    def __init__(self, provider: ModelProvider, budget: _CallBudget) -> None:
        self._provider = provider
        self._budget = budget

    @property
    def name(self) -> str:
        return self._provider.name

    @property
    def is_available(self) -> bool:
        return self._provider.is_available

    def profiles(self) -> Any:
        return self._provider.profiles()

    def complete(self, request: ModelRequest) -> ModelResponse:
        return self._budget.complete(request)


def _parse_coding_patches(text: str, workspace: Path) -> list[dict[str, str]]:
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        raise ValueError("Coding response did not contain a JSON object.")
    loaded = json.loads(text[start : end + 1])
    raw_patches = loaded.get("patches", [])
    if not isinstance(raw_patches, list) or not raw_patches:
        raise ValueError("Coding response did not contain patches.")
    patches: list[dict[str, str]] = []
    allowed = {"slugify.py", "test_slugify.py"}
    for raw in raw_patches:
        if not isinstance(raw, dict):
            raise ValueError("Coding patch must be an object.")
        patch = {key: str(raw.get(key, "")) for key in ("path", "find", "replace")}
        if patch["path"] not in allowed or not patch["find"] or not patch["replace"]:
            raise ValueError("Coding patch is outside the bounded fixture contract.")
        current = (workspace / patch["path"]).read_text(encoding="utf-8")
        if patch["find"] not in current:
            raise ValueError("Coding patch find text does not match the fixture.")
        if "import " in patch["replace"] and patch["path"] == "slugify.py":
            imports = set(re.findall(r"^import\s+\w+", patch["replace"], flags=re.MULTILINE))
            if imports - {"import re"}:
                raise ValueError("Coding patch attempted to add a dependency.")
        patches.append(patch)
    return patches


def _repo_manifest(root: Path) -> list[str]:
    ignored = {".git", ".venv", "node_modules", "__pycache__", ".hephaestus"}
    paths = [
        str(path.relative_to(root)).replace("\\", "/")
        for path in root.rglob("*")
        if path.is_file() and not any(part in ignored for part in path.relative_to(root).parts)
    ]
    return sorted(paths)[:500]


def _referenced_paths(answer: str, manifest: list[str]) -> list[str]:
    normalized = answer.replace("\\", "/")
    return [path for path in manifest if path in normalized]


def _workspace_digest(root: Path) -> str:
    digest = hashlib.sha256()
    ignored = {".git", ".hephaestus", "__pycache__", ".pytest_cache", ".mypy_cache"}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or any(part in ignored for part in path.relative_to(root).parts):
            continue
        digest.update(str(path.relative_to(root)).replace("\\", "/").encode())
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _smoke_session(database_path: Path, case: str) -> ConversationSession:
    session = ConversationSession(
        title=f"[deepseek-smoke] {case}",
        metadata={"namespace": "deepseek-live-smoke", "case": case},
    )
    return ConversationRepository(database_path).create_session(session)
