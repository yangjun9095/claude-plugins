"""Split masked text into paragraphs, sentences, words and numbers.

The detector, the voice profile and the guards share these helpers. Every function takes
the masked text of `prose_mask.mask`. A placeholder (U+E000, digits, U+E001) is no word and
no number. It never ends a sentence, and it can start one.

Offsets point into the text that the caller passes. `prose_mask.offset_map` maps them back
to the original text. Every returned range is trimmed of whitespace. No function raises on a str.

Sentence rule. A run of `.`, `!`, `?` or U+2026 ends a sentence when whitespace follows it and
a new sentence starts after the whitespace. The new sentence starts with an uppercase letter, a
digit, an opening quote or a placeholder. A bracket, asterisk or underscore may come first when a
capital letter or a digit follows it. Closing quotes, brackets, asterisks, underscores, tildes
and placeholders right after the run belong to the sentence. A paragraph break and the end of a
paragraph also end a sentence. A lowercase word after the run means no end.

One dot after an abbreviation never ends a sentence, even before a capital letter. The list
includes `et al.` and `No.`, so such a sentence stays joined to the next unless the paragraph
ends. An initial (one capital letter) or a dotted initialism (`U.S.`) blocks the end too, except
before a bracket and a capital letter. Lowercase forms such as `p.`, `fig.` and `ref.` block the
end only before a digit or a placeholder. A decimal has no whitespace after the dot and never
splits.
"""
import re
from bisect import bisect_left, bisect_right

from prose_mask_core import CLOSE, OPEN

_PLACEHOLDER = OPEN + "[0-9]+" + CLOSE
_PLACEHOLDER_RE = re.compile(_PLACEHOLDER)
_LETTER = r"[^\W\d_]"
_ALNUM = r"[^\W_]"
_JOINER = "['\u2019-]"
# A hyphen joins two alphanumeric runs unless a digit stands on both sides, so `3-5` is two tokens.
_TOKEN_JOINER = "(?:['\u2019]|(?<![0-9])-|-(?![0-9])|(?<=[0-9])[.,](?=[0-9]))"

_BREAK = re.compile(r"\n[^\S\n]*(?:\n[^\S\n]*)+")
_MARK = re.compile("([.!?\u2026]+)(?:[\"'\u201d\u2019)\\]*_~]|" + _PLACEHOLDER + ")*")
_OPENING_QUOTES = "\"'\u201c\u2018"
_OPENERS = "([*_"
_OPENERS_AND_QUOTES = _OPENERS + _OPENING_QUOTES

# Each pattern is anchored at the end of the window and needs a non-alphanumeric character before it.
_ABBREVIATIONS = ("et\\s+al Fig Figs Eq Eqs Ref Refs Sec Tab Suppl Supp Ext Exp Vol Vols Inc Ltd Corp Univ Dept "
                  "St Co Sect Chap Mt Cat Dr Mr Mrs Ms Prof No e\\.g i\\.e vs cf approx ca resp").split()
# An entry in lowercase also appears with a capital at the start of a sentence.
_CAPITALIZED = [a[0].upper() + a[1:] for a in _ABBREVIATIONS if a[0].islower() and a != "et\\s+al"]
# These entries also appear in lowercase, as in a reference list. "no", "sec" and "tab" stay out, as common words.
_LOWERCASE = "supp ext exp vol vols inc ltd corp univ dept".split()
_BEFORE = "(?<![A-Za-z0-9])"
_ABBREVIATION = re.compile(_BEFORE + "(?:" + "|".join(_ABBREVIATIONS + _CAPITALIZED + _LOWERCASE) + ")\\Z")
_INITIAL = re.compile(_BEFORE + "[A-Z]\\Z")
_DOTTED = re.compile(_BEFORE + "(?:[A-Z]\\.)+[A-Z]\\Z")
# These lowercase forms are common words or letters, so they block the end only before a digit or a placeholder.
_BEFORE_NUMBER = re.compile(_BEFORE + "(?:pp|p|fig|figs|eq|eqs|ref|refs|sect|chap|mt|cat)\\Z")
_WINDOW = 16

