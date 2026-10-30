"""Tests for lab/lab_card_check.py. All people, papers and text in this file are made up."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lab"))
sys.path.insert(0, HERE)

import lab_card_check as cc  # noqa: E402

PROFILE = {
    "person": "ada", "name": "Ada Quill", "checklist_version": 1, "n_papers": 12,
    "years": {"first": 2009, "last": 2024},
    "items": {"title_form": {"value": {"n": 12, "all": {"claim": 9, "topic": 3}}}},
    "surface": {"questions_per_100": 0.42, "sentence_length": {"mean": 23.5}},
    "quotes": [
        {"item": "here_we", "text": "Here we show that spores swell in 5 min when they touch water",
         "doi": "10.0000/fern.1", "work_id": "W1"},
        {"item": "limitations", "text": "Our data do not tell us why the coat splits along one seam",
         "doi": "10.0000/fern.2", "work_id": "W2"},
        {"item": "excitement", "text": "This simple rule predicts every split we measured",
         "doi": "10.0000/fern.1", "work_id": "W1"},
        {"item": "explanations", "text": "The coat works like a zip that opens from one end",
         "doi": "10.0000/fern.1", "work_id": "W1"},
    ],
}

CARD = """# Ada Quill

## Sample
The card uses 12 papers from 2009 to 2024.

## Storyline
Each paper moves from one question to the next.

## Introduction
9 of 12 titles state a claim. A typical opening: "Here we show that spores swell in 5 min" (doi:10.0000/fern.1).

## Results
Results sections open with the finding.

## Excitement
“This simple rule predicts every split we measured” (doi:10.0000/fern.1)

## Limitations
"Our data do not tell us why the coat splits" (doi:10.0000/fern.2)

## Discussion
The discussion returns to the first question.

## Sentences and words
Sentences have 23.5 words on average. There are 0.42 questions per 100 sentences.

## Signature moves
Plain comparisons explain the mechanism.

