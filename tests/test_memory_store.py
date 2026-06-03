from hephaestus.memory import InMemoryMemoryStore, MemoryItem, MemoryType


def test_memory_add_search_and_retrieve() -> None:
    store = InMemoryMemoryStore()
    store.add(
        MemoryItem(
            type=MemoryType.FAILURE,
            content="Validation failed because pytest was not installed.",
            summary="Missing pytest failure.",
            tags=["tests", "failure"],
            importance=0.8,
            confidence=0.9,
        )
    )
    store.add(
        MemoryItem(
            type=MemoryType.DECISION,
            content="Use fake models for deterministic tests.",
            summary="Fake model decision.",
            tags=["models", "tests"],
            importance=0.9,
            confidence=0.9,
        )
    )

    assert len(store.search("pytest", tags=["tests"])) == 1
    top = store.retrieve_top("fake models tests", limit=1)
    assert top[0].type == MemoryType.DECISION
