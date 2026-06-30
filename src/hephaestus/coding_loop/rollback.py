"""Scoped rollback cleanup and failed-workspace snapshots for coding manifests."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from hephaestus.coding_loop.schemas import (
    CreateFile,
    DeleteFile,
    MoveFile,
    OperationManifest,
    RepairManifest,
)
from hephaestus.validation.schemas import ValidationSuiteResult


@dataclass(frozen=True)
class ScopedInventory:
    """Before-apply filesystem inventory for manifest-scoped cleanup."""

    workspace_path: str
    scopes: list[str]
    existing_files: dict[str, str]
    existing_dirs: set[str]
    cleanup_roots: set[str] = field(default_factory=set)
    manifest_created_paths: set[str] = field(default_factory=set)


@dataclass(frozen=True)
class RollbackCleanupResult:
    """Post-rollback residue cleanup evidence."""

    removed_paths: list[str]
    residue_paths: list[str]
    clean: bool


@dataclass(frozen=True)
class FailedWorkspaceSnapshot:
    """Safe retained failed workspace snapshot evidence."""

    snapshot_path: str
    diff_path: str
    hashes_path: str
    validation_path: str


def build_scoped_inventory(root: Path | str, manifest: OperationManifest | RepairManifest) -> ScopedInventory:
    """Capture pre-apply files and dirs under manifest-relevant scopes."""

    workspace = Path(root).resolve()
    scopes = _scopes_for_manifest(workspace, manifest)
    existing_files: dict[str, str] = {}
    existing_dirs: set[str] = set()
    cleanup_roots: set[str] = set()
    for scope in scopes:
        target = workspace / scope if scope != "." else workspace
        if not target.exists():
            cleanup_roots.add(scope)
            continue
        if target.is_file():
            existing_files[scope] = _sha256_file(target)
            continue
        existing_dirs.add(scope)
        for path in sorted(target.rglob("*")):
            relative = _relative(path, workspace)
            if path.is_dir():
                existing_dirs.add(relative)
            elif path.is_file():
                existing_files[relative] = _sha256_file(path)
    return ScopedInventory(
        workspace_path=str(workspace),
        scopes=scopes,
        existing_files=existing_files,
        existing_dirs=existing_dirs,
        cleanup_roots=cleanup_roots,
        manifest_created_paths=_manifest_created_paths(manifest),
    )


def cleanup_after_rollback(
    root: Path | str,
    inventories: list[ScopedInventory],
) -> RollbackCleanupResult:
    """Remove new scoped residues after checkpoint rollback without broad git clean."""

    workspace = Path(root).resolve()
    removed: list[str] = []
    residue: list[str] = []
    for inventory in inventories:
        for scope in inventory.scopes:
            target = workspace / scope if scope != "." else workspace
            if target.is_file():
                relative = _relative(target, workspace)
                if _should_remove(relative, scope, inventory):
                    target.unlink()
                    removed.append(relative)
                continue
            if not target.exists() or not target.is_dir():
                continue
            for path in sorted(target.rglob("*"), reverse=True):
                relative = _relative(path, workspace)
                if path.is_file() and _should_remove(relative, scope, inventory):
                    path.unlink()
                    removed.append(relative)
            for path in sorted(target.rglob("*"), key=lambda item: len(item.parts), reverse=True):
                if not path.is_dir():
                    continue
                relative = _relative(path, workspace)
                if relative not in inventory.existing_dirs and _is_empty_dir(path):
                    path.rmdir()
                    removed.append(relative)
            if scope in inventory.cleanup_roots and target.exists() and target.is_dir() and _is_empty_dir(target):
                target.rmdir()
                removed.append(scope)

        residue.extend(_new_residue(workspace, inventory))
    return RollbackCleanupResult(
        removed_paths=sorted(dict.fromkeys(removed)),
        residue_paths=sorted(dict.fromkeys(residue)),
        clean=not residue,
    )


def create_failed_workspace_snapshot(
    root: Path | str,
    artifact_root: Path | str,
    *,
    suite: ValidationSuiteResult,
) -> FailedWorkspaceSnapshot:
    """Copy a sanitized failed workspace outside the target before rollback."""

    workspace = Path(root).resolve()
    destination_root = Path(artifact_root).resolve()
    destination_root.mkdir(parents=True, exist_ok=True)
    snapshot = destination_root / "failed-workspace"
    if snapshot.exists():
        shutil.rmtree(snapshot)
    shutil.copytree(workspace, snapshot, ignore=_snapshot_ignore)
    diff_path = destination_root / "pre-rollback-diff.patch"
    diff_path.write_text(_git_diff(workspace), encoding="utf-8")
    hashes_path = destination_root / "file-hashes.json"
    hashes_path.write_text(
        json.dumps(_file_hashes(workspace), indent=2, sort_keys=True),
        encoding="utf-8",
    )
    validation_path = destination_root / "validation-evidence.json"
    validation_path.write_text(
        suite.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return FailedWorkspaceSnapshot(
        snapshot_path=str(snapshot),
        diff_path=str(diff_path),
        hashes_path=str(hashes_path),
        validation_path=str(validation_path),
    )


def _scopes_for_manifest(root: Path, manifest: OperationManifest | RepairManifest) -> list[str]:
    scopes: list[str] = []
    for raw_path in _manifest_paths(manifest):
        pure = _safe_relative(raw_path)
        target = root.joinpath(*pure.parts)
        parent = pure.parent
        if parent == PurePosixPath("."):
            scopes.append(str(pure))
            continue
        if not (root / pure.parts[0]).exists():
            scopes.append(pure.parts[0])
            continue
        scopes.append(str(parent).replace("\\", "/"))
        if not target.exists() and len(pure.parts) > 1:
            scopes.append(str(pure))
    return _dedupe(scopes)


def _manifest_paths(manifest: OperationManifest | RepairManifest) -> list[str]:
    paths: list[str] = []
    for operation in manifest.operations:
        if isinstance(operation, MoveFile):
            paths.extend([operation.source_path, operation.destination_path])
        else:
            paths.append(operation.path)
    return paths


def _manifest_created_paths(manifest: OperationManifest | RepairManifest) -> set[str]:
    paths: set[str] = set()
    for operation in manifest.operations:
        if isinstance(operation, CreateFile):
            paths.add(str(_safe_relative(operation.path)).replace("\\", "/"))
        elif isinstance(operation, MoveFile):
            paths.add(str(_safe_relative(operation.destination_path)).replace("\\", "/"))
        elif isinstance(operation, DeleteFile):
            continue
    return paths


def _should_remove(relative: str, scope: str, inventory: ScopedInventory) -> bool:
    if relative in inventory.existing_files:
        return False
    if relative in inventory.manifest_created_paths:
        return True
    if _runtime_residue(relative):
        return True
    return scope in inventory.cleanup_roots


def _new_residue(workspace: Path, inventory: ScopedInventory) -> list[str]:
    residue: list[str] = []
    for scope in inventory.scopes:
        target = workspace / scope if scope != "." else workspace
        paths = [target] if target.is_file() else sorted(target.rglob("*")) if target.exists() else []
        for path in paths:
            if not path.is_file():
                continue
            relative = _relative(path, workspace)
            if relative not in inventory.existing_files:
                residue.append(relative)
    return residue


def _runtime_residue(relative: str) -> bool:
    pure = PurePosixPath(relative.replace("\\", "/"))
    return "__pycache__" in pure.parts or pure.suffix == ".pyc" or pure.name.endswith(".tmp")


def _snapshot_ignore(directory: str, names: list[str]) -> set[str]:
    blocked = {
        ".git",
        ".hephaestus",
        ".env",
        ".env.local",
        ".env.production",
        "node_modules",
        ".venv",
        "__pycache__",
        ".pytest_cache",
        ".mypy_cache",
    }
    ignored = {name for name in names if name in blocked}
    ignored.update(name for name in names if name.endswith((".db", ".sqlite", ".sqlite3", ".pyc")))
    return ignored


def _file_hashes(root: Path) -> dict[str, str]:
    hashes: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or _is_snapshot_blocked(path, root):
            continue
        hashes[_relative(path, root)] = _sha256_file(path)
    return hashes


def _is_snapshot_blocked(path: Path, root: Path) -> bool:
    parts = set(path.relative_to(root).parts)
    return bool(parts & {".git", ".hephaestus", ".venv", "node_modules", "__pycache__"}) or path.name.startswith(".env")


def _git_diff(root: Path) -> str:
    try:
        completed = subprocess.run(
            ["git", "diff", "--no-ext-diff", "--", "."],
            cwd=str(root),
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return completed.stdout


def _safe_relative(raw_path: str) -> PurePosixPath:
    normalized = raw_path.replace("\\", "/")
    pure = PurePosixPath(normalized)
    if pure.is_absolute() or ".." in pure.parts or not pure.parts or ":" in pure.parts[0]:
        raise PermissionError(f"Unsafe manifest path: {raw_path}")
    if pure.parts[0] in {".git", ".hephaestus"}:
        raise PermissionError(f"Protected repository path: {raw_path}")
    return pure


def _relative(path: Path, root: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _is_empty_dir(path: Path) -> bool:
    return not any(path.iterdir())


def _dedupe(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def snapshot_artifact_root(base: Path | str | None, result_id: str) -> Path:
    """Resolve the default opt-in artifact root for failed workspace snapshots."""

    if base is not None:
        return Path(base).resolve()
    return Path.cwd().resolve() / ".hephaestus" / "failed-workspaces" / result_id


def cleanup_metadata(cleanup: RollbackCleanupResult) -> dict[str, object]:
    """Return JSON-safe cleanup metadata."""

    return {
        "removed_paths": cleanup.removed_paths,
        "residue_paths": cleanup.residue_paths,
        "clean": cleanup.clean,
        "checked_at": datetime.now(UTC).isoformat(),
    }