_WORD = re.compile(
    "(?P<ph>" + _PLACEHOLDER + ")|(?P<number>[0-9]+(?:[.,][0-9]+)*%?)|(?P<word>" + _LETTER + "+(?:" + _JOINER +
    _LETTER + "+)*)")
_TOKEN = re.compile("(?P<ph>" + _PLACEHOLDER + ")|(?P<token>" + _ALNUM + "+(?:" + _TOKEN_JOINER + _ALNUM + "+)*)")
_NUMBER_LEAD = re.compile("([0-9]+(?:[.,][0-9]+)*)-[a-z]")

_UNITS = ("mg \u00b5g ug ng pg kg g mL ml \u00b5L \u00b5l uL L mM \u00b5M uM nM pM M mol mmol \u00b5mol umol nmol pmol fmol "
          "mm cm nm \u00b5m um m km ms \u00b5s s min h hr d Hz kHz MHz GHz bp kb Mb kDa Da \u00b0C K V mV A mA fold \u00d7").split()
# A time word and its plural give one token, so `3 weeks` and `a 3-week course` agree.
_TIME_WORDS = "second minute hour day week month year".split()
_TIME_ABBREVIATIONS = "wk mo yr".split()
_PLURAL_UNITS = dict([(word + "s", word) for word in _TIME_WORDS] + [("wks", "wk"), ("yrs", "yr")])
_UNITS += _TIME_WORDS + list(_PLURAL_UNITS) + _TIME_ABBREVIATIONS
# The Greek letter mu (U+03BC) also appears in text, so each unit with a micro sign gets a twin.
_UNIT_FORMS = sorted(set(_UNITS) | set(u.replace("\u00b5", "\u03bc") for u in _UNITS), key=lambda u: -len(u))
_ANY_UNIT = "(?:" + "|".join(re.escape(u) for u in _UNIT_FORMS) + ")"
# A unit may take `/unit` parts, as in `mg/kg/day`. The word `cells` is a unit only before a `/unit` part.
_UNIT_TEXT = "(?:" + _ANY_UNIT + "(?:/" + _ANY_UNIT + ")*|cells(?:/" + _ANY_UNIT + ")+)"
# One space, `~` or a hyphen may stand between a number and its unit.
_SPACE = "[ \u00a0\u2009\u200a\u202f]"
_UNIT_GAP = "[ \u00a0\u2009\u200a\u202f~\u2010\u2011-]"
# A sign belongs to the number at the text start, after whitespace, after an opening bracket or after a
# relation sign such as `=`. So `r=-0.5` keeps its minus.
_SIGN = "(?:(?<![^\\s(\\[{=<>\u2264\u2265\u00b1])[-\u2212\u2013+])"
_NUMBER = re.compile(
    "(?P<ph>" + _PLACEHOLDER + ")|(?<!\\w)(?P<number>" + _SIGN + "?[0-9]+(?:[.,][0-9]+)*)"
    "(?:" + _SPACE + "?(?P<percent>%)|" + _UNIT_GAP + "?(?P<unit>" + _UNIT_TEXT + ")(?!" + _LETTER + "))?")


def _trim(text, start, end):
    """Return start and end moved inward past whitespace."""
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _cut(text, ranges, hard_breaks):
    """Split each range at the hard-break offsets inside it. Trim the pieces and drop empty ones."""
    cuts = sorted(set(b for b in hard_breaks if 0 < b < len(text)))
    found = []
    for start, end in ranges:
        pos = start
        for cut in cuts[bisect_right(cuts, start):bisect_left(cuts, end)] + [end]:
            piece = _trim(text, pos, cut)
            if piece[0] < piece[1]:
                found.append(piece)
            pos = cut
    return found


