"""Tests for scripts/render_check.py, the optional render check, and for its wiring into `design_lint.py --render`.

Most tests use a fake soffice and a fake pdftotext. These are shell scripts in a temporary folder at the
front of PATH, so the tests run on every machine. One class renders decks with the real LibreOffice.
That class skips when soffice or pdftotext is missing, and when soffice is installed but cannot render.
"""
import contextlib
import errno
import html
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from pptx.shapes.group import GroupShape

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
for folder in (SCRIPTS_DIR, Path(__file__).resolve().parent):
    if str(folder) not in sys.path:
        sys.path.insert(0, str(folder))

import design_lint as dl  # noqa: E402
import render_check as rc  # noqa: E402
import style as style_mod  # noqa: E402
from lint_helpers import (  # noqa: E402
    BODY,
    SCRIPT,
    add_box,
    add_chart,
    add_notes,
    add_slide,
    build_all_layouts,
    clean_slide,
    new_deck,
    set_run,
)

SYSTEM_PATH = "/usr/bin:/bin"


def bbox(*pages):
    """Return the output of `pdftotext -bbox` for pages that are lists of (text, height) pairs."""
    rows = ['<?xml version="1.0"?>', "<html><body><doc>"]
    for page in pages:
        rows.append('  <page width="960.000000" height="540.000000">')
        for index, (text, height) in enumerate(page):
            rows.append('    <word xMin="{:.6f}" yMin="100.000000" xMax="{:.6f}" yMax="{:.6f}">{}</word>'.format(
                10.0 * index, 10.0 * index + 8, 100.0 + height, html.escape(text, quote=False)))
        rows.append("  </page>")
    rows.append("</doc></body></html>")
    return "\n".join(rows) + "\n"


def calibration_of(factors):
    """Return the canned output for the calibration render. `factors` maps a font to (word height) / 40.

    The pages follow the order of the module: the font of the theme (the key None) first, then the others by name.
    """
    names = sorted(name for name in factors if name)
    if None in factors:
        names.insert(0, None)
    return bbox(*[[("Sample", 40.0 * factors[name])] for name in names])


AVENIR = {"Avenir Light": 1.5}  # the font of every box that lint_helpers builds, and a height factor for it
AVENIR_AND_CALIBRI = {"Avenir Light": 1.5, "Calibri": 1.0}  # a deck with a table, or a box with no font of its own


def page_of(text, height):
    """Return the (word, height) pairs of a text, all at one height."""
    return [(word, height) for word in text.split()]


