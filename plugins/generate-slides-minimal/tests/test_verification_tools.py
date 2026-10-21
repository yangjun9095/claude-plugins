"""Tests for the comparison tools in tests/verification: make_project.py, score_deck.py and build_results.py.

make_project.py must build the same project on every run, with exactly the documented files, and write
nothing outside its folder. Each number that notes.md ties to a figure must follow from results.csv, and the
data must obey each rule that notes.md states. score_deck.py must give the findings, the ghost deck and the word counts of
design_lint, with exit codes by the lint result. build_results.py must read the real output of score_deck.py
with a strict parser, fail with a message on a missing file or a claim that disagrees, and keep failing under
python3 -O. The fixtures of build_results come from real score_deck.py output on decks that the plugin's own
test helpers build.
"""
import ast
import contextlib
import csv
import hashlib
import io
import os
import re
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import tokenize
import unittest
from pathlib import Path
from unittest import mock

from PIL import Image
from pptx import Presentation

TESTS_DIR = Path(__file__).resolve().parent
PLUGIN = TESTS_DIR.parent
VERIFICATION = TESTS_DIR / "verification"
SAMPLE_DECK = PLUGIN / "examples" / "sample-deck.pptx"
for folder in (PLUGIN / "scripts", TESTS_DIR, VERIFICATION):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import build_results as br  # noqa: E402
import design_lint as dl  # noqa: E402
import make_project as mp  # noqa: E402
import score_deck as sd  # noqa: E402
from lint_helpers import (  # noqa: E402
    BODY,
    LintCase,
    add_box,
    add_notes,
    add_slide,
    add_source,
    clean_slide,
    new_deck,
    words,
)
from test_docs import BANNED_WORDS, EM_DASH, SENTENCE_LIMIT, private_matches, prose_problems  # noqa: E402

SCRIPTS = ("make_project.py", "score_deck.py", "build_results.py")
FIGURES = ["figures/fig{}.png".format(number) for number in range(1, 9)]
PROJECT_FILES = sorted(FIGURES + ["notes.md", "results.csv"])
NUMBER = re.compile(r"(?<![\w.])[0-9]+(?:\.[0-9]+)?(?!\w)")
C_LOCALE = {"LC_ALL": "C", "LANG": "C", "PYTHONCOERCECLOCALE": "0"}


def run_tool(script, *args, flags=(), env=None, cwd=None, raw=False):
    """Run one of the tools through the interpreter, as a user does. Return the CompletedProcess.

    With `raw` the output stays as bytes, so that a test reads the encoding that the tool chose.
    """
    environment = dict(os.environ)
    environment.update(env or {})
    environment.pop("PYTHONIOENCODING", None)
    command = [sys.executable, "-B"] + list(flags) + [str(VERIFICATION / script)] + [str(a) for a in args]
    return subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=not raw,
                          env=environment, cwd=None if cwd is None else str(cwd))


def snapshot(root):
    """Return {relative path: hash of the content, or None for a folder} for everything under root."""
    found = {}
    for path in sorted(Path(root).rglob("*")):
        relative = str(path.relative_to(root))
        found[relative] = None if path.is_dir() else hashlib.sha256(path.read_bytes()).hexdigest()
    return found


def png_chunk_types(data):
    """Return the chunk types of a PNG file in order. The caller checks the signature."""
    types, position = [], 8
    while position < len(data):
        length = struct.unpack(">I", data[position:position + 4])[0]
        types.append(data[position + 4:position + 8].decode("ascii"))
        position += 12 + length
    return types


def prose_of(path):
    """Return the prose of a file: the whole text of a document, or the comments and strings of a script."""
    text = path.read_text(encoding="utf-8")
    if path.suffix != ".py":
        return text
    tokens = tokenize.generate_tokens(io.StringIO(text).readline)
    return "\n".join(token.string for token in tokens if token.type in (tokenize.COMMENT, tokenize.STRING))


def sentences_of_docs_and_comments(path):
    """Return the sentences of the docstrings and the comments of a script.

    A block of a docstring that starts with four spaces is a sample of output or code, and it drops out. A
    label such as "Run:" and a bullet each start a new sentence. A comment on its own line joins the comment
    lines around it. A comment after code stands alone.
    """
    text = path.read_text(encoding="utf-8")
    texts = []
    for node in ast.walk(ast.parse(text)):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)) and ast.get_docstring(node, clean=True):
            for chunk in re.split(r"\n\s*\n", ast.get_docstring(node, clean=True)):
                if not chunk.startswith("    "):
                    texts += re.split(r"\n(?=\w+:\s{2})|\n(?=\s*- )", chunk)
    block, last = [], None
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type != tokenize.COMMENT:
            continue
        body = token.string.lstrip("#").strip()
        if not body or set(body) <= {"-"} or body.startswith("noqa"):
            continue
        if not token.line.strip().startswith("#"):  # a comment after code
            texts.append(body)
            continue
        if block and token.start[0] != last + 1:
            texts.append(" ".join(block))
            block = []
        block.append(body)
        last = token.start[0]
    if block:
        texts.append(" ".join(block))
    return [unit for chunk in texts for unit in re.split(r"(?<=[.!?])\s+", " ".join(chunk.split())) if unit.strip()]


def unquoted_numbers(notes, csv_text):
    """Return the numbers of the Results section of the notes that results.csv does not hold."""
    section = notes.split("## Results", 1)[1].split("\n## ", 1)[0]
    known = set(float(n) for n in NUMBER.findall(csv_text.split("\n", 1)[1]))  # the header holds no number
    return sorted(set(n for n in NUMBER.findall(section) if float(n) not in known))


# A label holds a number that names a thing and states no result: fig3, Round 1, Design 4, 25 uM, 60 minutes.
LABEL = re.compile(r"\bfig[1-8]\b|\b(?:Round|Design) [0-9]+\b|\b[0-9]+ (?:uM|minutes)\b", re.I)
HERON = "Heron set"


def section_of(notes, name):
    """Return the text of one level 2 section of the notes."""
    return notes.split("\n## " + name + "\n", 1)[1].split("\n## ", 1)[0]


def bullets_of(text):
    return [line for line in text.splitlines() if line.startswith("- ")]


def csv_table(csv_text):
    """Return {figure: {series: [(x, y)]}} from the text of results.csv. x is a float, or text for a label."""
    table = {}
    for row in csv.DictReader(io.StringIO(csv_text)):
        try:
            x = float(row["x"])
        except ValueError:
            x = row["x"]
        table.setdefault(row["figure"], {}).setdefault(row["series"], []).append((x, float(row["y"])))
    return table


def number_spans(line):
    """Return (start, end) for each number of a claim. A number inside a label does not count."""
    labels = [m.span() for m in LABEL.finditer(line)]
    return [m.span() for m in NUMBER.finditer(line) if not any(a <= m.start() and m.end() <= b for a, b in labels)]


def claim_numbers(line):
    return [float(line[a:b]) for a, b in number_spans(line)]


def close(first, second):
    return len(first) == len(second) and all(abs(a - b) < 1e-9 for a, b in zip(first, second))


def fits(points, size):
    """Return True when each percentage is a whole number of designs in a group of `size` designs."""
    return all(abs(y * size / 100.0 - round(y * size / 100.0)) < 1e-9 for _, y in points)


def heron(table, fig):
    return table[fig][HERON]


def by_x(points, pick):
    return pick(points, key=lambda point: point[0])


def by_y(points, pick):
    return pick(points, key=lambda point: point[1])


def fmt_number(value):
    return str(int(value)) if value == int(value) else "{:.1f}".format(value)


def only_one(values, pick):
    values = list(values)
    return values.count(pick(values)) == 1


def expected_results(table):
    """Recompute the numbers of each Results sentence from results.csv, by the rule that the sentence names."""
    def at(fig, series, x):
        return dict(table[fig][series])[x]

    top, long_, short = by_x(heron(table, "fig3"), max), by_x(heron(table, "fig4"), max), by_x(heron(table, "fig4"), min)
    stable = by_y(heron(table, "fig6"), max)
    return {
        "fig1": [at("fig1", HERON, "Round 1"), at("fig1", HERON, "Round 4")],
        "fig2": [at("fig2", "Designed", "Target C"), at("fig2", "Control", "Target C")],
        "fig3": [top[0], top[1]],
        "fig4": [long_[0], long_[1], short[0], short[1]],
        "fig5": [by_y(heron(table, "fig5"), max)[1], by_y(heron(table, "fig5"), min)[1]],
        "fig6": [stable[1], stable[0]],
        "fig7": [at("fig7", "Cost", "Batched"), at("fig7", "Cost", "Manual")],
        "fig8": [at("fig8", "25 uM", 60.0), at("fig8", "1 uM", 60.0)],
    }


def expected_labels(table):
    """Return the Design labels of the fig5 sentence: the best design and then the lowest design."""
    return [by_y(heron(table, "fig5"), max)[0], by_y(heron(table, "fig5"), min)[0]]


def figure_wanted(fig, table, stated, total, size):
    """Return (numbers that the Figures sentence of `fig` must state, problems). Each number comes from results.csv."""
    problems = []
    count = len(next(iter(table[fig].values())))
    if fig == "fig1":
        if not fits(heron(table, fig), size):
            problems.append("fig1: a percentage is not a whole number of designs")
        return [count, size], problems
    if fig == "fig2":
        sizes = stated[1:3] if len(stated) == 3 else [0, 0]  # a group size follows from the percentages of its series
        if not (fits(table[fig]["Designed"], sizes[0]) and fits(table[fig]["Control"], sizes[1])):
            problems.append("fig2: a percentage is not a whole number of designs")
        return [count] + sizes, problems
    if fig == "fig8":
        return [len(table[fig]), count], problems
    return [total if fig in ("fig3", "fig4", "fig6") else count], problems


