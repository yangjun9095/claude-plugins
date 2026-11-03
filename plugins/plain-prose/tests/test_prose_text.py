"""Tests for scripts/prose_text.py. All text in this file is made up."""
import os
import random
import re
import subprocess
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))

import prose_mask as pm  # noqa: E402
import prose_mask_core as pmc  # noqa: E402
import prose_text as pt  # noqa: E402

OPEN, CLOSE = "\ue000", "\ue001"
TIME_UNITS = "second minute hour day week month year".split()
TIME_ABBREVIATIONS = "wk mo yr".split()
BRIEF_UNITS = ("mg \u00b5g ug ng pg kg g mL ml \u00b5L \u00b5l uL L mM \u00b5M uM nM pM M mm cm nm \u00b5m um m km "
               "ms \u00b5s s min h hr d Hz kHz MHz GHz bp kb Mb kDa Da \u00b0C K V mV A mA fold \u00d7").split()


def ph(i):
    """Return the placeholder of span number i, as the masker writes it."""
    return OPEN + str(i) + CLOSE


def show(text):
    """Return the text with each placeholder written as <i>."""
    return re.sub(OPEN + "([0-9]+)" + CLOSE, r"<\1>", text)


def masked_sents(source, fmt):
    """Mask the source, split it, and return the sentences with placeholders written as <i>."""
    text = pm.mask(source, fmt).text
    return [show(text[a:b]) for a, b in pt.split_sentences(text)]


def sents(text):
    return [text[a:b] for a, b in pt.split_sentences(text)]


def paras(text):
    return [text[a:b] for a, b in pt.paragraphs(text)]


def word_list(text):
    return [w for _, _, w in pt.words(text)]


class ParagraphTests(unittest.TestCase):
    def test_blank_line_splits(self):
        self.assertEqual(paras("One line.\n\nTwo lines\nstill two."), ["One line.", "Two lines\nstill two."])

    def test_single_newline_does_not_split(self):
        self.assertEqual(paras("a\nb"), ["a\nb"])

    def test_several_blank_lines_and_a_blank_line_with_spaces(self):
        self.assertEqual(paras("A\n\n\n\nB\n  \t\nC"), ["A", "B", "C"])

    def test_edges_are_trimmed(self):
        self.assertEqual(paras("\n\n  Lead.  \n\n\n"), ["Lead."])

    def test_crlf(self):
        self.assertEqual(paras("One.\r\n\r\nTwo.\r\nmore\r\n\r\n"), ["One.", "Two.\r\nmore"])

    def test_empty_inputs(self):
        for text in ("", "   ", "\n\n\n", "\r\n\r\n"):
            self.assertEqual(pt.paragraphs(text), [], repr(text))

    def test_a_placeholder_alone_is_a_paragraph(self):
        self.assertEqual(paras("A.\n\n" + ph(0) + "\n\nB."), ["A.", ph(0), "B."])


ABBREVIATIONS = ("et al.", "Fig.", "Figs.", "Eq.", "Eqs.", "Ref.", "Refs.", "Sec.", "Tab.", "Suppl.",
                 "e.g.", "i.e.", "vs.", "cf.", "approx.", "ca.", "resp.", "Dr.", "Mr.", "Mrs.", "Ms.",
                 "Prof.", "No.")


