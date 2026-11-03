"""Measure the precision of the detector on the fixture paragraphs.

Command line.
- `python3 precision.py rows [--paragraphs FILE] [--json]` prints one row for each flagged finding.
- `python3 precision.py report LABELS.json [--paragraphs FILE]` prints the measures.

The default paragraph file is `fixtures/paragraphs.json`. The tool runs the detector on each
paragraph as a plain-text file of its own. An `info` finding is no row.

A row has a key such as `p07:3`: the id of the paragraph, a colon, and the number of the flagged
finding in that paragraph. The number starts at 1 and follows the order of the detector. The key of
a finding stays the same while the paragraph text and the pattern data stay the same. The text form
of a row has five fields, separated by a tab: the key, the family, the kind of the paragraph
(`seeded` or `clean`), the text of the finding and the sentence. The last two fields are JSON strings.

The labels file is a JSON object that maps each key to `right` or `wrong`. A reader sets a label
after reading the row against the source sentence.

The report gives these measures, each by family.
- Precision: right / (right + wrong) for the flagged findings of the family.
- Recall of seeded labels: a seeded paragraph and a family of its `seeded` list form one seeded
  label. A flagged finding of that family, in that paragraph, with the label `right`, covers it.
- The flagged findings on clean paragraphs, with their labels.

The report gives no figure that adds the families together, because the families differ too much.

Exit codes: 0 success, 2 the check could not run. Code 2 covers a bad file, a flagged finding with no
label, a label with no flagged finding and a label other than `right` or `wrong`. Then stdout stays
empty.
"""
import argparse
import io
import json
import os
import sys
from collections import OrderedDict

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPTS = os.path.join(os.path.dirname(os.path.dirname(HERE)), "scripts")
if SCRIPTS not in sys.path:
    sys.path.insert(0, SCRIPTS)

import prose_lint as pl  # noqa: E402
from prose_patterns import PatternError, load_patterns  # noqa: E402

PROG = "precision.py"
DEFAULT_PARAGRAPHS = os.path.join(HERE, "fixtures", "paragraphs.json")
LABELS = ("right", "wrong")


class ToolError(Exception):
    """The tool cannot run. The messages go to stderr and the exit code is 2."""


def load_paragraphs(path):
    """Return the paragraphs of a JSON file: a list of dicts with `id`, `text` and `seeded`."""
    try:
        with io.open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as error:
        raise ToolError("cannot read the paragraphs %s: %s." % (path, error))
    if not isinstance(data, list):
        raise ToolError("%s does not hold a list of paragraphs." % path)
    seen = set()
    for item in data:
        if not (isinstance(item, dict) and isinstance(item.get("id"), str) and isinstance(item.get("text"), str)
                and isinstance(item.get("seeded"), list)):
            raise ToolError("each paragraph in %s needs an id, a text and a seeded list." % path)
        if item["id"] in seen:
            raise ToolError("the id %s occurs twice in %s." % (item["id"], path))
        seen.add(item["id"])
    return data


def flagged_rows(paragraphs, patterns):
    """Return one dict for each flagged finding, in the order of the paragraphs.

    The dict has `key`, `paragraph`, `kind`, `family`, `rule`, `text` and `sentence`.
    """
    rows = []
    for item in paragraphs:
        text = item["text"]
        result = pl.lint_text(text + "\n", "text", patterns)
        number = 0
        for finding in result.findings:
            if finding.severity != "flag":
                continue
            number += 1
            rows.append(OrderedDict([
                ("key", "%s:%d" % (item["id"], number)),
                ("paragraph", item["id"]),
                ("kind", "seeded" if item["seeded"] else "clean"),
                ("family", finding.family),
                ("rule", finding.rule_label),
                ("text", finding.text),
                ("sentence", text[finding.sentence_start:finding.sentence_end]),
            ]))
    return rows


def _one_line(value):
    return " ".join(value.split())


def _format_row(row):
    return "\t".join([
        row["key"], row["family"], row["kind"],
        json.dumps(_one_line(row["text"]), ensure_ascii=False), json.dumps(_one_line(row["sentence"]), ensure_ascii=False)])


def _read_labels(path):
    try:
        with io.open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError) as error:
        raise ToolError("cannot read the labels %s: %s." % (path, error))
    if not isinstance(data, dict):
        raise ToolError("%s must hold a JSON object that maps each key to right or wrong." % path)
    return data