def study_problems(notes, csv_text):
    """Recompute from results.csv every claim of notes.md that names a number, and return a message for each break.

    A claim is a bullet of Results or Figures. Methods states the sizes and the two rules, and the data must obey them.
    """
    table = csv_table(csv_text)
    problems = []
    expected = expected_results(table)
    named = set()
    results = bullets_of(section_of(notes, "Results"))
    for line in results:
        found = re.search(r"\((fig[1-8])\)\.$", line)
        if found is None:
            problems.append("a Results sentence names no figure: " + line)
            continue
        named.add(found.group(1))
        if not close(claim_numbers(line), expected[found.group(1)]):
            problems.append("{}: the sentence says {} and results.csv gives {}".format(
                found.group(1), claim_numbers(line), expected[found.group(1)]))
    if sorted(named) != sorted(expected):
        problems.append("the Results sentences name {} and not all eight figures".format(sorted(named)))
    for line in results:
        if "(fig5)" in line and re.findall(r"Design [0-9]+", line) != expected_labels(table):
            problems.append("fig5: the sentence names the wrong design")

    methods = section_of(notes, "Methods")
    size_claim = re.search(r"holds ([0-9]+) designs.* in ([0-9]+) rounds of ([0-9]+) designs each", methods)
    if size_claim is None:
        return problems + ["Methods does not state the size of the Heron set and of a round"]
    total, rounds, size = (int(n) for n in size_claim.groups())
    if total != rounds * size:
        problems.append("{} rounds of {} designs are not {} designs".format(rounds, size, total))
    figures = dict(re.match(r"- Fig([1-8]) (.*)", line).groups() for line in bullets_of(section_of(notes, "Figures")))
    if sorted(figures) != [str(n) for n in range(1, 9)]:
        problems.append("the Figures section does not hold one sentence for each of the eight figures")
    for number, text in sorted(figures.items()):
        wanted, found = figure_wanted("fig" + number, table, claim_numbers(text), total, size)
        problems += found
        if not close(claim_numbers(text), wanted):
            problems.append("fig{}: the sentence says {} and results.csv gives {}".format(
                number, claim_numbers(text), wanted))

    osprey = [x for x, _ in heron(table, "fig3")]
    filter_level = float(re.search(r"Osprey score below ([0-9]+)\.", methods).group(1))
    hit_level = float(re.search(r"signal of at least ([0-9]+) au", methods).group(1))
    if min(osprey + [x for x, _ in heron(table, "fig6")]) < filter_level:
        problems.append("a plotted design has an Osprey score below the filter level")
    if min(osprey) < 0 or max(osprey) > 10:
        problems.append("an Osprey score lies outside 0 to 10")
    hits = sum(1 for _, y in heron(table, "fig3") if y >= hit_level)
    hits_by_round = sum(y for _, y in heron(table, "fig1")) * size / 100.0
    if abs(hits - hits_by_round) > 1e-9:
        problems.append("fig3 holds {} hits and the rounds of fig1 hold {}".format(hits, hits_by_round))
    if sorted(y for _, y in heron(table, "fig3")) != sorted(y for _, y in heron(table, "fig4")):
        problems.append("fig3 and fig4 do not plot the same signals")
    if sorted(osprey) != sorted(x for x, _ in heron(table, "fig6")):
        problems.append("fig3 and fig6 do not plot the same Osprey scores")
    for name, ok in (("the highest Osprey score", only_one(osprey, max)),
                     ("the longest peptide", only_one((x for x, _ in heron(table, "fig4")), max)),
                     ("the shortest peptide", only_one((x for x, _ in heron(table, "fig4")), min)),
                     ("the highest signal", only_one((y for _, y in heron(table, "fig3")), max)),
                     ("the best yield", only_one((y for _, y in heron(table, "fig5")), max)),
                     ("the lowest yield", only_one((y for _, y in heron(table, "fig5")), min)),
                     ("the highest melting temperature", only_one((y for _, y in heron(table, "fig6")), max))):
        if not ok:
            problems.append(name + " belongs to more than one design")
    quoted = [n for line in results for n in claim_numbers(line)]
    if len(set(quoted)) != len(quoted):
        problems.append("two results share one number: " + ", ".join(str(n) for n in sorted(quoted)))
    if "Each number in the Results section comes from results.csv." not in section_of(notes, "Caveats"):
        problems.append("the caveat about the source of the numbers is missing")
    return problems


def mutations(notes):
    """Yield (old number, notes) with one number of one claim raised by 1.

    The claims are the bullets of Results and Figures and the bullet of Methods that states the sizes.
    """
    for name in ("Methods", "Figures", "Results"):
        body = section_of(notes, name)
        start = notes.index(body)
        for line in bullets_of(body):
            if name == "Methods" and not line.startswith("- The Heron set holds"):
                continue
            line_start = start + body.index(line)
            for a, b in number_spans(line):
                changed = line[:a] + "{:g}".format(float(line[a:b]) + 1) + line[b:]
                yield line[a:b], notes[:line_start] + changed + notes[line_start + len(line):]


# ---------------------------------------------------------------------------
# make_project.py
# ---------------------------------------------------------------------------

class MakeProject(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = Path(tempfile.mkdtemp())
        cls.runs = []
        for name, env in (("a", None), ("b", None), ("c", {"LC_ALL": "C", "TZ": "UTC+9", "PYTHONHASHSEED": "7"})):
            cls.runs.append(cls.root / name / "project")
            (cls.root / name).mkdir()
            done = run_tool("make_project.py", cls.runs[-1], env=env, cwd=cls.root)
            if done.returncode != 0:
                raise RuntimeError(done.stderr)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(str(cls.root), ignore_errors=True)

    def setUp(self):
        self.scratch = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, str(self.scratch), True)
        self.parent = self.scratch / "parent"
        self.parent.mkdir()
        self.cwd = self.scratch / "cwd"
        self.cwd.mkdir()

    def make(self, dest):
        return run_tool("make_project.py", dest, cwd=self.cwd)

    def files(self, project):
        return sorted(str(p.relative_to(project)) for p in Path(project).rglob("*") if p.is_file())

    def test_runs_in_other_folders_with_another_locale_and_hash_seed_give_the_same_hashes(self):
        first, second, third = (snapshot(run) for run in self.runs)
        self.assertEqual(len(first), 11)  # ten files and the folder figures
        self.assertEqual(first, second)
        self.assertEqual(first, third)

    def test_it_builds_exactly_the_documented_files(self):
        self.assertEqual(self.files(self.runs[0]), PROJECT_FILES)
        folders = sorted(str(p.relative_to(self.runs[0])) for p in self.runs[0].rglob("*") if p.is_dir())
        self.assertEqual(folders, ["figures"])

    def test_each_figure_is_a_png_that_pillow_opens_and_no_two_are_equal(self):
        hashes = set()
        for relative in FIGURES:
            path = self.runs[0] / relative
            with Image.open(str(path)) as image:
                self.assertEqual(image.format, "PNG", relative)
                image.verify()
            with Image.open(str(path)) as image:
                image.load()
                self.assertGreaterEqual(image.size[0], 1600, relative)  # 144 ppi over 11 inches
                self.assertGreater(len(image.convert("RGB").getcolors(maxcolors=100000)), 3, relative)
            hashes.add(hashlib.sha256(path.read_bytes()).hexdigest())
        self.assertEqual(len(hashes), 8)

    def test_a_png_holds_no_time_chunk_and_no_text_chunk(self):
        allowed = {"IHDR", "PLTE", "IDAT", "IEND", "pHYs", "sRGB", "gAMA"}
        for relative in FIGURES:
            data = (self.runs[0] / relative).read_bytes()
            self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n", relative)
            self.assertEqual(set(png_chunk_types(data)) - allowed, set(), relative)

    def test_the_csv_holds_all_eight_figures_in_the_three_kinds(self):
        with open(str(self.runs[0] / "results.csv"), newline="") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(list(rows[0]), list(mp.CSV_COLUMNS))
        kinds = {}
        for row in rows:
            kinds.setdefault(row["figure"], set()).add(row["kind"])
        self.assertEqual(sorted(kinds), ["fig{}".format(n) for n in range(1, 9)])
        self.assertTrue(all(len(k) == 1 for k in kinds.values()))
        counts = sorted(next(iter(k)) for k in kinds.values())
        self.assertEqual(counts, ["bar"] * 4 + ["line"] + ["scatter"] * 3)
        self.assertTrue(all(float(row["y"]) >= 0 for row in rows))

    def test_the_notes_quote_only_numbers_that_the_csv_holds(self):
        notes = (self.runs[0] / "notes.md").read_text()
        csv_text = (self.runs[0] / "results.csv").read_text()
        self.assertEqual(unquoted_numbers(notes, csv_text), [])
        self.assertEqual(len(NUMBER.findall(notes.split("## Results", 1)[1].split("\n## ", 1)[0])) > 10, True)

    def test_the_checker_of_the_notes_finds_a_number_that_the_csv_lacks(self):
        notes = (self.runs[0] / "notes.md").read_text()
        csv_text = (self.runs[0] / "results.csv").read_text()
        broken = notes.replace("(fig1).", "(fig1). It rose by 12345 percent.")
        self.assertEqual(unquoted_numbers(broken, csv_text), ["12345"])

    def notes_and_csv(self):
        return (self.runs[0] / "notes.md").read_text(), (self.runs[0] / "results.csv").read_text()

    def test_every_claim_of_the_notes_follows_from_the_csv(self):
        notes, csv_text = self.notes_and_csv()
        self.assertEqual(study_problems(notes, csv_text), [])
        self.assertGreater(len(list(mutations(notes))), 30)  # the check below has many numbers to change

    def test_a_changed_number_in_a_claim_makes_the_check_fail(self):
        notes, csv_text = self.notes_and_csv()
        for old, mutant in mutations(notes):
            with self.subTest(number=old):
                self.assertNotEqual(mutant, notes)
                self.assertNotEqual(study_problems(mutant, csv_text), [])

    def test_the_check_finds_each_rule_that_a_changed_csv_breaks(self):
        notes, csv_text = self.notes_and_csv()
        rows = [line.split(",") for line in csv_text.splitlines()]

        def edit(figure, which, **columns):
            """Return the csv with one row of a figure changed. `which` picks the row by the largest x or smallest y."""
            chosen = [row for row in rows if row[0] == figure]
            row = chosen[which]
            changed = [list(r) for r in rows]
            changed[rows.index(row)][3:5] = [columns.get("x", row[3]), columns.get("y", row[4])]
            return "\n".join(",".join(r) for r in changed) + "\n"

        fig3 = [row for row in rows if row[0] == "fig3"]
        quoted_x = max(float(row[3]) for row in fig3)
        free = next(i for i, row in enumerate(fig3) if float(row[4]) >= 50.0)  # the first hit
        cases = (
            ("an Osprey score below the filter level", edit("fig3", 0, x="3.9")),
            ("fig3 holds", edit("fig3", free, y="20")),
            ("belongs to more than one design", edit("fig3", len(fig3) - 2, x=fmt_number(quoted_x))),
        )
        for phrase, changed in cases:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, " | ".join(study_problems(notes, changed)))

    def test_the_check_finds_two_results_that_share_one_number(self):
        notes, csv_text = self.notes_and_csv()
        rows = csv_text.splitlines()
        index = rows.index("fig2,bar,Control,Target C,10")
        rows[index] = "fig2,bar,Control,Target C,20"  # Round 1 holds 20 as well
        problems = study_problems(notes.replace("control reached 10 percent", "control reached 20 percent"),
                                  "\n".join(rows) + "\n")
        self.assertEqual(len(problems), 1)
        self.assertIn("two results share one number", problems[0])

    def test_the_caveat_about_the_source_of_the_numbers_is_in_the_notes(self):
        notes, _ = self.notes_and_csv()
        self.assertIn("Each number in the Results section comes from results.csv.", section_of(notes, "Caveats"))

    def test_the_generated_text_follows_the_writing_rules_and_holds_nothing_private(self):
        for name in ("notes.md", "results.csv"):
            text = (self.runs[0] / name).read_text()
            self.assertEqual(private_matches(text), [], name)
            self.assertNotIn(EM_DASH, text, name)
        self.assertEqual(prose_problems((self.runs[0] / "notes.md").read_text()), [])

    def test_the_notes_say_that_the_study_is_made_up(self):
        text = (self.runs[0] / "notes.md").read_text()
        self.assertIn("made-up", text.splitlines()[0])
        self.assertIn("invented", text)

    def test_it_writes_nothing_outside_dest(self):
        before = snapshot(self.scratch)
        done = self.make(self.parent / "project")
        self.assertEqual((done.returncode, done.stderr), (0, ""))
        after = snapshot(self.scratch)
        inside = [name for name in after if name == "parent/project" or name.startswith("parent/project/")]
        self.assertEqual(len(inside), 12)  # the folder, the folder figures and ten files
        self.assertEqual({k: v for k, v in after.items() if k not in inside}, before)

    def test_it_fills_an_existing_empty_folder(self):
        dest = self.parent / "project"
        dest.mkdir()
        done = self.make(dest)
        self.assertEqual((done.returncode, done.stderr), (0, ""))
        self.assertEqual(self.files(dest), PROJECT_FILES)

    def test_a_read_only_parent_with_an_empty_dest_still_works(self):
        dest = self.parent / "project"
        dest.mkdir()
        self.parent.chmod(stat.S_IRUSR | stat.S_IXUSR)
        self.addCleanup(self.parent.chmod, stat.S_IRWXU)
        if os.access(str(self.parent), os.W_OK):
            self.skipTest("this account can write to a read-only folder")
        done = self.make(dest)
        self.assertEqual((done.returncode, done.stderr), (0, ""))
        self.assertEqual(self.files(dest), PROJECT_FILES)

    def test_a_read_only_parent_refuses_to_create_dest_and_leaves_it_untouched(self):
        self.parent.chmod(stat.S_IRUSR | stat.S_IXUSR)
        self.addCleanup(self.parent.chmod, stat.S_IRWXU)
        if os.access(str(self.parent), os.W_OK):
            self.skipTest("this account can write to a read-only folder")
        done = self.make(self.parent / "project")
        self.assertEqual((done.returncode, done.stdout), (2, ""))
        self.assertIn("cannot write", done.stderr)
        self.assertIn("Permission denied", done.stderr)  # the message names the failed mkdir
        self.assertEqual(len(done.stderr.splitlines()), 1)
        self.assertEqual(list(self.parent.iterdir()), [])

    def test_a_failed_mkdir_raises_the_error_of_the_mkdir_and_removes_nothing(self):
        self.parent.chmod(stat.S_IRUSR | stat.S_IXUSR)
        self.addCleanup(self.parent.chmod, stat.S_IRWXU)
        if os.access(str(self.parent), os.W_OK):
            self.skipTest("this account can write to a read-only folder")
        with mock.patch.object(Path, "rmdir", side_effect=AssertionError("rmdir of a folder that was never made")):
            with self.assertRaises(PermissionError):
                mp.write_files(self.parent / "project", [("one.bin", b"1")])

    def test_it_refuses_a_dest_that_is_not_empty_and_changes_nothing(self):
        dest = self.parent / "project"
        dest.mkdir()
        (dest / "mine.txt").write_text("keep me")
        before = snapshot(self.scratch)
        done = self.make(dest)
        self.assertEqual((done.returncode, done.stdout), (2, ""))
        self.assertIn("not empty", done.stderr)
        self.assertEqual(snapshot(self.scratch), before)

    def test_it_refuses_a_dest_that_is_a_file(self):
        dest = self.parent / "project"
        dest.write_text("a file")
        done = self.make(dest)
        self.assertEqual(done.returncode, 2)
        self.assertIn("not a folder", done.stderr)
        self.assertEqual(dest.read_text(), "a file")

    def test_it_refuses_a_dest_whose_parent_is_missing_and_does_not_create_the_parent(self):
        done = self.make(self.parent / "missing" / "project")
        self.assertEqual(done.returncode, 2)
        self.assertIn("does not exist", done.stderr)
        self.assertEqual(list(self.parent.iterdir()), [])

    def test_a_missing_argument_is_a_usage_error(self):
        done = run_tool("make_project.py")
        self.assertEqual(done.returncode, 2)

    def test_the_script_uses_no_clock_no_system_font_and_no_unseeded_random_number(self):
        tree = ast.parse((VERIFICATION / "make_project.py").read_text(encoding="utf-8"))
        imported = set(alias.name.split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.Import)
                       for alias in n.names)
        imported |= set((n.module or "").split(".")[0] for n in ast.walk(tree) if isinstance(n, ast.ImportFrom))
        self.assertEqual(imported & {"time", "datetime", "uuid", "tempfile", "platform", "getpass", "socket"}, set())
        names = set(n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute))
        names |= set(n.id for n in ast.walk(tree) if isinstance(n, ast.Name))
        self.assertEqual(names & {"truetype", "PngInfo", "pnginfo", "getenv", "environ"}, set())
        uses = [n for n in ast.walk(tree) if isinstance(n, ast.Attribute)
                and isinstance(n.value, ast.Name) and n.value.id == "random"]
        self.assertEqual([n.attr for n in uses], ["Random"])  # no call of the global generator
        seeded = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                  and n.func.attr == "Random"]
        self.assertEqual([len(n.args) for n in seeded], [1])

    def test_a_write_error_removes_what_the_call_wrote(self):
        dest = self.parent / "project"
        files = [("one.bin", b"1"), ("one.bin/two.bin", b"2")]  # the second path lies below a file
        with self.assertRaises(OSError):
            mp.write_files(dest, files)
        self.assertFalse(dest.exists())

    def test_a_write_error_keeps_a_folder_that_existed_and_leaves_it_empty(self):
        dest = self.parent / "project"
        dest.mkdir()
        with self.assertRaises(OSError):
            mp.write_files(dest, [("sub/one.bin", b"1"), ("sub/one.bin/two.bin", b"2")])
        self.assertEqual(list(dest.iterdir()), [])


