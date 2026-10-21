import hashlib
import json
import re
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
REPO = PLUGIN.parent.parent
NAME = "generate-slides-minimal"
NOTES = PLUGIN / "references" / "research-notes"

# SHA-256 of each research report as it was copied on 2026-10-20.
REPORT_SHA256 = {
    "jobs.md": "3bb6d1286e47c9ac2ad3267b963eab77eb3211a1061533bfe93fc1998a9509fc",
    "craft.md": "3941564108b9f9d157b288db0bf8caac5e1401bb52a6a9aa026c61a6abb2f72d",
    "science.md": "d0c1403b080339622e9f95c4a37f259f2a26686f2f9d82970888463df765ba80",
    "measurable.md": "a1da1bcd8d4ef38b8418501b2ed75c32f0b72d7c01e249e419acdccd09f50aad",
}

URL = re.compile(r"https?://[^\s)>\]\"|,]+")


class Manifest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        text = (PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        cls.plugin = json.loads(text)

    def test_plugin_json_fields(self):
        self.assertEqual(self.plugin["name"], NAME)
        self.assertEqual(self.plugin["name"], PLUGIN.name)
        self.assertEqual(self.plugin["version"], "0.1.0")
        self.assertTrue(self.plugin["description"].strip())
        self.assertLessEqual(len(self.plugin["description"]), 400)
        self.assertEqual(self.plugin["license"], "MIT")
        self.assertIsInstance(self.plugin["author"], dict)
        self.assertNotIn("commands", self.plugin)

    def test_marketplace_entry_matches_the_manifest(self):
        text = (REPO / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8")
        market = json.loads(text)
        entries = [p for p in market["plugins"] if p["name"] == NAME]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["source"], "./plugins/" + NAME)
        self.assertTrue((REPO / entries[0]["source"]).is_dir())
        self.assertEqual(entries[0]["version"], self.plugin["version"])


class ResearchNotes(unittest.TestCase):
    def test_reports_exist_and_hold_at_least_ten_urls(self):
        for name in REPORT_SHA256:
            with self.subTest(report=name):
                path = NOTES / name
                self.assertTrue(path.is_file(), name)
                text = path.read_text(encoding="utf-8")
                self.assertTrue(text.strip())
                self.assertGreaterEqual(len(set(URL.findall(text))), 10)

    def test_reports_are_byte_identical_to_the_originals(self):
        for name, expected in REPORT_SHA256.items():
            with self.subTest(report=name):
                digest = hashlib.sha256((NOTES / name).read_bytes()).hexdigest()
                self.assertEqual(digest, expected)

    def test_readme_names_the_reports_the_date_and_the_t1_difference(self):
        path = NOTES / "README.md"
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        self.assertTrue(text.strip())
        for name in REPORT_SHA256:
            self.assertIn(name, text)
        self.assertIn("2026-10-20", text)
        t1_lines = [line for line in text.splitlines() if "T1" in line]
        self.assertTrue(t1_lines, "the README must explain T1")
        t1_text = " ".join(t1_lines)
        self.assertIn("jobs.md", t1_text)
        self.assertIn("transcript", t1_text)
        self.assertIn("controlled study", t1_text)
        self.assertIn("standard", t1_text)


if __name__ == "__main__":
    unittest.main()
