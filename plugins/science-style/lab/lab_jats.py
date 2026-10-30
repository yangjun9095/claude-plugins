"""Read JATS XML from PMC, Europe PMC and bioRxiv into a paper file (spec section 10).

The reader refuses a document that declares an entity, so no entity expansion can run. It removes
the XML declaration and the DOCTYPE line, because ElementTree cannot load the external DTD that
JATS names. A run of citations becomes one [CIT] mark and a formula becomes [EQ].
"""
import re
import xml.etree.ElementTree as ET

from lab_text import finish_paper, new_paper


class ReaderError(ValueError):
    """The document cannot become a paper file. The fetch step counts this as a route failure."""


XML_DECL = re.compile(r"^\s*<\?xml[^>]*\?>")
DOCTYPE = re.compile(r"<!DOCTYPE[^>\[]*(?:\[[^\]]*\])?\s*>", re.S)
CIT_RUN = re.compile(r"\[CIT\](?:[\s,;\-–—]*\[CIT\])+")
CIT_WRAP = re.compile(r"[(\[]\s*\[CIT\]\s*[)\]]")
LEADING_NUMBER = re.compile(r"^[\d.\s]+")
DROP_HEADINGS = ("reference", "acknowledg", "author contribution", "competing interest",
                 "declaration of interest", "conflict of interest", "conflicts of interest", "data availability",
                 "code availability", "data and code availability", "materials availability", "supplementary",
                 "supporting information", "funding", "additional information", "abbreviations")
KIND_RULES = (("methods", ("method", "materials and method", "material and method", "online method",
                           "star method", "star★method", "star★ method", "experimental procedure",
                           "experimental model")),
              ("results", ("result",)),
              ("discussion", ("discussion", "conclusion", "concluding", "outlook")),
              ("intro", ("introduction", "background", "related work", "prior work")))
BLOCKS = frozenset(["p", "list", "disp-quote", "boxed-text"])
SKIP_INLINE = frozenset(["fig", "table-wrap", "supplementary-material", "fn", "table", "graphic", "media"])
FORMULA = frozenset(["inline-formula", "disp-formula", "math", "tex-math"])
ESSAY_ARTICLE_TYPES = frozenset(["review-article", "editorial", "article-commentary", "letter", "discussion",
                                 "book-review"])


def heading_kind(heading):
    """Return the kind that a section heading names, or "drop" for back matter.

    The heading must start with a key, after any leading number, so "A method to image moss" and
    "A reference atlas" stay "other".
    """
    text = LEADING_NUMBER.sub("", heading.casefold()).strip()
    if text.startswith(DROP_HEADINGS):
        return "drop"
    for kind, prefixes in KIND_RULES:
        if text.startswith(prefixes):
            return kind
    return "other"


