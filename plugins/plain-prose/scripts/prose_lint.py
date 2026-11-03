"""Find the writing patterns of plain-prose in LaTeX, Markdown and plain-text files.

Command line: `python3 prose_lint.py PATH... [--format auto|latex|markdown|text]
[--project-dir DIR] [--json] [--windows]`. Output is UTF-8 bytes.

A PATH is a file or a folder. The detector reads a file as given, whatever its extension. A folder
gives every `.tex`, `.md` and `.txt` file under it, sorted by path. The walk skips hidden folders,
`node_modules` and `docs/prose`. With `--format auto` the extension picks the format, and an unknown
extension gives `text`. `--project-dir` names the folder that holds `prose-style.yaml`,
`docs/prose-style.yaml` or `.claude/prose-style.yaml`. It must exist. The default is the working
directory.

Text output has one row for each finding, a summary of the file, one line for each family with a
finding, and the totals. `--json` prints the same data and adds the original offsets of each finding
and of its sentence. `--windows` prints the list of windows and nothing else.

The exit code is 0 for no flagged finding, 1 for at least one, and 2 when the check could not run.
Code 2 covers a bad option, a bad pattern file and a missing project folder. It also covers an
unreadable file or folder, a file with a NUL byte, and a file that is not UTF-8. The message gives
the byte offset. Then stdout stays empty, and the messages go to stderr.

How a file is read.
- The detector masks the text (prose_mask) and runs the rules on the masked sentences (prose_text).
  Every offset maps back to the original text with the offset map. A line ends at a line feed, so CRLF
  needs no special case. U+2028 and a form feed do not start a line.
- A finding gets its offsets from the regex match. If the match ends inside a placeholder, the
  finding ends at the end of the hidden text. `text` is the original text of the finding.
  `sentence_start` and `sentence_end` bound the sentence in the same way.
- A sentence starts at its first line that holds prose. Leading lines that hold only placeholders and
  blanks are no part of it. A comment, a label and the commands of a figure are such lines. A
  placeholder on the line of the first words stays, as an item marker or `\\caption{` does. A leading
  byte order mark (U+FEFF) and the blanks after it are no part of the sentence either.
- A rule sees the sentence without its leading placeholders, blanks, byte order marks (U+FEFF) and
  the marks `>`, `*` and `_`.
  It does not see a trailing run of placeholders, blanks, `*` and `_` either. So `^` matches after an
  item marker or a quote mark. The offsets of a finding still refer to the original text.
- A rule gets `cited` true when its sentence holds a placeholder of a `cite` span.
- A density family counts every finding of the file, info findings too. It reports a finding as
  `flag` when the findings per 1000 words exceed `max_per_1000`, and as `info` otherwise. A rule with
  severity `info` always reports `info`. A file with no word has density 0.
- A structural family reads its params. A finding of a structural check spans one sentence.
  `repeated_openers` flags the run-th sentence of a paragraph that starts like the sentences before
  it, and each next one. The key is the first word in lower case. A word of `ignore` makes the key
  its first `ignored_compare_words` words. The first word of a sentence is the first word after any
  placeholder, so `\\emph{This} gene` starts with `this`.
- `staccato` flags the run-th sentence of a run of sentences of 1 to `max_words` words. A sentence
  with no word breaks the run. A paragraph whose first sentence starts with a `\\caption` command is
  skipped. `question_answer` flags a question when the next sentence of the paragraph starts with a
  word of `answers`. With `skip_paragraph_start` it skips a question that opens its paragraph.
- A heading, an item and an environment end a paragraph and a sentence (see `hard_breaks`).

A window is one sentence that holds a flagged finding. Windows are never merged. A window has the
fields `id`, `file`, `start`, `end`, `before`, `occurrences`, `families` and `hits`. `before` is the
sentence, verbatim. `occurrences` is how often `before` occurs in the file, counted without overlap.
`hits` lists the flagged findings of the sentence. The ids run across all files.

Staccato notes. The check flags only the third sentence of a run, so its window holds the third
fragment. The command widens the window to the run. For a run of more than three fragments, the
command proposes for the first three. The detector run of Step 7 shows what remains.

Known limits. A title such as `[Cauchy's theorem]` forms one sentence with its `\\begin` token. A
trailing line of placeholders stays in the last sentence of a paragraph.
"""
import argparse
import json
import os
import re
import sys
from bisect import bisect_left, bisect_right
from collections import namedtuple
from itertools import groupby

from prose_mask import detect_format, mask, offset_map, piece
from prose_mask_core import CLOSE, OPEN
from prose_patterns import PatternError, load_patterns
from prose_text import paragraphs, split_sentences, word_count, words

