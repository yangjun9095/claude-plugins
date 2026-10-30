"""Tests for lab/lab_openalex.py. All people and papers in this file are made up."""
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lab"))
sys.path.insert(0, HERE)

import lab_openalex as lo  # noqa: E402
import lab_venues as lv  # noqa: E402
from fakes import ADA, BEN, FakeHttp, author, make_work  # noqa: E402

VENUES = lv.load_venues()
ADA_AUTHOR = author("A1", ADA["orcid"])
ADA_BY_ID = author("A11")


def others(n, start=90):
    return [author("A{}".format(start + i)) for i in range(n)]


def classify(work, person=ADA):
    return lo.classify(work, person, VENUES)


class PositionTests(unittest.TestCase):
    def test_position_names(self):
        self.assertEqual(lo.position_name(0, 1), "sole")
        self.assertEqual(lo.position_name(0, 3), "first")
        self.assertEqual(lo.position_name(2, 3), "last")
        self.assertEqual(lo.position_name(1, 3), "middle")

    def test_the_person_matches_by_orcid_or_by_openalex_id(self):
        brief = lo.authorship_brief(make_work("W1", others(2) + [ADA_BY_ID]))
        self.assertEqual(lo.person_index(brief, ADA), 2)
        brief = lo.authorship_brief(make_work("W1", [ADA_AUTHOR] + others(2)))
        self.assertEqual(lo.person_index(brief, ADA), 0)
        brief = lo.authorship_brief(make_work("W1", others(3)))
        self.assertIsNone(lo.person_index(brief, ADA))


class GroupTests(unittest.TestCase):
    def test_last_author_is_senior(self):
        record, reason = classify(make_work("W1", others(4) + [ADA_AUTHOR]))
        self.assertIsNone(reason)
        self.assertEqual((record["group"], record["position"]), ("senior", "last"))

    def test_a_corresponding_author_second_to_last_is_senior(self):
        authors = others(3) + [author("A1", ADA["orcid"], corresponding=True), author("A99", corresponding=True)]
        record, _ = classify(make_work("W1", authors))
        self.assertEqual(record["group"], "senior")
        self.assertTrue(record["co_senior"])

    def test_first_author_is_first(self):
        record, _ = classify(make_work("W1", [ADA_AUTHOR] + others(4)))
        self.assertEqual(record["group"], "first")
        self.assertFalse(record["co_senior"])

    def test_a_first_author_who_is_corresponding_stays_first(self):
        record, _ = classify(make_work("W1", [author("A1", ADA["orcid"], True)] + others(4)))
        self.assertEqual(record["group"], "first")

    def test_a_middle_author_is_dropped(self):
        record, reason = classify(make_work("W1", others(2) + [ADA_AUTHOR] + others(2, 95)))
        self.assertIsNone(record)
        self.assertEqual(reason, "middle author")

    def test_a_review_with_three_authors_is_an_essay_in_any_position(self):
        record, _ = classify(make_work("W1", others(1) + [ADA_AUTHOR] + others(1, 95), wtype="review"))
        self.assertEqual(record["group"], "essay")

    def test_a_review_with_four_authors_follows_the_position_rules(self):
        record, _ = classify(make_work("W1", others(3) + [ADA_AUTHOR], wtype="review"))
        self.assertEqual(record["group"], "senior")

    def test_an_article_in_an_essay_venue_is_an_essay(self):
        record, _ = classify(make_work("W1", [ADA_AUTHOR, author("A90")], venue="Trends in Genetics"))
        self.assertEqual(record["group"], "essay")

    def test_a_sole_author_research_paper_is_senior(self):
        record, _ = classify(make_work("W1", [ADA_AUTHOR], venue="Cell Systems"))
        self.assertEqual((record["group"], record["position"], record["tier"]), ("senior", "sole", "high"))

    def test_ml_venues_follow_the_flag_of_the_person(self):
        work = make_work("W1", others(2) + [author("A2", BEN["orcid"])],
                         venue="Advances in Neural Information Processing Systems")
        self.assertEqual(lo.classify(work, BEN, VENUES)[0]["tier"], "high")
        work = make_work("W1", others(2) + [ADA_AUTHOR], venue="Advances in Neural Information Processing Systems")
        self.assertEqual(classify(work)[0]["tier"], "other")


class FilterTests(unittest.TestCase):
    def test_types_outside_the_list_are_dropped(self):
        for wtype in ("erratum", "book-chapter", "peer-review", "dataset"):
            record, reason = classify(make_work("W1", others(2) + [ADA_AUTHOR], wtype=wtype))
            self.assertIsNone(record)
            self.assertEqual(reason, "type " + wtype)

    def test_correction_notices_are_dropped(self):
        for title in ("Author Correction: Fern spores swell", "Correction to: Fern spores swell",
                      "Retraction Note: Fern spores", "Erratum", "Publisher Correction"):
            record, reason = classify(make_work("W1", others(2) + [ADA_AUTHOR], title=title))
            self.assertIsNone(record, title)
            self.assertEqual(reason, "correction or retraction notice")

    def test_titles_that_only_start_with_the_word_correction_are_kept(self):
        for title in ("Correction of drift in light-sheet images", "Correctional rates of fern growth"):
            record, _ = classify(make_work("W1", others(2) + [ADA_AUTHOR], title=title))
            self.assertIsNotNone(record, title)

    def test_a_work_without_the_person_is_dropped(self):
        self.assertEqual(classify(make_work("W1", others(3)))[1], "person not in the author list")


