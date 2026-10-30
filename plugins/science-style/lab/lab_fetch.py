"""Fetch the full text of each sampled paper (spec section 9) and write its paper file.

The routes, in order: NCBI efetch for a PMC ID, Europe PMC fullTextXML, the bioRxiv or medRxiv
JATS file, and arXiv HTML. A route succeeds when the reader finds at least 600 words of body text
outside Methods. When every route fails, the sample replaces the paper (lab_sample.replace). The
manifest is saved after each paper, so an interrupted run resumes where it stopped.
"""
import re
import urllib.parse

from lab_arxiv import read_arxiv_html
from lab_http import FetchError
from lab_jats import ReaderError, read_jats
from lab_paths import paper_path, write_json
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
META_FIELDS = ("work_id", "doi", "title", "year", "venue", "tier", "group", "co_senior")


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
    for server in ("biorxiv", "medrxiv"):
        try:
            data = http.get(RXIV_DETAILS.format(server, doi)).json()
        except (FetchError, ValueError):
            continue
        collection = data.get("collection") or []
        if not collection:
            continue
        jats_url = collection[-1].get("jatsxml")
        if not jats_url:
            return None, "{} lists no JATS file for {}".format(server, doi)
        try:
            body = http.get(jats_url).body
        except FetchError as err:
            return None, str(err)
        return _try_reader(read_jats, body, dict(base, route=server, source_url=jats_url, text_version="preprint"))
    return None, "the bioRxiv and medRxiv APIs do not know {}".format(doi)


def try_routes(http, paper, person_id):
    """Return (paper_file, None) from the first route that works, or (None, reasons).

    Raise FetchError when a Europe PMC search failed and no route works. The paper then stays
    "chosen", because the failed search could have found a PMC ID or a preprint.
    """
    reasons = []
    info = epmc_lookup(http, paper)
    if info["failed"]:
        reasons.append("europepmc lookup: failed")
    base = {field: paper.get(field) for field in META_FIELDS}
    base["person"] = person_id
    if info["pmcid"]:
        number = re.sub(r"\D", "", info["pmcid"])
        routes = (("ncbi-pmc", NCBI_EFETCH + number, None), ("europepmc", EPMC_FULLTEXT.format("PMC" + number), 1))
        for route, url, retries in routes:
            try:
                body = http.get(url, retries=retries).body
            except FetchError as err:
                reasons.append("{}: {}".format(route, err))
                continue
            result, why = _try_reader(read_jats, body, dict(base, route=route, source_url=url, text_version=None))
            if result:
                result["text_version"] = "accepted" if (info["auth_man"] or result.get("jats_manuscript")) else "published"
                return result, None
            reasons.append("{}: {}".format(route, why))
    else:
        reasons.append("pmc: no PMC ID")
    doi = info["preprint_doi"]
    if not doi and paper.get("doi") and BIORXIV_DOI.match(paper["doi"]):
        doi = paper["doi"]
    if doi:
        result, why = _rxiv(http, doi, base)
        if result:
            return result, None
        reasons.append("preprint: " + why)
    else:
        reasons.append("preprint: no bioRxiv DOI")
    if paper.get("arxiv_id"):
        url = ARXIV_HTML.format(paper["arxiv_id"])
        try:
            body = http.get(url).body
        except FetchError as err:
            reasons.append("arxiv: {}".format(err))
        else:
            result, why = _try_reader(read_arxiv_html, body,
                                      dict(base, route="arxiv-html", source_url=url, text_version="arxiv"))
            if result:
                return result, None
            reasons.append("arxiv: " + why)
    else:
        reasons.append("arxiv: no arXiv ID")
    if info["failed"]:
        raise FetchError("europepmc", None, "Europe PMC lookup failed; paper left as chosen")
    return None, reasons


def fetch_person(http, manifest, manifest_path, data, lookup, only=None, log=None):
    """Fetch every paper with the status "chosen" and save the manifest after each one.

    lookup maps a work id to its record, for replacements. only, when given, is a set of work ids;
    a replacement of one of them joins the set.
    """
    log = log or (lambda message: None)
    counts = {"fetched": 0, "replaced": 0}
    while True:
        pending = [p for p in manifest["papers"]
                   if p["status"] == "chosen" and (only is None or p["work_id"] in only)]
        if not pending:
            break
        paper = pending[0]
        result, reasons = try_routes(http, paper, manifest["person"])
        if result:
            write_json(paper_path(data, manifest["person"], paper["work_id"]), result)
            paper.update({"status": "fetched", "route": result["route"], "text_version": result["text_version"],
                          "source_url": result["source_url"]})
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
    return counts


def renormalize_person(http, manifest, data):
    """Rebuild the paper file of every fetched paper from the cache. Return the failures."""
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
        result["text_version"] = paper["text_version"]
        write_json(paper_path(data, manifest["person"], paper["work_id"]), result)
    return failures
