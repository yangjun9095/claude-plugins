#!/usr/bin/env python3
"""Check the composition of one main-figure PDF against house ranges.

The script measures the geometry, type, panel letters, spacing, colour, frames,
text volume, images and strokes of one page. It compares each measure with the
range measured on exemplar figures. It prints one verdict per check: PASS, WARN,
FAIL or INFO.

The exemplar ranges come from 7 figures (4 papers, 3 labs). The sample is small.
Read a WARN as a prompt to look at the figure. Do not read it as proof of a defect.

Exit status: 1 when any check FAILs, 2 when the file cannot be opened, else 0.
Every length in the output is in millimetres. Type sizes are in points.
Dependencies: PyMuPDF (import fitz) and numpy.
"""

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass
from typing import List, Optional

import numpy as np

import fitz

# ---------------------------------------------------------------------------
# Constants. Each one has a comment that says where the value comes from.
# ---------------------------------------------------------------------------

MM_PER_PT = 25.4 / 72.0  # Definition of the point.
INK_DPI = 200  # House rule: render resolution for the ink checks.
COLOUR_DPI = 100  # House rule: render resolution for the colour checks.
INK_LEVEL = 245  # House rule: a grey pixel with a value below this is ink.
SIZE_STEP_PT = 0.25  # House rule: type sizes are rounded to this step.

# Geometry
SLOT_TOL_MM = 0.5  # House rule: the typesetter rescales a figure that misses the slot by more.
SLOT_INK_MIN_SHARE = 0.78  # Exemplar minimum of ink width / slot width (7 figures; median 0.86).
SLOT_INK_MAX_SHARE = 1.01  # Exemplar maximum of ink width / slot width (7 figures).
ASPECT_RANGE = (1.30, 4.63)  # Exemplar range of width / height (7 figures).
ASPECT_MEDIAN = 2.39  # Exemplar median of width / height.
INK_SHARE_RANGE = (0.13, 0.51)  # Exemplar range of the share of ink pixels.
INK_SHARE_MEDIAN = 0.20  # Exemplar median of the share of ink pixels.
EMPTY_MAX = 0.225  # Exemplar maximum of the largest empty rectangle (7 figures; median 0.084).
EMPTY_CELL_MM = 1.0  # House rule: the empty-rectangle search runs on cells of this size.

# Type
SIZES_RANGE = (2, 5)  # Exemplar range by this checker's count (7 figures; 6 of 7 use 4 or fewer).
SIZES_MEDIAN = 3  # Exemplar median of the number of distinct type sizes.
SIZES_MAX = 4  # House rule: WARN above this; 6 of 7 exemplars stay at or under it.
SMALLEST_RANGE_PT = (3.0, 6.0)  # Exemplar smallest label, as reduced for the journal.

# Panel letters
LETTER_SIZE_RANGE_PT = (6.0, 8.0)  # Exemplar range of the panel-letter size.
LETTER_SIZE_MEDIAN_PT = 8.0  # Exemplar median of the panel-letter size.
LETTER_SIZE_WARN_PT = (6.0, 9.0)  # Author: letters of 6 to 9 pt pass.
LETTER_BAND_MM = 3.0  # House rule: letters whose top y differs by less belong to one band.
BASELINE_SPREAD_MAX_MM = 0.3  # House rule: FAIL when letters in one band spread more than this.
CLEARANCE_MIN_MM = 1.0  # House rule: WARN when the gap from letter to title is smaller.
OVERLAP_MIN_FRACTION = 0.5  # House rule: a title must overlap the letter by half its height.
FLUSH_TOLERANCE_MM = 0.2  # House rule: text may stand this far left of the letter.
# Chosen here: how far left of its letter a panel reaches. It stays below the 4 mm
# minimum gap between panels, so text of the panel on the left is not taken in.
COLUMN_SEARCH_MARGIN_MM = 3.0
# Chosen here: a title starts at most this far right of its letter. Text farther away
# belongs to the next panel and not to this letter.
TITLE_MAX_GAP_MM = 10.0
# House rule: a font name that matches this pattern marks a bold font.
BOLD_PATTERN = re.compile(r"(bold|black|heavy|semibold|demi|extrabold)", re.I)
BOLD_FLAG = 16  # House rule: bit 16 of the span flags marks a bold font.

# Spacing
ROW_GAP_RANGE_MM = (2.5, 3.9)  # Exemplar gaps between rows of panels (7 figures; n = 4 gaps).
COL_GAP_RANGE_MM = (4.2, 8.1)  # Exemplar gaps between columns of panels (7 figures; n = 4 gaps).
GAP_EQUAL_TOL_MM = 1.0  # House rule: gaps of one kind may differ by this much.
INTERNAL_RUN_MIN_MM = 0.5  # House rule: shorter blank runs do not count as internal gaps.
# Chosen here: a blank run that starts or ends this close to the edge of a panel region
# counts as touching the edge. The tolerance absorbs the rounding of the pixel grid.
EDGE_TOLERANCE_PX = 2
# Chosen here: a title may rise this far above the ink top of its letter. The run of
# blank rows above a panel still counts from the title and not from the letter.
TITLE_OVERHANG_MM = 1.0

# Colour
COLOUR_SHARE_RANGE = (0.03, 0.12)  # Exemplar range of the coloured share by this method (median 0.06).
COLOUR_SPREAD_MIN = 40  # House rule: a pixel is coloured when max - min of RGB reaches this.
COLOUR_WHITE_LEVEL = 235  # House rule: a pixel with all channels above this is not coloured.
HUE_BINS = 24  # House rule: bins of 15 degrees in the hue histogram.
HUE_MIN_SHARE = 0.04  # House rule: a hue peak holds at least this share of coloured pixels.
HUE_MERGE_DEG = 30.0  # House rule: peaks closer than this merge into one hue.
HUES_RANGE = (1, 5)  # Exemplar range of hue peaks by this method (7 figures).
HUES_MAX = 5  # Exemplar maximum: WARN above it.
LEADING_HUE_RATIO = 1.5  # House rule: the largest hue leads when it is this many times the second.

# Frames
BOX_MIN_WIDTH_MM = 20.0  # House rule: a stroked rectangle at least this wide is a box.
BOX_MIN_HEIGHT_MM = 15.0  # House rule: a stroked rectangle at least this tall is a box.

# Text that belongs in the legend
CAPTION_MIN_WORDS = 6  # House rule: a line with this many words is caption material.
CAPTION_PATTERN = re.compile(
    r"\b(seed|bootstrap|resampl\w*|permutation|per-item"
    r"|see (the )?(SI|Methods|Supplementary)|n\s*=\s*\d|95\s*%)",
    re.I,
)  # House rule: words that mark methods text.
WORDS_MAX = 102  # Exemplar maximum of words in a figure (7 figures; median 56).
WORDS_PER_PANEL_MAX = 41  # Exemplar maximum of words in one panel (5 lettered figures).
TITLE_WORDS_WARN = 5  # House rule: a panel title of this many words belongs in the legend.

# Images and strokes
RASTER_MIN_PPI = 300  # House rule: a placed image below this resolution is soft in print.
STROKE_MEDIAN_RANGE_PT = (0.235, 0.842)  # Exemplar range of the median stroke width.
STROKE_THIN_PT = 0.25  # House rule: strokes thinner than this count as hairlines.

PASS, WARN, FAIL, INFO = "PASS", "WARN", "FAIL", "INFO"


class FigureError(Exception):
    """Raised when the figure cannot be read."""


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------


def make_check(cid, name, verdict, value, house="", detail=""):
    """Return one check result as a dictionary."""
    return {
        "id": cid,
        "name": name,
        "verdict": verdict,
        "value": value,
        "house": house,
        "detail": detail,
    }


def skipped(cid, name, why):
    """Return an INFO check that records why a check did not run."""
    return make_check(cid, name, INFO, "skipped", "", why)


def format_check(check):
    """Format one check as a table line."""
    line = "[%s] %s %s: %s" % (check["verdict"], check["id"], check["name"], check["value"])
    if check["house"]:
        line += " (%s)" % check["house"]
    if check["detail"]:
        line += " " + check["detail"]
    return line


