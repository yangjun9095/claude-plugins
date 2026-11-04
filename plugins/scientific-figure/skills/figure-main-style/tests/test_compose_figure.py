"""Tests for scripts/compose_figure.py.

Every panel is an invented PDF that the tests build with PyMuPDF at run time.
The tests run the composer as a command, so they check the exit status and the
messages that a user sees. The expected numbers are literals, not values read
back from the composer.

Run from the skill folder:
    python -I -m unittest discover -s tests -p "test_compose*" -v
"""
import contextlib
import hashlib
import io
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

import fitz

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(os.path.dirname(HERE), "scripts", "compose_figure.py")
sys.path.insert(0, os.path.dirname(SCRIPT))
sys.dont_write_bytecode = True  # keep the scripts folder free of cache files
import compose_figure  # noqa: E402

MM = 72.0 / 25.4

try:
    import matplotlib
    MPL_FONTS = os.path.join(matplotlib.get_data_path(), "fonts", "ttf")
except ImportError:  # pragma: no cover
    MPL_FONTS = None


def make_panel(path, w_mm, h_mm, label="LABEL", corner_ink=False, extra_ink=None, right_half_only=False):
    """Write a one-page panel PDF.

    The panel has a filled rectangle as data and a label in Helvetica at 7 pt. The top-left
    corner of 4 x 4 mm stays empty unless corner_ink or extra_ink asks for ink there.
    """
    doc = fitz.open()
    page = doc.new_page(width=w_mm * MM, height=h_mm * MM)
    left = 50 if right_half_only else 4
    page.draw_rect(fitz.Rect(left * MM, 10 * MM, (w_mm - 1) * MM, (h_mm - 1) * MM),
                   fill=(0.3, 0.3, 0.3), color=None)
    if label:
        page.insert_text((5 * MM, 8 * MM), label, fontname="helv", fontsize=7)
    if corner_ink:
        page.draw_rect(fitz.Rect(0, 0, 2 * MM, 2 * MM), fill=(0, 0, 0), color=None)
    if extra_ink:
        x0, y0, x1, y1 = extra_ink
        page.draw_rect(fitz.Rect(x0 * MM, y0 * MM, x1 * MM, y1 * MM), fill=(0, 0, 0), color=None)
    doc.save(path)
    doc.close()


def make_text_panel(path):
    """Write a 82.5 x 40 mm panel for the text removal tests.

    It holds three vector drawings, the panel's own letter "a" at 9 pt, a smaller single letter,
    the letter inside a word, tight lines of text, and a repeated string.
    """
    doc = fitz.open()
    page = doc.new_page(width=82.5 * MM, height=40 * MM)
    page.draw_rect(fitz.Rect(40, 45, 200, 100), fill=(0.6, 0.6, 0.6), color=None)
    page.draw_line((10, 106), (220, 106))
    page.draw_circle((210, 70), 8)
    page.insert_text((3, 10), "a", fontname="hebo", fontsize=9)
    page.insert_text((30, 12), "banana", fontname="helv", fontsize=7)
    page.insert_text((30, 25), "n = 5", fontname="helv", fontsize=7)
    page.insert_text((30, 32), "n = 50", fontname="helv", fontsize=7)
    page.insert_text((100, 25), "x", fontname="helv", fontsize=6)
    page.insert_text((120, 18), "KEEP-ME", fontname="helv", fontsize=7)
    page.insert_text((190, 12), "N/A", fontname="helv", fontsize=7)
    page.insert_text((190, 45), "N/A", fontname="helv", fontsize=7)
    doc.save(path)
    doc.close()


def make_tilted_panel(path):
    """Write a 60 x 40 mm panel with a horizontal title and three labels turned by 45 degrees."""
    doc = fitz.open()
    page = doc.new_page(width=60 * MM, height=40 * MM)
    page.insert_text((5 * MM, 6 * MM), "Title", fontname="helv", fontsize=7)
    for i, name in enumerate(["geneA", "geneB", "geneC"]):
        point = fitz.Point((12 + 12 * i) * MM, 34 * MM)
        page.insert_text(point, name, fontname="helv", fontsize=7, morph=(point, fitz.Matrix(-45)))
    doc.save(path)
    doc.close()


def make_vertical_panel(path):
    """Write a 60 x 40 mm panel with a title and two labels that read up and down (90 and 270 degrees)."""
    doc = fitz.open()
    page = doc.new_page(width=60 * MM, height=40 * MM)
    page.insert_text((5 * MM, 6 * MM), "Title", fontname="helv", fontsize=7)
    page.insert_text((8 * MM, 30 * MM), "yAxis", fontname="helv", fontsize=7, rotate=90)
    page.insert_text((52 * MM, 10 * MM), "other", fontname="helv", fontsize=7, rotate=270)
    doc.save(path)
    doc.close()


def make_overlap_panel(path):
    """Write a 60 x 40 mm panel in which the label OVERLAP is set over the right half of TARGET.

    A band through the middle of TARGET must also cut the first glyphs of OVERLAP.
    """
    doc = fitz.open()
    page = doc.new_page(width=60 * MM, height=40 * MM)
    page.insert_text((10 * MM, 20 * MM), "TARGET", fontname="helv", fontsize=8)
    page.insert_text((18 * MM, 20 * MM), "OVERLAP", fontname="helv", fontsize=8)
    page.insert_text((10 * MM, 30 * MM), "SAFE", fontname="helv", fontsize=8)
    doc.save(path)
    doc.close()


def make_rotate90_panel(path, crop_box=False):
    """Write a panel that reads 60 x 40 mm in a viewer but is stored 40 x 60 mm with /Rotate 90.

    The text KEEP sits at (5, 10) mm of the stored page. A viewer turns the page clockwise,
    so KEEP shows at (50, 5) mm of the 60 x 40 mm view, and it reads downward.
    """
    doc = fitz.open()
    page = doc.new_page(width=40 * MM, height=60 * MM)
    page.insert_text((5 * MM, 10 * MM), "KEEP", fontname="helv", fontsize=7)
    if crop_box:
        page.set_cropbox(fitz.Rect(2 * MM, 2 * MM, 38 * MM, 58 * MM))
    page.set_rotation(90)
    doc.save(path)
    doc.close()


