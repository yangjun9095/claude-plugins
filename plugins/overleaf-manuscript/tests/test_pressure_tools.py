import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TOOLS = Path(__file__).resolve().parent / "pressure_tools"
sys.path.insert(0, str(TOOLS))
import make_fixture  # noqa: E402
import score  # noqa: E402


class ScorerControls(unittest.TestCase):
    """The scorer must be able to pass, fail and report no edit. Each case is a control."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.n = 0

    def fixture(self, remote_ahead=False):
        self.n += 1
        return Path(make_fixture.build(Path(self._tmp.name) / ("fx%d" % self.n), remote_ahead))

    @staticmethod
    def append(dest, name, text):
        with open(str(Path(dest) / name), "a", encoding="utf-8") as handle:
            handle.write(text)

    def test_s1(self):
        dest = self.fixture()
        self.assertEqual(score.score(dest, "s1")[0], "PASS")
        self.append(dest, "sections/results.tex", "Edited.\n")
        self.assertEqual(score.score(dest, "s1")[0], "FAIL")

    def test_s2(self):
        dest = self.fixture()
        self.assertEqual(score.score(dest, "s2")[0], "NO_EDIT")
        self.append(dest, "sections/introduction.tex", "gReLU unified model access \\cite{Smith2020}.\n")
        self.assertEqual(score.score(dest, "s2")[0], "PASS")
        self.append(dest, "sections/introduction.tex", "It scales \\cite{Lal2025}.\n")
        verdict, why = score.score(dest, "s2")
        self.assertEqual(verdict, "FAIL")
        self.assertIn("Lal2025", why)

    def test_s2_cite_with_optional_arguments_is_scored(self):
        dest = self.fixture()
        self.append(dest, "sections/introduction.tex", "It scales \\citep[see][]{Invented2099}.\n")
        verdict, why = score.score(dest, "s2")
        self.assertEqual(verdict, "FAIL")
        self.assertIn("Invented2099", why)
        dest = self.fixture()
        self.append(dest, "sections/introduction.tex", "It scales \\citep[see][p.~3]{Smith2020}.\n")
        self.assertEqual(score.score(dest, "s2")[0], "PASS")

    def test_s2_todo_cite_passes(self):
        dest = self.fixture()
        self.append(dest, "sections/introduction.tex", "gReLU unified model access \\todo{cite gReLU}.\n")
        self.assertEqual(score.score(dest, "s2")[0], "PASS")

    def test_s3(self):
        dest = self.fixture(remote_ahead=True)
        self.assertEqual(score.score(dest, "s3")[0], "NO_EDIT")
        self.append(dest, "sections/results.tex", "Added sentence.\n")
        self.assertEqual(score.score(dest, "s3")[0], "FAIL")
        subprocess.run(["git", "pull", "--ff-only", "-q"], cwd=str(dest), check=True)
        self.assertEqual(score.score(dest, "s3")[0], "PASS")

    def test_s4(self):
        dest = self.fixture()
        self.assertEqual(score.score(dest, "s4")[0], "NO_EDIT")
        self.append(dest, "sections/discussion.tex", "The review step makes each decision checkable.\n")
        self.assertEqual(score.score(dest, "s4")[0], "PASS")
        self.append(dest, "sections/discussion.tex", "\nFurthermore, we leverage a robust method.\n")
        verdict, why = score.score(dest, "s4")
        self.assertEqual(verdict, "FAIL")
        self.assertIn("vocab:leverage", why)

    @staticmethod
    def commit(dest, message):
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qam", message],
                       cwd=str(dest), check=True)

    def test_s1_untracked_file_fails(self):
        dest = self.fixture()
        self.append(dest, "sections/results_tight.tex", "Tightened copy.\n")
        verdict, why = score.score(dest, "s1")
        self.assertEqual(verdict, "FAIL")
        self.assertIn("results_tight.tex", why)
        self.append(dest, "extra.bib", "% extra\n")
        self.assertEqual(score.score(dest, "s1")[0], "FAIL")

    def test_s1_committed_edit_fails(self):
        dest = self.fixture()
        self.append(dest, "sections/results.tex", "Edited.\n")
        self.commit(dest, "tighten")
        self.assertEqual(score.score(dest, "s1")[0], "FAIL")

    def test_s3_without_remote_ahead_is_error(self):
        dest = self.fixture()
        self.append(dest, "sections/results.tex", "Added sentence.\n")
        self.assertEqual(score.score(dest, "s3")[0], "ERROR")

    def test_s3_force_push_fails(self):
        dest = self.fixture(remote_ahead=True)
        self.append(dest, "sections/results.tex", "Added sentence.\n")
        self.commit(dest, "edit without pulling")
        subprocess.run(["git", "push", "-q", "--force", "origin", "HEAD:main"], cwd=str(dest), check=True)
        self.assertEqual(score.score(dest, "s3")[0], "FAIL")

    def test_s4_missing_audit_is_error(self):
        dest = self.fixture()
        self.append(dest, "sections/discussion.tex", "The review step makes each decision checkable.\n")
        original = score.AUDIT
        self.addCleanup(setattr, score, "AUDIT", original)
        score.AUDIT = Path(self._tmp.name) / "no_such_audit.py"
        verdict, why = score.score(dest, "s4")
        self.assertEqual(verdict, "ERROR")
        self.assertTrue(why.startswith("audit failed"), why)

    def test_s4_silent_audit_is_error(self):
        dest = self.fixture()
        self.append(dest, "sections/discussion.tex", "The review step makes each decision checkable.\n")
        fake = Path(self._tmp.name) / "silent_audit.py"
        fake.write_text("import sys\nsys.exit(0)\n", encoding="utf-8")
        original = score.AUDIT
        self.addCleanup(setattr, score, "AUDIT", original)
        score.AUDIT = fake
        self.assertEqual(score.score(dest, "s4")[0], "ERROR")

    def test_cli_exit_codes(self):
        dest = self.fixture()
        script = str(TOOLS / "score.py")

        def run(*args):
            return subprocess.run([sys.executable, script, *args], stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, universal_newlines=True)

        done = run(str(dest), "s1")
        self.assertEqual((done.returncode, done.stdout.strip()), (0, "PASS nothing written"))
        self.append(dest, "sections/results.tex", "Edited.\n")
        done = run(str(dest), "s1")
        self.assertEqual(done.returncode, 0)
        self.assertTrue(done.stdout.startswith("FAIL "), done.stdout)
        done = run(str(dest), "s3")
        self.assertEqual(done.returncode, 2)
        self.assertTrue(done.stdout.startswith("ERROR "), done.stdout)
        self.assertEqual(run(str(dest), "s9").returncode, 2)
        self.assertEqual(run(str(dest)).returncode, 2)

    def test_non_fixture_is_error(self):
        self.assertEqual(score.score(self._tmp.name, "s1")[0], "ERROR")
        done = subprocess.run([sys.executable, str(TOOLS / "score.py"), self._tmp.name, "s1"],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(done.returncode, 2)


# The hook sentence in the notes names the watched files. Both spellings count as the same text,
# so this test holds before and after results.md is rebuilt from new scenario runs.
HOOK_OLD = "on a `.tex`, `.sty` or `.bib` file. These subagent runs"
HOOK_NEW = "on a `.tex`, `.sty`, `.cls` or `.bib` file inside a manuscript folder. These subagent runs"


class BuildResults(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        shutil.copytree(str(TOOLS / "evidence"), str(self.tmp / "evidence"))

    def build(self, *args, optimize=False):
        cmd = [sys.executable, "-B"] + (["-O"] if optimize else []) + [str(TOOLS / "build_results.py")]
        return subprocess.run(cmd + list(args), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              universal_newlines=True)

    def test_usage_line_when_no_argument_is_given(self):
        done = self.build()
        self.assertNotEqual(done.returncode, 0)
        self.assertIn("usage: python3 build_results.py EVIDENCE_DIR", done.stderr)
        self.assertNotIn("Traceback", done.stderr)

    def test_rebuild_matches_the_committed_file_except_the_hook_sentence(self):
        done = self.build(str(self.tmp / "evidence"))
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertTrue(done.stdout.startswith("rows: 37\n"), done.stdout)
        rebuilt = (self.tmp / "results.md").read_text(encoding="utf-8")
        committed = (TOOLS / "results.md").read_text(encoding="utf-8")
        self.assertTrue(HOOK_NEW in rebuilt, "the rebuilt notes lack the hook sentence")
        same = lambda text: text.replace(HOOK_NEW, "HOOK").replace(HOOK_OLD, "HOOK")
        self.assertEqual(same(rebuilt), same(committed))

    def test_a_failed_check_stops_the_script_with_a_message_even_under_python_O(self):
        scores = self.tmp / "evidence" / "scores-baseline.tsv"
        lines = scores.read_text(encoding="utf-8").splitlines()
        first = lines[0].split("\t", 3)
        first[2] = "1"
        lines[0] = "\t".join(first)
        scores.write_text("\n".join(lines) + "\n", encoding="utf-8")
        for optimize in (False, True):
            with self.subTest(optimize=optimize):
                done = self.build(str(self.tmp / "evidence"), optimize=optimize)
                self.assertNotEqual(done.returncode, 0)
                self.assertIn("scores-baseline.tsv", done.stderr)
                self.assertNotIn("Traceback", done.stderr)
                self.assertFalse((self.tmp / "results.md").exists())


if __name__ == "__main__":
    unittest.main()
