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


BEN = dict(ADA, id="ben", name="Ben Rowan", orcid="0000-0000-0000-0002", openalex_ids=["A2"])
TEAM = {"id": "ada-ben", "name": "Ada Quill and Ben Rowan (joint papers)", "members": ["ada", "ben"],
        "confirmed_by": "test", "note": "papers that list both"}


class TeamRegistryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "people.json")

    def write(self, people):
        with open(self.path, "w", encoding="utf-8") as handle:
            json.dump({"schema": 1, "people": people}, handle)

    def test_a_team_loads_in_registry_order(self):
        self.write([ADA, BEN, TEAM])
        people = lr.load_registry(self.path)
        self.assertEqual([p["id"] for p in people], ["ada", "ben", "ada-ben"])
        self.assertEqual(people[2]["members"], ["ada", "ben"])

    def test_a_team_may_come_before_its_members(self):
        self.write([TEAM, ADA, BEN])
        self.assertEqual([p["id"] for p in lr.load_registry(self.path)], ["ada-ben", "ada", "ben"])

    def test_a_team_without_a_note_loads(self):
        self.write([ADA, BEN, {k: v for k, v in TEAM.items() if k != "note"}])
        lr.load_registry(self.path)

    def test_is_team(self):
        self.assertTrue(lr.is_team(TEAM))
        self.assertFalse(lr.is_team(ADA))
        self.assertFalse(lr.is_team("ada"))
        self.assertFalse(lr.is_team(None))

    def test_check_entry_accepts_a_team_and_rejects_a_malformed_one(self):
        lr.check_entry(TEAM)
        bad = [
            {k: v for k, v in TEAM.items() if k != "confirmed_by"},
            {k: v for k, v in TEAM.items() if k != "name"},
            dict(TEAM, id="Ada Ben"),
            dict(TEAM, id=7),
            dict(TEAM, members="ada"),
            dict(TEAM, members=["ada"]),
            dict(TEAM, members=[]),
            dict(TEAM, members=["ada", "ada"]),
            dict(TEAM, members=["ada", 2]),
            dict(TEAM, orcid="0000-0000-0000-0003"),
            dict(TEAM, openalex_ids=["A3"]),
        ]
        for entry in bad:
            with self.subTest(entry=entry):
                with self.assertRaises(lr.RegistryError):
                    lr.check_entry(entry)

    def test_check_entry_checks_the_members_against_a_given_registry(self):
        by_id = {p["id"]: p for p in (ADA, BEN, TEAM)}
        lr.check_entry(TEAM, by_id)
        with self.assertRaises(lr.RegistryError):
            lr.check_entry(dict(TEAM, members=["ada", "zed"]), by_id)

    def test_bad_teams_fail_to_load(self):
        nest = {"id": "outer", "name": "Outer", "members": ["ada", "ada-ben"], "confirmed_by": "test"}
        cases = {
            "unknown member": [ADA, BEN, dict(TEAM, members=["ada", "zed"])],
            "repeated member": [ADA, BEN, dict(TEAM, members=["ada", "ben", "ada"])],
            "one member": [ADA, BEN, dict(TEAM, members=["ada"])],
            "member is a team": [ADA, BEN, TEAM, nest],
            "team is its own member": [ADA, BEN, dict(TEAM, members=["ada", "ada-ben"])],
            "repeated id": [ADA, BEN, TEAM, dict(TEAM)],
            "id of a person": [ADA, BEN, dict(TEAM, id="ada")],
        }
        for label, people in cases.items():
            with self.subTest(label):
                self.write(people)
                with self.assertRaises(lr.RegistryError):
                    lr.load_registry(self.path)

    def test_team_members_returns_the_entries_in_member_order(self):
        people = [ADA, BEN, TEAM]
        self.assertEqual([p["id"] for p in lr.team_members(people, dict(TEAM, members=["ben", "ada"]))],
                         ["ben", "ada"])

    def test_the_shipped_registry_holds_the_team_of_shendure_and_trapnell(self):
        people = lr.load_registry()
        team = lr.get_person(people, "shendure-trapnell")
        self.assertTrue(lr.is_team(team))
        self.assertEqual(team["members"], ["shendure", "trapnell"])
        self.assertEqual(people[-1]["id"], "shendure-trapnell")
        self.assertNotIn("orcid", team)
        self.assertNotIn("openalex_ids", team)


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
