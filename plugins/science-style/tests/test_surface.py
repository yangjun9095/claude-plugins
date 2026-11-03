"""Tests for lab/lab_surface.py. All text in this file is made up."""
import os
import sys
import unittest
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lab"))
sys.path.insert(0, HERE)

import lab_surface as lsu  # noqa: E402
import lab_text as lt  # noqa: E402

WORDLISTS = lsu.load_wordlists()
TEXT = ("We measured spores. The spores were counted by hand. Why do spores swell? "
        "Spores swell in water [CIT]. They may split (Fig. 2).")


def make_paper(work_id="W1", paragraph=TEXT):
    paper = lt.new_paper({"work_id": work_id})
    paper["sections"] = [
        {"heading": "Introduction", "kind": "intro", "paragraphs": [paragraph], "subsections": []},
        {"heading": "Methods", "kind": "methods", "paragraphs": ["We soaked 40 spores. They were weighed."],
         "subsections": []}]
    return lt.finish_paper(paper)


class MeasureTests(unittest.TestCase):
    def test_stats(self):
        self.assertEqual(lsu.stats([1, 2, 3, 4, 10]), {"mean": 4.0, "median": 3.0, "p90": 10.0, "n": 5})
        self.assertEqual(lsu.stats([1, 2]), {"mean": 1.5, "median": 1.5, "p90": 2.0, "n": 2})
        self.assertEqual(lsu.stats([])["n"], 0)

    def test_measures_on_a_short_text_match_counts_by_hand(self):
        m = lsu.measures(lsu.collect(make_paper()), WORDLISTS)
        self.assertEqual((m["n_sentences"], m["n_words"], m["n_paragraphs"]), (5, 22, 1))
        self.assertEqual(m["sentence_length"], {"mean": 4.4, "median": 4.0, "p90": 6.0, "n": 5})
        self.assertEqual(m["first_person_share"], 0.2)
        self.assertEqual(m["passive_share"], 0.2)
        self.assertEqual(m["questions_per_100"], 20.0)
        self.assertEqual(m["hedges_per_1000"], 45.45)
        self.assertEqual(m["hedge_words"], [["may", 1]])
        self.assertEqual(m["numbers_per_sentence"], 0.2)
        self.assertEqual(m["citations_per_sentence"], 0.2)
        self.assertEqual(m["figure_refs_per_paragraph"], 1.0)
        self.assertEqual(m["openers"], [["spores", 1], ["the", 1], ["they", 1], ["we", 1], ["why", 1]])
        self.assertEqual(m["paragraph_sentences"]["mean"], 5.0)

    def test_methods_text_never_counts(self):
        sentences = [s for _, s in lsu.collect(make_paper())["sentences"]]
        self.assertNotIn("We soaked 40 spores.", sentences)

    def test_passive_estimate(self):
        pattern = lsu.passive_pattern(WORDLISTS["irregular_participles"])
        for yes in ("Spores were carefully counted.", "Coats were sorted.", "Spores have been shown to swell.",
                    "It was split in two."):
            self.assertTrue(pattern.search(yes), yes)
        for no in ("The coat is red.", "We counted spores.", "Spores are large.", "It is indeed large."):
            self.assertFalse(pattern.search(no), no)

    def test_first_person(self):
        for yes in ("Let us count.", "I counted.", "Our coats split."):
            self.assertTrue(lsu.has_first_person(yes), yes)
        for no in ("The US data.", "Use the mouse."):
            self.assertFalse(lsu.has_first_person(no), no)

    def test_first_person_ignores_roman_numeral_i(self):
        for no in ("Type I interferon rose.", "MHC class I molecules bound.", "In a Phase I trial, doses rose.",
                   "Type I and II interferons rose.", "The I-band shrank.", "Complex I, II and III bound."):
            self.assertFalse(lsu.has_first_person(no), no)
        for yes in ("Here I show the result.", "We show the result.", "I show the result.",
                    "In this section, I show the result.", "I'm sure of the result."):
            self.assertTrue(lsu.has_first_person(yes), yes)

    def test_first_person_share_skips_roman_numeral_i(self):
        m = lsu.measures(lsu.collect(make_paper("W9", "Type I interferon rose. I measured it.")), WORDLISTS)
        self.assertEqual(m["first_person_share"], 0.5)

    def test_figure_references_count_tables(self):
        self.assertEqual(len(lsu.FIGREF.findall("See Tables 1 and 2.")), 1)
        self.assertEqual(len(lsu.FIGREF.findall("Supplementary Tables S1 and S2.")), 1)
        self.assertEqual(len(lsu.FIGREF.findall("See Table 1 and Fig. 2.")), 2)

    def test_top_breaks_ties_by_word(self):
        self.assertEqual(lsu.top(Counter({"b": 2, "a": 2, "c": 5}), 2), [["c", 5], ["a", 2]])

    def test_the_shipped_word_lists(self):
        self.assertIn("may", WORDLISTS["hedges"])
        self.assertIn("however", WORDLISTS["connectives"])
        self.assertIn("shown", WORDLISTS["irregular_participles"])


