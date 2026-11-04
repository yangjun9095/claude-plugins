"""Tests for check_main_figure.py.

The tests draw invented PDFs with PyMuPDF at run time. They use no binary fixture
and no network. Each expected value is written as a literal in the test.
"""

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

import fitz

SKILL_DIR = Path(__file__).resolve().parent.parent
SCRIPT = SKILL_DIR / "scripts" / "check_main_figure.py"

_spec = importlib.util.spec_from_file_location("check_main_figure", str(SCRIPT))
cmf = importlib.util.module_from_spec(_spec)
sys.modules["check_main_figure"] = cmf
_spec.loader.exec_module(cmf)

# Every check id the tool must report, in report order.
EXPECTED_IDS = [
    "G1", "G2", "G3", "G4", "G5",
    "T1", "T2", "T3",
    "L1", "L2", "L3", "L4", "L5", "L6", "L7",
    "S1", "S2", "S3",
    "C1", "C2",
    "B1",
    "X1", "X2", "X3",
    "R1", "K1",
]

MM = 25.4 / 72.0


def pt(mm):
    """Convert mm to points."""
    return mm / MM


def new_page(doc, w_mm, h_mm):
    return doc.new_page(width=pt(w_mm), height=pt(h_mm))


def put_text(page, x_mm, base_mm, text, size, font="helv"):
    """Draw text with its baseline at base_mm. Return the advance width in mm."""
    page.insert_text((pt(x_mm), pt(base_mm)), text, fontname=font, fontsize=size)
    return fitz.get_text_length(text, fontname=font, fontsize=size) * MM


def fill_rect(page, x0, y0, x1, y1, rgb):
    page.draw_rect(fitz.Rect(pt(x0), pt(y0), pt(x1), pt(y1)), color=None, fill=rgb)


def stroke_rect(page, x0, y0, x1, y1, width=0.5):
    page.draw_rect(fitz.Rect(pt(x0), pt(y0), pt(x1), pt(y1)), color=(0, 0, 0), fill=None, width=width)


def letter_and_title(page, x_mm, base_mm, letter, title, letter_size, letter_font, title_size, gap_mm):
    """Draw a panel letter and a title on the same baseline, gap_mm apart."""
    advance = put_text(page, x_mm, base_mm, letter, letter_size, letter_font)
    if title:
        put_text(page, x_mm + advance + gap_mm, base_mm, title, title_size, "helv")


RED = (0.85, 0.2, 0.2)
BLUE = (0.2, 0.3, 0.85)


def build_panels(path, letters="ab", font="hebo", size=8.0, titles=("Short title", "Short title"), gap_mm=2.0,
                 w_mm=170.0, h_mm=75.0, extra=None):
    """Two panels side by side, 80 mm wide each and 6 mm apart. extra(page) adds more marks."""
    doc = fitz.open()
    page = new_page(doc, w_mm, h_mm)
    panels = ((letters[0], 0.0, 1.0, RED, titles[0]), (letters[1], 86.0, 85.8, BLUE, titles[1]))
    for letter, left, letter_x, colour, title in panels:
        fill_rect(page, left + 5.0, 8.0, left + 80.0, 68.0, colour)
        for k, y in enumerate((20.0, 35.0, 50.0)):
            put_text(page, left + 8.0, y, "label %d" % (k + 1), 7.0)
        letter_and_title(page, letter_x, 6.0, letter, title, size, font, 7.0, gap_mm)
    if extra is not None:
        extra(page)
    doc.save(path)
    doc.close()


def build_row(path, gap_ab, gap_bc, extra=None):
    """Three panels in one row. The gaps between the panel ink are gap_ab and gap_bc mm."""
    doc = fitz.open()
    page = new_page(doc, 170.0, 60.0)
    fill_rect(page, 5.0, 8.0, 50.0, 55.0, RED)
    letter_and_title(page, 1.0, 6.0, "a", "Short title", 8.0, "hebo", 7.0, 2.0)
    b_x = 50.0 + gap_ab - 0.2
    fill_rect(page, b_x + 5.0, 8.0, b_x + 45.0, 55.0, BLUE)
    letter_and_title(page, b_x, 6.0, "b", "Short title", 8.0, "hebo", 7.0, 2.0)
    c_x = b_x + 45.0 + gap_bc - 0.2
    fill_rect(page, c_x + 5.0, 8.0, c_x + 45.0, 55.0, RED)
    letter_and_title(page, c_x, 6.0, "c", "Short title", 8.0, "hebo", 7.0, 2.0)
    if extra is not None:
        extra(page)
    doc.save(path)
    doc.close()


def build_staggered(path):
    """Panel a is tall, so no blank row runs across the page above the letter c."""
    doc = fitz.open()
    page = new_page(doc, 170.0, 100.0)
    fill_rect(page, 5.0, 8.0, 80.0, 90.0, RED)
    letter_and_title(page, 1.0, 6.0, "a", "Short title", 8.0, "hebo", 7.0, 2.0)
    fill_rect(page, 91.0, 8.0, 166.0, 38.0, BLUE)
    letter_and_title(page, 85.8, 6.0, "b", "Short title", 8.0, "hebo", 7.0, 2.0)
    letter_and_title(page, 85.8, 44.0, "c", "Short title", 8.0, "hebo", 7.0, 2.0)
    fill_rect(page, 91.0, 47.0, 166.0, 95.0, BLUE)
    doc.save(path)
    doc.close()


def build_bad(path):
    """Two stacked panels with many faults."""
    doc = fitz.open()
    page = new_page(doc, 170.0, 120.0)
    letter_and_title(page, 1.0, 6.0, "a", "Alpha", 9.0, "helv", 7.0, 2.0)
    fill_rect(page, 5.0, 8.0, 60.0, 20.0, RED)
    fill_rect(page, 5.0, 24.0, 60.0, 36.0, RED)  # leaves a 4 mm blank run inside panel a
    put_text(page, 8.0, 15.0, "six", 6.0)
    put_text(page, 25.0, 15.0, "eight", 8.0)
    put_text(page, 42.0, 17.0, "ten", 10.0)
    # The letter b has its ink top 1.5 mm below the ink of panel a.
    letter_and_title(page, 1.0, 39.78, "b", "Beta", 9.0, "helv", 7.0, 0.3)
    fill_rect(page, 5.0, 42.0, 60.0, 59.0, BLUE)
    stroke_rect(page, 5.0, 62.0, 65.0, 92.0)
    put_text(page, 5.0, 95.0, "95% bootstrap intervals; 1,000 resamples; seed 20261005", 7.0)
    doc.save(path)
    doc.close()


def build_no_letters(path):
    doc = fitz.open()
    page = new_page(doc, 170.0, 75.0)
    fill_rect(page, 10.0, 10.0, 80.0, 60.0, RED)
    fill_rect(page, 90.0, 10.0, 160.0, 60.0, BLUE)
    put_text(page, 12.0, 30.0, "Alpha beta", 7.0)
    put_text(page, 92.0, 30.0, "12 0.5", 7.0)
    doc.save(path)
    doc.close()


def build_merged(path):
    doc = fitz.open()
    page = new_page(doc, 100.0, 40.0)
    page.insert_text((pt(5.0), pt(8.0)), "a  Title text", fontname="hebo", fontsize=8.0)
    fill_rect(page, 5.0, 12.0, 90.0, 35.0, RED)
    doc.save(path)
    doc.close()


def build_merged_tight(path):
    doc = fitz.open()
    page = new_page(doc, 100.0, 40.0)
    page.insert_text((pt(5.0), pt(8.0)), "a Title text", fontname="hebo", fontsize=8.0)
    fill_rect(page, 5.0, 12.0, 90.0, 35.0, RED)
    doc.save(path)
    doc.close()


def build_single_panel(path, with_letter=True):
    doc = fitz.open()
    page = new_page(doc, 80.0, 60.0)
    fill_rect(page, 5.0, 8.0, 75.0, 55.0, RED)
    put_text(page, 8.0, 20.0, "label", 7.0)
    if with_letter:
        letter_and_title(page, 1.0, 6.0, "a", "Short title", 8.0, "hebo", 7.0, 2.0)
    doc.save(path)
    doc.close()


