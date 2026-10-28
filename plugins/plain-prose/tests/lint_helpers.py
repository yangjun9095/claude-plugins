"""Shared builders for the tests of prose_lint. All text is made up.

The module puts the scripts folder on `sys.path`, loads the real pattern data once, and offers
these helpers.
- `lint(text, fmt)` runs the detector on a string and returns a LintResult.
- `patched(family_id, params=None, **fields)` returns the patterns with one family changed.
- `padded(n, extras)` builds a plain text of exactly n words that holds the extra sentences.
- `run_main(args)` runs the command line in this process. `run_script(args)` runs it as a script.
- `sentences_of(text, fmt)` returns the original text of each sentence. It finds the sentences
  without the offset map of prose_lint, so a test can check the hard breaks on their own.
- `FIRES`, `FAMILY_CLEAN` and `CLEAN` are the seeded and plain sentences of the pattern tests.
"""
import copy
import io
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(HERE)
SCRIPTS_DIR = os.path.join(PLUGIN_DIR, "scripts")
SCRIPT = os.path.join(SCRIPTS_DIR, "prose_lint.py")
for _path in (SCRIPTS_DIR, HERE):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import prose_lint as pl  # noqa: E402
import prose_patterns as pp  # noqa: E402
from prose_mask import mask, unmask  # noqa: E402
from prose_text import split_sentences, word_count  # noqa: E402
from test_patterns import CLEAN, FAMILY_CLEAN, FIRES  # noqa: E402,F401

PATTERNS = pp.load_patterns()

# Plain sentences of 9 to 15 words. No two start with the same two words, and no rule flags one.
FILLER = [
    "The sample was small and the plates dried before the scan.",
    "Each plate held twelve wells with a clear label on the lid.",
    "After the wash, cells were counted under a light microscope in four fields.",
    "Growth slowed in the mutant line after the third day of heat shock.",
    "A second group received the same buffer without the drug.",
    "Expression of the reporter rose in the root tip and fell in the leaf.",
    "Mice were housed in groups of four with free access to water.",
    "Reads were aligned to the reference genome with the default settings.",
    "Samples from the northern site arrived on ice within two hours.",
    "Our records list the date, the site and the name of each collector.",
    "Both strains reached the same density by the end of the week.",
    "Tubes were spun for ten minutes and the supernatant was removed.",
    "Seeds were sown on moist paper and kept in the dark for two days.",
    "No plate showed signs of contamination during the whole run.",
    "Fish were fed twice a day and tanks were cleaned each week.",
    "Then the filters were rinsed with cold water and dried in air.",
    "Several leaves from each plant were cut and weighed on a fine scale.",
    "Pairs of lines were crossed to give seeds for the next round.",
    "Data from the first run were stored on the lab server.",
    "Each reading was repeated three times and the mean was kept.",
    "Older plants grew taller than younger plants in every pot.",
    "Where the signal was weak, the slides were scanned a second time.",
    "Visits to the field site took place in spring and in autumn.",
    "One tube of each batch was frozen for later checks.",
    "Cells from the control group divided at a steady pace.",
    "During the second week the room stayed at twenty degrees.",
    "Frozen tissue was ground in a cold mortar with a small pestle.",
    "Counts from the two observers differed by less than five percent.",
    "Small gaps in the data were filled from the backup files.",
    "Late in the day the plates were moved to the warm room.",
]
# The pad sentence closes a text. It takes the first r of these 18 words.
PAD = "Quiet notes closed the long day without any further comment from the tired crew of the lab bench".split()

EM_SENTENCE = "The mutant grew slowly \u2014 and the control did not."


def filler_words(count):
    """Return plain paragraphs of exactly `count` words, five sentences to a paragraph."""
    sentences, total, i = [], 0, 0
    while True:
        sentence = FILLER[i % len(FILLER)]
        size = word_count(sentence)
        if total + size > count:
            break
        sentences.append(sentence)
        total += size
        i += 1
    if count > total:
        sentences.append(" ".join(PAD[:count - total]) + ".")
    paragraphs = [" ".join(sentences[k:k + 5]) for k in range(0, len(sentences), 5)]
    return "\n\n".join(paragraphs)


def padded(count, extras=()):
    """Return a plain text of exactly `count` words. Each extra sentence is its own paragraph."""
    base = filler_words(count - sum(word_count(extra) for extra in extras))
    paragraphs = base.split("\n\n")
    for k, extra in enumerate(extras):
        paragraphs.insert((k + 1) * len(paragraphs) // (len(extras) + 1) + k, extra)
    return "\n\n".join(paragraphs) + "\n"


def lint(text, fmt="text", patterns=None):
    return pl.lint_text(text, fmt, patterns or PATTERNS)


def patched(family_id, params=None, **fields):
    """Return a Patterns object in which one family has other params or fields. The data stays unchanged."""
    families = []
    for family in PATTERNS.families:
        if family.id == family_id:
            family = copy.copy(family)
            if params:
                family.params = dict(family.params, **params)
            for name, value in fields.items():
                setattr(family, name, value)
        families.append(family)
    return pp.Patterns(families, PATTERNS.as_of)


def of_family(result, family):
    return [f for f in result.findings if f.family == family]


def sentences_of(text, fmt):
    """Return the original text of each sentence that split_sentences finds with the hard breaks."""
    masked = mask(text, fmt)
    found = split_sentences(masked.text, pl.hard_breaks(masked))
    return [unmask(masked._replace(text=masked.text[s:e])) for s, e in found]


class Folder(object):
    """A temporary folder with a `write` helper. Use it as a context manager."""

    def __enter__(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = self.dir.name
        return self

    def __exit__(self, *exc):
        self.dir.cleanup()

    def path(self, name):
        return os.path.join(self.root, *name.split("/"))

    def write(self, name, data):
        path = self.path(name)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as handle:
            handle.write(data if isinstance(data, bytes) else data.encode("utf-8"))
        return path


def run_main(args):
    """Run `prose_lint.main` in this process. Return (exit code, stdout text, stderr text).

    The call passes an empty project folder unless the arguments name one, so no file of the
    working directory changes the result.
    """
    args = list(args)
    out, err = io.BytesIO(), io.BytesIO()
    with Folder() as empty:
        if "--project-dir" not in args:
            args += ["--project-dir", empty.root]
        code = pl.main(args, out, err)
    return code, out.getvalue().decode("utf-8"), err.getvalue().decode("utf-8")


def run_script(args, locale="C"):
    """Run `python3 prose_lint.py` in a child process. Return (exit code, stdout bytes, stderr bytes)."""
    env = dict(os.environ)
    env["LC_ALL"] = locale
    env.pop("PYTHONIOENCODING", None)
    with Folder() as empty:
        args = list(args)
        if "--project-dir" not in args:
            args += ["--project-dir", empty.root]
        proc = subprocess.run([sys.executable, "-B", SCRIPT] + args, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, env=env)
    return proc.returncode, proc.stdout, proc.stderr
