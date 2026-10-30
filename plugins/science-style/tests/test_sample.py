"""Tests for lab/lab_sample.py. All papers in this file are made up."""
import copy
import os
import random
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lab"))
sys.path.insert(0, HERE)

import lab_sample as ls  # noqa: E402


def rec(wid, group, tier, year):
    return {"work_id": wid, "doi": "10.0000/" + wid.lower(), "title": "Paper " + wid, "year": year,
            "venue": "Fern Letters", "type": "article", "tier": tier, "group": group, "co_senior": False,
            "pmcid": None, "preprint_doi": None, "arxiv_id": None, "authors": [{"id": "A1"}]}


def pool(group, tier, n, prefix):
    return [rec("{}{:03d}".format(prefix, i), group, tier, 2000 + i) for i in range(n)]


class AllocateTests(unittest.TestCase):
    def test_full_pools_meet_the_targets(self):
        pools = {ls.cell_name(g, t): 10 for g in ls.GROUPS for t in ls.TIERS}
        alloc, shortfall = ls.allocate(pools)
        self.assertEqual(alloc, {"senior/high": 5, "senior/other": 3, "first/high": 3, "first/other": 1,
                                 "essay/high": 2, "essay/other": 1})
        self.assertEqual(shortfall, 0)

    def test_short_high_tiers_move_to_the_other_tier_of_the_group(self):
        pools = {"senior/high": 4, "senior/other": 20, "first/high": 2, "first/other": 9,
                 "essay/high": 1, "essay/other": 3}
        alloc, shortfall = ls.allocate(pools)
        self.assertEqual(alloc, {"senior/high": 4, "senior/other": 4, "first/high": 2, "first/other": 2,
                                 "essay/high": 1, "essay/other": 2})
        self.assertEqual(shortfall, 0)

    def test_an_empty_group_moves_to_the_other_groups_high_tier_first(self):
        pools = {"senior/high": 6, "senior/other": 10, "first/high": 3, "first/other": 1,
                 "essay/high": 0, "essay/other": 0}
        alloc, shortfall = ls.allocate(pools)
        self.assertEqual(alloc, {"senior/high": 6, "senior/other": 5, "first/high": 3, "first/other": 1,
                                 "essay/high": 0, "essay/other": 0})
        self.assertEqual(shortfall, 0)

    def test_a_small_person_records_the_shortfall(self):
        pools = {"senior/high": 2, "senior/other": 3, "first/other": 1, "essay/high": 1}
        alloc, shortfall = ls.allocate(pools)
        self.assertEqual(sum(alloc.values()), 7)
        self.assertEqual(shortfall, 8)


class DrawTests(unittest.TestCase):
    def test_bins_spread_the_draw_across_years(self):
        papers = pool("senior", "high", 20, "W")
        chosen, bins, queue = ls.draw_cell(papers, 4, random.Random("seed"))
        self.assertEqual(len(bins), 4)
        self.assertEqual([len(b) for b in bins], [5, 5, 5, 5])
        for wid, members in zip(chosen, bins):
            self.assertIn(wid, members)
        self.assertEqual(sorted(chosen + queue), sorted(p["work_id"] for p in papers))

    def test_bins_follow_years_not_ids(self):
        papers = [rec("W{:03d}".format(i), "senior", "high", 2020 - i) for i in range(20)]
        year_of = {p["work_id"]: p["year"] for p in papers}
        chosen, bins, queue = ls.draw_cell(papers, 4, random.Random("seed"))
        years = [[year_of[w] for w in b] for b in bins]
        self.assertEqual([len(b) for b in years], [5, 5, 5, 5])
        for earlier, later in zip(years, years[1:]):
            self.assertLessEqual(max(earlier), min(later))

    def test_the_same_seed_gives_the_same_draw(self):
        papers = pool("senior", "high", 40, "W")
        a = ls.draw_cell(papers, 5, ls.cell_rng(7, "ada", "senior", "high"))
        b = ls.draw_cell(list(reversed(papers)), 5, ls.cell_rng(7, "ada", "senior", "high"))
        self.assertEqual(a, b)

    def test_another_seed_gives_another_draw(self):
        papers = pool("senior", "high", 40, "W")
        a = ls.draw_cell(papers, 5, ls.cell_rng(1, "ada", "senior", "high"))[0]
        b = ls.draw_cell(papers, 5, ls.cell_rng(2, "ada", "senior", "high"))[0]
        self.assertNotEqual(a, b)

    def test_a_draw_of_zero(self):
        chosen, bins, queue = ls.draw_cell(pool("first", "other", 3, "F"), 0, random.Random(1))
        self.assertEqual((chosen, bins), ([], []))
        self.assertEqual(len(queue), 3)


