#!/usr/bin/env python3
"""Mechanical prose checks for LaTeX manuscripts. Reports hits and never edits a file.

Usage: python3 audit.py [--spelling oxford|american|off] [--terms PATH] FILE...
Exit code: 1 when any rule except todo-cite has a hit, 2 on an error (a read error,
a bad terms file, or any other failure), else 0.
"""
import argparse
import bisect
import io
import json
import re
import sys
from collections import Counter
from pathlib import Path

DEFAULT_TERMS = Path(__file__).resolve().parent.parent / "audit_terms.json"

COMMENT = re.compile(r"(?<!\\)%.*$")
BLOCK_BEGIN = re.compile(r"\\begin\{(comment|verbatim|lstlisting)\}")
# Commands whose braced argument names something. The argument is not prose.
IDENT_ARG = re.compile(
    r"\\(?:begin|end|label|ref|cref|Cref|autoref|eqref|cite[A-Za-z]*|includegraphics|input|"
    r"include|usepackage|bibliography|bibliographystyle|url|href|pagestyle|documentclass)"
    r"\*?(?:\[[^\]]*\])*\{[^}]*\}"
)
COMMAND = re.compile(r"\\[A-Za-z]+\*?")
# A sectioning command that fills its line. Its title is not prose, so it must not start a
# paragraph. The title may hold one level of nested braces, such as \emph{...}.
HEADING = re.compile(
    r"(?m)^[ \t]*\\(?:part|chapter|section|subsection|subsubsection|paragraph|subparagraph)\*?"
    r"(?:\[[^\]]*\])?\{(?:[^{}\n]|\{[^{}\n]*\})*\}[ \t]*$"
)
FIG_REF = re.compile(r"\bFigs?\.\s*\\(?:ref|cref|Cref|autoref)\b")
TODO_CITE = re.compile(r"\\todo\{\s*cite[^}\n]*", re.I)
EMDASH = re.compile(r"---|\u2014")
WORD = re.compile(r"[A-Za-z][A-Za-z']*")


def blank(text):
    """Replace every character except a newline with a space, so offsets stay valid."""
    return re.sub(r"[^\n]", " ", text)


def strip_comments(text):
    """Blank % comments and comment, verbatim and lstlisting blocks."""
    out, block = [], None
    for line in text.split("\n"):
        stripped = line.strip()
        if block is None:
            match = BLOCK_BEGIN.match(stripped)
            if match:
                block = match.group(1)
                out.append(blank(line))
            else:
                out.append(COMMENT.sub(lambda m: blank(m.group(0)), line))
        else:
            if stripped.startswith("\\end{%s}" % block):
                block = None
            out.append(blank(line))
    return "\n".join(out)


def mask_commands(text):
    """Blank LaTeX commands and identifier arguments. What is left is prose."""
    text = IDENT_ARG.sub(lambda m: blank(m.group(0)), text)
    return COMMAND.sub(lambda m: blank(m.group(0)), text)


def paragraphs(masked):
    """Yield (offset, text) for each run of non-blank lines."""
    pos, start, buf = 0, None, []
    for line in masked.split("\n"):
        if line.strip():
            if start is None:
                start = pos
            buf.append(line)
        elif start is not None:
            yield start, "\n".join(buf)
            start, buf = None, []
        pos += len(line) + 1
    if start is not None:
        yield start, "\n".join(buf)


