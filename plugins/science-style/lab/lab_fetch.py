"""Fetch the full text of each sampled paper (spec section 9) and write its paper file.

The routes, in order: NCBI efetch for a PMC ID, Europe PMC fullTextXML, the bioRxiv or medRxiv
JATS file, and arXiv HTML. A route succeeds when the reader finds at least 600 words of body text
outside Methods. When every route fails for a permanent reason, the sample replaces the paper
(lab_sample.replace). When a failure may pass (is_transient), the paper stays "chosen", the fetch
goes on with the next paper and ends with an error, so a later run tries the paper again. The
manifest is saved after each paper, so an interrupted run resumes where it stopped.
"""
import re
import urllib.parse

from lab_arxiv import read_arxiv_html
from lab_http import FetchError
from lab_jats import ReaderError, read_jats
from lab_paths import paper_path, read_json, write_json
from lab_sample import count_papers, replace
from lab_text import body_words, normalize_doi, normalize_title

EPMC_SEARCH = ("https://www.ebi.ac.uk/europepmc/webservices/rest/search"
               "?format=json&resultType=core&pageSize=5&query=")
NCBI_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pmc&id="
EPMC_FULLTEXT = "https://www.ebi.ac.uk/europepmc/webservices/rest/{}/fullTextXML"
RXIV_DETAILS = "https://api.biorxiv.org/details/{}/{}"
ARXIV_HTML = "https://arxiv.org/html/{}"
MIN_BODY_WORDS = 600
BIORXIV_DOI = re.compile(r"^10\.1101/(?:\d{4}\.\d{2}\.\d{2}\.)?\d{6,}$")
DATED_RXIV_DOI = re.compile(r"^10\.1101/\d{4}\.\d{2}\.\d{2}\.\d{6,}$")
META_FIELDS = ("work_id", "doi", "title", "year", "venue", "tier", "group", "co_senior")
RXIV_HOSTS = frozenset(["www.biorxiv.org", "www.medrxiv.org", "api.biorxiv.org", "api.medrxiv.org"])
RXIV_ROUTES = ("biorxiv", "medrxiv")


class Deferred(FetchError):
    """No route worked, and at least one route failed for a reason that may pass. The paper stays
    "chosen". reasons lists the failure of each route."""

    def __init__(self, subject, reasons):
        Exception.__init__(self, "{}: deferred after a temporary failure: {}".format(subject, "; ".join(reasons)))
        self.url = subject
        self.status = None
        self.reasons = list(reasons)


def is_transient(err):
    """Return True when a FetchError may pass on a later run: a network error or time-out (status
    None), 429, a 5xx status, or 403 from a bioRxiv or medRxiv host (their firewall answers 403
    when it limits the rate)."""
    status = err.status
    if status is None or status == 429 or 500 <= status <= 599:
        return True
    return status == 403 and urllib.parse.urlparse(err.url or "").netloc in RXIV_HOSTS


def pmc_preprint_doi(paper, article_doi=None):
    """Return the dated bioRxiv or medRxiv DOI of a PMC text, or None.

    PMC holds some preprints. The JATS article DOI, or the DOI of the paper, is then a dated
    preprint DOI. The OpenAlex type of the work plays no part.
    """
    for doi in (normalize_doi(article_doi), normalize_doi(paper.get("doi"))):
        if doi and DATED_RXIV_DOI.match(doi):
            return doi
    return None


def derive_text_doi(route, paper, article_doi=None):
    """Return the DOI of the text that a route read, or None.

    arxiv-html: 10.48550/arxiv.<arXiv ID> in lower case. biorxiv and medrxiv: the preprint DOI.
    ncbi-pmc and europepmc: a dated preprint DOI (pmc_preprint_doi), else the DOI of the paper,
    else the JATS article DOI.
    """
    if route == "arxiv-html":
        return "10.48550/arxiv." + paper["arxiv_id"].lower() if paper.get("arxiv_id") else None
    if route in RXIV_ROUTES:
        own = normalize_doi(paper.get("doi"))
        return normalize_doi(paper.get("preprint_doi")) or (own if own and BIORXIV_DOI.match(own) else None)
    return pmc_preprint_doi(paper, article_doi) or normalize_doi(paper.get("doi")) or normalize_doi(article_doi)


def epmc_query(http, query):
    """Return the results of a Europe PMC search: [] for no hits, None when the request or the JSON fails."""
    try:
        data = http.get(EPMC_SEARCH + urllib.parse.quote(query)).json()
    except (FetchError, ValueError):
        return None
    return (data.get("resultList") or {}).get("result") or []


