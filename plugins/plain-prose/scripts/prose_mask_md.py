"""Markdown rules for prose_mask: the scanner that `mask(text, "markdown")` runs.

It reads the text once from left to right. At the start of each line it masks the
block marker: front matter, fenced code, reference definition, table row, heading
marker or list marker. Inside a line it masks inline code, math, HTML and link
targets.

Markdown constructs that stay visible on purpose:
- Indented code blocks. A four-space line can continue a list item, so a guess can hide prose.
- Blockquote markers (`>`).
- Thematic breaks (`---`, `***`) and setext underlines (`===`, `---`).
- Task-list boxes (`[ ]`, `[x]`) after a list marker.
- Emphasis marks (`*`, `_`, `**`).
"""
import re

from prose_mask_core import ESCAPE_OR_DOLLAR, EOL, PARA_BREAK, NextMatch, Span, skip_blanks

_MD_SPECIAL = re.compile(r"[`$<\\\n]|\]\(")
_MD_FENCE = re.compile(r"(`{3,}|~{3,})[^\r\n]*")
_MD_REF_DEFINITION = re.compile(r"\[(?!\^)[^\]\r\n]+\]:[ \t]*\S[^\r\n]*")
_MD_HEADING = re.compile(r"#{1,6}(?:[ \t]+|(?=[\r\n]|\Z))")
_MD_LIST = re.compile(r"([-*+]|\d{1,3}[.)])(?=[ \t])")
_MD_TAG = re.compile(r"</?[A-Za-z][A-Za-z0-9-]*(?=[\s/>])[^<>]*>")
_MD_FRONT_START = re.compile(r"---[ \t]*\r?\n")
_MD_FRONT_END = re.compile(r"^(---[ \t]*)\r?$", re.M)
_BACKTICKS = re.compile(r"`+")
_CODE_CLOSERS = {}


def _fence_close(char, size):
    return re.compile("^[ \t]*" + re.escape(char) + "{%d,}[ \t]*(?=\r?$)" % size, re.M)


def _markdown_block(text, ls, eol, add):
    """Mask the block marker of the line that starts at ls. Return where to go on."""
    ci = skip_blanks(text, ls)
    if ci >= len(text):
        return ci
    c, indent = text[ci], ci - ls
    if c in "`~":  # any indent: a fence under a list item sits four or more spaces in
        m = _MD_FENCE.match(text, ci)
        if m and not (c == "`" and "`" in text[m.end(1):m.end()]):
            close = _fence_close(c, len(m.group(1))).search(text, m.end())
            return add(ci, close.end() if close else len(text), "code")
    elif c == "[" and indent <= 3:
        m = _MD_REF_DEFINITION.match(text, ci)
        if m:
            return add(ci, m.end(), "markup")
    elif c == "|":
        return add(ci, eol(ci), "markup")
    elif c == "#" and indent <= 3:
        m = _MD_HEADING.match(text, ci)
        if m:
            return add(ci, m.end(), "markup")
    elif c in "-*+0123456789":
        m = _MD_LIST.match(text, ci)
        if m:
            return add(ci, m.end(1), "markup")
    return ci


def _markdown_math_close(text, pos, end, closer):
    """Offset after the closing `$` or `$$` of a Markdown math span, or -1."""
    while True:
        m = ESCAPE_OR_DOLLAR.search(text, pos, end)
        if m is None:
            return -1
        if m.group() == "$":
            s = m.start()
            if closer == "$$":
                if text.startswith("$$", s, end):
                    return s + 2
            elif not text[s - 1].isspace() and not text[m.end():m.end() + 1].isdigit():
                return m.end()
        pos = m.end()


def _link_target_end(text, p, line_end):
    """Offset after the `(...)` that starts at p, with nested parentheses. 0 if none."""
    first = text.find(")", p + 1, line_end)
    if first < 0:
        return 0
    depth, j, c = 1, p + 1, first
    for _ in range(4):
        depth += text.count("(", j, c) - 1
        if depth <= 0:
            return c + 1
        j = c + 1
        c = text.find(")", j, line_end)
        if c < 0:
            break
    return first + 1


def scan_markdown(text):
    """Return the Markdown spans of the text, sorted and non-overlapping."""
    n, spans = len(text), []

    def add(start, end, kind):
        spans.append(Span(start, end, kind))
        return end

    eol, para = NextMatch(EOL, text), NextMatch(PARA_BREAK, text)
    failed = {}
    i, line_start = 0, True
    front = _MD_FRONT_START.match(text)
    close = _MD_FRONT_END.search(text, front.end()) if front else None
    if close:
        i, line_start = add(0, close.end(1), "markup"), False
    while i < n:
        if line_start:
            i, line_start = _markdown_block(text, i, eol, add), False
            if i >= n:
                break
        m = _MD_SPECIAL.search(text, i)
        if m is None:
            break
        i, ch = m.start(), text[m.start()]
        if ch == "\n":
            i, line_start = i + 1, True
        elif ch == "\\":
            i += 1 if text[i + 1:i + 2] in ("", "\n") else 2
        elif ch == "`":
            i = _inline_code(text, i, para(i), add)
        elif ch == "$":
            i = _inline_math(text, i, para(i), failed, add)
        elif ch == "<":
            i = _html(text, i, add)
        else:
            line_end = eol(i)
            end = 0 if failed.get("target") == line_end else _link_target_end(text, i + 1, line_end)
            if end:
                i = add(i + 1, end, "url")
            else:
                failed["target"] = line_end
                i += 1
    return spans


def _code_close(size):
    """Pattern for a run of exactly `size` backticks."""
    if size not in _CODE_CLOSERS:
        _CODE_CLOSERS[size] = re.compile("(?<!`)`{%d}(?!`)" % size)
    return _CODE_CLOSERS[size]


def _inline_code(text, i, para_end, add):
    j = _BACKTICKS.match(text, i).end()
    close = _code_close(j - i).search(text, j, para_end)
    return add(i, close.end(), "code") if close else j


def _inline_math(text, i, para_end, failed, add):
    closer = "$$" if text.startswith("$$", i) else "$"
    start = i + len(closer)
    if closer == "$" and text[start:start + 1] in ("", " ", "\t", "\r", "\n"):
        return start
    if failed.get(closer) != para_end:
        end = _markdown_math_close(text, start, para_end, closer)
        if end >= 0:
            return add(i, end, "math")
        failed[closer] = para_end
    return start


def _html(text, i, add):
    if text.startswith("<!--", i):
        close = text.find("-->", i + 4)
        return add(i, len(text) if close < 0 else close + 3, "markup")
    m = _MD_TAG.match(text, i)
    return add(i, m.end(), "markup") if m else i + 1