def build_clip_page(path):
    """A figure in the upper 80 mm and body text below it."""
    doc = fitz.open()
    page = new_page(doc, 170.0, 200.0)
    fill_rect(page, 5.0, 8.0, 80.0, 70.0, RED)
    put_text(page, 8.0, 20.0, "label", 7.0)
    letter_and_title(page, 1.0, 6.0, "a", "Short title", 8.0, "hebo", 7.0, 2.0)
    for k in range(8):
        put_text(page, 10.0, 100.0 + 10.0 * k, "body text line %d of the article that runs on and on" % k, 11.0)
    doc.save(path)
    doc.close()


def build_narrow(path):
    """Ink covers only the left third of a 170 mm page."""
    doc = fitz.open()
    page = new_page(doc, 170.0, 40.0)
    fill_rect(page, 5.0, 8.0, 60.0, 35.0, RED)
    put_text(page, 8.0, 20.0, "label", 7.0)
    doc.save(path)
    doc.close()


def build_raster(path, pixels, width_mm):
    """Place one invented raster image of the given pixel width."""
    doc = fitz.open()
    page = new_page(doc, 100.0, 60.0)
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, pixels, pixels), False)
    pix.set_rect(pix.irect, (200, 60, 60))
    page.insert_image(fitz.Rect(pt(5.0), pt(5.0), pt(5.0 + width_mm), pt(5.0 + width_mm)), pixmap=pix)
    doc.save(path)
    doc.close()


def build_raster_rotated(path):
    """Place a 100 x 60 px image rotated by 90 degrees into a box 60/85 in wide and 100/85 in tall."""
    doc = fitz.open()
    page = new_page(doc, 100.0, 60.0)
    pix = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 100, 60), False)
    pix.set_rect(pix.irect, (200, 60, 60))
    page.insert_image(fitz.Rect(10.0, 10.0, 10.0 + 60.0 / 85.0 * 72.0, 10.0 + 100.0 / 85.0 * 72.0),
                      pixmap=pix, rotate=90)
    doc.save(path)
    doc.close()


def build_rotated(path):
    """A panel that shows 60 x 40 mm, stored as 40 x 60 mm with /Rotate 90.

    A stored point (x, y) shows at (60 - y, x) mm. The page holds the words KEEP and REMOVE-ME
    and a stroked box that shows 25 mm wide and 18 mm tall.
    """
    doc = fitz.open()
    page = new_page(doc, 40.0, 60.0)
    page.set_rotation(90)
    page.insert_text((pt(8.0), pt(50.0)), "KEEP", fontsize=7.0, rotate=90)
    page.insert_text((pt(28.0), pt(50.0)), "REMOVE-ME", fontsize=7.0, rotate=90)
    stroke_rect(page, 5.0, 30.0, 23.0, 55.0)
    doc.save(path)
    doc.close()


LETTER_RISE_MM = 2.3  # Measured at 200 dpi: the ink of an 8 pt bold letter b rises this far above its baseline.


def build_stack(path, row_gap_mm=7.5, gutter_mm=0.0):
    """Panel a above panel b in one column.

    The ink of a ends 30 mm from the top. The ink of the letter b starts row_gap_mm below it.
    Panel b holds one block, or two blocks that stand gutter_mm apart.
    """
    base_b = 30.0 + row_gap_mm + LETTER_RISE_MM
    top_b = base_b + 2.0
    doc = fitz.open()
    page = new_page(doc, 170.0, top_b + 22.0 + 3.0)
    letter_and_title(page, 1.0, 6.0, "a", "Short title", 8.0, "hebo", 7.0, 2.0)
    fill_rect(page, 5.0, 8.0, 115.0, 30.0, RED)
    letter_and_title(page, 1.0, base_b, "b", "Short title", 8.0, "hebo", 7.0, 2.0)
    if gutter_mm > 0:
        fill_rect(page, 5.0, top_b, 50.0, top_b + 22.0, BLUE)
        fill_rect(page, 50.0 + gutter_mm, top_b, 95.0 + gutter_mm, top_b + 22.0, BLUE)
    else:
        fill_rect(page, 5.0, top_b, 115.0, top_b + 22.0, BLUE)
    doc.save(path)
    doc.close()


def build_blank_band(path):
    """Panels a and b side by side, panel c below them, 7.5 mm of white between the rows.

    Panel a holds two blocks with 15 mm of white between them. Panel b holds one tall block
    that stands beside that white, so no row of the page is blank across its full width there.
    """
    base_c = 40.0 + 7.5 + 1.93  # The title ink of panel c rises 1.93 mm above the baseline; the letter c is lower.
    doc = fitz.open()
    page = new_page(doc, 170.0, 75.0)
    letter_and_title(page, 1.0, 6.0, "a", "Short title", 8.0, "hebo", 7.0, 2.0)
    letter_and_title(page, 85.8, 6.0, "b", "Short title", 8.0, "hebo", 7.0, 2.0)
    fill_rect(page, 5.0, 8.0, 80.0, 16.0, RED)
    fill_rect(page, 5.0, 31.0, 80.0, 40.0, RED)
    fill_rect(page, 91.0, 8.0, 166.0, 40.0, BLUE)
    letter_and_title(page, 1.0, base_c, "c", "Short title", 8.0, "hebo", 7.0, 2.0)
    fill_rect(page, 5.0, base_c + 2.0, 166.0, base_c + 20.0, RED)
    doc.save(path)
    doc.close()


def build_side_gutter(path, gutter_mm):
    """Panels a and b side by side, about 5.8 mm apart. Panel a holds two blocks gutter_mm apart."""
    doc = fitz.open()
    page = new_page(doc, 170.0, 60.0)
    letter_and_title(page, 1.0, 6.0, "a", "Short title", 8.0, "hebo", 7.0, 2.0)
    letter_and_title(page, 85.8, 6.0, "b", "Short title", 8.0, "hebo", 7.0, 2.0)
    fill_rect(page, 5.0, 8.0, 35.0, 55.0, RED)
    fill_rect(page, 35.0 + gutter_mm, 8.0, 80.0, 55.0, RED)
    fill_rect(page, 91.0, 8.0, 166.0, 55.0, BLUE)
    doc.save(path)
    doc.close()


def build_ink_width(path, ink_mm):
    """A 170 mm page whose ink covers ink_mm of its width."""
    doc = fitz.open()
    page = new_page(doc, 170.0, 40.0)
    fill_rect(page, 5.0, 8.0, 5.0 + ink_mm, 35.0, RED)
    doc.save(path)
    doc.close()


def build_ink_share(path, share):
    """A 100 x 50 mm page. Black ink covers the left part of it, share of the page width."""
    doc = fitz.open()
    page = new_page(doc, 100.0, 50.0)
    fill_rect(page, 0.0, 0.0, 100.0 * share, 50.0, (0.0, 0.0, 0.0))
    doc.save(path)
    doc.close()


HUE_COLOURS = [  # Red, yellow, green, cyan, blue and magenta: 60 degrees apart.
    (0.86, 0.16, 0.16), (0.86, 0.86, 0.16), (0.16, 0.78, 0.16),
    (0.16, 0.78, 0.78), (0.16, 0.16, 0.86), (0.86, 0.16, 0.86),
]


def build_hues(path, count):
    """One filled block of each of the first count colours, 2 mm apart."""
    doc = fitz.open()
    page = new_page(doc, 170.0, 60.0)
    for k in range(count):
        fill_rect(page, 5.0 + 26.0 * k, 10.0, 25.0 + 26.0 * k, 50.0, HUE_COLOURS[k])
    doc.save(path)
    doc.close()


def put_words(page, x_mm, base_mm, count, size=7.0):
    """Draw count one-word tokens in lines of at most 5 words, 4 mm apart."""
    used, line = 0, 0
    while used < count:
        n = min(5, count - used)
        put_text(page, x_mm, base_mm + 4.0 * line, " ".join("w%d" % (used + i) for i in range(n)), size)
        used += n
        line += 1