def round_step(value, step=SIZE_STEP_PT):
    """Round a value to the nearest multiple of step."""
    return round(value / step) * step


def plural(count, word):
    """Return the count with the word in singular or plural form."""
    return "%d %s%s" % (count, word, "" if count == 1 else "s")


def fmt_pt(value):
    """Format a type size without trailing zeros."""
    return "%g" % value


def count_words(text):
    """Count the tokens of the text that hold at least one letter or digit."""
    return sum(1 for tok in text.split() if any(ch.isalnum() for ch in tok))


def is_ascii_letter(ch):
    """Return True for one ASCII letter."""
    return len(ch) == 1 and ch.isascii() and ch.isalpha()


def clean_font_name(name):
    """Drop the subset prefix, such as ABCDEF+, from a font name."""
    return re.sub(r"^[A-Z]{6}\+", "", name or "")


def median(values):
    """Return the median of a non-empty list."""
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2.0


def native(obj):
    """Convert numpy values for the JSON writer."""
    if isinstance(obj, np.integer):
        return int(obj)
    if isinstance(obj, np.floating):
        return float(obj)
    if isinstance(obj, np.bool_):
        return bool(obj)
    if isinstance(obj, np.ndarray):
        return obj.tolist()
    raise TypeError("cannot serialise %r" % type(obj))


# ---------------------------------------------------------------------------
# Reading the page
# ---------------------------------------------------------------------------


@dataclass
class Span:
    """One text span. Positions are in mm from the top-left corner of the box."""

    text: str
    size: float
    font: str
    flags: int
    x0: float
    y0: float
    x1: float
    y1: float
    line: int
    #: When the span starts with one character, then white space, then more text (a letter
    #: and its label set in one font), these hold the right edge of that first character and
    #: the left edge of the text after the space, in mm. PyMuPDF joins such neighbours into
    #: one span, so the gap between them can only be read from the characters.
    head_x1: Optional[float] = None
    tail_x0: Optional[float] = None


@dataclass
class Line:
    """One text line made of spans."""

    text: str
    spans: List[Span]
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def words(self):
        return count_words(self.text)


@dataclass
class Letter:
    """One panel letter."""

    ch: str
    span: Span
    merged: bool
    band: int = 0
    col: int = 0
    region: Optional[tuple] = None
    ink_top: int = 0
    ink_left: int = 0
    gap_mm: Optional[float] = None
    neighbour: Optional[Span] = None
    title: str = ""

    @property
    def x(self):
        return self.span.x0

    @property
    def bold(self):
        return bool(BOLD_PATTERN.search(self.span.font) or (self.span.flags & BOLD_FLAG))


def open_page(path, page_no):
    """Open the PDF and return the document and the page."""
    try:
        doc = fitz.open(path)
    except Exception as exc:  # PyMuPDF raises several error types.
        raise FigureError("cannot open %s: %s" % (path, str(exc).splitlines()[0] if str(exc) else exc))
    if not doc.is_pdf:
        raise FigureError("cannot open %s: not a PDF file" % path)
    if page_no < 1 or page_no > doc.page_count:
        raise FigureError("%s has %d page(s); page %d does not exist" % (path, doc.page_count, page_no))
    return doc, doc[page_no - 1]


def box_rect(page, clip_mm):
    """Return the measured box in points. The default is the whole page."""
    if clip_mm is None:
        return fitz.Rect(page.rect)
    x0, y0, x1, y1 = [v / MM_PER_PT for v in clip_mm]
    rect = fitz.Rect(x0, y0, x1, y1) & page.rect
    if rect.is_empty or rect.width <= 0 or rect.height <= 0:
        raise FigureError("the clip region is empty or lies outside the page")
    return rect


def render(page, rect, dpi, gray):
    """Render the box. Pixel (0, 0) is the top-left corner of the box."""
    scale = dpi / 72.0
    matrix = fitz.Matrix(scale, 0, 0, scale, -rect.x0 * scale, -rect.y0 * scale)
    colorspace = fitz.csGRAY if gray else fitz.csRGB
    pix = page.get_pixmap(matrix=matrix, clip=rect, colorspace=colorspace, alpha=False)
    flat = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.stride)
    arr = flat[:, : pix.width * pix.n].reshape(pix.height, pix.width, pix.n)
    return arr[:, :, 0] if gray else arr


def head_and_tail(chars):
    """(right edge of the first character, left edge of the text after the first space).

    Both are in PDF points. Return (None, None) unless the characters read: one visible
    character, then white space, then a visible character.
    """
    visible = [i for i, c in enumerate(chars) if c["c"].strip()]
    if len(visible) < 2:
        return None, None
    first, second = visible[0], visible[1]
    between = chars[first + 1:second]
    if not between or any(c["c"].strip() for c in between):
        return None, None
    return chars[first]["bbox"][2], chars[second]["bbox"][0]


def read_text(page, rect):
    """Return the spans and lines whose centre lies in the box."""
    flags = fitz.TEXTFLAGS_RAWDICT & ~fitz.TEXT_PRESERVE_IMAGES
    raw = page.get_text("rawdict", flags=flags)
    spans, lines = [], []
    for block in raw["blocks"]:
        if block.get("type") != 0:
            continue
        for ln in block["lines"]:
            line_spans, pieces = [], []
            index = len(lines)
            for sp in ln["spans"]:
                chars = sp.get("chars", [])
                text = "".join(c["c"] for c in chars)
                visible = [c for c in chars if c["c"].strip()]
                if not visible:
                    pieces.append(text)
                    continue
                x0 = min(c["bbox"][0] for c in visible)
                x1 = max(c["bbox"][2] for c in visible)
                y0, y1 = sp["bbox"][1], sp["bbox"][3]
                centre_x, centre_y = (x0 + x1) / 2.0, (y0 + y1) / 2.0
                if not (rect.x0 <= centre_x <= rect.x1 and rect.y0 <= centre_y <= rect.y1):
                    continue
                pieces.append(text)
                head_x1, tail_x0 = head_and_tail(chars)
                line_spans.append(
                    Span(
                        text=text.strip(),
                        size=round_step(sp["size"]),
                        font=sp["font"],
                        flags=sp["flags"],
                        x0=(x0 - rect.x0) * MM_PER_PT,
                        y0=(y0 - rect.y0) * MM_PER_PT,
                        x1=(x1 - rect.x0) * MM_PER_PT,
                        y1=(y1 - rect.y0) * MM_PER_PT,
                        line=index,
                        head_x1=None if head_x1 is None else (head_x1 - rect.x0) * MM_PER_PT,
                        tail_x0=None if tail_x0 is None else (tail_x0 - rect.x0) * MM_PER_PT,
                    )
                )
            if not line_spans:
                continue
            lines.append(
                Line(
                    text="".join(pieces).strip(),
                    spans=line_spans,
                    x0=min(s.x0 for s in line_spans),
                    y0=min(s.y0 for s in line_spans),
                    x1=max(s.x1 for s in line_spans),
                    y1=max(s.y1 for s in line_spans),
                )
            )
            spans.extend(line_spans)
    return spans, lines


# ---------------------------------------------------------------------------
# Panel letters
# ---------------------------------------------------------------------------


def reading_order(items, top_of, x_of):
    """Group items into bands of similar top y. Sort each band by x."""
    bands = []
    for item in sorted(items, key=top_of):
        if bands and top_of(item) - top_of(bands[-1][0]) <= LETTER_BAND_MM:
            bands[-1].append(item)
        else:
            bands.append([item])
    return [sorted(band, key=x_of) for band in bands]


def alphabet_run(ordered):
    """Return the longest run a, b, c ... (or A, B, C ...) found in reading order."""
    best = []
    for first in ("a", "A"):
        run, expect = [], first
        for cand in ordered:
            if cand.ch == expect:
                run.append(cand)
                expect = chr(ord(expect) + 1)
        if len(run) > len(best):
            best = run
    return best


