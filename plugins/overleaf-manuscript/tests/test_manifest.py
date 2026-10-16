import json
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
REPO = PLUGIN.parent.parent
NAME = "overleaf-manuscript"


class Manifest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        text = (PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8")
        cls.plugin = json.loads(text)

    def test_name_and_author_follow_contributing_md(self):
        self.assertEqual(self.plugin["name"], NAME)
        self.assertIsInstance(self.plugin["author"], dict)
        self.assertNotIn("commands", self.plugin)

    def test_marketplace_entry_matches_the_manifest(self):
        market = json.loads((REPO / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
        entries = [p for p in market["plugins"] if p["name"] == NAME]
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["source"], "./plugins/" + NAME)
        self.assertEqual(entries[0]["version"], self.plugin["version"])

    def test_hook_command_points_at_an_existing_script(self):
        hooks = json.loads((PLUGIN / "hooks" / "hooks.json").read_text(encoding="utf-8"))
        groups = hooks["hooks"]["PreToolUse"]
        self.assertEqual(groups[0]["matcher"], "Edit|Write|MultiEdit")
        commands = [h["command"] for group in groups for h in group["hooks"]]
        self.assertEqual(len(commands), 1)
        script = commands[0].split("${CLAUDE_PLUGIN_ROOT}/")[1].rstrip('"')
        self.assertTrue((PLUGIN / script).is_file(), script)

    def test_skills_path_exists(self):
        self.assertTrue((PLUGIN / self.plugin["skills"]).is_dir())


if __name__ == "__main__":
    unittest.main()
