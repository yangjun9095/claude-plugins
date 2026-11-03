"""Check each proposed rewrite against ten guards before the author sees it.

Command line: `python3 prose_verify.py PROPOSALS.json [--format auto|latex|markdown|text] [--voice FILE]
[--project-dir DIR] [--json]`. Output is UTF-8 bytes. The file holds a list of proposals, or an
object with the list under `proposals`. An empty list is valid and gives `passed: 0 failed: 0`.

A proposal has these fields.
- `id`, `file`, `start`, `end`, `before`, `families`: `prose_lint.py --windows` writes them.
- `after`, `reason`: the model adds them. `reason` is a text for the author.
- `delete` (optional, bool): the proposal removes the sentence.
- `hedge_reason` (optional, text): why the rewrite changes the hedges.
The script ignores other fields, such as `occurrences` and `hits`.

The script reads `file` as the detector does, from the working directory. The offsets `start:end`
count characters of the decoded text, with CRLF kept. `--format` has the meaning and the values of
the detector option. With `auto`, the default, `detect_format` reads the extension of each file name.
Any other value sets the format of every proposal. Give the value that you gave the detector.
`--project-dir` only locates `prose-style.yaml`, as in the detector. `--voice` names a profile of
`voice_profile.py`.

The guards run on every proposal, in this order. `failed` lists each guard that fails, in this order.
1. `exact-before`: the file text at `start:end` equals `before`, and `before` occurs once in the file.
2. `masked-spans`: `before` and `after` hold the same masked spans. The count of each text matters.
3. `numbers`: `before` and `after` hold the same numeric tokens, relation signs, quantifier phrases
   and number words. The count of each item matters.
4. `no-flag`: `after` has no flagged finding of a family in mode `each`. A density family never fails.
5. `sentence-length`: no sentence of `after` has more words than the profile allows. The limit is
   35 without a profile.
6. `no-new-names`: `after` adds no name, acronym or token with a digit. A number is left to guard 3.
7. `not-longer`: `after` has at most max(ceil(1.15 * n), n + 1) words, for `n` words in `before`.
8. `no-empty`: `after` is not blank, unless `delete` is true and every family has `delete_ok`.
   A proposal with no family cannot delete.
9. `no-overlap`: the span does not overlap an earlier proposal of the same file. Spans that touch
   do not overlap. The later proposal fails. The result of the earlier proposal does not matter.
   Two names give one file when `os.path.realpath` gives one path, so a link and its target count once.
10. `hedge-kept`: `after` holds as many hedge cues as `before`. A non-empty `hedge_reason` waives the
   guard. So does the family `hedge-stack` with at least one cue left and no new cue.

Guards 2 to 7 and 10 read `before` and `after` alone. They mask each string alone, in the format of
the file. A hedge cue is a whole word of `voice_profile.HEDGE_WORDS`, in any case. A false match, such
as the month May, fails the guard. The guard prefers a false failure to a false pass.

Guard 3 in detail. The numeric tokens come from `prose_text.numeric_tokens`: a number with its
percent sign or its unit, a `/unit` part and a time unit. The noun after a number is no unit and is
not checked, so `12 mice` to `12 rats` passes. The relation signs are `<`, `>`, `~` and the characters
U+2264, U+2265, U+00B1 and U+2248. A tilde in LaTeX is a tie, so it is no sign there. The hyphen is no sign.
The quantifier phrases are `about approximately nearly over` and `at least`, `at most`, `up to`,
`more than`, `fewer than` and `less than`. The number words are `two` to `twelve`, `twenty`, `thirty`,
`forty`, `fifty`, `hundred`, `thousand`, `million`, `billion`, `half`, `twice`, `double` and `triple`.
The words `one` and `a` are no number words. A phrase or a word counts as a whole word, in any case.
`over` also counts as a preposition, so a rewrite that drops `over the plate` fails. That errs
toward failing.

Guard 4 lints `after` alone. A rewrite that merges into a neighbor sentence can show a hit only in
the final file. So can a rewrite that joins a run of repeated openers. The second run of the
detector, in step 7 of the command, catches such a hit.

Guard 6 misses a new name at the start of a sentence of `after`. So each sentence of `after` that
starts with a capitalized word that `before` lacks gives a warning. A word of `COMMON_STARTS`, a
closed list of function words and discourse adverbs, gives no warning. A warning never fails a proposal.

Output. Text has one line per proposal. A line reads `id: pass` or `id: FAIL guard1, guard2
(guard1: message; guard2: message)`. Each warning adds ` (warning: ...)` after it. The last line is
`passed: P failed: F`. With `--json` the output is one object with `results`, `passed` and `failed`.
Each result has `id`, `ok`, `failed`, `detail` and `warnings`.

The exit code is 0 when every proposal passes and 1 when one fails. It is 2 when the check cannot
run. Code 2 covers a bad option, a bad pattern file, a bad profile and a proposals file that is not
JSON or holds no list. It also covers a proposal with a missing or mistyped field, a repeated id
or an unknown family id. An unreadable file and a `start` or `end` outside the file give code 2 too.
The message names the first bad proposal. Then stdout stays empty, and the message goes to stderr.
"""
import argparse
import json
import os
import re
import sys
from collections import Counter, namedtuple