def find_letters(spans):
    """Find the panel letters. Return a list of bands, each a list of Letter."""
    groups = {}
    for span in spans:
        text = span.text
        if is_ascii_letter(text):
            cand = Letter(ch=text, span=span, merged=False)
        elif len(text) > 2 and is_ascii_letter(text[0]) and text[1].isspace():
            cand = Letter(ch=text[0], span=span, merged=True)
        else:
            continue
        groups.setdefault((span.size, span.font), []).append(cand)
    best_run, best_key = [], None
    for key in sorted(groups):
        ordered = [
            c
            for band in reading_order(groups[key], lambda c: c.span.y0, lambda c: c.x)
            for c in band
        ]
        run = alphabet_run(ordered)
        if len(run) > len(best_run) or (
            run and len(run) == len(best_run) and key[0] > best_key[0]
        ):
            best_run, best_key = run, key
    if not best_run:
        return []
    bands = reading_order(best_run, lambda c: c.span.y0, lambda c: c.x)
    for bi, band in enumerate(bands):
        for ci, letter in enumerate(band):
            letter.band, letter.col = bi, ci
    return bands


def panel_regions(bands, box_w, box_h):
    """Give each letter its panel region (x0, y0, x1, y1) in mm."""
    for bi, band in enumerate(bands):
        next_top = min(l.span.y0 for l in bands[bi + 1]) if bi + 1 < len(bands) else box_h
        for ci, letter in enumerate(band):
            right = band[ci + 1].x if ci + 1 < len(band) else box_w
            prev_x = band[ci - 1].x if ci > 0 else 0.0
            left = max(letter.x - COLUMN_SEARCH_MARGIN_MM, prev_x)
            letter.region = (left, letter.span.y0, right, next_top)


def link_titles(letters, spans, lines):
    """Find the neighbour span and the title text on the right of each letter.

    A neighbour counts only when it lies inside the panel region of the letter and starts
    at most TITLE_MAX_GAP_MM right of the letter. A letter without a title takes none.
    """
    for letter in letters:
        span = letter.span
        height = span.y1 - span.y0
        if letter.merged:
            line = lines[span.line]
            parts = [span.text[1:].strip()] + [
                s.text for s in line.spans if s is not span and s.x0 > span.x0
            ]
            letter.title = " ".join(p for p in parts if p)
            if span.head_x1 is not None and span.tail_x0 is not None:
                letter.gap_mm = span.tail_x0 - span.head_x1
            continue
        left, top, right_edge, bottom = letter.region
        right = [s for s in spans if s is not span and s.x0 > span.x0 + 1e-6]
        for cand in sorted(right, key=lambda s: s.x0):
            overlap = min(span.y1, cand.y1) - max(span.y0, cand.y0)
            own_panel = (
                left <= cand.x0 < right_edge
                and top <= (cand.y0 + cand.y1) / 2.0 < bottom
                and cand.x0 - span.x1 <= TITLE_MAX_GAP_MM
            )
            if overlap >= OVERLAP_MIN_FRACTION * height and own_panel:
                letter.neighbour = cand
                letter.gap_mm = cand.x0 - span.x1
                line = lines[cand.line]
                letter.title = " ".join(
                    s.text for s in line.spans if s is not span and s.x0 >= cand.x0 - 1e-6
                )
                break


# ---------------------------------------------------------------------------
# Ink geometry
# ---------------------------------------------------------------------------


def largest_empty_rectangle(blank):
    """Find the largest all-True rectangle of a 2-D bool array.

    Return (area, top, left, height, width) in cells. The method keeps a
    histogram of blank heights per column and scans it with a stack.
    """
    rows = blank.tolist()
    n_cols = len(rows[0]) if rows else 0
    heights = [0] * n_cols
    best = (0, 0, 0, 0, 0)
    for r, row in enumerate(rows):
        for c in range(n_cols):
            heights[c] = heights[c] + 1 if row[c] else 0
        stack = []
        for c in range(n_cols + 1):
            h = heights[c] if c < n_cols else 0
            start = c
            while stack and stack[-1][1] >= h:
                s, sh = stack.pop()
                area = sh * (c - s)
                if area > best[0]:
                    best = (area, r - sh + 1, s, sh, c - s)
                start = s
            stack.append((start, h))
    return best


def cell_grid(ink, px_per_mm, cell_mm):
    """Return the ink count of each cell of the given size."""
    height, width = ink.shape
    n_rows = max(1, int(round(height / (px_per_mm * cell_mm))))
    n_cols = max(1, int(round(width / (px_per_mm * cell_mm))))
    rows_at = np.minimum((np.arange(n_rows) * px_per_mm * cell_mm).astype(int), height - 1)
    cols_at = np.minimum((np.arange(n_cols) * px_per_mm * cell_mm).astype(int), width - 1)
    rows_at, cols_at = np.unique(rows_at), np.unique(cols_at)
    counts = np.add.reduceat(ink.astype(np.int32), rows_at, axis=0)
    return np.add.reduceat(counts, cols_at, axis=1)


def blank_run_above(profile, row, overhang_px):
    """Return the blank run that ends just above a row as (start, end) rows.

    The run may start after a short stretch of ink, such as a title that rises
    above its panel letter. A run of zero length means ink touches the row.
    """
    i = row - 1
    skipped_rows = 0
    while i >= 0 and profile[i]:
        if skipped_rows >= overhang_px:
            return (row, row)
        i -= 1
        skipped_rows += 1
    end = i + 1
    while i >= 0 and not profile[i]:
        i -= 1
    return (i + 1, end)


def blank_runs(profile, start, stop):
    """Return all runs of blank rows between two rows as (start, end) pairs."""
    runs, i = [], start
    while i < stop:
        if profile[i]:
            i += 1
            continue
        j = i
        while j < stop and not profile[j]:
            j += 1
        runs.append((i, j))
        i = j
    return runs


def region_pixels(region, ppm, shape):
    """Return (row0, row1, col0, col1) of a region (x0, y0, x1, y1) in mm, clipped to the image."""
    left, top, right, bottom = region
    height, width = shape
    c0 = min(max(int(math.floor(left * ppm)), 0), width - 1)
    c1 = min(max(int(math.ceil(right * ppm)), c0 + 1), width)
    r0 = min(max(int(math.floor(top * ppm)), 0), height - 1)
    r1 = min(max(int(math.ceil(bottom * ppm)), r0 + 1), height)
    return r0, r1, c0, c1


def widest_inner_run(profile, ppm):
    """Return the longest blank run of a profile as (length_mm, start, end), or None.

    A run that touches either end of the profile is the white around the region, not white
    inside it, so it does not count. Runs shorter than INTERNAL_RUN_MIN_MM do not count.
    """
    best = None
    for start, end in blank_runs(profile, 0, len(profile)):
        if start <= EDGE_TOLERANCE_PX or end >= len(profile) - EDGE_TOLERANCE_PX:
            continue
        length = (end - start) / ppm
        if length >= INTERNAL_RUN_MIN_MM and (best is None or length > best[0]):
            best = (length, start, end)
    return best


# ---------------------------------------------------------------------------
# Colour
# ---------------------------------------------------------------------------


def circular_distance(a, b):
    """Return the distance between two angles in degrees, on a circle."""
    diff = abs(a - b) % 360.0
    return min(diff, 360.0 - diff)


