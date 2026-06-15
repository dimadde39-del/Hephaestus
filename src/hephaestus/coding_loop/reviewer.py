"""Lightweight review for coding-loop patch proposals."""

from __future__ import annotations

import re
from pathlib import Path

from hephaestus.coding_loop.analysis import record_coding_trace
from hephaestus.coding_loop.schemas import (
    CodingChangeProposal,
    CodingLoopStatus,
    CodingPlan,
    CodingReview,
    CodingRisk,
)
from hephaestus.tool_runtime.filesystem import is_protected_path

_SECRET_PATTERNS = [
    re.compile(r"(?i)(api[_-]?key|secret|token|password)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{8,}"),
    re.compile(r"-----BEGIN [A-Z ]+PRIVATE KEY-----"),
]


class CodingPatchReviewer:
    """Review a coding-loop patch before applying it."""

    def __init__(self, database_path: Path | str | None = None) -> None:
        self.database_path = database_path

    def review(
        self,
        plan: CodingPlan,
        change: CodingChangeProposal,
        *,
        validation_enabled: bool = True,
    ) -> CodingReview:
        """Return a transparent allow/block review."""

        findings: list[str] = []
        blocked = False
        actual_files = change.patch_set.files_touched
        expected_files = plan.likely_files
        protected_files = [path for path in actual_files if is_protected_path(path)]
        if not actual_files:
            blocked = True
            findings.append("patch does not touch any files")
        if protected_files:
            blocked = True
            findings.append("patch touches protected secret-like files")
        if plan.scope_too_large:
            blocked = True
            findings.append("plan scope is too large for automatic patching")
        unexpected = _unexpected_files(expected_files, actual_files)
        if unexpected:
            blocked = True
            findings.append("patch touches files outside the planned scope: " + ", ".join(unexpected))
        if _diff_contains_obvious_secret(change.patch_set.diff):
            blocked = True
            findings.append("patch diff appears to contain a secret or credential")
        if not _diff_matches_request(change.patch_set.diff, plan.user_request):
            blocked = True
            findings.append("patch diff does not appear to match the user request")
        validation_present = bool(change.validation_commands)
        if validation_enabled and not validation_present:
            findings.append("no validation commands were detected")
            if change.risk != CodingRisk.LOW:
                blocked = True
        if change.risk == CodingRisk.HIGH:
            blocked = True
            findings.append("high-risk coding patches are plan-only in Phase 5G")
        if not findings:
            findings.append("patch matches request, expected files, and validation expectations")

        approved = not blocked
        review = CodingReview(
            request_id=plan.request_id,
            plan_id=plan.id,
            change_id=change.id,
            approved=approved,
            blocked=blocked,
            risk=change.risk,
            summary=(
                "Patch review passed."
                if approved
                else "Patch review blocked apply: " + "; ".join(findings)
            ),
            findings=findings,
            expected_files=expected_files,
            actual_files=actual_files,
            protected_files=protected_files,
            validation_present=validation_present,
            metadata={"validation_enabled": validation_enabled},
        )
        if self.database_path is not None and plan.run_id is not None:
            trace = record_coding_trace(
                self.database_path,
                run_id=plan.run_id,
                phase="patch_review",
                selected_option="approved" if approved else "blocked",
                rationale=review.summary,
                request_id=plan.request_id,
                status=(
                    CodingLoopStatus.PATCH_PROPOSED
                    if approved
                    else CodingLoopStatus.BLOCKED
                ),
                risk=change.risk,
                related_ids=[plan.id, change.id],
                objective_score=1.0 if approved else 0.0,
                tags=["patch_review"],
            )
            review = review.model_copy(update={"decision_trace_id": trace.id})
        return review


def _unexpected_files(expected_files: list[str], actual_files: list[str]) -> list[str]:
    if not expected_files:
        return []
    expected = set(expected_files)
    return [path for path in actual_files if path not in expected]


def _diff_contains_obvious_secret(diff: str) -> bool:
    added_lines = "\n".join(
        line for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++")
    )
    return any(pattern.search(added_lines) is not None for pattern in _SECRET_PATTERNS)


def _diff_matches_request(diff: str, request: str) -> bool:
    terms = [
        term
        for term in re.findall(r"[a-z0-9][a-z0-9_-]+", request.lower())
        if len(term) >= 5 and term not in {"update", "improve", "change", "mention"}
    ]
    if not terms:
        return True
    lowered_diff = diff.lower()
    overlap = [term for term in terms if term in lowered_diff]
    return bool(overlap)