def get_check(result, cid):
    return [c for c in result["checks"] if c["id"] == cid][0]


def verdicts(result):
    return {c["id"]: c["verdict"] for c in result["checks"]}


def run_cli(*args):
    return subprocess.run([sys.executable, "-I", str(SCRIPT)] + [str(a) for a in args],
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)


class FixtureTestCase(unittest.TestCase):
    """Build the invented PDFs once for the whole class."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory()
        cls.dir = Path(cls._tmp.name)
        cls.good = cls.dir / "good.pdf"
        build_panels(str(cls.good))
        cls.bad = cls.dir / "bad.pdf"
        build_bad(str(cls.bad))
        cls.no_letters = cls.dir / "no_letters.pdf"
        build_no_letters(str(cls.no_letters))
        cls.merged = cls.dir / "merged.pdf"
        build_merged(str(cls.merged))
        cls.merged_tight = cls.dir / "merged_tight.pdf"
        build_merged_tight(str(cls.merged_tight))
        cls.panel = cls.dir / "panel.pdf"
        build_single_panel(str(cls.panel))
        cls.clip_page = cls.dir / "clip.pdf"
        build_clip_page(str(cls.clip_page))
        cls.good_result = cmf.run_checks(str(cls.good))
        cls.bad_result = cmf.run_checks(str(cls.bad))

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()


class TestGood(FixtureTestCase):
    def test_letters_and_layout(self):
        r = self.good_result
        self.assertEqual(get_check(r, "L1")["value"], '"ab"')
        self.assertEqual(get_check(r, "L2")["verdict"], "PASS")
        self.assertEqual(get_check(r, "L5")["verdict"], "PASS")
        self.assertEqual(get_check(r, "L6")["verdict"], "PASS")
        self.assertEqual(get_check(r, "L7")["verdict"], "PASS")

    def test_letter_title_gap_is_two_mm(self):
        gaps = [l["gap_mm"] for l in self.good_result["measures"]["letters"]]
        self.assertEqual(len(gaps), 2)
        for gap in gaps:
            self.assertAlmostEqual(gap, 2.0, delta=0.15)

    def test_column_gap_is_about_six_mm(self):
        cols = self.good_result["measures"]["gaps"]["cols"]
        self.assertEqual(len(cols), 1)
        self.assertAlmostEqual(cols[0]["gap_mm"], 6.0, delta=0.6)
        self.assertEqual(get_check(self.good_result, "S1")["verdict"], "PASS")
        self.assertEqual(get_check(self.good_result, "S2")["verdict"], "PASS")

    def test_type_and_text(self):
        r = self.good_result
        self.assertEqual(get_check(r, "T1")["verdict"], "PASS")
        self.assertEqual([s["size_pt"] for s in r["measures"]["sizes"]], [7.0, 8.0])
        self.assertEqual(get_check(r, "X1")["verdict"], "PASS")
        self.assertEqual(get_check(r, "X3")["verdict"], "PASS")

    def test_two_hues(self):
        hues = self.good_result["measures"]["hues"]
        self.assertEqual(len(hues), 2)
        self.assertEqual(get_check(self.good_result, "C2")["verdict"], "PASS")

    def test_no_fail_and_exit_code_zero(self):
        self.assertNotIn("FAIL", verdicts(self.good_result).values())
        proc = run_cli(self.good)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_table_format(self):
        lines = cmf.render_table(self.good_result).splitlines()
        self.assertTrue(lines[0].startswith("[INFO] G1 width: 170.0 mm"), lines[0])
        self.assertRegex(lines[-1], r"^Summary: \d+ PASS, \d+ WARN, 0 FAIL, \d+ INFO$")


class TestBad(FixtureTestCase):
    def test_expected_verdicts(self):
        v = verdicts(self.bad_result)
        self.assertEqual(v["L2"], "FAIL")
        self.assertEqual(v["L6"], "WARN")
        self.assertEqual(v["T1"], "WARN")
        self.assertEqual(v["X1"], "WARN")
        self.assertEqual(v["S2"], "FAIL")
        self.assertEqual(v["B1"], "WARN")
        self.assertEqual(v["G5"], "WARN")

    def test_letter_b_sits_close_to_its_title(self):
        letters = self.bad_result["measures"]["letters"]
        self.assertEqual([l["letter"] for l in letters], ["a", "b"])
        self.assertAlmostEqual(letters[0]["gap_mm"], 2.0, delta=0.15)
        self.assertAlmostEqual(letters[1]["gap_mm"], 0.3, delta=0.15)

    def test_five_sizes(self):
        sizes = [s["size_pt"] for s in self.bad_result["measures"]["sizes"]]
        self.assertEqual(sizes, [6.0, 7.0, 8.0, 9.0, 10.0])

    def test_gap_between_panels_is_smaller_than_internal_run(self):
        gaps = self.bad_result["measures"]["gaps"]
        self.assertEqual(len(gaps["rows"]), 1)
        self.assertAlmostEqual(gaps["rows"][0]["gap_mm"], 1.5, delta=0.5)
        self.assertEqual(gaps["internal"]["rows"]["letter"], "a")
        self.assertAlmostEqual(gaps["internal"]["rows"]["gap_mm"], 4.0, delta=0.4)
        self.assertIsNone(gaps["internal"]["cols"])
        s2 = get_check(self.bad_result, "S2")
        self.assertEqual(s2["verdict"], "FAIL")
        self.assertIn("panel a, rows", s2["detail"])

    def test_footer_line_is_caption_material(self):
        lines = self.bad_result["measures"]["caption_lines"]
        self.assertEqual(len(lines), 1)
        self.assertTrue(lines[0]["text"].startswith("95% bootstrap"))

    def test_box_is_sixty_by_thirty(self):
        boxes = self.bad_result["measures"]["boxes"]
        self.assertEqual(len(boxes), 1)
        self.assertAlmostEqual(boxes[0]["x1_mm"] - boxes[0]["x0_mm"], 60.0, delta=0.2)
        self.assertAlmostEqual(boxes[0]["y1_mm"] - boxes[0]["y0_mm"], 30.0, delta=0.2)

    def test_exit_code_one(self):
        proc = run_cli(self.bad)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("[FAIL] L2 weight", proc.stdout)


class TestLayoutFaults(FixtureTestCase):
    """Each check must fire on a fault. A check that never fires guards nothing."""

    def test_text_left_of_the_letter_warns(self):
        path = self.dir / "left_text.pdf"
        # The label starts 2.3 mm left of the letter b, inside its panel margin.
        build_panels(str(path), extra=lambda page: put_text(page, 83.5, 30.0, "tick", 7.0))
        r = cmf.run_checks(str(path))
        l7 = get_check(r, "L7")
        self.assertEqual(l7["verdict"], "WARN")
        self.assertIn("letter b", l7["detail"])
        self.assertEqual(get_check(self.good_result, "L7")["verdict"], "PASS")

    def test_letters_off_baseline_fail(self):
        path = self.dir / "off_baseline.pdf"
        doc = fitz.open()
        page = new_page(doc, 170.0, 40.0)
        fill_rect(page, 5.0, 12.0, 160.0, 35.0, RED)
        letter_and_title(page, 1.0, 6.0, "a", "Short title", 8.0, "hebo", 7.0, 2.0)
        letter_and_title(page, 85.8, 7.0, "b", "Short title", 8.0, "hebo", 7.0, 2.0)  # 1 mm lower
        doc.save(str(path))
        doc.close()
        r = cmf.run_checks(str(path))
        self.assertEqual(get_check(r, "L5")["verdict"], "FAIL")
        self.assertAlmostEqual(r["measures"]["letters"][1]["y_mm"] - r["measures"]["letters"][0]["y_mm"], 1.0, delta=0.05)

    def test_unequal_column_gaps_warn(self):
        uneven, even = self.dir / "uneven.pdf", self.dir / "even.pdf"
        build_row(str(uneven), 5.0, 8.0)
        build_row(str(even), 5.0, 5.5)
        r = cmf.run_checks(str(uneven))
        gaps = [g["gap_mm"] for g in r["measures"]["gaps"]["cols"]]
        self.assertEqual(len(gaps), 2)
        self.assertAlmostEqual(gaps[0], 5.0, delta=0.4)
        self.assertAlmostEqual(gaps[1], 8.0, delta=0.4)
        self.assertEqual(get_check(r, "S3")["verdict"], "WARN")
        self.assertEqual(get_check(cmf.run_checks(str(even)), "S3")["verdict"], "PASS")

    def test_staggered_panels_use_the_column_profile(self):
        path = self.dir / "staggered.pdf"
        build_staggered(str(path))
        r = cmf.run_checks(str(path))
        self.assertEqual(get_check(r, "L1")["value"], '"abc"')
        rows = r["measures"]["gaps"]["rows"]
        self.assertEqual([(g["mode"], g["letter"]) for g in rows], [("column", "c")])
        self.assertAlmostEqual(rows[0]["gap_mm"], 4.5, delta=0.8)

    def test_many_words_in_one_panel_warn(self):
        path = self.dir / "wordy.pdf"

        def extra(page):
            for k in range(12):
                put_text(page, 25.0, 22.0 + 4.0 * k, "one two three four five", 7.0)

        build_panels(str(path), extra=extra)
        r = cmf.run_checks(str(path))
        self.assertEqual(r["measures"]["words"]["per_panel"], {"a": 69, "b": 9})
        self.assertEqual(r["measures"]["words"]["total"], 78)
        self.assertEqual(get_check(r, "X2")["verdict"], "WARN")
        self.assertEqual(get_check(self.good_result, "X2")["verdict"], "PASS")

    def test_six_words_make_caption_material(self):
        for text, expected in (("one two three four five", "PASS"), ("one two three four five six", "WARN")):
            path = self.dir / ("words_%d.pdf" % len(text))
            build_panels(str(path), extra=lambda page, t=text: put_text(page, 25.0, 30.0, t, 7.0))
            self.assertEqual(get_check(cmf.run_checks(str(path)), "X1")["verdict"], expected, text)

    def test_pattern_alone_makes_caption_material(self):
        path = self.dir / "pattern.pdf"
        build_panels(str(path), extra=lambda page: put_text(page, 25.0, 30.0, "n = 12 mice", 7.0))
        r = cmf.run_checks(str(path))
        self.assertEqual(get_check(r, "X1")["verdict"], "WARN")
        self.assertEqual([l["words"] for l in r["measures"]["caption_lines"]], [3])  # "=" is not a word


class TestNoLetters(FixtureTestCase):
    def test_l1_fails_and_spacing_is_skipped(self):
        r = cmf.run_checks(str(self.no_letters))
        self.assertEqual(get_check(r, "L1")["verdict"], "FAIL")
        self.assertIn("outlines", get_check(r, "L1")["detail"])
        for cid in ("S1", "S2", "S3"):
            self.assertEqual(get_check(r, cid)["verdict"], "INFO")
            self.assertEqual(get_check(r, cid)["value"], "skipped")
        self.assertEqual(get_check(r, "X3")["verdict"], "INFO")


class TestMerged(FixtureTestCase):
    def test_letter_merged_into_title(self):
        r = cmf.run_checks(str(self.merged))
        letters = r["measures"]["letters"]
        self.assertEqual([l["letter"] for l in letters], ["a"])
        self.assertTrue(letters[0]["merged"])
        self.assertEqual(get_check(r, "L1")["verdict"], "PASS")
        # Two Helvetica spaces at 8 pt: 2 x 0.278 em x 8 pt = 4.448 pt = 1.569 mm.
        self.assertEqual(get_check(r, "L6")["verdict"], "PASS")
        self.assertIn("a 1.57 mm", get_check(r, "L6")["detail"])
        self.assertEqual(letters[0]["title_words"], 2)
        self.assertEqual(get_check(r, "X3")["verdict"], "PASS")

    def test_letter_merged_with_one_space_runs_into_the_label(self):
        # One Helvetica space at 8 pt: 0.278 em x 8 pt = 2.224 pt = 0.785 mm, under 1.0 mm.
        r = cmf.run_checks(str(self.merged_tight))
        self.assertEqual(get_check(r, "L1")["value"], '"a"')
        self.assertEqual(get_check(r, "L6")["verdict"], "WARN")
        self.assertIn("a 0.78 mm", get_check(r, "L6")["detail"])

    def test_head_and_tail_needs_one_character_then_space(self):
        def chars(text):
            return [{"c": c, "bbox": (i * 2.0, 0, i * 2.0 + 2.0, 8)} for i, c in enumerate(text)]

        self.assertEqual(cmf.head_and_tail(chars("a  bc")), (2.0, 6.0))
        self.assertEqual(cmf.head_and_tail(chars("ab c")), (None, None))
        self.assertEqual(cmf.head_and_tail(chars("a")), (None, None))


class TestPanelMode(FixtureTestCase):
    def test_panel_skips_layout_checks(self):
        r = cmf.run_checks(str(self.panel), panel=True)
        for cid in ("G3", "L5", "L7", "S1", "S2", "S3"):
            self.assertEqual(get_check(r, cid)["verdict"], "INFO", cid)
            self.assertEqual(get_check(r, cid)["value"], "skipped", cid)
        l1 = get_check(r, "L1")
        self.assertEqual(l1["verdict"], "INFO")
        self.assertIn("letter drawn inside the panel", l1["detail"])

    def test_panel_without_letter(self):
        path = self.dir / "panel_plain.pdf"
        build_single_panel(str(path), with_letter=False)
        r = cmf.run_checks(str(path), panel=True)
        self.assertEqual(get_check(r, "L1")["value"], "none")
        self.assertNotIn("FAIL", verdicts(r).values())

    def test_panel_flag_on_the_command_line(self):
        proc = run_cli(self.panel, "--panel")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("letter drawn inside the panel", proc.stdout)


class TestClip(FixtureTestCase):
    def test_clip_limits_the_box(self):
        whole = cmf.run_checks(str(self.clip_page))
        clipped = cmf.run_checks(str(self.clip_page), clip_mm=(0.0, 0.0, 170.0, 80.0))
        self.assertAlmostEqual(whole["box_mm"][1], 200.0, delta=0.05)
        self.assertAlmostEqual(clipped["box_mm"][1], 80.0, delta=0.05)
        self.assertAlmostEqual(clipped["box_mm"][0], 170.0, delta=0.05)
        self.assertIn(11.0, [s["size_pt"] for s in whole["measures"]["sizes"]])
        self.assertEqual([s["size_pt"] for s in clipped["measures"]["sizes"]], [7.0, 8.0])
        self.assertLess(clipped["measures"]["words"]["total"], 10)

    def test_clip_on_the_command_line(self):
        proc = run_cli(self.clip_page, "--clip-mm", "0,0,170,80", "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertAlmostEqual(json.loads(proc.stdout)["box_mm"][1], 80.0, delta=0.05)

    def test_bad_clip_is_refused(self):
        proc = run_cli(self.clip_page, "--clip-mm", "10,10,5,5")
        self.assertEqual(proc.returncode, 2)


class TestJson(FixtureTestCase):
    def test_json_output(self):
        proc = run_cli(self.good, "--json")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual([c["id"] for c in data["checks"]], EXPECTED_IDS)
        self.assertEqual(sorted(data["checks"][0].keys()), ["detail", "house", "id", "name", "value", "verdict"])
        self.assertEqual(len(data["box_mm"]), 2)
        for key in ("sizes", "letters", "gaps", "hues", "empty", "words"):
            self.assertIn(key, data["measures"])


class TestOptions(FixtureTestCase):
    def test_slot_width(self):
        self.assertEqual(get_check(cmf.run_checks(str(self.good), slot_mm=180.0), "G1")["verdict"], "FAIL")
        self.assertEqual(get_check(cmf.run_checks(str(self.good), slot_mm=170.0), "G1")["verdict"], "PASS")

    def test_slot_left_unused(self):
        path = self.dir / "narrow.pdf"
        build_narrow(str(path))
        self.assertEqual(get_check(cmf.run_checks(str(path), slot_mm=170.0), "G1")["verdict"], "WARN")

    def test_max_height(self):
        self.assertEqual(get_check(cmf.run_checks(str(self.good), max_height_mm=70.0), "G2")["verdict"], "FAIL")
        self.assertEqual(get_check(cmf.run_checks(str(self.good), max_height_mm=80.0), "G2")["verdict"], "PASS")
        self.assertEqual(get_check(self.good_result, "G2")["verdict"], "INFO")

    def test_min_pt(self):
        self.assertEqual(get_check(cmf.run_checks(str(self.good), min_pt=8.0), "T2")["verdict"], "FAIL")
        self.assertEqual(get_check(self.good_result, "T2")["verdict"], "PASS")

    def test_case(self):
        path = self.dir / "upper.pdf"
        build_panels(str(path), letters="AB")
        self.assertEqual(get_check(cmf.run_checks(str(path)), "L3")["verdict"], "WARN")
        self.assertEqual(get_check(cmf.run_checks(str(path), case="upper"), "L3")["verdict"], "PASS")
        self.assertEqual(get_check(cmf.run_checks(str(path), case="any"), "L3")["verdict"], "PASS")

    def test_page_option(self):
        doc = fitz.open()
        new_page(doc, 100.0, 50.0)
        new_page(doc, 120.0, 60.0)
        path = self.dir / "two_pages.pdf"
        doc.save(str(path))
        doc.close()
        self.assertAlmostEqual(cmf.run_checks(str(path), page=2)["box_mm"][0], 120.0, delta=0.05)
        self.assertEqual(run_cli(path, "--page", "3").returncode, 2)

    def test_raster_resolution(self):
        soft = self.dir / "soft.pdf"
        sharp = self.dir / "sharp.pdf"
        build_raster(str(soft), 100, 50.0)    # 100 px over 50 mm is about 51 ppi
        build_raster(str(sharp), 800, 50.0)   # 800 px over 50 mm is about 406 ppi
        self.assertEqual(get_check(cmf.run_checks(str(soft)), "R1")["verdict"], "WARN")
        self.assertEqual(get_check(cmf.run_checks(str(sharp)), "R1")["verdict"], "PASS")
        self.assertAlmostEqual(cmf.run_checks(str(soft))["measures"]["images"][0]["ppi"], 50.8, delta=0.5)


class TestRanges(FixtureTestCase):
    """Each exemplar range must pass a figure inside it and warn on a figure outside it."""

    def test_aspect_range(self):
        self.assertEqual(get_check(self.good_result, "G3")["verdict"], "PASS")  # 170 / 75 = 2.27
        narrow = cmf.run_checks(str(self.good), clip_mm=(0.0, 0.0, 80.0, 75.0))  # 1.07
        wide = cmf.run_checks(str(self.good), clip_mm=(0.0, 0.0, 170.0, 30.0))  # 5.67
        self.assertEqual(get_check(narrow, "G3")["verdict"], "WARN")
        self.assertEqual(get_check(wide, "G3")["verdict"], "WARN")

    def test_ink_share_range(self):
        path = self.dir / "narrow_ink.pdf"
        build_narrow(str(path))
        self.assertEqual(get_check(self.good_result, "G4")["verdict"], "WARN")  # about 0.71
        self.assertEqual(get_check(cmf.run_checks(str(path)), "G4")["verdict"], "PASS")  # about 0.22

    def test_colour_share_range(self):
        self.assertEqual(get_check(self.good_result, "C1")["verdict"], "WARN")  # about 0.71
        self.assertEqual(get_check(self.bad_result, "C1")["verdict"], "PASS")  # about 0.11

    def test_stroke_widths(self):
        path = self.dir / "strokes.pdf"
        doc = fitz.open()
        page = new_page(doc, 100.0, 60.0)
        for k, width in enumerate((0.1, 0.2, 0.5, 1.0)):
            page.draw_line((pt(5.0), pt(10.0 + 5.0 * k)), (pt(50.0), pt(10.0 + 5.0 * k)), color=(0, 0, 0), width=width)
        doc.save(str(path))
        doc.close()
        r = cmf.run_checks(str(path))
        strokes = r["measures"]["strokes"]
        self.assertEqual(strokes["count"], 4)
        self.assertAlmostEqual(strokes["median_pt"], 0.35, places=3)
        self.assertEqual(strokes["below_min"], 2)
        self.assertEqual(get_check(r, "K1")["verdict"], "INFO")
        self.assertIn("2 of 4", get_check(r, "K1")["detail"])


class TestLetterWeightAndTitles(FixtureTestCase):
    """The author may set light letters, 6 pt letters and short labels after the letter."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.light = cls.dir / "light.pdf"
        build_panels(str(cls.light), font="helv", size=6.0, titles=("Two words", "Bench label"))

    def test_regular_passes_a_light_letter(self):
        r = cmf.run_checks(str(self.light), letter_weight="regular")
        self.assertEqual(get_check(r, "L2")["verdict"], "PASS")
        self.assertIn("Helvetica", get_check(r, "L2")["detail"])

    def test_default_bold_fails_a_light_letter(self):
        r = cmf.run_checks(str(self.light))
        self.assertEqual(get_check(r, "L2")["verdict"], "FAIL")
        self.assertIn("Helvetica", get_check(r, "L2")["detail"])

    def test_regular_fails_a_bold_letter(self):
        r = cmf.run_checks(str(self.good), letter_weight="regular")
        self.assertEqual(get_check(r, "L2")["verdict"], "FAIL")
        self.assertIn("Helvetica-Bold", get_check(r, "L2")["detail"])

    def test_any_weight_is_info_with_the_font_name(self):
        for path, name in ((self.good, "Helvetica-Bold"), (self.light, "Helvetica")):
            r = cmf.run_checks(str(path), letter_weight="any")
            self.assertEqual(get_check(r, "L2")["verdict"], "INFO")
            self.assertIn(name, get_check(r, "L2")["detail"])

    def test_weight_option_on_the_command_line(self):
        proc = run_cli(self.light, "--letter-weight", "regular", "--json")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        l2 = [c for c in json.loads(proc.stdout)["checks"] if c["id"] == "L2"][0]
        self.assertEqual(l2["verdict"], "PASS")
        self.assertEqual(run_cli(self.light, "--letter-weight", "heavy").returncode, 2)

    def test_six_point_letters_pass_l4(self):
        r = cmf.run_checks(str(self.light), letter_weight="regular")
        self.assertEqual(get_check(r, "L4")["verdict"], "PASS")
        self.assertEqual(get_check(r, "L4")["value"], "6 pt")

    def test_nine_point_passes_and_ten_point_warns(self):
        for size, expected in ((9.0, "PASS"), (10.0, "WARN"), (5.5, "WARN")):
            path = self.dir / ("size_%g.pdf" % size)
            build_panels(str(path), size=size)
            self.assertEqual(get_check(cmf.run_checks(str(path)), "L4")["verdict"], expected, size)

    def test_two_word_label_passes_x3(self):
        r = cmf.run_checks(str(self.light), letter_weight="regular")
        x3 = get_check(r, "X3")
        self.assertEqual(x3["verdict"], "PASS")
        self.assertEqual([l["title_words"] for l in r["measures"]["letters"]], [2, 2])
        self.assertEqual(get_check(self.good_result, "X3")["verdict"], "PASS")

    def test_x3_limit_is_five_words(self):
        for title, expected in (("one two three four", "PASS"), ("one two three four five", "WARN"),
                                ("Models pass the test but miss the reason", "WARN")):
            path = self.dir / ("title_%d.pdf" % len(title))
            build_panels(str(path), titles=(title, "Short title"))
            self.assertEqual(get_check(cmf.run_checks(str(path)), "X3")["verdict"], expected, title)


