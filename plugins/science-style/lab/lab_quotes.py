"""The quote check of the structure layer (spec section 12).

A quote passes when, after Unicode NFKC, straight quotes, one dash form and single spaces, it
occurs in the text of its paper file. It may include [CIT] and [EQ] marks. A paper whose failure
rate is above 10%, or whose extraction holds no quote, needs a fresh extraction; a second failure
marks it extraction_failed. An extraction made for an older paper file, checklist or prompt is stale.

check_person gives each paper its own check. A bad file makes that check invalid or missing and
never stops the check of the next paper.
"""
import os

from lab_checklist import PROMPT_VERSION, iter_quotes, validate_extraction
from lab_paths import check_path, extraction_path, paper_path, read_json, write_json
from lab_text import canonical_text, normalize_for_match, words

MAX_QUOTE_WORDS = 40
REDO_FAIL_RATE = 0.10


def make_check(work_id, status=None, errors=None, checked=0, failed=None, unverified=None):
    """Return a check with every key set. The status stays None until status_of sets it."""
    failed = failed or []
    rate = len(failed) / float(checked) if checked else 0.0
    return {"work_id": work_id, "checked": checked, "failed": failed, "fail_rate": round(rate, 3),
            "unverified_items": sorted(unverified or ()), "errors": list(errors or []), "status": status}


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
    return make_check(extraction.get("work_id"), checked=checked, failed=failed, unverified=unverified)


def status_of(check, extraction, paper, checklist, errors):
    if errors:
        return "invalid"
    if (extraction.get("paper_sha256") != paper.get("sha256")
            or extraction.get("checklist_version") != checklist["version"]
            or extraction.get("prompt_version") != PROMPT_VERSION):
        return "stale"
    if check["fail_rate"] > REDO_FAIL_RATE or check["checked"] == 0:
        return "extraction_failed" if extraction.get("attempt", 1) >= 2 else "redo"
    return "ok"


def _check_paper(data, person, wid, group, checklist, run):
    """Return the check of one paper. Return None when the run has no extraction to check."""
    extraction_file = extraction_path(data, person, wid, run)
    paper_file = paper_path(data, person, wid)
    has_extraction = os.path.exists(extraction_file)
    if not has_extraction and run != "main":
        return None
    if not os.path.exists(paper_file):
        return make_check(wid, "missing", ["no paper file"])
    if not has_extraction:
        return make_check(wid, "missing")
    try:
        extraction = read_json(extraction_file)
    except ValueError as error:
        return make_check(wid, "invalid", ["unreadable JSON: {}".format(error)])
    try:
        paper = read_json(paper_file)
    except ValueError as error:
        return make_check(wid, "invalid", ["unreadable paper file: {}".format(error)])
    if not isinstance(paper, dict):
        return make_check(wid, "invalid", ["paper file is not an object"])
    errors = validate_extraction(extraction, checklist, group)
    if isinstance(extraction, dict):
        if extraction.get("work_id") != wid:
            errors.append("work_id {!r} does not match {}".format(extraction.get("work_id"), wid))
        if extraction.get("run") != run:
            errors.append("run {!r} does not match {}".format(extraction.get("run"), run))
    if errors:
        return make_check(wid, "invalid", errors)
    check = check_extraction(extraction, paper, checklist)
    check["status"] = status_of(check, extraction, paper, checklist, errors)
    return check


def check_person(data, manifest, checklist, run="main"):
    """Check the extractions of every fetched paper of a person, write one check file each, and
    return the checks. In the main run, a fetched paper without an extraction is "missing". In
    any run, a check file whose extraction no longer exists is replaced (main) or removed
    (agreement), so no old check outlives its extraction."""
    person = manifest["person"]
    results = []
    for meta in manifest["papers"]:
        if meta["status"] != "fetched":
            continue
        wid = meta["work_id"]
        check = _check_paper(data, person, wid, meta.get("group"), checklist, run)
        path = check_path(data, person, wid, run)
        if check is None:
            if os.path.exists(path):
                os.remove(path)
            continue
        write_json(path, check)
        results.append(check)
    return results