class FakeTools(unittest.TestCase):
    """A temporary folder with a fake soffice and a fake pdftotext at the front of PATH."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.bin = self.tmp / "bin"
        self.log = self.tmp / "log"
        self.bin.mkdir()
        self.log.mkdir()
        patcher = mock.patch.dict(os.environ, {"PATH": str(self.bin) + os.pathsep + SYSTEM_PATH})
        patcher.start()
        self.addCleanup(patcher.stop)

    def tool(self, name, body):
        path = self.bin / name
        path.write_text("#!/bin/sh\n" + body + "\n")
        path.chmod(0o755)
        return path

    def soffice(self, body=None):
        """Install a fake soffice. It records its arguments. By default it writes an empty PDF named after the deck."""
        if body is None:
            body = ': > "$7/$name.pdf"'
        self.tool("soffice", 'echo "$@" >> "{log}/soffice.args"\necho "$7" >> "{log}/outdirs"\n'
                  'name=$(basename "$8" .pptx)\n{body}'.format(log=self.log, body=body))

    def pdftotext(self, deck="", calibration="", body=None):
        """Install a fake pdftotext. It copies a canned text to its third argument."""
        (self.log / "deck.html").write_text(deck)
        (self.log / "calibration.html").write_text(calibration)
        if body is None:
            body = ('case "$2" in\n  */calibration.pdf) cat "{log}/calibration.html" > "$3" ;;\n'
                    '  *) cat "{log}/deck.html" > "$3" ;;\nesac').format(log=self.log)
        self.tool("pdftotext", body)

    def outdirs(self):
        path = self.log / "outdirs"
        return path.read_text().split() if path.exists() else []


class Availability(FakeTools):
    def test_nothing_is_available_when_path_is_empty(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        with mock.patch.dict(os.environ, {"PATH": str(empty)}):
            self.assertIs(rc.available(), False)

    def test_both_tools_make_it_available(self):
        self.soffice()
        self.pdftotext()
        self.assertIs(rc.available(), True)

    def test_one_tool_is_not_enough(self):
        self.soffice()
        with mock.patch.dict(os.environ, {"PATH": str(self.bin)}):
            self.assertIs(rc.available(), False)
        (self.bin / "soffice").unlink()
        self.pdftotext()
        with mock.patch.dict(os.environ, {"PATH": str(self.bin)}):
            self.assertIs(rc.available(), False)


class Words(unittest.TestCase):
    """The text of the deck and the text of the page must compare equal when they differ only in form."""

    def test_case_and_edge_punctuation_do_not_matter(self):
        self.assertEqual(rc._split("Binder,"), ["binder"])
        self.assertEqual(rc._split("(BINDER)"), ["binder"])
        self.assertEqual(rc._split("\u201cbinder\u201d:"), ["binder"])

    def test_a_ligature_equals_its_letters(self):
        self.assertEqual(rc._split("\ufb01nd"), ["find"])
        self.assertEqual(rc._split("o\ufb03ce"), ["office"])

    def test_a_soft_hyphen_is_dropped(self):
        self.assertEqual(rc._split("co\u00adoperate"), ["cooperate"])

    def test_a_non_breaking_space_separates_two_words(self):
        self.assertEqual(rc._split("two\u00a0words"), ["two", "words"])

    def test_a_hyphenated_word_splits_at_each_hyphen(self):
        self.assertEqual(rc._split("state-of-the-art"), ["state", "of", "the", "art"])
        self.assertEqual(rc._split("5\u201310 mid\u2014way"), ["5", "10", "mid", "way"])

    def test_compatibility_forms_equal_their_plain_forms(self):
        self.assertEqual(rc._split("\uff22inder"), ["binder"])  # a full-width letter
        self.assertEqual(rc._split("CO\u00b2"), ["co2"])  # a superscript digit
        self.assertEqual(rc._split("cafe\u0301"), ["caf\u00e9"])  # a letter and a combining accent

    def test_a_micro_sign_equals_the_greek_mu(self):
        self.assertEqual(rc._split("5\u00b5M"), rc._split("5\u03bcM"))

    def test_the_deck_side_leaves_out_a_word_without_a_letter(self):
        self.assertEqual(rc._deck_tokens("2026"), [])
        self.assertEqual(rc._deck_tokens("-"), [])
        self.assertEqual(rc._deck_tokens("12-15"), [])
        self.assertEqual(rc._deck_tokens("CO2"), ["co2"])
        self.assertEqual(rc._deck_tokens("p<0.05"), ["p"])

    def test_the_page_side_keeps_a_word_of_digits(self):
        self.assertEqual(rc._split("2026"), ["2026"])

    def test_the_page_holds_each_word_and_the_joins_of_its_neighbors(self):
        def tokens(*words):
            return rc._page_tokens([(10.0, word) for word in words])

        self.assertLessEqual({"co", "operate", "cooperate"}, tokens("co-", "operate"))
        self.assertIn("co2", tokens("CO", "2"))
        self.assertIn("h2o", tokens("H", "2", "O"))  # a subscript splits a word in three
        self.assertIn("efficient", tokens("e", "\ufb03", "cient"))  # a font change splits a word in three
        self.assertIn("abcd", tokens("a", "b", "c", "d"))
        self.assertNotIn("abcde", tokens("a", "b", "c", "d", "e"))
        self.assertNotIn("ca", tokens("a", "b", "c"))  # the joins keep the order of the page


class Pages(unittest.TestCase):
    def test_each_page_gives_the_height_and_text_of_its_words(self):
        text = bbox([("Binder", 30.0), ("R&D", 12.5)], [], [("Next", 24.0)])
        pages = rc._pages(text)
        self.assertEqual(len(pages), 3)
        self.assertEqual(pages[0][0][1], "Binder")
        self.assertAlmostEqual(pages[0][0][0], 30.0, places=4)
        self.assertEqual(pages[0][1][1], "R&D")  # the markup is unescaped
        self.assertEqual(pages[1], [])
        self.assertEqual(pages[2][0][1], "Next")

    def test_a_word_beyond_the_page_edge_has_a_negative_coordinate(self):
        text = ('<doc><page width="10" height="10"><word xMin="-5.5" yMin="-3.250000" xMax="4" yMax="6.750000">Edge'
                '</word></page></doc>')
        self.assertAlmostEqual(rc._pages(text)[0][0][0], 10.0, places=4)

    def test_text_with_no_page_is_a_failure(self):
        for text in ("", "garbage \x00\x01 not a page", "<html><body>no pages</body></html>"):
            with self.subTest(text=text):
                with self.assertRaises(rc._Failure):
                    rc._pages(text)


def alive(pid):
    """Return True when a process with this id runs. A zombie does not run."""
    try:
        with open("/proc/{}/stat".format(pid)) as handle:
            return handle.read().rsplit(")", 1)[1].split()[0] != "Z"
    except (IOError, OSError):
        return False


def wait_until_gone(test, pid, name, seconds=10):
    """Fail the test when the process stays alive for `seconds`.

    SIGKILL takes effect when the dying process next gets the CPU. On a loaded machine a check
    right after the kill can see a process that is about to end, so the check polls.
    """
    deadline = time.time() + seconds
    while alive(pid) and time.time() < deadline:
        time.sleep(0.01)
    test.assertFalse(alive(pid), "{} (process {}) must be gone".format(name, pid))


class DeckCase(FakeTools):
    """Helpers that build a deck, install the fake tools and call render_findings()."""

    def save(self, prs, name="deck.pptx"):
        path = self.tmp / name
        prs.save(str(path))
        return path

    def one_slide(self, title="Binder design succeeds", body="Twelve designs fold", **font):
        prs = new_deck()
        slide = add_slide(prs, title)
        add_box(slide, body, **font)
        return self.save(prs)

    def render(self, path, deck_pages, factors=AVENIR, min_pt=12, **options):
        """Run the check with canned pages. `factors` maps each font of the deck to the height of a 40 pt word / 40."""
        self.soffice()
        self.pdftotext(deck=bbox(*deck_pages), calibration=calibration_of(factors))
        return rc.render_findings(path, min_pt, **options)

    def rows(self, findings, rule):
        return [f for f in findings if f.rule == rule]


class RenderFailures(DeckCase):
    @contextlib.contextmanager
    def timeout_clock_after_files(self, tool, *names):
        """Start the timeout clock of a fake `tool` only after it has written the files `names`.

        A fake tool is a shell script. On a loaded machine it can need seconds to reach its first
        line, and a short timeout then fires before the tool wrote anything. This context patches
        Popen.wait. The patch polls for the files first and then calls the real wait. The other
        tool gets a limit of 60 s, so the short timeout cannot fire in it by mistake.
        """
        real_wait = subprocess.Popen.wait

        def wait(process, timeout=None):
            if timeout is None:
                return real_wait(process)
            if os.path.basename(process.args[0]) != tool:
                return real_wait(process, 60)
            deadline = time.time() + 60
            while not all(self.written(name) for name in names):
                if time.time() > deadline:
                    self.fail("the fake {} wrote no file {}".format(tool, names))
                time.sleep(0.01)
            return real_wait(process, timeout)

        with mock.patch.object(subprocess.Popen, "wait", wait):
            yield

    def written(self, name):
        """Return True when a fake tool has written the whole line of a log file."""
        try:
            return (self.log / name).read_text().endswith("\n")
        except (IOError, OSError):
            return False

    def assert_one_failure(self, findings, reason):
        self.assertEqual(len(findings), 1, findings)
        finding = findings[0]
        self.assertEqual(tuple(finding[:4]), (0, "render-check", "warn", "T3"))
        self.assertTrue(finding.message.startswith("render check failed: "), finding.message)
        self.assertIn(reason, finding.message)
        for outdir in self.outdirs():
            self.assertFalse(os.path.exists(outdir), "the temporary folder must be gone")

    def test_a_timeout_gives_one_deck_level_warning(self):
        self.soffice('echo $$ > "{}/pid"\nexec sleep 30'.format(self.log))
        self.pdftotext()
        started = time.time()
        with self.timeout_clock_after_files("soffice", "pid"):
            findings = rc.render_findings(self.one_slide(), 12, timeout=1)
        self.assertLess(time.time() - started, 15)
        self.assert_one_failure(findings, "soffice did not finish in 1 s")
        wait_until_gone(self, int((self.log / "pid").read_text()), "soffice")

    @unittest.skipUnless(os.path.exists("/proc/self/stat"), "the check of a running process reads /proc")
    def test_a_timeout_kills_the_children_of_soffice_too(self):
        self.soffice('echo $$ > "{0}/pid"\nsleep 30 &\necho $! > "{0}/child"\nwait'.format(self.log))
        self.pdftotext()
        with self.timeout_clock_after_files("soffice", "pid", "child"):
            findings = rc.render_findings(self.one_slide(), 12, timeout=1)
        self.assert_one_failure(findings, "did not finish")
        for name in ("pid", "child"):
            wait_until_gone(self, int((self.log / name).read_text()), name)

    def test_a_timeout_applies_to_pdftotext_too(self):
        self.soffice()
        self.pdftotext(body='echo $$ > "{}/pid"\nexec sleep 30'.format(self.log))
        with self.timeout_clock_after_files("pdftotext", "pid"):
            findings = rc.render_findings(self.one_slide(), 12, timeout=1)
        self.assert_one_failure(findings, "pdftotext did not finish in 1 s")
        wait_until_gone(self, int((self.log / "pid").read_text()), "pdftotext")

    @unittest.skipUnless(os.path.exists("/proc/self/stat"), "the check of a running process reads /proc")
    def test_an_interrupt_kills_the_process_and_removes_the_folder(self):
        self.soffice("exec sleep 30")
        self.pdftotext()
        real_wait = subprocess.Popen.wait
        calls = []

        def interrupted_wait(process, timeout=None):
            if not calls:
                calls.append(process.pid)
                raise KeyboardInterrupt
            return real_wait(process, timeout)

        made = []
        real_mkdtemp = tempfile.mkdtemp

        def spy(*args, **options):
            made.append(real_mkdtemp(*args, **options))
            return made[-1]

        with mock.patch.object(subprocess.Popen, "wait", interrupted_wait), mock.patch.object(rc.tempfile, "mkdtemp", spy):
            with self.assertRaises(KeyboardInterrupt):
                rc.render_findings(self.one_slide(), 12)
        self.assertFalse(alive(calls[0]), "the process must be gone")
        self.assertEqual(len(made), 1)
        self.assertFalse(os.path.exists(made[0]), "the temporary folder must be gone")

    def test_a_file_error_gives_one_warning_and_removes_the_folder(self):
        self.soffice()
        self.pdftotext()
        full = OSError(errno.ENOSPC, "No space left on device")
        made = []
        real_mkdtemp = tempfile.mkdtemp

        def spy(*args, **options):
            made.append(real_mkdtemp(*args, **options))
            return made[-1]

        with mock.patch.object(rc.tempfile, "mkdtemp", side_effect=full):
            findings = rc.render_findings(self.one_slide(), 12)
        self.assert_one_failure(findings, "file error: [Errno 28] No space left on device")
        with mock.patch.object(rc.tempfile, "mkdtemp", spy), mock.patch.object(rc.shutil, "copyfile", side_effect=full):
            findings = rc.render_findings(self.one_slide(), 12)
        self.assert_one_failure(findings, "file error: [Errno 28] No space left on device")
        self.assertEqual(len(made), 1)
        self.assertFalse(os.path.exists(made[0]), "the temporary folder must be gone")
        self.assertEqual(self.outdirs(), [], "no conversion starts")

    def test_the_default_timeout_is_120_seconds(self):
        self.assertEqual(rc.TIMEOUT_SECONDS, 120)

    def test_a_nonzero_exit_gives_one_warning_with_the_code_and_the_message(self):
        self.soffice('echo "boom happened" >&2\nexit 1')
        self.pdftotext()
        findings = rc.render_findings(self.one_slide(), 12)
        self.assert_one_failure(findings, "soffice exited with code 1")
        self.assertIn("boom happened", findings[0].message)

    def test_an_exit_with_no_pdf_gives_one_warning(self):
        self.soffice("exit 0")
        self.pdftotext()
        self.assert_one_failure(rc.render_findings(self.one_slide(), 12), "soffice wrote no PDF")

    def test_a_pdftotext_that_fails_gives_one_warning(self):
        self.soffice()
        self.pdftotext(body="exit 2")
        self.assert_one_failure(rc.render_findings(self.one_slide(), 12), "pdftotext exited with code 2")

    def test_a_pdftotext_that_writes_no_file_gives_one_warning(self):
        self.soffice()
        self.pdftotext(body="exit 0")
        self.assert_one_failure(rc.render_findings(self.one_slide(), 12), "pdftotext wrote no text file")

    def test_a_pdftotext_that_prints_garbage_gives_one_warning(self):
        self.soffice()
        self.pdftotext(body='echo "garbage, not a page" > "$3"')
        self.assert_one_failure(rc.render_findings(self.one_slide(), 12), "the output of pdftotext has no page")

    def test_a_tool_that_cannot_start_gives_one_warning(self):
        path = self.bin / "soffice"
        path.write_text("#!/no/such/interpreter\n")
        path.chmod(0o755)
        self.pdftotext()
        self.assert_one_failure(rc.render_findings(self.one_slide(), 12), "cannot start soffice")

    def test_a_deck_that_cannot_be_read_gives_one_warning(self):
        self.soffice()
        self.pdftotext()
        broken = self.tmp / "broken.pptx"
        broken.write_text("this is not a zip file")
        self.assert_one_failure(rc.render_findings(broken, 12), "cannot read the deck")
        self.assert_one_failure(rc.render_findings(self.tmp / "missing.pptx", 12), "cannot read the deck")
        self.assertEqual(self.outdirs(), [], "a deck that cannot be read starts no conversion")

    def test_a_page_count_that_differs_from_the_slide_count_gives_one_warning(self):
        findings = self.render(self.one_slide(), [page_of("Binder design succeeds", 42.0), page_of("Extra", 20.0)])
        self.assert_one_failure(findings, "the PDF has 2 pages for 1 visible slide")

    def test_a_missing_calibration_word_gives_one_warning(self):
        self.soffice()
        self.pdftotext(deck=bbox(page_of("Binder design succeeds Twelve designs fold", 36.0)),
                       calibration=bbox([("Other", 60.0)]))
        self.assert_one_failure(rc.render_findings(self.one_slide(), 12), "cannot measure the font")

    def test_a_calibration_with_fewer_pages_than_fonts_gives_one_warning(self):
        prs = new_deck()
        slide = add_slide(prs, "Binder design succeeds")
        add_box(slide, "Twelve designs fold", family="Calibri")  # two fonts: Avenir Light and Calibri
        self.soffice()
        self.pdftotext(deck=bbox(page_of("Binder design succeeds Twelve designs fold", 36.0)),
                       calibration=bbox([("Sample", 60.0)]))
        self.assert_one_failure(rc.render_findings(self.save(prs), 12), "cannot measure the font")

    def test_a_height_of_zero_in_the_calibration_gives_one_warning(self):
        self.soffice()
        self.pdftotext(deck=bbox(page_of("Binder design succeeds Twelve designs fold", 36.0)),
                       calibration=bbox([("Sample", 0.0)]))
        self.assert_one_failure(rc.render_findings(self.one_slide(), 12), "cannot measure the font")

    def test_a_failed_calibration_keeps_the_missing_text_rows(self):
        # The word compare needs no calibration, so its rows stay. The deck-level row comes first.
        self.soffice()
        self.pdftotext(deck=bbox(page_of("Binder design succeeds Twelve fold", 36.0)),
                       calibration=bbox([("Other", 60.0)]))
        findings = rc.render_findings(self.one_slide(), 12)
        self.assertEqual([(f.slide, f.rule) for f in findings], [(0, "render-check"), (1, "render-missing-text")])
        self.assertIn("cannot measure the font", findings[0].message)
        self.assertIn("designs", findings[1].message)
        with mock.patch.object(rc, "_factors", side_effect=OSError(errno.ENOSPC, "No space left on device")):
            findings = rc.render_findings(self.one_slide(), 12)
        self.assertEqual([(f.slide, f.rule) for f in findings], [(0, "render-check"), (1, "render-missing-text")])
        self.assertIn("file error", findings[0].message)

    def test_every_path_removes_the_temporary_folder(self):
        path = self.one_slide()
        words = page_of("Binder design succeeds Twelve designs fold", 36.0)
        variants = [("exit 1", None), ("exit 0", None), (None, "exit 2"), (None, 'echo junk > "$3"'), (None, None)]
        for soffice, pdftotext in variants:
            with self.subTest(soffice=soffice, pdftotext=pdftotext):
                if (self.log / "outdirs").exists():
                    (self.log / "outdirs").unlink()
                self.soffice(soffice)
                self.pdftotext(deck=bbox(words), calibration=bbox([("Sample", 60.0)]),
                               body=pdftotext)
                rc.render_findings(path, 12)
                dirs = self.outdirs()
                self.assertTrue(dirs)
                for outdir in dirs:
                    self.assertFalse(os.path.exists(outdir))

    def test_a_bad_floor_is_an_error_of_the_caller(self):
        path = self.one_slide()
        for bad in (0, -1, float("nan"), float("inf"), "12", None, True):
            with self.subTest(min_pt=bad):
                with self.assertRaises(ValueError):
                    rc.render_findings(path, bad)

    def test_the_run_never_touches_the_profile_of_the_user(self):
        words = page_of("Binder design succeeds Twelve designs fold", 36.0)
        self.render(self.one_slide(), [words])
        lines = (self.log / "soffice.args").read_text().splitlines()
        self.assertEqual(len(lines), 2, "one conversion for the deck, one for the font calibration")
        for line in lines:
            arguments = line.split()
            self.assertTrue(arguments[0].startswith("-env:UserInstallation=file:///"), arguments[0])
            profile = arguments[0].split("file://", 1)[1]
            outdir = arguments[6]
            self.assertTrue(profile.startswith(outdir + "/"), "the profile lies in the temporary folder")
            self.assertNotIn(os.path.expanduser("~/.config"), line)
            self.assertEqual(arguments[1:6], ["--headless", "--norestore", "--convert-to", "pdf", "--outdir"])
        self.assertEqual(os.path.basename(lines[0].split()[7]), "deck.pptx")


class RenderFont(DeckCase):
    """Heights come from the fake pdftotext. Factor 1.5 is the font of the deck, so 15 pt tall is 10 pt."""

    def setUp(self):
        super().setUp()
        self.path = self.one_slide()
        self.title = page_of("Binder design succeeds", 42.0)  # 28 pt at factor 1.5

    def check(self, **heights):
        """Render with the body words Twelve, designs and fold at the given heights. Return the render-font rows."""
        body = [(word, heights.get(word, 36.0)) for word in ("Twelve", "designs", "fold")]
        return self.rows(self.render(self.path, [self.title + body]), "render-font")

    def test_a_word_below_the_floor_gives_a_warning_that_names_it(self):
        (finding,) = self.check(designs=15.0)
        self.assertEqual(tuple(finding[:4]), (1, "render-font", "warn", "T2"))
        self.assertIn("10.0 pt", finding.message)
        self.assertIn("'designs'", finding.message)
        self.assertIn("12 pt", finding.message)
        self.assertIn("1 rendered word ", finding.message)

    def test_the_message_counts_the_words_and_names_the_smallest(self):
        (finding,) = self.check(designs=15.0, fold=13.5)
        self.assertIn("2 rendered words", finding.message)
        self.assertIn("9.0 pt", finding.message)
        self.assertIn("'fold'", finding.message)
        self.assertNotIn("'designs'", finding.message)

    def test_a_deck_with_the_right_sizes_gives_no_warning(self):
        self.assertEqual(self.check(), [])

    def test_the_floor_has_a_one_percent_margin_for_the_rounding_of_the_renderer(self):
        self.assertEqual(self.check(designs=18.0), [])  # exactly 12 pt
        self.assertEqual(self.check(designs=17.9), [])  # 11.93 pt
        self.assertEqual(len(self.check(designs=17.0)), 1)  # 11.33 pt

    def test_the_floor_is_the_argument(self):
        pages = [self.title + [("Twelve", 36.0), ("designs", 15.0), ("fold", 36.0)]]
        self.assertEqual(self.rows(self.render(self.path, pages, min_pt=8), "render-font"), [])
        self.assertEqual(len(self.rows(self.render(self.path, pages, min_pt=10.5), "render-font")), 1)

    def test_one_warning_per_slide(self):
        prs = new_deck()
        for title, body in (("Binder design succeeds", "Twelve designs fold"), ("Controls stay silent", "Zero controls bind")):
            add_box(add_slide(prs, title), body)
        pages = [page_of("Binder design succeeds Twelve designs fold", 15.0),
                 page_of("Controls stay silent Zero controls bind", 15.0)]
        found = self.rows(self.render(self.save(prs), pages), "render-font")
        self.assertEqual([f.slide for f in found], [1, 2])
        self.assertIn("6 rendered words", found[0].message)

    def test_the_font_of_a_word_sets_its_factor(self):
        prs = new_deck()
        slide = add_slide(prs, "Binder design succeeds")
        add_box(slide, "Alpha", name="One", top=2.0)  # Avenir Light, factor 1.5
        add_box(slide, "Beta", name="Two", top=3.0, family="Calibri")  # factor 1.0
        pages = [self.title + [("Alpha", 15.0), ("Beta", 15.0)]]
        # The pages of the calibration: the default font, then Avenir Light, then Calibri.
        (finding,) = self.rows(self.render(self.save(prs), pages, factors=AVENIR_AND_CALIBRI), "render-font")
        self.assertIn("'Alpha'", finding.message)
        self.assertIn("1 rendered word ", finding.message)

    def test_a_word_that_the_deck_does_not_hold_takes_the_smallest_factor_of_the_fonts_of_the_deck(self):
        # The word 999 stands for a label of a chart. The deck uses Avenir Light (1.5) and Calibri (1.0).
        prs = new_deck()
        slide = add_slide(prs, "Binder design succeeds")
        add_box(slide, "Twelve designs fold", family="Calibri")
        path = self.save(prs)
        pages = [self.title + [("Twelve", 24.0), ("designs", 24.0), ("fold", 24.0), ("999", 11.5)]]
        (finding,) = self.rows(self.render(path, pages, factors=AVENIR_AND_CALIBRI), "render-font")
        self.assertIn("'999'", finding.message)
        self.assertIn("11.5 pt", finding.message)
        pages = [self.title + [("Twelve", 24.0), ("designs", 24.0), ("fold", 24.0), ("999", 13.0)]]
        self.assertEqual(self.rows(self.render(path, pages, factors=AVENIR_AND_CALIBRI), "render-font"), [])

    def test_the_label_of_a_chart_takes_the_only_font_of_the_deck(self):
        # A deck with one font, Avenir Light (1.5): a 9 pt label is 13.5 high and must count as 9 pt.
        pages = [self.title + [("Twelve", 36.0), ("designs", 36.0), ("fold", 36.0), ("999", 13.5)]]
        (finding,) = self.rows(self.render(self.path, pages), "render-font")
        self.assertIn("9.0 pt (the word '999')", finding.message)

    def test_the_font_of_the_theme_counts_when_a_run_resolves_to_no_font(self):
        prs = new_deck()
        slide = add_slide(prs, "Binder design succeeds")
        add_box(slide, "Twelve designs fold")
        real = rc._family

        def family(prs_, slide_, shape, paragraph, run):
            return None if run.text == "Twelve designs fold" else real(prs_, slide_, shape, paragraph, run)

        pages = [self.title + [("Twelve", 24.0), ("designs", 24.0), ("fold", 24.0), ("999", 11.5)]]
        with mock.patch.object(rc, "_family", family):
            # The fonts are Avenir Light (1.5) and the theme font (1.0), so 999 takes 1.0.
            (finding,) = self.rows(self.render(self.save(prs), pages, factors={None: 1.0, "Avenir Light": 1.5}),
                                   "render-font")
        self.assertIn("11.5 pt (the word '999')", finding.message)

    def test_a_deck_with_no_text_run_measures_with_the_font_of_the_theme(self):
        prs = new_deck()
        add_slide(prs, None)
        pages = [[("a", 14.0), ("b", 10.0)]]
        (finding,) = self.render(self.save(prs), pages, factors={None: 1.0})
        self.assertEqual((finding.rule, finding.slide), ("render-font", 1))
        self.assertIn("10.0 pt (the word 'b')", finding.message)
        self.assertIn("1 rendered word ", finding.message)

    def test_a_word_with_a_character_above_latin_1_is_not_measured(self):
        # LibreOffice draws a Greek letter or a rare symbol in another font, with another height factor.
        path = self.one_slide(body="Twelve designs fold \u03b1 a\u2011b \u00b5M")
        pages = [self.title + [("Twelve", 36.0), ("designs", 36.0), ("fold", 36.0), ("\u03b1", 13.0), ("a\u2011b", 13.0)]]
        self.assertEqual(self.rows(self.render(path, pages), "render-font"), [])
        pages = [self.title + [("Twelve", 36.0), ("designs", 36.0), ("fold", 36.0), ("\u00b5M", 15.0)]]
        (finding,) = self.rows(self.render(path, pages), "render-font")
        self.assertIn("'\u00b5M'", finding.message)

    def test_a_raised_or_lowered_run_is_not_measured(self):
        prs = new_deck()
        slide = add_slide(prs, "Binder design succeeds")
        add_box(slide, "Hole", name="Other", top=3.0)
        box = add_box(slide, "H")
        for text, shift in (("2", "-25000"), ("O", None)):
            run = box.text_frame.paragraphs[0].add_run()
            run.text = text
            set_run(run, size=24)
            if shift:
                run._r.get_or_add_rPr().set("baseline", shift)
        path = self.save(prs)
        # Both calibrations give 1.5, so the word "2" takes the factor 1.5 and would count as 10 pt without the rule.
        pages = [self.title + [("H", 36.0), ("2", 15.0), ("O", 36.0)]]
        self.assertEqual(self.rows(self.render(path, pages), "render-font"), [])
        pages = [self.title + [("H", 36.0), ("2", 15.0), ("O", 36.0), ("Hole", 15.0)]]  # a word of normal text is measured
        (finding,) = self.rows(self.render(path, pages), "render-font")
        self.assertIn("'Hole'", finding.message)

    def test_a_word_with_no_letter_or_digit_is_not_checked(self):
        pages = [self.title + [("Twelve", 36.0), ("designs", 36.0), ("fold", 36.0), ("\u2022", 3.0), ("-", 2.0)]]
        self.assertEqual(self.rows(self.render(self.path, pages), "render-font"), [])


class RenderMissingText(DeckCase):
    def missing(self, body, page_words, title="Binder design succeeds", factors=AVENIR):
        path = self.one_slide(title=title, body=body)
        pages = [page_of(title, 42.0) + [(word, 36.0) for word in page_words]]
        return self.rows(self.render(path, pages, factors=factors), "render-missing-text")

    def test_a_word_that_the_page_lacks_gives_a_warning_that_names_it(self):
        (finding,) = self.missing("Twelve designs fold", ["Twelve", "fold"])
        self.assertEqual(tuple(finding[:4]), (1, "render-missing-text", "warn", "T3"))
        self.assertIn("1 word ", finding.message)
        self.assertIn("designs", finding.message)

    def test_the_message_names_three_words_and_gives_the_count(self):
        (finding,) = self.missing("alpha beta gamma delta epsilon", [])
        self.assertIn("5 words", finding.message)
        self.assertIn("alpha, beta, gamma", finding.message)
        self.assertNotIn("delta", finding.message)

    def test_a_word_counts_once_however_often_it_appears(self):
        (finding,) = self.missing("alpha Alpha alpha, beta", ["beta"])
        self.assertIn("1 word ", finding.message)

    def test_a_page_with_every_word_gives_no_warning(self):
        self.assertEqual(self.missing("Twelve designs fold", ["Twelve", "designs", "fold"]), [])

    def test_the_forms_that_a_renderer_changes_give_no_warning(self):
        body = "find co\u00adoperate two\u00a0words state-of-the-art BINDER"
        shown = ["\ufb01nd", "co-", "operate", "two", "words", "state-of-", "the-art", "binder"]
        self.assertEqual(self.missing(body, shown), [])
        self.assertEqual(self.missing("co\u00adoperate", ["cooperate"]), [])

    def test_a_word_in_another_case_or_with_other_punctuation_gives_no_warning(self):
        self.assertEqual(self.missing("Binder, (designs) \u201cfold\u201d!", ["BINDER", "designs", "fold"]), [])

    def test_a_word_of_digits_or_punctuation_is_not_compared(self):
        self.assertEqual(self.missing("2026 - 12-15 % \u00d7 4", ["x"]), [])

    def test_a_word_that_a_font_change_or_a_shift_splits_gives_no_warning(self):
        self.assertEqual(self.missing("efficient H2O", ["e", "\ufb03", "cient", "H", "2", "O"]), [])

    def test_a_raised_or_lowered_run_is_left_out_of_the_words(self):
        # A renderer can put a subscript in any place of the reading order, so the check ignores raised and lowered text.
        prs = new_deck()
        box = add_box(add_slide(prs, "Binder design succeeds"), "Na")
        for text, shift in (("2", "-25000"), ("SO", None), ("4", "-25000")):
            run = box.text_frame.paragraphs[0].add_run()
            run.text = text
            if shift:
                run._r.get_or_add_rPr().set("baseline", shift)
        path = self.save(prs)
        pages = [page_of("Binder design succeeds", 42.0) + [("Na", 36.0), ("SO", 36.0)]]
        self.assertEqual(self.rows(self.render(path, pages, factors=AVENIR_AND_CALIBRI), "render-missing-text"), [])
        pages = [page_of("Binder design succeeds", 42.0) + [("Na", 36.0)]]
        (finding,) = self.rows(self.render(path, pages, factors=AVENIR_AND_CALIBRI), "render-missing-text")
        self.assertIn("SO", finding.message)
        self.assertIn("1 word ", finding.message)

    def test_letter_spaced_text_that_the_renderer_splits_in_many_parts_gives_no_warning(self):
        # pdftotext cuts a word of widely spaced letters into single letters, or into parts of 1 to 3 letters.
        self.assertEqual(self.missing("CONCLUSIONS", list("CONCLUSIONS")), [])
        self.assertEqual(self.missing("FOXTROT SUMMARY", list("FOXTROTSUMMA") + ["RY"]), [])
        self.assertEqual(self.missing("FOXTROT SUMMARY", ["FOX", "T", "ROT", "S", "U", "M", "M", "A", "RY"]), [])
        self.assertEqual(self.missing("state-of-the-art", list("STATE") + ["-", "O", "F", "-"] + list("THEART")), [])

    def test_a_word_of_letter_spaced_text_that_the_page_lacks_is_still_reported(self):
        (finding,) = self.missing("CONCLUSIONS SUMMARY", list("CONCLUSIONS"))
        self.assertIn("1 word ", finding.message)
        self.assertIn("SUMMARY", finding.message)

    def test_a_right_to_left_word_is_not_compared(self):
        # pdftotext gives the letters of a right-to-left word in reverse order.
        hebrew, arabic = "\u05e9\u05dc\u05d5\u05dd", "\u0645\u0631\u062d\u0628\u0627"
        body = "Twelve {} {} folded".format(hebrew, arabic)
        self.assertEqual(self.missing(body, ["Twelve", hebrew[::-1], arabic[::-1], "folded"]), [])
        (finding,) = self.missing(body, ["folded"])  # Twelve is missing, and the two other words never count
        self.assertIn("1 word ", finding.message)
        self.assertIn("Twelve", finding.message)
        self.assertNotIn(hebrew, finding.message)
        self.assertNotIn(arabic, finding.message)

    def test_a_word_with_one_right_to_left_letter_is_not_compared(self):
        self.assertEqual(self.missing("ab\u05e9cd", ["x"]), [])
        self.assertEqual(len(self.missing("abscd", ["x"])), 1)

    def test_a_run_of_parts_with_one_long_part_still_matches(self):
        self.assertEqual(self.missing("CONCLUSIONS", ["CONCLUS", "I", "O", "N", "S"]), [])

    def test_a_word_is_not_found_inside_a_longer_page_word_or_across_two_page_words(self):
        # The page holds "design" and "succeeds", whose letters in a row hold "designs". A search for a
        # part of the page text would find "designs" there and hide the missing word.
        for word, page_words in (("designs", ["design", "succeeds"]), ("fold", ["unfolded"]), ("the", ["other"]),
                                 ("tion", ["conclusions"]), ("conclusion", ["conclusions"])):
            with self.subTest(word=word):
                path = self.one_slide(title="Binder design succeeds", body=word)
                pages = [page_of("Binder design succeeds", 42.0) + [(w, 36.0) for w in page_words]]
                (finding,) = self.rows(self.render(path, pages), "render-missing-text")
                self.assertRegex(finding.message, r"^1 word of the deck is not in the rendered page \(for example: {}\)".format(word))

    def test_a_word_split_over_two_runs_matches_its_page_word(self):
        prs = new_deck()
        box = add_box(add_slide(prs, "Binder design succeeds"), "CO")
        box.text_frame.paragraphs[0].add_run().text = "2"
        pages = [page_of("Binder design succeeds", 42.0) + [("CO2", 36.0)]]
        self.assertEqual(self.rows(self.render(self.save(prs), pages), "render-missing-text"), [])
        pages = [page_of("Binder design succeeds", 42.0) + [("CO", 36.0), ("2", 36.0)]]
        self.assertEqual(self.rows(self.render(self.save(prs), pages), "render-missing-text"), [])

    def test_a_field_is_not_compared(self):
        prs = new_deck()
        box = add_box(add_slide(prs, "Binder design succeeds"), "Page")
        field = box.text_frame.paragraphs[0]._p.makeelement("{http://schemas.openxmlformats.org/drawingml/2006/main}fld",
                                                           {"id": "{B6F15528-21DE-4FAA-801E-634DDDAF4B2B}", "type": "datetime"})
        text = field.makeelement("{http://schemas.openxmlformats.org/drawingml/2006/main}t")
        text.text = "Tuesday"
        field.append(text)
        box.text_frame.paragraphs[0]._p.append(field)
        pages = [page_of("Binder design succeeds Page", 36.0)]
        self.assertEqual(self.rows(self.render(self.save(prs), pages), "render-missing-text"), [])

    def test_a_group_child_is_resolved_as_a_child(self):
        prs = new_deck()
        slide = add_slide(prs, "Binder design succeeds")
        group = slide.shapes.add_group_shape()
        group.shapes.add_textbox(914400, 3000000, 3000000, 500000).text_frame.text = "Gamma"
        seen = []
        real = rc.rs.resolve_run

        def spy(prs_, slide_, shape, *rest):
            seen.append(isinstance(shape, GroupShape))
            return real(prs_, slide_, shape, *rest)

        with mock.patch.object(rc.rs, "resolve_run", side_effect=spy):
            rc._read_deck(self.save(prs))
        self.assertIn(False, seen)
        self.assertNotIn(True, seen)

    def test_a_table_cell_and_a_group_child_are_read(self):
        prs = new_deck()
        slide = add_slide(prs, "Binder design succeeds")
        table = slide.shapes.add_table(1, 2, 914400, 914400, 4000000, 600000)
        table.table.cell(0, 0).text = "Alpha"
        table.table.cell(0, 1).text = "Beta"
        group = slide.shapes.add_group_shape()
        group.shapes.add_textbox(914400, 3000000, 3000000, 500000).text_frame.text = "Gamma Delta"
        pages = [page_of("Binder design succeeds Alpha", 36.0)]
        # The cells and the group have no font of their own, so they resolve to Calibri: a third calibration page.
        findings = self.render(self.save(prs), pages, factors=AVENIR_AND_CALIBRI)
        (finding,) = self.rows(findings, "render-missing-text")
        self.assertIn("3 words", finding.message)
        self.assertIn("Beta, Gamma, Delta", finding.message)


class RenderPages(DeckCase):
    def slides(self, count, hidden=()):
        prs = new_deck()
        for index in range(count):
            slide = add_slide(prs, "Binder design succeeds for %d targets" % (index + 1))
            if index + 1 in hidden:
                slide._element.set("show", "0")
        return self.save(prs)

    def test_a_hidden_slide_has_no_page_and_the_numbers_stay_those_of_the_deck(self):
        path = self.slides(3, hidden=(2,))
        pages = [page_of("Binder design succeeds for 1 targets", 42.0), page_of("Binder design succeeds for", 42.0)]
        findings = self.render(path, pages)
        self.assertEqual([(f.slide, f.rule) for f in findings], [(3, "render-missing-text")])
        self.assertIn("targets", findings[0].message)

    def test_each_page_belongs_to_the_slide_with_its_index(self):
        path = self.slides(2)
        pages = [page_of("Binder design succeeds for 1", 42.0), page_of("Binder design succeeds for 2 targets", 42.0)]
        findings = self.render(path, pages)
        self.assertEqual([(f.slide, f.rule) for f in findings], [(1, "render-missing-text")])

    def test_the_findings_are_ordered_by_slide_and_then_by_rule(self):
        path = self.slides(2)
        pages = [page_of("Binder design succeeds for 1 targets", 42.0), page_of("Binder succeeds for 2 targets", 10.0)]
        findings = self.render(path, pages)
        self.assertEqual([(f.slide, f.rule) for f in findings],
                         [(2, "render-font"), (2, "render-missing-text")])

    def test_a_deck_with_no_visible_slide_starts_no_conversion(self):
        path = self.slides(1, hidden=(1,))
        self.assertEqual(self.render(path, [page_of("x", 1.0)]), [])
        self.assertEqual(self.outdirs(), [])

    def test_a_page_with_no_word_at_all_is_a_page(self):
        path = self.slides(2)
        pages = [[], page_of("Binder design succeeds for 2 targets", 42.0)]
        findings = self.render(path, pages)
        self.assertEqual([(f.slide, f.rule) for f in findings], [(1, "render-missing-text")])
        self.assertIn("5 words", findings[0].message)


class CommandLine(DeckCase):
    """`design_lint.py --render` with the fake tools. The deck has one clean slide: the title and the body of lint_helpers."""

    def main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = dl.main([str(a) for a in args])
        return code, out.getvalue(), err.getvalue()

    def deck(self, slides=1, notes=True):
        prs = new_deck()
        for index in range(slides):
            slide = clean_slide(prs, title="Binder design succeeds for %d of 15 targets" % (index + 1))
            if notes:
                add_notes(slide, "Speak about the assay and the controls.")
        return self.save(prs)

    def pages(self, *lacking, slides=1, heights=None):
        """Return canned pages for the deck: every word at 24 pt (36 high), except those that the page lacks.

        `heights` maps a word to its height on the first page.
        """
        pages = []
        for index in range(slides):
            words = ("Binder design succeeds for %d of 15 targets " % (index + 1) + BODY).split()
            pages.append([(word, (heights or {}).get(word, 36.0) if index == 0 else 36.0) for word in words
                          if not (index == 0 and word in lacking)])
        return pages

    def install(self, pages, factors=AVENIR):
        self.soffice()
        self.pdftotext(deck=bbox(*pages), calibration=calibration_of(factors))

    def test_the_findings_are_appended_and_count_as_warnings(self):
        self.install(self.pages("Twelve"))
        code, out, err = self.main(self.deck(), "--minutes", "5", "--render")
        lines = out.splitlines()
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(len(lines), 3, out)
        self.assertRegex(lines[0], r"^slide 1: render-missing-text: warn: T3: 1 word of the deck is not in the rendered page")
        self.assertEqual(lines[1:], ["errors: 0", "warnings: 1"])

    def test_without_the_option_no_conversion_starts(self):
        self.install(self.pages("Twelve"))
        code, out, err = self.main(self.deck(), "--minutes", "5")
        self.assertEqual((code, out), (0, "errors: 0\nwarnings: 0\n"))
        self.assertEqual(self.outdirs(), [])

    def test_the_rows_stay_in_the_order_of_the_slides(self):
        self.install(self.pages("Twelve", slides=2))
        code, out, err = self.main(self.deck(slides=2, notes=False), "--minutes", "5", "--render")
        rows = [line.split(": ")[:2] for line in out.splitlines() if line.startswith(("slide", "deck"))]
        self.assertEqual(rows, [["slide 1", "notes"], ["slide 1", "render-missing-text"], ["slide 2", "notes"]])

    def test_a_failed_render_is_a_warning_and_leaves_the_exit_code(self):
        self.soffice("exit 1")
        self.pdftotext()
        code, out, err = self.main(self.deck(), "--minutes", "5", "--render")
        self.assertEqual((code, err), (0, ""))
        lines = out.splitlines()
        self.assertEqual(lines[0], "deck: render-check: warn: T3: render check failed: soffice exited with code 1")
        self.assertEqual(lines[1:], ["errors: 0", "warnings: 1"])

    def test_a_file_error_of_the_check_leaves_the_lint_rows(self):
        self.install(self.pages())
        with mock.patch.object(rc.tempfile, "mkdtemp", side_effect=OSError(errno.ENOSPC, "No space left on device")):
            code, out, err = self.main(self.deck(notes=False), "--minutes", "5", "--render")
        self.assertEqual((code, err), (0, ""))
        rows = [line.split(": ")[:2] for line in out.splitlines() if line.startswith(("slide", "deck"))]
        self.assertEqual(rows, [["deck", "render-check"], ["slide 1", "notes"]])
        self.assertIn("render check failed: file error", out)

    def test_a_deck_with_an_error_still_exits_1_with_the_option(self):
        prs = new_deck()
        add_box(add_slide(prs, None), BODY)
        self.install([[(word, 36.0) for word in BODY.split()]])
        code, out, err = self.main(self.save(prs), "--no-notes", "--render")
        self.assertEqual(code, 1)
        self.assertIn("title-empty: error", out)

    def test_a_deck_that_cannot_be_opened_exits_2_and_starts_no_conversion(self):
        self.install(self.pages())
        code, out, err = self.main(self.tmp / "missing.pptx", "--render")
        self.assertEqual((code, out), (2, ""))
        self.assertIn("cannot read the deck", err)
        self.assertEqual(self.outdirs(), [])

    def test_the_floor_is_the_source_font_limit_of_the_style(self):
        self.install(self.pages(heights={"Twelve": 27.0}))  # 18 pt at factor 1.5
        path = self.deck()
        self.assertNotIn("render-font", self.main(path, "--minutes", "5", "--render")[1])
        project = self.tmp / "project"
        project.mkdir()
        (project / "slide-style-minimal.yaml").write_text("lint:\n  source_font: {warn_below: 20, tier: T3}\n")
        code, out, err = self.main(path, "--minutes", "5", "--render", "--project-dir", project)
        self.assertEqual((code, err), (0, ""))
        self.assertRegex(out, r"slide 1: render-font: warn: T2: 1 rendered word is below 20 pt\. The smallest is 18\.0 pt")

    def test_the_script_runs_with_the_option(self):
        self.install(self.pages("Twelve"))
        done = subprocess.run([sys.executable, "-B", str(SCRIPT), str(self.deck()), "--minutes", "5", "--render"],
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual((done.returncode, done.stderr), (0, ""))
        self.assertIn("slide 1: render-missing-text: warn: T3:", done.stdout)
        self.assertTrue(done.stdout.endswith("errors: 0\nwarnings: 1\n"), done.stdout)


class CommandLineWhenUnavailable(FakeTools):
    def main(self, *args):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = dl.main([str(a) for a in args])
        return code, out.getvalue(), err.getvalue()

    def deck(self):
        prs = new_deck()
        add_notes(clean_slide(prs), "Speak about the assay and the controls.")
        path = self.tmp / "deck.pptx"
        prs.save(str(path))
        return path

    def test_render_prints_the_skip_line_and_goes_on(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        path = self.deck()
        with mock.patch.dict(os.environ, {"PATH": str(empty)}):
            code, out, err = self.main(path, "--minutes", "5", "--render")
        plain = self.main(path, "--minutes", "5")
        self.assertEqual((code, err), (0, ""))
        self.assertEqual(out.splitlines(), plain[1].splitlines() + [
            "render check skipped: soffice or pdftotext not found"])

    def test_the_skip_line_appears_once_and_only_with_the_option(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        path = self.deck()
        with mock.patch.dict(os.environ, {"PATH": str(empty)}):
            self.assertEqual(self.main(path, "--minutes", "5", "--render")[1].count("render check skipped"), 1)
            self.assertNotIn("render", self.main(path, "--minutes", "5")[1])


@unittest.skipUnless(rc.available(), "this check needs soffice (LibreOffice) to render the deck and pdftotext to read the PDF, "
                                     "and one is missing")
class RealLibreOffice(unittest.TestCase):
    """Render decks with the real LibreOffice. A LibreOffice that is installed but cannot render skips the class."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        try:
            prs = new_deck()
            clean_slide(prs)  # slide 1: no finding
            add_box(add_slide(prs), "Tiny words here", size=10)  # slide 2: 10 pt in Avenir Light
            hidden = add_slide(prs)  # slide 3: hidden
            hidden._element.set("show", "0")
            below = add_slide(prs)  # slide 4: a word below the page
            add_box(below, "Visible words", top=1.6)
            add_box(below, "Outside words", top=9.0, name="Off the page")
            add_box(add_slide(prs), "Calibri words", size=10, family="Calibri")  # slide 5: 10 pt in Calibri
            add_box(add_slide(prs), "Large Calibri words", size=24, family="Calibri")  # slide 6: no finding
            path = Path(cls._tmp.name) / "deck.pptx"
            prs.save(str(path))
            cls.findings = rc.render_findings(path, 12)
        except BaseException:
            cls._tmp.cleanup()
            raise
        failed = [f for f in cls.findings if f.rule == "render-check"]
        if failed:
            cls._tmp.cleanup()
            raise unittest.SkipTest("LibreOffice is installed but could not render the deck: {}".format(failed[0].message))

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def of(self, rule, slide):
        return [f for f in self.findings if f.rule == rule and f.slide == slide]

    def size_of(self, finding):
        return float(re.search(r"smallest is ([\d.]+) pt", finding.message).group(1))

    def test_a_10_pt_run_gives_a_render_font_warning_in_the_house_font(self):
        (finding,) = self.of("render-font", 2)
        self.assertEqual((finding.severity, finding.tier), ("warn", "T2"))
        self.assertAlmostEqual(self.size_of(finding), 10.0, delta=0.3)
        self.assertIn("'Tiny'", finding.message)

    def test_a_10_pt_run_gives_a_render_font_warning_in_another_font(self):
        (finding,) = self.of("render-font", 5)
        self.assertAlmostEqual(self.size_of(finding), 10.0, delta=0.3)

    def test_24_pt_text_gives_no_render_font_warning(self):
        self.assertEqual([f.slide for f in self.findings if f.rule == "render-font"], [2, 5])

    def test_text_below_the_page_gives_a_render_missing_text_warning(self):
        (finding,) = self.of("render-missing-text", 4)
        self.assertEqual((finding.severity, finding.tier), ("warn", "T3"))
        self.assertIn("1 word ", finding.message)
        self.assertIn("Outside", finding.message)
        self.assertNotIn("Visible", finding.message)

    def test_a_clean_slide_and_a_hidden_slide_give_no_finding(self):
        self.assertEqual([f for f in self.findings if f.slide in (1, 3, 6)], [])

    def test_nothing_else_is_reported(self):
        self.assertEqual(sorted((f.slide, f.rule) for f in self.findings),
                         [(2, "render-font"), (4, "render-missing-text"), (5, "render-font")])


