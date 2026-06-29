"""Hephaestus CLI."""

from __future__ import annotations

import json
import platform
import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated

import typer
from pydantic import BaseModel, Field
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from hephaestus import __version__
from hephaestus.benchmarks import load_all_benchmarks, load_benchmark, run_benchmark
from hephaestus.benchmarks.reporter import (
    print_benchmark_list,
    print_benchmark_result,
    print_benchmark_show,
    results_to_json,
)
from hephaestus.coding_loop import (
    CodingLoopExecutor,
    CodingLoopRepository,
    CodingScopeType,
)
from hephaestus.coding_loop.greenfield import CodingProviderError, GreenfieldCodingExecutor
from hephaestus.coding_loop.renderer import (
    build_coding_change_renderable,
    build_coding_conversation_proposal,
    build_coding_plan_renderable,
    build_coding_result_renderable,
    build_coding_results_table,
    build_coding_show_renderable,
)
from hephaestus.coding_loop.schemas import CodingWorkflowMode
from hephaestus.conversation import (
    ConversationMemoryUpdate,
    ConversationRequest,
    ConversationResponse,
    ConversationService,
    DeliberationMode,
)
from hephaestus.conversation.providers import (
    conversation_model_profiles,
    conversation_provider_statuses,
)
from hephaestus.conversation.renderer import (
    build_conversation_response_renderable,
    build_conversation_sessions_table,
    build_conversation_show_renderable,
)
from hephaestus.conversation_eval import (
    load_all_conversation_benchmarks,
    run_conversation_benchmarks,
)
from hephaestus.conversation_eval.renderer import (
    build_conversation_benchmark_result_renderable,
    build_conversation_benchmark_summary_table,
    print_conversation_benchmark_list,
)
from hephaestus.core.config import DEFAULT_CONFIG, PrivacyLevel, RiskLevel
from hephaestus.decision import (
    DecisionTraceRepository,
    aggregate_decision_stats,
    build_budget_decision,
    build_context_selection_decision,
    build_decision_stats_renderable,
    build_decision_summary_renderable,
    build_model_routing_decision,
    build_model_routing_error_decision,
    build_optimization_decision,
    build_run_explanation_renderable,
    build_safety_approval_decision,
    build_task_selection_decision,
    summarize_decisions,
)
from hephaestus.memory import MemoryItem, MemoryType
from hephaestus.models import DeepSeekProvider, ModelProfile, fake_model_profiles
from hephaestus.models.live_smoke import (
    LiveSmokeConfig,
    LiveSmokeResult,
    SmokeCase,
    run_live_smoke,
)
from hephaestus.optimize.context_packer import ContextCandidate, pack_context
from hephaestus.optimize.model_router import ModelRouteRequest, ModelRoutingError, route_model
from hephaestus.optimize.task_scheduler import compare_schedulers
from hephaestus.optimize.token_firewall import BudgetDecision, TokenBudget, evaluate_budget
from hephaestus.outcomes import (
    OutcomeLearningSummary,
    OutcomeRecord,
    OutcomeRepository,
    OutcomeStatus,
    build_failure_memory_table,
    build_learning_signal_table,
    build_outcome_list_renderable,
    build_outcome_show_renderable,
    build_outcome_summary_renderable,
    build_policy_update_table,
    build_reflection_report_renderable,
    reflect_on_outcome,
    reflect_run_outcomes,
    summarize_outcome_learning,
)
from hephaestus.pareto import ParetoRepository, get_preference_profile
from hephaestus.pareto.analysis import (
    build_pareto_selection_trace,
    compare_benchmark_case,
)
from hephaestus.pareto.renderer import (
    build_frontier_detail_renderable,
    build_frontier_list_table,
    build_pareto_summary_panel,
    build_pareto_summary_table,
    build_preference_profiles_table,
    build_selection_renderable,
)
from hephaestus.pareto.schemas import ParetoSelectionResult
from hephaestus.policy import (
    PolicyRepository,
    evaluate_policy_request,
    load_all_policy_benchmarks,
    run_policy_benchmark,
)
from hephaestus.policy.renderer import (
    build_active_policy_panel,
    build_policy_benchmark_fixture_table,
    build_policy_benchmark_list_table,
    build_policy_evaluation_renderable,
    build_policy_profile_renderable,
    build_policy_profiles_table,
)
from hephaestus.policy_learning import (
    DecisionArea,
    DecisionQualityProfile,
    ProfileApplicationResult,
    ProfileStore,
    apply_context_packer_profiles,
    apply_failure_memory_context_boost,
    apply_model_router_profiles,
    apply_safety_profiles,
    apply_scheduler_profiles,
    apply_token_firewall_profiles,
    build_profile_application_summary_renderable,
    build_profile_application_table,
    build_profile_list_renderable,
    build_profile_show_renderable,
    build_profile_suggest_renderable,
    build_profile_summary_renderable,
    suggest_profiles,
)
from hephaestus.qubo.analysis import build_qubo_solution_trace, compare_benchmark_with_qubo
from hephaestus.qubo.formulations import formulate_benchmark_case
from hephaestus.qubo.ising import qubo_to_ising
from hephaestus.qubo.renderer import (
    build_formulation_report_renderable,
    build_ising_renderable,
    build_qubo_comparison_table,
    build_qubo_explain_renderable,
    build_qubo_problem_list_table,
    build_qubo_problem_renderable,
    build_qubo_solution_renderable,
    build_qubo_summary_panel,
)
from hephaestus.qubo.repository import QuboRepository
from hephaestus.qubo.schemas import QuboProblemType
from hephaestus.qubo.solver import solve as solve_qubo
from hephaestus.release import (
    ReleasePlanningError,
    ReleasePlanningOrchestrator,
    ReleasePlanningRequest,
    ReleasePlanRepository,
)
from hephaestus.release.renderer import (
    build_release_demo_renderable,
    build_release_list_table,
    build_release_show_renderable,
)
from hephaestus.repo import (
    RepoProfile,
    RepoProfileRepository,
    inspect_repository,
    repo_profile_to_benchmark_case,
    repo_tasks_to_optimizer_tasks,
)
from hephaestus.repo.renderer import (
    build_repo_inspection_renderable,
    build_repo_plan_renderable,
    build_repo_profile_list_table,
    build_repo_show_renderable,
    build_repo_tasks_table,
)
from hephaestus.spec.goal import build_goal_spec
from hephaestus.spec.tasks import Task, generate_initial_tasks
from hephaestus.storage import (
    ApprovalRecord,
    RunDecisionRecord,
    RunRecord,
    RunRepository,
    RunTaskRecord,
    SqliteMemoryRepository,
    get_default_database_path,
    init_database,
)
from hephaestus.strategic_memory import (
    StrategicMemoryEvidence,
    StrategicMemoryItem,
    StrategicMemoryRepository,
    StrategicMemoryScope,
    StrategicMemorySource,
    StrategicMemoryStability,
    StrategicMemoryType,
)
from hephaestus.strategic_memory.renderer import (
    build_conflict_table,
    build_strategic_context_renderable,
    build_strategic_memory_detail,
    build_strategic_memory_table,
)
from hephaestus.studio.launcher import run_studio, studio_doctor
from hephaestus.studio.security import DEFAULT_STUDIO_HOST, DEFAULT_STUDIO_PORT, studio_url
from hephaestus.studio.services import StudioService
from hephaestus.tool_runtime import (
    ShellCommandRequest,
    ToolRuntime,
    ToolRuntimeRepository,
    propose_tool_actions,
)
from hephaestus.tool_runtime.renderer import (
    build_checkpoint_detail,
    build_checkpoint_table,
    build_filesystem_list_table,
    build_filesystem_read_renderable,
    build_filesystem_search_table,
    build_patch_proposal_renderable,
    build_tool_action_detail,
    build_tool_actions_table,
    build_tool_plan_renderable,
    build_tool_proposals_table,
    build_tool_result_renderable,
)
from hephaestus.validation import (
    ValidationCommandType,
    ValidationExecutor,
    ValidationPlanner,
    ValidationRepository,
)
from hephaestus.validation.renderer import (
    build_validation_plan_renderable,
    build_validation_results_table,
    build_validation_show_renderable,
    build_validation_suite_renderable,
)

console = Console()

app = typer.Typer(
    name="heph",
    help="Hephaestus: a self-improving local AI agent for project memory, scoped coding, and validation.",
    no_args_is_help=True,
)
memory_app = typer.Typer(help="Persistent local memory commands.", no_args_is_help=True)
budget_app = typer.Typer(help="Token and cost budget commands.", no_args_is_help=True)
db_app = typer.Typer(help="Local SQLite database commands.", no_args_is_help=True)
run_app = typer.Typer(help="Run history commands.", no_args_is_help=True)
benchmark_app = typer.Typer(help="Optimizer benchmark commands.", no_args_is_help=True)
outcome_app = typer.Typer(help="Decision outcome commands.", no_args_is_help=True)
learn_app = typer.Typer(help="Outcome-derived learning artifact commands.", no_args_is_help=True)
profile_app = typer.Typer(help="Decision quality profile commands.", no_args_is_help=True)
pareto_app = typer.Typer(help="Pareto decision frontier commands.", no_args_is_help=True)
qubo_app = typer.Typer(help="QUBO and Ising formulation commands.", no_args_is_help=True)
repo_app = typer.Typer(help="Read-only local repository intelligence commands.", no_args_is_help=True)
release_app = typer.Typer(help="Repo-aware release planning demo commands.", no_args_is_help=True)
validate_app = typer.Typer(help="Real repo validation planning and execution.", no_args_is_help=True)
code_app = typer.Typer(help="Repo-aware scoped coding loop commands.", no_args_is_help=True)
conversation_app = typer.Typer(help="Conversation session commands.", no_args_is_help=True)
conversation_benchmark_app = typer.Typer(
    help="Conversation quality benchmark commands.",
    no_args_is_help=True,
)
policy_app = typer.Typer(help="User-owned policy profile commands.", no_args_is_help=True)
policy_benchmark_app = typer.Typer(
    help="Policy behavior benchmark commands.",
    no_args_is_help=True,
)
strategy_app = typer.Typer(help="Strategic context and memory commands.", no_args_is_help=True)
strategy_memory_app = typer.Typer(help="Strategic memory commands.", no_args_is_help=True)
tools_app = typer.Typer(help="Safe local tool runtime commands.", no_args_is_help=True)
studio_app = typer.Typer(
    help="Local Hephaestus Studio web interface.",
    invoke_without_command=True,
)
models_app = typer.Typer(
    help="Model profiles, connectivity checks, and budgeted live smoke commands.",
    invoke_without_command=True,
)
tool_patch_app = typer.Typer(help="Patch proposal and apply commands.", no_args_is_help=True)
tool_checkpoint_app = typer.Typer(help="Checkpoint and rollback commands.", no_args_is_help=True)
tool_action_app = typer.Typer(help="Tool action inspection commands.", no_args_is_help=True)
conversation_app.add_typer(conversation_benchmark_app, name="benchmark")
policy_app.add_typer(policy_benchmark_app, name="benchmark")
strategy_app.add_typer(strategy_memory_app, name="memory")
tools_app.add_typer(tool_patch_app, name="patch")
tools_app.add_typer(tool_checkpoint_app, name="checkpoint")
tools_app.add_typer(tool_action_app, name="action")
app.add_typer(memory_app, name="memory")
app.add_typer(budget_app, name="budget")
app.add_typer(db_app, name="db")
app.add_typer(run_app, name="run")
app.add_typer(benchmark_app, name="benchmark")
app.add_typer(outcome_app, name="outcome")
app.add_typer(learn_app, name="learn")
app.add_typer(profile_app, name="profile")
app.add_typer(pareto_app, name="pareto")
app.add_typer(qubo_app, name="qubo")
app.add_typer(repo_app, name="repo")
app.add_typer(release_app, name="release")
app.add_typer(validate_app, name="validate")
app.add_typer(code_app, name="code")
app.add_typer(conversation_app, name="conversation")
app.add_typer(policy_app, name="policy")
app.add_typer(strategy_app, name="strategy")
app.add_typer(tools_app, name="tools")
app.add_typer(studio_app, name="studio")
app.add_typer(models_app, name="models")


class DemoScenario(BaseModel):
    tasks: list[Task]
    model_profiles: list[ModelProfile] = Field(default_factory=list)
    context_candidates: list[ContextCandidate] = Field(default_factory=list)
    quality_threshold: float = Field(default=0.76, ge=0, le=1)
    context_token_budget: int = Field(default=2_000, gt=0)
    token_budget: TokenBudget = Field(
        default_factory=lambda: TokenBudget(
            max_input_tokens=10_000,
            max_output_tokens=4_000,
            max_cost=0.25,
            quality_threshold=0.76,
        )
    )


@app.callback(invoke_without_command=True)
def main(
    version: Annotated[
        bool,
        typer.Option("--version", help="Show the Hephaestus version and exit."),
    ] = False,
) -> None:
    """CLI callback."""

    if version:
        console.print(f"Hephaestus {__version__}")
        raise typer.Exit


@app.command()
def doctor() -> None:
    """Check local environment and optional provider configuration."""

    table = Table(title="Hephaestus Doctor")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")

    python_ok = sys.version_info >= (3, 12)
    table.add_row(
        "Python",
        "ok" if python_ok else "warn",
        f"{platform.python_version()} ({'>=3.12 required'})",
    )
    table.add_row("Package", "ok", f"hephaestus {__version__}")
    for provider_status in conversation_provider_statuses():
        table.add_row(
            f"Conversation provider: {provider_status.provider}",
            "configured" if provider_status.available else "optional",
            provider_status.detail,
        )
    table.add_row(
        "Local config",
        "ok",
        (
            f"{DEFAULT_CONFIG.input_token_budget} input token budget, "
            f"quality threshold {DEFAULT_CONFIG.required_quality:.2f}"
        ),
    )
    console.print(table)


