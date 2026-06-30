"""Build validation execution plans from repo intelligence."""

from __future__ import annotations

from pathlib import Path, PurePosixPath
from typing import TypedDict
from uuid import uuid4

from hephaestus.decision import DecisionAlternative, DecisionTraceRepository, SafetyDecision, metric
from hephaestus.policy import PolicyRepository
from hephaestus.repo import RepoProfile, RepoProfileRepository, inspect_repository
from hephaestus.repo.schemas import ScriptCommand, TestCommand
from hephaestus.storage import RunRecord, RunRepository
from hephaestus.tool_runtime import ToolActionType, ToolRiskLevel, classify_tool_action
from hephaestus.validation.analysis import (
    classify_validation_command_type,
    command_type_order,
)
from hephaestus.validation.repository import ValidationRepository
from hephaestus.validation.schemas import (
    ValidationCommand,
    ValidationCommandType,
    ValidationExecutionPlan,
)


class NormalizedValidationCommand(TypedDict):
    command: str
    model_command: str
    reason: str
    source: str
    framework: str
    timeout_seconds: int


class NormalizedValidationPlan(TypedDict):
    commands: list[NormalizedValidationCommand]
    normalization_reasons: list[str]
    expected_test_locations: list[str]
    validation_stages: list[str]
    fallback_commands: list[str]


