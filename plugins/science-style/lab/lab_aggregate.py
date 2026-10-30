"""Synthesis by script (spec section 13): counts, the profile data, stability, the digest and the
quality report.

A profile counts papers, never sentences: each paper adds one to each closed value it holds. Only
papers whose check status is "ok" count. Quotes in a profile have at most 25 words, passed the
quote check, and carry the DOI of the text they come from (citation_doi): a quote read from
preprint text cites the preprint DOI, and a quote read from arXiv HTML cites the arXiv DOI.
"""
import os
from collections import Counter

from lab_checklist import (CLOSED_TYPES, NOT_APPLICABLE, PROMPT_VERSION, closed_items, item_agreement, iter_quotes,
                           validate_extraction)
from lab_paths import extraction_path, read_json
from lab_text import normalize_doi, words

QUOTE_LIMIT = 25
STABLE_THRESHOLD = 0.7


def quote_doi(meta):
    if meta.get("doi"):
        return meta["doi"]
    if meta.get("arxiv_id"):
        return "10.48550/arxiv." + meta["arxiv_id"]
    return None


def citation_doi(meta):
    """Return the DOI that a quote from this paper cites: the text_doi that the fetch step wrote.

    A manifest from before text_doi has none. Then an arXiv HTML text cites 10.48550/arxiv.<id>,
    a preprint text with a preprint DOI cites that DOI, and any other text cites quote_doi(meta).
    """
    text_doi = normalize_doi(meta.get("text_doi"))
    if text_doi:
        return text_doi
    if meta.get("route") == "arxiv-html" and meta.get("arxiv_id"):
        return "10.48550/arxiv." + meta["arxiv_id"].lower()
    if meta.get("text_version") == "preprint":
        preprint = normalize_doi(meta.get("preprint_doi"))
        if preprint:
            return preprint
    return quote_doi(meta)


def _new_counter(ordered):
    counter = {"n": 0, "all": Counter(), "by_group": {}, "by_tier": {}, "n_by_group": Counter(),
               "n_by_tier": Counter()}
    if ordered:
        counter["first"] = Counter()
        counter["last"] = Counter()
    return counter


def _add(counter, meta, values, ordered=False):
    counter["n"] += 1
    counter["n_by_group"][meta["group"]] += 1
    counter["n_by_tier"][meta["tier"]] += 1
    present = sorted({v for v in values if v is not None})
    counter["all"].update(present)
    counter["by_group"].setdefault(meta["group"], Counter()).update(present)
    counter["by_tier"].setdefault(meta["tier"], Counter()).update(present)
    if ordered and values:
        counter["first"][values[0]] += 1
        counter["last"][values[-1]] += 1


def _plain(counter):
    return dict(sorted(counter.items()))


def _finish(counter):
    out = {"n": counter["n"], "all": _plain(counter["all"]),
           "by_group": {g: _plain(c) for g, c in sorted(counter["by_group"].items())},
           "by_tier": {t: _plain(c) for t, c in sorted(counter["by_tier"].items())},
           "n_by_group": _plain(counter["n_by_group"]), "n_by_tier": _plain(counter["n_by_tier"])}
    if "first" in counter:
        out["first"] = _plain(counter["first"])
        out["last"] = _plain(counter["last"])
    return out


def count_answers(extractions, papers_meta, checklist):
    """Return, for each item with closed fields, the paper counts of every value."""
    counts = {}
    for item in checklist["items"]:
        fields = {}
        for name, spec in item["fields"].items():
            if spec["type"] == "objects":
                for key in sorted(spec["keys"]):
                    fields[name + "." + key] = _new_counter(False)
            elif spec["type"] in ("enum", "enum_list"):
                fields[name] = _new_counter(spec["type"] == "enum_list")
        if not fields:
            continue
        for wid in sorted(extractions):
            answer = extractions[wid]["answers"].get(item["id"])
            if not isinstance(answer, dict) or answer == NOT_APPLICABLE:
                continue
            meta = papers_meta[wid]
            for name, spec in item["fields"].items():
                value = answer.get(name)
                if spec["type"] == "enum":
                    _add(fields[name], meta, [value])
                elif spec["type"] == "enum_list":
                    _add(fields[name], meta, value or [], ordered=True)
                elif spec["type"] == "objects":
                    for key in spec["keys"]:
                        _add(fields[name + "." + key], meta, [e.get(key) for e in value or []])
        counts[item["id"]] = {name: _finish(counter) for name, counter in fields.items()}
    return counts