class SentenceTests(unittest.TestCase):
    def test_plain_split(self):
        self.assertEqual(sents("It rose. It fell."), ["It rose.", "It fell."])

    def test_each_abbreviation_before_a_lowercase_word_a_digit_and_a_capital(self):
        for ab in ABBREVIATIONS:
            for nxt in ("then", "2", "Smith"):
                text = "We cite %s %s for the claim. Then we stop." % (ab, nxt)
                self.assertEqual(sents(text), ["We cite %s %s for the claim." % (ab, nxt), "Then we stop."],
                                 text)

    def test_abbreviation_at_the_start_of_a_sentence(self):
        for ab in ("Cf.", "Vs.", "Approx.", "Ca.", "Resp.", "E.g.", "I.e.", "Dr.", "Fig."):
            text = "%s Smith is shown here. Then we stop." % ab
            self.assertEqual(sents(text), ["%s Smith is shown here." % ab, "Then we stop."], text)

    def test_a_word_that_only_ends_like_an_abbreviation_still_splits(self):
        self.assertEqual(sents("The tool is ConFig. Then it ran."), ["The tool is ConFig.", "Then it ran."])
        self.assertEqual(sents("Ask the Madr. Then go."), ["Ask the Madr.", "Then go."])

    def test_only_a_single_dot_counts_as_an_abbreviation_dot(self):
        self.assertEqual(sents("Did you mean Fig? Yes."), ["Did you mean Fig?", "Yes."])
        self.assertEqual(sents("Is it vitamin D? Yes it is."), ["Is it vitamin D?", "Yes it is."])
        self.assertEqual(sents("Was it Dr! Then go."), ["Was it Dr!", "Then go."])
        self.assertEqual(sents("It was Plan B... Then it stopped."), ["It was Plan B...", "Then it stopped."])

    def test_et_al_at_the_end_of_the_text_ends_the_sentence(self):
        self.assertEqual(sents("It follows Smith et al."), ["It follows Smith et al."])

    def test_decimal_does_not_split(self):
        self.assertEqual(sents("The value was 3.5 mg. Then it fell to 2.25."),
                         ["The value was 3.5 mg.", "Then it fell to 2.25."])

    def test_version_number_does_not_split(self):
        self.assertEqual(sents("We used v2.1.3 of the tool. It ran."), ["We used v2.1.3 of the tool.", "It ran."])

    def test_initial_does_not_split(self):
        self.assertEqual(sents("A. Smith wrote it. B. Jones agreed."), ["A. Smith wrote it.", "B. Jones agreed."])

    def test_digit_after_a_sentence_end_starts_a_sentence(self):
        self.assertEqual(sents("It was 5 mg. 10 mice died."), ["It was 5 mg.", "10 mice died."])

    def test_question_and_exclamation(self):
        self.assertEqual(sents("Is it so? Yes! It is. Really?!"), ["Is it so?", "Yes!", "It is.", "Really?!"])

    def test_runs_of_marks_count_once(self):
        self.assertEqual(sents("Wait... Then go."), ["Wait...", "Then go."])
        self.assertEqual(sents("Wait?! Then go."), ["Wait?!", "Then go."])

    def test_a_lowercase_word_after_the_mark_means_no_end(self):
        self.assertEqual(sents("Is it? yes it is."), ["Is it? yes it is."])
        self.assertEqual(sents("Smith et al. showed it."), ["Smith et al. showed it."])

    def test_closing_quote_or_bracket_belongs_to_the_sentence(self):
        self.assertEqual(sents('He said "stop." Then left.'), ['He said "stop."', "Then left."])
        self.assertEqual(sents("It held (see Fig. 2.) Then it broke."), ["It held (see Fig. 2.)", "Then it broke."])
        self.assertEqual(sents("It held [see Fig. 2.] Then it broke."), ["It held [see Fig. 2.]", "Then it broke."])

    def test_an_opening_quote_starts_a_sentence(self):
        self.assertEqual(sents('It ended. "Why?" he asked.'), ["It ended.", '"Why?" he asked.'])
        self.assertEqual(sents("It ended. \u201cWhy?\u201d he asked."), ["It ended.", "\u201cWhy?\u201d he asked."])
        self.assertEqual(sents("It ended. 'Why?' he asked."), ["It ended.", "'Why?' he asked."])
        self.assertEqual(sents("It ended. \u2018Why?\u2019 he asked."), ["It ended.", "\u2018Why?\u2019 he asked."])

    def test_the_ellipsis_character_is_an_end_mark(self):
        self.assertEqual(sents("Wait\u2026 Then go."), ["Wait\u2026", "Then go."])
        self.assertEqual(sents("Wait\u2026. Then go."), ["Wait\u2026.", "Then go."])
        self.assertEqual(sents("Wait\u2026 then go."), ["Wait\u2026 then go."])

    def test_emphasis_marks_after_the_end_mark(self):
        self.assertEqual(sents("**Note.** It fell."), ["**Note.**", "It fell."])
        self.assertEqual(sents("_Note._ It fell."), ["_Note._", "It fell."])
        self.assertEqual(sents("It fell. *Note.* Then it rose."), ["It fell.", "*Note.*", "Then it rose."])

    def test_emphasis_marks_start_a_sentence(self):
        self.assertEqual(sents("It rose. *Drosophila* grew."), ["It rose.", "*Drosophila* grew."])
        self.assertEqual(sents("It rose. _Drosophila_ grew."), ["It rose.", "_Drosophila_ grew."])
        self.assertEqual(sents("It rose. **Bold** start."), ["It rose.", "**Bold** start."])
        self.assertEqual(sents("It rose. *(A)* panel."), ["It rose.", "*(A)* panel."])
        self.assertEqual(sents("It rose. *lowercase* stays."), ["It rose. *lowercase* stays."])
        self.assertEqual(sents("It rose.\n* item"), ["It rose.\n* item"])

    def test_a_placeholder_can_start_a_sentence(self):
        text = ph(0) + " shows the gain. " + ph(1) + " shows the loss."
        self.assertEqual(sents(text), [ph(0) + " shows the gain.", ph(1) + " shows the loss."])

    def test_a_tilde_after_the_end_mark(self):
        self.assertEqual(masked_sents("Genes rose.~\\cite{a} It fell.", "latex"), ["Genes rose.~<0>", "It fell."])
        self.assertEqual(sents("It rose.~ Then fell."), ["It rose.~", "Then fell."])

    def test_a_tilde_after_an_abbreviation_does_not_split(self):
        self.assertEqual(sents("See Fig.~2 shows it. Then."), ["See Fig.~2 shows it.", "Then."])
        self.assertEqual(masked_sents("See Fig.~\\ref{a} for it. Then stop.", "latex"),
                         ["See Fig.~<0> for it.", "Then stop."])
        self.assertEqual(masked_sents("See Fig.~\\ref{a} Then stop.", "latex"), ["See Fig.~<0> Then stop."])

    def test_a_placeholder_never_ends_a_sentence(self):
        text = "The curve " + ph(0) + " Then it fell. " + ph(12) + " Later it rose."
        self.assertEqual(sents(text), ["The curve " + ph(0) + " Then it fell.", ph(12) + " Later it rose."])

    def test_a_placeholder_before_the_end_mark(self):
        text = "It follows " + ph(3) + ". Then it stops."
        self.assertEqual(sents(text), ["It follows " + ph(3) + ".", "Then it stops."])

    def test_heading_without_end_mark_is_its_own_sentence(self):
        self.assertEqual(sents("Results\n\nThe gene rose."), ["Results", "The gene rose."])

    def test_a_sentence_never_spans_a_blank_line(self):
        self.assertEqual(sents("First part\n\nsecond part."), ["First part", "second part."])
        self.assertEqual(sents("It ended.\n\nlower start. Then more."), ["It ended.", "lower start.", "Then more."])

    def test_single_newline_inside_a_sentence(self):
        self.assertEqual(sents("One line\nstill one. Two."), ["One line\nstill one.", "Two."])

    def test_crlf(self):
        text = "One. Two.\r\n\r\nThree. Four.\r\n"
        self.assertEqual(sents(text), ["One.", "Two.", "Three.", "Four."])
        self.assertEqual(sents("One.\r\nTwo."), ["One.", "Two."])
        self.assertEqual(sents("See Fig.\r\n2 for it.\r\nNext."), ["See Fig.\r\n2 for it.", "Next."])

    def test_no_letter_or_digit_gives_no_sentence(self):
        for text in ("", "   ", "...", "?!\n\n--", ph(0), ph(0) + " .", ph(0) + "\n\n" + ph(1)):
            self.assertEqual(pt.split_sentences(text), [], repr(text))

    def test_a_digit_alone_is_a_sentence(self):
        self.assertEqual(sents("7"), ["7"])

    def test_offsets_are_into_the_given_text(self):
        text = "  Lead one.  \n\n  Next one. Third!  "
        spans = pt.split_sentences(text)
        self.assertEqual([text[a:b] for a, b in spans], ["Lead one.", "Next one.", "Third!"])
        self.assertEqual(spans, [(2, 11), (17, 26), (27, 33)])

    def test_long_text_stays_fast(self):
        text = ("It rose by 3.5 mg, see Fig. 2 and Smith et al. 2020. " * 4000 + "\n   " * 2000 + "x. ") * 2
        start = time.time()
        pt.split_sentences(text)
        pt.paragraphs(text)
        self.assertLess(time.time() - start, 5.0)


class WordTests(unittest.TestCase):
    def test_words_with_offsets(self):
        text = "The well-known gene rose 12.5% in 1,000 cells."
        found = pt.words(text)
        self.assertEqual([w for _, _, w in found],
                         ["The", "well-known", "gene", "rose", "12.5%", "in", "1,000", "cells"])
        for start, end, word in found:
            self.assertEqual(text[start:end], word)

    def test_placeholder_is_no_word(self):
        text = "The gene " + ph(0) + " rose " + ph(12) + "."
        self.assertEqual(word_list(text), ["The", "gene", "rose"])
        self.assertEqual(pt.word_count(text), 3)
        self.assertEqual(pt.word_count(ph(7)), 0)

    def test_hyphenated_word_counts_once(self):
        self.assertEqual(pt.word_count("A GFP-tagged, well-known, once-off protein."), 5)

    def test_case_is_kept(self):
        self.assertEqual(word_list("Smith's mTOR"), ["Smith's", "mTOR"])
        self.assertEqual(word_list("Smith\u2019s"), ["Smith\u2019s"])

    def test_quotes_and_dashes_at_the_edge_are_not_part_of_the_word(self):
        self.assertEqual(word_list("'quoted' pre- and post-"), ["quoted", "pre", "and", "post"])

    def test_accented_and_greek_letters(self):
        self.assertEqual(word_list("M\u00fcller and \u03b2-catenin"), ["M\u00fcller", "and", "\u03b2-catenin"])

    def test_number_forms(self):
        self.assertEqual(word_list("5 mg, 3.5, 1,000.25 and 7."), ["5", "mg", "3.5", "1,000.25", "and", "7"])

    def test_empty(self):
        self.assertEqual(pt.words(""), [])
        self.assertEqual(pt.word_count("... --"), 0)