def paragraphs(text, hard_breaks=()):
    """Return the (start, end) of each paragraph. One or more blank lines separate paragraphs.

    Each offset in `hard_breaks` also ends a paragraph, as a blank line does.
    """
    ranges, pos = [], 0
    for m in _BREAK.finditer(text):
        ranges.append((pos, m.start()))
        pos = m.end()
    ranges.append((pos, len(text)))
    return _cut(text, ranges, hard_breaks)


def _add_sentence(found, text, start, end):
    """Add the range when it holds a letter or a digit outside the placeholders."""
    if any(c.isalnum() for c in _PLACEHOLDER_RE.sub("", text[start:end])):
        found.append((start, end))


def _after_openers(text, i, end):
    """Return the offset after the run of brackets, emphasis marks and quotes that starts at i."""
    while i < end and text[i] in _OPENERS_AND_QUOTES:
        i += 1
    return i


def _starts_sentence(text, i, end):
    """Tell whether a sentence can start at offset i. A bracket or a quote may come first."""
    char = text[i]
    if char.isupper() or char.isdigit() or char == OPEN or char in _OPENING_QUOTES:
        return True
    if char not in _OPENERS:
        return False
    i = _after_openers(text, i, end)
    return i < end and (text[i].isupper() or text[i].isdigit() or text[i] == OPEN)


def _blocks_end(text, mark, floor, nxt, end):
    """Tell whether the dot at offset `mark` belongs to a word that does not end a sentence.

    An abbreviation or a dotted initialism (`U.S.`) blocks the end before any start.
    A page or figure word in lowercase (`p.`, `fig.`) blocks it only before a digit or a placeholder.
    An initial (one capital letter) blocks it before any start except a bracket and a capital letter,
    so `Lee, A. (2020)` stays joined and `group A. (See Fig. 2.)` splits.
    """
    window = (text, max(floor, mark - _WINDOW), mark)
    if _ABBREVIATION.search(*window) or _DOTTED.search(*window):
        return True
    if (text[nxt].isdigit() or text[nxt] == OPEN) and _BEFORE_NUMBER.search(*window):
        return True
    if not _INITIAL.search(*window):
        return False
    after = _after_openers(text, nxt, end)
    return not (text[nxt] in "([" and after < end and text[after].isupper())


def split_sentences(text, hard_breaks=()):
    """Return the (start, end) of each sentence, in order and without overlap.

    Each offset in `hard_breaks` also ends a sentence, as a blank line does. A caller
    passes the end of a heading line or the start of an item line. An offset in the
    middle of a word splits there, and an offset in the middle of a placeholder splits it.
    """
    found = []
    for p_start, p_end in paragraphs(text, hard_breaks):
        start = p_start
        for m in _MARK.finditer(text, p_start, p_end):
            after = m.end()
            if after >= p_end or not text[after].isspace():
                continue
            nxt = after
            while text[nxt].isspace():
                nxt += 1
            if not _starts_sentence(text, nxt, p_end):
                continue
            if m.group(1) == "." and _blocks_end(text, m.start(), p_start, nxt, p_end):
                continue
            _add_sentence(found, text, start, after)
            start = nxt
        _add_sentence(found, text, start, p_end)
    return found


def words(text):
    """Return (start, end, word) for each word and each number, with the case kept.

    A word is a run of letters, joined by single hyphens or apostrophes. A number has digits,
    an optional thousands comma or decimal point, and an optional percent sign.
    """
    return [(m.start(), m.end(), m.group()) for m in _WORD.finditer(text) if m.lastgroup != "ph"]


def word_count(text):
    """Return the number of words and numbers in the text, as `words` counts them."""
    return len(words(text))


def _fold_unit(unit):
    """Return the unit text with the Greek mu as a micro sign and each plural time unit as its singular."""
    parts = unit.replace("\u03bc", "\u00b5").split("/")
    return "/".join(_PLURAL_UNITS.get(part, part) for part in parts)


