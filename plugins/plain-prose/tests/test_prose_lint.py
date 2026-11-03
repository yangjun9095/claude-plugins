"""Tests for scripts/prose_lint.py. All text is made up.

The tests check these facts.

Hard breaks. A heading line is a sentence of its own. A line that starts with an item or a bibitem
command starts a new sentence. Markdown list markers do the same. A text with no heading line has no
hard break. An environment token ends the sentence before it and starts a new one after it. A math
environment does not break a sentence.

Offsets. A finding keeps the offsets of the original text. The tests put a comment, a command and
math before the finding. They use CRLF line endings, the placeholder characters in the input, and an
unmatched dollar sign. The line and the column count the original text.

Sentence start. A rule with an anchor fires on a sentence that starts with a marker, a comment, a
label or a footnote command. A window starts at the first line that holds prose.

Families. Each family fires on a seeded sentence and stays quiet on a clean one. The seeded and
clean sentences of the pattern tests give the same result in the detector.

Severity. A density family reports info below its threshold and flag above it. A rule with
severity info reports info in an each family. A citation span silences the weasel rules.

Structure. The three structural checks read their params, work inside one paragraph, and stop at
a heading.

Windows. One window for each sentence that holds a flagged finding. Windows are never merged.

Command line. Exit codes, folder expansion, the project file, the text output and the JSON output.
"""
import io
import json
import os
import random
import re
import sys
import time
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import lint_helpers as h  # noqa: E402
import prose_patterns as pp  # noqa: E402
from lint_helpers import Folder, lint, of_family, run_main, run_script, sentences_of  # noqa: E402
from prose_mask import mask  # noqa: E402

pl = h.pl
OPEN, CLOSE = "\ue000", "\ue001"
FIELDS = ("family rule_label tier severity line col start end sentence_start sentence_end text strategy").split()

# (family, text, rule label, tier, severity, text of the first finding of the family).
SEEDED = [
    ("vocabulary-excess", "Here we delve into how Marlin-2 expression changes after heat shock (n = 24 plants).",
     "delve", "T1", "flag", "delve"),
    ("vocabulary-density", "We utilize a standard buffer.", "utilize", "T1", "flag", "utilize"),
    ("figurative-load", "The pipeline is the backbone of our analysis.", "backbone", "T3", "flag", "backbone"),
    ("binary-contrast", "The delay is not an artifact, it is a property of the cell cycle.",
     "is not X, it is Y", "T2", "flag", "is not an artifact, it is"),
    ("importance-puffery", "Marlin-2 played a crucial role in the response.",
     "plays a pivotal role", "T2", "flag", "played a crucial role"),
    ("participial-benefit", "The model was trained on 12,000 images, ensuring reproducibility across sites.",
     "trailing participial clause", "T1", "flag", ", ensuring"),
    ("weasel-attribution", "Studies show that Marlin-2 is expressed in the root.",
     "studies show", "T2", "flag", "Studies show"),
    ("fake-strong-verb", "Tavo serves as a critical checkpoint for growth.",
     "serves as praise", "T2", "flag", "serves as a critical"),
    ("throat-clearing", "It is worth noting that survival fell from 81% to 34% in the mutant.",
     "it is worth noting that", "T2", "flag", "It is worth noting"),
    ("recap-opener", "In conclusion, the mutant grows slowly.", "recap opener", "T2", "flag", "In conclusion,"),
    ("em-dash", "The mutant \u2014 which lacks the C-terminal domain \u2014 grows slowly.",
     "em dash", "T1", "flag", "\u2014"),
    ("colon-reveal", "The answer is simple: the mutant grows slowly.",
     "The X is Y: z", "T3", "flag", "The answer is simple: t"),
    ("assistant-residue", "As an AI language model, I cannot verify these values.",
     "as an AI", "T2", "flag", "As an AI language model"),
    ("hedge-stack", "These data may potentially explain the delay.",
     "modal and adverb", "T3", "flag", "may potentially"),
    ("rhetorical-question",
     "The dose varied across the six treatment groups in this trial. Why does this matter? The answer is the dose.",
     "question_answer", "T3", "flag", "Why does this matter?"),
    ("repeated-openers",
     "This assay failed after the third wash. This sample dried before the scan. This gene rose in every line.",
     "repeated_openers", "T2", "flag", "This gene rose in every line."),
    ("staccato-run", "The gene rose. The cells grew. The plates dried.",
     "staccato", "T2", "flag", "The plates dried."),
]

# A text that is plain for the family of the row, and for the other structural checks.
STRUCTURAL_CLEAN = {
    "rhetorical-question": "The dose varied across the six treatment groups in this trial. Why does this matter? "
                           "Figure 2 shows the dose.",
    "repeated-openers": "This assay failed after the third wash. Our sample dried before the scan. "
                        "The gene rose in every line.",
    "staccato-run": "The gene rose. The cells grew. The plates dried before the scan began.",
}

SEED = dict((row[0], row) for row in SEEDED)
LEAD = "The dose varied across the six treatment groups in this trial. "
THIS = ["This assay failed after the third wash.", "This sample dried before the scan.",
        "This gene rose in every line."]


def texts(findings):
    return [f.text for f in findings]


class HardBreakTests(unittest.TestCase):
    def test_a_sectioning_line_ends_a_sentence(self):
        for command in ("section", "subsection", "subsubsection", "paragraph", "subparagraph", "chapter", "title"):
            for star in ("", "*"):
                with self.subTest(command=command, star=star):
                    heading = "\\%s%s{Introduction}" % (command, star)
                    self.assertEqual(sentences_of(heading + "\nThe gene rose.\n", "latex"),
                                     [heading, "The gene rose."])

    def test_a_heading_line_breaks_at_its_start_and_at_its_end(self):
        masked = mask("Text\n\\section{A}\nMore", "latex")
        self.assertEqual(pl.hard_breaks(masked), [masked.text.index("\n") + 1, masked.text.rindex("\n")])
        masked = mask("Text\r\n\\section{A}\r\nMore", "latex")
        self.assertEqual(pl.hard_breaks(masked), [masked.text.index("\n") + 1, masked.text.rindex("\r")])

    def test_a_heading_after_prose_with_no_end_mark_is_its_own_sentence(self):
        self.assertEqual(sentences_of("The gene rose in the root\n\\section{Results}\nThe cells grew.\n", "latex"),
                         ["The gene rose in the root", "\\section{Results}", "The cells grew."])
        self.assertEqual(sentences_of("The gene rose in the root\n## Results\nThe cells grew.\n", "markdown"),
                         ["The gene rose in the root", "## Results", "The cells grew."])

    def test_the_end_of_a_list_environment_ends_the_last_item(self):
        text = "\\item The cell grew\n\\end{itemize}\nThe plate dried.\n"
        self.assertEqual(sentences_of(text, "latex"), ["\\item The cell grew", "The plate dried."])

    def test_an_environment_token_breaks_before_and_after_the_placeholder(self):
        masked = mask("A\n\\begin{abstract}\nB", "latex")
        self.assertEqual(pl.hard_breaks(masked), [masked.text.index(OPEN), masked.text.index(CLOSE) + 1])

    def test_two_adjacent_environment_tokens_give_one_offset_between_them(self):
        masked = mask("A\n\\end{a}\\begin{b}\nB", "latex")
        found = pl.hard_breaks(masked)
        self.assertEqual(len(found), 3)
        self.assertEqual(found, sorted(set(found)))

    def test_a_begin_figure_splits_two_sentences_of_one_paragraph(self):
        text = "The gene rose in the root\n\\begin{figure}\nThe cells grew.\n"
        self.assertEqual(sentences_of(text, "latex"), ["The gene rose in the root", "The cells grew."])

    def test_an_abstract_starts_its_own_sentence(self):
        text = "Some text without a mark\n\\begin{abstract}\nText.\n"
        self.assertEqual(sentences_of(text, "latex"), ["Some text without a mark", "Text."])

    def test_the_title_of_an_environment_ends_the_sentence_after_it(self):
        text = "\\begin{theorem}[Cauchy's theorem]\nThe cell grew.\n"
        self.assertEqual(sentences_of(text, "latex"), ["\\begin{theorem}[Cauchy's theorem]", "The cell grew."])

    def test_the_arguments_of_an_environment_stay_out_of_the_sentences(self):
        for begin in ("\\begin{figure}[t]", "\\begin{subfigure}[b]{0.45\\textwidth}", "\\begin{minipage}{0.5\\textwidth}",
                      "\\begin{multicols}{2}", "\\begin{wrapfigure}{r}{0.5\\textwidth}", "\\begin{thebibliography}{9}"):
            with self.subTest(begin=begin):
                text = begin + "\nWe delve into the data.\n"
                self.assertEqual(sentences_of(text, "latex"), ["We delve into the data."])
                masked = mask(text, "latex")
                self.assertEqual(pl.hard_breaks(masked), [0, masked.text.index("\n")])

    def test_a_math_environment_does_not_break_a_sentence(self):
        names = ("equation", "align", "gather", "multline", "eqnarray", "displaymath", "math", "split",
                 "subequations", "alignat", "flalign", "dmath", "IEEEeqnarray", "empheq")
        for name in names:
            for star in ("", "*"):
                with self.subTest(name=name, star=star):
                    text = "The rate follows\n\\begin{%s%s}\ny = 2x\n\\end{%s%s}\nwhere $y$ is the rate.\n" % (
                        name, star, name, star)
                    self.assertEqual(pl.hard_breaks(mask(text, "latex")), [])
                    self.assertEqual(sentences_of(text, "latex"), [text.strip()])

    def test_subequations_with_an_equation_inside_stay_in_one_sentence(self):
        text = ("The rate follows\n\\begin{subequations}\n\\begin{equation}\ny = 2x\n\\end{equation}\n"
                "\\end{subequations}\nwhere $y$ is the rate.\n")
        self.assertEqual(pl.hard_breaks(mask(text, "latex")), [])
        self.assertEqual(sentences_of(text, "latex"), [text.strip()])

    def test_other_whole_environments_break_before_and_after(self):
        for name in ("tabular", "tabularx", "longtable", "tikzpicture", "verbatim", "lstlisting", "minted"):
            with self.subTest(name=name):
                text = "Some text without a mark\n\\begin{%s}\ncell\n\\end{%s}\nMore text here.\n" % (name, name)
                self.assertEqual(sentences_of(text, "latex"), ["Some text without a mark", "More text here."])

    def test_other_environment_tokens_break_before_and_after(self):
        for name in ("figure", "abstract", "itemize", "table", "center"):
            with self.subTest(name=name):
                text = "Some text without a mark\n\\begin{%s}\ncell\n\\end{%s}\nMore text here.\n" % (name, name)
                self.assertEqual(sentences_of(text, "latex")[:3], ["Some text without a mark", "cell", "More text here."])

    def test_a_heading_on_the_last_line_breaks_at_the_end_of_the_text(self):
        masked = mask("The gene rose.\n\\section{End}", "latex")
        self.assertEqual(pl.hard_breaks(masked), [len("The gene rose.\n"), len(masked.text)])

    def test_other_commands_and_a_heading_inside_a_line_make_no_break(self):
        for text in ("\\textbf{Note}\nThe gene rose.\n", "The gene rose \\section{Methods}\nThe gene fell.\n",
                     "\\emph{Note}\nThe gene rose.\n", "\\caption{Note}\nThe gene rose.\n",
                     "\\sectionmark{Note}\nThe gene rose.\n", "\\titlepage\nThe gene rose.\n",
                     "\\itemsep 2pt\nThe gene rose.\n", "\\bibitemsep 2pt\nThe gene rose.\n"):
            with self.subTest(text=text):
                self.assertEqual(pl.hard_breaks(mask(text, "latex")), [])
                self.assertEqual(len(sentences_of(text, "latex")), 1)

    def test_an_item_line_starts_a_sentence(self):
        text = "\\begin{itemize}\n\\item First point\n\\item Second point\n\\end{itemize}\n\nThe gene rose.\n"
        self.assertEqual(sentences_of(text, "latex"), ["\\item First point", "\\item Second point", "The gene rose."])

    def test_the_item_break_is_at_the_start_of_the_line(self):
        masked = mask("Intro\n\\item One\n", "latex")
        self.assertEqual(pl.hard_breaks(masked), [masked.text.index("\n") + 1])

    def test_an_indented_item_and_an_item_with_a_label_start_a_sentence(self):
        self.assertEqual(sentences_of("  \\item One\n  \\item[a)] Two\n", "latex"), ["\\item One", "\\item[a)] Two"])

    def test_a_bibitem_line_starts_a_sentence(self):
        text = "\\bibitem{k1} Smith A. First study, 2020.\n\\bibitem{k2} Jones B. Second study, 2021.\n"
        found = sentences_of(text, "latex")
        self.assertEqual(len(found), 2)
        self.assertTrue(found[0].startswith("\\bibitem{k1}"))
        self.assertTrue(found[1].startswith("\\bibitem{k2}"))

    def test_a_markdown_heading_line_ends_a_sentence(self):
        for heading in ("# Title", "## Results", "###### Deep"):
            with self.subTest(heading=heading):
                self.assertEqual(sentences_of(heading + "\nThe gene rose.\n", "markdown"),
                                 [heading, "The gene rose."])

    def test_a_markdown_list_marker_starts_a_sentence(self):
        text = "Intro line without a mark\n- First point\n* Second point\n+ Third point\n1. Fourth point\n2) Fifth point\n"
        self.assertEqual(sentences_of(text, "markdown"),
                         ["Intro line without a mark", "- First point", "* Second point", "+ Third point",
                          "1. Fourth point", "2) Fifth point"])

    def test_markdown_lines_that_are_no_heading_and_no_list_make_no_break(self):
        for text in ("#hashtag is not a heading\nThe gene rose.\n", "---\ntitle: made up\n---\nThe gene rose.\n",
                     "Plain line\nAnother plain line.\n", "*Emphasis* starts this line\nand goes on.\n",
                     "| a | b |\nThe gene rose.\n"):
            with self.subTest(text=text):
                self.assertEqual(pl.hard_breaks(mask(text, "markdown")), [])

    def test_plain_text_has_no_hard_break(self):
        text = "# Title\n- item\n\\section{Intro}\n\\item One\n1. Two\nThe gene rose.\n"
        self.assertEqual(pl.hard_breaks(mask(text, "text")), [])

    def test_text_with_no_heading_lines_has_no_hard_break(self):
        body = h.filler_words(120)
        for fmt in ("latex", "markdown", "text"):
            with self.subTest(fmt=fmt):
                self.assertEqual(pl.hard_breaks(mask(body, fmt)), [])

    def test_crlf_gives_the_same_sentences(self):
        text = "\\section{Introduction}\nIntro line\n\\item One\n\\item Two\n"
        self.assertEqual(sentences_of(text.replace("\n", "\r\n"), "latex"), sentences_of(text, "latex"))
        self.assertEqual(sentences_of(text, "latex"), ["\\section{Introduction}", "Intro line", "\\item One", "\\item Two"])

    def test_a_byte_order_mark_does_not_hide_the_first_heading(self):
        self.assertEqual(sentences_of("\ufeff\\section{Introduction}\nThe gene rose.\n", "latex"),
                         ["\ufeff\\section{Introduction}", "The gene rose."])

    def test_the_offsets_are_sorted_integers(self):
        text = "\\section{A}\n\\item x\n\\subsection{B}\n\\item y\n"
        found = pl.hard_breaks(mask(text, "latex"))
        self.assertEqual(found, sorted(found))
        self.assertTrue(all(isinstance(b, int) for b in found))
        self.assertEqual(len(found), len(set(found)))
        self.assertEqual(len(found), 6)


