"""Tests for scripts/prose_verify.py. All text in this file is made up.

The tests check these facts.

Guards. Each of the ten guards has a passing and a failing proposal. A guard that reads the masked
text has a case that fails only when masking is on. The failed guards come in guard order, and every
guard runs after one fails.

Seeded cases. A dropped hedge, a moved and a dropped citation, a changed number and a new gene name.
A contrast pattern, a long rewrite and an empty rewrite. Two overlapping proposals, a repeated
`before` and a file that changed after the detect step.

Files. LaTeX, Markdown and plain text, CRLF text, a byte order mark, and the offsets that
`prose_lint.py --windows` prints. A file name that is not UTF-8.

Command line. The text output, the JSON output, the exit codes 0, 1 and 2, every data error, and
the two shapes of the proposals file. The `--format` option.

Numbers. The `numbers` guard also compares relation signs, quantifier phrases and number words.
The `no-new-names` guard leaves a number to the `numbers` guard.

Warnings. A closed list of common sentence starts gives no warning.
"""
import ast
import contextlib
import io
import json
import os
import re
import subprocess
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import lint_helpers as h  # noqa: E402
import prose_patterns as pp  # noqa: E402
import prose_verify as pv  # noqa: E402
from lint_helpers import FILLER, PATTERNS, Folder, patched  # noqa: E402
from prose_text import word_count  # noqa: E402

SCRIPT = os.path.join(h.SCRIPTS_DIR, "prose_verify.py")
GUARD_ORDER = ["exact-before", "masked-spans", "numbers", "no-flag", "sentence-length", "no-new-names",
               "not-longer", "no-empty", "no-overlap", "hedge-kept"]

S_HEDGE = "These data may suggest that growth slows in the mutant line \\cite{lee2020}."
S_NUMBERS = "The treated group received 5 mg of the compound and lost 12.5\\% of its mass."
S_CONTRAST = "The effect was not just large but also steady across the plates."
S_STACK = "The data may possibly suggest a link between heat and growth."
S_PUFF = "The study plays a pivotal role in the field."
S_SHORT = "The line grew slowly."
S_EFFECT = "The effect was large and also steady across the plates in every run."
TEX = ("\\section{Results}\n" + " ".join([S_HEDGE, S_NUMBERS, S_CONTRAST]) +
       "\n\nWe then grew the cells in fresh medium for two days.\n")

NEUTRAL = "grey stone path river bridge lamp field gate wall hill road cart".split()
# Plain text with no sentence that any family flags. Offsets of the six sentences in `PLAIN`.
PLAIN = " ".join(FILLER[:6])


def plain(count):
    """Return one neutral sentence of exactly `count` words."""
    return " ".join(NEUTRAL[i % len(NEUTRAL)] for i in range(count)).capitalize() + "."


def plain_run(count):
    """Return neutral sentences of 30 words or fewer, each with another first word, for `count` words."""
    sentences, k = [], 0
    while count > 0:
        size = min(30, count)
        sentences.append(" ".join(NEUTRAL[(k + i) % len(NEUTRAL)] for i in range(size)).capitalize() + ".")
        count, k = count - size, k + 1
    return " ".join(sentences)


def profile(p90):
    """Return a valid voice profile whose 90th percentile of the sentence length is `p90`."""
    return {"version": 1, "samples": 1, "words": 300, "sentences": 30,
            "sentence_length": {"mean": 12.0, "p10": 5, "p50": 11, "p90": p90}, "we_share": 0.1,
            "hedge_rate": 10.0, "passive_rate": 5.0, "em_dash_per_1000": 0.0, "semicolon_per_1000": 0.0,
            "avg_word_length": 4.5, "top_openers": [["the", 5]]}


def reader(files):
    """Return a `read` function over a dict of file texts."""
    def read(path):
        if path not in files:
            raise OSError(2, "No such file or directory", path)
        return files[path]
    return read


def sentence_bounds():
    """Return the (start, end) offsets of the six sentences of `PLAIN`."""
    found, pos = [], 0
    for sentence in FILLER[:6]:
        start = PLAIN.index(sentence, pos)
        found.append((start, start + len(sentence)))
        pos = start + len(sentence)
    return found


def prop(text, before, after, name="paper.tex", **fields):
    """Return a proposal for the first occurrence of `before` in `text`."""
    start = text.index(before)
    item = {"id": "p1", "file": name, "start": start, "end": start + len(before), "before": before,
            "after": after, "families": [], "reason": "made-up reason"}
    item.update(fields)
    return item


def span(text, start, end, name="paper.txt", **fields):
    """Return a proposal for `text[start:end]` that keeps the text as it is."""
    item = {"id": "p%d" % start, "file": name, "start": start, "end": end, "before": text[start:end],
            "after": text[start:end], "families": [], "reason": "made-up reason"}
    item.update(fields)
    return item


def check(text, before, after, name="paper.tex", profile=None, patterns=None, **fields):
    """Run the guards on one proposal and return its Result."""
    item = prop(text, before, after, name, **fields)
    return pv.check_proposals([item], patterns or PATTERNS, profile, reader({name: text}))[0]


def solo(before, after, name="paper.txt", **fields):
    """Run the guards on a file that holds `before` and nothing else."""
    return check(before, before, after, name, **fields)


def run(args, project=None):
    """Run the command line in this process. Return (exit code, stdout text, stderr text).

    The texts hold what argparse writes to the real streams, such as a usage message.
    """
    args = list(args)
    out, err = io.BytesIO(), io.BytesIO()
    shown_out, shown_err = io.StringIO(), io.StringIO()
    with Folder() as empty, contextlib.redirect_stdout(shown_out), contextlib.redirect_stderr(shown_err):
        if "--project-dir" not in args:
            args += ["--project-dir", project or empty.root]
        code = pv.main(args, out, err)
    return (code, out.getvalue().decode("utf-8") + shown_out.getvalue(),
            err.getvalue().decode("utf-8", "surrogateescape") + shown_err.getvalue())


def run_script(args, env=None):
    """Run `python3 prose_verify.py` in a child process. Return (exit code, stdout bytes, stderr bytes)."""
    env = dict(env or os.environ)
    env["LC_ALL"] = env.get("LC_ALL", "C")
    env.pop("PYTHONIOENCODING", None)
    with Folder() as empty:
        args = list(args)
        if "--project-dir" not in args:
            args += ["--project-dir", empty.root]
        proc = subprocess.run([sys.executable, "-B", SCRIPT] + args, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, env=env)
    return proc.returncode, proc.stdout, proc.stderr


class GuardCase(unittest.TestCase):
    def assertFails(self, result, *guards):
        self.assertEqual(result.failed, list(guards), result.detail)
        self.assertEqual(sorted(result.detail), sorted(guards))
        self.assertFalse(result.ok)

    def assertPasses(self, result):
        self.assertEqual((result.ok, result.failed, result.detail), (True, [], {}), result.detail)


class ExactBeforeTests(GuardCase):
    def test_the_text_at_the_span_passes(self):
        self.assertPasses(check(TEX, S_NUMBERS, S_NUMBERS))

    def test_a_shifted_span_fails(self):
        item = prop(TEX, S_NUMBERS, S_NUMBERS)
        item["start"] += 1
        item["end"] += 1
        result = pv.check_proposals([item], PATTERNS, None, reader({"paper.tex": TEX}))[0]
        self.assertFails(result, "exact-before")
        self.assertEqual(result.detail["exact-before"], "the file text at %d:%d differs from before" % (
            item["start"], item["end"]))

    def test_a_before_that_occurs_twice_fails(self):
        text = FILLER[0] + " " + FILLER[1] + " " + FILLER[0] + "\n"
        result = check(text, FILLER[0], FILLER[0])
        self.assertFails(result, "exact-before")
        self.assertEqual(result.detail["exact-before"], "before occurs 2 times in the file")

    def test_a_before_that_occurs_once_passes(self):
        text = FILLER[0] + " " + FILLER[1] + "\n"
        self.assertPasses(check(text, FILLER[0], FILLER[0]))

    def test_a_file_that_changed_after_the_detect_step_fails(self):
        item = prop(TEX, S_NUMBERS, S_NUMBERS)
        changed = TEX.replace("Results", "Findings and results")
        result = pv.check_proposals([item], PATTERNS, None, reader({"paper.tex": changed}))[0]
        self.assertFails(result, "exact-before")

    def test_a_file_that_changed_after_the_span_fails_when_before_is_gone(self):
        item = prop(TEX, S_NUMBERS, S_NUMBERS)
        changed = TEX.replace("12.5", "13.5")
        result = pv.check_proposals([item], PATTERNS, None, reader({"paper.tex": changed}))[0]
        self.assertFails(result, "exact-before")

    def test_a_before_that_differs_by_white_space_fails(self):
        for before in (S_NUMBERS + " ", " " + S_NUMBERS, S_NUMBERS.replace(" of the", "  of the")):
            with self.subTest(before=before):
                item = prop(TEX, S_NUMBERS, S_NUMBERS)
                item["before"] = before
                result = pv.check_proposals([item], PATTERNS, None, reader({"paper.tex": TEX}))[0]
                self.assertIn("exact-before", result.failed)

    def test_an_empty_before_fails(self):
        item = prop(TEX, S_NUMBERS, "x")
        item.update(before="", start=5, end=5)
        result = pv.check_proposals([item], PATTERNS, None, reader({"paper.tex": TEX}))[0]
        self.assertIn("exact-before", result.failed)
        self.assertEqual(result.detail["exact-before"], "before is empty")

    def test_an_empty_before_in_an_empty_file_fails(self):
        item = prop(TEX, S_NUMBERS, "x")
        item.update(before="", start=0, end=0)
        result = pv.check_proposals([item], PATTERNS, None, reader({"paper.tex": ""}))[0]
        self.assertIn("exact-before", result.failed)

    def test_crlf_text_keeps_its_offsets(self):
        text = "\\section{Results}\r\nThe line grew slowly in heat\r\nand stopped after two days.\r\n"
        before = "The line grew slowly in heat\r\nand stopped after two days."
        self.assertPasses(check(text, before, "The line grew slowly in heat and stopped after two days."))
        lf = prop(text, before, "The line grew slowly in heat and stopped after two days.")
        lf["before"] = before.replace("\r\n", "\n")
        result = pv.check_proposals([lf], PATTERNS, None, reader({"paper.tex": text}))[0]
        self.assertIn("exact-before", result.failed)

    def test_a_byte_order_mark_counts_as_one_character(self):
        text = "\ufeff" + PLAIN
        item = span(text, 1, len(FILLER[0]) + 1)
        self.assertEqual(item["before"], FILLER[0])
        result = pv.check_proposals([item], PATTERNS, None, reader({"paper.txt": text}))[0]
        self.assertPasses(result)