def _check_labels(rows, labels):
    """Raise ToolError with every problem of the labels."""
    keys = [row["key"] for row in rows]
    known = set(keys)
    problems = ["the flagged finding %s has no label." % key for key in keys if key not in labels]
    problems += ["the label %s has no flagged finding." % key for key in sorted(labels) if key not in known]
    problems += ["the label of %s is %s. Use right or wrong." % (key, json.dumps(value))
                 for key, value in sorted(labels.items()) if value not in LABELS]
    if problems:
        raise ToolError("\n".join(problems))


def measures(paragraphs, rows, labels, family_order):
    """Return (precision, recall, missed) from the rows and their labels.

    `precision` maps a family to (right, wrong) for the families with a flagged finding.
    `recall` maps a family to (covered, seeded) for the families that a paragraph seeds.
    `missed` lists the (paragraph id, family) pairs that no right finding covers.
    """
    precision = OrderedDict()
    for family in family_order:
        mine = [labels[row["key"]] for row in rows if row["family"] == family]
        if mine:
            precision[family] = (mine.count("right"), mine.count("wrong"))
    right = set((row["paragraph"], row["family"]) for row in rows if labels[row["key"]] == "right")
    recall, missed = OrderedDict(), []
    for family in family_order:
        pairs = [(item["id"], family) for item in paragraphs if family in item["seeded"]]
        if pairs:
            covered = [pair for pair in pairs if pair in right]
            recall[family] = (len(covered), len(pairs))
            missed.extend(pair for pair in pairs if pair not in right)
    return precision, recall, missed


def format_report(paragraphs, rows, labels, family_order):
    precision, recall, missed = measures(paragraphs, rows, labels, family_order)
    lines = ["Precision by family: right / (right + wrong)."]
    for family, (right, wrong) in precision.items():
        lines.append("  %-22s %.2f  (%d right, %d wrong)" % (family, right / float(right + wrong), right, wrong))
    if not precision:
        lines.append("  no flagged finding.")
    lines.append("")
    lines.append("Recall of seeded labels by family. A right finding of the family in the seeded paragraph covers a label.")
    for family, (covered, seeded) in recall.items():
        lines.append("  %-22s %d of %d covered" % (family, covered, seeded))
    lines.append("")
    lines.append("Seeded labels that no right finding covers:")
    lines.extend("  %s %s" % pair for pair in missed)
    if not missed:
        lines.append("  none.")
    lines.append("")
    lines.append("Flagged findings on clean paragraphs:")
    clean = [row for row in rows if row["kind"] == "clean"]
    for row in clean:
        lines.append("  %s %s %s (%s)" % (row["key"], row["family"], json.dumps(_one_line(row["text"]), ensure_ascii=False),
                                          labels[row["key"]]))
    if not clean:
        lines.append("  none.")
    return "\n".join(lines) + "\n"


def _write(stream, text):
    stream.write(text.encode("utf-8", "surrogateescape"))
    stream.flush()


def _parser():
    parser = argparse.ArgumentParser(prog=PROG, description="Measure the precision of the detector on the fixtures.")
    commands = parser.add_subparsers(dest="command", metavar="COMMAND")
    commands.required = True
    rows = commands.add_parser("rows", help="print one row for each flagged finding")
    rows.add_argument("--paragraphs", default=DEFAULT_PARAGRAPHS, metavar="FILE")
    rows.add_argument("--json", action="store_true", help="print the rows as JSON")
    report = commands.add_parser("report", help="print the precision and the recall from a labels file")
    report.add_argument("labels", metavar="LABELS.json")
    report.add_argument("--paragraphs", default=DEFAULT_PARAGRAPHS, metavar="FILE")
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
        try:
            patterns = load_patterns()
        except PatternError as error:
            raise ToolError(str(error))
        paragraphs = load_paragraphs(args.paragraphs)
        rows = flagged_rows(paragraphs, patterns)
        if args.command == "rows":
            if args.json:
                _write(out, json.dumps(rows, ensure_ascii=False, indent=2) + "\n")
            else:
                _write(out, "".join(_format_row(row) + "\n" for row in rows))
            return 0
        labels = _read_labels(args.labels)
        _check_labels(rows, labels)
        _write(out, format_report(paragraphs, rows, labels, [family.id for family in patterns.families]))
    except ToolError as error:
        _write(err, "".join("%s: error: %s\n" % (PROG, line) for line in str(error).split("\n")))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
