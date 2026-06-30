"""Frozen protocol orchestrator for the DeepSeek same-model harness benchmark."""

from __future__ import annotations

import argparse
import json
import random
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from benchmarks.harness_gain import PROTOCOL_VERSION
from benchmarks.harness_gain.reporting import effective_cost, load_records, write_reports
from benchmarks.harness_gain.runners import (
    bare_one_shot,
    bare_two_stage,
    hephaestus_runner,
    mimocode_runner,
)
from benchmarks.harness_gain.schemas import (
    INFRASTRUCTURE_FAILURES,
    ArmId,
    FailureCode,
    RunnerResult,
    RunRecord,
    ScheduledRun,
    ValidationResult,
)
from benchmarks.harness_gain.scoring import score_validation
from benchmarks.harness_gain.secret_redaction import (
    scan_artifacts,
    write_json,
    write_text,
)
from benchmarks.harness_gain.task_catalog import TASKS, TaskSpec, get_task

DEFAULT_ROOT = Path(r"C:\Temp\hephaestus-harness-gain")
SEED = 56062026
ARMS = list(ArmId)
MAX_WALL_TIME = 600
MAX_OUTPUT_TOKENS = 12_288
MAX_COST = 0.03
GLOBAL_COST_CAP = 0.60
REQUIRED_ARTIFACTS = {
    "metadata.json",
    "prompt.txt",
    "fixture-hash.txt",
    "stdout.txt",
    "stderr.txt",
    "provider-usage.json",
    "session-export.json",
    "file-list.txt",
    "diff.patch",
    "self-validation.json",
    "hidden-validation.json",
    "scope-report.json",
    "final-status.json",
}


def prepare_live_root(root: Path) -> None:
    for name in ("fixtures", "targets", "validators", "mimo-sessions", "artifacts", "reports"):
        (root / name).mkdir(parents=True, exist_ok=True)
    for task in TASKS.values():
        destination = root / "fixtures" / task.task_id
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(task.fixture_dir, destination)
        (destination / ".gitignore").write_text(
            "__pycache__/\n.pytest_cache/\n*.pyc\n.validator-temp/\n", encoding="utf-8"
        )
    shutil.copy2(Path(__file__).with_name("hidden_validator.py"), root / "validators" / "hidden_validator.py")
    protocol_lock = root / "protocol-lock.json"
    if protocol_lock.exists():
        previous = json.loads(protocol_lock.read_text(encoding="utf-8"))
        previous_version = str(previous.get("protocol_version", "unknown")).replace(".", "_")
        archived_lock = root / f"protocol-lock-{previous_version}.json"
        if previous.get("protocol_version") != PROTOCOL_VERSION and not archived_lock.exists():
            shutil.copy2(protocol_lock, archived_lock)
    write_json(
        protocol_lock,
        {
            "protocol_version": PROTOCOL_VERSION,
            "seed": SEED,
            "tasks": {task_id: spec.prompt for task_id, spec in TASKS.items()},
            "arms": [arm.value for arm in ARMS],
            "per_run": {
                "wall_time_seconds": MAX_WALL_TIME,
                "logical_provider_calls": 3,
                "output_tokens": MAX_OUTPUT_TOKENS,
                "estimated_cost": MAX_COST,
                "repair_calls": 1,
            },
            "global_cost_cap": GLOBAL_COST_CAP,
        },
    )


def schedule(phase: str) -> list[ScheduledRun]:
    if phase == "pilot":
        items = [
            ScheduledRun(task_id="taskforge_greenfield", arm_id=arm, run_index=1)
            for arm in ARMS
        ]
    elif phase == "main":
        items = [
            ScheduledRun(task_id=task_id, arm_id=arm, run_index=index)
            for task_id in TASKS
            for arm in ARMS
            for index in (1, 2)
        ]
    else:
        raise ValueError(f"Unsupported phase: {phase}")
    random.Random(SEED + (0 if phase == "pilot" else 1)).shuffle(items)
    return items


