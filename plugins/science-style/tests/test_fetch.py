"""Tests for lab/lab_fetch.py. All papers and text in this file are made up."""
import os
import sys
import tempfile
import unittest
import urllib.parse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lab"))
sys.path.insert(0, HERE)

import lab_fetch as lf  # noqa: E402
import lab_http as lh  # noqa: E402
import lab_paths as lp  # noqa: E402
import lab_sample as ls  # noqa: E402
import lab_text as lt  # noqa: E402
from fakes import FakeHttp, MapOpener, arxiv_body, epmc_result, jats_body  # noqa: E402

SEARCH = "europepmc/webservices/rest/search"
NO_HITS = (SEARCH, {"resultList": {"result": []}})


def q(text):
    return urllib.parse.quote(text)


def rec(wid, pmcid=None, doi=None, preprint_doi=None, arxiv_id=None, year=2010, title=None):
    return {"work_id": wid, "doi": doi, "title": title or "Paper " + wid, "year": year, "venue": "Cell",
            "type": "article", "tier": "high", "group": "senior", "co_senior": False, "pmcid": pmcid,
            "preprint_doi": preprint_doi, "arxiv_id": arxiv_id, "authors": []}


def paper(wid, **kwargs):
    return ls.manifest_paper(rec(wid, **kwargs), "senior/high")


class RouteTests(unittest.TestCase):
    def test_a_pmc_paper_is_published_unless_flagged(self):
        http = FakeHttp([((SEARCH, q('DOI:"10.1000/a"')), epmc_result(doi="10.1000/a", pmcid="PMC1000001")),
                         ("efetch.fcgi?db=pmc&id=1000001", jats_body(700))])
        result, reasons = lf.try_routes(http, paper("W1", pmcid="PMC1000001", doi="10.1000/a"), "ada")
        self.assertIsNone(reasons)
        self.assertEqual((result["route"], result["text_version"], result["person"]), ("ncbi-pmc", "published", "ada"))
        self.assertGreaterEqual(lt.body_words(result), lf.MIN_BODY_WORDS)

    def test_the_author_manuscript_flag_gives_accepted(self):
        http = FakeHttp([((SEARCH, q('DOI:"10.1000/a"')), epmc_result(doi="10.1000/a", pmcid="PMC1000001",
                                                                      auth_man="Y")),
                         ("efetch.fcgi?db=pmc&id=1000001", jats_body(700))])
        result, _ = lf.try_routes(http, paper("W1", pmcid="PMC1000001", doi="10.1000/a"), "ada")
        self.assertEqual(result["text_version"], "accepted")

    def test_a_manuscript_id_in_the_jats_gives_accepted(self):
        http = FakeHttp([("efetch.fcgi?db=pmc&id=1000001", jats_body(700, manuscript=True))])
        result, _ = lf.try_routes(http, paper("W1", pmcid="PMC1000001"), "ada")
        self.assertEqual(result["text_version"], "accepted")

    def test_a_failed_ncbi_request_falls_back_to_europe_pmc_with_one_retry(self):
        http = FakeHttp([("efetch.fcgi", lh.FetchError("u", 500, "down")),
                         ("PMC1000001/fullTextXML", jats_body(700))])
        result, _ = lf.try_routes(http, paper("W1", pmcid="PMC1000001"), "ada")
        self.assertEqual(result["route"], "europepmc")
        self.assertIn(("https://www.ebi.ac.uk/europepmc/webservices/rest/PMC1000001/fullTextXML", 1), http.calls)

    def test_a_short_body_is_a_route_failure(self):
        http = FakeHttp([("efetch.fcgi?db=pmc&id=1000001", jats_body(100)), NO_HITS])
        result, reasons = lf.try_routes(http, paper("W1", pmcid="PMC1000001"), "ada")
        self.assertIsNone(result)
        self.assertTrue(any("fewer than 600" in r for r in reasons))
        self.assertIn("preprint: no bioRxiv DOI", reasons)
        self.assertIn("arxiv: no arXiv ID", reasons)

    def test_the_preprint_route(self):
        jats_url = "https://www.biorxiv.org/content/early/2020/01/01/222222.source.xml"
        http = FakeHttp([("details/biorxiv/10.1101/222222", {"collection": [{"version": "1", "jatsxml": jats_url}]}),
                         ("222222.source.xml", jats_body(700))])
        result, _ = lf.try_routes(http, paper("W2", preprint_doi="10.1101/222222"), "ada")
        self.assertEqual((result["route"], result["text_version"], result["source_url"]),
                         ("biorxiv", "preprint", jats_url))

    def test_a_doi_unknown_to_both_preprint_servers_fails(self):
        http = FakeHttp([("details/biorxiv/", {"collection": []}), ("details/medrxiv/", {"collection": []})])
        result, reasons = lf.try_routes(http, paper("W2", preprint_doi="10.1101/222222"), "ada")
        self.assertIsNone(result)
        self.assertTrue(any("do not know" in r for r in reasons))

    def test_a_cold_spring_harbor_journal_doi_is_not_tried_as_a_preprint(self):
        result, reasons = lf.try_routes(FakeHttp([NO_HITS]), paper("W3", doi="10.1101/gad.000001.17"), "ada")
        self.assertIsNone(result)
        self.assertIn("preprint: no bioRxiv DOI", reasons)

    def test_medrxiv_after_biorxiv(self):
        jats_url = "https://www.medrxiv.org/content/early/2021/01/01/333333.source.xml"
        http = FakeHttp([("details/biorxiv/", {"collection": []}),
                         ("details/medrxiv/10.1101/333333", {"collection": [{"jatsxml": jats_url}]}),
                         ("333333.source.xml", jats_body(700))])
        result, _ = lf.try_routes(http, paper("W2", preprint_doi="10.1101/333333"), "ada")
        self.assertEqual(result["route"], "medrxiv")

    def test_the_arxiv_route(self):
        http = FakeHttp([("arxiv.org/html/1901.00001", arxiv_body(700))])
        result, _ = lf.try_routes(http, paper("W4", arxiv_id="1901.00001"), "ben")
        self.assertEqual((result["route"], result["text_version"]), ("arxiv-html", "arxiv"))


