"""Safe local filesystem operations for the tool runtime."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path

from hephaestus.tool_runtime.schemas import (
    FileMetadata,
    FilesystemListResult,
    FilesystemReadRequest,
    FilesystemReadResult,
    FilesystemSearchMatch,
    FilesystemSearchRequest,
    FilesystemSearchResult,
)

_IGNORED_DIR_NAMES = {
    ".git",
    ".hg",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "node_modules",
}

_PROTECTED_SUFFIXES = {".pem", ".key", ".p12", ".pfx", ".kdbx"}
_PROTECTED_NAMES = {"id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"}
_SECRET_TOKENS = ("credential", "credentials", "secret", "secrets", "token", "password")


def resolve_workspace(workspace_path: str | Path = ".") -> Path:
    """Resolve the default workspace path."""

    workspace = Path(workspace_path).resolve()
    if not workspace.exists():
        raise FileNotFoundError(f"Workspace path not found: {workspace}")
    if not workspace.is_dir():
        raise NotADirectoryError(f"Workspace path is not a directory: {workspace}")
    return workspace


def resolve_inside_workspace(
    workspace_path: str | Path,
    target_path: str | Path,
    *,
    allow_outside_workspace: bool = False,
) -> Path:
    """Resolve a target path and keep it inside the workspace unless explicitly allowed."""

    workspace = resolve_workspace(workspace_path)
    raw = Path(target_path)
    target = raw.resolve() if raw.is_absolute() else (workspace / raw).resolve()
    if not allow_outside_workspace and not _is_relative_to(target, workspace):
        raise PermissionError(f"Path is outside workspace: {target}")
    return target


def list_directory(workspace_path: str | Path, path: str | Path = ".") -> FilesystemListResult:
    """List one directory without reading file contents."""

    target = resolve_inside_workspace(workspace_path, path)
    if not target.exists():
        raise FileNotFoundError(f"Path not found: {target}")
    if not target.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {target}")
    entries = [_metadata(item, workspace=resolve_workspace(workspace_path)) for item in sorted(target.iterdir())]
    return FilesystemListResult(path=_relative_text(target, resolve_workspace(workspace_path)), entries=entries)


def read_file(request: FilesystemReadRequest) -> FilesystemReadResult:
    """Read a file safely, withholding protected contents by default."""

    workspace = resolve_workspace(request.workspace_path)
    target = resolve_inside_workspace(
        workspace,
        request.path,
        allow_outside_workspace=request.allow_outside_workspace,
    )
    if not target.exists():
        raise FileNotFoundError(f"Path not found: {target}")
    if not target.is_file():
        raise IsADirectoryError(f"Path is not a file: {target}")

    metadata = _metadata(target, workspace=workspace)
    protected = metadata.protected
    if protected and not request.include_protected_content:
        return FilesystemReadResult(
            path=metadata.path,
            content=None,
            metadata=metadata,
            protected=True,
            message="Protected file detected; content not shown.",
        )

    raw = target.read_bytes()
    truncated = len(raw) > request.max_bytes
    if truncated:
        raw = raw[: request.max_bytes]
    text = raw.decode("utf-8", errors="replace")
    return FilesystemReadResult(
        path=metadata.path,
        content=text,
        metadata=metadata,
        protected=protected,
        truncated=truncated,
        message="Content truncated." if truncated else "",
    )


def search_files(request: FilesystemSearchRequest) -> FilesystemSearchResult:
    """Search UTF-8-ish text files by simple substring match."""

    workspace = resolve_workspace(request.workspace_path)
    target = resolve_inside_workspace(workspace, request.path)
    if not target.exists():
        raise FileNotFoundError(f"Path not found: {target}")

    matches: list[FilesystemSearchMatch] = []
    skipped_protected: list[str] = []
    truncated = False
    files = [target] if target.is_file() else _walk_files(target)
    for file_path in files:
        metadata = _metadata(file_path, workspace=workspace)
        if metadata.protected:
            skipped_protected.append(metadata.path)
            continue
        if metadata.size_bytes > request.max_file_bytes:
            continue
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line_number, line in enumerate(content.splitlines(), start=1):
            if request.query in line:
                matches.append(
                    FilesystemSearchMatch(
                        path=metadata.path,
                        line_number=line_number,
                        line=line.strip(),
                    )
                )
                if len(matches) >= request.max_matches:
                    truncated = True
                    return FilesystemSearchResult(
                        query=request.query,
                        path=_relative_text(target, workspace),
                        matches=matches,
                        skipped_protected=skipped_protected,
                        truncated=truncated,
                    )
    return FilesystemSearchResult(
        query=request.query,
        path=_relative_text(target, workspace),
        matches=matches,
        skipped_protected=skipped_protected,
        truncated=truncated,
    )


def is_protected_path(path: str | Path) -> bool:
    """Return whether a path looks like a secret, credential, token, or key file."""

    path_obj = Path(path)
    name = path_obj.name.lower()
    lowered = str(path_obj).lower()
    if name == ".env" or name.startswith(".env."):
        return True
    if name in _PROTECTED_NAMES:
        return True
    if path_obj.suffix.lower() in _PROTECTED_SUFFIXES:
        return True
    return any(token in lowered for token in _SECRET_TOKENS)


def sha256_text(value: str) -> str:
    """Hash text content for checkpoint and patch validation."""

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    """Hash a file's raw bytes."""

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 64), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _metadata(path: Path, *, workspace: Path) -> FileMetadata:
    stat = path.stat()
    return FileMetadata(
        path=_relative_text(path, workspace),
        is_file=path.is_file(),
        is_dir=path.is_dir(),
        size_bytes=stat.st_size if path.is_file() else 0,
        modified_at=None if stat.st_mtime <= 0 else _datetime_from_timestamp(stat.st_mtime),
        protected=is_protected_path(path),
        hash_sha256=sha256_file(path) if path.is_file() and not is_protected_path(path) else "",
    )


def _walk_files(root: Path) -> Iterable[Path]:
    for item in root.rglob("*"):
        if any(part in _IGNORED_DIR_NAMES for part in item.parts):
            continue
        if item.is_file():
            yield item


def _relative_text(path: Path, workspace: Path) -> str:
    if _is_relative_to(path, workspace):
        text = str(path.relative_to(workspace))
        return "." if text == "." else text.replace("\\", "/")
    return str(path)


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _datetime_from_timestamp(timestamp: float) -> object:
    from datetime import UTC, datetime

    return datetime.fromtimestamp(timestamp, UTC)