def candidate_quotes(extractions, checks, papers_meta, checklist):
    """Return the verified quotes of at most QUOTE_LIMIT words, without repeats. Each quote has the
    DOI of the text it comes from and the text version of that text."""
    out = []
    for wid in sorted(extractions):
        doi = citation_doi(papers_meta[wid])
        if not doi:
            continue
        text_version = papers_meta[wid].get("text_version")
        failed = {(f["item"], f["field"], f["quote"]) for f in checks[wid]["failed"]}
        seen = set()
        for item_id, field, quote in iter_quotes(extractions[wid], checklist):
            text = " ".join(quote.split())
            if (item_id, field, quote) in failed or len(words(text)) > QUOTE_LIMIT or (item_id, text) in seen:
                continue
            seen.add((item_id, text))
            out.append({"item": item_id, "field": field, "text": text, "doi": doi, "work_id": wid,
                        "text_version": text_version})
    return out


def compute_stability(pairs, checklist, threshold=STABLE_THRESHOLD):
    """Return the mean agreement of each closed item over the extraction pairs of all people."""
    out = {}
    for item in closed_items(checklist):
        scores = [s for s in (item_agreement(item, a["answers"].get(item["id"]), b["answers"].get(item["id"]))
                              for a, b in pairs) if s is not None]
        if scores:
            mean = sum(scores) / len(scores)
            out[item["id"]] = {"agreement": round(mean, 3), "pairs": len(scores), "stable": mean >= threshold}
        else:
            out[item["id"]] = {"agreement": None, "pairs": 0, "stable": None}
    return out


def _read_extraction(path):
    """Return the extraction in the file, or None when the file is unreadable or not an object."""
    try:
        extraction = read_json(path)
    except (ValueError, OSError):
        return None
    return extraction if isinstance(extraction, dict) else None


def _is_current(extraction, work_id, run, checklist):
    return (extraction.get("checklist_version") == checklist["version"]
            and extraction.get("prompt_version") == PROMPT_VERSION
            and extraction.get("work_id") == work_id
            and extraction.get("run") == run)


def collect_pairs(data, manifests, checklist):
    """Return (main, agreement) extraction pairs of fetched papers. A pair needs two readable valid
    extractions of the current checklist and prompt, each labelled with its own work id and run,
    and both made from the same paper text. The function skips any other pair."""
    pairs = []
    for manifest in manifests:
        for meta in manifest["papers"]:
            if meta["status"] != "fetched":
                continue
            main = extraction_path(data, manifest["person"], meta["work_id"], "main")
            agree = extraction_path(data, manifest["person"], meta["work_id"], "agreement")
            if not (os.path.exists(main) and os.path.exists(agree)):
                continue
            a, b = _read_extraction(main), _read_extraction(agree)
            if a is None or b is None:
                continue
            if validate_extraction(a, checklist, meta["group"]) or validate_extraction(b, checklist, meta["group"]):
                continue
            if not (_is_current(a, meta["work_id"], "main", checklist)
                    and _is_current(b, meta["work_id"], "agreement", checklist)
                    and a["paper_sha256"] == b["paper_sha256"]):
                continue
            pairs.append((a, b))
    return pairs


