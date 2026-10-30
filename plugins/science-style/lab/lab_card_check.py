"""Check a card or the principles file against the profile data (spec section 13).

A quote takes the form "text" (doi:10.xxxx/yyyy). Double quotes mark nothing else. A quote must be
a contiguous part of a verified quote in a profile, with the same DOI. Every number outside the
quotes must occur in the profile data, except the unit numbers 100 and 1,000 of "per 100" and
"per 1,000".
"""
import re

from lab_text import normalize_for_match, words

CARD_HEADINGS = ("Sample", "Storyline", "Introduction", "Results", "Excitement", "Limitations", "Discussion",
                 "Sentences and words", "Signature moves", "Caveats")
PRINCIPLES_HEADINGS = ("Shared moves", "Distinctive moves")
LIMITS = {"card": {"words": 900, "quotes": 20, "per_doi": 2},
          "principles": {"words": 1200, "quotes": 20, "per_doi": 2}}
MAX_QUOTE_WORDS = 25
UNIT_NUMBERS = frozenset(["100", "1000", "1,000"])
QUOTE = re.compile(r'"([^"\n]+)"(\s*\(doi:\s*(10\.[^\s)]+)\))?')
DOI_TAG = re.compile(r"\(doi:[^)]*\)")
NUMBER = re.compile(r"(?<![\w.,])(?:\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?)(?![\w])")
N_OF_M = re.compile(r"\b(\d+) of (\d+)\b")


def profile_numbers(obj, out=None):
    """Return every number in a profile as text, with floats also rounded to 1 and 2 decimals."""
    out = set() if out is None else out
    if isinstance(obj, bool):
        return out
    if isinstance(obj, int):
        out.add(str(obj))
    elif isinstance(obj, float):
        out.update([repr(obj), "{:g}".format(obj), "{:.1f}".format(obj), "{:.2f}".format(obj)])
        if obj == int(obj):
            out.add(str(int(obj)))
    elif isinstance(obj, dict):
        for value in obj.values():
            profile_numbers(value, out)
    elif isinstance(obj, list):
        for value in obj:
            profile_numbers(value, out)
    return out


def check_text(text, kind, profiles):
    """Return the failures of a card (kind "card") or a principles file (kind "principles")."""
    failures = []
    text = text.replace("“", '"').replace("”", '"')
    limits = LIMITS[kind]
    expected = CARD_HEADINGS if kind == "card" else PRINCIPLES_HEADINGS
    headings = tuple(line[3:].strip() for line in text.splitlines() if line.startswith("## "))
    if headings != expected:
        failures.append("headings must be, in order: " + ", ".join(expected))
    verified = {}
    allowed = set(UNIT_NUMBERS)
    for profile in profiles:
        profile_numbers(profile, allowed)
        for quote in profile.get("quotes", []):
            verified.setdefault(quote["doi"].lower(), []).append(normalize_for_match(quote["text"]))
    per_doi, n_quotes = {}, 0
    for match in QUOTE.finditer(text):
        quote, doi = match.group(1), match.group(3)
        n_quotes += 1
        if not doi:
            failures.append('quote without a DOI: "{}"'.format(quote))
            continue
        doi = doi.lower().rstrip(".,;")
        if len(words(quote)) > MAX_QUOTE_WORDS:
            failures.append('quote with more than {} words: "{}"'.format(MAX_QUOTE_WORDS, quote))
        needle = normalize_for_match(quote)
        if not any(needle in known for known in verified.get(doi, [])):
            failures.append('quote not among the verified quotes of {}: "{}"'.format(doi, quote))
        per_doi[doi] = per_doi.get(doi, 0) + 1
    for doi, count in sorted(per_doi.items()):
        if count > limits["per_doi"]:
            failures.append("{} quotes from {}; the limit is {}".format(count, doi, limits["per_doi"]))
    if n_quotes > limits["quotes"]:
        failures.append("{} quotes; the limit is {}".format(n_quotes, limits["quotes"]))
    count = len(words(DOI_TAG.sub(" ", text)))
    if count > limits["words"]:
        failures.append("the text has {} words; the limit is {}".format(count, limits["words"]))
    prose = QUOTE.sub(" ", text)
    if "%" in prose:
        failures.append("the text uses a percentage")
    for number in sorted(set(NUMBER.findall(prose))):
        if number not in allowed:
            failures.append("number not in the profile data: " + number)
    for n, m in N_OF_M.findall(prose):
        if int(n) > int(m):
            failures.append("{} of {} has N larger than M".format(n, m))
    return failures