class TestRotatedPage(FixtureTestCase):
    """A page with /Rotate keeps its text, drawings and render in one frame."""

    def test_rotated_panel_keeps_both_words_and_the_box(self):
        path = self.dir / "rotated.pdf"
        build_rotated(str(path))
        r = cmf.run_checks(str(path), panel=True)
        self.assertEqual(r["box_mm"], [60.0, 40.0])
        self.assertEqual(r["measures"]["words"]["total"], 2)
        self.assertEqual(get_check(r, "X2")["value"], "2 words")
        self.assertEqual(get_check(r, "B1")["value"], "1 box")
        g1 = get_check(r, "G1")["detail"]
        self.assertIn("NOTE", g1)
        self.assertIn("90", g1)

    def test_upright_page_carries_no_rotation_note(self):
        self.assertNotIn("NOTE", get_check(self.good_result, "G1")["detail"])

    def test_rotated_page_reaches_the_command_line_with_the_note(self):
        path = self.dir / "rotated_cli.pdf"
        build_rotated(str(path))
        proc = run_cli(path, "--panel")
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("[INFO] G1 width: 60.0 mm", proc.stdout)
        self.assertIn("NOTE: the page carries /Rotate 90", proc.stdout)


class TestSpacingRanges(FixtureTestCase):
    """Rows and columns each have their own exemplar range."""

    def s1_for_row_gap(self, gap):
        path = self.dir / ("stack_%g.pdf" % gap)
        build_stack(str(path), row_gap_mm=gap)
        r = cmf.run_checks(str(path))
        rows = r["measures"]["gaps"]["rows"]
        self.assertEqual(len(rows), 1)
        self.assertAlmostEqual(rows[0]["gap_mm"], gap, delta=0.15)
        self.assertEqual(r["measures"]["gaps"]["cols"], [])
        return get_check(r, "S1")

    def s1_for_col_gap(self, gap):
        path = self.dir / ("row_%g.pdf" % gap)
        # build_row leaves the measured ink gap about 0.17 mm short of its argument, so add 0.17 mm.
        build_row(str(path), gap + 0.17, gap + 0.17)
        r = cmf.run_checks(str(path))
        cols = r["measures"]["gaps"]["cols"]
        self.assertEqual(len(cols), 2)
        for col in cols:
            self.assertAlmostEqual(col["gap_mm"], gap, delta=0.15)
        return get_check(r, "S1")

    def test_row_gap_inside_the_row_range_passes(self):
        self.assertEqual(self.s1_for_row_gap(3.2)["verdict"], "PASS")

    def test_row_gap_of_eight_mm_warns(self):
        self.assertEqual(self.s1_for_row_gap(8.0)["verdict"], "WARN")

    def test_row_gap_of_six_mm_warns_because_six_mm_is_a_column_gap(self):
        self.assertEqual(self.s1_for_row_gap(6.0)["verdict"], "WARN")

    def test_column_gap_of_six_mm_passes(self):
        self.assertEqual(self.s1_for_col_gap(6.0)["verdict"], "PASS")

    def test_column_gap_of_two_point_six_mm_warns(self):
        self.assertEqual(self.s1_for_col_gap(2.6)["verdict"], "WARN")

    def test_column_gap_of_three_point_two_mm_warns_because_it_is_a_row_gap(self):
        self.assertEqual(self.s1_for_col_gap(3.2)["verdict"], "WARN")

    def test_row_gaps_near_each_limit_of_the_row_range(self):
        for gap, expected in ((2.2, "WARN"), (2.8, "PASS"), (3.7, "PASS"), (4.1, "WARN")):
            self.assertEqual(self.s1_for_row_gap(gap)["verdict"], expected, gap)

    def test_column_gaps_near_each_limit_of_the_column_range(self):
        for gap, expected in ((3.8, "WARN"), (4.6, "PASS"), (7.7, "PASS"), (8.6, "WARN")):
            self.assertEqual(self.s1_for_col_gap(gap)["verdict"], expected, gap)

    def test_house_text_names_both_ranges(self):
        house = get_check(self.good_result, "S1")["house"]
        self.assertEqual(house, "rows 2.5 to 3.9 mm, columns 4.2 to 8.1 mm")


