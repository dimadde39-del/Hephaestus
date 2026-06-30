import unittest

from config import Config, parse_config


class ConfigTests(unittest.TestCase):
    def test_defaults(self) -> None:
        self.assertEqual(parse_config({}, {}), Config())

    def test_values(self) -> None:
        self.assertEqual(
            parse_config({"debug": "true", "port": "9000", "mode": "prod"}, {}),
            Config(debug=True, port=9000, mode="prod"),
        )


if __name__ == "__main__":
    unittest.main()