# `_read` is private in prose_lint. The guards read a file the way the detector does.
from prose_lint import FORMATS, _read, hard_breaks, lint_text
from prose_mask import detect_format, mask, piece
from prose_patterns import PatternError, load_patterns
from prose_text import numeric_tokens, protected_names, split_sentences, word_count, words
from voice_profile import DEFAULT_MAX_SENTENCE_WORDS, HEDGE_WORDS, load_profile, max_sentence_words

PROG = "prose_verify.py"
LENGTH_PERCENT = 115
SHOWN_ITEMS = 3
SHOWN_CHARACTERS = 30

_HEDGES = frozenset(HEDGE_WORDS)

# A sentence of `after` that starts with one of these words gives no warning. The list holds
# function words and discourse adverbs. It holds no technical word and no name.
COMMON_STARTS = frozenset((
    "a an the this that these those it its they them their he she his her we our us you your i my "
    "there here then thus hence therefore however moreover furthermore overall together both each every all "
    "some many most more less few several other another such same one two three four five first second third "
    "next last finally also still yet now today so but and or nor either neither if when while although though "
    "because since after before during within without between among in on at by for from of to with as into "
    "over under per via upon about against across despite unlike like once not no only even just instead rather "
    "indeed again further likewise similarly conversely consequently accordingly meanwhile otherwise "
    "nevertheless nonetheless specifically notably importantly interestingly").split())

# The `numbers` guard compares these items with the numeric tokens.
RELATION_SIGNS = "<>\u2264\u2265\u00b1\u2248~"
QUANTIFIER_PHRASES = ("at least", "at most", "up to", "more than", "fewer than", "less than",
                      "approximately", "nearly", "about", "over")
NUMBER_WORDS = tuple(
    "two three four five six seven eight nine ten eleven twelve twenty thirty forty fifty hundred thousand "
    "million billion half twice double triple".split())
_QUANTITY_WORDS = re.compile(
    r"\b(?:" + "|".join(sorted((phrase.replace(" ", r"\s+") for phrase in QUANTIFIER_PHRASES + NUMBER_WORDS),
                               key=len, reverse=True)) + r")\b", re.I)
_NUMBER_TOKEN = re.compile(r"[-+]?([0-9]+(?:[.,][0-9]+)*)(.*)\Z", re.S)
_FIELDS = ("id", "file", "start", "end", "before", "after", "families", "reason")


class ProposalError(ValueError):
    """The check cannot run. The message names the proposal, or the proposals file."""


