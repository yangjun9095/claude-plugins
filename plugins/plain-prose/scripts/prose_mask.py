"""Hide the parts of a file that are not prose.

A detector and a rewrite then touch prose only. `mask(text, fmt)` finds the spans that
are not prose in LaTeX, Markdown or plain text. It replaces span number i with the
placeholder U+E000 + str(i) + U+E001. `unmask` puts the original text back.

Each scanner reads the text once from left to right, so spans never overlap. When two
constructs can start at the same offset, the first one in this list wins.
LaTeX: comment, environment masked whole, math, environment token, command with a prose
argument, cite or ref or url command, other command, control symbol.
A `\\begin{name}` token hides its arguments. These are the brace groups that follow it with no
blank, and the bracket groups without a blank. Examples are `[t]` and `{0.45\\textwidth}`. A
bracket group ends at its balanced close, so `[a[b]c]` and `[label={[a]}]` hide whole. A brace
group that does not close on its line hides to the end of that line.
Markdown (in prose_mask_md.py): front matter, fenced code, reference definition, table
row, heading marker, list marker; then inline code, math, HTML, link target.
After the scan, the visible text gets a second pass. It masks URLs, DOIs and email
addresses in all formats, citations in Markdown and text, and the characters U+E000
and U+E001 of the input. In Markdown, every bracket group with an `@` and a key is a cite span, as
in `[@a]`, `[see @a, p. 3]` and `[@a; @b]`. So is a link whose text is `@name`, as in
`[@user](https://example.org/user)`. That errs on the quiet side.

The masker works from the safe side. A construct that it cannot parse hides more text,
so the worst result is a missed hit. Hidden text ends at the end of the file (unclosed
environment), the paragraph (unclosed `$`) or the line (unclosed brace). The scanners
never raise on a str. Each search for a closing mark is bounded or cached, so a long line
stays linear.

LaTeX constructs that stay visible on purpose:
- A bracket group after `\\begin{name}` that holds white space (a space, a tab, a line end),
  such as the theorem title `[Cauchy's theorem]`. A bracket inside does not change this, so
  `[a [b] c]` stays visible.
- A bracket group after `\\begin{name}` with no balanced close, such as `[a}b]`.
- The entries of `thebibliography`. Only the `\\bibitem{key}` command is masked.
- The content of `\\begin{comment}`. Only the two environment tokens are masked.
- Every entry of a `.bib` file, which `detect_format` sends to the LaTeX scanner.
"""
import os
import re
from collections import namedtuple

from prose_mask_core import CLOSE, EOL, ESCAPE_OR_DOLLAR, OPEN, PARA_BREAK, NextMatch, Span, skip_blanks
from prose_mask_md import scan_markdown

Masked = namedtuple("Masked", "text spans original")

KINDS = ("comment", "math", "env", "command", "cite", "ref", "url", "code", "markup")

PROSE_ARG_COMMANDS = tuple(
    "section subsection subsubsection paragraph subparagraph chapter caption footnote "
    "emph textit textbf textsc textrm underline title".split())
CITE_COMMANDS = tuple(
    "cite citep citet citeauthor citeyear parencite textcite autocite nocite "
    "citealp citealt Citep Citet Citealp footcite supercite citeyearpar citenum cites parencites "
    "textcites Parencite Textcite citetitle".split())
REF_COMMANDS = tuple("ref eqref autoref cref Cref pageref vref".split())
_LITERAL_ENVS = ("verbatim", "lstlisting", "minted")
_WHOLE_ENVS = _LITERAL_ENVS + (
    "tikzpicture", "tabular", "tabularx", "longtable", "equation", "align", "gather", "multline",
    "eqnarray", "displaymath", "math", "split", "alignat", "flalign", "dmath", "IEEEeqnarray", "empheq")
_KIND_OF_COMMAND = dict(
    [(name, "cite") for name in CITE_COMMANDS] + [(name, "ref") for name in REF_COMMANDS] +
    [("label", "ref"), ("url", "url"), ("href", "url")])

_PLACEHOLDER = re.compile(OPEN + r"(\d+)" + CLOSE)

_LATEX_STOP = re.compile(r"[\\%$]")
_LATEX_COMMAND = re.compile(r"\\([A-Za-z]+)\*?")
_LATEX_ENV = re.compile(r"\\(begin|end)[ \t]*\{([^{}\r\n]*)\}")
_BRACKET_TOKEN = re.compile(r"\\[\s\S]|[%{}\[\]]")
_BLANK = re.compile(r"\s")
_PRIVATE_USE = re.compile("[" + OPEN + CLOSE + "]")

