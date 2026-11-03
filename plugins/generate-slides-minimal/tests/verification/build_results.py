#!/usr/bin/env python3
"""Build results.md from the saved scores of the comparison.

Run:  python3 build_results.py EVIDENCE_DIR [--out results.md]
In:   EVIDENCE_DIR holds the six files v1-1.score.txt to v1-3.score.txt and minimal-1.score.txt to
      minimal-3.score.txt. Each file is the output of score_deck.py. A deck file with the same
      name and the suffix .pptx is optional. The grammar of a score file is in evidence/README.md.
      Two more files are optional. A file such as v1-1.titles.txt holds the titles of that run as the
      controller read them. The file controller-notes.md holds the notes of the controller.
Out:  results.md, by default in the folder above EVIDENCE_DIR.

Every number in results.md is computed from the score files. The wording of each comparison sentence
follows the computed numbers. The script stops with a message and writes no file when:
  - a score file is missing, is not named as above, or does not follow the grammar. A line that
    the parser cannot read is an error and never a skip.
  - a score file disagrees with itself. The summary differs from the rows, or the ghost deck and the
    word counts list different slides.
  - the six score files were made with different settings.
  - a deck file is present and a new scoring of it differs from the saved score.
  - a titles file does not follow the grammar, or lists another number of slides than its score file.
  - a titles file has a name that no run has.
  - a file is not UTF-8.

The script copies controller-notes.md into results.md as it is. It does not change, wrap or count
anything in that file.

The script writes results.md through a temporary file in the same folder and renames it. A write error
cannot cut an existing results.md. The script uses check() and never the assert statement, because
python3 -O removes every assert.

Exit codes: 0 done. 1 for each failure above, with the message on stderr. 2 for a usage error of the
command line, with the usage message of argparse.
"""
import argparse
import math
import os
import re
import sys
from collections import namedtuple
from fractions import Fraction
from itertools import zip_longest
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import score_deck  # noqa: E402  (it also puts the scripts folder of the plugin on sys.path)
import style  # noqa: E402

VARIANTS = ("v1", "minimal")
RUNS = (1, 2, 3)
TITLE_RULES = ("title-empty", "title-sentence", "title-unique")  # the rules about the text of a title
NOTES_NAME = "controller-notes.md"

Row = namedtuple("Row", "slide rule severity tier message")
Score = namedtuple("Score", "profile minutes theme notes findings ghost words errors warnings")
Run = namedtuple("Run", "variant number score checked titles")
Stats = namedtuple("Stats", "slides errors warnings words flagged")
Summary = namedtuple("Summary", "runs slides errors warnings per_run clean words flagged")


def check(condition, message):
    """Stop with `message` unless `condition` holds. This is the only guard of the script."""
    if not condition:
        raise SystemExit(message)


# ---------------------------------------------------------------------------
# The grammar of a score file
# ---------------------------------------------------------------------------

SETTINGS = re.compile(r"settings: profile=(\S+) minutes=(\S+) theme=(\S+) notes=(on|off)")
FINDING = re.compile(r"(?:slide ([1-9][0-9]*)|deck): ([a-z][a-z0-9-]*): (error|warn): (T[123]): (\S.*)")
GHOST = re.compile(r"slide ([1-9][0-9]*): (\S.*)")
WORDS = re.compile(r"slide ([1-9][0-9]*): (?:([0-9]+) words|(unreadable))")
SUMMARY = re.compile(r"errors: ([0-9]+) warnings: ([0-9]+)")


