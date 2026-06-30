import unittest

from ttl_cache import TTLCache


class TTLCacheTests(unittest.TestCase):
    def test_set_and_get(self) -> None:
        cache = TTLCache[str, int](10)
        cache.set("answer", 42)
        self.assertEqual(cache.get("answer"), 42)

    def test_missing_uses_default(self) -> None:
        cache = TTLCache[str, int](10)
        self.assertEqual(cache.get("missing", 7), 7)


if __name__ == "__main__":
    unittest.main()
