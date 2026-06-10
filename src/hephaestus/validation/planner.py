"""Build validation execution plans from repo intelligence."""

from __future__ import annotations

from pathlib import Path
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