def run_phase(root: Path, phase: str) -> list[RunRecord]:
    prepare_live_root(root)
    if phase == "main":
        pilot_path = root / "reports" / "pilot-validation.json"
        pilot = json.loads(pilot_path.read_text(encoding="utf-8")) if pilot_path.exists() else {}
        if not pilot.get("passed") or pilot.get("protocol_version") != PROTOCOL_VERSION:
            raise RuntimeError("BLOCKED_PILOT_INVALID")
    existing = load_records(root / "artifacts")
    spent = sum(effective_cost(root, record) for record in existing)
    records: list[RunRecord] = []
    for item in schedule(phase):
        projected = _project_next_cost(existing + records, item.arm_id)
        if spent + sum(record.estimated_cost for record in records) + projected >= GLOBAL_COST_CAP:
            write_json(
                root / "reports" / "spend-cap-stop.json",
                {
                    "status": "BUDGET_EXCEEDED",
                    "actual_cost": spent + sum(record.estimated_cost for record in records),
                    "projected_next_cost": projected,
                    "next_run": item.model_dump(mode="json"),
                },
            )
            break
        record = execute_run(root, phase, item)
        records.append(record)
        print(
            f"{record.run_id}: {record.final_status}; score={record.verifier_adjusted_score:.1f}; "
            f"cost=${record.estimated_cost:.6f}",
            flush=True,
        )
    all_records = existing + records
    if phase == "pilot":
        audit = validate_pilot(root, records)
        canonical = root / "reports" / "pilot-validation.json"
        if canonical.exists():
            previous = json.loads(canonical.read_text(encoding="utf-8"))
            previous_version = str(previous.get("protocol_version", "unknown")).replace(".", "_")
            archived = root / "reports" / f"pilot-validation-{previous_version}.json"
            if not archived.exists():
                shutil.copy2(canonical, archived)
        write_json(canonical, audit)
        write_json(
            root / "reports" / f"pilot-validation-{PROTOCOL_VERSION.replace('.', '_')}.json",
            audit,
        )
        write_reports(root, all_records, phase="pilot")
        if not audit["passed"]:
            raise RuntimeError("BLOCKED_PILOT_INVALID")
    else:
        write_reports(root, all_records, phase="main")
    return records