# ---------------------------------------------------------------------------
# Decks for score_deck.py and the fixtures of build_results.py
# ---------------------------------------------------------------------------

def defective_deck(count, error=False):
    """Return a deck of `count` slides with a 2-word title, 30 words and no notes.

    `error` adds a last slide with no title, which is an error.
    """
    prs = new_deck()
    for index in range(count):
        add_box(add_slide(prs, "Results {}".format(index + 1)), words(30))
    if error:
        add_box(add_slide(prs, None), BODY)
    return prs


def tidy_deck(count):
    """Return a deck of `count` slides that the linter leaves alone, with notes."""
    prs = new_deck()
    for index in range(count):
        slide = clean_slide(prs, title="Binder design succeeds for {} of 15 targets".format(index + 1))
        add_notes(slide, "Speak about the assay and the controls in your own words, slide {}.".format(index + 1))
    return prs


def mixed_deck():
    """Return a deck of two slides. Slide 1 has a good title and the findings words-per-slide and notes only.

    Slide 2 has a title of two words, which is a title-sentence finding.
    """
    prs = new_deck()
    slide = add_slide(prs, "Binder design succeeds for 7 of 15 targets")
    for index, top in enumerate((1.6, 3.0, 4.4)):  # three short paragraphs of 27 words in all
        add_box(slide, words(9), name="Body {}".format(index + 1), top=top)
    add_box(add_slide(prs, "Results 2"), words(30))
    return prs


def block(text, start, stop):
    """Return the lines of a score text after the line `start` and before the line `stop`."""
    lines = text.splitlines()
    return lines[lines.index(start) + 1:lines.index(stop)]


