"""Tests for lab/style_lab.py: the whole pipeline offline, and the exit codes. All data is made up."""
import io
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lab"))
sys.path.insert(0, HERE)

import lab_card_check  # noqa: E402
import lab_checklist  # noqa: E402
import lab_http  # noqa: E402
import lab_paths as lp  # noqa: E402
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
        self.assertEqual(style_lab.main(["--help"], out=io.StringIO(), err=io.StringIO()), 0)


if __name__ == "__main__":
    unittest.main()