def execute_run(root: Path, phase: str, scheduled: ScheduledRun) -> RunRecord:
    task = get_task(scheduled.task_id)
    version = PROTOCOL_VERSION.replace(".", "_")
    run_id = (
        f"{phase}-{version}-{scheduled.task_id}-{scheduled.arm_id.value}-r{scheduled.run_index}"
    )
    target = root / "targets" / run_id
    artifact = root / "artifacts" / run_id
    session = root / "mimo-sessions" / run_id
    for path in (target, artifact, session):
        if path.exists():
            raise FileExistsError(f"Run path already exists; failed runs are never overwritten: {path}")
    shutil.copytree(root / "fixtures" / task.task_id, target)
    artifact.mkdir(parents=True)
    session.mkdir(parents=True)
    _init_git(target)
    baseline = _inventory(target)
    fixture_hash = _hash_tree(target)
    prompt_hash = sha256(task.prompt.encode("utf-8")).hexdigest()
    write_text(artifact / "prompt.txt", task.prompt + "\n")
    write_text(artifact / "fixture-hash.txt", fixture_hash + "\n")
    started_at = datetime.now(UTC)
    started = time.monotonic()
    try:
        runner = _run_arm(scheduled.arm_id, task, target, session)
    except Exception as error:  # noqa: BLE001 - preserve crash as benchmark evidence
        runner = RunnerResult(
            failure_code=FailureCode.HARNESS_CRASH,
            failure_detail=f"{type(error).__name__}: {error}",
        )
    wall_time = time.monotonic() - started
    if runner.self_validation is None:
        runner.self_validation = _self_validate(task, target)
    hidden_target = runner.hidden_target or target
    hidden = _hidden_validate(root, task, hidden_target)
    final_inventory = _inventory(target)
    diff = _git_diff(target)
    scope = _scope_report(target, final_inventory)
    created, modified, deleted, loc_added, loc_deleted = _change_metrics(
        baseline, final_inventory, diff
    )
    budget_failure = _budget_failure(scheduled.arm_id, runner, wall_time)
    if budget_failure is not None:
        runner.failure_code = budget_failure
        runner.failure_detail = "Observed primary-track budget envelope was exceeded."
        runner.declared_success = False
    functional, requirements, safety, score = score_validation(hidden)
    scope_violations = len(scope["violations"])
    exact = hidden.passed and scope_violations == 0
    failure_code = runner.failure_code
    if not hidden.passed and failure_code is None:
        failure_code = FailureCode.HIDDEN_VALIDATION_FAILURE
    if scope_violations and failure_code is None:
        failure_code = FailureCode.SCOPE_VIOLATION
    infrastructure = failure_code in INFRASTRUCTURE_FAILURES if failure_code is not None else False
    end_time = datetime.now(UTC)
    final_status = "EXACT_PASS" if exact else (failure_code.value if failure_code else "FAILED")
    record = RunRecord(
        protocol_version=PROTOCOL_VERSION,
        phase=phase,
        run_id=run_id,
        task_id=task.task_id,
        arm_id=scheduled.arm_id,
        run_index=scheduled.run_index,
        fixture_sha256=fixture_hash,
        prompt_sha256=prompt_hash,
        harness_version=_harness_version(scheduled.arm_id),
        start_time=started_at,
        end_time=end_time,
        wall_time=wall_time,
        logical_provider_calls=runner.usage.logical_provider_calls,
        transport_attempts=runner.usage.transport_attempts,
        input_tokens=runner.usage.input_tokens,
        cached_tokens=runner.usage.cached_tokens,
        output_tokens=runner.usage.output_tokens,
        estimated_cost=runner.usage.estimated_cost,
        files_created=created,
        files_modified=modified,
        files_deleted=deleted,
        loc_added=loc_added,
        loc_deleted=loc_deleted,
        self_validation=runner.self_validation.passed,
        hidden_validation=hidden.passed,
        repair_calls=runner.usage.repair_calls,
        scope_violations=scope_violations,
        declared_success=runner.declared_success,
        exact_pass=exact,
        hidden_check_pass_rate=(
            sum(check.passed for check in hidden.checks) / len(hidden.checks) if hidden.checks else 0
        ),
        functional_score=functional,
        requirement_score=requirements,
        safety_score=safety,
        verifier_adjusted_score=score,
        false_success=runner.declared_success and not hidden.passed,
        infrastructure_failure=infrastructure,
        protocol_mismatch=runner.usage.protocol_mismatch,
        final_status=final_status,
        failure_code=failure_code,
        failure_detail=runner.failure_detail,
    )
    _write_run_artifacts(
        artifact,
        record,
        runner,
        baseline,
        final_inventory,
        diff,
        hidden,
        scope,
    )
    return record


def _run_arm(arm: ArmId, task: TaskSpec, target: Path, session: Path) -> RunnerResult:
    if arm == ArmId.BARE_ONE_SHOT:
        return bare_one_shot.run(task.prompt, target)
    if arm == ArmId.BARE_TWO_STAGE:
        return bare_two_stage.run(task.prompt, target)
    if arm == ArmId.MIMOCODE:
        return mimocode_runner.run(task.prompt, target, session)
    if arm == ArmId.HEPHAESTUS:
        return hephaestus_runner.run(task.prompt, target, session)
    raise ValueError(arm)