def linter_cli(path, *args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = dl.main([str(path)] + [str(a) for a in args])
    return code, out.getvalue(), err.getvalue()


class ScoreDeck(LintCase):
    def score(self, prs, *args, **kwargs):
        path = prs if isinstance(prs, Path) else self.save(prs)
        args = args or ("--minutes", "12")
        return run_tool("score_deck.py", path, *args, **kwargs)

    def test_scoring_does_not_change_the_deck_file(self):
        path = self.save(defective_deck(2))
        before = path.read_bytes()
        self.score(path)
        self.assertEqual(path.read_bytes(), before)

    def test_a_deck_with_no_error_exits_0_and_the_output_parses(self):
        done = self.score(tidy_deck(2))
        self.assertEqual((done.returncode, done.stderr), (0, ""))
        score = br.parse_score(done.stdout, "score.txt")
        self.assertEqual((score.errors, score.profile, score.minutes, score.theme, score.notes),
                         (0, "peers", 12.0, "light", True))

    def test_the_parts_come_in_the_documented_order(self):
        lines = self.score(defective_deck(2)).stdout.splitlines()
        marks = [lines.index(m) for m in ("findings:", "ghost deck:", "words per slide:")]
        self.assertEqual(marks, sorted(marks))
        self.assertTrue(lines[0].startswith("settings: "))
        self.assertRegex(lines[-1], r"^errors: \d+ warnings: \d+$")
        self.assertEqual(lines[0], "settings: profile=peers minutes=12 theme=light notes=on")

    def test_a_deck_with_an_error_exits_1(self):
        done = self.score(defective_deck(1, error=True))
        self.assertEqual((done.returncode, done.stderr), (1, ""))
        score = br.parse_score(done.stdout, "score.txt")
        self.assertEqual(score.errors, 1)
        self.assertEqual([(r.slide, r.rule, r.severity) for r in score.findings if r.severity == "error"],
                         [(2, "title-empty", "error")])
        self.assertEqual(score.ghost[1], (2, "(no title)"))

    def test_a_missing_file_exits_2_with_one_line_on_stderr_and_no_output(self):
        done = run_tool("score_deck.py", self.tmp / "missing.pptx", "--minutes", "12")
        self.assertEqual((done.returncode, done.stdout), (2, ""))
        self.assertEqual(len(done.stderr.splitlines()), 1)
        self.assertIn("missing.pptx", done.stderr)

    def test_a_file_that_is_not_a_deck_exits_2(self):
        path = self.tmp / "text.pptx"
        path.write_text("this is not a deck")
        done = run_tool("score_deck.py", path, "--minutes", "12")
        self.assertEqual((done.returncode, done.stdout), (2, ""))
        self.assertIn("cannot read the deck", done.stderr)

    def test_a_bad_option_exits_2(self):
        path = self.save(tidy_deck(1))
        for args in (["--minutes", "0"], ["--minutes", "abc"], ["--minutes", "nan"], [],
                     ["--minutes", "5", "--profile", "nobody"], ["--minutes", "5", "--theme", "pink"]):
            with self.subTest(args=args):
                done = run_tool("score_deck.py", path, *args)
                self.assertEqual((done.returncode, done.stdout), (2, ""))
                self.assertNotEqual(done.stderr, "")

    def test_the_findings_are_the_rows_of_the_linter_and_the_exit_code_agrees(self):
        for prs in (defective_deck(3, error=True), tidy_deck(2), defective_deck(1)):
            path = self.save(prs)
            done = self.score(path, "--minutes", "2", "--profile", "peers")
            code, out, _ = linter_cli(path, "--profile", "peers", "--minutes", "2")
            lines = out.splitlines()
            with self.subTest(rows=len(lines)):
                self.assertEqual(done.returncode, code)
                self.assertEqual(block(done.stdout, "findings:", "ghost deck:"), lines[:-2])
                self.assertEqual(done.stdout.splitlines()[-1], "{} {}".format(*lines[-2:]))

    def test_the_rows_come_from_design_lint_format_finding(self):
        self.assertFalse(hasattr(sd, "format_finding"), "score_deck uses the formatter of design_lint")
        path = self.save(defective_deck(1))
        with mock.patch.object(dl, "format_finding", side_effect=lambda finding: "ROW " + finding.rule):
            text, _ = sd.score_text(path, 12)
        rows = block(text, "findings:", "ghost deck:")
        self.assertTrue(rows)
        self.assertTrue(all(row.startswith("ROW ") for row in rows), rows)

    def test_the_word_count_is_the_count_that_the_words_rule_reports(self):
        prs = new_deck()
        for count in (26, 30, 41):
            slide = add_slide(prs, "A made up title for this slide of the test")
            add_box(slide, words(count))
            add_source(slide, "Source: made up data for this slide")
        path = self.save(prs)
        done = self.score(path, "--minutes", "12", "--no-notes")
        shown = [int(m) for m in re.findall(r"^slide \d+: (\d+) words$", done.stdout, re.M)]
        self.assertEqual(shown, [26, 30, 41])  # the title and the source line do not count
        reported = dict((f.slide, int(re.match(r"(\d+) words", f.message).group(1)))
                        for f in dl.lint(path, notes=False, minutes=12) if f.rule == "words-per-slide")
        self.assertEqual(reported, {1: 26, 2: 30, 3: 41})
        self.assertEqual([reported[n] for n in (1, 2, 3)], shown)

    def test_a_slide_with_no_text_has_zero_words(self):
        prs = new_deck()
        add_slide(prs, None)
        lines = self.score(prs).stdout.splitlines()
        self.assertEqual(lines[lines.index("words per slide:") + 1:-1], ["slide 1: 0 words"])

    def test_the_ghost_deck_lists_every_slide_in_order_on_one_line_each(self):
        prs = new_deck()
        clean_slide(prs, title="First title of the made up deck")
        add_slide(prs, None)
        hidden = add_slide(prs, "A hidden slide keeps its place in the ghost deck")
        hidden._element.set("show", "0")
        multi = add_slide(prs, "x")
        multi.shapes.title.text_frame.text = "Second   line\nand a third   line"
        done = self.score(prs, "--minutes", "12", "--no-notes")
        self.assertEqual(block(done.stdout, "ghost deck:", "words per slide:"), [
            "slide 1: First title of the made up deck", "slide 2: (no title)",
            "slide 3: A hidden slide keeps its place in the ghost deck", "slide 4: Second line and a third line"])
        lines = done.stdout.splitlines()
        self.assertEqual(len(lines[lines.index("words per slide:") + 1:-1]), 4)

    def test_a_title_that_looks_like_a_header_or_a_summary_still_parses(self):
        prs = new_deck()
        clean_slide(prs, title="errors: 99 warnings: 99")
        clean_slide(prs, title="ghost deck:")
        clean_slide(prs, title="slide 7: words per slide:")
        score = br.parse_score(self.score(prs, "--minutes", "12", "--no-notes").stdout, "score.txt")
        self.assertEqual([title for _, title in score.ghost],
                         ["errors: 99 warnings: 99", "ghost deck:", "slide 7: words per slide:"])
        self.assertLess(score.errors, 99)

    def test_a_deck_with_no_slide_gives_empty_lists_and_exits_1(self):
        done = self.score(new_deck())
        self.assertEqual(done.returncode, 1)
        score = br.parse_score(done.stdout, "score.txt")
        self.assertEqual((score.ghost, score.words, score.errors), ([], [], 1))
        self.assertEqual([(r.slide, r.rule, r.severity) for r in score.findings], [(0, "slide-count", "error")])

    def test_no_notes_switches_the_notes_rows_off_and_the_settings_line_says_so(self):
        path = self.save(defective_deck(1))
        notes_on = self.score(path, "--minutes", "12").stdout
        notes_off = self.score(path, "--minutes", "12", "--no-notes").stdout
        self.assertIn(": notes: warn: ", notes_on)
        self.assertNotIn(": notes: warn: ", notes_off)
        self.assertEqual(notes_on.splitlines()[0].split()[-1], "notes=on")
        self.assertEqual(notes_off.splitlines()[0].split()[-1], "notes=off")

    def test_profile_theme_and_fractional_minutes_reach_the_settings_line(self):
        done = self.score(tidy_deck(1), "--minutes", "7.5", "--profile", "lab-meeting", "--theme", "dark")
        self.assertEqual(done.stdout.splitlines()[0], "settings: profile=lab-meeting minutes=7.5 theme=dark notes=on")

    def test_a_profile_changes_the_findings_as_it_does_in_the_linter(self):
        path = self.save(defective_deck(1))
        peers = br.parse_score(self.score(path, "--minutes", "12", "--no-notes").stdout, "a")
        lab = br.parse_score(self.score(path, "--minutes", "12", "--no-notes", "--profile", "lab-meeting").stdout, "b")
        self.assertTrue(any(r.rule == "words-per-slide" for r in peers.findings))
        self.assertFalse(any(r.rule == "words-per-slide" for r in lab.findings))  # 30 words is below 40

    def test_non_ascii_titles_keep_their_characters_under_the_c_locale(self):
        prs = new_deck()
        clean_slide(prs, title="Mean signal rises by 3 μM for each × dilution step")
        done = self.score(prs, "--minutes", "12", "--no-notes", env=C_LOCALE, raw=True)
        self.assertEqual((done.returncode, done.stderr), (0, b""))
        text = done.stdout.decode("utf-8")
        self.assertIn("slide 1: Mean signal rises by 3 μM for each × dilution step", text)
        self.assertEqual(br.parse_score(text, "score.txt").ghost[0][1], "Mean signal rises by 3 μM for each × dilution step")

    def test_write_utf8_encodes_by_itself_and_replaces_a_lone_surrogate(self):
        raw = io.BytesIO()
        stream = io.TextIOWrapper(raw, encoding="ascii", errors="strict")  # the encoding of the C locale
        sd.write_utf8(stream, "3 μM \ud800 ×\n")
        self.assertEqual(raw.getvalue(), "3 μM ? ×\n".encode("utf-8"))
        plain = io.StringIO()
        sd.write_utf8(plain, "text")
        self.assertEqual(plain.getvalue(), "text")

    def test_an_unexpected_exception_ends_with_exit_2_and_one_message_on_stderr(self):
        path = self.save(tidy_deck(1))
        for target, name in ((dl, "_slides"), (sd.rs, "find_title"), (sd.style, "load_style")):
            out, err = io.StringIO(), io.StringIO()
            with self.subTest(patched=name), mock.patch.object(target, name, side_effect=RuntimeError("boom\nsecond line")):
                with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                    code = sd.main([str(path), "--minutes", "12"])
            self.assertEqual((code, out.getvalue()), (2, ""))
            self.assertEqual(err.getvalue().splitlines(), ["score_deck.py: error: RuntimeError: boom second line"])

    def test_a_failure_to_write_the_output_ends_with_exit_2_and_one_message(self):
        path = self.save(tidy_deck(1))
        err = io.StringIO()
        with mock.patch.object(sd, "write_utf8", side_effect=OSError("disk full")), contextlib.redirect_stderr(err):
            code = sd.main([str(path), "--minutes", "12"])
        self.assertEqual(code, 2)
        self.assertEqual(err.getvalue().splitlines(), ["score_deck.py: error: disk full"])

    def test_an_unreadable_slide_is_listed_as_unreadable_and_gets_no_count(self):
        prs = new_deck()
        clean_slide(prs)
        path = self.save(prs)
        slide = list(prs.slides)[0]
        with mock.patch.object(dl, "_slides", return_value=([(1, slide)], [2])):
            text, errors = sd.score_text(path, 5, notes=False)
        self.assertEqual(errors, 0)
        score = br.parse_score(text, "score.txt")
        self.assertEqual(score.ghost[1], (2, "(unreadable)"))
        self.assertEqual(score.words[1], (2, None))
        self.assertEqual([r.rule for r in score.findings if r.slide == 2], ["unreadable-shape"])

    def test_the_sample_deck_scores_zero_errors_with_12_minutes(self):
        done = run_tool("score_deck.py", SAMPLE_DECK, "--minutes", "12")
        self.assertEqual((done.returncode, done.stderr), (0, ""))
        score = br.parse_score(done.stdout, "score.txt")
        self.assertEqual(score.errors, 0)
        slides = list(Presentation(str(SAMPLE_DECK)).slides)
        self.assertEqual(len(score.ghost), len(slides))
        for (number, title), slide in zip(score.ghost, slides):  # a second view of the titles, from python-pptx
            self.assertEqual(title, " ".join(slide.shapes.title.text_frame.text.split()), number)


# ---------------------------------------------------------------------------
# build_results.py
# ---------------------------------------------------------------------------

FIXTURE = {}


def setUpModule():
    """Build six decks and score each with the real script. The v1 decks carry defects and the last one an error."""
    root = Path(tempfile.mkdtemp())
    decks = root / "decks"
    decks.mkdir()
    makers = {"v1": lambda n: defective_deck(n + 2, error=(n == 3)), "minimal": tidy_deck}
    for variant, make in sorted(makers.items()):
        for number in (1, 2, 3):
            deck = decks / "{}-{}.pptx".format(variant, number)
            make(number).save(str(deck))
            done = run_tool("score_deck.py", deck, "--minutes", "12")
            if done.returncode not in (0, 1):
                raise RuntimeError(done.stderr)
            (decks / "{}-{}.score.txt".format(variant, number)).write_text(done.stdout, encoding="utf-8")
    FIXTURE["root"], FIXTURE["decks"] = root, decks


def tearDownModule():
    shutil.rmtree(str(FIXTURE["root"]), ignore_errors=True)


class Evidence(unittest.TestCase):
    """A base class with six real score files and the six decks that they came from."""

    def setUp(self):
        self.decks = FIXTURE["decks"]
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, str(self.tmp), True)

    def folder(self, decks=False, swap=False, name="evidence"):
        """Return a fresh evidence folder. `swap` gives each score file the name of the other variant."""
        folder = self.tmp / name
        folder.mkdir()
        other = {"v1": "minimal", "minimal": "v1"}
        for path in sorted(self.decks.iterdir()):
            if path.suffix == ".pptx" and not decks:
                continue
            variant, rest = path.name.split("-", 1)
            shutil.copy(str(path), str(folder / ((other[variant] if swap else variant) + "-" + rest)))
        return folder

    def run_main(self, *args):
        """Run build_results.main in this process and keep its one line of output off the screen."""
        with contextlib.redirect_stdout(io.StringIO()):
            return br.main([str(a) for a in args])

    def build(self, folder):
        out = self.tmp / "out.md"
        self.run_main(folder, "--out", out)
        return out.read_text(encoding="utf-8")

    def stop_message(self, folder):
        """Run build_results on the folder, expect a stop, and return the message. Check that no file came out."""
        out = self.tmp / "must-not-exist.md"
        with self.assertRaises(SystemExit) as caught:
            self.run_main(folder, "--out", out)
        self.assertIsInstance(caught.exception.code, str)
        self.assertFalse(out.exists())
        return caught.exception.code