class MapperTests(unittest.TestCase):
    def setUp(self):
        self.source = "Cost \\cite{ab} here."
        self.masked = mask(self.source, "latex")
        self.mapper = pl.Mapper(self.masked)
        self.first = self.masked.text.index(OPEN)
        self.last = self.masked.text.index(CLOSE) + 1

    def test_the_masked_text_has_one_placeholder(self):
        self.assertEqual((self.first, self.last), (5, 8))

    def test_a_start_inside_a_placeholder_maps_to_the_start_of_the_span(self):
        self.assertEqual([self.mapper.start(p) for p in range(5, 9)], [5, 5, 5, 14])

    def test_an_end_inside_a_placeholder_maps_to_the_end_of_the_span(self):
        self.assertEqual([self.mapper.end(p) for p in range(5, 9)], [5, 14, 14, 14])

    def test_offsets_outside_placeholders_shift_by_the_hidden_text(self):
        self.assertEqual(self.mapper.start(0), 0)
        self.assertEqual(self.mapper.start(9), 15)
        self.assertEqual(self.mapper.end(len(self.masked.text)), len(self.source))

    def test_a_text_without_spans_maps_to_itself(self):
        mapper = pl.Mapper(mask("Plain words here.", "text"))
        self.assertEqual([mapper.start(p) for p in (0, 5, 17)], [0, 5, 17])
        self.assertEqual([mapper.end(p) for p in (0, 5, 17)], [0, 5, 17])


LATEX_SOURCE = (
    "% a comment that says delve\n"
    "\\section{Intro}\n"
    "The sample was small \\cite{a} and $p<0.05$ held. We delve into the data.\n")


class OffsetTests(unittest.TestCase):
    def check_latex(self, source):
        found = lint(source, "latex").findings
        self.assertEqual([f.family for f in found], ["vocabulary-excess"])
        f = found[0]
        start = source.index("We delve") + 3
        self.assertEqual((f.text, f.rule_label), ("delve", "delve"))
        self.assertEqual((f.start, f.end), (start, start + 5))
        self.assertEqual(source[f.start:f.end], "delve")
        self.assertEqual(f.line, 3)
        self.assertEqual(f.col, len("The sample was small \\cite{a} and $p<0.05$ held. We ") + 1)
        self.assertEqual(source[f.sentence_start:f.sentence_end], "We delve into the data.")

    def test_offsets_with_a_command_a_comment_and_math_before_the_hit(self):
        self.check_latex(LATEX_SOURCE)

    def test_offsets_with_crlf_line_endings(self):
        self.check_latex(LATEX_SOURCE.replace("\n", "\r\n"))

    def test_a_line_ends_at_a_line_feed_only(self):
        source = "Page one\fPage two\u2028still line one\r\nWe delve into the data.\n"
        f = lint(source, "text").findings[0]
        self.assertEqual((f.line, f.col), (2, 4))
        self.assertEqual(source[f.start:f.end], "delve")

    def test_lines_and_columns_count_characters(self):
        source = "Caf\u00e9 \u00fcber alles.\nR\u00e9sum\u00e9: we delve into the data.\n"
        f = lint(source, "text").findings[0]
        self.assertEqual((f.line, f.col), (2, len("R\u00e9sum\u00e9: we ") + 1))
        self.assertEqual(source[f.start:f.end], "delve")

    def test_offsets_in_markdown_with_a_comment_code_and_a_link_target_before_the_hit(self):
        source = ("<!-- delve -->\n\n## Methods\n\nSee [the page](http://delve.example/x) and `delve` here. "
                  "We delve into the data.\n")
        found = lint(source, "markdown").findings
        self.assertEqual([f.text for f in found], ["delve"])
        self.assertEqual(source[found[0].start:found[0].end], "delve")
        self.assertEqual(source[found[0].sentence_start:found[0].sentence_end], "We delve into the data.")
        self.assertEqual(found[0].line, 5)
        self.assertEqual(found[0].col, source.split("\n")[4].index("We delve") + 4)

    def test_a_match_that_covers_a_placeholder_includes_the_hidden_text(self):
        source = "We found one reason: \\cite{smith} for this.\n"
        found = of_family(lint(source, "latex"), "colon-reveal")
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0].text, "We found one reason: \\cite{smith}")
        self.assertEqual((found[0].start, found[0].end), (0, len("We found one reason: \\cite{smith}")))

    def test_the_text_of_a_finding_is_the_slice_of_the_original(self):
        for source, fmt in ((LATEX_SOURCE, "latex"), (LATEX_SOURCE.replace("\n", "\r\n"), "latex"),
                            ("We delve \u2014 and we utilize \u2014 the data.\n", "text")):
            found = lint(source, fmt).findings
            self.assertTrue(found, source)
            for f in found:
                self.assertEqual(f.text, source[f.start:f.end])
                self.assertLessEqual(f.sentence_start, f.start)
                self.assertLessEqual(f.end, f.sentence_end)

    def test_findings_come_in_the_order_of_the_text(self):
        source = "We utilize it. Interestingly, we delve in. The pipeline is the backbone of the plan.\n"
        found = lint(source, "text").findings
        self.assertGreaterEqual(len(found), 3)
        self.assertEqual([f.start for f in found], sorted(f.start for f in found))

    def test_a_file_that_holds_the_placeholder_characters(self):
        for source in ("Alpha \ue000 beta. We delve into the data.\n",
                       "The \ue0000\ue001 value was low. We delve into the data.\n",
                       "\ue001\ue000 We delve into the data.\n"):
            for fmt in ("text", "latex", "markdown"):
                with self.subTest(source=source, fmt=fmt):
                    found = lint(source, fmt).findings
                    self.assertEqual([f.text for f in found], ["delve"])
                    self.assertEqual(source[found[0].start:found[0].end], "delve")
                    self.assertEqual(found[0].line, 1)

    def test_an_unmatched_dollar_sign_does_not_break_the_next_paragraph(self):
        source = "Cost is $5 here and nothing else.\n\nWe delve into the data.\n"
        found = lint(source, "latex").findings
        self.assertEqual([f.text for f in found], ["delve"])
        self.assertEqual(source[found[0].start:found[0].end], "delve")
        self.assertEqual(found[0].line, 3)

    def test_unbalanced_braces_and_an_unknown_command_do_not_raise(self):
        for source, expected in (("\\foo{bar {baz\n\nWe delve into the data.\n", ["delve"]),
                                 ("\\unknown{We delve here}\n\nPlain text.\n", []),
                                 ("\\begin{verbatim}\nWe delve here\n", [])):
            with self.subTest(source=source):
                found = lint(source, "latex").findings
                self.assertEqual([f.text for f in found], expected)
                for f in found:
                    self.assertEqual(f.text, source[f.start:f.end])

    def test_sentence_bounds_lie_on_the_original_text(self):
        source = "\\section{Intro}\nThe sample was small \\cite{a}. We delve into the data \\cite{b}.\n"
        f = lint(source, "latex").findings[0]
        self.assertEqual(source[f.sentence_start:f.sentence_end], "We delve into the data \\cite{b}.")


