"""Tests for lab/style_lab.py: the whole pipeline offline, and the exit codes. All data is made up."""
import contextlib
import io
import json
import os
import sys
import tempfile
import unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lab"))
sys.path.insert(0, HERE)

import lab_card_check  # noqa: E402
import lab_checklist  # noqa: E402
import lab_http  # noqa: E402
import lab_paths as lp  # noqa: E402
import lab_surface  # noqa: E402
import style_lab  # noqa: E402
from fakes import ADA, BEN, FakeHttp, arxiv_body, author, jats_body, make_extraction, make_work  # noqa: E402


def page(results):
    return {"meta": {"count": len(results)}, "results": results}


def world():
    ada_last = author("A1", ADA["orcid"])
    ada_first = author("A1", ADA["orcid"])
    w1 = make_work("W1", [author("A90"), ada_last], title="Spores swell in water", venue="Cell", doi="10.0000/w1",
                   pmcid="PMC5000001", year=2012)
    w2 = make_work("W2", [ada_first, author("A91")], title="Moss dries on rocks", venue="Nature Genetics",
                   doi="10.0000/w2", pmcid="PMC5000002", year=2008)
    w3 = make_work("W3", [author("A92"), ada_last], title="Coats split along a seam", wtype="preprint",
                   venue="bioRxiv", doi="10.1101/500003", year=2020)
    w4 = make_work("W4", [author("A93"), author("A1", ADA["orcid"], True), author("A2", BEN["orcid"], True)],
                   title="A shared atlas of ferns", venue="Cell Systems", doi="10.0000/w4", pmcid="PMC5000004",
                   year=2018)
    w5 = make_work("W5", [author("A94"), author("A2", BEN["orcid"])], title="Nets sort spores",
                   venue="Advances in Neural Information Processing Systems", year=2021,
                   locations=[{"landing_page_url": "https://arxiv.org/abs/2101.00005"}])
    jats_url = "https://www.biorxiv.org/content/early/2020/01/01/500003.source.xml"
    return FakeHttp([
        (("author.orcid:" + ADA["orcid"],), page([w1, w2, w3, w4])),
        (("author.orcid:" + BEN["orcid"],), page([w4, w5])),
        (("author.id:",), page([])),
        ("efetch.fcgi?db=pmc&id=500000", jats_body(700)),
        ("details/biorxiv/10.1101/500003", {"collection": [{"jatsxml": jats_url}]}),
        ("500003.source.xml", jats_body(700)),
        ("arxiv.org/html/2101.00005", arxiv_body(700)),
    ])