def parse_score(text, name):
    """Return the Score of a score file. Stop with `name:line: reason` at the first line that breaks the grammar."""
    check(text.endswith("\n"), "{}: the file does not end with a newline".format(name))
    check("\r" not in text, "{}: the file holds a carriage return".format(name))
    lines = text[:-1].split("\n")
    position = [0]

    def fail(index, what):
        shown = lines[index] if index < len(lines) else "(end of file)"
        raise SystemExit("{}:{}: {}: {!r}".format(name, index + 1, what, shown))

    def take(pattern, what):
        index = position[0]
        match = pattern.fullmatch(lines[index]) if index < len(lines) else None
        if match is None:
            fail(index, what)
        position[0] += 1
        return match

    def header(expected):
        index = position[0]
        if index >= len(lines) or lines[index] != expected:
            fail(index, "expected the line {!r}".format(expected))
        position[0] += 1

    def more_before(stop):
        return position[0] < len(lines) and lines[position[0]] != stop

    profile, minutes_text, theme, notes = take(SETTINGS, "expected the settings line").groups()
    if profile not in style.PROFILES:
        fail(0, "unknown profile")
    if theme not in style.THEMES:
        fail(0, "unknown theme")
    try:
        minutes = float(minutes_text)
    except ValueError:
        minutes = float("nan")
    if not math.isfinite(minutes) or not minutes > 0:
        fail(0, "minutes must be a finite number above 0")
    header("findings:")
    findings = []
    while more_before("ghost deck:"):
        match = take(FINDING, "not a finding row")
        findings.append(Row(int(match.group(1) or 0), match.group(2), match.group(3), match.group(4), match.group(5)))
    header("ghost deck:")
    ghost = []
    while more_before("words per slide:"):
        match = take(GHOST, "not a ghost deck row")
        if int(match.group(1)) != len(ghost) + 1:
            fail(position[0] - 1, "the slide numbers must run 1, 2, 3 and so on")
        ghost.append((int(match.group(1)), match.group(2)))
    header("words per slide:")
    words = []
    while position[0] < len(lines) and not SUMMARY.fullmatch(lines[position[0]]):
        match = take(WORDS, "not a word count row and not the summary line")
        if int(match.group(1)) != len(words) + 1:
            fail(position[0] - 1, "the slide numbers must run 1, 2, 3 and so on")
        words.append((int(match.group(1)), None if match.group(3) else int(match.group(2))))
    errors, warnings = (int(value) for value in take(SUMMARY, "expected the summary line").groups())
    if position[0] != len(lines):
        fail(position[0], "text after the summary line")
    check(len(ghost) == len(words), "{}: the ghost deck lists {} slides and the word counts list {}".format(
        name, len(ghost), len(words)))
    for (number, title), (_, count) in zip(ghost, words):
        check((title == score_deck.UNREADABLE_TITLE) == (count is None),
              "{}: slide {} is unreadable in one list and readable in the other".format(name, number))
    check(all(row.slide <= len(ghost) for row in findings),
          "{}: a finding names a slide that the ghost deck does not list".format(name))
    found_errors = sum(1 for row in findings if row.severity == "error")
    check(errors == found_errors, "{}: the summary says {} errors and the rows hold {}".format(
        name, errors, found_errors))
    check(warnings == len(findings) - found_errors, "{}: the summary says {} warnings and the rows hold {}".format(
        name, warnings, len(findings) - found_errors))
    return Score(profile, minutes, theme, notes == "on", findings, ghost, words, errors, warnings)


def parse_titles(text, name, slides):
    """Return [(number, title)] of a titles file. Stop with `name:line: reason` at the first line that breaks the grammar.

    A row has the grammar of a ghost deck row of a score file. The file lists as many slides as the score file.
    """
    check(text.endswith("\n"), "{}: the file does not end with a newline".format(name))
    check("\r" not in text, "{}: the file holds a carriage return".format(name))
    rows = []
    for index, line in enumerate(text[:-1].split("\n")):
        match = GHOST.fullmatch(line)
        check(match is not None, "{}:{}: not a title row: {!r}".format(name, index + 1, line))
        check(int(match.group(1)) == index + 1, "{}:{}: the slide numbers must run 1, 2, 3 and so on: {!r}".format(
            name, index + 1, line))
        rows.append((index + 1, match.group(2)))
    check(len(rows) == slides, "{}: the titles file lists {} slides and the score file lists {}".format(
        name, len(rows), slides))
    return rows


# ---------------------------------------------------------------------------
# Reading the evidence folder
# ---------------------------------------------------------------------------

def score_name(variant, number):
    return "{}-{}.score.txt".format(variant, number)


def titles_name(variant, number):
    return "{}-{}.titles.txt".format(variant, number)


def read_utf8(path):
    """Return the text of a file. Stop with a message when the file is not UTF-8."""
    try:
        return path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as error:
        raise SystemExit("{}: the file is not UTF-8: {}".format(path.name, error))


def optional_file(path):
    """Return True when the file exists. Stop when the name belongs to something that is not a file."""
    check(not path.exists() or path.is_file(), "{} is not a file".format(path))
    return path.exists()


def minutes_text(minutes):
    return "{:g}".format(minutes)


