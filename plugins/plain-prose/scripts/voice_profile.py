"""Build and read the voice profile of an author.

The profile holds counts and rates that describe how the author writes. It holds no sentence of
the samples. A rewrite check reads it to keep a rewrite near the author's voice.

Command line: `python3 voice_profile.py SAMPLE... [--format auto|latex|markdown|text] [--out FILE]`.
Each SAMPLE is a file. With `--format auto` the extension picks the format, and an unknown
extension gives `text`. A value of `latex`, `markdown` or `text` applies to every sample.
Without `--out` the command prints the JSON. With `--out` it writes the JSON to that file
and prints nothing.

The exit code is 0 for a profile and 2 when the command cannot build one. Code 2 covers a bad option,
an unreadable file and fewer than 200 words in all samples. It also covers a file with a NUL byte and
a file that is not UTF-8. It covers an `--out` path that names a sample file, as the same path or through
a symbolic or hard link. The command then writes nothing. The message goes to stderr. It holds each file name as the original
bytes, also for a name that is not UTF-8.

How a sample is read.
- The script masks the text (prose_mask). Math, commands, comments, citations and code count as no prose.
- It splits the masked text into sentences with `split_sentences` and the hard breaks of prose_lint.
  So it counts sentences as the detector does.
- A word is a word of `prose_text.words`. A number is a word. A placeholder is no word.
- A sentence with no word counts as no sentence.

The profile keys. Every number is an int, or a float rounded to 3 places.
- `version` is 1. `samples` is the number of sample files. `words` and `sentences` are the totals.
- `sentence_length` holds `mean`, `p10`, `p50` and `p90` of the word counts of the sentences with at
  least 3 words. A percentile is the nearest rank. All four values are `None` when no sentence
  has 3 words.
- `we_share` is the share of sentences whose first word is `we`, in lower case.
- `hedge_rate` is the number of sentences with a word of `HEDGE_WORDS` per 100 sentences.
- `passive_rate` is the number of sentences with a form of be and a participle per 100 sentences.
  The participle is the next word. It ends in `ed` after at least one character, or it is one of
  `IRREGULAR_PARTICIPLES`.
- `em_dash_per_1000` counts U+2014 in all formats and the three characters `---` in LaTeX only.
  `semicolon_per_1000` counts `;`. Both rates are per 1000 words.
- `avg_word_length` is the mean number of characters of a word.
- `top_openers` lists the ten most common first words as `[word, count]`, in lower case. A tie
  goes in the order of the word.
"""
import argparse
import json
import math
import os
import re
import sys
from collections import Counter

# `_read` is private in prose_lint. The profile reads a file the way the detector does.
from prose_lint import _read, hard_breaks
from prose_mask import detect_format, mask
from prose_text import split_sentences, words

PROG = "voice_profile.py"
FORMATS = ("latex", "markdown", "text")
VERSION = 1
MIN_WORDS = 200
MIN_LENGTH_WORDS = 3
TOP_OPENERS = 10
DEFAULT_MAX_SENTENCE_WORDS = 35
SENTENCE_LENGTH_FACTOR = 1.25

HEDGE_WORDS = tuple(
    "may might could suggest suggests suggested appear appears appeared likely possibly perhaps "
    "seem seems seemed probably".split())
BE_FORMS = frozenset("be am is are was were been being".split())
IRREGULAR_PARTICIPLES = frozenset("known shown found seen done made given taken written run set built held".split())

COUNT_KEYS = ("samples", "words", "sentences")
RATE_KEYS = ("we_share", "hedge_rate", "passive_rate", "em_dash_per_1000", "semicolon_per_1000", "avg_word_length")
LENGTH_KEYS = ("mean", "p10", "p50", "p90")
REQUIRED_KEYS = ("version",) + COUNT_KEYS + ("sentence_length",) + RATE_KEYS + ("top_openers",)

_HEDGES = frozenset(HEDGE_WORDS)
_PARTICIPLE = re.compile(r"\w+ed")


def _sentence_tokens(masked):
    """Return the lower-case words of each sentence of the masked text that holds a word."""
    text, found = masked.text, []
    for start, end in split_sentences(text, hard_breaks(masked)):
        tokens = [word.lower() for _, _, word in words(text[start:end])]
        if tokens:
            found.append(tokens)
    return found


