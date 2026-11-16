"""Tests for lab/lab_openalex.py. All people and papers in this file are made up."""
import copy
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

    def test_an_essay_type_with_four_authors_is_dropped(self):
        for wtype in ("review", "editorial", "letter"):
            record, reason = classify(make_work("W1", others(3) + [ADA_AUTHOR], wtype=wtype))
            self.assertIsNone(record, wtype)
            self.assertEqual(reason, "essay type with more than 3 authors")

    def test_an_article_in_an_essay_venue_is_an_essay(self):
        record, _ = classify(make_work("W1", [ADA_AUTHOR, author("A90")], venue="Trends in Genetics"))
        self.assertEqual(record["group"], "essay")

    def test_an_article_in_an_essay_venue_with_four_authors_is_dropped(self):
        record, reason = classify(make_work("W1", [ADA_AUTHOR] + others(3), venue="Trends in Genetics"))
        self.assertIsNone(record)
        self.assertEqual(reason, "essay type with more than {} authors".format(lo.MAX_ESSAY_AUTHORS))

    def test_a_reply_with_three_authors_is_an_essay(self):
        for title in ("Reply to: Fern spores swell", "Response to Ash and Birch", '"Reply to" a critique of moss',
                      "“Response to” spore critics", "CORRESPONDENCE: moss dries", "correspondence"):
            record, reason = classify(make_work("W1", [ADA_AUTHOR] + others(2), title=title))
            self.assertIsNone(reason, title)
            self.assertEqual(record["group"], "essay", title)

    def test_a_reply_with_four_authors_is_dropped(self):
        record, reason = classify(make_work("W1", others(3) + [ADA_AUTHOR], title="Reply to: Fern spores swell"))
        self.assertIsNone(record)
        self.assertEqual(reason, "reply with more than 3 authors")

    def test_titles_that_only_resemble_a_reply_follow_the_position_rules(self):
        for title in ("Responses to drought in ferns", "A reply to critics of moss", "Replying to light in ferns"):
            record, _ = classify(make_work("W1", others(3) + [ADA_AUTHOR], title=title))
            self.assertEqual(record["group"], "senior", title)

    def test_a_list_of_exactly_100_authors_is_dropped_as_cut(self):
        record, reason = classify(make_work("W1", others(99, start=200) + [ADA_AUTHOR]))
        self.assertIsNone(record)
        self.assertEqual(reason, "author list cut at 100")
        record, _ = classify(make_work("W1", others(98, start=200) + [ADA_AUTHOR]))
        self.assertEqual(record["group"], "senior")
        flagged = make_work("W1", others(3) + [ADA_AUTHOR])
        flagged["is_authors_truncated"] = True
        self.assertEqual(classify(flagged), (None, "author list cut at 100"))

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
        work = make_work("W1", [ADA_AUTHOR], doi="10.1000/FERN.1", pmcid="PMC90000001", locations=[
            {"landing_page_url": "https://www.biorxiv.org/content/10.1101/2020.01.02.123456v2.full"}])
        self.assertEqual(lo.identifiers(work), ("10.1000/fern.1", "PMC90000001", "10.1101/2020.01.02.123456", None))

    def test_a_cold_spring_harbor_journal_doi_is_not_a_preprint(self):
        work = make_work("W1", [ADA_AUTHOR], doi="10.1101/gad.000001.17")
        self.assertIsNone(lo.identifiers(work)[2])

    def test_a_biorxiv_doi_is_its_own_preprint(self):
        work = make_work("W1", [ADA_AUTHOR], doi="10.1101/954321", wtype="preprint")
        self.assertEqual(lo.identifiers(work)[2], "10.1101/954321")

    def test_preprint_doi_comes_from_a_biorxiv_location_with_a_doi_landing_url(self):
        work = make_work("W1", [ADA_AUTHOR], doi="10.1000/fern.1", locations=[
            {"landing_page_url": "https://doi.org/10.1000/fern.1", "pdf_url": None,
             "source": {"display_name": "Current Biology"}},
            {"landing_page_url": "https://doi.org/10.1101/2020.07.21.000777",
             "pdf_url": "https://www.biorxiv.org/content/biorxiv/early/2020/07/22/2020.07.21.000777.full.pdf",
             "source": {"display_name": "bioRxiv (Cold Spring Harbor Laboratory)"}}])
        self.assertEqual(lo.identifiers(work)[2], "10.1101/2020.07.21.000777")

    def test_the_new_rxiv_prefix_is_a_preprint_doi(self):
        new = "10.64898/2026.02.03.000321"
        work = make_work("W1", [ADA_AUTHOR], doi=new, wtype="preprint")
        self.assertEqual(lo.identifiers(work)[2], new)
        work = make_work("W1", [ADA_AUTHOR], doi="10.1000/fern.1", locations=[
            {"landing_page_url": "https://www.biorxiv.org/content/10.64898/2026.02.03.000321v1.full"}])
        self.assertEqual(lo.identifiers(work)[2], new)
        work = make_work("W1", [ADA_AUTHOR], doi="10.1000/fern.1", locations=[
            {"landing_page_url": "https://doi.org/10.64898/2026.02.03.000321", "pdf_url": None,
             "source": {"display_name": "medRxiv"}}])
        self.assertEqual(lo.identifiers(work)[2], new)
        work = make_work("W1", [ADA_AUTHOR], doi="10.64898/journal.000001")
        self.assertIsNone(lo.identifiers(work)[2])

    def test_arxiv_from_the_doi_and_from_a_url(self):
        work = make_work("W1", [ADA_AUTHOR], doi="10.48550/arXiv.1901.99901")
        self.assertEqual(lo.identifiers(work)[3], "1901.99901")
        work = make_work("W1", [ADA_AUTHOR], locations=[{"pdf_url": "https://arxiv.org/pdf/2101.99902v3"}])
        self.assertEqual(lo.identifiers(work)[3], "2101.99902")

    def test_a_pmcid_without_the_prefix_gets_it(self):
        work = make_work("W1", [ADA_AUTHOR])
        work["ids"] = {"pmcid": "https://www.ncbi.nlm.nih.gov/pmc/articles/PMC90000002/"}
        self.assertEqual(lo.identifiers(work)[1], "PMC90000002")


