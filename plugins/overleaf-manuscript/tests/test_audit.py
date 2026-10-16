import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
AUDIT = HERE.parent / "skills" / "overleaf-manuscript" / "scripts" / "audit.py"
FIX = HERE / "fixtures"


def run(*args):
    done = subprocess.run([sys.executable, str(AUDIT), *args], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, universal_newlines=True)
    return done.returncode, done.stdout


def run_full(*args, env=None):
    done = subprocess.run([sys.executable, str(AUDIT), *args], stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, universal_newlines=True, env=env)
    return done.returncode, done.stdout, done.stderr


def rows(stdout):
    """Return a list of (line, rule) for each hit row. Count and summary lines are skipped."""
    out = []
    for text in stdout.splitlines():
        head, _, rest = text.partition(": ")
        match = re.match(r"^.+:(\d+)$", head)
        if match and rest:
            out.append((int(match.group(1)), rest.split(": ", 1)[0]))
    return out


def audit_text(text, *flags):
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "doc.tex"
        path.write_text(text, encoding="utf-8")
        return run(*flags, str(path))


def audit_with_terms(terms):
    """Run the script with a terms file built from the given object. Return (rc, stdout, stderr)."""
    with tempfile.TemporaryDirectory() as tmp:
        terms_path = Path(tmp) / "terms.json"
        terms_path.write_text(json.dumps(terms), encoding="utf-8")
        doc = Path(tmp) / "doc.tex"
        doc.write_text("Plain text.\n", encoding="utf-8")
        return run_full("--terms", str(terms_path), str(doc))


class PositiveAndNegativeControls(unittest.TestCase):
    def test_every_rule_fires_at_the_right_line(self):
        rc, out = run("--spelling", "oxford", str(FIX / "positive.tex"))
        expected = {
            (1, "emdash:density"),
            (3, "construction:paragraph-initial"), (3, "emdash:paragraph"),
            (3, "vocab:pivotal"), (3, "vocab:robust"),
            (5, "construction:it is worth noting"), (5, "fig-ref"), (5, "spelling:-or/-er form"),
            (7, "construction:not only ... but also"), (7, "construction:plays a key role in"),
            (7, "spelling:-ise form"), (7, "todo-cite"),
        }
        self.assertEqual(set(rows(out)), expected)
        self.assertEqual(rc, 1)

    def test_clean_fixture_has_no_hits(self):
        rc, out = run("--spelling", "oxford", str(FIX / "clean.tex"))
        self.assertEqual(rows(out), [])
        self.assertEqual(rc, 0)
        self.assertIn("no hits", out)

    def test_commented_out_text_is_ignored(self):
        text = (FIX / "positive.tex").read_text(encoding="utf-8")
        commented = "\n".join("% " + line for line in text.splitlines()) + "\n"
        rc, out = audit_text(commented, "--spelling", "oxford")
        self.assertEqual((rc, rows(out)), (0, []))

    def test_comment_environment_is_ignored(self):
        text = "\\begin{comment}\nThis is pivotal and robust.\n\\end{comment}\nPlain text.\n"
        rc, out = audit_text(text)
        self.assertEqual((rc, rows(out)), (0, []))


class Spelling(unittest.TestCase):
    def test_spelling_is_off_by_default(self):
        _, out = run(str(FIX / "positive.tex"))
        self.assertEqual([r for _, r in rows(out) if r.startswith("spelling")], [])

    def test_american_mode_flags_british_forms(self):
        _, out = audit_text("The colour and the centre differ.\n", "--spelling", "american")
        self.assertEqual({r for _, r in rows(out)}, {"spelling:-our/-re form"})

    def test_oxford_keeps_analyse_and_organize(self):
        rc, out = audit_text("We analyse and organize the data.\n", "--spelling", "oxford")
        self.assertEqual((rc, rows(out)), (0, []))


class ExitCode(unittest.TestCase):
    def test_todo_cite_alone_exits_zero(self):
        rc, out = audit_text("Add the source \\todo{cite foo} here.\n")
        self.assertEqual(rows(out), [(1, "todo-cite")])
        self.assertEqual(rc, 0)

    def test_missing_file_exits_two(self):
        rc, _ = run("/no/such/file.tex")
        self.assertEqual(rc, 2)


