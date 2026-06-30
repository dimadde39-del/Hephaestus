from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError

from hephaestus.coding_loop.executor import CodingLoopExecutor
from hephaestus.coding_loop.greenfield import (
    CodingProviderError,
    GreenfieldCodingExecutor,
    _validate_repair_manifest,
)
from hephaestus.coding_loop.operations import apply_manifest
from hephaestus.coding_loop.schemas import (
    CodingWorkflowMode,
    CreateFile,
    DeleteFile,
    OperationManifest,
    RepairManifest,
)
from hephaestus.coding_loop.validation import CodingValidationEngine
from hephaestus.models import DeepSeekProvider, ModelRequest, ModelResponse
from hephaestus.validation import (
    VALIDATION_IMPORT_FAILED,
    VALIDATION_NO_TESTS_DISCOVERED,
    VALIDATION_SYNTAX_FAILED,
    VALIDATION_TESTS_FAILED,
    normalize_model_validation_commands,
    parse_test_counts,
)
from hephaestus.validation.schemas import (
    ValidationCommand,
    ValidationCommandType,
    ValidationExecutionPlan,
    ValidationStatus,
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


def test_python_test_directory_detection_and_unittest_normalization(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_storage.py").write_text("import unittest\n", encoding="utf-8")

    normalized = normalize_model_validation_commands(
        tmp_path,
        model_commands=["python -m unittest discover -v"],
        changed_files=["taskforge/storage.py", "tests/test_storage.py"],
        expected_files=[],
    )

    assert normalized["expected_test_locations"] == ["tests/test_storage.py"]
    assert normalized["commands"][0]["command"] == (
        'python -m unittest discover -s tests -p "test_*.py" -v'
    )
    assert "normalized generic unittest discovery" in normalized["commands"][0]["reason"]


def test_no_tests_discovered_classification_and_single_fallback(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    manifest = _taskforge_manifest(storage=_working_storage())
    apply_manifest(repo, manifest)
    plan = ValidationExecutionPlan(
        repo_path=str(repo),
        commands=[
            ValidationCommand(
                command="python -m unittest discover -v",
                command_type=ValidationCommandType.TEST,
                metadata={"stage": "tests"},
            )
        ],
        metadata={
            "expected_test_locations": ["tests/test_storage.py"],
            "fallback_commands": ['python -m unittest discover -s tests -p "test_*.py" -v'],
        },
    )

    suite = CodingValidationEngine(tmp_path / "db.sqlite").run(repo, manifest, plan=plan)

    zero_attempts = [
        item for item in suite.evidence if item.failure_classification == VALIDATION_NO_TESTS_DISCOVERED
    ]
    assert suite.status == ValidationStatus.PASSED
    assert len(zero_attempts) == 1
    assert len([item for item in suite.evidence if item.command_type == ValidationCommandType.TEST]) == 2
    assert any(item.metadata.get("superseded_by_deterministic_fallback") for item in suite.evidence)


def test_no_false_success_when_zero_tests_run(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    manifest = OperationManifest(
        task_summary="no tests",
        operations=[
            CreateFile(operation="create", path="taskforge/__init__.py", content=""),
            CreateFile(operation="create", path="taskforge/storage.py", content="VALUE = 1\n"),
        ],
        validation_commands=["python -m unittest discover -v"],
        expected_files=["taskforge/__init__.py", "taskforge/storage.py"],
    )
    apply_manifest(repo, manifest)
    plan = ValidationExecutionPlan(
        repo_path=str(repo),
        commands=[
            ValidationCommand(command="python -m unittest discover -v", command_type=ValidationCommandType.TEST)
        ],
    )

    suite = CodingValidationEngine(tmp_path / "db.sqlite").run(repo, manifest, plan=plan)

    assert suite.status == ValidationStatus.FAILED
    assert suite.evidence[-1].failure_classification == VALIDATION_NO_TESTS_DISCOVERED


def test_syntax_import_and_real_test_failure_taxonomy(tmp_path: Path) -> None:
    syntax_repo = _repo(tmp_path, "syntax")
    syntax_manifest = OperationManifest(
        task_summary="syntax",
        operations=[CreateFile(operation="create", path="pkg/bad.py", content="def nope(:\n")],
        expected_files=["pkg/bad.py"],
        validation_commands=[],
    )
    apply_manifest(syntax_repo, syntax_manifest)
    syntax_suite = CodingValidationEngine(tmp_path / "syntax.sqlite").run(syntax_repo, syntax_manifest)
    assert syntax_suite.status == ValidationStatus.FAILED
    assert syntax_suite.evidence[-1].failure_classification == VALIDATION_SYNTAX_FAILED

    import_repo = _repo(tmp_path, "import")
    import_manifest = _taskforge_manifest(
        storage=_working_storage(),
        test="import missing_module\n",
    )
    apply_manifest(import_repo, import_manifest)
    import_suite = CodingValidationEngine(tmp_path / "import.sqlite").run(import_repo, import_manifest)
    assert import_suite.evidence[-1].failure_classification == VALIDATION_IMPORT_FAILED

    fail_repo = _repo(tmp_path, "fail")
    fail_manifest = _taskforge_manifest(storage=_working_storage(), assertion="self.assertEqual(1, 2)")
    apply_manifest(fail_repo, fail_manifest)
    fail_suite = CodingValidationEngine(tmp_path / "fail.sqlite").run(fail_repo, fail_manifest)
    assert fail_suite.evidence[-1].failure_classification == VALIDATION_TESTS_FAILED


def test_successful_test_count_parsing() -> None:
    counts = parse_test_counts("2 passed, 1 skipped", "Ran 3 tests in 0.001s")
    assert counts["discovered"] == 3
    assert counts["passed"] == 2
    assert counts["skipped"] == 1


def test_strict_repair_manifest_and_test_deletion_guard() -> None:
    with pytest.raises(ValidationError):
        RepairManifest.model_validate(
            {
                "task_summary": "bad",
                "failure_classification": VALIDATION_TESTS_FAILED,
                "operations": [],
                "extra": "forbidden",
            }
        )
    repair = RepairManifest(
        task_summary="delete tests",
        failure_classification=VALIDATION_TESTS_FAILED,
        operations=[
            DeleteFile(
                operation="delete",
                path="tests/test_storage.py",
                expected_sha256="0" * 64,
            )
        ],
    )
    with pytest.raises(CodingProviderError, match="delete tests"):
        _validate_repair_manifest(repair)


def test_taskforge_acceptance_normalizes_generic_unittest_and_validates(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    provider = ScriptedProvider([_plan_json(), _manifest_json(storage=_working_storage())])
    database = tmp_path / "db.sqlite"
    greenfield = GreenfieldCodingExecutor(
        database,
        provider_override=provider,
        provider_source="fake-http",
    )

    _request, plan = greenfield.plan(
        "Create TaskForge",
        repo_path=repo,
        provider="real",
        workflow_mode=CodingWorkflowMode.BUILD,
    )
    change = greenfield.prepare(plan.id, approved=True)
    normalized = change.metadata["normalized_validation_plan"]
    assert normalized["deterministic_normalized_commands"] == [
        'python -m unittest discover -s tests -p "test_*.py" -v'
    ]

    result = CodingLoopExecutor(database).apply_change(change.id, yes=True)

    assert result.status.value == "completed", result.model_dump_json(indent=2)
    assert result.validation.pass_count >= 3
    assert provider.calls == 2


def test_real_failure_triggers_one_repair_and_revalidation_pass(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    bad_storage = _bad_storage()
    repair = _repair_json(expected_sha256=_hash_text(bad_storage), storage=_working_storage())
    provider = ScriptedProvider([_plan_json(), _manifest_json(storage=bad_storage), repair])
    database = tmp_path / "db.sqlite"
    greenfield = GreenfieldCodingExecutor(database, provider_override=provider, provider_source="fake-http")
    _request, plan = greenfield.plan(
        "Create TaskForge",
        repo_path=repo,
        provider="real",
        workflow_mode=CodingWorkflowMode.BUILD,
        max_calls=3,
    )
    change = greenfield.prepare(plan.id, approved=True)

    result = CodingLoopExecutor(database, provider_override=provider).apply_change(
        change.id,
        yes=True,
        allow_one_repair=True,
    )

    assert result.status.value == "completed", result.model_dump_json(indent=2)
    assert provider.calls == 3
    assert result.metadata["repair_attempted"] is True
    assert result.metadata["repair_result"] == "validation_passed"
    assert len(result.validation_result_ids) == 2


def test_no_repair_when_budget_exhausted(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    provider = ScriptedProvider([_plan_json(), _manifest_json(storage=_bad_storage())])
    database = tmp_path / "db.sqlite"
    greenfield = GreenfieldCodingExecutor(database, provider_override=provider, provider_source="fake-http")
    _request, plan = greenfield.plan(
        "Create TaskForge",
        repo_path=repo,
        provider="real",
        workflow_mode=CodingWorkflowMode.BUILD,
        max_calls=2,
    )
    change = greenfield.prepare(plan.id, approved=True)

    result = CodingLoopExecutor(database, provider_override=provider).apply_change(
        change.id,
        yes=True,
        allow_one_repair=True,
    )

    assert result.status.value == "validation_failed"
    assert provider.calls == 2
    assert "Provider call budget exhausted" in str(result.metadata["repair_result"])


def test_failed_repair_rolls_back_removes_runtime_residue_and_snapshots(tmp_path: Path) -> None:
    repo = _repo(tmp_path)
    (repo / ".env").write_text("API_KEY=secret\n", encoding="utf-8")
    bad_storage = _bad_storage()
    still_bad = _repair_json(expected_sha256=_hash_text(bad_storage), storage=_bad_storage(return_zero=True))
    provider = ScriptedProvider([_plan_json(), _manifest_json(storage=bad_storage), still_bad])
    database = tmp_path / "db.sqlite"
    artifact_root = tmp_path / "artifacts"
    greenfield = GreenfieldCodingExecutor(database, provider_override=provider, provider_source="fake-http")
    _request, plan = greenfield.plan(
        "Create TaskForge",
        repo_path=repo,
        provider="real",
        workflow_mode=CodingWorkflowMode.BUILD,
        max_calls=3,
    )
    change = greenfield.prepare(plan.id, approved=True)

    result = CodingLoopExecutor(database, provider_override=provider).apply_change(
        change.id,
        yes=True,
        allow_one_repair=True,
        rollback_on_failure=True,
        retain_failed_snapshot=True,
        artifact_root=artifact_root,
    )

    assert result.status.value == "rolled_back"
    assert not (repo / "taskforge").exists()
    assert not (repo / "tests").exists()
    assert not (repo / "README.md").exists()
    assert not list(repo.rglob("__pycache__"))
    assert not list(repo.rglob("*.pyc"))
    assert (repo / ".env").exists()
    cleanup = result.metadata["rollback_cleanup"]
    assert isinstance(cleanup, dict)
    assert cleanup["clean"] is True
    snapshot = artifact_root / "failed-workspace"
    assert (snapshot / "taskforge" / "storage.py").exists()
    assert not (snapshot / ".env").exists()
    assert (artifact_root / "validation-evidence.json").exists()


def _repo(tmp_path: Path, name: str = "repo") -> Path:
    repo = tmp_path / name
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)
    return repo


def _plan_json() -> str:
    return json.dumps(
        {
            "task_summary": "Build TaskForge",
            "architecture": ["stdlib package and unittest"],
            "proposed_files": [
                {"path": "taskforge/__init__.py", "purpose": "package"},
                {"path": "taskforge/storage.py", "purpose": "storage"},
                {"path": "tests/test_storage.py", "purpose": "tests"},
                {"path": "README.md", "purpose": "usage"},
            ],
            "implementation_approach": ["argparse and JSON storage"],
            "tests": ["storage operations"],
            "validation_commands": ["python -m unittest discover -v"],
            "assumptions": [],
            "risks": [],
        }
    )


def _manifest_json(*, storage: str) -> str:
    return _taskforge_manifest(storage=storage).model_dump_json()


def _taskforge_manifest(
    *,
    storage: str,
    test: str | None = None,
    assertion: str = "self.assertEqual(manager.list()[0]['text'], 'write tests')",
) -> OperationManifest:
    test_content = test if test is not None else _storage_test(assertion)
    return OperationManifest(
        task_summary="Implement TaskForge",
        operations=[
            CreateFile(operation="create", path="taskforge/__init__.py", content=""),
            CreateFile(operation="create", path="taskforge/storage.py", content=storage),
            CreateFile(operation="create", path="tests/test_storage.py", content=test_content),
            CreateFile(operation="create", path="README.md", content="# TaskForge\n"),
        ],
        validation_commands=["python -m unittest discover -v"],
        expected_files=[
            "taskforge/__init__.py",
            "taskforge/storage.py",
            "tests/test_storage.py",
            "README.md",
        ],
    )


def _storage_test(assertion: str) -> str:
    return f"""import tempfile
import unittest
from pathlib import Path
from taskforge.storage import TaskManager

class StorageTest(unittest.TestCase):
    def test_add_lists_and_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = TaskManager(Path(tmp) / "tasks.json")
            self.assertEqual(manager.add("write tests"), 1)
            {assertion}

    def test_done_missing_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = TaskManager(Path(tmp) / "tasks.json")
            with self.assertRaises(ValueError):
                manager.done(404)

    def test_delete_missing_raises(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = TaskManager(Path(tmp) / "tasks.json")
            with self.assertRaises(ValueError):
                manager.delete(404)
"""


def _working_storage() -> str:
    return """import json
import os
import tempfile
from pathlib import Path

class TaskManager:
    def __init__(self, filepath="tasks.json"):
        self.filepath = Path(filepath)
        if not self.filepath.exists():
            self._write([])

    def _read(self):
        return json.loads(self.filepath.read_text(encoding="utf-8"))

    def _write(self, tasks):
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        fd, temp = tempfile.mkstemp(dir=self.filepath.parent, suffix=".tmp")
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(tasks, handle)
        os.replace(temp, self.filepath)

    def add(self, text):
        tasks = self._read()
        task_id = max([item["id"] for item in tasks], default=0) + 1
        tasks.append({"id": task_id, "text": text, "done": False})
        self._write(tasks)
        return task_id

    def list(self):
        return self._read()

    def done(self, task_id):
        tasks = self._read()
        for task in tasks:
            if task["id"] == task_id:
                task["done"] = True
                self._write(tasks)
                return
        raise ValueError("missing task")

    def delete(self, task_id):
        tasks = self._read()
        kept = [task for task in tasks if task["id"] != task_id]
        if len(kept) == len(tasks):
            raise ValueError("missing task")
        self._write(kept)
"""


def _bad_storage(*, return_zero: bool = False) -> str:
    return f"""from pathlib import Path

class TaskManager:
    def __init__(self, filepath="tasks.json"):
        self.filepath = Path(filepath)

    def add(self, text):
        return {0 if return_zero else 1}

    def list(self):
        return []

    def done(self, task_id):
        raise ValueError("missing task")

    def delete(self, task_id):
        raise ValueError("missing task")
"""


def _repair_json(*, expected_sha256: str, storage: str) -> str:
    return json.dumps(
        {
            "task_summary": "Repair TaskForge storage",
            "failure_classification": VALIDATION_TESTS_FAILED,
            "operations": [
                {
                    "operation": "modify",
                    "path": "taskforge/storage.py",
                    "expected_sha256": expected_sha256,
                    "mode": "replace",
                    "content": storage,
                }
            ],
            "validation_commands": ['python -m unittest discover -s tests -p "test_*.py" -v'],
            "expected_files": ["taskforge/storage.py", "tests/test_storage.py"],
            "risks": [],
        }
    )


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
