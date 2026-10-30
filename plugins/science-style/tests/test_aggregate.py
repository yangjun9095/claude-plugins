"""Tests for lab/lab_aggregate.py. All people, papers and text in this file are made up."""
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lab"))
sys.path.insert(0, HERE)

import lab_aggregate as la  # noqa: E402
import lab_checklist as lc  # noqa: E402
import lab_paths as lp  # noqa: E402
import lab_quotes as lq  # noqa: E402
import lab_text as lt  # noqa: E402
from fakes import ADA, make_extraction, make_paper_file  # noqa: E402

CHECKLIST = lc.load_checklist()
PARAGRAPH = "Here we show that spores swell in water. Long sentence " + "word " * 30 + "ends here."
INVENTED = ("brim tolk vane sorp quill dren mavo fell grisp holt jarn kell lumo nest orba pell ruve sild toma "
            "urn veld wick yarn zest amble bront clove drift ember fjord glen").split()


def quote_of(n_words, marks=0):
    """Return a quote of n_words invented words, followed by marks citation placeholders."""
    return " ".join(INVENTED[:n_words] + ["[CIT]"] * marks)


def meta(wid, group="senior", tier="high", year=2010, doi=None, arxiv_id=None):
    return {"work_id": wid, "status": "fetched", "group": group, "tier": tier, "cell": group + "/" + tier,
            "year": year, "doi": doi if doi is not None else "10.0000/" + wid.lower(), "arxiv_id": arxiv_id,
            "title": "Paper " + wid, "text_version": "published"}


def ok_check(wid, failed=(), unverified=()):
    return {"work_id": wid, "checked": 9, "failed": list(failed), "fail_rate": 0.0,
            "unverified_items": list(unverified), "errors": [], "status": "ok"}


class CountTests(unittest.TestCase):
    def setUp(self):
        self.metas = {"W1": meta("W1"), "W2": meta("W2"), "W3": meta("W3", group="first", tier="other")}
        self.extractions = {}
        for wid in self.metas:
            self.extractions[wid] = make_extraction(make_paper_file(wid, "ada", [PARAGRAPH]), CHECKLIST)
        self.extractions["W2"]["answers"]["title_form"]["value"] = "topic"
        self.extractions["W3"]["answers"]["intro_roles"]["value"] = ["field", "gap", "here-we"]

    def test_counts_by_value_group_and_tier(self):
        counts = la.count_answers(self.extractions, self.metas, CHECKLIST)
        title = counts["title_form"]["value"]
        self.assertEqual(title["n"], 3)
        self.assertEqual(title["all"], {"claim": 2, "topic": 1})
        self.assertEqual(title["by_group"], {"first": {"claim": 1}, "senior": {"claim": 1, "topic": 1}})
        self.assertEqual(title["n_by_group"], {"first": 1, "senior": 2})
        self.assertEqual(title["by_tier"]["other"], {"claim": 1})

    def test_ordered_lists_count_presence_first_and_last(self):
        roles = la.count_answers(self.extractions, self.metas, CHECKLIST)["intro_roles"]["value"]
        self.assertEqual(roles["all"], {"field": 3, "gap": 1, "here-we": 1})
        self.assertEqual(roles["first"], {"field": 3})
        self.assertEqual(roles["last"], {"field": 2, "here-we": 1})

    def test_objects_are_counted_per_key_and_items_without_closed_fields_are_absent(self):
        counts = la.count_answers(self.extractions, self.metas, CHECKLIST)
        self.assertEqual(counts["excitement"]["value.marker"]["all"], {"evaluative word": 3})
        self.assertNotIn("storyline", counts)
        self.assertEqual(counts["essay_argument"]["thesis_location"]["n"], 0)