class Result(namedtuple("Result", "id ok failed detail warnings")):
    """The outcome for one proposal.

    `failed` lists the failing guards in guard order. `detail` maps each of them to a short
    message. `warnings` lists notes that never fail the proposal.
    """

    __slots__ = ()

    def __new__(cls, id, ok, failed, detail, warnings=None):
        return super().__new__(cls, id, ok, list(failed), dict(detail), list(warnings or []))


Proposal = namedtuple("Proposal", "id file start end before after families reason delete hedge_reason")


class _Case(object):
    """One proposal with the values that its guards share."""

    def __init__(self, proposal, fmt, text, earlier, patterns, profile):
        self.proposal, self.fmt, self.text, self.earlier = proposal, fmt, text, earlier
        self.patterns = patterns
        self.before = mask(proposal.before, fmt)
        self.after = mask(proposal.after, fmt)
        self.limit = DEFAULT_MAX_SENTENCE_WORDS if profile is None else max_sentence_words(profile)


# Messages

def _show(item):
    """Return the item in quotes, on one line and cut to `SHOWN_CHARACTERS` characters."""
    one_line = " ".join(item.split())
    if len(one_line) > SHOWN_CHARACTERS:
        one_line = one_line[:SHOWN_CHARACTERS - 3] + "..."
    return '"%s"' % one_line


def _list(items):
    """Return up to `SHOWN_ITEMS` quoted items, then the number of the others."""
    shown = ", ".join(_show(item) for item in items[:SHOWN_ITEMS])
    if len(items) > SHOWN_ITEMS:
        shown += " and %d more" % (len(items) - SHOWN_ITEMS)
    return shown


def _changes(before, after):
    """Return the message for two Counters that differ, or None when they are equal."""
    lost = sorted((before - after).elements())
    gained = sorted((after - before).elements())
    if lost and gained:
        return "after lacks %s and adds %s" % (_list(lost), _list(gained))
    if lost:
        return "after lacks %s" % _list(lost)
    if gained:
        return "after adds %s" % _list(gained)
    return None


# The guards. Each takes a _Case and returns None for a pass or a short message for a failure.

def _exact_before(case):
    p = case.proposal
    if not p.before:
        return "before is empty"
    if case.text[p.start:p.end] != p.before:
        return "the file text at %d:%d differs from before" % (p.start, p.end)
    count = case.text.count(p.before)
    if count != 1:
        return "before occurs %d times in the file" % count
    return None


def _masked_spans(case):
    def texts(masked):
        return Counter(piece(masked, i) for i in range(len(masked.spans)))

    return _changes(texts(case.before), texts(case.after))


def _quantities(text, fmt):
    """Return the items that the `numbers` guard compares: tokens, relation signs, phrases and number words."""
    signs = RELATION_SIGNS.replace("~", "") if fmt == "latex" else RELATION_SIGNS
    items = list(numeric_tokens(text)) + [char for char in text if char in signs]
    items += [" ".join(match.group().lower().split()) for match in _QUANTITY_WORDS.finditer(text)]
    return items


def _numbers(case):
    return _changes(Counter(_quantities(case.before.text, case.fmt)), Counter(_quantities(case.after.text, case.fmt)))


def _no_flag(case):
    hits = [f for f in lint_text(case.proposal.after, case.fmt, case.patterns).findings
            if f.severity == "flag" and case.patterns.family(f.family).mode == "each"]
    if not hits:
        return None
    first = {}
    for hit in hits:
        first.setdefault(hit.family, hit.text)
    names = list(first)
    shown = ", ".join("%s %s" % (name, _show(first[name])) for name in names[:SHOWN_ITEMS])
    if len(names) > SHOWN_ITEMS:
        shown += " and %d more" % (len(names) - SHOWN_ITEMS)
    return "after still triggers %s" % shown


def _sentences(masked):
    """Return the text of each sentence of the masked text. The splits are those of the detector."""
    return [masked.text[start:end] for start, end in split_sentences(masked.text, hard_breaks(masked))]


def _sentence_length(case):
    longest = max([word_count(sentence) for sentence in _sentences(case.after)] or [0])
    if longest > case.limit:
        return "a sentence of after has %d words and the limit is %d" % (longest, case.limit)
    return None