def table_header(text, heading):
    """Return the header cells of the table under a level 2 heading."""
    section = text.split("## " + heading, 1)[1].split("\n## ", 1)[0]
    row = [line for line in section.splitlines() if line.startswith("|")][0]
    return [cell.strip() for cell in row.strip("|").split("|")]


def table_cells(text, heading):
    """Return the rows of the table under a level 2 heading as lists of cells."""
    section = text.split("## " + heading, 1)[1].split("\n## ", 1)[0]
    rows = [line for line in section.splitlines() if line.startswith("|")]
    return [[cell.strip() for cell in row.strip("|").split("|")] for row in rows[2:]]


class BuildResults(Evidence):
    def test_it_writes_every_section_in_order(self):
        text = self.build(self.folder())
        headings = re.findall(r"^## (.+)$", text, re.M)
        self.assertEqual(headings, ["Results per run", "Summary per variant", "Comparison", "Findings per rule",
                                    "Ghost decks", "Limits"])

    def test_the_default_output_is_results_md_above_the_evidence_folder(self):
        folder = self.folder()
        self.run_main(folder)
        self.assertTrue((self.tmp / "results.md").is_file())
        self.assertFalse((folder / "results.md").exists())

    def test_the_command_line_exits_0_when_it_writes(self):
        folder = self.folder()
        done = run_tool("build_results.py", folder, "--out", self.tmp / "r.md")
        self.assertEqual((done.returncode, done.stderr), (0, ""))
        self.assertTrue((self.tmp / "r.md").is_file())

    def test_the_run_table_matches_a_count_that_the_test_makes_itself(self):
        text = self.build(self.folder())
        rows = table_cells(text, "Results per run")
        self.assertEqual([r[:2] for r in rows], [[v, str(n)] for v in ("v1", "minimal") for n in (1, 2, 3)])
        for row in rows:
            saved = (self.decks / "{}-{}.score.txt".format(row[0], row[1])).read_text()
            findings = block(saved, "findings:", "ghost deck:")
            ghost = block(saved, "ghost deck:", "words per slide:")
            counts = [int(m) for m in re.findall(r"^slide \d+: (\d+) words$", saved, re.M)]
            errors = sum(1 for line in findings if line.split(": ")[2] == "error")
            flagged = set(line.split(": ")[0] for line in findings
                          if line.split(": ")[1] in ("title-empty", "title-sentence", "title-unique"))
            expected = [len(ghost), errors, len(findings) - errors, max(counts), len(flagged)]
            self.assertEqual([int(c) for c in row[2:]], expected, row)

    def test_the_summary_is_computed_from_the_table(self):
        text = self.build(self.folder())
        runs = table_cells(text, "Results per run")
        summary = table_cells(text, "Summary per variant")
        for row in summary:
            mine = [[int(c) for c in r[2:]] for r in runs if r[0] == row[0]]
            self.assertEqual(int(row[1]), len(mine))
            self.assertEqual(row[2], "{:.1f}".format(sum(m[0] for m in mine) / float(len(mine))))
            self.assertEqual(int(row[3]), sum(m[1] for m in mine))
            self.assertEqual(int(row[4]), sum(m[2] for m in mine))
            self.assertEqual(row[5], "{:.1f}".format(sum(m[2] for m in mine) / float(len(mine))))
            self.assertEqual(row[6], "{} of {}".format(sum(1 for m in mine if m[1] == 0), len(mine)))
            self.assertEqual(int(row[7]), max(m[3] for m in mine))
            self.assertEqual(int(row[8]), sum(m[4] for m in mine))

    def test_the_comparison_wording_follows_the_numbers(self):
        for swap, fixed in ((False, ("fewer errors", "fewer warnings", "fewer flagged titles", "fewer slides",
                                     "holds fewer words")),
                            (True, ("more errors", "more warnings", "more flagged titles", "more slides",
                                    "holds more words"))):
            text = self.build(self.folder(swap=swap, name="evidence-swap" if swap else "evidence"))
            sentences = re.findall(r"^- (The .+)$", text.split("## Comparison", 1)[1].split("\n## ", 1)[0], re.M)
            self.assertEqual(len(sentences), 5)
            for sentence, expected in zip(sentences, fixed):
                self.assertIn(expected, sentence)

    def test_equal_counts_give_the_wording_for_the_same_number(self):
        folder = self.tmp / "equal"
        folder.mkdir()
        for number in (1, 2, 3):
            for variant in ("v1", "minimal"):
                shutil.copy(str(self.decks / "minimal-{}.score.txt".format(number)),
                            str(folder / "{}-{}.score.txt".format(variant, number)))
        text = self.build(folder)
        section = text.split("## Comparison", 1)[1].split("\n## ", 1)[0]
        self.assertEqual(section.count("the same number of"), 5)
        self.assertNotIn("fewer", section)
        self.assertNotIn("more", section)

    def test_a_sentence_changes_when_one_count_changes(self):
        before = self.build(self.folder())
        folder = self.folder(name="evidence-edit")
        path = folder / "minimal-2.score.txt"
        text = path.read_text()
        error = ("slide 1: title-empty: error: T2: no title placeholder or shape named Title holds text; add a headline "
                 "that states the claim")
        edited = text.replace("findings:\n", "findings:\n" + error + "\n", 1).replace(
            "errors: 0 ", "errors: 1 ", 1)
        path.write_text(edited)
        after = self.build(folder)

        def about_errors(report):
            return [line for line in report.splitlines() if line.startswith("- The minimal decks") and "errors" in line]

        self.assertEqual(about_errors(before),
                         ["- The minimal decks have fewer errors than the v1 decks: 0 against 1 in total."])
        self.assertEqual(about_errors(after),
                         ["- The minimal decks have the same number of errors as the v1 decks: 1 and 1 in total."])

    def test_the_text_of_the_report_follows_the_writing_rules_and_holds_nothing_private(self):
        text = self.build(self.folder(decks=True))
        self.assertEqual(prose_problems(text), [])
        self.assertEqual(private_matches(text), [])

    def test_the_limits_section_states_the_limits(self):
        limits = self.build(self.folder()).split("## Limits", 1)[1]
        for phrase in ("3 runs per variant on one synthetic project", "headless", "belongs to the minimal plugin",
                       "does not score", "read the ghost decks", "audience outcomes",
                       "The All slides column counts every slide. The slide-count rule of the linter counts "
                       "visible main slides only."):
            self.assertIn(phrase, limits)

    def test_the_report_is_the_same_on_every_build(self):
        folder = self.folder(decks=True)
        self.assertEqual(self.build(folder), self.build(folder))

    def test_the_ghost_decks_show_every_title_of_every_run(self):
        text = self.build(self.folder())
        self.assertIn("### v1 run 3 (6 slides)", text)
        self.assertIn("6. (no title)", text)
        self.assertIn("### minimal run 1 (1 slide)", text)

    def test_a_good_title_with_other_findings_is_not_a_flagged_title(self):
        folder = self.folder()
        deck = self.tmp / "mixed.pptx"
        mixed_deck().save(str(deck))
        done = run_tool("score_deck.py", deck, "--minutes", "12")
        (folder / "minimal-1.score.txt").write_text(done.stdout, encoding="utf-8")
        score = br.parse_score(done.stdout, "mixed.score.txt")
        self.assertEqual(sorted(r.rule for r in score.findings if r.slide == 1), ["notes", "words-per-slide"])
        self.assertEqual([r.rule for r in score.findings if r.slide == 2 and r.rule in br.TITLE_RULES],
                         ["title-sentence"])
        mixed = [run for run in br.load_runs(folder) if (run.variant, run.number) == ("minimal", 1)][0]
        self.assertEqual(br.run_stats(mixed).flagged, 1)
        row = [r for r in table_cells(self.build(folder), "Results per run") if r[:2] == ["minimal", "1"]][0]
        self.assertEqual(row[-1], "1")
        with mock.patch.object(br, "TITLE_RULES", br.TITLE_RULES + ("notes", "title-font")):
            self.assertEqual(br.run_stats(mixed).flagged, 2)  # a wider definition would count slide 1 as well

    def test_each_column_has_one_name_and_the_all_slides_column_says_what_it_counts(self):
        text = self.build(self.folder())
        self.assertEqual(table_header(text, "Results per run"), [
            "Variant", "Run", "All slides", "Errors", "Warnings", "Words on the busiest slide", "Flagged titles"])
        self.assertEqual(table_header(text, "Summary per variant"), [
            "Variant", "Runs", "All slides per run", "Errors", "Warnings", "Warnings per run", "Runs without errors",
            "Words on the busiest slide", "Flagged titles"])
        comparison = section_of(text, "Comparison")
        self.assertIn("The busiest slide of the minimal decks", comparison)
        self.assertIn("fewer flagged titles", comparison)

    def test_the_names_of_the_columns_do_not_drift_in_any_file(self):
        for path in [VERIFICATION / name for name in SCRIPTS] + [VERIFICATION / "evidence" / "README.md"]:
            text = path.read_text(encoding="utf-8")
            for old in ("Titles flagged", "Most words on one slide", "Slides per run", '"Slides"'):
                with self.subTest(file=path.name, name=old):
                    self.assertNotIn(old, text.replace("All slides per run", ""))

    def test_a_skip_note_is_described_once_as_a_warning_and_the_warnings_comparison_says_so(self):
        text = self.build(self.folder())
        self.assertIn("A skip note is a warning and counts under its rule.", section_of(text, "Findings per rule"))
        self.assertNotIn("rule skipped counts", text)
        about_warnings = [line for line in section_of(text, "Comparison").splitlines() if " warnings " in line]
        self.assertEqual(len(about_warnings), 1)
        self.assertTrue(about_warnings[0].endswith(" Skip notes raise the warning count."), about_warnings[0])

    def test_the_command_line_exits_2_for_a_usage_error(self):
        for args in ((), ("--bogus", "folder")):
            with self.subTest(args=args):
                done = run_tool("build_results.py", *args)
                self.assertEqual((done.returncode, done.stdout), (2, ""))
                self.assertIn("usage:", done.stderr)

    def test_the_results_file_is_written_through_a_temporary_file_that_is_gone_afterwards(self):
        folder = self.folder()
        out_dir = self.tmp / "reports"
        out_dir.mkdir()
        other = out_dir / "other.txt"
        other.write_text("a file with the default mode")
        self.run_main(folder, "--out", out_dir / "results.md")
        self.assertEqual(sorted(p.name for p in out_dir.iterdir()), ["other.txt", "results.md"])
        self.assertEqual(stat.S_IMODE((out_dir / "results.md").stat().st_mode), stat.S_IMODE(other.stat().st_mode))

    def test_a_write_error_keeps_the_results_file_that_exists_and_leaves_no_temporary_file(self):
        folder = self.folder()
        out_dir = self.tmp / "reports"
        out_dir.mkdir()
        out = out_dir / "results.md"
        out.write_text("the old results")

        class HalfWriter(object):
            """A file that writes ten bytes and then fails, as a full disk does."""

            def __init__(self, handle):
                self.handle = handle

            def __enter__(self):
                return self

            def __exit__(self, *details):
                self.handle.close()
                return False

            def write(self, data):
                self.handle.write(data[:10])
                raise OSError("disk full")

        real_open = open
        failures = (("the write", mock.patch.object(br, "open", create=True, new=lambda *a: HalfWriter(real_open(*a))),
                     "disk full"),
                    ("the rename", mock.patch.object(br.os, "replace", side_effect=OSError("no rename")), "no rename"))
        for label, patched, cause in failures:
            with self.subTest(failing=label):
                with patched, self.assertRaises(SystemExit) as caught:
                    self.run_main(folder, "--out", out)
                self.assertIn("cannot write", caught.exception.code)
                self.assertIn(cause, caught.exception.code)
                self.assertEqual(out.read_text(), "the old results")
                self.assertEqual([p.name for p in out_dir.iterdir()], ["results.md"])

    def test_the_summary_counts_the_runs_that_it_is_given(self):
        runs = br.load_runs(self.folder())
        self.assertEqual(br.summarize(runs, "v1").runs, 3)
        self.assertEqual(br.summarize([run for run in runs if run.number < 3], "v1").runs, 2)

    # --- failures ---------------------------------------------------------

    def test_a_missing_score_file_stops_with_its_name_and_writes_nothing(self):
        for variant in ("v1", "minimal"):
            for number in (1, 2, 3):
                name = "{}-{}.score.txt".format(variant, number)
                with self.subTest(name=name):
                    folder = self.folder(name="e-" + name)
                    (folder / name).unlink()
                    message = self.stop_message(folder)
                    self.assertIn("missing score file", message)
                    self.assertIn(name, message)

    def test_every_missing_file_is_named(self):
        folder = self.folder()
        for name in ("v1-1.score.txt", "minimal-3.score.txt"):
            (folder / name).unlink()
        message = self.stop_message(folder)
        self.assertIn("v1-1.score.txt", message)
        self.assertIn("minimal-3.score.txt", message)

    def test_a_missing_folder_stops(self):
        self.assertIn("does not exist", self.stop_message(self.tmp / "nowhere"))

    def test_a_score_file_with_another_name_stops(self):
        folder = self.folder()
        shutil.copy(str(folder / "v1-1.score.txt"), str(folder / "v1-4.score.txt"))
        message = self.stop_message(folder)
        self.assertIn("unexpected score file", message)
        self.assertIn("v1-4.score.txt", message)

    def test_an_empty_score_file_stops(self):
        folder = self.folder()
        (folder / "v1-2.score.txt").write_text("")
        self.assertIn("v1-2.score.txt", self.stop_message(folder))

    def test_a_score_file_that_is_not_utf8_stops(self):
        folder = self.folder()
        (folder / "v1-2.score.txt").write_bytes(b"\xff\xfe\x00")
        self.assertIn("not UTF-8", self.stop_message(folder))

    def test_a_malformed_score_file_stops_with_the_file_and_the_line(self):
        folder = self.folder()
        path = folder / "minimal-2.score.txt"
        path.write_text(path.read_text().replace("ghost deck:\n", "ghost deck:\nthis line is wrong\n"))
        message = self.stop_message(folder)
        self.assertIn("minimal-2.score.txt:", message)
        self.assertIn("this line is wrong", message)

    def test_scores_made_with_different_settings_stop(self):
        folder = self.folder()
        done = run_tool("score_deck.py", self.decks / "v1-3.pptx", "--minutes", "10")
        (folder / "v1-3.score.txt").write_text(done.stdout)
        message = self.stop_message(folder)
        self.assertIn("different settings", message)
        self.assertIn("v1-3: profile peers minutes 10", message)

    def test_a_failed_run_keeps_the_results_file_that_exists(self):
        folder = self.folder()
        (folder / "v1-1.score.txt").unlink()
        out = self.tmp / "results.md"
        out.write_text("the old results")
        with self.assertRaises(SystemExit):
            self.run_main(folder, "--out", out)
        self.assertEqual(out.read_text(), "the old results")

    # --- decks that are present ------------------------------------------

    def test_with_all_six_decks_present_the_scores_are_checked_again(self):
        text = self.build(self.folder(decks=True))
        self.assertIn("scored each of the 6 decks again, and each new score matched", text)

    def test_with_no_deck_present_the_report_says_so(self):
        self.assertIn("No deck file was present", self.build(self.folder()))

    def test_with_some_decks_present_the_report_counts_them(self):
        folder = self.folder(decks=True)
        for name in ("v1-1.pptx", "v1-2.pptx", "minimal-3.pptx"):
            (folder / name).unlink()
        self.assertIn("3 of 6 deck files were present", self.build(folder))

    def test_a_saved_score_that_disagrees_with_its_deck_stops(self):
        folder = self.folder(decks=True)
        shutil.copy(str(self.decks / "v1-3.pptx"), str(folder / "v1-2.pptx"))  # another deck under the same name
        message = self.stop_message(folder)
        self.assertIn("v1-2.score.txt: the saved score does not match the deck v1-2.pptx", message)

    def test_a_deck_that_cannot_be_read_stops(self):
        folder = self.folder(decks=True)
        (folder / "minimal-1.pptx").write_text("not a deck")
        self.assertIn("cannot score the deck minimal-1.pptx", self.stop_message(folder))