class NumericTokenTests(unittest.TestCase):
    def check(self, text, expected):
        self.assertEqual(pt.numeric_tokens(text), expected, repr(text))

    def test_unit_with_and_without_a_space(self):
        self.check("5 mg", ["5mg"])
        self.check("5mg", ["5mg"])

    def test_percent(self):
        self.check("12.5%", ["12.5%"])

    def test_unit_outside_the_list_gives_the_bare_number(self):
        self.check("3 of 4 samples", ["3", "4"])

    def test_range_puts_the_unit_on_the_last_number(self):
        self.check("10\u201320 nM", ["10", "20nM"])
        self.check("10-20 nM", ["10", "20nM"])

    def test_minus_sign_and_unit(self):
        self.check("-2.5 fold", ["-2.5fold"])
        self.check("a -2.5 fold change", ["-2.5fold"])
        self.check("+3 K and -4 K", ["+3K", "-4K"])

    def test_unit_must_not_continue_into_a_letter(self):
        self.check("5 mgs", ["5"])
        self.check("5mgs", ["5"])
        self.check("5 mMol", ["5"])
        self.check("3 samples", ["3"])

    def test_amounts_of_substance_are_units(self):
        # The Greek mu (U+03BC) and the micro sign (U+00B5) both give the micro sign.
        self.check("5 mmol and 20 μmol", ["5mmol", "20µmol"])
        self.check("5 mmol and 20 µmol", ["5mmol", "20µmol"])
        self.check("5 umol", ["5umol"])
        self.check("1 mol, 2 nmol, 3 pmol and 4 fmol", ["1mol", "2nmol", "3pmol", "4fmol"])
        for unit in ("mol", "mmol", "µmol", "nmol", "pmol", "fmol"):
            self.assertIn(unit, pt._UNITS)

    def test_only_one_space_between_number_and_unit(self):
        self.check("5  mg", ["5"])
        self.check("5\u00a0mg", ["5mg"])

    def test_every_unit_of_the_list(self):
        for unit in BRIEF_UNITS:
            self.check("4 " + unit, ["4" + unit])
            self.check("4" + unit, ["4" + unit])
            self.check("of 4 %s." % unit, ["4" + unit])
            self.check("4 %s, 5 %s" % (unit, unit), ["4" + unit, "5" + unit])

    def test_no_unit_of_the_list_continues_into_a_letter(self):
        for unit in BRIEF_UNITS:
            self.check("4 %sx" % unit, ["4"])
            self.check("4%sx" % unit, ["4"])

    def test_the_greek_letter_mu_works_like_the_micro_sign(self):
        for unit in BRIEF_UNITS:
            if "\u00b5" in unit:
                greek = unit.replace("\u00b5", "\u03bc")
                self.check("4 " + greek, ["4" + unit])

    def test_minus_signs_fold_to_a_hyphen(self):
        self.check("\u22122.5 fold", ["-2.5fold"])
        self.check("\u201380 \u00b0C", ["-80\u00b0C"])
        self.check("a \u22123 change and \u20134", ["-3", "-4"])
        self.check("+3 K", ["+3K"])
        self.check("10\u221220 nM", ["10", "20nM"])
        self.check("10\u201320 nM", ["10", "20nM"])

    def test_a_dash_after_a_unit_or_a_symbol_is_a_range_dash(self):
        self.check("10%\u201320% of cells", ["10%", "20%"])
        self.check("10%\u221220% of cells", ["10%", "20%"])
        self.check("2\u00d7\u20133\u00d7", ["2\u00d7", "3\u00d7"])
        self.check("3\u00b0\u20135\u00b0", ["3", "5"])
        self.check("10--20 nM", ["10", "20nM"])
        self.check("10%-20%", ["10%", "20%"])

    def test_a_masked_percent_range(self):
        for dash in ("--", "\u2013"):
            text = pm.mask("A 10\\%" + dash + "20\\% rise.", "latex").text
            self.assertEqual(pt.numeric_tokens(text), ["10", "20"], dash)

    def test_a_sign_stands_at_the_start_after_whitespace_or_an_opening_bracket(self):
        self.check("\u201380 \u00b0C", ["-80\u00b0C"])
        self.check("(\u22122.5 fold)", ["-2.5fold"])
        self.check("[-3] and {+4}", ["-3", "+4"])
        self.check("and\n-5", ["-5"])
        self.check("and\u00a0\u22125", ["-5"])
        self.check("a (\u20136)", ["-6"])

    def test_a_sign_after_a_relation_sign_belongs_to_the_number(self):
        self.check("x=-5", ["-5"])
        self.check("p=\u22120.5", ["-0.5"])
        self.check("r<\u20130.2", ["-0.2"])
        self.check("d\u2265-1", ["-1"])
        self.check("\u00b1-2", ["-2"])

    def test_no_sign_after_other_characters(self):
        self.check("a,-5", ["5"])
        self.check("a/\u22125", ["5"])
        self.check(ph(0) + "-5", ["5"])
        self.check("10%\u201320%", ["10%", "20%"])

    def test_a_hyphen_between_a_number_and_a_unit_attaches(self):
        for text in ("2-fold", "2 fold", "2\u2010fold", "2\u2011fold"):
            self.check(text, ["2fold"])
        self.check("a 5-mg dose", ["5mg"])
        self.check("a 3-d delay", ["3d"])
        self.check("IL-6 and a 2-fold rise", ["6", "2fold"])
        self.check("10-20 nM", ["10", "20nM"])

    def test_a_hyphen_before_an_unlisted_word_gives_the_bare_number(self):
        self.check("a 3-plate delay", ["3"])
        self.check("a 3-plates delay", ["3"])
        self.check("a 12-gene trial", ["12"])
        self.check("a 12-mouse trial", ["12"])

    def test_a_hyphen_before_a_time_unit_attaches(self):
        self.check("a 3-day delay", ["3day"])
        self.check("a 3-days delay", ["3day"])
        self.check("a 12-week trial", ["12week"])

    def test_every_time_unit_and_its_plural(self):
        for unit in TIME_UNITS:
            for form in (unit, unit + "s"):
                with self.subTest(form=form):
                    self.check("4 " + form, ["4" + unit])
                    self.check("4" + form, ["4" + unit])
                    self.check("4-" + form, ["4" + unit])
                    self.check("of 4 %s." % form, ["4" + unit])
                    self.check("4 %s, 5 %s" % (form, form), ["4" + unit, "5" + unit])
                    self.check("4 %sx" % form, ["4"])

    def test_a_time_unit_gives_the_same_token_as_its_plural(self):
        self.check("3 weeks", ["3week"])
        self.check("3 week", ["3week"])
        self.check("a 3-week course", ["3week"])
        self.assertNotEqual(pt.numeric_tokens("3 weeks"), pt.numeric_tokens("3 months"))
        self.assertNotEqual(pt.numeric_tokens("3 days"), pt.numeric_tokens("3 hours"))
        self.assertNotEqual(pt.numeric_tokens("3 weeks"), pt.numeric_tokens("3"))

    def test_the_time_abbreviations(self):
        for unit in TIME_ABBREVIATIONS:
            with self.subTest(unit=unit):
                self.check("4 " + unit, ["4" + unit])
                self.check("4" + unit, ["4" + unit])
                self.check("4 %sx" % unit, ["4"])
        self.check("4 wks", ["4wk"])
        self.check("4 yrs", ["4yr"])
        self.check("5 more", ["5"])
        self.check("5 months", ["5month"])

    def test_a_time_unit_in_a_capital_form_is_not_a_unit(self):
        self.check("3 Weeks", ["3"])

    def test_a_unit_may_take_a_per_unit_suffix(self):
        self.check("5 mg/kg", ["5mg/kg"])
        self.check("5mg/kg", ["5mg/kg"])
        self.check("5 mg/L", ["5mg/L"])
        self.check("2 ng/mL", ["2ng/mL"])
        self.check("3 mm/s", ["3mm/s"])
        self.check("4 \u00b5g/mL and 4 \u03bcg/mL", ["4\u00b5g/mL", "4\u00b5g/mL"])
        self.check("5 mg/kg/day", ["5mg/kg/day"])
        self.check("5 mg/kg/days", ["5mg/kg/day"])
        self.check("dose of 5 mg/kg.", ["5mg/kg"])

    def test_a_per_unit_suffix_needs_a_listed_unit_and_no_space(self):
        self.check("5 mg/kgs", ["5mg"])
        self.check("5 mg/dl", ["5mg"])
        self.check("5 mg / kg", ["5mg"])
        self.check("5 mg/ kg", ["5mg"])
        self.check("5 mg/", ["5mg"])
        self.check("3/4 of the cells", ["3", "4"])
        self.check("5/kg", ["5"])

    def test_cells_per_unit_is_a_unit_and_cells_alone_is_not(self):
        self.check("10 cells/mL", ["10cells/mL"])
        self.check("10cells/mL", ["10cells/mL"])
        self.check("10 cells", ["10"])
        self.check("10 cells/day", ["10cells/day"])
        self.check("10 cells/dl", ["10"])

    def test_a_changed_unit_text_gives_another_token(self):
        self.assertNotEqual(pt.numeric_tokens("5 mg/kg"), pt.numeric_tokens("5 mg"))
        self.assertNotEqual(pt.numeric_tokens("5 mg/kg"), pt.numeric_tokens("5 mg/L"))
        self.assertNotEqual(pt.numeric_tokens("5 mg/kg"), pt.numeric_tokens("5 g/kg"))

    def test_the_one_allowed_space_before_a_unit(self):
        for gap in (" ", "~", "\u2009", "\u200a", "\u00a0", "\u202f"):
            self.check("5" + gap + "mg", ["5mg"])
        self.check("5  mg", ["5"])
        self.check("5 ~mg", ["5"])

    def test_micro_sign_and_greek_mu_give_the_same_token(self):
        self.check("4 \u00b5M", ["4\u00b5M"])
        self.check("4 \u03bcM", ["4\u00b5M"])
        self.assertEqual(pt.numeric_tokens("4 \u00b5M and 2\u03bcg"), pt.numeric_tokens("4 \u03bcM and 2\u00b5g"))

    def test_one_space_before_a_percent_sign(self):
        for gap in (" ", "\u00a0", "\u2009", "\u200a", "\u202f"):
            self.check("10" + gap + "%", ["10%"])
        self.check("10  %", ["10"])
        self.check("10~%", ["10"])
        self.check("10 % of 5 mg", ["10%", "5mg"])

    def test_every_number_in_a_sentence_in_order(self):
        self.check("We gave 5 mg to 12 mice for 3 d (n = 12, p < 0.05).", ["5mg", "12", "3d", "12", "0.05"])

    def test_placeholder_digits_are_not_numbers(self):
        self.check("It gave " + ph(12) + " and 5 mg " + ph(3) + ".", ["5mg"])

    def test_digits_inside_a_name_are_not_numbers(self):
        self.check("p53 and Cas9 and H2O", [])

    def test_thousands_comma_and_decimal(self):
        self.check("1,000 cells and 3.25 mL.", ["1,000", "3.25mL"])

    def test_sentence_end_after_a_number(self):
        self.check("It was 5. Then 6, and 7.", ["5", "6", "7"])

    def test_empty(self):
        self.check("", [])
        self.check("no numbers here", [])


