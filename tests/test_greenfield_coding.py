from __future__ import annotations

import hashlib
import subprocess
from pathlib import Path

import pytest

from hephaestus.coding_loop.executor import CodingLoopExecutor
from hephaestus.coding_loop.greenfield import GreenfieldCodingExecutor, classify_task_intent
from hephaestus.coding_loop.operations import apply_manifest, preflight_manifest
from hephaestus.coding_loop.schemas import (
    CodingTaskIntent,
    CodingWorkflowMode,
    CreateFile,
    DeleteFile,
    ModifyFile,
    MoveFile,
    OperationManifest,
)
from hephaestus.models import DeepSeekProvider, ModelRequest, ModelResponse


class ScriptedProvider(DeepSeekProvider):
    def __init__(self, responses: list[str]) -> None:
        super().__init__(api_key="test")
        self.responses = responses
        self.calls = 0

    def complete(self, request: ModelRequest) -> ModelResponse:
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
    import json

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