def _has_passive(tokens):
    """Tell whether a form of be stands right before a participle."""
    return any(be in BE_FORMS and (after in IRREGULAR_PARTICIPLES or _PARTICIPLE.fullmatch(after))
               for be, after in zip(tokens, tokens[1:]))


def _percentile(ordered, percent):
    """Return the nearest-rank percentile of a sorted list. Integer arithmetic keeps the rank exact."""
    rank = (percent * len(ordered) + 99) // 100
    return ordered[max(rank - 1, 0)]


def _round(value):
    return round(float(value), 3)


def build_profile(texts_with_formats):
    """Return the voice profile of the samples as a dict.

    `texts_with_formats` holds one (text, format) pair for each sample. The format is `latex`,
    `markdown` or `text`. The profile counts all samples together. It raises ValueError for an
    unknown format and for fewer than `MIN_WORDS` words in all samples.
    """
    samples = list(texts_with_formats)
    total_words = total_letters = semicolons = dashes = 0
    sentences = []
    for text, fmt in samples:
        masked = mask(text, fmt)
        found = words(masked.text)
        total_words += len(found)
        total_letters += sum(len(word) for _, _, word in found)
        semicolons += masked.text.count(";")
        dashes += masked.text.count("\u2014") + (masked.text.count("---") if fmt == "latex" else 0)
        sentences.extend(_sentence_tokens(masked))
    if total_words < MIN_WORDS:
        raise ValueError("too little text for a profile (%d words; need %d)" % (total_words, MIN_WORDS))
    count = len(sentences)
    lengths = sorted(len(tokens) for tokens in sentences if len(tokens) >= MIN_LENGTH_WORDS)
    openers = Counter(tokens[0] for tokens in sentences)
    ranked = sorted(openers.items(), key=lambda item: (-item[1], item[0]))
    if lengths:
        spread = {"mean": _round(sum(lengths) / len(lengths)), "p10": _percentile(lengths, 10),
                  "p50": _percentile(lengths, 50), "p90": _percentile(lengths, 90)}
    else:
        spread = dict((key, None) for key in LENGTH_KEYS)
    return {
        "version": VERSION,
        "samples": len(samples),
        "words": total_words,
        "sentences": count,
        "sentence_length": spread,
        "we_share": _round(openers["we"] / count),
        "hedge_rate": _round(100 * sum(1 for t in sentences if _HEDGES.intersection(t)) / count),
        "passive_rate": _round(100 * sum(1 for t in sentences if _has_passive(t)) / count),
        "em_dash_per_1000": _round(1000 * dashes / total_words),
        "semicolon_per_1000": _round(1000 * semicolons / total_words),
        "avg_word_length": _round(total_letters / total_words),
        "top_openers": [[word, number] for word, number in ranked[:TOP_OPENERS]],
    }


def profile_json(profile):
    """Return the profile as JSON text. The keys are sorted and the text ends with a line feed."""
    return json.dumps(profile, sort_keys=True, ensure_ascii=False, indent=2) + "\n"


# Reading a profile