Finding = namedtuple(
    "Finding", "family rule_label tier severity line col start end sentence_start sentence_end text strategy")
LintResult = namedtuple("LintResult", "findings words density")

PROG = "prose_lint.py"
FORMATS = ("latex", "markdown", "text")
PROSE_EXTENSIONS = (".tex", ".md", ".txt")
TEXT_LIMIT = 80

_SECTION = re.compile(r"\\(?:chapter|section|subsection|subsubsection|paragraph|subparagraph|title)(?![A-Za-z])")
_ITEM = re.compile(r"\\(?:item|bibitem)(?![A-Za-z])")
_LIST_MARKER = re.compile(r"(?:[-*+]|[0-9]{1,3}[.)])\Z")
_LINE_BLANKS = re.compile("[ \t\ufeff]*")
_MATH_ENV = re.compile(
    r"\\(?:begin|end)[ \t]*\{(?:equation|align|gather|multline|eqnarray|displaymath|math|split|subequations|alignat"
    r"|flalign|dmath|IEEEeqnarray|empheq)\*?\}")
_BEGIN_TOKEN = re.compile(r"\\begin[ \t]*\{[^{}\r\n]*\}\Z")
_OPTIONAL_ARG = re.compile(r"\[[^\[\]\r\n]*\]")
_CAPTION = re.compile(r"\\caption(?![A-Za-z])")
_PLACEHOLDER = OPEN + "[0-9]+" + CLOSE
_LEAD_LINES = re.compile("(?:[ \t\ufeff]*(?:" + _PLACEHOLDER + "[ \t]*)+\r?\n)+[ \t]*")
_LEAD_BOM = re.compile("\ufeff[\ufeff\\s]*")
_LEAD = re.compile("(?:" + _PLACEHOLDER + "|[\\s>*_\ufeff])*")
_QUESTION = re.compile("\\?(?:[\"'\u201d\u2019)\\]*_~]|" + OPEN + "[0-9]+" + CLOSE + ")*\\Z")
_NEWLINES = re.compile(r"\r\n|\r|\n")

# A finding before its severity and its original offsets. `start` and `end` are masked offsets.
_Raw = namedtuple("_Raw", "family label tier severity start end sentence")


def _placeholder_ranges(masked):
    """Return the start offsets and the end offsets of the placeholders in the masked text."""
    starts, ends, pos, original = [], [], 0, 0
    for k, span in enumerate(masked.spans):
        pos += span.start - original
        starts.append(pos)
        pos += len(OPEN) + len(str(k)) + len(CLOSE)
        ends.append(pos)
        original = span.end
    return starts, ends


def hard_breaks(masked):
    """Return the masked-text offsets where a sentence must end although no end mark is there.

    A line whose first span is a LaTeX sectioning command or a Markdown heading marker is a sentence
    of its own. The offsets are its start and its end. A line whose first span is a LaTeX `\\item` or
    `\\bibitem` or a Markdown list marker starts a sentence. The offset is its start.

    A LaTeX environment token or whole environment ends the sentence before it and starts a new one
    after it. The offsets are the start and the end of its placeholder. The end of `\\begin{name}`
    moves past a visible title such as `[Cauchy's theorem]`. A math environment is no break, so an
    equation stays inside its sentence. A plain-text file has no such span and gives an empty list.
    """
    text, found = masked.text, []
    starts, ends = _placeholder_ranges(masked)
    line_start, newline = 0, text.find("\n")
    for k, start in enumerate(starts):
        kind, original = masked.spans[k].kind, piece(masked, k)
        if kind == "env":
            if not _MATH_ENV.match(original):
                after = ends[k]
                if _BEGIN_TOKEN.match(original):
                    argument = _OPTIONAL_ARG.match(text, after)
                    after = argument.end() if argument else after
                found.extend((start, after))
            continue
        while 0 <= newline < start:
            line_start = newline + 1
            newline = text.find("\n", line_start)
        if _LINE_BLANKS.match(text, line_start).end() != start:
            continue
        line_end = len(text) if newline < 0 else newline
        if line_end > line_start and text[line_end - 1] == "\r":
            line_end -= 1
        if kind == "command" and _SECTION.match(original) or kind == "markup" and original.startswith("#"):
            found.extend((line_start, line_end))
        elif kind == "command" and _ITEM.match(original) or kind == "markup" and _LIST_MARKER.match(original):
            found.append(line_start)
    return sorted(set(found))