class ProtectedNameTests(unittest.TestCase):
    def test_brief_example(self):
        text = "The mTOR pathway in HeLa cells and GFP-tagged proteins, per Smith."
        self.assertEqual(pt.protected_names(text), {"mTOR", "HeLa", "GFP-tagged", "GFP", "Smith"})

    def test_a_capitalized_word_at_the_start_of_a_sentence_is_not_protected(self):
        text = "Smith found it. Jones agreed with Smith. Python is fast."
        self.assertEqual(pt.protected_names(text), {"Smith"})

    def test_a_sentence_start_with_an_acronym_digit_or_inner_capital_is_protected(self):
        text = "DNA binds. HeLa grows. P53 is here. IL-6 rises. PubMed lists it."
        self.assertEqual(pt.protected_names(text), {"DNA", "HeLa", "P53", "IL-6", "PubMed"})

    def test_tokens_that_hold_a_digit(self):
        self.assertEqual(pt.protected_names("We used p53, Cas9 and 12.5 mg."), {"p53", "Cas9", "12.5"})

    def test_case_is_kept(self):
        names = pt.protected_names("We used mTOR here.")
        self.assertIn("mTOR", names)
        self.assertNotIn("mtor", names)

    def test_a_placeholder_leading_a_sentence_does_not_move_the_start(self):
        text = ph(0) + " The cat sat with Bob."
        self.assertEqual(pt.protected_names(text), {"Bob"})

    def test_placeholder_digits_are_not_names(self):
        self.assertEqual(pt.protected_names("The " + ph(12) + " cat."), set())

    def test_the_word_after_a_masked_sentence_end_is_a_start(self):
        text = "It follows " + ph(3) + ". Then Bob left."
        self.assertEqual(pt.protected_names(text), {"Bob"})

    def test_the_word_after_an_abbreviation_is_not_a_start(self):
        self.assertEqual(pt.protected_names("See Fig. 2 for Bob."), {"Fig", "2", "Bob"})

    def test_lowercase_words_are_not_protected(self):
        self.assertEqual(pt.protected_names("the cat sat on the mat."), set())

    def test_empty(self):
        self.assertEqual(pt.protected_names(""), set())

    def test_include_starts(self):
        text = "Smith found it. Jones agreed. the cat sat."
        self.assertEqual(pt.protected_names(text), set())
        self.assertEqual(pt.protected_names(text, include_starts=True), {"Smith", "Jones"})
        self.assertEqual(pt.protected_names(text, False), set())

    def test_a_name_that_moves_away_from_the_sentence_start(self):
        before = pt.protected_names("Figure 2 shows it", include_starts=True)
        after = pt.protected_names("it appears in Figure 2")
        self.assertEqual(before, {"Figure", "2"})
        self.assertEqual(after, {"Figure", "2"})
        self.assertFalse(after <= pt.protected_names("Figure 2 shows it"))

    def test_a_possessive_is_the_name(self):
        before = pt.protected_names("Smith's data fit", include_starts=True)
        after = pt.protected_names("The data of Smith fit")
        self.assertEqual(before, {"Smith"})
        self.assertEqual(after, {"Smith"})
        self.assertEqual(pt.protected_names("We used mTOR's site."), {"mTOR"})

    def test_the_right_single_quote_folds_to_an_apostrophe(self):
        self.assertEqual(pt.protected_names("We thank Smith\u2019s lab."), pt.protected_names("We thank Smith's lab."))
        self.assertEqual(pt.protected_names("We thank Smith\u2019s lab."), {"Smith"})
        self.assertEqual(pt.protected_names("We thank O\u2019Brien."), {"O'Brien"})
        self.assertEqual(pt.protected_names("We thank O'Brien."), {"O'Brien"})

    def test_greek_mu_folds_to_the_micro_sign(self):
        self.assertEqual(pt.protected_names("We used 5 \u00b5M here."), pt.protected_names("We used 5 \u03bcM here."))
        self.assertEqual(pt.protected_names("We used 5 \u03bcM here."), {"5", "\u00b5M"})

    def test_a_number_with_a_hyphenated_word_keeps_the_number(self):
        self.assertEqual(pt.protected_names("A 12-week trial"), {"12"})
        self.assertEqual(pt.protected_names("A 12 week trial"), {"12"})
        self.assertEqual(pt.protected_names("a 10-fold rise"), {"10"})
        self.assertEqual(pt.protected_names("a 12-week-old mouse"), {"12"})

    def test_hyphenated_names_keep_their_hyphen(self):
        self.assertEqual(pt.protected_names("we used IL-6 and 5-HT and 3T3-L1 cells"), {"IL-6", "5-HT", "3T3-L1"})

    def test_a_hyphen_range_gives_two_numbers(self):
        self.assertEqual(pt.protected_names("we used 3-5 mice"), {"3", "5"})
        self.assertEqual(pt.protected_names("we used 3 to 5 mice"), {"3", "5"})

    def test_a_word_after_a_colon_counts_as_a_start(self):
        before = pt.protected_names("Results: the gene rose", include_starts=True)
        after = pt.protected_names("Results: The gene rose")
        self.assertEqual(before, {"Results"})
        self.assertEqual(after, set())
        self.assertTrue(after <= before)
        self.assertEqual(pt.protected_names("Results: The gene rose", include_starts=True), {"Results", "The"})
        self.assertEqual(pt.protected_names("Results:" + ph(0) + " The gene rose"), set())

    def test_a_word_after_other_punctuation_is_not_a_start(self):
        self.assertEqual(pt.protected_names("it rose; The gene fell"), {"The"})

    def test_a_protected_part_of_a_hyphenated_name_is_added(self):
        cases = [("mTOR-dependent growth", {"mTOR-dependent", "mTOR"}),
                 ("GFP-tagged cells", {"GFP-tagged", "GFP"}),
                 ("p53-dependent growth", {"p53-dependent", "p53"}),
                 ("HeLa-derived cells", {"HeLa-derived", "HeLa"}),
                 ("we used anti-GFP beads", {"anti-GFP", "GFP"}),
                 ("we used the GFP-tagged cells", {"GFP-tagged", "GFP"})]
        for text, expected in cases:
            self.assertEqual(pt.protected_names(text), expected, text)

    def test_names_without_a_lowercase_part_keep_their_result(self):
        self.assertEqual(pt.protected_names("we used IL-6"), {"IL-6"})
        self.assertEqual(pt.protected_names("we used 5-HT"), {"5-HT"})
        self.assertEqual(pt.protected_names("we used 3T3-L1 cells"), {"3T3-L1"})
        self.assertEqual(pt.protected_names("we used COVID-19 data"), {"COVID-19"})

    def test_a_part_of_digits_only_is_not_added(self):
        self.assertEqual(pt.protected_names("we used 5-HT-dependent cells"), {"5-HT-dependent", "HT"})

    def test_a_capitalized_part_follows_the_start_rule(self):
        self.assertEqual(pt.protected_names("the Smith-based approach"), {"Smith-based", "Smith"})
        self.assertEqual(pt.protected_names("Smith-based approach"), set())
        self.assertEqual(pt.protected_names("Smith-based approach", include_starts=True), {"Smith-based", "Smith"})

    def test_a_rewrite_that_drops_the_suffix_keeps_the_guard_quiet(self):
        before = pt.protected_names("mTOR-dependent growth", include_starts=True)
        after = pt.protected_names("growth that depends on mTOR")
        self.assertEqual(after, {"mTOR"})
        self.assertTrue(after <= before)

    def test_the_docstring_states_the_gap(self):
        doc = " ".join(pt.protected_names.__doc__.split())
        self.assertIn("a new name at a sentence start in `after` is not caught", doc)


