from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from benchmarks.harness_gain.orchestrator import (
    ARMS,
    _init_git,
    prepare_live_root,
    schedule,
)
from benchmarks.harness_gain.reporting import write_reports
from benchmarks.harness_gain.runners import (
    bare_one_shot,
    bare_two_stage,
    hephaestus_runner,
    mimocode_runner,
)
from benchmarks.harness_gain.runners.common import parse_manifest, usage_from_responses
from benchmarks.harness_gain.schemas import ArmId, RunRecord
from benchmarks.harness_gain.secret_redaction import redact_data, redact_text, scan_artifacts

from hephaestus.coding_loop.schemas import OperationManifest, ProviderProjectPlan
from hephaestus.models import DeepSeekProvider, ModelRequest, ModelResponse


class ScriptedDeepSeek(DeepSeekProvider):
    def __init__(self, responses: list[str]) -> None:
        super().__init__(api_key="test")
        self.responses = list(responses)

    def complete(self, request: ModelRequest) -> ModelResponse:
        del request
        text = self.responses.pop(0)
        return ModelResponse(
            text=text,
            model="deepseek-v4-flash",
            input_tokens=100,
            output_tokens=50,
            cached_input_tokens=10,
            estimated_cost=0.0001,
            finish_reason="stop",
        )


def _manifest(path: str = "answer.py") -> str:
    return OperationManifest(
        task_summary="implement",
        operations=[{"operation": "create", "path": path, "content": "ANSWER = 42\n"}],
        expected_files=[path],
    ).model_dump_json()


def _plan() -> str:
    return ProviderProjectPlan(
        task_summary="implement",
        proposed_files=[{"path": "answer.py", "purpose": "answer"}],
        implementation_approach=["create answer"],
    ).model_dump_json()


def test_fixture_reset_and_validator_isolation(tmp_path: Path) -> None:
    prepare_live_root(tmp_path)
    changed = tmp_path / "fixtures" / "ttl_cache_bugfix" / "ttl_cache.py"
    changed.write_text("changed", encoding="utf-8")
    prepare_live_root(tmp_path)
    assert changed.read_text(encoding="utf-8").startswith('"""A tiny cache')
    assert (tmp_path / "validators" / "hidden_validator.py").is_file()
    assert not (tmp_path / "fixtures" / "ttl_cache_bugfix" / "hidden_validator.py").exists()


def test_bare_one_shot_fake_response_and_strict_parser(tmp_path: Path) -> None:
    result = bare_one_shot.run("make answer", tmp_path, ScriptedDeepSeek([_manifest()]))
    assert result.declared_success
    assert result.usage.logical_provider_calls == 1
    assert (tmp_path / "answer.py").read_text(encoding="utf-8") == "ANSWER = 42\n"
    try:
        parse_manifest("```json\n{}\n```")
    except Exception:
        pass
    else:
        raise AssertionError("fenced JSON must be a format failure")


def test_bare_two_stage_fake_responses(tmp_path: Path) -> None:
    result = bare_two_stage.run(
        "make answer",
        tmp_path,
        ScriptedDeepSeek([_plan(), _manifest()]),
    )
    assert result.declared_success
    assert result.usage.logical_provider_calls == 2


def test_mimo_command_and_environment_isolation(tmp_path: Path) -> None:
    command = mimocode_runner.build_command("exact prompt", tmp_path)
    assert str(mimocode_runner.WRAPPER) in command
    assert "-Agent" in command and command[command.index("-Agent") + 1] == "build"
    assert "-Format" in command and command[command.index("-Format") + 1] == "json"
    env = mimocode_runner.isolated_environment(tmp_path / "session")
    assert env["HOME"] == env["USERPROFILE"]
    assert env["MIMOCODE_DISABLE_PROJECT_CONFIG"] == "true"
    assert "DEEPSEEK_API_KEY" not in env


