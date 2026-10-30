"""OpenAlex: author candidates, the works of a person, and the discovery rules (spec section 7).

Discovery finds works by ORCID and by every OpenAlex author ID in the registry entry, because one
person can have two OpenAlex records. Each kept work becomes a record with one group: essay,
senior or first. Shared papers go to one person only (assign_shared).
"""
import re
import urllib.parse

from lab_text import normalize_doi, normalize_title
from lab_venues import is_essay_venue, tier_of

API = "https://api.openalex.org"
SELECT = "id,doi,title,display_name,publication_year,type,primary_location,authorships,ids,locations"
PER_PAGE = 200
KEEP_TYPES = frozenset(["article", "review", "preprint", "editorial", "letter", "conference-paper"])
ESSAY_TYPES = frozenset(["review", "editorial", "letter"])
MAX_ESSAY_AUTHORS = 3
CORRECTION = re.compile(r"^\s*(?:author correction|publisher correction|correction|corrigendum|erratum|"
                        r"retraction note|retraction|retracted|expression of concern)\s*(?::|\bto\b|\bfor\b|$)",
                        re.I)
# bioRxiv and medRxiv DOIs: prefix 10.1101, and 10.64898 for newer works (every 2026 work in the
# Stage A cache has it).
BIORXIV_DOI = re.compile(r"^10\.(?:1101|64898)/(?:\d{4}\.\d{2}\.\d{2}\.)?\d{6,}$")
RXIV_URL = re.compile(r"(?:bio|med)rxiv\.org/content/(?:early/\d{4}/\d{2}/\d{2}/)?"
                      r"(10\.(?:1101|64898)/(?:\d{4}\.\d{2}\.\d{2}\.)?\d{6,})")
ARXIV_URL = re.compile(r"arxiv\.org/(?:abs|pdf|html)/(\d{4}\.\d{4,5}|[a-z\-]+(?:\.[a-z]{2})?/\d{7})", re.I)
ARXIV_DOI = re.compile(r"^10\.48550/arxiv\.(.+)$")


def short_id(url):
    """Return the last part of an OpenAlex or ORCID URL, or "" for None."""
    return (url or "").rstrip("/").split("/")[-1]


def candidates(http, name):
    """Return the OpenAlex author records that match a name, for the orchestrator to confirm."""
    url = API + "/authors?search=" + urllib.parse.quote(name) + "&per-page=25"
    rows = []
    for record in http.get(url).json().get("results", []):
        rows.append({
            "id": short_id(record.get("id")),
            "orcid": short_id(record.get("orcid")) or None,
            "works_count": record.get("works_count", 0),
            "name": record.get("display_name", ""),
            "institutions": [i.get("display_name", "") for i in (record.get("last_known_institutions") or [])],
        })
    return rows


def _pages(http, filt):
    """Yield the works that match filt, one numbered page at a time.

    OpenAlex needs an API key for cursor paging past the first page (checked on 2026-10-29).
    Numbered pages need no key and reach 10,000 works, far more than one person has.
    """
    page = 1
    while True:
        url = API + "/works?filter=" + filt + "&per-page=" + str(PER_PAGE) + "&select=" + SELECT + "&page=" + str(page)
        data = http.get(url).json()
        results = data.get("results") or []
        for work in results:
            yield work
        count = (data.get("meta") or {}).get("count") or 0
        if not results or page * PER_PAGE >= count:
            break
        page += 1


def fetch_works(http, person):
    """Return every work of the person by ORCID and by OpenAlex ID, each work once."""
    seen, works = set(), []
    filters = ["author.orcid:" + person["orcid"]] + ["author.id:" + a for a in person["openalex_ids"]]
    for filt in filters:
        for work in _pages(http, filt):
            wid = short_id(work.get("id"))
            if wid and wid not in seen:
                seen.add(wid)
                works.append(work)
    return works


def authorship_brief(work):
    """Return one dict per author, in order: OpenAlex id, ORCID and the corresponding flag."""
    brief = []
    for entry in work.get("authorships") or []:
        entry = entry or {}
        person = entry.get("author") or {}
        brief.append({"id": short_id(person.get("id")), "orcid": short_id(person.get("orcid")) or None,
                      "corresponding": bool(entry.get("is_corresponding"))})
    return brief


def _is_person(entry, person):
    return (entry["orcid"] is not None and entry["orcid"] == person["orcid"]) or entry["id"] in person["openalex_ids"]


def person_index(brief, person):
    for index, entry in enumerate(brief):
        if _is_person(entry, person):
            return index
    return None


def position_name(index, n):
    if n == 1:
        return "sole"
    if index == 0:
        return "first"
    if index == n - 1:
        return "last"
    return "middle"


def identifiers(work):
    """Return (doi, pmcid, preprint_doi, arxiv_id) of a work. Each one may be None."""
    ids = work.get("ids") or {}
    digits = re.sub(r"\D", "", short_id(ids.get("pmcid")))
    pmcid = "PMC" + digits if digits else None
    doi = normalize_doi(work.get("doi"))
    preprint_doi = doi if doi and BIORXIV_DOI.match(doi) else None
    match = ARXIV_DOI.match(doi or "")
    arxiv_id = match.group(1) if match else None
    for location in work.get("locations") or []:
        location = location or {}
        # OpenAlex gives a bioRxiv location a landing page that is the DOI resolver URL of the preprint.
        source_name = ((location.get("source") or {}).get("display_name") or "").lower()
        if not preprint_doi and ("biorxiv" in source_name or "medrxiv" in source_name):
            landing_doi = normalize_doi(location.get("landing_page_url"))
            if landing_doi and BIORXIV_DOI.match(landing_doi):
                preprint_doi = landing_doi
        for url in (location.get("landing_page_url") or "", location.get("pdf_url") or ""):
            found = RXIV_URL.search(url)
            if found and not preprint_doi:
                preprint_doi = found.group(1).lower()
            found = ARXIV_URL.search(url)
            if found and not arxiv_id:
                arxiv_id = found.group(1).lower()
    return doi, pmcid, preprint_doi, arxiv_id