class MarkBeforePlaceholderTests(unittest.TestCase):
    """An end mark directly before a placeholder (a citation, a footnote mark) still ends the sentence."""

    def test_latex_cite(self):
        self.assertEqual(masked_sents("Genes rose.\\cite{a2020} It fell.", "latex"), ["Genes rose.<0>", "It fell."])

    def test_latex_superscript_text(self):
        self.assertEqual(masked_sents("Genes rose.\\textsuperscript{1} It fell.", "latex"),
                         ["Genes rose.<0>", "It fell."])

    def test_latex_superscript_math(self):
        self.assertEqual(masked_sents("Genes rose.$^{1}$ It fell.", "latex"), ["Genes rose.<0>", "It fell."])

    def test_latex_footnote(self):
        self.assertEqual(masked_sents("Genes rose.\\footnote{Made up note.} It fell.", "latex"),
                         ["Genes rose.<0>Made up note.<1>", "It fell."])

    def test_plain_text_number_citation(self):
        self.assertEqual(masked_sents("Genes rose.[12] It fell.", "text"), ["Genes rose.<0>", "It fell."])

    def test_several_placeholders_after_the_mark(self):
        text = "Genes rose." + ph(0) + ph(1) + " It fell."
        self.assertEqual(sents(text), ["Genes rose." + ph(0) + ph(1), "It fell."])

    def test_question_and_exclamation_before_a_placeholder(self):
        self.assertEqual(sents("Did it rise?" + ph(0) + " Yes!" + ph(1) + " Later."),
                         ["Did it rise?" + ph(0), "Yes!" + ph(1), "Later."])

    def test_closing_quote_then_placeholder(self):
        self.assertEqual(sents('He said "stop."' + ph(3) + " Then left."), ['He said "stop."' + ph(3), "Then left."])

    def test_a_lowercase_word_after_the_placeholder_means_no_end(self):
        self.assertEqual(sents("It rose." + ph(0) + " and fell."), ["It rose." + ph(0) + " and fell."])

    def test_text_right_after_the_placeholder_means_no_end(self):
        self.assertEqual(sents("It rose." + ph(0) + "Then fell."), ["It rose." + ph(0) + "Then fell."])

    def test_the_end_of_the_paragraph_after_the_placeholder(self):
        self.assertEqual(sents("It rose." + ph(0)), ["It rose." + ph(0)])