NOTES_HEADING = "## Notes of the controller"
READ_HEADING = "## Ghost decks as read by the controller"
GHOST_POINTER = ('A v1 slide reads "(no title)" here because v1 builds titles as text boxes, so "Ghost decks as read by '
                 'the controller" holds them.')
RUN_NAMES = ["{}-{}".format(variant, number) for variant in br.VARIANTS for number in br.RUNS]


def titles_text(score_text, prefix="Controller title"):
    """Return a titles file for a score file: one row for each slide of its ghost deck."""
    count = len(block(score_text, "ghost deck:", "words per slide:"))
    return "".join("slide {}: {} {}\n".format(number, prefix, number) for number in range(1, count + 1))


class ControllerTitles(Evidence):
    """The optional file <variant>-<n>.titles.txt holds the titles of a run as the controller read them."""

    def with_titles(self, names=RUN_NAMES, **kwargs):
        folder = self.folder(**kwargs)
        for name in names:
            saved = (folder / (name + ".score.txt")).read_text(encoding="utf-8")
            (folder / (name + ".titles.txt")).write_text(titles_text(saved), encoding="utf-8")
        return folder

    def test_each_titles_file_adds_one_block_in_the_order_of_the_runs(self):
        text = self.build(self.with_titles())
        self.assertEqual(re.findall(r"^## (.+)$", text, re.M), [
            "Results per run", "Summary per variant", "Comparison", "Findings per rule", "Ghost decks",
            "Ghost decks as read by the controller", "Limits"])
        read = section_of(text, "Ghost decks as read by the controller")
        self.assertEqual(re.findall(r"^### (.+)$", read, re.M), [
            "v1 run 1 (3 slides)", "v1 run 2 (4 slides)", "v1 run 3 (6 slides)", "minimal run 1 (1 slide)",
            "minimal run 2 (2 slides)", "minimal run 3 (3 slides)"])
        self.assertIn("### v1 run 3 (6 slides)\n\n1. Controller title 1\n", read)
        self.assertIn("6. Controller title 6\n", read)
        self.assertNotIn("No titles file", read)
        self.assertIn("6. (no title)", section_of(text, "Ghost decks"))  # the ghost deck of the linter stays as it is

    def test_the_tables_and_the_comparison_keep_the_numbers_of_the_linter(self):
        folder = self.with_titles()
        with_titles = self.build(folder)
        without = self.build(self.folder(name="evidence-without"))
        for heading in ("Results per run", "Summary per variant", "Comparison", "Findings per rule", "Ghost decks",
                        "Limits"):
            # The ghost decks of the linter are the same. Only the pointer to the titles of the controller is added.
            self.assertEqual(section_of(with_titles, heading).replace(GHOST_POINTER + "\n\n", ""),
                             section_of(without, heading), heading)

    def test_the_ghost_decks_point_to_the_titles_of_the_controller_when_they_exist(self):
        with_titles = section_of(self.build(self.with_titles()), "Ghost decks")
        self.assertTrue(with_titles.lstrip("\n").startswith(GHOST_POINTER + "\n\n### v1 run 1"), with_titles[:300])
        self.assertNotIn(GHOST_POINTER, self.build(self.folder(name="evidence-without")))

    def test_some_titles_files_leave_the_other_runs_named_in_one_sentence(self):
        text = self.build(self.with_titles(names=("v1-1", "minimal-2")))
        read = section_of(text, "Ghost decks as read by the controller")
        self.assertEqual(re.findall(r"^### (.+)$", read, re.M), ["v1 run 1 (3 slides)", "minimal run 2 (2 slides)"])
        self.assertIn("No titles file for v1-2, v1-3, minimal-1, minimal-3.", read)

    def test_without_a_titles_file_the_report_has_no_such_section_and_stays_the_same(self):
        text = self.build(self.folder())
        self.assertNotIn("as read by the controller", text)
        self.assertNotIn(NOTES_HEADING, text)

    def test_a_title_that_looks_like_a_row_or_a_header_is_kept(self):
        folder = self.with_titles(names=("minimal-1",))
        (folder / "minimal-1.titles.txt").write_text("slide 1: slide 7: errors: 99 warnings: 99\n", encoding="utf-8")
        self.assertIn("1. slide 7: errors: 99 warnings: 99\n", self.build(folder))

    def test_a_malformed_titles_file_stops_with_the_file_and_the_line(self):
        valid = "slide 1: Controller title 1\nslide 2: Controller title 2\nslide 3: Controller title 3\n"
        cases = (
            ("no final newline", valid[:-1], "does not end with a newline"),
            ("a carriage return", valid.replace("\n", "\r\n"), "carriage return"),
            ("a row of another shape", valid.replace("slide 2: ", "page 2: "), "v1-1.titles.txt:2: not a title row"),
            ("a slide number that skips", valid.replace("slide 2:", "slide 3:"), "v1-1.titles.txt:2: the slide numbers"),
            ("a slide number 0", valid.replace("slide 1:", "slide 0:"), "v1-1.titles.txt:1: not a title row"),
            ("an empty title", valid.replace("Controller title 2", ""), "v1-1.titles.txt:2: not a title row"),
            ("a title with a leading space", valid.replace("slide 2: ", "slide 2:  "), "v1-1.titles.txt:2: not a title row"),
            ("a blank line", valid.replace("slide 2:", "\nslide 2:"), "v1-1.titles.txt:2: not a title row"),
            ("a header line", "titles:\n" + valid, "v1-1.titles.txt:1: not a title row"),
            ("an empty file", "", "does not end with a newline"),
        )
        for label, text, phrase in cases:
            with self.subTest(defect=label):
                folder = self.with_titles(names=(), name="e-" + label.replace(" ", "-"))
                (folder / "v1-1.titles.txt").write_text(text, encoding="utf-8")
                message = self.stop_message(folder)
                self.assertIn(phrase, message)
                self.assertTrue(message.startswith("v1-1.titles.txt"), message)

    def test_a_titles_file_that_is_not_utf8_stops(self):
        folder = self.with_titles(names=())
        (folder / "v1-1.titles.txt").write_bytes(b"slide 1: caf\xe9\n")
        message = self.stop_message(folder)
        self.assertIn("v1-1.titles.txt", message)
        self.assertIn("not UTF-8", message)

    def test_a_titles_file_with_another_slide_count_than_its_score_file_stops(self):
        for label, rows in (("one row short", 2), ("one row too many", 4)):
            with self.subTest(defect=label):
                folder = self.with_titles(names=(), name="e-" + label.replace(" ", "-"))
                (folder / "v1-1.titles.txt").write_text(
                    "".join("slide {}: Controller title {}\n".format(n, n) for n in range(1, rows + 1)),
                    encoding="utf-8")
                message = self.stop_message(folder)
                self.assertIn("v1-1.titles.txt: the titles file lists {} slides and the score file lists 3".format(rows),
                              message)

    def test_a_titles_file_with_a_name_that_no_run_has_stops(self):
        for name in ("v1-4.titles.txt", "minimal-0.titles.txt", "v2-1.titles.txt", "notes.titles.txt"):
            with self.subTest(name=name):
                folder = self.with_titles(names=("v1-1",), name="e-" + name)
                shutil.copy(str(folder / "v1-1.titles.txt"), str(folder / name))
                message = self.stop_message(folder)
                self.assertIn("unexpected titles file", message)
                self.assertIn(name, message)

    def test_a_folder_with_the_name_of_a_titles_file_stops(self):
        folder = self.with_titles(names=())
        (folder / "v1-2.titles.txt").mkdir()
        self.assertIn("is not a file", self.stop_message(folder))

    def test_a_titles_file_beside_a_missing_score_file_reports_the_missing_score_file(self):
        folder = self.with_titles()
        (folder / "v1-2.score.txt").unlink()
        self.assertIn("missing score file(s)", self.stop_message(folder))