def word_box_mm(page, text):
    """Return the box of the first word with this text in mm, as (x0, y0, x1, y1)."""
    for word in page.get_text("words"):
        if word[4] == text:
            return tuple(v / MM for v in word[:4])
    raise AssertionError("no word %r on the page" % text)


def spans_of(page):
    """Return every text span of a page."""
    out = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            out.extend(line["spans"])
    return out


def span_texts(page):
    return [s["text"].strip() for s in spans_of(page)]


def letter_spans(page, size, texts):
    """Return the spans of the given size whose text is one of texts."""
    return [s for s in spans_of(page) if abs(s["size"] - size) < 0.01 and s["text"].strip() in texts]


def ink_pixels(page, dpi=50):
    pix = page.get_pixmap(dpi=dpi, colorspace=fitz.csGRAY, alpha=False)
    return sum(1 for value in pix.samples if value < 245)


def sha256(path):
    with open(path, "rb") as handle:
        return hashlib.sha256(handle.read()).hexdigest()


class ComposeBase(unittest.TestCase):
    """Build the invented panels once and offer helpers that run the composer."""

    @classmethod
    def setUpClass(cls):
        cls.dir = tempfile.mkdtemp(prefix="compose_test_")
        cls.addClassCleanup(shutil.rmtree, cls.dir, True)
        make_panel(cls.p("panel_a.pdf"), 170, 50, "LABEL-A")
        make_panel(cls.p("panel_b.pdf"), 82.5, 40, "LABEL-B")
        make_panel(cls.p("panel_c.pdf"), 82.5, 40, "LABEL-C")
        make_panel(cls.p("panel_90a.pdf"), 90, 40, "LABEL-90A")
        make_panel(cls.p("panel_90b.pdf"), 90, 40, "LABEL-90B")
        make_panel(cls.p("panel_150.pdf"), 150, 50, "LABEL-150")
        make_panel(cls.p("panel_ink.pdf"), 82.5, 40, "LABEL-INK", corner_ink=True)
        make_panel(cls.p("panel_right.pdf"), 80, 30, None, right_half_only=True)
        make_panel(cls.p("panel_far_ink.pdf"), 82.5, 40, "LABEL-FAR", extra_ink=(8, 0.2, 10, 2))
        make_text_panel(cls.p("panel_text.pdf"))
        make_tilted_panel(cls.p("panel_tilted.pdf"))
        make_vertical_panel(cls.p("panel_vertical.pdf"))
        make_overlap_panel(cls.p("panel_overlap.pdf"))
        make_rotate90_panel(cls.p("panel_rotate90.pdf"))
        make_rotate90_panel(cls.p("panel_rotate90_crop.pdf"), crop_box=True)

    @classmethod
    def p(cls, name):
        """Return the path of a file in the shared panel folder."""
        return os.path.join(cls.dir, name)

    def setUp(self):
        self.out_dir = tempfile.mkdtemp(prefix="compose_out_")
        self.addCleanup(shutil.rmtree, self.out_dir, True)
        self.out_pdf = os.path.join(self.out_dir, "figure.pdf")
        self.before = sorted(os.listdir(self.dir))

    def layout(self, rows, **kw):
        """Write a layout file next to the panels and return its path."""
        data = {"width_mm": 170, "gap_mm": 5.0, "rows": [{"panels": r} for r in rows]}
        data.update(kw)
        self._count = getattr(self, "_count", 0) + 1
        path = os.path.join(self.dir, "layout_%s_%d.json" % (self.id().split(".")[-1], self._count))
        with open(path, "w") as handle:
            json.dump(data, handle)
        return path

    def run_cli(self, layout_path, *extra, **kw):
        cmd = [sys.executable, "-I", SCRIPT, layout_path]
        if kw.get("out", True):
            cmd += ["--out", self.out_pdf]
        proc = subprocess.run(cmd + list(extra), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                              encoding="utf-8", errors="replace")
        return proc

    def compose(self, rows, *extra, **layout_kw):
        proc = self.run_cli(self.layout(rows, **layout_kw), *extra)
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
        return proc

    def figure(self):
        doc = fitz.open(self.out_pdf)
        self.addCleanup(doc.close)
        self.assertEqual(doc.page_count, 1)
        return doc[0]

    def sidecar(self):
        with open(os.path.splitext(self.out_pdf)[0] + ".layout.json") as handle:
            return json.load(handle)