class FamilyTests(unittest.TestCase):
    def test_the_detector_has_one_function_for_each_check_of_the_data(self):
        self.assertEqual(sorted(pl._CHECKS), sorted(pp.CHECKS))

    def test_every_family_has_a_seeded_sentence(self):
        self.assertEqual(sorted(row[0] for row in SEEDED), sorted(f.id for f in h.PATTERNS.families))

    def test_each_family_fires_on_its_seeded_sentence(self):
        for family, text, label, tier, severity, hit in SEEDED:
            with self.subTest(family=family):
                found = of_family(lint(text), family)
                self.assertTrue(found, family)
                first = found[0]
                self.assertEqual((first.rule_label, first.tier, first.severity, first.text),
                                 (label, tier, severity, hit))
                self.assertEqual(first.strategy, h.PATTERNS.family(family).strategy)
                self.assertEqual(text[first.start:first.end], hit)

    def test_each_regex_family_stays_quiet_on_its_clean_sentence(self):
        for family, text in sorted(h.FAMILY_CLEAN.items()):
            with self.subTest(family=family):
                self.assertEqual(of_family(lint(text), family), [])

    def test_each_structural_family_stays_quiet_on_its_clean_text(self):
        for family, text in sorted(STRUCTURAL_CLEAN.items()):
            with self.subTest(family=family):
                self.assertEqual(of_family(lint(text), family), [])

    def test_a_structural_finding_has_the_sentence_as_its_text_and_bounds(self):
        text = SEED["repeated-openers"][1]
        f = of_family(lint(text), "repeated-openers")[0]
        self.assertEqual((f.start, f.end), (f.sentence_start, f.sentence_end))
        self.assertEqual(f.text, THIS[2])
        self.assertEqual(text[f.start:f.end], THIS[2])

    def test_every_seeded_sentence_of_the_pattern_tests_is_found(self):
        for family, label, sentence in h.FIRES:
            with self.subTest(family=family, label=label, sentence=sentence):
                found = [(f.family, f.rule_label) for f in lint(sentence).findings]
                self.assertIn((family, label), found)

    def test_a_plain_sentence_of_the_pattern_tests_gives_no_finding(self):
        for sentence in h.CLEAN:
            with self.subTest(sentence=sentence):
                self.assertEqual(lint(sentence).findings, [])

    def test_the_plain_filler_gives_no_finding(self):
        for fmt in ("text", "latex", "markdown"):
            with self.subTest(fmt=fmt):
                self.assertEqual(lint(h.filler_words(1500), fmt).findings, [])

    def test_a_family_that_the_project_file_switches_off_does_not_run(self):
        patterns = pp.apply_project(h.PATTERNS, {"families": {"vocabulary-excess": {"enabled": False}}})
        self.assertEqual(lint("We delve into the data.", "text", patterns).findings, [])
        self.assertEqual(len(lint("We delve into the data.", "text").findings), 1)

    def test_a_disabled_rule_does_not_fire(self):
        patterns = pp.apply_project(h.PATTERNS, {"families": {"vocabulary-density": {"disable_labels": ["utilize"]}}})
        self.assertEqual(lint("We utilize a standard buffer.", "text", patterns).findings, [])

    def test_a_placeholder_name_does_not_end_in_an_underscore(self):
        source = "Dear INSERT_NAME_\n"
        found = [f for f in lint(source).findings if f.rule_label == "placeholder"]
        self.assertEqual([(f.text, f.start, f.end, f.line, f.col) for f in found], [("INSERT_NAME", 5, 16, 1, 6)])
        for name in ("INSERT_FIRST_NAME", "INSERT_A1_B2", "INSERT_X"):
            with self.subTest(name=name):
                found = [f for f in lint("Dear %s.\n" % name).findings if f.rule_label == "placeholder"]
                self.assertEqual([f.text for f in found], [name])
        self.assertEqual([f for f in lint("Dear INSERT_ and INSERT__X.\n").findings if f.rule_label == "placeholder"], [])

    def test_a_match_with_no_length_gives_no_finding(self):
        # The loader refuses a regex that matches "". This one matches "" only between an a and a b.
        extra = {"extra_patterns": [{"id": "probe", "title": "Probe", "regex": "(?<=a)(?=b)", "strategy": "Fix it."}]}
        patterns = pp.apply_project(h.PATTERNS, extra)
        self.assertEqual(lint("We see ab here today.", "text", patterns).findings, [])

    def test_two_hits_of_one_rule_in_a_sentence_give_two_findings(self):
        found = of_family(lint(SEED["em-dash"][1]), "em-dash")
        self.assertEqual([f.text for f in found], ["\u2014", "\u2014"])
        self.assertEqual(len(set(f.sentence_start for f in found)), 1)

    def test_the_findings_of_several_families_on_one_sentence_are_all_kept(self):
        found = lint("Interestingly, we delve into the data.").findings
        self.assertEqual(sorted(set(f.family for f in found)), ["throat-clearing", "vocabulary-excess"])


class SeverityTests(unittest.TestCase):
    def test_one_em_dash_in_500_words_is_info(self):
        result = lint(h.padded(500, [h.EM_SENTENCE]))
        self.assertEqual(result.words, 500)
        found = of_family(result, "em-dash")
        self.assertEqual([f.severity for f in found], ["info"])
        self.assertEqual(result.density["em-dash"], 2.0)

    def test_five_em_dashes_in_500_words_are_flags(self):
        result = lint(h.padded(500, [h.EM_SENTENCE] * 5))
        self.assertEqual(result.words, 500)
        found = of_family(result, "em-dash")
        self.assertEqual([f.severity for f in found], ["flag"] * 5)
        self.assertEqual(result.density["em-dash"], 10.0)

    def test_the_threshold_itself_is_info_and_one_hit_more_is_flag(self):
        at = lint(h.padded(2000, [h.EM_SENTENCE] * 5))
        self.assertEqual(at.density["em-dash"], 2.5)
        self.assertEqual(set(f.severity for f in of_family(at, "em-dash")), {"info"})
        over = lint(h.padded(2000, [h.EM_SENTENCE] * 6))
        self.assertEqual(set(f.severity for f in of_family(over, "em-dash")), {"flag"})

    def test_the_density_is_the_hits_per_1000_words(self):
        result = lint(h.padded(800, [h.EM_SENTENCE] * 3))
        self.assertEqual(result.words, 800)
        self.assertAlmostEqual(result.density["em-dash"], 3 / 800 * 1000)

    def test_the_density_holds_every_family_with_a_hit_and_no_other(self):
        result = lint(h.padded(500, [h.EM_SENTENCE, "We delve into the data.",
                                     "The tank was drained daily, allowing fresh medium to enter."]))
        self.assertEqual(sorted(result.density), ["em-dash", "participial-benefit", "vocabulary-excess"])

    def test_an_info_finding_counts_toward_the_density_of_its_family(self):
        patterns = pp.apply_project(h.PATTERNS, {"families": {"binary-contrast": {"mode": "density", "max_per_1000": 3}}})
        extras = ["The assay captures not only growth but also death in each line.",
                  "The delay is not an artifact, it is a property of the cell cycle."]
        result = lint(h.padded(500, extras), "text", patterns)
        found = of_family(result, "binary-contrast")
        self.assertEqual([(f.rule_label, f.severity) for f in found],
                         [("not only X but also Y", "info"), ("is not X, it is Y", "flag")])
        self.assertEqual(result.density["binary-contrast"], 4.0)

    def test_the_density_counts_each_hit_and_not_each_sentence(self):
        result = lint(h.padded(500, ["The mutant \u2014 which lacks the domain \u2014 grows slowly."]))
        self.assertEqual(result.density["em-dash"], 4.0)
        self.assertEqual([f.severity for f in of_family(result, "em-dash")], ["flag", "flag"])

    def test_the_hits_of_an_info_family_count_toward_the_density(self):
        extras = ["The tank was drained daily, allowing fresh medium to enter."] * 3
        result = lint(h.padded(500, extras))
        self.assertEqual(result.density["participial-benefit"], 6.0)

    def test_a_file_with_no_word_has_density_zero_and_no_division(self):
        # U+0663 is an Arabic-Indic digit. It makes a sentence, and it is no word.
        result = lint("\u0663 \u2014 \u0663\n")
        self.assertEqual(result.words, 0)
        self.assertEqual(result.density, {"em-dash": 0.0})
        self.assertEqual([f.severity for f in result.findings], ["info"])

    def test_an_empty_text_gives_nothing(self):
        for fmt in ("text", "latex", "markdown"):
            for source in ("", "\n", "  \r\n\r\n"):
                with self.subTest(fmt=fmt, source=source):
                    result = lint(source, fmt)
                    self.assertEqual((result.findings, result.words, result.density), ([], 0, {}))

    def test_a_flag_in_an_each_family_stays_a_flag_in_a_long_text(self):
        result = lint(h.padded(2000, ["We delve into the data."]))
        self.assertEqual([f.severity for f in of_family(result, "vocabulary-excess")], ["flag"])

    def test_a_rule_with_severity_info_reports_info_in_an_each_family(self):
        text = "The tank was drained daily, allowing fresh medium to enter."
        found = lint(text).findings
        self.assertEqual([(f.family, f.rule_label, f.severity) for f in found],
                         [("participial-benefit", "mild participial clause", "info")])
        self.assertEqual(pl.windows(found, text, "a.txt"), [])

    def test_a_rule_with_severity_info_never_becomes_a_flag_in_a_density_family(self):
        family = pp.Family("probe", "Probe", "density", 1, "Fix it.", False, rules=[
            pp.Rule("T3", ["authors:S1"], "probe", re.compile(r"\bzorb\b"), severity="info")])
        patterns = pp.Patterns([family], "2026-10-23")
        found = lint("We zorb the data.", "text", patterns).findings
        self.assertEqual([f.severity for f in found], ["info"])

    def test_a_density_family_flags_above_the_threshold_of_the_project_file(self):
        patterns = pp.apply_project(h.PATTERNS, {"families": {"em-dash": {"max_per_1000": 500}}})
        result = lint(h.EM_SENTENCE, "text", patterns)
        self.assertEqual([f.severity for f in result.findings], ["info"])
        self.assertEqual([f.severity for f in lint(h.EM_SENTENCE).findings], ["flag"])

    def test_the_mode_of_the_project_file_changes_the_severity(self):
        patterns = pp.apply_project(h.PATTERNS, {"families": {"vocabulary-excess": {"mode": "density",
                                                                                      "max_per_1000": 1000}}})
        found = lint("We delve into the data.", "text", patterns).findings
        self.assertEqual([f.severity for f in found], ["info"])


class WeaselTests(unittest.TestCase):
    def test_a_claim_with_no_source_flags(self):
        found = of_family(lint("Studies show that X improves Y.", "latex"), "weasel-attribution")
        self.assertEqual([f.text for f in found], ["Studies show"])

    def test_a_cite_command_silences_it(self):
        self.assertEqual(of_family(lint("Studies show that X improves Y \\cite{a}.", "latex"), "weasel-attribution"), [])

    def test_a_numeric_citation_silences_it_in_text_and_markdown(self):
        for fmt in ("text", "markdown"):
            with self.subTest(fmt=fmt):
                self.assertEqual(of_family(lint("Studies show that X improves Y [12].", fmt), "weasel-attribution"), [])

    def test_an_author_year_citation_silences_it(self):
        text = "Studies show that X improves Y (Smith et al., 2020)."
        self.assertEqual(of_family(lint(text, "text"), "weasel-attribution"), [])

    def test_the_other_citation_commands_and_the_pandoc_form_silence_it(self):
        for source, fmt in (("Studies show that dose improves growth \\citealp{a}.", "latex"),
                            ("Studies show that dose improves growth \\citealt{a}.", "latex"),
                            ("Studies show that dose improves growth \\footcite{a}.", "latex"),
                            ("Studies show that dose improves growth \\citeyearpar{a}.", "latex"),
                            ("Studies show that dose improves growth \\citenum{a}.", "latex"),
                            ("Studies show that dose improves growth \\cites{a}{b}.", "latex"),
                            ("Studies show that dose improves growth \\parencites{a}{b}.", "latex"),
                            ("Studies show that dose improves growth \\Textcite{a}.", "latex"),
                            ("Studies show that dose improves growth \\citetitle{a}.", "latex"),
                            ("Studies show that dose improves growth [@a].", "markdown"),
                            ("Studies show that dose improves growth [@a; @b].", "markdown"),
                            ("Studies show that dose improves growth [@a, p. 3].", "markdown"),
                            ("Studies show that dose improves growth [see @a].", "markdown"),
                            ("Studies show that dose improves growth [-@a].", "markdown"),
                            ("Studies show that dose improves growth [@a; see @b].", "markdown")):
            with self.subTest(source=source):
                self.assertEqual(of_family(lint(source, fmt), "weasel-attribution"), [])
        self.assertEqual(len(of_family(lint("Studies show that dose improves growth [a].", "markdown"), "weasel-attribution")), 1)

    def test_a_citation_among_other_spans_silences_it(self):
        text = "Studies show that $x$ improves growth \\cite{a} when $p$ is small."
        self.assertEqual(of_family(lint(text, "latex"), "weasel-attribution"), [])

    def test_a_citation_in_the_next_sentence_does_not_silence_it(self):
        found = of_family(lint("Studies show that dose improves growth. See [12].", "text"), "weasel-attribution")
        self.assertEqual(len(found), 1)

    def test_a_span_that_is_no_citation_does_not_silence_it(self):
        for source, fmt in (("Studies show that $x$ improves Y.", "latex"),
                            ("Studies show that X improves Y, see Figure \\ref{f}.", "latex"),
                            ("Studies show that X improves `Y`.", "markdown"),
                            ("Studies show that X improves Y (see http://example.org/a).", "text")):
            with self.subTest(source=source):
                self.assertEqual(len(of_family(lint(source, fmt), "weasel-attribution")), 1)

    def test_the_same_sentence_without_the_citation_flags_in_text(self):
        self.assertEqual(len(of_family(lint("Studies show that X improves Y.", "text"), "weasel-attribution")), 1)