class MaskedSpanTests(GuardCase):
    def test_a_moved_citation_passes(self):
        before = "These data may suggest slower growth in the mutant line \\cite{lee2020} after heat."
        after = "These data \\cite{lee2020} may suggest slower growth in the mutant line after heat."
        self.assertPasses(solo(before, after, "paper.tex"))

    def test_a_dropped_citation_fails_only_this_guard(self):
        result = solo(S_HEDGE, "These data may suggest that growth slows in the mutant line.", "paper.tex")
        self.assertFails(result, "masked-spans")
        self.assertEqual(result.detail["masked-spans"], 'after lacks "\\cite{lee2020}"')

    def test_a_new_citation_fails_only_this_guard(self):
        before = "The mutant line grows slowly under heat."
        result = solo(before, before + " \\cite{aa}\\cite{bb}\\cite{cc}", "paper.tex")
        self.assertFails(result, "masked-spans")
        self.assertEqual(result.detail["masked-spans"], 'after adds "\\cite{aa}", "\\cite{bb}", "\\cite{cc}"')

    def test_a_changed_citation_key_fails(self):
        result = solo(S_HEDGE, S_HEDGE.replace("lee2020", "lee2021"), "paper.tex")
        self.assertFails(result, "masked-spans")
        self.assertEqual(result.detail["masked-spans"], 'after lacks "\\cite{lee2020}" and adds "\\cite{lee2021}"')

    def test_a_duplicated_citation_fails(self):
        result = solo(S_HEDGE, S_HEDGE + " \\cite{lee2020}", "paper.tex")
        self.assertIn("masked-spans", result.failed)

    def test_a_citation_key_with_a_hedge_word_or_a_number_is_hidden_from_other_guards(self):
        before = "Growth slows \\cite{may2020}."
        self.assertFails(solo(before, "Growth slows.", "paper.tex"), "masked-spans")

    def test_a_dropped_command_fails(self):
        before = "The mutant line grows \\emph{slowly} under heat."
        self.assertFails(solo(before, "The mutant line grows slowly under heat.", "paper.tex"), "masked-spans")

    def test_math_and_labels_count_as_spans(self):
        before = "The slope is $k = 0.4$ in the mutant line \\label{sec:slope}."
        self.assertPasses(solo(before, "In the mutant line the slope is $k = 0.4$ \\label{sec:slope}.", "paper.tex"))
        self.assertFails(solo(before, "The slope is $k = 0.4$ in the mutant line.", "paper.tex"), "masked-spans")

    def test_plain_text_masks_a_numeric_citation(self):
        before = "Growth slows in the mutant line [12]."
        result = solo(before, "Growth slows in the mutant line.", "notes.txt")
        self.assertFails(result, "masked-spans")
        self.assertEqual(result.detail["masked-spans"], 'after lacks "[12]"')

    def test_latex_does_not_mask_a_numeric_citation(self):
        before = "Growth slows in the mutant line [12]."
        result = solo(before, "Growth slows in the mutant line.", "paper.tex")
        self.assertFails(result, "numbers")

    def test_plain_text_masks_an_author_year_citation(self):
        before = "Growth slows in the mutant line (Lee et al., 2020)."
        for name in ("notes.txt", "notes.rst", "notes.md"):
            with self.subTest(name=name):
                result = solo(before, "Growth slows in the mutant line.", name)
                self.assertFails(result, "masked-spans")
                self.assertEqual(result.detail["masked-spans"], 'after lacks "(Lee et al., 2020)"')
        self.assertPasses(solo(before, "In the mutant line growth slows (Lee et al., 2020).", "notes.txt"))

    def test_markdown_masks_a_link_target_and_inline_code(self):
        before = "See [the data](https://example.org/data) and `code` for 5 mg of the compound."
        self.assertPasses(solo(before, "For 5 mg of the compound, see [the data](https://example.org/data) and `code`.",
                               "notes.md"))
        lost = solo(before, "See [the data] and `code` for 5 mg of the compound.", "notes.md")
        self.assertFails(lost, "masked-spans")
        self.assertEqual(lost.detail["masked-spans"], 'after lacks "(https://example.org/data)"')
        code = solo(before, "See [the data](https://example.org/data) for 5 mg of the compound.", "notes.md")
        self.assertEqual(code.detail["masked-spans"], 'after lacks "`code`"')

    def test_the_detail_shows_each_item_on_one_line_and_in_sorted_order(self):
        result = solo("Words \\cite{aa,\n   bb} here.", "Words here.", "paper.tex")
        self.assertEqual(result.detail["masked-spans"], 'after lacks "\\cite{aa, bb}"')
        result = solo("Words \\cite{zz} \\cite{aa} here.", "Words here.", "paper.tex")
        self.assertEqual(result.detail["masked-spans"], 'after lacks "\\cite{aa}", "\\cite{zz}"')

    def test_the_detail_cuts_a_long_span_and_lists_three_items(self):
        before = "Words \\cite{a} \\cite{b} \\cite{c} \\cite{d} \\cite{e} here."
        result = solo(before, "Words here.", "paper.tex")
        self.assertEqual(result.detail["masked-spans"],
                         'after lacks "\\cite{a}", "\\cite{b}", "\\cite{c}" and 2 more')
        long_key = "\\cite{" + "k" * 60 + "}"
        result = solo("Words " + long_key + " here.", "Words here.", "paper.tex")
        self.assertEqual(result.detail["masked-spans"], 'after lacks "\\cite{kkkkkkkkkkkkkkkkkkkkk..."')
        self.assertEqual(len(result.detail["masked-spans"]), len('after lacks ""') + 30)


class NumberTests(GuardCase):
    def test_a_changed_number_fails(self):
        result = solo(S_NUMBERS, S_NUMBERS.replace("12.5", "12"), "paper.tex")
        self.assertFails(result, "numbers")
        self.assertEqual(result.detail["numbers"], 'after lacks "12.5" and adds "12"')

    def test_a_changed_percent_sign_fails_in_plain_text(self):
        before = "The treated group lost 12.5% of its mass in two weeks."
        result = solo(before, before.replace("12.5%", "12%"), "notes.txt")
        self.assertFails(result, "numbers")
        self.assertEqual(result.detail["numbers"], 'after lacks "12.5%" and adds "12%"')

    def test_a_reworded_sentence_keeps_the_dose_and_passes(self):
        after = "The treated group lost 12.5\\% of its mass after 5 mg of the compound."
        self.assertPasses(solo(S_NUMBERS, after, "paper.tex"))

    def test_a_changed_unit_fails(self):
        result = solo(S_NUMBERS, S_NUMBERS.replace("5 mg", "5 g"), "paper.tex")
        self.assertFails(result, "numbers")
        self.assertEqual(result.detail["numbers"], 'after lacks "5mg" and adds "5g"')

    def test_a_changed_amount_of_substance_fails(self):
        before = "The cells were kept in 5 mmol sucrose for 48 h."
        result = solo(before, before.replace("5 mmol", "5 mol"), "notes.txt")
        self.assertFails(result, "numbers")
        self.assertEqual(result.detail["numbers"], 'after lacks "5mmol" and adds "5mol"')

    def test_the_space_before_a_unit_does_not_matter(self):
        self.assertPasses(solo(S_NUMBERS, S_NUMBERS.replace("5 mg", "5mg"), "paper.tex"))
        self.assertPasses(solo(S_NUMBERS.replace("5 mg", "5mg"), S_NUMBERS, "paper.tex"))

    def test_a_dropped_number_fails(self):
        result = solo(S_NUMBERS, "The treated group received the compound and lost 12.5\\% of its mass.", "paper.tex")
        self.assertFails(result, "numbers")
        self.assertEqual(result.detail["numbers"], 'after lacks "5mg"')

    def test_a_new_number_fails(self):
        result = solo(S_NUMBERS, S_NUMBERS.replace("compound", "compound on day 3"), "paper.tex")
        self.assertFails(result, "numbers")
        self.assertEqual(result.detail["numbers"], 'after adds "3"')

    def test_the_count_of_each_number_matters(self):
        before = "Two groups of 3 mice received 3 doses."
        result = solo(before, "Two groups of 3 mice received doses.", "paper.txt")
        self.assertFails(result, "numbers")
        self.assertPasses(solo(before, "Two groups received 3 doses and 3 mice.", "paper.txt"))

    def test_the_order_of_the_numbers_does_not_matter(self):
        before = "The line grew 5 cm in 3 days under heat."
        self.assertPasses(solo(before, "In 3 days the line grew 5 cm under heat.", "paper.txt"))

    def test_a_citation_key_with_digits_does_not_count_as_a_number(self):
        before = "The mutant line grows slowly under heat \\cite{lee2020}."
        self.assertPasses(solo(before, "Under heat the mutant line grows slowly \\cite{lee2020}.", "paper.tex"))

    def test_a_per_unit_suffix_and_a_time_unit_count(self):
        before = "The mice got 5 mg/kg once per day for 3 weeks in the treated group."
        self.assertPasses(solo(before, "In the treated group the mice got 5 mg/kg once per day for 3 weeks.", "paper.tex"))
        result = solo(before, before.replace("5 mg/kg", "5 mg"), "paper.tex")
        self.assertFails(result, "numbers")
        self.assertEqual(result.detail["numbers"], 'after lacks "5mg/kg" and adds "5mg"')
        self.assertFails(solo(before, before.replace("5 mg/kg", "5 mg/L"), "paper.tex"), "numbers")
        result = solo(before, before.replace("3 weeks", "3 months"), "paper.tex")
        self.assertFails(result, "numbers")
        self.assertEqual(result.detail["numbers"], 'after lacks "3week" and adds "3month"')
        self.assertPasses(solo(before, before.replace("for 3 weeks in", "for a 3-week course in"), "paper.tex"))

    def test_the_noun_after_a_number_is_not_checked(self):
        before = "The group held 12 mice in the cage during the whole run of the test."
        self.assertPasses(solo(before, before.replace("12 mice", "12 rats")))

    def test_each_relation_sign_counts(self):
        for sign in "<>\u2264\u2265\u00b1\u2248~":
            for name in ("notes.txt", "notes.md"):
                with self.subTest(sign=sign, name=name):
                    before = "The reading was %s 5 units in the treated group of mice." % sign
                    result = solo(before, "The reading was 5 units in the treated group of mice.", name)
                    self.assertFails(result, "numbers")
                    self.assertEqual(result.detail["numbers"], 'after lacks "%s"' % sign)
                    result = solo(before.replace(sign, "%"), before, name)
                    self.assertEqual(result.detail["numbers"], 'after adds "%s"' % sign)

    def test_a_changed_relation_sign_fails_in_text_and_in_markdown(self):
        before = "The difference was real in the treated mice (p < 0.01) across all of the plates."
        for name in ("notes.txt", "notes.md", "notes.rst"):
            with self.subTest(name=name):
                greater = solo(before, before.replace("<", ">"), name)
                self.assertFails(greater, "numbers")
                self.assertEqual(greater.detail["numbers"], 'after lacks "<" and adds ">"')
                equal = solo(before, before.replace("<", "="), name)
                self.assertFails(equal, "numbers")
                self.assertEqual(equal.detail["numbers"], 'after lacks "<"')
                self.assertPasses(solo(before, before, name))

    def test_each_use_of_a_sign_a_phrase_and_a_number_word_counts(self):
        before = "The first reading was < 5 units and the second reading was < 6 units in the treated mice."
        result = solo(before, before.replace("< 6", "6"))
        self.assertFails(result, "numbers")
        self.assertEqual(result.detail["numbers"], 'after lacks "<"')
        before = "The mice gained about 5 grams and the controls gained about 6 grams in the cage."
        result = solo(before, before.replace("about 6", "6"))
        self.assertEqual(result.detail["numbers"], 'after lacks "about"')
        before = "The mice grew three days and the controls grew three days in the cage."
        result = solo(before, before.replace("three days and", "days and"))
        self.assertEqual(result.detail["numbers"], 'after lacks "three"')

    def test_a_negative_number_is_a_number(self):
        before = "The reading fell to -5 units in the room during the first run."
        result = solo(before, before.replace("-5", "-6"))
        self.assertFails(result, "numbers")
        self.assertEqual(result.detail["numbers"], 'after lacks "-5" and adds "-6"')
        self.assertPasses(solo(before, "During the first run the reading fell to -5 units in the room."))

    def test_a_word_outside_the_closed_lists_is_no_quantity(self):
        for word in ("roughly", "under", "above", "fifteen", "sixty", "dozen", "hundreds", "several", "many"):
            with self.subTest(word=word):
                before = "The dish held %s cells in each field of the treated mice." % word
                self.assertPasses(solo(before, before.replace(word + " ", "")))

    def test_the_lists_of_the_numbers_guard_are_closed(self):
        self.assertEqual(set(pv.QUANTIFIER_PHRASES), set(
            ["about", "approximately", "nearly", "over", "at least", "at most", "up to", "more than", "fewer than",
             "less than"]))
        self.assertEqual(set(pv.NUMBER_WORDS), set(
            ("two three four five six seven eight nine ten eleven twelve twenty thirty forty fifty hundred thousand "
             "million billion half twice double triple").split()))
        self.assertEqual(set(pv.RELATION_SIGNS), set("<>\u2264\u2265\u00b1\u2248~"))

    def test_a_tie_in_latex_is_no_relation_sign(self):
        before = "The result appears in Figure~2 for the treated mice across the plates."
        after = "The result appears in Figure 2 for the treated mice across the plates."
        self.assertPasses(solo(before, after, "paper.tex"))
        result = solo(before, after, "paper.txt")
        self.assertFails(result, "numbers")
        self.assertEqual(result.detail["numbers"], 'after lacks "~"')

    def test_a_hyphen_is_no_relation_sign(self):
        before = "The mice gained from 5-10 grams in the treated group over time."
        self.assertPasses(solo(before, "The mice gained from 5 to 10 grams in the treated group over time."))

    def test_each_quantifier_phrase_counts(self):
        phrases = ["about", "approximately", "nearly", "over", "at least", "at most", "up to", "more than",
                   "fewer than", "less than"]
        for phrase in phrases:
            with self.subTest(phrase=phrase):
                before = "The dish held %s 40 cells in each field of the treated mice." % phrase
                result = solo(before, before.replace(phrase + " ", "exactly "))
                self.assertFails(result, "numbers")
                self.assertEqual(result.detail["numbers"], 'after lacks "%s"' % phrase)
                result = solo(before.replace(phrase + " ", "exactly "), before)
                self.assertEqual(result.detail["numbers"], 'after adds "%s"' % phrase)

    def test_one_quantifier_replaces_another(self):
        before = "The lesion measured at least 12 mm across in the treated mice."
        result = solo(before, before.replace("at least", "at most"))
        self.assertFails(result, "numbers")
        self.assertEqual(result.detail["numbers"], 'after lacks "at least" and adds "at most"')
        result = solo("The dish held more than 12 mice in each field.", "The dish held at least 12 mice in each field.")
        self.assertEqual(result.detail["numbers"], 'after lacks "more than" and adds "at least"')

    def test_a_dropped_or_added_quantifier_fails(self):
        before = "The plate held approximately 40 cells in each field of the dish."
        result = solo(before, before.replace("approximately ", ""))
        self.assertEqual(result.detail["numbers"], 'after lacks "approximately"')
        result = solo(before.replace("approximately ", ""), before)
        self.assertEqual(result.detail["numbers"], 'after adds "approximately"')
        result = solo("The plate held about 40 cells in each field of the dish.",
                      "The plate held exactly 40 cells in each field of the dish.")
        self.assertEqual(result.detail["numbers"], 'after lacks "about"')

    def test_a_quantifier_may_move_inside_the_sentence(self):
        before = "About 40 cells grew in the dish after the heat shock."
        self.assertPasses(solo(before, "After the heat shock, about 40 cells grew in the dish."))
        self.assertPasses(solo("After the heat shock, about 40 cells grew in the dish.", before))

    def test_a_quantifier_with_a_line_break_equals_the_same_phrase(self):
        before = "The lesion measured at\nleast 12 mm across in the treated mice."
        self.assertPasses(solo(before, before.replace("at\nleast", "at least")))

    def test_a_quantifier_inside_a_longer_word_is_no_quantifier(self):
        before = "The overall result was stable in the treated mice across the plates."
        self.assertPasses(solo(before, before.replace("overall ", "")))
        self.assertPasses(solo("The moreover aboutface often changed.", "The change was often there."))

    def test_over_as_a_preposition_counts_and_a_rewrite_that_drops_it_fails(self):
        before = "The cells grew over the plate in the dish for many days."
        self.assertPasses(solo(before, "Over the plate in the dish the cells grew for many days."))
        result = solo(before, "The cells grew on the plate in the dish for many days.")
        self.assertFails(result, "numbers")
        self.assertEqual(result.detail["numbers"], 'after lacks "over"')

    def test_each_number_word_counts(self):
        words = ("two three four five six seven eight nine ten eleven twelve twenty thirty forty fifty hundred "
                 "thousand million billion half twice double triple").split()
        for word in words:
            with self.subTest(word=word):
                before = "The %s mice grew faster than the controls in the cage." % word
                result = solo(before, before.replace(word, "many"))
                self.assertFails(result, "numbers")
                self.assertEqual(result.detail["numbers"], 'after lacks "%s"' % word)

    def test_a_changed_number_word_fails_and_a_kept_one_passes(self):
        before = "Three mice grew faster than the control mice in the cage."
        result = solo(before, before.replace("Three", "Four"))
        self.assertFails(result, "numbers")
        self.assertEqual(result.detail["numbers"], 'after lacks "three" and adds "four"')
        self.assertPasses(solo(before, "In the cage, three mice grew faster than the control mice."))

    def test_the_words_one_and_a_are_no_number_words(self):
        before = "The team saw one change in the growth of the line after heat."
        self.assertPasses(solo(before, "The team saw a change in the growth of the line after heat."))
        self.assertPasses(solo("A change was seen in the growth of the line after heat.",
                               "One change was seen in the growth of the line after heat."))

    def test_a_number_written_in_words_is_not_the_digit(self):
        before = "The mice grew 3 times faster than the control mice in the cage."
        result = solo(before, before.replace("3 times", "three times"))
        self.assertFails(result, "numbers")
        self.assertEqual(result.detail["numbers"], 'after lacks "3" and adds "three"')

    def test_a_quantifier_in_hidden_text_is_not_counted(self):
        before = "The mutant line grows slowly under heat \\cite{about2020} in the dish."
        self.assertFails(solo(before, "The mutant line grows slowly under heat in the dish.", "paper.tex"),
                         "masked-spans")