class ValidationPlanner:
    """Create approval-aware validation plans from repo profiles."""

    def __init__(self, database_path: Path | str | None = None) -> None:
        self.repository = ValidationRepository(database_path)
        self.database_path = self.repository.database_path
        self.repo_repository = RepoProfileRepository(self.database_path)
        self.policy_repository = PolicyRepository(self.database_path)
        self.run_repository = RunRepository(self.database_path)
        self.trace_repository = DecisionTraceRepository(self.database_path)

    def build_plan(
        self,
        path: Path | str,
        *,
        profile: RepoProfile | None = None,
        release_plan_id: str | None = None,
        use_latest_profile: bool = True,
        persist: bool = True,
    ) -> ValidationExecutionPlan:
        """Build and optionally persist a validation execution plan."""

        root = Path(path).resolve()
        repo_profile = profile or self._resolve_profile(root, use_latest_profile=use_latest_profile)
        plan_id = f"validation_plan_{uuid4().hex[:12]}"
        run_id: str | None = None
        if persist:
            run = self.run_repository.save_run(
                RunRecord(
                    goal=f"Validation plan for {repo_profile.name}",
                    mode="validation_plan",
                    status="running",
                )
            )
            run_id = run.id

        commands = self._commands_for_profile(repo_profile, plan_id=plan_id)
        notes = [
            "Validation commands are selected from repo manifests, scripts, and detected tools.",
            "Execution is approval-gated; use `heph validate run ... --yes` after reviewing the plan.",
        ]
        if not commands:
            notes.append("No supported validation commands were detected.")
        if any(command.blocked for command in commands):
            notes.append("Blocked commands are retained as evidence but will not be executed.")
        if repo_profile.validation_plan.notes:
            notes.extend(repo_profile.validation_plan.notes)

        commands, trace_ids = self._record_plan_traces(
            commands,
            run_id=run_id,
            profile=repo_profile,
            persist=persist,
        )
        plan = ValidationExecutionPlan(
            id=plan_id,
            repo_path=str(root),
            repo_profile_id=repo_profile.id,
            release_plan_id=release_plan_id,
            run_id=run_id,
            commands=commands,
            notes=notes,
            confidence=repo_profile.validation_plan.confidence,
            decision_trace_ids=trace_ids,
            metadata={
                "repo_name": repo_profile.name,
                "detected_languages": repo_profile.detected_languages,
                "package_managers": [
                    f"{manager.ecosystem}:{manager.name}"
                    for manager in repo_profile.package_managers
                ],
            },
        )
        if persist:
            self.repository.save_plan(plan)
            self.run_repository.complete_run(
                run_id or "",
                estimated_input_tokens=0,
                estimated_output_tokens=0,
                estimated_cost=0.0,
                objective_score=plan.confidence,
                risk_score=max((_risk_value(command.risk_level) for command in commands), default=0.0),
                summary=f"Validation plan created with {len(commands)} command(s).",
                status="completed",
            )
        return plan

    def _resolve_profile(self, path: Path, *, use_latest_profile: bool) -> RepoProfile:
        if use_latest_profile:
            latest = self.repo_repository.latest_profile_for_path(path)
            if latest is not None:
                return latest
        report = inspect_repository(path)
        self.repo_repository.save_inspection(report)
        return report.profile

    def _commands_for_profile(
        self,
        profile: RepoProfile,
        *,
        plan_id: str,
    ) -> list[ValidationCommand]:
        policy_profile = self.policy_repository.get_active_profile()
        candidates = _dedupe_test_commands(
            [
                *profile.lint_commands,
                *profile.test_commands,
                *profile.build_commands,
                *profile.validation_plan.commands,
                *self._script_validation_commands(profile.scripts),
            ]
        )
        commands: list[ValidationCommand] = []
        for index, candidate in enumerate(candidates, start=1):
            command_type = classify_validation_command_type(
                candidate.command,
                framework=candidate.framework,
                source=candidate.source,
            )
            decision = classify_tool_action(
                ToolActionType.RUN_COMMAND,
                policy_profile=policy_profile,
                command=candidate.command,
            )
            blocked = (
                decision.blocked
                or decision.risk_level
                in {ToolRiskLevel.DESTRUCTIVE, ToolRiskLevel.EXTERNAL_SIDE_EFFECT}
            )
            requires_approval = True
            reasons = [
                *candidate.reasons,
                *decision.reasons,
                "validation execution requires explicit approval via --yes",
            ]
            if blocked:
                reasons.append("blocked from validation execution")
            commands.append(
                ValidationCommand(
                    id=f"validation_cmd_{uuid4().hex[:12]}",
                    plan_id=plan_id,
                    repo_profile_id=profile.id,
                    command=candidate.command,
                    command_type=command_type,
                    source=candidate.source,
                    framework=candidate.framework,
                    order=index,
                    risk_level=decision.risk_level,
                    requires_approval=requires_approval,
                    tool_policy_approval_required=decision.approval_required,
                    blocked=blocked,
                    reasons=reasons,
                    metadata={
                        "repo_classification": candidate.classification.value,
                        "policy_decision": decision.policy_decision,
                    },
                )
            )
        ordered = sorted(
            commands,
            key=lambda command: (
                command_type_order(command.command_type),
                command.order,
                command.command,
            ),
        )
        return [
            command.model_copy(update={"order": index})
            for index, command in enumerate(ordered, start=1)
        ]

    def _script_validation_commands(self, scripts: list[ScriptCommand]) -> list[TestCommand]:
        commands: list[TestCommand] = []
        for script in scripts:
            command_type = classify_validation_command_type(
                script.command,
                source=script.source,
                name=script.name,
                framework=script.package_manager,
            )
            if command_type == ValidationCommandType.CUSTOM:
                continue
            commands.append(
                TestCommand(
                    command=script.command,
                    source=f"{script.source}:{script.name}",
                    framework=script.package_manager,
                    classification=script.classification,
                    reasons=script.reasons,
                    requires_approval=script.requires_approval,
                )
            )
        return commands

    def _record_plan_traces(
        self,
        commands: list[ValidationCommand],
        *,
        run_id: str | None,
        profile: RepoProfile,
        persist: bool,
    ) -> tuple[list[ValidationCommand], list[str]]:
        if not persist or run_id is None:
            return commands, []
        if not commands:
            trace = SafetyDecision(
                run_id=run_id,
                phase="validation_planning",
                selected_option="no_validation_commands_detected",
                alternatives=[],
                rationale=(
                    "No supported validation commands were detected from repo manifests, "
                    "scripts, package managers, or language tooling."
                ),
                metrics=[metric("repo_profile_id", profile.id), metric("command_count", 0)],
                objective_score=0.0,
                confidence=0.72,
                constraints_considered=["repo manifests", "supported validation command catalog"],
                tags=["validation", "planning", "missing-commands"],
                caused_by=[profile.id],
                will_affect=["release_readiness", "learning_signals"],
                learning_hooks=["missing_validation_commands"],
            )
            self.trace_repository.save_trace(trace)
            return commands, [trace.id]

        updated_commands: list[ValidationCommand] = []
        trace_ids: list[str] = []
        for command in commands:
            selected = "blocked" if command.blocked else "selected"
            if command.requires_approval and not command.blocked:
                selected = "approval_required"
            trace = SafetyDecision(
                run_id=run_id,
                phase="validation_planning",
                selected_option=f"{selected}: {command.command}",
                alternatives=[
                    DecisionAlternative(
                        option_id="invent_unsupported_command",
                        rejection_reason="Validation execution only uses commands supported by repo signals.",
                        violated_constraints=["repo evidence", "non-hallucinated validation"],
                        risk=0.6,
                    )
                ],
                rationale=_plan_rationale(command),
                metrics=[
                    metric("repo_profile_id", profile.id),
                    metric("command_id", command.id),
                    metric("command_type", command.command_type.value),
                    metric("risk_level", command.risk_level.value),
                    metric("requires_approval", command.requires_approval),
                    metric("blocked", command.blocked),
                ],
                objective_score=0.0 if command.blocked else 1.0,
                confidence=0.84,
                constraints_considered=[
                    "repo-supported command",
                    "tool runtime risk classifier",
                    "policy approval profile",
                    "no destructive validation execution",
                ],
                tags=["validation", "planning", command.command_type.value, command.risk_level.value],
                caused_by=[profile.id],
                will_affect=["validation_execution", "release_readiness"],
                learning_hooks=["validation_command_outcome", "approval_precision"],
            )
            self.trace_repository.save_trace(trace)
            trace_ids.append(trace.id)
            updated_commands.append(command.model_copy(update={"decision_trace_id": trace.id}))
        return updated_commands, trace_ids


