"""Structured provider contract helpers for greenfield coding stages."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ValidationError

from hephaestus.coding_loop.schemas import OperationManifest, ProviderProjectPlan, RepairManifest

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)


@dataclass(frozen=True)
class StructuredParseFailure(Exception):
    label: str
    status: str
    message: str
    validation_errors: list[dict[str, Any]]
    content_length: int
    content_sha256: str

    @property
    def failure_code(self) -> str:
        prefix = self.label.upper()
        if self.status in {"invalid_json", "multiple_top_level_objects", "not_json_object"}:
            return f"{prefix}_JSON_PARSE_FAILED"
        if self.status == "schema_validation_failed":
            return f"{prefix}_SCHEMA_VALIDATION_FAILED"
        return f"{prefix}_FORMAT_REPAIR_FAILED"


@dataclass(frozen=True)
class StructuredParseSuccess:
    value: Any
    status: str
    content_length: int
    content_sha256: str


def parse_structured_response(
    text: str,
    schema: type[BaseModel],
    label: str,
) -> StructuredParseSuccess:
    """Parse one structured JSON object and validate it against a Pydantic schema."""

    normalized = text.lstrip("\ufeff").strip()
    content_length = len(normalized)
    content_sha256 = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    data, status = _parse_json_object(normalized)
    if data is None:
        fenced = _extract_single_fenced_block(normalized)
        if fenced is None:
            raise StructuredParseFailure(
                label=label,
                status=status,
                message=f"Provider returned {status}.",
                validation_errors=[],
                content_length=content_length,
                content_sha256=content_sha256,
            )
        data, fenced_status = _parse_json_object(fenced)
        if data is None:
            raise StructuredParseFailure(
                label=label,
                status=fenced_status,
                message=f"Provider returned fenced {fenced_status}.",
                validation_errors=[],
                content_length=content_length,
                content_sha256=content_sha256,
            )
        status = "ok_fenced_json"
    try:
        value = schema.model_validate(data)
    except ValidationError as error:
        raise StructuredParseFailure(
            label=label,
            status="schema_validation_failed",
            message=f"Provider JSON failed {schema.__name__} validation.",
            validation_errors=[dict(item) for item in error.errors(include_url=False)],
            content_length=content_length,
            content_sha256=content_sha256,
        ) from error
    return StructuredParseSuccess(
        value=value,
        status=status,
        content_length=content_length,
        content_sha256=content_sha256,
    )


def provider_contract_system_prompt(schema: type[BaseModel], label: str) -> str:
    example = compact_example(schema)
    required = ", ".join(_required_fields(schema))
    return (
        "You are returning machine-readable JSON for Hephaestus. "
        "Return exactly one top-level JSON object. Do not wrap it in markdown fences. "
        "Do not include prose before or after the JSON object. "
        f"The required top-level fields are: {required}. "
        "Null values and omitted required fields are invalid. "
        "Use only field names and operation discriminator values accepted by the schema. "
        f"Compact valid {label} JSON example: {example}"
    )


def format_repair_prompt(
    *,
    schema: type[BaseModel],
    label: str,
    original_content: str,
    failure: StructuredParseFailure,
) -> str:
    schema_json = json.dumps(schema.model_json_schema(), ensure_ascii=False, separators=(",", ":"))
    errors_json = json.dumps(
        failure.validation_errors or [{"status": failure.status, "message": failure.message}],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return (
        "Repair the provider final content into valid JSON only. "
        "Preserve the same meaning and do not add implementation ideas. "
        "Fix only JSON formatting or schema field shape. "
        "Return exactly one top-level JSON object, with no markdown fences and no prose. "
        "Do not use null for required fields.\n"
        f"Label: {label}\n"
        f"Validation errors: {errors_json}\n"
        f"Compact valid example: {compact_example(schema)}\n"
        f"JSON schema: {schema_json}\n"
        f"Original final content:\n{original_content}"
    )


def compact_example(schema: type[BaseModel]) -> str:
    example = _example_data(schema)
    schema.model_validate(example)
    return json.dumps(example, ensure_ascii=False, separators=(",", ":"))


def _parse_json_object(text: str) -> tuple[dict[str, Any] | None, str]:
    if not text:
        return None, "invalid_json"
    decoder = json.JSONDecoder()
    try:
        data, index = decoder.raw_decode(text)
    except json.JSONDecodeError:
        return None, "invalid_json"
    if text[index:].strip():
        return None, "multiple_top_level_objects"
    if not isinstance(data, dict):
        return None, "not_json_object"
    return data, "ok_direct_json"


def _extract_single_fenced_block(text: str) -> str | None:
    blocks = [match.group(1).strip() for match in _FENCE_RE.finditer(text)]
    if len(blocks) != 1:
        return None
    return blocks[0]


def _required_fields(schema: type[BaseModel]) -> list[str]:
    if schema is ProviderProjectPlan:
        return [
            "task_summary",
            "architecture",
            "proposed_files",
            "implementation_approach",
            "tests",
            "validation_commands",
            "assumptions",
            "risks",
        ]
    if schema is OperationManifest:
        return [
            "task_summary",
            "assumptions",
            "operations",
            "validation_commands",
            "expected_files",
            "risks",
        ]
    if schema is RepairManifest:
        return [
            "task_summary",
            "failure_classification",
            "operations",
            "validation_commands",
            "expected_files",
            "risks",
        ]
    return [name for name, field in schema.model_fields.items() if field.is_required()]


def _example_data(schema: type[BaseModel]) -> dict[str, Any]:
    if schema is ProviderProjectPlan:
        return {
            "task_summary": "Create a small Python CLI project.",
            "architecture": ["Package module plus tests and README."],
            "proposed_files": [{"path": "taskforge/__main__.py", "purpose": "CLI entrypoint"}],
            "implementation_approach": ["Use argparse and JSON persistence."],
            "tests": ["Exercise add, list, done, delete, and error cases."],
            "validation_commands": ["python -m unittest discover -v"],
            "assumptions": [],
            "risks": [],
        }
    if schema is OperationManifest:
        return {
            "task_summary": "Create TaskForge files.",
            "assumptions": [],
            "operations": [
                {
                    "operation": "create",
                    "path": "README.md",
                    "content": "# TaskForge\n",
                    "encoding": "utf-8",
                    "executable": False,
                }
            ],
            "validation_commands": ["python -m unittest discover -v"],
            "expected_files": ["README.md"],
            "risks": [],
        }
    if schema is RepairManifest:
        return {
            "task_summary": "Repair validation failure.",
            "failure_classification": "VALIDATION_TESTS_FAILED",
            "operations": [
                {
                    "operation": "modify",
                    "path": "taskforge/storage.py",
                    "expected_sha256": "0" * 64,
                    "mode": "replace",
                    "content": "print('fixed')\n",
                }
            ],
            "validation_commands": ["python -m unittest discover -s tests -p \"test_*.py\" -v"],
            "expected_files": ["taskforge/storage.py", "tests/test_storage.py"],
            "risks": [],
        }
    raise TypeError(f"No compact example registered for {schema.__name__}.")