class EmDashDensity(unittest.TestCase):
    @staticmethod
    def doc(n_dashed, n_plain):
        dashed = " ".join(["word"] * 199) + " a---b"
        plain = " ".join(["word"] * 201)
        return "\n\n".join([dashed] * n_dashed + [plain] * n_plain) + "\n"

    def test_two_dashes_in_about_800_words_pass(self):
        _, out = audit_text(self.doc(2, 2))
        self.assertEqual(rows(out), [])

    def test_three_dashes_in_about_800_words_fail(self):
        _, out = audit_text(self.doc(3, 1))
        self.assertEqual([r for _, r in rows(out)], ["emdash:density"])


class HarnessRule(unittest.TestCase):
    def hits(self, sentence):
        return [r for _, r in rows(audit_text(sentence + "\n")[1])]

    def test_verb_forms_are_flagged(self):
        for sentence in ("We harness the signal.", "Harnessing the atlas helps.",
                         "It harnesses priors.", "A method that harnesses priors."):
            self.assertEqual(self.hits(sentence), ["vocab:harness"], sentence)

    def test_noun_forms_are_allowed(self):
        for sentence in ("The test harness fixes defaults.", "Each harness was tuned.",
                         "The test harnesses differ."):
            self.assertEqual(self.hits(sentence), [], sentence)


class InputShapes(unittest.TestCase):
    def test_escaped_percent_is_not_a_comment(self):
        _, out = audit_text("Half of 50\\% of cells is pivotal.\n")
        self.assertEqual(rows(out), [(1, "vocab:pivotal")])

    def test_crlf_gives_the_same_rows_as_lf(self):
        text = (FIX / "positive.tex").read_text(encoding="utf-8")
        lf = rows(audit_text(text, "--spelling", "oxford")[1])
        crlf = rows(audit_text(text.replace("\n", "\r\n"), "--spelling", "oxford")[1])
        self.assertEqual(lf, crlf)

    def test_byte_order_mark_does_not_hide_the_first_paragraph(self):
        _, out = audit_text("\ufeffFurthermore, we begin.\n")
        self.assertEqual(rows(out), [(1, "construction:paragraph-initial")])


class RepeatedHits(unittest.TestCase):
    def test_every_occurrence_gets_a_row(self):
        rc, out = audit_text("The model is robust, and the loss is robust, and the prior is robust.\n")
        self.assertEqual(rows(out), [(1, "vocab:robust")] * 3)
        self.assertIn("vocab: 3", out.splitlines())
        self.assertEqual(rc, 1)


class ErrorExits(unittest.TestCase):
    def test_non_ascii_row_under_c_locale_does_not_crash(self):
        env = dict(os.environ)
        env["LC_ALL"] = "C"
        env.pop("PYTHONIOENCODING", None)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "doc.tex"
            path.write_text("not only caf\u00e9 designs but also\n", encoding="utf-8")
            rc, out, err = run_full(str(path), env=env)
        self.assertEqual(rc, 1, err)
        self.assertIn("construction:not only ... but also", out)
        self.assertNotIn("Traceback", err)

    def test_terms_file_missing_a_key_exits_two(self):
        rc, _, err = audit_with_terms({"vocabulary": []})
        self.assertEqual(rc, 2, err)
        self.assertIn("bad terms file", err)
        self.assertNotIn("Traceback", err)

    def test_terms_file_with_bad_pattern_exits_two(self):
        terms = {"vocabulary": [{"term": "bad", "pattern": "(unclosed"}],
                 "constructions": [], "paragraph_initial": [],
                 "spelling": {"oxford": [], "american": []}}
        rc, _, err = audit_with_terms(terms)
        self.assertEqual(rc, 2, err)
        self.assertIn("bad terms file", err)
        self.assertNotIn("Traceback", err)


TERMS = json.loads((AUDIT.parent.parent / "audit_terms.json").read_text(encoding="utf-8"))
NEW_ISE_STEMS = ("parameteris", "tokenis", "vectoris", "regularis", "hybridis", "discretis",
                 "localis", "stabilis", "quantis", "binaris", "centralis", "digitis",
                 "mobilis", "sensitis", "polaris", "immunis")


