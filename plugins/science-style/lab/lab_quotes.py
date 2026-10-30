"""The quote check of the structure layer (spec section 12).

A quote passes when, after Unicode NFKC, straight quotes, one dash form and single spaces, it
occurs in the text of its paper file. It may include [CIT] and [EQ] marks. A paper whose failure
rate is above 10% needs a fresh extraction; a second failure marks it extraction_failed.
"""
import os

from lab_checklist import iter_quotes, validate_extraction
from lab_paths import check_path, extraction_path, paper_path, read_json, write_json
from lab_text import canonical_text, normalize_for_match, words

MAX_QUOTE_WORDS = 40
REDO_FAIL_RATE = 0.10


def check_extraction(extraction, paper, checklist):
    """Return the check of every quote in one extraction against its paper file."""
    text = normalize_for_match(canonical_text(paper))
    failed, checked, unverified = [], 0, set()
    for item_id, field, quote in iter_quotes(extraction, checklist):
        checked += 1
        needle = normalize_for_match(quote)
        if not needle:
            reason = "empty quote"
        elif len(words(needle)) > MAX_QUOTE_WORDS:
            reason = "more than {} words".format(MAX_QUOTE_WORDS)
        elif needle not in text:
            reason = "not in the paper"
        else:
            reason = None
        if reason:
            failed.append({"item": item_id, "field": field, "quote": quote, "reason": reason})
            unverified.add(item_id)
    rate = len(failed) / float(checked) if checked else 0.0
    return {"work_id": extraction.get("work_id"), "checked": checked, "failed": failed,
            "fail_rate": round(rate, 3), "unverified_items": sorted(unverified)}


def status_of(check, extraction, paper, checklist, errors):
    if errors:
        return "invalid"
    if extraction.get("paper_sha256") != paper.get("sha256") or extraction.get("checklist_version") != checklist["version"]:
        return "stale"
    if check["fail_rate"] > REDO_FAIL_RATE:
        return "extraction_failed" if extraction.get("attempt", 1) >= 2 else "redo"
    return "ok"


def check_person(data, manifest, checklist, run="main"):
    """Check the extractions of every fetched paper of a person, write one check file each, and
    return the checks. In the main run, a fetched paper without an extraction is "missing"."""
    person = manifest["person"]
    results = []
    for meta in manifest["papers"]:
        if meta["status"] != "fetched":
            continue
        wid = meta["work_id"]
        path = extraction_path(data, person, wid, run)
        if not os.path.exists(path):
            if run == "main":
                results.append({"work_id": wid, "checked": 0, "failed": [], "fail_rate": 0.0,
                                "unverified_items": [], "errors": [], "status": "missing"})
            continue
        extraction = read_json(path)
        paper = read_json(paper_path(data, person, wid))
        errors = validate_extraction(extraction, checklist, meta["group"])
        if extraction.get("work_id") != wid:
            errors.append("work_id {!r} does not match {}".format(extraction.get("work_id"), wid))
        if extraction.get("run") != run:
            errors.append("run {!r} does not match {}".format(extraction.get("run"), run))
        if errors:
            check = {"work_id": wid, "checked": 0, "failed": [], "fail_rate": 0.0, "unverified_items": []}
        else:
            check = check_extraction(extraction, paper, checklist)
        check["errors"] = errors
        check["status"] = status_of(check, extraction, paper, checklist, errors)
        write_json(check_path(data, person, wid, run), check)
        results.append(check)
    return results