def build_validation_execution_plan(
    path: Path | str,
    *,
    database_path: Path | str | None = None,
    release_plan_id: str | None = None,
    use_latest_profile: bool = True,
    persist: bool = True,
) -> ValidationExecutionPlan:
    """Convenience wrapper for building a validation execution plan."""

    return ValidationPlanner(database_path).build_plan(
        path,
        release_plan_id=release_plan_id,
        use_latest_profile=use_latest_profile,
        persist=persist,
    )


def build_candidate_validation_plan(
    path: Path | str,
    *,
    model_commands: list[str],
    changed_files: list[str],
    expected_files: list[str] | None = None,
    database_path: Path | str | None = None,
    repo_profile_id: str | None = None,
    persist: bool = False,
) -> ValidationExecutionPlan:
    """Normalize model-proposed validation commands into a deterministic plan."""

    root = Path(path).resolve()
    plan_id = f"validation_plan_{uuid4().hex[:12]}"
    normalized = normalize_model_validation_commands(
        root,
        model_commands=model_commands,
        changed_files=changed_files,
        expected_files=expected_files or [],
    )
    commands = [
        ValidationCommand(
            id=f"validation_cmd_{uuid4().hex[:12]}",
            plan_id=plan_id,
            repo_profile_id=repo_profile_id,
            command=item["command"],
            command_type=classify_validation_command_type(item["command"], source=item["source"]),
            source=item["source"],
            framework=item["framework"],
            order=index,
            risk_level=ToolRiskLevel.SAFE_VALIDATION,
            requires_approval=True,
            reasons=[item["reason"], "normalized validation execution requires approval"],
            timeout_seconds=int(item["timeout_seconds"]),
            metadata={
                "model_command": item["model_command"],
                "normalization_reason": item["reason"],
                "expected_test_locations": normalized["expected_test_locations"],
                "fallback_commands": normalized["fallback_commands"],
            },
        )
        for index, item in enumerate(normalized["commands"], start=1)
    ]
    plan = ValidationExecutionPlan(
        id=plan_id,
        repo_path=str(root),
        repo_profile_id=repo_profile_id,
        commands=commands,
        notes=[
            "Model-proposed validation commands are candidates and were normalized deterministically.",
            *[str(reason) for reason in normalized["normalization_reasons"]],
        ],
        confidence=0.82 if commands else 0.35,
        metadata={
            "model_proposed_commands": model_commands,
            "deterministic_normalized_commands": [command.command for command in commands],
            "normalization_reasons": normalized["normalization_reasons"],
            "expected_test_locations": normalized["expected_test_locations"],
            "validation_stages": normalized["validation_stages"],
            "stage_count": len(normalized["validation_stages"]),
            "fallback_commands": normalized["fallback_commands"],
            "timeouts": {command.command: command.timeout_seconds for command in commands},
        },
    )
    if persist:
        ValidationRepository(database_path).save_plan(plan)
    return plan


def normalize_model_validation_commands(
    root: Path,
    *,
    model_commands: list[str],
    changed_files: list[str],
    expected_files: list[str],
) -> NormalizedValidationPlan:
    """Return normalized command records and explain every normalization."""

    files = _dedupe_paths([*changed_files, *expected_files, *_existing_test_files(root)])
    test_files = [path for path in files if _is_python_test_file(path)]
    has_python = any(path.endswith(".py") for path in files) or (root / "pyproject.toml").exists()
    test_dirs = _test_dirs(test_files)
    commands: list[NormalizedValidationCommand] = []
    reasons: list[str] = []
    fallback_commands: list[str] = []
    seen: set[str] = set()
    proposed = [command for command in model_commands if command.strip()]

    for command in proposed:
        normalized_command, reason = _normalize_python_test_command(command, test_dirs)
        if normalized_command is None:
            if _safe_functional_smoke(command):
                normalized_command = command.strip()
                reason = "kept safe functional smoke command proposed by model"
            else:
                reasons.append(
                    f"Skipped unsafe or non-validation candidate `{command}`; functional smoke is opt-in and bounded."
                )
                continue
        if normalized_command in seen:
            continue
        seen.add(normalized_command)
        reasons.append(reason)
        commands.append(
            {
                "command": normalized_command,
                "model_command": command,
                "reason": reason,
                "source": "deterministic_normalizer",
                "framework": "python-unittest" if "unittest" in normalized_command else "",
                "timeout_seconds": 120,
            }
        )

    if has_python and test_files and not any("unittest" in str(item["command"]) or "pytest" in str(item["command"]) for item in commands):
        command = _preferred_unittest_command(test_dirs)
        reason = "added deterministic unittest discovery because Python test files were detected"
        commands.append(
            {
                "command": command,
                "model_command": "",
                "reason": reason,
                "source": "deterministic_normalizer",
                "framework": "python-unittest",
                "timeout_seconds": 120,
            }
        )
        reasons.append(reason)

    if test_dirs:
        fallback = _preferred_unittest_command(test_dirs)
        if all(str(item["command"]) != fallback for item in commands):
            fallback_commands.append(fallback)

    stages = ["structure"]
    if has_python:
        stages.append("syntax/import")
    if test_files:
        stages.extend(["test_discovery", "test_execution"])
    return {
        "commands": commands,
        "normalization_reasons": _dedupe_text(reasons),
        "expected_test_locations": sorted(test_files),
        "validation_stages": stages,
        "fallback_commands": fallback_commands[:1],
    }


