"""Tests for lab/lab_text.py. All text in this file is made up."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lab"))
sys.path.insert(0, HERE)

import lab_text as lt  # noqa: E402


def make_paper():
    paper = lt.new_paper({"work_id": "W1", "person": "ada", "title": "Fern spores swell"})
    paper["abstract"] = ["Fern spores swell in water."]
    paper["sections"] = [
        {"heading": "Introduction", "kind": "intro", "paragraphs": ["Spores need water.", "We ask how."],
         "subsections": []},
        {"heading": "Results", "kind": "results", "paragraphs": [],
         "subsections": [{"heading": "Spores swell fast", "paragraphs": ["They swell in 5 min [CIT]."]}]},
        {"heading": "Methods", "kind": "methods", "paragraphs": ["We soaked 40 spores."], "subsections": []},
    ]
    paper["legends"] = ["Figure 1. Spores in water."]
    return paper


class SplitTests(unittest.TestCase):
    def test_three_plain_sentences(self):
        self.assertEqual(lt.split_sentences("Spores swell. They split. Cells grow."),
                         ["Spores swell.", "They split.", "Cells grow."])

    def test_abbreviations_do_not_end_a_sentence(self):
        text = "Spores swell (Fig. 2). Ash et al. found this, e.g. in moss. Birch i.e. Ash agreed."
        self.assertEqual(lt.split_sentences(text),
                         ["Spores swell (Fig. 2).", "Ash et al. found this, e.g. in moss.",
                          "Birch i.e. Ash agreed."])

    def test_initials_and_decimals_do_not_end_a_sentence(self):
        self.assertEqual(lt.split_sentences("H. G. Ash measured 0.5 mm. The rest grew."),
                         ["H. G. Ash measured 0.5 mm.", "The rest grew."])

    def test_a_question_and_a_citation_after_the_stop(self):
        self.assertEqual(lt.split_sentences("Why do spores swell? They take up water.[CIT] Then they split."),
                         ["Why do spores swell?", "They take up water.[CIT]", "Then they split."])

    def test_a_closing_bracket_stays_with_its_sentence(self):
        self.assertEqual(lt.split_sentences("They swell (in water.) Then they split."),
                         ["They swell (in water.)", "Then they split."])

    def test_a_lower_case_word_after_a_stop_does_not_split(self):
        self.assertEqual(lt.split_sentences("The value was approx. ten."), ["The value was approx. ten."])

    def test_empty_text(self):
        self.assertEqual(lt.split_sentences("   "), [])


class WordTests(unittest.TestCase):
    def test_words_drop_placeholders_and_keep_hyphens_and_numbers(self):
        self.assertEqual(lt.words("Single-cell spores [CIT] swell 2.5 fold [EQ]."),
                         ["Single-cell", "spores", "swell", "2.5", "fold"])

    def test_words_keep_letters_with_accents(self):
        self.assertEqual(lt.words("García's fern"), ["García's", "fern"])


class NormalizeTests(unittest.TestCase):
    def test_quotes_dashes_spaces_and_ligatures(self):
        text = "“Spores” – the ﬁrst step’s   end"
        self.assertEqual(lt.normalize_for_match(text), "\"Spores\" - the first step's end")

    def test_titles(self):
        self.assertEqual(lt.normalize_title("Fern Spores: Swell, Split!"), "fern spores swell split")
        self.assertEqual(lt.normalize_title("Fern spóres swell"), "fern spores swell")

    def test_dois(self):
        self.assertEqual(lt.normalize_doi("https://doi.org/10.1000/ABC.1"), "10.1000/abc.1")
        self.assertEqual(lt.normalize_doi("doi:10.1000/x"), "10.1000/x")
        self.assertEqual(lt.normalize_doi("http://dx.doi.org/10.1000/x "), "10.1000/x")
        self.assertIsNone(lt.normalize_doi(None))
        self.assertIsNone(lt.normalize_doi(""))


class PaperTests(unittest.TestCase):
    def test_iter_paragraphs_reads_in_order_and_skips_methods(self):
        rows = list(lt.iter_paragraphs(make_paper()))
        self.assertEqual([r[0] for r in rows], ["abstract", "intro", "intro", "results"])
        self.assertEqual(rows[3][1], "Spores swell fast")

    def test_iter_paragraphs_can_keep_methods_and_drop_the_abstract(self):
        rows = list(lt.iter_paragraphs(make_paper(), include_abstract=False, exclude_kinds=()))
        self.assertEqual([r[0] for r in rows], ["intro", "intro", "results", "methods"])

    def test_body_words_count_the_body_without_methods_or_abstract(self):
        self.assertEqual(lt.body_words(make_paper()), 3 + 3 + 5)

    def test_word_counts_by_kind(self):
        self.assertEqual(lt.word_counts(make_paper()),
                         {"abstract": 5, "intro": 6, "results": 5, "methods": 4})

    def test_finish_paper_adds_counts_and_a_stable_hash(self):
        a = lt.finish_paper(make_paper())
        b = lt.finish_paper(make_paper())
        self.assertEqual(a["sha256"], b["sha256"])
        self.assertEqual(len(a["sha256"]), 64)
        b["sections"][0]["paragraphs"][0] = "Spores need light."
        self.assertNotEqual(lt.paper_sha256(b), a["sha256"])

    def test_canonical_text_holds_headings_paragraphs_and_legends(self):
        text = lt.canonical_text(make_paper())
        self.assertIn("Spores swell fast\nThey swell in 5 min [CIT].", text)
        self.assertTrue(text.endswith("Figure 1. Spores in water."))

    def test_new_paper_copies_the_metadata(self):
        paper = lt.new_paper({"work_id": "W9", "route": "ncbi-pmc", "extra": "ignored"})
        self.assertEqual(paper["work_id"], "W9")
        self.assertEqual(paper["route"], "ncbi-pmc")
        self.assertNotIn("extra", paper)
        self.assertEqual(paper["normalizer_version"], lt.NORMALIZER_VERSION)
        self.assertEqual(paper["sections"], [])


if __name__ == "__main__":
    unittest.main()
