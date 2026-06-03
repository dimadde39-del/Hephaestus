"""Benchmark fixture discovery and loading."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from hephaestus.benchmarks.schemas import BenchmarkCase


def default_benchmark_directory() -> Path:
    """Return the preferred task graph fixture directory."""

    cwd_candidate = Path.cwd() / "benchmarks" / "task_graphs"
    if cwd_candidate.exists():
        return cwd_candidate
    return Path(__file__).resolve().parents[3] / "benchmarks" / "task_graphs"


def discover_benchmark_paths(directory: Path | str | None = None) -> list[Path]:
    """List benchmark JSON fixtures in stable order."""

    root = Path(directory) if directory is not None else default_benchmark_directory()
    if not root.exists():
        return []
    return sorted(path for path in root.glob("*.json") if path.is_file())


def load_all_benchmarks(directory: Path | str | None = None) -> list[BenchmarkCase]:
    """Load every discovered benchmark fixture."""

    return [load_benchmark(path, directory=directory) for path in discover_benchmark_paths(directory)]


def load_benchmark(identifier: str | Path, directory: Path | str | None = None) -> BenchmarkCase:
    """Load a benchmark by filesystem path, fixture filename, stem, or benchmark id."""

    path = resolve_benchmark_path(identifier, directory=directory)
    data = _read_json_object(path)
    prepared = _prepare_legacy_compatible_data(data, path)
    return BenchmarkCase.model_validate(prepared).model_copy(update={"source_path": path})


def resolve_benchmark_path(
    identifier: str | Path,
    directory: Path | str | None = None,
) -> Path:
    """Resolve a benchmark identifier to a JSON fixture path."""

    requested = Path(identifier)
    if requested.exists():
        return requested

    root = Path(directory) if directory is not None else default_benchmark_directory()
    candidates = discover_benchmark_paths(root)
    requested_text = str(identifier)
    requested_stem = requested.stem

    for candidate in candidates:
        if requested_text in {candidate.name, candidate.stem} or requested_stem == candidate.stem:
            return candidate

    for candidate in candidates:
        data = _read_json_object(candidate)
        if str(data.get("id", "")) == requested_text:
            return candidate

    raise FileNotFoundError(f"Benchmark not found: {identifier}")


def _read_json_object(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"Benchmark fixture must be a JSON object: {path}")
    return loaded


def _prepare_legacy_compatible_data(data: dict[str, Any], path: Path) -> dict[str, Any]:
    prepared = dict(data)
    prepared.setdefault("id", path.stem)
    prepared.setdefault("title", _human_title(path.stem))
    prepared.setdefault("description", "")
    prepared.setdefault("goal", prepared.get("description", ""))
    prepared.setdefault("expected_constraints", [])
    prepared.setdefault("notes", [])
    prepared.setdefault("tags", [])
    return prepared


def _human_title(stem: str) -> str:
    return stem.replace("_", " ").replace("-", " ").title()
