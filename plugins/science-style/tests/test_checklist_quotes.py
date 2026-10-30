"""Tests for lab/lab_checklist.py and lab/lab_quotes.py. All text in this file is made up."""
import copy
import json
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


def without_quotes(extraction):
    """Edit a valid extraction so that it holds no quote and still follows every evidence rule."""
    answers = extraction["answers"]
    answers["gap_sentence"].update(value="none", paragraph=None, quote=None)
    answers["here_we"].update(value="none", paragraph=None, quote=None)
    answers["strongest_claim"].update(value="none", quote=None, hedge_quote=None)
    answers["limitations"].update(placement="none", specificity="none", quotes=[])
    answers["excitement"]["value"] = []
    for item_id in ("storyline", "explanations", "signature_phrases"):
        answers[item_id]["quotes"] = []
    return extraction


class TopKeyTypeTests(unittest.TestCase):
    def setUp(self):
        self.paper = make_paper_file("W1", "ada", PARAGRAPHS)

    def errors(self, **changes):
        extraction = make_extraction(self.paper, CHECKLIST)
        extraction.update(changes)
        return lc.validate_extraction(extraction, CHECKLIST, "senior")

    def test_each_top_key_needs_its_type(self):
        bad = {"schema": "1", "checklist_version": 1.5, "prompt_version": None, "attempt": "2",
               "paper_sha256": 5, "work_id": None, "person": ["ada"], "run": 3}
        for key, value in sorted(bad.items()):
            errors = self.errors(**{key: value})
            self.assertTrue(any(e.startswith(key) for e in errors), (key, errors))

    def test_attempt_is_an_integer_of_one_or_more(self):
        for value in (0, -1, True, 1.0):
            self.assertTrue(any(e.startswith("attempt") for e in self.errors(attempt=value)), value)
        self.assertEqual(self.errors(attempt=2), [])

    def test_answers_must_be_an_object(self):
        self.assertIn("answers must be an object", self.errors(answers=[]))

    def test_an_extraction_that_is_not_an_object_fails(self):
        self.assertEqual(lc.validate_extraction([], CHECKLIST, "senior"), ["extraction is not an object"])