def local(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _child(elem, name):
    for child in elem:
        if local(child.tag) == name:
            return child
    return None


def _children(elem, name):
    return [child for child in elem if local(child.tag) == name]


def _collect(elem, parts, top=False):
    name = local(elem.tag)
    if not top:
        if name == "xref" and elem.get("ref-type") == "bibr":
            parts.append("[CIT]")
            parts.append(elem.tail or "")
            return
        if name in FORMULA:
            parts.append("[EQ]")
            parts.append(elem.tail or "")
            return
        if name in SKIP_INLINE:
            parts.append(elem.tail or "")
            return
    parts.append(elem.text or "")
    for child in elem:
        _collect(child, parts)
    if not top:
        parts.append(elem.tail or "")


def inline_text(elem):
    """Return the text of an element with [CIT] and [EQ] marks and single spaces."""
    parts = []
    _collect(elem, parts, top=True)
    text = " ".join("".join(parts).split())
    return CIT_WRAP.sub("[CIT]", CIT_RUN.sub("[CIT]", text))


def block_paragraphs(elem):
    """Return the paragraphs of a block: a p, or every p inside a list, quote or box."""
    if local(elem.tag) == "p":
        text = inline_text(elem)
        return [text] if text else []
    out = []
    for child in elem.iter():
        if child is not elem and local(child.tag) == "p":
            text = inline_text(child)
            if text:
                out.append(text)
    return out


def _title(sec):
    title = _child(sec, "title")
    return inline_text(title) if title is not None else ""


def _sec_paragraphs(sec, recurse):
    out = []
    for child in sec:
        name = local(child.tag)
        if name in BLOCKS:
            out.extend(block_paragraphs(child))
        elif name == "sec" and recurse:
            out.extend(_sec_paragraphs(child, True))
    return out


def read_section(sec):
    """Return a section dict. Nested sections deeper than one level join their subsection."""
    heading = _title(sec)
    kind = heading_kind(heading) if heading else "other"
    sec_type = (sec.get("sec-type") or "").casefold()
    if "method" in sec_type:
        kind = "methods"
    if "supplementary" in sec_type:
        kind = "drop"
    subsections = []
    for child in _children(sec, "sec"):
        sub_heading = _title(child)
        if sub_heading and heading_kind(sub_heading) == "drop":
            continue
        subsections.append({"heading": sub_heading, "paragraphs": _sec_paragraphs(child, True)})
    return {"heading": heading, "kind": kind, "paragraphs": _sec_paragraphs(sec, False), "subsections": subsections}


def read_body(body):
    """Return the sections of a body. Unheaded text before the first section is the introduction,
    or the whole body when the paper has no sections."""
    sections, lead = [], []
    for child in body:
        name = local(child.tag)
        if name == "sec":
            sections.append(read_section(child))
        elif name in BLOCKS:
            if sections:
                sections[-1]["paragraphs"].extend(block_paragraphs(child))
            else:
                lead.extend(block_paragraphs(child))
    if lead:
        kind = "intro" if sections else "body"
        sections.insert(0, {"heading": "", "kind": kind, "paragraphs": lead, "subsections": []})
    return [s for s in sections if s["kind"] != "drop"]


def infer_results(sections):
    """Mark as results the sections of kind "other" between the introduction and the discussion
    or methods, when no section is named Results. Change the list in place and return it."""
    if any(s["kind"] == "results" for s in sections):
        return sections
    seen_intro = False
    for section in sections:
        if section["kind"] in ("discussion", "methods"):
            break
        if section["kind"] == "intro":
            seen_intro = True
        elif section["kind"] == "other" and seen_intro:
            section["kind"] = "results"
    return sections


def read_abstract(article):
    meta = _child(article, "front")
    meta = _child(meta, "article-meta") if meta is not None else None
    if meta is None:
        return []
    abstracts = _children(meta, "abstract")
    main = [a for a in abstracts if not a.get("abstract-type")] or abstracts
    if not main:
        return []
    paragraphs = [inline_text(p) for p in main[0].iter() if local(p.tag) == "p"]
    paragraphs = [p for p in paragraphs if p]
    if not paragraphs:
        text = inline_text(main[0])
        paragraphs = [text] if text else []
    return paragraphs


def read_legends(article):
    legends = []
    for elem in article.iter():
        if local(elem.tag) in ("fig", "table-wrap"):
            caption = _child(elem, "caption")
            if caption is None:
                continue
            text = " ".join(t for t in (inline_text(c) for c in caption if local(c.tag) in ("title", "p")) if t)
            if text:
                legends.append(text)
    return legends


def is_manuscript(article):
    meta = _child(article, "front")
    meta = _child(meta, "article-meta") if meta is not None else None
    if meta is None:
        return False
    for aid in _children(meta, "article-id"):
        kind = (aid.get("pub-id-type") or "").casefold()
        text = (aid.text or "").strip().casefold()
        if kind in ("manuscript", "mid") or text.startswith("nihms") or text.startswith("ems"):
            return True
    return False


def read_jats(data, meta):
    """Return the paper file of a JATS document, or raise ReaderError."""
    text = data.decode("utf-8", errors="replace") if isinstance(data, bytes) else data
    if "<!ENTITY" in text:
        raise ReaderError("the document declares an entity")
    text = DOCTYPE.sub("", XML_DECL.sub("", text, count=1), count=1)
    try:
        root = ET.fromstring(text)
    except ET.ParseError as err:
        raise ReaderError("XML parse error: {}".format(err))
    if local(root.tag) == "article":
        article = root
    else:
        article = next((e for e in root.iter() if local(e.tag) == "article"), None)
    if article is None:
        raise ReaderError("no article element")
    article_type = article.get("article-type") or ""
    body = _child(article, "body")
    sections = read_body(body) if body is not None else []
    if meta.get("group") != "essay" and article_type not in ESSAY_ARTICLE_TYPES:
        infer_results(sections)
    paper = new_paper(meta)
    paper.update({"article_type": article_type, "jats_manuscript": is_manuscript(article),
                  "abstract": read_abstract(article), "sections": sections, "legends": read_legends(article)})
    return finish_paper(paper)