def measure_colour(rgb):
    """Return the share of coloured pixels and the list of hues."""
    pixels = rgb.reshape(-1, 3).astype(np.int16)
    peak, low = pixels.max(axis=1), pixels.min(axis=1)
    coloured = ((peak - low) >= COLOUR_SPREAD_MIN) & ~(pixels > COLOUR_WHITE_LEVEL).all(axis=1)
    n_coloured = int(coloured.sum())
    share = n_coloured / float(len(pixels)) if len(pixels) else 0.0
    if n_coloured == 0:
        return share, []
    px = pixels[coloured]
    spread = (peak - low)[coloured].astype(float)
    r, g, b = px[:, 0].astype(float), px[:, 1].astype(float), px[:, 2].astype(float)
    is_red = px[:, 0] == peak[coloured]
    is_green = ~is_red & (px[:, 1] == peak[coloured])
    hue = np.where(is_red, ((g - b) / spread) % 6.0, np.where(is_green, (b - r) / spread + 2.0, (r - g) / spread + 4.0))
    hue = (hue * 60.0) % 360.0
    width = 360.0 / HUE_BINS
    hist = np.bincount(np.minimum((hue / width).astype(int), HUE_BINS - 1), minlength=HUE_BINS)
    hist = hist.astype(float) / n_coloured
    smooth = (np.roll(hist, 1) + 2.0 * hist + np.roll(hist, -1)) / 4.0
    peaks = [
        i
        for i in range(HUE_BINS)
        if smooth[i] > smooth[i - 1]
        and smooth[i] >= smooth[(i + 1) % HUE_BINS]
        and smooth[i] >= HUE_MIN_SHARE
    ]
    kept = []
    for i in sorted(peaks, key=lambda k: -smooth[k]):
        centre = (i + 0.5) * width
        if all(circular_distance(centre, k) >= HUE_MERGE_DEG for k in kept):
            kept.append(centre)
    if not kept:
        return share, []
    centres = np.array(kept)
    diff = np.abs(hue[:, None] - centres[None, :])
    owner = np.minimum(diff, 360.0 - diff).argmin(axis=1)
    hues = []
    for k in range(len(kept)):
        mine = owner == k
        count = int(mine.sum())
        if count == 0:
            continue
        angles = np.radians(hue[mine])
        mean_angle = math.degrees(math.atan2(np.sin(angles).mean(), np.cos(angles).mean())) % 360.0
        rgb_med = np.median(px[mine], axis=0).astype(int)
        hues.append(
            {
                "centre_deg": round(mean_angle, 1),
                "share": count / float(n_coloured),
                "hex": "#%02x%02x%02x" % tuple(int(v) for v in rgb_med),
            }
        )
    hues.sort(key=lambda h: -h["share"])
    return share, hues


# ---------------------------------------------------------------------------
# Drawings
# ---------------------------------------------------------------------------


def is_white(colour):
    """Return True when a stroke colour is white."""
    if colour is None:
        return False
    if len(colour) == 4:
        return all(v <= 0.01 for v in colour)
    return all(v >= 0.99 for v in colour)


def rectangle_of(items):
    """Return the Rect of a path that is one rectangle, else None."""
    if len(items) == 1 and items[0][0] == "re":
        return fitz.Rect(items[0][1])
    if len(items) == 4 and all(it[0] == "l" for it in items):
        tol = 0.05
        for k, it in enumerate(items):
            nxt = items[(k + 1) % 4]
            if abs(it[2].x - nxt[1].x) > tol or abs(it[2].y - nxt[1].y) > tol:
                return None
            horizontal = abs(it[1].y - it[2].y) <= tol
            vertical = abs(it[1].x - it[2].x) <= tol
            if not (horizontal or vertical) or (horizontal and vertical):
                return None
        xs = [it[1].x for it in items]
        ys = [it[1].y for it in items]
        return fitz.Rect(min(xs), min(ys), max(xs), max(ys))
    return None


# ---------------------------------------------------------------------------
# The checker
# ---------------------------------------------------------------------------


