from hephaestus.strategic_memory import (
    StrategicMemoryEvidence,
    StrategicMemoryItem,
    StrategicMemoryRepository,
    StrategicMemoryScope,
    StrategicMemorySource,
    StrategicMemoryStability,
    StrategicMemoryType,
)


def test_strategic_memory_schema_validation() -> None:
    item = StrategicMemoryItem(
        type=StrategicMemoryType.GOAL,
        scope=StrategicMemoryScope.PROJECT,
        content="Build Hephaestus toward a 20k-star open-source project.",
        summary="20k-star open-source ambition.",
        evidence=[StrategicMemoryEvidence(source="test", content="User explicitly said 20k.")],
        tags=["Strategy", "open-source", "strategy"],
        confidence=0.9,
        importance=0.95,
        stability=StrategicMemoryStability.LONG_TERM,
        source=StrategicMemorySource.USER_EXPLICIT,
    )

    assert item.tags == ["strategy", "open-source"]
    assert item.evidence[0].confidence == 0.7
    assert "20k-star" in item.searchable_text


def test_strategic_memory_persistence_roundtrip(tmp_path) -> None:
    database_path = tmp_path / "hephaestus.db"
    repository = StrategicMemoryRepository(database_path)
    item = StrategicMemoryItem(
        type=StrategicMemoryType.PRINCIPLE,
        content="Hephaestus should separate facts from assumptions.",
        summary="Separate facts from assumptions.",
        tags=["honesty", "strategy"],
        confidence=0.88,
        importance=0.9,
    )

    saved = repository.save_memory(item)
    reloaded = StrategicMemoryRepository(database_path).get_memory(saved.id)
    listed = repository.list_memories(project="default")

    assert reloaded == saved
    assert listed[0].id == saved.id


def test_strategic_memory_search_recall_and_archive(tmp_path) -> None:
    repository = StrategicMemoryRepository(tmp_path / "hephaestus.db")
    goal = repository.save_memory(
        StrategicMemoryItem(
            type=StrategicMemoryType.AMBITION,
            content="Build Hephaestus toward a 20k-star open-source project.",
            summary="20k-star ambition.",
            tags=["strategy", "open-source", "ambition"],
            importance=0.95,
        )
    )
    repository.save_memory(
        StrategicMemoryItem(
            type=StrategicMemoryType.OPEN_QUESTION,
            content="Which agent frameworks should Hephaestus compare against?",
            tags=["research", "open-question"],
        )
    )

    search = repository.search_memories("20k")
    recall = repository.recall(query="open source strategy", tags=["strategy"])
    repository.save_recall_event(recall)
    archived = repository.archive_memory(goal.id)

    assert search[0].id == goal.id
    assert recall.memory_ids == [goal.id]
    assert archived is not None
    assert archived.archived_at is not None
    assert goal.id not in [memory.id for memory in repository.search_memories("20k")]


def test_strategic_memory_conflict_detection(tmp_path) -> None:
    repository = StrategicMemoryRepository(tmp_path / "hephaestus.db")
    repository.save_memory(
        StrategicMemoryItem(
            type=StrategicMemoryType.ROADMAP_DECISION,
            content="Launch Hephaestus before command execution to learn positioning.",
            summary="Launch before command execution.",
            tags=["roadmap", "launch"],
        )
    )
    candidate = StrategicMemoryItem(
        type=StrategicMemoryType.ROADMAP_DECISION,
        content="Do not launch Hephaestus before command execution.",
        summary="Do not launch before command execution.",
        tags=["roadmap", "launch"],
    )

    conflicts = repository.detect_simple_conflicts(candidate)

    assert conflicts
    assert conflicts[0].severity >= 0.6
