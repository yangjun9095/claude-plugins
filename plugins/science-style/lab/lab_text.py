"""Text helpers of the style lab: sentences, words, normalization and the text of a paper file.

A paper file has an abstract, sections with subsections, and legends (spec section 10). The
helpers read that structure and never change it, except new_paper and finish_paper, which build it.
"""
import hashlib
import re
import unicodedata

NORMALIZER_VERSION = "1"
PLACEHOLDERS = ("[CIT]", "[EQ]")
PAPER_META_FIELDS = ("work_id", "person", "doi", "title", "year", "venue", "tier", "group",
                     "co_senior", "text_version", "text_doi", "route", "source_url")
ABBREVIATIONS = frozenset("""fig figs eq eqs ref refs no nos vs al approx ca cf resp sec suppl ext
dr prof st etc e.g i.e""".split())

_SINGLE_QUOTES = "‘’‚‛′"
_DOUBLE_QUOTES = "“”„‟″"
_DASHES = "‐‑‒–—―−"
_END = re.compile(r"[.?!]")
_TAIL = re.compile(r"(?:\[CIT\])?[\"')\]’”]*")
_NEXT = re.compile(r"\s+[\"'(\[‘“]?[A-Z0-9]")
_WORD = re.compile(r"\d+(?:[.,]\d+)*(?![^\W_])|[^\W_]+(?:['’‐‑–\-][^\W_]+)*")
_DOI_PREFIX = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:)", re.I)


def normalize_for_match(text):
    """Return text with NFKC forms, straight quotes, one dash form and single spaces."""
    text = unicodedata.normalize("NFKC", text)
    for ch in _SINGLE_QUOTES:
        text = text.replace(ch, "'")
    for ch in _DOUBLE_QUOTES:
        text = text.replace(ch, '"')
    for ch in _DASHES:
        text = text.replace(ch, "-")
    return " ".join(text.split())


def _is_abbreviation(before):
    tokens = before.split()
    token = tokens[-1].lstrip("([\"'").lower() if tokens else ""
    return token in ABBREVIATIONS or (len(token) == 1 and token.isalpha())


def split_sentences(text):
    """Split a paragraph into sentences.

    A sentence ends at ".", "?" or "!" when white space and a capital letter or a digit follow.
    Abbreviations, initials and decimals do not end a sentence. A citation mark, closing quotes
    and closing brackets after the stop stay with the sentence.
    """
    text = " ".join(text.split())
    sentences, start = [], 0
    for match in _END.finditer(text):
        pos = match.start()
        tail = _TAIL.match(text, pos + 1)
        end = tail.end()
        if not _NEXT.match(text, end):
            continue
        if match.group() == "." and _is_abbreviation(text[start:pos]):
            continue
        sentences.append(text[start:end].strip())
        start = end
    rest = text[start:].strip()
    if rest:
        sentences.append(rest)
    return [s for s in sentences if s]


def words(text):
    """Return the words and numbers of text. Placeholders are not words."""
    for mark in PLACEHOLDERS:
        text = text.replace(mark, " ")
    return _WORD.findall(text)


def normalize_title(title):
    """Return a key for matching titles: lower case, no accents, letters and digits only."""
    text = unicodedata.normalize("NFKD", title or "")
    text = "".join(ch for ch in text if not unicodedata.combining(ch)).lower()
    return " ".join(re.sub(r"[\W_]+", " ", text).split())


def normalize_doi(doi):
    """Return the DOI in lower case without a resolver prefix, or None."""
    if not doi:
        return None
    doi = _DOI_PREFIX.sub("", doi.strip()).strip().lower()
    return doi or None


def iter_paragraphs(paper, include_abstract=True, exclude_kinds=("methods",)):
    """Yield (kind, heading, paragraph) in reading order.

    A paragraph of a subsection carries the heading of the subsection. The abstract has the kind
    "abstract" and an empty heading.
    """
    if include_abstract:
        for para in paper.get("abstract", []):
            yield ("abstract", "", para)
    for section in paper.get("sections", []):
        kind = section.get("kind", "other")
        if kind in exclude_kinds:
            continue
        for para in section.get("paragraphs", []):
            yield (kind, section.get("heading", ""), para)
        for sub in section.get("subsections", []):
            for para in sub.get("paragraphs", []):
                yield (kind, sub.get("heading", ""), para)


def body_words(paper):
    """Return the number of words in the sections, without Methods, abstract or legends."""
    return sum(len(words(p)) for _, _, p in iter_paragraphs(paper, include_abstract=False))


def word_counts(paper):
    """Return the number of words for each kind of text, Methods included."""
    counts = {}
    if paper.get("abstract"):
        counts["abstract"] = sum(len(words(p)) for p in paper["abstract"])
    for kind, _, para in iter_paragraphs(paper, include_abstract=False, exclude_kinds=()):
        counts[kind] = counts.get(kind, 0) + len(words(para))
    return counts


def canonical_text(paper):
    """Return the abstract, headings, paragraphs and legends, one per line."""
    parts = list(paper.get("abstract", []))
    for section in paper.get("sections", []):
        parts.append(section.get("heading", ""))
        parts.extend(section.get("paragraphs", []))
        for sub in section.get("subsections", []):
            parts.append(sub.get("heading", ""))
            parts.extend(sub.get("paragraphs", []))
    parts.extend(paper.get("legends", []))
    return "\n".join(p for p in parts if p)


def paper_sha256(paper):
    return hashlib.sha256(canonical_text(paper).encode("utf-8")).hexdigest()


def new_paper(meta):
    """Return an empty paper file with the metadata of meta."""
    paper = {"schema": 1, "normalizer_version": NORMALIZER_VERSION}
    for field in PAPER_META_FIELDS:
        paper[field] = meta.get(field)
    paper.update({"article_type": "", "abstract": [], "sections": [], "legends": []})
    return paper


def finish_paper(paper):
    """Add word_counts and sha256 to a paper file that a reader built, and return it."""
    paper["word_counts"] = word_counts(paper)
    paper["sha256"] = paper_sha256(paper)
    return paper