@studio_app.callback(invoke_without_command=True)
def studio(
    context: typer.Context,
    port: Annotated[
        int,
        typer.Option("--port", min=1, max=65535, help="Local Studio port."),
    ] = DEFAULT_STUDIO_PORT,
    host: Annotated[
        str,
        typer.Option("--host", help="Bind host. Defaults to loopback only."),
    ] = DEFAULT_STUDIO_HOST,
    no_open: Annotated[
        bool,
        typer.Option("--no-open", help="Do not open a browser automatically."),
    ] = False,
) -> None:
    """Start the local Hephaestus Studio server."""

    if context.invoked_subcommand is not None:
        return
    service = StudioService()
    config = service.config(host=host, port=port)
    console.print(f"Hephaestus Studio: {studio_url(host, port)}")
    console.print(f"Database: {config.database_path}")
    console.print(f"Policy profile: {config.active_policy_profile}")
    console.print(f"Conversation provider: {config.provider_label}")
    console.print("Press Ctrl+C to stop.")
    try:
        run_studio(host=host, port=port, open_browser=not no_open)
    except RuntimeError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error
    except KeyboardInterrupt:
        console.print("\nStopped Hephaestus Studio.")


@studio_app.command("doctor")
def studio_doctor_command(
    port: Annotated[
        int,
        typer.Option("--port", min=1, max=65535, help="Local Studio port to check."),
    ] = DEFAULT_STUDIO_PORT,
    host: Annotated[
        str,
        typer.Option("--host", help="Bind host to check."),
    ] = DEFAULT_STUDIO_HOST,
) -> None:
    """Check Studio dependencies, local server readiness, and active configuration."""

    table = Table(title="Hephaestus Studio Doctor")
    table.add_column("Check")
    table.add_column("Status")
    table.add_column("Detail")
    for check in studio_doctor(host=host, port=port):
        table.add_row(check.name, check.status, check.detail)
    console.print(table)


@db_app.command("init")
def db_init() -> None:
    """Initialize the local SQLite database."""

    path = init_database()
    console.print(f"Initialized database: {path}")


@db_app.command("path")
def db_path() -> None:
    """Show the default local SQLite database path."""

    console.print(str(get_default_database_path()))