def _self_validate(task: TaskSpec, target: Path) -> ValidationResult:
    started = time.monotonic()
    try:
        process = subprocess.run(
            list(task.self_test_command),
            cwd=target,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
            timeout=120,
        )
        return ValidationResult(
            passed=process.returncode == 0 and "Ran 0 tests" not in process.stderr,
            command=" ".join(task.self_test_command),
            exit_code=process.returncode,
            stdout=process.stdout,
            stderr=process.stderr,
            duration_seconds=time.monotonic() - started,
        )
    except subprocess.TimeoutExpired as error:
        return ValidationResult(
            passed=False,
            command=" ".join(task.self_test_command),
            stderr=f"timeout: {error}",
            duration_seconds=time.monotonic() - started,
        )


def _hidden_validate(root: Path, task: TaskSpec, target: Path) -> ValidationResult:
    started = time.monotonic()
    process = subprocess.run(
        [sys.executable, str(root / "validators" / "hidden_validator.py"), task.task_id, str(target)],
        cwd=root / "validators",
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=180,
    )
    try:
        data = json.loads(process.stdout)
        data.update(
            {
                "command": "external deterministic hidden validator",
                "exit_code": process.returncode,
                "stdout": "",
                "stderr": process.stderr,
                "duration_seconds": time.monotonic() - started,
            }
        )
        return ValidationResult.model_validate(data)
    except Exception as error:  # noqa: BLE001 - validator crash is structured evidence
        return ValidationResult(
            passed=False,
            command="external deterministic hidden validator",
            exit_code=process.returncode,
            stderr=f"{process.stderr}\nvalidator parse failure: {error}",
            duration_seconds=time.monotonic() - started,
        )


def validate_pilot(root: Path, records: list[RunRecord]) -> dict[str, Any]:
    checks: dict[str, bool] = {
        "four_arms": {record.arm_id for record in records} == set(ARMS),
        "same_model": all(record.model == "deepseek-v4-flash" for record in records),
        "same_provider": all(
            record.provider == "deepseek" and record.base_url == "https://api.deepseek.com"
            for record in records
        ),
        "mimo_not_auto": True,
        "mimo_fresh_session": True,
        "mimo_model_and_provider": True,
        "mimo_no_forbidden_network_or_push": True,
        "hephaestus_real_provider": True,
        "bare_call_limits": True,
        "hidden_not_in_context": True,
        "targets_unique": len({record.run_id for record in records}) == len(records),
        "accounting_present": True,
        "secrets_absent": True,
        "artifacts_complete": True,
    }
    for record in records:
        artifact = root / "artifacts" / record.run_id
        files = {path.name for path in artifact.iterdir() if path.is_file()}
        checks["artifacts_complete"] &= files >= REQUIRED_ARTIFACTS
        checks["secrets_absent"] &= not scan_artifacts(artifact)
        checks["accounting_present"] &= (
            (artifact / "provider-usage.json").exists()
            and record.logical_provider_calls > 0
            and record.input_tokens > 0
            and record.output_tokens > 0
        )
        if record.arm_id == ArmId.MIMOCODE:
            text = (artifact / "stdout.txt").read_text(encoding="utf-8").lower()
            session_export = json.loads(
                (artifact / "session-export.json").read_text(encoding="utf-8")
            )
            checks["mimo_not_auto"] &= "mimo auto" not in text
            checks["mimo_fresh_session"] &= (
                (root / "mimo-sessions" / record.run_id).is_dir()
                and session_export.get("fresh_session") is True
            )
            checks["mimo_model_and_provider"] &= _mimo_models_are_canonical(session_export)
            checks["mimo_no_forbidden_network_or_push"] &= not _mimo_forbidden_commands(
                session_export
            )
        if record.arm_id == ArmId.HEPHAESTUS:
            session = json.loads((artifact / "session-export.json").read_text(encoding="utf-8"))
            checks["hephaestus_real_provider"] &= (
                session.get("provider") == "deepseek"
                and str(session.get("model", "")).split("/")[-1] == "deepseek-v4-flash"
            )
        if record.arm_id == ArmId.BARE_ONE_SHOT:
            checks["bare_call_limits"] &= record.logical_provider_calls == 1
        if record.arm_id == ArmId.BARE_TWO_STAGE:
            checks["bare_call_limits"] &= record.logical_provider_calls <= 2
        checks["hidden_not_in_context"] &= "hidden_validator" not in (
            artifact / "prompt.txt"
        ).read_text(encoding="utf-8")
    return {
        "protocol_version": PROTOCOL_VERSION,
        "status": "PILOT_VALID" if all(checks.values()) else "BLOCKED_PILOT_INVALID",
        "passed": all(checks.values()),
        "checks": checks,
    }