@unittest.skipUnless(rc.available(), "this check needs soffice (LibreOffice) to render the deck and pdftotext to read the PDF, "
                                     "and one is missing")
class RealLetterSpacing(unittest.TestCase):
    """Widely spaced letters become single letters in the text of the PDF. The words must still match."""

    def test_letter_spaced_text_gives_no_render_missing_text_warning(self):
        with tempfile.TemporaryDirectory() as folder:
            prs = new_deck()
            for text, size, spacing in (("CONCLUSIONS", 12, "500"), ("FOXTROT SUMMARY", 14, "150")):
                slide = add_slide(prs, "Binder design succeeds for 12 of 15 targets")
                box = add_box(slide, text, size=size)
                box.text_frame.paragraphs[0].runs[0]._r.get_or_add_rPr().set("spc", spacing)
            path = Path(folder) / "deck.pptx"
            prs.save(str(path))
            pages = rc._render(path, Path(folder), (shutil.which("soffice"), shutil.which("pdftotext")), 120)
            if any(word in (text for _height, text in page) for page in pages for word in ("CONCLUSIONS", "FOXTROT")):
                self.skipTest("this LibreOffice does not split letter-spaced words, so the test cannot fail")
            findings = rc.render_findings(path, 12)
        self.assertEqual([f for f in findings if f.rule == "render-missing-text"], [])


