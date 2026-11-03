"""Compare a manuscript before and after a rewrite pass.

Command line: `python3 diff_report.py ORIGINAL REVISED [--format auto|latex|markdown|text]`.
With `--format auto` the extension of ORIGINAL picks the format of both files. An unknown
extension gives plain text.

The report holds these parts.
- The number of words before and after.
- The flagged findings of the detector before and after, by family.
- The masked spans (math, citations, references and other hidden text). The report tells whether
  the two files hold the same spans, and lists each span that one file lacks.
- The numbers. The report tells whether the two files hold the same numbers, and lists the others.
- The changed sentences, as before and after.

A sentence is a sentence of the detector, with the white space folded to single spaces. A changed
sentence is a sentence that one file holds and the other file does not. The tool aligns each run of
changed sentences in order. Two sentences form a pair when their texts are at least half alike
(`SIMILAR` in the code). A stretch of old and new sentences with no pair between two pairs gives one
change with the joined text. A change with no `before` is an added sentence. A change with no `after`
is a deleted sentence. A sentence that the pass splits gives a reworded sentence and an added sentence.

Exit codes: 0 when the masked spans and the numbers are identical, 1 when they differ, 2 when the
check could not run (a missing file, a file with a NUL byte or a file that is not UTF-8). Then
stdout stays empty and the message goes to stderr.
"""
import argparse
import difflib
import io
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(HERE)), "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import prose_lint as pl  # noqa: E402
from prose_mask import detect_format, mask, piece  # noqa: E402
from prose_mask_core import CLOSE, OPEN  # noqa: E402
from prose_patterns import PatternError, load_patterns  # noqa: E402
from prose_text import numeric_tokens, split_sentences, word_count  # noqa: E402

PROG = "diff_report.py"
FORMATS = ("latex", "markdown", "text")
SHOWN_ITEMS = 20
SIMILAR = 0.5
MAX_CELLS = 250000
_PLACEHOLDER = re.compile(OPEN + r"(\d+)" + CLOSE)


class ToolError(Exception):
    """The tool cannot run. The message goes to stderr and the exit code is 2."""


def read_text(path):
    """Return the text of a file. Raise ToolError for a missing file, a NUL byte or a byte that is not UTF-8."""
    try:
        with io.open(path, "rb") as handle:
            data = handle.read()
    except OSError as error:
        raise ToolError("cannot read %s: %s." % (path, error.strerror or error))
    if b"\x00" in data:
        raise ToolError("%s is a binary file: it holds a NUL byte." % path)
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ToolError("%s is not valid UTF-8: the byte at offset %d cannot be decoded." % (path, error.start))


def sentences_of(text, fmt):
    """Return the sentences of the text, as strings of the original text with single spaces.

    A sentence with no word (a line of commands) is left out.
    """
    masked = mask(text, fmt)
    found = []
    for start, end in split_sentences(masked.text, pl.hard_breaks(masked)):
        chunk = masked.text[start:end]
        if word_count(chunk) == 0:
            continue
        restored = _PLACEHOLDER.sub(lambda match: piece(masked, int(match.group(1))), chunk)
        found.append(" ".join(restored.split()))
    return found


def _ratio(a, b):
    matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
    if matcher.real_quick_ratio() < SIMILAR or matcher.quick_ratio() < SIMILAR:
        return 0.0
    return matcher.ratio()


def _align(old, new):
    """Return the (i, j) pairs of similar sentences, in order, that give the largest sum of similarity."""
    if len(old) * len(new) > MAX_CELLS:
        return []
    sim = [[_ratio(a, b) for b in new] for a in old]
    rows, cols = len(old), len(new)
    best = [[0.0] * (cols + 1) for _ in range(rows + 1)]
    for i in range(rows - 1, -1, -1):
        for j in range(cols - 1, -1, -1):
            top = max(best[i + 1][j], best[i][j + 1])
            if sim[i][j] >= SIMILAR:
                top = max(top, sim[i][j] + best[i + 1][j + 1])
            best[i][j] = top
    pairs, i, j = [], 0, 0
    while i < rows and j < cols:
        if sim[i][j] >= SIMILAR and best[i][j] == sim[i][j] + best[i + 1][j + 1]:
            pairs.append((i, j))
            i, j = i + 1, j + 1
        elif best[i + 1][j] >= best[i][j + 1]:
            i += 1
        else:
            j += 1
    return pairs


def _block_changes(old, new):
    """Return the changes of one run of changed sentences. `old` and `new` are the two lists of the run."""
    changes, i0, j0 = [], 0, 0
    pairs = _align(old, new)
    for i, j in pairs + [(len(old), len(new))]:
        gap_old, gap_new = old[i0:i], new[j0:j]
        if gap_old and gap_new:
            changes.append({"before": " ".join(gap_old), "after": " ".join(gap_new)})
        else:
            changes.extend({"before": text, "after": None} for text in gap_old)
            changes.extend({"before": None, "after": text} for text in gap_new)
        if i < len(old) and old[i] != new[j]:
            changes.append({"before": old[i], "after": new[j]})
        i0, j0 = i + 1, j + 1
    return changes