def recheck(deck, name, text, score):
    """Score the deck again with the saved settings and stop when the result differs from the saved text."""
    minutes = int(score.minutes) if score.minutes == int(score.minutes) else score.minutes
    try:
        fresh, _ = score_deck.score_text(str(deck), minutes, score.profile, score.theme, score.notes)
    except (ValueError, OSError) as error:
        raise SystemExit("{}: cannot score the deck {}: {}".format(name, deck.name, error))
    for index, (saved, now) in enumerate(zip_longest(text.split("\n"), fresh.split("\n"))):
        check(saved == now, "{}: the saved score does not match the deck {} at line {}: saved {!r}, scored now {!r}"
              .format(name, deck.name, index + 1, saved, now))


def load_runs(folder):
    """Return the six Run records. Stop when a score file or a titles file is missing, unexpected or malformed."""
    folder = Path(folder)
    check(folder.is_dir(), "the evidence folder does not exist: {}".format(folder))
    wanted = [(variant, number) for variant in VARIANTS for number in RUNS]
    names = set(score_name(*pair) for pair in wanted)
    unexpected = sorted(path.name for path in folder.glob("*.score.txt") if path.name not in names)
    check(not unexpected, "unexpected score file(s) in {}: {}".format(folder, ", ".join(unexpected)))
    title_names = set(titles_name(*pair) for pair in wanted)
    unexpected = sorted(path.name for path in folder.glob("*.titles.txt") if path.name not in title_names)
    check(not unexpected, "unexpected titles file(s) in {}: {}".format(folder, ", ".join(unexpected)))
    missing = [score_name(*pair) for pair in wanted if not (folder / score_name(*pair)).is_file()]
    check(not missing, "missing score file(s) in {}: {}".format(folder, ", ".join(missing)))
    runs = []
    for variant, number in wanted:
        name = score_name(variant, number)
        text = read_utf8(folder / name)
        score = parse_score(text, name)
        deck = folder / "{}-{}.pptx".format(variant, number)
        if deck.is_file():
            recheck(deck, name, text, score)
        titles_file = folder / titles_name(variant, number)
        titles = parse_titles(read_utf8(titles_file), titles_file.name, len(score.ghost)) \
            if optional_file(titles_file) else None
        runs.append(Run(variant, number, score, deck.is_file(), titles))
    settings = sorted(set((run.score.profile, minutes_text(run.score.minutes), run.score.theme, run.score.notes)
                          for run in runs))
    check(len(settings) == 1, "the score files use different settings: " + "; ".join(
        "{}-{}: profile {} minutes {} theme {} notes {}".format(run.variant, run.number, run.score.profile,
                                                                 minutes_text(run.score.minutes), run.score.theme,
                                                                 "on" if run.score.notes else "off")
        for run in runs))
    return runs


def load_notes(folder):
    """Return the text of controller-notes.md, or None when the file is absent."""
    path = Path(folder) / NOTES_NAME
    return read_utf8(path) if optional_file(path) else None


# ---------------------------------------------------------------------------
# The numbers
# ---------------------------------------------------------------------------

def run_stats(run):
    score = run.score
    counted = [count for _, count in score.words if count is not None]
    flagged = len(set(row.slide for row in score.findings if row.rule in TITLE_RULES))
    return Stats(len(score.ghost), score.errors, score.warnings, max(counted) if counted else 0, flagged)


def summarize(runs, variant):
    stats = [run_stats(run) for run in runs if run.variant == variant]
    check(stats, "no run of the variant {}".format(variant))
    return Summary(len(stats), Fraction(sum(s.slides for s in stats), len(stats)), sum(s.errors for s in stats),
                   sum(s.warnings for s in stats), Fraction(sum(s.warnings for s in stats), len(stats)),
                   sum(1 for s in stats if s.errors == 0), max(s.words for s in stats),
                   sum(s.flagged for s in stats))


def number_text(value):
    """Return an integer as it is, and a fraction with one decimal."""
    return str(value) if isinstance(value, int) else "{:.1f}".format(float(value))


def plural(count, noun):
    return "{} {}{}".format(count, noun, "" if count == 1 else "s")


def direction(first, second):
    """Return -1, 0 or 1 for first below, equal to or above second."""
    return (first > second) - (first < second)


