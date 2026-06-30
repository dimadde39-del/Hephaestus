"""A tiny cache with intentionally incomplete TTL handling."""

from __future__ import annotations

import time
from collections.abc import Callable


class TTLCache[K, V]:
    def __init__(self, ttl: float, clock: Callable[[], float] = time.monotonic) -> None:
        self.ttl = ttl
        self.clock = clock
        self._items: dict[K, tuple[V, float]] = {}

    def set(self, key: K, value: V) -> None:
        self._items[key] = (value, self.clock() + self.ttl)

    def get(self, key: K, default: V | None = None) -> V | None:
        item = self._items.get(key)
        return default if item is None else item[0]

    def __contains__(self, key: object) -> bool:
        return key in self._items

    def __len__(self) -> int:
        return len(self._items)