class ControllerNotes(Evidence):
    """The optional file controller-notes.md goes to the end of results.md as it is."""

    NOTES = (
        ("plain text", "The controller read all six decks.\n"),
        ("no final newline", "A last line without a newline"),
        ("windows line ends", "line one\r\nline two\r\n"),
        ("headings and numbers", "## A heading of the controller\n\nerrors: 99 warnings: 99\n\n- 12 of 15 slides\n"),
        ("trailing spaces and blank lines", "text with trailing spaces   \n\n\n\n"),
        ("non-ASCII characters", "A signal of 3 μM and a dilution of 2 × and β\n"),
        ("a long line", "word " * 200 + "\n"),
        ("an empty file", ""),
    )

    def build_bytes(self, folder):
        out = self.tmp / "out-{}.md".format(len(list(self.tmp.iterdir())))
        self.run_main(folder, "--out", out)
        return out.read_bytes()

    def test_the_notes_end_the_report_byte_for_byte_under_their_own_heading(self):
        baseline = self.build_bytes(self.folder())
        for label, notes in self.NOTES:
            with self.subTest(notes=label):
                folder = self.folder(name="e-" + label.replace(" ", "-"))
                (folder / "controller-notes.md").write_bytes(notes.encode("utf-8"))
                text = self.build_bytes(folder)
                self.assertEqual(text, baseline + b"\n" + NOTES_HEADING.encode("ascii") + b"\n\n" + notes.encode("utf-8"))

    def test_the_notes_come_after_the_limits_and_change_no_number_above_them(self):
        folder = self.folder()
        (folder / "controller-notes.md").write_text("errors: 99\n## Limits\n", encoding="utf-8")
        text = self.build(folder)
        base = self.build(self.folder(name="evidence-without"))
        self.assertTrue(text.startswith(base))
        self.assertGreater(text.index(NOTES_HEADING), text.index("## Limits"))
        self.assertEqual(text[len(base):], "\n" + NOTES_HEADING + "\n\nerrors: 99\n## Limits\n")

    def test_without_the_notes_the_report_has_no_heading_for_them(self):
        self.assertNotIn("Notes of the controller", self.build(self.folder()))

    def test_the_notes_file_is_not_changed_by_a_run(self):
        folder = self.folder()
        path = folder / "controller-notes.md"
        path.write_bytes("Keep this text.\r\n".encode("utf-8"))
        before = snapshot(folder)
        self.build(folder)
        self.assertEqual(snapshot(folder), before)

    def test_notes_that_are_not_utf8_stop_the_run(self):
        folder = self.folder()
        (folder / "controller-notes.md").write_bytes(b"caf\xe9\n")
        message = self.stop_message(folder)
        self.assertIn("controller-notes.md", message)
        self.assertIn("not UTF-8", message)

    def test_a_folder_with_the_name_of_the_notes_file_stops(self):
        folder = self.folder()
        (folder / "controller-notes.md").mkdir()
        self.assertIn("is not a file", self.stop_message(folder))

    def test_the_command_line_copies_non_ascii_notes_under_the_c_locale(self):
        folder = self.folder()
        notes = "A signal of 3 μM and a dilution of 2 × and β\n"
        (folder / "controller-notes.md").write_bytes(notes.encode("utf-8"))
        out = self.tmp / "c-locale.md"
        done = run_tool("build_results.py", folder, "--out", out, env=C_LOCALE, raw=True)
        self.assertEqual((done.returncode, done.stderr), (0, b""))
        self.assertTrue(out.read_bytes().endswith(("\n" + NOTES_HEADING + "\n\n" + notes).encode("utf-8")))


