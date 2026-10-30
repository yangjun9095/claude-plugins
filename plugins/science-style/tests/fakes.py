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