def check_text(raw, terms, spelling):
    """Return (line, rule, text) for each occurrence, sorted by offset then rule."""
    clean = strip_comments(raw)
    masked = mask_commands(clean)
    starts = [0] + [m.end() for m in re.finditer("\n", masked)]
    hits = {}

    def add(offset, rule, text):
        # One entry per (offset, rule), so repeated hits on one line each keep a row.
        hits[(offset, rule)] = " ".join(text.split())

    for item in terms["vocabulary"]:
        for m in re.finditer(item["pattern"], masked, re.I):
            add(m.start(), "vocab:" + item["term"], m.group(0))
    for item in terms["constructions"]:
        for m in re.finditer(item["pattern"], masked, re.I | re.S):
            add(m.start(), "construction:" + item["term"], m.group(0))
    initial = {w.lower() for w in terms["paragraph_initial"]}
    # Blank each heading line so the prose under it starts a paragraph. Offsets stay valid
    # because blank() keeps the length. The vocabulary checks above still see the heading words.
    body = mask_commands(HEADING.sub(lambda m: blank(m.group(0)), clean))
    for offset, para in paragraphs(body):
        lead = para.lstrip()
        first = re.match(r"[A-Za-z]+", lead)
        if first and first.group(0).lower() in initial:
            add(offset + len(para) - len(lead), "construction:paragraph-initial", first.group(0))
        dashes = list(EMDASH.finditer(para))
        if len(dashes) > 1:
            add(offset + dashes[1].start(), "emdash:paragraph", "%d em dashes in one paragraph" % len(dashes))
    words = len(WORD.findall(masked))
    total = len(EMDASH.findall(masked))
    allowed = max(1, words // 400)
    if total > allowed:
        add(0, "emdash:density", "%d em dashes in %d words (allowed %d)" % (total, words, allowed))
    if spelling != "off":
        for item in terms["spelling"][spelling]:
            for m in re.finditer(item["pattern"], masked, re.I):
                add(m.start(), "spelling:" + item["term"], m.group(0))
    for m in FIG_REF.finditer(clean):
        add(m.start(), "fig-ref", m.group(0))
    for m in TODO_CITE.finditer(clean):
        add(m.start(), "todo-cite", m.group(0))
    return [(bisect.bisect_right(starts, offset), rule, text)
            for (offset, rule), text in sorted(hits.items())]


TERM_KEYS = ("vocabulary", "constructions", "paragraph_initial", "spelling")
SPELLING_KEYS = ("oxford", "american")


def validate_terms(terms):
    """Raise ValueError when the terms file lacks a key or holds a pattern that does not compile."""
    if not isinstance(terms, dict):
        raise ValueError("top level must be a JSON object")
    for key in TERM_KEYS:
        if key not in terms:
            raise ValueError("missing key %r" % key)
    if not isinstance(terms["spelling"], dict):
        raise ValueError("spelling must be a JSON object")
    for key in SPELLING_KEYS:
        if key not in terms["spelling"]:
            raise ValueError("missing key spelling.%s" % key)
    groups = [terms["vocabulary"], terms["constructions"],
              terms["spelling"]["oxford"], terms["spelling"]["american"]]
    try:
        for group in groups:
            for item in group:
                re.compile(item["pattern"], re.I)
    except KeyError:
        raise ValueError("an entry has no pattern")
    except TypeError as exc:
        raise ValueError("malformed entry: %s" % exc)
    except re.error as exc:
        raise ValueError("bad pattern: %s" % exc)


def main(argv=None):
    # On Python 3.6 a C locale encodes stdout as ASCII. Replace unencodable characters
    # instead of crashing mid-run.
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding=sys.stdout.encoding or "utf-8",
                                  errors="replace", line_buffering=True)
    try:
        ap = argparse.ArgumentParser(description="Mechanical prose checks for LaTeX manuscripts.")
        ap.add_argument("files", nargs="+")
        ap.add_argument("--spelling", choices=["oxford", "american", "off"], default="off")
        ap.add_argument("--terms", default=str(DEFAULT_TERMS))
        args = ap.parse_args(argv)
        try:
            terms = json.loads(Path(args.terms).read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            print("error: cannot read terms file: %s" % exc, file=sys.stderr)
            return 2
        try:
            validate_terms(terms)
        except ValueError as exc:
            print("error: bad terms file: %s" % exc, file=sys.stderr)
            return 2
        counts = Counter()
        for name in args.files:
            try:
                raw = Path(name).read_text(encoding="utf-8-sig", errors="replace")
            except OSError as exc:
                print("error: cannot read %s: %s" % (name, exc), file=sys.stderr)
                return 2
            for line, rule, text in check_text(raw, terms, args.spelling):
                print("%s:%d: %s: %s" % (name, line, rule, text))
                counts[rule.split(":")[0]] += 1
        print("--- counts ---")
        for rule in sorted(counts):
            print("%s: %d" % (rule, counts[rule]))
        if not counts:
            print("no hits")
        return 1 if any(rule != "todo-cite" for rule in counts) else 0
    except Exception as exc:
        print("error: %s" % (str(exc) or type(exc).__name__), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