def _dedupe_test_commands(commands: list[TestCommand]) -> list[TestCommand]:
    seen: set[str] = set()
    deduped: list[TestCommand] = []
    for command in commands:
        normalized = " ".join(command.command.split())
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(command)
    return deduped


def _dedupe_text(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value.strip()))


def _dedupe_paths(values: list[str]) -> list[str]:
    normalized = [str(PurePosixPath(value.replace("\\", "/"))) for value in values if value.strip()]
    return _dedupe_text(normalized)


def _normalize_python_test_command(command: str, test_dirs: list[str]) -> tuple[str | None, str]:
    normalized = " ".join(command.split())
    lower = normalized.lower()
    if "pytest" in lower:
        return normalized, "kept pytest command because the model explicitly proposed pytest"
    if "python -m unittest" not in lower and "unittest" not in lower:
        return None, ""
    preferred = _preferred_unittest_command(test_dirs)
    if test_dirs and normalized == "python -m unittest discover -v":
        return (
            preferred,
            "normalized generic unittest discovery to explicit tests directory and test_*.py pattern",
        )
    if test_dirs and " discover" in lower and " -s " not in f" {lower} ":
        return (
            preferred,
            "normalized unittest discovery without -s because test files exist under an explicit tests directory",
        )
    return normalized, "kept model unittest command; it already specifies discovery scope"


def _preferred_unittest_command(test_dirs: list[str]) -> str:
    directory = "tests" if "tests" in test_dirs else (test_dirs[0] if test_dirs else ".")
    return f'python -m unittest discover -s {directory} -p "test_*.py" -v'


def _existing_test_files(root: Path) -> list[str]:
    ignored = {".git", ".hephaestus", ".venv", "node_modules", "__pycache__"}
    if not root.exists():
        return []
    return [
        str(path.relative_to(root)).replace("\\", "/")
        for path in root.rglob("test_*.py")
        if path.is_file() and not any(part in ignored for part in path.relative_to(root).parts)
    ]


def _is_python_test_file(path: str) -> bool:
    pure = PurePosixPath(path.replace("\\", "/"))
    return pure.name.startswith("test_") and pure.suffix == ".py"


def _test_dirs(test_files: list[str]) -> list[str]:
    dirs = [
        str(PurePosixPath(path.replace("\\", "/")).parent)
        for path in test_files
    ]
    return _dedupe_text(["." if item == "." else item for item in dirs])


def _safe_functional_smoke(command: str) -> bool:
    normalized = " ".join(command.split()).lower()
    if not normalized:
        return False
    read_only_tokens = (" --help", " -h", " version", " --version")
    return normalized.startswith("python -m ") and any(token in normalized for token in read_only_tokens)


def _plan_rationale(command: ValidationCommand) -> str:
    if command.blocked:
        return (
            f"`{command.command}` was detected as {command.command_type.value}, but its "
            "risk classification prevents validation execution."
        )
    return (
        f"`{command.command}` was selected as {command.command_type.value} validation "
        "because repo intelligence found supporting manifests, scripts, or tool config. "
        "Execution requires explicit approval via --yes."
    )


def _risk_value(risk_level: ToolRiskLevel) -> float:
    return {
        ToolRiskLevel.SAFE_READONLY: 0.05,
        ToolRiskLevel.SAFE_VALIDATION: 0.15,
        ToolRiskLevel.MEDIUM_RISK: 0.4,
        ToolRiskLevel.HIGH_RISK: 0.7,
        ToolRiskLevel.EXTERNAL_SIDE_EFFECT: 0.85,
        ToolRiskLevel.DESTRUCTIVE: 1.0,
    }[risk_level]
