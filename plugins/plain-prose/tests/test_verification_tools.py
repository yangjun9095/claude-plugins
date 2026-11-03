"""Tests for the verification fixtures and the verification tools. All text in this file is made up.

The class names are FixtureTests, FixtureDetectorTests, ManuscriptTests, PrecisionTests,
DiffReportTests and AbSampleTests.

Fixtures. `tests/verification/fixtures/paragraphs.json` holds 60 paragraphs with the ids p01 to p60,
in this order. 30 are seeded and 30 are clean. Each paragraph has 3 to 6 sentences. Each seeded
entry is a family id. Each family that prose can seed has 3 seeded paragraphs at least, and the two
density families `em-dash` and `vocabulary-density` have 1 at least. Each `legit` entry is a non-empty
string, and the legit names of the legitimate science uses are present. The text holds ASCII and the
em dash only. It holds no home path, no e-mail address, no URL and no name except the invented
names of ALLOWED_NAMES.

Fixtures and the detector. The writer did not tune the fixtures to the detector (see the README of
`tests/verification`). So the detector flags some clean paragraphs. EXPECTED_CLEAN_FLAGS lists those
known false positives. The test checks that the clean flags equal this list. It also checks that at
least 80 percent of the seeded paragraphs have a flagged finding of a seeded family, and that each
family fires in one seeded paragraph at least. When the pattern data change, read each new or lost
flag, then update the list on purpose.

Tools. Each tool runs as a script. The tests check the exit codes and the output.
- `make_manuscript.py` is deterministic, writes only inside OUT_DIR, refuses a folder that holds a
  file, and writes LaTeX that survives the mask round trip and uses all 60 paragraphs.
- `precision.py rows` has stable keys. `precision.py report` exits 2 for a missing label, for a
  label without a finding and for a label other than right or wrong. It computes the precision of
  each family on a hand-made case and prints no figure that adds the families together.
- `diff_report.py` lists the changed sentence, exits 0 on a clean rewrite, and exits 1 when a number
  changes, a citation drops or a masked span changes.
- `ab_sample.py` is deterministic for a seed, depends on the seed, hides the revised side, writes a key
  that maps every item, and refuses when fewer than `n` sentences changed.
"""
import io
import itertools
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN_DIR = os.path.dirname(HERE)
SCRIPTS_DIR = os.path.join(PLUGIN_DIR, "scripts")
VERIFY_DIR = os.path.join(HERE, "verification")
FIXTURES = os.path.join(VERIFY_DIR, "fixtures", "paragraphs.json")
for _path in (SCRIPTS_DIR,):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import prose_lint as pl  # noqa: E402
from prose_mask import mask, unmask  # noqa: E402
from prose_patterns import load_patterns  # noqa: E402
from prose_text import split_sentences, word_count  # noqa: E402

PATTERNS = load_patterns()
FAMILY_IDS = [family.id for family in PATTERNS.families]
DENSITY_ONLY = ("em-dash", "vocabulary-density")
SEEDABLE = [name for name in FAMILY_IDS if name not in DENSITY_ONLY]
EM_DASH = "\u2014"

# The names in the invented citations of the fixtures. No other name may appear.
ALLOWED_NAMES = ("Brantwick", "Quenby", "Marchbanks", "Ludgrove", "Fenwhistle")

# The legit names that the clean paragraphs must use at least once.
REQUIRED_LEGIT = (
    "hedge-qualifying-inference", "passive-methods", "we-first-person", "single-em-dash", "taken-together-once",
    "genuine-question", "robust-statistical-term", "comprehensive-technical-term", "key-literature-sense",
    "serves-as-literal-role", "list-after-colon")

# The known false positives: (paragraph id, family, rule label) of each flagged finding on a clean paragraph.
# Each one is a legitimate use that a word or phrase rule cannot tell from the style use.
EXPECTED_CLEAN_FLAGS = [
    ("p09", "em-dash", "em dash"),  # one em dash that a human writes; a short text puts the rate over the limit
    ("p10", "recap-opener", "recap opener"),  # "Taken together" that draws a new inference
    ("p35", "recap-opener", "recap opener"),  # same
    ("p39", "rhetorical-question", "question_answer"),  # a genuine open question in a Discussion
    ("p52", "vocabulary-density", "paradigm"),  # "adapted this paradigm": no local context names the design
]

SLASH = "/"  # The path patterns below come from parts, so this file does not match its own privacy scan.
PRIVATE_PATTERNS = (
    ("path", re.compile("(?<![\\w.-])" + SLASH + "(?:home|Users|hpc|scratch|mnt|gpfs|projects)" + SLASH)),
    ("windows path", re.compile("[A-Z]:" + chr(92) + chr(92))),
    ("e-mail", re.compile("[A-Za-z0-9._-]+" + chr(64) + "[A-Za-z0-9-]+\\.[A-Za-z]")),
    ("url", re.compile("(?:https?:" + SLASH + SLASH + "|www\\.)")),
    ("doi", re.compile("\\b10\\.\\d{4,9}" + SLASH)),
    ("title", re.compile("\\b(?:Dr|Prof|Mr|Mrs|Ms)\\.? [A-Z]")),
)
_ET_AL = re.compile("\\b([A-Z][A-Za-z'-]+) et al\\.")
_YEAR_CITATION = re.compile("\\(([A-Z][A-Za-z'-]+(?: (?:and|&) [A-Z][A-Za-z'-]+)?),? (?:1[5-9]|20)\\d\\d[a-z]?\\)")
_AND_YEAR = re.compile("\\b([A-Z][A-Za-z'-]+) (?:and|&) ([A-Z][A-Za-z'-]+) \\((?:1[5-9]|20)\\d\\d[a-z]?\\)")


def private_hits(text):
    """Return the (label, snippet) of each private item in the text."""
    return [(label, m.group(0)) for label, pattern in PRIVATE_PATTERNS for m in pattern.finditer(text)]


def unknown_names(text, allowed=ALLOWED_NAMES):
    """Return the surnames in citation forms that the allowed list does not hold."""
    found = set(_ET_AL.findall(text))
    for group in _YEAR_CITATION.findall(text):
        found.update(re.split(" (?:and|&) ", group))
    for pair in _AND_YEAR.findall(text):
        found.update(pair)
    return sorted(name for name in found if name not in allowed)


def used_names(text):
    found = set(_ET_AL.findall(text))
    return found


def load_fixtures():
    with io.open(FIXTURES, encoding="utf-8") as handle:
        return json.load(handle)