def classify(work, person, venues):
    """Return (record, None) for a kept work, or (None, reason) for a dropped work."""
    brief = authorship_brief(work)
    index = person_index(brief, person)
    if index is None:
        return None, "person not in the author list"
    wtype = work.get("type") or ""
    if wtype not in KEEP_TYPES:
        return None, "type " + (wtype or "missing")
    title = " ".join((work.get("title") or work.get("display_name") or "").split())
    if not title:
        return None, "no title"
    if CORRECTION.match(title):
        return None, "correction or retraction notice"
    venue = ((work.get("primary_location") or {}).get("source") or {}).get("display_name")
    n = len(brief)
    position = position_name(index, n)
    corresponding = brief[index]["corresponding"]
    if (wtype in ESSAY_TYPES or is_essay_venue(venue, venues)) and n <= MAX_ESSAY_AUTHORS:
        group = "essay"
    elif position in ("last", "sole") or (corresponding and position != "first"):
        group = "senior"
    elif position == "first":
        group = "first"
    else:
        return None, "middle author"
    doi, pmcid, preprint_doi, arxiv_id = identifiers(work)
    others_corresponding = any(e["corresponding"] for i, e in enumerate(brief) if i != index)
    record = {
        "work_id": short_id(work.get("id")), "doi": doi, "title": title,
        "year": work.get("publication_year"), "type": wtype, "venue": venue,
        "tier": tier_of(venue, venues, person.get("ml_venues", False)),
        "group": group, "position": position, "author_index": index, "n_authors": n,
        "is_corresponding": corresponding, "co_senior": group == "senior" and others_corresponding,
        "pmcid": pmcid, "preprint_doi": preprint_doi, "arxiv_id": arxiv_id, "authors": brief,
    }
    return record, None


def _merge_key(record):
    return (record["type"] == "preprint", record["pmcid"] is None, record["year"] or 9999, record["work_id"])


def merge_preprints(records):
    """Join records with the same normalized title. Return (kept, merged).

    The kept record is a journal record when one exists. It takes the preprint DOI, arXiv ID and
    PMC ID of the records it absorbs when it lacks them. kept is sorted by year, then work id.
    """
    by_title = {}
    for record in records:
        by_title.setdefault(normalize_title(record["title"]), []).append(record)
    kept, merged = [], []
    for key in sorted(by_title):
        group = sorted(by_title[key], key=_merge_key)
        head = group[0]
        for other in group[1:]:
            for field in ("preprint_doi", "arxiv_id", "pmcid"):
                if not head.get(field) and other.get(field):
                    head[field] = other[field]
            merged.append({"kept": head["work_id"], "merged": other["work_id"], "title": other["title"]})
        kept.append(head)
    kept.sort(key=lambda r: (r["year"] or 0, r["work_id"]))
    return kept, merged


def _rank(brief, index):
    position = position_name(index, len(brief))
    if position in ("last", "sole"):
        return 0
    if brief[index]["corresponding"] and position != "first":
        return 1
    if position == "first":
        return 2
    return 3


def owner_of(record, people):
    """Return the id of the person who may draw the paper: last author, then a corresponding
    author, then the first author. Registry order breaks a tie."""
    best = None
    for order, person in enumerate(people):
        index = person_index(record["authors"], person)
        if index is None:
            continue
        key = (_rank(record["authors"], index), order)
        if best is None or key < best[0]:
            best = (key, person["id"])
    return best[1] if best else None


def assign_shared(discoveries, people):
    """Move each shared paper to the dropped list of every person except its owner.

    discoveries maps a person id to a discovery dict. The function changes it and returns it.
    """
    for person in people:
        discovery = discoveries[person["id"]]
        keep = []
        for record in discovery["papers"]:
            owner = owner_of(record, people)
            if owner == person["id"]:
                keep.append(record)
            else:
                discovery["dropped"].append({"work_id": record["work_id"], "title": record["title"][:200],
                                             "type": record["type"], "reason": "shared: drawn by " + str(owner)})
        discovery["papers"] = keep
    return discoveries


def discover(http, person, venues):
    """Return the discovery of one person: kept papers, dropped works with reasons, merges."""
    works = fetch_works(http, person)
    kept, dropped = [], []
    for work in works:
        record, reason = classify(work, person, venues)
        if record:
            kept.append(record)
        else:
            dropped.append({"work_id": short_id(work.get("id")),
                            "title": (work.get("title") or work.get("display_name") or "")[:200],
                            "type": work.get("type"), "reason": reason})
    papers, merged = merge_preprints(kept)
    dropped.sort(key=lambda d: d["work_id"])
    return {"schema": 1, "person": person["id"], "orcid": person["orcid"],
            "venues_version": venues.get("version"), "n_works": len(works),
            "papers": papers, "dropped": dropped, "merged": merged}