## Caveats
Trainees drafted most senior-author papers.
"""


def check(text, profiles=(PROFILE,), kind="card"):
    return cc.check_text(text, kind, list(profiles))


class CardTests(unittest.TestCase):
    def test_a_valid_card_passes(self):
        self.assertEqual(check(CARD), [])

    def test_a_missing_or_moved_heading_fails(self):
        self.assertTrue(any("headings" in f for f in check(CARD.replace("## Caveats", "## Notes"))))
        moved = CARD.replace("## Results", "## Tmp").replace("## Excitement", "## Results").replace("## Tmp", "## Excitement")
        self.assertTrue(any("headings" in f for f in check(moved)))

    def test_an_invented_number_fails(self):
        self.assertIn("number not in the profile data: 73", check(CARD.replace("uses 12 papers", "uses 73 papers")))

    def test_a_percentage_fails(self):
        self.assertIn("the text uses a percentage", check(CARD.replace("9 of 12 titles", "75% of titles")))

    def test_a_quote_without_a_doi_fails(self):
        failures = check(CARD.replace("Plain comparisons", 'The phrase "spores swell" and plain comparisons'))
        self.assertTrue(any(f.startswith("quote without a DOI") for f in failures))

    def test_a_long_quote_fails(self):
        long_quote = " ".join(["spores"] * 26)
        failures = check(CARD.replace("Plain comparisons", '"{}" (doi:10.0000/fern.2) Plain'.format(long_quote)))
        self.assertTrue(any("more than 25 words" in f for f in failures))

    def test_a_quote_that_is_not_verified_fails(self):
        failures = check(CARD.replace("Plain comparisons", '"Spores fly at night" (doi:10.0000/fern.2) Plain'))
        self.assertTrue(any(f.startswith("quote not among the verified quotes of 10.0000/fern.2") for f in failures))

    def test_a_quote_with_the_doi_of_another_paper_fails(self):
        failures = check(CARD.replace("(doi:10.0000/fern.2)", "(doi:10.0000/fern.1)"))
        self.assertTrue(any(f.startswith("quote not among the verified quotes of 10.0000/fern.1") for f in failures))

    def test_three_quotes_from_one_paper_fail(self):
        third = '"The coat works like a zip" (doi:10.0000/fern.1) Plain'
        self.assertIn("3 quotes from 10.0000/fern.1; the limit is 2", check(CARD.replace("Plain", third, 1)))

    def test_too_many_quotes_fail(self):
        quotes = [{"item": "signature_phrases", "text": "Spore phrase number {}".format(i),
                   "doi": "10.0000/q{}".format(i), "work_id": "W{}".format(i)} for i in range(21)]
        profile = dict(PROFILE, quotes=PROFILE["quotes"] + quotes)
        extra = " ".join('"Spore phrase number {}" (doi:10.0000/q{})'.format(i, i) for i in range(21))
        failures = check(CARD.replace("Plain comparisons", extra), profiles=[profile])
        self.assertTrue(any(f.startswith("24 quotes; the limit is 20") for f in failures))

    def test_a_long_card_fails(self):
        failures = check(CARD + "\nfiller " * 900)
        self.assertTrue(any(f.startswith("the text has") and "the limit is 900" in f for f in failures))

    def test_n_larger_than_m_fails(self):
        self.assertIn("12 of 9 has N larger than M", check(CARD.replace("9 of 12 titles", "12 of 9 titles")))

    def test_numbers_inside_quotes_are_ignored(self):
        self.assertNotIn("number not in the profile data: 5", check(CARD))


class PrinciplesTests(unittest.TestCase):
    def test_a_principles_file_with_its_headings_passes(self):
        text = ("# Principles\n\n## Shared moves\n9 of 12 titles state a claim.\n\n"
                "## Distinctive moves\n\"The coat works like a zip\" (doi:10.0000/fern.1)\n")
        self.assertEqual(check(text, kind="principles"), [])
        self.assertTrue(any("headings" in f for f in check(CARD, kind="principles")))


# The tests below close the bypasses found in the review of the first version. All data is invented.
GROUPED = dict(PROFILE, papers_used=["W{}".format(i) for i in range(12)], items={"title_form": {"value": {
    "n": 12, "all": {"claim": 9, "topic": 3}, "first": {"claim": 8},
    "by_group": {"senior": {"claim": 5}}, "n_by_group": {"senior": 6, "other": 6},
    "by_tier": {"high": {"claim": 4}}, "n_by_tier": {"high": 7}}}})
OTHER = dict(PROFILE, person="bo", name="Bo Reed", n_papers=10,
             items={"title_form": {"value": {"n": 10, "all": {"claim": 7, "topic": 3}}}})
SIGNATURE = "Plain comparisons explain the mechanism."


def sig(sentence):
    """Return the card with the sentence in place of the sentence of the Signature moves section."""
    return CARD.replace(SIGNATURE, sentence)


def principles(sentence):
    return "# Principles\n\n## Shared moves\n{}\n\n## Distinctive moves\nThe coat works like a zip.\n".format(sentence)


class CountPairTests(unittest.TestCase):
    def test_a_count_with_the_wrong_denominator_or_count_fails(self):
        for sentence in ("12 of 12 titles state a claim.", "3 of 9 titles state a claim.",
                         "3 out of 9 titles state a claim.", "12/12 titles state a claim."):
            failures = check(CARD.replace("9 of 12 titles state a claim.", sentence))
            self.assertTrue(any(f.startswith("count not in the profile data: ") for f in failures), sentence)
        self.assertIn("count not in the profile data: 12 of 12",
                      check(CARD.replace("9 of 12 titles", "12 of 12 titles")))
        self.assertIn("count not in the profile data: 3 of 9",
                      check(CARD.replace("9 of 12 titles", "3 out of 9 titles")))

    def test_a_count_of_the_profile_passes_in_each_form(self):
        for form in ("9 of 12 titles", "9 out of 12 titles", "9/12 titles", "9 of the 12 titles", "3 of 12 titles"):
            self.assertEqual(check(CARD.replace("9 of 12 titles", form)), [], form)

    def test_counts_of_groups_tiers_and_first_values_use_their_own_denominators(self):
        def failures(sentence):
            return check(CARD.replace("9 of 12 titles state a claim.", sentence), profiles=[GROUPED])
        self.assertEqual(failures("5 of 6 senior-author titles state a claim."), [])
        self.assertEqual(failures("4 of 7 titles of high-tier venues state a claim."), [])
        self.assertEqual(failures("8 of 12 titles state a claim."), [])
        self.assertIn("count not in the profile data: 5 of 12", failures("5 of 12 titles state a claim."))
        self.assertIn("count not in the profile data: 6 of 7", failures("6 of 7 titles state a claim."))

    def test_the_paper_total_counts_only_before_the_word_papers(self):
        profile = GROUPED
        self.assertEqual(check(CARD.replace("9 of 12 titles state a claim.", "12 of 12 papers have a full text."),
                               profiles=[profile]), [])
        self.assertIn("count not in the profile data: 12 of 12",
                      check(CARD.replace("9 of 12 titles", "12 of 12 titles"), profiles=[profile]))

    def test_paper_splits_pass_as_counts(self):
        profile = dict(PROFILE, by_cell={"senior_high": 6, "senior_other": 1, "first_high": 4, "first_other": 1},
                       by_group={"senior": 7, "first": 5}, by_tier={"high": 10, "other": 2},
                       text_versions={"published": 10, "preprint": 2})

        def failures(sentence):
            return check(sig(sentence), profiles=[profile])
        self.assertEqual(failures("7 of 12 papers come from senior-author groups."), [])
        self.assertEqual(failures("2 of 12 papers use the preprint text."), [])
        self.assertEqual(failures("10 of 12 papers appear in high-tier venues."), [])
        self.assertEqual(failures("4 of 12 papers belong to the first-author high-tier cell."), [])
        self.assertIn("count not in the profile data: 8 of 12",
                      failures("8 of 12 papers come from senior-author groups."))
        self.assertIn("count not in the profile data: 7 of 12", failures("7 of 12 titles state a claim."))

    def test_a_count_in_capitals_is_checked(self):
        for form in ("12 OF 12 titles", "12 Of 12 titles", "3 OUT OF 9 titles"):
            failures = check(CARD.replace("9 of 12 titles", form))
            self.assertTrue(any(f.startswith("count not in the profile data: ") for f in failures), form)
        self.assertIn("count not in the profile data: 12 of 12",
                      check(CARD.replace("9 of 12 titles", "12 OF 12 titles")))
        self.assertEqual(check(CARD.replace("9 of 12 titles", "9 OF 12 titles")), [])

    def test_n_larger_than_m_gives_one_failure_for_the_pair(self):
        failures = check(CARD.replace("9 of 12 titles", "12 of 9 titles"))
        self.assertEqual([f for f in failures if " of " in f], ["12 of 9 has N larger than M"])

    def test_principles_accepts_a_pair_of_one_profile_and_rejects_a_mixed_or_unknown_pair(self):
        both = [GROUPED, OTHER]

        def failures(sentence):
            return check(principles(sentence), profiles=both, kind="principles")
        self.assertEqual(failures("9 of 12 titles state a claim."), [])
        self.assertEqual(failures("7 of 10 titles state a claim."), [])
        self.assertEqual(failures("7 of 12 titles state a claim."), ["count not in the profile data: 7 of 12"])
        self.assertIn("count not in the profile data: 5 of 9", failures("5 of 9 titles state a claim."))


class NumberWordTests(unittest.TestCase):
    def assertWord(self, sentence, word):
        self.assertIn("write numbers as digits: " + word, check(sig(sentence)), sentence)

    def test_number_words_fail(self):
        self.assertWord("Nine of twelve titles state a claim.", "Nine")
        self.assertWord("Nine of twelve titles state a claim.", "twelve")
        self.assertWord("All fifteen papers use a question.", "fifteen")
        self.assertWord("Seventy-three percent of titles state a claim.", "Seventy-three")
        self.assertWord("Three quarters of titles state a claim.", "quarters")
        self.assertWord("Half of titles state a claim.", "Half")
        self.assertWord("Titles state a claim twice as often.", "twice")
        self.assertWord("The rate rose five-fold.", "five-fold")
        self.assertWord("The rate rose 3-fold.", "3-fold")
        self.assertWord("The rate rose twofold.", "twofold")
        self.assertWord("About a dozen titles state a claim.", "dozen")
        self.assertWord("Several hundred words repeat.", "hundred")

    def test_one_fails_only_before_of_or_in_and_a_number(self):
        self.assertWord("One in five titles states a claim.", "One in five")
        self.assertWord("Only one of 12 titles states a claim.", "one of 12")
        self.assertEqual(check(sig("One question leads to the next, and one of the titles asks it.")), [])

    def test_one_fails_before_out_of_and_before_of_the_and_a_number(self):
        self.assertWord("One out of 12 titles states a claim.", "One out of 12")
        self.assertWord("Only one of the 12 titles states a claim.", "one of the 12")
        self.assertWord("Only one of the twelve titles states a claim.", "one of the twelve")
        self.assertEqual(check(sig("One out of the question leads to the next, and one of the titles asks it.")), [])

    def test_percentages_fail_in_every_form(self):
        for sentence in ("12 percent of titles state a claim.", "12 per cent of titles state a claim.",
                         "The percentage of titles rose.", "12\uff05 of titles state a claim.",
                         "Seventy-three percent of titles state a claim."):
            self.assertIn("the text uses a percentage", check(sig(sentence)), sentence)

    def test_number_words_inside_a_quote_pass(self):
        quote = {"item": "explanations", "text": "The two halves open at once", "doi": "10.0000/fern.3",
                 "work_id": "W3"}
        profile = dict(PROFILE, quotes=PROFILE["quotes"] + [quote])
        sentence = 'The phrase "The two halves open at once" (doi:10.0000/fern.3) appears often.'
        self.assertEqual(check(sig(sentence), profiles=[profile]), [])


class QuoteBypassTests(unittest.TestCase):
    def test_a_quote_broken_across_lines_fails(self):
        failures = check(sig('The phrase "spores swell in\n5 min" appears often.'))
        self.assertIn("unpaired or multi-line double quote", failures)

    def test_other_quote_marks_fail(self):
        failures = check(sig("\u00abHere we show that spores swell\u00bb (doi:10.0000/fern.1) appears often."))
        self.assertIn("unpaired or multi-line double quote", failures)
        self.assertIn("DOI tag without a quote", failures)
        failures = check(sig("\u201eHere we show that spores swell\u201c (doi:10.0000/fern.1) appears often."))
        self.assertIn("unpaired or multi-line double quote", failures)

    def test_a_bare_doi_tag_fails(self):
        failures = check(sig("Plain comparisons (doi:10.0000/fern.1) explain the mechanism."))
        self.assertIn("DOI tag without a quote", failures)
        self.assertFalse(any(f.startswith("number not in the profile data") for f in failures))

    def test_a_short_verified_quote_passes(self):
        quote = {"item": "signature_phrases", "text": "Spores swell.", "doi": "10.0000/fern.4", "work_id": "W4"}
        profile = dict(PROFILE, quotes=PROFILE["quotes"] + [quote])
        sentence = 'The phrase "Spores swell." (doi:10.0000/fern.4) appears often.'
        self.assertEqual(check(sig(sentence), profiles=[profile]), [])


class NumberBypassTests(unittest.TestCase):
    def assertNumber(self, sentence, number, profile=PROFILE):
        failures = check(sig(sentence), profiles=[profile])
        self.assertIn("number not in the profile data: " + number, failures, sentence)

    def test_a_number_with_letters_after_it_counts(self):
        self.assertNumber("The first paper is from the 1990s.", "1990")
        self.assertNumber("Titles state a claim 7x more often.", "7")
        self.assertNumber("The 7th paper asks a question.", "7")

    def test_a_number_after_a_dot_counts_with_its_dot(self):
        profile = dict(PROFILE, extra={"rate": 0.73})
        self.assertNumber("Each paper has .73 questions.", ".73", profile)
        self.assertEqual(check(sig("Each paper has 0.73 questions."), profiles=[profile]), [])

    def test_a_comma_inside_a_number_splits_it_unless_it_is_a_thousands_form(self):
        self.assertNumber("A total of 9,73 words.", "73")
        self.assertNumber("A total of 1,0005 words.", "0005")

    def test_a_letter_or_digit_before_the_digits_hides_an_identifier(self):
        self.assertEqual(check(sig("The gene p53, the mark H3K27 and the work W123 appear.")), [])

    def test_the_numbers_100_and_1000_pass_only_after_per(self):
        self.assertNumber("More than 100 papers use a question.", "100")
        self.assertNumber("The papers have 1,000 words.", "1,000")
        self.assertEqual(check(sig("The rate is 0.42 per 1,000 sentences.")), [])
        self.assertEqual(check(sig("The rate is 0.42 per 1000 sentences.")), [])
        self.assertEqual(check(sig("The rate is 0.42 questions per 100 sentences.")), [])

    def test_a_number_of_1000_or_more_passes_with_a_comma(self):
        profile = dict(PROFILE, n_words=24317)
        self.assertEqual(check(sig("The papers have 24,317 words."), profiles=[profile]), [])
        self.assertEqual(check(sig("The papers have 24317 words."), profiles=[profile]), [])
        self.assertNumber("The papers have 24,318 words.", "24,318", profile)

    def test_a_float_allows_its_neighbours_when_rounded_down_and_up(self):
        profile = dict(PROFILE, extra={"a": 0.25, "b": 0.65, "c": 23.456})
        ok = "The rates are 0.2, 0.3, 0.25, 0.6, 0.7, 23.4, 23.45 and 23.46."
        self.assertEqual(check(sig(ok), profiles=[profile]), [])
        self.assertNumber("The rate is 0.26.", "0.26", profile)
        self.assertNumber("The rate is 0.1.", "0.1", profile)
        self.assertNumber("The rate is 0.8.", "0.8", profile)

    def test_profile_numbers_gives_the_comma_and_rounded_forms_and_skips_non_numbers(self):
        found = cc.profile_numbers({"n": 24317, "r": 0.25, "flag": True, "name": "ada", "x": float("nan")})
        self.assertTrue({"24317", "24,317", "0.25", "0.2", "0.3"} <= found)
        self.assertNotIn("True", found)
        self.assertNotIn("1", found)


if __name__ == "__main__":
    unittest.main()
