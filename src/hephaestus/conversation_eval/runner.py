"""Load and run deterministic conversation quality benchmarks."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from hephaestus.conversation import ConversationRequest, ConversationService
from hephaestus.conversation_eval.evaluator import evaluate_conversation_response
from hephaestus.conversation_eval.schemas import (
    BenchmarkMemoryContext,
    BenchmarkStrategicMemoryContext,
    ConversationBenchmarkFixture,
    ConversationEvaluationResult,
)
from hephaestus.memory import MemoryItem, MemoryType
from hephaestus.storage import SqliteMemoryRepository
from hephaestus.strategic_memory import (
    StrategicMemoryItem,
    StrategicMemoryRepository,
    StrategicMemoryScope,
    StrategicMemorySource,
    StrategicMemoryStability,
    StrategicMemoryType,
)


def default_conversation_benchmark_directory() -> Path:
    """Return the default conversation benchmark directory."""

    cwd_candidate = Path.cwd() / "benchmarks" / "conversation"
    if cwd_candidate.exists():
        return cwd_candidate
    return Path(__file__).resolve().parents[3] / "benchmarks" / "conversation"


def discover_conversation_benchmark_paths(directory: Path | str | None = None) -> list[Path]:
    """List conversation benchmark JSON fixtures in stable order."""

    root = Path(directory) if directory is not None else default_conversation_benchmark_directory()
    if not root.exists():
        return []
    return sorted(path for path in root.glob("*.json") if path.is_file())


def load_conversation_benchmark(
    identifier: str | Path,
    directory: Path | str | None = None,
) -> ConversationBenchmarkFixture:
    """Load a fixture by path, filename, stem, or benchmark id."""

    path = resolve_conversation_benchmark_path(identifier, directory=directory)
    data = _read_json_object(path)
    data.setdefault("id", path.stem)
    data.setdefault("title", path.stem.replace("_", " ").title())
    return ConversationBenchmarkFixture.model_validate(data).model_copy(update={"source_path": path})


def load_all_conversation_benchmarks(
    directory: Path | str | None = None,
) -> list[ConversationBenchmarkFixture]:
    """Load all discovered conversation benchmark fixtures."""

    return [
        load_conversation_benchmark(path, directory=directory)
        for path in discover_conversation_benchmark_paths(directory)
    ]


def resolve_conversation_benchmark_path(
    identifier: str | Path,
    directory: Path | str | None = None,
) -> Path:
    """Resolve a conversation benchmark identifier to a JSON fixture path."""

    requested = Path(identifier)
    if requested.exists():
        return requested
    root = Path(directory) if directory is not None else default_conversation_benchmark_directory()
    requested_text = str(identifier)
    requested_stem = requested.stem
    for candidate in discover_conversation_benchmark_paths(root):
        if requested_text in {candidate.name, candidate.stem} or requested_stem == candidate.stem:
            return candidate
    for candidate in discover_conversation_benchmark_paths(root):
        data = _read_json_object(candidate)
        if str(data.get("id", "")) == requested_text:
            return candidate
    raise FileNotFoundError(f"Conversation benchmark not found: {identifier}")


def run_conversation_benchmark(
    fixture: ConversationBenchmarkFixture,
    *,
    provider: str = "local",
) -> ConversationEvaluationResult:
    """Run one conversation benchmark and return deterministic evaluation."""

    database_path = Path(tempfile.mkdtemp(prefix="heph_conv_bench_")) / "hephaestus.db"
    _seed_regular_memory(database_path, fixture.memory_context)
    _seed_strategic_memory(database_path, fixture.strategic_memory_context)
    service = ConversationService(database_path)
    response = service.respond(
        ConversationRequest(
            prompt=fixture.prompt,
            mode=fixture.mode,
            repo_path=_resolve_repo_path(fixture.repo_path),
            provider=provider,
            discussion=True,
        )
    )
    return evaluate_conversation_response(fixture, response)


def run_conversation_benchmarks(
    target: str | Path | None = None,
    *,
    provider: str = "local",
) -> list[ConversationEvaluationResult]:
    """Run one target fixture or all conversation fixtures."""

    fixtures = [load_conversation_benchmark(target)] if target is not None else load_all_conversation_benchmarks()
    return [run_conversation_benchmark(fixture, provider=provider) for fixture in fixtures]


def _seed_regular_memory(
    database_path: Path,
    memories: list[BenchmarkMemoryContext],
) -> None:
    repository = SqliteMemoryRepository(database_path)
    for memory in memories:
        repository.add(
            MemoryItem(
                type=_memory_type(memory.type),
                content=memory.content,
                summary=memory.summary,
                tags=memory.tags,
                importance=memory.importance,
                confidence=memory.confidence,
                source="conversation-benchmark",
            )
        )


def _seed_strategic_memory(
    database_path: Path,
    memories: list[BenchmarkStrategicMemoryContext],
) -> None:
    repository = StrategicMemoryRepository(database_path)
    for memory in memories:
        repository.save_memory(
            StrategicMemoryItem(
                type=_strategic_type(memory.type),
                scope=StrategicMemoryScope.PROJECT,
                content=memory.content,
                summary=memory.summary,
                tags=memory.tags,
                importance=memory.importance,
                confidence=memory.confidence,
                stability=_strategic_stability(memory.stability),
                source=StrategicMemorySource.MANUAL,
            )
        )


def _resolve_repo_path(value: str | None) -> str | None:
    if value is None:
        return None
    path = Path(value)
    if path.exists():
        return str(path)
    repo_root_candidate = Path(__file__).resolve().parents[3] / value
    if repo_root_candidate.exists():
        return str(repo_root_candidate)
    return value


def _memory_type(value: str) -> MemoryType:
    try:
        return MemoryType(value)
    except ValueError:
        return MemoryType.PROJECT


def _strategic_type(value: str) -> StrategicMemoryType:
    try:
        return StrategicMemoryType(value)
    except ValueError:
        return StrategicMemoryType.PRINCIPLE


def _strategic_stability(value: str) -> StrategicMemoryStability:
    try:
        return StrategicMemoryStability(value)
    except ValueError:
        return StrategicMemoryStability.MEDIUM_TERM


def _read_json_object(path: Path) -> dict[str, Any]:
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise ValueError(f"Conversation benchmark fixture must be a JSON object: {path}")
    return loaded