_TARGET = r"[^\s<>\"{}|\\^`\[\]]+"
_URL = re.compile(r"(?:(?:https?|ftp)://|\bwww\.)" + _TARGET)
_DOI = re.compile(r"\b10\.\d{4,9}/" + _TARGET)
_EMAIL_CHARS = frozenset("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
_EMAIL_LOCAL = _EMAIL_CHARS | frozenset("._%+-")
_EMAIL_DOMAIN = _EMAIL_CHARS | frozenset(".-")
_CITE_NUMBER = re.compile("\\[[ \t]*\\d{1,4}(?:[ \t]*[-\u2013\u2014,][ \t]*\\d{1,4})*[ \t]*\\]")
_AUTHOR = "[A-Z][A-Za-z\u00c0-\u024f'\u2019-]*"
_AUTHOR_YEAR = (_AUTHOR + r"(?:\s+et\s+al\.?|\s+(?:and|&)\s+" + _AUTHOR + r")?,?\s+(?:1[5-9]|20)\d\d[a-z]?")
_PANDOC_AT = re.compile(r"(?<![A-Za-z0-9_])-?@[A-Za-z0-9_]")
_BRACKET_OR_LINE_END = re.compile(r"[\[\]\r\n]")
_CITE_AUTHOR_YEAR = re.compile(
    r"\((?:(?:see|see also|e\.g\.,?|cf\.)\s+)?" + _AUTHOR_YEAR + r"(?:\s*;\s*" + _AUTHOR_YEAR + r")*\)")


def detect_format(path):
    """Return "latex", "markdown" or "text" from the extension of the path."""
    ext = os.path.splitext(os.fspath(path))[1].lower()
    if ext in (".tex", ".sty", ".cls", ".bib"):
        return "latex"
    if ext in (".md", ".markdown"):
        return "markdown"
    return "text"


def _bracket_table(text):
    """Map the offset of each `{` and `[` to the offset of its closing mark.

    Escaped marks and marks in comments do not count. A `]` inside a brace group,
    or an unmatched mark, has no entry.
    """
    match, stack, pos = {}, [], 0
    search = _BRACKET_TOKEN.search
    while True:
        m = search(text, pos)
        if m is None:
            return match
        i, tok = m.start(), m.group()
        pos = m.end()
        if tok == "%":
            e = EOL.search(text, pos)
            pos = e.start() if e else len(text)
        elif tok == "{" or tok == "[":
            stack.append(i)
        elif tok == "}":
            while stack:
                j = stack.pop()
                if text[j] == "{":
                    match[j] = i
                    break
        elif tok == "]" and stack and text[stack[-1]] == "[":
            match[stack.pop()] = i


def _math_close(text, pos, end, closer):
    """Offset after the closing mark of a LaTeX math span, or -1."""
    while True:
        m = ESCAPE_OR_DOLLAR.search(text, pos, end)
        if m is None:
            return -1
        tok = m.group()
        if tok == closer == "$":
            return m.end()
        if tok == "$" and closer == "$$" and text.startswith("$$", m.start(), end):
            return m.start() + 2
        if tok == closer:
            return m.end()
        pos = m.end()


_ENV_PATTERNS = {}


def _env_end(text, name, pos):
    """Offset after the matching `\\end{name}`, or the end of the text when it is open."""
    pat = _ENV_PATTERNS.get(name)
    literal = (name[:-1] if name.endswith("*") else name) in _LITERAL_ENVS
    if pat is None:
        key = re.escape(name)
        if literal:
            pat = re.compile(r"\\end[ \t]*\{" + key + r"\}")
        else:
            pat = re.compile(r"\\(begin|end)[ \t]*\{" + key + r"\}|\\[\s\S]|%[^\r\n]*")
        _ENV_PATTERNS[name] = pat
    if literal:
        m = pat.search(text, pos)
        return m.end() if m else len(text)
    depth = 1
    while True:
        m = pat.search(text, pos)
        if m is None:
            return len(text)
        pos = m.end()
        if m.group(1) == "begin":
            depth += 1
        elif m.group(1) == "end":
            depth -= 1
            if depth == 0:
                return pos


class _LatexScanner(object):
    def __init__(self, text):
        self.text, self.n = text, len(text)
        self.match = _bracket_table(text)
        self.spans = []
        self.closers = []
        self.eol = NextMatch(EOL, text)
        self.blank = NextMatch(_BLANK, text)
        self.para_end = NextMatch(PARA_BREAK, text)
        self.body_start = None

    def add(self, start, end, kind):
        self.spans.append(Span(start, end, kind))
        return end

    def scan(self):
        text, n, closers = self.text, self.n, self.closers
        i = 0
        while i < n:
            m = _LATEX_STOP.search(text, i)
            stop = m.start() if m else n
            while closers and closers[-1] < stop:
                c = closers.pop()
                if c >= i:
                    self.add(c, c + 1, "command")
            if m is None:
                break
            ch = text[stop]
            if ch == "%":
                i = self.add(stop, self.eol(stop), "comment")
            elif ch == "$":
                if text.startswith("$$", stop):
                    i = self.math(stop, stop + 2, "$$")
                else:
                    i = self.math(stop, stop + 1, "$")
            else:
                i = self.backslash(stop)
        if self.body_start is not None:
            kept = [s for s in self.spans if s.start >= self.body_start]
            self.spans = [Span(0, self.body_start, "env")] + kept
        return self.spans

    def math(self, start, open_end, closer):
        stop = self.para_end(start)
        close = _math_close(self.text, open_end, stop, closer)
        return self.add(start, close if close >= 0 else max(stop, open_end), "math")

    def backslash(self, i):
        text, n = self.text, self.n
        if i + 1 >= n:
            return self.add(i, n, "command")
        if text[i + 1] in "([":
            return self.math(i, i + 2, "\\)" if text[i + 1] == "(" else "\\]")
        env = _LATEX_ENV.match(text, i)
        if env:
            return self.environment(i, env)
        m = _LATEX_COMMAND.match(text, i)
        if m is None:
            return self.add(i, i + (1 if text[i + 1] in "\r\n" else 2), "command")
        name, end = m.group(1), m.end()
        if name == "verb":
            return self.verb(i, end)
        if name in PROSE_ARG_COMMANDS:
            return self.prose_command(i, end)
        return self.other_command(i, end, _KIND_OF_COMMAND.get(name, "command"))

    def environment(self, i, m):
        name, end = m.group(2).strip(), m.end()
        base = name[:-1] if name.endswith("*") else name
        if m.group(1) == "begin" and base in _WHOLE_ENVS:
            return self.add(i, _env_end(self.text, name, end), "env")
        if name == "document":
            if m.group(1) == "begin" and self.body_start is None:
                self.body_start = end
            elif m.group(1) == "end" and self.body_start is not None:
                return self.add(i, self.n, "env")
        elif m.group(1) == "begin":
            end = self.env_arguments(end)
        return self.add(i, end, "env")

    def env_arguments(self, end):
        """Offset after the arguments of `\\begin{name}` that the masker hides, or `end`.

        A group hides when it follows with no blank between. A brace group that does not close on its
        line hides to the end of that line. A bracket group hides through its balanced close when no
        blank comes before that close. A line end is a blank, so the close is on the same line.
        Otherwise the bracket group is a title, and it stays visible. The balanced table skips escaped
        marks and comments, so a `%` leaves the group open. The blank search is cached, so a run of
        calls costs linear time.
        """
        text, match = self.text, self.match
        p = end
        while p < self.n and text[p] in "{[":
            close = match.get(p)
            if text[p] == "{":
                line_end = self.eol(p)
                if close is None or close >= line_end:
                    return line_end
            elif close is None or self.blank(p) < close:
                break
            p = close + 1
        return p

    def verb(self, i, end):
        text = self.text
        delimiter = text[end:end + 1]
        if delimiter == "" or delimiter in " \t\r\n":
            return self.add(i, end, "command")
        line_end = self.eol(end)
        close = text.find(delimiter, end + 1, line_end)
        return self.add(i, close + 1 if close >= 0 else line_end, "code")

    def prose_command(self, i, end):
        text, match = self.text, self.match
        p = skip_blanks(text, end)
        if text.startswith("[", p) and p in match:
            p = skip_blanks(text, match[p] + 1)
        if not text.startswith("{", p):
            return self.add(i, end, "command")
        if p not in match:
            return self.add(i, self.eol(p), "command")
        self.closers.append(match[p])
        return self.add(i, p + 1, "command")

    def other_command(self, i, end, kind):
        text, match = self.text, self.match
        stop = end
        while True:
            p = skip_blanks(text, stop)
            if text.startswith("{", p):
                if p not in match:
                    return self.add(i, self.eol(p), kind)
            elif not (text.startswith("[", p) and p in match):
                return self.add(i, stop, kind)
            stop = match[p] + 1


def _trimmed(url):
    """Length of the URL without trailing punctuation and an unbalanced `)`."""
    opens, closes, end = url.count("("), url.count(")"), len(url)
    while end:
        c = url[end - 1]
        if c in ".,;:!?'\"":
            end -= 1
        elif c == ")" and closes > opens:
            end, closes = end - 1, closes - 1
        else:
            break
    return end


def _emails(seg):
    found, at = [], seg.find("@")
    while at >= 0:
        start, end = at, at + 1
        while start > 0 and seg[start - 1] in _EMAIL_LOCAL:
            start -= 1
        while end < len(seg) and seg[end] in _EMAIL_DOMAIN:
            end += 1
        domain = seg[at + 1:end].rstrip(".-")
        end = at + 1 + len(domain)
        tld = domain.rpartition(".")[2]
        if start < at and "." in domain and len(tld) >= 2 and tld.isalpha():
            found.append((start, end, "url"))
        at = seg.find("@", max(end, at + 1))
    return found


def _pandoc_cites(seg):
    """Return (start, end, "cite") for each bracket group that holds an `@` and a key.

    A group has no bracket inside and stays on one line. A `[` with no closing bracket on its line is
    skipped, and the scan goes on after it. Each step reads to the next bracket or line end, so the
    scan costs linear time.
    """
    found, i = [], seg.find("[")
    while i >= 0:
        stop = _BRACKET_OR_LINE_END.search(seg, i + 1)
        if stop is None:
            break
        if stop.group() == "]":
            if _PANDOC_AT.search(seg, i + 1, stop.start()):
                found.append((i, stop.end(), "cite"))
            i = seg.find("[", stop.end())
        else:
            i = seg.find("[", i + 1)
    return found


def _inline_spans(seg, base, fmt):
    """Spans in a stretch of visible text: placeholder characters, URLs, emails, citations."""
    found = [(m.start(), m.end(), "markup") for m in _PRIVATE_USE.finditer(seg)]
    for pattern in (_URL, _DOI):
        found.extend((m.start(), m.start() + _trimmed(m.group()), "url") for m in pattern.finditer(seg))
    found.extend(_emails(seg))
    if fmt != "latex":
        for pattern in (_CITE_NUMBER, _CITE_AUTHOR_YEAR):
            found.extend((m.start(), m.end(), "cite") for m in pattern.finditer(seg))
        if fmt == "markdown":
            found.extend(_pandoc_cites(seg))
    found.sort(key=lambda f: (f[0], f[0] - f[1]))
    out, last = [], 0
    for start, end, kind in found:
        if start >= last:
            out.append(Span(base + start, base + end, kind))
            last = end
    return out


def _raw_spans(text, fmt):
    """The spans of the text, sorted and non-overlapping, before the final safety pass."""
    if fmt == "latex":
        spans = _LatexScanner(text).scan()
    elif fmt == "markdown":
        spans = scan_markdown(text)
    elif fmt == "text":
        spans = []
    else:
        raise ValueError("unknown format: %r" % (fmt,))
    out, pos = [], 0
    for span in spans + [Span(len(text), len(text), "markup")]:
        if span.start > pos:
            out.extend(_inline_spans(text[pos:span.start], pos, fmt))
        if span.end > span.start:
            out.append(span)
        pos = max(pos, span.end)
    return out


def _normalize(spans, text):
    """Keep the spans sorted and disjoint, and keep every CRLF pair outside the span edges."""
    out, last = [], 0
    for span in sorted(spans):
        start, end = max(span.start, last), span.end
        if text[start - 1:start + 1] == "\r\n" and start > 0:
            start += 1
        if text[end - 1:end + 1] == "\r\n" and end > 0:
            end -= 1
        if start < end:
            out.append(Span(start, end, span.kind))
            last = end
    return out


def mask(text, fmt):
    """Return a Masked value for the text. `fmt` is "latex", "markdown" or "text"."""
    spans = _normalize(_raw_spans(text, fmt), text)
    parts, pos = [], 0
    for k, span in enumerate(spans):
        parts.append(text[pos:span.start])
        parts.append(OPEN + str(k) + CLOSE)
        pos = span.end
    parts.append(text[pos:])
    return Masked("".join(parts), spans, text)


def piece(masked, i):
    """Return the original text of span i."""
    span = masked.spans[i]
    return masked.original[span.start:span.end]


def unmask(masked):
    """Put the original text of each span back in place of its placeholder."""
    return _PLACEHOLDER.sub(lambda m: piece(masked, int(m.group(1))), masked.text)


def offset_map(masked):
    """Map each offset of the masked text, and its end, to an offset of the original.

    A character inside a placeholder maps to the start of its span. The offset
    after a placeholder maps to the end of its span.
    """
    out, pos = [], 0
    for k, span in enumerate(masked.spans):
        out.extend(range(pos, span.start))
        out.extend([span.start] * len(OPEN + str(k) + CLOSE))
        pos = span.end
    out.extend(range(pos, len(masked.original) + 1))
    return out
