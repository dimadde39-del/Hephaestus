from __future__ import annotations

import hashlib
import io
import json
import subprocess
import urllib.request
from pathlib import Path
from typing import Any

import pytest

from hephaestus.coding_loop.executor import CodingLoopExecutor
from hephaestus.coding_loop.greenfield import (
    CodingProviderError,
    GreenfieldCodingExecutor,
    classify_task_intent,
)
from hephaestus.coding_loop.operations import apply_manifest, preflight_manifest
from hephaestus.coding_loop.provider_contract import (
    StructuredParseFailure,
    parse_structured_response,
)
from hephaestus.coding_loop.renderer import _cost_text
from hephaestus.coding_loop.schemas import (
    CodingTaskIntent,
    CodingWorkflowMode,
    CreateFile,
    DeleteFile,
    ModifyFile,
    MoveFile,
    OperationManifest,
    ProviderProjectPlan,
)
from hephaestus.models import DeepSeekProvider, ModelRequest, ModelResponse, ProviderRequestError

VALID_PLAN_JSON = json.dumps(
    {
        "task_summary": "Build TaskForge",
        "architecture": ["stdlib package and unittest"],
        "proposed_files": [
            {"path": "taskforge/__main__.py", "purpose": "CLI"},
            {"path": "tests/test_cli.py", "purpose": "tests"},
            {"path": "README.md", "purpose": "usage"},
        ],
        "implementation_approach": ["argparse and JSON"],
        "tests": ["add and list"],
        "validation_commands": ["python -m unittest discover -v"],
        "assumptions": [],
        "risks": [],
    }
)