@repo_app.command("inspect")
def repo_inspect(
    path: Annotated[
        Path,
        typer.Argument(help="Repository path to inspect read-only."),
    ] = Path("."),
) -> None:
    """Inspect a local repository, generate tasks, and persist a repo profile."""

    try:
        report = inspect_repository(path)
    except (FileNotFoundError, NotADirectoryError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error
    RepoProfileRepository().save_inspection(report)
    console.print(build_repo_inspection_renderable(report))
    console.print(f"Saved repo profile: {report.profile.id}")
    console.print(f"Plan with: heph repo plan {report.profile.id}")


@repo_app.command("list")
def repo_list(
    limit: Annotated[int, typer.Option("--limit", min=1, help="Maximum profiles to show.")] = 20,
) -> None:
    """List persisted repository profiles."""

    repository = RepoProfileRepository()
    console.print(build_repo_profile_list_table(repository.list_profiles(limit=limit)))


@repo_app.command("show")
def repo_show(
    profile_id: Annotated[str, typer.Argument(help="Repo profile ID to inspect.")],
) -> None:
    """Show one persisted repository profile."""

    profile = _get_repo_profile_or_exit(profile_id)
    console.print(build_repo_show_renderable(profile))


@repo_app.command("tasks")
def repo_tasks(
    profile_id: Annotated[str, typer.Argument(help="Repo profile ID to inspect.")],
) -> None:
    """Show generated repo-aware tasks and dependencies."""

    profile = _get_repo_profile_or_exit(profile_id)
    console.print(build_repo_tasks_table(profile))


@repo_app.command("plan")
def repo_plan(
    profile_id: Annotated[str, typer.Argument(help="Repo profile ID to turn into a task graph.")],
) -> None:
    """Turn a repo profile into an optimization-ready task graph."""

    profile = _get_repo_profile_or_exit(profile_id)
    tasks = repo_tasks_to_optimizer_tasks(profile)
    comparison = compare_schedulers(tasks, DEFAULT_CONFIG.objective_weights)
    console.print(build_repo_plan_renderable(profile, comparison.best_order, comparison.explanation))


@repo_app.command("export-benchmark")
def repo_export_benchmark(
    profile_id: Annotated[str, typer.Argument(help="Repo profile ID to export.")],
    output: Annotated[
        Path,
        typer.Option("--output", help="Output benchmark JSON path."),
    ],
) -> None:
    """Export repo-aware tasks to a benchmark fixture."""

    profile = _get_repo_profile_or_exit(profile_id)
    case = repo_profile_to_benchmark_case(profile)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(case.model_dump_json(indent=2), encoding="utf-8")
    console.print(f"Exported repo benchmark: {output}")
    console.print(f"Run with: heph benchmark run {output} --pareto --qubo")


@release_app.command("plan")
def release_plan(
    path: Annotated[
        Path,
        typer.Argument(help="Repository path to inspect for release planning."),
    ] = Path("."),
    profile: Annotated[
        str | None,
        typer.Option("--profile", help="Existing repo profile ID to use instead of inspecting."),
    ] = None,
    preference: Annotated[
        str,
        typer.Option("--preference", help="Pareto preference profile when --pareto is enabled."),
    ] = "balanced",
    pareto: Annotated[
        bool,
        typer.Option("--pareto", help="Generate Pareto tradeoff frontiers."),
    ] = False,
    qubo: Annotated[
        bool,
        typer.Option("--qubo", help="Formulate and solve local QUBO problems."),
    ] = False,
    evaluate: Annotated[
        bool,
        typer.Option("--evaluate", help="Generate simulated outcomes and learning signals."),
    ] = False,
    with_validation: Annotated[
        bool,
        typer.Option("--with-validation", help="Run real validation through the safe tool runtime."),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Approve validation execution when --with-validation is used."),
    ] = False,
    latest_profile: Annotated[
        bool,
        typer.Option("--latest-profile", help="Reuse the latest profile for this path if available."),
    ] = False,
) -> None:
    """Plan a repo-aware release flow, optionally with real validation evidence."""

    request = ReleasePlanningRequest(
        path=str(path),
        profile_id=profile,
        preference=preference,
        pareto=pareto,
        qubo=qubo,
        evaluate=evaluate,
        with_validation=with_validation,
        validation_yes=yes,
        use_latest_profile=latest_profile,
    )
    try:
        demo = ReleasePlanningOrchestrator().plan(request)
    except (ReleasePlanningError, ValueError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error
    console.print(build_release_demo_renderable(demo))
    console.print(f"Saved repo profile: {demo.repo_profile.id}")
    console.print(f"Saved release plan: {demo.result.id}")
    console.print(f"Explain with: heph explain {demo.result.optimizer_run_id}")


@release_app.command("list")
def release_list(
    limit: Annotated[int, typer.Option("--limit", min=1, help="Maximum plans to show.")] = 20,
) -> None:
    """List persisted release planning results."""

    repository = ReleasePlanRepository()
    console.print(build_release_list_table(repository.list_release_plans(limit=limit)))


@release_app.command("show")
def release_show(
    release_run_id: Annotated[str, typer.Argument(help="Release planning result ID.")],
) -> None:
    """Show one persisted release planning result and linked inspection commands."""

    repository = ReleasePlanRepository()
    plan_result = repository.get_release_plan(release_run_id)
    if plan_result is None:
        console.print(f"[red]Release plan not found: {release_run_id}[/red]")
        raise typer.Exit(1)
    console.print(build_release_show_renderable(plan_result))


@validate_app.command("plan")
def validate_plan(
    path: Annotated[
        Path,
        typer.Argument(help="Repository path to inspect for validation planning."),
    ] = Path("."),
    refresh: Annotated[
        bool,
        typer.Option("--refresh", help="Inspect the repo again instead of reusing latest profile."),
    ] = False,
) -> None:
    """Build and persist an approval-aware validation execution plan."""

    try:
        plan = ValidationPlanner().build_plan(path, use_latest_profile=not refresh)
    except (FileNotFoundError, NotADirectoryError, ValueError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error
    console.print(build_validation_plan_renderable(plan))
    console.print(f"Saved validation plan: {plan.id}")


@validate_app.command("run")
def validate_run(
    path: Annotated[
        Path,
        typer.Argument(help="Repository path to validate."),
    ] = Path("."),
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Classify and record the run without executing commands."),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Approve safe validation execution after reviewing the plan."),
    ] = False,
    only: Annotated[
        str | None,
        typer.Option(
            "--only",
            help="Run one command type: lint, test, typecheck, build, format_check, security_check, or custom.",
        ),
    ] = None,
    stop_on_failure: Annotated[
        bool,
        typer.Option("--stop-on-failure", help="Skip remaining commands after the first failed or timed-out command."),
    ] = False,
) -> None:
    """Run a validation plan through the safe local tool runtime."""

    try:
        suite = ValidationExecutor(workspace_path=path).run(
            path,
            only=_parse_validation_only(only),
            dry_run=dry_run,
            yes=yes,
            stop_on_failure=stop_on_failure,
        )
    except (FileNotFoundError, NotADirectoryError, ValueError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error
    console.print(build_validation_suite_renderable(suite))
    console.print(f"Saved validation result: {suite.id}")


@validate_app.command("results")
def validate_results(
    limit: Annotated[int, typer.Option("--limit", min=1, help="Maximum validation runs to show.")] = 20,
) -> None:
    """Show recent validation runs."""

    repository = ValidationRepository()
    console.print(build_validation_results_table(repository.list_suite_results(limit=limit)))


@validate_app.command("show")
def validate_show(
    validation_result_id: Annotated[str, typer.Argument(help="Validation result ID to inspect.")],
) -> None:
    """Show command evidence and linked artifacts for one validation run."""

    repository = ValidationRepository()
    suite = repository.get_suite_result(validation_result_id)
    if suite is None:
        console.print(f"[red]Validation result not found: {validation_result_id}[/red]")
        raise typer.Exit(1)
    console.print(build_validation_show_renderable(suite))


@validate_app.command("latest")
def validate_latest(
    path: Annotated[
        Path,
        typer.Argument(help="Repository path whose latest validation run should be shown."),
    ] = Path("."),
) -> None:
    """Show the latest validation run for a repository path."""

    repository = ValidationRepository()
    suite = repository.latest_suite_result_for_path(path)
    if suite is None:
        console.print(f"[red]No validation result found for {Path(path).resolve()}[/red]")
        raise typer.Exit(1)
    console.print(build_validation_show_renderable(suite))


@code_app.command("plan")
def code_plan(
    request_text: Annotated[str, typer.Argument(help="Scoped repo change request.")],
    repo: Annotated[
        Path,
        typer.Option("--repo", help="Repository path to plan against."),
    ] = Path("."),
    scope: Annotated[
        CodingScopeType | None,
        typer.Option("--scope", help="Optional scope override."),
    ] = None,
    provider: Annotated[
        str,
        typer.Option("--provider", help="Coding provider: auto, local, real, deepseek, or Studio provider ID."),
    ] = "auto",
    max_calls: Annotated[int, typer.Option("--max-calls", min=1)] = 3,
    max_output_tokens: Annotated[int, typer.Option("--max-output-tokens", min=1)] = 4096,
    estimated_cost_cap: Annotated[float, typer.Option("--estimated-cost-cap", min=0.000001)] = 0.05,
) -> None:
    """Plan a scoped repo change without proposing or applying a patch."""

    try:
        if scope is not None:
            request, plan = CodingLoopExecutor().plan(request_text, repo_path=repo, scope=scope)
        else:
            request, plan = GreenfieldCodingExecutor().plan(
                request_text,
                repo_path=repo,
                provider=provider,
                workflow_mode=CodingWorkflowMode.PLAN,
                max_calls=max_calls,
                max_output_tokens=max_output_tokens,
                estimated_cost_cap=estimated_cost_cap,
            )
    except (CodingProviderError, FileNotFoundError, NotADirectoryError, ValueError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error
    console.print(build_coding_plan_renderable(plan))
    console.print(f"Saved coding request: {request.id}")
    console.print(f"Saved coding plan: {plan.id}")


@code_app.command("prepare")
def code_prepare(
    plan_id: Annotated[str, typer.Argument(help="Approved coding plan ID.")],
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Approve the plan and allow manifest generation."),
    ] = False,
) -> None:
    """Generate a structured operation manifest after explicit plan approval."""

    try:
        change = GreenfieldCodingExecutor().prepare(plan_id, approved=yes)
    except (CodingProviderError, PermissionError, ValueError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error
    console.print(build_coding_change_renderable(change))
    console.print(f"Saved coding change: {change.id}")


@code_app.command("propose")
def code_propose(
    request_text: Annotated[str, typer.Argument(help="Scoped repo change request.")],
    repo: Annotated[
        Path,
        typer.Option("--repo", help="Repository path to plan against."),
    ] = Path("."),
    scope: Annotated[
        CodingScopeType | None,
        typer.Option("--scope", help="Optional scope override."),
    ] = None,
) -> None:
    """Create a patch proposal without applying it."""

    executor = CodingLoopExecutor()
    try:
        request, plan, change = executor.propose(request_text, repo_path=repo, scope=scope)
    except (FileNotFoundError, NotADirectoryError, PermissionError, ValueError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error
    console.print(build_coding_plan_renderable(plan))
    console.print(build_coding_change_renderable(change))
    console.print(f"Saved coding request: {request.id}")
    console.print(f"Saved coding change: {change.id}")


@code_app.command("apply")
def code_apply(
    coding_change_id: Annotated[str, typer.Argument(help="Coding change ID to apply.")],
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Approve patch application after reviewing the proposal."),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Review and classify without changing files."),
    ] = False,
    no_validate: Annotated[
        bool,
        typer.Option("--no-validate", help="Skip validation after applying the patch."),
    ] = False,
    rollback_on_failure: Annotated[
        bool,
        typer.Option("--rollback-on-failure", help="Restore the checkpoint if validation fails."),
    ] = False,
) -> None:
    """Apply a previously proposed patch with approval gates."""

    try:
        result = CodingLoopExecutor().apply_change(
            coding_change_id,
            yes=yes,
            dry_run=dry_run,
            no_validate=no_validate,
            rollback_on_failure=rollback_on_failure,
        )
    except (FileNotFoundError, PermissionError, ValueError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error
    console.print(build_coding_result_renderable(result))
    if result.status.value in {"blocked", "requires_approval", "validation_failed"}:
        raise typer.Exit(1)


@code_app.command("run")
def code_run(
    request_text: Annotated[str, typer.Argument(help="Scoped repo change request.")],
    repo: Annotated[
        Path,
        typer.Option("--repo", help="Repository path to plan against."),
    ] = Path("."),
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Plan, propose, and review without changing files."),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Approve eligible patch application and validation."),
    ] = False,
    max_iterations: Annotated[
        int,
        typer.Option("--max-iterations", min=1, help="Maximum bounded iterations. Defaults to 1."),
    ] = 1,
    no_validate: Annotated[
        bool,
        typer.Option("--no-validate", help="Skip validation after applying the patch."),
    ] = False,
    rollback_on_failure: Annotated[
        bool,
        typer.Option("--rollback-on-failure", help="Restore the checkpoint if validation fails."),
    ] = False,
    scope: Annotated[
        CodingScopeType | None,
        typer.Option("--scope", help="Optional scope override."),
    ] = None,
) -> None:
    """Run the controlled coding loop: plan, propose, review, apply, validate."""

    try:
        result = CodingLoopExecutor().run(
            request_text,
            repo_path=repo,
            dry_run=dry_run,
            yes=yes,
            max_iterations=max_iterations,
            no_validate=no_validate,
            rollback_on_failure=rollback_on_failure,
            scope=scope,
        )
    except (FileNotFoundError, NotADirectoryError, PermissionError, ValueError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error
    console.print(build_coding_result_renderable(result))
    if result.status.value in {"blocked", "requires_approval", "validation_failed"}:
        raise typer.Exit(1)


@code_app.command("results")
def code_results(
    limit: Annotated[int, typer.Option("--limit", min=1, help="Maximum results to show.")] = 20,
) -> None:
    """Show recent coding loop results."""

    console.print(build_coding_results_table(CodingLoopRepository().list_results(limit=limit)))


@code_app.command("show")
def code_show(
    coding_request_id: Annotated[str, typer.Argument(help="Coding request, result, plan, or change ID.")],
) -> None:
    """Show a coding loop request with plan, patch, validation, outcomes, and traces."""

    detail = CodingLoopRepository().show_result(coding_request_id)
    if detail.request is None and detail.result is None and detail.plan is None and detail.change is None:
        console.print(f"[red]Coding loop record not found: {coding_request_id}[/red]")
        raise typer.Exit(1)
    console.print(build_coding_show_renderable(detail))


@app.command("ask")
def ask(
    prompt: Annotated[str, typer.Argument(help="Question or context to ask Hephaestus.")],
    mode: Annotated[
        DeliberationMode,
        typer.Option("--mode", help="Reasoning style for the response."),
    ] = DeliberationMode.BALANCED,
    repo: Annotated[
        Path | None,
        typer.Option("--repo", help="Optional repository path for read-only repo context."),
    ] = None,
    save_memory: Annotated[
        bool,
        typer.Option("--save-memory", help="Persist suggested conversation and strategic memories."),
    ] = False,
    save_strategy: Annotated[
        bool,
        typer.Option("--save-strategy", help="Persist suggested strategic memories only."),
    ] = False,
    show_context: Annotated[
        bool,
        typer.Option("--show-context", help="Show selected memory and strategic context."),
    ] = False,
    show_budget: Annotated[
        bool,
        typer.Option("--show-budget", help="Show conversation token, context, and model budget."),
    ] = False,
    provider: Annotated[
        str,
        typer.Option(
            "--provider",
            help="Conversation provider mode: auto, local, real, or a provider name.",
        ),
    ] = "auto",
    no_memory: Annotated[
        bool,
        typer.Option("--no-memory", help="Do not retrieve persistent memories."),
    ] = False,
    propose_tools: Annotated[
        bool,
        typer.Option("--propose-tools", help="Show safe tool actions the user can run manually."),
    ] = False,
    propose_code: Annotated[
        bool,
        typer.Option("--propose-code", help="Show a repo-aware coding plan and next command."),
    ] = False,
) -> None:
    """Ask a one-shot text question using memory, repo context, and deliberation."""

    _run_conversation_turn(
        prompt,
        mode=mode,
        repo=repo,
        save_memory=save_memory,
        save_strategy=save_strategy,
        use_memory=not no_memory,
        show_context=show_context,
        show_budget=show_budget,
        provider=provider,
        discussion=False,
        propose_tools=propose_tools,
        propose_code=propose_code,
    )


@app.command("discuss")
def discuss(
    prompt: Annotated[str, typer.Argument(help="Long-form plan, idea, or strategic context.")],
    mode: Annotated[
        DeliberationMode,
        typer.Option("--mode", help="Reasoning style for the response."),
    ] = DeliberationMode.BALANCED,
    repo: Annotated[
        Path | None,
        typer.Option("--repo", help="Optional repository path for read-only repo context."),
    ] = None,
    save_memory: Annotated[
        bool,
        typer.Option("--save-memory", help="Persist suggested conversation and strategic memories."),
    ] = False,
    save_strategy: Annotated[
        bool,
        typer.Option("--save-strategy", help="Persist suggested strategic memories only."),
    ] = False,
    show_context: Annotated[
        bool,
        typer.Option("--show-context", help="Show selected memory and strategic context."),
    ] = False,
    show_budget: Annotated[
        bool,
        typer.Option("--show-budget", help="Show conversation token, context, and model budget."),
    ] = False,
    provider: Annotated[
        str,
        typer.Option(
            "--provider",
            help="Conversation provider mode: auto, local, real, or a provider name.",
        ),
    ] = "auto",
    no_memory: Annotated[
        bool,
        typer.Option("--no-memory", help="Do not retrieve persistent memories."),
    ] = False,
    propose_tools: Annotated[
        bool,
        typer.Option("--propose-tools", help="Show safe tool actions the user can run manually."),
    ] = False,
    propose_code: Annotated[
        bool,
        typer.Option("--propose-code", help="Show a repo-aware coding plan and next command."),
    ] = False,
) -> None:
    """Discuss a longer plan or idea with structured deliberation."""

    _run_conversation_turn(
        prompt,
        mode=mode,
        repo=repo,
        save_memory=save_memory,
        save_strategy=save_strategy,
        use_memory=not no_memory,
        show_context=show_context,
        show_budget=show_budget,
        provider=provider,
        discussion=True,
        propose_tools=propose_tools,
        propose_code=propose_code,
    )


@app.command("chat")
def chat(
    repo: Annotated[
        Path | None,
        typer.Option("--repo", help="Optional repository path for read-only repo context."),
    ] = None,
    session_id: Annotated[
        str | None,
        typer.Option("--session", help="Existing conversation session ID."),
    ] = None,
    mode: Annotated[
        DeliberationMode,
        typer.Option("--mode", help="Initial reasoning style."),
    ] = DeliberationMode.BALANCED,
    propose_code: Annotated[
        bool,
        typer.Option("--propose-code", help="Show a coding plan after each chat turn."),
    ] = False,
) -> None:
    """Start a persistent interactive text session."""

    service = ConversationService()
    current_session_id = session_id
    current_repo = repo
    current_mode = mode
    last_response: ConversationResponse | None = None
    console.print("Hephaestus chat. Type /exit to leave, /memory for selected context.")
    while True:
        try:
            raw_text = console.input("[bold cyan]you> [/bold cyan]")
        except EOFError:
            console.print()
            break
        text = raw_text.strip()
        if not text:
            continue
        if text in {"exit", "/exit", "quit", "/quit"}:
            break
        if text.startswith("/mode"):
            parts = text.split(maxsplit=1)
            if len(parts) != 2:
                console.print(f"Current mode: {current_mode.value}")
                continue
            try:
                current_mode = DeliberationMode(parts[1].strip())
            except ValueError:
                console.print(f"[red]Unknown mode: {parts[1].strip()}[/red]")
                continue
            if current_session_id is not None:
                service.set_mode(current_session_id, current_mode)
            console.print(f"Mode set to {current_mode.value}")
            continue
        if text.startswith("/repo"):
            parts = text.split(maxsplit=1)
            if len(parts) != 2:
                console.print(f"Current repo: {current_repo or '-'}")
                continue
            current_repo = Path(parts[1].strip())
            console.print(f"Repo context set to {current_repo}")
            continue
        if text == "/memory":
            _print_chat_context(last_response)
            continue
        if text == "/summary":
            if current_session_id is None:
                console.print("No session has been created yet.")
                continue
            session = service.get_session(current_session_id)
            if session is None:
                console.print(f"[red]Session not found: {current_session_id}[/red]")
                continue
            messages = service.list_messages(current_session_id)
            updates = service.repository.list_memory_updates(current_session_id)
            console.print(build_conversation_show_renderable(session, messages, updates))
            continue
        if text == "/save-memory":
            if last_response is None:
                console.print("No suggested memories yet.")
                continue
            saved_count = 0
            saved_strategy_count = 0
            for candidate in last_response.memory_candidates:
                memory = service.memory_repository.add(candidate.to_memory_item())
                service.repository.save_memory_update(
                    ConversationMemoryUpdate(
                        session_id=last_response.session_id,
                        message_id=last_response.message_id,
                        candidate=candidate,
                        status="saved",
                        memory_id=memory.id,
                    )
                )
                saved_count += 1
            for strategic_candidate in last_response.strategic_memory_candidates:
                service.strategic_memory_repository.save_memory(strategic_candidate)
                saved_strategy_count += 1
            console.print(
                f"Saved {saved_count} memory update(s) and "
                f"{saved_strategy_count} strategic memory update(s)."
            )
            continue
        if text.startswith("/propose-code"):
            parts = text.split(maxsplit=1)
            code_request = parts[1].strip() if len(parts) == 2 else ""
            if not code_request:
                console.print("Usage: /propose-code <request>")
                continue
            try:
                _request, code_plan_result = CodingLoopExecutor(service.database_path).plan(
                    code_request,
                    repo_path=current_repo or Path("."),
                )
            except (FileNotFoundError, NotADirectoryError, ValueError) as error:
                console.print(f"[red]{error}[/red]")
                continue
            console.print(build_coding_conversation_proposal(code_plan_result))
            continue

        try:
            last_response = service.respond(
                ConversationRequest(
                    prompt=text,
                    mode=current_mode,
                    session_id=current_session_id,
                    repo_path=str(current_repo) if current_repo is not None else None,
                    provider="auto",
                )
            )
        except (FileNotFoundError, NotADirectoryError, ValueError) as error:
            console.print(f"[red]{error}[/red]")
            continue
        current_session_id = last_response.session_id
        console.print(build_conversation_response_renderable(last_response))
        if propose_code:
            try:
                _request, code_plan_result = CodingLoopExecutor(service.database_path).plan(
                    text,
                    repo_path=current_repo or Path("."),
                    conversation_id=current_session_id,
                )
            except (FileNotFoundError, NotADirectoryError, ValueError) as error:
                console.print(f"[red]{error}[/red]")
                continue
            console.print(build_coding_conversation_proposal(code_plan_result))


@app.command("conversations")
def conversations(
    limit: Annotated[int, typer.Option("--limit", min=1, help="Maximum sessions to show.")] = 20,
) -> None:
    """List persisted conversation sessions."""

    service = ConversationService()
    console.print(build_conversation_sessions_table(service.list_sessions(limit=limit)))


@conversation_app.command("show")
def conversation_show(
    session_id: Annotated[str, typer.Argument(help="Conversation session ID.")],
) -> None:
    """Show a conversation session, messages, traces, and memory updates."""

    service = ConversationService()
    session = service.get_session(session_id)
    if session is None:
        console.print(f"[red]Conversation session not found: {session_id}[/red]")
        raise typer.Exit(1)
    messages = service.list_messages(session_id)
    updates = service.repository.list_memory_updates(session_id)
    console.print(build_conversation_show_renderable(session, messages, updates))


@conversation_benchmark_app.command("list")
def conversation_benchmark_list() -> None:
    """List deterministic conversation benchmark fixtures."""

    print_conversation_benchmark_list(console, load_all_conversation_benchmarks())


@conversation_benchmark_app.command("run")
def conversation_benchmark_run(
    target: Annotated[
        str | None,
        typer.Argument(help="Optional conversation benchmark JSON path, id, or file stem."),
    ] = None,
    provider: Annotated[
        str,
        typer.Option(
            "--provider",
            help="Provider mode for benchmark conversations: local, real, auto, or provider name.",
        ),
    ] = "local",
    live: Annotated[
        bool,
        typer.Option("--live", help="Opt into real configured provider calls."),
    ] = False,
) -> None:
    """Run one or all conversation quality benchmarks."""

    selected_provider = "real" if live else provider
    try:
        results = run_conversation_benchmarks(target, provider=selected_provider)
    except (FileNotFoundError, ValueError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error
    if len(results) > 1:
        console.print(build_conversation_benchmark_summary_table(results))
    for result in results:
        console.print(build_conversation_benchmark_result_renderable(result))


@policy_app.command("profiles")
def policy_profiles() -> None:
    """List built-in and custom policy profiles."""

    repository = PolicyRepository()
    active_profile = repository.get_active_profile()
    console.print(
        build_policy_profiles_table(
            repository.list_profiles(),
            active_profile_id=active_profile.id,
        )
    )


@policy_app.command("active")
def policy_active() -> None:
    """Show the active policy profile."""

    repository = PolicyRepository()
    console.print(build_active_policy_panel(repository.get_active_profile()))


@policy_app.command("set")
def policy_set(
    profile_id: Annotated[str, typer.Argument(help="Policy profile ID to activate.")],
) -> None:
    """Set the active policy profile."""

    repository = PolicyRepository()
    profile = repository.set_active_profile(profile_id)
    if profile is None:
        console.print(f"[red]Policy profile not found: {profile_id}[/red]")
        raise typer.Exit(1)
    console.print(f"Active policy profile set to {profile.id}: {profile.name}")


@policy_app.command("show")
def policy_show(
    profile_id: Annotated[str, typer.Argument(help="Policy profile ID to inspect.")],
) -> None:
    """Show one policy profile."""

    repository = PolicyRepository()
    profile = repository.get_profile(profile_id)
    if profile is None:
        console.print(f"[red]Policy profile not found: {profile_id}[/red]")
        raise typer.Exit(1)
    console.print(build_policy_profile_renderable(profile))


@policy_app.command("evaluate")
def policy_evaluate(
    prompt: Annotated[str, typer.Argument(help="Request text to evaluate.")],
    profile: Annotated[
        str | None,
        typer.Option("--profile", help="Policy profile to use instead of the active profile."),
    ] = None,
) -> None:
    """Evaluate request text against the active or selected policy profile."""

    repository = PolicyRepository()
    selected_profile = repository.get_profile(profile) if profile is not None else repository.get_active_profile()
    if selected_profile is None:
        console.print(f"[red]Policy profile not found: {profile}[/red]")
        raise typer.Exit(1)
    evaluation = evaluate_policy_request(prompt, profile=selected_profile)
    repository.record_evaluation(evaluation)
    console.print(build_policy_evaluation_renderable(evaluation))


@policy_benchmark_app.command("list")
def policy_benchmark_list() -> None:
    """List policy benchmark fixtures."""

    cases = load_all_policy_benchmarks()
    console.print(build_policy_benchmark_fixture_table([case.id for case in cases]))


@policy_benchmark_app.command("run")
def policy_benchmark_run(
    target: Annotated[
        str | None,
        typer.Argument(help="Optional policy benchmark JSON path, id, or file stem."),
    ] = None,
) -> None:
    """Run one or all policy behavior benchmarks."""

    try:
        results = run_policy_benchmark(target)
    except (FileNotFoundError, ValueError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error
    console.print(build_policy_benchmark_list_table(results))
    if any(not result.passed for result in results):
        raise typer.Exit(1)


@tools_app.command("list")
def tools_list(
    path: Annotated[str, typer.Argument(help="Directory path inside the workspace.")] = ".",
) -> None:
    """List a local directory through the safe tool runtime."""

    runtime = ToolRuntime()
    try:
        action, result, listing = runtime.list_directory(path)
    except (FileNotFoundError, NotADirectoryError, PermissionError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error
    console.print(build_filesystem_list_table(listing))
    console.print(build_tool_result_renderable(action, result))


@tools_app.command("read")
def tools_read(
    path: Annotated[str, typer.Argument(help="File path inside the workspace.")],
) -> None:
    """Read a local file, withholding protected secret-like contents."""

    runtime = ToolRuntime()
    try:
        action, result, read_result = runtime.read_file(path)
    except (FileNotFoundError, IsADirectoryError, PermissionError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error
    console.print(build_filesystem_read_renderable(read_result))
    console.print(build_tool_result_renderable(action, result))


@tools_app.command("search")
def tools_search(
    query: Annotated[str, typer.Argument(help="Text to search for.")],
    path: Annotated[
        str,
        typer.Option("--path", help="File or directory path inside the workspace."),
    ] = ".",
) -> None:
    """Search local files by simple text match."""

    runtime = ToolRuntime()
    try:
        action, result, search_result = runtime.search_files(query, path=path)
    except (FileNotFoundError, PermissionError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error
    console.print(build_filesystem_search_table(search_result))
    console.print(build_tool_result_renderable(action, result))


@tools_app.command("run")
def tools_run(
    command: Annotated[str, typer.Argument(help="Shell command to classify and optionally run.")],
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Classify and persist the action without execution."),
    ] = False,
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Approve eligible approval-gated execution."),
    ] = False,
    require_approval: Annotated[
        bool,
        typer.Option("--require-approval", help="Force approval gate even for safe commands."),
    ] = False,
    timeout: Annotated[
        int,
        typer.Option("--timeout", min=1, help="Command timeout in seconds."),
    ] = 120,
) -> None:
    """Classify, approval-gate, and run a local shell command."""

    runtime = ToolRuntime()
    plan, action, result = runtime.run_command(
        ShellCommandRequest(
            command=command,
            cwd=".",
            timeout_seconds=timeout,
            dry_run=dry_run,
            yes=yes,
            require_approval=require_approval,
        )
    )
    console.print(build_tool_plan_renderable(plan))
    console.print(build_tool_result_renderable(action, result))
    if result.status.value in {"blocked", "approval_required", "failed", "timed_out"}:
        raise typer.Exit(1)


@tool_patch_app.command("propose")
def tools_patch_propose(
    path: Annotated[str, typer.Argument(help="File path to patch.")],
    find: Annotated[str, typer.Option("--find", help="Exact text to replace.")],
    replace: Annotated[str, typer.Option("--replace", help="Replacement text.")],
) -> None:
    """Create a deterministic patch proposal without changing files."""

    runtime = ToolRuntime()
    try:
        action, result, proposal = runtime.propose_patch(path, find=find, replace=replace)
    except (FileNotFoundError, IsADirectoryError, PermissionError, ValueError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error
    console.print(build_patch_proposal_renderable(proposal))
    console.print(build_tool_result_renderable(action, result))


@tool_patch_app.command("apply")
def tools_patch_apply(
    patch_id: Annotated[str, typer.Argument(help="Patch proposal ID to apply.")],
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Approve patch application after reviewing the diff."),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show the stored patch without applying it."),
    ] = False,
) -> None:
    """Apply a stored patch proposal after approval."""

    runtime = ToolRuntime()
    try:
        plan, action, result, _apply_result = runtime.apply_patch(
            patch_id,
            yes=yes,
            dry_run=dry_run,
        )
    except (FileNotFoundError, PermissionError, ValueError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error
    console.print(build_tool_plan_renderable(plan))
    console.print(build_tool_result_renderable(action, result))
    if result.status.value in {"blocked", "approval_required", "failed", "timed_out"}:
        raise typer.Exit(1)


@tools_app.command("actions")
def tools_actions(
    limit: Annotated[int, typer.Option("--limit", min=1, help="Maximum actions to show.")] = 20,
) -> None:
    """List recent tool runtime actions."""

    repository = ToolRuntimeRepository()
    console.print(build_tool_actions_table(repository.list_actions(limit=limit)))


@tool_action_app.command("show")
def tools_action_show(
    action_id: Annotated[str, typer.Argument(help="Tool action ID to inspect.")],
) -> None:
    """Show one tool action with approvals, results, and observations."""

    repository = ToolRuntimeRepository()
    action = repository.get_action(action_id)
    if action is None:
        console.print(f"[red]Tool action not found: {action_id}[/red]")
        raise typer.Exit(1)
    console.print(
        build_tool_action_detail(
            action,
            repository.list_approvals_for_action(action.id),
            repository.list_results_for_action(action.id),
            repository.list_observations_for_action(action.id),
        )
    )


@tool_checkpoint_app.command("list")
def tools_checkpoint_list(
    limit: Annotated[int, typer.Option("--limit", min=1, help="Maximum checkpoints to show.")] = 20,
) -> None:
    """List recent tool checkpoints."""

    repository = ToolRuntimeRepository()
    console.print(build_checkpoint_table(repository.list_checkpoints(limit=limit)))


@tool_checkpoint_app.command("show")
def tools_checkpoint_show(
    checkpoint_id: Annotated[str, typer.Argument(help="Checkpoint ID to inspect.")],
) -> None:
    """Show one checkpoint."""

    repository = ToolRuntimeRepository()
    checkpoint = repository.get_checkpoint(checkpoint_id)
    if checkpoint is None:
        console.print(f"[red]Checkpoint not found: {checkpoint_id}[/red]")
        raise typer.Exit(1)
    console.print(build_checkpoint_detail(checkpoint))


@tool_checkpoint_app.command("restore")
def tools_checkpoint_restore(
    checkpoint_id: Annotated[str, typer.Argument(help="Checkpoint ID to restore.")],
    yes: Annotated[
        bool,
        typer.Option("--yes", help="Approve restoring files from this checkpoint."),
    ] = False,
    dry_run: Annotated[
        bool,
        typer.Option("--dry-run", help="Show the restore plan without changing files."),
    ] = False,
) -> None:
    """Restore files captured by a Hephaestus checkpoint."""

    runtime = ToolRuntime()
    try:
        plan, action, result, _restored = runtime.restore_checkpoint(
            checkpoint_id,
            yes=yes,
            dry_run=dry_run,
        )
    except (FileNotFoundError, PermissionError, ValueError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error
    console.print(build_tool_plan_renderable(plan))
    console.print(build_tool_result_renderable(action, result))
    if result.status.value in {"blocked", "approval_required", "failed", "timed_out"}:
        raise typer.Exit(1)


@app.command()
def plan(
    goal: Annotated[str, typer.Argument(help="User goal to turn into a spec/task graph.")],
) -> None:
    """Create a deterministic spec and initial task graph."""

    goal_spec = build_goal_spec(goal)
    tasks = generate_initial_tasks(goal_spec)
    comparison = compare_schedulers(tasks, DEFAULT_CONFIG.objective_weights)

    console.print(Panel(goal_spec.intent, title=goal_spec.title))
    task_table = Table(title="Initial Tasks")
    task_table.add_column("Order")
    task_table.add_column("Task")
    task_table.add_column("Priority", justify="right")
    task_table.add_column("Risk", justify="right")
    task_table.add_column("Approval")
    for index, task in enumerate(comparison.best_order, start=1):
        task_table.add_row(
            str(index),
            task.id,
            str(task.priority),
            f"{task.risk:.2f}",
            "yes" if task.requires_approval else "no",
        )
    console.print(task_table)
    console.print(comparison.explanation)


@app.command()
def optimize(
    path: Annotated[
        Path,
        typer.Argument(help="Path to a demo JSON file with tasks, models, and context."),
    ],
) -> None:
    """Compare greedy and annealing plans, then route models and pack context."""

    scenario = DemoScenario.model_validate_json(path.read_text(encoding="utf-8"))
    run_repository = RunRepository()
    trace_repository = DecisionTraceRepository(run_repository.database_path)
    run = run_repository.save_run(RunRecord(goal=f"Optimize {path}", mode="optimize"))
    profile_store = ProfileStore(run_repository.database_path)
    active_profiles = profile_store.list_active_profiles()
    profile_applications: list[ProfileApplicationResult] = []
    scheduler_weights, scheduler_apps = apply_scheduler_profiles(
        DEFAULT_CONFIG.objective_weights,
        active_profiles,
        run_id=run.id,
        store=profile_store,
    )
    profile_applications.extend(scheduler_apps)
    comparison = compare_schedulers(scenario.tasks, scheduler_weights)
    context_settings, context_apps = apply_context_packer_profiles(
        active_profiles,
        run_id=run.id,
        store=profile_store,
    )
    profile_applications.extend(context_apps)
    context_candidates = apply_failure_memory_context_boost(
        scenario.context_candidates,
        context_settings,
    )
    context = pack_context(
        context_candidates,
        scenario.context_token_budget,
        preserve_critical_context=context_settings.preserve_critical_context,
        failure_memory_importance_boost=context_settings.failure_memory_importance_boost,
        compression_aggressiveness=context_settings.compression_aggressiveness,
    )
    optimization_trace = build_optimization_decision(run.id, comparison)
    task_trace = build_task_selection_decision(
        run.id,
        comparison,
        parent_id=optimization_trace.id,
    )
    trace_repository.save_traces(
        [
            optimization_trace,
            task_trace,
            build_context_selection_decision(
                run.id,
                context_candidates,
                context,
                scenario.context_token_budget,
            ),
        ]
    )
    run_repository.save_run_tasks(
        RunTaskRecord(
            run_id=run.id,
            task_id=task.id,
            title=task.title,
            description=task.description,
            selected_order=index,
            priority=task.priority,
            risk=task.risk,
            expected_value=task.expected_value,
            dependencies=task.dependencies,
            required_capabilities=sorted(task.required_capabilities),
            requires_approval=task.requires_approval,
        )
        for index, task in enumerate(comparison.best_order, start=1)
    )
    for task in comparison.best_order:
        if task.requires_approval:
            risk_level = _risk_level_from_score(task.risk)
            approval = run_repository.save_approval(
                ApprovalRecord(
                    run_id=run.id,
                    action_type="task",
                    action_description=task.description,
                    risk_level=risk_level,
                )
            )
            trace_repository.save_trace(
                build_safety_approval_decision(
                    run.id,
                    action=approval.action_description,
                    reason=f"Task {task.id} requires approval before execution.",
                    risk_level=risk_level,
                    parent_id=task_trace.id,
                )
            )
    run_repository.save_decision(
        RunDecisionRecord(
            run_id=run.id,
            decision_type="scheduler_greedy",
            selected_option=_task_order_text(comparison.greedy.order),
            objective_score=comparison.greedy.score,
            rationale=comparison.greedy.explanation,
        )
    )
    run_repository.save_decision(
        RunDecisionRecord(
            run_id=run.id,
            decision_type="scheduler_annealing",
            selected_option=_task_order_text(comparison.annealed.order),
            objective_score=comparison.annealed.score,
            rationale=comparison.annealed.explanation,
        )
    )
    run_repository.save_decision(
        RunDecisionRecord(
            run_id=run.id,
            decision_type="context_packing",
            selected_option=", ".join(item.id for item in context.selected) or "none",
            rejected_options=[f"{item.id}: {item.reason}" for item in context.excluded],
            objective_score=context.score,
            rationale=context.explanation,
        )
    )

    console.print(Panel("Naive greedy vs simulated annealing", title="Optimization"))
    schedule_table = Table()
    schedule_table.add_column("Scheduler")
    schedule_table.add_column("Score", justify="right")
    schedule_table.add_column("Dependency Violations", justify="right")
    schedule_table.add_column("Order")
    schedule_table.add_row(
        "greedy",
        f"{comparison.greedy.score:.2f}",
        str(comparison.greedy.breakdown.dependency_violations),
        " -> ".join(task.id for task in comparison.greedy.order),
    )
    schedule_table.add_row(
        "annealing",
        f"{comparison.annealed.score:.2f}",
        str(comparison.annealed.breakdown.dependency_violations),
        " -> ".join(task.id for task in comparison.annealed.order),
    )
    console.print(schedule_table)

    profiles = scenario.model_profiles or fake_model_profiles()
    route_table = Table(title="Model Routing")
    route_table.add_column("Task")
    route_table.add_column("Model")
    route_table.add_column("Quality", justify="right")
    route_table.add_column("Cost", justify="right")
    total_input = 0
    total_output = 0
    total_cost = 0.0
    selected_routes: list[tuple[Task, ModelProfile, float]] = []
    for task in comparison.best_order:
        total_input += task.estimated_input_tokens
        total_output += task.estimated_output_tokens
        route_request = ModelRouteRequest(
            required_capabilities=task.required_capabilities,
            input_tokens=task.estimated_input_tokens,
            output_tokens=task.estimated_output_tokens,
            quality_threshold=scenario.quality_threshold,
            privacy_level=task.privacy_level,
            needs_tools=bool(task.allowed_tools),
            needs_json=True,
            profiles=profiles,
        )
        route_request, route_apps = apply_model_router_profiles(
            route_request,
            active_profiles,
            run_id=run.id,
            store=profile_store,
        )
        profile_applications.extend(route_apps)
        try:
            route = route_model(route_request)
        except ModelRoutingError as error:
            route_table.add_row(task.id, "unrouted", "-", "-", style="red")
            run_repository.save_decision(
                RunDecisionRecord(
                    run_id=run.id,
                    decision_type=f"model_route:{task.id}",
                    selected_option="unrouted",
                    rejected_options=[str(error)],
                    estimated_cost=0.0,
                    rationale=str(error),
                )
            )
            trace_repository.save_trace(
                build_model_routing_error_decision(
                    run.id,
                    route_request,
                    error,
                    task_id=task.id,
                    parent_id=task_trace.id,
                )
            )
            console.print(f"[red]{error}[/red]")
            continue
        total_cost += route.estimated_cost
        selected_routes.append((task, route.profile, route.quality))
        run_repository.save_decision(
            RunDecisionRecord(
                run_id=run.id,
                decision_type=f"model_route:{task.id}",
                selected_option=route.profile.identifier,
                rejected_options=[
                    f"{rejected.identifier}: {rejected.reason}" for rejected in route.rejected
                ],
                objective_score=route.quality,
                estimated_cost=route.estimated_cost,
                rationale=route.explanation,
            )
        )
        trace_repository.save_trace(
            build_model_routing_decision(
                run.id,
                route_request,
                route,
                task_id=task.id,
                parent_id=task_trace.id,
            )
        )
        route_table.add_row(
            task.id,
            route.profile.identifier,
            f"{route.quality:.2f}",
            f"${route.estimated_cost:.6f}",
        )
    console.print(route_table)

    context_table = Table(title="Context Packing")
    context_table.add_column("Selected")
    context_table.add_column("Tokens", justify="right")
    context_table.add_column("Critical")
    for item in context.selected:
        context_table.add_row(item.id, str(item.token_cost), "yes" if item.critical else "no")
    console.print(context_table)

    approval_tasks = [task.id for task in comparison.best_order if task.requires_approval]
    budget_decision = None
    if selected_routes:
        task, profile, quality = selected_routes[0]
        token_budget, token_apps = apply_token_firewall_profiles(
            scenario.token_budget,
            active_profiles,
            run_id=run.id,
            store=profile_store,
        )
        profile_applications.extend(token_apps)
        budget_decision = evaluate_budget(
            input_tokens=task.estimated_input_tokens,
            output_tokens=task.estimated_output_tokens,
            selected_model=profile,
            selected_quality=quality,
            budget=token_budget,
        )
        run_repository.save_decision(
            RunDecisionRecord(
                run_id=run.id,
                decision_type="token_budget",
                selected_option="approved" if budget_decision.approved else "blocked",
                rejected_options=_budget_rejections(budget_decision),
                estimated_cost=budget_decision.estimated_cost,
                rationale=budget_decision.explanation,
            )
        )
        trace_repository.save_trace(
            build_budget_decision(
                run.id,
                budget_decision,
                token_budget,
            )
        )

    summary_lines = [
        comparison.explanation,
        context.explanation,
        f"Estimated tokens: {total_input} input + {total_output} output",
        f"Estimated routed cost: ${total_cost:.6f}",
        "Approval-needed tasks: " + (", ".join(approval_tasks) or "none"),
        "Active profiles: " + (", ".join(profile.id for profile in active_profiles) or "none"),
        f"Profile applications: {len(profile_applications)}",
        budget_decision.explanation if budget_decision else "No routed model for budget check.",
    ]
    run_repository.complete_run(
        run.id,
        estimated_input_tokens=total_input,
        estimated_output_tokens=total_output,
        estimated_cost=total_cost,
        objective_score=comparison.best_score,
        risk_score=max((task.risk for task in comparison.best_order), default=0.0),
        summary="\n".join(summary_lines),
    )

    console.print(
        Panel(
            "\n".join(summary_lines),
            title="Summary",
        )
    )
    console.print(f"Saved run: {run.id}")
    console.print(f"View with: heph run show {run.id}")
    console.print(f"Explain with: heph explain {run.id}")


@models_app.callback(invoke_without_command=True)
def list_models(context: typer.Context) -> None:
    """Show model profiles and conversation provider configuration."""

    if context.invoked_subcommand is not None:
        return
    statuses = {status.provider: status for status in conversation_provider_statuses()}
    profiles = conversation_model_profiles(include_unavailable=True)
    table = Table(title="Model Profiles")
    table.add_column("Provider")
    table.add_column("Model")
    table.add_column("Available")
    table.add_column("Context", justify="right")
    table.add_column("In / Out $ per 1M")
    table.add_column("Tools")
    table.add_column("JSON")
    table.add_column("Stream")
    table.add_column("Conversation roles", overflow="fold")
    for profile in profiles:
        available = "yes"
        if profile.provider == "deepseek":
            available = "yes" if statuses["deepseek"].available else "needs key"
        if profile.provider == "openai-compatible":
            available = "yes" if statuses["openai-compatible"].available else "needs env"
        table.add_row(
            profile.provider,
            profile.model,
            available,
            str(profile.context_window),
            f"{profile.input_cost_per_million:g} / {profile.output_cost_per_million:g}",
            "yes" if profile.supports_tools else "no",
            "yes" if profile.supports_json else "no",
            "yes" if profile.supports_streaming else "no",
            ", ".join(sorted(profile.intended_roles)) or "-",
        )
    console.print(table)


@models_app.command("test")
def models_test(
    provider: Annotated[str, typer.Argument(help="Provider name; currently deepseek.")],
    live: Annotated[bool, typer.Option("--live", help="Allow exactly one real request.")] = False,
    max_output_tokens: Annotated[
        int,
        typer.Option("--max-output-tokens", min=1, help="Hard response token limit."),
    ] = 8,
    estimated_cost_cap: Annotated[
        float,
        typer.Option("--estimated-cost-cap", min=0.000001, help="Estimated run cap in USD."),
    ] = 0.05,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print machine-readable redacted output."),
    ] = False,
) -> None:
    """Run a one-request connectivity smoke; defaults to a network-free dry-run."""

    _require_deepseek(provider)
    result = run_live_smoke(
        LiveSmokeConfig(
            case=SmokeCase.CONNECTION,
            live=live,
            max_calls=1,
            max_output_tokens=max_output_tokens,
            estimated_cost_cap=estimated_cost_cap,
        )
    )
    _print_live_smoke(result, json_output=json_output)


@models_app.command("smoke")
def models_smoke(
    provider: Annotated[str, typer.Argument(help="Provider name; currently deepseek.")],
    case: Annotated[
        SmokeCase,
        typer.Option("--case", help="connection, conversation, repo-read, or coding."),
    ] = SmokeCase.CONVERSATION,
    repo: Annotated[
        Path,
        typer.Option("--repo", help="Repository used only by repo-read smoke."),
    ] = Path("."),
    live: Annotated[bool, typer.Option("--live", help="Allow real provider requests.")] = False,
    max_calls: Annotated[
        int,
        typer.Option("--max-calls", min=1, help="Maximum provider requests."),
    ] = 3,
    max_output_tokens: Annotated[
        int,
        typer.Option("--max-output-tokens", min=1, help="Maximum tokens per response."),
    ] = 4096,
    estimated_cost_cap: Annotated[
        float,
        typer.Option("--estimated-cost-cap", min=0.000001, help="Estimated run cap in USD."),
    ] = 0.05,
    keep_workspace: Annotated[
        bool,
        typer.Option("--keep-workspace", help="Keep the temporary smoke workspace."),
    ] = False,
    apply_patch: Annotated[
        bool,
        typer.Option(
            "--apply",
            help="Apply a coding proposal only inside the disposable fixture and validate it.",
        ),
    ] = False,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print machine-readable redacted output."),
    ] = False,
) -> None:
    """Run an isolated smoke case; without --live this is preflight only."""

    _require_deepseek(provider)
    result = run_live_smoke(
        LiveSmokeConfig(
            case=case,
            live=live,
            repo_path=repo,
            max_calls=max_calls,
            max_output_tokens=max_output_tokens,
            estimated_cost_cap=estimated_cost_cap,
            keep_workspace=keep_workspace,
            apply_coding_patch=apply_patch,
        )
    )
    _print_live_smoke(result, json_output=json_output)


def _require_deepseek(provider: str) -> None:
    if provider.strip().lower() != "deepseek":
        console.print("[red]Only the deepseek live smoke is supported in Phase 5.6A.0.[/red]")
        raise typer.Exit(2)


def _print_live_smoke(result: LiveSmokeResult, *, json_output: bool) -> None:
    if json_output:
        console.print(json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True))
        return
    table = Table(title="DeepSeek Live Smoke" if result.live else "DeepSeek Smoke Dry Run")
    table.add_column("Field")
    table.add_column("Value", overflow="fold")
    rows = [
        ("Provider", result.provider),
        ("Model", result.model),
        ("Base URL", result.base_url),
        ("API key source", result.api_key_source),
        ("Calls", str(result.calls)),
        ("Maximum calls", str(result.details.get("maximum_provider_requests", result.calls))),
        (
            "Maximum output tokens",
            str(result.details.get("maximum_output_tokens", "-")),
        ),
        ("Input tokens", str(result.input_tokens)),
        ("Output tokens", str(result.output_tokens)),
        ("Cached input tokens", str(result.cached_input_tokens)),
        ("Estimated cost", f"${result.estimated_cost:.6f}"),
        ("Conservative preflight", f"${result.conservative_preflight_estimate:.6f}"),
        ("Elapsed", f"{result.elapsed_seconds:.3f}s"),
        ("Result", result.result),
        ("Workspace", result.workspace_status),
    ]
    if result.artifact_path:
        rows.append(("Artifact", result.artifact_path))
    for label, value in rows:
        table.add_row(label, value)
    console.print(table)


@benchmark_app.command("list")
def benchmark_list() -> None:
    """List available benchmark fixtures."""

    cases = load_all_benchmarks()
    print_benchmark_list(console, cases)


@benchmark_app.command("show")
def benchmark_show(
    benchmark_id: Annotated[str, typer.Argument(help="Benchmark id, file stem, or path.")],
) -> None:
    """Show benchmark fixture metadata without running it."""

    try:
        case = load_benchmark(benchmark_id)
    except (FileNotFoundError, ValueError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error
    print_benchmark_show(console, case)


@benchmark_app.command("run")
def benchmark_run(
    target: Annotated[
        str | None,
        typer.Argument(help="Optional benchmark id, file stem, filename, or JSON path."),
    ] = None,
    json_output: Annotated[
        bool,
        typer.Option("--json", help="Print machine-readable JSON instead of Rich tables."),
    ] = False,
    evaluate: Annotated[
        bool,
        typer.Option("--evaluate", help="Generate simulated outcomes and learning artifacts."),
    ] = False,
    profile: Annotated[
        list[str] | None,
        typer.Option("--profile", help="Profile ID to apply for this benchmark run."),
    ] = None,
    pareto: Annotated[
        bool,
        typer.Option("--pareto", help="Generate and persist Pareto tradeoff frontiers."),
    ] = False,
    pareto_preference: Annotated[
        str,
        typer.Option(
            "--pareto-preference",
            help="Pareto preference profile to use when --pareto is enabled.",
        ),
    ] = "balanced",
    qubo: Annotated[
        bool,
        typer.Option("--qubo", help="Formulate and solve relevant local QUBO problems."),
    ] = False,
) -> None:
    """Run one benchmark fixture, or all fixtures when no target is supplied."""

    try:
        cases = [load_benchmark(target)] if target is not None else load_all_benchmarks()
    except (FileNotFoundError, ValueError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error

    try:
        results = [
            run_benchmark(
                case,
                profile_ids=profile,
                pareto=pareto,
                pareto_preference=pareto_preference,
                qubo=qubo,
            )
            for case in cases
        ]
    except ValueError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error
    if evaluate:
        for result in results:
            if result.run_id is not None:
                reflect_run_outcomes(result.run_id)
    if json_output:
        typer.echo(results_to_json(results))
        return

    for result in results:
        print_benchmark_result(console, result)
        if evaluate and result.run_id is not None:
            batch = reflect_run_outcomes(result.run_id)
            summary = summarize_outcome_learning(
                batch.outcomes,
                batch.reflections,
                batch.learning_signals,
                batch.failure_memory_drafts,
                batch.policy_update_suggestions,
            )
            console.print(
                build_reflection_report_renderable(
                    f"Benchmark {result.case.id}: {result.run_id}",
                    batch.outcomes,
                    batch.reflections,
                    batch.learning_signals,
                    batch.failure_memory_drafts,
                    batch.policy_update_suggestions,
                    summary,
                )
            )


@pareto_app.command("profiles")
def pareto_profiles() -> None:
    """Show built-in Pareto preference profiles."""

    console.print(build_preference_profiles_table())


@pareto_app.command("compare")
def pareto_compare(
    benchmark_fixture: Annotated[
        str,
        typer.Argument(help="Benchmark id, file stem, filename, or JSON path."),
    ],
    preference: Annotated[
        str,
        typer.Option("--preference", help="Pareto preference profile to apply."),
    ] = "balanced",
) -> None:
    """Generate, select, explain, and persist Pareto frontiers for a benchmark fixture."""

    try:
        case = load_benchmark(benchmark_fixture)
        preference_profile = get_preference_profile(preference)
    except (FileNotFoundError, ValueError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error

    run_repository = RunRepository()
    run = run_repository.save_run(
        RunRecord(goal=f"Pareto compare {case.id}: {case.goal or case.title}", mode="pareto")
    )
    profile_store = ProfileStore(run_repository.database_path)
    active_profiles = profile_store.list_active_profiles()
    selections = compare_benchmark_case(
        case,
        preference_profile,
        run_id=run.id,
        active_profiles=active_profiles,
    )
    ParetoRepository(run_repository.database_path).save_selections(selections)
    DecisionTraceRepository(run_repository.database_path).save_traces(
        build_pareto_selection_trace(selection, run.id) for selection in selections
    )
    total_tokens = sum(selection.selected_candidate.estimated_tokens for selection in selections)
    total_cost = sum(selection.selected_candidate.estimated_cost for selection in selections)
    average_score = _average_pareto_score(selections)
    max_risk = max(
        (selection.selected_candidate.objective_vector.risk for selection in selections),
        default=0.0,
    )
    summary = "\n".join(
        [
            f"Pareto fixture: {case.id}",
            f"Preference: {preference_profile.id}",
            f"Frontiers: {len(selections)}",
            (
                "Selected candidates: "
                + (", ".join(selection.selected_candidate.label for selection in selections) or "none")
            ),
            (
                "Dominated candidates: "
                + str(sum(selection.dominated_candidate_count for selection in selections))
            ),
        ]
    )
    run_repository.complete_run(
        run.id,
        estimated_input_tokens=total_tokens,
        estimated_output_tokens=0,
        estimated_cost=total_cost,
        objective_score=average_score,
        risk_score=max_risk,
        summary=summary,
    )

    for selection in selections:
        console.print(build_selection_renderable(selection))
    console.print(f"Saved Pareto run: {run.id}")
    console.print(
        "Persisted frontiers: "
        + ", ".join(selection.frontier.id for selection in selections)
    )


@pareto_app.command("list")
def pareto_list(
    limit: Annotated[int, typer.Option("--limit", min=1, help="Maximum frontiers to show.")] = 20,
) -> None:
    """List persisted Pareto frontiers."""

    repository = ParetoRepository()
    console.print(build_frontier_list_table(repository.list_frontiers(limit=limit)))


@pareto_app.command("show")
def pareto_show(
    frontier_id: Annotated[str, typer.Argument(help="Pareto frontier ID to inspect.")],
) -> None:
    """Show a persisted Pareto frontier."""

    repository = ParetoRepository()
    selection = repository.get_selection(frontier_id)
    frontier = selection.frontier if selection is not None else repository.get_frontier(frontier_id)
    if frontier is None:
        console.print(f"[red]Pareto frontier not found: {frontier_id}[/red]")
        raise typer.Exit(1)
    console.print(build_frontier_detail_renderable(frontier, selection))


@qubo_app.command("formulate")
def qubo_formulate(
    benchmark_fixture: Annotated[
        str,
        typer.Argument(help="Benchmark id, file stem, filename, or JSON path."),
    ],
    problem_type: Annotated[
        QuboProblemType,
        typer.Option("--type", help="QUBO problem type to formulate."),
    ],
) -> None:
    """Create and persist a QUBO problem from a benchmark fixture."""

    try:
        case = load_benchmark(benchmark_fixture)
    except (FileNotFoundError, ValueError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error

    repository = QuboRepository()
    active_profiles = ProfileStore(repository.database_path).list_active_profiles()
    try:
        report = formulate_benchmark_case(
            case,
            problem_type,
            active_profiles=active_profiles,
        )
    except ValueError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error
    repository.save_problem(report.problem)
    console.print(build_formulation_report_renderable(report))


@qubo_app.command("solve")
def qubo_solve(
    problem_id: Annotated[str, typer.Argument(help="Persisted QUBO problem ID.")],
    solver_name: Annotated[
        str,
        typer.Option("--solver", help="Solver: exhaustive, greedy, or annealing."),
    ] = "exhaustive",
    seed: Annotated[int, typer.Option("--seed", help="Seed for annealing.")] = 17,
    iterations: Annotated[int, typer.Option("--iterations", min=1, help="Solver iterations.")] = 750,
) -> None:
    """Solve a persisted QUBO problem and save the solution."""

    repository = QuboRepository()
    problem = repository.get_problem(problem_id)
    if problem is None:
        console.print(f"[red]QUBO problem not found: {problem_id}[/red]")
        raise typer.Exit(1)
    try:
        solution = solve_qubo(
            problem,
            solver_name=solver_name,
            seed=seed,
            iterations=iterations,
        )
    except ValueError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error
    repository.save_solution(solution, problem)
    console.print(build_qubo_solution_renderable(solution, problem))


@qubo_app.command("show")
def qubo_show(
    problem_id: Annotated[str, typer.Argument(help="QUBO problem ID to inspect.")],
) -> None:
    """Show a persisted QUBO problem and its latest solution."""

    repository = QuboRepository()
    problem = repository.get_problem(problem_id)
    if problem is None:
        console.print(f"[red]QUBO problem not found: {problem_id}[/red]")
        raise typer.Exit(1)
    console.print(build_qubo_problem_renderable(problem, repository.get_latest_solution(problem.id)))


@qubo_app.command("list")
def qubo_list(
    limit: Annotated[int, typer.Option("--limit", min=1, help="Maximum problems to show.")] = 20,
) -> None:
    """List persisted QUBO problems."""

    repository = QuboRepository()
    console.print(build_qubo_problem_list_table(repository.list_problems(limit=limit)))


@qubo_app.command("compare")
def qubo_compare(
    benchmark_fixture: Annotated[
        str,
        typer.Argument(help="Benchmark id, file stem, filename, or JSON path."),
    ],
    solver_name: Annotated[
        str,
        typer.Option("--solver", help="Solver: exhaustive, greedy, or annealing."),
    ] = "exhaustive",
) -> None:
    """Compare baseline decisions with locally solved QUBO formulations."""

    try:
        case = load_benchmark(benchmark_fixture)
    except (FileNotFoundError, ValueError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error

    run_repository = RunRepository()
    run = run_repository.save_run(
        RunRecord(goal=f"QUBO compare {case.id}: {case.goal or case.title}", mode="qubo")
    )
    profile_store = ProfileStore(run_repository.database_path)
    active_profiles = profile_store.list_active_profiles()
    qubo_repository = QuboRepository(run_repository.database_path)

    preference_profile = get_preference_profile("balanced")
    pareto_selections = compare_benchmark_case(
        case,
        preference_profile,
        run_id=run.id,
        active_profiles=active_profiles,
    )
    pareto_repository = ParetoRepository(run_repository.database_path)
    pareto_repository.save_selections(pareto_selections)
    pareto_traces = [build_pareto_selection_trace(selection, run.id) for selection in pareto_selections]
    DecisionTraceRepository(run_repository.database_path).save_traces(pareto_traces)
    pareto_note = (
        "Pareto reference: "
        + (", ".join(selection.selected_candidate.label for selection in pareto_selections) or "none")
    )

    try:
        comparisons = compare_benchmark_with_qubo(
            case,
            repository=qubo_repository,
            run_id=run.id,
            active_profiles=active_profiles,
            source_decision_trace_ids=[trace.id for trace in pareto_traces],
            solver_name=solver_name,
            notes=[
                pareto_note,
                "Pareto exposes tradeoff frontiers; QUBO encodes binary optimization energy.",
            ],
        )
    except ValueError as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error

    qubo_traces = []
    for comparison in comparisons:
        problem = qubo_repository.get_problem(comparison.problem_id)
        solution = qubo_repository.get_latest_solution(comparison.problem_id)
        if problem is None or solution is None:
            continue
        qubo_traces.append(build_qubo_solution_trace(comparison, problem, solution, run.id))
        run_repository.save_decision(
            RunDecisionRecord(
                run_id=run.id,
                decision_type=f"qubo:{comparison.problem_type.value}",
                selected_option=comparison.qubo_selected,
                rejected_options=[f"baseline: {comparison.baseline_selected}"],
                objective_score=-comparison.objective_difference,
                rationale=(
                    f"Solver {comparison.solver_name}; feasible {comparison.feasible}; "
                    f"objective delta {comparison.objective_difference:+.3f}."
                ),
            )
        )
    DecisionTraceRepository(run_repository.database_path).save_traces(qubo_traces)
    run_repository.complete_run(
        run.id,
        estimated_input_tokens=sum(task.estimated_input_tokens for task in case.tasks),
        estimated_output_tokens=sum(task.estimated_output_tokens for task in case.tasks),
        estimated_cost=sum(comparison.cost_comparison.get("qubo", 0.0) for comparison in comparisons),
        objective_score=sum(-comparison.objective_difference for comparison in comparisons),
        risk_score=0.0 if all(comparison.feasible for comparison in comparisons) else 0.5,
        summary="\n".join(
            [
                f"QUBO fixture: {case.id}",
                f"Problems: {len(comparisons)}",
                f"Feasible solutions: {sum(1 for comparison in comparisons if comparison.feasible)}",
                pareto_note,
            ]
        ),
    )
    console.print(build_qubo_comparison_table(comparisons))
    console.print(f"Saved QUBO run: {run.id}")
    console.print(
        "Persisted QUBO problems: "
        + ", ".join(comparison.problem_id for comparison in comparisons)
    )


@qubo_app.command("convert-ising")
def qubo_convert_ising(
    problem_id: Annotated[str, typer.Argument(help="QUBO problem ID to convert.")],
) -> None:
    """Convert a persisted QUBO problem to inspectable Ising form."""

    repository = QuboRepository()
    problem = repository.get_problem(problem_id)
    if problem is None:
        console.print(f"[red]QUBO problem not found: {problem_id}[/red]")
        raise typer.Exit(1)
    console.print(build_ising_renderable(qubo_to_ising(problem)))


@memory_app.command("add")
def memory_add(
    type_: Annotated[MemoryType, typer.Option("--type", help="Memory type.")],
    content: Annotated[str, typer.Option("--content", help="Memory content.")],
    summary: Annotated[str, typer.Option("--summary", help="Short summary.")] = "",
    tag: Annotated[list[str] | None, typer.Option("--tag", help="Repeatable tag.")] = None,
    project: Annotated[str, typer.Option("--project", help="Project namespace.")] = "default",
    confidence: Annotated[
        float,
        typer.Option("--confidence", min=0.0, max=1.0, help="Memory confidence."),
    ] = 0.7,
    importance: Annotated[
        float,
        typer.Option("--importance", min=0.0, max=1.0, help="Memory importance."),
    ] = 0.5,
    source: Annotated[str, typer.Option("--source", help="Memory source.")] = "user",
) -> None:
    """Add a memory to the persistent local store."""

    item = MemoryItem(
        type=type_,
        content=content,
        summary=summary,
        tags=tag or [],
        project=project,
        confidence=confidence,
        importance=importance,
        source=source,
    )
    store = SqliteMemoryRepository()
    store.add(item)
    console.print(
        f"Added {item.type.value} memory {item.id} with tags: {', '.join(item.tags) or '-'}"
    )
    console.print(f"[dim]Stored in {store.database_path}[/dim]")


@memory_app.command("search")
def memory_search(
    query: Annotated[str, typer.Argument(help="Text query.")],
    project: Annotated[str | None, typer.Option("--project", help="Project namespace.")] = None,
    limit: Annotated[int, typer.Option("--limit", min=1, help="Maximum results.")] = 5,
) -> None:
    """Search persistent local memories."""

    store = SqliteMemoryRepository()
    results = store.retrieve_top(query, project=project, limit=limit)
    _print_memory_table("Memory Search", results)


@memory_app.command("list")
def memory_list(
    project: Annotated[str | None, typer.Option("--project", help="Project namespace.")] = None,
) -> None:
    """List persistent local memories."""

    store = SqliteMemoryRepository()
    _print_memory_table("Memory List", store.list(project=project))


@strategy_memory_app.command("add")
def strategy_memory_add(
    type_: Annotated[StrategicMemoryType, typer.Option("--type", help="Strategic memory type.")],
    content: Annotated[str, typer.Option("--content", help="Strategic memory content.")],
    summary: Annotated[str, typer.Option("--summary", help="Short summary.")] = "",
    scope: Annotated[
        StrategicMemoryScope,
        typer.Option("--scope", help="Memory scope."),
    ] = StrategicMemoryScope.PROJECT,
    tag: Annotated[list[str] | None, typer.Option("--tag", help="Repeatable tag.")] = None,
    project: Annotated[str | None, typer.Option("--project", help="Project namespace.")] = "default",
    repo_profile_id: Annotated[
        str | None,
        typer.Option("--repo-profile", help="Optional repo profile ID."),
    ] = None,
    confidence: Annotated[
        float,
        typer.Option("--confidence", min=0.0, max=1.0, help="Memory confidence."),
    ] = 0.75,
    importance: Annotated[
        float,
        typer.Option("--importance", min=0.0, max=1.0, help="Memory importance."),
    ] = 0.7,
    stability: Annotated[
        StrategicMemoryStability,
        typer.Option("--stability", help="Expected memory lifetime."),
    ] = StrategicMemoryStability.MEDIUM_TERM,
    source: Annotated[
        StrategicMemorySource,
        typer.Option("--source", help="Memory source."),
    ] = StrategicMemorySource.MANUAL,
) -> None:
    """Add a strategic memory to the persistent local store."""

    item = StrategicMemoryItem(
        type=type_,
        scope=scope,
        project=project,
        repo_profile_id=repo_profile_id,
        content=content,
        summary=summary,
        evidence=[
            StrategicMemoryEvidence(
                source="cli",
                content=content,
                kind="manual",
                confidence=confidence,
            )
        ],
        confidence=confidence,
        importance=importance,
        stability=stability,
        source=source,
        tags=tag or [],
    )
    repository = StrategicMemoryRepository()
    conflicts = repository.detect_simple_conflicts(item)
    saved = repository.save_memory(item)
    console.print(
        f"Added strategic {saved.type.value} memory {saved.id} "
        f"with tags: {', '.join(saved.tags) or '-'}"
    )
    console.print(f"[dim]Stored in {repository.database_path}[/dim]")
    if conflicts:
        console.print(build_conflict_table(conflicts))


@strategy_memory_app.command("list")
def strategy_memory_list(
    project: Annotated[str | None, typer.Option("--project", help="Project namespace.")] = None,
    type_: Annotated[
        StrategicMemoryType | None,
        typer.Option("--type", help="Filter by strategic memory type."),
    ] = None,
    scope: Annotated[
        StrategicMemoryScope | None,
        typer.Option("--scope", help="Filter by scope."),
    ] = None,
    include_archived: Annotated[
        bool,
        typer.Option("--include-archived", help="Include archived strategic memories."),
    ] = False,
) -> None:
    """List strategic memories."""

    repository = StrategicMemoryRepository()
    console.print(
        build_strategic_memory_table(
            repository.list_memories(
                project=project,
                type_=type_,
                scope=scope,
                include_archived=include_archived,
            ),
            title="Strategic Memory List",
        )
    )


@strategy_memory_app.command("search")
def strategy_memory_search(
    query: Annotated[str, typer.Argument(help="Text query.")],
    project: Annotated[str | None, typer.Option("--project", help="Project namespace.")] = None,
    limit: Annotated[int, typer.Option("--limit", min=1, help="Maximum results.")] = 8,
) -> None:
    """Search strategic memories."""

    repository = StrategicMemoryRepository()
    console.print(
        build_strategic_memory_table(
            repository.search_memories(query, project=project, limit=limit),
            title="Strategic Memory Search",
        )
    )


@strategy_memory_app.command("show")
def strategy_memory_show(
    memory_id: Annotated[str, typer.Argument(help="Strategic memory ID.")],
) -> None:
    """Show one strategic memory."""

    repository = StrategicMemoryRepository()
    memory = repository.get_memory(memory_id)
    if memory is None:
        console.print(f"[red]Strategic memory not found: {memory_id}[/red]")
        raise typer.Exit(1)
    console.print(build_strategic_memory_detail(memory))


@strategy_memory_app.command("archive")
def strategy_memory_archive(
    memory_id: Annotated[str, typer.Argument(help="Strategic memory ID.")],
) -> None:
    """Archive one strategic memory."""

    repository = StrategicMemoryRepository()
    memory = repository.archive_memory(memory_id)
    if memory is None:
        console.print(f"[red]Strategic memory not found: {memory_id}[/red]")
        raise typer.Exit(1)
    console.print(f"Archived strategic memory {memory.id}")


@strategy_app.command("context")
def strategy_context(
    project: Annotated[str | None, typer.Option("--project", help="Project namespace.")] = "default",
    include_archived: Annotated[
        bool,
        typer.Option("--include-archived", help="Include archived strategic memories."),
    ] = False,
) -> None:
    """Show the currently known long-term strategic context."""

    repository = StrategicMemoryRepository()
    memories = repository.list_memories(project=project, include_archived=include_archived)
    console.print(build_strategic_context_renderable(memories))


@app.command("runs")
def list_runs(
    limit: Annotated[int, typer.Option("--limit", min=1, help="Maximum runs to show.")] = 10,
) -> None:
    """List recent persisted runs."""

    repository = RunRepository()
    runs = repository.list_recent_runs(limit=limit)
    table = Table(title="Recent Runs")
    table.add_column("ID", no_wrap=True)
    table.add_column("Mode")
    table.add_column("Status")
    table.add_column("Started")
    table.add_column("Goal", overflow="fold")
    table.add_column("Score", justify="right")
    table.add_column("Cost", justify="right")
    for run in runs:
        table.add_row(
            run.id,
            run.mode,
            run.status,
            _format_datetime(run.started_at),
            run.goal,
            f"{run.objective_score:.2f}",
            f"${run.estimated_cost:.6f}",
        )
    console.print(table)


@app.command("explain")
def explain_run(
    run_id: Annotated[
        str,
        typer.Argument(help="Run ID to explain, or 'stats' for aggregate trace statistics."),
    ],
    summary: Annotated[
        bool,
        typer.Option("--summary", help="Show a compact decision count and rejection summary."),
    ] = False,
) -> None:
    """Explain a run's rich decision trace, or aggregate trace statistics."""

    trace_repository = DecisionTraceRepository()
    if run_id == "stats":
        traces = trace_repository.list_traces()
        console.print(build_decision_stats_renderable(aggregate_decision_stats(traces)))
        return

    run_repository = RunRepository(trace_repository.database_path)
    detail = run_repository.get_run(run_id)
    if detail is None:
        console.print(f"[red]Run not found: {run_id}[/red]")
        raise typer.Exit(1)

    traces = trace_repository.list_traces(run_id=run_id)
    outcome_repository = OutcomeRepository(trace_repository.database_path)
    profile_store = ProfileStore(trace_repository.database_path)
    profile_applications = profile_store.list_profile_applications(run_id=run_id)
    pareto_selections = ParetoRepository(trace_repository.database_path).list_selections_by_run(
        run_id
    )
    qubo_repository = QuboRepository(trace_repository.database_path)
    qubo_problems = qubo_repository.list_problems(run_id=run_id, limit=100)
    qubo_solutions = [
        qubo_repository.get_latest_solution(problem.id) for problem in qubo_problems
    ]
    if summary:
        console.print(build_decision_summary_renderable(run_id, summarize_decisions(traces)))
        console.print(build_profile_application_summary_renderable(profile_applications))
        if pareto_selections:
            console.print(build_pareto_summary_panel(pareto_selections))
        if qubo_problems:
            console.print(build_qubo_summary_panel(qubo_problems, qubo_solutions))
        outcome_summary = _outcome_learning_summary(outcome_repository, run_id)
        if outcome_summary.total_outcomes:
            console.print(build_outcome_summary_renderable(outcome_summary))
        return

    outcomes_by_trace = {
        trace.id: outcome_repository.list_outcomes_by_decision_trace(trace.id)
        for trace in traces
    }
    reflections_by_trace = {
        trace.id: outcome_repository.list_reflections(decision_trace_id=trace.id)
        for trace in traces
    }
    console.print(
        build_run_explanation_renderable(
            run_id,
            traces,
            outcomes_by_trace,
            reflections_by_trace,
            profile_applications,
        )
    )
    if pareto_selections:
        console.print(build_pareto_summary_table(pareto_selections))
        for selection in pareto_selections:
            console.print(Panel(selection.tradeoff_explanation.summary, title="Tradeoff"))
    if qubo_problems:
        console.print(build_qubo_explain_renderable(qubo_problems, qubo_solutions))


@outcome_app.command("add")
def outcome_add(
    decision_trace_id: Annotated[str, typer.Argument(help="Decision trace ID to attach to.")],
    status: Annotated[OutcomeStatus, typer.Option("--status", help="Observed outcome status.")],
    summary: Annotated[str, typer.Option("--summary", help="Human outcome summary.")],
    severity: Annotated[
        float,
        typer.Option("--severity", min=0.0, max=1.0, help="Outcome severity."),
    ] = 0.0,
    confidence: Annotated[
        float,
        typer.Option("--confidence", min=0.0, max=1.0, help="Outcome confidence."),
    ] = 0.7,
    tag: Annotated[list[str] | None, typer.Option("--tag", help="Repeatable tag.")] = None,
) -> None:
    """Manually attach an outcome to a decision trace."""

    trace_repository = DecisionTraceRepository()
    trace = trace_repository.get_trace(decision_trace_id)
    if trace is None:
        console.print(f"[red]Decision trace not found: {decision_trace_id}[/red]")
        raise typer.Exit(1)
    outcome_repository = OutcomeRepository(trace_repository.database_path)
    outcome = outcome_repository.save_outcome(
        OutcomeRecord(
            run_id=trace.run_id,
            decision_trace_id=trace.id,
            status=status,
            summary=summary,
            severity=severity,
            confidence=confidence,
            tags=[*(tag or []), "manual-outcome"],
        )
    )
    reflection = outcome_repository.save_reflection(reflect_on_outcome(trace, outcome))
    console.print(f"Added outcome {outcome.id} to trace {trace.id}")
    console.print(f"Created reflection {reflection.id}")


@outcome_app.command("list")
def outcome_list(
    run_id: Annotated[str | None, typer.Option("--run", help="Filter by run ID.")] = None,
) -> None:
    """List recorded outcomes."""

    repository = OutcomeRepository()
    console.print(build_outcome_list_renderable(repository.list_outcomes(run_id=run_id)))


@outcome_app.command("show")
def outcome_show(
    outcome_id: Annotated[str, typer.Argument(help="Outcome ID to inspect.")],
) -> None:
    """Show one outcome with linked learning artifacts."""

    repository = OutcomeRepository()
    outcome = repository.get_outcome(outcome_id)
    if outcome is None:
        console.print(f"[red]Outcome not found: {outcome_id}[/red]")
        raise typer.Exit(1)
    console.print(
        build_outcome_show_renderable(
            outcome,
            repository.list_reflections(outcome_id=outcome.id),
            repository.list_learning_signals(outcome_id=outcome.id),
            repository.list_failure_memory_drafts(outcome_id=outcome.id),
            repository.list_policy_update_suggestions(outcome_id=outcome.id),
        )
    )


@app.command("reflect")
def reflect_run(
    run_id: Annotated[str, typer.Argument(help="Run ID to reflect on.")],
) -> None:
    """Generate deterministic reflections and learning artifacts for a run."""

    outcome_repository = OutcomeRepository()
    run_repository = RunRepository(outcome_repository.database_path)
    if run_repository.get_run(run_id) is None:
        console.print(f"[red]Run not found: {run_id}[/red]")
        raise typer.Exit(1)
    batch = reflect_run_outcomes(
        run_id,
        repository=outcome_repository,
        trace_repository=DecisionTraceRepository(outcome_repository.database_path),
    )
    summary = summarize_outcome_learning(
        batch.outcomes,
        batch.reflections,
        batch.learning_signals,
        batch.failure_memory_drafts,
        batch.policy_update_suggestions,
    )
    console.print(
        build_reflection_report_renderable(
            f"Run {run_id}",
            batch.outcomes,
            batch.reflections,
            batch.learning_signals,
            batch.failure_memory_drafts,
            batch.policy_update_suggestions,
            summary,
        )
    )


@learn_app.command("signals")
def learn_signals(
    run_id: Annotated[str | None, typer.Option("--run", help="Filter by run ID.")] = None,
) -> None:
    """List draft and reviewed learning signals."""

    repository = OutcomeRepository()
    console.print(build_learning_signal_table(repository.list_learning_signals(run_id=run_id)))


@learn_app.command("failures")
def learn_failures(
    run_id: Annotated[str | None, typer.Option("--run", help="Filter by run ID.")] = None,
) -> None:
    """List failure memory drafts."""

    repository = OutcomeRepository()
    console.print(build_failure_memory_table(repository.list_failure_memory_drafts(run_id=run_id)))


@learn_app.command("policies")
def learn_policies(
    run_id: Annotated[str | None, typer.Option("--run", help="Filter by run ID.")] = None,
) -> None:
    """List policy update suggestions."""

    repository = OutcomeRepository()
    console.print(
        build_policy_update_table(repository.list_policy_update_suggestions(run_id=run_id))
    )


@learn_app.command("promote-failure")
def learn_promote_failure(
    failure_draft_id: Annotated[
        str,
        typer.Argument(help="Failure memory draft ID to promote."),
    ],
    project: Annotated[str, typer.Option("--project", help="Memory project namespace.")] = "default",
) -> None:
    """Promote a failure memory draft into persistent memory."""

    outcome_repository = OutcomeRepository()
    draft = outcome_repository.get_failure_memory_draft(failure_draft_id)
    if draft is None:
        console.print(f"[red]Failure memory draft not found: {failure_draft_id}[/red]")
        raise typer.Exit(1)
    memory = MemoryItem(
        type=MemoryType.FAILURE,
        content=draft.content,
        summary=draft.summary,
        tags=draft.tags,
        project=project,
        confidence=draft.confidence,
        importance=draft.suggested_memory_importance,
        source="outcome-learning",
    )
    SqliteMemoryRepository(outcome_repository.database_path).add(memory)
    outcome_repository.link_decision_trace(draft.decision_trace_id, failure_memory_id=memory.id)
    console.print(f"Promoted failure draft {draft.id} to memory {memory.id}")


@profile_app.command("suggest")
def profile_suggest() -> None:
    """Generate draft decision quality profiles from learning artifacts."""

    evaluation = suggest_profiles()
    console.print(build_profile_suggest_renderable(evaluation))


@profile_app.command("list")
def profile_list() -> None:
    """List all decision quality profiles."""

    store = ProfileStore()
    console.print(build_profile_summary_renderable(store.list_profiles()))


@profile_app.command("show")
def profile_show(
    profile_id: Annotated[str, typer.Argument(help="Profile ID to inspect.")],
) -> None:
    """Show one decision quality profile."""

    store = ProfileStore()
    profile = store.get_profile(profile_id)
    if profile is None:
        console.print(f"[red]Profile not found: {profile_id}[/red]")
        raise typer.Exit(1)
    console.print(build_profile_show_renderable(profile))


@profile_app.command("activate")
def profile_activate(
    profile_id: Annotated[str, typer.Argument(help="Profile ID to activate.")],
) -> None:
    """Activate a draft profile so it can influence future decisions."""

    store = ProfileStore()
    profile = store.activate_profile(profile_id)
    if profile is None:
        console.print(f"[red]Profile not found: {profile_id}[/red]")
        raise typer.Exit(1)
    console.print(f"Activated profile {profile.id}: {profile.name}")


@profile_app.command("archive")
def profile_archive(
    profile_id: Annotated[str, typer.Argument(help="Profile ID to archive.")],
) -> None:
    """Archive a profile so it no longer influences future decisions."""

    store = ProfileStore()
    profile = store.archive_profile(profile_id)
    if profile is None:
        console.print(f"[red]Profile not found: {profile_id}[/red]")
        raise typer.Exit(1)
    console.print(f"Archived profile {profile.id}: {profile.name}")


@profile_app.command("active")
def profile_active() -> None:
    """List active decision quality profiles."""

    store = ProfileStore()
    console.print(build_profile_list_renderable(store.list_active_profiles(), title="Active Profiles"))


@profile_app.command("apply-demo")
def profile_apply_demo(
    profile_id: Annotated[str, typer.Argument(help="Profile ID to apply in a safe demo.")],
) -> None:
    """Safely demonstrate how one profile would affect a synthetic decision."""

    store = ProfileStore()
    profile = store.get_profile(profile_id)
    if profile is None:
        console.print(f"[red]Profile not found: {profile_id}[/red]")
        raise typer.Exit(1)
    _print_profile_apply_demo(profile, store)


@run_app.command("show")
def run_show(
    run_id: Annotated[str, typer.Argument(help="Run ID to inspect.")],
) -> None:
    """Show a persisted run with tasks, decisions, and approvals."""

    repository = RunRepository()
    detail = repository.get_run(run_id)
    if detail is None:
        console.print(f"[red]Run not found: {run_id}[/red]")
        raise typer.Exit(1)

    run = detail.run
    console.print(
        Panel(
            "\n".join(
                [
                    f"Goal: {run.goal}",
                    f"Mode: {run.mode}",
                    f"Status: {run.status}",
                    f"Started: {_format_datetime(run.started_at)}",
                    f"Completed: {_format_datetime(run.completed_at)}",
                    f"Estimated tokens: {run.estimated_input_tokens} input + "
                    f"{run.estimated_output_tokens} output",
                    f"Estimated cost: ${run.estimated_cost:.6f}",
                    f"Objective score: {run.objective_score:.2f}",
                    f"Risk score: {run.risk_score:.2f}",
                    "",
                    run.summary or "No summary recorded.",
                ]
            ),
            title=f"Run {run.id}",
        )
    )

    task_table = Table(title="Run Tasks")
    task_table.add_column("Order", justify="right")
    task_table.add_column("Task")
    task_table.add_column("Priority", justify="right")
    task_table.add_column("Risk", justify="right")
    task_table.add_column("Approval")
    for task in detail.tasks:
        task_table.add_row(
            str(task.selected_order),
            task.task_id,
            str(task.priority),
            f"{task.risk:.2f}",
            "yes" if task.requires_approval else "no",
        )
    console.print(task_table)

    decision_table = Table(title="Run Decisions")
    decision_table.add_column("Type")
    decision_table.add_column("Selected")
    decision_table.add_column("Rejected")
    decision_table.add_column("Score", justify="right")
    decision_table.add_column("Cost", justify="right")
    for decision in detail.decisions:
        decision_table.add_row(
            decision.decision_type,
            decision.selected_option,
            ", ".join(decision.rejected_options) or "-",
            f"{decision.objective_score:.2f}" if decision.objective_score is not None else "-",
            f"${decision.estimated_cost:.6f}" if decision.estimated_cost is not None else "-",
        )
    console.print(decision_table)

    if detail.approvals:
        approval_table = Table(title="Approvals")
        approval_table.add_column("ID")
        approval_table.add_column("Action")
        approval_table.add_column("Risk")
        approval_table.add_column("Status")
        for approval in detail.approvals:
            approval_table.add_row(
                approval.id,
                approval.action_type,
                approval.risk_level.value,
                approval.status.value,
            )
        console.print(approval_table)

    trace_count = len(DecisionTraceRepository(repository.database_path).list_traces(run_id=run.id))
    if trace_count:
        console.print(f"Decision traces: {trace_count}")
        console.print(f"View decision trace: heph explain {run.id}")
        console.print("Attach outcome: heph outcome add <trace_id> --status success --summary ...")
    else:
        console.print("Decision traces: none")


def _print_profile_apply_demo(
    profile: DecisionQualityProfile,
    store: ProfileStore,
) -> None:
    if profile.decision_area == DecisionArea.MODEL_ROUTER:
        request = ModelRouteRequest(
            required_capabilities={"analysis"},
            input_tokens=1_600,
            output_tokens=900,
            quality_threshold=0.86,
            needs_json=True,
            profiles=fake_model_profiles(),
        )
        adjusted, applications = apply_model_router_profiles(request, [profile], store=store)
        try:
            route = route_model(adjusted)
            detail = (
                f"Selected {route.profile.identifier} with quality {route.quality:.2f}; "
                f"threshold {request.quality_threshold:.2f} -> {adjusted.quality_threshold:.2f}."
            )
        except ModelRoutingError as error:
            detail = str(error)
        console.print(build_profile_application_table(applications, title="Profile Applied"))
        console.print(Panel(detail, title="Model Router Demo"))
        return

    if profile.decision_area in {DecisionArea.CONTEXT_PACKER, DecisionArea.MEMORY_RETRIEVAL}:
        candidates = [
            ContextCandidate(
                id="critical-policy",
                content="Quality guard policy.",
                relevance=0.9,
                importance=0.9,
                token_cost=260,
                critical=True,
            ),
            ContextCandidate(
                id="failure-memory-context",
                content="Past similar failure.",
                relevance=0.82,
                importance=0.62,
                token_cost=260,
                metadata={"memory_type": "failure", "tags": ["failure"]},
            ),
            ContextCandidate(
                id="low-relevance-summary",
                content="Nice-to-have summary.",
                relevance=0.3,
                importance=0.35,
                token_cost=240,
            ),
        ]
        settings, applications = apply_context_packer_profiles([profile], store=store)
        adjusted_candidates = apply_failure_memory_context_boost(candidates, settings)
        result = pack_context(
            adjusted_candidates,
            540,
            preserve_critical_context=settings.preserve_critical_context,
            failure_memory_importance_boost=settings.failure_memory_importance_boost,
            compression_aggressiveness=settings.compression_aggressiveness,
        )
        console.print(build_profile_application_table(applications, title="Profile Applied"))
        console.print(
            Panel(
                "\n".join(
                    [
                        "Selected context: "
                        + (", ".join(item.id for item in result.selected) or "none"),
                        result.explanation,
                    ]
                ),
                title="Context Demo",
            )
        )
        return

    if profile.decision_area == DecisionArea.TOKEN_FIREWALL:
        budget = TokenBudget(
            max_input_tokens=5_000,
            max_output_tokens=2_000,
            max_cost=0.05,
            quality_threshold=0.86,
        )
        adjusted_budget, applications = apply_token_firewall_profiles(
            budget,
            [profile],
            store=store,
        )
        console.print(build_profile_application_table(applications, title="Profile Applied"))
        console.print(
            Panel(
                f"Quality threshold {budget.quality_threshold:.2f} -> "
                f"{adjusted_budget.quality_threshold:.2f}.",
                title="Token Firewall Demo",
            )
        )
        return

    if profile.decision_area in {DecisionArea.SCHEDULER, DecisionArea.OPTIMIZER}:
        weights, applications = apply_scheduler_profiles(
            DEFAULT_CONFIG.objective_weights,
            [profile],
            store=store,
        )
        comparison = compare_schedulers(_profile_demo_tasks(), weights)
        console.print(build_profile_application_table(applications, title="Profile Applied"))
        console.print(
            Panel(
                "\n".join(
                    [
                        f"Dependency penalty: {weights.dependency_violation_penalty:.2f}",
                        f"Risk penalty: {weights.risk_penalty:.2f}",
                        f"Selected order: {_task_order_text(comparison.best_order)}",
                    ]
                ),
                title="Scheduler Demo",
            )
        )
        return

    requires_approval, applications = apply_safety_profiles(
        "git push origin main",
        base_requires_approval=False,
        risk_level=RiskLevel.HIGH,
        profiles=[profile],
        store=store,
    )
    console.print(build_profile_application_table(applications, title="Profile Applied"))
    console.print(
        Panel(
            "git push origin main requires approval: "
            + ("yes" if requires_approval else "no"),
            title="Safety Demo",
        )
    )


def _profile_demo_tasks() -> list[Task]:
    return [
        Task(
            id="publish-release",
            title="Publish release",
            description="Publish release artifacts.",
            priority=10,
            dependencies=["validate-release"],
            risk=0.75,
            expected_value=8.5,
            uncertainty=0.2,
            required_capabilities={"git", "safety"},
            estimated_input_tokens=500,
            estimated_output_tokens=200,
            requires_approval=True,
        ),
        Task(
            id="validate-release",
            title="Validate release",
            description="Run validation before publish.",
            priority=9,
            dependencies=[],
            risk=0.2,
            expected_value=9.0,
            uncertainty=0.2,
            required_capabilities={"testing"},
            estimated_input_tokens=900,
            estimated_output_tokens=400,
        ),
    ]


def _get_repo_profile_or_exit(profile_id: str) -> RepoProfile:
    repository = RepoProfileRepository()
    profile = repository.get_profile(profile_id)
    if profile is None:
        console.print(f"[red]Repo profile not found: {profile_id}[/red]")
        raise typer.Exit(1)
    return profile


def _parse_validation_only(value: str | None) -> set[ValidationCommandType] | None:
    if value is None:
        return None
    selected: set[ValidationCommandType] = set()
    for part in value.split(","):
        normalized = part.strip()
        if not normalized:
            continue
        try:
            selected.add(ValidationCommandType(normalized))
        except ValueError as error:
            valid = ", ".join(item.value for item in ValidationCommandType)
            raise ValueError(f"Unknown validation command type {normalized!r}. Valid: {valid}") from error
    return selected or None


def _run_conversation_turn(
    prompt: str,
    *,
    mode: DeliberationMode,
    repo: Path | None,
    save_memory: bool,
    save_strategy: bool,
    use_memory: bool,
    show_context: bool,
    show_budget: bool,
    provider: str,
    discussion: bool,
    propose_tools: bool,
    propose_code: bool,
) -> None:
    service = ConversationService()
    try:
        response = service.respond(
            ConversationRequest(
                prompt=prompt,
                mode=mode,
                repo_path=str(repo) if repo is not None else None,
                save_memory=save_memory,
                save_strategy=save_strategy,
                use_memory=use_memory,
                show_context=show_context,
                show_budget=show_budget,
                provider=provider,
                discussion=discussion,
            )
        )
    except (FileNotFoundError, NotADirectoryError, ValueError) as error:
        console.print(f"[red]{error}[/red]")
        raise typer.Exit(1) from error
    if show_context:
        _print_chat_context(response)
    if show_budget:
        _print_conversation_budget(response)
    console.print(build_conversation_response_renderable(response))
    if propose_tools:
        repo_profile = None
        if repo is not None:
            repo_profile = RepoProfileRepository(service.database_path).latest_profile_for_path(repo)
        policy_profile = PolicyRepository(service.database_path).get_active_profile()
        console.print(
            build_tool_proposals_table(
                propose_tool_actions(
                    prompt,
                    policy_profile=policy_profile,
                    repo_profile=repo_profile,
                    repo_path=repo,
                )
            )
        )
    if propose_code:
        try:
            _request, plan = CodingLoopExecutor(service.database_path).plan(
                prompt,
                repo_path=repo or Path("."),
                conversation_id=response.session_id,
            )
        except (FileNotFoundError, NotADirectoryError, ValueError) as error:
            console.print(f"[red]{error}[/red]")
            raise typer.Exit(1) from error
        console.print(build_coding_conversation_proposal(plan))


def _print_chat_context(response: ConversationResponse | None) -> None:
    table = Table(title="Selected Conversation Context")
    table.add_column("Source")
    table.add_column("ID")
    table.add_column("Summary", overflow="fold")
    if response is None or not response.selected_context:
        table.add_row("-", "-", "No selected context yet.")
    else:
        for item in response.selected_context:
            table.add_row(item.source, item.id, item.summary)
    console.print(table)


def _print_conversation_budget(response: ConversationResponse) -> None:
    budget = response.budget
    table = Table(title="Conversation Budget")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Provider/model", budget.provider_model)
    table.add_row("Input tokens", str(budget.estimated_input_tokens))
    table.add_row("Output budget", str(budget.output_token_budget))
    table.add_row("Estimated output tokens", str(budget.estimated_output_tokens))
    table.add_row("Context window", str(budget.context_window))
    table.add_row("Prompt token budget", str(budget.prompt_token_budget))
    table.add_row("Selected context", str(budget.selected_context_count))
    table.add_row("Regular memories", str(budget.selected_memory_count))
    table.add_row("Strategic memories", str(budget.selected_strategic_memory_count))
    table.add_row("Context trimmed", "yes" if budget.context_trimmed else "no")
    table.add_row("Estimated cost", f"${budget.estimated_cost:.6f}")
    for note in budget.trimming_notes:
        table.add_row("Trim note", note)
    console.print(table)


def _print_memory_table(title: str, memories: list[MemoryItem]) -> None:
    table = Table(title=title)
    table.add_column("ID", no_wrap=True)
    table.add_column("Type")
    table.add_column("Project")
    table.add_column("Tags")
    table.add_column("Summary")
    for item in memories:
        table.add_row(
            item.id,
            item.type.value,
            item.project,
            ", ".join(item.tags),
            item.summary or item.content,
        )
    console.print(table)


@budget_app.command("demo")
def budget_demo() -> None:
    """Show quality-preserving token/cost optimization without a live API call."""

    profiles = DeepSeekProvider().profiles()
    route = route_model(
        ModelRouteRequest(
            required_capabilities={"planning", "reasoning"},
            input_tokens=8_000,
            output_tokens=1_500,
            quality_threshold=0.85,
            privacy_level=PrivacyLevel.INTERNAL,
            needs_tools=False,
            needs_json=True,
            profiles=list(profiles),
        )
    )
    baseline = route.profile.model_copy(
        update={
            "provider": "comparison",
            "model": "higher-cost-baseline",
            "input_cost_per_million": route.profile.input_cost_per_million * 3,
            "output_cost_per_million": route.profile.output_cost_per_million * 3,
        }
    )
    decision = evaluate_budget(
        input_tokens=8_000,
        output_tokens=1_500,
        selected_model=route.profile,
        selected_quality=route.quality,
        budget=TokenBudget(
            max_input_tokens=12_000,
            max_output_tokens=4_000,
            max_cost=0.05,
            quality_threshold=0.85,
        ),
        baseline_model=baseline,
    )
    console.print(Panel(decision.explanation, title="Budget Demo"))
    console.print(
        "Principle: cheap when possible, strong when necessary, local/private when required."
    )


def _task_order_text(tasks: list[Task]) -> str:
    return " -> ".join(task.id for task in tasks)


def _risk_level_from_score(score: float) -> RiskLevel:
    if score >= 0.75:
        return RiskLevel.CRITICAL
    if score >= 0.5:
        return RiskLevel.HIGH
    if score >= 0.25:
        return RiskLevel.MEDIUM
    return RiskLevel.LOW


def _budget_rejections(decision: BudgetDecision) -> list[str]:
    rejected: list[str] = []
    if not decision.within_token_budget:
        rejected.append("token budget exceeded")
    if not decision.within_cost_budget:
        rejected.append("cost budget exceeded")
    if not decision.meets_quality_threshold:
        rejected.append("quality threshold missed")
    return rejected


def _outcome_learning_summary(
    repository: OutcomeRepository,
    run_id: str,
) -> OutcomeLearningSummary:
    return summarize_outcome_learning(
        repository.list_outcomes_by_run(run_id),
        repository.list_reflections(run_id=run_id),
        repository.list_learning_signals(run_id=run_id),
        repository.list_failure_memory_drafts(run_id=run_id),
        repository.list_policy_update_suggestions(run_id=run_id),
    )


def _average_pareto_score(selections: list[ParetoSelectionResult]) -> float:
    scores = [
        selection.candidate_scores[selection.selected_candidate.id]
        for selection in selections
        if selection.selected_candidate.id in selection.candidate_scores
    ]
    if not scores:
        return 0.0
    return sum(scores) / len(scores)


def _format_datetime(value: datetime | None) -> str:
    if value is None:
        return "-"
    return value.isoformat(timespec="seconds")


if __name__ == "__main__":
    app()