def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value):
    """Tell whether the value is a finite int or float. A bool is no number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:  # an int too large for a float
        return False


def _bad_openers(openers):
    return not (isinstance(openers, list) and all(
        isinstance(item, list) and len(item) == 2 and isinstance(item[0], str) and _is_int(item[1])
        for item in openers))


def load_profile(path):
    """Read a profile file and return it as a dict. Raise ValueError for a file that is not a profile.

    The message names the file and, for a bad value, the key. The file must hold UTF-8 JSON with an
    object at the top. Every key of the profile must exist, and `version` must be 1. The counts must be
    ints. The rates and the lengths must be finite numbers, and a bool is no number. No count, rate or
    length may be below 0, and `we_share` may not be above 1. `sentence_length` must hold its four keys,
    each a number or None. `top_openers` must be a list of [word, count] pairs.
    """
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError as error:
        raise ValueError("cannot read %s: %s." % (path, error.strerror or error)) from None
    try:
        profile = json.loads(data.decode("utf-8"))
    except ValueError as error:  # a bad byte or bad JSON syntax
        raise ValueError("%s is not valid JSON in UTF-8: %s." % (path, error)) from None
    if not isinstance(profile, dict):
        raise ValueError("%s must hold a JSON object." % path)

    def fail(key, problem):
        raise ValueError('%s: key "%s" %s.' % (path, key, problem))

    for key in REQUIRED_KEYS:
        if key not in profile:
            fail(key, "is missing")
    if not _is_int(profile["version"]) or profile["version"] != VERSION:
        fail("version", "must be %d" % VERSION)
    def need(name, value, is_valid, kind):
        if not is_valid(value):
            fail(name, "must be %s" % kind)
        if value < 0:
            fail(name, "must not be below 0")

    for key in COUNT_KEYS:
        need(key, profile[key], _is_int, "an int")
    for key in RATE_KEYS:
        need(key, profile[key], _is_number, "a number")
    if profile["we_share"] > 1:
        fail("we_share", "must not be above 1")
    spread = profile["sentence_length"]
    if not isinstance(spread, dict):
        fail("sentence_length", "must be an object")
    for key in LENGTH_KEYS:
        name = "sentence_length." + key
        if key not in spread:
            fail(name, "is missing")
        if spread[key] is not None:
            need(name, spread[key], _is_number, "a number or null")
    if _bad_openers(profile["top_openers"]):
        fail("top_openers", "must be a list of [word, count] pairs")
    return profile


def max_sentence_words(profile):
    """Return the longest sentence the author's voice allows, in words.

    The value is the 90th percentile of the sentence length times 1.25, rounded up. A profile with
    no 90th percentile gives 35.
    """
    p90 = profile["sentence_length"]["p90"]
    if p90 is None:
        return DEFAULT_MAX_SENTENCE_WORDS
    return int(math.ceil(p90 * SENTENCE_LENGTH_FACTOR))


# Command line

def _write(stream, text):
    """Write the text as UTF-8 bytes. A file name that is not UTF-8 keeps its original bytes."""
    stream.write(text.encode("utf-8", "surrogateescape"))
    stream.flush()


def _same_file(a, b):
    """Return True when the two paths name one file, as a hard link does. A path that is missing gives False."""
    try:
        return os.path.samefile(a, b)
    except OSError:
        return False


def _overwrite_problems(args):
    """Return a message when `--out` names a sample file. Real paths and the file decide, so any link counts."""
    if args.out is not None:
        target = os.path.realpath(args.out)
        if any(os.path.realpath(path) == target or _same_file(path, args.out) for path in args.samples):
            return ["--out would overwrite the sample file %s." % args.out]
    return []


def _parser():
    parser = argparse.ArgumentParser(prog=PROG, description="Build a voice profile from files of your own writing.")
    parser.add_argument("samples", nargs="+", metavar="SAMPLE", help="a file of your own writing")
    parser.add_argument("--format", choices=("auto",) + FORMATS, default="auto", help="default: from the extension")
    parser.add_argument("--out", metavar="FILE", help="write the JSON to this file and print nothing")
    return parser


def main(argv=None, out=None, err=None):
    """Run the command line. Return the exit code. `out` and `err` are binary streams."""
    out = out or sys.stdout.buffer
    err = err or sys.stderr.buffer
    try:
        args = _parser().parse_args(argv)
    except SystemExit as stop:
        return stop.code
    texts, problems, profile = [], _overwrite_problems(args), None
    for path in args.samples:
        text, problem = _read(path)
        if problem:
            problems.append(problem)
        else:
            texts.append((text, detect_format(path) if args.format == "auto" else args.format))
    if not problems:
        try:
            profile = build_profile(texts)
        except ValueError as error:
            problems.append(str(error))
        except Exception as error:  # a crash must not look like a profile
            problems.append("cannot build the profile: %s: %s." % (type(error).__name__, error))
    if problems:
        _write(err, "".join("%s: error: %s\n" % (PROG, problem) for problem in problems))
        return 2
    text = profile_json(profile)
    if args.out is None:
        _write(out, text)
        return 0
    try:
        with open(args.out, "wb") as handle:
            handle.write(text.encode("utf-8"))
    except OSError as error:
        _write(err, "%s: error: cannot write %s: %s.\n" % (PROG, args.out, error.strerror or error))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
