from pathlib import Path

from typer.testing import CliRunner

from hephaestus.cli.main import app
from hephaestus.decision import DecisionTraceRepository
from hephaestus.outcomes import OutcomeRepository
from hephaestus.policy import (
    PolicyProfileType,
    developer_profile,
    research_profile,
    strict_profile,
)
from hephaestus.tool_runtime import (
    ShellCommandRequest,
    ToolActionType,
    ToolExecutionStatus,
    ToolRiskLevel,
    ToolRuntime,
    ToolRuntimeRepository,
    classify_tool_action,
)
from hephaestus.tool_runtime.filesystem import (
    FilesystemReadRequest,
    FilesystemSearchRequest,
    is_protected_path,
    list_directory,
    read_file,
    search_files,
)
from hephaestus.tool_runtime.schemas import ToolAction, ToolApprovalPolicy

runner = CliRunner()


def test_tool_schemas() -> None:
    action = ToolAction(
        action_type=ToolActionType.RUN_COMMAND,
        workspace_path=".",
        command="python --version",
    )
    policy = ToolApprovalPolicy(profile_id="developer", profile_name="Developer")

    assert action.id.startswith("tool_action_")
    assert action.action_type == ToolActionType.RUN_COMMAND
    assert policy.block_destructive is True


def test_risk_classifier_policy_profiles() -> None:
    safe = classify_tool_action(
        ToolActionType.RUN_COMMAND,
        policy_profile=developer_profile(),
        command="python --version",
    )
    destructive = classify_tool_action(
        ToolActionType.RUN_COMMAND,
        policy_profile=developer_profile(),
        command="rm -rf dist",
    )
    research = classify_tool_action(
        ToolActionType.RUN_COMMAND,
        policy_profile=research_profile(),
        command="uv run pytest",
    )
    strict_external = classify_tool_action(
        ToolActionType.RUN_COMMAND,
        policy_profile=strict_profile(),
        command="git push origin main",
    )

    assert safe.risk_level == ToolRiskLevel.SAFE_VALIDATION
    assert safe.approval_required is False
    assert destructive.risk_level == ToolRiskLevel.DESTRUCTIVE
    assert destructive.blocked is True
    assert research.approval_required is True
    assert strict_external.blocked is True


def test_filesystem_list_read_search_and_secret_protection(tmp_path: Path) -> None:
    readme = tmp_path / "README.md"
    readme.write_text("Hephaestus learns decision quality.\n", encoding="utf-8")
    secret = tmp_path / ".env"
    secret.write_text("SECRET_TOKEN=abc123\n", encoding="utf-8")

    listing = list_directory(tmp_path)
    read_result = read_file(FilesystemReadRequest(path="README.md", workspace_path=str(tmp_path)))
    protected = read_file(FilesystemReadRequest(path=".env", workspace_path=str(tmp_path)))
    search = search_files(
        FilesystemSearchRequest(
            query="Hephaestus",
            path=".",
            workspace_path=str(tmp_path),
        )
    )

    assert {entry.path for entry in listing.entries} >= {"README.md", ".env"}
    assert (read_result.content or "").splitlines() == ["Hephaestus learns decision quality."]
    assert protected.protected is True
    assert protected.content is None
    assert "SECRET_TOKEN" not in (protected.message or "")
    assert is_protected_path(secret)
    assert search.matches[0].path == "README.md"
    assert ".env" in search.skipped_protected


def test_shell_dry_run_execution_timeout_and_truncation(tmp_path: Path) -> None:
    runtime = ToolRuntime(tmp_path / "hephaestus.db", workspace_path=tmp_path)

    _plan, _action, dry = runtime.run_command(
        ShellCommandRequest(command="python --version", dry_run=True)
    )
    _plan, action, executed = runtime.run_command(
        ShellCommandRequest(command="python --version", yes=True)
    )
    _plan, _action, timed_out = runtime.run_command(
        ShellCommandRequest(
            command='python -c "import time; time.sleep(2)"',
            yes=True,
            timeout_seconds=1,
        )
    )
    _plan, _action, truncated = runtime.run_command(
        ShellCommandRequest(
            command='python -c "print(' + "'x'" + '*20000)"',
            yes=True,
            max_output_chars=100,
        )
    )

    assert dry.status == ToolExecutionStatus.DRY_RUN
    assert executed.status == ToolExecutionStatus.SUCCEEDED
    assert executed.exit_code == 0
    assert timed_out.status == ToolExecutionStatus.TIMED_OUT
    assert truncated.output_truncated is True
    assert ToolRuntimeRepository(tmp_path / "hephaestus.db").get_action(action.id) is not None


