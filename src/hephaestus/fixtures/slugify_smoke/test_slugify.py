"""Existing tests for the disposable slugify fixture."""

import unittest

from slugify import slugify  # type: ignore[import-not-found]


class SlugifyTests(unittest.TestCase):
    def test_lowercases_words(self) -> None:
        self.assertEqual(slugify("Hello World"), "hello-world")

    def test_trims_one_edge_separator(self) -> None:
        self.assertEqual(slugify(" Hello "), "hello")


if __name__ == "__main__":
    unittest.main()
