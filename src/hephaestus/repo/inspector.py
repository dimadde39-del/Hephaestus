"""Repository inspection orchestration."""

from __future__ import annotations

from pathlib import Path

from hephaestus.repo.analysis import (
    build_project_stack,
    build_validation_plan,
    inspection_summary,
    profile_confidence,
    repo_stack_summary,
    risk_summary,
    validation_summary,
)
from hephaestus.repo.detectors import detect_repository
from hephaestus.repo.schemas import RepoInspectionReport, RepoProfile
from hephaestus.repo.task_generator import generate_repo_tasks


def inspect_repository(path: Path | str) -> RepoInspectionReport:
    """Inspect a local repository without executing repository commands."""

    root = Path(path).resolve()
    if not root.exists():
        raise FileNotFoundError(f"Repository path not found: {root}")
    if not root.is_dir():
        raise NotADirectoryError(f"Repository path is not a directory: {root}")

    detection = detect_repository(root)
    stack = build_project_stack(detection)
    validation_plan = build_validation_plan(detection)
    profile = RepoProfile(
        path=str(root),
        name=root.name,
        detected_languages=detection.languages,
        detected_frameworks=detection.frameworks,
        package_managers=detection.package_managers,
        scripts=detection.scripts,
        test_commands=detection.test_commands,
        build_commands=detection.build_commands,
        lint_commands=detection.lint_commands,
        ci_providers=detection.ci_providers,
        docker_detected=detection.docker_detected,
        env_files_detected=detection.env_files_detected,
        risk_signals=detection.risk_signals,
        validation_plan=validation_plan,
        confidence=profile_confidence(detection),
        file_signals=detection.file_signals,
        stack=stack,
    )
    profile = profile.model_copy(update={"generated_tasks": generate_repo_tasks(profile)})
    limitations = [
        "Inspection is read-only and based on manifests, config filenames, and package metadata.",
        "Validation commands are suggested but not executed in Phase 4A.",
        "CI workflow contents are not fully parsed; provider presence is detected by file path.",
    ]
    if profile.env_files_detected:
        limitations.append("Environment file contents are not inspected automatically.")
    return RepoInspectionReport(
        profile=profile,
        summary=inspection_summary(profile),
        detected_stack_summary=repo_stack_summary(profile),
        validation_summary=validation_summary(profile),
        risk_summary=risk_summary(profile),
        limitations=limitations,
        inspected_at=profile.inspected_at,
    )
