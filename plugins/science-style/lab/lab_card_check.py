"""Check a card or the principles file against the profile data (spec section 13).

A quote takes the form "text" (doi:10.xxxx/yyyy). Double quotes mark nothing else. A quote has 3 to
25 words and is a contiguous part of a verified quote in a profile, with the same DOI.

Outside the quotes, every number occurs in the profile data, except the numbers of the phrases
"per 100" and "per 1,000". A count written "N of M", "N out of M" or "N/M" is a (count,
denominator) pair of one profile. The text writes numbers as digits and states no percentage.
"""
import math
import re
from decimal import Decimal, InvalidOperation, ROUND_CEILING, ROUND_FLOOR

from lab_text import normalize_for_match, words

CARD_HEADINGS = ("Sample", "Storyline", "Introduction", "Results", "Excitement", "Limitations", "Discussion",
                 "Sentences and words", "Signature moves", "Caveats")
PRINCIPLES_HEADINGS = ("Shared moves", "Distinctive moves")
LIMITS = {"card": {"words": 900, "quotes": 20, "per_doi": 2},
          "principles": {"words": 1200, "quotes": 20, "per_doi": 2}}
MAX_QUOTE_WORDS = 25
MIN_QUOTE_WORDS = 3
UNIT_NUMBERS = frozenset(["100", "1000", "1,000"])
NUMBER_WORDS = frozenset("""two three four five six seven eight nine ten eleven twelve thirteen fourteen
fifteen sixteen seventeen eighteen nineteen twenty thirty forty fifty sixty seventy eighty ninety hundred
thousand dozen half halves quarter quarters twice thrice hundreds thousands dozens million millions
billion billions""".split())
PAPER_NOUNS = frozenset(["paper", "papers"])
QUOTE = re.compile(r'"([^"\n]+)"(\s*\(doi:\s*(10\.[^\s)]+)\))?')
DOI_TAG = re.compile(r"\(doi:[^)]*\)")
STRAY_QUOTES = '"\u201c\u201d\u00ab\u00bb\u201e\u201f\u2033'
# A digit run counts when letters follow it (1990s, 3x, 12th) or a dot precedes it (.73). It does not
# count when a letter or digit precedes it (W123, H3K27, p53). "9,73" is two numbers, "24,317" is one.
NUMBER = re.compile(r"(?<!\w)(?:\d{1,3}(?:,\d{3})+(?!\d)|\.?\d+(?:\.\d+)?)")
UNIT_PHRASE = re.compile(r"\bper\s+(?:{})(?!\d|,\d)".format(
    "|".join(sorted((re.escape(n) for n in UNIT_NUMBERS), key=len, reverse=True))), re.I)
COUNT = re.compile(r"(?<![\w.,/])(\d{1,3}(?:,\d{3})+|\d+)(?:\s+(?:of|out\s+of)(?:\s+the)?\s+|\s*/\s*)"
                   r"(\d{1,3}(?:,\d{3})+|\d+)(?![\d/]|\.\d|,\d)(?:\s+([^\W\d_]+))?")
PERCENT = re.compile(r"[%\uff05]|\bper\s+cent\b|\bpercent(?:age)?s?\b", re.I)
HYPHENS = "-\u2010\u2011"
WORD_TOKEN = re.compile(r"[^\W\d_]+(?:[{0}][^\W\d_]+)*".format(HYPHENS))
FOLD = re.compile(r"\b\w+[{0}]fold\b".format(HYPHENS), re.I)
ONE_OF = re.compile(r"\bone\s+(?:of|in)\s+(?:\d+|(?:{})\b)".format(
    "|".join(sorted(NUMBER_WORDS, key=len, reverse=True))), re.I)


def _with_commas(text):
    whole, dot, fraction = text.partition(".")
    if whole.isdigit() and len(whole) > 3:
        return "{:,}".format(int(whole)) + dot + fraction
    return None


def _decimal_forms(value):
    """Return the one- and two-decimal forms of a float, rounded down and rounded up."""
    forms = set()
    try:
        exact = Decimal(repr(value))
        for places in ("0.1", "0.01"):
            for rounding in (ROUND_FLOOR, ROUND_CEILING):
                text = format(exact.quantize(Decimal(places), rounding=rounding), "f")
                forms.add(text)
                forms.add(text.rstrip("0").rstrip(".") if "." in text else text)
    except InvalidOperation:
        pass
    return forms