def test_hephaestus_official_runner_with_fake_provider(tmp_path: Path) -> None:
    target = tmp_path / "target"
    target.mkdir()
    (target / ".gitignore").write_text("__pycache__/\n", encoding="utf-8")
    _init_git(target)
    plan = ProviderProjectPlan(
        task_summary="greenfield answer",
        proposed_files=[
            {"path": "answer.py", "purpose": "implementation"},
            {"path": "test_answer.py", "purpose": "tests"},
        ],
        implementation_approach=["create implementation and tests"],
        tests=["unit test"],
        validation_commands=["python -m unittest discover -v"],
    ).model_dump_json()
    manifest = OperationManifest(
        task_summary="greenfield answer",
        operations=[
            {"operation": "create", "path": "answer.py", "content": "ANSWER = 42\n"},
            {
                "operation": "create",
                "path": "test_answer.py",
                "content": (
                    "import unittest\nfrom answer import ANSWER\n\n"
                    "class T(unittest.TestCase):\n"
                    "    def test_answer(self):\n"
                    "        self.assertEqual(ANSWER, 42)\n"
                ),
            },
        ],
        validation_commands=["python -m unittest discover -v"],
        expected_files=["answer.py", "test_answer.py"],
    ).model_dump_json()
    result = hephaestus_runner.run(
        "Create a tiny Python project with tests.",
        target,
        tmp_path / "runtime",
        ScriptedDeepSeek([plan, manifest]),
    )
    assert result.declared_success
    assert result.self_validation is not None and result.self_validation.passed
    assert result.usage.logical_provider_calls == 2


def test_usage_cost_and_secret_redaction(tmp_path: Path) -> None:
    responses = [
        ModelResponse(
            text="{}",
            model="deepseek-v4-flash",
            input_tokens=10,
            output_tokens=5,
            cached_input_tokens=2,
            estimated_cost=0.1,
        ),
        ModelResponse(
            text="{}",
            model="deepseek-v4-flash",
            input_tokens=20,
            output_tokens=7,
            cached_input_tokens=3,
            estimated_cost=0.2,
        ),
    ]
    usage = usage_from_responses(responses)
    assert (usage.input_tokens, usage.output_tokens, usage.cached_tokens) == (30, 12, 5)
    assert usage.estimated_cost == 0.30000000000000004
    assert "[REDACTED]" in redact_text("Authorization: Bearer sk-abcdefghijklmnop")
    assert redact_data({"reasoning_content": "private"})["reasoning_content"] == "[REDACTED]"
    (tmp_path / "safe.txt").write_text("ordinary output", encoding="utf-8")
    assert scan_artifacts(tmp_path) == []


def test_hidden_validator_runs_outside_target(tmp_path: Path) -> None:
    prepare_live_root(tmp_path)
    target = tmp_path / "fixtures" / "config_refactor"
    process = subprocess.run(
        [
            sys.executable,
            str(tmp_path / "validators" / "hidden_validator.py"),
            "config_refactor",
            str(target),
        ],
        text=True,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    payload = json.loads(process.stdout)
    assert "checks" in payload
    assert not (target / ".validator-temp").exists()


def test_randomized_schedule_is_reproducible_and_interleaved() -> None:
    first = schedule("main")
    second = schedule("main")
    assert first == second
    assert len(first) == 32
    assert {item.arm_id for item in first} == set(ARMS)
    assert any(first[index].arm_id != first[index + 1].arm_id for index in range(31))


def test_report_generation(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    record = RunRecord(
        protocol_version="5.6B.1",
        phase="main",
        run_id="main-task-bare_one_shot-r1",
        task_id="task",
        arm_id=ArmId.BARE_ONE_SHOT,
        run_index=1,
        fixture_sha256="a" * 64,
        prompt_sha256="b" * 64,
        harness_version="test",
        start_time=now,
        end_time=now,
        wall_time=1,
        logical_provider_calls=1,
        transport_attempts=1,
        input_tokens=10,
        cached_tokens=0,
        output_tokens=10,
        estimated_cost=0.001,
        files_created=1,
        files_modified=0,
        files_deleted=0,
        loc_added=1,
        loc_deleted=0,
        self_validation=True,
        hidden_validation=True,
        repair_calls=0,
        declared_success=True,
        exact_pass=True,
        hidden_check_pass_rate=1,
        functional_score=70,
        requirement_score=20,
        safety_score=10,
        verifier_adjusted_score=100,
        false_success=False,
        infrastructure_failure=False,
        final_status="EXACT_PASS",
    )
    payload = write_reports(tmp_path, [record])
    assert payload["sample_size"] == 1
    for name in ("summary.md", "results.csv", "results.json", "failures.md", "methodology.md"):
        assert (tmp_path / "reports" / name).exists()