class Mapper(object):
    """Map an offset of the masked text to an offset of the original text.

    `start(p)` is for the start of a range. Inside a placeholder it gives the start of the hidden
    text. `end(p)` is for the end of a range. Inside a placeholder it gives the end of the hidden
    text, so a range never cuts a hidden piece in half.
    """

    def __init__(self, masked):
        self.map = offset_map(masked)
        self.spans = masked.spans
        self.starts, self.ends = _placeholder_ranges(masked)

    def start(self, offset):
        return self.map[offset]

    def end(self, offset):
        k = bisect_left(self.starts, offset) - 1
        if k >= 0 and offset < self.ends[k]:
            return self.spans[k].end
        return self.map[offset]


class _Sentence(object):
    __slots__ = ("start", "end", "text", "para", "cited", "caption", "words")

    def __init__(self, start, end, text, para, cited, caption):
        self.start, self.end, self.text, self.para = start, end, text, para
        self.cited, self.caption, self.words = cited, caption, None


def _sentences(masked, breaks, mapper):
    """Return the _Sentence list: masked bounds, masked text, paragraph, cited and caption flags.

    A sentence starts at its first line that holds prose. A byte order mark and the blanks after it
    are no part of it. A caption sentence starts with a `\\caption` command.
    """
    text = masked.text
    cuts = paragraphs(text, breaks)
    found, para = [], 0
    for start, end in split_sentences(text, breaks):
        while para + 1 < len(cuts) and cuts[para][1] <= start:
            para += 1
        bom = _LEAD_BOM.match(text, start, end)
        if bom:
            start = bom.end()
        lead = _LEAD_LINES.match(text, start, end)
        if lead:
            start = lead.end()
        first, last = bisect_left(mapper.starts, start), bisect_left(mapper.starts, end)
        cited = any(masked.spans[k].kind == "cite" for k in range(first, last))
        caption = (first < last and mapper.starts[first] == start and masked.spans[first].kind == "command"
                   and bool(_CAPTION.match(piece(masked, first))))
        found.append(_Sentence(start, end, text[start:end], para, cited, caption))
    return found


def _words(sentence):
    if sentence.words is None:
        sentence.words = words(sentence.text)
    return sentence.words


def _first_word(sentence):
    found = _words(sentence)
    return found[0][2].lower() if found else None


def _raw(family, sentence, index):
    return _Raw(family, family.check, family.tier, "flag", sentence.start, sentence.end, index)


def _trail_start(text, lead):
    """Return the offset where the trailing run of placeholders, blanks, `*` and `_` starts.

    The run ends at the end of the text and starts at or after `lead`. The loop reads each
    character once, so a long run costs linear time.
    """
    pos = len(text)
    while pos > lead:
        char = text[pos - 1]
        if char.isspace() or char == "*" or char == "_":
            pos -= 1
        elif char == CLOSE:
            first = pos - 2
            while first >= lead and "0" <= text[first] <= "9":
                first -= 1
            if first == pos - 2 or first < lead or text[first] != OPEN:
                break
            pos = first
        else:
            break
    return pos


def _regex_findings(family, sentences):
    for index, sentence in enumerate(sentences):
        lead = _LEAD.match(sentence.text).end()
        body = sentence.text[lead:_trail_start(sentence.text, lead)]
        for rule in family.rules:
            if rule.fires(body, sentence.cited):
                for m in rule.regex.finditer(body):
                    if m.end() > m.start():
                        yield _Raw(family, rule.label, rule.tier, rule.severity,
                                   sentence.start + lead + m.start(), sentence.start + lead + m.end(), index)


def _by_paragraph(sentences):
    for _, group in groupby(enumerate(sentences), key=lambda pair: pair[1].para):
        yield list(group)


def _repeated_openers(family, sentences):
    params = family.params
    ignore = set(word.lower() for word in params["ignore"])
    for paragraph in _by_paragraph(sentences):
        count, previous = 0, None
        for index, sentence in paragraph:
            found = _words(sentence)
            key = found[0][2].lower() if found else None
            if key in ignore:
                key = tuple(word[2].lower() for word in found[:params["ignored_compare_words"]])
            if key is None or key != previous:
                count = 0 if key is None else 1
            else:
                count += 1
            previous = key
            if count >= params["run"]:
                yield _raw(family, sentence, index)


def _staccato(family, sentences):
    params = family.params
    for paragraph in _by_paragraph(sentences):
        if paragraph[0][1].caption:
            continue
        count = 0
        for index, sentence in paragraph:
            count = count + 1 if 0 < len(_words(sentence)) <= params["max_words"] else 0
            if count == params["run"]:
                yield _raw(family, sentence, index)


