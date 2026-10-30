"""Tests for lab/lab_checklist.py and lab/lab_quotes.py. All text in this file is made up."""
import copy
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lab"))
sys.path.insert(0, HERE)

import lab_checklist as lc  # noqa: E402
import lab_paths as lp  # noqa: E402
import lab_quotes as lq  # noqa: E402
from fakes import make_extraction, make_paper_file  # noqa: E402

CHECKLIST = lc.load_checklist()
PARAGRAPHS = ["Spores need water to grow [CIT]. Here we ask how spores split.",
              "The coat’s “seam” – the ﬁrst split – opens in 5 min."]
ITEM_IDS = ["title_form", "abstract_moves", "intro_roles", "gap_sentence", "here_we", "results_headings",
            "results_openings", "storyline", "excitement", "strongest_claim", "limitations", "discussion_moves",
            "explanations", "figure_reference", "signature_phrases", "essay_argument"]


def item(item_id):
    return next(i for i in CHECKLIST["items"] if i["id"] == item_id)


class ChecklistTests(unittest.TestCase):
    def setUp(self):
        self.paper = make_paper_file("W1", "ada", PARAGRAPHS)
        self.extraction = make_extraction(self.paper, CHECKLIST)

    def test_the_shipped_checklist(self):
        self.assertEqual(CHECKLIST["version"], 1)
        self.assertEqual([i["id"] for i in CHECKLIST["items"]], ITEM_IDS)

    def test_a_valid_extraction_passes(self):
        self.assertEqual(lc.validate_extraction(self.extraction, CHECKLIST, "senior"), [])

    def test_a_missing_item_fails(self):
        del self.extraction["answers"]["here_we"]
        self.assertIn("here_we: missing", lc.validate_extraction(self.extraction, CHECKLIST, "senior"))

    def test_a_value_outside_the_list_fails(self):
        self.extraction["answers"]["title_form"]["value"] = "slogan"
        errors = lc.validate_extraction(self.extraction, CHECKLIST, "senior")
        self.assertTrue(any(e.startswith("title_form.value") for e in errors))

    def test_the_essay_item_follows_the_group(self):
        errors = lc.validate_extraction(self.extraction, CHECKLIST, "essay")
        self.assertTrue(any(e.startswith("essay_argument") for e in errors))
        essay = make_extraction(self.paper, CHECKLIST, group="essay")
        self.assertEqual(lc.validate_extraction(essay, CHECKLIST, "essay"), [])
        self.assertTrue(lc.validate_extraction(essay, CHECKLIST, "senior"))

    def test_unknown_and_missing_fields_fail(self):
        self.extraction["answers"]["limitations"]["tone"] = "calm"
        del self.extraction["answers"]["limitations"]["quotes"]
        errors = lc.validate_extraction(self.extraction, CHECKLIST, "senior")
        self.assertTrue(any("unknown fields" in e for e in errors))
        self.assertTrue(any("missing fields" in e for e in errors))

    def test_an_excitement_entry_needs_a_quote(self):
        del self.extraction["answers"]["excitement"]["value"][0]["quote"]
        errors = lc.validate_extraction(self.extraction, CHECKLIST, "senior")
        self.assertTrue(any(e.startswith("excitement.value") for e in errors))

    def test_missing_top_keys_fail(self):
        del self.extraction["paper_sha256"]
        self.assertEqual(lc.validate_extraction(self.extraction, CHECKLIST, "senior"), ["missing keys: paper_sha256"])

    def test_iter_quotes_walks_quote_quotes_and_objects(self):
        rows = list(lc.iter_quotes(self.extraction, CHECKLIST))
        self.assertEqual(len(rows), 9)
        self.assertIn(("excitement", "value", "Spores need water to grow [CIT]."), rows)
        self.assertFalse(any(r[0] == "essay_argument" for r in rows))


class AgreementTests(unittest.TestCase):
    def test_enum(self):
        spec = {"type": "enum", "values": ["a", "b"]}
        self.assertEqual(lc.field_agreement(spec, "a", "a"), 1.0)
        self.assertEqual(lc.field_agreement(spec, "a", "b"), 0.0)

    def test_enum_list_uses_edit_distance(self):
        spec = {"type": "enum_list", "values": ["a", "b", "c"]}
        self.assertAlmostEqual(lc.field_agreement(spec, ["a", "b", "c"], ["a", "c"]), 2.0 / 3)
        self.assertEqual(lc.field_agreement(spec, [], []), 1.0)

    def test_objects_use_overlap_of_closed_keys(self):
        spec = item("excitement")["fields"]["value"]
        a = [{"marker": "scope claim", "location": "abstract", "quote": "x"},
             {"marker": "evaluative word", "location": "results", "quote": "y"}]
        b = [{"marker": "scope claim", "location": "abstract", "quote": "other words"}]
        self.assertEqual(lc.field_agreement(spec, a, b), 0.5)

    def test_item_agreement_is_the_mean_of_closed_fields_and_skips_not_applicable(self):
        limitations = item("limitations")
        a = {"placement": "own paragraph", "specificity": "specific", "quotes": []}
        b = {"placement": "own paragraph", "specificity": "generic", "quotes": ["z"]}
        self.assertEqual(lc.item_agreement(limitations, a, b), 0.5)
        self.assertIsNone(lc.item_agreement(item("essay_argument"), lc.NOT_APPLICABLE, lc.NOT_APPLICABLE))
        self.assertNotIn("storyline", [i["id"] for i in lc.closed_items(CHECKLIST)])