class QuestionTests(unittest.TestCase):
    def found(self, text, fmt="text", patterns=None):
        return of_family(lint(text, fmt, patterns), "rhetorical-question")

    def test_a_question_that_the_next_sentence_answers_flags_the_question(self):
        found = self.found(LEAD + "Why does this matter? The answer is the dose.")
        self.assertEqual(texts(found), ["Why does this matter?"])
        self.assertEqual(found[0].severity, "flag")

    def test_an_answer_that_starts_with_we_flags_the_question(self):
        self.assertEqual(texts(self.found(LEAD + "How was the dose set? We used 5 mg.")), ["How was the dose set?"])

    def test_every_answer_word_of_the_data_flags(self):
        answers = h.PATTERNS.family("rhetorical-question").params["answers"]
        for word in answers:
            with self.subTest(word=word):
                found = self.found(LEAD + "How was the dose set? %s was the plan." % word.capitalize())
                self.assertEqual(len(found), 1)

    def test_a_question_followed_by_a_figure_reference_is_quiet(self):
        self.assertEqual(self.found(LEAD + "How was the dose set? Figure 2 shows the plan."), [])

    def test_a_question_that_ends_a_paragraph_is_quiet(self):
        self.assertEqual(self.found(LEAD + "Why does this matter?"), [])
        self.assertEqual(self.found(LEAD + "Why does this matter?\n\nThe answer is the dose."), [])

    def test_a_question_that_opens_its_paragraph_is_quiet_even_before_the_word_the(self):
        self.assertEqual(self.found("Why does this matter? The answer is the dose."), [])
        self.assertEqual(self.found(LEAD + "\n\nWhy does this matter? The answer is the dose."), [])

    def test_a_question_after_a_heading_opens_its_paragraph(self):
        self.assertEqual(self.found("\\section{Dose}\nWhy does this matter? The answer is the dose.\n", "latex"), [])
        self.assertEqual(self.found("## Dose\nWhy does this matter? The answer is the dose.\n", "markdown"), [])

    def test_the_param_skip_paragraph_start_false_flags_an_opening_question(self):
        patterns = h.patched("rhetorical-question", params={"skip_paragraph_start": False})
        found = self.found("Why does this matter? The answer is the dose.", patterns=patterns)
        self.assertEqual(texts(found), ["Why does this matter?"])

    def test_the_param_answers_decides_the_answer_words(self):
        patterns = h.patched("rhetorical-question", params={"answers": ["figure"]})
        self.assertEqual(len(self.found(LEAD + "How was the dose set? Figure 2 shows the plan.", patterns=patterns)), 1)
        self.assertEqual(self.found(LEAD + "How was the dose set? We used 5 mg.", patterns=patterns), [])

    def test_the_case_of_an_answer_word_does_not_matter(self):
        patterns = h.patched("rhetorical-question", params={"answers": ["We"]})
        self.assertEqual(len(self.found(LEAD + "How was the dose set? We used 5 mg.", patterns=patterns)), 1)

    def test_a_statement_before_an_answer_word_is_quiet(self):
        self.assertEqual(self.found(LEAD + "The dose was set. We used 5 mg."), [])

    def test_a_question_with_a_closing_quote_or_bracket_still_counts(self):
        self.assertEqual(len(self.found(LEAD + '"Why does this matter?" The answer is the dose.')), 1)
        self.assertEqual(len(self.found(LEAD + "(Why does this matter?) The answer is the dose.")), 1)

    def test_an_answer_that_starts_with_an_emphasis_command_counts(self):
        found = self.found(LEAD + "How was the dose set? \\textbf{We} used 5 mg.", "latex")
        self.assertEqual(len(found), 1)


class OpenerTests(unittest.TestCase):
    def found(self, text, fmt="text", patterns=None):
        return of_family(lint(text, fmt, patterns), "repeated-openers")

    def test_three_sentences_that_start_with_this_flag_the_third(self):
        found = self.found(" ".join(THIS))
        self.assertEqual(texts(found), [THIS[2]])

    def test_each_sentence_after_the_third_flags_too(self):
        found = self.found(" ".join(THIS + ["This line held at noon today."]))
        self.assertEqual(texts(found), [THIS[2], "This line held at noon today."])

    def test_two_sentences_do_not_flag(self):
        self.assertEqual(self.found(" ".join(THIS[:2])), [])

    def test_three_sentences_that_start_with_we_and_differ_after_it_do_not_flag(self):
        text = "We grew the cells for two days. We washed the plates twice. We read the signal at noon."
        self.assertEqual(self.found(text), [])

    def test_three_sentences_that_start_with_the_assay_flag(self):
        text = ("The assay failed after the third wash. The assay dried before the scan. "
                "The assay rose in every line.")
        self.assertEqual(texts(self.found(text)), ["The assay rose in every line."])

    def test_three_sentences_that_start_with_the_and_differ_after_it_do_not_flag(self):
        text = "The cells grew in warm broth. The medium ran low after a day. The plates dried before the scan."
        self.assertEqual(self.found(text), [])

    def test_the_case_of_the_first_word_does_not_matter(self):
        text = "This assay failed after the third wash. THIS sample dried before the scan. This gene rose in every line."
        self.assertEqual(len(self.found(text)), 1)

    def test_a_paragraph_break_ends_the_run(self):
        self.assertEqual(self.found(" ".join(THIS[:2]) + "\n\n" + THIS[2]), [])

    def test_a_heading_ends_the_paragraph_and_the_run(self):
        text = "\\section{This works.}\n" + " ".join(THIS[:2]) + "\n"
        self.assertEqual(self.found(text, "latex"), [])
        self.assertEqual(self.found("# This works.\n" + " ".join(THIS[:2]) + "\n", "markdown"), [])

    def test_a_different_opener_ends_the_run(self):
        text = " ".join([THIS[0], THIS[1], "Our gene rose in every line.", THIS[2]])
        self.assertEqual(self.found(text), [])

    def test_the_param_ignored_compare_words_sets_the_number_of_words(self):
        text = "The cells grew in warm broth. The medium ran low after a day. The plates dried before the scan."
        one = h.patched("repeated-openers", params={"ignored_compare_words": 1})
        self.assertEqual(texts(self.found(text, patterns=one)), ["The plates dried before the scan."])
        same = ("The assay failed after the third wash. The assay failed before the scan. "
                "The assay rose in every line.")
        self.assertEqual(len(self.found(same)), 1)
        three = h.patched("repeated-openers", params={"ignored_compare_words": 3})
        self.assertEqual(self.found(same, patterns=three), [])

    def test_the_param_ignore_lists_the_words_that_compare_by_more_than_one_word(self):
        text = " ".join(["We grew the cells for two days.", "We washed the plates twice.", "We read the signal at noon."])
        patterns = h.patched("repeated-openers", params={"ignore": []})
        self.assertEqual(len(self.found(text, patterns=patterns)), 1)

    def test_the_param_run_sets_the_length_of_the_run(self):
        patterns = h.patched("repeated-openers", params={"run": 2})
        self.assertEqual(texts(self.found(" ".join(THIS[:2]), patterns=patterns)), [THIS[1]])
        patterns = h.patched("repeated-openers", params={"run": 4})
        self.assertEqual(self.found(" ".join(THIS), patterns=patterns), [])

    def test_a_sentence_that_starts_with_an_emphasis_command_has_the_opener_inside_it(self):
        text = "\\emph{This} assay failed after the third wash. This sample dried before the scan. " \
               "\\textbf{This} gene rose in every line."
        self.assertEqual(len(self.found(text, "latex")), 1)


class StaccatoTests(unittest.TestCase):
    def found(self, text, fmt="text", patterns=None):
        return of_family(lint(text, fmt, patterns), "staccato-run")

    def test_three_sentences_of_four_words_flag_the_third(self):
        found = self.found("The gene rose fast. The cells grew well. The plates dried out.")
        self.assertEqual(texts(found), ["The plates dried out."])

    def test_two_sentences_do_not_flag(self):
        self.assertEqual(self.found("The gene rose fast. The cells grew well. " + h.FILLER[0]), [])
        self.assertEqual(self.found("The gene rose fast. The cells grew well."), [])

    def test_five_words_flag_and_six_do_not(self):
        five = "The gene rose very fast. The cells grew very well. The plates dried very slowly."
        six = "The gene rose very fast today. The cells grew very well today. The plates dried very slowly today."
        self.assertEqual(len(self.found(five)), 1)
        self.assertEqual(self.found(six), [])

    def test_a_longer_run_gives_one_finding_at_the_third_sentence(self):
        text = "The gene rose fast. The cells grew well. The plates dried out. Our mice ate less."
        self.assertEqual(texts(self.found(text)), ["The plates dried out."])

    def test_a_long_sentence_breaks_the_run(self):
        text = "The gene rose fast. The cells grew well. " + h.FILLER[0] + " The plates dried out."
        self.assertEqual(self.found(text), [])

    def test_a_paragraph_break_ends_the_run(self):
        self.assertEqual(self.found("The gene rose fast. The cells grew well.\n\nThe plates dried out."), [])

    def test_a_heading_ends_the_paragraph_and_the_run(self):
        text = "\\section{Next}\nThe gene rose fast. The cells grew well.\n"
        self.assertEqual(self.found(text, "latex"), [])
        self.assertEqual(self.found("# Next\nThe gene rose fast. The cells grew well.\n", "markdown"), [])

    def test_a_sentence_with_no_word_breaks_the_run(self):
        # U+0663 is an Arabic-Indic digit. The text splitter keeps it as a sentence, and it holds no word.
        text = "The gene rose fast. The cells grew well. \u0663. The plates dried out."
        self.assertEqual(self.found(text), [])

    def test_a_caption_gives_no_finding_and_a_plain_paragraph_does(self):
        caption = "\\caption{Tavo in roots. Scale bar, 10 \\textmu m. Data are mean.}"
        plain = "Tavo in roots. Scale bar, 10 \\textmu m. Data are mean."
        self.assertEqual(self.found("\\begin{figure}\n" + caption + "\n\\end{figure}\n", "latex"), [])
        self.assertEqual(self.found(caption + "\n", "latex"), [])
        self.assertEqual(self.found("\\begin{figure}\n\\centering\n" + caption + "\n\\end{figure}\n", "latex"), [])
        self.assertEqual(len(self.found(plain + "\n", "latex")), 1)
        self.assertEqual(len(self.found("\\begin{figure}\n\\centering\n" + plain + "\n\\end{figure}\n", "latex")), 1)

    def test_a_paragraph_that_starts_with_another_command_still_flags(self):
        text = "\\textbf{Tavo} in roots. Scale bar, 10 \\textmu m. Data are mean.\n"
        self.assertEqual(len(self.found(text, "latex")), 1)

    def test_a_subfigure_caption_gives_no_finding(self):
        text = ("\\begin{subfigure}[b]{0.45\\textwidth}\n\\centering\n"
                "\\caption{Tavo in roots. Scale bar, 10 \\textmu m. Data are mean.}\n\\end{subfigure}\n")
        self.assertEqual(self.found(text, "latex"), [])

    def test_a_caption_in_the_middle_of_a_paragraph_does_not_switch_the_check_off(self):
        text = "Tavo in roots. Scale bar, 10 \\textmu m.\n\\caption{Data are mean.}\n"
        self.assertEqual(len(self.found(text, "latex")), 1)

    def test_a_command_is_no_word(self):
        text = ("The gene rose very fast \\cite{a}. The cells grew very well \\cite{b}. "
                "The plates dried very slowly \\cite{c}.")
        self.assertEqual(len(self.found(text, "latex")), 1)

    def test_the_param_max_words_sets_the_length(self):
        six = "The gene rose very fast today. The cells grew very well today. The plates dried very slowly today."
        patterns = h.patched("staccato-run", params={"max_words": 6})
        self.assertEqual(len(self.found(six, patterns=patterns)), 1)

    def test_the_param_run_sets_the_length_of_the_run(self):
        patterns = h.patched("staccato-run", params={"run": 2})
        self.assertEqual(texts(self.found("The gene rose fast. The cells grew well.", patterns=patterns)),
                         ["The cells grew well."])
        patterns = h.patched("staccato-run", params={"run": 4})
        self.assertEqual(self.found("The gene rose fast. The cells grew well. The plates dried out.", patterns=patterns), [])


