"""Transactional, repository-confined application of structured coding manifests."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from uuid import uuid4

from hephaestus.coding_loop.rollback import ScopedInventory, build_scoped_inventory
from hephaestus.coding_loop.schemas import (
    CreateFile,
    DeleteFile,
    ModifyFile,
    MoveFile,
    OperationManifest,
)
from hephaestus.tool_runtime.checkpoint import create_checkpoint, restore_checkpoint
from hephaestus.tool_runtime.filesystem import is_protected_path, sha256_file
from hephaestus.tool_runtime.schemas import CheckpointRecord

MAX_FILE_BYTES = 128 * 1024
MAX_TOTAL_BYTES = 256 * 1024
_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class PreparedOperation:
    operation: CreateFile | ModifyFile | DeleteFile | MoveFile
    source: Path | None
    destination: Path | None
    content: bytes | None


@dataclass(frozen=True)
class ManifestApplyResult:
    files_touched: list[str]
    checkpoint: CheckpointRecord
    inventory: ScopedInventory
    rolled_back: bool = False


def preflight_manifest(root: Path | str, manifest: OperationManifest) -> list[PreparedOperation]:
    workspace = Path(root).resolve()
    if not workspace.is_dir():
        raise NotADirectoryError(workspace)
    prepared: list[PreparedOperation] = []
    occupied: set[str] = set()
    total = 0
    for operation in manifest.operations:
        if isinstance(operation, MoveFile):
            source = _safe_path(workspace, operation.source_path)
            destination = _safe_path(workspace, operation.destination_path)
            _claim(occupied, operation.source_path, operation.destination_path)
            _require_file_hash(source, operation.expected_sha256)
            if destination.exists():
                raise FileExistsError(f"Move destination exists: {operation.destination_path}")
            content = source.read_bytes()
            total += len(content)
            prepared.append(PreparedOperation(operation, source, destination, content))
            continue
        path = _safe_path(workspace, operation.path)
        _claim(occupied, operation.path)
        if isinstance(operation, CreateFile):
            if path.exists():
                raise FileExistsError(f"Create destination exists: {operation.path}")
            content = operation.content.encode("utf-8")
            _check_size(operation.path, content)
            total += len(content)
            prepared.append(PreparedOperation(operation, None, path, content))
        elif isinstance(operation, ModifyFile):
            _require_file_hash(path, operation.expected_sha256)
            original = path.read_text(encoding="utf-8")
            updated = (
                operation.content
                if operation.mode == "replace"
                else apply_unified_diff(original, operation.unified_diff or "")
            )
            content = (updated or "").encode("utf-8")
            _check_size(operation.path, content)
            total += len(content)
            prepared.append(PreparedOperation(operation, path, path, content))
        elif isinstance(operation, DeleteFile):
            _require_file_hash(path, operation.expected_sha256)
            prepared.append(PreparedOperation(operation, path, None, None))
    if total > MAX_TOTAL_BYTES:
        raise ValueError("Manifest content exceeds 256 KiB.")
    return prepared


def apply_manifest(root: Path | str, manifest: OperationManifest) -> ManifestApplyResult:
    workspace = Path(root).resolve()
    prepared = preflight_manifest(workspace, manifest)
    inventory = build_scoped_inventory(workspace, manifest)
    affected = sorted(
        {
            str(path.relative_to(workspace)).replace("\\", "/")
            for item in prepared
            for path in (item.source, item.destination)
            if path is not None
        }
    )
    checkpoint = create_checkpoint(workspace, [Path(path) for path in affected])
    staged: list[tuple[Path, Path, bool]] = []
    created_dirs: list[Path] = []
    try:
        for item in prepared:
            if item.destination is None or item.content is None:
                continue
            _mkdir_parents(item.destination.parent, workspace, created_dirs)
            temporary = item.destination.with_name(f".{item.destination.name}.heph-{uuid4().hex}.tmp")
            with temporary.open("xb") as handle:
                handle.write(item.content)
                handle.flush()
                os.fsync(handle.fileno())
            executable = isinstance(item.operation, CreateFile) and item.operation.executable
            staged.append((temporary, item.destination, executable))
        for temporary, destination, executable in staged:
            os.replace(temporary, destination)
            if executable and os.name != "nt":
                destination.chmod(destination.stat().st_mode | 0o100)
        for item in prepared:
            if (
                isinstance(item.operation, (DeleteFile, MoveFile))
                and item.source is not None
                and item.source != item.destination
                and item.source.exists()
            ):
                item.source.unlink()
        return ManifestApplyResult(files_touched=affected, checkpoint=checkpoint, inventory=inventory)
    except Exception:
        for temporary, _, _ in staged:
            if temporary.exists():
                temporary.unlink()
        restore_checkpoint(checkpoint)
        for directory in reversed(created_dirs):
            if directory.exists() and not any(directory.iterdir()):
                directory.rmdir()
        raise


def apply_unified_diff(original: str, diff: str) -> str:
    lines = diff.splitlines(keepends=True)
    if not lines or any(line.startswith(("diff --git", "Binary files")) for line in lines):
        raise ValueError("Only one textual unified diff is supported.")
    original_lines = original.splitlines(keepends=True)
    output: list[str] = []
    source_index = 0
    index = 0
    while index < len(lines) and not lines[index].startswith("@@"):
        index += 1
    if index == len(lines):
        raise ValueError("Unified diff contains no hunks.")
    while index < len(lines):
        header = lines[index]
        match = re.match(r"@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@", header)
        if match is None:
            raise ValueError("Malformed unified diff hunk.")
        start = int(match.group(1)) - 1
        if start < source_index or start > len(original_lines):
            raise ValueError("Unified diff hunk position is invalid.")
        output.extend(original_lines[source_index:start])
        source_index = start
        index += 1
        while index < len(lines) and not lines[index].startswith("@@"):
            line = lines[index]
            if line.startswith("\\ No newline"):
                index += 1
                continue
            marker, value = line[:1], line[1:]
            if marker in {" ", "-"}:
                if source_index >= len(original_lines) or original_lines[source_index] != value:
                    raise ValueError("Unified diff context does not match current file.")
                if marker == " ":
                    output.append(value)
                source_index += 1
            elif marker == "+":
                output.append(value)
            else:
                raise ValueError("Unsupported unified diff line.")
            index += 1
    output.extend(original_lines[source_index:])
    return "".join(output)


def _safe_path(root: Path, raw_path: str) -> Path:
    if not raw_path or "\x00" in raw_path:
        raise PermissionError("Manifest path is empty or invalid.")
    normalized = raw_path.replace("\\", "/")
    pure = PurePosixPath(normalized)
    if pure.is_absolute() or ".." in pure.parts or ":" in pure.parts[0]:
        raise PermissionError(f"Unsafe manifest path: {raw_path}")
    if pure.parts[0].lower() in {".git", ".hephaestus"}:
        raise PermissionError(f"Protected repository path: {raw_path}")
    target = root.joinpath(*pure.parts)
    current = root
    for part in pure.parts:
        current = current / part
        if current.exists() and current.is_symlink():
            raise PermissionError(f"Symlink paths are not allowed: {raw_path}")
    resolved = target.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise PermissionError(f"Path escapes repository: {raw_path}") from error
    if is_protected_path(normalized):
        raise PermissionError(f"Secret-like path is protected: {raw_path}")
    return resolved


def _require_file_hash(path: Path, expected: str) -> None:
    if not path.is_file():
        raise FileNotFoundError(path)
    if not _HASH_RE.fullmatch(expected) or sha256_file(path) != expected:
        raise ValueError(f"File hash mismatch: {path.name}")


def _claim(occupied: set[str], *paths: str) -> None:
    normalized = [str(PurePosixPath(path.replace("\\", "/"))).lower() for path in paths]
    if any(path in occupied for path in normalized) or len(set(normalized)) != len(normalized):
        raise ValueError("Manifest contains duplicate or conflicting paths.")
    occupied.update(normalized)


def _check_size(path: str, content: bytes) -> None:
    if len(content) > MAX_FILE_BYTES:
        raise ValueError(f"File exceeds 128 KiB: {path}")


def _mkdir_parents(path: Path, root: Path, created: list[Path]) -> None:
    missing: list[Path] = []
    current = path
    while current != root and not current.exists():
        missing.append(current)
        current = current.parent
    path.mkdir(parents=True, exist_ok=True)
    created.extend(reversed(missing))