def numeric_tokens(text):
    """Return each number as a string, with its unit or percent sign attached and no space.

    A minus sign, U+2212 or an en dash joins the number after whitespace, after an opening
    bracket or at the text start. It becomes `-`. After any other character a dash is a range
    dash, so `10-20 nM` gives `10` and `20nM`. One space, `~` or a hyphen may stand between
    the number and a listed unit, and no letter may follow the unit. A unit outside the list
    gives the bare number, so `3-plate` gives `3`. The noun after a number is no unit, so
    `12 mice` and `12 rats` both give `12`. One space may stand before `%`. The micro
    sign and the Greek mu both give the micro sign.

    The unit list is closed. It holds the lab units and the time words
    `second minute hour day week month year` with their plurals. It holds the abbreviations
    `s min h hr d wk mo yr` and the plurals `wks yrs`. A plural time word gives its singular.
    So `3 weeks`, `3 week` and `3-week` give `3week`. Case counts, so `3 Weeks` gives `3`.

    A unit may take `/unit` parts from the same list. The token keeps the whole text.
    So `5 mg/kg` gives `5mg/kg` and `5 mg/kg/days` gives `5mg/kg/day`. The word `cells` is a unit
    only before such a part. So `10 cells/mL` gives `10cells/mL` and `10 cells` gives `10`.
    A space around the `/`, an unlisted part or a letter after the part ends the unit before the `/`.
    """
    found = []
    for m in _NUMBER.finditer(text):
        if m.lastgroup != "ph":
            unit = m.group("percent") or _fold_unit(m.group("unit") or "")
            found.append(m.group("number").replace("\u2212", "-").replace("\u2013", "-") + unit)
    return found


def _fold(token):
    """Return the token in the form that a rewrite keeps: no possessive, one apostrophe, one mu."""
    token = token.replace("\u2019", "'").replace("\u03bc", "\u00b5")
    if token.endswith("'s") and len(token) > 2:
        token = token[:-2]
    lead = _NUMBER_LEAD.match(token)
    return lead.group(1) if lead else token


def _is_name(token, may_capitalize):
    """Tell whether a token is a name: it holds a digit or an inner capital, or it is capitalized."""
    return bool(re.search("[0-9]", token) or any(c.isupper() for c in token[1:])
                or (may_capitalize and token[0].isupper()))


def protected_names(text, include_starts=False):
    """Return the tokens that a rewrite must not add: names, acronyms and tokens with a digit.

    A token is protected when it holds a digit or an uppercase letter after its first
    character (`p53`, `mTOR`, `DNA`). Capitalized tokens count unless they start a sentence
    or follow a colon. With `include_starts` true, those tokens count too. A guard compares
    `protected_names(after)` with `protected_names(before, include_starts=True)`.

    Hyphenated tokens that hold an ordinary lowercase word also add each protected part, so
    `mTOR-dependent` gives `mTOR-dependent` and `mTOR`. Parts of digits only stay out.
    The tokens keep their case, but a trailing `'s` goes, U+2019 becomes an apostrophe, and
    U+03BC becomes U+00B5. Tokens such as `12-week` give their number, `12`. Between two
    digits, a hyphen splits the token. Known gap: a new name at a sentence start in `after`
    is not caught.
    """
    starts = set()
    for s_start, s_end in split_sentences(text):
        for m in _TOKEN.finditer(text, s_start, s_end):
            if m.lastgroup == "token":
                starts.add(m.start())
                break
    names, prev_end = set(), 0
    for m in _TOKEN.finditer(text):
        if m.lastgroup != "token":
            continue
        token = _fold(m.group())
        opens = m.start() in starts or _PLACEHOLDER_RE.sub("", text[prev_end:m.start()]).rstrip().endswith(":")
        prev_end = m.end()
        if _is_name(token, include_starts or not opens):
            names.add(token)
        parts = token.split("-")
        if len(parts) > 1 and any(part.isalpha() and part.islower() for part in parts):
            for i, part in enumerate(parts):
                if not part.isdigit() and _is_name(part, include_starts or not (opens and i == 0)):
                    names.add(part)
    return names