class Figure:
    """Hold the measured box and run every check on it."""

    def __init__(self, path, page_no, clip_mm, slot_mm, max_height_mm, min_pt, case, letter_weight, panel):
        self.path = path
        self.page_no = page_no
        self.slot_mm = slot_mm
        self.max_height_mm = max_height_mm
        self.min_pt = min_pt
        self.case = case
        self.letter_weight = letter_weight
        self.panel = panel
        self.doc, self.page = open_page(path, page_no)
        # Text, drawings and images come in unrotated page coordinates, and the box and the
        # render follow the rotation. Remove the rotation in memory so that all of them agree.
        self.rotation = self.page.rotation
        if self.rotation:
            try:
                self.page.remove_rotation()
            except Exception as exc:  # PyMuPDF raises several error types.
                raise FigureError("cannot remove the page rotation of %s: %s" % (path, exc))
        self.rect = box_rect(self.page, clip_mm)
        self.w_mm = self.rect.width * MM_PER_PT
        self.h_mm = self.rect.height * MM_PER_PT
        self.ppm = INK_DPI / 25.4
        self.ink = render(self.page, self.rect, INK_DPI, True) < INK_LEVEL
        self.rgb = render(self.page, self.rect, COLOUR_DPI, False)
        self.spans, self.lines = read_text(self.page, self.rect)
        self.bands = find_letters(self.spans)
        self.letters = [l for band in self.bands for l in band]
        panel_regions(self.bands, self.w_mm, self.h_mm)
        link_titles(self.letters, self.spans, self.lines)
        self.checks = []
        self.measures = {"page_rotation_deg": self.rotation}

    # -- geometry mm of a rectangle on the page, from points
    def to_box_mm(self, rect):
        return (
            (rect.x0 - self.rect.x0) * MM_PER_PT,
            (rect.y0 - self.rect.y0) * MM_PER_PT,
            (rect.x1 - self.rect.x0) * MM_PER_PT,
            (rect.y1 - self.rect.y0) * MM_PER_PT,
        )

    def in_box(self, rect):
        """Return True when the centre of a page rectangle lies in the box."""
        cx, cy = (rect.x0 + rect.x1) / 2.0, (rect.y0 + rect.y1) / 2.0
        return self.rect.x0 <= cx <= self.rect.x1 and self.rect.y0 <= cy <= self.rect.y1

    def add(self, *args, **kwargs):
        self.checks.append(make_check(*args, **kwargs))

    def run(self):
        self.geometry()
        self.type_checks()
        self.letter_checks()
        self.spacing_checks()
        self.colour_checks()
        self.frame_checks()
        self.text_checks()
        self.image_checks()
        return {
            "file": self.path,
            "box_mm": [round(self.w_mm, 2), round(self.h_mm, 2)],
            "checks": self.checks,
            "measures": self.measures,
        }

    # -- geometry ----------------------------------------------------------

    def geometry(self):
        cols = np.nonzero(self.ink.any(axis=0))[0]
        extent = (cols[-1] - cols[0] + 1) / self.ppm if cols.size else 0.0
        self.measures["ink_extent_mm"] = round(float(extent), 2)
        width = "%.1f mm" % self.w_mm
        note = ""
        if self.rotation:
            note = ("NOTE: the page carries /Rotate %d; the checker removed the rotation in memory "
                    "before it measured, and the figures show the page as displayed" % self.rotation)
        slot_house = "slot %g mm" % self.slot_mm if self.slot_mm is not None else ""
        share_house = "%s; exemplars %.2f to %.2f of the slot width" % (
            slot_house, SLOT_INK_MIN_SHARE, SLOT_INK_MAX_SHARE)
        if self.slot_mm is None:
            detail, verdict, house = "no slot given (--slot-mm)", INFO, ""
        elif abs(self.w_mm - self.slot_mm) > SLOT_TOL_MM:
            detail, verdict = "the typesetter will rescale the figure", FAIL
            house = "slot %g mm +/- %g" % (self.slot_mm, SLOT_TOL_MM)
        elif extent < SLOT_INK_MIN_SHARE * self.slot_mm:
            detail = ("the ink covers %.1f mm, %.0f%% of the slot; the figure leaves the slot unused"
                      % (extent, 100.0 * extent / self.slot_mm))
            verdict, house = WARN, share_house
        else:
            detail, verdict, house = "the ink covers %.1f mm of the slot" % extent, PASS, share_house
        self.add("G1", "width", verdict, width, house, "; ".join(part for part in (detail, note) if part))

        height = "%.1f mm" % self.h_mm
        if self.max_height_mm is None:
            self.add("G2", "height", INFO, height, "", "no maximum given (--max-height-mm)")
        elif self.h_mm > self.max_height_mm:
            self.add("G2", "height", FAIL, height, "at most %g mm" % self.max_height_mm, "the figure is too tall")
        else:
            self.add("G2", "height", PASS, height, "at most %g mm" % self.max_height_mm)

        if self.panel:
            self.checks.append(skipped("G3", "aspect", "--panel: the panel is not the composed figure"))
        else:
            aspect = self.w_mm / self.h_mm
            house = "%.2f to %.2f, median %.2f" % (ASPECT_RANGE + (ASPECT_MEDIAN,))
            inside = ASPECT_RANGE[0] <= aspect <= ASPECT_RANGE[1]
            self.add("G3", "aspect", PASS if inside else WARN, "%.2f" % aspect, house,
                     "%s found by their letters" % plural(len(self.letters), "panel"))

        share = float(self.ink.mean())
        self.measures["ink_share"] = round(share, 4)
        house = "%.2f to %.2f, median %.2f" % (INK_SHARE_RANGE + (INK_SHARE_MEDIAN,))
        inside = INK_SHARE_RANGE[0] <= share <= INK_SHARE_RANGE[1]
        self.add("G4", "ink", PASS if inside else WARN, "%.2f" % share, house)

        self.empty_check()

    def empty_check(self):
        counts = cell_grid(self.ink, self.ppm, EMPTY_CELL_MM)
        area, top, left, h_cells, w_cells = largest_empty_rectangle(counts == 0)
        share = area / float(counts.size)
        empty = {
            "share": round(share, 4),
            "x0_mm": left * EMPTY_CELL_MM,
            "y0_mm": top * EMPTY_CELL_MM,
            "x1_mm": (left + w_cells) * EMPTY_CELL_MM,
            "y1_mm": (top + h_cells) * EMPTY_CELL_MM,
        }
        self.measures["empty"] = empty
        detail = "from x=%.0f, y=%.0f mm, %.0f x %.0f mm" % (
            empty["x0_mm"], empty["y0_mm"], w_cells * EMPTY_CELL_MM, h_cells * EMPTY_CELL_MM)
        self.add("G5", "empty", WARN if share > EMPTY_MAX else PASS, "%.1f%% of the box" % (100 * share),
                 "at most %.0f%%" % (100 * EMPTY_MAX), detail)

    # -- type ----------------------------------------------------------------

    def type_checks(self):
        table = {}
        for span in self.spans:
            entry = table.setdefault(span.size, [0, span.text[:40]])
            entry[0] += len(span.text)
        sizes = [{"size_pt": s, "chars": table[s][0], "example": table[s][1]} for s in sorted(table)]
        self.measures["sizes"] = sizes
        if not sizes:
            self.add("T1", "sizes", INFO, "no text", "", "the box holds no text")
            self.add("T2", "smallest", INFO, "no text", "", "the box holds no text")
        else:
            house = "%d to %d, median %d" % (SIZES_RANGE + (SIZES_MEDIAN,))
            listing = ", ".join(fmt_pt(s["size_pt"]) for s in sizes)
            self.add("T1", "sizes", WARN if len(sizes) > SIZES_MAX else PASS, plural(len(sizes), "size"), house,
                     "%s pt" % listing)
            smallest = sizes[0]["size_pt"]
            house = "at least %g pt" % self.min_pt
            detail = "exemplar smallest label %.1f to %.1f pt (journal-reduced)" % SMALLEST_RANGE_PT
            self.add("T2", "smallest", FAIL if smallest < self.min_pt else PASS, "%s pt" % fmt_pt(smallest),
                     house, detail)
        fonts = self.doc.get_page_fonts(self.page_no - 1, full=True)
        self.checks.append(check_fonts(fonts))
        self.measures["fonts"] = [
            {"name": clean_font_name(f[3]), "type": f[2], "ext": f[1]} for f in fonts
        ]

    # -- panel letters ---------------------------------------------------------

    def letter_checks(self):
        letters = self.letters
        self.measures["letters"] = [
            {
                "letter": l.ch,
                "merged": l.merged,
                "size_pt": l.span.size,
                "font": clean_font_name(l.span.font),
                "bold": l.bold,
                "x_mm": round(l.x, 2),
                "y_mm": round(l.span.y0, 2),
                "band": l.band,
                "gap_mm": None if l.gap_mm is None else round(l.gap_mm, 2),
                "title": l.title,
                "title_words": count_words(l.title),
            }
            for l in letters
        ]
        word = "".join(l.ch for l in letters)
        if self.panel:
            if letters:
                self.add("L1", "found", INFO, '"%s"' % word, "", "letter drawn inside the panel")
            else:
                self.add("L1", "found", INFO, "none", "", "no letter inside the panel; the composer adds it")
        elif letters:
            self.add("L1", "found", PASS, '"%s"' % word, "", "%s in %s, %s pt"
                     % (plural(len(letters), "letter"), plural(len(self.bands), "band"), fmt_pt(letters[0].span.size)))
        else:
            self.add("L1", "found", FAIL, "none", "", "no panel letter found; letters drawn as outlines are "
                     "invisible to this check")
        why = "no letter inside the panel" if self.panel else "no letters found (see L1)"
        layout_why = "--panel: the panel carries no layout of letters"
        steps = (
            ("L2", "weight", self.weight_check, why),
            ("L3", "case", self.case_check, why),
            ("L4", "size", self.size_check, why),
            ("L5", "baseline", self.baseline_check, layout_why if self.panel else why),
            ("L6", "clearance", self.clearance_check, why),
            ("L7", "flush left", self.flush_check, layout_why if self.panel else why),
        )
        for cid, name, step, reason in steps:
            layout_check = cid in ("L5", "L7")
            if not letters or (self.panel and layout_check):
                self.checks.append(skipped(cid, name, reason))
            else:
                step()

    def weight_check(self):
        letters = self.letters
        fonts = sorted(set(clean_font_name(l.span.font) for l in letters))
        names = "font %s" % ", ".join(fonts)
        not_bold = [l.ch for l in letters if not l.bold]
        bold = [l.ch for l in letters if l.bold]
        mode = self.letter_weight
        if mode == "any":
            self.add("L2", "weight", INFO, "any weight accepted", "any", names)
        elif mode == "regular":
            if bold:
                self.add("L2", "weight", FAIL, "bold: %s" % ",".join(bold), "regular",
                         "%s; the author asks for regular letters" % names)
            else:
                self.add("L2", "weight", PASS, "all regular", "regular", names)
        elif not_bold:
            self.add("L2", "weight", FAIL, "not bold: %s" % ",".join(not_bold), "bold",
                     "%s; panel letters must be bold" % names)
        else:
            self.add("L2", "weight", PASS, "all bold", "bold", names)

    def case_check(self):
        letters = self.letters
        if all(l.ch.islower() for l in letters):
            found = "lower"
        elif all(l.ch.isupper() for l in letters):
            found = "upper"
        else:
            found = "mixed"
        if self.case == "any" or found == self.case:
            self.add("L3", "case", PASS, found, self.case)
        else:
            self.add("L3", "case", WARN, found, self.case,
                     "house style decides (eLife uses capitals)")

    def size_check(self):
        size = self.letters[0].span.size
        lo, hi = LETTER_SIZE_WARN_PT
        house = "%.1f to %.1f pt; exemplars %.1f to %.1f, median %.1f" % (
            lo, hi, LETTER_SIZE_RANGE_PT[0], LETTER_SIZE_RANGE_PT[1], LETTER_SIZE_MEDIAN_PT)
        inside = lo - 1e-9 <= size <= hi + 1e-9
        self.add("L4", "size", PASS if inside else WARN, "%s pt" % fmt_pt(size), house)

    def baseline_check(self):
        spreads = []
        for band in self.bands:
            tops = [l.span.y0 for l in band]
            spreads.append(max(tops) - min(tops))
        worst = max(spreads)
        verdict = FAIL if worst > BASELINE_SPREAD_MAX_MM else PASS
        detail = "" if any(len(b) > 1 for b in self.bands) else "one letter per band; nothing to compare"
        self.add("L5", "baseline", verdict, "%.2f mm spread" % worst,
                 "at most %.1f mm" % BASELINE_SPREAD_MAX_MM, detail)

    def clearance_check(self):
        # A letter set in one span with its label (same font and size) is measured from its
        # characters. Only a merged letter whose gap cannot be read fails.
        unreadable = [l.ch for l in self.letters if l.merged and l.gap_mm is None]
        merged = [l.ch for l in self.letters if l.merged and l.gap_mm is not None]
        gaps = [(l.ch, l.gap_mm) for l in self.letters if l.gap_mm is not None]
        house = "at least %.1f mm" % CLEARANCE_MIN_MM
        listing = ", ".join("%s %.2f mm" % (ch, gap) for ch, gap in gaps)
        if merged:
            listing += "; %s set in one text span with the label" % ",".join(merged)
        if unreadable:
            self.add("L6", "clearance", FAIL, "merged: %s" % ",".join(unreadable), house,
                     "the letter shares one text span with its title and the gap cannot be "
                     "read; set it as its own text" + ("; gaps: " + listing if listing else ""))
        elif not gaps:
            self.add("L6", "clearance", PASS, "no title", house, "no text stands to the right of a letter")
        else:
            smallest = min(g for _, g in gaps)
            verdict = WARN if smallest < CLEARANCE_MIN_MM else PASS
            detail = ("the letter runs into the title; " if verdict == WARN else "") + listing
            self.add("L6", "clearance", verdict, "%.2f mm" % smallest, house, detail)

    def flush_check(self):
        letter_spans = set(id(l.span) for l in self.letters)
        offenders = []
        for letter in self.letters:
            left, top, right, bottom = letter.region
            for span in self.spans:
                if id(span) in letter_spans:
                    continue
                centre_y = (span.y0 + span.y1) / 2.0
                if not (top <= centre_y < bottom and left <= span.x0 < right):
                    continue
                if span.x0 < letter.x - FLUSH_TOLERANCE_MM:
                    offenders.append((letter.ch, span))
        house = "no text left of its letter"
        if offenders:
            detail = "; ".join('letter %s: "%s" at x=%.1f mm stands %.1f mm left' % (
                ch, sp.text[:30], sp.x0, self.letters[[l.ch for l in self.letters].index(ch)].x - sp.x0)
                for ch, sp in offenders)
            self.add("L7", "flush left", WARN, plural(len(offenders), "span"), house, detail)
        else:
            self.add("L7", "flush left", PASS, "0 spans", house)

    # -- spacing -----------------------------------------------------------------

    def spacing_checks(self):
        names = (("S1", "between panels"), ("S2", "hierarchy"), ("S3", "equal"))
        if self.panel:
            for cid, name in names:
                self.checks.append(skipped(cid, name, "--panel: the panel carries no layout of panels"))
            return
        if not self.letters:
            for cid, name in names:
                self.checks.append(skipped(cid, name, "no letters found (see L1)"))
            return
        ink, ppm = self.ink, self.ppm
        height, width = ink.shape
        for letter in self.letters:
            span = letter.span
            c0 = min(max(int(math.floor(span.x0 * ppm)), 0), width - 1)
            c1 = min(max(int(math.ceil(span.x1 * ppm)), c0 + 1), width)
            r0 = min(max(int(math.floor(span.y0 * ppm)), 0), height - 1)
            r1 = min(max(int(math.ceil(span.y1 * ppm)), r0 + 1), height)
            sub = ink[r0:r1, c0:c1]
            rows = np.nonzero(sub.any(axis=1))[0]
            cols = np.nonzero(sub.any(axis=0))[0]
            letter.ink_top = r0 + int(rows[0]) if rows.size else r0
            letter.ink_left = c0 + int(cols[0]) if cols.size else c0
        profile = ink.any(axis=1)
        ink_rows = np.nonzero(profile)[0]
        last_row = int(ink_rows[-1]) + 1 if ink_rows.size else height
        band_top = [min(l.ink_top for l in band) for band in self.bands]
        band_end = band_top[1:] + [last_row]
        overhang = int(round(TITLE_OVERHANG_MM * ppm))

        row_gaps, col_gaps = [], []
        for bi in range(1, len(self.bands)):
            start, end = blank_run_above(profile, band_top[bi], overhang)
            if end > start:
                row_gaps.append({"band": bi, "mode": "full", "letter": None,
                                 "gap_mm": (end - start) / ppm, "y0_mm": start / ppm, "y1_mm": end / ppm})
                continue
            band = self.bands[bi]
            for ci, letter in enumerate(band):
                right = band[ci + 1].x if ci + 1 < len(band) else self.w_mm
                c0 = min(max(int(math.floor(letter.x * ppm)), 0), width - 1)
                c1 = min(max(int(math.ceil(right * ppm)), c0 + 1), width)
                column_profile = ink[:, c0:c1].any(axis=1)
                start, end = blank_run_above(column_profile, letter.ink_top, overhang)
                row_gaps.append({"band": bi, "mode": "column", "letter": letter.ch,
                                 "gap_mm": (end - start) / ppm, "y0_mm": start / ppm, "y1_mm": end / ppm})
        for bi, band in enumerate(self.bands):
            r0, r1 = band_top[bi], band_end[bi]
            if r1 <= r0:
                continue
            column_profile = ink[r0:r1, :].any(axis=0)
            for letter in band[1:]:
                c = letter.ink_left - 1
                run = 0
                while c >= 0 and not column_profile[c]:
                    c -= 1
                    run += 1
                col_gaps.append({"band": bi, "letter": letter.ch, "gap_mm": run / ppm,
                                 "x0_mm": (c + 1) / ppm, "x1_mm": letter.ink_left / ppm})

        panels, widest = [], {"rows": None, "cols": None}
        for letter in self.letters:
            left, top, right, bottom = letter.region
            # The title of the next band may rise above its letter, so stop short of the region end.
            region = (left, top, right, max(top, bottom - TITLE_OVERHANG_MM))
            r0, r1, c0, c1 = region_pixels(region, ppm, ink.shape)
            sub = ink[r0:r1, c0:c1]
            # The letter and its title are the header of the panel. The white between the letter
            # and the title is not a gutter, so the column profile starts below the header.
            header_bottom = max(letter.span.y1, letter.neighbour.y1 if letter.neighbour is not None else 0.0)
            body = min(max(int(math.ceil(header_bottom * ppm)) - r0, 0), r1 - r0)
            found = {"letter": letter.ch, "rows": None, "cols": None}
            run = widest_inner_run(sub.any(axis=1), ppm)
            if run is not None:
                found["rows"] = {"letter": letter.ch, "band": letter.band, "gap_mm": run[0],
                                 "y0_mm": (r0 + run[1]) / ppm, "y1_mm": (r0 + run[2]) / ppm}
            run = widest_inner_run(sub[body:].any(axis=0), ppm)
            if run is not None:
                found["cols"] = {"letter": letter.ch, "band": letter.band, "gap_mm": run[0],
                                 "x0_mm": (c0 + run[1]) / ppm, "x1_mm": (c0 + run[2]) / ppm}
            panels.append(found)
            for direction in ("rows", "cols"):
                entry = found[direction]
                if entry is not None and (widest[direction] is None or entry["gap_mm"] > widest[direction]["gap_mm"]):
                    widest[direction] = entry
        self.measures["gaps"] = {"rows": row_gaps, "cols": col_gaps, "internal": widest, "panels": panels}

        all_gaps = [g["gap_mm"] for g in row_gaps + col_gaps]
        house = "rows %.1f to %.1f mm, columns %.1f to %.1f mm" % (ROW_GAP_RANGE_MM + COL_GAP_RANGE_MM)
        if not all_gaps:
            self.add("S1", "between panels", INFO, "no gap to measure", house, "the figure holds one panel")
        else:
            parts = []
            if row_gaps:
                parts.append("rows " + ", ".join("%.1f" % g["gap_mm"] for g in row_gaps))
            if col_gaps:
                parts.append("columns " + ", ".join("%.1f" % g["gap_mm"] for g in col_gaps))
            outside = []
            for label, gaps, (low, high) in (("rows", row_gaps, ROW_GAP_RANGE_MM),
                                             ("columns", col_gaps, COL_GAP_RANGE_MM)):
                bad = ["%.1f" % g["gap_mm"] for g in gaps if not low <= g["gap_mm"] <= high]
                if bad:
                    outside.append("%s outside %.1f to %.1f mm: %s" % (label, low, high, ", ".join(bad)))
            self.add("S1", "between panels", WARN if outside else PASS, "; ".join(parts) + " mm", house,
                     "; ".join(outside))

        self.hierarchy_check(row_gaps, col_gaps, widest)

        row_values = [g["gap_mm"] for g in row_gaps]
        col_values = [g["gap_mm"] for g in col_gaps]
        spread_rows = max(row_values) - min(row_values) if len(row_values) > 1 else None
        spread_cols = max(col_values) - min(col_values) if len(col_values) > 1 else None
        house = "within %.1f mm" % GAP_EQUAL_TOL_MM
        if spread_rows is None and spread_cols is None:
            self.add("S3", "equal", INFO, "fewer than two gaps of one kind", house)
        else:
            bad = []
            if spread_rows is not None and spread_rows > GAP_EQUAL_TOL_MM:
                bad.append("row gaps differ by %.1f mm" % spread_rows)
            if spread_cols is not None and spread_cols > GAP_EQUAL_TOL_MM:
                bad.append("column gaps differ by %.1f mm" % spread_cols)
            shown = ", ".join(
                "%s %.1f mm" % (label, spread)
                for label, spread in (("rows", spread_rows), ("columns", spread_cols))
                if spread is not None
            )
            self.add("S3", "equal", WARN if bad else PASS, "spread " + shown, house, "; ".join(bad))

    def hierarchy_check(self, row_gaps, col_gaps, widest):
        """S2: the white between panels must be wider than the white inside a panel.

        FAIL when a gap between panels is not larger than the widest internal white in the
        same direction. WARN when the widest internal white in one direction is larger than
        the smallest gap between panels in the other direction.
        """
        gaps = {"rows": [g["gap_mm"] for g in row_gaps], "cols": [g["gap_mm"] for g in col_gaps]}
        word = {"rows": "row", "cols": "column"}
        plural_word = {"rows": "rows", "cols": "columns"}
        other = {"rows": "cols", "cols": "rows"}
        house = "gap between panels larger than any white inside a panel"
        if not gaps["rows"] and not gaps["cols"]:
            self.add("S2", "hierarchy", INFO, "no gap to measure", "", "the figure holds one panel")
            return

        def where(direction):
            white = widest[direction]
            axis, lo, hi = (("y", white["y0_mm"], white["y1_mm"]) if direction == "rows"
                            else ("x", white["x0_mm"], white["x1_mm"]))
            return "panel %s, %s: widest internal white %.1f mm at %s=%.1f to %.1f mm" % (
                white["letter"], plural_word[direction], white["gap_mm"], axis, lo, hi)

        fails, warns = [], []
        for direction in ("rows", "cols"):
            white = widest[direction]
            if white is None:
                continue
            same, across = gaps[direction], gaps[other[direction]]
            if same and min(same) <= white["gap_mm"]:
                fails.append((direction, "%s gap %.1f mm <= internal white %.1f mm" % (
                    word[direction], min(same), white["gap_mm"])))
            if across and white["gap_mm"] > min(across):
                warns.append((direction, "internal %s white %.1f mm > %s gap %.1f mm" % (
                    word[direction], white["gap_mm"], word[other[direction]], min(across))))
        if fails:
            self.add("S2", "hierarchy", FAIL, "; ".join(text for _, text in fails), house,
                     "; ".join(where(d) for d, _ in fails) + "; a reader cannot see where a panel ends")
        elif warns:
            self.add("S2", "hierarchy", WARN, "; ".join(text for _, text in warns), house,
                     "; ".join(where(d) for d, _ in warns)
                     + "; a gutter inside a panel is wider than the boundary between panels")
        else:
            smallest = min(gaps["rows"] + gaps["cols"])
            present = [d for d in ("rows", "cols") if widest[d] is not None]
            if not present:
                self.add("S2", "hierarchy", PASS,
                         "no internal blank run of %.1f mm or more" % INTERNAL_RUN_MIN_MM, house,
                         "smallest gap between panels %.1f mm" % smallest)
            else:
                biggest = max(present, key=lambda d: widest[d]["gap_mm"])
                self.add("S2", "hierarchy", PASS, "gap %.1f mm > internal white %.1f mm" % (
                    smallest, widest[biggest]["gap_mm"]), house, where(biggest))

    # -- colour ----------------------------------------------------------------------

    def colour_checks(self):
        share, hues = measure_colour(self.rgb)
        self.measures["colour_share"] = round(share, 4)
        self.measures["hues"] = hues
        house = "%.2f to %.2f" % COLOUR_SHARE_RANGE
        inside = COLOUR_SHARE_RANGE[0] <= share <= COLOUR_SHARE_RANGE[1]
        self.add("C1", "colour share", PASS if inside else WARN, "%.2f" % share, house)
        house = "%d to %d" % HUES_RANGE
        if not hues:
            self.add("C2", "hues", INFO, "0 hues", house, "no hue holds %.0f%% of the coloured pixels"
                     % (100 * HUE_MIN_SHARE))
            return
        listing = "; ".join("%s %.0f%% at %.0f deg" % (h["hex"], 100 * h["share"], h["centre_deg"]) for h in hues)
        leading = len(hues) > 1 and hues[0]["share"] >= LEADING_HUE_RATIO * hues[1]["share"]
        if len(hues) > HUES_MAX:
            verdict = WARN
            detail = listing + ("; leading hue" if leading else "")
        elif leading:
            verdict, detail = INFO, "leading hue; " + listing
        else:
            verdict, detail = PASS, listing
        self.add("C2", "hues", verdict, plural(len(hues), "hue"), house, detail)

    # -- frames ------------------------------------------------------------------------

    def frame_checks(self):
        boxes, widths = [], []
        for drawing in self.page.get_drawings():
            if "s" not in drawing["type"] or not self.in_box(drawing["rect"]):
                continue
            if drawing.get("width") is not None:
                widths.append(float(drawing["width"]))
            rect = rectangle_of(drawing["items"])
            if rect is None or is_white(drawing.get("color")):
                continue
            x0, y0, x1, y1 = self.to_box_mm(rect)
            if x1 - x0 >= BOX_MIN_WIDTH_MM and y1 - y0 >= BOX_MIN_HEIGHT_MM:
                boxes.append({"x0_mm": x0, "y0_mm": y0, "x1_mm": x1, "y1_mm": y1})
        self.measures["boxes"] = boxes
        house = "none; nothing is boxed"
        if boxes:
            detail = "; ".join("%.0f x %.0f mm at x=%.1f, y=%.1f mm" % (
                b["x1_mm"] - b["x0_mm"], b["y1_mm"] - b["y0_mm"], b["x0_mm"], b["y0_mm"]) for b in boxes)
            self.add("B1", "boxes", WARN, plural(len(boxes), "box"), house, detail)
        else:
            self.add("B1", "boxes", PASS, "0 boxes", house)
        self.measures["strokes"] = {
            "count": len(widths),
            "median_pt": median(widths) if widths else None,
            "below_min": sum(1 for w in widths if w < STROKE_THIN_PT),
        }

    # -- text that belongs in the legend ------------------------------------------------------

    def text_checks(self):
        flagged = []
        for line in self.lines:
            if line.words >= CAPTION_MIN_WORDS or CAPTION_PATTERN.search(line.text):
                flagged.append({"text": line.text[:80], "y_mm": round(line.y0, 1), "words": line.words})
        self.measures["caption_lines"] = flagged
        house = "none; explanation goes in the legend"
        if flagged:
            detail = " | ".join('y=%.1f mm: "%s"' % (f["y_mm"], f["text"]) for f in flagged)
            self.add("X1", "caption material", WARN, plural(len(flagged), "line"), house, detail)
        else:
            self.add("X1", "caption material", PASS, "0 lines", house)

        total = sum(line.words for line in self.lines)
        per_panel = {}
        outside = 0
        for line in self.lines:
            owner = self.panel_of(line)
            if owner is None:
                outside += line.words
            else:
                per_panel[owner.ch] = per_panel.get(owner.ch, 0) + line.words
        grid = np.zeros((max(1, int(math.ceil(self.h_mm))), max(1, int(math.ceil(self.w_mm)))), dtype=bool)
        for span in self.spans:
            r0, r1 = max(int(math.floor(span.y0)), 0), max(int(math.ceil(span.y1)), 0)
            c0, c1 = max(int(math.floor(span.x0)), 0), max(int(math.ceil(span.x1)), 0)
            grid[r0:r1, c0:c1] = True
        text_share = float(grid.mean())
        self.measures["words"] = {
            "total": total,
            "per_panel": per_panel,
            "outside_panels": outside,
            "text_area_share": round(text_share, 4),
        }
        over = []
        if total > WORDS_MAX:
            over.append("%d words in the box" % total)
        over += ["panel %s holds %d words" % (k, v) for k, v in sorted(per_panel.items()) if v > WORDS_PER_PANEL_MAX]
        detail = "text boxes cover %.0f%% of the box" % (100 * text_share)
        if per_panel:
            detail += "; per panel " + ", ".join("%s %d" % (k, v) for k, v in sorted(per_panel.items()))
        if over:
            detail = "; ".join(over) + "; " + detail
        house = "at most %d words, %d per panel" % (WORDS_MAX, WORDS_PER_PANEL_MAX)
        self.add("X2", "text volume", WARN if over else PASS, "%d words" % total, house, detail)

        if not self.letters:
            why = "no letter inside the panel" if self.panel else "no letters found (see L1)"
            self.checks.append(skipped("X3", "panel titles", why))
            return
        counts = [(l.ch, count_words(l.title), l.title) for l in self.letters]
        long_titles = [c for c in counts if c[1] >= TITLE_WORDS_WARN]
        house = "fewer than %d words; the legend states the finding" % TITLE_WORDS_WARN
        if long_titles:
            detail = "; ".join('%s: %d words "%s"' % (ch, n, text[:50]) for ch, n, text in long_titles)
            self.add("X3", "panel titles", WARN, "longest %s" % plural(max(c[1] for c in counts), "word"), house, detail)
        else:
            self.add("X3", "panel titles", PASS, "longest %s" % plural(max(c[1] for c in counts), "word"), house,
                     ", ".join("%s: %d" % (ch, n) for ch, n, _ in counts))

    def panel_of(self, line):
        """Return the Letter whose panel region holds the centre of the line."""
        cx, cy = (line.x0 + line.x1) / 2.0, (line.y0 + line.y1) / 2.0
        for letter in self.letters:
            left, top, right, bottom = letter.region
            if left <= cx < right and top <= cy < bottom:
                return letter
        return None

    # -- images and strokes ---------------------------------------------------------------------

    def image_checks(self):
        images = []
        for info in self.page.get_image_info():
            rect = fitz.Rect(info["bbox"])
            if rect.width <= 0 or rect.height <= 0 or not self.in_box(rect):
                continue
            # The pixel area over the box area gives the same ppi for an image rotated by 90 degrees.
            ppi = math.sqrt(info["width"] * info["height"] / ((rect.width / 72.0) * (rect.height / 72.0)))
            images.append({"ppi": round(ppi, 1), "x_mm": (rect.x0 - self.rect.x0) * MM_PER_PT,
                           "y_mm": (rect.y0 - self.rect.y0) * MM_PER_PT})
        self.measures["images"] = images
        house = "at least %d ppi" % RASTER_MIN_PPI
        soft = [i for i in images if i["ppi"] < RASTER_MIN_PPI]
        if not images:
            self.add("R1", "raster", PASS, "no placed images", house)
        elif soft:
            detail = "; ".join("%.0f ppi at x=%.1f, y=%.1f mm" % (i["ppi"], i["x_mm"], i["y_mm"]) for i in soft)
            self.add("R1", "raster", WARN, "lowest %.0f ppi" % min(i["ppi"] for i in images), house, detail)
        else:
            self.add("R1", "raster", PASS, "lowest %.0f ppi" % min(i["ppi"] for i in images), house)
        strokes = self.measures["strokes"]
        house = "median %.3f to %.3f pt" % STROKE_MEDIAN_RANGE_PT
        if strokes["count"] == 0:
            self.add("K1", "strokes", INFO, "no stroked paths", house)
        else:
            self.add("K1", "strokes", INFO, "median %.3f pt" % strokes["median_pt"], house,
                     "%d of %d below %.2f pt" % (strokes["below_min"], strokes["count"], STROKE_THIN_PT))


