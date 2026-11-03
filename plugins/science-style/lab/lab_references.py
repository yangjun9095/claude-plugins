"""The paper list at the end of a card.

The command `references` writes a section `## Papers` at the end of profiles/<id>.md. The section has
one sentence that gives the number of papers, then one bullet for each paper in papers_used of the
profile. The card check ignores everything from the line `## Papers` to the end of the text. A card
writer never writes this section: the script adds it after the card check.
"""
import os
import re

from lab_aggregate import citation_doi
from lab_card_check import PAPERS_HEADING as HEADING, papers_offset

_BLANK_END = re.compile(r"\n[ \t\r]*\n$")


class ReferencesError(ValueError):
    """The manifest and the profile disagree. The command line turns it into exit code 2."""


def text_doi(meta):
    """Return the DOI that the profile quotes cite for this paper, or None.

    citation_doi gives the text_doi of the manifest paper when it has one. Otherwise it gives the DOI
    of the preprint or of the arXiv text that the paper was read from, and last the DOI of the paper.
    """
    return citation_doi(meta)


def _title(meta):
    title = " ".join((meta.get("title") or "").split())
    return title if title[-1:] in (".", "?", "!") else title + "."


def paper_line(meta):
    """Return the bullet of one manifest paper."""
    doi = text_doi(meta)
    year = meta.get("year")
    return "- {} {}, {}. {} ({} text)".format(
        _title(meta), meta.get("venue") or "no venue", year if year else "no year",
        "doi:" + doi if doi else "no doi", meta.get("text_version") or "unknown")


def _sort_key(meta):
    year = meta.get("year")
    title = " ".join((meta.get("title") or "").split())
    return (year is None, year or 0, title.casefold(), title, meta["work_id"])


def papers_section(manifest, profile):
    """Return the text of the section `## Papers` for the papers used in the profile.

    The bullets run by year, then by title. A paper without a year comes last. The function raises
    ReferencesError when a paper used is missing from the manifest or has the status "replaced".
    """
    fetched = {p["work_id"]: p for p in manifest["papers"] if p.get("status") != "replaced"}
    used = list(profile["papers_used"])
    missing = [wid for wid in used if wid not in fetched]
    if missing:
        raise ReferencesError("the profile uses papers that the manifest lacks or replaced: " + ", ".join(missing))
    lines = [HEADING, "", "The card rests on these {} papers.".format(len(used)), ""]
    lines += [paper_line(meta) for meta in sorted((fetched[wid] for wid in used), key=_sort_key)]
    return "\n".join(lines) + "\n"


def add_section(card_text, section):
    """Return the card with the section at its end.

    An existing `## Papers` section and everything after it goes. The text above stays as it was,
    except that the function ends it with a blank line.
    """
    start = papers_offset(card_text)
    head = card_text if start is None else card_text[:start]
    if head and not head.endswith("\n"):
        head += "\n"
    if head and not _BLANK_END.search(head):
        head += "\n"
    return head + section


def update_card(path, manifest, profile):
    """Write the section into the card file and return the number of papers listed.

    The function builds the new text before it touches the file, so an error leaves the card as it was.
    """
    section = papers_section(manifest, profile)
    with open(path, encoding="utf-8", newline="") as handle:
        text = handle.read()
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="") as handle:
        handle.write(add_section(text, section))
    os.replace(tmp, path)
    return len(profile["papers_used"])