class TestInternalWhite(FixtureTestCase):
    """S2 measures white inside each panel region, in rows and in columns."""

    def test_blank_band_beside_an_inked_block_fails(self):
        path = self.dir / "blank_band.pdf"
        build_blank_band(str(path))
        r = cmf.run_checks(str(path))
        self.assertEqual(get_check(r, "L1")["value"], '"abc"')
        gaps = r["measures"]["gaps"]
        self.assertEqual([(g["mode"], round(g["gap_mm"], 1)) for g in gaps["rows"]][0][0], "full")
        self.assertAlmostEqual(gaps["rows"][0]["gap_mm"], 7.5, delta=0.3)
        white = gaps["internal"]["rows"]
        self.assertEqual(white["letter"], "a")
        self.assertAlmostEqual(white["gap_mm"], 15.0, delta=0.3)
        self.assertAlmostEqual(white["y0_mm"], 16.0, delta=0.3)
        self.assertAlmostEqual(white["y1_mm"], 31.0, delta=0.3)
        s2 = get_check(r, "S2")
        self.assertEqual(s2["verdict"], "FAIL")
        self.assertIn("panel a, rows", s2["detail"])
        self.assertIn("y=", s2["detail"])
        self.assertIn("<=", s2["value"])

    def test_blank_column_wider_than_the_row_gap_warns(self):
        path = self.dir / "gutter_20.pdf"
        build_stack(str(path), row_gap_mm=7.5, gutter_mm=20.0)
        r = cmf.run_checks(str(path))
        gaps = r["measures"]["gaps"]
        self.assertAlmostEqual(gaps["rows"][0]["gap_mm"], 7.5, delta=0.3)
        white = gaps["internal"]["cols"]
        self.assertEqual(white["letter"], "b")
        self.assertAlmostEqual(white["gap_mm"], 20.0, delta=0.3)
        self.assertAlmostEqual(white["x0_mm"], 50.0, delta=0.3)
        self.assertAlmostEqual(white["x1_mm"], 70.0, delta=0.3)
        s2 = get_check(r, "S2")
        self.assertEqual(s2["verdict"], "WARN")
        self.assertIn("panel b, columns", s2["detail"])
        self.assertIn("x=", s2["detail"])

    def test_blank_column_narrower_than_the_row_gap_passes(self):
        path = self.dir / "gutter_5.pdf"
        build_stack(str(path), row_gap_mm=7.5, gutter_mm=5.0)
        r = cmf.run_checks(str(path))
        white = r["measures"]["gaps"]["internal"]["cols"]
        self.assertAlmostEqual(white["gap_mm"], 5.0, delta=0.3)
        self.assertEqual(get_check(r, "S2")["verdict"], "PASS")

    def test_gutter_wider_than_the_column_gap_fails(self):
        path = self.dir / "side_gutter_10.pdf"
        build_side_gutter(str(path), 10.0)
        r = cmf.run_checks(str(path))
        gaps = r["measures"]["gaps"]
        self.assertAlmostEqual(gaps["cols"][0]["gap_mm"], 5.8, delta=0.4)
        self.assertAlmostEqual(gaps["internal"]["cols"]["gap_mm"], 10.0, delta=0.3)
        s2 = get_check(r, "S2")
        self.assertEqual(s2["verdict"], "FAIL")
        self.assertIn("panel a, columns", s2["detail"])

    def test_gutter_narrower_than_the_column_gap_passes(self):
        path = self.dir / "side_gutter_4.pdf"
        build_side_gutter(str(path), 4.0)
        r = cmf.run_checks(str(path))
        self.assertAlmostEqual(r["measures"]["gaps"]["internal"]["cols"]["gap_mm"], 4.0, delta=0.3)
        self.assertEqual(get_check(r, "S2")["verdict"], "PASS")

    def test_good_figure_passes_and_names_the_internal_white(self):
        s2 = get_check(self.good_result, "S2")
        self.assertEqual(s2["verdict"], "PASS")
        self.assertIsNone(self.good_result["measures"]["gaps"]["internal"]["cols"])
        self.assertAlmostEqual(self.good_result["measures"]["gaps"]["internal"]["rows"]["gap_mm"], 2.0, delta=0.3)
        self.assertIn("panel", s2["detail"])


