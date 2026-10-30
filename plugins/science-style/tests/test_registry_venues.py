"""Tests for lab/lab_registry.py and lab/lab_venues.py. All people in this file are made up."""
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lab"))
sys.path.insert(0, HERE)

import lab_registry as lr  # noqa: E402
import lab_venues as lv  # noqa: E402

ADA = {"id": "ada", "name": "Ada Quill", "orcid": "0000-0000-0000-0001", "openalex_ids": ["A1"],
       "ml_venues": False, "confirmed_by": "test"}


class RegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "people.json")

    def write(self, people):
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump({"schema": 1, "people": people}, handle)

    def test_a_valid_registry_loads_in_order(self):
        ben = dict(ADA, id="ben", orcid="0000-0000-0000-000X", openalex_ids=["A2", "A22"])
        self.write([ADA, ben])
        self.assertEqual([p["id"] for p in lr.load_registry(self.path)], ["ada", "ben"])

    def test_an_empty_registry_loads(self):
        self.write([])
        self.assertEqual(lr.load_registry(self.path), [])

    def test_the_shipped_registry_loads(self):
        lr.load_registry()

    def test_bad_entries_fail(self):
        bad = [
            {k: v for k, v in ADA.items() if k != "orcid"},
            dict(ADA, id="Ada Quill"),
            dict(ADA, orcid="0000-0000-0001"),
            dict(ADA, openalex_ids=[]),
            dict(ADA, openalex_ids=["W1"]),
            dict(ADA, ml_venues="no"),
            dict(ADA, orcid=12345),
            dict(ADA, id=7),
            dict(ADA, openalex_ids="A1"),
            dict(ADA, openalex_ids=[1]),
            dict(ADA, id="ada\n"),
            dict(ADA, orcid="0000-0000-0000-0001\n"),
            dict(ADA, openalex_ids=["A1\n"]),
            dict(ADA, orcid="\u0660\u0661\u0662\u0663-0000-0000-0001"),
        ]
        for entry in bad:
            with self.subTest(entry=entry):
                self.write([entry])
                with self.assertRaises(lr.RegistryError):
                    lr.load_registry(self.path)

    def test_malformed_registry_files_raise_registry_error(self):
        texts = ["{not json", json.dumps([ADA]), '{"people": null}', '{"people": "x"}',
                 '{"people": ["ada"]}']
        for text in texts:
            with self.subTest(text=text):
                with open(self.path, "w", encoding="utf-8") as handle:
                    handle.write(text)
                with self.assertRaises(lr.RegistryError):
                    lr.load_registry(self.path)

    def test_a_missing_registry_file_raises_registry_error(self):
        with self.assertRaises(lr.RegistryError):
            lr.load_registry(os.path.join(self.tmp.name, "absent.json"))

    def test_a_repeated_id_fails(self):
        self.write([ADA, dict(ADA)])
        with self.assertRaises(lr.RegistryError):
            lr.load_registry(self.path)

    def test_get_person(self):
        self.assertEqual(lr.get_person([ADA], "ada")["name"], "Ada Quill")
        with self.assertRaises(lr.RegistryError):
            lr.get_person([ADA], "zed")


class VenueTests(unittest.TestCase):
    def setUp(self):
        self.venues = lv.load_venues()

    def test_the_spec_list_is_in_the_high_tier(self):
        for name in ("Science", "Nature", "Cell", "Cell Systems", "Cell Genomics", "Molecular Cell",
                     "Current Biology", "Science Translational Medicine", "Cell Host & Microbe"):
            self.assertEqual(lv.tier_of(name, self.venues), "high", name)

    def test_the_nature_prefix_and_its_exclusions(self):
        self.assertEqual(lv.tier_of("Nature Genetics", self.venues), "high")
        self.assertEqual(lv.tier_of("Nature Reviews Genetics", self.venues), "high")
        self.assertEqual(lv.tier_of("Nature Communications", self.venues), "other")
        self.assertEqual(lv.tier_of("Nature Precedings", self.venues), "other")
        self.assertEqual(lv.tier_of("Naturwissenschaften", self.venues), "other")

    def test_case_and_spaces_do_not_matter(self):
        self.assertEqual(lv.tier_of("  nature   METHODS ", self.venues), "high")
        self.assertEqual(lv.tier_of("CELL", self.venues), "high")

    def test_other_venues(self):
        for name in ("Cell Reports", "Science Advances", "eLife", "PNAS", "bioRxiv", "", None):
            self.assertEqual(lv.tier_of(name, self.venues), "other", name)

    def test_ml_venues_count_only_for_a_flagged_person(self):
        name = "Advances in Neural Information Processing Systems"
        self.assertEqual(lv.tier_of(name, self.venues), "other")
        self.assertEqual(lv.tier_of(name, self.venues, ml_venues=True), "high")
        self.assertEqual(lv.tier_of("International Conference on Learning Representations", self.venues, True),
                         "high")

    def test_essay_venues(self):
        self.assertTrue(lv.is_essay_venue("Trends in Genetics", self.venues))
        self.assertTrue(lv.is_essay_venue("Nature Reviews. Genetics", self.venues))
        self.assertTrue(lv.is_essay_venue("Annual Review of Biophysics", self.venues))
        self.assertFalse(lv.is_essay_venue("Cell Systems", self.venues))
        self.assertFalse(lv.is_essay_venue(None, self.venues))


if __name__ == "__main__":
    unittest.main()