class MergeTests(unittest.TestCase):
    def test_a_preprint_and_its_journal_paper_become_one_paper(self):
        journal, _ = classify(make_work("W2", others(2) + [ADA_AUTHOR], title="Fern Spores Swell in Water.",
                                        doi="10.1000/fern.2", year=2016))
        preprint, _ = classify(make_work("W1", others(2) + [ADA_AUTHOR], title="Fern spores swell in water",
                                         wtype="preprint", venue="bioRxiv", doi="10.1101/911111", year=2015))
        kept, merged = lo.merge_preprints([preprint, journal])
        self.assertEqual([r["work_id"] for r in kept], ["W2"])
        self.assertEqual(kept[0]["preprint_doi"], "10.1101/911111")
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


TEAM = {"id": "ada-ben", "name": "Ada Quill and Ben Rowan (joint papers)", "members": ["ada", "ben"],
        "confirmed_by": "test"}
ADA_SIGNED = author("A1", ADA["orcid"])
BEN_SIGNED = author("A2", BEN["orcid"])


def member_works(*works):
    """Return the discovery dict of Ada and of Ben for the same OpenAlex works, as discover builds them."""
    out = []
    for person in (ADA, BEN):
        kept, dropped = [], []
        for work in works:
            record, reason = lo.classify(work, person, VENUES)
            if record:
                kept.append(record)
            else:
                dropped.append({"work_id": lo.short_id(work["id"]), "title": work["title"], "type": work["type"],
                                "reason": reason})
        papers, merged = lo.merge_preprints(kept)
        out.append({"schema": 1, "person": person["id"], "orcid": person["orcid"], "n_works": len(works),
                    "papers": papers, "dropped": dropped, "merged": merged})
    return out


def team_of(*works):
    return lo.team_works(TEAM, member_works(*works), [ADA, BEN])