def _mimo_models_are_canonical(session: dict[str, Any]) -> bool:
    messages = session.get("messages")
    if not isinstance(messages, list):
        return False
    provider_rows = []
    for message in messages:
        data = message.get("data") if isinstance(message, dict) else None
        if isinstance(data, dict) and data.get("providerID"):
            provider_rows.append((data.get("providerID"), data.get("modelID"), data.get("mode")))
    return bool(provider_rows) and all(
        provider == "deepseek-bench"
        and model == "deepseek-v4-flash"
        and mode not in {"max", "compose", "auto"}
        for provider, model, mode in provider_rows
    )


def _mimo_forbidden_commands(session: dict[str, Any]) -> list[str]:
    forbidden = (
        "git push",
        "git clone",
        "curl http",
        "wget http",
        "invoke-webrequest",
        "invoke-restmethod",
        "start-bitstransfer",
        "ssh ",
        "scp ",
    )
    findings: list[str] = []
    parts = session.get("parts")
    if not isinstance(parts, list):
        return ["session parts unavailable"]
    for part in parts:
        data = part.get("data") if isinstance(part, dict) else None
        state = data.get("state") if isinstance(data, dict) else None
        tool_input = state.get("input") if isinstance(state, dict) else None
        command = tool_input.get("command") if isinstance(tool_input, dict) else None
        if isinstance(command, str) and any(marker in command.lower() for marker in forbidden):
            findings.append(command[:200])
    return findings


def _write_run_artifacts(
    artifact: Path,
    record: RunRecord,
    runner: RunnerResult,
    baseline: dict[str, dict[str, Any]],
    final: dict[str, dict[str, Any]],
    diff: str,
    hidden: ValidationResult,
    scope: dict[str, Any],
) -> None:
    assert runner.self_validation is not None
    write_json(artifact / "metadata.json", record.model_dump(mode="json"))
    write_text(artifact / "stdout.txt", runner.stdout)
    write_text(artifact / "stderr.txt", runner.stderr)
    write_json(artifact / "provider-usage.json", runner.usage.model_dump(mode="json"))
    write_json(artifact / "session-export.json", runner.session_export)
    write_text(artifact / "file-list.txt", "\n".join(final) + ("\n" if final else ""))
    write_text(artifact / "diff.patch", diff)
    write_json(artifact / "self-validation.json", runner.self_validation.model_dump(mode="json"))
    write_json(artifact / "hidden-validation.json", hidden.model_dump(mode="json"))
    write_json(artifact / "scope-report.json", scope)
    write_json(
        artifact / "final-status.json",
        {
            "final_status": record.final_status,
            "failure_code": record.failure_code,
            "failure_detail": record.failure_detail,
            "declared_success": record.declared_success,
            "exact_pass": record.exact_pass,
        },
    )
    write_json(artifact / "baseline-inventory.json", baseline)


def _budget_failure(arm: ArmId, runner: RunnerResult, wall_time: float) -> FailureCode | None:
    if wall_time > MAX_WALL_TIME:
        return FailureCode.PROCESS_TIMEOUT
    if runner.usage.output_tokens > MAX_OUTPUT_TOKENS or runner.usage.estimated_cost > MAX_COST:
        return FailureCode.BUDGET_EXCEEDED
    limits = {ArmId.BARE_ONE_SHOT: 1, ArmId.BARE_TWO_STAGE: 2, ArmId.HEPHAESTUS: 3}
    if arm in limits and runner.usage.logical_provider_calls > limits[arm]:
        return FailureCode.BUDGET_EXCEEDED
    if runner.usage.repair_calls > 1:
        return FailureCode.BUDGET_EXCEEDED
    return None