def epmc_lookup(http, paper):
    """Return the PMC ID, the author-manuscript flag and a preprint DOI from the Europe PMC search.

    The key "failed" is True when a search request failed. The other keys then hold what the other
    searches found, and a missing value does not show that Europe PMC has no record.
    """
    info = {"pmcid": paper.get("pmcid"), "auth_man": False, "preprint_doi": paper.get("preprint_doi"),
            "failed": False}

    def search(query):
        hits = epmc_query(http, query)
        if hits is None:
            info["failed"] = True
            return []
        return hits

    results = []
    if paper.get("doi"):
        results = [r for r in search('DOI:"{}"'.format(paper["doi"])) if normalize_doi(r.get("doi")) == paper["doi"]]
    if not results and info["pmcid"]:
        results = [r for r in search("PMCID:" + info["pmcid"]) if r.get("pmcid") == info["pmcid"]]
    if results:
        if results[0].get("pmcid") and not info["pmcid"]:
            info["pmcid"] = results[0]["pmcid"]
        info["auth_man"] = results[0].get("authMan") == "Y"
    if not info["preprint_doi"] and paper.get("title"):
        title = " ".join(re.sub(r"[^\w\s]", " ", paper["title"]).split())
        for record in search('SRC:PPR AND TITLE:"{}"'.format(title)):
            doi = normalize_doi(record.get("doi"))
            if doi and BIORXIV_DOI.match(doi) and normalize_title(record.get("title")) == normalize_title(paper["title"]):
                info["preprint_doi"] = doi
                break
    return info


def _try_reader(reader, body, meta):
    try:
        result = reader(body, meta)
    except ReaderError as err:
        return None, "reader: {}".format(err)
    count = body_words(result)
    if count < MIN_BODY_WORDS:
        return None, "body has {} words, fewer than {}".format(count, MIN_BODY_WORDS)
    return result, None


def _rxiv(http, doi, base):
    """Return (paper_file, None, False) from the bioRxiv or medRxiv JATS file, or (None, reason,
    transient).

    transient is True when an API request or the JATS download failed for a reason that may pass,
    or when an API answer is not JSON. Only an answer with an empty collection from each server
    shows that neither server knows the DOI.
    """
    failures, transient = [], False
    for server in ("biorxiv", "medrxiv"):
        try:
            data = http.get(RXIV_DETAILS.format(server, doi)).json()
        except FetchError as err:
            failures.append("{} API: {}".format(server, err))
            transient = transient or is_transient(err)
            continue
        except ValueError:
            failures.append("{} API: the answer is not JSON".format(server))
            transient = True
            continue
        collection = data.get("collection") or []
        if not collection:
            continue
        jats_url = collection[-1].get("jatsxml")
        if not jats_url:
            return None, "{} lists no JATS file for {}".format(server, doi), False
        try:
            body = http.get(jats_url).body
        except FetchError as err:
            return None, str(err), is_transient(err)
        result, why = _try_reader(read_jats, body, dict(base, route=server, source_url=jats_url,
                                                        text_version="preprint", text_doi=doi))
        return result, why, False
    if failures:
        return None, "; ".join(failures), transient
    return None, "the bioRxiv and medRxiv APIs do not know {}".format(doi), False


def try_routes(http, paper, person_id):
    """Return (paper_file, None) from the first route that works, or (None, reasons) when every
    route failed for a permanent reason.

    Raise Deferred when no route works and a route failed for a reason that may pass, or a Europe
    PMC search failed (it could have found a PMC ID or a preprint). A 500 from the Europe PMC
    fullTextXML route is permanent: Europe PMC answers 500 for an author manuscript without XML.
    """
    reasons, transient = [], []

    def fail(reason, temporary=False):
        reasons.append(reason)
        if temporary:
            transient.append(reason)

    info = epmc_lookup(http, paper)
    if info["failed"]:
        fail("europepmc lookup: failed", True)
    base = {field: paper.get(field) for field in META_FIELDS}
    base["person"] = person_id
    if info["pmcid"]:
        number = re.sub(r"\D", "", info["pmcid"])
        routes = (("ncbi-pmc", NCBI_EFETCH + number, None), ("europepmc", EPMC_FULLTEXT.format("PMC" + number), 1))
        for route, url, retries in routes:
            try:
                body = http.get(url, retries=retries).body
            except FetchError as err:
                fail("{}: {}".format(route, err),
                     is_transient(err) and not (route == "europepmc" and err.status == 500))
                continue
            result, why = _try_reader(read_jats, body, dict(base, route=route, source_url=url, text_version=None))
            if result:
                if pmc_preprint_doi(paper, result.get("article_doi")):
                    result["text_version"] = "preprint"
                elif info["auth_man"] or result.get("jats_manuscript"):
                    result["text_version"] = "accepted"
                else:
                    result["text_version"] = "published"
                result["text_doi"] = derive_text_doi(route, paper, result.get("article_doi"))
                return result, None
            fail("{}: {}".format(route, why))
    else:
        fail("pmc: no PMC ID")
    doi = info["preprint_doi"]
    if not doi and paper.get("doi") and BIORXIV_DOI.match(paper["doi"]):
        doi = paper["doi"]
    if doi:
        result, why, temporary = _rxiv(http, doi, base)
        if result:
            return result, None
        fail("preprint: " + why, temporary)
    else:
        fail("preprint: no bioRxiv DOI")
    if paper.get("arxiv_id"):
        url = ARXIV_HTML.format(paper["arxiv_id"])
        try:
            body = http.get(url).body
        except FetchError as err:
            fail("arxiv: {}".format(err), is_transient(err))
        else:
            result, why = _try_reader(read_arxiv_html, body,
                                      dict(base, route="arxiv-html", source_url=url, text_version="arxiv",
                                           text_doi=derive_text_doi("arxiv-html", paper)))
            if result:
                return result, None
            fail("arxiv: " + why)
    else:
        fail("arxiv: no arXiv ID")
    if transient:
        raise Deferred(paper.get("work_id"), reasons)
    return None, reasons