def card_for(profile, papers_line=None):
    quote = profile["quotes"][0]
    body = {"Sample": papers_line or "The card uses {} papers.".format(profile["n_papers"]),
            "Excitement": '"{}" (doi:{})'.format(quote["text"], quote["doi"])}
    lines = ["# " + profile["name"], ""]
    for heading in lab_card_check.CARD_HEADINGS:
        lines += ["## " + heading, body.get(heading, "Plain text."), ""]
    return "\n".join(lines)


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = os.path.join(self.tmp.name, "data")
        os.makedirs(self.data)
        self.registry = os.path.join(self.tmp.name, "people.json")
        with open(self.registry, "w", encoding="utf-8") as handle:
            json.dump({"schema": 1, "people": [ADA, BEN]}, handle)
        self.http = world()
        self.out = io.StringIO()
        self.err = io.StringIO()

    def run_lab(self, *argv):
        return style_lab.main(["--registry", self.registry] + list(argv), http_factory=lambda cache, **kw: self.http,
                              environ={"STYLE_LAB_DATA": self.data}, out=self.out, err=self.err)

    def test_the_whole_pipeline_offline(self):
        self.assertEqual(self.run_lab("discover", "--all"), 0)
        self.assertTrue(os.path.exists(lp.works_path(self.data, "ada")))
        self.assertEqual(self.run_lab("sample", "--all", "--pilot"), 0)
        ada = lp.read_json(os.path.join(self.data, "pilot", "manifests", "ada.json"))
        self.assertEqual(sorted(p["work_id"] for p in ada["papers"]), ["W1", "W2", "W3"])
        ben = lp.read_json(os.path.join(self.data, "pilot", "manifests", "ben.json"))
        self.assertEqual(sorted(p["work_id"] for p in ben["papers"]), ["W4", "W5"])
        self.assertFalse(os.path.exists(os.path.join(lp.PLUGIN_ROOT, "manifests", "ada.json")))
        self.assertEqual(self.run_lab("sample", "--all", "--pilot"), 2)
        self.assertIn("--force", self.err.getvalue())

        self.assertEqual(self.run_lab("fetch", "--all", "--pilot"), 0)
        ada = lp.read_json(os.path.join(self.data, "pilot", "manifests", "ada.json"))
        self.assertEqual({p["work_id"]: p["route"] for p in ada["papers"]},
                         {"W1": "ncbi-pmc", "W2": "ncbi-pmc", "W3": "biorxiv"})
        self.assertEqual(self.run_lab("normalize", "--all", "--pilot"), 0)
        self.assertEqual(self.run_lab("surface", "--all", "--pilot"), 0)
        self.assertTrue(os.path.exists(os.path.join(self.data, "pilot", "surface", "ben.json")))
        self.assertEqual(self.run_lab("select", "agreement", "ada", "--pilot"), 0)
        self.assertIn("ada: W1 W2 W3", self.out.getvalue())

        self.assertEqual(self.run_lab("check-quotes", "--all", "--pilot"), 1)
        checklist = lab_checklist.load_checklist()
        for person, ids in (("ada", ["W1", "W2", "W3"]), ("ben", ["W4", "W5"])):
            for wid in ids:
                paper = lp.read_json(lp.paper_path(self.data, person, wid))
                lp.write_json(lp.extraction_path(self.data, person, wid),
                              make_extraction(paper, checklist, group=paper["group"]))
        self.assertEqual(self.run_lab("check-quotes", "--all", "--pilot"), 0)
        self.assertEqual(self.run_lab("aggregate", "--all", "--pilot"), 0)
        profile = lp.read_json(os.path.join(self.data, "pilot", "profiles", "ada.json"))
        self.assertEqual(profile["n_papers"], 3)
        self.assertTrue(os.path.exists(os.path.join(self.data, "pilot", "digest", "ada.json")))

        card = os.path.join(self.data, "pilot", "profiles", "ada.md")
        with open(card, "w", encoding="utf-8") as handle:
            handle.write(card_for(profile))
        self.assertEqual(self.run_lab("check-card", "ada", "--pilot"), 0)
        with open(card, "w", encoding="utf-8") as handle:
            handle.write(card_for(profile, "The card uses 777 papers."))
        self.assertEqual(self.run_lab("check-card", "ada", "--pilot"), 1)
        self.assertIn("number not in the profile data: 777", self.out.getvalue())

        self.assertEqual(self.run_lab("quality", "--pilot"), 0)
        self.assertTrue(os.path.exists(os.path.join(self.data, "pilot", "profiles", "quality.md")))
        self.assertEqual(self.run_lab("status", "--pilot"), 0)
        self.assertIn("ada: works 4, sample 3, fetched 3", self.out.getvalue())

    def test_sample_needs_the_works_file_of_every_person(self):
        self.assertEqual(self.run_lab("discover", "ada"), 0)
        self.assertEqual(self.run_lab("sample", "ada", "--pilot"), 2)
        self.assertIn("run discover first for: ben", self.err.getvalue())

    def test_a_network_failure_is_exit_code_1(self):
        self.http = FakeHttp([("api.openalex.org", lab_http.FetchError("u", 503, "down"))])
        self.assertEqual(self.run_lab("discover", "ada"), 1)
        self.assertIn("network error", self.err.getvalue())

    def fetch_everyone(self):
        self.assertEqual(self.run_lab("discover", "--all"), 0)
        self.assertEqual(self.run_lab("sample", "--all", "--pilot"), 0)
        self.assertEqual(self.run_lab("fetch", "--all", "--pilot"), 0)

    def test_surface_of_one_person_uses_every_person_with_a_manifest(self):
        self.fetch_everyone()
        self.assertEqual(self.run_lab("surface", "--all", "--pilot"), 0)
        folder = os.path.join(self.data, "pilot", "surface")
        ada_path, ben_path = os.path.join(folder, "ada.json"), os.path.join(folder, "ben.json")
        ada_all = lp.read_json(ada_path)
        lp.write_json(ben_path, {"sentinel": True})
        seen = []

        def spy(papers_by_person, wordlists):
            seen.append(sorted(papers_by_person))
            return real(papers_by_person, wordlists)

        real = lab_surface.run_surface
        with mock.patch.object(lab_surface, "run_surface", spy):
            self.assertEqual(self.run_lab("surface", "ada", "--pilot"), 0)
        self.assertEqual(seen, [["ada", "ben"]])
        self.assertEqual(lp.read_json(ada_path), ada_all)
        self.assertEqual(lp.read_json(ben_path), {"sentinel": True})

    def test_a_failed_lookup_stops_the_fetch_and_keeps_the_manifest(self):
        self.assertEqual(self.run_lab("discover", "ada"), 0)
        self.assertEqual(self.run_lab("discover", "ben"), 0)
        self.assertEqual(self.run_lab("sample", "--all", "--pilot"), 0)
        self.http = FakeHttp([])
        self.assertEqual(self.run_lab("fetch", "ada", "--pilot"), 1)
        self.assertIn("network error: ada: ", self.err.getvalue())
        self.assertIn("deferred", self.err.getvalue())
        self.assertIn("run fetch again", self.err.getvalue())
        ada = lp.read_json(os.path.join(self.data, "pilot", "manifests", "ada.json"))
        self.assertEqual([p["status"] for p in ada["papers"]], ["chosen"] * 3)
        self.assertEqual(ada["replacements"], [])

    def test_check_quotes_reports_the_number_of_papers_checked(self):
        self.assertEqual(self.run_lab("discover", "--all"), 0)
        self.assertEqual(self.run_lab("sample", "--all", "--pilot"), 0)
        self.assertEqual(self.run_lab("check-quotes", "ada", "--pilot"), 0)
        self.assertIn("ada: 0 papers checked", self.out.getvalue())
        self.assertEqual(self.run_lab("fetch", "--all", "--pilot"), 0)
        self.assertEqual(self.run_lab("check-quotes", "ada", "--pilot"), 1)
        self.assertIn("ada: 3 papers checked", self.out.getvalue())

    def build_profiles(self):
        self.fetch_everyone()
        checklist = lab_checklist.load_checklist()
        for person, ids in (("ada", ["W1", "W2", "W3"]), ("ben", ["W4", "W5"])):
            for wid in ids:
                paper = lp.read_json(lp.paper_path(self.data, person, wid))
                lp.write_json(lp.extraction_path(self.data, person, wid),
                              make_extraction(paper, checklist, group=paper["group"]))
        self.assertEqual(self.run_lab("aggregate", "--all", "--pilot"), 0)

    def write_card(self, person):
        profile = lp.read_json(os.path.join(self.data, "pilot", "profiles", person + ".json"))
        path = os.path.join(self.data, "pilot", "profiles", person + ".md")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(card_for(profile))
        return path

    def read(self, path):
        with open(path, encoding="utf-8") as handle:
            return handle.read()

    def test_references_adds_the_paper_list_after_the_card_check(self):
        self.build_profiles()
        path = self.write_card("ada")
        card = self.read(path)
        self.assertEqual(self.run_lab("check-card", "ada", "--pilot"), 0)
        self.assertEqual(self.run_lab("references", "ada", "--pilot"), 0)
        self.assertIn("ada: 3 papers listed", self.out.getvalue())
        text = self.read(path)
        self.assertTrue(text.startswith(card))
        self.assertEqual(text.count("## Papers"), 1)
        self.assertTrue(text[len(card):].lstrip("\n").startswith("## Papers\n\nThe card rests on these 3 papers.\n"))
        lines = [line for line in text.splitlines() if line.startswith("- ")]
        self.assertEqual([line.split(".")[0] for line in lines],
                         ["- Moss dries on rocks", "- Spores swell in water", "- Coats split along a seam"])
        self.assertTrue(all(line.endswith(" text)") and " doi:" in line for line in lines))
        self.assertEqual(self.run_lab("check-card", "ada", "--pilot"), 0)
        self.assertEqual(self.run_lab("references", "ada", "--pilot"), 0)
        self.assertEqual(self.read(path), text)

    def test_references_writes_nothing_outside_the_pilot_folder(self):
        self.build_profiles()
        self.write_card("ada")
        self.assertEqual(self.run_lab("references", "ada", "--pilot"), 0)
        self.assertFalse(os.path.exists(os.path.join(lp.PLUGIN_ROOT, "profiles", "ada.md")))

    def test_references_needs_a_card_a_profile_and_a_known_person(self):
        self.build_profiles()
        self.assertEqual(self.run_lab("references", "ada", "--pilot"), 2)
        self.assertIn("ada.md", self.err.getvalue())
        self.assertEqual(self.run_lab("references", "nobody", "--pilot"), 2)
        self.assertEqual(self.run_lab("references", "--pilot"), 2)
        self.write_card("ada")
        os.remove(os.path.join(self.data, "pilot", "profiles", "ada.json"))
        self.err = io.StringIO()
        self.assertEqual(self.run_lab("references", "ada", "--pilot"), 2)
        self.assertIn("run aggregate first", self.err.getvalue())

    def test_references_changes_no_card_when_one_target_fails(self):
        self.build_profiles()
        path = self.write_card("ada")
        card = self.read(path)
        self.assertEqual(self.run_lab("references", "--all", "--pilot"), 2)
        self.assertEqual(self.read(path), card)

    def test_a_truncated_manifest_is_exit_code_2(self):
        folder = lp.ensure_dir(self.data, "pilot", "manifests")
        with open(os.path.join(folder, "ada.json"), "w", encoding="utf-8") as handle:
            handle.write('{"person": "ada", "papers": [')
        for argv in (("status", "--pilot"), ("select", "agreement", "ada", "--pilot")):
            self.assertEqual(self.run_lab(*argv), 2)
        self.assertIn("error: cannot read or parse a data file", self.err.getvalue())
        self.assertNotIn("Traceback", self.err.getvalue())

    def test_a_spot_file_with_a_bad_mark_or_no_marks_is_exit_code_2(self):
        path = os.path.join(lp.ensure_dir(self.data, "spot"), "ada.json")
        for content, phrase in (({"work_id": "W1", "marks": {"title_form": "correct", "here_we": "right"}}, "here_we: right"),
                                ({"work_id": "W1"}, '"marks"'), ({"work_id": "W1", "marks": ["correct"]}, '"marks"'),
                                (["correct"], '"marks"')):
            lp.write_json(path, content)
            self.err = io.StringIO()
            self.assertEqual(self.run_lab("quality", "--pilot"), 2, content)
            self.assertIn("ada.json", self.err.getvalue())
            self.assertIn(phrase, self.err.getvalue())
        lp.write_json(path, {"work_id": "W1", "marks": {"title_form": "correct", "here_we": "wrong", "storyline": "vague"}})
        self.assertEqual(self.run_lab("quality", "--pilot"), 0)

    def test_a_missing_paper_file_is_exit_code_2(self):
        self.fetch_everyone()
        os.remove(lp.paper_path(self.data, "ada", "W1"))
        self.assertEqual(self.run_lab("surface", "ada", "--pilot"), 2)
        self.assertIn("error: cannot read or parse a data file", self.err.getvalue())