class TestTitleSearch(FixtureTestCase):
    """A letter takes a title only from its own panel."""

    def test_letter_without_a_title_does_not_take_the_next_letter(self):
        path = self.dir / "no_title_a.pdf"
        build_panels(str(path), titles=("", "Short title"))
        r = cmf.run_checks(str(path))
        letters = r["measures"]["letters"]
        self.assertEqual([l["letter"] for l in letters], ["a", "b"])
        self.assertIsNone(letters[0]["gap_mm"])
        self.assertEqual(letters[0]["title"], "")
        self.assertEqual(letters[1]["title"], "Short title")
        l6 = get_check(r, "L6")
        self.assertTrue(l6["detail"].startswith("b "), l6["detail"])
        self.assertNotIn("a ", l6["detail"])
        self.assertEqual([l["title_words"] for l in letters], [0, 2])
        self.assertEqual(get_check(r, "X3")["detail"], "a: 0, b: 2")

    def test_title_farther_than_ten_mm_from_its_letter_is_not_taken(self):
        path = self.dir / "far_title.pdf"
        doc = fitz.open()
        page = new_page(doc, 100.0, 40.0)
        fill_rect(page, 5.0, 12.0, 95.0, 35.0, RED)
        put_text(page, 1.0, 6.0, "a", 8.0, "hebo")
        put_text(page, 21.0, 6.0, "Far title", 7.0)
        doc.save(str(path))
        doc.close()
        r = cmf.run_checks(str(path))
        self.assertIsNone(r["measures"]["letters"][0]["gap_mm"])
        self.assertEqual(r["measures"]["letters"][0]["title"], "")

    def test_title_nine_mm_from_its_letter_is_taken(self):
        path = self.dir / "near_title.pdf"
        build_panels(str(path), gap_mm=9.0)
        r = cmf.run_checks(str(path))
        letters = r["measures"]["letters"]
        self.assertAlmostEqual(letters[0]["gap_mm"], 9.0, delta=0.2)
        self.assertEqual(letters[0]["title"], "Short title")

    def test_text_inside_the_next_panel_is_not_taken_even_when_near(self):
        # Letter b stands 6 mm right of letter a, inside 10 mm, so only the panel-region
        # clause keeps a from taking b (or b's title) as its own title.
        path = self.dir / "near_next_panel.pdf"
        doc = fitz.open()
        page = new_page(doc, 100.0, 40.0)
        fill_rect(page, 1.0, 12.0, 5.0, 35.0, RED)
        fill_rect(page, 7.0, 12.0, 95.0, 35.0, RED)
        put_text(page, 1.0, 6.0, "a", 8.0, "hebo")
        put_text(page, 7.0, 6.0, "b", 8.0, "hebo")
        put_text(page, 9.5, 6.0, "Next title", 7.0)
        doc.save(str(path))
        doc.close()
        r = cmf.run_checks(str(path))
        letters = r["measures"]["letters"]
        self.assertEqual([l["letter"] for l in letters], ["a", "b"])
        self.assertIsNone(letters[0]["gap_mm"])
        self.assertEqual(letters[0]["title"], "")
        self.assertEqual(letters[1]["title"], "Next title")