class LeadingSpanTests(unittest.TestCase):
    RECAP = "Overall, these data suggest that Marlin-2 limits root growth."
    # (format, text before the sentence, text after it). A footnote holds the sentence itself.
    MARKERS = [("latex", "\\item ", ""), ("markdown", "- ", ""), ("markdown", "1. ", ""), ("latex", "% note\n", ""),
               ("latex", "\\label{a}\n", ""), ("markdown", "<!-- n -->\n", ""), ("latex", "\\footnote{", "}"),
               ("latex", "\\item\n", "")]
    # Markdown marks that wrap or open a sentence and stay visible.
    WRAPS = [("> ", ""), ("**", "**"), ("*", "*"), ("_", "_"), ("> > ", ""), ("> **", "**")]

    def check_recap(self, source, fmt):
        found = of_family(lint(source, fmt), "recap-opener")
        self.assertEqual(len(found), 1)
        f, start = found[0], source.index("Overall,")
        self.assertEqual((f.text, f.start, f.end), ("Overall,", start, start + len("Overall,")))
        self.assertEqual(f.line, source.count("\n", 0, start) + 1)
        self.assertEqual(f.col, start - source.rfind("\n", 0, start))

    def test_an_opener_rule_fires_after_each_marker_with_exact_offsets(self):
        for fmt, prefix, suffix in self.MARKERS:
            with self.subTest(prefix=prefix):
                self.check_recap(prefix + self.RECAP + suffix + "\n", fmt)

    def test_an_opener_rule_fires_inside_quotes_and_emphasis(self):
        for prefix, suffix in self.WRAPS:
            with self.subTest(prefix=prefix):
                self.check_recap(prefix + self.RECAP + suffix + "\n", "markdown")

    def test_an_opener_rule_fires_in_the_second_sentence_after_a_bold_lead_in(self):
        self.check_recap("**Note.** " + self.RECAP + "\n", "markdown")

    def test_every_seeded_sentence_fires_inside_quotes_and_emphasis(self):
        for prefix, suffix in self.WRAPS:
            for family, label, sentence in h.FIRES:
                with self.subTest(prefix=prefix, family=family, label=label, sentence=sentence):
                    found = [(f.family, f.rule_label) for f in lint(prefix + sentence + suffix + "\n", "markdown").findings]
                    self.assertIn((family, label), found)

    def test_a_word_rule_after_an_underscore_keeps_its_boundary(self):
        source = "_Delve into the data._\n"
        found = lint(source, "markdown").findings
        self.assertEqual([(f.text, f.start, f.line, f.col) for f in found], [("Delve", 1, 1, 2)])

    def test_a_rule_that_ends_at_the_end_of_the_sentence_fires_before_a_closing_mark(self):
        for source, fmt in (("**Not a technical artifact.**\n", "markdown"), ("_Not a technical artifact._\n", "markdown"),
                            ("\\footnote{Not a technical artifact.}\n", "latex"),
                            ("\\emph{Not a technical artifact.}\n", "latex")):
            with self.subTest(source=source):
                found = [f for f in lint(source, fmt).findings if f.family == "binary-contrast"]
                self.assertEqual([f.text for f in found], ["Not a technical artifact."])
                self.assertEqual(source[found[0].start:found[0].end], "Not a technical artifact.")

    def test_a_colon_reveal_after_an_item_marker_fires(self):
        source = "\\item The answer is simple: the mutant grows slowly.\n"
        found = of_family(lint(source, "latex"), "colon-reveal")
        self.assertEqual([f.text for f in found], ["The answer is simple: t"])
        self.assertEqual(found[0].col, len("\\item ") + 1)

    def test_every_seeded_sentence_fires_after_each_marker(self):
        # LaTeX reads a percent sign as a comment and hides the closing brace of a footnote after it.
        # So a seeded sentence with a percent sign is a Markdown test only.
        for fmt, prefix, suffix in self.MARKERS:
            for family, label, sentence in h.FIRES:
                if fmt == "latex" and "%" in sentence:
                    continue
                with self.subTest(prefix=prefix, family=family, label=label, sentence=sentence):
                    found = [(f.family, f.rule_label) for f in lint(prefix + sentence + suffix + "\n", fmt).findings]
                    self.assertIn((family, label), found)

    def test_a_byte_order_mark_before_the_first_sentence_does_not_hide_an_opener(self):
        source = "\ufeff" + self.RECAP + "\n"
        found = of_family(lint(source, "text"), "recap-opener")
        self.assertEqual([(f.text, f.start, f.end, f.line, f.col) for f in found],
                         [("Overall,", 1, 1 + len("Overall,"), 1, 2)])
        found = of_family(lint(source, "latex"), "recap-opener")
        self.assertEqual([f.start for f in found], [1])

    def test_a_rule_that_needs_the_start_of_a_sentence_still_stops_inside_one(self):
        source = "\\item We said so. Then, overall, the data held.\n"
        self.assertEqual(of_family(lint(source, "latex"), "recap-opener"), [])

    def test_a_marker_in_the_middle_of_a_sentence_does_not_move_the_start(self):
        source = "The data held, overall \\cite{a}, Overall, in the end.\n"
        self.assertEqual(of_family(lint(source, "latex"), "recap-opener"), [])

    def test_the_offsets_stay_exact_with_crlf_after_a_comment_line(self):
        source = "% note\r\n\\label{a}\r\n" + self.RECAP + "\r\n"
        f = of_family(lint(source, "latex"), "recap-opener")[0]
        self.assertEqual((f.line, f.col, source[f.start:f.end]), (3, 1, "Overall,"))


class TrailingRunTests(unittest.TestCase):
    # The regex that the detector used before the loop. The loop must give the same start.
    OLD = re.compile("(?:" + OPEN + "[0-9]+" + CLOSE + "|[\\s*_])*\\Z")
    PIECES = ["a", "b", " ", "\t", "\n", "*", "_", "7", OPEN + "12" + CLOSE, OPEN + "3" + CLOSE, OPEN, CLOSE,
              OPEN + CLOSE, "\u2028", "\x1c"]

    def test_the_trim_start_equals_the_old_regex_on_random_strings(self):
        rng = random.Random(3)
        for _ in range(2000):
            text = "".join(rng.choice(self.PIECES) for _ in range(rng.randint(0, 40)))
            lead = rng.randint(0, len(text))
            self.assertEqual(pl._trail_start(text, lead), self.OLD.search(text, lead).start(), (text, lead))

    def test_the_trim_start_on_simple_strings(self):
        ph = OPEN + "5" + CLOSE
        self.assertEqual(pl._trail_start("Word. " + ph + " * _ ", 0), len("Word."))
        self.assertEqual(pl._trail_start("Word" + ph, 0), len("Word"))
        self.assertEqual(pl._trail_start("12" + ph, 0), len("12"))
        self.assertEqual(pl._trail_start(ph + " ", 0), 0)
        self.assertEqual(pl._trail_start(ph + " ", 1), 3)
        self.assertEqual(pl._trail_start("", 0), 0)

    def test_a_long_run_before_a_word_takes_linear_time(self):
        for fmt in ("latex", "markdown", "text"):
            for unit in ("\\cite{a} ", "* ", "_ "):
                text = "The gene rose " + unit * 20000 + "word and more.\n"
                start = time.time()
                lint(text, fmt)
                seconds = time.time() - start
                self.assertLess(seconds, 20.0, (fmt, unit, seconds))

    def test_a_long_run_at_the_end_takes_linear_time(self):
        for unit in ("\\cite{a} ", "* ", "_ "):
            start = time.time()
            lint("The gene rose " + unit * 20000, "latex")
            self.assertLess(time.time() - start, 20.0, unit)


class WindowStartTests(unittest.TestCase):
    SENTENCE = "We delve into the data."

    def window(self, source, fmt):
        windows = pl.windows(lint(source, fmt).findings, source, "a")
        self.assertEqual(len(windows), 1)
        return windows[0]

    def test_a_preamble_stays_out_of_the_first_window(self):
        lines = "".join("\\usepackage{pkg%d}\n" % i for i in range(60))
        for source in (lines + self.SENTENCE + "\n",
                       "\\documentclass{article}\n" + lines + "\\begin{document}\n" + self.SENTENCE + "\n\\end{document}\n"):
            for newline in ("\n", "\r\n"):
                with self.subTest(newline=newline, size=len(source)):
                    self.assertEqual(self.window(source.replace("\n", newline), "latex")["before"], self.SENTENCE)

    def test_a_comment_line_stays_out_of_the_window(self):
        source = "% check this later\n" + self.SENTENCE + "\n"
        window = self.window(source, "latex")
        self.assertEqual(window["before"], self.SENTENCE)
        self.assertEqual(window["start"], source.index("We delve"))

    def test_a_label_line_stays_out_of_the_window(self):
        self.assertEqual(self.window("\\label{sec:intro}\n" + self.SENTENCE + "\n", "latex")["before"], self.SENTENCE)

    def test_several_command_lines_stay_out_of_the_window(self):
        source = "\\label{a}\n% note\n\\vspace{1em} \\hfill\n  " + self.SENTENCE + "\n"
        self.assertEqual(self.window(source, "latex")["before"], self.SENTENCE)

    def test_a_figure_stays_out_of_the_window_of_its_caption(self):
        source = ("\\begin{figure}[t]\n\\centering\n\\includegraphics{a.pdf}\n"
                  "\\caption{We delve into the data.}\n\\end{figure}\n")
        self.assertEqual(self.window(source, "latex")["before"], "\\caption{We delve into the data.}")

    def test_a_subfigure_caption_gives_its_findings_and_a_window_that_starts_at_the_caption(self):
        source = ("\\begin{subfigure}[b]{0.45\\textwidth}\n\\centering\n\\includegraphics[width=\\textwidth]{a.pdf}\n"
                  "\\caption{Overall, we delve into plates.}\n\\end{subfigure}\n")
        result = lint(source, "latex")
        self.assertEqual(sorted(f.family for f in result.findings), ["recap-opener", "vocabulary-excess"])
        window = self.window(source, "latex")
        self.assertEqual(window["before"], "\\caption{Overall, we delve into plates.}")
        self.assertEqual(window["start"], source.index("\\caption"))
        self.assertEqual(window["families"], ["recap-opener", "vocabulary-excess"])

    def test_the_arguments_of_an_environment_stay_out_of_the_window(self):
        for begin in ("\\begin{minipage}{0.5\\textwidth}", "\\begin{multicols}{2}", "\\begin{wrapfigure}{r}{0.5\\textwidth}",
                      "\\begin{thebibliography}{9}", "\\begin{subfigure}[b]{0.45\\textwidth}"):
            with self.subTest(begin=begin):
                self.assertEqual(self.window(begin + "\n" + self.SENTENCE + "\n", "latex")["before"], self.SENTENCE)

    def test_the_caption_command_stays_when_it_is_on_the_line_of_the_first_words(self):
        source = "\\label{a}\n\\caption{We delve into the data. More text follows.}\n"
        self.assertEqual(self.window(source, "latex")["before"], "\\caption{We delve into the data.")

    def test_a_table_row_stays_out_of_the_window(self):
        source = "| a | b |\n|---|---|\n" + self.SENTENCE + "\n"
        self.assertEqual(self.window(source, "markdown")["before"], self.SENTENCE)

    def test_a_comment_line_in_markdown_stays_out_of_the_window(self):
        self.assertEqual(self.window("<!-- n -->\n" + self.SENTENCE + "\n", "markdown")["before"], self.SENTENCE)

    def test_an_item_line_keeps_its_marker(self):
        self.assertEqual(self.window("\\item " + self.SENTENCE + "\n", "latex")["before"], "\\item " + self.SENTENCE)
        self.assertEqual(self.window("- " + self.SENTENCE + "\n", "markdown")["before"], "- " + self.SENTENCE)

    def test_the_sentence_bounds_of_a_finding_start_at_the_first_prose_line(self):
        source = "% note\n\\label{a}\n" + self.SENTENCE + "\n"
        f = lint(source, "latex").findings[0]
        self.assertEqual((f.sentence_start, f.sentence_end), (source.index("We delve"), source.index("data.") + 5))

    def test_a_sentence_in_plain_text_is_unchanged(self):
        source = "Plain line one\nWe delve into the data.\n"
        self.assertEqual(self.window(source, "text")["before"], "Plain line one\nWe delve into the data.")

    def test_a_byte_order_mark_stays_out_of_the_window(self):
        sentence = "The answer is simple: the mutant grows."
        for fmt in ("latex", "markdown", "text"):
            for newline in ("\n", "\r\n"):
                for lead in ("\ufeff", "\ufeff" + newline):
                    with self.subTest(fmt=fmt, newline=newline, lead=lead):
                        source = lead + sentence + newline
                        start, end = len(lead), len(lead) + len(sentence)
                        window = self.window(source, fmt)
                        self.assertEqual((window["start"], window["end"], window["before"]), (start, end, sentence))
                        found = [(f.family, f.text, f.start, f.end, f.line, f.col, f.sentence_start, f.sentence_end)
                                 for f in lint(source, fmt).findings]
                        line = 1 if lead == "\ufeff" else 2
                        self.assertEqual(found, [("colon-reveal", "The answer is simple: t", start, start + 23, line,
                                                  start - source.rfind("\n", 0, start), start, end)])