class NoFlagTests(GuardCase):
    def test_a_contrast_pattern_in_after_fails(self):
        before = "The effect was large and the plates stayed steady in every run."
        result = solo(before, S_CONTRAST, "paper.txt")
        self.assertFails(result, "no-flag")
        self.assertEqual(result.detail["no-flag"], 'after still triggers binary-contrast "not just large but"')

    def test_a_clean_rewrite_passes(self):
        self.assertPasses(solo(S_CONTRAST, "The effect was large and steady across the plates.", "paper.txt"))

    def test_the_detail_lists_each_family_once(self):
        after = "We delve into the data, and we delve into the plates. The effect was not just large but also steady."
        before = "We study the data and the plates, and the effect was large and steady across them."
        result = solo(before, after, "paper.txt")
        self.assertIn("no-flag", result.failed)
        self.assertEqual(result.detail["no-flag"],
                         'after still triggers vocabulary-excess "delve", binary-contrast "not just large but"')

    def test_the_detail_shows_the_first_hit_of_a_family(self):
        after = "The effect was not just large but also steady. The yield was not just high but also late."
        before = "The effect was large and steady. The yield was high and late in the run."
        result = solo(before, after, "paper.txt")
        self.assertEqual(result.detail["no-flag"], 'after still triggers binary-contrast "not just large but"')

    def test_the_detail_cuts_the_list_at_three_families(self):
        after = ("We delve into the data. The effect was not just large but also steady. "
                 "Studies show that the plates matter. The study plays a pivotal role here.")
        result = solo("The effect was large and the data are on the plates in the lab.", after, "paper.txt")
        self.assertTrue(result.detail["no-flag"].endswith(" and 1 more"), result.detail["no-flag"])

    def test_a_density_family_never_fails(self):
        after = "The effect was large \u2014 and it was steady across the many plates."
        from prose_lint import lint_text
        findings = lint_text(after, "text", PATTERNS).findings
        self.assertEqual([(f.family, f.severity) for f in findings], [("em-dash", "flag")])
        self.assertPasses(solo("The effect was large and it was steady across the many plates.", after))

    def test_an_info_hit_in_an_each_family_does_not_fail(self):
        after = "The effect was not only large but also steady across the plates."
        from prose_lint import lint_text
        findings = lint_text(after, "text", PATTERNS).findings
        self.assertEqual([(f.family, f.severity) for f in findings], [("binary-contrast", "info")])
        self.assertPasses(solo("The effect was large and steady across all of the plates.", after))

    def test_the_mode_comes_from_the_patterns(self):
        density = patched("binary-contrast", mode="density", max_per_1000=1)
        self.assertPasses(solo(S_CONTRAST, S_CONTRAST, "paper.txt", patterns=density))
        each = patched("em-dash", mode="each", max_per_1000=None)
        after = "The effect was large \u2014 and it was steady across the many plates."
        result = solo("The effect was large and it was steady across the many plates.", after, patterns=each)
        self.assertFails(result, "no-flag")

    def test_a_structural_family_in_each_mode_fails(self):
        after = "Rain fell. Wind blew. Snow came. The plates froze in the cold."
        result = solo("Rain fell and the wind blew and the snow came as the plates froze in the cold.", after)
        self.assertFails(result, "no-flag")
        self.assertIn("staccato-run", result.detail["no-flag"])

    def test_the_guard_reads_the_text_in_the_format_of_the_file(self):
        before = "The effect was large and steady across the plates $not just x but y$."
        after = "The effect was large and steady across the plates $not just x but y$ too."
        self.assertPasses(solo(before, after, "paper.tex"))
        self.assertFails(solo(before, after, "paper.txt"), "no-flag")


class SentenceLengthTests(GuardCase):
    def test_a_sentence_at_the_limit_passes_and_one_over_fails(self):
        self.assertEqual(word_count(plain(35)), 35)
        self.assertPasses(solo(plain(40), plain(35)))
        result = solo(plain(40), plain(36))
        self.assertFails(result, "sentence-length")
        self.assertEqual(result.detail["sentence-length"], "a sentence of after has 36 words and the limit is 35")

    def test_the_limit_applies_to_each_sentence(self):
        self.assertPasses(solo(plain(35), plain(20) + " " + plain(20)))

    def test_the_longest_sentence_counts(self):
        result = solo(plain(40), plain(10) + " " + plain(36))
        self.assertFails(result, "sentence-length")
        self.assertIn("has 36 words", result.detail["sentence-length"])

    def test_a_profile_sets_the_limit(self):
        self.assertPasses(solo(plain(30), plain(25), profile=profile(20)))
        result = solo(plain(30), plain(26), profile=profile(20))
        self.assertFails(result, "sentence-length")
        self.assertEqual(result.detail["sentence-length"], "a sentence of after has 26 words and the limit is 25")

    def test_the_limit_rounds_up(self):
        self.assertPasses(solo(plain(30), plain(27), profile=profile(21)))
        self.assertFails(solo(plain(30), plain(28), profile=profile(21)), "sentence-length")

    def test_a_profile_without_a_percentile_gives_35(self):
        self.assertPasses(solo(plain(40), plain(35), profile=profile(None)))
        self.assertFails(solo(plain(40), plain(36), profile=profile(None)), "sentence-length")

    def test_a_placeholder_is_no_word(self):
        after = plain(34)[:-1] + " \\cite{a}\\cite{b}\\cite{c}."
        before = plain(34)[:-1] + " \\cite{a}\\cite{b}\\cite{c}."
        self.assertPasses(solo(before, after, "paper.tex"))

    def test_an_item_command_ends_a_sentence(self):
        item = "\\item " + plain(30)[:-1]
        before = item + "\n" + item
        self.assertPasses(solo(before, before, "paper.tex"))
        result = solo(before, "\\item " + plain(36)[:-1] + "\n" + item, "paper.tex")
        self.assertFails(result, "sentence-length")
        self.assertIn("has 36 words", result.detail["sentence-length"])