class TestRotatedImage(FixtureTestCase):
    def test_rotated_image_uses_the_pixel_area_over_the_box_area(self):
        path = self.dir / "raster_rotated.pdf"
        build_raster_rotated(str(path))
        r = cmf.run_checks(str(path))
        self.assertEqual(len(r["measures"]["images"]), 1)
        self.assertAlmostEqual(r["measures"]["images"][0]["ppi"], 85.0, delta=1.0)
        self.assertEqual(get_check(r, "R1")["value"], "lowest 85 ppi")


class TestBoundaries(FixtureTestCase):
    """Pin each range constant near its limit, with literal expectations."""

    def test_slot_ink_share_of_0_80_passes_and_0_70_warns(self):
        for ink_mm, expected in ((136.0, "PASS"), (119.0, "WARN")):
            path = self.dir / ("ink_width_%d.pdf" % ink_mm)
            build_ink_width(str(path), ink_mm)
            r = cmf.run_checks(str(path), slot_mm=170.0)
            self.assertAlmostEqual(r["measures"]["ink_extent_mm"], ink_mm, delta=0.3)
            self.assertEqual(get_check(r, "G1")["verdict"], expected, ink_mm)

    def test_slot_house_text_names_the_exemplar_range(self):
        path = self.dir / "ink_width_house.pdf"
        build_ink_width(str(path), 136.0)
        house = get_check(cmf.run_checks(str(path), slot_mm=170.0), "G1")["house"]
        self.assertIn("exemplars 0.78 to 1.01", house)

    def test_ink_share_limits(self):
        cases = ((0.10, "WARN"), (0.16, "PASS"), (0.20, "PASS"), (0.49, "PASS"), (0.53, "WARN"), (0.98, "WARN"))
        for share, expected in cases:
            path = self.dir / ("share_%d.pdf" % round(share * 100))
            build_ink_share(str(path), share)
            r = cmf.run_checks(str(path))
            self.assertAlmostEqual(r["measures"]["ink_share"], share, delta=0.01)
            self.assertEqual(get_check(r, "G4")["verdict"], expected, share)

    def test_five_hues_pass_and_six_hues_warn(self):
        for count, expected in ((5, "PASS"), (6, "WARN")):
            path = self.dir / ("hues_%d.pdf" % count)
            build_hues(str(path), count)
            r = cmf.run_checks(str(path))
            c2 = get_check(r, "C2")
            self.assertEqual(c2["value"], "%d hues" % count)
            self.assertEqual(c2["verdict"], expected, count)

    def test_words_in_a_figure_limit_is_102(self):
        for total, expected in ((102, "PASS"), (103, "WARN")):
            path = self.dir / ("words_total_%d.pdf" % total)
            # Each panel holds 3 words of letter and title. The three panels get 31, 31 and total - 71.
            build_row(str(path), 5.0, 5.0, extra=lambda page, t=total: (
                put_words(page, 8.0, 14.0, 31), put_words(page, 61.8, 14.0, 31),
                put_words(page, 111.6, 14.0, t - 9 - 62)))
            r = cmf.run_checks(str(path))
            words = r["measures"]["words"]
            self.assertEqual(words["total"], total)
            self.assertEqual(words["per_panel"], {"a": 34, "b": 34, "c": total - 68})
            x2 = get_check(r, "X2")
            self.assertEqual(x2["verdict"], expected, total)
            self.assertEqual(x2["value"], "%d words" % total)

    def test_baseline_spread_limit(self):
        for offset, expected in ((0.2, "PASS"), (0.4, "FAIL")):
            path = self.dir / ("baseline_%d.pdf" % round(offset * 10))
            doc = fitz.open()
            page = new_page(doc, 170.0, 40.0)
            fill_rect(page, 5.0, 12.0, 160.0, 35.0, RED)
            letter_and_title(page, 1.0, 6.0, "a", "Short title", 8.0, "hebo", 7.0, 2.0)
            letter_and_title(page, 85.8, 6.0 + offset, "b", "Short title", 8.0, "hebo", 7.0, 2.0)
            doc.save(str(path))
            doc.close()
            r = cmf.run_checks(str(path))
            letters = r["measures"]["letters"]
            self.assertAlmostEqual(letters[1]["y_mm"] - letters[0]["y_mm"], offset, delta=0.03)
            self.assertEqual(get_check(r, "L5")["verdict"], expected, offset)