FIXTURE_ROWS = load_fixtures()


def run_tool(name, *args, **kwargs):
    """Run a tool as a script. Return (exit code, stdout, stderr) as text. `cwd` is optional."""
    env = dict(os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    command = [sys.executable, "-B", os.path.join(VERIFY_DIR, name)] + [str(a) for a in args]
    proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env, cwd=kwargs.get("cwd"))
    return proc.returncode, proc.stdout.decode("utf-8"), proc.stderr.decode("utf-8")


def tree(root):
    """Return the set of relative paths of the files and folders under root. Compiled files stay out."""
    found = set()
    for folder, dirs, names in os.walk(root):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for name in dirs + names:
            if not name.endswith(".pyc"):
                found.add(os.path.relpath(os.path.join(folder, name), root))
    return found


class ScratchCase(unittest.TestCase):
    def scratch(self):
        path = tempfile.mkdtemp(prefix="verify-")
        self.addCleanup(shutil.rmtree, path, True)
        return path

    def write(self, folder, name, text):
        path = os.path.join(folder, name)
        with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        return path

    def read(self, path):
        with io.open(path, encoding="utf-8") as handle:
            return handle.read()


class FixtureTests(unittest.TestCase):
    def test_sixty_paragraphs_with_the_ids_p01_to_p60_in_order(self):
        self.assertEqual(len(FIXTURE_ROWS), 60)
        self.assertEqual([row["id"] for row in FIXTURE_ROWS], ["p%02d" % n for n in range(1, 61)])
        self.assertEqual(len(set(row["id"] for row in FIXTURE_ROWS)), 60)

    def test_every_row_has_the_four_fields(self):
        for row in FIXTURE_ROWS:
            with self.subTest(id=row["id"]):
                self.assertEqual(sorted(row), ["id", "legit", "seeded", "text"])
                self.assertIsInstance(row["text"], str)
                self.assertIsInstance(row["seeded"], list)
                self.assertIsInstance(row["legit"], list)

    def test_thirty_are_seeded_and_thirty_are_clean(self):
        self.assertEqual(sum(1 for row in FIXTURE_ROWS if row["seeded"]), 30)
        self.assertEqual(sum(1 for row in FIXTURE_ROWS if not row["seeded"]), 30)

    def test_every_seeded_entry_is_a_family_id(self):
        for row in FIXTURE_ROWS:
            for name in row["seeded"]:
                with self.subTest(id=row["id"], family=name):
                    self.assertIn(name, FAMILY_IDS)

    def test_a_seeded_paragraph_holds_one_to_three_different_families(self):
        for row in FIXTURE_ROWS:
            if row["seeded"]:
                with self.subTest(id=row["id"]):
                    self.assertTrue(1 <= len(row["seeded"]) <= 3)
                    self.assertEqual(len(set(row["seeded"])), len(row["seeded"]))

    def test_every_legit_entry_is_a_non_empty_string(self):
        for row in FIXTURE_ROWS:
            for entry in row["legit"]:
                with self.subTest(id=row["id"], entry=entry):
                    self.assertIsInstance(entry, str)
                    self.assertTrue(entry.strip())

    def test_only_clean_paragraphs_name_a_legit_use(self):
        for row in FIXTURE_ROWS:
            if row["seeded"]:
                self.assertEqual(row["legit"], [], row["id"])

    def test_the_legitimate_uses_of_the_ruling_are_present(self):
        names = set(name for row in FIXTURE_ROWS for name in row["legit"])
        for name in REQUIRED_LEGIT:
            with self.subTest(name=name):
                self.assertIn(name, names)

    def test_most_clean_paragraphs_name_a_legit_use(self):
        named = sum(1 for row in FIXTURE_ROWS if not row["seeded"] and row["legit"])
        self.assertGreaterEqual(named, 25)

    def test_each_paragraph_has_three_to_six_sentences(self):
        for row in FIXTURE_ROWS:
            with self.subTest(id=row["id"]):
                count = len(split_sentences(row["text"]))
                self.assertTrue(3 <= count <= 6, count)

    def test_each_seedable_family_has_three_seeded_paragraphs_and_each_density_family_one(self):
        counts = Counter(name for row in FIXTURE_ROWS for name in row["seeded"])
        for name in SEEDABLE:
            with self.subTest(family=name):
                self.assertGreaterEqual(counts[name], 3)
        for name in DENSITY_ONLY:
            with self.subTest(family=name):
                self.assertGreaterEqual(counts[name], 1)

    def test_the_family_list_has_the_17_ids_that_the_ruling_names(self):
        self.assertEqual(len(FAMILY_IDS), 17)
        self.assertEqual(len(SEEDABLE), 15)

    def test_the_order_is_mixed(self):
        kinds = [bool(row["seeded"]) for row in FIXTURE_ROWS]
        self.assertTrue(10 <= sum(kinds[:30]) <= 20, "the first 30 paragraphs hold %d seeded" % sum(kinds[:30]))
        self.assertLessEqual(max(len(list(g)) for _, g in itertools.groupby(kinds)), 8)
        firsts = [row["seeded"][0] for row in FIXTURE_ROWS if row["seeded"]]
        self.assertNotEqual(firsts, sorted(firsts))
        self.assertLessEqual(sum(1 for a, b in zip(firsts, firsts[1:]) if a == b), 4)

    def test_the_text_holds_ascii_and_the_em_dash_only(self):
        for row in FIXTURE_ROWS:
            with self.subTest(id=row["id"]):
                self.assertLessEqual(set(ch for ch in row["text"] if ord(ch) > 127), {EM_DASH})
                self.assertEqual(row["text"], row["text"].strip())
                self.assertNotIn("\n", row["text"])

    def test_the_fixtures_hold_no_private_text(self):
        for row in FIXTURE_ROWS:
            with self.subTest(id=row["id"]):
                self.assertEqual(private_hits(row["text"]), [])
        with io.open(FIXTURES, encoding="utf-8") as handle:
            self.assertEqual(private_hits(handle.read()), [])

    def test_the_only_names_are_the_invented_ones(self):
        for row in FIXTURE_ROWS:
            with self.subTest(id=row["id"]):
                self.assertEqual(unknown_names(row["text"]), [])

    def test_the_invented_names_are_used(self):
        used = set()
        for row in FIXTURE_ROWS:
            used |= used_names(row["text"])
        self.assertEqual(sorted(used), sorted(ALLOWED_NAMES))

    def test_the_private_text_patterns_find_made_up_private_text(self):
        samples = (
            ("path", SLASH + "home" + SLASH + "someone/work"),
            ("path", "see " + SLASH + "hpc" + SLASH + "projects/x"),
            ("path", SLASH + "Users" + SLASH + "someone"),
            ("windows path", "C:" + chr(92) + chr(92) + "Users"),
            ("e-mail", "someone" + chr(64) + "university.edu"),
            ("url", "see https:" + SLASH + SLASH + "example.org"),
            ("url", "see www.example.org"),
            ("doi", "see 10.1234" + SLASH + "abc"),
            ("title", "Dr. Someone said"),
        )
        for label, text in samples:
            with self.subTest(text=text):
                self.assertIn(label, [hit[0] for hit in private_hits(text)])
        for text in ("a relative path docs" + SLASH + "scratch" + SLASH + "x", "the word home and the word hpc", "p < 0.05 and n = 12"):
            with self.subTest(text=text):
                self.assertEqual(private_hits(text), [])

    def test_the_name_check_finds_a_real_looking_name_and_accepts_an_invented_one(self):
        self.assertEqual(unknown_names("as shown (Smith et al., 2020)"), ["Smith"])
        self.assertEqual(unknown_names("Smith et al. showed it"), ["Smith"])
        self.assertEqual(unknown_names("(Jones and Lee, 2019)"), ["Jones", "Lee"])
        self.assertEqual(unknown_names("(Jones, 2019)"), ["Jones"])
        self.assertEqual(unknown_names("Jones and Lee (2019) said"), ["Jones", "Lee"])
        self.assertEqual(unknown_names("(Brantwick et al., 2018; Quenby et al., 2020)"), [])
        self.assertEqual(unknown_names("Marlin-2 and Tavo (Fig. 2) rose in 2019"), [])


