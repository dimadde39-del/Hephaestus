"""Patch proposal support for the repo-aware coding loop."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from hephaestus.coding_loop.analysis import record_coding_outcome, record_coding_trace
from hephaestus.coding_loop.repository import CodingLoopRepository
from hephaestus.coding_loop.schemas import (
    CodingChangeProposal,
    CodingLoopStatus,
    CodingPatch,
    CodingPatchSet,
    CodingPlan,
    CodingScopeType,
)
from hephaestus.conversation.providers import list_conversation_providers
from hephaestus.models import ModelRequest
from hephaestus.outcomes import OutcomeStatus
from hephaestus.storage import RunRecord, RunRepository
from hephaestus.tool_runtime import ToolRuntime
from hephaestus.tool_runtime.filesystem import is_protected_path

_MAX_DETERMINISTIC_FILE_CHARS = 120_000


@dataclass(frozen=True)
class _PatchSpec:
    path: str
    find: str
    replace: str
    kind: str


class CodingPatcher:
    """Create deterministic or provider-backed coding patch proposals."""

    def __init__(self, database_path: Path | str | None = None) -> None:
        self.repository = CodingLoopRepository(database_path)
        self.database_path = self.repository.database_path
        self.run_repository = RunRepository(self.database_path)

    def propose(self, plan: CodingPlan) -> CodingChangeProposal:
        """Create and persist a patch proposal for a plan."""

        if plan.scope_too_large:
            raise ValueError("Request is too large for automatic patch proposal in Phase 5G.")
        if not plan.patch_proposal_possible:
            raise ValueError("No deterministic patch proposal is available for this request.")

        spec = self._deterministic_spec(plan)
        if spec is None:
            spec = self._model_backed_spec(plan)
        if spec is None:
            raise ValueError("No safe patch proposal could be generated for this scoped request.")
        if is_protected_path(spec.path):
            raise PermissionError("Protected files cannot be patched by the coding loop.")

        runtime = ToolRuntime(self.database_path, workspace_path=plan.repo_path)
        action, _result, proposal = runtime.propose_patch(
            spec.path,
            find=spec.find,
            replace=spec.replace,
        )
        run_id = plan.run_id or self.run_repository.save_run(
            RunRecord(
                goal=f"Coding patch proposal: {plan.user_request}",
                mode="coding_patch_proposal",
            )
        ).id
        trace = record_coding_trace(
            self.database_path,
            run_id=run_id,
            phase="patch_proposal",
            selected_option=proposal.id,
            rationale=(
                "Patch proposal was created without modifying files. "
                f"Proposal kind: {spec.kind}."
            ),
            request_id=plan.request_id,
            status=CodingLoopStatus.PATCH_PROPOSED,
            risk=plan.scope.risk,
            related_ids=[plan.id, action.id, proposal.id],
            objective_score=1.0,
            safety=False,
            tags=["patch_proposal"],
        )
        outcome = record_coding_outcome(
            self.database_path,
            run_id=run_id,
            decision_trace_id=trace.id,
            status=OutcomeStatus.SUCCESS,
            summary=f"Patch proposal {proposal.id} created for {proposal.path}.",
            request_id=plan.request_id,
            evidence_content=proposal.diff,
            tags=["patch-proposed"],
        )
        coding_patch = CodingPatch(
            path=proposal.path,
            diff=proposal.diff,
            find=proposal.find,
            replace=proposal.replace,
            tool_patch_id=proposal.id,
            tool_action_id=action.id,
            original_hash=proposal.original_hash,
            patch_kind=spec.kind,
        )
        patch_set = CodingPatchSet(
            patches=[coding_patch],
            files_touched=proposal.files_touched,
            diff=proposal.diff,
            patch_ids=[proposal.id],
            tool_action_ids=[action.id],
        )
        change = CodingChangeProposal(
            request_id=plan.request_id,
            plan_id=plan.id,
            repo_path=plan.repo_path,
            repo_profile_id=plan.repo_profile_id,
            active_policy_profile=plan.active_policy_profile,
            summary=f"Proposed {plan.scope.scope_type.value} patch for {', '.join(proposal.files_touched)}.",
            risk=plan.scope.risk,
            scope_type=plan.scope.scope_type,
            patch_set=patch_set,
            validation_commands=plan.validation_commands,
            checkpoint_plan=plan.checkpoint_plan,
            approval_required=True,
            decision_trace_ids=[trace.id],
            outcome_ids=[outcome.id],
            metadata={"proposal_kind": spec.kind},
        )
        return self.repository.save_change_proposal(change)

    def _deterministic_spec(self, plan: CodingPlan) -> _PatchSpec | None:
        root = Path(plan.repo_path)
        target = _target_file(root, plan)
        if target is None:
            return None
        content = target.read_text(encoding="utf-8", errors="replace")
        if len(content) > _MAX_DETERMINISTIC_FILE_CHARS:
            return None
        relative = str(target.relative_to(root)).replace("\\", "/")
        exact = _exact_replace_spec(relative, content, plan.user_request)
        if exact is not None:
            return exact
        if plan.scope.scope_type == CodingScopeType.DOCS:
            return _docs_append_spec(relative, content, plan.user_request)
        if plan.scope.scope_type == CodingScopeType.TESTS:
            return _line_update_spec(relative, content, plan.user_request, fallback_prefix="test")
        if plan.scope.scope_type == CodingScopeType.CONFIG:
            return _line_update_spec(relative, content, plan.user_request, fallback_prefix="config")
        if plan.scope.scope_type == CodingScopeType.BUGFIX:
            return _line_update_spec(relative, content, plan.user_request, fallback_prefix="fix")
        return None

    def _model_backed_spec(self, plan: CodingPlan) -> _PatchSpec | None:
        providers = [
            provider
            for provider in list_conversation_providers()
            if provider.is_available and provider.name != "fake"
        ]
        if not providers:
            return None
        provider = providers[0]
        profile = next(iter(provider.profiles()), None)
        if profile is None:
            return None
        prompt = _model_patch_prompt(plan)
        try:
            response = provider.complete(
                ModelRequest(
                    prompt=prompt,
                    model=profile.model,
                    temperature=0.0,
                    max_output_tokens=1_200,
                    require_json=True,
                )
            )
        except Exception:
            return None
        data = _json_object_from_text(response.text)
        if data is None:
            return None
        path = str(data.get("path", ""))
        find = str(data.get("find", ""))
        replace = str(data.get("replace", ""))
        if not path or not find or not replace:
            return None
        if path not in plan.likely_files:
            return None
        return _PatchSpec(path=path, find=find, replace=replace, kind=f"model:{provider.name}")


def _target_file(root: Path, plan: CodingPlan) -> Path | None:
    for candidate in plan.likely_files:
        target = (root / candidate).resolve()
        try:
            target.relative_to(root)
        except ValueError:
            continue
        if target.exists() and target.is_file() and not is_protected_path(target):
            return target
    return None


def _exact_replace_spec(relative: str, content: str, request: str) -> _PatchSpec | None:
    patterns = [
        r"replace\s+['\"](?P<find>.+?)['\"]\s+with\s+['\"](?P<replace>.+?)['\"]",
        r"change\s+['\"](?P<find>.+?)['\"]\s+to\s+['\"](?P<replace>.+?)['\"]",
        r"update\s+['\"](?P<find>.+?)['\"]\s+to\s+['\"](?P<replace>.+?)['\"]",
    ]
    for pattern in patterns:
        match = re.search(pattern, request, flags=re.IGNORECASE | re.DOTALL)
        if match is None:
            continue
        find = match.group("find")
        replace = match.group("replace")
        if find in content:
            return _PatchSpec(path=relative, find=find, replace=replace, kind="exact_replace")
    return None


def _docs_append_spec(relative: str, content: str, request: str) -> _PatchSpec | None:
    phrase = _mention_phrase(request)
    if phrase and phrase.lower() in content.lower():
        heading = "Coding Loop Evidence"
        body = (
            f"This document already mentions {phrase}; the coding loop keeps that claim "
            "tied to scoped patches, checkpoints, and real validation results."
        )
        updated = content.rstrip() + f"\n\n## {heading}\n\n{body}\n"
        return _PatchSpec(path=relative, find=content, replace=updated, kind="docs_append_existing")
    heading = _docs_heading(phrase)
    body = _docs_body(phrase or request)
    addition = f"\n\n## {heading}\n\n{body}\n"
    updated = content.rstrip() + addition
    return _PatchSpec(path=relative, find=content, replace=updated, kind="docs_append")


def _line_update_spec(
    relative: str,
    content: str,
    request: str,
    *,
    fallback_prefix: str,
) -> _PatchSpec | None:
    phrase = _mention_phrase(request) or _compact_request_phrase(request)
    if not phrase:
        return None
    lowered = content.lower()
    if phrase.lower() in lowered:
        replacement = phrase
        if phrase.lower().startswith(("updated ", "improved ")):
            replacement = phrase
        elif fallback_prefix == "test":
            replacement = f"updated {phrase}"
        elif fallback_prefix == "fix":
            replacement = f"fixed {phrase}"
        else:
            replacement = f"updated {phrase}"
        index = lowered.find(phrase.lower())
        find = content[index : index + len(phrase)]
        return _PatchSpec(path=relative, find=find, replace=replacement, kind="line_update")
    if "\n" in content:
        updated = content.rstrip() + f"\n\n# {fallback_prefix}: {phrase}\n"
        return _PatchSpec(path=relative, find=content, replace=updated, kind=f"{fallback_prefix}_append")
    return None


def _mention_phrase(request: str) -> str:
    match = re.search(r"\bmention\s+(?P<phrase>.+?)(?:[.!?]\s*$|$)", request, flags=re.IGNORECASE)
    if match is None:
        match = re.search(r"\badd\s+(?P<phrase>.+?)(?:[.!?]\s*$|$)", request, flags=re.IGNORECASE)
    if match is None:
        return ""
    phrase = match.group("phrase").strip(" .!?'\"")
    return _clean_phrase(phrase)


def _compact_request_phrase(request: str) -> str:
    normalized = request.strip(" .!?'\"")
    normalized = re.sub(r"^(update|improve|fix|change)\s+", "", normalized, flags=re.IGNORECASE)
    return _clean_phrase(normalized)


def _clean_phrase(phrase: str) -> str:
    phrase = " ".join(phrase.split())
    if len(phrase) > 120:
        phrase = phrase[:117].rstrip() + "..."
    return phrase


def _docs_heading(phrase: str) -> str:
    if "validation" in phrase.lower():
        return "Validation-Backed Evidence"
    if "coding loop" in phrase.lower():
        return "Repo-Aware Coding Loop"
    return "Project Note"


def _docs_body(phrase: str) -> str:
    phrase = phrase.rstrip(".")
    if "validation" in phrase.lower():
        return (
            "Hephaestus treats validation-backed release evidence as part of the normal "
            "repo workflow, so changes can be connected to real command results."
        )
    return f"Hephaestus now documents {phrase} as part of the current repo workflow."


def _model_patch_prompt(plan: CodingPlan) -> str:
    return "\n".join(
        [
            "Return JSON only with keys: path, find, replace.",
            "The patch must be one exact find/replace against an existing file.",
            "Do not include secrets. Do not touch files outside likely_files.",
            f"Request: {plan.user_request}",
            "likely_files: " + ", ".join(plan.likely_files),
            f"scope: {plan.scope.scope_type.value}",
            f"risk: {plan.scope.risk.value}",
        ]
    )


def _json_object_from_text(text: str) -> dict[str, Any] | None:
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        stripped = re.sub(r"^json\s*", "", stripped, flags=re.IGNORECASE)
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start < 0 or end < start:
        return None
    try:
        loaded = json.loads(stripped[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(loaded, dict):
        return None
    return cast(dict[str, Any], loaded)