class TestHelpers(unittest.TestCase):
    def test_largest_empty_rectangle(self):
        blank = np.ones((6, 8), dtype=bool)
        blank[2, 3] = False
        area, top, left, height, width = cmf.largest_empty_rectangle(blank)
        # Two rectangles tie at 24 cells: rows 3 to 5 over all 8 columns, and columns 4 to 7 over all 6 rows.
        self.assertEqual(area, 24)
        self.assertEqual(height * width, 24)
        self.assertTrue(blank[top:top + height, left:left + width].all())

    def test_largest_empty_rectangle_all_ink(self):
        self.assertEqual(cmf.largest_empty_rectangle(np.zeros((4, 4), dtype=bool))[0], 0)

    def test_count_words(self):
        self.assertEqual(cmf.count_words(""), 0)
        self.assertEqual(cmf.count_words("a - b"), 2)
        self.assertEqual(cmf.count_words("n = 3, seed 7"), 4)

    def test_fonts_type3_fails(self):
        fonts = [(1, "n/a", "Type3", "ABCDEF+Glyphs", "F1", "WinAnsi", 0)]
        check = cmf.check_fonts(fonts)
        self.assertEqual(check["verdict"], "FAIL")
        self.assertIn("Glyphs", check["detail"])

    def test_fonts_not_embedded_warns(self):
        fonts = [(1, "n/a", "Type1", "Helvetica", "F1", "WinAnsi", 0)]
        self.assertEqual(cmf.check_fonts(fonts)["verdict"], "WARN")

    def test_fonts_embedded_passes(self):
        fonts = [(1, "ttf", "Type0", "ABCDEF+Avenir-Roman", "F1", "Identity-H", 0)]
        check = cmf.check_fonts(fonts)
        self.assertEqual(check["verdict"], "PASS")
        self.assertIn("Avenir-Roman", check["detail"])
        self.assertNotIn("ABCDEF", check["detail"])

    def test_bold_is_read_from_the_font_name_or_the_flag(self):
        def letter(font, flags):
            span = cmf.Span(text="a", size=8.0, font=font, flags=flags, x0=1, y0=1, x1=3, y1=4, line=0)
            return cmf.Letter(ch="a", span=span, merged=False)

        for font in ("Foo-Bold", "Foo-SemiBold", "Foo-Demi", "Foo-Black", "Foo-Heavy", "Foo-ExtraBold", "FOO-BOLD"):
            self.assertTrue(letter(font, 0).bold, font)
        self.assertTrue(letter("Foo-Plain", 16).bold)
        for font in ("Foo-Roman", "Foo-Light", "Foo-Regular"):
            self.assertFalse(letter(font, 4).bold, font)

    def test_blank_run_above(self):
        profile = np.array([1, 0, 0, 0, 1, 1, 1], dtype=bool)  # ink at rows 0, 4, 5, 6
        self.assertEqual(cmf.blank_run_above(profile, 4, 0), (1, 4))
        self.assertEqual(cmf.blank_run_above(profile, 6, 0), (6, 6))
        self.assertEqual(cmf.blank_run_above(profile, 6, 2), (1, 4))

    def test_hues_of_a_two_colour_image(self):
        image = np.full((100, 100, 3), 255, dtype=np.uint8)
        image[:, :50] = (220, 40, 40)
        image[:, 50:90] = (40, 60, 220)
        share, hues = cmf.measure_colour(image)
        self.assertAlmostEqual(share, 0.9, places=3)
        self.assertEqual(len(hues), 2)
        self.assertEqual([h["hex"] for h in hues], ["#dc2828", "#283cdc"])
        self.assertAlmostEqual(hues[0]["share"], 50.0 / 90.0, places=3)

    def test_grey_image_has_no_hue(self):
        image = np.full((50, 50, 3), 120, dtype=np.uint8)
        share, hues = cmf.measure_colour(image)
        self.assertEqual(share, 0.0)
        self.assertEqual(hues, [])

    def test_letter_run_ignores_other_groups(self):
        def span(text, size, font, x, y):
            return cmf.Span(text=text, size=size, font=font, flags=0, x0=x, y0=y, x1=x + 2, y1=y + 3, line=0)

        spans = [span("a", 8.0, "F", 1, 1), span("b", 8.0, "F", 50, 1), span("c", 8.0, "F", 1, 40),
                 span("x", 9.0, "G", 5, 5), span("y", 9.0, "G", 9, 5)]
        bands = cmf.find_letters(spans)
        self.assertEqual(["".join(l.ch for l in band) for band in bands], ["ab", "c"])

    def test_letter_run_prefers_the_larger_size_on_a_tie(self):
        def span(text, size, x):
            return cmf.Span(text=text, size=size, font="F", flags=0, x0=x, y0=1, x1=x + 2, y1=4, line=0)

        spans = [span("a", 7.0, 1), span("b", 7.0, 20), span("a", 9.0, 40), span("b", 9.0, 60)]
        letters = [l for band in cmf.find_letters(spans) for l in band]
        self.assertEqual([l.span.size for l in letters], [9.0, 9.0])

    def test_alphabet_must_start_at_a(self):
        span = cmf.Span(text="b", size=8.0, font="F", flags=0, x0=1, y0=1, x1=3, y1=4, line=0)
        self.assertEqual(cmf.find_letters([span]), [])


class TestCommandLine(FixtureTestCase):
    def test_missing_file_exits_two(self):
        proc = run_cli(self.dir / "missing.pdf")
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(len(proc.stderr.strip().splitlines()), 1)
        self.assertEqual(proc.stdout, "")

    def test_text_file_exits_two(self):
        path = self.dir / "notes.pdf"
        path.write_text("this is not a pdf\n")
        proc = run_cli(path)
        self.assertEqual(proc.returncode, 2)
        self.assertEqual(len(proc.stderr.strip().splitlines()), 1)


# The needles are built from pieces, so that this file does not hold them as literal text
# and the scan of this file does not match its own pattern definitions.
PERSONAL_PATTERNS = {
    "home path": re.compile("/ho" + "me/"),
    "cluster path": re.compile("/h" + "pc/"),
    "first name part": re.compile("ya" + "ng", re.I),
    "second name part": re.compile("jo" + "on", re.I),
    "institute": re.compile("czbio" + "hub", re.I),
    "email address": re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9-]+(\.[A-Za-z0-9-]+)*\.[A-Za-z]{2,}"),
}


def personal_hits(text):
    """Return the sorted names of the personal-data patterns that match the text."""
    return sorted(name for name, pattern in PERSONAL_PATTERNS.items() if pattern.search(text))


def published_files():
    """Every file of scripts/ and tests/, and the SKILL.md and references/*.md of the skill."""
    files = []
    for folder in ("scripts", "tests"):
        files += sorted(p for p in (SKILL_DIR / folder).iterdir() if p.is_file())
    files.append(SKILL_DIR / "SKILL.md")
    files += sorted((SKILL_DIR / "references").glob("*.md"))
    return files


class TestNoPersonalData(unittest.TestCase):
    def test_every_published_file_is_scanned(self):
        names = set(p.name for p in published_files())
        for expected in ("check_main_figure.py", "compose_figure.py", "test_check_main_figure.py",
                         "test_compose_figure.py", "SKILL.md", "measured-taste.md"):
            self.assertIn(expected, names)

    def test_published_files_hold_no_personal_data(self):
        for path in published_files():
            hits = personal_hits(path.read_text(encoding="utf-8", errors="replace"))
            self.assertEqual(hits, [], "%s matches %s" % (path.name, hits))

    def test_each_pattern_matches_a_sample_and_clean_text_matches_none(self):
        samples = {
            "home path": "see /ho" + "me/someone/file",
            "cluster path": "in /h" + "pc/projects/x",
            "first name part": "Ya" + "ng wrote it",
            "second name part": "the Jo" + "on lab",
            "institute": "someone at CZBIO" + "HUB",
            "email address": "write to someone" + "@" + "example.org",
        }
        self.assertEqual(sorted(samples), sorted(PERSONAL_PATTERNS))
        for name, text in samples.items():
            self.assertEqual(personal_hits(text), [name], text)
        self.assertEqual(personal_hits("The panel letters use 8 pt type. @property and @dataclass are fine."), [])


if __name__ == "__main__":
    unittest.main()