class NoNewNameTests(GuardCase):
    def test_a_new_gene_name_fails(self):
        before = "The line grew slowly in the heat of the room."
        result = solo(before, "The line grew slowly in the heat of the mTOR room.")
        self.assertFails(result, "no-new-names")
        self.assertEqual(result.detail["no-new-names"], 'after adds "mTOR"')

    def test_a_new_token_with_a_digit_fails(self):
        result = solo(S_SHORT, "The line grew slowly and p53 rose.")
        self.assertIn("no-new-names", result.failed)
        self.assertEqual(result.detail["no-new-names"], 'after adds "p53"')

    def test_a_new_capitalized_word_inside_a_sentence_fails(self):
        result = solo("The line grew slowly in the room.", "The line grew slowly in Smith room.")
        self.assertFails(result, "no-new-names")

    def test_a_name_that_before_holds_passes(self):
        before = "The mTOR line grew slowly in the room."
        self.assertPasses(solo(before, "In the room the mTOR line grew slowly."))

    def test_a_name_at_the_start_of_before_may_move_inside(self):
        before = "Marlin grew slowly in the heat of the room."
        self.assertPasses(solo(before, "In the heat of the room Marlin grew slowly."))

    def test_a_changed_number_is_left_to_the_numbers_guard(self):
        before = "The treated group received 5 mg of the compound in the first week."
        self.assertPasses(solo(before, before.replace("5 mg", "5mg")))
        self.assertPasses(solo(before.replace("5 mg", "5mg"), before))
        result = solo("The treated group lost 15.5% of its mass in the first week.",
                      "The treated group lost 15% of its mass in the first week.")
        self.assertFails(result, "numbers")
        result = solo(before, before.replace("5 mg", "6 mg"))
        self.assertFails(result, "numbers")

    def test_a_capital_unit_is_not_a_name(self):
        before = "The cells grew in 5 mg of the compound in the first week."
        result = solo(before, before.replace("5 mg", "5 mg/L"))
        self.assertFails(result, "numbers")
        result = solo(before, before.replace("5 mg", "5 mM"))
        self.assertFails(result, "numbers")
        result = solo(before, before.replace("5 mg", "5 kDa"))
        self.assertFails(result, "numbers")
        self.assertPasses(solo(before.replace("5 mg", "5 mg/L"), "In 5 mg/L of the compound the cells grew in the first week."))

    def test_a_unit_inside_a_hidden_span_covers_no_name(self):
        before = "The cells grew in the dish. Sample of $5 mg/L$."
        result = solo(before, "The cells grew in the dish. Sample L of $5 mg/L$.", "paper.tex")
        self.assertEqual(result.failed, ["no-new-names"])
        self.assertEqual(result.detail["no-new-names"], 'after adds "L"')

    def test_a_new_name_next_to_a_number_still_fails(self):
        before = "The group received 5 mg of the compound in the first week."
        result = solo(before, before.replace("the compound", "mTOR"))
        self.assertEqual(result.failed, ["no-new-names"])
        self.assertEqual(result.detail["no-new-names"], 'after adds "mTOR"')
        result = solo(before, before.replace("5 mg of the compound", "6 mg of mTOR"))
        self.assertEqual(result.failed, ["numbers", "no-new-names"])
        self.assertEqual(result.detail["no-new-names"], 'after adds "mTOR"')

    def test_a_plural_time_unit_without_a_space_is_no_name(self):
        before = "The mice got the dose for 3 weeks in the treated group."
        self.assertPasses(solo(before, before.replace("3 weeks", "3weeks")))
        before = "The mice stayed in a 12-week trial in the treated group."
        self.assertPasses(solo(before, "The mice stayed for 12 weeks in the treated group."))

    def test_a_token_with_a_digit_that_is_no_number_is_still_a_name(self):
        result = solo("The line grew slowly in the room.", "The line grew slowly in the room with p53.")
        self.assertIn("no-new-names", result.failed)
        self.assertEqual(result.detail["no-new-names"], 'after adds "p53"')

    def test_a_name_inside_a_hidden_span_of_before_does_not_count(self):
        before = "The line grew slowly in heat \\cite{mTOR}."
        result = solo(before, "The mTOR line grew slowly in heat \\cite{mTOR}.", "paper.tex")
        self.assertFails(result, "no-new-names")
        self.assertEqual(result.detail["no-new-names"], 'after adds "mTOR"')

    def test_a_name_inside_a_citation_is_hidden(self):
        self.assertFails(solo(S_SHORT, S_SHORT + " \\cite{lee2020}", "paper.tex"), "masked-spans")

    def test_a_new_name_at_the_start_of_a_sentence_gives_a_warning_only(self):
        result = solo("The line grew slowly in heat.", "Zhang saw slow growth in heat.")
        self.assertPasses(result)
        self.assertEqual(result.warnings, ['new sentence-initial word "Zhang"'])

    def test_a_warning_never_fails_a_proposal(self):
        result = solo("The line grew slowly in heat.", "Zhang saw slow growth in heat.")
        self.assertTrue(result.ok)

    def test_a_common_word_at_the_start_gives_no_warning(self):
        before = "The line grew slowly in heat."
        for word in ("However", "Overall", "Thus", "This", "These", "Together", "Both", "After", "Then", "Here",
                     "Still", "Our", "We", "In", "It", "There", "Furthermore", "One", "Two", "First", "As"):
            with self.subTest(word=word):
                self.assertEqual(solo(before, "%s the line grew slowly in heat." % word).warnings, [])

    def test_a_name_at_the_start_still_gives_a_warning(self):
        before = "The line grew slowly in heat."
        for word in ("Zhang", "Notch", "Marlin", "Growth"):
            with self.subTest(word=word):
                result = solo(before, "%s grew slowly in heat." % word)
                self.assertEqual(result.warnings, ['new sentence-initial word "%s"' % word])

    def test_the_list_of_common_starts_is_a_closed_list_of_lowercase_words(self):
        starts = pv.COMMON_STARTS
        self.assertIsInstance(starts, frozenset)
        self.assertTrue(90 <= len(starts) <= 160, len(starts))
        for word in starts:
            self.assertEqual(word, word.lower())
            self.assertRegex(word, "^[a-z]+$")
        for word in ("the", "however", "this", "we", "in", "thus", "overall", "one", "two", "as"):
            self.assertIn(word, starts)
        for word in ("zhang", "notch", "gene", "cell", "protein", "mice", "data", "results", "growth", "line",
                     "mtor", "plates", "assay", "signal"):
            self.assertNotIn(word, starts)

    def test_a_word_that_before_holds_gives_no_warning(self):
        result = solo("The line grew slowly in heat. Growth stopped after day.",
                      "Growth stopped after day. The line grew slowly in heat.")
        self.assertEqual(result.warnings, [])

    def test_the_comparison_ignores_case_and_looks_at_every_word_of_before(self):
        before = "In heat the line GREW slowly."
        self.assertEqual(solo(before, "Grew slowly in heat the line.").warnings, [])
        self.assertEqual(solo(before, "Slowly the line grew in heat.").warnings, [])

    def test_a_lowercase_new_word_gives_no_warning(self):
        self.assertEqual(solo("The line grew slowly in heat.", "the line grew in heat.").warnings, [])

    def test_a_number_at_the_start_gives_no_warning(self):
        self.assertEqual(solo("The line grew slowly in heat.", "12 lines grew slowly in heat.").warnings, [])

    def test_each_new_word_is_listed_once(self):
        before = "The line grew slowly in heat. Growth stopped after day three."
        after = "Zhang saw slow growth in heat. Zhang saw growth stop after day three. Lee agreed."
        self.assertEqual(solo(before, after).warnings,
                         ['new sentence-initial word "Zhang"', 'new sentence-initial word "Lee"'])

    def test_a_new_name_inside_a_sentence_gives_no_warning(self):
        result = solo("The line grew slowly in the room.", "The line grew slowly in Smith room.")
        self.assertEqual(result.warnings, [])

    def test_a_word_after_a_command_counts_as_the_first_word(self):
        result = solo("The line grew slowly in heat.", "\\emph{Zhang} saw slow growth in heat.", "paper.tex")
        self.assertIn('new sentence-initial word "Zhang"', result.warnings)


class NotLongerTests(GuardCase):
    def test_the_limit_for_20_words_is_23(self):
        self.assertPasses(solo(plain(20), plain(23)))
        result = solo(plain(20), plain(24))
        self.assertFails(result, "not-longer")
        self.assertEqual(result.detail["not-longer"], "after has 24 words and the limit for 20 words is 23")

    def test_the_limit_is_exact_for_whole_percentages(self):
        for before, limit in ((20, 23), (40, 46), (60, 69), (100, 115), (7, 9), (10, 12), (5, 6), (1, 2), (3, 4)):
            with self.subTest(before=before):
                self.assertPasses(solo(plain(before), plain_run(limit)))
                self.assertFails(solo(plain(before), plain_run(limit + 1)), "not-longer")

    def test_a_short_sentence_may_gain_one_word(self):
        self.assertPasses(solo(plain(1), plain(2)))
        self.assertFails(solo(plain(1), plain(3)), "not-longer")

    def test_a_before_with_no_word_may_gain_one_word(self):
        before = "\\cite{lee2020}"
        self.assertPasses(solo(before, before + " Growth.", "paper.tex"))
        result = solo(before, before + " Growth slowed.", "paper.tex")
        self.assertFails(result, "not-longer")
        self.assertEqual(result.detail["not-longer"], "after has 2 words and the limit for 0 words is 1")

    def test_the_limit_counts_the_words_of_the_masked_before(self):
        cites = "\\cite{aa}\\cite{bb}\\cite{cc}\\cite{dd}"
        before = "Growth slows " + cites + "."
        self.assertPasses(solo(before, "Growth slows now " + cites + ".", "paper.tex"))
        result = solo(before, "Growth slows in time " + cites + ".", "paper.tex")
        self.assertFails(result, "not-longer")
        self.assertEqual(result.detail["not-longer"], "after has 4 words and the limit for 2 words is 3")

    def test_a_sixty_word_rewrite_of_a_twenty_word_sentence_fails_two_guards(self):
        result = solo(plain(20), plain(60))
        self.assertFails(result, "sentence-length", "not-longer")

    def test_a_shorter_rewrite_passes(self):
        self.assertPasses(solo(plain(30), plain(10)))

    def test_words_are_counted_in_the_masked_text(self):
        before = "The mutant line grows slowly under heat \\cite{lee2020}."
        self.assertPasses(solo(before, "Under heat the mutant line grows slowly \\cite{lee2020}.", "paper.tex"))


class NoEmptyTests(GuardCase):
    def test_an_empty_after_fails(self):
        result = solo(S_SHORT, "")
        self.assertFails(result, "no-empty")
        self.assertEqual(result.detail["no-empty"], "after is empty and the proposal does not set delete")

    def test_a_blank_after_fails(self):
        self.assertFails(solo(S_SHORT, " \n\t "), "no-empty")

    def test_a_deletion_with_a_family_that_allows_it_passes(self):
        self.assertPasses(solo(S_PUFF, "", delete=True, families=["importance-puffery"]))

    def test_a_deletion_with_a_family_that_forbids_it_fails(self):
        result = solo(S_CONTRAST, "", delete=True, families=["binary-contrast"])
        self.assertIn("no-empty", result.failed)
        self.assertEqual(result.detail["no-empty"], "the family binary-contrast does not allow deletion")

    def test_every_family_must_allow_the_deletion(self):
        result = solo(S_PUFF, "", delete=True, families=["importance-puffery", "binary-contrast"])
        self.assertIn("no-empty", result.failed)
        result = solo(S_PUFF, "", delete=True, families=["binary-contrast", "importance-puffery"])
        self.assertIn("no-empty", result.failed)

    def test_a_deletion_with_no_family_fails(self):
        result = solo(S_PUFF, "", delete=True, families=[])
        self.assertEqual(result.detail["no-empty"], "delete needs at least one family")

    def test_a_family_that_allows_deletion_is_no_leave_without_the_flag(self):
        result = solo(S_PUFF, "", delete=False, families=["importance-puffery"])
        self.assertFails(result, "no-empty")

    def test_a_deletion_flag_with_text_in_after_passes(self):
        self.assertPasses(solo(S_PUFF, "The study matters in the field.", delete=True, families=["binary-contrast"]))

    def test_a_disabled_family_still_gives_its_delete_ok(self):
        families = [f for f in PATTERNS.families if f.id != "importance-puffery"]
        disabled = [f for f in PATTERNS.families if f.id == "importance-puffery"]
        patterns = pp.Patterns(families, PATTERNS.as_of, disabled)
        self.assertPasses(solo(S_PUFF, "", delete=True, families=["importance-puffery"], patterns=patterns))


class NoOverlapTests(GuardCase):
    def run_spans(self, spans, names=None):
        items = [span(PLAIN, a, b, **({"file": names[i]} if names else {})) for i, (a, b) in enumerate(spans)]
        for i, item in enumerate(items):
            item["id"] = "p%d" % i
        return pv.check_proposals(items, PATTERNS, None, reader({"paper.txt": PLAIN, "other.txt": PLAIN}))

    def bounds(self):
        return sentence_bounds()

    def test_the_later_of_two_overlapping_proposals_fails(self):
        (a0, a1), (b0, b1) = self.bounds()[:2]
        first, second = self.run_spans([(a0, b0 + 10), (b0, b1)])
        self.assertPasses(first)
        self.assertFails(second, "no-overlap")
        self.assertEqual(second.detail["no-overlap"], "the span %d:%d overlaps the proposal p%d at %d:%d" % (
            b0, b1, a0, a0, b0 + 10))

    def test_the_order_of_the_list_decides_not_the_position(self):
        (a0, a1), (b0, b1) = self.bounds()[:2]
        first, second = self.run_spans([(b0, b1), (a0, b0 + 10)])
        self.assertPasses(first)
        self.assertFails(second, "no-overlap")

    def test_a_contained_span_fails(self):
        (a0, a1), (b0, b1), (c0, c1) = self.bounds()[:3]
        first, second = self.run_spans([(a0, c1), (b0, b1)])
        self.assertPasses(first)
        self.assertFails(second, "no-overlap")

    def test_the_same_span_twice_fails_the_second(self):
        (a0, a1) = self.bounds()[0]
        first, second = self.run_spans([(a0, a1), (a0, a1)])
        self.assertFails(second, "no-overlap")
        self.assertFalse(first.failed)

    def test_spans_that_touch_do_not_overlap(self):
        (a0, a1), (b0, b1) = self.bounds()[:2]
        middle = a1 + 5
        first, second = self.run_spans([(a0, middle), (middle, b1)])
        self.assertPasses(first)
        self.assertPasses(second)
        first, second = self.run_spans([(middle, b1), (a0, middle)])
        self.assertPasses(first)
        self.assertPasses(second)

    def test_spans_that_share_one_character_overlap(self):
        (a0, a1), (b0, b1) = self.bounds()[:2]
        middle = a1 + 5
        self.assertFails(self.run_spans([(a0, middle), (middle - 1, b1)])[1], "no-overlap")
        self.assertFails(self.run_spans([(middle, b1), (a0, middle + 1)])[1], "no-overlap")

    def test_an_earlier_proposal_counts_even_when_it_fails(self):
        (a0, a1), (b0, b1) = self.bounds()[:2]
        items = [span(PLAIN, a0, b0 + 10, after="Changed 7 words."), span(PLAIN, b0, b1)]
        items[1]["id"] = "later"
        first, second = pv.check_proposals(items, PATTERNS, None, reader({"paper.txt": PLAIN}))
        self.assertIn("numbers", first.failed)
        self.assertNotIn("no-overlap", first.failed)
        self.assertFails(second, "no-overlap")

    def test_the_later_proposal_is_compared_with_every_earlier_one(self):
        (a0, a1), (b0, b1), (c0, c1) = self.bounds()[:3]
        first, second, third = self.run_spans([(a0, b0 + 10), (b0, c0 + 10), (c0, c1)])
        self.assertPasses(first)
        self.assertFails(second, "no-overlap")
        self.assertFails(third, "no-overlap")
        self.assertEqual(third.detail["no-overlap"], "the span %d:%d overlaps the proposal p1 at %d:%d" % (
            c0, c1, b0, c0 + 10))
        first, second, third = self.run_spans([(a0, c0 + 10), (b0, b1), (c0, c1)])
        self.assertEqual(third.detail["no-overlap"], "the span %d:%d overlaps the proposal p0 at %d:%d" % (
            c0, c1, a0, c0 + 10))

    def test_the_first_overlapping_proposal_names_its_partner(self):
        (a0, a1), (b0, b1) = self.bounds()[:2]
        items = [span(PLAIN, a0, a1), span(PLAIN, a0, b1)]
        items[0]["id"], items[1]["id"] = "first", "second"
        results = pv.check_proposals(items, PATTERNS, None, reader({"paper.txt": PLAIN}))
        self.assertIn("proposal first at %d:%d" % (a0, a1), results[1].detail["no-overlap"])

    def test_two_files_do_not_overlap(self):
        (a0, a1) = self.bounds()[0]
        items = [span(PLAIN, a0, a1, "paper.txt"), span(PLAIN, a0, a1, "other.txt")]
        items[1]["id"] = "other"
        results = pv.check_proposals(items, PATTERNS, None, reader({"paper.txt": PLAIN, "other.txt": PLAIN}))
        self.assertTrue(all(r.ok for r in results))

    def test_a_symbolic_link_and_its_target_are_one_file(self):
        with Folder() as folder:
            real = folder.write("real.txt", PLAIN)
            link = folder.path("link.txt")
            try:
                os.symlink(real, link)
            except OSError:
                self.skipTest("the file system rejects a symbolic link")
            (a0, a1), (b0, b1) = self.bounds()[:2]
            items = [span(PLAIN, a0, b0 + 10, real), span(PLAIN, b0, b1, link)]
            items[0]["id"], items[1]["id"] = "real", "link"
            results = pv.check_proposals(items, PATTERNS)
            self.assertPasses(results[0])
            self.assertFails(results[1], "no-overlap")
            other = folder.write("other.txt", PLAIN)
            items[1] = dict(items[1], file=other)
            results = pv.check_proposals(items, PATTERNS)
            self.assertPasses(results[1])

    def test_a_file_name_that_realpath_rejects_is_still_a_file_name(self):
        for name in ("a\x00b.txt", "\ud800.txt"):
            with self.subTest(name=name):
                (a0, a1) = self.bounds()[0]
                items = [span(PLAIN, a0, a1, name)]
                result = pv.check_proposals(items, PATTERNS, None, reader({name: PLAIN}))[0]
                self.assertPasses(result)

    def test_two_spellings_of_a_file_name_that_realpath_rejects_overlap(self):
        for name in ("a\x00b.txt", "\ud800.txt"):
            with self.subTest(name=name):
                (a0, a1) = self.bounds()[0]
                items = [span(PLAIN, a0, a1, name), span(PLAIN, a0, a1, "./" + name)]
                items[1]["id"] = "again"
                files = reader({name: PLAIN, "./" + name: PLAIN})
                results = pv.check_proposals(items, PATTERNS, None, files)
                self.assertPasses(results[0])
                self.assertFails(results[1], "no-overlap")

    def test_two_spellings_of_one_file_overlap(self):
        (a0, a1) = self.bounds()[0]
        items = [span(PLAIN, a0, a1, "dir/paper.txt"), span(PLAIN, a0, a1, "dir/./sub/../paper.txt")]
        items[1]["id"] = "again"
        results = pv.check_proposals(items, PATTERNS, None, reader({"dir/paper.txt": PLAIN,
                                                                    "dir/./sub/../paper.txt": PLAIN}))
        self.assertPasses(results[0])
        self.assertFails(results[1], "no-overlap")