# One entry per comparison: the field of the summary, and a sentence for each direction (fewer, same, more).
# {a} is the minimal variant and {b} is v1. {x} is the value of a and {y} the value of b.
COMPARISONS = (
    ("errors", ("The {a} decks have fewer errors than the {b} decks: {x} against {y} in total.",
                "The {a} decks have the same number of errors as the {b} decks: {x} and {y} in total.",
                "The {a} decks have more errors than the {b} decks: {x} against {y} in total.")),
    ("warnings", ("The {a} decks have fewer warnings than the {b} decks: {x} against {y} in total.",
                  "The {a} decks have the same number of warnings as the {b} decks: {x} and {y} in total.",
                  "The {a} decks have more warnings than the {b} decks: {x} against {y} in total.")),
    ("flagged", ("The {a} decks have fewer flagged titles than the {b} decks: {x} against {y} in total.",
                 "The {a} decks have the same number of flagged titles as the {b} decks: {x} and {y} in total.",
                 "The {a} decks have more flagged titles than the {b} decks: {x} against {y} in total.")),
    ("slides", ("The {a} decks have fewer slides than the {b} decks: {x} against {y} on average.",
                "The {a} decks have the same number of slides as the {b} decks: {x} and {y} on average.",
                "The {a} decks have more slides than the {b} decks: {x} against {y} on average.")),
    ("words", ("The busiest slide of the {a} decks holds fewer words than the busiest slide of the {b} decks: "
               "{x} against {y}.",
               "The busiest slide of the {a} decks holds the same number of words as the busiest slide of the "
               "{b} decks: {x} and {y}.",
               "The busiest slide of the {a} decks holds more words than the busiest slide of the {b} decks: "
               "{x} against {y}.")),
)
_WORD_FOR = {-1: "fewer", 0: "the same number", 1: "more"}
SKIP_NOTE_SENTENCE = "Skip notes raise the warning count."


def comparison_sentences(first, second):
    """Return one sentence for each comparison. The numbers choose the wording, and each sentence is checked."""
    sentences = []
    for field, templates in COMPARISONS:
        x, y = getattr(first, field), getattr(second, field)
        sign = direction(x, y)
        sentence = templates[sign + 1].format(a="minimal", b="v1", x=number_text(x), y=number_text(y))
        # A whole number only. The 1 of "v1" is no match.
        shown = re.findall(r"(?<![\w.])[0-9]+(?:\.[0-9]+)?(?!\w)", sentence)
        check(shown == [number_text(x), number_text(y)], "the sentence {!r} does not show {} and {}".format(
            sentence, number_text(x), number_text(y)))
        check(_WORD_FOR[direction(float(shown[0]), float(shown[1]))] in sentence,
              "the wording of {!r} disagrees with its numbers".format(sentence))
        sentences.append(sentence + (" " + SKIP_NOTE_SENTENCE if field == "warnings" else ""))
    return sentences


# ---------------------------------------------------------------------------
# The report
# ---------------------------------------------------------------------------

def table(header, rows):
    lines = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    return lines + ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]


def rule_table(runs):
    counts = {}
    for run in runs:
        for row in run.score.findings:
            counts.setdefault(row.rule, dict((variant, 0) for variant in VARIANTS))[run.variant] += 1
    if not counts:
        return ["No run has a finding."]
    return table(("Rule", "v1", "minimal"), [(rule, counts[rule]["v1"], counts[rule]["minimal"])
                                              for rule in sorted(counts)])


def checked_sentence(runs):
    count = sum(1 for run in runs if run.checked)
    if count == len(runs):
        return "build_results.py scored each of the {} decks again, and each new score matched.".format(count)
    if count == 0:
        return "No deck file was present, so build_results.py did not score the decks again."
    return "{} of {} deck files were present. Each of them scored the same as its saved score.".format(
        count, len(runs))