class DistinctiveTests(unittest.TestCase):
    def test_log_odds_favour_the_heavier_user(self):
        a = Counter({"spores": 50, "the": 50})
        b = Counter({"spores": 5, "the": 95})
        z = lsu.log_odds_z(a, b, a + b)
        self.assertGreater(z["spores"], 2)
        self.assertLess(z["the"], 0)

    def test_fewer_than_four_people_give_nothing(self):
        counts = {p: Counter({"spores": 3}) for p in ("a", "b", "c")}
        self.assertEqual(lsu.distinctive(counts), {})

    def test_one_shared_word_gives_empty_lists_not_an_error(self):
        counts = {p: Counter({"spores": 3}) for p in ("a", "b", "c", "d")}
        self.assertEqual(lsu.distinctive(counts), {"a": [], "b": [], "c": [], "d": []})

    def test_words_of_fewer_than_four_people_are_left_out(self):
        counts = {"a": Counter({"spores": 40, "the": 10, "fern": 30}), "b": Counter({"spores": 5, "the": 40, "fern": 1}),
                  "c": Counter({"spores": 5, "the": 40, "fern": 1}), "d": Counter({"spores": 5, "the": 40})}
        result = lsu.distinctive(counts)
        self.assertEqual(sorted(result), ["a", "b", "c", "d"])
        self.assertEqual([w for w, _ in result["a"]], ["spores", "the"])
        self.assertNotIn("fern", [w for w, _ in result["b"]])

    def test_run_surface_for_two_people(self):
        out = lsu.run_surface({"ada": [make_paper("W1")], "ben": [make_paper("W2", "Moss dries. It recovers.")]},
                              WORDLISTS)
        self.assertEqual(out["ada"]["n_papers"], 1)
        self.assertEqual(sorted(out["ada"]["per_paper"]), ["W1"])
        self.assertEqual(out["ben"]["pooled"]["n_sentences"], 2)
        self.assertEqual(out["ada"]["distinctive_words"], [])
        self.assertEqual(out["ada"]["distinctive_note"], "needs at least 4 people")

    def test_one_shared_pair_gives_empty_lists_and_a_note(self):
        # The four people share four words and exactly one pair of words: "spores swell".
        texts = {"ada": "Spores swell water coats.", "ben": "Spores swell coats water.",
                 "cy": "Water spores swell coats.", "di": "Coats water spores swell."}
        papers = {person: [make_paper("W" + person, text)] for person, text in texts.items()}
        out = lsu.run_surface(papers, WORDLISTS)
        for person in texts:
            self.assertEqual(out[person]["distinctive_pairs"], [], person)
            self.assertEqual(sorted(w for w, _ in out[person]["distinctive_words"]),
                             ["coats", "spores", "swell", "water"], person)
            self.assertEqual(out[person]["distinctive_note"], "fewer than 2 pairs shared by 4 people", person)

    def test_one_shared_word_and_no_pair_give_both_notes(self):
        papers = {person: [make_paper("W" + person, "Spores.")] for person in ("ada", "ben", "cy", "di")}
        out = lsu.run_surface(papers, WORDLISTS)
        self.assertEqual(out["ada"]["distinctive_words"], [])
        self.assertEqual(out["ada"]["distinctive_pairs"], [])
        self.assertEqual(out["ada"]["distinctive_note"],
                         "fewer than 2 words shared by 4 people; fewer than 2 pairs shared by 4 people")

    def test_enough_shared_words_and_pairs_give_no_note(self):
        texts = {"ada": "Spores swell in water. Spores swell in coats.", "ben": "Spores swell in moss. Moss swell in coats.",
                 "cy": "Spores swell in ferns. Ferns swell in coats.", "di": "Spores swell in lichens. Lichens swell in coats."}
        papers = {person: [make_paper("W" + person, text)] for person, text in texts.items()}
        out = lsu.run_surface(papers, WORDLISTS)
        for person in texts:
            self.assertTrue(out[person]["distinctive_words"], person)
            self.assertTrue(out[person]["distinctive_pairs"], person)
            self.assertEqual(out[person]["distinctive_note"], "", person)


if __name__ == "__main__":
    unittest.main()