def ise_rows(word, spelling="oxford"):
    """Audit a made-up sentence that holds one word. Return (rc, rows)."""
    rc, out = audit_text("We use the %s here.\n" % word, "--spelling", spelling)
    return rc, rows(out)


class PilotGaps(unittest.TestCase):
    """Gaps the pilot audit exposed. Every sentence is made up."""

    def test_untied_ref_with_no_space_is_flagged(self):
        rc, out = audit_text("See Fig.\\ref{fig:a} for details.\n")
        self.assertEqual((rc, rows(out)), (1, [(1, "fig-ref")]))

    def test_untied_ref_after_a_tied_prefix_is_flagged(self):
        rc, out = audit_text("See Supp.~Fig.\\ref{fig:a}b for details.\n")
        self.assertEqual((rc, rows(out)), (1, [(1, "fig-ref")]))

    def test_plural_and_cleveref_forms_with_no_space_are_flagged(self):
        rc, out = audit_text("See Figs.\\ref{fig:a} and Fig.\\cref{fig:b}.\n")
        self.assertEqual((rc, rows(out)), (1, [(1, "fig-ref"), (1, "fig-ref")]))

    def test_ref_after_a_space_is_still_flagged(self):
        rc, out = audit_text("See Fig. \\ref{fig:a} for details.\n")
        self.assertEqual((rc, rows(out)), (1, [(1, "fig-ref")]))

    def test_tied_refs_pass(self):
        rc, out = audit_text("See Fig.~\\ref{fig:a} and Figs.~\\ref{fig:a}.\n")
        self.assertEqual((rc, rows(out)), (0, []))

    def test_figure_without_a_ref_command_passes(self):
        rc, out = audit_text("See Fig.~3 and Fig. 4 for details.\n")
        self.assertEqual((rc, rows(out)), (0, []))

    def test_ref_on_the_next_line_is_flagged_at_the_fig_line(self):
        rc, out = audit_text("Intro line.\nSee Fig.\n\\ref{fig:a} for details.\n")
        self.assertEqual((rc, rows(out)), (1, [(2, "fig-ref")]))

    def test_oxford_flags_er_nouns_and_more_stems(self):
        for word in ("tokeniser", "Parameterisation", "optimiser", "optimisers",
                     "normalisation", "synthesised"):
            with self.subTest(word=word):
                self.assertEqual(ise_rows(word), (1, [(1, "spelling:-ise form")]))

    def test_oxford_flags_every_new_stem(self):
        for stem in NEW_ISE_STEMS:
            for suffix in ("e", "ed", "er", "ation"):
                with self.subTest(word=stem + suffix):
                    self.assertEqual(ise_rows(stem + suffix), (1, [(1, "spelling:-ise form")]))

    def test_oxford_flags_every_form_of_the_verb_synthesise(self):
        for word in ("synthesise", "synthesises", "synthesised", "synthesising",
                     "synthesiser", "synthesisers"):
            with self.subTest(word=word):
                self.assertEqual(ise_rows(word), (1, [(1, "spelling:-ise form")]))

    def test_oxford_leaves_ize_forms_and_ordinary_words_alone(self):
        for word in ("optimizer", "organizer", "synthesis", "syntheses", "advise",
                     "exercise", "promise", "analyse", "tokenizer", "synthesized"):
            with self.subTest(word=word):
                self.assertEqual(ise_rows(word), (0, []))

    def test_american_still_flags_british_ise_forms_and_keeps_ize_forms(self):
        rc, out = audit_text("The tokeniser and the optimiser differ.\n", "--spelling", "american")
        self.assertEqual((rc, rows(out)), (1, [(1, "spelling:-ise form")] * 2))
        rc, out = audit_text("The tokenizer and the optimizer and synthesized text.\n",
                             "--spelling", "american")
        self.assertEqual((rc, rows(out)), (0, []))

    def test_ise_pattern_is_identical_in_both_spelling_lists(self):
        def pattern(mode):
            return [e["pattern"] for e in TERMS["spelling"][mode] if e["term"] == "-ise form"]
        self.assertEqual(len(pattern("oxford")), 1)
        self.assertEqual(pattern("oxford"), pattern("american"))


if __name__ == "__main__":
    unittest.main()