def profile_numbers(obj, out=None):
    """Return every number in a profile as text. A number of 1,000 or more also has its comma form. A
    float also has its one- and two-decimal forms, rounded down and rounded up."""
    out = set() if out is None else out
    if isinstance(obj, bool):
        return out
    if isinstance(obj, int):
        forms = {str(abs(obj))}
    elif isinstance(obj, float):
        if not math.isfinite(obj):
            return out
        value = abs(obj)
        forms = {repr(value), "{:g}".format(value), "{:.1f}".format(value), "{:.2f}".format(value)}
        forms |= _decimal_forms(value)
        if value == int(value):
            forms.add(str(int(value)))
    elif isinstance(obj, dict):
        for value in obj.values():
            profile_numbers(value, out)
        return out
    elif isinstance(obj, list):
        for value in obj:
            profile_numbers(value, out)
        return out
    else:
        return out
    out.update(forms)
    out.update(form for form in map(_with_commas, forms) if form)
    return out


def _is_count(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _add_pairs(pairs, counts, size):
    if isinstance(counts, dict) and _is_count(size):
        pairs.update((count, size) for count in counts.values() if _is_count(count))


def profile_count_pairs(profile):
    """Return two sets of (count, denominator) pairs of a profile.

    The first set holds the paper counts of the item fields: the counts of all papers, of the first and
    last value, and of each group and tier, each with its own denominator. The second set holds the
    pairs of the paper total: (n_papers, n_papers) and (papers used, n_papers). A text may use these
    only before the word "papers".
    """
    pairs, paper_pairs = set(), set()
    for fields in (profile.get("items") or {}).values():
        for counter in (fields.values() if isinstance(fields, dict) else []):
            if not isinstance(counter, dict):
                continue
            size = counter.get("n")
            for section in ("all", "first", "last"):
                _add_pairs(pairs, counter.get(section), size)
            for level, sizes in (("by_group", "n_by_group"), ("by_tier", "n_by_tier")):
                for key, counts in (counter.get(level) or {}).items():
                    _add_pairs(pairs, counts, (counter.get(sizes) or {}).get(key))
    total = profile.get("n_papers")
    if _is_count(total):
        paper_pairs.add((total, total))
        if isinstance(profile.get("papers_used"), list):
            paper_pairs.add((len(profile["papers_used"]), total))
    return pairs, paper_pairs


def _number_word_failures(prose):
    """Return the words of a number written in letters, once each, in the order of the text."""
    found, seen = [], set()

    def note(token):
        if token.lower() not in seen:
            seen.add(token.lower())
            found.append(token)

    for token in WORD_TOKEN.findall(prose):
        for part in re.split("[{}]".format(HYPHENS), token.lower()):
            if part in NUMBER_WORDS or (part.endswith("fold") and part[:-4] in NUMBER_WORDS):
                note(token)
                break
    for match in FOLD.finditer(prose):
        note(match.group())
    for match in ONE_OF.finditer(prose):
        note(" ".join(match.group().split()))
    return found


def check_text(text, kind, profiles):
    """Return the failures of a card (kind "card") or a principles file (kind "principles")."""
    failures = []
    text = text.replace("\u201c", '"').replace("\u201d", '"')
    limits = LIMITS[kind]
    expected = CARD_HEADINGS if kind == "card" else PRINCIPLES_HEADINGS
    headings = tuple(line[3:].strip() for line in text.splitlines() if line.startswith("## "))
    if headings != expected:
        failures.append("headings must be, in order: " + ", ".join(expected))
    verified = {}
    allowed = set()
    pairs, paper_pairs = set(), set()
    for profile in profiles:
        profile_numbers(profile, allowed)
        item_pairs, total_pairs = profile_count_pairs(profile)
        pairs |= item_pairs
        paper_pairs |= total_pairs
        for quote in profile.get("quotes", []):
            verified.setdefault(quote["doi"].lower(), []).append(normalize_for_match(quote["text"]))
    per_doi, n_quotes = {}, 0
    for match in QUOTE.finditer(text):
        quote, doi = match.group(1), match.group(3)
        n_quotes += 1
        if len(words(quote)) < MIN_QUOTE_WORDS:
            failures.append('quote too short: "{}"'.format(quote))
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
    if any(mark in prose for mark in STRAY_QUOTES):
        failures.append("unpaired or multi-line double quote")
    if DOI_TAG.search(prose):
        failures.append("DOI tag without a quote")
    if PERCENT.search(prose):
        failures.append("the text uses a percentage")
    for token in _number_word_failures(prose):
        failures.append("write numbers as digits: " + token)
    scan = UNIT_PHRASE.sub(" ", DOI_TAG.sub(" ", prose))
    for number in sorted(set(NUMBER.findall(scan))):
        if number not in allowed:
            failures.append("number not in the profile data: " + number)
    for n, m, noun in COUNT.findall(scan):
        pair = (int(n.replace(",", "")), int(m.replace(",", "")))
        if pair[0] > pair[1]:
            failure = "{} of {} has N larger than M".format(*pair)
        elif pair in pairs or (pair in paper_pairs and noun.lower() in PAPER_NOUNS):
            continue
        else:
            failure = "count not in the profile data: {} of {}".format(*pair)
        if failure not in failures:
            failures.append(failure)
    return failures
