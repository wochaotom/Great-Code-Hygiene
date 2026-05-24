import unittest

from app.config import load_config


class ConfigTests(unittest.TestCase):
    def test_defaults_are_used_without_overrides(self):
        self.assertEqual(load_config()["timeout"], 30)

    def test_file_config_can_override_defaults(self):
        self.assertEqual(load_config({"timeout": 12})["timeout"], 12)

    def test_environment_overrides_file_config(self):
        config = load_config({"timeout": 12}, {"APP_TIMEOUT": "5"})
        self.assertEqual(config["timeout"], 5)

    def test_environment_overrides_file_endpoint(self):
        config = load_config(
            {"endpoint": "http://file.example"},
            {"APP_ENDPOINT": "https://env.example"},
        )
        self.assertEqual(config["endpoint"], "https://env.example")


if __name__ == "__main__":
    unittest.main()