def fetch_person(http, manifest, manifest_path, data, lookup, only=None, log=None):
    """Fetch every paper with the status "chosen" and save the manifest after each one.

    lookup maps a work id to its record, for replacements. only, when given, is a set of work ids;
    a replacement of one of them joins the set. A deferred paper stays "chosen" and the loop goes
    on with the next paper. At the end, raise Deferred that names the person and every deferred
    paper, so the command exits with 1 and a later run tries those papers again.
    """
    log = log or (lambda message: None)
    counts = {"fetched": 0, "replaced": 0}
    deferred = []
    while True:
        pending = [p for p in manifest["papers"]
                   if p["status"] == "chosen" and p["work_id"] not in {w for w, _ in deferred}
                   and (only is None or p["work_id"] in only)]
        if not pending:
            break
        paper = pending[0]
        try:
            result, reasons = try_routes(http, paper, manifest["person"])
        except Deferred as err:
            deferred.append((paper["work_id"], "; ".join(err.reasons)))
            log("deferred {}: {}".format(paper["work_id"], "; ".join(err.reasons)))
            continue
        if result:
            write_json(paper_path(data, manifest["person"], paper["work_id"]), result)
            paper.update({"status": "fetched", "route": result["route"], "text_version": result["text_version"],
                          "text_doi": result["text_doi"], "source_url": result["source_url"]})
            if result["text_version"] == "preprint" and not paper.get("preprint_doi"):
                paper["preprint_doi"] = result["text_doi"]
            counts["fetched"] += 1
            log("fetched {} by {}".format(paper["work_id"], result["route"]))
        else:
            new = replace(manifest, paper["work_id"], "no open full text: " + "; ".join(reasons), lookup)
            counts["replaced"] += 1
            if only is not None and new:
                only.add(new)
            log("replaced {} by {}".format(paper["work_id"], new))
        manifest["n_papers"] = count_papers(manifest)
        write_json(manifest_path, manifest)
    if deferred:
        raise Deferred(manifest["person"], ["{} ({})".format(w, why) for w, why in deferred])
    return counts


def _old_text_doi(path):
    """Return the text_doi of an existing paper file, or None."""
    try:
        return read_json(path).get("text_doi")
    except (OSError, ValueError, AttributeError):
        return None


def renormalize_person(http, manifest, data):
    """Rebuild the paper file of every fetched paper from the cache. Return the failures.

    The text_doi comes from the manifest paper, else from the old paper file, else derive_text_doi.
    """
    failures = []
    for paper in manifest["papers"]:
        if paper["status"] != "fetched":
            continue
        reader = read_arxiv_html if paper["route"] == "arxiv-html" else read_jats
        meta = {field: paper.get(field) for field in META_FIELDS}
        meta.update({"person": manifest["person"], "route": paper["route"], "source_url": paper["source_url"],
                     "text_version": paper["text_version"]})
        try:
            result = reader(http.get(paper["source_url"]).body, meta)
        except (FetchError, ReaderError) as err:
            failures.append({"work_id": paper["work_id"], "error": str(err)})
            continue
        path = paper_path(data, manifest["person"], paper["work_id"])
        result["text_version"] = paper["text_version"]
        result["text_doi"] = (paper.get("text_doi") or _old_text_doi(path)
                              or derive_text_doi(paper["route"], paper, result.get("article_doi")))
        write_json(path, result)
    return failures
