"""Read arXiv LaTeXML HTML (arxiv.org/html/<id>) into a paper file (spec section 10).

The reader builds a small tree with html.parser. Paragraphs are the p elements of class ltx_p.
Citations become [CIT], formulas and display equations become [EQ], and number tags, footnotes,
figures, the bibliography, appendices and acknowledgements stay out of the text. On a page with
sections, the text before the first section is front matter: the dry run of 2026-10-29 found only
style-file warnings there (arXiv 1901.11365). The reader keeps that text only on a page without
sections, as its body.
"""
import re
from html.parser import HTMLParser

from lab_jats import CIT_RUN, CIT_WRAP, ReaderError, heading_kind, infer_results
from lab_text import finish_paper, new_paper

VOID = frozenset("area base br col embed hr img input link meta param source track wbr".split())
SECTION_CLASSES = ("ltx_section", "ltx_subsection", "ltx_subsubsection", "ltx_paragraph", "ltx_bibliography",
                   "ltx_appendix")
SKIP_CLASSES = ("ltx_figure", "ltx_table", "ltx_note", "ltx_bibliography", "ltx_appendix", "ltx_abstract",
                "ltx_authors", "ltx_dates", "ltx_keywords", "ltx_classification", "ltx_acknowledgements")


class Node(object):
    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag, attrs, parent):
        self.tag = tag
        self.attrs = dict(attrs)
        self.children = []
        self.parent = parent

    def has_class(self, name):
        return name in (self.attrs.get("class") or "").split()


class TreeBuilder(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.root = Node("#root", [], None)
        self.current = self.root

    def handle_starttag(self, tag, attrs):
        node = Node(tag, attrs, self.current)
        self.current.children.append(node)
        if tag not in VOID:
            self.current = node

    def handle_startendtag(self, tag, attrs):
        self.current.children.append(Node(tag, attrs, self.current))

    def handle_endtag(self, tag):
        node = self.current
        while node is not None and node.tag != tag:
            node = node.parent
        if node is not None and node.parent is not None:
            self.current = node.parent

    def handle_data(self, data):
        self.current.children.append(data)


def parse_html(text):
    builder = TreeBuilder()
    builder.feed(text)
    builder.close()
    return builder.root


def _text(node, parts):
    for child in node.children:
        if isinstance(child, str):
            parts.append(child)
        elif child.tag == "cite" or child.has_class("ltx_cite"):
            parts.append("[CIT]")
        elif child.tag == "math" or child.has_class("ltx_equation") or child.has_class("ltx_equationgroup"):
            parts.append(" [EQ] ")
        elif child.has_class("ltx_note") or child.has_class("ltx_tag") or child.tag in ("script", "style", "figure"):
            continue
        else:
            _text(child, parts)


def node_text(node):
    parts = []
    _text(node, parts)
    text = " ".join("".join(parts).split())
    return CIT_WRAP.sub("[CIT]", CIT_RUN.sub("[CIT]", text))


def _find_all(node, pred, stop=None):
    """Yield the descendants that match pred, in document order. Do not enter a node where stop is true."""
    for child in node.children:
        if isinstance(child, str):
            continue
        if pred(child):
            yield child
        if stop is not None and stop(child):
            continue
        for found in _find_all(child, pred, stop):
            yield found


def is_section(node):
    return node.tag == "section" or any(node.has_class(c) for c in SECTION_CLASSES)


def is_skipped(node):
    return node.tag == "figure" or any(node.has_class(c) for c in SKIP_CLASSES)


def is_para(node):
    return node.tag == "p" and node.has_class("ltx_p")


def _section_or_skipped(node):
    return is_section(node) or is_skipped(node)


def _paragraphs(node, stop):
    return [t for t in (node_text(p) for p in _find_all(node, is_para, stop)) if t]


def _heading(section):
    for child in section.children:
        if not isinstance(child, str) and re.match(r"^h[1-6]$", child.tag):
            return node_text(child)
    return ""


def _sections(node):
    return [s for s in _find_all(node, is_section, _section_or_skipped) if not is_skipped(s)]


def read_arxiv_html(data, meta):
    """Return the paper file of a LaTeXML page, or raise ReaderError."""
    text = data.decode("utf-8", errors="replace") if isinstance(data, bytes) else data
    root = parse_html(text)
    article = next(_find_all(root, lambda n: n.has_class("ltx_document")), None)
    if article is None:
        raise ReaderError("no LaTeXML document element")
    abstract = []
    for block in _find_all(article, lambda n: n.has_class("ltx_abstract")):
        abstract = _paragraphs(block, None)
        break
    sections = []
    lead = _paragraphs(article, _section_or_skipped)
    for sec in _sections(article):
        heading = _heading(sec)
        kind = heading_kind(heading) if heading else "other"
        if kind == "drop":
            continue
        subsections = [{"heading": _heading(sub), "paragraphs": _paragraphs(sub, is_skipped)}
                       for sub in _sections(sec) if heading_kind(_heading(sub)) != "drop"]
        sections.append({"heading": heading, "kind": kind, "paragraphs": _paragraphs(sec, _section_or_skipped),
                         "subsections": subsections})
    if lead and not sections:
        sections = [{"heading": "", "kind": "body", "paragraphs": lead, "subsections": []}]
    if meta.get("group") != "essay":
        infer_results(sections)
    legends = []
    for figure in _find_all(article, lambda n: n.tag == "figure"):
        for caption in _find_all(figure, lambda n: n.tag == "figcaption"):
            caption_text = node_text(caption)
            if caption_text:
                legends.append(caption_text)
    paper = new_paper(meta)
    paper.update({"article_type": "arxiv", "jats_manuscript": False, "abstract": abstract,
                  "sections": sections, "legends": legends})
    return finish_paper(paper)
