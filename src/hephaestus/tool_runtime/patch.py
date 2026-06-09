"""Deterministic patch proposal and application."""

from __future__ import annotations

import difflib
from pathlib import Path

from hephaestus.tool_runtime.checkpoint import create_checkpoint
from hephaestus.tool_runtime.filesystem import (
    is_protected_path,
    resolve_inside_workspace,
    resolve_workspace,
    sha256_text,
)
from hephaestus.tool_runtime.schemas import (
    CheckpointRecord,
    PatchApplyResult,
    PatchProposal,
)


def propose_patch(
    workspace_path: str | Path,
    path: str | Path,
    *,
    find: str,
    replace: str,
    action_id: str | None = None,
) -> PatchProposal:
    """Build a single-file find/replace patch proposal without writing files."""

    workspace = resolve_workspace(workspace_path)
    target = resolve_inside_workspace(workspace, path)
    if not target.exists():
        raise FileNotFoundError(f"Path not found: {target}")
    if not target.is_file():
        raise IsADirectoryError(f"Path is not a file: {target}")
    if is_protected_path(target):
        raise PermissionError("Protected files cannot be patched by this runtime.")
    content = target.read_text(encoding="utf-8")
    if find not in content:
        raise ValueError("Find text was not found; no patch proposal created.")
    updated = content.replace(find, replace, 1)
    relative = _relative_text(target, workspace)
    diff = "".join(
        difflib.unified_diff(
            content.splitlines(keepends=True),
            updated.splitlines(keepends=True),
            fromfile=f"a/{relative}",
            tofile=f"b/{relative}",
        )
    )
    return PatchProposal(
        action_id=action_id,
        workspace_path=str(workspace),
        path=relative,
        find=find,
        replace=replace,
        original_hash=sha256_text(content),
        diff=diff,
        files_touched=[relative],
    )


def apply_patch_proposal(
    proposal: PatchProposal,
    *,
    action_id: str,
) -> tuple[PatchApplyResult, CheckpointRecord]:
    """Apply a stored patch proposal after approval, creating a checkpoint first."""

    workspace = resolve_workspace(proposal.workspace_path)
    target = resolve_inside_workspace(workspace, proposal.path)
    if not target.exists():
        raise FileNotFoundError(f"Path not found: {target}")
    if is_protected_path(target):
        raise PermissionError("Protected files cannot be patched by this runtime.")
    content = target.read_text(encoding="utf-8")
    current_hash = sha256_text(content)
    if current_hash != proposal.original_hash:
        raise ValueError("File changed since patch proposal; refusing stale patch.")
    checkpoint = create_checkpoint(workspace, [proposal.path], action_id=action_id)
    updated = content.replace(proposal.find, proposal.replace, 1)
    target.write_text(updated, encoding="utf-8")
    result = PatchApplyResult(
        proposal_id=proposal.id,
        action_id=action_id,
        applied=True,
        message="Patch applied.",
        files_touched=proposal.files_touched,
        checkpoint_id=checkpoint.id,
    )
    return result, checkpoint


def _relative_text(path: Path, workspace: Path) -> str:
    text = str(path.relative_to(workspace))
    return "." if text == "." else text.replace("\\", "/")