def _question_answer(family, sentences):
    params = family.params
    answers = set(word.lower() for word in params["answers"])
    for paragraph in _by_paragraph(sentences):
        for position, (index, sentence) in enumerate(paragraph[:-1]):
            if position == 0 and params["skip_paragraph_start"]:
                continue
            if _QUESTION.search(sentence.text) and _first_word(paragraph[position + 1][1]) in answers:
                yield _raw(family, sentence, index)


_CHECKS = {"repeated_openers": _repeated_openers, "staccato": _staccato, "question_answer": _question_answer}


def _severity(raw, counts, total):
    """Return flag or info. A density family flags only above its threshold."""
    family = raw.family
    if raw.severity == "info":
        return "info"
    if family.mode == "density" and not (total and counts[family.id] * 1000 > family.max_per_1000 * total):
        return "info"
    return "flag"


def lint_text(text, fmt, patterns):
    """Run every enabled family on the text. Return a LintResult.

    `fmt` is latex, markdown or text. The findings come in the order of the text, then in the
    order of the families. All offsets belong to `text`. `density` maps the id of each family with
    a finding to its findings per 1000 words.
    """
    masked = mask(text, fmt)
    breaks = hard_breaks(masked)
    mapper = Mapper(masked)
    sentences = _sentences(masked, breaks, mapper)
    raw = []
    for family in patterns.families:
        check = _CHECKS[family.check] if family.check else _regex_findings
        raw.extend(check(family, sentences))
    total = word_count(masked.text)
    counts = {}
    for item in raw:
        counts[item.family.id] = counts.get(item.family.id, 0) + 1
    density = dict((name, count / total * 1000 if total else 0.0) for name, count in counts.items())
    order = dict((family.id, number) for number, family in enumerate(patterns.families))
    line_starts = [0] + [m.end() for m in re.finditer("\n", text)]
    findings = []
    for item in raw:
        start, end = mapper.start(item.start), mapper.end(item.end)
        sentence = sentences[item.sentence]
        line = bisect_right(line_starts, start)
        findings.append(Finding(
            item.family.id, item.label, item.tier, _severity(item, counts, total), line, start - line_starts[line - 1] + 1,
            start, end, mapper.start(sentence.start), mapper.end(sentence.end), text[start:end], item.family.strategy))
    findings.sort(key=lambda f: (f.start, f.end, order[f.family]))
    return LintResult(findings, total, density)


def windows(findings, text, path, start_id=1):
    """Return one window for each sentence that holds a flagged finding, in the order of the text.

    A window is a dict with `id`, `file`, `start`, `end`, `before`, `occurrences`, `families` and
    `hits`. `start` and `end` bound the sentence in the original text. `before` is that text,
    verbatim. `occurrences` counts how often `before` occurs in `text`, without overlap. `families`
    lists the families in the order of the findings. `hits` holds the flagged findings.
    """
    groups = {}
    for finding in sorted(findings, key=lambda f: (f.start, f.end)):
        if finding.severity == "flag":
            groups.setdefault((finding.sentence_start, finding.sentence_end), []).append(finding)
    found = []
    for number, key in enumerate(sorted(groups), start_id):
        group = groups[key]
        families = []
        for finding in group:
            if finding.family not in families:
                families.append(finding.family)
        found.append({
            "id": "w%03d" % number, "file": path, "start": key[0], "end": key[1], "before": text[key[0]:key[1]],
            "occurrences": text.count(text[key[0]:key[1]]), "families": families,
            "hits": [{"family": f.family, "text": f.text, "line": f.line} for f in group]})
    return found


# Files

def _folder_files(root):
    """Return the prose files under a folder, sorted by path, and the folders that cannot be read.

    The walk skips hidden folders, `node_modules` and the proposal folder `docs/prose`.
    """
    found, problems = [], []

    def failed(error):
        problems.append("cannot read %s: %s." % (error.filename or root, error.strerror or error))

    for folder, names, files in os.walk(root, onerror=failed):
        here = os.path.basename(os.path.abspath(folder))
        names[:] = [name for name in names
                    if not name.startswith(".") and name != "node_modules" and not (here == "docs" and name == "prose")]
        found.extend(os.path.join(folder, name) for name in files if os.path.splitext(name)[1].lower() in PROSE_EXTENSIONS)
    return sorted(found), problems


def _collect(paths):
    """Return the files to read, and the problems with the paths."""
    files, problems = [], []
    for path in paths:
        if os.path.isdir(path):
            found, unreadable = _folder_files(path)
            files.extend(found)
            problems.extend(unreadable)
            if not found and not unreadable:
                problems.append("%s holds no .tex, .md or .txt file." % path)
        else:
            files.append(path)
    return files, problems


