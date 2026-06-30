import tempfile
import unittest
from pathlib import Path

import tracker


class TrackerTests(unittest.TestCase):
    def test_add_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data = Path(directory) / "tasks.json"
            self.assertEqual(tracker.main(["--data", str(data), "add", "hello"]), 0)
            self.assertEqual(tracker.load(data)[0]["text"], "hello")


if __name__ == "__main__":
    unittest.main()