class LegendAndParenthesisTests(unittest.TestCase):
    def test_four_panel_legend(self):
        text = ("(A) UMAP of the cells. (B) Heatmap of the genes. (C) Violin plots of the scores. "
                "(D) Dot plot of the groups.")
        self.assertEqual(sents(text), ["(A) UMAP of the cells.", "(B) Heatmap of the genes.",
                                       "(C) Violin plots of the scores.", "(D) Dot plot of the groups."])

    def test_numbered_parenthesis_and_bracket_start(self):
        self.assertEqual(sents("(1) First step. (2) Second step. [3] Third step."),
                         ["(1) First step.", "(2) Second step.", "[3] Third step."])

    def test_parenthetical_after_an_initial_like_capital(self):
        self.assertEqual(sents("It rose in group A. (See Fig. 2.)"), ["It rose in group A.", "(See Fig. 2.)"])

    def test_see_figure_after_a_real_end(self):
        self.assertEqual(sents("The gene rose. (See Fig. 2.) The rest fell."),
                         ["The gene rose.", "(See Fig. 2.)", "The rest fell."])

    def test_lowercase_parenthetical_stays_joined(self):
        self.assertEqual(sents("The gene rose. (see below)"), ["The gene rose. (see below)"])
        self.assertEqual(sents("The gene rose. [see below] It fell."), ["The gene rose. [see below] It fell."])

    def test_an_initial_before_a_capitalized_name_still_joins(self):
        self.assertEqual(sents("A. Smith wrote it. B. Jones agreed."), ["A. Smith wrote it.", "B. Jones agreed."])

    def test_an_initial_before_a_digit_stays_joined(self):
        self.assertEqual(sents("It was vitamin A. 5 mice were used."), ["It was vitamin A. 5 mice were used."])


class InitialTests(unittest.TestCase):
    def check(self, text, expected):
        self.assertEqual(sents(text), expected, text)

    def test_a_year_in_parentheses_or_brackets(self):
        self.check("Lee, A. (2020) showed it.", ["Lee, A. (2020) showed it."])
        self.check("Lee, A. [2020] showed it.", ["Lee, A. [2020] showed it."])

    def test_a_dotted_initialism_before_a_parenthesis(self):
        self.check("It crossed the U.S. (Texas) coast.", ["It crossed the U.S. (Texas) coast."])
        self.check("It crossed the U.S. [Texas] coast.", ["It crossed the U.S. [Texas] coast."])

    def test_a_dotted_initialism_before_a_capital_stays_joined(self):
        self.check("He left the U.S. Then he returned.", ["He left the U.S. Then he returned."])

    def test_a_year_after_an_initial(self):
        self.check("Smith, J. 2020. Title.", ["Smith, J. 2020.", "Title."])

    def test_a_quote_after_an_initial(self):
        self.check('Wang, J. "Title" appeared.', ['Wang, J. "Title" appeared.'])
        self.check("Wang, J. \u201cTitle\u201d appeared.", ["Wang, J. \u201cTitle\u201d appeared."])

    def test_a_placeholder_after_an_initial(self):
        self.check("Lee, A. " + ph(0) + " wrote.", ["Lee, A. " + ph(0) + " wrote."])
        self.assertEqual(masked_sents("Lee, A. \\cite{a} wrote.", "latex"), ["Lee, A. <0> wrote."])

    def test_an_emphasis_mark_after_an_initial(self):
        self.check("Lee, A. *Nature* paper.", ["Lee, A. *Nature* paper."])

    def test_a_digit_after_an_initial_stays_joined(self):
        self.check("It was vitamin A. 5 mice were used.", ["It was vitamin A. 5 mice were used."])

    def test_a_capital_after_an_initial_stays_joined(self):
        self.check("It was Plan B. Then we stopped.", ["It was Plan B. Then we stopped."])
        self.check("A. Smith wrote it. B. Jones agreed.", ["A. Smith wrote it.", "B. Jones agreed."])

    def test_a_bracketed_capital_after_an_initial_ends_the_sentence(self):
        self.check("It rose in group A. (See Fig. 2.)", ["It rose in group A.", "(See Fig. 2.)"])
        self.check("It rose in group A. [See Fig. 2.]", ["It rose in group A.", "[See Fig. 2.]"])


NEW_ABBREVIATIONS = ("Vol", "Vols", "Supp", "Ext", "Exp", "Inc", "Ltd", "Corp", "Univ", "Dept", "St", "Co")
LOWERCASE_ABBREVIATIONS = ("vol", "vols", "supp", "ext", "exp", "inc", "ltd", "corp", "univ", "dept")