def _read(path):
    """Return (text, None) or (None, problem). A NUL byte or a byte that is not UTF-8 is a problem."""
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError as error:
        return None, "cannot read %s: %s." % (path, error.strerror or error)
    nul = data.find(b"\x00")
    if nul >= 0:
        return None, "%s is a binary file: it holds a NUL byte at byte offset %d." % (path, nul)
    try:
        return data.decode("utf-8"), None
    except UnicodeDecodeError as error:
        return None, "%s is not valid UTF-8: it holds a byte that cannot be decoded at byte offset %d." % (path, error.start)


# Output

Report = namedtuple("Report", "path format text result")


def _count(findings, severity):
    return sum(1 for f in findings if f.severity == severity)


def _row(path, f):
    shown = _NEWLINES.sub(" ", f.text)
    if len(shown) > TEXT_LIMIT:
        shown = shown[:TEXT_LIMIT - 3] + "..."
    return '%s:%d:%d: %s: %s: %s: "%s" (%s)' % (path, f.line, f.col, f.family, f.tier, f.severity, shown, f.strategy)


def _text_output(reports, patterns):
    lines, flagged, info = [], 0, 0
    for report in reports:
        findings = report.result.findings
        lines.extend(_row(report.path, f) for f in findings)
        lines.append("%s: %d words, %d flagged, %d info" % (
            report.path, report.result.words, _count(findings, "flag"), _count(findings, "info")))
        for family in patterns.families:
            if family.id in report.result.density:
                count = sum(1 for f in findings if f.family == family.id)
                lines.append("  %s: %d hits, %.2f per 1000 words" % (family.id, count, report.result.density[family.id]))
        flagged, info = flagged + _count(findings, "flag"), info + _count(findings, "info")
    lines.append("flagged: %d info: %d" % (flagged, info))
    return "\n".join(lines) + "\n"


def _json_output(reports):
    files = [{"file": r.path, "format": r.format, "words": r.result.words, "density": r.result.density,
              "findings": [dict(f._asdict()) for f in r.result.findings]} for r in reports]
    every = [f for r in reports for f in r.result.findings]
    return _dump({"files": files, "flagged": _count(every, "flag"), "info": _count(every, "info")})


def _dump(data):
    return json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _write(stream, text):
    stream.write(text.encode("utf-8", "surrogateescape"))
    stream.flush()


def _parser():
    parser = argparse.ArgumentParser(prog=PROG, description="Find writing patterns in LaTeX, Markdown and text files.")
    parser.add_argument("paths", nargs="+", metavar="PATH", help="a file or a folder")
    parser.add_argument("--format", choices=("auto",) + FORMATS, default="auto", help="default: from the extension")
    parser.add_argument("--project-dir", default=".", metavar="DIR", help="default: the working directory")
    parser.add_argument("--json", action="store_true", help="print the findings as JSON")
    parser.add_argument("--windows", action="store_true", help="print the windows as JSON")
    return parser


def main(argv=None, out=None, err=None):
    """Run the command line. Return the exit code. `out` and `err` are binary streams."""
    out = out or sys.stdout.buffer
    err = err or sys.stderr.buffer
    try:
        args = _parser().parse_args(argv)
    except SystemExit as stop:
        return stop.code
    if not os.path.isdir(args.project_dir):
        _write(err, "%s: error: project directory not found: %s\n" % (PROG, args.project_dir))
        return 2
    try:
        patterns = load_patterns(args.project_dir)
    except PatternError as error:
        _write(err, "%s: error: %s\n" % (PROG, error))
        return 2
    files, problems = _collect(args.paths)
    reports = []
    for path in files:
        text, problem = _read(path)
        if problem:
            problems.append(problem)
        elif not problems:
            fmt = detect_format(path) if args.format == "auto" else args.format
            try:
                reports.append(Report(path, fmt, text, lint_text(text, fmt, patterns)))
            except Exception as error:  # a crash must not look like findings (exit 1)
                problems.append("cannot check %s: %s: %s." % (path, type(error).__name__, error))
    if problems:
        _write(err, "".join("%s: error: %s\n" % (PROG, problem) for problem in problems))
        return 2
    if args.windows:
        shown = []
        for report in reports:
            shown.extend(windows(report.result.findings, report.text, report.path, len(shown) + 1))
        _write(out, _dump(shown))
    else:
        _write(out, _json_output(reports) if args.json else _text_output(reports, patterns))
    return 1 if any(f.severity == "flag" for r in reports for f in r.result.findings) else 0


if __name__ == "__main__":
    sys.exit(main())