class StrictParser(Evidence):
    """Each seeded defect corrupts one line of a real score file. The parser must stop and name the line."""

    def setUp(self):
        super().setUp()
        self.text = (self.decks / "v1-1.score.txt").read_text()
        self.lines = self.text.splitlines()

    def edit(self, index, new):
        lines = list(self.lines)
        if new is None:
            del lines[index]
        else:
            lines[index] = new
        return "\n".join(lines) + "\n"

    def stops(self, text, *phrases):
        with self.assertRaises(SystemExit) as caught:
            br.parse_score(text, "x.score.txt")
        message = caught.exception.code
        self.assertIsInstance(message, str)
        self.assertTrue(message.startswith("x.score.txt"), message)
        for phrase in phrases:
            self.assertIn(phrase, message)
        return message

    def index_of(self, prefix):
        return next(i for i, line in enumerate(self.lines) if line.startswith(prefix))

    def test_the_real_file_parses(self):
        score = br.parse_score(self.text, "x.score.txt")
        self.assertEqual(len(score.ghost), 3)
        self.assertGreater(len(score.findings), 5)

    def test_a_finding_row_with_a_bad_severity(self):
        index = self.index_of("slide 1: title-sentence")
        self.stops(self.edit(index, self.lines[index].replace(": warn: ", ": warning: ")),
                   "x.score.txt:{}:".format(index + 1), "not a finding row")

    def test_a_finding_row_with_a_bad_tier(self):
        index = self.index_of("slide 1: title-sentence")
        self.stops(self.edit(index, self.lines[index].replace(": T3: ", ": T4: ")),
                   "x.score.txt:{}:".format(index + 1))

    def test_a_finding_row_for_slide_0(self):
        index = self.index_of("slide 1: title-sentence")
        self.stops(self.edit(index, self.lines[index].replace("slide 1:", "slide 0:", 1)),
                   "x.score.txt:{}:".format(index + 1))

    def test_a_finding_row_with_a_leading_space(self):
        index = self.index_of("slide 1: title-sentence")
        self.stops(self.edit(index, " " + self.lines[index]), "x.score.txt:{}:".format(index + 1))

    def test_a_finding_row_with_an_empty_message(self):
        index = self.index_of("slide 1: title-sentence")
        self.stops(self.edit(index, "slide 1: title-sentence: warn: T3: "), "x.score.txt:{}:".format(index + 1))

    def test_a_finding_row_with_a_rule_in_capitals(self):
        index = self.index_of("slide 1: title-sentence")
        self.stops(self.edit(index, self.lines[index].replace("title-sentence", "Title_Sentence")),
                   "x.score.txt:{}:".format(index + 1))

    def test_a_ghost_row_that_skips_a_number(self):
        index = self.index_of("slide 2: Results 2")
        self.stops(self.edit(index, "slide 5: Results 2"), "x.score.txt:{}:".format(index + 1), "1, 2, 3")

    def test_a_ghost_row_with_an_empty_title(self):
        index = self.index_of("slide 2: Results 2")
        self.stops(self.edit(index, "slide 2: "), "x.score.txt:{}:".format(index + 1))

    def test_a_word_row_that_spells_the_count(self):
        index = self.lines.index("words per slide:") + 1
        self.stops(self.edit(index, "slide 1: thirty words"), "x.score.txt:{}:".format(index + 1), "word count")

    def test_a_word_row_without_the_word_words(self):
        index = self.lines.index("words per slide:") + 1
        self.stops(self.edit(index, "slide 1: 30"), "x.score.txt:{}:".format(index + 1))

    def test_a_word_row_with_a_negative_count(self):
        index = self.lines.index("words per slide:") + 1
        self.stops(self.edit(index, "slide 1: -3 words"), "x.score.txt:{}:".format(index + 1))

    def test_a_blank_line_inside_a_block(self):
        index = self.lines.index("ghost deck:") + 1
        self.stops(self.edit(index, "\n" + self.lines[index]), "x.score.txt:{}:".format(index + 1))

    def test_a_missing_header(self):
        index = self.lines.index("ghost deck:")
        self.stops(self.edit(index, None), "not a finding row", "Results 1")

    def test_a_summary_that_disagrees_with_the_rows_about_errors(self):
        warnings = self.lines[-1].split()[-1]
        self.stops(self.edit(len(self.lines) - 1, "errors: 5 warnings: " + warnings),
                   "the summary says 5 errors and the rows hold 0")

    def test_a_summary_that_disagrees_with_the_rows_about_warnings(self):
        warnings = int(self.lines[-1].split()[-1])
        self.stops(self.edit(len(self.lines) - 1, "errors: 0 warnings: {}".format(warnings + 1)),
                   "the summary says {} warnings and the rows hold {}".format(warnings + 1, warnings))

    def test_a_summary_in_another_format(self):
        self.stops(self.edit(len(self.lines) - 1, "errors=0 warnings=12"), "the summary line", "errors=0 warnings=12")

    def test_text_after_the_summary(self):
        self.stops(self.text + "one more line\n", "text after the summary line")

    def test_a_missing_summary(self):
        self.stops("\n".join(self.lines[:-1]) + "\n", "expected the summary line")

    def test_a_settings_line_with_bad_minutes(self):
        for bad in ("abc", "0", "-3", "nan", "inf"):
            with self.subTest(minutes=bad):
                self.stops(self.edit(0, self.lines[0].replace("minutes=12", "minutes=" + bad)), "x.score.txt:1:")

    def test_a_settings_line_with_an_unknown_profile_or_theme(self):
        self.stops(self.edit(0, self.lines[0].replace("profile=peers", "profile=nobody")), "unknown profile")
        self.stops(self.edit(0, self.lines[0].replace("theme=light", "theme=pink")), "unknown theme")

    def test_a_missing_settings_line(self):
        self.stops(self.edit(0, None), "x.score.txt:1:", "settings")

    def test_a_file_without_the_final_newline(self):
        self.stops(self.text[:-1], "does not end with a newline")

    def test_a_file_with_windows_line_ends(self):
        self.stops(self.text.replace("\n", "\r\n"), "carriage return")

    def test_an_empty_file(self):
        self.stops("", "does not end with a newline")

    def test_a_ghost_deck_that_is_shorter_than_the_word_counts(self):
        index = self.index_of("slide 3: Results 3")
        self.stops(self.edit(index, None), "ghost deck lists 2 slides and the word counts list 3")

    def test_a_slide_that_is_unreadable_in_one_list_only(self):
        index = self.index_of("slide 2: Results 2")
        self.stops(self.edit(index, "slide 2: (unreadable)"), "unreadable in one list")

    def test_a_finding_that_names_a_slide_beyond_the_deck(self):
        index = self.index_of("slide 1: title-sentence")
        self.stops(self.edit(index, self.lines[index].replace("slide 1:", "slide 9:", 1)),
                   "names a slide that the ghost deck does not list")


class Guards(unittest.TestCase):
    def test_check_stops_with_the_message_and_passes_a_true_condition(self):
        with self.assertRaises(SystemExit) as caught:
            br.check(False, "the message")
        self.assertEqual(caught.exception.code, "the message")
        self.assertIsNone(br.check(True, "never shown"))

    def test_the_tools_hold_no_assert_statement(self):
        for name in SCRIPTS:
            tree = ast.parse((VERIFICATION / name).read_text(encoding="utf-8"))
            self.assertEqual([n.lineno for n in ast.walk(tree) if isinstance(n, ast.Assert)], [], name)

    def test_the_scan_for_assert_finds_one(self):
        tree = ast.parse("def f(x):\n    assert x, 'no'\n")
        self.assertEqual(len([n for n in ast.walk(tree) if isinstance(n, ast.Assert)]), 1)


class UnderOptimizedPython(Evidence):
    """python3 -O removes assert statements. The checks of build_results must still stop the run."""

    def run_O(self, folder):
        out = self.tmp / "o.md"
        done = run_tool("build_results.py", folder, "--out", out, flags=("-O",))
        return done, out

    def test_a_missing_file_still_stops_the_run(self):
        folder = self.folder()
        (folder / "v1-2.score.txt").unlink()
        done, out = self.run_O(folder)
        self.assertEqual(done.returncode, 1)
        self.assertIn("missing score file(s)", done.stderr)
        self.assertIn("v1-2.score.txt", done.stderr)
        self.assertFalse(out.exists())

    def test_a_claim_that_disagrees_still_stops_the_run(self):
        folder = self.folder()
        path = folder / "minimal-1.score.txt"
        path.write_text(path.read_text().replace("errors: 0 warnings: 0", "errors: 4 warnings: 0"))
        done, out = self.run_O(folder)
        self.assertEqual(done.returncode, 1)
        self.assertIn("the summary says 4 errors and the rows hold 0", done.stderr)
        self.assertFalse(out.exists())

    def test_a_stale_deck_still_stops_the_run(self):
        folder = self.folder(decks=True)
        shutil.copy(str(self.decks / "minimal-3.pptx"), str(folder / "minimal-1.pptx"))
        done, out = self.run_O(folder)
        self.assertEqual(done.returncode, 1)
        self.assertIn("does not match the deck minimal-1.pptx", done.stderr)
        self.assertFalse(out.exists())

    def test_good_input_still_builds_the_report(self):
        done, out = self.run_O(self.folder(decks=True))
        self.assertEqual((done.returncode, done.stderr), (0, ""))
        self.assertIn("## Limits", out.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# The files themselves
# ---------------------------------------------------------------------------

class PublicFiles(unittest.TestCase):
    TEXTS = [VERIFICATION / name for name in SCRIPTS] + [VERIFICATION / "evidence" / "README.md", Path(__file__)]

    def test_no_file_holds_a_private_path_an_address_or_an_em_dash(self):
        for path in self.TEXTS:
            text = path.read_text(encoding="utf-8")
            with self.subTest(file=path.name):
                self.assertEqual(private_matches(text), [])
                self.assertNotIn(EM_DASH, text)

    def test_no_comment_string_or_document_uses_a_banned_word_or_a_not_pair(self):
        for path in self.TEXTS:
            text = prose_of(path)
            for word in BANNED_WORDS:
                with self.subTest(file=path.name, word=word):
                    self.assertIsNone(re.search(r"(?<![\w-]){}(?![\w-])".format(re.escape(word)), text, re.I))
            with self.subTest(file=path.name, rule="a pair of a claim and its denial"):
                self.assertIsNone(re.search(r"\w,\s+(?:not|never)\s", text, re.I))

    def test_no_sentence_of_a_docstring_or_comment_is_longer_than_25_words(self):
        for name in SCRIPTS:
            sentences = sentences_of_docs_and_comments(VERIFICATION / name)
            with self.subTest(file=name):
                self.assertGreater(len(sentences), 20)  # the scan reads something
                self.assertEqual([(len(u.split()), u[:60]) for u in sentences if len(u.split()) > SENTENCE_LIMIT], [])

    def test_the_scan_of_docstrings_and_comments_finds_a_long_sentence_in_each(self):
        folder = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, str(folder), True)
        long_text = " ".join(["word"] * 26) + "."
        path = folder / "sample.py"
        path.write_text('"""{0}\n\nA short line.\n\n    {0}\n"""\nx = 1  # {0}\n# A short comment.\n# A second line.\n'.format(
            long_text), encoding="utf-8")
        lengths = [len(u.split()) for u in sentences_of_docs_and_comments(path)]
        self.assertEqual(sorted(lengths), [3, 3, 3, 26, 26])  # the long sentence of the docstring and the inline one
        self.assertEqual(len([n for n in lengths if n > SENTENCE_LIMIT]), 2)  # the indented sample drops out

    def test_the_evidence_readme_states_the_exit_codes_and_the_limits_of_its_numbers(self):
        text = (VERIFICATION / "evidence" / "README.md").read_text(encoding="utf-8")
        for phrase in ("The script `build_results.py` exits with 1", "It exits with 2 for a usage error",
                       "Each must be a name that the plugin knows", "It must be finite and above 0",
                       "counts visible main slides only", "The busiest slide of a run"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_the_evidence_readme_documents_the_titles_file_and_the_notes_of_the_controller(self):
        text = (VERIFICATION / "evidence" / "README.md").read_text(encoding="utf-8")
        for phrase in ("v1-1.titles.txt", "controller-notes.md", "Ghost decks as read by the controller",
                       "Notes of the controller", "plain text boxes", "as many slides as the score file",
                       "It does not change, wrap or count anything in it"):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_the_titles_example_in_the_readme_parses(self):
        text = (VERIFICATION / "evidence" / "README.md").read_text(encoding="utf-8")
        example = text.split("## The titles file", 1)[1].split("```")[3].lstrip("\n")
        self.assertEqual(br.parse_titles(example, "README.md", 2),
                         [(1, "A made up talk about binder design"), (2, "Binder design succeeds for 12 of 15 targets")])

    def test_the_evidence_readme_follows_the_writing_rules(self):
        self.assertEqual(prose_problems((VERIFICATION / "evidence" / "README.md").read_text(encoding="utf-8")), [])

    def test_the_evidence_readme_names_every_file_that_build_results_reads(self):
        text = (VERIFICATION / "evidence" / "README.md").read_text(encoding="utf-8")
        for variant in br.VARIANTS:
            for number in br.RUNS:
                self.assertIn("{}-{}.score.txt".format(variant, number), text)

    def test_the_grammar_example_in_the_readme_parses(self):
        text = (VERIFICATION / "evidence" / "README.md").read_text(encoding="utf-8")
        example = text.split("## An example", 1)[1].split("```")[1].lstrip("\n")
        score = br.parse_score(example, "README.md")
        self.assertEqual((score.errors, score.warnings, len(score.ghost)), (0, 2, 2))


if __name__ == "__main__":
    unittest.main()
