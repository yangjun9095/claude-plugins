import re
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
SKILL_DIR = PLUGIN / "skills" / "overleaf-manuscript"
TEXT = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")

# Rule text that belongs to manuscript-write. SKILL.md must point to it, not repeat it.
RESTATED = ("explicit approval in the current turn", "Never invent", "Prefer commenting out",
            "Pull before editing", "Never edit a shared style file")


def split(text):
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    front = dict(line.split(": ", 1) for line in match.group(1).splitlines())
    return front, match.group(2)


class SkillContract(unittest.TestCase):
    def setUp(self):
        self.front, self.body = split(TEXT)

    def test_frontmatter_names_the_skill(self):
        self.assertEqual(self.front["name"], "overleaf-manuscript")

    def test_description_gives_triggers_only(self):
        desc = self.front["description"]
        self.assertTrue(desc.startswith("Use when"))
        self.assertLessEqual(len(desc), 500)
        for word in ("preflight", "audit", "hook"):
            self.assertNotIn(word, desc.lower())

    def test_body_stays_under_300_words(self):
        self.assertLessEqual(len(self.body.split()), 300)

    def test_body_points_to_manuscript_write(self):
        self.assertIn("`manuscript-write`", self.body)

    def test_body_repeats_no_rule_from_manuscript_write(self):
        for phrase in RESTATED:
            self.assertNotIn(phrase.lower(), self.body.lower())

    def test_every_script_it_names_exists(self):
        names = re.findall(r"<base>/(scripts/[\w.]+)", self.body)
        self.assertEqual(sorted(names), ["scripts/audit.py", "scripts/preflight.sh"])
        for name in names:
            self.assertTrue((SKILL_DIR / name).is_file(), name)

    def test_body_says_to_stop_when_the_fast_forward_fails(self):
        self.assertIn("If `git pull --ff-only` fails, stop and ask.", self.body)


if __name__ == "__main__":
    unittest.main()