class ProfileTests(unittest.TestCase):
    def test_a_profile_uses_only_papers_that_passed(self):
        manifest = {"person": "ada", "papers": [meta("W1", year=2009), meta("W2", year=2024),
                                                meta("W3", doi="", arxiv_id="1901.00001"), meta("W4")]}
        manifest["papers"][2]["doi"] = None
        extractions = {w: make_extraction(make_paper_file(w, "ada", [PARAGRAPH]), CHECKLIST)
                       for w in ("W1", "W2", "W3", "W4")}
        failed = {"item": "here_we", "field": "quote", "quote": "Here we show that spores swell in water.",
                  "reason": "not in the paper"}
        checks = {"W1": ok_check("W1"), "W2": ok_check("W2", failed=[failed], unverified=["here_we"]),
                  "W3": ok_check("W3"), "W4": dict(ok_check("W4"), status="redo")}
        stability = la.compute_stability([], CHECKLIST)
        profile = la.build_profile(ADA, manifest, extractions, checks, CHECKLIST, stability,
                                   {"pooled": {"n_sentences": 2}, "distinctive_words": [["swell", 3.1]]})
        self.assertEqual(profile["papers_used"], ["W1", "W2", "W3"])
        self.assertEqual(profile["n_papers"], 3)
        self.assertEqual(profile["left_out"], [{"work_id": "W4", "reason": "redo"}])
        self.assertEqual(profile["years"], {"first": 2009, "last": 2024})
        self.assertEqual(profile["unverified"], {"here_we": 1})
        self.assertEqual(profile["surface"], {"n_sentences": 2})
        texts = {(q["work_id"], q["item"], q["field"]) for q in profile["quotes"]}
        self.assertNotIn(("W2", "here_we", "quote"), texts)
        self.assertIn(("W1", "here_we", "quote"), texts)
        self.assertTrue(all(len(lt.words(q["text"])) <= la.QUOTE_LIMIT for q in profile["quotes"]))
        self.assertIn("10.48550/arxiv.1901.00001", {q["doi"] for q in profile["quotes"]})

    def test_the_profile_keeps_the_note_and_the_paper_count_of_the_surface(self):
        manifest = {"person": "ada", "papers": [meta("W1")]}
        extraction = make_extraction(make_paper_file("W1", "ada", [PARAGRAPH]), CHECKLIST)
        stability = la.compute_stability([], CHECKLIST)
        surface = {"n_papers": 4, "pooled": {}, "distinctive_words": [],
                   "distinctive_note": "the comparison has fewer than 3 people"}
        profile = la.build_profile(ADA, manifest, {"W1": extraction}, {"W1": ok_check("W1")}, CHECKLIST,
                                   stability, surface)
        self.assertEqual(profile["surface_papers"], 4)
        self.assertEqual(profile["distinctive_note"], "the comparison has fewer than 3 people")
        bare = la.build_profile(ADA, manifest, {"W1": extraction}, {"W1": ok_check("W1")}, CHECKLIST,
                                stability, None)
        self.assertIsNone(bare["surface_papers"])
        self.assertEqual(bare["distinctive_note"], "")

    def test_the_digest_holds_free_text_and_no_quotes(self):
        manifest = {"person": "ada", "papers": [meta("W1")]}
        extraction = make_extraction(make_paper_file("W1", "ada", [PARAGRAPH]), CHECKLIST)
        digest = la.build_digest("ada", manifest, {"W1": extraction}, CHECKLIST, ["W1"])
        free = digest["papers"][0]["free_text"]
        self.assertEqual(free["storyline.lines"], ["The first section asks how spores swell."])
        self.assertEqual(free["results_headings.headings"], ["A heading"])
        self.assertNotIn("gap_sentence.quote", free)