class QuoteTests(unittest.TestCase):
    def setUp(self):
        self.paper = make_paper_file("W1", "ada", PARAGRAPHS)
        self.extraction = make_extraction(self.paper, CHECKLIST)

    def set_quote(self, quote):
        self.extraction["answers"]["gap_sentence"]["quote"] = quote
        return lq.check_extraction(self.extraction, self.paper, CHECKLIST)

    def test_an_exact_quote_passes(self):
        check = lq.check_extraction(self.extraction, self.paper, CHECKLIST)
        self.assertEqual((check["checked"], check["failed"], check["fail_rate"]), (9, [], 0.0))

    def test_unicode_variants_match(self):
        self.assertEqual(self.set_quote("The coat's \"seam\" - the first split - opens in 5 min.")["failed"], [])

    def test_a_paraphrase_fails(self):
        check = self.set_quote("Spores require water to grow.")
        self.assertEqual(check["failed"][0]["reason"], "not in the paper")
        self.assertEqual(check["unverified_items"], ["gap_sentence"])
        self.assertEqual(check["fail_rate"], 0.111)

    def test_long_and_empty_quotes_fail(self):
        self.assertEqual(self.set_quote(" ".join(["spores"] * 41))["failed"][0]["reason"], "more than 40 words")
        self.assertEqual(self.set_quote("   ")["failed"][0]["reason"], "empty quote")

    def test_a_quote_across_a_citation_mark_passes(self):
        self.assertEqual(self.set_quote("to grow [CIT]. Here we ask")["failed"], [])


class StatusTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = self.tmp.name
        self.manifest = {"person": "ada", "papers": [
            {"work_id": "W1", "status": "fetched", "group": "senior"},
            {"work_id": "W2", "status": "fetched", "group": "senior"},
            {"work_id": "W3", "status": "chosen", "group": "senior"}]}
        for wid in ("W1", "W2"):
            lp.write_json(lp.paper_path(self.data, "ada", wid), make_paper_file(wid, "ada", PARAGRAPHS))

    def statuses(self, run="main"):
        return {c["work_id"]: c["status"] for c in lq.check_person(self.data, self.manifest, CHECKLIST, run)}

    def write_extraction(self, wid, extraction, run="main"):
        lp.write_json(lp.extraction_path(self.data, "ada", wid, run), extraction)

    def test_ok_missing_and_stale(self):
        paper = lp.read_json(lp.paper_path(self.data, "ada", "W1"))
        self.write_extraction("W1", make_extraction(paper, CHECKLIST))
        self.assertEqual(self.statuses(), {"W1": "ok", "W2": "missing"})
        self.assertTrue(os.path.exists(lp.check_path(self.data, "ada", "W1")))
        changed = make_paper_file("W1", "ada", PARAGRAPHS + ["A new paragraph."])
        lp.write_json(lp.paper_path(self.data, "ada", "W1"), changed)
        self.assertEqual(self.statuses()["W1"], "stale")

    def test_redo_then_extraction_failed(self):
        paper = lp.read_json(lp.paper_path(self.data, "ada", "W1"))
        bad = make_extraction(paper, CHECKLIST)
        bad["answers"]["gap_sentence"]["quote"] = "Spores require water."
        self.write_extraction("W1", bad)
        self.assertEqual(self.statuses()["W1"], "redo")
        bad = copy.deepcopy(bad)
        bad["attempt"] = 2
        self.write_extraction("W1", bad)
        self.assertEqual(self.statuses()["W1"], "extraction_failed")

    def test_a_wrong_work_id_or_run_is_invalid(self):
        paper = lp.read_json(lp.paper_path(self.data, "ada", "W2"))
        self.write_extraction("W1", make_extraction(paper, CHECKLIST))
        self.assertEqual(self.statuses()["W1"], "invalid")
        paper = lp.read_json(lp.paper_path(self.data, "ada", "W1"))
        self.write_extraction("W1", make_extraction(paper, CHECKLIST, run="main"), run="agreement")
        self.assertEqual(self.statuses("agreement"), {"W1": "invalid"})


if __name__ == "__main__":
    unittest.main()
