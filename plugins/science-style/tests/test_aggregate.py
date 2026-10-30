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
from fakes import ADA, make_extraction, make_paper_file  # noqa: E402

CHECKLIST = lc.load_checklist()
PARAGRAPH = "Here we show that spores swell in water. Long sentence " + "word " * 30 + "ends here."


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
        self.assertTrue(all(len(q["text"].split()) <= la.QUOTE_LIMIT for q in profile["quotes"]))
        self.assertIn("10.48550/arxiv.1901.00001", {q["doi"] for q in profile["quotes"]})

    def test_the_digest_holds_free_text_and_no_quotes(self):
        manifest = {"person": "ada", "papers": [meta("W1")]}
        extraction = make_extraction(make_paper_file("W1", "ada", [PARAGRAPH]), CHECKLIST)
        digest = la.build_digest("ada", manifest, {"W1": extraction}, CHECKLIST, ["W1"])
        free = digest["papers"][0]["free_text"]
        self.assertEqual(free["storyline.lines"], ["The first section asks how spores swell."])
        self.assertEqual(free["results_headings.headings"], ["A heading"])
        self.assertNotIn("gap_sentence.quote", free)


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