class MoreAbbreviationTests(unittest.TestCase):
    def check(self, text, expected):
        self.assertEqual(sents(text), expected, text)

    def test_the_named_cases(self):
        self.check("We used reagents (Sigma-Aldrich, St. Louis, MO). They worked.",
                   ["We used reagents (Sigma-Aldrich, St. Louis, MO).", "They worked."])
        self.check("See Vol. 5 for the data. It holds.", ["See Vol. 5 for the data.", "It holds."])
        self.check("See pp. 3-9 for the data. It holds.", ["See pp. 3-9 for the data.", "It holds."])
        self.check("See p. 5 for the data. It holds.", ["See p. 5 for the data.", "It holds."])
        self.check("See Supp. Fig. 3 for the data. It holds.", ["See Supp. Fig. 3 for the data.", "It holds."])
        self.check("See Ext. Data Fig. 3 for the data. It holds.", ["See Ext. Data Fig. 3 for the data.", "It holds."])
        self.check("We used Thermo Fisher Scientific, Inc. Waltham made it. It holds.",
                   ["We used Thermo Fisher Scientific, Inc. Waltham made it.", "It holds."])
        self.check("We thank Univ. Cambridge for help. It holds.", ["We thank Univ. Cambridge for help.", "It holds."])

    def test_each_new_abbreviation_before_a_lowercase_word_a_digit_and_a_capital(self):
        for ab in NEW_ABBREVIATIONS + LOWERCASE_ABBREVIATIONS:
            for nxt in ("then", "2", "Smith"):
                text = "We cite %s. %s for the claim. Then we stop." % (ab, nxt)
                self.check(text, ["We cite %s. %s for the claim." % (ab, nxt), "Then we stop."])

    def test_page_marks_block_only_before_a_digit(self):
        self.check("See pp. 3 and p. 4 for it. Then stop.", ["See pp. 3 and p. 4 for it.", "Then stop."])
        self.check("It was shown by p. The next one failed.", ["It was shown by p.", "The next one failed."])
        self.check("It was shown by pp. The next one failed.", ["It was shown by pp.", "The next one failed."])

    def test_a_p_value_still_ends_a_sentence(self):
        self.check("The effect held at p < 0.05. The next one failed.",
                   ["The effect held at p < 0.05.", "The next one failed."])
        self.check("The effect held (p < 0.05). The next one failed.",
                   ["The effect held (p < 0.05).", "The next one failed."])

    def test_figure_abbreviation_is_unchanged(self):
        self.check("It held (see Fig. 2). Then it broke.", ["It held (see Fig. 2).", "Then it broke."])
        self.check("See Fig. 2 and Figs. 3-4. Then stop.", ["See Fig. 2 and Figs. 3-4.", "Then stop."])

    def test_a_word_that_ends_like_a_new_abbreviation_still_splits(self):
        self.check("We read the Convol. Then we stopped.", ["We read the Convol.", "Then we stopped."])
        self.check("We bought a tinc. Then we stopped.", ["We bought a tinc.", "Then we stopped."])


REFERENCE_WORDS = ("fig", "figs", "eq", "eqs", "ref", "refs", "sect", "chap", "mt", "cat")


class ReferenceAbbreviationTests(unittest.TestCase):
    def check(self, text, expected):
        self.assertEqual(sents(text), expected, text)

    def test_the_named_cases(self):
        self.check("See fig. 2 for the data. Then stop.", ["See fig. 2 for the data.", "Then stop."])
        self.check("Then eq. 3 gives the rate. It rose.", ["Then eq. 3 gives the rate.", "It rose."])
        self.check("As shown in ref. 5 the gene rose. Then it fell.",
                   ["As shown in ref. 5 the gene rose.", "Then it fell."])
        self.check("We used the antibody (Cat. No. 12345) as stated. Then we stopped.",
                   ["We used the antibody (Cat. No. 12345) as stated.", "Then we stopped."])
        self.check("We climbed Mt. Fuji in May. Then we left.", ["We climbed Mt. Fuji in May.", "Then we left."])

    def test_lowercase_and_capitalized_forms_before_a_digit(self):
        for word in REFERENCE_WORDS:
            for form in (word, word.capitalize()):
                text = "See %s. 2 for the data. Then stop." % form
                self.check(text, ["See %s. 2 for the data." % form, "Then stop."])

    def test_a_capitalized_form_before_a_capital(self):
        for word in REFERENCE_WORDS:
            text = "See %s. Smith for the data. Then stop." % word.capitalize()
            self.check(text, ["See %s. Smith for the data." % word.capitalize(), "Then stop."])

    def test_a_lowercase_form_before_a_capital_ends_the_sentence(self):
        for word in REFERENCE_WORDS:
            self.check("It was in the %s. Then we stopped." % word, ["It was in the %s." % word, "Then we stopped."])

    def test_a_lowercase_form_before_a_catalog_number(self):
        self.check("The antibody (cat. 12345) worked.", ["The antibody (cat. 12345) worked."])
        self.check("The antibody (cat. and lot) worked.", ["The antibody (cat. and lot) worked."])

    def test_a_lowercase_form_before_a_placeholder(self):
        self.assertEqual(masked_sents("See fig. \\ref{a} for it. Then stop.", "latex"),
                         ["See fig. <0> for it.", "Then stop."])

    def test_a_word_that_ends_like_one_still_splits(self):
        self.check("He fed the bobcat. Then he left.", ["He fed the bobcat.", "Then he left."])
        self.check("It had a config. Then it ran.", ["It had a config.", "Then it ran."])


class HardBreakTests(unittest.TestCase):
    HEADING = OPEN + "0" + CLOSE + "Introduction" + OPEN + "1" + CLOSE + "\nThe gene rose."

    def test_a_hard_break_at_the_newline_splits_the_heading(self):
        text = self.HEADING
        cut = text.index("\n")
        self.assertEqual([text[a:b] for a, b in pt.split_sentences(text, hard_breaks=[cut])],
                         [ph(0) + "Introduction" + ph(1), "The gene rose."])
        self.assertEqual([text[a:b] for a, b in pt.split_sentences(text, [cut])],
                         [ph(0) + "Introduction" + ph(1), "The gene rose."])

    def test_without_a_hard_break_it_is_one_sentence(self):
        text = self.HEADING
        self.assertEqual([text[a:b] for a, b in pt.split_sentences(text)], [text])
        self.assertEqual(pt.split_sentences(text, hard_breaks=()), pt.split_sentences(text))
        self.assertEqual(pt.split_sentences(text, hard_breaks=[]), pt.split_sentences(text))

    def test_paragraphs_take_the_same_parameter(self):
        text = self.HEADING
        cut = text.index("\n")
        self.assertEqual([text[a:b] for a, b in pt.paragraphs(text, hard_breaks=[cut])],
                         [ph(0) + "Introduction" + ph(1), "The gene rose."])
        self.assertEqual(pt.paragraphs(text), [(0, len(text))])

    def test_unsorted_and_duplicate_offsets(self):
        text = "aaa bbb ccc"
        variants = [[8, 4, 4, 8], [4, 8], (8, 4, 8, 4, 4), {4, 8}, (b for b in [8, 4, 4])]
        for breaks in variants:
            self.assertEqual([text[a:b] for a, b in pt.split_sentences(text, breaks)], ["aaa", "bbb", "ccc"])

    def test_offsets_at_the_ends_and_outside_the_text(self):
        text = "The gene rose."
        for breaks in ([0], [len(text)], [0, len(text)], [-5, 99], [0, 0, len(text), len(text) + 1]):
            self.assertEqual(pt.split_sentences(text, breaks), [(0, len(text))], breaks)
            self.assertEqual(pt.paragraphs(text, breaks), [(0, len(text))], breaks)

    def test_an_offset_inside_a_sentence_splits_it_in_two(self):
        text = "The gene rose here."
        self.assertEqual([text[a:b] for a, b in pt.split_sentences(text, [9])], ["The gene", "rose here."])
        self.assertEqual([text[a:b] for a, b in pt.split_sentences(text, [4])], ["The", "gene rose here."])

    def test_an_offset_inside_a_word_splits_there(self):
        text = "abcdef"
        self.assertEqual([text[a:b] for a, b in pt.split_sentences(text, [3])], ["abc", "def"])
        self.assertEqual([text[a:b] for a, b in pt.paragraphs(text, [3])], ["abc", "def"])

    def test_an_offset_in_the_whitespace_between_sentences(self):
        text = "One.   Two."
        self.assertEqual([text[a:b] for a, b in pt.split_sentences(text, [5])], ["One.", "Two."])
        self.assertEqual([text[a:b] for a, b in pt.split_sentences(text)], ["One.", "Two."])

    def test_a_piece_without_a_letter_or_digit_is_dropped_from_the_sentences(self):
        text = "One. -- Two."
        self.assertEqual([text[a:b] for a, b in pt.split_sentences(text, [5, 8])], ["One.", "Two."])
        self.assertEqual([text[a:b] for a, b in pt.paragraphs(text, [5, 8])], ["One.", "--", "Two."])

    def test_a_hard_break_works_with_blank_lines_and_crlf(self):
        text = "Head\r\nBody one. Body two.\r\n\r\nTail\r\nMore."
        cuts = [text.index("\r\nBody"), text.index("\r\nMore")]
        self.assertEqual([text[a:b] for a, b in pt.split_sentences(text, cuts)],
                         ["Head", "Body one.", "Body two.", "Tail", "More."])

    def test_a_hard_break_after_an_abbreviation_still_splits(self):
        text = "See Fig.\n2 here."
        self.assertEqual([text[a:b] for a, b in pt.split_sentences(text, [8])], ["See Fig.", "2 here."])