def build_report(runs, notes=None):
    """Return the text of results.md. Every number comes from the runs.

    `notes` is the text of controller-notes.md. The report ends with it, as it is, under its own heading.
    """
    first = runs[0].score
    per_variant = dict((variant, summarize(runs, variant)) for variant in VARIANTS)
    counts = [per_variant[variant].runs for variant in VARIANTS]
    runs_limit = ("The comparison has {} per variant on one synthetic project.".format(plural(counts[0], "run"))
                  if len(set(counts)) == 1 else
                  "The comparison has {} on one synthetic project.".format(
                      " and ".join("{} for {}".format(plural(per_variant[v].runs, "run"), v) for v in VARIANTS)))
    lines = [
        "# Comparison of generate-slides and generate-slides-minimal",
        "",
        "The script build_results.py computed this file from the saved score files. Do not edit it by hand.",
        "",
        "All {} decks were scored with the {} profile for {} minutes, with the {} theme and notes {}. {}".format(
            len(runs), first.profile, minutes_text(first.minutes), first.theme, "on" if first.notes else "off",
            checked_sentence(runs)),
        "",
        "## Results per run",
        "",
    ]
    rows = []
    for run in runs:
        stats = run_stats(run)
        rows.append((run.variant, run.number, stats.slides, stats.errors, stats.warnings, stats.words, stats.flagged))
    lines += table(("Variant", "Run", "All slides", "Errors", "Warnings", "Words on the busiest slide",
                    "Flagged titles"), rows)
    lines += ["", "## Summary per variant", ""]
    summary_rows = []
    for variant in VARIANTS:
        s = per_variant[variant]
        summary_rows.append((variant, s.runs, number_text(s.slides), s.errors, s.warnings, number_text(s.per_run),
                             "{} of {}".format(s.clean, s.runs), s.words, s.flagged))
    lines += table(("Variant", "Runs", "All slides per run", "Errors", "Warnings", "Warnings per run",
                    "Runs without errors", "Words on the busiest slide", "Flagged titles"), summary_rows)
    lines += ["", "## Comparison", ""]
    lines += ["- " + sentence for sentence in comparison_sentences(per_variant["minimal"], per_variant["v1"])]
    lines += ["", "## Findings per rule", "",
              "A skip note is a warning and counts under its rule.", ""]
    lines += rule_table(runs)
    lines += ["", "## Ghost decks", ""]
    readers = [run for run in runs if run.titles is not None]
    if readers:
        lines += ['A v1 slide reads "(no title)" here because v1 builds titles as text boxes, so "Ghost decks as read '
                  'by the controller" holds them.', ""]
    for run in runs:
        lines += ["### {} run {} ({})".format(run.variant, run.number, plural(len(run.score.ghost), "slide")), ""]
        lines += ["{}. {}".format(number, title) for number, title in run.score.ghost]
        lines.append("")
    if readers:
        lines += ["## Ghost decks as read by the controller", "",
                  "The controller read these titles by hand. The tables keep the numbers of the linter.", ""]
        missing = ["{}-{}".format(run.variant, run.number) for run in runs if run.titles is None]
        if missing:
            lines += ["No titles file for {}.".format(", ".join(missing)), ""]
        for run in readers:
            lines += ["### {} run {} ({})".format(run.variant, run.number, plural(len(run.titles), "slide")), ""]
            lines += ["{}. {}".format(number, title) for number, title in run.titles]
            lines.append("")
    lines += [
        "## Limits",
        "",
        "- " + runs_limit,
        "- The subagents follow the command text. The interactive questions cannot run in a headless session.",
        "- The linter belongs to the minimal plugin, so v1 is judged by rules that it did not set out to meet.",
        "- The linter does not score what needs a judgment, such as whether a figure supports its headline.",
        "- The controller read the ghost decks. That reading is a judgment, and this file does not score it.",
        "- The word count covers every slide. The words-per-slide rule skips a take-home slide of the minimal plugin.",
        "- The All slides column counts every slide. The slide-count rule of the linter counts visible main slides only.",
        "- The comparison measures compliance with rules. It does not measure audience outcomes.",
        "",
    ]
    report = "\n".join(lines)
    if notes is not None:
        report += "\n## Notes of the controller\n\n" + notes  # verbatim: no strip, no wrap, no count
    return report


def write_atomic(out, text):
    """Write text to `out` as UTF-8 through a temporary file in the same folder, then rename the file.

    A write error leaves an existing `out` as it was and removes the temporary file.
    """
    temporary = out.with_name(".{}.{}.tmp".format(out.name, os.getpid()))
    handle = open(str(temporary), "xb")  # "x" refuses to reuse a file, so a failure here leaves nothing to remove
    try:
        with handle:
            handle.write(text.encode("utf-8"))
        os.replace(str(temporary), str(out))
    except BaseException:
        try:
            os.unlink(str(temporary))
        except OSError:
            pass
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(prog="build_results.py", description="Build results.md from the saved scores.")
    parser.add_argument("evidence", metavar="EVIDENCE_DIR", help="the folder with the six score files")
    parser.add_argument("--out", help="the file to write; the default is results.md in the folder above EVIDENCE_DIR")
    args = parser.parse_args(argv)
    report = build_report(load_runs(args.evidence), load_notes(args.evidence))  # every check runs first
    out = Path(args.out) if args.out else Path(args.evidence).resolve().parent / "results.md"
    try:
        write_atomic(out, report)
    except OSError as error:
        raise SystemExit("cannot write {}: {}".format(out, error))
    sys.stdout.write("wrote {}\n".format(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
