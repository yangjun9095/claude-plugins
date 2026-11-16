"""Tests for lab/lab_references.py. All people, papers and text in this file are made up."""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lab"))
sys.path.insert(0, HERE)

import lab_aggregate  # noqa: E402
import lab_references as lr  # noqa: E402


def paper(work_id, title, year, venue="Cell", doi=None, text_doi=None, text_version="published", **extra):
    out = {"work_id": work_id, "title": title, "year": year, "venue": venue, "doi": doi, "text_doi": text_doi,
           "text_version": text_version, "status": "fetched", "route": None, "preprint_doi": None, "arxiv_id": None}
    out.update(extra)
    return out


MANIFEST = {"person": "ada", "papers": [
    paper("W1", "Spores swell in water", 2012, "Cell", doi="10.0000/w1", text_doi="10.0000/w1"),
    paper("W2", "Coats split along a seam", 2020, "Cell Systems", doi="10.0000/w2", text_version="preprint",
          route="biorxiv", preprint_doi="10.1101/500002"),
    paper("W3", "Nets sort spores", 2021, "arXiv (Cornell University)", doi="10.48550/arxiv.2101.00005",
          text_version="arxiv", route="arxiv-html", arxiv_id="2101.00005"),
    paper("W4", "Moss dries on rocks", 2012, None, doi="10.0000/W4"),
    paper("W5", "A paper that the fetch replaced", 2015, "Cell", doi="10.0000/w5", status="replaced",
          text_version=None),
    paper("W6", "Ferns unroll in the dark", 2012, "", doi="10.0000/w6", text_doi="10.1101/600006",
          text_version="preprint"),
    paper("W7", "Does lichen grow on glass?", 2008, "Nature Genetics", doi="10.0000/w7"),
]}
PROFILE = {"person": "ada", "name": "Ada Quill", "papers_used": ["W1", "W2", "W3", "W4", "W6", "W7"], "n_papers": 6}


def bullets(section):
    return [line for line in section.splitlines() if line.startswith("- ")]


def by_title(section):
    """Map the title of each manifest paper to its bullet. A bullet starts with the title."""
    found = {}
    for line in bullets(section):
        for meta in MANIFEST["papers"]:
            if line.startswith("- " + " ".join(meta["title"].split())):
                found[meta["title"]] = line
    return found


class SectionTests(unittest.TestCase):
    def test_the_section_starts_with_the_heading_and_the_count_sentence(self):
        lines = lr.papers_section(MANIFEST, PROFILE).splitlines()
        self.assertEqual(lines[:4], ["## Papers", "", "The card rests on these 6 papers.", ""])

    def test_the_count_is_the_number_of_papers_used_not_of_papers_in_the_manifest(self):
        profile = dict(PROFILE, papers_used=["W1", "W2"])
        section = lr.papers_section(MANIFEST, profile)
        self.assertIn("The card rests on these 2 papers.", section)
        self.assertEqual(len(bullets(section)), 2)

    def test_the_list_holds_one_bullet_per_paper_used_and_skips_the_others(self):
        section = lr.papers_section(MANIFEST, PROFILE)
        self.assertEqual(len(bullets(section)), 6)
        self.assertNotIn("replaced", section)

    def test_the_papers_are_sorted_by_year_then_title(self):
        expected = ["Does lichen grow on glass?", "Ferns unroll in the dark", "Moss dries on rocks",
                    "Spores swell in water", "Coats split along a seam", "Nets sort spores"]
        lines = bullets(lr.papers_section(MANIFEST, PROFILE))
        self.assertEqual(len(lines), len(expected))
        for line, title in zip(lines, expected):
            self.assertTrue(line.startswith("- " + title), (line, title))

    def test_the_input_order_does_not_change_the_list(self):
        reverse = dict(PROFILE, papers_used=list(reversed(PROFILE["papers_used"])))
        self.assertEqual(lr.papers_section(MANIFEST, reverse), lr.papers_section(MANIFEST, PROFILE))

    def test_a_bullet_has_the_title_venue_year_doi_and_text_version(self):
        found = by_title(lr.papers_section(MANIFEST, PROFILE))
        self.assertEqual(found["Spores swell in water"],
                         "- Spores swell in water. Cell, 2012. doi:10.0000/w1 (published text)")
        self.assertEqual(found["Coats split along a seam"],
                         "- Coats split along a seam. Cell Systems, 2020. doi:10.1101/500002 (preprint text)")
        self.assertEqual(found["Nets sort spores"],
                         "- Nets sort spores. arXiv (Cornell University), 2021. "
                         "doi:10.48550/arxiv.2101.00005 (arxiv text)")

    def test_a_paper_without_a_venue_reads_no_venue(self):
        found = by_title(lr.papers_section(MANIFEST, PROFILE))
        self.assertIn(". no venue, 2012. ", found["Moss dries on rocks"])
        self.assertIn(". no venue, 2012. ", found["Ferns unroll in the dark"])

    def test_a_title_that_ends_in_a_question_mark_gets_no_second_stop(self):
        found = by_title(lr.papers_section(MANIFEST, PROFILE))
        self.assertEqual(found["Does lichen grow on glass?"],
                         "- Does lichen grow on glass? Nature Genetics, 2008. doi:10.0000/w7 (published text)")

    def test_a_title_that_ends_in_a_stop_keeps_one_stop(self):
        manifest = {"papers": [paper("W9", "  Spores   swell.  ", 2012, "Cell", doi="10.0000/w9")]}
        profile = {"papers_used": ["W9"]}
        self.assertEqual(bullets(lr.papers_section(manifest, profile)),
                         ["- Spores swell. Cell, 2012. doi:10.0000/w9 (published text)"])