class BuildTests(unittest.TestCase):
    def test_a_full_person_gets_fifteen_papers(self):
        papers = (pool("senior", "high", 9, "SH") + pool("senior", "other", 9, "SO") + pool("first", "high", 9, "FH")
                  + pool("first", "other", 9, "FO") + pool("essay", "high", 9, "EH") + pool("essay", "other", 9, "EO"))
        manifest = ls.build_sample("ada", papers, venues_version=1)
        self.assertEqual(manifest["n_papers"], 15)
        self.assertEqual(manifest["seed"], ls.DEFAULT_SEED)
        self.assertEqual(manifest["shortfall"], 0)
        self.assertEqual(sum(1 for p in manifest["papers"] if p["cell"] == "senior/high"), 5)
        paper = manifest["papers"][0]
        self.assertEqual(paper["status"], "chosen")
        self.assertNotIn("authors", paper)
        self.assertEqual(set(paper), set(ls.MANIFEST_FIELDS) | {"cell", "status", "route", "text_version", "source_url"})
        self.assertEqual(manifest["cells"]["essay/other"]["pool"], 9)
        self.assertEqual(manifest["cells"]["essay/other"]["allocated"], 1)
        self.assertEqual(len(manifest["cells"]["essay/other"]["queue"]), 8)

    def test_a_person_with_no_essays(self):
        papers = pool("senior", "high", 4, "SH") + pool("senior", "other", 2, "SO") + pool("first", "high", 1, "FH")
        manifest = ls.build_sample("ben", papers)
        self.assertEqual(manifest["n_papers"], 7)
        self.assertEqual(manifest["shortfall"], 8)
        self.assertEqual(manifest["cells"]["essay/high"]["pool"], 0)


class ReplaceTests(unittest.TestCase):
    def setUp(self):
        self.lookup = {r["work_id"]: r for r in pool("senior", "high", 6, "W")}
        ids = sorted(self.lookup)
        self.manifest = {
            "person": "ada",
            "papers": [ls.manifest_paper(self.lookup[ids[0]], "senior/high"),
                       ls.manifest_paper(self.lookup[ids[3]], "senior/high")],
            "cells": {"senior/high": {"bins": [ids[0:3], ids[3:6]],
                                      "queue": [ids[4], ids[2], ids[5], ids[1]]}},
            "replacements": [], "n_papers": 2}
        self.ids = ids

    def test_replacements_come_from_the_bin_then_the_queue_then_none(self):
        i = self.ids
        self.assertEqual(ls.replace(self.manifest, i[0], "no text", self.lookup), i[2])
        self.assertEqual(ls.replace(self.manifest, i[2], "no text", self.lookup), i[1])
        self.assertEqual(ls.replace(self.manifest, i[1], "no text", self.lookup), i[4])
        self.assertEqual(ls.replace(self.manifest, i[3], "no text", self.lookup), i[5])
        self.assertIsNone(ls.replace(self.manifest, i[4], "no text", self.lookup))
        self.assertEqual(self.manifest["n_papers"], 1)
        self.assertEqual(len(self.manifest["replacements"]), 5)
        self.assertEqual(self.manifest["replacements"][-1], {"replaced": i[4], "reason": "no text", "replacement": None})
        statuses = {p["work_id"]: p["status"] for p in self.manifest["papers"]}
        self.assertEqual(statuses[i[5]], "chosen")
        self.assertEqual(statuses[i[0]], "replaced")

    def test_replace_refuses_unknown_and_already_replaced_ids(self):
        i = self.ids
        with self.assertRaisesRegex(ValueError, "unknown work id: W999"):
            ls.replace(self.manifest, "W999", "no text", self.lookup)
        self.assertEqual(ls.replace(self.manifest, i[0], "no text", self.lookup), i[2])
        after_first = copy.deepcopy(self.manifest)
        with self.assertRaisesRegex(ValueError, "already replaced: " + i[0]):
            ls.replace(self.manifest, i[0], "no text", self.lookup)
        self.assertEqual(self.manifest, after_first)
        self.assertEqual(len(self.manifest["replacements"]), 1)
        self.assertEqual(self.manifest["n_papers"], 2)

    def test_replace_leaves_the_manifest_unchanged_when_the_lookup_lacks_the_replacement(self):
        i = self.ids
        lookup = {wid: record for wid, record in self.lookup.items() if wid != i[2]}
        before = copy.deepcopy(self.manifest)
        with self.assertRaises(KeyError):
            ls.replace(self.manifest, i[0], "no text", lookup)
        self.assertEqual(self.manifest, before)


class SubsetTests(unittest.TestCase):
    def test_a_seeded_subset_is_stable_and_sorted(self):
        ids = ["W{}".format(n) for n in range(20)]
        a = ls.seeded_subset(ids, 4, "20261029:agreement:ada")
        self.assertEqual(a, ls.seeded_subset(list(reversed(ids)), 4, "20261029:agreement:ada"))
        self.assertEqual(a, sorted(a))
        self.assertEqual(len(a), 4)
        self.assertEqual(len(ls.seeded_subset(ids[:2], 4, "x")), 2)

    def test_agreement_count_is_a_fifth_and_at_least_three(self):
        self.assertEqual(ls.agreement_count(15), 3)
        self.assertEqual(ls.agreement_count(20), 4)
        self.assertEqual(ls.agreement_count(21), 5)
        self.assertEqual(ls.agreement_count(2), 2)


if __name__ == "__main__":
    unittest.main()
