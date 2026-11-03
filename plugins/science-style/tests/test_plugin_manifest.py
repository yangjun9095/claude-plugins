"""Tests for the plugin manifest and the marketplace entry."""
import json
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.dirname(HERE)
REPO = os.path.dirname(os.path.dirname(PLUGIN))


class ManifestTests(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(PLUGIN, ".claude-plugin", "plugin.json"), encoding="utf-8") as handle:
            self.plugin = json.load(handle)
        with open(os.path.join(REPO, ".claude-plugin", "marketplace.json"), encoding="utf-8") as handle:
            self.market = json.load(handle)

    def test_the_plugin_has_a_name_a_version_and_the_mit_license(self):
        self.assertEqual(self.plugin["name"], "science-style")
        self.assertEqual(self.plugin["license"], "MIT")
        self.assertRegex(self.plugin["version"], r"^\d+\.\d+\.\d+$")

    def test_the_marketplace_lists_the_plugin_with_the_same_version_and_description(self):
        entries = [p for p in self.market["plugins"] if p["name"] == "science-style"]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["source"], "./plugins/science-style")
        self.assertEqual(entries[0]["version"], self.plugin["version"])
        self.assertEqual(entries[0]["description"], self.plugin["description"])

    def test_the_license_file_is_mit(self):
        with open(os.path.join(PLUGIN, "LICENSE"), encoding="utf-8") as handle:
            self.assertTrue(handle.read().startswith("MIT License"))


if __name__ == "__main__":
    unittest.main()