class TeamWorksTests(unittest.TestCase):
    def test_a_paper_with_both_members_and_one_last_author_is_kept_as_senior(self):
        work = make_work("W1", others(2) + [ADA_SIGNED, BEN_SIGNED], title="A joint atlas", doi="10.1000/j1",
                         venue="Cell Systems", year=2018, pmcid="PMC5000001")
        result = team_of(work)
        self.assertEqual([p["work_id"] for p in result["papers"]], ["W1"])
        paper = result["papers"][0]
        self.assertEqual(paper["group"], "senior")
        self.assertEqual((paper["tier"], paper["venue"], paper["doi"], paper["pmcid"]),
                         ("high", "Cell Systems", "10.1000/j1", "PMC5000001"))
        self.assertEqual(result["dropped"], [])

    def test_the_result_has_the_shape_of_an_individual_works_file(self):
        result = team_of(make_work("W1", others(2) + [ADA_SIGNED, BEN_SIGNED]))
        self.assertEqual(sorted(result), ["dropped", "merged", "n_works", "papers", "person", "schema"])
        self.assertEqual((result["schema"], result["person"], result["n_works"]), (1, "ada-ben", 1))
        self.assertEqual(result["merged"], [])

    def test_a_paper_that_one_member_drops_as_middle_author_is_kept_from_the_other_file(self):
        work = make_work("W2", others(1) + [ADA_SIGNED] + others(1, 95) + [BEN_SIGNED], title="Ada in the middle")
        ada_file, ben_file = member_works(work)
        self.assertEqual(ada_file["papers"], [])
        self.assertEqual([p["work_id"] for p in ben_file["papers"]], ["W2"])
        result = lo.team_works(TEAM, [ada_file, ben_file], [ADA, BEN])
        self.assertEqual([p["work_id"] for p in result["papers"]], ["W2"])
        self.assertEqual(result["papers"][0]["group"], "senior")

    def test_a_first_author_record_becomes_senior_when_the_other_member_is_last(self):
        work = make_work("W3", [ADA_SIGNED] + others(2) + [BEN_SIGNED], title="Ada leads, Ben is last")
        ada_file, ben_file = member_works(work)
        self.assertEqual(ada_file["papers"][0]["group"], "first")
        result = lo.team_works(TEAM, [ada_file, ben_file], [ADA, BEN])
        self.assertEqual([(p["work_id"], p["group"]) for p in result["papers"]], [("W3", "senior")])

    def test_a_corresponding_member_who_is_not_first_counts_as_senior(self):
        work = make_work("W4", others(1) + [author("A1", ADA["orcid"], True)] + others(2, 95) + [BEN_SIGNED] + others(1, 97),
                         title="Ada corresponds")
        result = team_of(work)
        self.assertEqual([p["work_id"] for p in result["papers"]], ["W4"])

    def test_a_paper_where_no_member_is_last_or_corresponding_is_dropped(self):
        work = make_work("W5", [ADA_SIGNED] + others(2) + [BEN_SIGNED] + others(2, 95), title="Neither leads")
        ada_file, ben_file = member_works(work)
        self.assertEqual(ben_file["papers"], [])
        result = lo.team_works(TEAM, [ada_file, ben_file], [ADA, BEN])
        self.assertEqual(result["papers"], [])
        self.assertEqual(result["dropped"][0]["work_id"], "W5")
        self.assertEqual(result["dropped"][0]["reason"], "no member is last or corresponding author")
        self.assertEqual(result["n_works"], 1)

    def test_a_paper_of_one_member_alone_is_dropped(self):
        work = make_work("W6", others(2) + [ADA_SIGNED], title="Ada alone")
        result = team_of(work)
        self.assertEqual(result["papers"], [])
        self.assertEqual([(d["work_id"], d["reason"]) for d in result["dropped"]],
                         [("W6", "not every member is in the author list")])

    def test_a_paper_in_both_files_appears_once(self):
        work = make_work("W7", [ADA_SIGNED] + others(2) + [BEN_SIGNED])
        files = member_works(work)
        self.assertEqual([len(f["papers"]) for f in files], [1, 1])
        result = lo.team_works(TEAM, files, [ADA, BEN])
        self.assertEqual(len(result["papers"]), 1)
        self.assertEqual(result["n_works"], 1)

    def test_papers_are_sorted_by_year_then_work_id(self):
        late = make_work("W9", others(2) + [ADA_SIGNED, BEN_SIGNED], title="Late", year=2022)
        early = make_work("W8", others(2) + [ADA_SIGNED, BEN_SIGNED], title="Early", year=2011)
        result = team_of(late, early)
        self.assertEqual([p["work_id"] for p in result["papers"]], ["W8", "W9"])

    def test_a_preprint_and_its_journal_paper_merge_across_the_member_files(self):
        journal = make_work("W11", others(2) + [ADA_SIGNED, BEN_SIGNED], title="Fern Spores Swell", doi="10.1000/f",
                            year=2016)
        preprint = make_work("W10", others(2) + [ADA_SIGNED, BEN_SIGNED], title="Fern spores swell",
                             wtype="preprint", venue="bioRxiv", doi="10.1101/933333", year=2015)
        ada_file, ben_file = member_works(journal, preprint)
        ada_file["papers"] = [p for p in ada_file["papers"] if p["work_id"] == "W10"]
        ben_file["papers"] = [p for p in ben_file["papers"] if p["work_id"] == "W11"]
        result = lo.team_works(TEAM, [ada_file, ben_file], [ADA, BEN])
        self.assertEqual([p["work_id"] for p in result["papers"]], ["W11"])
        self.assertEqual(result["papers"][0]["preprint_doi"], "10.1101/933333")
        self.assertEqual(result["merged"], [{"kept": "W11", "merged": "W10", "title": "Fern spores swell"}])

    def test_the_merges_of_the_members_carry_over_for_kept_papers_only(self):
        journal = make_work("W13", [ADA_SIGNED] + others(2) + [BEN_SIGNED], title="Moss Dries", doi="10.1000/m",
                            year=2016)
        preprint = make_work("W12", [ADA_SIGNED] + others(2) + [BEN_SIGNED], title="Moss dries", wtype="preprint",
                             venue="bioRxiv", doi="10.1101/944444", year=2015)
        lone = make_work("W15", others(2) + [ADA_SIGNED], title="Lone Rock", doi="10.1000/lr", year=2017)
        lone_preprint = make_work("W14", others(2) + [ADA_SIGNED], title="Lone rock", wtype="preprint",
                                  venue="bioRxiv", doi="10.1101/955555", year=2016)
        ada_file, ben_file = member_works(journal, preprint, lone, lone_preprint)
        self.assertEqual(sorted(m["kept"] for m in ada_file["merged"]), ["W13", "W15"])
        result = lo.team_works(TEAM, [ada_file, ben_file], [ADA, BEN])
        self.assertEqual([p["work_id"] for p in result["papers"]], ["W13"])
        self.assertEqual([(m["kept"], m["merged"]) for m in result["merged"]], [("W13", "W12")])

    def test_an_identifier_that_only_the_second_file_holds_is_filled_in(self):
        work = make_work("W16", others(2) + [ADA_SIGNED, BEN_SIGNED], title="Ferns", doi="10.1000/fe")
        ada_file, ben_file = member_works(work)
        ben_file["papers"][0]["pmcid"] = "PMC5000016"
        ben_file["papers"][0]["arxiv_id"] = "2101.00016"
        result = lo.team_works(TEAM, [ada_file, ben_file], [ADA, BEN])
        paper = result["papers"][0]
        self.assertEqual((paper["pmcid"], paper["arxiv_id"]), ("PMC5000016", "2101.00016"))

    def test_the_position_fields_describe_the_most_senior_member(self):
        work = make_work("W17", [ADA_SIGNED] + others(2) + [BEN_SIGNED], title="Ada first, Ben last")
        paper = team_of(work)["papers"][0]
        self.assertEqual((paper["position"], paper["author_index"], paper["n_authors"]), ("last", 3, 4))

    def test_co_senior_is_true_only_for_a_corresponding_author_outside_the_team(self):
        inside = make_work("W18", others(2) + [author("A1", ADA["orcid"], True), author("A2", BEN["orcid"], True)],
                           title="Both correspond")
        outside = make_work("W19", [author("A90", None, True)] + others(1, 91) + [ADA_SIGNED, BEN_SIGNED],
                            title="A third author corresponds")
        papers = {p["work_id"]: p for p in team_of(inside, outside)["papers"]}
        self.assertFalse(papers["W18"]["co_senior"])
        self.assertTrue(papers["W19"]["co_senior"])

    def test_the_member_files_stay_unchanged(self):
        work = make_work("W20", [ADA_SIGNED] + others(2) + [BEN_SIGNED], title="Unchanged")
        files = member_works(work)
        before = copy.deepcopy(files)
        lo.team_works(TEAM, files, [ADA, BEN])
        self.assertEqual(files, before)

    def test_a_team_of_three_needs_all_three_members(self):
        cal = {"id": "cal", "name": "Cal Moss", "orcid": "0000-0000-0000-0003", "openalex_ids": ["A3"],
               "ml_venues": False, "confirmed_by": "test"}
        three = dict(TEAM, id="trio", members=["ada", "ben", "cal"])
        work = make_work("W21", others(2) + [ADA_SIGNED, BEN_SIGNED], title="Two of three")
        files = member_works(work)
        result = lo.team_works(three, files, [ADA, BEN, cal])
        self.assertEqual(result["papers"], [])
        self.assertEqual(result["dropped"][0]["reason"], "not every member is in the author list")


