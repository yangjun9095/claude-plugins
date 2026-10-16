import importlib.util
import re
import unittest
from pathlib import Path

PLUGIN = Path(__file__).resolve().parent.parent
SKILL_DIR = PLUGIN / "skills" / "overleaf-manuscript"
TEXT = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")

# Rule text that belongs to manuscript-write. SKILL.md must point to it and not repeat it.
# These five phrases guard against copying. They do not prove that no rule is restated in
# other words, and they break if manuscript-write changes its wording. The final review
# compared the SKILL.md body with the full text of manuscript-write by hand.
RESTATED =("explicit approval in the current turn", "Never invent", "Prefer commenting out",
            "Pull before editing", "Never edit a shared style file")


def watched_extensions():
    """Return the sorted extensions that the edit guard hook watches."""
    path = PLUGIN / "hooks" / "guard_tex_edit.py"
    spec = importlib.util.spec_from_file_location("guard_tex_edit", str(path))
    hook = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hook)
    return sorted(hook.WATCHED)


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

    def test_pull_command_names_the_manuscript_folder(self):
        self.assertIn("Run `git -C <manuscript-folder> pull --ff-only` only when", self.body)

    def test_base_is_the_directory_that_holds_this_file(self):
        self.assertIn("`<base>` below means the directory that contains this SKILL.md.", self.body)

    def test_body_lists_every_extension_the_hook_watches(self):
        for ext in watched_extensions():
            with self.subTest(ext=ext):
                self.assertIn("`%s`" % ext, self.body)

    def test_no_git_covers_any_folder_that_is_not_a_work_tree(self):
        row = [line for line in self.body.splitlines() if line.startswith("| `no-git`")][0]
        self.assertIn("not a git work tree", row)

    def test_body_follows_the_writing_standard_on_known_misses(self):
        for text in (", not ", "route around", "\u2014"):
            with self.subTest(text=text):
                self.assertNotIn(text, self.body)
        self.assertIn("A `todo-cite` row is an inventory entry and does not fail the audit.", self.body)
        self.assertIn("Do not bypass it with", self.body)


class ReadmeContract(unittest.TestCase):
    def setUp(self):
        self.text = (PLUGIN / "README.md").read_text(encoding="utf-8")

    def test_readme_names_every_mode_the_script_reports(self):
        for mode in ("overleaf-git", "github-linked", "no-git", "other"):
            with self.subTest(mode=mode):
                self.assertIn("`%s`" % mode, self.text)

    def test_readme_says_no_git_covers_any_folder_that_is_not_a_work_tree(self):
        self.assertIn("any folder that is not a git work tree", self.text)

    def test_readme_lists_every_extension_the_hook_watches(self):
        for ext in watched_extensions():
            with self.subTest(ext=ext):
                self.assertIn("`%s`" % ext, self.text)

    def test_readme_gives_the_hook_depth(self):
        self.assertIn("up to four levels above the file", self.text)


if __name__ == "__main__":
    unittest.main()