class DoiTests(unittest.TestCase):
    def doi_of(self, **fields):
        manifest = {"papers": [paper("W9", "A title", 2012, **fields)]}
        line = lr.papers_section(manifest, {"papers_used": ["W9"]}).splitlines()[-1]
        return line.split(" doi:")[1].split(" (")[0]

    def test_the_text_doi_comes_first(self):
        self.assertEqual(self.doi_of(doi="10.0000/journal", text_doi="10.1101/preprint.1", text_version="preprint",
                                     preprint_doi="10.1101/other.2"), "10.1101/preprint.1")

    def test_the_doi_that_the_quotes_use_comes_next(self):
        fields = dict(doi="10.0000/journal", text_version="preprint", preprint_doi="10.1101/500009")
        self.assertEqual(self.doi_of(**fields), "10.1101/500009")
        self.assertEqual(self.doi_of(**fields), lab_aggregate.citation_doi(paper("W9", "A title", 2012, **fields)))
        arxiv = dict(doi="10.0000/journal", route="arxiv-html", arxiv_id="2101.00009", text_version="arxiv")
        self.assertEqual(self.doi_of(**arxiv), "10.48550/arxiv.2101.00009")

    def test_the_paper_doi_is_the_last_choice(self):
        self.assertEqual(self.doi_of(doi="10.0000/journal"), "10.0000/journal")

    def test_every_doi_matches_the_doi_of_the_profile_quotes(self):
        for meta in MANIFEST["papers"]:
            if meta["work_id"] in PROFILE["papers_used"]:
                section = lr.papers_section(MANIFEST, PROFILE)
                self.assertIn("doi:" + lab_aggregate.citation_doi(meta) + " (", section)

    def test_a_paper_with_no_doi_at_all_says_so(self):
        manifest = {"papers": [paper("W9", "A title", 2012, doi=None)]}
        line = lr.papers_section(manifest, {"papers_used": ["W9"]}).splitlines()[-1]
        self.assertEqual(line, "- A title. Cell, 2012. no doi (published text)")


class ErrorTests(unittest.TestCase):
    def test_a_paper_used_that_the_manifest_lacks_raises(self):
        with self.assertRaises(lr.ReferencesError) as caught:
            lr.papers_section(MANIFEST, dict(PROFILE, papers_used=["W1", "W404"]))
        self.assertIn("W404", str(caught.exception))

    def test_a_paper_used_that_the_manifest_marks_replaced_raises(self):
        with self.assertRaises(lr.ReferencesError):
            lr.papers_section(MANIFEST, dict(PROFILE, papers_used=["W5"]))

    def test_the_input_stays_unchanged(self):
        before = repr((MANIFEST, PROFILE))
        lr.papers_section(MANIFEST, PROFILE)
        self.assertEqual(repr((MANIFEST, PROFILE)), before)