def check_fonts(fonts):
    """Check the fonts of a page. Each entry is a tuple of get_page_fonts(full=True)."""

    def name_of(entry):
        return clean_font_name(entry[3]) or str(entry[4])

    names = sorted(set(name_of(f) for f in fonts))
    type3 = sorted(set(name_of(f) for f in fonts if str(f[2]).lower() == "type3"))
    loose = sorted(set(name_of(f) for f in fonts if f[1] == "n/a"))
    others = [n for n in names if n not in type3 and n not in loose]
    house = "embedded, editable fonts"
    value = plural(len(names), "font")
    tail = "; other fonts: %s" % ", ".join(others) if others else ""
    if type3:
        detail = "Type3 font, the text is not editable: %s" % ", ".join(type3)
        if loose:
            detail += "; not embedded: %s" % ", ".join(n for n in loose if n not in type3)
        return make_check("T3", "fonts", FAIL, value, house, detail + tail)
    if loose:
        return make_check("T3", "fonts", WARN, value, house, "not embedded: %s%s" % (", ".join(loose), tail))
    return make_check("T3", "fonts", PASS, value, house, ", ".join(names) if names else "no fonts")


def run_checks(path, page=1, clip_mm=None, slot_mm=None, max_height_mm=None, min_pt=5.0,
               case="lower", letter_weight="bold", panel=False):
    """Run every check on one page and return the result dictionary."""
    figure = Figure(path, page, clip_mm, slot_mm, max_height_mm, min_pt, case, letter_weight, panel)
    return figure.run()


