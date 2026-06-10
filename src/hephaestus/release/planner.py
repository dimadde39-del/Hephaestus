"""Release task planning helpers built on repo intelligence."""

from __future__ import annotations

from hephaestus.benchmarks.schemas import BenchmarkCase
from hephaestus.release.schemas import ReleaseTaskPlan
from hephaestus.repo import repo_profile_to_benchmark_case
from hephaestus.repo.schemas import RepoProfile
from hephaestus.repo.task_generator import generate_repo_tasks


def ensure_release_tasks(profile: RepoProfile) -> RepoProfile:
    """Return a profile with generated release-readiness tasks."""

    if profile.generated_tasks:
        return profile
    return profile.model_copy(update={"generated_tasks": generate_repo_tasks(profile)})


def build_release_benchmark_case(profile: RepoProfile, goal: str) -> BenchmarkCase:
    """Convert a repo profile into the benchmark-compatible release demo fixture."""

    profile_with_tasks = ensure_release_tasks(profile)
    case = repo_profile_to_benchmark_case(profile_with_tasks)
    return case.model_copy(
        update={
            "id": f"release_{case.id}",
            "title": f"{profile_with_tasks.name} Release Planning Demo",
            "goal": goal,
            "description": (
                "Repo-aware release planning demo built from read-only repository inspection. "
                "Hephaestus optimizes, explains, compares Pareto tradeoffs, and can formulate "
                "QUBO problems, and can optionally execute approved validation commands."
            ),
            "tags": list(dict.fromkeys([*case.tags, "release-planning", "phase-4b"])),
            "notes": [
                *case.notes,
                "Release planning executes validation only with --with-validation; deploy, publish, and destructive commands remain gated.",
            ],
        }
    )


def build_release_task_plan(
    profile: RepoProfile,
    *,
    optimized_task_order: list[str],
) -> ReleaseTaskPlan:
    """Build compact release task-plan metadata for CLI and persistence."""

    approval_task_ids = [task.id for task in profile.generated_tasks if task.requires_approval]
    notes = [
        "Generated tasks came from read-only repo intelligence.",
        "Optimizer order is a plan, not an execution log.",
    ]
    if approval_task_ids:
        notes.append("Approval-gated tasks remain blocked from automatic execution.")
    if not profile.validation_plan.command_texts:
        notes.append("No safe validation command was detected.")
    return ReleaseTaskPlan(
        repo_profile_id=profile.id,
        generated_task_ids=[task.id for task in profile.generated_tasks],
        optimized_task_order=optimized_task_order,
        approval_task_ids=approval_task_ids,
        validation_commands=profile.validation_plan.command_texts,
        notes=notes,
    )