class DocstringTests(unittest.TestCase):
    NAMES = ("paragraphs", "split_sentences", "words", "word_count", "numeric_tokens", "protected_names")

    def docstrings(self):
        yield "module", pt.__doc__ or ""
        for name in self.NAMES:
            yield name, getattr(pt, name).__doc__ or ""

    @staticmethod
    def sentences(doc):
        return [x for x in re.split("(?<=[.!?])\\s+(?=[A-Z`(])", " ".join(doc.split())) if x]

    def test_every_public_function_has_a_docstring(self):
        for name in self.NAMES:
            self.assertTrue((getattr(pt, name).__doc__ or "").strip(), name)

    def test_no_sentence_is_longer_than_25_words(self):
        for name, doc in self.docstrings():
            for sentence in self.sentences(doc):
                self.assertLessEqual(len(sentence.split()), 25, "%s: %s" % (name, sentence))

    def test_no_three_sentences_in_a_row_start_alike(self):
        for name, doc in self.docstrings():
            firsts = [sentence.split()[0] for sentence in self.sentences(doc)]
            for i in range(len(firsts) - 2):
                self.assertFalse(firsts[i] == firsts[i + 1] == firsts[i + 2], "%s: %s" % (name, firsts))

    def test_no_em_dash(self):
        for name, doc in self.docstrings():
            self.assertNotIn("\u2014", doc, name)


class PlaceholderCharacterTests(unittest.TestCase):
    def test_the_core_module_owns_the_characters(self):
        self.assertEqual((pmc.OPEN, pmc.CLOSE), ("\ue000", "\ue001"))
        self.assertEqual((pm.OPEN, pm.CLOSE), (pmc.OPEN, pmc.CLOSE))

    def test_prose_text_does_not_import_the_masker(self):
        code = ("import sys; sys.path.insert(0, %r); import prose_text; "
                "print('prose_mask' in sys.modules, 'prose_mask_md' in sys.modules, 'prose_mask_core' in sys.modules)"
                % os.path.join(os.path.dirname(HERE), "scripts"))
        done = subprocess.run([sys.executable, "-I", "-B", "-c", code], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(done.returncode, 0, done.stderr)
        self.assertEqual(done.stdout.split(), ["False", "False", "True"])


class FuzzTests(unittest.TestCase):
    ALPHABET = ["A", "a", "b", ".", "!", "?", ":", ";", " ", "\n", "\r", '"', "'", "(", ")", "1", "2", ".", ",", "-",
                OPEN, CLOSE]

    def test_random_text(self):
        rng = random.Random(2026)
        for _ in range(2000):
            text = "".join(rng.choice(self.ALPHABET) for _ in range(rng.randint(0, 80)))
            spans = pt.split_sentences(text)
            last = 0
            for start, end in spans:
                piece = text[start:end]
                self.assertTrue(piece, repr(text))
                self.assertEqual(piece, piece.strip(), repr(text))
                self.assertTrue(any(c.isalnum() for c in piece), repr(text))
                self.assertGreaterEqual(start, last, repr(text))
                last = end
            last = 0
            for start, end in pt.paragraphs(text):
                self.assertTrue(text[start:end].strip(), repr(text))
                self.assertGreaterEqual(start, last, repr(text))
                last = end
            for start, end, word in pt.words(text):
                self.assertEqual(text[start:end], word, repr(text))
            self.assertEqual(pt.word_count(text), len(pt.words(text)))
            self.assertIsInstance(pt.numeric_tokens(text), list)
            self.assertIsInstance(pt.protected_names(text), set)

    def test_random_hard_breaks(self):
        rng = random.Random(11)
        for _ in range(1000):
            text = "".join(rng.choice(self.ALPHABET) for _ in range(rng.randint(0, 60)))
            breaks = [rng.randint(-3, len(text) + 3) for _ in range(rng.randint(0, 6))]
            for found in (pt.split_sentences(text, breaks), pt.paragraphs(text, breaks)):
                last = 0
                for start, end in found:
                    piece = text[start:end]
                    self.assertTrue(piece and piece == piece.strip(), repr((text, breaks)))
                    self.assertGreaterEqual(start, last, repr((text, breaks)))
                    self.assertFalse([b for b in breaks if start < b < end], repr((text, breaks, start, end)))
                    last = end
            for start, end in pt.split_sentences(text, breaks):
                self.assertTrue(any(c.isalnum() for c in text[start:end]), repr((text, breaks)))

    def test_a_sentence_never_holds_a_blank_line(self):
        rng = random.Random(7)
        for _ in range(500):
            text = "".join(rng.choice(self.ALPHABET) for _ in range(rng.randint(0, 80)))
            for start, end in pt.split_sentences(text):
                self.assertFalse(re.search(r"\n[^\S\n]*\n", text[start:end]), repr(text))


if __name__ == "__main__":
    unittest.main()