class BracketArgumentTests(unittest.TestCase):
    """A bracket group after `\\begin{name}` hides up to its balanced close on its line."""

    def found(self, source):
        return [(f.family, f.text, f.start, f.end, f.line, f.col, f.sentence_start, f.sentence_end)
                for f in lint(source, "latex").findings]

    def test_a_bracket_inside_a_brace_group_does_not_end_the_argument(self):
        for newline in ("\n", "\r\n"):
            with self.subTest(newline=newline):
                source = "\\begin{tcolorbox}[title={Fig[1]},colback=red]Overall, we delve into plates." + newline
                self.assertEqual(self.found(source), [("recap-opener", "Overall,", 45, 53, 1, 46, 45, 75),
                                                      ("vocabulary-excess", "delve", 57, 62, 1, 58, 45, 75)])

    def test_a_label_with_brackets_is_hidden(self):
        for newline, shift in (("\n", 0), ("\r\n", 1)):
            with self.subTest(newline=newline):
                source = "\\begin{enumerate}[label={[\\arabic*]}]" + newline + "\\item Overall, we delve." + newline
                self.assertEqual(pl.piece(mask(source, "latex"), 0), "\\begin{enumerate}[label={[\\arabic*]}]")
                self.assertEqual(self.found(source), [
                    ("recap-opener", "Overall,", 44 + shift, 52 + shift, 2, 7, 38 + shift, 62 + shift),
                    ("vocabulary-excess", "delve", 56 + shift, 61 + shift, 2, 19, 38 + shift, 62 + shift)])

    def test_a_percent_sign_inside_the_group_hides_the_rest_of_the_line(self):
        for newline, shift in (("\n", 0), ("\r\n", 1)):
            with self.subTest(newline=newline):
                self.assertEqual(self.found("\\begin{x}[%]We delve into plates." + newline), [])
                source = "\\begin{x}[%]We delve into plates." + newline + "We delve again." + newline
                self.assertEqual([f[1:6] for f in self.found(source)], [("delve", 37 + shift, 42 + shift, 2, 4)])

    def test_an_escaped_bracket_does_not_close_the_group(self):
        for newline in ("\n", "\r\n"):
            with self.subTest(newline=newline):
                source = "\\begin{x}[a\\]b]We delve." + newline
                self.assertEqual(self.found(source), [("vocabulary-excess", "delve", 18, 23, 1, 19, 15, 24)])


class WindowTests(unittest.TestCase):
    TWO = "The mutant \u2014 which lacks the domain \u2014 grows slowly."

    def test_a_sentence_with_two_hits_gives_one_window(self):
        found = lint(self.TWO).findings
        self.assertEqual(len(found), 2)
        windows = pl.windows(found, self.TWO, "a.txt")
        self.assertEqual(len(windows), 1)
        window = windows[0]
        self.assertEqual(window["hits"], [{"family": "em-dash", "text": "\u2014", "line": 1}] * 2)
        self.assertEqual(window["families"], ["em-dash"])

    def test_the_window_has_exactly_the_fields_of_the_brief(self):
        window = pl.windows(lint(self.TWO).findings, self.TWO, "a.txt")[0]
        self.assertEqual(sorted(window), ["before", "end", "families", "file", "hits", "id", "occurrences", "start"])
        self.assertEqual(window["file"], "a.txt")
        self.assertEqual(window["id"], "w001")

    def test_before_is_the_original_sentence_verbatim(self):
        source = "\\section{Intro}\r\nThe sample was small \\cite{a}.\r\nWe delve\r\ninto the data \\cite{b}.\r\n"
        findings = lint(source, "latex").findings
        window = pl.windows(findings, source, "a.tex")[0]
        self.assertEqual(window["before"], source[window["start"]:window["end"]])
        self.assertEqual(window["before"], "We delve\r\ninto the data \\cite{b}.")

    def test_ids_count_from_one_in_file_order(self):
        source = "We delve into the data.\n\n" + h.FILLER[0] + "\n\nThe pipeline is the backbone of the plan.\n"
        windows = pl.windows(lint(source).findings, source, "a.txt")
        self.assertEqual([w["id"] for w in windows], ["w001", "w002"])
        self.assertLess(windows[0]["end"], windows[1]["start"])

    def test_a_window_counts_how_often_its_text_occurs_in_the_file(self):
        source = "We delve into the data.\n\nThe sample was small.\n\nWe delve into the data.\n"
        windows = pl.windows(lint(source).findings, source, "a.txt")
        self.assertEqual([w["occurrences"] for w in windows], [2, 2])
        for w in windows:
            self.assertEqual(w["occurrences"], source.count(w["before"]))
        unique = "We delve into the data.\n"
        self.assertEqual([w["occurrences"] for w in pl.windows(lint(unique).findings, unique, "a.txt")], [1])

    def test_a_window_whose_text_sits_inside_a_longer_text_counts_that_text_too(self):
        source = "We delve into the data.\n\nWe delve into the data. We delve into the data.\n"
        windows = pl.windows(lint(source).findings, source, "a.txt")
        self.assertEqual(len(windows), 3)
        self.assertEqual(set(w["occurrences"] for w in windows), {3})

    def test_the_first_id_can_be_set_for_a_later_file(self):
        windows = pl.windows(lint(self.TWO).findings, self.TWO, "a.txt", start_id=7)
        self.assertEqual(windows[0]["id"], "w007")

    def test_two_flagged_sentences_in_a_row_give_two_windows(self):
        source = "We delve into the data. We utilize a standard buffer.\n"
        windows = pl.windows(lint(source).findings, source, "a.txt")
        self.assertEqual([w["before"] for w in windows], ["We delve into the data.", "We utilize a standard buffer."])
        self.assertLessEqual(windows[0]["end"], windows[1]["start"])

    def test_a_sentence_with_hits_of_two_families_lists_both_in_the_order_of_the_hits(self):
        source = "Interestingly, we delve into the data.\n"
        window = pl.windows(lint(source).findings, source, "a.txt")[0]
        self.assertEqual(window["families"], ["throat-clearing", "vocabulary-excess"])
        self.assertEqual([hit["text"] for hit in window["hits"]], ["Interestingly", "delve"])

    def test_a_structural_finding_and_a_rule_finding_share_the_window_of_the_sentence(self):
        source = " ".join(THIS[:2] + ["This gene will delve into the data in every line."]) + "\n"
        windows = pl.windows(lint(source).findings, source, "a.txt")
        self.assertEqual(len(windows), 1)
        self.assertEqual(windows[0]["families"], ["repeated-openers", "vocabulary-excess"])

    def test_a_window_lists_only_the_flagged_hits(self):
        source = "We delve into the data, allowing fresh medium to enter.\n"
        findings = lint(source).findings
        self.assertEqual(sorted(f.severity for f in findings), ["flag", "info"])
        window = pl.windows(findings, source, "a.txt")[0]
        self.assertEqual([hit["family"] for hit in window["hits"]], ["vocabulary-excess"])

    def test_the_hit_holds_the_line_of_the_hit(self):
        source = "Plain first line here\nand We delve into the data.\n"
        window = pl.windows(lint(source).findings, source, "a.txt")[0]
        self.assertEqual(window["hits"][0]["line"], 2)

    def test_a_sentence_with_no_flag_gives_no_window(self):
        self.assertEqual(pl.windows(lint(h.filler_words(300)).findings, h.filler_words(300), "a.txt"), [])

    def test_a_heading_stays_out_of_the_window_in_latex(self):
        source = "\\section{Introduction}\nWe delve into the gene.\n"
        window = pl.windows(lint(source, "latex").findings, source, "a.tex")[0]
        self.assertEqual(window["before"], "We delve into the gene.")
        self.assertNotIn("Introduction", window["before"])

    def test_the_heading_example_of_the_brief_with_a_probe_pattern(self):
        extra = {"extra_patterns": [{"id": "probe", "title": "Probe", "regex": "\\brose\\b", "strategy": "Fix it."}]}
        patterns = pp.apply_project(h.PATTERNS, extra)
        source = "\\section{Introduction}\nThe gene rose.\n"
        windows = pl.windows(lint(source, "latex", patterns).findings, source, "a.tex")
        self.assertEqual([w["before"] for w in windows], ["The gene rose."])
        self.assertEqual([w["hits"] for w in windows], [[{"family": "probe", "text": "rose", "line": 2}]])
        self.assertEqual(pl.windows(lint("Introduction\nThe gene rose.\n", "text", patterns).findings,
                                    "Introduction\nThe gene rose.\n", "a.txt")[0]["before"],
                         "Introduction\nThe gene rose.")

    def test_a_heading_stays_out_of_the_window_in_markdown(self):
        source = "## Results\nWe delve into the gene.\n"
        window = pl.windows(lint(source, "markdown").findings, source, "a.md")[0]
        self.assertEqual(window["before"], "We delve into the gene.")

    def test_an_item_line_without_an_end_mark_is_its_own_window(self):
        source = "\\begin{itemize}\n\\item We delve into the gene\n\\item Plain item here\n\\end{itemize}\n"
        window = pl.windows(lint(source, "latex").findings, source, "a.tex")[0]
        self.assertEqual(window["before"], "\\item We delve into the gene")

    def test_a_markdown_list_item_is_its_own_window(self):
        source = "- Plain item here\n- We delve into the gene\n- Another plain item\n"
        window = pl.windows(lint(source, "markdown").findings, source, "a.md")[0]
        self.assertEqual(window["before"], "- We delve into the gene")

    def test_a_text_with_no_heading_line_keeps_a_window_over_the_wrapped_lines(self):
        source = "The sample was small and\nWe delve into the data\nfor two days.\n"
        windows = pl.windows(lint(source).findings, source, "a.txt")
        self.assertEqual(len(windows), 1)
        self.assertEqual(windows[0]["before"], source.strip())

    def test_a_window_keeps_a_command_at_the_end_of_the_sentence(self):
        source = "We delve into the data \\cite{b}.\n\nPlain text follows here.\n"
        window = pl.windows(lint(source, "latex").findings, source, "a.tex")[0]
        self.assertEqual(window["before"], "We delve into the data \\cite{b}.")


