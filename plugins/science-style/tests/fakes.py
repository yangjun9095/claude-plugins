"""Fakes for the tests of the style lab. All people, papers and text here are made up."""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "lab"))

import lab_http  # noqa: E402

ADA = {"id": "ada", "name": "Ada Quill", "orcid": "0000-0000-0000-0001", "openalex_ids": ["A1", "A11"],
       "ml_venues": False, "confirmed_by": "test"}
BEN = {"id": "ben", "name": "Ben Rowan", "orcid": "0000-0000-0000-0002", "openalex_ids": ["A2"],
       "ml_venues": True, "confirmed_by": "test"}


class FakeResponse(object):
    def __init__(self, url, body):
        self.url = url
        self.status = 200
        self.from_cache = False
        self.body = body if isinstance(body, bytes) else body.encode("utf-8")

    def json(self):
        return json.loads(self.body.decode("utf-8"))


class FakeHttp(object):
    """Answers a URL from routes, a list of (key, answer). The first matching route wins.

    A key is a string or a tuple of strings that must all occur in the URL. An answer is bytes, a
    string, a dict or list (sent as JSON), or an exception to raise. A URL with no route raises
    FetchError with status 404.
    """

    def __init__(self, routes=None):
        self.routes = list(routes or [])
        self.calls = []

    def add(self, key, answer):
        self.routes.append((key, answer))
        return self

    def get(self, url, retries=None):
        self.calls.append((url, retries))
        for key, answer in self.routes:
            keys = key if isinstance(key, tuple) else (key,)
            if all(k in url for k in keys):
                if isinstance(answer, Exception):
                    raise answer
                if isinstance(answer, (dict, list)):
                    answer = json.dumps(answer)
                return FakeResponse(url, answer)
        raise lab_http.FetchError(url, 404, "no fake route")


def author(aid, orcid=None, corresponding=False):
    return {"author": {"id": "https://openalex.org/" + aid,
                       "orcid": ("https://orcid.org/" + orcid) if orcid else None,
                       "display_name": "Author " + aid},
            "is_corresponding": corresponding}


def make_work(wid, authors, title="Fern spores swell in water", wtype="article", year=2015,
              venue="Current Biology", doi=None, pmcid=None, locations=None):
    return {
        "id": "https://openalex.org/" + wid,
        "doi": ("https://doi.org/" + doi) if doi else None,
        "title": title,
        "display_name": title,
        "publication_year": year,
        "type": wtype,
        "primary_location": {"source": {"display_name": venue}} if venue else {"source": None},
        "authorships": authors,
        "ids": {"pmcid": ("https://www.ncbi.nlm.nih.gov/pmc/articles/" + pmcid[3:]) if pmcid else None},
        "locations": locations or [],
    }


import urllib.error  # noqa: E402

PARAGRAPH = "Spores swell in water and split along a seam while the coat dries under light."


def jats_body(n_words, manuscript=False, doi=None, article_type="research-article"):
    """Return a JATS document whose introduction has at least n_words words."""
    paragraphs = "".join("<p>{}</p>".format(PARAGRAPH) for _ in range(-(-n_words // 15)))
    mid = '<article-id pub-id-type="manuscript">NIHMS000001</article-id>' if manuscript else ""
    if doi:
        mid += '<article-id pub-id-type="doi">{}</article-id>'.format(doi)
    return ('<?xml version="1.0" encoding="UTF-8"?><pmc-articleset><article article-type="{}">'
            '<front><article-meta>{}<abstract><p>Spores swell.</p></abstract></article-meta></front>'
            '<body><sec><title>Introduction</title>{}</sec><sec><title>Results</title><p>Spores split.</p></sec>'
            '</body></article></pmc-articleset>').format(article_type, mid, paragraphs).encode("utf-8")


def arxiv_body(n_words):
    """Return a LaTeXML page whose introduction has at least n_words words."""
    paragraphs = "".join('<div class="ltx_para"><p class="ltx_p">{}</p></div>'.format(PARAGRAPH)
                         for _ in range(-(-n_words // 15)))
    return ('<html><body><article class="ltx_document"><div class="ltx_abstract"><p class="ltx_p">Nets sort spores.'
            '</p></div><section class="ltx_section"><h2 class="ltx_title">1 Introduction</h2>{}</section>'
            '</article></body></html>').format(paragraphs).encode("utf-8")


def epmc_result(doi=None, pmcid=None, auth_man="N", title=None):
    record = {"authMan": auth_man}
    if doi:
        record["doi"] = doi
    if pmcid:
        record["pmcid"] = pmcid
    if title:
        record["title"] = title
    return {"resultList": {"result": [record]}}


class MapOpener(object):
    """An opener for lab_http.Http. It answers from routes like FakeHttp, and a URL with no route
    gets HTTP 404."""

    def __init__(self, routes):
        self.routes = list(routes)
        self.calls = []

    def __call__(self, url, headers, timeout):
        self.calls.append(url)
        for key, answer in self.routes:
            keys = key if isinstance(key, tuple) else (key,)
            if all(k in url for k in keys):
                if isinstance(answer, Exception):
                    raise answer
                if isinstance(answer, (dict, list)):
                    answer = json.dumps(answer)
                return 200, answer if isinstance(answer, bytes) else answer.encode("utf-8")
        raise urllib.error.HTTPError(url, 404, "not found", {}, None)


import lab_text  # noqa: E402


def make_paper_file(work_id, person, paragraphs, group="senior", tier="high"):
    """Return a finished paper file with one introduction section."""
    paper = lab_text.new_paper({"work_id": work_id, "person": person, "group": group, "tier": tier,
                                "doi": "10.0000/" + work_id.lower(), "title": "Paper " + work_id})
    paper["sections"] = [{"heading": "Introduction", "kind": "intro", "paragraphs": list(paragraphs),
                          "subsections": []}]
    return lab_text.finish_paper(paper)


def make_extraction(paper, checklist, group="senior", attempt=1, run="main"):
    """Return a valid extraction whose every quote is the first sentence of the paper."""
    first = next(p for _, _, p in lab_text.iter_paragraphs(paper))
    sentence = lab_text.split_sentences(first)[0]
    answers = {}
    for item in checklist["items"]:
        if "groups" in item and group not in item["groups"]:
            answers[item["id"]] = {"not_applicable": True}
            continue
        answer = {}
        for name, spec in item["fields"].items():
            kind = spec["type"]
            if kind == "enum":
                answer[name] = spec["values"][0]
            elif kind == "enum_list":
                answer[name] = [spec["values"][0]]
            elif kind == "objects":
                entry = {key: values[0] for key, values in spec["keys"].items()}
                entry["quote"] = sentence
                answer[name] = [entry]
            elif kind == "quote":
                answer[name] = sentence
            elif kind == "quotes":
                answer[name] = [sentence]
            elif kind == "text":
                answer[name] = "The essay argues one point."
            elif kind == "texts":
                answer[name] = ["The first section asks how spores swell."]
            elif kind == "int":
                answer[name] = 1
            elif kind == "strings":
                answer[name] = ["A heading"]
        answers[item["id"]] = answer
    return {"schema": 1, "checklist_version": checklist["version"], "prompt_version": 1,
            "paper_sha256": paper["sha256"], "work_id": paper["work_id"], "person": paper["person"],
            "attempt": attempt, "run": run, "answers": answers}