class HedgeKeptTests(GuardCase):
    SENTENCE = "These data may suggest that growth slows in the mutant line."

    def test_a_dropped_hedge_fails(self):
        result = solo(self.SENTENCE, "These data suggest that growth slows in the mutant line.")
        self.assertFails(result, "hedge-kept")
        self.assertEqual(result.detail["hedge-kept"], "after has 1 and before has 2 hedge cues")

    def test_a_hedge_reason_waives_the_guard(self):
        after = "These data suggest that growth slows in the mutant line."
        self.assertPasses(solo(self.SENTENCE, after, hedge_reason="The new assay removes the doubt."))

    def test_a_blank_hedge_reason_does_not_waive_the_guard(self):
        after = "These data suggest that growth slows in the mutant line."
        self.assertFails(solo(self.SENTENCE, after, hedge_reason="  \n"), "hedge-kept")
        self.assertFails(solo(self.SENTENCE, after, hedge_reason=""), "hedge-kept")

    def test_a_kept_hedge_passes(self):
        self.assertPasses(solo(self.SENTENCE, "In the mutant line, growth may slow, and the data suggest it."))

    def test_an_added_hedge_fails(self):
        result = solo("These data show that growth slows in the mutant line.", self.SENTENCE)
        self.assertFails(result, "hedge-kept")
        self.assertEqual(result.detail["hedge-kept"], "after has 2 and before has 0 hedge cues")

    def test_a_hedge_stack_rewrite_passes(self):
        after = "The data may suggest a link between heat and growth."
        self.assertPasses(solo(S_STACK, after, families=["hedge-stack"]))
        result = solo(S_STACK, after)
        self.assertFails(result, "hedge-kept")
        self.assertEqual(result.detail["hedge-kept"], "after has 2 and before has 3 hedge cues")

    def test_the_stack_rule_from_the_brief_passes_with_either_family_list(self):
        before = "The data may potentially suggest a link between heat and growth."
        after = "The data may suggest a link between heat and growth."
        self.assertPasses(solo(before, after, families=["hedge-stack"]))
        self.assertPasses(solo(before, after, families=[]))

    def test_the_stack_family_passes_with_one_cue_left(self):
        after = "The data suggest a link between heat and growth."
        self.assertPasses(solo(S_STACK, after, families=["hedge-stack"]))

    def test_each_use_of_a_cue_counts(self):
        before = "Growth may slow and yield may rise in the mutant line."
        result = solo(before, "Growth may slow and yield rises in the mutant line.")
        self.assertFails(result, "hedge-kept")
        self.assertEqual(result.detail["hedge-kept"], "after has 1 and before has 2 hedge cues")
        self.assertPasses(solo(before, "Yield may rise and growth may slow in the mutant line."))

    def test_the_stack_family_needs_one_cue_to_remain(self):
        after = "The data show a link between heat and growth."
        self.assertFails(solo(S_STACK, after, families=["hedge-stack"]), "hedge-kept")

    def test_the_stack_family_does_not_allow_a_new_cue(self):
        before = "The data may suggest a link between heat and growth."
        more = "The data may suggest a likely link between heat and growth."
        self.assertFails(solo(before, more, families=["hedge-stack"]), "hedge-kept")

    def test_another_family_does_not_waive_the_guard(self):
        after = "The data may suggest a link between heat and growth."
        self.assertFails(solo(S_STACK, after, families=["binary-contrast"]), "hedge-kept")

    def test_the_count_ignores_case(self):
        self.assertPasses(solo("Growth may slow in the mutant line.", "May growth slow in the mutant line."))
        self.assertPasses(solo("May growth slow in the mutant line.", "Growth may slow in the mutant line."))
        self.assertFails(solo("Growth may slow in the mutant line.", "Growth slows in the mutant line."), "hedge-kept")

    def test_the_count_uses_whole_words(self):
        self.assertPasses(solo("The mayor read the long report about the plan.",
                               "The leader read the long report about the plan."))
        self.assertPasses(solo("The appearance of the line changed in heat.", "The shape of the line changed in heat."))
        self.assertPasses(solo("The likely maybe line changed in heat.", "The likely maybe line changed in heat."))
        self.assertFails(solo("The likely line changed in heat.", "The likelihood line changed in heat."), "hedge-kept")

    def test_each_cue_of_the_list_counts(self):
        for word in pv.HEDGE_WORDS:
            with self.subTest(word=word):
                before = "The data %s a change in the mutant line." % word
                self.assertFails(solo(before, "The data show a change in the mutant line."), "hedge-kept")

    def test_hidden_text_gives_no_cue(self):
        before = "Growth slows \\cite{may2020}."
        self.assertFails(solo(before, "Growth slows.", "paper.tex"), "masked-spans")


class ResultTests(GuardCase):
    def test_the_guards_come_in_the_order_of_the_brief(self):
        self.assertEqual(list(pv.GUARDS), GUARD_ORDER)

    def test_every_guard_runs_after_one_fails(self):
        before = "These data may suggest that the dose of 5 mg slows growth in the line \\cite{lee2020}."
        after = ("Zhang found with mTOR that the dose of 12 mg did not just slow growth but stopped it, and we delve "
                 + plain(36))
        result = solo(before, after, "paper.tex", families=["hedge-stack"])
        expected = ["masked-spans", "numbers", "no-flag", "sentence-length", "no-new-names", "not-longer", "hedge-kept"]
        self.assertEqual(result.failed, expected)
        self.assertEqual(sorted(result.detail), sorted(expected))
        for message in result.detail.values():
            self.assertTrue(message and message == " ".join(message.split()))

    def test_every_guard_but_no_empty_can_fail_together(self):
        sentence = "These data may suggest that the dose of 5 mg slows growth in the line \\cite{lee2020}."
        text = "Intro words came first. " + sentence + " Closing words came last.\n"
        first = prop(text, sentence, sentence, id="a", families=["hedge-stack"])
        second = dict(first, id="b", before=sentence.replace("slows", "slowed"),
                      after="Zhang found with mTOR that the dose of 12 mg did not just slow growth, and we delve "
                            + plain(36))
        results = pv.check_proposals([first, second], PATTERNS, None, reader({"paper.tex": text}))
        self.assertTrue(results[0].ok)
        self.assertEqual(results[1].failed, [name for name in GUARD_ORDER if name != "no-empty"])
        self.assertEqual(sorted(results[1].detail), sorted(results[1].failed))

    def test_an_empty_after_can_fail_six_guards_together(self):
        sentence = "These data may suggest that the dose of 5 mg slows growth in the line \\cite{lee2020}."
        text = "Intro words came first. " + sentence + " Closing words came last.\n"
        first = prop(text, sentence, sentence, id="a")
        second = dict(first, id="b", before=sentence.replace("slows", "slowed"), after="")
        results = pv.check_proposals([first, second], PATTERNS, None, reader({"paper.tex": text}))
        self.assertEqual(results[1].failed, ["exact-before", "masked-spans", "numbers", "no-empty", "no-overlap",
                                             "hedge-kept"])

    def test_a_passing_result_has_nothing_in_failed_and_detail(self):
        result = solo(S_SHORT, S_SHORT)
        self.assertEqual((result.id, result.ok, result.failed, result.detail, result.warnings),
                         ("p1", True, [], {}, []))

    def test_the_detail_messages_are_short(self):
        result = solo("The mutant line grows slowly under heat.", "x " * 40 + "Zhang p53 \\cite{aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa}")
        for message in result.detail.values():
            self.assertLess(len(message), 160)

    def test_the_result_has_a_warnings_list_by_default(self):
        result = pv.Result("a", True, [], {})
        self.assertEqual(result.warnings, [])
        result.warnings.append("x")
        self.assertEqual(pv.Result("b", True, [], {}).warnings, [])

    def test_the_result_is_a_named_tuple(self):
        result = pv.Result("a", False, ["numbers"], {"numbers": "m"}, ["w"])
        self.assertEqual(result, ("a", False, ["numbers"], {"numbers": "m"}, ["w"]))
        self.assertEqual(result._fields, ("id", "ok", "failed", "detail", "warnings"))

    def test_one_result_for_each_proposal_in_the_order_of_the_list(self):
        a, b, c = [span(PLAIN, *bounds, id=name) for name, bounds in zip("abc", sentence_bounds())]
        results = pv.check_proposals([b, c, a], PATTERNS, None, reader({"paper.txt": PLAIN}))
        self.assertEqual([r.id for r in results], ["b", "c", "a"])

    def test_an_empty_list_gives_no_result(self):
        self.assertEqual(pv.check_proposals([], PATTERNS), [])

    def test_the_same_file_in_two_proposals_gives_two_results_and_one_read(self):
        reads = []

        def read(path):
            reads.append(path)
            return TEX

        good, bad = prop(TEX, S_NUMBERS, S_NUMBERS), prop(TEX, S_CONTRAST, S_CONTRAST)
        good["id"], bad["id"] = "good", "bad"
        results = pv.check_proposals([good, bad], PATTERNS, None, read)
        self.assertEqual([(r.id, r.ok) for r in results], [("good", True), ("bad", False)])
        self.assertEqual(results[1].failed, ["no-flag"])
        self.assertEqual(reads, ["paper.tex"])

    def test_extra_fields_stay_unread(self):
        item = prop(TEX, S_NUMBERS, S_NUMBERS, occurrences=1, hits=[{"family": "x"}], note="free text")
        self.assertPasses(pv.check_proposals([item], PATTERNS, None, reader({"paper.tex": TEX}))[0])