class RandomTextTests(unittest.TestCase):
    TOKENS = [
        "We", "delve", "into", "the", "data.", "Why", "does", "this", "matter?", "The", "answer", "is", "dose.",
        "\\cite{a}", "\\section{Intro}", "\\item", "\\bibitem{k}", "$x$", "$", "{", "}", "[12]", "(Smith et al., 2020)",
        "%", "\\emph{This}", "\\begin{itemize}", "\\end{itemize}", "# Head", "- item", "1. one", "`code`", "<!--",
        "-->", "\u2014", "---", "\ue000", "\ue001", "\ue0003\ue001", "\n", "\n\n", "\r\n", "\r\n\r\n", "  ", "\t",
        "\u2028", "\f", "Studies", "show", "that", "utilize", "Fig.", "2", "et", "al.", "e.g.", "4.5", "\\verb|x|",
        "\\\\", "\\", "&", "Interestingly,", "Overall,", "robust", "serves", "as", "a", "testament", "This", "gene",
        "rose.", "\u0663.", "\ufeff"]

    def test_offsets_lines_and_windows_stay_exact_on_random_text(self):
        rng = random.Random(7)
        checked = 0
        for trial in range(250):
            source = "".join(rng.choice(self.TOKENS) + rng.choice([" ", " ", "", "\n"]) for _ in range(rng.randint(1, 60)))
            for fmt in ("latex", "markdown", "text"):
                result = lint(source, fmt)
                found = result.findings
                self.assertEqual([(f.start, f.end) for f in found], sorted((f.start, f.end) for f in found))
                for f in found:
                    checked += 1
                    self.assertEqual(source[f.start:f.end], f.text, (source, fmt))
                    self.assertTrue(0 <= f.sentence_start <= f.start <= f.end <= f.sentence_end <= len(source))
                    self.assertEqual(f.line, source.count("\n", 0, f.start) + 1, (source, fmt))
                    self.assertEqual(f.col, f.start - source.rfind("\n", 0, f.start), (source, fmt))
                spans = mask(source, fmt).spans
                last_end = -1
                for window in pl.windows(found, source, "x"):
                    self.assertEqual(window["before"], source[window["start"]:window["end"]])
                    self.assertGreaterEqual(window["start"], last_end, (source, fmt))
                    last_end = window["end"]
                    for span in spans:
                        inside = window["start"] <= span.start and span.end <= window["end"]
                        outside = span.end <= window["start"] or span.start >= window["end"]
                        self.assertTrue(inside or outside, (source, fmt, span))
                    self.assertEqual(window["occurrences"], source.count(window["before"]))
        self.assertGreater(checked, 100)


class CliTests(unittest.TestCase):
    def test_a_clean_file_exits_0_and_a_flagged_file_exits_1(self):
        with Folder() as folder:
            clean = folder.write("clean.txt", h.filler_words(100) + "\n")
            flagged = folder.write("flagged.txt", "We delve into the data.\n")
            code, out, err = run_main([clean])
            self.assertEqual((code, err), (0, ""))
            self.assertIn("clean.txt: 100 words, 0 flagged, 0 info\n", out)
            self.assertEqual(run_main([flagged])[0], 1)
            self.assertEqual(run_main([clean, flagged])[0], 1)

    def test_an_info_finding_alone_exits_0(self):
        with Folder() as folder:
            path = folder.write("a.txt", h.padded(500, [h.EM_SENTENCE]))
            code, out, _ = run_main([path])
            self.assertEqual(code, 0)
            self.assertIn("flagged: 0 info: 1", out)

    def test_five_em_dashes_in_500_words_exit_1(self):
        with Folder() as folder:
            path = folder.write("a.txt", h.padded(500, [h.EM_SENTENCE] * 5))
            code, out, _ = run_main([path])
            self.assertEqual(code, 1)
            self.assertIn("flagged: 5 info: 0", out)

    def test_a_binary_file_exits_2_and_names_the_file(self):
        with Folder() as folder:
            for name, data in (("a.bin", bytes(range(256))), ("b.txt", b"\xff\xfe"), ("c.txt", b"abc\x00def"),
                               ("d.md", b"Plain start \xe2\x80")):
                with self.subTest(name=name):
                    path = folder.write(name, data)
                    code, out, err = run_main([path])
                    self.assertEqual((code, out), (2, ""))
                    self.assertIn("prose_lint.py: error:", err)
                    self.assertIn(path, err)

    def test_a_decode_error_gives_the_byte_offset(self):
        with Folder() as folder:
            self.assertIn("byte offset 0", run_main([folder.write("a.txt", b"\xff\xfe")])[2])
            self.assertIn("byte offset 9", run_main([folder.write("b.txt", b"Okay text\xff")])[2])

    def test_an_empty_file_exits_0_with_0_words(self):
        with Folder() as folder:
            code, out, err = run_main([folder.write("empty.txt", b"")])
            self.assertEqual((code, err), (0, ""))
            self.assertIn("empty.txt: 0 words, 0 flagged, 0 info\n", out)
            self.assertTrue(out.endswith("flagged: 0 info: 0\n"))

    def test_a_crash_while_checking_a_file_exits_2_and_names_the_file(self):
        with Folder() as folder:
            path = folder.write("a.txt", "We delve into the data.\n")
            with mock.patch.object(pl, "lint_text", side_effect=RuntimeError("boom")):
                code, out, err = run_main([path])
            self.assertEqual((code, out), (2, ""))
            self.assertIn(path, err)
            self.assertIn("RuntimeError: boom", err)

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root can read every folder")
    def test_an_unreadable_subfolder_exits_2_and_names_the_folder(self):
        with Folder() as folder:
            folder.write("ok.md", "x\n")
            folder.write("locked/a.md", "x\n")
            locked = folder.path("locked")
            os.chmod(locked, 0)
            try:
                code, out, err = run_main([folder.root])
            finally:
                os.chmod(locked, 0o700)
            self.assertEqual((code, out), (2, ""))
            self.assertIn("prose_lint.py: error: cannot read %s" % locked, err)

    def test_a_project_folder_that_does_not_exist_exits_2(self):
        with Folder() as folder:
            path = folder.write("a.txt", "x\n")
            missing = folder.path("nowhere")
            code, out, err = run_main([path, "--project-dir", missing])
            self.assertEqual((code, out), (2, ""))
            self.assertEqual(err, "prose_lint.py: error: project directory not found: %s\n" % missing)

    def test_a_missing_path_exits_2(self):
        with Folder() as folder:
            path = folder.path("missing.txt")
            code, out, err = run_main([path])
            self.assertEqual((code, out), (2, ""))
            self.assertIn(path, err)

    def test_one_unreadable_file_stops_the_run_before_any_output(self):
        with Folder() as folder:
            good = folder.write("a.txt", "We delve into the data.\n")
            bad = folder.write("b.txt", b"\xff")
            code, out, err = run_main([good, bad])
            self.assertEqual((code, out), (2, ""))
            self.assertIn(bad, err)

    def test_a_folder_with_no_prose_file_exits_2(self):
        with Folder() as folder:
            folder.write("notes.py", "print(1)\n")
            code, out, err = run_main([folder.root])
            self.assertEqual((code, out), (2, ""))
            self.assertIn(folder.root, err)
            self.assertIn(".tex, .md or .txt", err)

    def test_an_unknown_extension_lints_as_text(self):
        with Folder() as folder:
            path = folder.write("notes.log", "We delve into the data.\n")
            code, out, _ = run_main([path, "--json"])
            data = json.loads(out)
            self.assertEqual(code, 1)
            self.assertEqual(data["files"][0]["format"], "text")
            self.assertEqual(data["files"][0]["findings"][0]["family"], "vocabulary-excess")

    def test_auto_picks_the_format_from_the_extension_and_an_explicit_format_wins(self):
        with Folder() as folder:
            paths = [folder.write("a.tex", "x\n"), folder.write("b.md", "x\n"), folder.write("c.txt", "x\n")]
            formats = [f["format"] for f in json.loads(run_main(paths + ["--json"])[1])["files"]]
            self.assertEqual(formats, ["latex", "markdown", "text"])
            for name in ("latex", "markdown", "text"):
                formats = [f["format"] for f in json.loads(run_main(paths + ["--json", "--format", name])[1])["files"]]
                self.assertEqual(formats, [name] * 3)

    def test_the_explicit_format_changes_the_masking(self):
        with Folder() as folder:
            path = folder.write("a.txt", "We delve into the data \\cite{delve}.\n")
            as_text = json.loads(run_main([path, "--json"])[1])["files"][0]["findings"]
            as_latex = json.loads(run_main([path, "--json", "--format", "latex"])[1])["files"][0]["findings"]
            self.assertEqual(len(as_text), 2)
            self.assertEqual(len(as_latex), 1)

    def test_a_folder_expands_to_prose_files_in_sorted_order(self):
        with Folder() as folder:
            for name in ("b.md", "a.tex", "sub/c.txt", "sub/deep/d.md", "docs/h.md", "other/prose/i.md",
                         "docs/other/j.md", "UPPER.TXT", "z.py", ".hidden/e.md", "node_modules/f.md",
                         "docs/prose/g.md", "sub/.cache/k.md"):
                folder.write(name, "x\n")
            code, out, _ = run_main([folder.root, "--json"])
            names = [os.path.relpath(f["file"], folder.root).replace(os.sep, "/") for f in json.loads(out)["files"]]
            self.assertEqual(code, 0)
            self.assertEqual(names, ["UPPER.TXT", "a.tex", "b.md", "docs/h.md", "docs/other/j.md",
                                     "other/prose/i.md", "sub/c.txt", "sub/deep/d.md"])

    def test_a_folder_named_docs_skips_its_prose_folder(self):
        with Folder() as folder:
            folder.write("docs/a.md", "x\n")
            folder.write("docs/prose/b.md", "x\n")
            code, out, _ = run_main([folder.path("docs"), "--json"])
            names = [os.path.basename(f["file"]) for f in json.loads(out)["files"]]
            self.assertEqual(names, ["a.md"])

    def test_a_hidden_folder_that_the_user_names_is_read(self):
        with Folder() as folder:
            folder.write(".claude/a.md", "x\n")
            code, out, _ = run_main([folder.path(".claude"), "--json"])
            self.assertEqual([os.path.basename(f["file"]) for f in json.loads(out)["files"]], ["a.md"])

    def test_a_file_argument_is_used_as_given_with_any_extension(self):
        with Folder() as folder:
            path = folder.write("notes.py", "We delve into the data.\n")
            code, out, _ = run_main([path])
            self.assertEqual(code, 1)
            self.assertIn(path + ":1:4: vocabulary-excess", out)

    def test_files_and_folders_mix_in_the_order_of_the_arguments(self):
        with Folder() as folder:
            second = folder.write("b.txt", "x\n")
            folder.write("dir/a.txt", "x\n")
            code, out, _ = run_main([second, folder.path("dir"), "--json"])
            names = [os.path.basename(f["file"]) for f in json.loads(out)["files"]]
            self.assertEqual(names, ["b.txt", "a.txt"])

    def test_a_typo_in_the_project_file_exits_2_and_names_the_id(self):
        with Folder() as folder:
            folder.write("project/prose-style.yaml", "families:\n  vocabulary-exces:\n    enabled: false\n")
            path = folder.write("a.txt", "We delve into the data.\n")
            code, out, err = run_main([path, "--project-dir", folder.path("project")])
            self.assertEqual((code, out), (2, ""))
            self.assertTrue(err.startswith("prose_lint.py: error: "))
            self.assertIn("vocabulary-exces", err)

    def test_the_project_file_in_docs_changes_the_result(self):
        with Folder() as folder:
            folder.write("project/docs/prose-style.yaml", "families:\n  vocabulary-excess:\n    enabled: false\n")
            path = folder.write("a.txt", "We delve into the data.\n")
            self.assertEqual(run_main([path, "--project-dir", folder.path("project")])[0], 0)
            self.assertEqual(run_main([path])[0], 1)

    def test_an_extra_pattern_of_the_project_file_flags_with_tier_t3(self):
        yaml = ("extra_patterns:\n  - id: house-word\n    title: House word\n    regex: '\\bzorb\\w*'\n"
                "    strategy: Use the plain word.\n")
        with Folder() as folder:
            folder.write("project/prose-style.yaml", yaml)
            path = folder.write("a.txt", "We zorb the data.\n")
            code, out, _ = run_main([path, "--project-dir", folder.path("project"), "--json"])
            finding = json.loads(out)["files"][0]["findings"][0]
            self.assertEqual((code, finding["family"], finding["tier"], finding["text"]), (1, "house-word", "T3", "zorb"))

    def test_the_default_project_folder_is_the_working_directory(self):
        with Folder() as folder:
            folder.write("prose-style.yaml", "families:\n  vocabulary-excess:\n    enabled: false\n")
            path = folder.write("a.txt", "We delve into the data.\n")
            old = os.getcwd()
            os.chdir(folder.root)
            try:
                out, err = io.BytesIO(), io.BytesIO()
                code = pl.main([path], out, err)
            finally:
                os.chdir(old)
            self.assertEqual(code, 0)

    def test_a_bad_option_exits_2_with_a_message_on_stderr(self):
        for args in (["--nope", "a.txt"], ["--format", "pdf", "a.txt"], []):
            with self.subTest(args=args):
                code, out, err = run_script(args)
                self.assertEqual(code, 2)
                self.assertEqual(out, b"")
                self.assertIn(b"usage:", err)

    def test_windows_prints_the_list_and_nothing_else(self):
        with Folder() as folder:
            first = folder.write("a.txt", "We delve into the data.\n")
            second = folder.write("b.txt", "Plain text here today.\n\nWe utilize a standard buffer.\n")
            code, out, _ = run_main([first, second, "--windows"])
            self.assertEqual(code, 1)
            windows = json.loads(out)
            self.assertEqual([(w["id"], w["file"], w["before"]) for w in windows],
                             [("w001", first, "We delve into the data."), ("w002", second, "We utilize a standard buffer.")])
            self.assertEqual(out, json.dumps(windows, ensure_ascii=False, sort_keys=True, indent=2) + "\n")

    def test_windows_of_a_clean_file_is_an_empty_list_and_exit_0(self):
        with Folder() as folder:
            code, out, _ = run_main([folder.write("a.txt", h.filler_words(50)), "--windows"])
            self.assertEqual((code, json.loads(out)), (0, []))

    def test_windows_wins_over_json(self):
        with Folder() as folder:
            code, out, _ = run_main([folder.write("a.txt", "We delve into the data.\n"), "--windows", "--json"])
            self.assertIsInstance(json.loads(out), list)

    def test_the_before_text_of_a_window_matches_the_file_bytes(self):
        with Folder() as folder:
            source = "\\section{Intro}\r\nThe sample was small \\cite{a}.\r\nWe delve into the data \\cite{b}.\r\n"
            path = folder.write("a.tex", source)
            windows = json.loads(run_main([path, "--windows"])[1])
            self.assertEqual(windows[0]["before"], source[windows[0]["start"]:windows[0]["end"]])