def summarise(checks):
    """Return the verdict counts."""
    return {v: sum(1 for c in checks if c["verdict"] == v) for v in (PASS, WARN, FAIL, INFO)}


def render_table(result):
    """Return the text table for a result."""
    lines = [format_check(c) for c in result["checks"]]
    counts = summarise(result["checks"])
    lines.append("Summary: %d PASS, %d WARN, %d FAIL, %d INFO" % (
        counts[PASS], counts[WARN], counts[FAIL], counts[INFO]))
    return "\n".join(lines)


def parse_clip(text):
    """Parse X0,Y0,X1,Y1 in mm."""
    try:
        values = [float(v) for v in text.split(",")]
    except ValueError:
        values = []
    if len(values) != 4 or values[2] <= values[0] or values[3] <= values[1]:
        raise argparse.ArgumentTypeError("expected X0,Y0,X1,Y1 in mm with X1 > X0 and Y1 > Y0")
    return tuple(values)


def build_parser():
    parser = argparse.ArgumentParser(
        description="Measure the composition of one main-figure PDF and compare it with house ranges.")
    parser.add_argument("figure", metavar="FIGURE.pdf", help="the figure PDF")
    parser.add_argument("--page", type=int, default=1, help="1-based page number (default 1)")
    parser.add_argument("--clip-mm", type=parse_clip, default=None, metavar="X0,Y0,X1,Y1",
                        help="measure only this region, in mm from the top-left of the page")
    parser.add_argument("--slot-mm", type=float, default=None, metavar="W",
                        help="the width the journal allots, in mm")
    parser.add_argument("--max-height-mm", type=float, default=None, metavar="H",
                        help="the tallest the figure may be, in mm")
    parser.add_argument("--min-pt", type=float, default=5.0, help="smallest allowed type size in pt (default 5.0)")
    parser.add_argument("--case", choices=("lower", "upper", "any"), default="lower",
                        help="expected case of the panel letters (default lower)")
    parser.add_argument("--letter-weight", choices=("bold", "regular", "any"), default="bold",
                        help="expected weight of the panel letters (default bold)")
    parser.add_argument("--panel", action="store_true",
                        help="the PDF is one panel before composition")
    parser.add_argument("--json", action="store_true", help="print JSON instead of the table")
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        result = run_checks(args.figure, page=args.page, clip_mm=args.clip_mm, slot_mm=args.slot_mm,
                            max_height_mm=args.max_height_mm, min_pt=args.min_pt, case=args.case,
                            letter_weight=args.letter_weight, panel=args.panel)
    except FigureError as exc:
        print("check_main_figure: %s" % exc, file=sys.stderr)
        return 2
    if args.json:
        print(json.dumps(result, indent=2, default=native))
    else:
        print(render_table(result))
    return 1 if any(c["verdict"] == FAIL for c in result["checks"]) else 0


if __name__ == "__main__":
    sys.exit(main())