class EvidenceTests(unittest.TestCase):
    def setUp(self):
        self.paper = make_paper_file("W1", "ada", PARAGRAPHS)
        self.extraction = make_extraction(self.paper, CHECKLIST)

    def errors(self, item_id, group="senior", **fields):
        self.extraction["answers"][item_id].update(fields)
        return lc.validate_extraction(self.extraction, CHECKLIST, group)

    def assert_rejects(self, item_id, field, group="senior", **fields):
        errors = self.errors(item_id, group, **fields)
        self.assertTrue(any(e.startswith("{}.{}".format(item_id, field)) for e in errors), errors)

    def test_the_shipped_checklist_has_five_evidence_rules(self):
        self.assertEqual([i["id"] for i in CHECKLIST["items"] if "evidence" in i],
                         ["gap_sentence", "here_we", "strongest_claim", "limitations", "essay_argument"])

    def test_a_present_sentence_needs_a_quote_and_a_paragraph(self):
        for item_id in ("gap_sentence", "here_we"):
            self.extraction = make_extraction(self.paper, CHECKLIST)
            self.assertEqual(self.errors(item_id, value="present", quote="Here we ask.", paragraph=2), [])
            self.assert_rejects(item_id, "quote", value="present", quote=None, paragraph=1)
            self.assert_rejects(item_id, "quote", value="present", quote="  ", paragraph=1)
            self.assert_rejects(item_id, "paragraph", value="present", quote="Here we ask.", paragraph=None)
            self.assert_rejects(item_id, "paragraph", value="present", quote="Here we ask.", paragraph=0)

    def test_an_absent_sentence_needs_a_null_quote_and_a_null_paragraph(self):
        for item_id in ("gap_sentence", "here_we"):
            self.extraction = make_extraction(self.paper, CHECKLIST)
            self.assertEqual(self.errors(item_id, value="none", quote=None, paragraph=None), [])
            self.assert_rejects(item_id, "quote", value="none", quote="Here we ask.", paragraph=None)
            self.assert_rejects(item_id, "quote", value="none", quote="", paragraph=None)
            self.assert_rejects(item_id, "paragraph", value="none", quote=None, paragraph=1)

    def test_a_hedged_claim_needs_a_quote_and_a_hedge_quote(self):
        self.assertEqual(self.errors("strongest_claim", value="hedged", quote="It may split.",
                                     hedge_quote="may"), [])
        self.assert_rejects("strongest_claim", "quote", value="hedged", quote=None, hedge_quote="may")
        self.assert_rejects("strongest_claim", "hedge_quote", value="hedged", quote="It may split.",
                            hedge_quote=None)

    def test_an_unhedged_claim_needs_a_quote_and_no_hedge_quote(self):
        self.assertEqual(self.errors("strongest_claim", value="unhedged", quote="It splits.",
                                     hedge_quote=None), [])
        self.assert_rejects("strongest_claim", "quote", value="unhedged", quote=None, hedge_quote=None)
        self.assert_rejects("strongest_claim", "hedge_quote", value="unhedged", quote="It splits.",
                            hedge_quote="may")

    def test_no_claim_needs_two_null_quotes(self):
        self.assertEqual(self.errors("strongest_claim", value="none", quote=None, hedge_quote=None), [])
        self.assert_rejects("strongest_claim", "quote", value="none", quote="It splits.", hedge_quote=None)
        self.assert_rejects("strongest_claim", "hedge_quote", value="none", quote=None, hedge_quote="may")

    def test_no_limits_need_no_specificity_and_no_quotes(self):
        self.assertEqual(self.errors("limitations", placement="none", specificity="none", quotes=[]), [])
        self.assert_rejects("limitations", "specificity", placement="none", specificity="generic", quotes=[])
        self.assert_rejects("limitations", "quotes", placement="none", specificity="none", quotes=["It fails."])

    def test_stated_limits_need_quotes_and_a_specificity(self):
        for placement in ("own paragraph", "own section", "inline in results", "inline in discussion"):
            self.assertEqual(self.errors("limitations", placement=placement, specificity="specific",
                                         quotes=["It fails."]), [])
        self.assert_rejects("limitations", "quotes", placement="own section", specificity="specific", quotes=[])
        self.assert_rejects("limitations", "specificity", placement="own section", specificity="none",
                            quotes=["It fails."])

    def test_a_call_to_action_needs_a_quote(self):
        self.extraction = make_extraction(self.paper, CHECKLIST, group="essay")
        self.assertEqual(self.errors("essay_argument", "essay", call_to_action="yes", quote="Act now."), [])
        self.assert_rejects("essay_argument", "quote", "essay", call_to_action="yes", quote=None)
        self.assertEqual(self.errors("essay_argument", "essay", call_to_action="no", quote=None), [])
        self.assert_rejects("essay_argument", "quote", "essay", call_to_action="no", quote="Act now.")

    def test_a_not_applicable_answer_skips_the_rules(self):
        self.assertEqual(lc.validate_extraction(self.extraction, CHECKLIST, "senior"), [])
        self.assertEqual(self.extraction["answers"]["essay_argument"], lc.NOT_APPLICABLE)

    def test_a_field_error_does_not_run_the_rules(self):
        errors = self.errors("gap_sentence", value="maybe", quote=None, paragraph=None)
        self.assertEqual([e for e in errors if not e.startswith("gap_sentence.value")], [])


class LoadChecklistTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def load_with(self, evidence):
        checklist = copy.deepcopy(CHECKLIST)
        next(i for i in checklist["items"] if i["id"] == "gap_sentence")["evidence"] = evidence
        path = os.path.join(self.tmp.name, "checklist.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(checklist, handle)
        return lc.load_checklist(path)

    def test_a_rule_that_names_a_known_field_and_value_loads(self):
        self.load_with({"value": {"present": {"filled": ["quote"]}, "*": {"empty": ["quote"]}}})

    def test_a_rule_with_an_unknown_name_is_rejected(self):
        bad = {"controlling field": {"nope": {"present": {"filled": ["quote"]}}},
               "controlling field of the wrong type": {"paragraph": {"present": {"filled": ["quote"]}}},
               "value": {"value": {"maybe": {"filled": ["quote"]}}},
               "filled field": {"value": {"present": {"filled": ["nope"]}}},
               "empty field": {"value": {"none": {"empty": ["nope"]}}},
               "is field": {"value": {"present": {"is": {"nope": "x"}}}},
               "is value": {"value": {"present": {"is": {"value": "maybe"}}}},
               "is_not value": {"value": {"present": {"is_not": {"value": "maybe"}}}},
               "rule": {"value": {"present": {"required": ["quote"]}}},
               "rule list": {"value": {"present": {"filled": "quote"}}},
               "evidence that is not an object": ["quote"]}
        for name, evidence in sorted(bad.items()):
            with self.subTest(name):
                with self.assertRaises(lc.ChecklistError):
                    self.load_with(evidence)


class PerPaperCheckTests(unittest.TestCase):
    """One bad paper gives its own check and never stops the checks of the papers after it."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = self.tmp.name
        self.manifest = {"person": "ada", "papers": [
            {"work_id": "W1", "status": "fetched", "group": "senior"},
            {"work_id": "W2", "status": "fetched", "group": "senior"}]}
        self.papers = {}
        for wid in ("W1", "W2"):
            self.papers[wid] = make_paper_file(wid, "ada", PARAGRAPHS)
            lp.write_json(lp.paper_path(self.data, "ada", wid), self.papers[wid])
        self.write_extraction("W2", make_extraction(self.papers["W2"], CHECKLIST))

    def write_extraction(self, wid, extraction, run="main"):
        lp.write_json(lp.extraction_path(self.data, "ada", wid, run), extraction)

    def checks(self, run="main"):
        return {c["work_id"]: c for c in lq.check_person(self.data, self.manifest, CHECKLIST, run)}

    def check_file(self, wid, run="main"):
        return lp.read_json(lp.check_path(self.data, "ada", wid, run))

    def assert_second_paper_is_ok(self, checks):
        self.assertEqual(checks["W2"]["status"], "ok")
        self.assertEqual(self.check_file("W2")["status"], "ok")

    def test_unreadable_json(self):
        path = lp.extraction_path(self.data, "ada", "W1")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write('{"schema": 1, "answers": {')
        checks = self.checks()
        self.assertEqual(checks["W1"]["status"], "invalid")
        self.assertTrue(checks["W1"]["errors"][0].startswith("unreadable JSON: "))
        self.assertEqual(self.check_file("W1")["status"], "invalid")
        self.assert_second_paper_is_ok(checks)

    def test_an_extraction_that_is_a_list(self):
        self.write_extraction("W1", [])
        checks = self.checks()
        self.assertEqual((checks["W1"]["status"], checks["W1"]["errors"]),
                         ("invalid", ["extraction is not an object"]))
        self.assert_second_paper_is_ok(checks)

    def test_an_attempt_that_is_a_string(self):
        self.write_extraction("W1", make_extraction(self.papers["W1"], CHECKLIST, attempt="2"))
        checks = self.checks()
        self.assertEqual(checks["W1"]["status"], "invalid")
        self.assertTrue(any(e.startswith("attempt") for e in checks["W1"]["errors"]))
        self.assert_second_paper_is_ok(checks)

    def test_a_manifest_entry_without_a_group(self):
        del self.manifest["papers"][0]["group"]
        self.write_extraction("W1", make_extraction(self.papers["W1"], CHECKLIST))
        checks = self.checks()
        self.assertEqual((checks["W1"]["status"], checks["W1"]["errors"]), ("ok", []))
        self.assert_second_paper_is_ok(checks)
        self.write_extraction("W1", make_extraction(self.papers["W1"], CHECKLIST, group="essay"))
        self.assertEqual(self.checks()["W1"]["status"], "invalid")

    def test_a_missing_paper_file(self):
        self.write_extraction("W1", make_extraction(self.papers["W1"], CHECKLIST))
        os.remove(lp.paper_path(self.data, "ada", "W1"))
        checks = self.checks()
        self.assertEqual((checks["W1"]["status"], checks["W1"]["errors"]), ("missing", ["no paper file"]))
        self.assertEqual(self.check_file("W1")["status"], "missing")
        self.assert_second_paper_is_ok(checks)

    def test_an_unreadable_paper_file(self):
        self.write_extraction("W1", make_extraction(self.papers["W1"], CHECKLIST))
        with open(lp.paper_path(self.data, "ada", "W1"), "w", encoding="utf-8") as handle:
            handle.write("[1, 2")
        checks = self.checks()
        self.assertEqual(checks["W1"]["status"], "invalid")
        self.assertTrue(checks["W1"]["errors"][0].startswith("unreadable paper file: "))
        self.assert_second_paper_is_ok(checks)

    def test_every_check_has_the_same_keys(self):
        self.write_extraction("W1", [])
        os.remove(lp.extraction_path(self.data, "ada", "W2"))
        keys = set()
        for check in self.checks().values():
            keys.add(tuple(sorted(check)))
        self.assertEqual(keys, {("checked", "errors", "fail_rate", "failed", "status", "unverified_items",
                                 "work_id")})

    def test_a_deleted_extraction_replaces_its_old_check_file(self):
        self.assertEqual(self.checks()["W2"]["status"], "ok")
        os.remove(lp.extraction_path(self.data, "ada", "W2"))
        self.assertEqual(self.checks()["W2"]["status"], "missing")
        self.assertEqual(self.check_file("W2")["status"], "missing")

    def test_a_deleted_agreement_extraction_removes_its_old_check_file(self):
        self.write_extraction("W1", make_extraction(self.papers["W1"], CHECKLIST, run="agreement"), "agreement")
        self.assertEqual(self.checks("agreement")["W1"]["status"], "ok")
        self.assertTrue(os.path.exists(lp.check_path(self.data, "ada", "W1", "agreement")))
        os.remove(lp.extraction_path(self.data, "ada", "W1", "agreement"))
        self.assertEqual(self.checks("agreement"), {})
        self.assertFalse(os.path.exists(lp.check_path(self.data, "ada", "W1", "agreement")))

    def test_an_extraction_with_no_quote_needs_a_redo(self):
        extraction = without_quotes(make_extraction(self.papers["W1"], CHECKLIST))
        self.assertEqual(lc.validate_extraction(extraction, CHECKLIST, "senior"), [])
        self.assertEqual(lq.check_extraction(extraction, self.papers["W1"], CHECKLIST)["checked"], 0)
        self.write_extraction("W1", extraction)
        self.assertEqual(self.checks()["W1"]["status"], "redo")
        extraction["attempt"] = 2
        self.write_extraction("W1", extraction)
        self.assertEqual(self.checks()["W1"]["status"], "extraction_failed")

    def test_an_old_prompt_version_is_stale(self):
        extraction = make_extraction(self.papers["W1"], CHECKLIST)
        self.write_extraction("W1", extraction)
        self.assertEqual(self.checks()["W1"]["status"], "ok")
        extraction["prompt_version"] = 0
        self.write_extraction("W1", extraction)
        self.assertEqual(self.checks()["W1"]["status"], "stale")


if __name__ == "__main__":
    unittest.main()