def lint_rows(text):
    """Return the findings of the detector on one paragraph as plain text."""
    return pl.lint_text(text + "\n", "text", PATTERNS).findings


class FixtureDetectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.flags = {}
        for row in FIXTURE_ROWS:
            cls.flags[row["id"]] = [f for f in lint_rows(row["text"]) if f.severity == "flag"]

    def test_the_clean_flags_equal_the_known_false_positives(self):
        found = sorted((row["id"], f.family, f.rule_label)
                       for row in FIXTURE_ROWS if not row["seeded"] for f in self.flags[row["id"]])
        self.assertEqual(found, EXPECTED_CLEAN_FLAGS)

    def test_the_known_false_positives_are_sorted_and_name_clean_paragraphs_and_families(self):
        self.assertEqual(EXPECTED_CLEAN_FLAGS, sorted(EXPECTED_CLEAN_FLAGS))
        clean = set(row["id"] for row in FIXTURE_ROWS if not row["seeded"])
        for paragraph, family, label in EXPECTED_CLEAN_FLAGS:
            self.assertIn(paragraph, clean)
            self.assertIn(family, FAMILY_IDS)
            self.assertTrue(label)

    def test_at_least_80_percent_of_the_seeded_paragraphs_have_a_finding_of_a_seeded_family(self):
        seeded = [row for row in FIXTURE_ROWS if row["seeded"]]
        hit = [row["id"] for row in seeded if any(f.family in row["seeded"] for f in self.flags[row["id"]])]
        self.assertGreaterEqual(len(hit) * 100, 80 * len(seeded), "%d of %d" % (len(hit), len(seeded)))

    def test_each_family_fires_in_a_seeded_paragraph_of_its_own(self):
        for name in FAMILY_IDS:
            with self.subTest(family=name):
                rows = [row for row in FIXTURE_ROWS if name in row["seeded"]]
                self.assertTrue(rows)
                self.assertTrue(any(f.family == name for row in rows for f in self.flags[row["id"]]))

    def test_precision_rows_agree_with_the_detector_on_the_count_of_flagged_findings(self):
        code, out, err = run_tool("precision.py", "rows")
        self.assertEqual((code, err), (0, ""))
        expected = sum(len(found) for found in self.flags.values())
        self.assertEqual(len(out.splitlines()), expected)
        self.assertGreater(expected, 0)