def _init_git(target: Path) -> None:
    for command in (
        ["git", "init", "--quiet"],
        ["git", "add", "."],
        [
            "git",
            "-c",
            "user.name=Harness Benchmark",
            "-c",
            "user.email=benchmark@localhost",
            "commit",
            "--quiet",
            "-m",
            "fixture",
        ],
    ):
        subprocess.run(command, cwd=target, check=True, capture_output=True, text=True)


def _git_diff(target: Path) -> str:
    subprocess.run(["git", "add", "-N", "."], cwd=target, capture_output=True, text=True)
    return subprocess.run(
        ["git", "diff", "--binary", "--no-ext-diff", "HEAD"],
        cwd=target,
        check=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
    ).stdout


def _inventory(root: Path) -> dict[str, dict[str, Any]]:
    output: dict[str, dict[str, Any]] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or ".git" in path.parts or "__pycache__" in path.parts:
            continue
        relative = path.relative_to(root).as_posix()
        content = path.read_bytes()
        output[relative] = {
            "sha256": sha256(content).hexdigest(),
            "bytes": len(content),
            "lines": len(content.splitlines()),
        }
    return output


def _hash_tree(root: Path) -> str:
    digest = sha256()
    for path, metadata in _inventory(root).items():
        digest.update(path.encode())
        digest.update(str(metadata["sha256"]).encode())
    return digest.hexdigest()


def _change_metrics(
    before: dict[str, dict[str, Any]],
    after: dict[str, dict[str, Any]],
    diff: str,
) -> tuple[int, int, int, int, int]:
    created = len(set(after) - set(before))
    deleted = len(set(before) - set(after))
    modified = sum(
        before[path]["sha256"] != after[path]["sha256"] for path in set(before) & set(after)
    )
    added = sum(1 for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in diff.splitlines() if line.startswith("-") and not line.startswith("---"))
    return created, modified, deleted, added, removed


def _scope_report(target: Path, inventory: dict[str, dict[str, Any]]) -> dict[str, Any]:
    violations = []
    for path in target.rglob("*"):
        if path.is_symlink():
            violations.append(f"symlink:{path.relative_to(target).as_posix()}")
    protected = [path for path in inventory if path.lower() in {".env", "credentials"}]
    violations.extend(f"protected:{path}" for path in protected)
    return {
        "target": str(target),
        "observed_files": len(inventory),
        "violations": violations,
        "boundary_method": "fresh target + confined manifest or isolated harness cwd/home",
    }


def _harness_version(arm: ArmId) -> str:
    if arm == ArmId.MIMOCODE:
        return "MiMo-Code 0.1.4"
    if arm == ArmId.HEPHAESTUS:
        return f"Hephaestus protocol {PROTOCOL_VERSION}"
    return f"bare protocol {PROTOCOL_VERSION}"


def _project_next_cost(records: list[RunRecord], arm: ArmId) -> float:
    observed = [
        record.estimated_cost
        for record in records
        if record.arm_id == arm and record.estimated_cost > 0
    ]
    return (sum(observed) / len(observed) * 1.25) if observed else 0.01


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("prepare", "pilot", "main", "report"))
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    if args.command == "prepare":
        prepare_live_root(args.root)
        print(args.root)
        return 0
    if args.command in {"pilot", "main"}:
        run_phase(args.root, args.command)
        return 0
    records = load_records(args.root / "artifacts")
    phase = "main" if any(record.phase == "main" for record in records) else "pilot"
    write_reports(args.root, records, phase=phase)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
