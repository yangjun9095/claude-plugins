import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
HOOK = HERE.parent / "hooks" / "guard_tex_edit.py"


def run_hook(stdin_text):
    done = subprocess.run([sys.executable, str(HOOK)], input=stdin_text, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, universal_newlines=True)
    return done.returncode, done.stdout, done.stderr


def payload(tool, path, cwd=None):
    body = {"tool_name": tool, "tool_input": {"file_path": str(path)}}
    if cwd:
        body["cwd"] = str(cwd)
    return json.dumps(body)


def decision(stdout):
    return json.loads(stdout)["hookSpecificOutput"]


class GuardTexEdit(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "paper"
        (self.root / "sections").mkdir(parents=True)
        (self.root / "main.tex").write_text("\\documentclass{article}\n", encoding="utf-8")
        self.addCleanup(self._tmp.cleanup)

    def ask(self, tool, path, **kw):
        rc, out, _ = run_hook(payload(tool, path, **kw))
        self.assertEqual(rc, 0)
        self.assertTrue(out, "expected a decision for %s" % path)
        d = decision(out)
        self.assertEqual(d["hookEventName"], "PreToolUse")
        self.assertEqual(d["permissionDecision"], "ask")
        return d["permissionDecisionReason"]

    def silent(self, stdin_text):
        rc, out, _ = run_hook(stdin_text)
        self.assertEqual((rc, out), (0, ""))

    def test_section_file_cites_rule_1(self):
        self.assertIn("Rule 1", self.ask("Edit", self.root / "sections" / "results.tex"))

    def test_main_tex_cites_rule_4(self):
        self.assertIn("Rule 4", self.ask("Write", self.root / "main.tex"))

    def test_style_file_cites_rule_3(self):
        self.assertIn("Rule 3", self.ask("MultiEdit", self.root / "royer_style.sty"))

    def test_bibliography_cites_rule_2(self):
        self.assertIn("Rule 2", self.ask("Edit", self.root / "paperpile.bib"))

    def test_new_main_tex_is_in_scope(self):
        fresh = Path(self._tmp.name) / "fresh" / "main.tex"
        self.assertIn("Rule 4", self.ask("Write", fresh))

    def test_relative_path_uses_cwd(self):
        self.assertIn("Rule 1", self.ask("Edit", "sections/results.tex", cwd=self.root))

    def test_four_levels_below_main_tex_is_in_scope(self):
        deep = self.root / "a" / "b" / "c" / "d.tex"
        self.assertIn("Rule 1", self.ask("Edit", deep))

    def test_five_levels_below_main_tex_is_silent(self):
        self.silent(payload("Edit", self.root / "a" / "b" / "c" / "d" / "e.tex"))

    def test_tex_file_without_main_tex_is_silent(self):
        elsewhere = Path(self._tmp.name) / "notes" / "scratch.tex"
        elsewhere.parent.mkdir()
        self.silent(payload("Edit", elsewhere))

    def test_other_extensions_are_silent(self):
        self.silent(payload("Edit", self.root / "figures.py"))
        self.silent(payload("Edit", self.root / "README.md"))

    def test_other_tools_are_silent(self):
        self.silent(payload("Read", self.root / "sections" / "results.tex"))
        self.silent(payload("Bash", self.root / "sections" / "results.tex"))

    def test_bad_input_fails_open(self):
        rc, out, err = run_hook("not json")
        self.assertEqual((rc, out), (0, ""))
        self.assertIn("ignored error", err)
        self.silent("{}")


if __name__ == "__main__":
    unittest.main()
