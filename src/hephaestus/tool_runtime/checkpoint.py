"""Lightweight checkpoint and restore support."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from hephaestus.tool_runtime.filesystem import (
    resolve_inside_workspace,
    resolve_workspace,
    sha256_text,
)
from hephaestus.tool_runtime.schemas import (
    CheckpointFileSnapshot,
    CheckpointRecord,
    RollbackPlan,
)


def create_checkpoint(
    workspace_path: str | Path,
    files: list[str | Path],
    *,
    action_id: str | None = None,
) -> CheckpointRecord:
    """Create a checkpoint with original contents for the requested files."""

    workspace = resolve_workspace(workspace_path)
    snapshots: list[CheckpointFileSnapshot] = []
    for file_path in files:
        target = resolve_inside_workspace(workspace, file_path)
        existed = target.exists()
        if existed and target.is_dir():
            raise IsADirectoryError(f"Cannot checkpoint directory contents directly: {target}")
        content: str | None = None
        hash_sha256 = ""
        modified_at = None
        if existed:
            content = target.read_text(encoding="utf-8", errors="replace")
            hash_sha256 = sha256_text(content)
            modified_at = datetime.fromtimestamp(target.stat().st_mtime, UTC)
        snapshots.append(
            CheckpointFileSnapshot(
                path=_relative_text(target, workspace),
                existed=existed,
                content=content,
                hash_sha256=hash_sha256,
                modified_at=modified_at,
            )
        )
    return CheckpointRecord(
        action_id=action_id,
        workspace_path=str(workspace),
        files=snapshots,
    )


def rollback_plan(checkpoint: CheckpointRecord) -> RollbackPlan:
    """Build a restore plan for a checkpoint."""

    warnings: list[str] = []
    workspace = Path(checkpoint.workspace_path)
    for snapshot in checkpoint.files:
        target = resolve_inside_workspace(workspace, snapshot.path)
        if snapshot.existed and not target.exists():
            warnings.append(f"{snapshot.path} no longer exists; it will be recreated.")
        if not snapshot.existed and target.exists():
            warnings.append(f"{snapshot.path} did not exist before; restore will delete it.")
    return RollbackPlan(
        checkpoint_id=checkpoint.id,
        files=checkpoint.files_touched,
        can_restore=True,
        warnings=warnings,
    )


def restore_checkpoint(checkpoint: CheckpointRecord) -> CheckpointRecord:
    """Restore files captured in a checkpoint."""

    workspace = resolve_workspace(checkpoint.workspace_path)
    for snapshot in checkpoint.files:
        target = resolve_inside_workspace(workspace, snapshot.path)
        target.parent.mkdir(parents=True, exist_ok=True)
        if snapshot.existed:
            target.write_text(snapshot.content or "", encoding="utf-8")
        elif target.exists():
            target.unlink()
    return checkpoint.model_copy(update={"restored_at": datetime.now(UTC)})


def _relative_text(path: Path, workspace: Path) -> str:
    text = str(path.relative_to(workspace))
    return "." if text == "." else text.replace("\\", "/")