class ManuscriptTests(ScratchCase):
    def make(self, folder):
        return run_tool("make_manuscript.py", folder)

    def test_two_runs_give_the_same_bytes(self):
        base = self.scratch()
        first, second = os.path.join(base, "one"), os.path.join(base, "two")
        self.assertEqual(self.make(first)[0], 0)
        self.assertEqual(self.make(second)[0], 0)
        for name in ("main.tex", "refs.bib"):
            with io.open(os.path.join(first, name), "rb") as a, io.open(os.path.join(second, name), "rb") as b:
                self.assertEqual(a.read(), b.read(), name)

    def test_it_writes_two_files_inside_out_dir_and_nothing_outside(self):
        base, cwd = self.scratch(), self.scratch()
        out = os.path.join(base, "made")
        before = {"base": tree(base), "cwd": tree(cwd), "tool": tree(VERIFY_DIR)}
        code, stdout, stderr = run_tool("make_manuscript.py", out, cwd=cwd)
        self.assertEqual((code, stdout, stderr), (0, "", ""))
        self.assertEqual(tree(base), before["base"] | {"made", os.path.join("made", "main.tex"), os.path.join("made", "refs.bib")})
        self.assertEqual(tree(cwd), before["cwd"])
        self.assertEqual(tree(VERIFY_DIR), before["tool"])

    def test_it_writes_inside_an_empty_folder_and_a_nested_new_folder(self):
        base = self.scratch()
        empty = os.path.join(base, "empty")
        os.mkdir(empty)
        self.assertEqual(self.make(empty)[0], 0)
        self.assertEqual(sorted(os.listdir(empty)), ["main.tex", "refs.bib"])
        nested = os.path.join(base, "a", "b")
        self.assertEqual(self.make(nested)[0], 0)
        self.assertEqual(sorted(os.listdir(nested)), ["main.tex", "refs.bib"])

    def test_it_refuses_a_folder_that_holds_a_file(self):
        base = self.scratch()
        out = os.path.join(base, "busy")
        os.mkdir(out)
        mine = self.write(out, "notes.txt", "keep me\n")
        code, stdout, stderr = self.make(out)
        self.assertEqual(code, 2)
        self.assertEqual(stdout, "")
        self.assertIn("not empty", stderr)
        self.assertEqual(os.listdir(out), ["notes.txt"])
        self.assertEqual(self.read(mine), "keep me\n")

    def test_it_refuses_a_folder_that_holds_only_a_folder(self):
        base = self.scratch()
        out = os.path.join(base, "busy")
        os.makedirs(os.path.join(out, "sub"))
        code, _, stderr = self.make(out)
        self.assertEqual(code, 2)
        self.assertIn("not empty", stderr)
        self.assertEqual(os.listdir(out), ["sub"])

    def test_it_refuses_a_path_that_is_a_file(self):
        base = self.scratch()
        path = self.write(base, "plain.txt", "x\n")
        code, _, stderr = self.make(path)
        self.assertEqual(code, 2)
        self.assertIn("not a folder", stderr)
        self.assertEqual(self.read(path), "x\n")

    def test_it_needs_one_argument(self):
        self.assertEqual(run_tool("make_manuscript.py")[0], 2)

    def manuscript(self):
        out = os.path.join(self.scratch(), "made")
        self.assertEqual(self.make(out)[0], 0)
        return self.read(os.path.join(out, "main.tex")), self.read(os.path.join(out, "refs.bib"))

    def test_the_manuscript_has_the_required_parts(self):
        tex, bib = self.manuscript()
        for name in ("Introduction", "Methods", "Results", "Discussion"):
            self.assertIn("\\section{%s}" % name, tex)
        self.assertEqual(tex.count("\\begin{figure}"), 1)
        self.assertEqual(tex.count("\\begin{equation}"), 2)
        self.assertEqual(tex.count("\\begin{table}"), 1)
        self.assertGreaterEqual(len(re.findall(r"\\cite\{", tex)), 2)
        self.assertGreaterEqual(len(re.findall(r"\\citep\{", tex)), 4)
        begins = Counter(re.findall(r"\\begin\{([a-z*]+)\}", tex))
        ends = Counter(re.findall(r"\\end\{([a-z*]+)\}", tex))
        self.assertEqual(begins, ends)

    def test_every_cite_key_has_a_bib_entry(self):
        tex, bib = self.manuscript()
        keys = set()
        for group in re.findall(r"\\cite[a-z]*\{([^}]*)\}", tex):
            keys.update(group.split(","))
        entries = re.findall(r"@article\{([a-z0-9]+),", bib)
        self.assertTrue(keys)
        self.assertEqual(sorted(keys), sorted(entries))
        self.assertEqual(len(entries), len(set(entries)))

    def test_it_uses_all_sixty_paragraphs(self):
        tex, _ = self.manuscript()
        for row in FIXTURE_ROWS:
            with self.subTest(id=row["id"]):
                for chunk in re.split(r"\((?:[A-Z][a-z]+ et al\., \d{4}(?:; )?)+\)", row["text"]):
                    if chunk.strip():
                        self.assertIn(chunk.replace("%", "\\%"), tex)

    def test_a_percent_sign_never_starts_a_comment(self):
        tex, _ = self.manuscript()
        self.assertEqual(re.findall(r"(?<!\\)%", tex), [])

    def test_a_citation_becomes_a_cite_command(self):
        tex, _ = self.manuscript()
        self.assertIn("\\citep{brantwick2018}", tex)
        self.assertIn("\\citep{marchbanks2019,ludgrove2021}", tex)
        self.assertNotIn("et al.,", tex)

    def test_the_output_passes_the_mask_round_trip(self):
        tex, bib = self.manuscript()
        for text in (tex, bib):
            self.assertEqual(unmask(mask(text, "latex")), text)
        masked = mask(tex, "latex")
        cites = sum(1 for span in masked.spans if span.kind == "cite")
        self.assertEqual(cites, len(re.findall(r"\\cite[a-z]*\{", tex)))
        visible = word_count(masked.text)
        stripped = [re.sub(r"\((?:[A-Z][a-z]+ et al\., \d{4}(?:; )?)+\)", "", row["text"]) for row in FIXTURE_ROWS]
        self.assertGreaterEqual(visible, sum(word_count(text) for text in stripped))

    def test_the_detector_reads_the_manuscript_without_an_error(self):
        out = os.path.join(self.scratch(), "made")
        self.make(out)
        proc = subprocess.run([sys.executable, "-B", os.path.join(SCRIPTS_DIR, "prose_lint.py"), os.path.join(out, "main.tex")],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        self.assertIn(proc.returncode, (0, 1))
        self.assertEqual(proc.stderr, b"")


HAND = [
    {"id": "h1", "seeded": ["hedge-stack"], "legit": [],
     "text": "Marlin-2 may possibly limit root growth (Fig. 2). We measured growth in 12 plants. The assay ran for 6 h."},
    {"id": "h2", "seeded": ["hedge-stack"], "legit": [],
     "text": "These data could potentially suggest that Tavo acts upstream of Marlin-2. The delay lasted 6 h. We tested 12 plants."},
    {"id": "h3", "seeded": ["hedge-stack", "assistant-residue"], "legit": [],
     "text": ("Tavo might possibly act in two pathways. As an AI language model, I cannot verify these values. "
              "The signal rose by 20% in 9 samples.")},
    {"id": "h4", "seeded": [], "legit": ["a made-up use"],
     "text": "Growth may possibly slow in the mutant. We measured 14 plants over 10 days. The plants grew in a chamber."},
]
HAND_KEYS = ["h1:1", "h2:1", "h3:1", "h3:2", "h3:3", "h4:1"]
HAND_LABELS = {"h1:1": "right", "h2:1": "wrong", "h3:1": "right", "h3:2": "right", "h3:3": "right", "h4:1": "wrong"}


class PrecisionTests(ScratchCase):
    def hand_files(self, labels=None):
        folder = self.scratch()
        paragraphs = self.write(folder, "hand.json", json.dumps(HAND))
        path = self.write(folder, "labels.json", json.dumps(HAND_LABELS if labels is None else labels))
        return paragraphs, path

    def report(self, labels=None):
        paragraphs, path = self.hand_files(labels)
        return run_tool("precision.py", "report", path, "--paragraphs", paragraphs)

    def test_rows_keys_are_stable_across_two_runs(self):
        first = run_tool("precision.py", "rows")
        second = run_tool("precision.py", "rows")
        self.assertEqual(first[0], 0)
        self.assertEqual(first, second)
        keys = [line.split("\t")[0] for line in first[1].splitlines()]
        self.assertTrue(keys)
        self.assertEqual(len(set(keys)), len(keys))
        for key in keys:
            self.assertRegex(key, r"^p\d\d:[1-9]\d*$")

    def test_rows_hold_the_key_the_family_the_kind_the_text_and_the_sentence(self):
        _, out, _ = run_tool("precision.py", "rows")
        kinds = {row["id"]: bool(row["seeded"]) for row in FIXTURE_ROWS}
        for line in out.splitlines():
            fields = line.split("\t")
            self.assertEqual(len(fields), 5, line)
            key, family, kind, text, sentence = fields
            self.assertIn(family, FAMILY_IDS)
            self.assertEqual(kind, "seeded" if kinds[key.split(":")[0]] else "clean")
            self.assertIsInstance(json.loads(text), str)
            self.assertIn(json.loads(text), json.loads(sentence))

    def test_rows_on_the_hand_made_case(self):
        paragraphs, _ = self.hand_files()
        code, out, err = run_tool("precision.py", "rows", "--paragraphs", paragraphs)
        self.assertEqual((code, err), (0, ""))
        self.assertEqual([line.split("\t")[0] for line in out.splitlines()], HAND_KEYS)
        self.assertEqual([line.split("\t")[1] for line in out.splitlines()],
                         ["hedge-stack", "hedge-stack", "hedge-stack", "assistant-residue", "assistant-residue", "hedge-stack"])

    def test_rows_json_has_the_same_keys(self):
        paragraphs, _ = self.hand_files()
        _, text_out, _ = run_tool("precision.py", "rows", "--paragraphs", paragraphs)
        code, json_out, _ = run_tool("precision.py", "rows", "--paragraphs", paragraphs, "--json")
        self.assertEqual(code, 0)
        self.assertEqual([row["key"] for row in json.loads(json_out)], [line.split("\t")[0] for line in text_out.splitlines()])
        self.assertEqual([row["kind"] for row in json.loads(json_out)], ["seeded"] * 5 + ["clean"])

    def test_the_report_computes_the_precision_of_each_family(self):
        code, out, err = self.report()
        self.assertEqual((code, err), (0, ""))
        self.assertRegex(out, r"hedge-stack\s+0\.50\s+\(2 right, 2 wrong\)")
        self.assertRegex(out, r"assistant-residue\s+1\.00\s+\(2 right, 0 wrong\)")

    def test_the_report_never_prints_a_pooled_figure(self):
        _, out, _ = self.report()
        # The families give 2 right of 4 and 2 right of 2. The figure that adds them is 4 of 6.
        for text in ("0.67", "0.66", "66.", "67%", "4 of 6", "4/6", "0.75", "75%"):
            self.assertNotIn(text, out)
        for word in ("pooled", "overall", "total", "all families", "micro", "macro", "average", "mean"):
            self.assertNotIn(word, out.lower())

    def test_the_report_gives_the_recall_of_the_seeded_labels_by_family(self):
        _, out, _ = self.report()
        self.assertRegex(out, r"hedge-stack\s+2 of 3 covered")
        self.assertRegex(out, r"assistant-residue\s+1 of 1 covered")
        section = out.split("Seeded labels that no right finding covers:")[1].split("Flagged findings on clean paragraphs:")[0]
        self.assertEqual(section.split(), ["h2", "hedge-stack"])

    def test_the_report_lists_the_flagged_findings_on_clean_paragraphs(self):
        _, out, _ = self.report()
        section = out.split("Flagged findings on clean paragraphs:")[1]
        self.assertIn("h4:1 hedge-stack", section)
        self.assertIn("(wrong)", section)
        self.assertNotIn("h1:1", section)

    def test_a_wrong_label_does_not_cover_a_seeded_label(self):
        labels = dict(HAND_LABELS, **{"h1:1": "wrong"})
        _, out, _ = self.report(labels)
        self.assertRegex(out, r"hedge-stack\s+1 of 3 covered")
        self.assertRegex(out, r"hedge-stack\s+0\.25\s+\(1 right, 3 wrong\)")

    def test_a_missing_label_gives_exit_code_2_and_no_output(self):
        labels = dict(HAND_LABELS)
        del labels["h3:2"]
        code, out, err = self.report(labels)
        self.assertEqual(code, 2)
        self.assertEqual(out, "")
        self.assertIn("h3:2", err)
        self.assertIn("no label", err)

    def test_a_label_without_a_finding_gives_exit_code_2(self):
        code, out, err = self.report(dict(HAND_LABELS, **{"h9:1": "right"}))
        self.assertEqual((code, out), (2, ""))
        self.assertIn("h9:1", err)
        self.assertIn("no flagged finding", err)

    def test_a_label_other_than_right_or_wrong_gives_exit_code_2(self):
        for value in ("maybe", "Right", "", None, True, 1, ["right"]):
            with self.subTest(value=value):
                code, out, err = self.report(dict(HAND_LABELS, **{"h1:1": value}))
                self.assertEqual((code, out), (2, ""))
                self.assertIn("h1:1", err)

    def test_every_problem_is_named_in_one_run(self):
        labels = dict(HAND_LABELS, **{"h9:1": "right", "h1:1": "maybe"})
        del labels["h2:1"]
        code, _, err = self.report(labels)
        self.assertEqual(code, 2)
        for text in ("h2:1", "h9:1", "h1:1"):
            self.assertIn(text, err)

    def test_a_bad_labels_file_gives_exit_code_2(self):
        folder = self.scratch()
        paragraphs = self.write(folder, "hand.json", json.dumps(HAND))
        for name, text in (("list.json", "[]"), ("broken.json", "{"), ("empty.json", "")):
            path = self.write(folder, name, text)
            with self.subTest(name=name):
                code, out, err = run_tool("precision.py", "report", path, "--paragraphs", paragraphs)
                self.assertEqual((code, out), (2, ""))
                self.assertTrue(err)
        code, out, err = run_tool("precision.py", "report", os.path.join(folder, "missing.json"), "--paragraphs", paragraphs)
        self.assertEqual((code, out), (2, ""))

    def test_a_bad_paragraph_file_gives_exit_code_2(self):
        folder = self.scratch()
        for name, text in (("a.json", "{}"), ("b.json", "[{\"id\": \"x\"}]"), ("c.json", "nope")):
            path = self.write(folder, name, text)
            with self.subTest(name=name):
                code, out, _ = run_tool("precision.py", "rows", "--paragraphs", path)
                self.assertEqual((code, out), (2, ""))
        path = self.write(folder, "dup.json", json.dumps([HAND[0], HAND[0]]))
        self.assertEqual(run_tool("precision.py", "rows", "--paragraphs", path)[0], 2)

    def test_the_report_on_the_real_fixtures_with_every_label_right(self):
        folder = self.scratch()
        _, out, _ = run_tool("precision.py", "rows", "--json")
        rows = json.loads(out)
        labels = self.write(folder, "labels.json", json.dumps(dict((row["key"], "right") for row in rows)))
        code, report, err = run_tool("precision.py", "report", labels)
        self.assertEqual((code, err), (0, ""))
        families = sorted(set(row["family"] for row in rows))
        for name in families:
            self.assertRegex(report, name + r"\s+1\.00\s+\(\d+ right, 0 wrong\)")
        clean = [row for row in rows if row["kind"] == "clean"]
        section = report.split("Flagged findings on clean paragraphs:")[1]
        self.assertEqual(len([line for line in section.splitlines() if line.strip()]), len(clean))
        for row in clean:
            self.assertIn(row["key"], section)


LATEX_BEFORE = (
    "\\section{Results}\n"
    "We delve into the assay (n = 24 plants). The signal rose by 20\\% at 6 h \\cite{brantwick2018}. "
    "The mutant grew slowly (Fig. 2).\n"
    "\\begin{equation}\n"
    "y = x + 1\n"
    "\\end{equation}\n"
    "The model fits the data.\n")


class DiffReportTests(ScratchCase):
    def diff(self, before, after, name="paper.tex", *extra):
        folder = self.scratch()
        old = self.write(folder, "a_" + name, before)
        new = self.write(folder, "b_" + name, after)
        return run_tool("diff_report.py", old, new, *extra)

    def test_a_clean_rewrite_exits_0_and_lists_the_changed_sentence(self):
        after = LATEX_BEFORE.replace("We delve into", "We examine")
        code, out, err = self.diff(LATEX_BEFORE, after)
        self.assertEqual((code, err), (0, ""))
        self.assertIn("changed sentences: 1 (1 reworded, 0 deleted, 0 added).", out)
        self.assertIn("before: We delve into the assay (n = 24 plants).", out)
        self.assertIn("after:  We examine the assay (n = 24 plants).", out)
        self.assertIn("masked spans: identical", out)
        self.assertIn("numbers: identical", out)

    def test_it_prints_the_words_and_the_flagged_findings_by_family(self):
        after = LATEX_BEFORE.replace("We delve into", "We examine")
        _, out, _ = self.diff(LATEX_BEFORE, after)
        before_words, after_words = word_count(mask(LATEX_BEFORE, "latex").text), word_count(mask(after, "latex").text)
        self.assertIn("words: %d before, %d after." % (before_words, after_words), out)
        self.assertRegex(out, r"vocabulary-excess\s+1 -> 0")
        self.assertNotIn("em-dash", out)

    def test_identical_files_exit_0_with_no_change(self):
        code, out, _ = self.diff(LATEX_BEFORE, LATEX_BEFORE)
        self.assertEqual(code, 0)
        self.assertIn("changed sentences: 0 (0 reworded, 0 deleted, 0 added).", out)

    def test_a_changed_number_exits_1_and_lists_both_numbers(self):
        after = LATEX_BEFORE.replace("n = 24 plants", "n = 25 plants")
        code, out, _ = self.diff(LATEX_BEFORE, after)
        self.assertEqual(code, 1)
        self.assertIn("numbers: DIFFERENT", out)
        self.assertIn('only in the original: "24"', out)
        self.assertIn('only in the revised file: "25"', out)
        self.assertIn("masked spans: identical", out)
        self.assertIn("after:  We delve into the assay (n = 25 plants).", out)

    def test_a_dropped_number_and_a_new_number_exit_1(self):
        for after in (LATEX_BEFORE.replace(" at 6 h", ""), LATEX_BEFORE.replace("slowly", "slowly in 3 plants")):
            with self.subTest(after=after[:60]):
                code, out, _ = self.diff(LATEX_BEFORE, after)
                self.assertEqual(code, 1)
                self.assertIn("numbers: DIFFERENT", out)

    def test_a_dropped_citation_exits_1_and_lists_the_span(self):
        after = LATEX_BEFORE.replace(" \\cite{brantwick2018}", "")
        code, out, _ = self.diff(LATEX_BEFORE, after)
        self.assertEqual(code, 1)
        self.assertIn("masked spans: DIFFERENT", out)
        self.assertIn('only in the original: "\\cite{brantwick2018}"', out)
        self.assertIn("numbers: identical", out)

    def test_a_moved_citation_key_and_a_changed_equation_exit_1(self):
        for after in (LATEX_BEFORE.replace("brantwick2018", "quenby2020"), LATEX_BEFORE.replace("y = x + 1", "y = x + 2")):
            with self.subTest(after=after[-60:]):
                code, out, _ = self.diff(LATEX_BEFORE, after)
                self.assertEqual(code, 1)
                self.assertIn("masked spans: DIFFERENT", out)

    def test_the_comparison_of_spans_ignores_the_position_of_a_citation(self):
        after = LATEX_BEFORE.replace("The signal rose by 20\\% at 6 h \\cite{brantwick2018}.", "The signal \\cite{brantwick2018} rose by 20\\% at 6 h.")
        code, out, _ = self.diff(LATEX_BEFORE, after)
        self.assertEqual(code, 0)
        self.assertIn("masked spans: identical", out)

    def test_a_deleted_sentence_and_an_added_sentence_are_listed(self):
        after = LATEX_BEFORE.replace(" The mutant grew slowly (Fig. 2).", "")
        code, out, _ = self.diff(LATEX_BEFORE, after)
        self.assertIn("(0 reworded, 1 deleted, 0 added)", out)
        self.assertIn("after:  (none: the sentence is deleted)", out)
        self.assertIn("before: The mutant grew slowly (Fig. 2).", out)
        added = LATEX_BEFORE.replace("The model fits the data.", "The model fits the data. The fit is close.")
        _, out, _ = self.diff(LATEX_BEFORE, added)
        self.assertIn("(0 reworded, 0 deleted, 1 added)", out)
        self.assertIn("before: (none: the sentence is new)", out)

    def test_a_split_sentence_gives_a_reworded_sentence_and_an_added_sentence(self):
        before = "The cells were sorted by flow cytometry, ensuring 94% pure populations. We then counted them.\n"
        after = "The cells were sorted by flow cytometry. The sorted populations were 94% pure. We then counted them.\n"
        code, out, _ = self.diff(before, after, "note.txt")
        self.assertEqual(code, 0)
        self.assertIn("changed sentences: 2 (1 reworded, 0 deleted, 1 added).", out)
        self.assertIn("after:  The cells were sorted by flow cytometry.\n", out)
        self.assertIn("before: (none: the sentence is new)\n  after:  The sorted populations were 94% pure.", out)

    def test_a_sentence_with_no_likeness_to_its_new_text_is_one_joined_change(self):
        before = "The assay was bad. We then counted them.\n"
        after = "Cells died within an hour of plating. We then counted them.\n"
        code, out, _ = self.diff(before, after, "note.txt")
        self.assertEqual(code, 0)
        self.assertIn("changed sentences: 1 (1 reworded, 0 deleted, 0 added).", out)
        self.assertIn("before: The assay was bad.\n  after:  Cells died within an hour of plating.", out)

    def test_an_added_sentence_and_a_deleted_sentence_do_not_pair_with_each_other(self):
        old = "\n\n".join("Plate %d dried and then it cracked on the shelf." % n for n in range(1, 5)) + "\n\nThe lid was lost.\n"
        new = "A tall flask arrived from the store.\n\n" + "\n\n".join(
            "Plate %d dried, then it cracked on the shelf." % n for n in range(1, 5)) + "\n"
        code, out, _ = self.diff(old, new, "note.txt")
        self.assertIn("changed sentences: 6 (4 reworded, 1 deleted, 1 added).", out)
        self.assertIn("before: The lid was lost.\n  after:  (none: the sentence is deleted)", out)

    def test_the_text_format_and_the_markdown_format(self):
        before = "We delve into the assay (n = 24 plants). The mutant grew slowly.\n"
        after = "We examine the assay (n = 24 plants). The mutant grew slowly.\n"
        for name in ("note.txt", "note.md"):
            with self.subTest(name=name):
                code, out, _ = self.diff(before, after, name)
                self.assertEqual(code, 0)
                self.assertIn("changed sentences: 1", out)
        code, _, _ = self.diff(before, after.replace("24", "25"), "note.md")
        self.assertEqual(code, 1)

    def test_the_format_option_sets_the_format_of_both_files(self):
        before = "We delve into it \\cite{a}. The mutant grew.\n"
        after = "We delve into it. The mutant grew.\n"
        code, out, _ = self.diff(before, after, "note.txt")
        self.assertEqual(code, 0, "plain text hides no citation command")
        code, out, _ = self.diff(before, after, "note.txt", "--format", "latex")
        self.assertEqual(code, 1)
        self.assertIn("masked spans: DIFFERENT", out)

    def test_a_missing_file_a_binary_file_and_a_file_that_is_not_utf8_exit_2(self):
        folder = self.scratch()
        good = self.write(folder, "good.txt", "A sentence.\n")
        for name, data in (("nul.txt", b"abc\x00def"), ("latin.txt", b"caf\xe9 au lait.\n")):
            path = os.path.join(folder, name)
            with io.open(path, "wb") as handle:
                handle.write(data)
            for order in ((good, path), (path, good)):
                with self.subTest(name=name, order=order[0] == good):
                    code, out, err = run_tool("diff_report.py", *order)
                    self.assertEqual((code, out), (2, ""))
                    self.assertTrue(err)
        code, out, err = run_tool("diff_report.py", good, os.path.join(folder, "missing.txt"))
        self.assertEqual((code, out), (2, ""))
        self.assertIn("missing.txt", err)

    def test_an_empty_file_exits_0(self):
        code, out, _ = self.diff("", "", "empty.txt")
        self.assertEqual(code, 0)
        self.assertIn("words: 0 before, 0 after.", out)


def pairs(count):
    """Return the text of an original and of a revised file with `count` reworded sentences."""
    old, new = [], []
    for n in range(1, count + 1):
        old.append("Sample %d was heated for %d min and then it cooled in the dark." % (n, n + 3))
        new.append("Sample %d was heated for %d min, then it cooled in the dark." % (n, n + 3))
    return "\n\n".join(old) + "\n", "\n\n".join(new) + "\n"


class AbSampleTests(ScratchCase):
    def sample(self, count=14, extra=(), out=None, original=None, revised=None):
        base = self.scratch()
        before, after = pairs(count)
        old = self.write(base, "before.txt", original if original is not None else before)
        new = self.write(base, "after.txt", revised if revised is not None else after)
        out = out or os.path.join(base, "out")
        return run_tool("ab_sample.py", old, new, "--out", out, *extra), out, (old, new)

    def key(self, out):
        return json.loads(self.read(os.path.join(out, "ab-key.json")))

    def options(self, out):
        """Return a list of (A text, B text) from the sample file."""
        text = self.read(os.path.join(out, "ab-sample.md"))
        found = re.findall(r"^## Item (\d+)\n\nA\. (.*)\n\nB\. (.*)$", text, re.M)
        return [(int(n), a, b) for n, a, b in found]

    def test_it_writes_the_sample_and_the_key(self):
        (code, stdout, stderr), out, _ = self.sample()
        self.assertEqual((code, stdout, stderr), (0, "", ""))
        self.assertEqual(sorted(os.listdir(out)), ["ab-key.json", "ab-sample.md"])
        self.assertEqual(len(self.options(out)), 10)
        self.assertEqual(len(self.key(out)["items"]), 10)

    def test_it_writes_two_files_inside_out_dir_and_nothing_outside(self):
        base, cwd = self.scratch(), self.scratch()
        before_text, after_text = pairs(12)
        old, new = self.write(base, "before.txt", before_text), self.write(base, "after.txt", after_text)
        out = os.path.join(base, "nested", "out")
        seen = {"base": tree(base), "cwd": tree(cwd), "tool": tree(VERIFY_DIR)}
        code, stdout, stderr = run_tool("ab_sample.py", old, new, "--out", out, cwd=cwd)
        self.assertEqual((code, stdout, stderr), (0, "", ""))
        self.assertEqual(tree(base), seen["base"] | {
            "nested", os.path.join("nested", "out"), os.path.join("nested", "out", "ab-sample.md"),
            os.path.join("nested", "out", "ab-key.json")})
        self.assertEqual(tree(cwd), seen["cwd"])
        self.assertEqual(tree(VERIFY_DIR), seen["tool"])

    def test_the_key_maps_every_item(self):
        (code, _, _), out, (old, new) = self.sample()
        key, options = self.key(out), self.options(out)
        self.assertEqual((key["seed"], key["n"]), (7, 10))
        self.assertEqual([item["item"] for item in key["items"]], list(range(1, 11)))
        self.assertEqual([n for n, _, _ in options], list(range(1, 11)))
        old_sentences = set(self.read(old).replace("\n\n", "\n").splitlines())
        new_sentences = set(self.read(new).replace("\n\n", "\n").splitlines())
        for item, (number, a, b) in zip(key["items"], options):
            with self.subTest(item=number):
                self.assertEqual(sorted([item["A"], item["B"]]), ["original", "revised"])
                texts = {"original": item["original"], "revised": item["revised"]}
                self.assertEqual((texts[item["A"]], texts[item["B"]]), (a, b))
                self.assertIn(item["original"], old_sentences)
                self.assertIn(item["revised"], new_sentences)
                self.assertNotEqual(item["original"], item["revised"])

    def test_the_sample_file_gives_no_hint_of_the_revised_side(self):
        (_, _, _), out, (old, new) = self.sample()
        text = self.read(os.path.join(out, "ab-sample.md")).lower()
        for word in ("revised", "original", "before", "after", "rewrite", os.path.basename(old), os.path.basename(new)):
            self.assertNotIn(word, text)
        # Each option is a sentence of the manuscript, with no mark, so only the order of the options is left.
        for _, a, b in self.options(out):
            self.assertNotEqual(a, b)
            self.assertTrue(a.startswith("Sample ") and b.startswith("Sample "))

    def test_both_sides_hold_the_revised_text_at_the_default_seed(self):
        (_, _, _), out, _ = self.sample()
        sides = set(item["A"] for item in self.key(out)["items"])
        self.assertEqual(sides, {"original", "revised"})

    def test_the_same_seed_gives_the_same_bytes(self):
        base = self.scratch()
        before, after = pairs(14)
        old, new = self.write(base, "before.txt", before), self.write(base, "after.txt", after)
        outs = [os.path.join(base, "one"), os.path.join(base, "two")]
        for out in outs:
            self.assertEqual(run_tool("ab_sample.py", old, new, "--seed", 5, "--out", out)[0], 0)
        for name in ("ab-sample.md", "ab-key.json"):
            self.assertEqual(self.read(os.path.join(outs[0], name)), self.read(os.path.join(outs[1], name)))

    def test_the_order_and_the_pick_depend_on_the_seed(self):
        base = self.scratch()
        before, after = pairs(14)
        old, new = self.write(base, "before.txt", before), self.write(base, "after.txt", after)
        orders, picks = set(), set()
        for seed in range(1, 7):
            out = os.path.join(base, "s%d" % seed)
            self.assertEqual(run_tool("ab_sample.py", old, new, "--seed", seed, "--out", out)[0], 0)
            items = self.key(out)["items"]
            orders.add(tuple(item["A"] for item in items))
            picks.add(tuple(item["original"] for item in items))
            self.assertEqual(set(item["A"] for item in items), {"original", "revised"}, "seed %d" % seed)
        self.assertGreaterEqual(len(orders), 4)
        self.assertGreaterEqual(len(picks), 4)

    def test_the_defaults_are_n_10_and_seed_7(self):
        base = self.scratch()
        before, after = pairs(14)
        old, new = self.write(base, "before.txt", before), self.write(base, "after.txt", after)
        plain, named = os.path.join(base, "plain"), os.path.join(base, "named")
        run_tool("ab_sample.py", old, new, "--out", plain)
        run_tool("ab_sample.py", old, new, "--n", 10, "--seed", 7, "--out", named)
        for name in ("ab-sample.md", "ab-key.json"):
            self.assertEqual(self.read(os.path.join(plain, name)), self.read(os.path.join(named, name)))

    def test_the_option_n_sets_the_number_of_items(self):
        (code, _, _), out, _ = self.sample(extra=("--n", 3))
        self.assertEqual(code, 0)
        self.assertEqual(len(self.options(out)), 3)
        self.assertEqual(len(self.key(out)["items"]), 3)
        self.assertEqual(self.key(out)["n"], 3)

    def test_the_picks_keep_the_order_of_the_manuscript(self):
        (_, _, _), out, _ = self.sample()
        numbers = [int(re.match(r"Sample (\d+)", item["original"]).group(1)) for item in self.key(out)["items"]]
        self.assertEqual(numbers, sorted(numbers))
        self.assertEqual(len(set(numbers)), 10)

    def test_it_refuses_when_fewer_than_n_sentences_changed(self):
        (code, stdout, stderr), out, _ = self.sample(count=9)
        self.assertEqual((code, stdout), (2, ""))
        self.assertIn("only 9 sentences changed", stderr)
        self.assertFalse(os.path.exists(out))

    def test_it_runs_when_exactly_n_sentences_changed(self):
        (code, _, _), out, _ = self.sample(count=10)
        self.assertEqual(code, 0)
        self.assertEqual(len(self.options(out)), 10)

    def test_a_deleted_sentence_and_an_added_sentence_do_not_count(self):
        before, after = pairs(9)
        before += "\nThe extra plate dried and was not used.\n"
        after = "A new plate arrived late and was not read.\n\n" + after
        (code, _, stderr), out, _ = self.sample(original=before, revised=after)
        self.assertEqual(code, 2)
        self.assertIn("only 9 sentences changed", stderr)

    def test_it_refuses_to_overwrite_an_earlier_sample(self):
        base = self.scratch()
        before, after = pairs(12)
        old, new = self.write(base, "before.txt", before), self.write(base, "after.txt", after)
        out = os.path.join(base, "out")
        self.assertEqual(run_tool("ab_sample.py", old, new, "--out", out)[0], 0)
        key = self.read(os.path.join(out, "ab-key.json"))
        code, stdout, stderr = run_tool("ab_sample.py", old, new, "--seed", 9, "--out", out)
        self.assertEqual((code, stdout), (2, ""))
        self.assertIn("exists", stderr)
        self.assertEqual(self.read(os.path.join(out, "ab-key.json")), key)

    def test_a_bad_n_a_missing_out_option_and_a_missing_file_exit_2(self):
        base = self.scratch()
        before, after = pairs(12)
        old, new = self.write(base, "before.txt", before), self.write(base, "after.txt", after)
        out = os.path.join(base, "out")
        self.assertEqual(run_tool("ab_sample.py", old, new, "--n", 0, "--out", out)[0], 2)
        self.assertEqual(run_tool("ab_sample.py", old, new)[0], 2)
        code, _, err = run_tool("ab_sample.py", old, os.path.join(base, "none.txt"), "--out", out)
        self.assertEqual(code, 2)
        self.assertIn("none.txt", err)
        self.assertFalse(os.path.exists(out))


if __name__ == "__main__":
    unittest.main()
