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


if __name__ == "__main__":
    unittest.main()
