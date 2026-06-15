"""Repo-aware planning for controlled coding loops."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from hephaestus.coding_loop.analysis import record_coding_trace
from hephaestus.coding_loop.repository import CodingLoopRepository
from hephaestus.coding_loop.schemas import (
    CodingLoopStatus,
    CodingPlan,
    CodingPlanStep,
    CodingRequest,
    CodingRisk,
    CodingScope,
    CodingScopeType,
)
from hephaestus.policy import PolicyRepository
from hephaestus.repo import RepoProfile, RepoProfileRepository, inspect_repository
from hephaestus.storage import RunRecord, RunRepository
from hephaestus.strategic_memory.repository import StrategicMemoryRepository
from hephaestus.validation import ValidationPlanner

_CODE_FILE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx", ".go", ".rs", ".toml", ".yaml", ".yml"}
_IGNORED_PARTS = {".git", ".venv", "__pycache__", "node_modules", ".mypy_cache", ".pytest_cache"}


class CodingPlanner:
    """Build scoped coding-loop plans from repo context and policy state."""

    def __init__(self, database_path: Path | str | None = None) -> None:
        self.repository = CodingLoopRepository(database_path)
        self.database_path = self.repository.database_path
        self.repo_repository = RepoProfileRepository(self.database_path)
        self.policy_repository = PolicyRepository(self.database_path)
        self.run_repository = RunRepository(self.database_path)
        self.strategic_memory_repository = StrategicMemoryRepository(self.database_path)

    def create_request(
        self,
        user_request: str,
        *,
        repo_path: Path | str = ".",
        scope: CodingScopeType | None = None,
        conversation_id: str | None = None,
        provider: str = "auto",
    ) -> CodingRequest:
        """Persist a coding request shell before planning."""

        root = Path(repo_path).resolve()
        if not root.exists():
            raise FileNotFoundError(f"Repository path not found: {root}")
        if not root.is_dir():
            raise NotADirectoryError(f"Repository path is not a directory: {root}")
        active_profile = self.policy_repository.get_active_profile()
        request = CodingRequest(
            repo_path=str(root),
            conversation_id=conversation_id,
            active_policy_profile=active_profile.id,
            user_request=user_request,
            requested_scope=scope,
            provider=provider,
        )
        return self.repository.create_coding_request(request)

    def build_plan(self, request: CodingRequest, *, persist: bool = True) -> CodingPlan:
        """Create a repo-aware coding plan for a persisted request."""

        root = Path(request.repo_path).resolve()
        profile = self._resolve_profile(root)
        validation_plan = ValidationPlanner(self.database_path).build_plan(
            root,
            profile=profile,
            use_latest_profile=True,
            persist=persist,
        )
        strategic_recall = self.strategic_memory_repository.recall(
            query=request.user_request,
            project=root.name,
            repo_profile_id=profile.id,
            limit=4,
            metadata={"source": "coding_loop_plan"},
        )
        if persist:
            self.strategic_memory_repository.save_recall_event(strategic_recall)
        run = (
            self.run_repository.save_run(
                RunRecord(
                    goal=f"Coding loop plan: {request.user_request}",
                    mode="coding_plan",
                    status="running",
                )
            )
            if persist
            else None
        )
        request = request.model_copy(
            update={
                "repo_profile_id": profile.id,
                "run_id": run.id if run is not None else request.run_id,
                "updated_at": datetime.now(UTC),
            }
        )
        if persist:
            self.repository.create_coding_request(request)

        scope = self._classify_scope(request.user_request, root, request.requested_scope)
        steps = _build_steps(scope, validation_plan.command_texts)
        status = CodingLoopStatus.SCOPE_TOO_LARGE if scope.too_large else CodingLoopStatus.PLANNED
        patch_possible = _patch_possible(scope)
        approval_behavior = _approval_behavior(scope)
        summary = _plan_summary(request.user_request, scope, patch_possible)
        trace_ids: list[str] = []
        if persist and run is not None:
            scope_trace = record_coding_trace(
                self.database_path,
                run_id=run.id,
                phase="scope",
                selected_option=scope.scope_type.value if not scope.too_large else "scope_too_large",
                rationale="; ".join(scope.reasons) or scope.summary,
                request_id=request.id,
                status=status,
                risk=scope.risk,
                related_ids=[profile.id, validation_plan.id],
                objective_score=0.0 if scope.too_large else 1.0,
                safety=not scope.too_large,
                tags=["scope"],
            )
            file_trace = record_coding_trace(
                self.database_path,
                run_id=run.id,
                phase="file_selection",
                selected_option=", ".join(scope.likely_files) or "no_files_selected",
                rationale="Likely files were selected from explicit paths, repo conventions, and request terms.",
                request_id=request.id,
                status=status,
                risk=scope.risk,
                related_ids=[profile.id, *scope.likely_files],
                objective_score=1.0 if scope.likely_files else 0.45,
                safety=False,
                tags=["file_selection"],
            )
            validation_trace = record_coding_trace(
                self.database_path,
                run_id=run.id,
                phase="validation_selected",
                selected_option=", ".join(validation_plan.command_texts) or "no_validation_commands",
                rationale="Validation commands come from the Phase 5F validation planner.",
                request_id=request.id,
                status=status,
                risk=scope.risk,
                related_ids=[validation_plan.id],
                objective_score=1.0 if validation_plan.commands else 0.35,
                safety=False,
                tags=["validation"],
            )
            trace_ids = [scope_trace.id, file_trace.id, validation_trace.id]

        plan = CodingPlan(
            request_id=request.id,
            repo_path=str(root),
            repo_profile_id=profile.id,
            conversation_id=request.conversation_id,
            run_id=run.id if run is not None else request.run_id,
            active_policy_profile=request.active_policy_profile,
            user_request=request.user_request,
            scope=scope,
            summary=summary,
            steps=steps,
            likely_files=scope.likely_files,
            validation_commands=validation_plan.command_texts,
            validation_plan_id=validation_plan.id,
            approval_behavior=approval_behavior,
            patch_proposal_possible=patch_possible,
            scope_too_large=scope.too_large,
            requires_approval=True,
            status=status,
            strategic_memory_ids=strategic_recall.memory_ids,
            decision_trace_ids=trace_ids,
            metadata={
                "repo_name": profile.name,
                "strategic_memory_count": len(strategic_recall.memory_ids),
            },
        )
        if persist:
            self.repository.save_plan(plan)
            if run is not None:
                self.run_repository.complete_run(
                    run.id,
                    estimated_input_tokens=0,
                    estimated_output_tokens=0,
                    estimated_cost=0.0,
                    objective_score=0.0 if scope.too_large else scope.confidence,
                    risk_score=_risk_score(scope.risk),
                    summary=summary,
                    status="completed",
                )
        return plan

    def plan(
        self,
        user_request: str,
        *,
        repo_path: Path | str = ".",
        scope: CodingScopeType | None = None,
        conversation_id: str | None = None,
        provider: str = "auto",
        persist: bool = True,
    ) -> tuple[CodingRequest, CodingPlan]:
        """Create a request and plan in one call."""

        request = self.create_request(
            user_request,
            repo_path=repo_path,
            scope=scope,
            conversation_id=conversation_id,
            provider=provider,
        )
        return request, self.build_plan(request, persist=persist)

    def _resolve_profile(self, root: Path) -> RepoProfile:
        profile = self.repo_repository.latest_profile_for_path(root)
        if profile is not None:
            return profile
        report = inspect_repository(root)
        self.repo_repository.save_inspection(report)
        return report.profile

    def _classify_scope(
        self,
        user_request: str,
        root: Path,
        override: CodingScopeType | None,
    ) -> CodingScope:
        lowered = user_request.lower()
        scope_type = override or _infer_scope_type(lowered)
        likely_files = _likely_files(root, lowered, scope_type)
        reasons = _scope_reasons(lowered, scope_type, likely_files)
        risk = _risk_for_scope(scope_type, lowered, likely_files)
        too_large = _scope_too_large(lowered, scope_type, likely_files)
        if too_large:
            risk = CodingRisk.HIGH
            reasons.append("request is too broad for Phase 5G automatic patching")
        summary = f"{scope_type.value} change touching {', '.join(likely_files) or 'no clear file'}."
        return CodingScope(
            scope_type=scope_type,
            risk=risk,
            summary=summary,
            likely_files=likely_files,
            too_large=too_large,
            reasons=reasons,
            confidence=0.82 if likely_files and not too_large else 0.52,
        )


def _infer_scope_type(lowered: str) -> CodingScopeType:
    if any(term in lowered for term in ("readme", "docs", "documentation", "wording", "intro", "section")):
        return CodingScopeType.DOCS
    if any(term in lowered for term in ("test", "fixture", "pytest", "spec")):
        return CodingScopeType.TESTS
    if any(term in lowered for term in ("config", "help text", "cli help", "pyproject", "setting")):
        return CodingScopeType.CONFIG
    if any(term in lowered for term in ("bug", "fix", "broken", "error", "failure")):
        return CodingScopeType.BUGFIX
    if any(term in lowered for term in ("feature", "add command", "support")):
        return CodingScopeType.SMALL_FEATURE
    if "refactor" in lowered:
        return CodingScopeType.REFACTOR
    return CodingScopeType.UNKNOWN


def _likely_files(root: Path, lowered: str, scope_type: CodingScopeType) -> list[str]:
    explicit = _explicit_paths(root, lowered)
    if explicit:
        return explicit[:4]
    candidates: list[str] = []
    if scope_type == CodingScopeType.DOCS:
        candidates.extend(_docs_candidates(root, lowered))
    elif scope_type == CodingScopeType.TESTS:
        candidates.extend(_test_candidates(root, lowered))
    elif scope_type == CodingScopeType.CONFIG:
        candidates.extend(_config_candidates(root, lowered))
    elif scope_type in {CodingScopeType.BUGFIX, CodingScopeType.SMALL_FEATURE, CodingScopeType.REFACTOR}:
        candidates.extend(_code_candidates(root, lowered))
    if not candidates and (root / "README.md").exists():
        candidates.append("README.md")
    return list(dict.fromkeys(candidates))[:4]


def _explicit_paths(root: Path, lowered: str) -> list[str]:
    paths: list[str] = []
    for match in re.findall(r"[\w./\\-]+\.[a-z0-9]+", lowered):
        normalized = match.replace("\\", "/").strip("./")
        if not normalized:
            continue
        target = (root / normalized).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            continue
        if target.exists() and target.is_file():
            paths.append(str(target.relative_to(root)).replace("\\", "/"))
    return list(dict.fromkeys(paths))


def _docs_candidates(root: Path, lowered: str) -> list[str]:
    candidates: list[str] = []
    if "readme" in lowered and (root / "README.md").exists():
        candidates.append("README.md")
    docs_dir = root / "docs"
    if docs_dir.exists():
        for path in sorted(docs_dir.glob("*.md")):
            if _path_matches_terms(path, lowered):
                candidates.append(str(path.relative_to(root)).replace("\\", "/"))
        if not candidates:
            first_doc = next(iter(sorted(docs_dir.glob("*.md"))), None)
            if first_doc is not None:
                candidates.append(str(first_doc.relative_to(root)).replace("\\", "/"))
    if (root / "README.md").exists() and "README.md" not in candidates:
        candidates.append("README.md")
    return candidates


def _test_candidates(root: Path, lowered: str) -> list[str]:
    tests_dir = root / "tests"
    if not tests_dir.exists():
        return []
    matches = [
        str(path.relative_to(root)).replace("\\", "/")
        for path in sorted(tests_dir.rglob("test_*.py"))
        if _path_allowed(path) and _path_matches_terms(path, lowered)
    ]
    if matches:
        return matches
    first = next((path for path in sorted(tests_dir.rglob("test_*.py")) if _path_allowed(path)), None)
    return [str(first.relative_to(root)).replace("\\", "/")] if first is not None else []


def _config_candidates(root: Path, lowered: str) -> list[str]:
    names = ["pyproject.toml", "package.json", "ruff.toml", "mypy.ini", "tox.ini"]
    candidates = [name for name in names if (root / name).exists() and name.lower() in lowered]
    if candidates:
        return candidates
    return [name for name in names if (root / name).exists()][:1]


def _code_candidates(root: Path, lowered: str) -> list[str]:
    matches: list[str] = []
    for path in sorted((root / "src").rglob("*")) if (root / "src").exists() else []:
        if not path.is_file() or path.suffix not in _CODE_FILE_SUFFIXES or not _path_allowed(path):
            continue
        if _path_matches_terms(path, lowered):
            matches.append(str(path.relative_to(root)).replace("\\", "/"))
    return matches[:4]


def _path_matches_terms(path: Path, lowered: str) -> bool:
    path_text = str(path).replace("\\", "/").lower()
    terms = [term for term in re.findall(r"[a-z0-9_]+", lowered) if len(term) >= 4]
    return any(term in path_text for term in terms)


def _path_allowed(path: Path) -> bool:
    return not any(part in _IGNORED_PARTS for part in path.parts)


def _scope_reasons(
    lowered: str,
    scope_type: CodingScopeType,
    likely_files: list[str],
) -> list[str]:
    reasons = [f"request classified as {scope_type.value}"]
    if likely_files:
        reasons.append("likely files were inferred from request terms and repo conventions")
    else:
        reasons.append("no clear target file was found")
    if "approval" in lowered or "--yes" in lowered:
        reasons.append("request references approval/trust behavior")
    return reasons


def _risk_for_scope(
    scope_type: CodingScopeType,
    lowered: str,
    likely_files: list[str],
) -> CodingRisk:
    if scope_type in {CodingScopeType.DOCS, CodingScopeType.TESTS, CodingScopeType.CONFIG}:
        risk = CodingRisk.LOW
    elif scope_type in {CodingScopeType.BUGFIX, CodingScopeType.SMALL_FEATURE}:
        risk = CodingRisk.MEDIUM
    else:
        risk = CodingRisk.HIGH if scope_type == CodingScopeType.REFACTOR else CodingRisk.MEDIUM
    if any(term in lowered for term in ("delete", "remove files", "migrate", "dependency", "install")):
        return CodingRisk.HIGH
    if len(likely_files) > 2:
        return CodingRisk.MEDIUM if risk == CodingRisk.LOW else CodingRisk.HIGH
    return risk


def _scope_too_large(
    lowered: str,
    scope_type: CodingScopeType,
    likely_files: list[str],
) -> bool:
    broad_terms = (
        "rewrite",
        "entire",
        "whole repo",
        "whole app",
        "architecture",
        "large refactor",
        "migrate",
        "redesign",
        "all files",
        "everywhere",
    )
    if any(term in lowered for term in broad_terms):
        return True
    if scope_type == CodingScopeType.REFACTOR:
        return True
    return len(likely_files) > 4


def _patch_possible(scope: CodingScope) -> bool:
    if scope.too_large or not scope.likely_files:
        return False
    return scope.scope_type in {
        CodingScopeType.DOCS,
        CodingScopeType.TESTS,
        CodingScopeType.CONFIG,
        CodingScopeType.BUGFIX,
    }


def _approval_behavior(scope: CodingScope) -> str:
    if scope.too_large:
        return "Plan only. Automatic patching is blocked until the user narrows the request."
    if scope.risk == CodingRisk.LOW:
        return (
            "Low-risk local patching may proceed with --yes: checkpoint, apply, validate, "
            "and optionally rollback on validation failure."
        )
    return "Patch application requires explicit --yes after reviewing the proposed diff."


def _build_steps(scope: CodingScope, validation_commands: list[str]) -> list[CodingPlanStep]:
    return [
        CodingPlanStep(
            order=1,
            title="Inspect repo context",
            summary="Use the latest repo profile or read-only inspection.",
            expected_files=[],
            requires_approval=False,
        ),
        CodingPlanStep(
            order=2,
            title="Propose scoped patch",
            summary="Create a reviewable deterministic patch when the scope is small enough.",
            expected_files=scope.likely_files,
            requires_approval=False,
            status=(
                CodingLoopStatus.SCOPE_TOO_LARGE
                if scope.too_large
                else CodingLoopStatus.PATCH_PROPOSED
            ),
        ),
        CodingPlanStep(
            order=3,
            title="Apply with checkpoint",
            summary="Apply only after --yes and create a checkpoint for touched files.",
            expected_files=scope.likely_files,
            requires_approval=True,
        ),
        CodingPlanStep(
            order=4,
            title="Run validation",
            summary=", ".join(validation_commands) or "No validation commands detected.",
            expected_files=[],
            requires_approval=True,
        ),
    ]


def _plan_summary(user_request: str, scope: CodingScope, patch_possible: bool) -> str:
    if scope.too_large:
        return f"Plan-only: {user_request}. Narrow the scope before patching."
    proposal = "patch proposal is possible" if patch_possible else "patch proposal needs clearer target"
    return f"Planned {scope.risk.value}-risk {scope.scope_type.value} change; {proposal}."


def _risk_score(risk: CodingRisk) -> float:
    return {CodingRisk.LOW: 0.15, CodingRisk.MEDIUM: 0.45, CodingRisk.HIGH: 0.8}[risk]