class SharedWithTeamsTests(unittest.TestCase):
    def test_assign_shared_leaves_a_team_alone(self):
        work = make_work("W22", others(3) + [author("A1", ADA["orcid"], True), author("A2", BEN["orcid"], True)])
        team_paper = dict(classify(work)[0])
        discoveries = {"ada": {"papers": [classify(work)[0]], "dropped": []},
                       "ben": {"papers": [lo.classify(work, BEN, VENUES)[0]], "dropped": []},
                       "ada-ben": {"papers": [team_paper], "dropped": []}}
        lo.assign_shared(discoveries, [ADA, BEN, TEAM])
        self.assertEqual([r["work_id"] for r in discoveries["ben"]["papers"]], ["W22"])
        self.assertEqual(discoveries["ada"]["papers"], [])
        self.assertEqual([r["work_id"] for r in discoveries["ada-ben"]["papers"]], ["W22"])
        self.assertEqual(discoveries["ada-ben"]["dropped"], [])

    def test_a_team_never_owns_a_paper(self):
        record = classify(make_work("W23", [ADA_SIGNED] + others(2) + [BEN_SIGNED]))[0]
        self.assertEqual(lo.owner_of(record, [TEAM, ADA, BEN]), "ben")


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
                      doi="10.1101/922222", year=2015),
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