@unittest.skipUnless(rc.available(), "this check needs soffice (LibreOffice) to render the deck and pdftotext to read the PDF, "
                                     "and one is missing")
class RealChartLabels(unittest.TestCase):
    """A deck whose only font is Avenir Light has a chart with 9 pt labels. The labels hold no text of the deck."""

    def test_9_pt_axis_labels_give_a_render_font_warning(self):
        with tempfile.TemporaryDirectory() as folder:
            prs = new_deck()
            frame = add_chart(add_slide(prs), size=9)
            frame.chart.font.name = "Avenir Light"
            path = Path(folder) / "deck.pptx"
            prs.save(str(path))
            findings = rc.render_findings(path, 12)
        if any(f.rule == "render-check" for f in findings):
            self.skipTest("LibreOffice is installed but could not render the deck: {}".format(findings[0].message))
        (finding,) = [f for f in findings if f.rule == "render-font"]
        self.assertEqual(finding.slide, 1)
        self.assertAlmostEqual(float(re.search(r"smallest is ([\d.]+) pt", finding.message).group(1)), 9.0, delta=0.4)
        self.assertRegex(finding.message, r"^\d+ rendered words are below 12 pt")


@unittest.skipUnless(rc.available(), "this check needs soffice (LibreOffice) to render the deck and pdftotext to read the PDF, "
                                     "and one is missing")