def _accounted(tokens):
    """Return the name tokens that the `numbers` guard already covers for these numeric tokens.

    A numeric token covers its number, its unit parts and the number with its first unit part.
    The number with a plural unit covers a time unit that stands with no space.
    """
    covered = set()
    for token in tokens:
        number, unit = _NUMBER_TOKEN.match(token).groups()
        parts = [part for part in unit.split("/") if part and part != "%"]
        covered.update([number] + parts)
        if parts:
            covered.update([number + parts[0], number + parts[0] + "s"])
    return covered


def _no_new_names(case):
    names = protected_names(case.after.text) - protected_names(case.before.text, include_starts=True)
    added = sorted(names - _accounted(numeric_tokens(case.after.text)))
    return "after adds %s" % _list(added) if added else None


def _length_limit(count):
    """Return max(ceil(1.15 * count), count + 1). Integer arithmetic keeps the rounding exact."""
    return max((LENGTH_PERCENT * count + 99) // 100, count + 1)


def _not_longer(case):
    count = word_count(case.before.text)
    limit, now = _length_limit(count), word_count(case.after.text)
    if now > limit:
        return "after has %d words and the limit for %d words is %d" % (now, count, limit)
    return None


def _no_empty(case):
    p = case.proposal
    if p.after.strip():
        return None
    if not p.delete:
        return "after is empty and the proposal does not set delete"
    if not p.families:
        return "delete needs at least one family"
    blocked = [name for name in p.families if not case.patterns.family(name).delete_ok]
    if blocked:
        return "the family %s does not allow deletion" % blocked[0]
    return None


def _no_overlap(case):
    p = case.proposal
    for other_id, other_start, other_end in case.earlier:
        if p.start < other_end and other_start < p.end:
            return "the span %d:%d overlaps the proposal %s at %d:%d" % (p.start, p.end, other_id, other_start, other_end)
    return None


def _hedge_cues(masked):
    return sum(1 for _, _, word in words(masked.text) if word.lower() in _HEDGES)


def _hedge_kept(case):
    p = case.proposal
    before, after = _hedge_cues(case.before), _hedge_cues(case.after)
    if after == before or p.hedge_reason.strip():
        return None
    if "hedge-stack" in p.families and 1 <= after <= before:
        return None
    return "after has %d and before has %d hedge cues" % (after, before)


_CHECKS = (
    ("exact-before", _exact_before), ("masked-spans", _masked_spans), ("numbers", _numbers),
    ("no-flag", _no_flag), ("sentence-length", _sentence_length), ("no-new-names", _no_new_names),
    ("not-longer", _not_longer), ("no-empty", _no_empty), ("no-overlap", _no_overlap),
    ("hedge-kept", _hedge_kept),
)
GUARDS = tuple(name for name, _ in _CHECKS)


def _new_initial_words(case):
    """Return a warning for each capitalized first word of a sentence of `after` that `before` lacks."""
    known = set(word.lower() for _, _, word in words(case.before.text))
    found, seen = [], set()
    for sentence in _sentences(case.after):
        first = words(sentence)[:1]
        if first and first[0][2][0].isupper() and first[0][2].lower() not in known | seen | COMMON_STARTS:
            seen.add(first[0][2].lower())
            found.append('new sentence-initial word "%s"' % first[0][2])
    return found


# Proposals

def _is_text(value):
    return isinstance(value, str)


def _is_name(value):
    return isinstance(value, str) and bool(value)


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _is_bool(value):
    return isinstance(value, bool)


def _is_texts(value):
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


_KINDS = {
    "id": (_is_name, "a non-empty text"), "file": (_is_name, "a non-empty text"),
    "start": (_is_int, "a whole number"), "end": (_is_int, "a whole number"),
    "before": (_is_text, "a text"), "after": (_is_text, "a text"),
    "families": (_is_texts, "a list of texts"), "reason": (_is_text, "a text"),
    "delete": (_is_bool, "true or false"), "hedge_reason": (_is_text, "a text"),
}


def _parse(item, number, taken):
    """Return the Proposal for one item of the list. Raise ProposalError for a bad item."""
    if not isinstance(item, dict):
        raise ProposalError("proposal number %d must be a JSON object." % number)
    where = "proposal number %d" % number
    if _is_name(item.get("id")):
        where = "proposal %s" % item["id"]
    for name in _FIELDS + ("delete", "hedge_reason"):
        if name not in item:
            if name in _FIELDS:
                raise ProposalError('%s: the field "%s" is missing.' % (where, name))
            continue
        is_valid, kind = _KINDS[name]
        if not is_valid(item[name]):
            raise ProposalError('%s: the field "%s" must be %s.' % (where, name, kind))
    if item["id"] in taken:
        raise ProposalError("%s: the id is used twice." % where)
    return Proposal(item["id"], item["file"], item["start"], item["end"], item["before"], item["after"],
                    list(item["families"]), item["reason"], item.get("delete", False), item.get("hedge_reason", ""))


def _default_read(path):
    text, problem = _read(path)
    if problem:
        raise ValueError(problem)
    return text


def _check_range(where, proposal, text):
    start, end, size = proposal.start, proposal.end, len(text)
    if start < 0:
        raise ProposalError('%s: "start" must not be negative.' % where)
    if start > size:
        raise ProposalError('%s: "start" (%d) is beyond the end of the file (%d characters).' % (where, start, size))
    if end < start:
        raise ProposalError('%s: "end" (%d) is before "start" (%d).' % (where, end, start))
    if end > size:
        raise ProposalError('%s: "end" (%d) is beyond the end of the file (%d characters).' % (where, end, size))


def _file_key(path):
    """Return the key that names a file, so two spellings or a link and its target give one key."""
    try:
        return os.path.realpath(path)
    except (OSError, ValueError):  # a name with a NUL character or with a lone surrogate
        return os.path.abspath(path)


def check_proposals(proposals, patterns, profile=None, read=None, fmt="auto"):
    """Run the ten guards on each proposal. Return one Result for each, in the order of the list.

    `proposals` is a list of dicts. `patterns` comes from `load_patterns`. `profile` is a voice
    profile or None. `read(path)` returns the text of a file. The default reads it as the detector
    does and raises ValueError for a file that cannot be read. Each file is read once.
    `fmt` is `auto`, `latex`, `markdown` or `text`. With `auto` the extension of each file picks the
    format. Any other value sets the format of every file.
    Raise ProposalError at the first proposal that is malformed or that names a file, a family or
    an offset that does not exist. A guard that crashes also raises ProposalError.
    """
    if fmt != "auto" and fmt not in FORMATS:
        raise ProposalError('unknown format "%s". Use auto, latex, markdown or text.' % fmt)
    read = read or _default_read
    files, earlier, taken, results = {}, {}, set(), []
    for number, item in enumerate(proposals, 1):
        p = _parse(item, number, taken)
        where = "proposal %s" % p.id
        taken.add(p.id)
        for name in p.families:
            try:
                patterns.family(name)
            except KeyError:
                known = [family.id for family in patterns.families + patterns.disabled]
                raise ProposalError('%s: the family id "%s" is unknown. The valid ids are %s.' % (
                    where, name, ", ".join(known))) from None
        key = _file_key(p.file)
        if key not in files:
            try:
                files[key] = read(p.file)
            except (OSError, ValueError) as error:
                problem = "cannot read %s: %s." % (p.file, error.strerror or error) if isinstance(error, OSError) \
                    else str(error)
                raise ProposalError("%s: %s" % (where, problem)) from None
        text = files[key]
        _check_range(where, p, text)
        try:
            case = _Case(p, detect_format(p.file) if fmt == "auto" else fmt, text, earlier.get(key, []), patterns, profile)
            failed, detail = [], {}
            for name, guard in _CHECKS:
                message = guard(case)
                if message is not None:
                    failed.append(name)
                    detail[name] = message
            warnings = _new_initial_words(case)
        except Exception as error:  # a crash must not look like a pass
            raise ProposalError("%s: cannot check the proposal: %s: %s." % (where, type(error).__name__, error)) from None
        results.append(Result(p.id, not failed, failed, detail, warnings))
        earlier.setdefault(key, []).append((p.id, p.start, p.end))
    return results


# Command line

def _load_proposals(path):
    """Return the list of proposals in the file. Raise ProposalError for a file that holds none."""
    try:
        with open(path, "rb") as handle:
            data = handle.read()
    except OSError as error:
        raise ProposalError("cannot read %s: %s." % (path, error.strerror or error)) from None
    try:
        loaded = json.loads(data.decode("utf-8"))
    except (ValueError, RecursionError) as error:  # a bad byte or bad JSON syntax
        raise ProposalError("%s is not valid JSON in UTF-8: %s." % (path, error)) from None
    if isinstance(loaded, dict):
        loaded = loaded.get("proposals")
    if not isinstance(loaded, list):
        raise ProposalError('%s must hold a list of proposals, or an object with a list under "proposals".' % path)
    return loaded


def _text_output(results):
    lines = []
    for result in results:
        if result.ok:
            line = "%s: pass" % result.id
        else:
            line = "%s: FAIL %s (%s)" % (result.id, ", ".join(result.failed),
                                         "; ".join("%s: %s" % (name, result.detail[name]) for name in result.failed))
        lines.append(line + "".join(" (warning: %s)" % warning for warning in result.warnings))
    passed = sum(1 for result in results if result.ok)
    lines.append("passed: %d failed: %d" % (passed, len(results) - passed))
    return "\n".join(lines) + "\n"


def _json_output(results):
    passed = sum(1 for result in results if result.ok)
    shown = [{"id": r.id, "ok": r.ok, "failed": r.failed, "detail": r.detail, "warnings": r.warnings} for r in results]
    return json.dumps({"results": shown, "passed": passed, "failed": len(results) - passed},
                      ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def _write(stream, text):
    """Write the text as UTF-8 bytes. A file name that is not UTF-8 keeps its original bytes."""
    try:
        data = text.encode("utf-8", "surrogateescape")
    except UnicodeEncodeError:  # a lone surrogate that is no escaped byte
        data = text.encode("utf-8", "backslashreplace")
    stream.write(data)
    stream.flush()


def _parser():
    parser = argparse.ArgumentParser(prog=PROG, description="Check proposed rewrites against the guards.")
    parser.add_argument("proposals", metavar="PROPOSALS", help="a JSON file with a list of proposals")
    parser.add_argument("--format", choices=("auto",) + FORMATS, default="auto", help="default: from the extension")
    parser.add_argument("--voice", metavar="FILE", help="a voice profile from voice_profile.py")
    parser.add_argument("--project-dir", default=".", metavar="DIR", help="default: the working directory")
    parser.add_argument("--json", action="store_true", help="print the results as JSON")
    return parser


def main(argv=None, out=None, err=None):
    """Run the command line. Return the exit code. `out` and `err` are binary streams."""
    out = out or sys.stdout.buffer
    err = err or sys.stderr.buffer
    try:
        args = _parser().parse_args(argv)
    except SystemExit as stop:
        return stop.code
    problem, results = None, None
    if not os.path.isdir(args.project_dir):
        problem = "project directory not found: %s" % args.project_dir
    else:
        try:
            patterns = load_patterns(args.project_dir)
            profile = load_profile(args.voice) if args.voice is not None else None
            results = check_proposals(_load_proposals(args.proposals), patterns, profile, fmt=args.format)
        except (PatternError, ProposalError, ValueError) as error:
            problem = str(error)
    if problem is not None:
        _write(err, "%s: error: %s\n" % (PROG, problem))
        return 2
    _write(out, _json_output(results) if args.json else _text_output(results))
    return 0 if all(result.ok for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