class ScriptedProvider(DeepSeekProvider):
    def __init__(self, responses: list[str]) -> None:
        super().__init__(api_key="test")
        self.responses = responses
        self.calls = 0
        self.requests: list[ModelRequest] = []

    def complete(self, request: ModelRequest) -> ModelResponse:
        self.requests.append(request)
        text = self.responses[self.calls]
        self.calls += 1
        return ModelResponse(
            text=text,
            model="deepseek/deepseek-v4-flash",
            input_tokens=100,
            output_tokens=max(1, len(text) // 4),
            estimated_cost=0.0002,
            thinking_enabled=True,
            reasoning_effort="high",
            reasoning_content="must never persist",
        )


class FakeResponse:
    status = 200

    def __init__(self, payload: dict[str, Any] | None = None, *, raw: bytes | None = None) -> None:
        self.payload = payload or {
            "choices": [{"message": {"content": VALID_PLAN_JSON}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5},
        }
        self.raw = raw

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(self, *args: object) -> None:
        return None

    def read(self) -> bytes:
        return self.raw if self.raw is not None else json.dumps(self.payload).encode()


class TimeoutOnReadResponse(FakeResponse):
    def read(self) -> bytes:
        raise TimeoutError


def test_deepseek_plan_request_uses_json_mode_and_contract_prompt(tmp_path: Path) -> None:
    captured: list[dict[str, Any]] = []

    def urlopen(request: urllib.request.Request, *, timeout: float) -> FakeResponse:
        captured.append(json.loads(bytes(request.data or b"{}")))
        return FakeResponse()

    target = tmp_path / "target"
    target.mkdir()
    subprocess.run(["git", "init"], cwd=target, check=True, capture_output=True)
    provider = DeepSeekProvider(api_key="test", urlopen=urlopen)
    executor = GreenfieldCodingExecutor(
        tmp_path / "db.sqlite", provider_override=provider, provider_source="fake-http"
    )

    executor.plan("Create TaskForge", repo_path=target, workflow_mode=CodingWorkflowMode.BUILD)

    payload = captured[0]
    assert payload["response_format"] == {"type": "json_object"}
    system = payload["messages"][0]["content"]
    assert "JSON" in system
    assert "top-level JSON object" in system
    assert "markdown fences" in system
    assert "task_summary" in system


@pytest.mark.parametrize(
    "content",
    [
        VALID_PLAN_JSON,
        f"\ufeff  {VALID_PLAN_JSON}\n",
        f"```json\n{VALID_PLAN_JSON}\n```",
    ],
)
def test_structured_parser_accepts_direct_whitespace_and_single_fence(content: str) -> None:
    parsed = parse_structured_response(content, ProviderProjectPlan, "plan")

    assert parsed.value.task_summary == "Build TaskForge"


@pytest.mark.parametrize(
    ("content", "status"),
    [
        (f"{VALID_PLAN_JSON}\n{VALID_PLAN_JSON}", "multiple_top_level_objects"),
        ("{not json", "invalid_json"),
        ("[]", "not_json_object"),
    ],
)
def test_structured_parser_rejects_invalid_shapes(content: str, status: str) -> None:
    with pytest.raises(StructuredParseFailure) as caught:
        parse_structured_response(content, ProviderProjectPlan, "plan")

    assert caught.value.status == status


def test_structured_parser_reports_schema_validation_errors() -> None:
    with pytest.raises(StructuredParseFailure) as caught:
        parse_structured_response('{"task_summary":null}', ProviderProjectPlan, "plan")

    assert caught.value.status == "schema_validation_failed"
    assert caught.value.validation_errors
    assert caught.value.failure_code == "PLAN_SCHEMA_VALIDATION_FAILED"


def test_format_repair_succeeds_once_without_full_regeneration(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    subprocess.run(["git", "init"], cwd=target, check=True, capture_output=True)
    provider = ScriptedProvider(['{"task_summary":null}', VALID_PLAN_JSON])
    executor = GreenfieldCodingExecutor(
        tmp_path / "db.sqlite", provider_override=provider, provider_source="fake-http"
    )

    _request, plan = executor.plan(
        "Create TaskForge", repo_path=target, workflow_mode=CodingWorkflowMode.BUILD
    )

    assert plan.summary == "Build TaskForge"
    assert provider.calls == 2
    assert [request.call_kind for request in provider.requests] == ["plan", "format_repair"]
    assert "Original final content" in provider.requests[1].prompt


def test_failed_format_repair_stops_with_precise_code(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    subprocess.run(["git", "init"], cwd=target, check=True, capture_output=True)
    provider = ScriptedProvider(
        ['{"task_summary":null}', '{"task_summary":null}']
    )
    executor = GreenfieldCodingExecutor(
        tmp_path / "db.sqlite", provider_override=provider, provider_source="fake-http"
    )

    with pytest.raises(CodingProviderError, match="PLAN_FORMAT_REPAIR_FAILED"):
        executor.plan("Create TaskForge", repo_path=target, workflow_mode=CodingWorkflowMode.BUILD)

    assert provider.calls == 2
    assert not [path for path in target.iterdir() if path.name != ".git"]


def test_read_timeout_retries_once_and_accounts_attempts() -> None:
    calls = 0

    def urlopen(request: urllib.request.Request, *, timeout: float) -> FakeResponse:
        nonlocal calls
        calls += 1
        if calls == 1:
            return TimeoutOnReadResponse()
        return FakeResponse()

    provider = DeepSeekProvider(api_key="test", urlopen=urlopen)
    response = provider.complete(
        ModelRequest(prompt="hi", max_transport_attempts=2, require_json=True)
    )

    assert response.text == VALID_PLAN_JSON
    assert calls == 2
    assert [attempt.error_code for attempt in response.transport_attempts] == [
        "read_timeout",
        "",
    ]


@pytest.mark.parametrize(
    ("status", "body", "code"),
    [
        (401, b"unauthorized", "unauthorized"),
        (402, b"insufficient balance", "insufficient_balance"),
        (400, b"invalid model", "invalid_model"),
    ],
)
def test_non_transient_provider_errors_do_not_retry(status: int, body: bytes, code: str) -> None:
    calls = 0

    def urlopen(request: urllib.request.Request, *, timeout: float) -> FakeResponse:
        nonlocal calls
        calls += 1
        raise urllib.error.HTTPError(request.full_url, status, "failure", None, io.BytesIO(body))

    provider = DeepSeekProvider(api_key="test", urlopen=urlopen)

    with pytest.raises(ProviderRequestError) as caught:
        provider.complete(ModelRequest(prompt="hi", max_transport_attempts=2))

    assert caught.value.code == code
    assert calls == 1


def test_keep_alive_prefixed_response_is_accepted() -> None:
    raw = b"\n\n" + json.dumps(
        {
            "choices": [{"message": {"content": VALID_PLAN_JSON}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 4, "completion_tokens": 4},
        }
    ).encode()

    def urlopen(request: urllib.request.Request, *, timeout: float) -> FakeResponse:
        return FakeResponse(raw=raw)

    provider = DeepSeekProvider(api_key="test", urlopen=urlopen)
    response = provider.complete(ModelRequest(prompt="hi", require_json=True))

    assert response.finish_reason == "stop"
    assert response.text == VALID_PLAN_JSON


def test_sse_keep_alive_comments_are_ignored() -> None:
    payload = json.dumps(
        {
            "choices": [{"message": {"content": VALID_PLAN_JSON}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 4, "completion_tokens": 4},
        }
    )
    raw = f": keep-alive\n\ndata: {payload}\n\ndata: [DONE]\n".encode()

    def urlopen(request: urllib.request.Request, *, timeout: float) -> FakeResponse:
        return FakeResponse(raw=raw)

    provider = DeepSeekProvider(api_key="test", urlopen=urlopen)
    response = provider.complete(ModelRequest(prompt="hi", require_json=True))

    assert response.text == VALID_PLAN_JSON


def test_budget_tracks_logical_calls_transport_attempts_and_repairs(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    subprocess.run(["git", "init"], cwd=target, check=True, capture_output=True)
    calls = 0

    def urlopen(request: urllib.request.Request, *, timeout: float) -> FakeResponse:
        nonlocal calls
        calls += 1
        if calls == 1:
            return TimeoutOnReadResponse()
        if calls == 2:
            payload = {
                "choices": [{"message": {"content": '{"task_summary":null}'}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 5, "completion_tokens": 2},
            }
            return FakeResponse(payload)
        return FakeResponse()

    provider = DeepSeekProvider(api_key="test", urlopen=urlopen)
    executor = GreenfieldCodingExecutor(
        tmp_path / "db.sqlite", provider_override=provider, provider_source="fake-http"
    )

    _request, plan = executor.plan(
        "Create TaskForge",
        repo_path=target,
        workflow_mode=CodingWorkflowMode.BUILD,
        max_network_attempts=3,
    )

    assert plan.budget.calls == 2
    assert plan.budget.transport_attempts == 3
    assert plan.budget.format_repair_calls == 1


def test_cost_unknown_is_not_rendered_as_false_zero() -> None:
    assert _cost_text(0.0, "unknown") == "Cost unknown"


def test_manifest_create_modify_move_delete_and_preflight(tmp_path: Path) -> None:
    existing = tmp_path / "existing.txt"
    existing.write_text("old\n", encoding="utf-8")
    remove = tmp_path / "remove.txt"
    remove.write_text("remove\n", encoding="utf-8")
    move = tmp_path / "move.txt"
    move.write_text("move\n", encoding="utf-8")
    manifest = OperationManifest(
        task_summary="mixed",
        operations=[
            CreateFile(operation="create", path="nested/new.txt", content="new\n"),
            ModifyFile(
                operation="modify",
                path="existing.txt",
                expected_sha256=_hash(existing),
                mode="replace",
                content="updated\n",
            ),
            DeleteFile(operation="delete", path="remove.txt", expected_sha256=_hash(remove)),
            MoveFile(
                operation="move",
                source_path="move.txt",
                destination_path="moved.txt",
                expected_sha256=_hash(move),
            ),
        ],
        expected_files=["nested/new.txt", "existing.txt", "remove.txt", "move.txt", "moved.txt"],
    )
    result = apply_manifest(tmp_path, manifest)
    assert (tmp_path / "nested/new.txt").read_text(encoding="utf-8") == "new\n"
    assert existing.read_text(encoding="utf-8") == "updated\n"
    assert not remove.exists()
    assert not move.exists()
    assert (tmp_path / "moved.txt").read_text(encoding="utf-8") == "move\n"
    assert result.checkpoint.files_touched


@pytest.mark.parametrize("path", ["../escape.py", "/absolute.py", ".git/config", ".hephaestus/x"])
def test_manifest_rejects_unsafe_paths_atomically(tmp_path: Path, path: str) -> None:
    safe = tmp_path / "safe.txt"
    safe.write_text("unchanged", encoding="utf-8")
    manifest = OperationManifest(
        task_summary="unsafe",
        operations=[CreateFile(operation="create", path=path, content="bad")],
    )
    with pytest.raises(PermissionError):
        preflight_manifest(tmp_path, manifest)
    assert safe.read_text(encoding="utf-8") == "unchanged"


def test_hash_mismatch_and_duplicate_destination_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "a.txt"
    path.write_text("a", encoding="utf-8")
    with pytest.raises(ValueError):
        preflight_manifest(
            tmp_path,
            OperationManifest(
                task_summary="stale",
                operations=[
                    ModifyFile(
                        operation="modify",
                        path="a.txt",
                        expected_sha256="0" * 64,
                        mode="replace",
                        content="b",
                    )
                ],
            ),
        )
    with pytest.raises(ValueError):
        preflight_manifest(
            tmp_path,
            OperationManifest(
                task_summary="duplicate",
                operations=[
                    CreateFile(operation="create", path="x.txt", content="x"),
                    CreateFile(operation="create", path="x.txt", content="y"),
                ],
            ),
        )


def test_taskforge_greenfield_flow_calls_provider_requires_approvals_and_validates(
    tmp_path: Path,
) -> None:
    target = tmp_path / "target"
    target.mkdir()
    subprocess.run(["git", "init"], cwd=target, check=True, capture_output=True)
    plan_json = """{
      "task_summary":"Build TaskForge",
      "architecture":["stdlib package and unittest"],
      "proposed_files":[
        {"path":"taskforge/__main__.py","purpose":"CLI"},
        {"path":"tests/test_cli.py","purpose":"tests"},
        {"path":"README.md","purpose":"usage"}
      ],
      "implementation_approach":["argparse and JSON"],
      "tests":["add and list"],
      "validation_commands":["python -m unittest discover -v"],
      "assumptions":[],
      "risks":[]
    }"""
    main = """import argparse
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["add", "list", "done", "delete"])
    parser.add_argument("value", nargs="?")
    parser.parse_args()
if __name__ == "__main__":
    main()
"""
    test = """import subprocess, sys, unittest
class CliTest(unittest.TestCase):
    def test_help(self):
        result = subprocess.run([sys.executable, "-m", "taskforge", "--help"])
        self.assertEqual(result.returncode, 0)
"""
    manifest_json = json.dumps(
        {
            "task_summary": "Implement TaskForge",
            "assumptions": [],
            "operations": [
                {"operation": "create", "path": "taskforge/__init__.py", "content": ""},
                {"operation": "create", "path": "taskforge/__main__.py", "content": main},
                {"operation": "create", "path": "tests/__init__.py", "content": ""},
                {"operation": "create", "path": "tests/test_cli.py", "content": test},
                {"operation": "create", "path": "README.md", "content": "# TaskForge\n"},
            ],
            "validation_commands": ["python -m unittest discover -v"],
            "expected_files": [
                "taskforge/__init__.py",
                "taskforge/__main__.py",
                "tests/__init__.py",
                "tests/test_cli.py",
                "README.md",
            ],
            "risks": [],
        }
    )
    provider = ScriptedProvider([plan_json, manifest_json])
    database = tmp_path / "hephaestus.db"
    executor = GreenfieldCodingExecutor(
        database, provider_override=provider, provider_source="fake-http"
    )
    request, plan = executor.plan(
        "Создай небольшой Python CLI TaskForge",
        repo_path=target,
        provider="real",
        workflow_mode=CodingWorkflowMode.BUILD,
    )
    assert request.task_intent == CodingTaskIntent.GREENFIELD_PROJECT
    assert provider.calls == 1
    with pytest.raises(PermissionError):
        executor.prepare(plan.id, approved=False)
    change = executor.prepare(plan.id, approved=True)
    assert provider.calls == 2
    blocked = CodingLoopExecutor(database).apply_change(change.id, yes=False)
    assert blocked.status.value == "requires_approval"
    result = CodingLoopExecutor(database).apply_change(change.id, yes=True)
    assert result.status.value == "completed", result.model_dump_json(indent=2)
    assert result.validation.pass_count >= 1
    assert (target / "README.md").exists()
    assert "reasoning_content" not in request.model_dump_json()


def test_build_overrides_docs_classifier_in_empty_repo(tmp_path: Path) -> None:
    assert (
        classify_task_intent("Create README and application", tmp_path, CodingWorkflowMode.BUILD)
        == CodingTaskIntent.GREENFIELD_PROJECT
    )


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
