"""Conservative artifact redaction without reading provider credentials."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

_PATTERNS = (
    re.compile(r"(?i)(authorization\s*[:=]\s*bearer\s+)[^\s\"']+"),
    re.compile(r"(?i)((?:api[_-]?key|token|secret)\s*[:=]\s*)[^\s,\"']+"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
)
_REASONING_CONTENT = re.compile(
    r'(?i)("reasoning_content"\s*:\s*")(?:\\.|[^"\\])*(")'
)


def redact_text(value: str) -> str:
    redacted = _REASONING_CONTENT.sub(r"\1[REDACTED]\2", value)
    for pattern in _PATTERNS:
        redacted = pattern.sub(lambda match: f"{match.group(1) if match.groups() else ''}[REDACTED]", redacted)
    return redacted


def redact_data(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]"
            if any(
                marker in key.lower()
                for marker in ("api_key", "authorization", "credential", "secret", "reasoning_content")
            )
            else redact_data(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [redact_data(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    return value


def write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(redact_text(value), encoding="utf-8")


def write_json(path: Path, value: Any) -> None:
    write_text(path, json.dumps(redact_data(value), ensure_ascii=False, indent=2, default=str) + "\n")


def scan_artifacts(root: Path) -> list[str]:
    findings: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if redact_text(text) != text:
            findings.append(str(path.relative_to(root)).replace("\\", "/"))
        if re.search(
            r"(?i)\b(authorization|api[_-]?key|credential_store)\b(?![^\r\n]{0,80}\[REDACTED\])",
            text,
        ):
            findings.append(str(path.relative_to(root)).replace("\\", "/"))
    return sorted(set(findings))