class TestPlacement(ComposeBase):
    def test_two_rows(self):
        proc = self.compose([[{"file": "panel_a.pdf"}],
                             [{"file": "panel_b.pdf"}, {"file": "panel_c.pdf"}]])
        page = self.figure()
        self.assertAlmostEqual(page.rect.width / MM, 170.0, delta=0.05)
        self.assertAlmostEqual(page.rect.height / MM, 95.0, delta=0.05)
        side = self.sidecar()
        self.assertAlmostEqual(side["page_mm"]["width"], 170.0, delta=0.05)
        panels = side["panels"]
        self.assertAlmostEqual(panels[1]["x_mm"], 0.0, delta=0.05)
        self.assertAlmostEqual(panels[2]["x_mm"], 87.5, delta=0.05)
        self.assertAlmostEqual(panels[1]["y_mm"], 55.0, delta=0.05)
        # The panel text sits 5 mm inside its panel, so the output shows where the panel landed.
        words = {w[4]: w for w in page.get_text("words")}
        self.assertAlmostEqual(words["LABEL-B"][0] / MM, 5.0, delta=0.1)
        self.assertAlmostEqual(words["LABEL-C"][0] / MM, 92.5, delta=0.1)
        # Letters a, b, c at 8 pt.
        spans = letter_spans(page, 8.0, {"a", "b", "c"})
        self.assertEqual(sorted(s["text"].strip() for s in spans), ["a", "b", "c"])
        by_text = {s["text"].strip(): s for s in spans}
        self.assertAlmostEqual(by_text["b"]["bbox"][1], by_text["c"]["bbox"][1], delta=0.01)
        self.assertAlmostEqual(by_text["b"]["origin"][1], by_text["c"]["origin"][1], delta=0.01)
        self.assertAlmostEqual(by_text["c"]["origin"][0] / MM, 87.5, delta=0.05)
        self.assertIn("Panels placed at 100%: type sizes are the panels' own.", proc.stdout)
        self.assertNotIn("corner free", proc.stdout)
        self.assertTrue(os.path.exists(os.path.splitext(self.out_pdf)[0] + ".png"))

    def test_overflow_is_an_error(self):
        path = self.layout([[{"file": "panel_90a.pdf"}, {"file": "panel_90b.pdf"}]])
        proc = self.run_cli(path)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("row 1", proc.stderr)
        self.assertIn("15.0 mm", proc.stderr)
        self.assertIn("does not scale", proc.stderr)
        self.assertFalse(os.path.exists(self.out_pdf))

    def test_overflow_names_every_row(self):
        row = [{"file": "panel_90a.pdf"}, {"file": "panel_90b.pdf"}]
        proc = self.run_cli(self.layout([row, [{"file": "panel_b.pdf"}], row]))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("row 1", proc.stderr)
        self.assertIn("row 3", proc.stderr)
        self.assertNotIn("row 2 is", proc.stderr)

    def test_leftover_warns_and_does_not_spread(self):
        proc = self.compose([[{"file": "panel_150.pdf"}]])
        self.assertRegex(proc.stdout, r"WARNING: row 1 leaves 20\.0 mm unused")
        self.assertIn("do not add air", proc.stdout)
        page = self.figure()
        self.assertAlmostEqual(page.rect.width / MM, 170.0, delta=0.05)
        panel = self.sidecar()["panels"][0]
        self.assertAlmostEqual(panel["x_mm"], 0.0, delta=0.05)
        self.assertAlmostEqual(panel["w_mm"], 150.0, delta=0.05)

    def test_small_leftover_does_not_warn(self):
        # 82.5 + 5 + 82.5 = 170: nothing is left over.
        proc = self.compose([[{"file": "panel_b.pdf"}, {"file": "panel_c.pdf"}]])
        self.assertNotIn("unused", proc.stdout)

    def test_too_tall_is_an_error(self):
        path = self.layout([[{"file": "panel_a.pdf"}],
                            [{"file": "panel_b.pdf"}, {"file": "panel_c.pdf"}]], max_height_mm=60)
        proc = self.run_cli(path)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("35.0 mm", proc.stderr)
        self.assertFalse(os.path.exists(self.out_pdf))

    def test_margin_and_gap(self):
        clip = [0, 0, 78, 40]
        self.compose([[{"file": "panel_b.pdf", "clip_mm": clip}, {"file": "panel_c.pdf", "clip_mm": clip}],
                      [{"file": "panel_b.pdf", "clip_mm": clip}]],
                     margin_mm=3, gap_mm=4)
        side = self.sidecar()
        xs = [p["x_mm"] for p in side["panels"]]
        ys = [p["y_mm"] for p in side["panels"]]
        self.assertEqual([round(v, 1) for v in xs], [3.0, 85.0, 3.0])
        self.assertEqual([round(v, 1) for v in ys], [3.0, 3.0, 47.0])
        self.assertAlmostEqual(side["page_mm"]["height"], 2 * 3 + 40 + 4 + 40, delta=0.05)
        self.assertAlmostEqual(side["page_mm"]["width"], 170.0, delta=0.05)

    def test_row_gap_and_col_gap_are_separate(self):
        # Two panels of 78 mm per row: 78 + 6 + 78 = 162 mm. The rows are 40 mm tall, 3 mm apart.
        clip = [0, 0, 78, 40]
        row = [{"file": "panel_b.pdf", "clip_mm": clip}, {"file": "panel_c.pdf", "clip_mm": clip}]
        self.compose([row, row], gap_mm=5, row_gap_mm=3, col_gap_mm=6)
        side = self.sidecar()
        self.assertEqual([round(p["x_mm"], 2) for p in side["panels"]], [0.0, 84.0, 0.0, 84.0])
        self.assertEqual([round(p["y_mm"], 2) for p in side["panels"]], [0.0, 0.0, 43.0, 43.0])
        self.assertAlmostEqual(side["page_mm"]["height"], 83.0, delta=0.05)
        self.assertEqual(side["row_gap_mm"], 3.0)
        self.assertEqual(side["col_gap_mm"], 6.0)

    def test_each_gap_defaults_to_gap_mm(self):
        clip = [0, 0, 78, 40]
        row = [{"file": "panel_b.pdf", "clip_mm": clip}, {"file": "panel_c.pdf", "clip_mm": clip}]
        self.compose([row, row], gap_mm=4, row_gap_mm=1)
        side = self.sidecar()
        self.assertEqual([round(p["x_mm"], 2) for p in side["panels"]], [0.0, 82.0, 0.0, 82.0])
        self.assertEqual([round(p["y_mm"], 2) for p in side["panels"]], [0.0, 0.0, 41.0, 41.0])
        self.assertEqual((side["row_gap_mm"], side["col_gap_mm"]), (1.0, 4.0))
        self.compose([row, row], gap_mm=4, col_gap_mm=1)
        side = self.sidecar()
        self.assertEqual([round(p["x_mm"], 2) for p in side["panels"]], [0.0, 79.0, 0.0, 79.0])
        self.assertEqual([round(p["y_mm"], 2) for p in side["panels"]], [0.0, 0.0, 44.0, 44.0])
        self.assertEqual((side["row_gap_mm"], side["col_gap_mm"]), (4.0, 1.0))
        self.compose([row, row])
        side = self.sidecar()
        self.assertEqual((side["row_gap_mm"], side["col_gap_mm"]), (5.0, 5.0))
        self.assertEqual([round(p["y_mm"], 2) for p in side["panels"]], [0.0, 0.0, 45.0, 45.0])

    def test_col_gap_decides_the_row_width_and_row_gap_the_height(self):
        row = [{"file": "panel_b.pdf"}, {"file": "panel_c.pdf"}]
        # 82.5 + 6 + 82.5 = 171 mm on a 170 mm page.
        proc = self.run_cli(self.layout([row], gap_mm=0, col_gap_mm=6))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("row 1 is 1.0 mm too wide", proc.stderr)
        # 82.5 + 0 + 82.5 = 165 mm: 5.0 mm stay unused, however large the row gap is.
        proc = self.compose([row, row], gap_mm=5, col_gap_mm=0, row_gap_mm=50)
        self.assertIn("row 1 leaves 5.0 mm unused", proc.stdout)
        self.assertAlmostEqual(self.figure().rect.height / MM, 130.0, delta=0.05)
        # Page height 50 + 3 + 40 = 93 mm against a limit of 92 mm.
        proc = self.run_cli(self.layout([[{"file": "panel_a.pdf"}], [{"file": "panel_b.pdf"}]],
                                        row_gap_mm=3, max_height_mm=92))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("1.0 mm over max_height_mm", proc.stderr)

    def test_bad_row_gap_and_col_gap_are_errors(self):
        for bad in ({"row_gap_mm": -1}, {"col_gap_mm": -0.5}, {"row_gap_mm": "3"}, {"col_gap_mm": True}):
            proc = self.run_cli(self.layout([[{"file": "panel_a.pdf"}]], **bad))
            self.assertEqual(proc.returncode, 1, bad)
            self.assertIn("'%s' must" % list(bad)[0], proc.stderr)

    def test_clip_changes_the_placed_size(self):
        self.compose([[{"file": "panel_b.pdf", "clip_mm": [0, 0, 40, 30]}]])
        panel = self.sidecar()["panels"][0]
        self.assertAlmostEqual(panel["w_mm"], 40.0, delta=0.05)
        self.assertAlmostEqual(panel["h_mm"], 30.0, delta=0.05)
        self.assertAlmostEqual(self.figure().rect.height / MM, 30.0, delta=0.05)

    def test_clip_crops_the_content(self):
        none = {"position": "none"}
        self.compose([[{"file": "panel_right.pdf", "clip_mm": [0, 0, 40, 30]}]], letters=none)
        self.assertEqual(ink_pixels(self.figure()), 0)
        self.compose([[{"file": "panel_right.pdf", "clip_mm": [40, 0, 80, 30]}]], letters=none)
        self.assertGreater(ink_pixels(self.figure()), 0)

    def test_absolute_panel_path_and_relative_output(self):
        # A layout may name a panel by absolute path. A relative 'output' resolves against the layout folder.
        proc = self.run_cli(self.layout([[{"file": self.p("panel_a.pdf")}]], output="rel_out.pdf"), out=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        made = os.path.join(self.dir, "rel_out.pdf")
        self.assertTrue(os.path.exists(made))
        for ext in (".pdf", ".png", ".layout.json"):
            os.remove(os.path.join(self.dir, "rel_out" + ext))


class TestLetters(ComposeBase):
    def test_above_adds_a_strip_per_row(self):
        self.compose([[{"file": "panel_a.pdf"}],
                      [{"file": "panel_b.pdf"}, {"file": "panel_c.pdf"}]],
                     letters={"position": "above", "size_pt": 8, "clearance_mm": 1.0})
        page = self.figure()
        height = page.rect.height / MM
        # The strip is the cap height of an 8 pt letter (2.0 to 2.1 mm) plus 1.0 mm clearance.
        self.assertGreaterEqual(height, 95 + 2 * 3.0)
        self.assertLessEqual(height, 95 + 2 * 3.1)
        side = self.sidecar()
        spans = {s["text"].strip(): s for s in letter_spans(page, 8.0, {"a", "b", "c"})}
        for panel in side["panels"]:
            span = spans[panel["letter"]]
            self.assertLess(span["bbox"][1] / MM, panel["y_mm"])
            # The baseline sits exactly the clearance above the panel.
            self.assertAlmostEqual(panel["y_mm"] - span["origin"][1] / MM, 1.0, delta=0.02)
            self.assertAlmostEqual(span["origin"][0] / MM, panel["x_mm"], delta=0.05)
        strip = (height - 95) / 2
        self.assertAlmostEqual(side["panels"][0]["y_mm"], strip, delta=0.02)
        self.assertAlmostEqual(side["panels"][1]["y_mm"], 50 + 5 + 2 * strip, delta=0.02)

    def test_none_draws_no_letters(self):
        self.compose([[{"file": "panel_a.pdf"}]], letters={"position": "none"})
        page = self.figure()
        self.assertEqual(letter_spans(page, 8.0, {"a"}), [])
        self.assertAlmostEqual(page.rect.height / MM, 50.0, delta=0.05)
        self.assertIsNone(self.sidecar()["panels"][0]["letter"])

    def test_letter_sequence_and_blank(self):
        # An empty letter does not use up a letter. An explicit letter uses up its place.
        self.compose([[{"file": "panel_a.pdf"}], [{"file": "panel_b.pdf", "letter": ""}],
                      [{"file": "panel_c.pdf"}]])
        self.assertEqual([p["letter"] for p in self.sidecar()["panels"]], ["a", None, "b"])
        self.compose([[{"file": "panel_a.pdf"}], [{"file": "panel_b.pdf", "letter": "x"}],
                      [{"file": "panel_c.pdf"}]])
        self.assertEqual([p["letter"] for p in self.sidecar()["panels"]], ["a", "x", "c"])

    def test_upper_case(self):
        self.compose([[{"file": "panel_a.pdf"}], [{"file": "panel_b.pdf"}, {"file": "panel_c.pdf"}]],
                     letters={"case": "upper"})
        self.assertEqual([p["letter"] for p in self.sidecar()["panels"]], ["A", "B", "C"])
        self.assertEqual(len(letter_spans(self.figure(), 8.0, {"A", "B", "C"})), 3)

    def test_corner_ink_warns_for_that_panel_only(self):
        proc = self.compose([[{"file": "panel_ink.pdf"}, {"file": "panel_c.pdf"}]])
        warnings = [line for line in proc.stdout.splitlines() if "corner free" in line]
        self.assertEqual(len(warnings), 1, proc.stdout)
        self.assertTrue(warnings[0].startswith("WARNING"))
        self.assertIn("panel_ink.pdf", warnings[0])
        self.assertIn("mm corner free", warnings[0])
        self.assertIn("position 'above'", warnings[0])
        self.assertRegex(warnings[0], r"leave a \d+\.\d \S \d+\.\d mm corner free")

    def test_corner_check_reads_the_clip(self):
        proc = self.compose([[{"file": "panel_ink.pdf", "clip_mm": [10, 0, 82.5, 40]}]])
        self.assertNotIn("corner free", proc.stdout)

    def test_above_does_not_check_the_corner(self):
        proc = self.compose([[{"file": "panel_ink.pdf"}, {"file": "panel_c.pdf"}]],
                            letters={"position": "above"})
        self.assertNotIn("corner free", proc.stdout)

    def test_default_font_comes_from_matplotlib_or_the_builtin(self):
        self.compose([[{"file": "panel_a.pdf"}]])
        font_file = self.sidecar()["font_file"]
        if MPL_FONTS is None:
            self.assertIsNone(font_file)
        else:
            self.assertTrue(os.path.isfile(font_file))

    def test_builtin_font_without_matplotlib(self):
        with mock.patch.dict(sys.modules, {"matplotlib": None, "matplotlib.font_manager": None}):
            self.assertIsNone(compose_figure.default_font_path())
            warnings = []
            font = compose_figure.load_letter_font(None, self.dir, warnings)
        self.assertIsNone(font.path)
        self.assertEqual(font.name, "hebo")
        self.assertEqual(len(warnings), 1)
        self.assertIn("not embedded", warnings[0])
        self.assertIn("Base-14", warnings[0])
        self.assertGreater(font.cap_em, 0.6)
        self.assertLess(font.cap_em, 0.8)

    def test_missing_font_file_is_an_error(self):
        proc = self.run_cli(self.layout([[{"file": "panel_a.pdf"}]], letters={"font_file": "no_such.ttf"}))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("no_such.ttf", proc.stderr)

    @unittest.skipIf(MPL_FONTS is None, "matplotlib is not installed")
    def test_light_font_is_used_as_given(self):
        light = os.path.join(MPL_FONTS, "DejaVuSans.ttf")
        self.compose([[{"file": "panel_a.pdf"}]], letters={"font_file": light})
        page = self.figure()
        spans = letter_spans(page, 8.0, {"a"})
        self.assertEqual(len(spans), 1)
        self.assertIn("DejaVuSans", spans[0]["font"])
        self.assertNotIn("Bold", spans[0]["font"])
        side = self.sidecar()
        self.assertEqual(side["font_file"], light)
        self.assertIn("DejaVu Sans", side["font"])
        self.assertNotIn("Bold", side["font"])
        # No text render mode operator: the composer does not fake bold with a stroke.
        self.assertIsNone(re.search(rb"\bTr\b", page.read_contents()))


class TestLabels(ComposeBase):
    def test_label_sits_on_the_letter_baseline(self):
        self.compose([[{"file": "panel_a.pdf", "label": "Heading"}]],
                     letters={"size_pt": 8, "label_size_pt": 6, "label_gap_mm": 2.0})
        page = self.figure()
        letter = letter_spans(page, 8.0, {"a"})
        label = letter_spans(page, 6.0, {"Heading"})
        self.assertEqual(len(letter), 1)
        self.assertEqual(len(label), 1)
        self.assertAlmostEqual(label[0]["origin"][1], letter[0]["origin"][1], delta=0.01)
        gap_pt = label[0]["origin"][0] - letter[0]["bbox"][2]
        self.assertGreaterEqual(gap_pt, 2.0 * MM - 0.01)
        self.assertAlmostEqual(gap_pt, 2.0 * MM, delta=0.05)
        panel = self.sidecar()["panels"][0]
        self.assertEqual(panel["label"], "Heading")
        self.assertAlmostEqual(panel["label_x_mm"], label[0]["origin"][0] / MM, delta=0.02)

    def test_label_defaults_to_the_letter_size_and_a_gap_of_1_5_mm(self):
        self.compose([[{"file": "panel_a.pdf", "label": "Head"}]])
        page = self.figure()
        words = {w[4]: w for w in page.get_text("words")}
        letter, label = words["a"], words["Head"]
        self.assertGreaterEqual(label[0] - letter[2], 1.5 * MM - 0.01)
        self.assertAlmostEqual(label[1], letter[1], delta=0.01)
        self.assertAlmostEqual(label[3], letter[3], delta=0.01)
        sizes = {round(s["size"], 2) for s in spans_of(page) if "Head" in s["text"]}
        self.assertEqual(sizes, {8.0})

    def test_label_font_file(self):
        if MPL_FONTS is None:
            self.skipTest("matplotlib is not installed")
        light = os.path.join(MPL_FONTS, "DejaVuSans.ttf")
        bold = os.path.join(MPL_FONTS, "DejaVuSans-Bold.ttf")
        self.compose([[{"file": "panel_a.pdf", "label": "Heading"}]],
                     letters={"font_file": bold, "label_font_file": light, "label_size_pt": 6})
        page = self.figure()
        self.assertIn("Bold", letter_spans(page, 8.0, {"a"})[0]["font"])
        label_font = letter_spans(page, 6.0, {"Heading"})[0]["font"]
        self.assertIn("DejaVuSans", label_font)
        self.assertNotIn("Bold", label_font)
        self.assertEqual(self.sidecar()["label_font_file"], light)

    def test_corner_check_covers_the_label(self):
        plain = self.compose([[{"file": "panel_far_ink.pdf"}]])
        self.assertNotIn("corner free", plain.stdout)
        labelled = self.compose([[{"file": "panel_far_ink.pdf", "label": "Heading"}]],
                                letters={"label_size_pt": 6})
        self.assertIn("panel_far_ink.pdf", labelled.stdout)
        self.assertIn("corner free", labelled.stdout)

    def test_label_makes_the_strip_as_tall_as_its_tallest_text(self):
        self.compose([[{"file": "panel_b.pdf", "label": "Heading"}]],
                     letters={"position": "above", "size_pt": 6, "label_size_pt": 12})
        # A 12 pt cap height is 3.0 to 3.1 mm; the strip adds 1.0 mm clearance.
        height = self.figure().rect.height / MM
        self.assertGreaterEqual(height, 40 + 4.0)
        self.assertLessEqual(height, 40 + 4.15)

    def test_label_without_a_letter_is_ignored_with_a_warning(self):
        proc = self.compose([[{"file": "panel_a.pdf", "letter": "", "label": "Heading"}]])
        self.assertIn("WARNING", proc.stdout)
        self.assertIn("Heading", proc.stdout)
        self.assertNotIn("Heading", self.figure().get_text())
        self.assertIsNone(self.sidecar()["panels"][0]["label"])


class TestRemoval(ComposeBase):
    def removal_layout(self, **panel):
        entry = {"file": "panel_text.pdf"}
        entry.update(panel)
        return self.layout([[entry]], letters={"position": "none"})

    def test_removed_strings_are_gone_and_the_others_stay(self):
        proc = self.run_cli(self.removal_layout(remove_text=["n = 5", "N/A"]))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        texts = span_texts(self.figure())
        self.assertNotIn("n = 5", texts)
        self.assertNotIn("N/A", texts)
        for kept in ("n = 50", "banana", "KEEP-ME", "x", "a"):
            self.assertIn(kept, texts)
        self.assertEqual(texts.count("N/A"), 0)

    def test_report_and_sidecar_list_every_removed_string(self):
        proc = self.run_cli(self.removal_layout(remove_text=["n = 5", "N/A", "KEEP-ME"]))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('Removed from panel panel_text.pdf: "n = 5", "N/A", "KEEP-ME"', proc.stdout)
        self.assertEqual(self.sidecar()["panels"][0]["removed_text"], ["n = 5", "N/A", "KEEP-ME"])

    def test_every_matching_span_is_removed_and_listed_once(self):
        proc = self.run_cli(self.removal_layout(remove_text=["N/A"]))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(span_texts(self.figure()).count("N/A"), 0)
        self.assertEqual(self.sidecar()["panels"][0]["removed_text"], ["N/A"])

    def test_vector_drawings_survive(self):
        source = fitz.open(self.p("panel_text.pdf"))
        before = len(source[0].get_drawings())
        source.close()
        self.assertEqual(before, 3)
        proc = self.run_cli(self.removal_layout(remove_text=["n = 5", "N/A", "KEEP-ME", "banana"],
                                                remove_letter="a"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        page = self.figure()
        self.assertEqual(len(page.get_drawings()), before)
        self.assertEqual(page.get_images(), [])

    def test_unmatched_string_is_an_error(self):
        proc = self.run_cli(self.removal_layout(remove_text=["n = 5", "n = 7"]))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("n = 7", proc.stderr)
        self.assertNotIn("'n = 5'", proc.stderr)
        self.assertFalse(os.path.exists(self.out_pdf))

    def test_part_of_a_span_is_not_a_match(self):
        proc = self.run_cli(self.removal_layout(remove_text=["n ="]))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("'n ='", proc.stderr)
        proc = self.run_cli(self.removal_layout(remove_text=["nan"]))
        self.assertEqual(proc.returncode, 1)

    def test_remove_letter_removes_the_letter_but_not_the_letter_in_a_word(self):
        proc = self.run_cli(self.removal_layout(remove_letter="a"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        page = self.figure()
        self.assertEqual(letter_spans(page, 9.0, {"a"}), [])
        texts = span_texts(page)
        self.assertIn("banana", texts)
        self.assertIn("x", texts)
        self.assertEqual(self.sidecar()["panels"][0]["removed_text"], ["a"])
        self.assertIn('Removed from panel panel_text.pdf: "a"', proc.stdout)

    def test_remove_letter_takes_the_largest_single_letter_span(self):
        # The 9 pt "a" is larger than the 6 pt "x", so "x" is not the panel letter.
        proc = self.run_cli(self.removal_layout(remove_letter="x"))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("remove_letter 'x'", proc.stderr)
        proc = self.run_cli(self.removal_layout(remove_letter="q"))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("remove_letter 'q'", proc.stderr)

    def test_remove_letter_frees_the_corner(self):
        with_letter = self.run_cli(self.layout([[{"file": "panel_text.pdf"}]]))
        self.assertIn("corner free", with_letter.stdout)
        without = self.run_cli(self.layout([[{"file": "panel_text.pdf", "remove_letter": "a"}]]))
        self.assertEqual(without.returncode, 0, without.stderr)
        self.assertNotIn("corner free", without.stdout)

    def test_the_panel_file_is_never_written(self):
        digest = sha256(self.p("panel_text.pdf"))
        proc = self.run_cli(self.removal_layout(remove_text=["n = 5"], remove_letter="a"))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(sha256(self.p("panel_text.pdf")), digest)
        source = fitz.open(self.p("panel_text.pdf"))
        self.assertIn("n = 5", span_texts(source[0]))
        source.close()

    def test_bad_removal_keys_are_errors(self):
        for bad in ({"remove_text": "n = 5"}, {"remove_text": [5]}, {"remove_letter": "ab"},
                    {"remove_letter": ""}):
            proc = self.run_cli(self.removal_layout(**bad))
            self.assertEqual(proc.returncode, 1, bad)

    def test_dry_run_reports_the_removal_and_the_error(self):
        proc = self.run_cli(self.removal_layout(remove_text=["n = 5"]), "--dry-run")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn('Removed from panel panel_text.pdf: "n = 5"', proc.stdout)
        proc = self.run_cli(self.removal_layout(remove_text=["n = 9"]), "--dry-run")
        self.assertEqual(proc.returncode, 1)

    def tilted_layout(self, **panel):
        entry = {"file": "panel_tilted.pdf"}
        entry.update(panel)
        return self.layout([[entry]], letters={"position": "none"})

    def test_text_turned_by_45_degrees_is_an_error(self):
        for name in ("geneA", "geneB", "geneC"):
            proc = self.run_cli(self.tilted_layout(remove_text=[name]))
            self.assertEqual(proc.returncode, 1, name)
            self.assertIn("'%s'" % name, proc.stderr)
            self.assertIn("this text is rotated; remove it in the panel script, or remove it by hand",
                          proc.stderr)
            self.assertFalse(os.path.exists(self.out_pdf))

    def test_dry_run_also_stops_for_rotated_text(self):
        proc = self.run_cli(self.tilted_layout(remove_text=["geneC"]), "--dry-run")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("rotated", proc.stderr)

    def test_a_rotated_label_that_is_not_listed_does_not_stop_the_run(self):
        proc = self.run_cli(self.tilted_layout(remove_text=["Title"]))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        texts = span_texts(self.figure())
        self.assertNotIn("Title", texts)
        for kept in ("geneA", "geneB", "geneC"):
            self.assertIn(kept, texts)

    def test_text_that_reads_up_or_down_is_removed(self):
        entry = {"file": "panel_vertical.pdf", "remove_text": ["yAxis", "other"]}
        proc = self.run_cli(self.layout([[entry]], letters={"position": "none"}))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(span_texts(self.figure()), ["Title"])

    def test_axis_aligned_direction_is_within_one_degree(self):
        def direction(degrees):
            return (math.cos(math.radians(degrees)), math.sin(math.radians(degrees)))
        for degrees in (0, 90, 180, 270, -90, 0.5, 89.5, 180.9, 269.2):
            self.assertTrue(compose_figure._is_axis_aligned(direction(degrees)), degrees)
        for degrees in (45, 135, 1.5, 88.5, 2, 30):
            self.assertFalse(compose_figure._is_axis_aligned(direction(degrees)), degrees)

    def test_a_removal_that_damages_a_neighbour_is_an_error(self):
        # OVERLAP is set over the right half of TARGET, so erasing TARGET cuts its first glyphs.
        entry = {"file": "panel_overlap.pdf", "remove_text": ["TARGET"]}
        proc = self.run_cli(self.layout([[entry]], letters={"position": "none"}))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("'OVERLAP'", proc.stderr)
        self.assertNotIn("'SAFE'", proc.stderr)
        self.assertFalse(os.path.exists(self.out_pdf))

    def test_a_band_that_cuts_every_neighbour_names_every_damaged_string(self):
        def whole_page(span):
            return fitz.Rect(-1000, -1000, 5000, 5000)
        entry = {"file": "panel_text.pdf", "remove_text": ["n = 5"]}
        path = self.layout([[entry]], letters={"position": "none"})
        err, out = io.StringIO(), io.StringIO()
        with mock.patch.object(compose_figure, "_redaction_band", whole_page), \
                contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
            status = compose_figure.main([path, "--out", self.out_pdf])
        self.assertEqual(status, 1)
        for damaged in ("'a'", "'banana'", "'n = 50'", "'x'", "'KEEP-ME'", "'N/A'"):
            self.assertIn(damaged, err.getvalue())
        self.assertNotIn("'n = 5'", err.getvalue())
        self.assertFalse(os.path.exists(self.out_pdf))

    def test_a_removal_that_keeps_the_neighbours_is_not_an_error(self):
        # The same panel and string with the real band: the neighbours stay and the run succeeds.
        proc = self.run_cli(self.removal_layout(remove_text=["n = 5"]))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(sorted(span_texts(self.figure())),
                         ["KEEP-ME", "N/A", "N/A", "a", "banana", "n = 50", "x"])


class TestRotatedPages(ComposeBase):
    def rotated_layout(self, name="panel_rotate90.pdf", width_mm=64, **panel):
        entry = {"file": name}
        entry.update(panel)
        return self.layout([[entry]], letters={"position": "none"}, margin_mm=2, width_mm=width_mm)

    def test_a_rotated_page_is_placed_as_a_viewer_shows_it(self):
        proc = self.run_cli(self.rotated_layout())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        page = self.figure()
        # The panel reads 60 x 40 mm. With the 2 mm margin the page is 64 x 44 mm.
        self.assertAlmostEqual(page.rect.width / MM, 64.0, delta=0.05)
        self.assertAlmostEqual(page.rect.height / MM, 44.0, delta=0.05)
        panel = self.sidecar()["panels"][0]
        self.assertEqual([round(panel[k], 2) for k in ("x_mm", "y_mm", "w_mm", "h_mm")],
                         [2.0, 2.0, 60.0, 40.0])
        # KEEP sits at (49.3, 5.0) to (52.6, 11.6) mm of the panel, so 2 mm further on the page.
        box = word_box_mm(page, "KEEP")
        for got, want in zip(box, (51.3, 7.0, 54.6, 13.6)):
            self.assertAlmostEqual(got, want, delta=1.0)
        self.assertTrue(2.0 <= box[0] and box[2] <= 62.0 and 2.0 <= box[1] and box[3] <= 42.0, box)

    def test_the_note_names_the_panel(self):
        proc = self.run_cli(self.rotated_layout())
        note = [line for line in proc.stdout.splitlines() if line.startswith("NOTE")]
        self.assertEqual(len(note), 1, proc.stdout)
        self.assertIn("panel_rotate90.pdf", note[0])
        self.assertIn("/Rotate 90", note[0])
        plain = self.compose([[{"file": "panel_b.pdf"}]])
        self.assertNotIn("NOTE", plain.stdout)

    def test_clip_selects_by_visual_coordinates(self):
        # The right 20 mm of the viewer's 60 x 40 mm panel hold KEEP, 9.3 mm from the clip's left edge.
        proc = self.run_cli(self.rotated_layout(width_mm=24, clip_mm=[40, 0, 60, 40]))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        page = self.figure()
        self.assertAlmostEqual(page.rect.width / MM, 24.0, delta=0.05)
        self.assertAlmostEqual(page.rect.height / MM, 44.0, delta=0.05)
        box = word_box_mm(page, "KEEP")
        for got, want in zip(box, (11.3, 7.0, 14.6, 13.6)):
            self.assertAlmostEqual(got, want, delta=1.0)
        # The left 30 mm hold no ink.
        proc = self.run_cli(self.rotated_layout(clip_mm=[0, 0, 30, 40]))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(ink_pixels(self.figure()), 0)

    def test_text_removal_works_on_a_rotated_page(self):
        proc = self.run_cli(self.rotated_layout(remove_text=["KEEP"]))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(span_texts(self.figure()), [])
        self.assertIn('Removed from panel panel_rotate90.pdf: "KEEP"', proc.stdout)

    def test_a_rotated_page_with_a_crop_box_is_an_error(self):
        proc = self.run_cli(self.rotated_layout("panel_rotate90_crop.pdf"))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("panel_rotate90_crop.pdf", proc.stderr)
        self.assertIn("/Rotate", proc.stderr)
        self.assertFalse(os.path.exists(self.out_pdf))

    def test_the_panel_file_is_never_written(self):
        digest = sha256(self.p("panel_rotate90.pdf"))
        proc = self.run_cli(self.rotated_layout())
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(sha256(self.p("panel_rotate90.pdf")), digest)
        source = fitz.open(self.p("panel_rotate90.pdf"))
        self.addCleanup(source.close)
        self.assertEqual(source[0].rotation, 90)


class TestCommandLine(ComposeBase):
    def test_vector_is_kept(self):
        self.compose([[{"file": "panel_a.pdf"}], [{"file": "panel_b.pdf"}, {"file": "panel_c.pdf"}]])
        page = self.figure()
        text = page.get_text()
        for label in ("LABEL-A", "LABEL-B", "LABEL-C"):
            self.assertIn(label, text)
        self.assertEqual(page.get_images(), [])
        self.assertEqual(len(page.get_drawings()), 3)

    def test_scale_needs_allow_scale(self):
        proc = self.run_cli(self.layout([[{"file": "panel_b.pdf", "scale": 0.9}]]))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("scale", proc.stderr)
        self.assertIn("allow_scale", proc.stderr)
        self.assertFalse(os.path.exists(self.out_pdf))

    def test_scale_with_allow_scale(self):
        proc = self.compose([[{"file": "panel_a.pdf"}], [{"file": "panel_b.pdf", "scale": 0.9}]],
                            allow_scale=True)
        self.assertIn("every type size in panel b shrinks to 0.90x", proc.stdout)
        self.assertNotIn("Panels placed at 100%", proc.stdout)
        panel = self.sidecar()["panels"][1]
        self.assertAlmostEqual(panel["w_mm"], 74.25, delta=0.05)
        self.assertAlmostEqual(panel["h_mm"], 36.0, delta=0.05)
        self.assertAlmostEqual(panel["scale"], 0.9, delta=0.001)

    def test_dry_run_writes_nothing(self):
        path = self.layout([[{"file": "panel_a.pdf"}]], output="never_written.pdf")
        proc = self.run_cli(path, "--dry-run", out=False)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIn("Page: 170.00 x 50.00 mm", proc.stdout)
        self.assertIn("panel_a.pdf", proc.stdout)
        self.assertEqual(sorted(os.listdir(self.dir)), sorted(self.before + [os.path.basename(path)]))
        proc = self.run_cli(path, "--dry-run")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(os.listdir(self.out_dir), [])

    def test_no_png(self):
        self.compose([[{"file": "panel_a.pdf"}]], "--no-png")
        self.assertTrue(os.path.exists(self.out_pdf))
        self.assertFalse(os.path.exists(os.path.splitext(self.out_pdf)[0] + ".png"))
        self.assertTrue(os.path.exists(os.path.splitext(self.out_pdf)[0] + ".layout.json"))

    def test_png_resolution(self):
        self.compose([[{"file": "panel_a.pdf"}]], "--png-dpi", "100")
        pix = fitz.Pixmap(os.path.splitext(self.out_pdf)[0] + ".png")
        self.assertIn(pix.width, (669, 670))
        self.compose([[{"file": "panel_a.pdf"}]])
        pix = fitz.Pixmap(os.path.splitext(self.out_pdf)[0] + ".png")
        self.assertIn(pix.width, (2007, 2008))

    def test_unknown_key_is_an_error(self):
        proc = self.run_cli(self.layout([[{"file": "panel_a.pdf"}]], gapp_mm=3))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("gapp_mm", proc.stderr)
        proc = self.run_cli(self.layout([[{"file": "panel_a.pdf", "colour": "red"}]]))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("colour", proc.stderr)

    def test_note_keys_are_ignored(self):
        proc = self.run_cli(self.layout([[{"file": "panel_a.pdf", "_note": "x"}]], _comment="y"))
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_missing_panel_is_an_error(self):
        proc = self.run_cli(self.layout([[{"file": "no_such_panel.pdf"}]]))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("no_such_panel.pdf", proc.stderr)

    def test_invalid_json_is_an_error(self):
        path = os.path.join(self.dir, "broken_layout.json")
        with open(path, "w") as handle:
            handle.write("{not json")
        proc = self.run_cli(path)
        self.assertEqual(proc.returncode, 1)
        self.assertIn("not valid JSON", proc.stderr)

    def test_output_may_not_overwrite_a_panel(self):
        digest = sha256(self.p("panel_a.pdf"))
        proc = self.run_cli(self.layout([[{"file": "panel_a.pdf"}]]), "--out", self.p("panel_a.pdf"), out=False)
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(sha256(self.p("panel_a.pdf")), digest)

    def test_help_describes_the_layout_keys(self):
        proc = subprocess.run([sys.executable, "-I", SCRIPT, "--help"], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, encoding="utf-8", errors="replace")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("usage:", proc.stdout)
        for key in ("width_mm", "max_height_mm", "gap_mm", "row_gap_mm", "col_gap_mm",
                    "margin_mm", "allow_scale", "letters",
                    "position", "font_file", "clearance_mm", "label_gap_mm", "label_font_file",
                    "label_size_pt", "clip_mm", "label", "scale", "remove_text", "remove_letter",
                    "--dry-run", "--no-png", "--png-dpi", "--out"):
            self.assertIn(key, proc.stdout)


if __name__ == "__main__":
    unittest.main()