class RealRightToLeft(unittest.TestCase):
    def test_hebrew_and_arabic_words_give_no_render_missing_text_warning(self):
        with tempfile.TemporaryDirectory() as folder:
            prs = new_deck()
            add_box(add_slide(prs), "Twelve \u05e9\u05dc\u05d5\u05dd \u0645\u0631\u062d\u0628\u0627 folded", size=24)
            path = Path(folder) / "deck.pptx"
            prs.save(str(path))
            findings = rc.render_findings(path, 12)
        self.assertEqual(findings, [])


@unittest.skipUnless(rc.available(), "this check needs soffice (LibreOffice) to render the deck and pdftotext to read the PDF, "
                                     "and one is missing")
class RealHouseDeck(unittest.TestCase):
    """The deck of all six layouts is in budget, so the render check must stay quiet on it."""

    def test_a_deck_of_all_six_layouts_gives_no_finding(self):
        with tempfile.TemporaryDirectory() as folder:
            prs = build_all_layouts(style_mod.load_style("peers", "light"), Path(folder))
            path = Path(folder) / "all.pptx"
            prs.save(str(path))
            findings = rc.render_findings(path, 12)
        if any(f.rule == "render-check" for f in findings):
            self.skipTest("LibreOffice is installed but could not render the deck: {}".format(findings[0].message))
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