def build_profile(person, manifest, extractions, checks, checklist, stability, surface):
    """Return the profile data of one person (spec section 13)."""
    meta = {p["work_id"]: p for p in manifest["papers"] if p["status"] == "fetched"}
    used = sorted(w for w in meta if w in extractions and checks.get(w, {}).get("status") == "ok")
    left_out = [{"work_id": w, "reason": checks.get(w, {}).get("status", "missing")} for w in sorted(meta) if w not in used]
    chosen = {w: extractions[w] for w in used}
    unverified = Counter()
    for w in used:
        unverified.update(checks[w]["unverified_items"])
    years = sorted(meta[w]["year"] for w in used if meta[w].get("year"))
    surface = surface or {}
    return {
        "schema": 1, "person": person["id"], "name": person["name"], "checklist_version": checklist["version"],
        "n_papers": len(used), "papers_used": used, "left_out": left_out,
        "by_cell": _plain(Counter(meta[w]["cell"] for w in used)),
        "by_group": _plain(Counter(meta[w]["group"] for w in used)),
        "by_tier": _plain(Counter(meta[w]["tier"] for w in used)),
        "text_versions": _plain(Counter(meta[w]["text_version"] for w in used)),
        "years": {"first": years[0], "last": years[-1]} if years else {"first": None, "last": None},
        "items": count_answers(chosen, meta, checklist),
        "unverified": _plain(unverified),
        "stability": stability,
        "surface": surface.get("pooled"),
        "surface_papers": surface.get("n_papers"),
        "distinctive_words": surface.get("distinctive_words", []),
        "distinctive_pairs": surface.get("distinctive_pairs", []),
        "distinctive_note": surface.get("distinctive_note", ""),
        "quotes": candidate_quotes(chosen, checks, meta, checklist),
    }


def build_digest(person_id, manifest, extractions, checklist, used):
    """Return the free-text answers of each used paper, for the card writer. It never enters the
    repository."""
    meta = {p["work_id"]: p for p in manifest["papers"]}
    papers = []
    for wid in used:
        answers = extractions[wid]["answers"]
        entry = {"work_id": wid, "doi": quote_doi(meta[wid]), "title": meta[wid]["title"],
                 "group": meta[wid]["group"], "tier": meta[wid]["tier"], "free_text": {}}
        for item in checklist["items"]:
            answer = answers.get(item["id"])
            if not isinstance(answer, dict) or answer == NOT_APPLICABLE:
                continue
            for name, spec in item["fields"].items():
                if spec["type"] in ("text", "texts", "strings") and answer.get(name):
                    entry["free_text"][item["id"] + "." + name] = answer[name]
        papers.append(entry)
    return {"person": person_id, "papers": papers}


def quality_report(profiles, checks_by_person, spot, checklist):
    """Return profiles/quality.md: agreement and spot checks per item, quote checks per person."""
    stability = profiles[0]["stability"] if profiles else {}
    lines = ["# Quality of the profiles", "",
             "Checklist version {}. Each column is a separate measure. No column combines the others into a score."
             .format(checklist["version"]), "",
             "## Items", "", "| Item | Agreement | Pairs | Spot check correct |", "|---|---|---|---|"]
    for item in checklist["items"]:
        entry = stability.get(item["id"], {})
        marks = [m[item["id"]] for m in spot.values() if m.get(item["id"])]
        correct = sum(1 for m in marks if m == "correct")
        agreement = "n/a" if entry.get("agreement") is None else "{:.2f}".format(entry["agreement"])
        lines.append("| {} | {} | {} | {} of {} |".format(item["id"], agreement, entry.get("pairs", 0), correct, len(marks)))
    lines += ["", "## People", "", "| Person | Papers used | Left out | Quotes failed |", "|---|---|---|---|"]
    for profile in profiles:
        checks = checks_by_person.get(profile["person"], [])
        checked = sum(c.get("checked", 0) for c in checks)
        failed = sum(len(c.get("failed", [])) for c in checks)
        lines.append("| {} | {} | {} | {} of {} |".format(profile["name"], profile["n_papers"],
                                                         len(profile["left_out"]), failed, checked))
    return "\n".join(lines) + "\n"