def changed_sentences(original, revised, fmt):
    """Return the changes between two texts as a list of dicts with `before` and `after`.

    `before` is None for an added sentence, and `after` is None for a deleted one.
    """
    old, new = sentences_of(original, fmt), sentences_of(revised, fmt)
    changes = []
    matcher = difflib.SequenceMatcher(None, old, new, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "delete":
            changes.extend({"before": text, "after": None} for text in old[i1:i2])
        elif tag == "insert":
            changes.extend({"before": None, "after": text} for text in new[j1:j2])
        elif tag == "replace":
            changes.extend(_block_changes(old[i1:i2], new[j1:j2]))
    return changes


def reworded(changes):
    """Return the changes that hold both a before and an after."""
    return [change for change in changes if change["before"] is not None and change["after"] is not None]


def span_texts(masked):
    return Counter(piece(masked, i) for i in range(len(masked.spans)))


def flagged_by_family(text, fmt, patterns):
    """Return a Counter of the flagged findings, by family id."""
    result = pl.lint_text(text, fmt, patterns)
    return Counter(f.family for f in result.findings if f.severity == "flag")


def _show(items):
    shown = ", ".join('"%s"' % " ".join(item.split()) for item in items[:SHOWN_ITEMS])
    if len(items) > SHOWN_ITEMS:
        shown += " and %d more" % (len(items) - SHOWN_ITEMS)
    return shown


def _compare(label, before, after):
    """Return (lines, same) for two Counters."""
    lost = sorted((before - after).elements())
    gained = sorted((after - before).elements())
    if not lost and not gained:
        return ["%s: identical (%d)." % (label, sum(before.values()))], True
    lines = ["%s: DIFFERENT." % label]
    if lost:
        lines.append("  only in the original: %s" % _show(lost))
    if gained:
        lines.append("  only in the revised file: %s" % _show(gained))
    return lines, False


def report(original, revised, fmt, patterns):
    """Return (text, same) for two texts. `same` is true when the spans and the numbers match."""
    before, after = mask(original, fmt), mask(revised, fmt)
    lines = ["words: %d before, %d after." % (word_count(before.text), word_count(after.text)), ""]
    lines.append("flagged findings by family (before -> after):")
    flags_before, flags_after = flagged_by_family(original, fmt, patterns), flagged_by_family(revised, fmt, patterns)
    shown = False
    for family in patterns.families:
        if flags_before[family.id] or flags_after[family.id]:
            lines.append("  %-22s %d -> %d" % (family.id, flags_before[family.id], flags_after[family.id]))
            shown = True
    if not shown:
        lines.append("  none.")
    lines.append("")
    span_lines, same_spans = _compare("masked spans", span_texts(before), span_texts(after))
    number_lines, same_numbers = _compare("numbers", Counter(numeric_tokens(before.text)), Counter(numeric_tokens(after.text)))
    lines.extend(span_lines + number_lines + [""])
    changes = changed_sentences(original, revised, fmt)
    lines.append("changed sentences: %d (%d reworded, %d deleted, %d added)." % (
        len(changes), len(reworded(changes)), sum(1 for c in changes if c["after"] is None),
        sum(1 for c in changes if c["before"] is None)))
    for number, change in enumerate(changes, 1):
        lines.append("")
        lines.append("[%d]" % number)
        lines.append("  before: %s" % ("(none: the sentence is new)" if change["before"] is None else change["before"]))
        lines.append("  after:  %s" % ("(none: the sentence is deleted)" if change["after"] is None else change["after"]))
    return "\n".join(lines) + "\n", same_spans and same_numbers


def _write(stream, text):
    stream.write(text.encode("utf-8", "surrogateescape"))
    stream.flush()


def _parser():
    parser = argparse.ArgumentParser(prog=PROG, description="Compare a manuscript before and after a rewrite pass.")
    parser.add_argument("original", metavar="ORIGINAL")
    parser.add_argument("revised", metavar="REVISED")
    parser.add_argument("--format", choices=("auto",) + FORMATS, default="auto", help="default: from the extension of ORIGINAL")
    return parser


def main(argv=None, out=None, err=None):
    """Run the command line. Return the exit code. `out` and `err` are binary streams."""
    out = out or sys.stdout.buffer
    err = err or sys.stderr.buffer
    try:
        args = _parser().parse_args(argv)
    except SystemExit as stop:
        return stop.code
    try:
        original, revised = read_text(args.original), read_text(args.revised)
        fmt = detect_format(args.original) if args.format == "auto" else args.format
        try:
            patterns = load_patterns()
        except PatternError as error:
            raise ToolError(str(error))
        text, same = report(original, revised, fmt, patterns)
    except ToolError as error:
        _write(err, "%s: error: %s\n" % (PROG, error))
        return 2
    _write(out, text)
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())