class DataErrorTests(unittest.TestCase):
    def error(self, items, files=None, default_read=False):
        files = {"paper.tex": TEX} if files is None else files
        with self.assertRaises(pv.ProposalError) as caught:
            pv.check_proposals(items, PATTERNS, None, None if default_read else reader(files))
        return str(caught.exception)

    def good(self, **fields):
        return prop(TEX, S_NUMBERS, S_NUMBERS, **fields)

    def test_the_error_is_a_value_error(self):
        self.assertTrue(issubclass(pv.ProposalError, ValueError))

    def test_a_missing_field_names_the_proposal_and_the_field(self):
        for name in ("id", "file", "start", "end", "before", "after", "families", "reason"):
            with self.subTest(name=name):
                item = self.good(id="w007")
                del item[name]
                message = self.error([item])
                self.assertIn('the field "%s" is missing' % name, message)
                self.assertTrue(message.startswith("proposal w007:" if name != "id" else "proposal number 1:"), message)

    def test_a_mistyped_field_names_the_proposal_and_the_field(self):
        cases = {"id": [5, "", None, ["a"]], "file": [5, "", None], "start": ["5", 5.0, True, None],
                 "end": ["5", 5.5, False, None], "before": [5, None, ["a"]], "after": [5, None, ["a"]],
                 "families": ["binary-contrast", None, [5], ["binary-contrast", None], {"a": 1}], "reason": [5, None],
                 "delete": ["yes", 1, None], "hedge_reason": [5, None, True]}
        for name, values in cases.items():
            for value in values:
                with self.subTest(name=name, value=value):
                    item = self.good(id="w007")
                    item[name] = value
                    message = self.error([item], {"paper.tex": TEX})
                    self.assertIn('the field "%s" must be' % name, message)

    def test_a_proposal_that_is_no_object_is_a_data_error(self):
        message = self.error([self.good(), "text"])
        self.assertEqual(message, "proposal number 2 must be a JSON object.")

    def test_an_unknown_family_id_names_the_id_and_lists_the_valid_ones(self):
        message = self.error([self.good(id="w007", families=["binary-contrst"])])
        self.assertTrue(message.startswith('proposal w007: the family id "binary-contrst" is unknown. The valid ids are '),
                        message)
        self.assertIn("binary-contrast", message)
        self.assertIn("hedge-stack", message)

    def test_an_unknown_family_id_after_a_known_one_is_a_data_error(self):
        message = self.error([self.good(id="w007", families=["binary-contrast", "nope"])])
        self.assertTrue(message.startswith('proposal w007: the family id "nope" is unknown.'), message)

    def test_a_repeated_id_is_a_data_error(self):
        message = self.error([self.good(id="w007"), prop(TEX, S_CONTRAST, S_CONTRAST, id="w007")])
        self.assertEqual(message, "proposal w007: the id is used twice.")

    def test_an_unreadable_file_names_the_proposal_and_the_file(self):
        message = self.error([self.good(id="w007", file="missing.tex")])
        self.assertEqual(message, "proposal w007: cannot read missing.tex: No such file or directory.")

    def test_a_read_function_may_raise_a_value_error(self):
        def read(path):
            raise ValueError("%s is a binary file." % path)

        with self.assertRaises(pv.ProposalError) as caught:
            pv.check_proposals([self.good(id="w007")], PATTERNS, None, read)
        self.assertEqual(str(caught.exception), "proposal w007: paper.tex is a binary file.")

    def test_the_offsets_must_lie_in_the_file(self):
        size = len(TEX)
        cases = [
            (dict(start=-1, end=5), '"start" must not be negative'),
            (dict(start=size + 1, end=size + 2), '"start" (%d) is beyond the end of the file (%d characters)' % (size + 1, size)),
            (dict(start=10, end=5), '"end" (5) is before "start" (10)'),
            (dict(start=10, end=9), '"end" (9) is before "start" (10)'),
            (dict(start=10, end=size + 1), '"end" (%d) is beyond the end of the file (%d characters)' % (size + 1, size)),
        ]
        for fields, text in cases:
            with self.subTest(fields=fields):
                message = self.error([self.good(id="w007", **fields)])
                self.assertEqual(message, "proposal w007: %s." % text)

    def test_the_offsets_may_reach_the_end_of_the_file(self):
        before = TEX[-10:]
        item = {"id": "w007", "file": "paper.tex", "start": len(TEX) - 10, "end": len(TEX), "before": before,
                "after": before, "families": [], "reason": "r"}
        result = pv.check_proposals([item], PATTERNS, None, reader({"paper.tex": TEX}))[0]
        self.assertEqual(result.id, "w007")

    def test_the_first_data_error_wins(self):
        bad_field = self.good(id="first")
        del bad_field["reason"]
        bad_file = self.good(id="second", file="missing.tex")
        self.assertIn("proposal first:", self.error([bad_field, bad_file]))
        self.assertIn("proposal second:", self.error([self.good(id="ok"), bad_file, bad_field]))

    def test_a_crash_in_a_guard_is_a_data_error(self):
        from unittest import mock
        with mock.patch.object(pv, "lint_text", side_effect=RuntimeError("boom")):
            message = self.error([self.good(id="w007")])
        self.assertEqual(message, "proposal w007: cannot check the proposal: RuntimeError: boom.")

    def test_the_default_read_gives_the_text_of_a_file(self):
        with Folder() as folder:
            head = "\\section{A}\r\n"
            path = folder.write("a.tex", head + S_NUMBERS + "\r\n")
            item = {"id": "w007", "file": path, "start": len(head), "end": len(head) + len(S_NUMBERS), "before": S_NUMBERS,
                    "after": S_NUMBERS, "families": [], "reason": "r"}
            self.assertTrue(pv.check_proposals([item], PATTERNS)[0].ok)
            binary = folder.write("b.tex", b"abc\x00def")
            message = self.error([dict(item, file=binary)], default_read=True)
            self.assertIn("proposal w007:", message)
            self.assertIn("binary file", message)
            bad = folder.write("c.tex", b"abc\xffdef")
            self.assertIn("not valid UTF-8", self.error([dict(item, file=bad)], default_read=True))
            self.assertIn("cannot read", self.error([dict(item, file=folder.path("none.tex"))], default_read=True))
            self.assertIn("Is a directory", self.error([dict(item, file=folder.root)], default_read=True))