CAL = {"id": "cal", "name": "Cal Moss", "orcid": "0000-0000-0000-0003", "openalex_ids": ["A3"],
       "ml_venues": False, "confirmed_by": "test"}
TEAM = {"id": "ada-ben", "name": "Ada Quill and Ben Rowan (joint papers)", "members": ["ada", "ben"],
        "confirmed_by": "test"}


def team_world():
    """Ada and Ben share W4 (both corresponding, Ben last) and W7 (Ada first, Ben last). Cal has W6."""
    w1 = make_work("W1", [author("A90"), author("A1", ADA["orcid"])], title="Spores swell in water", venue="Cell",
                   doi="10.0000/w1", pmcid="PMC5000001", year=2012)
    w4 = make_work("W4", [author("A93"), author("A1", ADA["orcid"], True), author("A2", BEN["orcid"], True)],
                   title="A shared atlas of ferns", venue="Cell Systems", doi="10.0000/w4", pmcid="PMC5000004",
                   year=2018)
    w7 = make_work("W7", [author("A1", ADA["orcid"]), author("A96"), author("A2", BEN["orcid"])],
                   title="Ferns and mosses compared", venue="Nature Genetics", doi="10.0000/w7", pmcid="PMC5000007",
                   year=2020)
    w6 = make_work("W6", [author("A95"), author("A3", CAL["orcid"])], title="Lichen grows on stone", venue="Cell",
                   doi="10.0000/w6", pmcid="PMC5000006", year=2016)
    return FakeHttp([
        (("author.orcid:" + ADA["orcid"],), page([w1, w4, w7])),
        (("author.orcid:" + BEN["orcid"],), page([w4, w7])),
        (("author.orcid:" + CAL["orcid"],), page([w6])),
        (("author.id:",), page([])),
        ("efetch.fcgi?db=pmc&id=500000", jats_body(700)),
    ])


class TeamPipelineTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = os.path.join(self.tmp.name, "data")
        os.makedirs(self.data)
        self.registry = os.path.join(self.tmp.name, "people.json")
        with open(self.registry, "w", encoding="utf-8") as handle:
            json.dump({"schema": 1, "people": [TEAM, ADA, BEN, CAL]}, handle)
        self.http = team_world()
        self.out = io.StringIO()
        self.err = io.StringIO()

    def run_lab(self, *argv):
        return style_lab.main(["--registry", self.registry] + list(argv), http_factory=lambda cache, **kw: self.http,
                              environ={"STYLE_LAB_DATA": self.data}, out=self.out, err=self.err)

    def pilot_manifest(self, person):
        return lp.read_json(os.path.join(self.data, "pilot", "manifests", person + ".json"))

    def fetch_everyone(self):
        self.assertEqual(self.run_lab("discover", "--all"), 0)
        self.assertEqual(self.run_lab("sample", "--all", "--pilot"), 0)
        self.assertEqual(self.run_lab("fetch", "--all", "--pilot"), 0)

    def test_discover_all_runs_the_individuals_first_and_the_team_makes_no_request(self):
        self.assertEqual(self.run_lab("discover", "--all"), 0)
        for person in ("ada", "ben", "cal", "ada-ben"):
            self.assertTrue(os.path.exists(lp.works_path(self.data, person)), person)
        lines = [line.split(":")[0] for line in self.out.getvalue().splitlines()]
        self.assertEqual(lines, ["ada", "ben", "cal", "ada-ben"])
        team = lp.read_json(lp.works_path(self.data, "ada-ben"))
        self.assertEqual(team["person"], "ada-ben")
        self.assertEqual([p["work_id"] for p in team["papers"]], ["W4", "W7"])
        self.assertEqual([p["group"] for p in team["papers"]], ["senior", "senior"])
        calls = len(self.http.calls)
        self.http = FakeHttp([])
        self.assertEqual(self.run_lab("discover", "ada-ben"), 0)
        self.assertEqual(self.http.calls, [])
        self.assertGreater(calls, 0)
        self.assertIn("ada-ben: 3 works, 2 papers, 1 dropped, 0 merged", self.out.getvalue())
        self.assertEqual([(d["work_id"], d["reason"]) for d in team["dropped"]],
                         [("W1", "not every member is in the author list")])

    def test_the_papers_of_a_team_also_stay_in_the_works_file_of_each_member(self):
        self.assertEqual(self.run_lab("discover", "--all"), 0)
        ada = lp.read_json(lp.works_path(self.data, "ada"))
        ben = lp.read_json(lp.works_path(self.data, "ben"))
        self.assertEqual(sorted(p["work_id"] for p in ada["papers"]), ["W1", "W4", "W7"])
        self.assertEqual(sorted(p["work_id"] for p in ben["papers"]), ["W4", "W7"])

    def test_a_team_needs_the_works_files_of_its_members(self):
        self.assertEqual(self.run_lab("discover", "ada-ben"), 2)
        self.assertIn("run discover first for the members of ada-ben: ada, ben", self.err.getvalue())
        self.assertFalse(os.path.exists(lp.works_path(self.data, "ada-ben")))

    def test_a_team_is_built_after_its_members_even_when_named_first(self):
        self.assertEqual(self.run_lab("discover", "ada-ben", "ada", "ben"), 0)
        self.assertEqual([p["work_id"] for p in lp.read_json(lp.works_path(self.data, "ada-ben"))["papers"]],
                         ["W4", "W7"])

    def test_sample_gives_the_shared_papers_to_ben_and_to_the_team(self):
        self.assertEqual(self.run_lab("discover", "--all"), 0)
        self.assertEqual(self.run_lab("sample", "--all", "--pilot"), 0)
        self.assertEqual(sorted(p["work_id"] for p in self.pilot_manifest("ada")["papers"]), ["W1"])
        self.assertEqual(sorted(p["work_id"] for p in self.pilot_manifest("ben")["papers"]), ["W4", "W7"])
        team = self.pilot_manifest("ada-ben")
        self.assertEqual(team["person"], "ada-ben")
        self.assertEqual(sorted(p["work_id"] for p in team["papers"]), ["W4", "W7"])
        self.assertEqual(team["n_papers"], 2)

    def test_sample_of_an_individual_does_not_need_the_works_file_of_the_team(self):
        for person in ("ada", "ben", "cal"):
            self.assertEqual(self.run_lab("discover", person), 0)
        self.assertEqual(self.run_lab("sample", "ada", "--pilot"), 0)
        self.assertEqual(self.run_lab("sample", "ada-ben", "--pilot"), 2)
        self.assertIn("run discover first for: ada-ben", self.err.getvalue())

    def test_sample_needs_the_works_file_of_every_individual_for_a_team_too(self):
        for person in ("ada", "ben"):
            self.assertEqual(self.run_lab("discover", person), 0)
        self.assertEqual(self.run_lab("discover", "ada-ben"), 0)
        self.assertEqual(self.run_lab("sample", "ada-ben", "--pilot"), 2)
        self.assertIn("run discover first for: cal", self.err.getvalue())

    def test_fetch_normalize_and_status_work_for_a_team_id(self):
        self.fetch_everyone()
        team = self.pilot_manifest("ada-ben")
        self.assertEqual({p["work_id"]: p["status"] for p in team["papers"]}, {"W4": "fetched", "W7": "fetched"})
        self.assertTrue(os.path.exists(lp.paper_path(self.data, "ada-ben", "W4")))
        self.assertEqual(lp.read_json(lp.paper_path(self.data, "ada-ben", "W4"))["person"], "ada-ben")
        self.assertEqual(self.run_lab("normalize", "ada-ben", "--pilot"), 0)
        self.assertEqual(self.run_lab("status", "--pilot"), 0)
        self.assertIn("ada-ben: works 2, sample 2, fetched 2", self.out.getvalue())

    def test_surface_of_individuals_leaves_the_team_out_and_the_team_meets_the_other_people(self):
        self.fetch_everyone()
        seen = []
        real = lab_surface.run_surface

        def spy(papers_by_person, wordlists):
            seen.append(sorted(papers_by_person))
            return real(papers_by_person, wordlists)

        with mock.patch.object(lab_surface, "run_surface", spy):
            self.assertEqual(self.run_lab("surface", "--all", "--pilot"), 0)
        self.assertEqual(seen, [["ada", "ben", "cal"], ["ada-ben", "cal"]])
        folder = os.path.join(self.data, "pilot", "surface")
        self.assertEqual(sorted(os.listdir(folder)), ["ada-ben.json", "ada.json", "ben.json", "cal.json"])

    def test_the_surface_files_of_individuals_do_not_depend_on_the_team(self):
        self.fetch_everyone()
        self.assertEqual(self.run_lab("surface", "--all", "--pilot"), 0)
        folder = os.path.join(self.data, "pilot", "surface")
        papers = {person: [lp.read_json(lp.paper_path(self.data, person, p["work_id"]))
                           for p in self.pilot_manifest(person)["papers"]] for person in ("ada", "ben", "cal")}
        expected = lab_surface.run_surface(papers, lab_surface.load_wordlists())
        for person in ("ada", "ben", "cal"):
            self.assertEqual(lp.read_json(os.path.join(folder, person + ".json")), expected[person], person)

    def test_surface_of_a_team_writes_only_the_file_of_the_team(self):
        self.fetch_everyone()
        self.assertEqual(self.run_lab("surface", "--all", "--pilot"), 0)
        folder = os.path.join(self.data, "pilot", "surface")
        before = {n: lp.read_json(os.path.join(folder, n)) for n in os.listdir(folder)}
        lp.write_json(os.path.join(folder, "ada.json"), {"sentinel": True})
        before["ada.json"] = {"sentinel": True}
        self.assertEqual(self.run_lab("surface", "ada-ben", "--pilot"), 0)
        after = {n: lp.read_json(os.path.join(folder, n)) for n in os.listdir(folder)}
        self.assertEqual(after, before)

    def test_a_team_card_goes_through_aggregate_and_check_card_like_a_person_card(self):
        self.fetch_everyone()
        self.assertEqual(self.run_lab("surface", "--all", "--pilot"), 0)
        checklist = lab_checklist.load_checklist()
        for wid in ("W4", "W7"):
            paper = lp.read_json(lp.paper_path(self.data, "ada-ben", wid))
            lp.write_json(lp.extraction_path(self.data, "ada-ben", wid),
                          make_extraction(paper, checklist, group=paper["group"]))
        self.assertEqual(self.run_lab("check-quotes", "ada-ben", "--pilot"), 0)
        self.assertEqual(self.run_lab("aggregate", "ada-ben", "--pilot"), 0)
        profile = lp.read_json(os.path.join(self.data, "pilot", "profiles", "ada-ben.json"))
        self.assertEqual((profile["person"], profile["n_papers"]), ("ada-ben", 2))
        self.assertEqual(profile["name"], TEAM["name"])
        with open(os.path.join(self.data, "pilot", "profiles", "ada-ben.md"), "w", encoding="utf-8") as handle:
            handle.write(card_for(profile))
        self.assertEqual(self.run_lab("check-card", "ada-ben", "--pilot"), 0)
        self.assertEqual(self.run_lab("references", "ada-ben", "--pilot"), 0)
        with open(os.path.join(self.data, "pilot", "profiles", "ada-ben.md"), encoding="utf-8") as handle:
            lines = [line for line in handle.read().splitlines() if line.startswith("- ")]
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("- A shared atlas of ferns. Cell Systems, 2018. doi:10.0000/w4 ("))
        self.assertTrue(lines[1].startswith("- Ferns and mosses compared. Nature Genetics, 2020. doi:10.0000/w7 ("))
        self.assertEqual(self.run_lab("check-card", "ada-ben", "--pilot"), 0)
        self.assertEqual(self.run_lab("quality", "--pilot"), 0)
        with open(os.path.join(self.data, "pilot", "profiles", "quality.md"), encoding="utf-8") as handle:
            self.assertIn(TEAM["name"], handle.read())

    def test_the_principles_check_uses_the_profiles_of_individuals_only(self):
        folder = lp.ensure_dir(self.data, "pilot", "profiles")
        for person in ("ada", "ben", "ada-ben"):
            lp.write_json(os.path.join(folder, person + ".json"), {"person": person, "quotes": []})
        with open(os.path.join(folder, "principles.md"), "w", encoding="utf-8") as handle:
            handle.write("# Principles\n")
        seen = []

        def spy(text, kind, profiles):
            seen.append((kind, [p["person"] for p in profiles]))
            return []

        with mock.patch.object(lab_card_check, "check_text", spy):
            self.assertEqual(self.run_lab("check-card", "principles", "--pilot"), 0)
        self.assertEqual(seen, [("principles", ["ada", "ben"])])


class ExitCodeTests(unittest.TestCase):
    def test_usage_errors_are_exit_code_2(self):
        out, err = io.StringIO(), io.StringIO()
        self.assertEqual(style_lab.main(["status"], environ={}, out=out, err=err), 2)
        self.assertIn("STYLE_LAB_DATA is not set", err.getvalue())
        with tempfile.TemporaryDirectory() as data:
            env = {"STYLE_LAB_DATA": data}
            self.assertEqual(style_lab.main(["discover", "nobody"], environ=env, out=out, err=err), 2)
            self.assertEqual(style_lab.main(["discover"], environ=env, out=out, err=err), 2)
            self.assertEqual(style_lab.main([], environ=env, out=out, err=err), 2)
            self.assertEqual(style_lab.main(["fly"], environ=env, out=out, err=err), 2)

    def test_help_is_exit_code_0(self):
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(style_lab.main(["--help"], out=io.StringIO(), err=io.StringIO()), 0)


if __name__ == "__main__":
    unittest.main()