class OutputTests(unittest.TestCase):
    SOURCE = "We delve into the data.\n"

    def strategy(self, family):
        return h.PATTERNS.family(family).strategy

    def test_the_text_output_has_the_rows_the_summary_and_the_totals(self):
        with Folder() as folder:
            path = folder.write("a.txt", self.SOURCE)
            code, out, _ = run_main([path])
            self.assertEqual(code, 1)
            self.assertEqual(out, (
                '%s:1:4: vocabulary-excess: T1: flag: "delve" (%s)\n'
                "%s: 5 words, 1 flagged, 0 info\n"
                "  vocabulary-excess: 1 hits, 200.00 per 1000 words\n"
                "flagged: 1 info: 0\n") % (path, self.strategy("vocabulary-excess"), path))

    def test_each_file_has_its_own_block_and_the_totals_come_last(self):
        with Folder() as folder:
            first = folder.write("a.txt", self.SOURCE)
            second = folder.write("b.txt", "Plain text here today.\n\nWe utilize a standard buffer.\n")
            lines = run_main([first, second])[1].splitlines()
            self.assertEqual([line.split(":")[0] for line in lines[:2]], [first, first])
            self.assertEqual(lines[3], "%s:3:4: vocabulary-density: T1: flag: \"utilize\" (%s)" % (
                second, self.strategy("vocabulary-density")))
            self.assertEqual(lines[-1], "flagged: 2 info: 0")
            self.assertEqual(lines[4], "%s: 9 words, 1 flagged, 0 info" % second)

    def test_an_info_row_and_a_flag_row_count_apart(self):
        with Folder() as folder:
            path = folder.write("a.txt", "We delve into the data, allowing fresh medium to enter.\n")
            out = run_main([path])[1]
            self.assertIn(": vocabulary-excess: T1: flag: ", out)
            self.assertIn(": participial-benefit: T1: info: ", out)
            self.assertIn("%s: 10 words, 1 flagged, 1 info\n" % path, out)
            self.assertTrue(out.endswith("flagged: 1 info: 1\n"))

    def test_the_family_lines_follow_the_order_of_the_data_file(self):
        with Folder() as folder:
            path = folder.write("a.txt", "Interestingly, we delve into the data. The pipeline is the backbone of the plan.\n")
            out = run_main([path])[1]
            lines = [line for line in out.splitlines() if line.startswith("  ")]
            self.assertEqual([line.split(":")[0].strip() for line in lines],
                             ["vocabulary-excess", "figurative-load", "throat-clearing"])

    def test_the_density_uses_two_decimals(self):
        with Folder() as folder:
            path = folder.write("a.txt", h.padded(700, ["We delve into the data."]))
            out = run_main([path])[1]
            self.assertIn("  vocabulary-excess: 1 hits, 1.43 per 1000 words\n", out)

    def test_the_text_of_a_row_is_cut_to_80_characters_and_shows_no_newline(self):
        long_sentence = ("This gene rose in every line\nof the long trial that ran from the first week of spring "
                         "to the last week of the following autumn without any pause.")
        source = " ".join(THIS[:2]) + " " + long_sentence + "\n"
        with Folder() as folder:
            path = folder.write("a.txt", source)
            rows = [line for line in run_main([path])[1].splitlines() if "repeated-openers: T2" in line]
            self.assertEqual(len(rows), 1)
            shown = rows[0].split(': flag: "', 1)[1].split('" (', 1)[0]
            flat = long_sentence.replace("\n", " ")
            self.assertEqual(len(shown), 80)
            self.assertEqual(shown, flat[:77] + "...")

    def test_a_short_text_with_a_line_break_shows_on_one_row(self):
        for newline in ("\n", "\r\n"):
            with Folder() as folder:
                sentence = "This gene" + newline + "rose in every line."
                path = folder.write("a.txt", " ".join(THIS[:2]) + " " + sentence + "\n")
                rows = [line for line in run_main([path])[1].splitlines() if "repeated-openers: T2" in line]
                self.assertEqual(len(rows), 1)
                self.assertIn(': flag: "This gene rose in every line." (', rows[0])

    def test_a_text_of_80_characters_is_not_cut_and_one_of_81_is(self):
        exact = "This gene rose in " + "a" * 61 + "."
        longer = "This gene rose in " + "a" * 62 + "."
        self.assertEqual((len(exact), len(longer)), (80, 81))
        for sentence, shown in ((exact, exact), (longer, longer[:77] + "...")):
            with Folder() as folder:
                path = folder.write("a.txt", " ".join(THIS[:2]) + " " + sentence + "\n")
                rows = [line for line in run_main([path])[1].splitlines() if "repeated-openers: T2" in line]
                self.assertEqual(len(rows), 1)
                self.assertIn(': flag: "' + shown + '" (', rows[0])

    def test_the_json_output_has_the_fields_of_the_brief(self):
        with Folder() as folder:
            path = folder.write("a.txt", self.SOURCE)
            code, out, _ = run_main([path, "--json"])
            self.assertEqual(code, 1)
            expected = {
                "files": [{
                    "file": path, "format": "text", "words": 5,
                    "findings": [{
                        "family": "vocabulary-excess", "rule_label": "delve", "tier": "T1", "severity": "flag",
                        "line": 1, "col": 4, "start": 3, "end": 8, "sentence_start": 0, "sentence_end": 23,
                        "text": "delve", "strategy": self.strategy("vocabulary-excess")}],
                    "density": {"vocabulary-excess": 200.0}}],
                "flagged": 1, "info": 0}
            self.assertEqual(json.loads(out), expected)
            self.assertEqual(out, json.dumps(expected, ensure_ascii=False, sort_keys=True, indent=2) + "\n")

    def test_the_finding_fields_are_those_of_the_brief(self):
        self.assertEqual(list(pl.Finding._fields), FIELDS)
        self.assertEqual(list(pl.LintResult._fields), ["findings", "words", "density"])

    def test_a_clean_file_has_an_empty_density_and_no_finding_in_json(self):
        with Folder() as folder:
            data = json.loads(run_main([folder.write("a.txt", h.filler_words(40)), "--json"])[1])
            self.assertEqual(data["files"][0]["findings"], [])
            self.assertEqual(data["files"][0]["density"], {})
            self.assertEqual((data["flagged"], data["info"]), (0, 0))

    def test_the_json_totals_cover_all_files(self):
        with Folder() as folder:
            first = folder.write("a.txt", "We delve into the data, allowing fresh medium to enter.\n")
            second = folder.write("b.txt", "We utilize a standard buffer.\n")
            data = json.loads(run_main([first, second, "--json"])[1])
            self.assertEqual((data["flagged"], data["info"]), (2, 1))
            self.assertEqual([f["words"] for f in data["files"]], [10, 5])

    def test_the_script_writes_utf_8_bytes_under_the_c_locale(self):
        with Folder() as folder:
            path = folder.write("a.txt", "The caf\u00e9 mutant \u2014 which lacks the domain \u2014 grows slowly.\n")
            code, out, err = run_script([path, "--json"], locale="C")
            self.assertEqual((code, err), (1, b""))
            self.assertIn("\u2014".encode("utf-8"), out)
            self.assertNotIn(b"\\u2014", out)
            self.assertEqual(json.loads(out.decode("utf-8"))["files"][0]["findings"][0]["text"], "\u2014")
            code, out, err = run_script([path], locale="C")
            self.assertEqual((code, err), (1, b""))
            self.assertIn('"\u2014"'.encode("utf-8"), out)

    @unittest.skipUnless(sys.getfilesystemencoding().lower().replace("-", "") == "utf8",
                         "the test needs a file system that holds UTF-8 names")
    def test_an_error_message_with_a_non_ascii_name_survives_the_c_locale(self):
        with Folder() as folder:
            path = folder.write("caf\u00e9.txt", b"\xff")
            code, out, err = run_script([path], locale="C")
            self.assertEqual((code, out), (2, b""))
            self.assertIn("caf\u00e9.txt".encode("utf-8"), err)


class SpeedTests(unittest.TestCase):
    BOUND = 10.0

    def timed(self, text, fmt="text"):
        start = time.time()
        result = lint(text, fmt)
        return time.time() - start, result

    def test_a_plain_text_of_50000_words(self):
        text = h.filler_words(50000) + "\n"
        seconds, result = self.timed(text)
        self.assertEqual(result.words, 50000)
        self.assertEqual(result.findings, [])
        self.assertLess(seconds, self.BOUND)

    def test_the_command_line_on_50000_words(self):
        with Folder() as folder:
            path = folder.write("a.txt", h.filler_words(50000) + "\n")
            start = time.time()
            code, out, _ = run_main([path])
            self.assertEqual(code, 0)
            self.assertIn("50000 words", out)
            self.assertLess(time.time() - start, self.BOUND)

    def test_one_long_line_of_50000_words(self):
        text = h.filler_words(50000).replace("\n\n", " ") + "\n"
        seconds, result = self.timed(text)
        self.assertEqual(result.words, 50000)
        self.assertLess(seconds, self.BOUND)

    def test_a_text_with_a_hit_in_every_sentence(self):
        text = "\n\n".join("We delve into the data, which was small number %d." % i for i in range(4000)) + "\n"
        seconds, result = self.timed(text)
        self.assertEqual(len(of_family(result, "vocabulary-excess")), 4000)
        self.assertLess(seconds, self.BOUND)

    def test_a_latex_text_with_a_command_after_every_sentence(self):
        body = " ".join("%s \\cite{k%d}." % (s[:-1], i) for i, s in enumerate(h.FILLER * 100))
        seconds, result = self.timed(body + "\n", "latex")
        self.assertGreater(result.words, 20000)
        self.assertLess(seconds, self.BOUND)

    def test_nested_environment_arguments_and_open_groups(self):
        for label, text, fmt in (("nested brackets", "\\begin{x}[" * 20000 + " " + "]" * 20000, "latex"),
                                 ("many open environments", "\\begin{x}[" * 100000, "latex"),
                                 ("unclosed brackets", "\\begin{x}[a\n" * 20000, "latex"),
                                 ("unclosed braces", "\\begin{x}{a\n" * 20000, "latex"),
                                 ("one open bracket", "[" + "@a " * 40000 + "\n", "markdown")):
            with self.subTest(label=label):
                seconds, _ = self.timed(text, fmt)
                self.assertLess(seconds, 5.0)

    def test_windows_of_many_findings(self):
        text = "\n\n".join("We delve into the data, which was small number %d." % i for i in range(4000)) + "\n"
        start = time.time()
        windows = pl.windows(lint(text).findings, text, "a.txt")
        self.assertEqual(len(windows), 4000)
        self.assertEqual(windows[-1]["id"], "w4000")
        self.assertLess(time.time() - start, self.BOUND)


if __name__ == "__main__":
    unittest.main()