class CommandLineTests(unittest.TestCase):
    def setUp(self):
        self.folder = Folder().__enter__()
        self.addCleanup(self.folder.__exit__, None, None, None)
        self.tex = self.folder.write("paper.tex", TEX)
        self.pass1 = self.item("w001", S_NUMBERS, S_NUMBERS)
        self.fail2 = self.item("w002", S_HEDGE, S_HEDGE.replace("may ", ""))

    def item(self, ident, before, after, **fields):
        start = TEX.index(before)
        data = {"id": ident, "file": self.tex, "start": start, "end": start + len(before), "before": before,
                "after": after, "families": [], "reason": "made-up reason"}
        data.update(fields)
        return data

    def proposals(self, data, name="proposals.json"):
        return self.folder.write(name, json.dumps(data))

    def test_all_pass_gives_exit_0(self):
        code, out, err = run([self.proposals([self.pass1])])
        self.assertEqual((code, out, err), (0, "w001: pass\npassed: 1 failed: 0\n", ""))

    def test_a_failed_guard_gives_exit_1(self):
        code, out, err = run([self.proposals([self.pass1, self.fail2])])
        self.assertEqual(code, 1)
        self.assertEqual(err, "")
        self.assertEqual(out, "w001: pass\nw002: FAIL hedge-kept (hedge-kept: after has 1 and before has 2 hedge cues)\n"
                              "passed: 1 failed: 1\n")

    def test_the_text_output_lists_the_guards_and_the_warnings(self):
        text = "The line grew slowly. " + S_NUMBERS
        path = self.folder.write("warn.tex", text)
        warn = {"id": "w003", "file": path, "start": 0, "end": len(S_SHORT), "before": S_SHORT,
                "after": "Zhang saw slow growth.", "families": [], "reason": "made-up reason"}
        many = dict(warn, id="w004", before=S_SHORT, after="Zhang saw p53 grow 12 days.")
        code, out, err = run([self.proposals([warn, many])])
        self.assertEqual(code, 1)
        self.assertEqual(out, (
            'w003: pass (warning: new sentence-initial word "Zhang")\n'
            'w004: FAIL numbers, no-new-names, not-longer, no-overlap (numbers: after adds "12day"; '
            'no-new-names: after adds "p53"; not-longer: after has 7 words and the limit for 4 words is 5; '
            'no-overlap: the span 0:21 overlaps the proposal w003 at 0:21) '
            '(warning: new sentence-initial word "Zhang")\n'
            "passed: 1 failed: 1\n"))

    def test_the_json_output(self):
        code, out, err = run([self.proposals([self.pass1, self.fail2]), "--json"])
        self.assertEqual(code, 1)
        self.assertEqual(err, "")
        self.assertEqual(out, (
            '{\n  "failed": 1,\n  "passed": 1,\n  "results": [\n    {\n      "detail": {},\n      "failed": [],\n'
            '      "id": "w001",\n      "ok": true,\n      "warnings": []\n    },\n    {\n      "detail": {\n'
            '        "hedge-kept": "after has 1 and before has 2 hedge cues"\n      },\n      "failed": [\n'
            '        "hedge-kept"\n      ],\n      "id": "w002",\n      "ok": false,\n      "warnings": []\n    }\n  ]\n}\n'))
        data = json.loads(out)
        self.assertEqual(sorted(data), ["failed", "passed", "results"])
        self.assertEqual(sorted(data["results"][0]), ["detail", "failed", "id", "ok", "warnings"])

    def test_the_json_output_carries_the_warnings(self):
        path = self.folder.write("warn.tex", "The line grew slowly. " + S_NUMBERS)
        warn = {"id": "w003", "file": path, "start": 0, "end": len(S_SHORT), "before": S_SHORT,
                "after": "Zhang saw slow growth.", "families": [], "reason": "made-up reason"}
        code, out, err = run([self.proposals([warn]), "--json"])
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out)["results"][0]["warnings"], ['new sentence-initial word "Zhang"'])

    def test_a_bare_list_and_an_object_give_the_same_output(self):
        items = [self.pass1, self.fail2]
        bare = run([self.proposals(items, "a.json")])
        wrapped = run([self.proposals({"proposals": items}, "b.json")])
        self.assertEqual(bare, wrapped)
        self.assertEqual(run([self.proposals(items, "c.json"), "--json"]),
                         run([self.proposals({"proposals": items, "note": "x"}, "d.json"), "--json"]))

    def test_an_empty_list_gives_exit_0(self):
        for data in ([], {"proposals": []}):
            with self.subTest(data=data):
                code, out, err = run([self.proposals(data)])
                self.assertEqual((code, out, err), (0, "passed: 0 failed: 0\n", ""))

    def test_the_json_output_of_an_empty_list(self):
        code, out, err = run([self.proposals([]), "--json"])
        self.assertEqual((code, json.loads(out)), (0, {"failed": 0, "passed": 0, "results": []}))

    def test_a_data_error_gives_exit_2_and_writes_nothing_to_stdout(self):
        broken = dict(self.pass1)
        del broken["start"]
        code, out, err = run([self.proposals([self.pass1, broken])])
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(err, 'prose_verify.py: error: proposal w001: the field "start" is missing.\n')

    def test_the_proposals_file_must_exist(self):
        path = self.folder.path("none.json")
        code, out, err = run([path])
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(err, "prose_verify.py: error: cannot read %s: No such file or directory.\n" % path)

    def test_the_proposals_file_must_be_json(self):
        for data in (b"not json", b"", b"[1, 2", b"{'a': 1}", b"\xff\xfe[]", b"[]\xff", b"[" * 100000):
            with self.subTest(data=data[:20]):
                path = self.folder.write("bad.json", data)
                code, out, err = run([path])
                self.assertEqual((code, out), (2, ""))
                self.assertIn("is not valid JSON in UTF-8", err)
                self.assertIn(path, err)
                self.assertNotIn("Traceback", err)

    def test_the_proposals_file_must_hold_a_list(self):
        for data in ("{}", '{"proposals": 5}', '{"proposals": {"a": 1}}', '{"items": []}', "5", '"text"', "null", "true"):
            with self.subTest(data=data):
                path = self.folder.write("shape.json", data)
                code, out, err = run([path])
                self.assertEqual((code, out), (2, ""))
                self.assertEqual(err, 'prose_verify.py: error: %s must hold a list of proposals, or an object with a '
                                      'list under "proposals".\n' % path)

    def test_a_folder_as_the_proposals_file_gives_exit_2(self):
        code, out, err = run([self.folder.root])
        self.assertEqual((code, out), (2, ""))
        self.assertIn("cannot read", err)

    def test_no_argument_gives_exit_2(self):
        code, out, err = run([])
        self.assertEqual((code, out), (2, ""))
        self.assertIn("PROPOSALS", err)

    def test_two_proposals_files_give_exit_2(self):
        path = self.proposals([self.pass1])
        code, out, err = run([path, path])
        self.assertEqual((code, out), (2, ""))
        self.assertIn("unrecognized arguments", err)

    def test_an_unknown_option_gives_exit_2(self):
        code, out, err = run([self.proposals([self.pass1]), "--frmat", "latex"])
        self.assertEqual((code, out), (2, ""))
        self.assertIn("--frmat", err)

    def test_help_gives_exit_0(self):
        code, out, err = run(["--help"])
        self.assertEqual((code, err), (0, ""))
        self.assertIn("PROPOSALS", out)

    def test_a_missing_project_directory_gives_exit_2(self):
        path = self.folder.path("none")
        code, out, err = run([self.proposals([self.pass1]), "--project-dir", path])
        self.assertEqual((code, out), (2, ""))
        self.assertEqual(err, "prose_verify.py: error: project directory not found: %s\n" % path)

    def test_a_bad_project_file_gives_exit_2(self):
        project = Folder().__enter__()
        self.addCleanup(project.__exit__, None, None, None)
        project.write("prose-style.yaml", "families:\n  binary-contrst:\n    enabled: false\n")
        code, out, err = run([self.proposals([self.pass1]), "--project-dir", project.root])
        self.assertEqual((code, out), (2, ""))
        self.assertIn("binary-contrst", err)

    def test_the_project_file_changes_the_guards(self):
        path = self.folder.write("effect.txt", S_EFFECT + "\n")
        item = {"id": "w009", "file": path, "start": 0, "end": len(S_EFFECT), "before": S_EFFECT,
                "after": S_CONTRAST, "families": [], "reason": "r"}
        proposals = self.proposals([item], "effect.json")
        code, out, err = run([proposals])
        self.assertEqual(code, 1)
        self.assertTrue(out.startswith("w009: FAIL no-flag ("), out)
        project = Folder().__enter__()
        self.addCleanup(project.__exit__, None, None, None)
        project.write("prose-style.yaml", "families:\n  binary-contrast:\n    enabled: false\n")
        self.assertEqual(run([proposals, "--project-dir", project.root]), (0, "w009: pass\npassed: 1 failed: 0\n", ""))
        item["families"] = ["binary-contrast"]
        proposals = self.proposals([item], "effect2.json")
        self.assertEqual(run([proposals, "--project-dir", project.root])[0], 0)

    def test_the_project_file_is_found_in_docs_and_claude_folders(self):
        path = self.folder.write("effect.txt", S_EFFECT + "\n")
        item = {"id": "w009", "file": path, "start": 0, "end": len(S_EFFECT), "before": S_EFFECT,
                "after": S_CONTRAST, "families": [], "reason": "r"}
        proposals = self.proposals([item], "effect.json")
        for where in ("docs", ".claude"):
            with self.subTest(where=where):
                project = Folder().__enter__()
                self.addCleanup(project.__exit__, None, None, None)
                project.write(where + "/prose-style.yaml", "families:\n  binary-contrast:\n    enabled: false\n")
                self.assertEqual(run([proposals, "--project-dir", project.root])[0], 0)

    def test_the_default_project_directory_is_the_working_directory(self):
        path = self.folder.write("effect.txt", S_EFFECT)
        item = {"id": "w009", "file": path, "start": 0, "end": len(S_EFFECT), "before": S_EFFECT,
                "after": S_CONTRAST, "families": [], "reason": "r"}
        proposals = self.proposals([item], "effect.json")
        old = os.getcwd()
        self.addCleanup(os.chdir, old)
        os.chdir(self.folder.root)
        out, err = io.BytesIO(), io.BytesIO()
        self.assertEqual(pv.main([proposals], out, err), 1)
        self.assertIn(b"no-flag", out.getvalue())
        self.folder.write("prose-style.yaml", "families:\n  binary-contrast:\n    enabled: false\n")
        out = io.BytesIO()
        self.assertEqual(pv.main([proposals], out, err), 0)
        self.assertEqual(out.getvalue(), b"w009: pass\npassed: 1 failed: 0\n")

    def test_a_relative_file_name_is_read_from_the_working_directory(self):
        old = os.getcwd()
        self.addCleanup(os.chdir, old)
        os.chdir(self.folder.root)
        item = self.item("w001", S_NUMBERS, S_NUMBERS, file="paper.tex")
        out, err = io.BytesIO(), io.BytesIO()
        self.assertEqual(pv.main([self.proposals([item]), "--project-dir", self.folder.root], out, err), 0)

    def test_the_voice_option_sets_the_sentence_limit(self):
        before = plain(30)
        path = self.folder.write("long.txt", before)
        item = {"id": "w005", "file": path, "start": 0, "end": len(before), "before": before,
                "after": plain(26), "families": [], "reason": "r"}
        proposals = self.proposals([item], "long.json")
        self.assertEqual(run([proposals])[0], 0)
        voice = self.folder.write("voice.json", json.dumps(profile(20)))
        code, out, err = run([proposals, "--voice", voice])
        self.assertEqual(code, 1)
        self.assertEqual(out, "w005: FAIL sentence-length (sentence-length: a sentence of after has 26 words and the "
                              "limit is 25)\npassed: 0 failed: 1\n")

    def test_a_bad_voice_file_gives_exit_2(self):
        proposals = self.proposals([self.pass1])
        for name, data in (("missing.json", None), ("bad.json", "{"), ("list.json", "[]"),
                           ("partial.json", json.dumps({"version": 1}))):
            with self.subTest(name=name):
                path = self.folder.path(name) if data is None else self.folder.write(name, data)
                code, out, err = run([proposals, "--voice", path])
                self.assertEqual((code, out), (2, ""))
                self.assertIn(path, err)
                self.assertNotIn("Traceback", err)

    def test_markdown_and_plain_text_files(self):
        md_text = "See [the data](https://example.org/data) and `code` for 5 mg of the compound.\n"
        txt_text = "Growth slows in the mutant line (Lee et al., 2020).\n"
        md = self.folder.write("notes.md", md_text)
        txt = self.folder.write("notes.txt", txt_text)
        items = [
            {"id": "m1", "file": md, "start": 0, "end": len(md_text) - 1, "before": md_text[:-1],
             "after": "For 5 mg of the compound, see [the data](https://example.org/data) and `code`.",
             "families": [], "reason": "r"},
            {"id": "m2", "file": md, "start": 0, "end": len(md_text) - 1, "before": md_text[:-1],
             "after": "See [the data] and `code` for 5 mg of the compound.", "families": [], "reason": "r"},
            {"id": "t1", "file": txt, "start": 0, "end": len(txt_text) - 1, "before": txt_text[:-1],
             "after": "Growth slows in the mutant line.", "families": [], "reason": "r"},
        ]
        code, out, err = run([self.proposals(items)])
        self.assertEqual(code, 1)
        lines = out.splitlines()
        self.assertEqual(lines[0], "m1: pass")
        self.assertEqual(lines[1], (
            'm2: FAIL masked-spans, no-overlap (masked-spans: after lacks "(https://example.org/data)"; '
            "no-overlap: the span 0:%d overlaps the proposal m1 at 0:%d)" % (len(md_text) - 1, len(md_text) - 1)))
        self.assertEqual(lines[2], 't1: FAIL masked-spans (masked-spans: after lacks "(Lee et al., 2020)")')
        self.assertEqual(lines[3], "passed: 1 failed: 2")

    def test_the_format_comes_from_the_file_name(self):
        text = "The line grew slowly under heat [12]."
        for name, guard in (("a.tex", "numbers"), ("a.txt", "masked-spans"), ("a.md", "masked-spans"),
                            ("a.unknown", "masked-spans"), ("a", "masked-spans"), ("A.TEX", "numbers")):
            with self.subTest(name=name):
                path = self.folder.write(name, text)
                item = {"id": "w001", "file": path, "start": 0, "end": len(text), "before": text,
                        "after": "The line grew slowly under heat.", "families": [], "reason": "r"}
                code, out, err = run([self.proposals([item], "f.json")])
                self.assertEqual(code, 1)
                self.assertTrue(out.startswith("w001: FAIL %s (" % guard), out)

    def latex_in_a_text_file(self):
        """Write a LaTeX paragraph into chapter.txt. Return the proposals file that drops the citation."""
        text = "\\section{Results}\n" + S_HEDGE + "\n"
        path = self.folder.write("chapter.txt", text)
        item = {"id": "w001", "file": path, "start": text.index(S_HEDGE), "end": text.index(S_HEDGE) + len(S_HEDGE),
                "before": S_HEDGE, "after": "These data may suggest that growth slows in the mutant line.",
                "families": [], "reason": "r"}
        return self.proposals([item], "chapter.json")

    def test_the_format_option_overrides_the_extension(self):
        proposals = self.latex_in_a_text_file()
        self.assertEqual(run([proposals]), (0, "w001: pass\npassed: 1 failed: 0\n", ""))
        self.assertEqual(run([proposals, "--format", "auto"]), (0, "w001: pass\npassed: 1 failed: 0\n", ""))
        self.assertEqual(run([proposals, "--format", "text"]), (0, "w001: pass\npassed: 1 failed: 0\n", ""))
        code, out, err = run([proposals, "--format", "latex"])
        self.assertEqual((code, err), (1, ""))
        self.assertEqual(out, 'w001: FAIL masked-spans (masked-spans: after lacks "\\cite{lee2020}")\n'
                              "passed: 0 failed: 1\n")

    def test_the_format_option_applies_to_a_tex_file_as_well(self):
        text = S_HEDGE + "\n"
        path = self.folder.write("paper.tex", text)
        item = {"id": "w001", "file": path, "start": 0, "end": len(S_HEDGE), "before": S_HEDGE,
                "after": "These data may suggest that growth slows in the mutant line.", "families": [], "reason": "r"}
        proposals = self.proposals([item])
        self.assertEqual(run([proposals])[0], 1)
        self.assertEqual(run([proposals, "--format", "latex"])[0], 1)
        self.assertEqual(run([proposals, "--format", "text"])[0], 0)
        self.assertEqual(run([proposals, "--format", "markdown"])[0], 0)

    def test_the_format_option_applies_to_every_proposal(self):
        text = "\\section{Results}\n" + S_HEDGE + " " + S_NUMBERS + "\n"
        path = self.folder.write("chapter.txt", text)
        items = []
        for ident, before, after in (("w001", S_HEDGE, "These data may suggest slower growth."),
                                     ("w002", S_NUMBERS, "The treated group lost 12.5 of its mass.")):
            start = text.index(before)
            items.append({"id": ident, "file": path, "start": start, "end": start + len(before), "before": before,
                          "after": after, "families": [], "reason": "r"})
        proposals = self.proposals(items)
        code, out, err = run([proposals, "--format", "latex"])
        self.assertEqual(code, 1)
        lines = out.splitlines()
        self.assertTrue(lines[0].startswith("w001: FAIL masked-spans"), lines[0])
        self.assertTrue(lines[1].startswith("w002: FAIL masked-spans"), lines[1])

    def test_a_markdown_format_masks_a_link_target_in_a_text_file(self):
        text = "See the `code` for the results of the first run.\n"
        path = self.folder.write("notes.txt", text)
        item = {"id": "w001", "file": path, "start": 0, "end": len(text) - 1, "before": text[:-1],
                "after": "See the code for the results of the first run.", "families": [], "reason": "r"}
        proposals = self.proposals([item])
        self.assertEqual(run([proposals])[0], 0)
        code, out, err = run([proposals, "--format", "markdown"])
        self.assertEqual(code, 1)
        self.assertIn('after lacks "`code`"', out)

    def test_a_bad_format_value_gives_exit_2(self):
        proposals = self.latex_in_a_text_file()
        for value in ("xml", "LaTeX", ""):
            with self.subTest(value=value):
                code, out, err = run([proposals, "--format", value])
                self.assertEqual((code, out), (2, ""))
                self.assertIn("--format", err)
                self.assertIn("invalid choice", err)
        code, out, err = run([proposals, "--format"])
        self.assertEqual((code, out), (2, ""))

    def test_the_check_function_takes_a_format(self):
        item = prop(S_HEDGE, S_HEDGE, "These data may suggest that growth slows in the mutant line.", "chapter.txt")
        files = reader({"chapter.txt": S_HEDGE})
        self.assertTrue(pv.check_proposals([item], PATTERNS, None, files)[0].ok)
        self.assertTrue(pv.check_proposals([item], PATTERNS, None, files, "auto")[0].ok)
        result = pv.check_proposals([item], PATTERNS, None, files, "latex")[0]
        self.assertEqual(result.failed, ["masked-spans"])
        with self.assertRaises(pv.ProposalError) as caught:
            pv.check_proposals([item], PATTERNS, None, files, "xml")
        self.assertEqual(str(caught.exception), 'unknown format "xml". Use auto, latex, markdown or text.')

    def test_a_proposal_for_a_file_that_changed_fails_and_exits_1(self):
        item = self.item("w001", S_NUMBERS, S_NUMBERS)
        self.folder.write("paper.tex", TEX.replace("Results", "Findings of the run"))
        code, out, err = run([self.proposals([item])])
        self.assertEqual(code, 1)
        self.assertTrue(out.startswith("w001: FAIL exact-before (exact-before: the file text at "), out)

    def test_main_runs_as_a_script(self):
        code, out, err = run_script([self.proposals([self.pass1, self.fail2])])
        self.assertEqual((code, err), (1, b""))
        self.assertEqual(out.decode("utf-8"), "w001: pass\nw002: FAIL hedge-kept (hedge-kept: after has 1 and before "
                                              "has 2 hedge cues)\npassed: 1 failed: 1\n")

    def test_non_ascii_text_goes_out_as_utf8_in_the_c_locale(self):
        text = "Growth slows under heat (M\u00fcller et al., 2020)."
        path = self.folder.write("accent.txt", text)
        item = {"id": "w\u00e9", "file": path, "start": 0, "end": len(text), "before": text,
                "after": "Growth slows under heat.", "families": [], "reason": "r"}
        proposals = self.folder.write("accent.json", json.dumps([item], ensure_ascii=False))
        code, out, err = run_script([proposals], env=dict(os.environ, LC_ALL="C"))
        self.assertEqual((code, err), (1, b""))
        self.assertIn("w\u00e9: FAIL masked-spans".encode("utf-8"), out)
        self.assertIn("(M\u00fcller et al., 2020)".encode("utf-8"), out)
        self.assertNotIn(b"\\u00", out)


    def test_non_ascii_text_goes_out_as_utf8_in_the_json_output(self):
        text = "Growth slows under heat (M\u00fcller et al., 2020)."
        path = self.folder.write("accent.txt", text)
        item = {"id": "w\u00e9", "file": path, "start": 0, "end": len(text), "before": text,
                "after": "Growth slows under heat.", "families": [], "reason": "r"}
        proposals = self.folder.write("accent.json", json.dumps([item]))
        code, out, err = run_script([proposals, "--json"])
        self.assertEqual((code, err), (1, b""))
        self.assertIn('"id": "w\u00e9"'.encode("utf-8"), out)
        self.assertIn("(M\u00fcller et al., 2020)".encode("utf-8"), out)
        self.assertNotIn(b"\\u00", out)