class QuoteTests(unittest.TestCase):
    def accepted(self, wid, quotes_by_item):
        """Return an extraction and a check. The paper text holds each quote, so the quote check
        accepts it."""
        paper = make_paper_file(wid, "ada", [PARAGRAPH] + [q + "." for q in quotes_by_item.values()])
        extraction = make_extraction(paper, CHECKLIST)
        for item_id, quote in quotes_by_item.items():
            extraction["answers"][item_id]["quote"] = quote
        check = lq.check_extraction(extraction, paper, CHECKLIST)
        self.assertEqual(check["failed"], [])
        check["status"] = "ok"
        return extraction, check

    def candidates(self, quotes_by_item, paper_meta=None):
        extraction, check = self.accepted("W1", quotes_by_item)
        return la.candidate_quotes({"W1": extraction}, {"W1": check}, {"W1": paper_meta or meta("W1")}, CHECKLIST)

    @staticmethod
    def texts(quotes, item):
        return [q["text"] for q in quotes if q["item"] == item]

    def test_a_quote_of_26_words_is_dropped_and_one_of_25_is_kept(self):
        quotes = self.candidates({"gap_sentence": quote_of(26), "here_we": quote_of(25)})
        self.assertEqual(self.texts(quotes, "gap_sentence"), [])
        self.assertEqual(self.texts(quotes, "here_we"), [quote_of(25)])

    def test_placeholders_do_not_count_as_words(self):
        marked = quote_of(25, marks=3)
        self.assertEqual(len(marked.split()), 28)
        self.assertEqual(len(lt.words(marked)), 25)
        quotes = self.candidates({"here_we": marked, "gap_sentence": quote_of(26, marks=3)})
        self.assertEqual(self.texts(quotes, "here_we"), [marked])
        self.assertEqual(self.texts(quotes, "gap_sentence"), [])

    def test_a_paper_with_neither_doi_nor_arxiv_id_gives_no_quotes(self):
        self.assertTrue(self.candidates({"here_we": quote_of(10)}))
        self.assertEqual(self.candidates({"here_we": quote_of(10)}, meta("W1", doi="")), [])
        arxiv = self.candidates({"here_we": quote_of(10)}, meta("W1", doi="", arxiv_id="1901.00001"))
        self.assertEqual({q["doi"] for q in arxiv}, {"10.48550/arxiv.1901.00001"})

    def test_a_quote_repeated_in_two_answers_of_one_item_appears_once(self):
        sentence = "Here we show that spores swell in water."
        paper = make_paper_file("W1", "ada", [PARAGRAPH])
        extraction = make_extraction(paper, CHECKLIST)
        entries = extraction["answers"]["excitement"]["value"]
        self.assertEqual(entries[0]["quote"], sentence)
        entries.append(dict(entries[0], marker="scope claim"))
        extraction["answers"]["limitations"]["quotes"] = [sentence, sentence]
        check = lq.check_extraction(extraction, paper, CHECKLIST)
        self.assertEqual(check["failed"], [])
        check["status"] = "ok"
        quotes = la.candidate_quotes({"W1": extraction}, {"W1": check}, {"W1": meta("W1")}, CHECKLIST)
        self.assertEqual(self.texts(quotes, "excitement"), [sentence])
        self.assertEqual(self.texts(quotes, "limitations"), [sentence])
        self.assertIn("here_we", {q["item"] for q in quotes if q["text"] == sentence})

    def test_a_quote_from_preprint_text_cites_the_preprint_doi(self):
        preprint = dict(meta("W1", doi="10.0000/journal.1"), text_version="preprint",
                        preprint_doi="https://doi.org/10.1101/222222")
        quotes = self.candidates({"here_we": quote_of(10)}, preprint)
        self.assertTrue(quotes)
        self.assertEqual({q["doi"] for q in quotes}, {"10.1101/222222"})
        self.assertEqual({q["text_version"] for q in quotes}, {"preprint"})
        published = self.candidates({"here_we": quote_of(10)}, dict(preprint, text_version="published"))
        self.assertEqual({q["doi"] for q in published}, {"10.0000/journal.1"})
        self.assertEqual({q["text_version"] for q in published}, {"published"})
        no_preprint_doi = self.candidates({"here_we": quote_of(10)}, dict(preprint, preprint_doi=None))
        self.assertEqual({q["doi"] for q in no_preprint_doi}, {"10.0000/journal.1"})
        self.assertEqual({q["text_version"] for q in no_preprint_doi}, {"preprint"})
        unknown = self.candidates({"here_we": quote_of(10)}, dict(preprint, text_version=None))
        self.assertEqual({q["text_version"] for q in unknown}, {None})


class StabilityTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_threshold_and_empty_pairs(self):
        paper = make_paper_file("W1", "ada", [PARAGRAPH])
        a = make_extraction(paper, CHECKLIST)
        b = make_extraction(paper, CHECKLIST, run="agreement")
        b["answers"]["title_form"]["value"] = "topic"
        stability = la.compute_stability([(a, b), (a, a)], CHECKLIST)
        self.assertEqual(stability["title_form"], {"agreement": 0.5, "pairs": 2, "stable": False})
        self.assertEqual(stability["figure_reference"]["stable"], True)
        self.assertNotIn("storyline", stability)
        self.assertEqual(la.compute_stability([], CHECKLIST)["title_form"], {"agreement": None, "pairs": 0, "stable": None})

    def test_collect_pairs_reads_valid_pairs_only(self):
        data = self.tmp.name
        paper = make_paper_file("W1", "ada", [PARAGRAPH])
        manifest = {"person": "ada", "papers": [meta("W1"), meta("W2")]}
        lp.write_json(lp.extraction_path(data, "ada", "W1"), make_extraction(paper, CHECKLIST))
        lp.write_json(lp.extraction_path(data, "ada", "W1", "agreement"), make_extraction(paper, CHECKLIST, run="agreement"))
        broken = make_extraction(paper, CHECKLIST)
        del broken["answers"]["here_we"]
        lp.write_json(lp.extraction_path(data, "ada", "W2"), broken)
        lp.write_json(lp.extraction_path(data, "ada", "W2", "agreement"), make_extraction(paper, CHECKLIST, run="agreement"))
        self.assertEqual(len(la.collect_pairs(data, [manifest], CHECKLIST)), 1)

    def write_pair(self, wid, edit_main=None, edit_agreement=None, agreement=True):
        paper = make_paper_file(wid, "ada", [PARAGRAPH])
        main = make_extraction(paper, CHECKLIST)
        agree = make_extraction(paper, CHECKLIST, run="agreement")
        if edit_main:
            edit_main(main)
        if edit_agreement:
            edit_agreement(agree)
        lp.write_json(lp.extraction_path(self.tmp.name, "ada", wid), main)
        if agreement:
            lp.write_json(lp.extraction_path(self.tmp.name, "ada", wid, "agreement"), agree)

    def write_bytes(self, wid, run, content):
        path = lp.extraction_path(self.tmp.name, "ada", wid, run)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(content)

    def collected(self, *wids):
        manifest = {"person": "ada", "papers": [meta(w) for w in wids]}
        return [a["work_id"] for a, b in la.collect_pairs(self.tmp.name, [manifest], CHECKLIST)]

    def test_an_unreadable_file_skips_only_its_pair(self):
        for wid in ("W1", "W2", "W3", "W4", "W5", "W6"):
            self.write_pair(wid)
        self.write_bytes("W2", "agreement", b"{not json")
        self.write_bytes("W3", "main", b"{not json")
        self.write_bytes("W4", "agreement", b"[]")
        self.write_bytes("W5", "main", b"\xff\xfe\x00")
        self.assertEqual(self.collected("W1", "W2", "W3", "W4", "W5", "W6"), ["W1", "W6"])

    def test_a_stale_version_skips_the_pair(self):
        self.write_pair("W1")
        self.write_pair("W2", edit_main=lambda e: e.update(prompt_version=0))
        self.write_pair("W3", edit_agreement=lambda e: e.update(prompt_version=0))
        self.write_pair("W4", edit_main=lambda e: e.update(checklist_version=0))
        self.write_pair("W5", edit_agreement=lambda e: e.update(checklist_version=0))
        self.assertEqual(self.collected("W1", "W2", "W3", "W4", "W5"), ["W1"])

    def test_a_wrong_run_label_skips_the_pair(self):
        self.write_pair("W1")
        self.write_pair("W2", edit_main=lambda e: e.update(run="agreement"))
        self.write_pair("W3", edit_agreement=lambda e: e.update(run="main"))
        self.assertEqual(self.collected("W1", "W2", "W3"), ["W1"])

    def test_an_extraction_of_another_paper_never_makes_a_pair(self):
        self.write_pair("W1")
        w1_main = lp.read_json(lp.extraction_path(self.tmp.name, "ada", "W1"))

        def copy_of_w1(extraction):
            extraction.clear()
            extraction.update(w1_main)

        self.write_pair("W2", edit_agreement=copy_of_w1)
        self.write_pair("W3", edit_agreement=lambda e: e.update(work_id="W1"))
        self.write_pair("W4", edit_main=lambda e: e.update(work_id="W1"))
        self.assertEqual(self.collected("W1", "W2", "W3", "W4"), ["W1"])

    def test_two_runs_on_different_paper_text_never_make_a_pair(self):
        other = make_paper_file("W2", "ada", [PARAGRAPH + " More text follows."])
        self.write_pair("W1")
        self.write_pair("W2", edit_agreement=lambda e: e.update(paper_sha256=other["sha256"]))
        self.assertNotEqual(other["sha256"], make_paper_file("W2", "ada", [PARAGRAPH])["sha256"])
        self.assertEqual(self.collected("W1", "W2"), ["W1"])

    def test_a_missing_file_skips_the_pair(self):
        self.write_pair("W1")
        self.write_pair("W2", agreement=False)
        self.write_pair("W3")
        os.remove(lp.extraction_path(self.tmp.name, "ada", "W3"))
        self.assertEqual(self.collected("W1", "W2", "W3"), ["W1"])


class QualityTests(unittest.TestCase):
    def test_the_report_lists_items_and_people_and_combines_nothing(self):
        stability = {"title_form": {"agreement": 0.8, "pairs": 5, "stable": True}}
        profile = {"person": "ada", "name": "Ada Quill", "n_papers": 12, "left_out": [{"work_id": "W9"}],
                   "stability": stability}
        checks = {"ada": [{"checked": 9, "failed": [{}]}, {"checked": 9, "failed": []}]}
        spot = {"ada": {"title_form": "correct", "here_we": "wrong"}}
        report = la.quality_report([profile], checks, spot, CHECKLIST)
        self.assertIn("| title_form | 0.80 | 5 | 1 of 1 |", report)
        self.assertIn("| here_we | n/a | 0 | 0 of 1 |", report)
        self.assertIn("| Ada Quill | 12 | 1 | 1 of 18 |", report)
        self.assertIn("No column combines the others into a score.", report)


if __name__ == "__main__":
    unittest.main()