JATS_URL = "https://www.biorxiv.org/content/early/2020/01/01/222222.source.xml"
DETAILS = ("details/biorxiv/10.1101/222222", {"collection": [{"version": "1", "jatsxml": JATS_URL}]})


class TransientTests(unittest.TestCase):
    def test_which_failures_are_transient(self):
        cases = [(None, "https://arxiv.org/html/1", True), (429, "https://www.biorxiv.org/x", True),
                 (503, "https://eutils.ncbi.nlm.nih.gov/x", True), (500, "https://arxiv.org/html/1", True),
                 (404, "https://www.biorxiv.org/x", False), (403, "https://www.biorxiv.org/x", True),
                 (403, "https://www.medrxiv.org/x", True), (403, "https://api.biorxiv.org/x", True),
                 (403, "https://api.medrxiv.org/x", True), (403, "https://www.ebi.ac.uk/x", False),
                 (400, "https://api.biorxiv.org/x", False)]
        for status, url, expected in cases:
            self.assertEqual(lf.is_transient(lh.FetchError(url, status, "x")), expected, (status, url))

    def test_a_biorxiv_jats_429_defers_the_paper(self):
        http = FakeHttp([NO_HITS, DETAILS, (JATS_URL, lh.FetchError(JATS_URL, 429, "HTTP status 429"))])
        with self.assertRaises(lf.Deferred) as caught:
            lf.try_routes(http, paper("W2", preprint_doi="10.1101/222222"), "ada")
        self.assertTrue(any("429" in r for r in caught.exception.reasons))
        self.assertIsInstance(caught.exception, lh.FetchError)

    def test_a_failed_preprint_api_defers_the_paper(self):
        http = FakeHttp([NO_HITS, ("details/biorxiv/", lh.FetchError("https://api.biorxiv.org/d", 503, "down")),
                         ("details/medrxiv/", {"collection": []})])
        with self.assertRaises(lf.Deferred) as caught:
            lf.try_routes(http, paper("W2", preprint_doi="10.1101/222222"), "ada")
        self.assertFalse(any("do not know" in r for r in caught.exception.reasons))

    def test_a_preprint_api_answer_that_is_not_json_defers_the_paper(self):
        http = FakeHttp([NO_HITS, ("details/biorxiv/", "<html>busy</html>"), ("details/medrxiv/", {"collection": []})])
        with self.assertRaises(lf.Deferred):
            lf.try_routes(http, paper("W2", preprint_doi="10.1101/222222"), "ada")

    def test_an_empty_collection_from_both_apis_is_permanent(self):
        http = FakeHttp([NO_HITS, ("details/biorxiv/", {"collection": []}), ("details/medrxiv/", {"collection": []})])
        result, reasons = lf.try_routes(http, paper("W2", preprint_doi="10.1101/222222"), "ada")
        self.assertIsNone(result)
        self.assertIn("preprint: the bioRxiv and medRxiv APIs do not know 10.1101/222222", reasons)

    def test_a_europe_pmc_fulltext_500_is_a_normal_route_failure(self):
        fulltext = "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC1000001/fullTextXML"
        http = FakeHttp([NO_HITS, ("efetch.fcgi", lh.FetchError("https://eutils.ncbi.nlm.nih.gov/e", 404, "gone")),
                         ("fullTextXML", lh.FetchError(fulltext, 500, "HTTP status 500"))])
        result, reasons = lf.try_routes(http, paper("W1", pmcid="PMC1000001"), "ada")
        self.assertIsNone(result)
        self.assertTrue(any(r.startswith("europepmc: ") and "500" in r for r in reasons))

    def test_a_europe_pmc_fulltext_503_defers_the_paper(self):
        fulltext = "https://www.ebi.ac.uk/europepmc/webservices/rest/PMC1000001/fullTextXML"
        http = FakeHttp([NO_HITS, ("efetch.fcgi", lh.FetchError("https://eutils.ncbi.nlm.nih.gov/e", 404, "gone")),
                         ("fullTextXML", lh.FetchError(fulltext, 503, "HTTP status 503"))])
        with self.assertRaises(lf.Deferred):
            lf.try_routes(http, paper("W1", pmcid="PMC1000001"), "ada")

    def test_an_arxiv_timeout_defers_the_paper(self):
        http = FakeHttp([NO_HITS, ("arxiv.org/html/", lh.FetchError("https://arxiv.org/html/1901.00001", None, "timed out"))])
        with self.assertRaises(lf.Deferred):
            lf.try_routes(http, paper("W4", arxiv_id="1901.00001"), "ben")

    def test_a_transient_failure_does_not_block_a_working_route(self):
        http = FakeHttp([NO_HITS, ("efetch.fcgi", lh.FetchError("https://eutils.ncbi.nlm.nih.gov/e", 503, "busy")),
                         ("fullTextXML", lh.FetchError("https://www.ebi.ac.uk/f", 503, "busy")),
                         ("arxiv.org/html/1901.00001", arxiv_body(700))])
        result, reasons = lf.try_routes(http, paper("W4", pmcid="PMC1000001", arxiv_id="1901.00001"), "ben")
        self.assertIsNone(reasons)
        self.assertEqual(result["route"], "arxiv-html")