CARD = "# Ada Quill\n\n## Sample\n\nThe card uses 6 papers.\n\n## Caveats\n\nTrainees drafted most papers.\n"


class AddSectionTests(unittest.TestCase):
    def setUp(self):
        self.section = lr.papers_section(MANIFEST, PROFILE)

    def test_the_section_goes_to_the_end_after_a_blank_line(self):
        text = lr.add_section(CARD, self.section)
        self.assertTrue(text.startswith(CARD + "\n## Papers\n"))
        self.assertTrue(text.endswith(self.section))
        self.assertEqual(text.count("## Papers"), 1)

    def test_the_text_above_the_section_stays_as_it_was(self):
        for card in (CARD, CARD.rstrip("\n"), CARD + "\n\n"):
            with self.subTest(card=card):
                text = lr.add_section(card, self.section)
                self.assertTrue(text.startswith(card.rstrip("\n")))
                self.assertTrue(text.index("## Papers") >= len(card.rstrip("\n")))
                self.assertEqual(text[:text.index("## Papers")].rstrip("\n"), card.rstrip("\n"))

    def test_a_second_run_gives_the_same_text(self):
        once = lr.add_section(CARD, self.section)
        self.assertEqual(lr.add_section(once, self.section), once)

    def test_a_run_replaces_an_old_section_and_never_duplicates_it(self):
        stale = lr.add_section(CARD, "## Papers\n\nThe card rests on these 2 papers.\n\n- Old. Cell, 2001. doi:10.0/x "
                                     "(published text)\n- Older. Cell, 2000. doi:10.0/y (published text)\n")
        text = lr.add_section(stale, self.section)
        self.assertEqual(text.count("## Papers"), 1)
        self.assertNotIn("Old.", text)
        self.assertEqual(text, lr.add_section(CARD, self.section))

    def test_everything_after_the_old_heading_goes(self):
        stale = CARD + "\n## Papers\n\nOld list.\n\n## Notes\n\nA note that follows.\n"
        text = lr.add_section(stale, self.section)
        self.assertNotIn("A note that follows.", text)
        self.assertEqual(text, lr.add_section(CARD, self.section))

    def test_a_line_that_only_starts_like_the_heading_is_not_the_heading(self):
        card = CARD + "\n## Papers and notes\n\nText.\n"
        text = lr.add_section(card, self.section)
        self.assertIn("## Papers and notes", text)
        self.assertEqual(text.count("\n## Papers\n"), 1)

    def test_a_card_with_windows_line_ends_keeps_one_section(self):
        once = lr.add_section("# Ada\r\n\r\n## Sample\r\n\r\nText.\r\n\r\n## Papers \r\n\r\nOld.\r\n", self.section)
        self.assertEqual(once.count("## Papers"), 1)
        self.assertNotIn("Old.", once)


class WriteTests(unittest.TestCase):
    def test_update_card_writes_the_file_and_returns_the_number_of_papers(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "ada.md")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(CARD)
            self.assertEqual(lr.update_card(path, MANIFEST, PROFILE), 6)
            with open(path, encoding="utf-8") as handle:
                first = handle.read()
            self.assertTrue(first.startswith(CARD))
            self.assertEqual(lr.update_card(path, MANIFEST, PROFILE), 6)
            with open(path, encoding="utf-8") as handle:
                self.assertEqual(handle.read(), first)
            self.assertEqual(os.listdir(folder), ["ada.md"])

    def test_a_bad_profile_leaves_the_card_unchanged(self):
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "ada.md")
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(CARD)
            with self.assertRaises(lr.ReferencesError):
                lr.update_card(path, MANIFEST, dict(PROFILE, papers_used=["W404"]))
            with open(path, encoding="utf-8") as handle:
                self.assertEqual(handle.read(), CARD)


if __name__ == "__main__":
    unittest.main()