class DocstringTests(unittest.TestCase):
    """The docstrings of the module and of the test file follow the writing rules."""

    def docstrings(self):
        yield "module", pv.__doc__ or ""
        for name in dir(pv):
            item = getattr(pv, name)
            if getattr(item, "__module__", None) == pv.__name__ and (callable(item) or isinstance(item, type)):
                yield name, item.__doc__ or ""
        with open(os.path.abspath(__file__), encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        yield "test module", ast.get_docstring(tree) or ""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                yield "test " + node.name, ast.get_docstring(node) or ""

    @staticmethod
    def sentences(doc):
        """Split at blank lines, at the start of a list item and after an end mark."""
        found = []
        for chunk in re.split(r"\n\s*\n|\n(?=\s*(?:-|[0-9]+\.)\s)", doc):
            found.extend(x for x in re.split("(?<=[.!?])\\s+(?=[A-Z`(])", " ".join(chunk.split())) if x)
        return found

    def test_no_sentence_is_longer_than_25_words(self):
        for name, doc in self.docstrings():
            for sentence in self.sentences(doc):
                self.assertLessEqual(len(sentence.split()), 25, "%s: %s" % (name, sentence))

    def test_no_em_dash(self):
        for name, doc in self.docstrings():
            self.assertNotIn("\u2014", doc, name)

    def test_no_banned_word(self):
        for name, doc in self.docstrings():
            self.assertNotRegex(doc.lower(), r"\b(leverage|robust|seamless|crucial|comprehensive|very|really)\b", name)


class OddNameTests(unittest.TestCase):
    """A name with a byte that is not UTF-8 must never end in a traceback."""

    def setUp(self):
        self.folder = Folder().__enter__()
        self.addCleanup(self.folder.__exit__, None, None, None)

    def odd(self, base, data):
        try:
            return self.folder.write(os.fsdecode(b"caf\xe9-" + base), data)
        except OSError:
            raise unittest.SkipTest("the file system rejects a file name with a byte that is not UTF-8")

    def proposals_for(self, path, name="proposals.json", **fields):
        before = S_NUMBERS
        item = {"id": "w001", "file": path, "start": 0, "end": len(before), "before": before, "after": before,
                "families": [], "reason": "r"}
        item.update(fields)
        return self.folder.write(name, json.dumps([item]))

    def run_bytes(self, args):
        with Folder() as empty:
            out, err = io.BytesIO(), io.BytesIO()
            code = pv.main(list(args) + ["--project-dir", empty.root], out, err)
        return code, out.getvalue(), err.getvalue()

    def test_a_file_with_such_a_name_is_checked(self):
        path = self.odd(b"ok.tex", S_NUMBERS)
        code, out, err = self.run_bytes([self.proposals_for(path)])
        self.assertEqual((code, out, err), (0, b"w001: pass\npassed: 1 failed: 0\n", b""))

    def test_a_missing_file_with_such_a_name_names_the_original_bytes(self):
        path = os.fsdecode(b"caf\xe9-missing.tex")
        code, out, err = self.run_bytes([self.proposals_for(path)])
        self.assertEqual((code, out), (2, b""))
        self.assertIn(os.fsencode(path), err)
        self.assertIn(b"proposal w001:", err)
        self.assertNotIn(b"Traceback", err)

    def test_a_file_that_is_not_utf8_with_such_a_name_gives_exit_2(self):
        path = self.odd(b"bad.tex", b"x\xff")
        code, out, err = self.run_bytes([self.proposals_for(path)])
        self.assertEqual((code, out), (2, b""))
        self.assertIn(os.fsencode(path), err)
        self.assertIn(b"UTF-8", err)

    def test_the_proposals_file_with_such_a_name(self):
        path = self.odd(b"ok.tex", S_NUMBERS)
        proposals = self.proposals_for(path, name=os.fsdecode(b"caf\xe9-proposals.json"))
        self.assertEqual(self.run_bytes([proposals])[0], 0)
        missing = os.fsdecode(b"caf\xe9-none.json")
        code, out, err = self.run_bytes([missing])
        self.assertEqual((code, out), (2, b""))
        self.assertIn(os.fsencode(missing), err)
        self.assertNotIn(b"Traceback", err)

    def test_a_voice_file_and_a_project_directory_with_such_names(self):
        proposals = self.proposals_for(self.folder.write("ok.tex", S_NUMBERS))
        voice = os.fsdecode(b"caf\xe9-voice.json")
        code, out, err = self.run_bytes([proposals, "--voice", voice])
        self.assertEqual((code, out), (2, b""))
        self.assertIn(os.fsencode(voice), err)
        self.assertNotIn(b"Traceback", err)
        project = os.fsdecode(b"caf\xe9-project")
        out, err = io.BytesIO(), io.BytesIO()
        self.assertEqual(pv.main([proposals, "--project-dir", project], out, err), 2)
        self.assertIn(os.fsencode(project), err.getvalue())

    def test_a_script_run_with_such_a_name(self):
        path = os.fsdecode(b"caf\xe9-missing.tex")
        proposals = self.proposals_for(path)
        code, out, err = run_script([proposals])
        self.assertEqual((code, out), (2, b""))
        self.assertIn(os.fsencode(path), err)
        self.assertNotIn(b"Traceback", err)

    def test_an_id_with_a_lone_surrogate_does_not_crash_the_output(self):
        path = self.folder.write("ok.tex", S_NUMBERS)
        data = json.dumps([{"id": "w\ud800", "file": path, "start": 0, "end": len(S_NUMBERS), "before": S_NUMBERS,
                            "after": S_NUMBERS, "families": [], "reason": "r"}])
        proposals = self.folder.write("surrogate.json", data)
        code, out, err = self.run_bytes([proposals])
        self.assertEqual((code, err), (0, b""))
        self.assertIn(b"w\\ud800: pass", out)
        code, out, err = self.run_bytes([proposals, "--json"])
        self.assertEqual((code, err), (0, b""))
        self.assertIn(b"w\\ud800", out)


class DetectorPipelineTests(unittest.TestCase):
    """The offsets of `prose_lint.py --windows` and the guards agree."""

    def windows(self, path):
        out, err = io.BytesIO(), io.BytesIO()
        with Folder() as empty:
            code = h.pl.main([path, "--windows", "--project-dir", empty.root], out, err)
        self.assertEqual((code, err.getvalue()), (1, b""))
        return json.loads(out.getvalue().decode("utf-8"))

    def verify(self, folder, windows, afters):
        items = []
        for window, after in zip(windows, afters):
            item = dict((k, window[k]) for k in ("id", "file", "start", "end", "before", "families"))
            item.update(after=after, reason="made-up reason")
            items.append(item)
        proposals = folder.write("proposals.json", json.dumps(items))
        with Folder() as empty:
            out, err = io.BytesIO(), io.BytesIO()
            code = pv.main([proposals, "--json", "--project-dir", empty.root], out, err)
        self.assertEqual(err.getvalue(), b"")
        return code, json.loads(out.getvalue().decode("utf-8"))

    def test_crlf_and_a_byte_order_mark(self):
        text = ("\ufeff\\section{Results}\r\nThe effect was not just large\r\nbut also steady across the plates "
                "\\cite{lee2020}.\r\n\r\nWe then grew the cells in fresh medium for two days.\r\n")
        with Folder() as folder:
            path = folder.write("crlf.tex", text.encode("utf-8"))
            windows = self.windows(path)
            self.assertEqual(len(windows), 1)
            self.assertIn("\r\n", windows[0]["before"])
            self.assertEqual(windows[0]["families"], ["binary-contrast"])
            code, data = self.verify(folder, windows, ["The effect was large and steady across the plates \\cite{lee2020}."])
            self.assertEqual((code, data["passed"], data["failed"]), (0, 1, 0), data)
            code, data = self.verify(folder, windows, [windows[0]["before"]])
            self.assertEqual(data["results"][0]["failed"], ["no-flag"])

    def test_a_format_option_of_the_detector_and_of_the_verifier(self):
        text = "\\section{Results}\n" + S_CONTRAST[:-1] + " \\cite{lee2020}.\n\nWe then grew the cells in fresh medium for two days.\n"
        after = "The effect was large and steady across the plates."
        with Folder() as folder:
            path = folder.write("chapter.txt", text)
            out, err = io.BytesIO(), io.BytesIO()
            with Folder() as empty:
                code = h.pl.main([path, "--format", "latex", "--windows", "--project-dir", empty.root], out, err)
            self.assertEqual((code, err.getvalue()), (1, b""))
            windows = json.loads(out.getvalue().decode("utf-8"))
            self.assertEqual(len(windows), 1)
            item = dict((k, windows[0][k]) for k in ("id", "file", "start", "end", "before", "families"))
            item.update(after=after, reason="made-up reason")
            proposals = folder.write("proposals.json", json.dumps([item]))
            with Folder() as empty:
                out, err = io.BytesIO(), io.BytesIO()
                self.assertEqual(pv.main([proposals, "--project-dir", empty.root], out, err), 0)
                out, err = io.BytesIO(), io.BytesIO()
                self.assertEqual(pv.main([proposals, "--format", "latex", "--project-dir", empty.root], out, err), 1)
                self.assertIn(b"masked-spans", out.getvalue())

    def test_a_file_that_changed_after_the_detect_step(self):
        text = "\\section{Results}\n" + S_CONTRAST + "\n\nWe then grew the cells in fresh medium for two days.\n"
        with Folder() as folder:
            path = folder.write("changed.tex", text)
            windows = self.windows(path)
            folder.write("changed.tex", text.replace("Results", "Findings of the second run"))
            code, data = self.verify(folder, windows, ["The effect was large and steady across the plates."])
            self.assertEqual(code, 1)
            self.assertEqual(data["results"][0]["failed"], ["exact-before"])

    def test_every_window_of_a_file_verifies_as_it_is(self):
        text = ("\\section{Methods}\n" + S_CONTRAST + " Cells grew in fresh medium. "
                "The study plays a pivotal role in the field.\n\n"
                "Plates dried before the scan. The effect was not just small but also late.\n")
        with Folder() as folder:
            path = folder.write("many.tex", text)
            windows = self.windows(path)
            self.assertEqual(len(windows), 3)
            code, data = self.verify(folder, windows, [w["before"] for w in windows])
            for result in data["results"]:
                self.assertNotIn("exact-before", result["failed"])
                self.assertNotIn("no-overlap", result["failed"])
            self.assertEqual([r["failed"] for r in data["results"]], [["no-flag"]] * 3)

    def test_a_plain_text_file_and_a_markdown_file(self):
        with Folder() as folder:
            for name in ("notes.txt", "notes.md"):
                path = folder.write(name, "# Title\n\n" + S_CONTRAST + " Cells grew in fresh medium.\n")
                windows = self.windows(path)
                self.assertEqual(len(windows), 1, name)
                code, data = self.verify(folder, windows, ["The effect was large and steady across the plates."])
                self.assertEqual((code, data["passed"]), (0, 1), (name, data))


if __name__ == "__main__":
    unittest.main()