class EmptyFieldTests(unittest.TestCase):
    def test_a_work_with_empty_fields_is_classified(self):
        work = make_work("W1", others(2) + [ADA_AUTHOR], venue=None)
        work["primary_location"] = None
        work["title"] = None
        work["publication_year"] = None
        work["ids"] = None
        work["locations"] = None
        work["doi"] = None
        work["authorships"][0]["author"]["orcid"] = None
        record, reason = classify(work)
        self.assertIsNone(reason)
        self.assertEqual(record["title"], "Fern spores swell in water")
        self.assertEqual(record["tier"], "other")
        self.assertIsNone(record["year"])
        self.assertIsNone(record["pmcid"])

    def test_a_work_with_no_title_at_all_is_dropped(self):
        work = make_work("W1", others(2) + [ADA_AUTHOR])
        work["title"] = None
        work["display_name"] = None
        self.assertEqual(classify(work)[1], "no title")

    def test_a_missing_author_object_does_not_crash(self):
        work = make_work("W1", [{"author": None, "is_corresponding": None}, ADA_AUTHOR])
        self.assertEqual(classify(work)[0]["group"], "senior")


class IdentifierTests(unittest.TestCase):
    def test_pmcid_doi_and_preprint_from_the_landing_page(self):
        work = make_work("W1", [ADA_AUTHOR], doi="10.1000/FERN.1", pmcid="PMC1234567", locations=[
            {"landing_page_url": "https://www.biorxiv.org/content/10.1101/2020.01.02.123456v2.full"}])
        self.assertEqual(lo.identifiers(work), ("10.1000/fern.1", "PMC1234567", "10.1101/2020.01.02.123456", None))

    def test_a_cold_spring_harbor_journal_doi_is_not_a_preprint(self):
        work = make_work("W1", [ADA_AUTHOR], doi="10.1101/gad.000001.17")
        self.assertIsNone(lo.identifiers(work)[2])

    def test_a_biorxiv_doi_is_its_own_preprint(self):
        work = make_work("W1", [ADA_AUTHOR], doi="10.1101/654321", wtype="preprint")
        self.assertEqual(lo.identifiers(work)[2], "10.1101/654321")

    def test_arxiv_from_the_doi_and_from_a_url(self):
        work = make_work("W1", [ADA_AUTHOR], doi="10.48550/arXiv.1901.00001")
        self.assertEqual(lo.identifiers(work)[3], "1901.00001")
        work = make_work("W1", [ADA_AUTHOR], locations=[{"pdf_url": "https://arxiv.org/pdf/2101.00002v3"}])
        self.assertEqual(lo.identifiers(work)[3], "2101.00002")

    def test_a_pmcid_without_the_prefix_gets_it(self):
        work = make_work("W1", [ADA_AUTHOR])
        work["ids"] = {"pmcid": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7654321/"}
        self.assertEqual(lo.identifiers(work)[1], "PMC7654321")


class MergeTests(unittest.TestCase):
    def test_a_preprint_and_its_journal_paper_become_one_paper(self):
        journal, _ = classify(make_work("W2", others(2) + [ADA_AUTHOR], title="Fern Spores Swell in Water.",
                                        doi="10.1000/fern.2", year=2016))
        preprint, _ = classify(make_work("W1", others(2) + [ADA_AUTHOR], title="Fern spores swell in water",
                                         wtype="preprint", venue="bioRxiv", doi="10.1101/111111", year=2015))
        kept, merged = lo.merge_preprints([preprint, journal])
        self.assertEqual([r["work_id"] for r in kept], ["W2"])
        self.assertEqual(kept[0]["preprint_doi"], "10.1101/111111")
        self.assertEqual(merged, [{"kept": "W2", "merged": "W1", "title": "Fern spores swell in water"}])

    def test_different_titles_stay_apart_and_sort_by_year(self):
        a, _ = classify(make_work("W5", others(2) + [ADA_AUTHOR], title="Moss dries", year=2019))
        b, _ = classify(make_work("W4", others(2) + [ADA_AUTHOR], title="Fern swells", year=2011))
        kept, merged = lo.merge_preprints([a, b])
        self.assertEqual([r["work_id"] for r in kept], ["W4", "W5"])
        self.assertEqual(merged, [])


class SharedTests(unittest.TestCase):
    def test_the_last_author_draws_a_shared_paper(self):
        work = make_work("W7", others(3) + [author("A1", ADA["orcid"], True), author("A2", BEN["orcid"], True)])
        discoveries = {"ada": {"papers": [classify(work)[0]], "dropped": []},
                       "ben": {"papers": [lo.classify(work, BEN, VENUES)[0]], "dropped": []}}
        lo.assign_shared(discoveries, [ADA, BEN])
        self.assertEqual(discoveries["ada"]["papers"], [])
        self.assertEqual(discoveries["ada"]["dropped"][0]["reason"], "shared: drawn by ben")
        self.assertEqual([r["work_id"] for r in discoveries["ben"]["papers"]], ["W7"])

    def test_registry_order_breaks_a_tie(self):
        authors = others(1) + [author("A1", ADA["orcid"], True), author("A2", BEN["orcid"], True)] + others(2, 95)
        work = make_work("W8", authors)
        record = classify(work)[0]
        self.assertEqual(lo.owner_of(record, [ADA, BEN]), "ada")
        self.assertEqual(lo.owner_of(record, [BEN, ADA]), "ben")

    def test_a_paper_of_one_person_stays(self):
        record = classify(make_work("W9", others(2) + [ADA_AUTHOR]))[0]
        self.assertEqual(lo.owner_of(record, [ADA, BEN]), "ada")


def page(results, count=None):
    return {"meta": {"count": len(results) if count is None else count}, "results": results}


class FetchTests(unittest.TestCase):
    def test_numbered_pages_and_both_filters_without_repeats(self):
        w1 = make_work("W1", others(2) + [ADA_AUTHOR], title="Paper one")
        w2 = make_work("W2", [ADA_AUTHOR] + others(2), title="Paper two")
        w3 = make_work("W3", others(1) + [ADA_BY_ID], title="Paper three")
        http = FakeHttp([
            (("author.orcid:0000-0000-0000-0001", "&page=1"), page([w1, w2], 201)),
            (("author.orcid:0000-0000-0000-0001", "&page=2"), page([w3], 201)),
            (("author.id:A1&", "&page=1"), page([w1])),
            (("author.id:A11&", "&page=1"), page([w3])),
        ])
        works = lo.fetch_works(http, ADA)
        self.assertEqual([lo.short_id(w["id"]) for w in works], ["W1", "W2", "W3"])
        self.assertEqual(len(http.calls), 4)
        self.assertFalse(any("cursor" in url for url, _ in http.calls))

    def test_an_empty_page_ends_the_paging(self):
        http = FakeHttp([(("author.orcid:", "&page=1"), page([make_work("W1", [ADA_AUTHOR])], 500)),
                         (("author.orcid:", "&page=2"), page([], 500)), (("author.id:",), page([]))])
        self.assertEqual(len(lo.fetch_works(http, ADA)), 1)

    def test_candidates(self):
        http = FakeHttp([("authors?search=Ada%20Quill", {"results": [
            {"id": "https://openalex.org/A1", "orcid": "https://orcid.org/0000-0000-0000-0001", "works_count": 40,
             "display_name": "Ada Quill", "last_known_institutions": [{"display_name": "Fern Institute"}]},
            {"id": "https://openalex.org/A7", "orcid": None, "works_count": 2, "display_name": "A. Quill",
             "last_known_institutions": None}]})])
        rows = lo.candidates(http, "Ada Quill")
        self.assertEqual(rows[0], {"id": "A1", "orcid": "0000-0000-0000-0001", "works_count": 40,
                                   "name": "Ada Quill", "institutions": ["Fern Institute"]})
        self.assertIsNone(rows[1]["orcid"])
        self.assertEqual(rows[1]["institutions"], [])

    def test_discover_keeps_drops_and_merges(self):
        works = [
            make_work("W1", others(2) + [ADA_AUTHOR], title="Spores swell", doi="10.1000/a", year=2016),
            make_work("W2", others(2) + [ADA_AUTHOR], title="Spores swell", wtype="preprint", venue="bioRxiv",
                      doi="10.1101/222222", year=2015),
            make_work("W3", [ADA_AUTHOR] + others(3), title="Moss dries", venue="Nature Genetics", year=2009),
            make_work("W4", others(2) + [ADA_AUTHOR] + others(2, 95), title="A big atlas"),
            make_work("W5", others(2) + [ADA_AUTHOR], title="Erratum", wtype="erratum"),
        ]
        http = FakeHttp([(("author.orcid:",), page(works)), (("author.id:",), page([]))])
        result = lo.discover(http, ADA, VENUES)
        self.assertEqual(result["n_works"], 5)
        self.assertEqual([p["work_id"] for p in result["papers"]], ["W3", "W1"])
        self.assertEqual({d["work_id"]: d["reason"] for d in result["dropped"]},
                         {"W4": "middle author", "W5": "type erratum"})
        self.assertEqual(result["merged"][0]["merged"], "W2")
        self.assertEqual(result["papers"][0]["tier"], "high")
        self.assertEqual(result["venues_version"], VENUES["version"])


if __name__ == "__main__":
    unittest.main()