class LookupTests(unittest.TestCase):
    def test_the_lookup_fills_the_pmcid_the_flag_and_a_matching_preprint(self):
        http = FakeHttp([((SEARCH, q('DOI:"10.1000/a"')), epmc_result(doi="10.1000/A", pmcid="PMC1000009",
                                                                      auth_man="Y")),
                         ((SEARCH, "SRC%3APPR"), {"resultList": {"result": [
                             {"doi": "10.1101/333333", "title": "Fern Spores Swell!"}]}})])
        info = lf.epmc_lookup(http, paper("W1", doi="10.1000/a", title="Fern spores swell"))
        self.assertEqual(info, {"pmcid": "PMC1000009", "auth_man": True, "preprint_doi": "10.1101/333333",
                                "failed": False})

    def test_a_preprint_with_another_title_is_ignored(self):
        http = FakeHttp([((SEARCH, "SRC%3APPR"), {"resultList": {"result": [
            {"doi": "10.1101/333333", "title": "Moss dries in wind"}]}})])
        info = lf.epmc_lookup(http, paper("W1", title="Fern spores swell"))
        self.assertIsNone(info["preprint_doi"])


class LookupFailureTests(unittest.TestCase):
    def test_a_failed_search_sets_the_failed_key(self):
        http = FakeHttp([(SEARCH, lh.FetchError("u", 500, "down"))])
        info = lf.epmc_lookup(http, paper("W1", doi="10.1000/a", title="Fern spores swell"))
        self.assertEqual(info, {"pmcid": None, "auth_man": False, "preprint_doi": None, "failed": True})

    def test_a_search_with_no_hits_is_not_a_failure(self):
        info = lf.epmc_lookup(FakeHttp([NO_HITS]), paper("W1", doi="10.1000/a", title="Fern spores swell"))
        self.assertFalse(info["failed"])

    def test_a_failed_lookup_does_not_block_a_working_pmc_route(self):
        http = FakeHttp([(SEARCH, lh.FetchError("u", 500, "down")),
                         ("efetch.fcgi?db=pmc&id=1000001", jats_body(700))])
        result, reasons = lf.try_routes(http, paper("W1", pmcid="PMC1000001", doi="10.1000/a"), "ada")
        self.assertIsNone(reasons)
        self.assertEqual(result["route"], "ncbi-pmc")

    def test_a_failed_lookup_with_no_working_route_defers_the_paper(self):
        http = FakeHttp([(SEARCH, lh.FetchError("u", 500, "down"))])
        with self.assertRaises(lf.Deferred) as caught:
            lf.try_routes(http, paper("W1", doi="10.1000/a"), "ada")
        self.assertIn("europepmc lookup: failed", caught.exception.reasons)


class FetchPersonTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.data = self.tmp.name
        self.path = os.path.join(self.data, "manifest.json")

    def test_a_paper_without_text_is_replaced_and_the_replacement_is_fetched(self):
        records = [rec("W{}".format(i), pmcid="PMC100000{}".format(i), year=2000 + i) for i in range(6)]
        manifest = ls.build_sample("ada", records)
        failing = manifest["papers"][0]["work_id"]
        http = FakeHttp([("efetch.fcgi?db=pmc&id=100000{}".format(i), jats_body(700))
                         for i in range(6) if "W{}".format(i) != failing] + [NO_HITS])
        counts = lf.fetch_person(http, manifest, self.path, self.data, {r["work_id"]: r for r in records})
        self.assertEqual(counts, {"fetched": 5, "replaced": 1})
        self.assertEqual(manifest["n_papers"], 5)
        self.assertTrue(manifest["replacements"][0]["reason"].startswith("no open full text: "))
        self.assertEqual(lp.read_json(self.path)["n_papers"], 5)
        for p in manifest["papers"]:
            if p["status"] == "fetched":
                self.assertTrue(os.path.exists(lp.paper_path(self.data, "ada", p["work_id"])))

    def test_an_interrupted_fetch_resumes_without_downloading_again(self):
        records = [rec("W{}".format(i), pmcid="PMC200000{}".format(i), year=2000 + i) for i in range(3)]
        lookup = {r["work_id"]: r for r in records}
        manifest = ls.build_sample("ada", records)
        order = [p["work_id"] for p in manifest["papers"]]
        cache = os.path.join(self.data, "raw")
        crash = MapOpener([("id=200000" + order[1][1:], RuntimeError("power cut")), ("efetch.fcgi", jats_body(700))])
        with self.assertRaises(RuntimeError):
            lf.fetch_person(lh.Http(cache, opener=crash, sleep=lambda s: None), manifest, self.path, self.data, lookup)
        saved = lp.read_json(self.path)
        self.assertEqual([p["status"] for p in saved["papers"]], ["fetched", "chosen", "chosen"])
        calm = MapOpener([("efetch.fcgi", jats_body(700))])
        counts = lf.fetch_person(lh.Http(cache, opener=calm, sleep=lambda s: None), saved, self.path, self.data, lookup)
        self.assertEqual(counts, {"fetched": 2, "replaced": 0})
        self.assertFalse(any("id=200000" + order[0][1:] in url for url in calm.calls))
        self.assertEqual(saved["replacements"], [])

    def test_a_failed_europe_pmc_lookup_stops_instead_of_replacing(self):
        records = [rec("W{}".format(i), year=2000 + i) for i in range(3)]
        manifest = ls.build_sample("ada", records)
        http = FakeHttp([(SEARCH, lh.FetchError("u", 500, "down"))])
        with self.assertRaises(lh.FetchError):
            lf.fetch_person(http, manifest, self.path, self.data, {r["work_id"]: r for r in records})
        self.assertEqual([p["status"] for p in manifest["papers"]], ["chosen", "chosen", "chosen"])
        self.assertEqual(manifest["replacements"], [])

    def test_after_a_failed_lookup_the_saved_manifest_keeps_the_earlier_papers(self):
        records = [rec("W{}".format(i), pmcid="PMC500000{}".format(i), year=2000 + i) for i in range(3)]
        manifest = ls.build_sample("ada", records)
        first = manifest["papers"][0]["pmcid"][3:]
        http = FakeHttp([(SEARCH, lh.FetchError("u", 500, "down")), ("efetch.fcgi?db=pmc&id=" + first, jats_body(700))])
        with self.assertRaises(lh.FetchError):
            lf.fetch_person(http, manifest, self.path, self.data, {r["work_id"]: r for r in records})
        saved = lp.read_json(self.path)
        self.assertEqual([p["status"] for p in saved["papers"]], ["fetched", "chosen", "chosen"])
        self.assertEqual(saved["replacements"], [])

    def test_a_paper_that_biorxiv_refuses_for_now_is_deferred_and_the_next_paper_is_fetched(self):
        records = [rec("W0", preprint_doi="10.1101/222222", year=2000),
                   rec("W1", pmcid="PMC6000001", year=2001), rec("W2", pmcid="PMC6000002", year=2002)]
        manifest = ls.build_sample("ada", records)
        self.assertEqual([p["work_id"] for p in manifest["papers"]], ["W0", "W1", "W2"])
        http = FakeHttp([NO_HITS, DETAILS, (JATS_URL, lh.FetchError(JATS_URL, 429, "HTTP status 429")),
                         ("efetch.fcgi?db=pmc&id=600000", jats_body(700))])
        logged = []
        with self.assertRaises(lh.FetchError) as caught:
            lf.fetch_person(http, manifest, self.path, self.data, {r["work_id"]: r for r in records}, log=logged.append)
        self.assertIsInstance(caught.exception, lf.Deferred)
        self.assertIn("ada", str(caught.exception))
        self.assertIn("W0", str(caught.exception))
        self.assertIn("429", str(caught.exception))
        self.assertEqual([p["status"] for p in manifest["papers"]], ["chosen", "fetched", "fetched"])
        self.assertEqual(manifest["replacements"], [])
        saved = lp.read_json(self.path)
        self.assertEqual([p["status"] for p in saved["papers"]], ["chosen", "fetched", "fetched"])
        self.assertTrue(any(line.startswith("deferred W0: ") for line in logged))
        self.assertEqual(sum(1 for url, _ in http.calls if url == JATS_URL), 1)

    def test_an_api_with_no_record_still_leads_to_a_replacement(self):
        records = [rec("W0", preprint_doi="10.1101/222222", year=2000)]
        manifest = ls.build_sample("ada", records)
        http = FakeHttp([NO_HITS, ("details/", {"collection": []})])
        counts = lf.fetch_person(http, manifest, self.path, self.data, {"W0": records[0]})
        self.assertEqual(counts, {"fetched": 0, "replaced": 1})
        self.assertIn("do not know", manifest["replacements"][0]["reason"])

    def test_an_empty_queue_ends_the_loop(self):
        records = [rec("W0")]
        manifest = ls.build_sample("ada", records)
        counts = lf.fetch_person(FakeHttp([NO_HITS]), manifest, self.path, self.data, {"W0": records[0]})
        self.assertEqual(counts, {"fetched": 0, "replaced": 1})
        self.assertEqual(manifest["n_papers"], 0)
        self.assertIsNone(manifest["replacements"][0]["replacement"])

    def test_only_limits_the_fetch(self):
        records = [rec("W{}".format(i), pmcid="PMC300000{}".format(i), year=2000 + i) for i in range(3)]
        manifest = ls.build_sample("ada", records)
        first = manifest["papers"][0]["work_id"]
        http = FakeHttp([("efetch.fcgi", jats_body(700))])
        counts = lf.fetch_person(http, manifest, self.path, self.data, {r["work_id"]: r for r in records},
                                 only={first})
        self.assertEqual(counts, {"fetched": 1, "replaced": 0})
        self.assertEqual([p["status"] for p in manifest["papers"]], ["fetched", "chosen", "chosen"])

    def test_renormalize_rebuilds_from_the_cache_without_requests(self):
        records = [rec("W0", pmcid="PMC4000000")]
        manifest = ls.build_sample("ada", records)
        cache = os.path.join(self.data, "raw")
        lf.fetch_person(lh.Http(cache, opener=MapOpener([("efetch.fcgi", jats_body(700))]), sleep=lambda s: None),
                        manifest, self.path, self.data, {"W0": records[0]})
        os.remove(lp.paper_path(self.data, "ada", "W0"))
        self.assertEqual(lf.renormalize_person(lh.Http(cache, offline=True), manifest, self.data), [])
        rebuilt = lp.read_json(lp.paper_path(self.data, "ada", "W0"))
        self.assertEqual((rebuilt["route"], rebuilt["text_version"]), ("ncbi-pmc", "published"))
        empty = os.path.join(self.data, "empty")
        failures = lf.renormalize_person(lh.Http(empty, offline=True), manifest, self.data)
        self.assertEqual(failures[0]["work_id"], "W0")
        self.assertIn("not in the cache", failures[0]["error"])


if __name__ == "__main__":
    unittest.main()