def test_approval_required_and_persistence(tmp_path: Path) -> None:
    runtime = ToolRuntime(tmp_path / "hephaestus.db", workspace_path=tmp_path)

    _plan, action, result = runtime.run_command(
        ShellCommandRequest(command="git push origin main")
    )
    approvals = ToolRuntimeRepository(tmp_path / "hephaestus.db").list_approvals_for_action(
        action.id
    )

    assert result.status == ToolExecutionStatus.APPROVAL_REQUIRED
    assert approvals
    assert approvals[0].approved is False


def test_patch_checkpoint_restore_and_learning_links(tmp_path: Path) -> None:
    target = tmp_path / "README.md"
    target.write_text("Hermes learns workflows.\n", encoding="utf-8")
    runtime = ToolRuntime(tmp_path / "hephaestus.db", workspace_path=tmp_path)

    _proposal_action, _proposal_result, proposal = runtime.propose_patch(
        "README.md",
        find="Hermes learns workflows.",
        replace="Hephaestus learns decision quality.",
    )
    _plan, apply_action, apply_result, patch_result = runtime.apply_patch(
        proposal.id,
        yes=True,
    )
    assert patch_result is not None
    checkpoint_id = patch_result.checkpoint_id
    assert checkpoint_id is not None
    assert target.read_text(encoding="utf-8") == "Hephaestus learns decision quality.\n"

    _restore_plan, _restore_action, restore_result, restored = runtime.restore_checkpoint(
        checkpoint_id,
        yes=True,
    )

    assert apply_result.status == ToolExecutionStatus.SUCCEEDED
    assert restore_result.status == ToolExecutionStatus.RESTORED
    assert restored is not None
    assert target.read_text(encoding="utf-8") == "Hermes learns workflows.\n"
    assert apply_action.decision_trace_id is not None
    assert DecisionTraceRepository(tmp_path / "hephaestus.db").get_trace(
        apply_action.decision_trace_id
    )
    assert OutcomeRepository(tmp_path / "hephaestus.db").list_outcomes(
        decision_trace_id=apply_action.decision_trace_id
    )


def test_tool_cli_smoke(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text(
        "Hephaestus is a self-improving local AI agent.\n",
        encoding="utf-8",
    )

    list_result = runner.invoke(app, ["tools", "list", "."])
    read_result = runner.invoke(app, ["tools", "read", "README.md"])
    search_result = runner.invoke(
        app,
        ["tools", "search", "Hephaestus", "--path", "README.md"],
    )
    dry_run = runner.invoke(app, ["tools", "run", "python --version", "--dry-run"])
    run_result = runner.invoke(app, ["tools", "run", "python --version", "--yes"])
    actions = runner.invoke(app, ["tools", "actions"])

    assert list_result.exit_code == 0
    assert "Directory" in list_result.output
    assert read_result.exit_code == 0
    assert "self-improving" in read_result.output
    assert search_result.exit_code == 0
    assert "README.md" in search_result.output
    assert dry_run.exit_code == 0
    assert "dry_run" in dry_run.output
    assert run_result.exit_code == 0
    assert "succeeded" in run_result.output
    assert actions.exit_code == 0
    assert "Tool Actions" in actions.output


def test_patch_cli_and_action_show(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    target = tmp_path / "README.md"
    target.write_text("old phrase\n", encoding="utf-8")

    propose = runner.invoke(
        app,
        [
            "tools",
            "patch",
            "propose",
            "README.md",
            "--find",
            "old phrase",
            "--replace",
            "new phrase",
        ],
    )
    patch_id = next(part for part in propose.output.split() if part.startswith("patch_"))
    apply = runner.invoke(app, ["tools", "patch", "apply", patch_id, "--yes"])
    checkpoints = runner.invoke(app, ["tools", "checkpoint", "list"])
    actions = ToolRuntimeRepository().list_actions(limit=1)
    show = runner.invoke(app, ["tools", "action", "show", actions[0].id])

    assert propose.exit_code == 0
    assert apply.exit_code == 0
    assert target.read_text(encoding="utf-8") == "new phrase\n"
    assert checkpoints.exit_code == 0
    assert "Tool Checkpoints" in checkpoints.output
    assert show.exit_code == 0
    assert actions[0].id in show.output


def test_conversation_propose_tools_output(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname='demo'\nrequires-python='>=3.12'\n",
        encoding="utf-8",
    )
    result = runner.invoke(
        app,
        [
            "discuss",
            "Propose a safe validation plan for this repo.",
            "--repo",
            ".",
            "--provider",
            "local",
            "--propose-tools",
        ],
    )

    assert result.exit_code == 0
    assert "Proposed Tool Actions" in result.output
    assert "heph tools" in result.output
    assert PolicyProfileType.DEVELOPER.value != ""
