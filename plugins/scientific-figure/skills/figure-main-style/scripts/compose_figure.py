#!/usr/bin/env python
"""Place finished one-page panel PDFs onto one figure page from a JSON layout.

The composer keeps every panel vector. It places each panel with
``page.show_pdf_page``, so glyphs stay glyphs and lines stay lines. It sets the
panel letters at assembly, in one font, one size and one baseline per row.

The composer never scales a panel unless the layout asks for it. It never adds
white space to fill a row. A row that is too wide is an error. A row that is
too narrow gets a warning that tells you to widen a panel.

All lengths in the layout and in the output are millimetres.

Usage
-----
    compose_figure.py LAYOUT.json [--out FIGURE.pdf] [--png-dpi 300] [--no-png] [--dry-run]

Exit status: 0 on success, 1 on a layout error, 2 on a command-line error.
"""
import argparse
import json
import logging
import math
import os
import sys
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    import fitz  # PyMuPDF
except ImportError:  # pragma: no cover
    raise SystemExit("compose_figure.py needs PyMuPDF. Install it with: pip install pymupdf")

MM = 72.0 / 25.4          # points per millimetre
TOL_MM = 0.01             # PDF page sizes carry rounding noise below this
UNUSED_WARN_MM = 2.0      # warn when a row leaves more than this unused
CORNER_DPI = 300          # resolution of the corner ink check
INK_BELOW = 245           # a grey value below this counts as ink
SIZE_TOL_PT = 0.05        # two font sizes closer than this are the same size
AXIS_TOL_DEG = 1.0        # text this close to 0, 90, 180 or 270 degrees counts as axis-aligned
FALLBACK_FONT = "hebo"    # PyMuPDF built-in Helvetica-Bold
FONT_FAMILIES = ["Arial", "Helvetica", "Liberation Sans", "DejaVu Sans"]

TOP_KEYS = {"width_mm", "max_height_mm", "gap_mm", "row_gap_mm", "col_gap_mm", "margin_mm",
            "letters", "rows", "output", "allow_scale"}
LETTER_KEYS = {"position", "size_pt", "font_file", "case", "clearance_mm",
               "label_gap_mm", "label_font_file", "label_size_pt"}
ROW_KEYS = {"panels"}
PANEL_KEYS = {"file", "clip_mm", "letter", "label", "scale", "remove_text", "remove_letter"}

EPILOG = """\
layout keys (JSON; every length is in mm):
  width_mm       page width. Required.
  max_height_mm  largest allowed page height. Optional. A taller page is an error.
  gap_mm         white between neighbouring panels, across a row and between
                 rows. Default 5.0.
  row_gap_mm     white between one row and the next. Default: gap_mm.
  col_gap_mm     white between neighbouring panels of a row. Default: gap_mm.
  margin_mm      white around the whole figure. Default 0.
  allow_scale    true lets a panel carry "scale". Default false.
  output         figure PDF path. Relative paths resolve against the layout
                 folder. The --out option overrides it.
  letters        panel letter settings:
    position       "corner" (default): the letter's top-left sits at the
                   panel's top-left corner, and the panel must leave that
                   corner free. "above": each row gets a strip above it, as
                   tall as the cap height plus clearance_mm. "none": no
                   letters.
    size_pt        letter size in points. Default 8.
    font_file      TrueType or OpenType file. Any face works, such as a light
                   cut: the composer does not force bold and does not fake
                   bold. Default: a bold sans font that matplotlib finds, else
                   the built-in Helvetica-Bold.
    case           "lower" (default) or "upper" for the default letters.
    clearance_mm   white kept around a letter and its label. Default 1.0.
    label_gap_mm   white between the letter's right edge and its label.
                   Default 1.5.
    label_font_file  font file of the labels. Default: the letter font.
    label_size_pt  label size in points. Default: size_pt.
  rows           list of rows, top to bottom. Each row is
                 {"panels": [panel, ...]}, left to right.
  panel          {"file": "panel_a.pdf"} with these optional keys:
    clip_mm        [left, top, right, bottom] in mm from the panel page's
                   top-left. The panel's size is then the size of the clip.
    letter         text of the panel letter. "" sets no letter on this panel
                   and does not use up a letter of the sequence. Default: the
                   next letter of a, b, c ... in reading order.
    label          short text set on the letter's baseline, right of the
                   letter, label_gap_mm from the letter's right edge. A
                   label needs a letter. For "corner", the ink check covers
                   the letter and the label.
    scale          placement factor, such as 0.9. Needs "allow_scale": true.
    remove_text    list of strings to erase from the panel. Each string must
                   equal the stripped text of a whole text span on the panel
                   page. A string that matches no span is an error. Every
                   matching span is erased. Vector art and images stay. The
                   panel file is never written. Text that is not horizontal
                   or vertical (more than 1 degree off) is an error: remove
                   it in the panel script, or by hand. If the erasure
                   damages any text that you did not list, that is an error
                   too.
    remove_letter  one letter, such as "a". It erases the single-letter span
                   with that text whose font size is the largest among the
                   panel's single-letter spans. No such span is an error. Use
                   it to drop the old letter of a panel that is a PDF only.
The report and the sidecar list every erased string for each panel.

Relative panel paths resolve against the layout file's folder.
A panel page with a /Rotate entry is placed as a viewer shows it: the
composer removes the rotation in memory and prints a NOTE. A clip_mm then
counts from the top-left of the page as a viewer shows it.
Rows stack top to bottom, row_gap_mm apart. Panels sit left to right,
col_gap_mm apart, and top-aligned. A row wider than the page is an error. A
row that leaves more than 2 mm unused gets a warning.
Besides the figure PDF, the composer writes a PNG and a sidecar file named
<output stem>.layout.json with the resolved placements.
"""


class LayoutError(Exception):
    """Carry one or more messages that stop the run with exit status 1."""

    def __init__(self, messages):
        if isinstance(messages, str):
            messages = [messages]
        Exception.__init__(self, "; ".join(messages))
        self.messages = list(messages)


# ---------------------------------------------------------------------------
# Layout file
# ---------------------------------------------------------------------------

def _number(value, where, positive=False, minimum=None):
    """Return value as a float, or raise LayoutError when it is not a fitting number."""
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise LayoutError("%s must be a number" % where)
    if positive and value <= 0:
        raise LayoutError("%s must be greater than 0" % where)
    if minimum is not None and value < minimum:
        raise LayoutError("%s must be at least %s" % (where, minimum))
    return float(value)


def _reject_unknown(mapping, allowed, where):
    """Raise LayoutError for a key that the schema does not know. Keys that start with _ are notes."""
    if not isinstance(mapping, dict):
        raise LayoutError("%s must be a JSON object" % where)
    for key in mapping:
        if key not in allowed and not str(key).startswith("_"):
            raise LayoutError("unknown key '%s' in %s. Known keys: %s"
                              % (key, where, ", ".join(sorted(allowed))))


def load_layout(path):
    """Read the layout file and return a validated dictionary with defaults filled in."""
    try:
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
    except OSError as err:
        raise LayoutError("cannot read the layout file %s: %s" % (path, err.strerror))
    except ValueError as err:
        raise LayoutError("the layout file %s is not valid JSON: %s" % (path, err))
    return validate_layout(data)


def validate_layout(data):
    """Check a layout dictionary and return a copy with every default filled in."""
    _reject_unknown(data, TOP_KEYS, "the layout")
    if "width_mm" not in data:
        raise LayoutError("the layout needs 'width_mm'")
    out = {"width_mm": _number(data["width_mm"], "'width_mm'", positive=True)}
    out["max_height_mm"] = (_number(data["max_height_mm"], "'max_height_mm'", positive=True)
                            if data.get("max_height_mm") is not None else None)
    out["gap_mm"] = _number(data.get("gap_mm", 5.0), "'gap_mm'", minimum=0)
    for key in ("row_gap_mm", "col_gap_mm"):     # each defaults to gap_mm
        out[key] = (_number(data[key], "'%s'" % key, minimum=0)
                    if data.get(key) is not None else out["gap_mm"])
    out["margin_mm"] = _number(data.get("margin_mm", 0.0), "'margin_mm'", minimum=0)
    if out["width_mm"] - 2 * out["margin_mm"] <= 0:
        raise LayoutError("'margin_mm' leaves no room: the page is %.1f mm wide" % out["width_mm"])
    allow_scale = data.get("allow_scale", False)
    if not isinstance(allow_scale, bool):
        raise LayoutError("'allow_scale' must be true or false")
    out["allow_scale"] = allow_scale
    output = data.get("output")
    if output is not None and not isinstance(output, str):
        raise LayoutError("'output' must be a string")
    out["output"] = output

    raw = data.get("letters", {})
    _reject_unknown(raw, LETTER_KEYS, "'letters'")
    letters = {
        "position": raw.get("position", "corner"),
        "size_pt": _number(raw.get("size_pt", 8), "'letters.size_pt'", positive=True),
        "font_file": raw.get("font_file"),
        "case": raw.get("case", "lower"),
        "clearance_mm": _number(raw.get("clearance_mm", 1.0), "'letters.clearance_mm'", minimum=0),
        "label_gap_mm": _number(raw.get("label_gap_mm", 1.5), "'letters.label_gap_mm'", minimum=0),
        "label_font_file": raw.get("label_font_file"),
        "label_size_pt": None,
    }
    letters["label_size_pt"] = (_number(raw["label_size_pt"], "'letters.label_size_pt'", positive=True)
                                if raw.get("label_size_pt") is not None else letters["size_pt"])
    if letters["position"] not in ("corner", "above", "none"):
        raise LayoutError("'letters.position' must be \"corner\", \"above\" or \"none\"")
    if letters["case"] not in ("lower", "upper"):
        raise LayoutError("'letters.case' must be \"lower\" or \"upper\"")
    for key in ("font_file", "label_font_file"):
        if letters[key] is not None and not isinstance(letters[key], str):
            raise LayoutError("'letters.%s' must be a path or null" % key)
    out["letters"] = letters

    rows = data.get("rows")
    if not isinstance(rows, list) or not rows:
        raise LayoutError("the layout needs a non-empty list 'rows'")
    out["rows"] = []
    for r, row in enumerate(rows, start=1):
        _reject_unknown(row, ROW_KEYS, "row %d" % r)
        panels = row.get("panels")
        if not isinstance(panels, list) or not panels:
            raise LayoutError("row %d needs a non-empty list 'panels'" % r)
        out_row = []
        for i, panel in enumerate(panels, start=1):
            where = "panel %d of row %d" % (i, r)
            _reject_unknown(panel, PANEL_KEYS, where)
            if not isinstance(panel.get("file"), str) or not panel["file"]:
                raise LayoutError("%s needs a 'file' string" % where)
            clip = panel.get("clip_mm")
            if clip is not None:
                if not isinstance(clip, list) or len(clip) != 4:
                    raise LayoutError("'clip_mm' in %s must be [left, top, right, bottom]" % where)
                clip = [_number(v, "'clip_mm' in %s" % where) for v in clip]
                if clip[2] <= clip[0] or clip[3] <= clip[1]:
                    raise LayoutError("'clip_mm' in %s must have right > left and bottom > top" % where)
            letter = panel.get("letter")
            if letter is not None and not isinstance(letter, str):
                raise LayoutError("'letter' in %s must be a string" % where)
            label = panel.get("label")
            if label is not None and not isinstance(label, str):
                raise LayoutError("'label' in %s must be a string" % where)
            remove_text = panel.get("remove_text", [])
            if not isinstance(remove_text, list) or not all(isinstance(t, str) and t for t in remove_text):
                raise LayoutError("'remove_text' in %s must be a list of non-empty strings" % where)
            remove_letter = panel.get("remove_letter")
            if remove_letter is not None and (not isinstance(remove_letter, str)
                                              or len(remove_letter) != 1 or remove_letter.isspace()):
                raise LayoutError("'remove_letter' in %s must be a single letter" % where)
            scale = panel.get("scale")
            if scale is not None:
                if not allow_scale:
                    raise LayoutError(
                        "%s ('%s') sets 'scale', but the layout does not set \"allow_scale\": true. "
                        "The composer places panels at 100%%." % (where, panel["file"]))
                scale = _number(scale, "'scale' in %s" % where, positive=True)
            out_row.append({"file": panel["file"], "clip_mm": clip,
                            "letter_spec": letter, "label": label or "", "scale": scale,
                            "remove_text": list(remove_text), "remove_letter": remove_letter or ""})
        out["rows"].append(out_row)
    return out


# ---------------------------------------------------------------------------
# Letter font
# ---------------------------------------------------------------------------

def default_font_path():
    """Return a bold sans font file that matplotlib finds, or None without matplotlib."""
    try:
        from matplotlib import font_manager
    except Exception:
        return None
    logger = logging.getLogger("matplotlib.font_manager")
    old_level = logger.level
    logger.setLevel(logging.ERROR)  # a missing family is normal here
    try:
        props = font_manager.FontProperties(family=FONT_FAMILIES, weight="bold")
        return font_manager.findfont(props, fallback_to_default=True)
    except Exception:
        return None
    finally:
        logger.setLevel(old_level)


class LetterFont:
    """One font for every panel letter, with the metrics that the placement needs."""

    def __init__(self, path, alias="PanelLetterFont"):
        self.path = path                     # font file, or None for the built-in font
        self.alias = alias                   # name of the font resource on the page
        font = None
        if path is not None:
            try:
                font = fitz.Font(fontfile=path)
            except Exception:
                font = None
        if font is None:
            if path is not None:
                raise LayoutError("cannot load the letter font file: %s" % path)
            font = fitz.Font(FALLBACK_FONT)
        self.font = font
        self.name = font.name if path is not None else FALLBACK_FONT
        self.cap_em = self._measure_cap_height_em()

    def _measure_cap_height_em(self):
        """Render a large H and return its height above the baseline in em units."""
        size, scale, base = 100.0, 4.0, 150.0
        doc = fitz.open()
        page = doc.new_page(width=200, height=200)
        page.insert_text((20, base), "H", fontname=self.fontname(page), fontsize=size)
        pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), colorspace=fitz.csGRAY, alpha=False)
        samples, width = pix.samples, pix.width
        for row in range(pix.height):
            if min(samples[row * width:(row + 1) * width]) < 128:
                return (base * scale - row) / scale / size
        raise LayoutError("cannot measure the cap height of the letter font")

    def fontname(self, page):
        """Register the font on the page and return the name to draw with."""
        if self.path is None:
            return FALLBACK_FONT
        page.insert_font(fontname=self.alias, fontfile=self.path)
        return self.alias

    def cap_height_pt(self, size_pt):
        return self.cap_em * size_pt

    def width_pt(self, text, size_pt):
        return self.font.text_length(text, fontsize=size_pt)


def load_letter_font(font_file, base_dir, warnings):
    """Return the LetterFont for the layout. Append a warning to warnings when the font is not embedded."""
    if font_file:
        return load_font_file(font_file, base_dir)
    path = default_font_path()
    if path is not None:
        try:
            return LetterFont(path)
        except LayoutError:
            pass
    warnings.append("matplotlib gave no usable font file, so the letters use the built-in "
                    "Helvetica-Bold (hebo). It is a Base-14 font and is not embedded in the PDF.")
    return LetterFont(None)


def load_font_file(font_file, base_dir, alias="PanelLetterFont"):
    """Load the font file that the layout names. The composer uses the face as given."""
    path = font_file if os.path.isabs(font_file) else os.path.join(base_dir, font_file)
    if not os.path.isfile(path):
        raise LayoutError("the font file does not exist: %s" % font_file)
    return LetterFont(path, alias)


# ---------------------------------------------------------------------------
# Plan: sizes, positions, warnings
# ---------------------------------------------------------------------------

@dataclass
class Panel:
    row: int
    index: int
    file: str                                  # path as written in the layout
    path: str                                  # resolved path
    clip_mm: Optional[List[float]]
    letter_spec: Optional[str]
    scale_spec: Optional[float]
    label_spec: str = ""
    remove_text: List[str] = field(default_factory=list)
    remove_letter: str = ""
    removed: List[str] = field(default_factory=list)   # strings erased from the panel
    rotation_removed: int = 0                  # the /Rotate value of the panel page, 0 when none
    letter: str = ""                           # "" means no letter
    label: str = ""                            # "" means no label
    scale: float = 1.0
    src_w_mm: float = 0.0
    src_h_mm: float = 0.0
    x_mm: float = 0.0
    y_mm: float = 0.0
    w_mm: float = 0.0
    h_mm: float = 0.0
    letter_x_mm: Optional[float] = None
    letter_top_mm: Optional[float] = None
    letter_baseline_mm: Optional[float] = None
    label_x_mm: Optional[float] = None

    @property
    def short_name(self):
        return "panel %s" % (self.letter or self.file)

    @property
    def long_name(self):
        if self.letter:
            return "panel %s (%s)" % (self.letter, self.file)
        return "panel %s" % self.file

    def clip_rect_pt(self):
        """Return the clip in source-page points, or None for the whole page."""
        if self.clip_mm is None:
            return None
        left, top, right, bottom = self.clip_mm
        return fitz.Rect(left * MM, top * MM, right * MM, bottom * MM)


@dataclass
class Row:
    index: int
    panels: List[Panel]
    top_mm: float = 0.0
    strip_mm: float = 0.0
    height_mm: float = 0.0


@dataclass
class Plan:
    width_mm: float
    height_mm: float
    margin_mm: float
    gap_mm: float
    row_gap_mm: float
    col_gap_mm: float
    letters: Dict[str, Any]
    font: Optional[LetterFont]
    label_font: Optional[LetterFont]
    rows: List[Row]
    warnings: List[str] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)
    line_cap_mm: float = 0.0                   # height of the letter and label line

    @property
    def panels(self):
        return [p for row in self.rows for p in row.panels]

    @property
    def any_scaled(self):
        return any(abs(p.scale - 1.0) > 1e-9 for p in self.panels)


def open_panel(path, label):
    """Open a panel PDF. Raise LayoutError with a plain message when that fails."""
    if not os.path.isfile(path):
        raise LayoutError("panel file not found: %s" % label)
    try:
        doc = fitz.open(path)
    except Exception as err:
        raise LayoutError("cannot open panel %s: %s" % (label, err))
    if not doc.is_pdf:
        doc.close()
        raise LayoutError("panel %s is not a PDF" % label)
    if doc.page_count < 1:
        doc.close()
        raise LayoutError("panel %s has no pages" % label)
    return doc


def _page_spans(page):
    """Return every text span of the page. Each span also carries the direction of its line."""
    spans = []
    for block in page.get_text("dict")["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                item = dict(span)
                item["dir"] = line["dir"]
                spans.append(item)
    return spans


def _is_axis_aligned(direction):
    """Return True when a line direction lies within AXIS_TOL_DEG of 0, 90, 180 or 270 degrees."""
    angle = math.degrees(math.atan2(direction[1], direction[0]))
    return abs((angle + 45.0) % 90.0 - 45.0) <= AXIS_TOL_DEG


def _redaction_band(span):
    """Return a thin band through the middle of the span's box.

    A redaction removes each glyph that its rectangle touches. The whole span box also
    touches the glyph boxes of a neighbouring line when the lines are set tight, so the
    composer redacts only a band along the middle of the box. The band keeps a small
    distance from both ends of the span for the same reason. Only a span that is
    axis-aligned gets a band: a band through the box of a tilted span misses part of it
    and cuts its neighbours.
    """
    box = fitz.Rect(span["bbox"])
    if abs(span["dir"][0]) >= abs(span["dir"][1]):       # horizontal text
        mid, half = (box.y0 + box.y1) / 2, max(0.1, 0.05 * box.height)
        return fitz.Rect(box.x0 + 0.25, mid - half, box.x1 - 0.25, mid + half)
    mid, half = (box.x0 + box.x1) / 2, max(0.1, 0.05 * box.width)      # vertical text
    return fitz.Rect(mid - half, box.y0 + 0.25, mid + half, box.y1 - 0.25)


def remove_panel_text(page, panel):
    """Erase the text that the panel names from an in-memory page. Return the erased strings.

    Vector art and images stay. Raise LayoutError when a string matches no whole span, when
    a span to erase is not axis-aligned, or when the erasure changes any span that the layout
    did not list.
    """
    spans = _page_spans(page)
    hits, errors = [], []
    for wanted in panel.remove_text:
        found = [sp for sp in spans if sp["text"].strip() == wanted]
        if not found:
            errors.append("remove_text '%s' matches no whole text span in %s. A string must equal "
                          "the stripped text of one span." % (wanted, panel.long_name))
        hits.extend(found)
    if panel.remove_letter:
        singles = [sp for sp in spans if len(sp["text"].strip()) == 1 and sp["text"].strip().isalpha()]
        biggest = max([sp["size"] for sp in singles], default=0.0)
        found = [sp for sp in singles if sp["size"] > biggest - SIZE_TOL_PT
                 and sp["text"].strip() == panel.remove_letter]
        if not found:
            largest = sorted(set(sp["text"].strip() for sp in singles if sp["size"] > biggest - SIZE_TOL_PT))
            errors.append("remove_letter '%s' matches no single-letter span of the largest size in %s. "
                          "The largest single-letter spans read: %s."
                          % (panel.remove_letter, panel.long_name, ", ".join(largest) or "none found"))
        elif len(found) > 1:
            errors.append("remove_letter '%s' is ambiguous in %s: %d single-letter spans of the largest "
                          "size have that text. Use remove_text instead."
                          % (panel.remove_letter, panel.long_name, len(found)))
        hits.extend(found)
    for text in dict.fromkeys(sp["text"].strip() for sp in hits if not _is_axis_aligned(sp["dir"])):
        errors.append("cannot erase '%s' from %s: this text is rotated; remove it in the panel "
                      "script, or remove it by hand." % (text, panel.long_name))
    if errors:
        raise LayoutError(errors)
    if not hits:
        return []
    unique = list({id(sp): sp for sp in hits}.values())
    listed = {id(sp) for sp in unique}
    kept_before = Counter(sp["text"].strip() for sp in spans if id(sp) not in listed and sp["text"].strip())
    for sp in unique:
        page.add_redact_annot(_redaction_band(sp), fill=False)
    page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE, graphics=fitz.PDF_REDACT_LINE_ART_NONE,
                          text=fitz.PDF_REDACT_TEXT_REMOVE)
    left = _page_spans(page)
    problems = []
    for sp in unique:
        if any(other["text"] == sp["text"] and fitz.Rect(other["bbox"]) == fitz.Rect(sp["bbox"])
               for other in left):
            problems.append("cannot erase '%s' from %s: the text is still in the panel"
                            % (sp["text"].strip(), panel.long_name))
    # Every span that the layout did not list must come out of the erasure with its text intact.
    kept_after = Counter(sp["text"].strip() for sp in left if sp["text"].strip())
    damaged = [text for text in kept_before if kept_before[text] > kept_after[text]]
    if damaged:
        problems.append("erasing text from %s damaged text that the layout does not list: %s. "
                        "The panel file is unchanged. Remove the text in the panel script, or remove "
                        "it by hand." % (panel.long_name, ", ".join("'%s'" % text for text in damaged)))
    if problems:
        raise LayoutError(problems)
    return list(dict.fromkeys(sp["text"].strip() for sp in unique))


def _remove_rotation(doc, panel):
    """Turn page 1 of the in-memory document upright, so that its size, text and ink match the view.

    A page with a /Rotate entry reports the rotated size, but show_pdf_page draws its content
    unrotated. Raise LayoutError when removing the rotation changes the page size, which
    happens for a page that also has a crop box.
    """
    page = doc[0]
    panel.rotation_removed = page.rotation
    if not page.rotation:
        return
    width, height = page.rect.width, page.rect.height
    page.remove_rotation()
    new_width, new_height = doc[0].rect.width, doc[0].rect.height
    if abs(new_width - width) > TOL_MM * MM or abs(new_height - height) > TOL_MM * MM:
        raise LayoutError("cannot remove the /Rotate %d entry of %s: the page changes from %.1f x %.1f mm "
                          "to %.1f x %.1f mm, which happens when the page has a crop box. Save the panel "
                          "without /Rotate or without the crop box."
                          % (panel.rotation_removed, panel.long_name, width / MM, height / MM,
                             new_width / MM, new_height / MM))


def open_prepared(panel):
    """Open a panel and erase its remove_text and remove_letter strings from the in-memory copy.

    The composer never writes the panel file. A page with a /Rotate entry is turned upright
    first, and Panel.rotation_removed holds the old /Rotate value. Panel.removed lists the
    erased strings.
    """
    doc = open_panel(panel.path, panel.file)
    try:
        _remove_rotation(doc, panel)
        panel.removed = remove_panel_text(doc[0], panel) if (panel.remove_text or panel.remove_letter) else []
    except Exception:
        doc.close()
        raise
    return doc


def _assign_letters(panels, position, case, warnings):
    """Give each panel its letter. An empty letter does not use up a letter of the sequence."""
    used = 0
    for panel in panels:
        spec = panel.letter_spec
        if position == "none":
            panel.letter = ""
            if spec:
                warnings.append("letters.position is 'none', so the letter '%s' on %s is ignored."
                                % (spec, "panel " + panel.file))
        elif spec == "":
            panel.letter = ""
        elif spec is None:
            if used >= 26:
                raise LayoutError("the layout has more than 26 panels; set 'letter' on each panel "
                                  "past the 26th")
            letter = chr(ord("a") + used)
            panel.letter = letter.upper() if case == "upper" else letter
            used += 1
        else:
            panel.letter = spec
            used += 1
        panel.label = panel.label_spec
        if panel.label and not panel.letter:
            warnings.append("the label '%s' on panel %s is ignored because the panel has no letter."
                            % (panel.label, panel.file))
            panel.label = ""


def build_plan(layout, base_dir):
    """Resolve every panel size and position. Raise LayoutError for an overflow or a page that is too tall."""
    warnings, notes, errors = [], [], []
    letters = layout["letters"]
    position = letters["position"]
    width, gap, margin = layout["width_mm"], layout["gap_mm"], layout["margin_mm"]
    row_gap, col_gap = layout["row_gap_mm"], layout["col_gap_mm"]

    rows = []
    for r, raw_row in enumerate(layout["rows"], start=1):
        panels = []
        for i, raw in enumerate(raw_row, start=1):
            path = raw["file"] if os.path.isabs(raw["file"]) else os.path.join(base_dir, raw["file"])
            panels.append(Panel(row=r, index=i, file=raw["file"], path=path, clip_mm=raw["clip_mm"],
                                letter_spec=raw["letter_spec"], scale_spec=raw["scale"],
                                label_spec=raw["label"], remove_text=raw["remove_text"],
                                remove_letter=raw["remove_letter"]))
        rows.append(Row(index=r, panels=panels))
    all_panels = [p for row in rows for p in row.panels]
    _assign_letters(all_panels, position, letters["case"], warnings)

    font = label_font = None
    line_cap_mm = 0.0
    if position != "none":
        font = load_letter_font(letters["font_file"], base_dir, warnings)
        label_font = font
        if letters["label_font_file"]:
            label_font = load_font_file(letters["label_font_file"], base_dir, "PanelLabelFont")
        # Letters and labels share one baseline, so the text line is as tall as its tallest part.
        line_cap_pt = font.cap_height_pt(letters["size_pt"])
        if any(p.label for p in all_panels):
            line_cap_pt = max(line_cap_pt, label_font.cap_height_pt(letters["label_size_pt"]))
        line_cap_mm = line_cap_pt / MM

    # Read each panel's size from its first page.
    for panel in all_panels:
        doc = open_prepared(panel)
        try:
            if doc.page_count > 1:
                warnings.append("%s has %d pages; the composer places page 1 only."
                                % (panel.long_name, doc.page_count))
            page_w, page_h = doc[0].rect.width / MM, doc[0].rect.height / MM
        finally:
            doc.close()
        if panel.clip_mm is not None:
            left, top, right, bottom = panel.clip_mm
            if left < -TOL_MM or top < -TOL_MM or right > page_w + TOL_MM or bottom > page_h + TOL_MM:
                raise LayoutError("'clip_mm' of %s lies outside the %.1f x %.1f mm page"
                                  % (panel.long_name, page_w, page_h))
            panel.src_w_mm, panel.src_h_mm = right - left, bottom - top
        else:
            panel.src_w_mm, panel.src_h_mm = page_w, page_h
        panel.scale = panel.scale_spec if panel.scale_spec is not None else 1.0
        panel.w_mm, panel.h_mm = panel.src_w_mm * panel.scale, panel.src_h_mm * panel.scale
        if abs(panel.scale - 1.0) > 1e-9:
            verb = "shrinks to" if panel.scale < 1 else "grows to"
            notes.append("every type size in %s %s %.2fx" % (panel.short_name, verb, panel.scale))

    # Row heights and positions.
    avail = width - 2 * margin
    y = margin
    for row in rows:
        has_letter = any(p.letter for p in row.panels)
        if position == "above" and has_letter:
            row.strip_mm = line_cap_mm + letters["clearance_mm"]
        row.top_mm = y
        row.height_mm = row.strip_mm + max(p.h_mm for p in row.panels)
        x = margin
        for panel in row.panels:
            panel.x_mm = x
            panel.y_mm = y + row.strip_mm
            x += panel.w_mm + col_gap
        used = sum(p.w_mm for p in row.panels) + col_gap * (len(row.panels) - 1)
        over = used - avail
        if over > TOL_MM:
            errors.append("row %d is %.1f mm too wide: its panels and gaps need %.1f mm and the page "
                          "offers %.1f mm. Redraw a panel narrower; the composer does not scale."
                          % (row.index, over, used, avail))
        elif avail - used > UNUSED_WARN_MM:
            warnings.append("row %d leaves %.1f mm unused (%.1f of %.1f mm used): widen a panel, "
                            "do not add air." % (row.index, avail - used, used, avail))
        y += row.height_mm + row_gap
    height = y - row_gap + margin

    max_height = layout["max_height_mm"]
    if max_height is not None and height - max_height > TOL_MM:
        errors.append("the page is %.1f mm tall, %.1f mm over max_height_mm %.1f. Shorten a panel or "
                      "remove a row; the composer does not scale." % (height, height - max_height, max_height))
    if errors:
        raise LayoutError(errors)

    # Letter positions: one top y, hence one baseline, per row.
    if font is not None:
        for row in rows:
            for panel in row.panels:
                if panel.letter:
                    panel.letter_x_mm = panel.x_mm
                    panel.letter_top_mm = row.top_mm if position == "above" else panel.y_mm
                    panel.letter_baseline_mm = panel.letter_top_mm + line_cap_mm
                if panel.label:
                    letter_w_mm = font.width_pt(panel.letter, letters["size_pt"]) / MM
                    panel.label_x_mm = panel.letter_x_mm + letter_w_mm + letters["label_gap_mm"]

    plan = Plan(width_mm=width, height_mm=height, margin_mm=margin, gap_mm=gap, row_gap_mm=row_gap,
                col_gap_mm=col_gap, letters=letters, font=font, label_font=label_font, rows=rows,
                warnings=warnings, notes=notes, line_cap_mm=line_cap_mm)
    if position == "corner":
        plan.warnings.extend(check_corners(plan))
    return plan


def count_ink(page, rect_pt):
    """Render rect_pt of a source page at 300 dpi and count pixels darker than the ink limit."""
    rect = rect_pt & page.rect
    if rect.is_empty:
        return 0
    zoom = CORNER_DPI / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=rect, colorspace=fitz.csGRAY, alpha=False)
    return sum(1 for value in pix.samples if value < INK_BELOW)


def check_corners(plan):
    """Return a warning for each panel whose top-left corner holds ink where its letter or label goes."""
    warnings = []
    size = plan.letters["size_pt"]
    clearance = plan.letters["clearance_mm"]
    for panel in plan.panels:
        if not panel.letter:
            continue
        corner_w = plan.font.width_pt(panel.letter, size) / MM + clearance
        if panel.label:
            label_w = plan.label_font.width_pt(panel.label, plan.letters["label_size_pt"]) / MM
            corner_w += plan.letters["label_gap_mm"] + label_w
        corner_h = plan.line_cap_mm + clearance
        doc = open_prepared(panel)
        try:
            clip = panel.clip_rect_pt()
            left = clip.x0 if clip is not None else 0.0
            top = clip.y0 if clip is not None else 0.0
            # The corner is measured on the placed panel, so divide by the scale for the source.
            rect = fitz.Rect(left, top, left + corner_w * MM / panel.scale, top + corner_h * MM / panel.scale)
            if clip is not None:
                rect &= clip
            ink = count_ink(doc[0], rect)
        finally:
            doc.close()
        if ink:
            warnings.append("leave a %.1f × %.1f mm corner free in %s, or use position 'above'."
                            % (corner_w, corner_h, panel.long_name))
    return warnings


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def report_lines(plan):
    """Return the placement report as a list of lines."""
    lines = ["Page: %.2f x %.2f mm" % (plan.width_mm, plan.height_mm)]
    if plan.font is not None:
        lines.append("Letters: position %s, %g pt, font %s"
                     % (plan.letters["position"], plan.letters["size_pt"], plan.font.name))
    else:
        lines.append("Letters: none")
    lines.append("%-6s %-24s %8s %8s %8s %8s %6s  %s"
                 % ("letter", "file", "x_mm", "y_mm", "w_mm", "h_mm", "scale", "label"))
    for panel in plan.panels:
        lines.append(("%-6s %-24s %8.2f %8.2f %8.2f %8.2f %6.2f  %s"
                      % (panel.letter or "-", panel.file, panel.x_mm, panel.y_mm,
                         panel.w_mm, panel.h_mm, panel.scale, panel.label or "-")))
    for panel in plan.panels:
        if panel.removed:
            lines.append("Removed from %s: %s" % (panel.long_name, ", ".join(
                json.dumps(text, ensure_ascii=False) for text in panel.removed)))
    for panel in plan.panels:
        if panel.rotation_removed:
            lines.append("NOTE: %s has a /Rotate %d entry. The composer removed the rotation in memory "
                         "and places the panel as a viewer shows it."
                         % (panel.long_name, panel.rotation_removed))
    for warning in plan.warnings:
        lines.append("WARNING: " + warning)
    if plan.any_scaled:
        lines.extend(plan.notes)
    else:
        lines.append("Panels placed at 100%: type sizes are the panels' own.")
    return lines


def sidecar_data(plan):
    """Return the resolved placements as a JSON-ready dictionary."""
    def rnd(value):
        return None if value is None else round(value, 4)

    panels = []
    for panel in plan.panels:
        panels.append({
            "row": panel.row,
            "file": panel.file,
            "letter": panel.letter or None,
            "x_mm": rnd(panel.x_mm), "y_mm": rnd(panel.y_mm),
            "w_mm": rnd(panel.w_mm), "h_mm": rnd(panel.h_mm),
            "scale": rnd(panel.scale),
            "clip_mm": panel.clip_mm,
            "letter_x_mm": rnd(panel.letter_x_mm),
            "letter_top_mm": rnd(panel.letter_top_mm),
            "letter_baseline_mm": rnd(panel.letter_baseline_mm),
            "label": panel.label or None,
            "label_x_mm": rnd(panel.label_x_mm),
            "removed_text": list(panel.removed),
        })
    return {
        "page_mm": {"width": rnd(plan.width_mm), "height": rnd(plan.height_mm)},
        "row_gap_mm": rnd(plan.row_gap_mm),
        "col_gap_mm": rnd(plan.col_gap_mm),
        "letters": {"position": plan.letters["position"], "size_pt": plan.letters["size_pt"],
                    "case": plan.letters["case"], "clearance_mm": plan.letters["clearance_mm"],
                    "label_gap_mm": plan.letters["label_gap_mm"],
                    "label_size_pt": plan.letters["label_size_pt"]},
        "font": plan.font.name if plan.font is not None else None,
        "font_file": plan.font.path if plan.font is not None else None,
        "label_font": plan.label_font.name if plan.label_font is not None else None,
        "label_font_file": plan.label_font.path if plan.label_font is not None else None,
        "panels": panels,
    }


def build_pdf(plan, out_pdf):
    """Draw the panels and letters on one page and save it. Panels stay vector."""
    doc = fitz.open()
    page = doc.new_page(width=plan.width_mm * MM, height=plan.height_mm * MM)
    sources = []
    try:
        for panel in plan.panels:
            src = open_prepared(panel)
            sources.append(src)
            rect = fitz.Rect(panel.x_mm * MM, panel.y_mm * MM,
                             (panel.x_mm + panel.w_mm) * MM, (panel.y_mm + panel.h_mm) * MM)
            page.show_pdf_page(rect, src, 0, clip=panel.clip_rect_pt())
        if plan.font is not None:
            fontname = plan.font.fontname(page)
            label_fontname = plan.label_font.fontname(page)
            for panel in plan.panels:
                if panel.letter:
                    page.insert_text((panel.letter_x_mm * MM, panel.letter_baseline_mm * MM),
                                     panel.letter, fontname=fontname,
                                     fontsize=plan.letters["size_pt"], color=(0, 0, 0))
                if panel.label:
                    page.insert_text((panel.label_x_mm * MM, panel.letter_baseline_mm * MM),
                                     panel.label, fontname=label_fontname,
                                     fontsize=plan.letters["label_size_pt"], color=(0, 0, 0))
        doc.save(out_pdf, garbage=4, deflate=True)
    finally:
        for src in sources:
            src.close()
        doc.close()


def write_png(pdf_path, png_path, dpi):
    """Render the first page of the figure PDF to a PNG."""
    doc = fitz.open(pdf_path)
    try:
        doc[0].get_pixmap(dpi=dpi, alpha=False).save(png_path)
    finally:
        doc.close()


# ---------------------------------------------------------------------------
# Command line
# ---------------------------------------------------------------------------

def _positive_int(text):
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError("%r is not a whole number" % text)
    if value <= 0:
        raise argparse.ArgumentTypeError("the resolution must be greater than 0")
    return value


def make_parser():
    parser = argparse.ArgumentParser(
        prog="compose_figure.py",
        description="Place finished one-page panel PDFs onto one figure page from a JSON layout.\n"
                    "Panels stay vector. The composer sets the panel letters, never scales a\n"
                    "panel unless the layout asks for it, and never adds white space to fill\n"
                    "a row.",
        epilog=EPILOG, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("layout", metavar="LAYOUT.json", help="the layout file")
    parser.add_argument("--out", metavar="FIGURE.pdf",
                        help="figure PDF to write; overrides 'output' in the layout")
    parser.add_argument("--png-dpi", type=_positive_int, default=300, metavar="DPI",
                        help="resolution of the PNG preview (default 300)")
    parser.add_argument("--no-png", action="store_true", help="do not write the PNG preview")
    parser.add_argument("--dry-run", action="store_true",
                        help="print the placement report and write nothing")
    return parser


def output_path(args, layout, layout_dir):
    """Return the figure PDF path from --out, from the layout, or from the layout file's name."""
    if args.out:
        return args.out
    if layout["output"]:
        out = layout["output"]
        return out if os.path.isabs(out) else os.path.join(layout_dir, out)
    stem = os.path.splitext(os.path.basename(args.layout))[0]
    return os.path.join(layout_dir, stem + ".pdf")


def main(argv=None):
    args = make_parser().parse_args(argv)
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    layout_dir = os.path.dirname(os.path.abspath(args.layout))
    try:
        layout = load_layout(args.layout)
        plan = build_plan(layout, layout_dir)
        out_pdf = output_path(args, layout, layout_dir)
        if any(os.path.realpath(out_pdf) == os.path.realpath(p.path) for p in plan.panels):
            raise LayoutError("the output path %s is also a panel file; the composer would overwrite "
                              "the panel. Choose another output path." % out_pdf)
    except LayoutError as err:
        for message in err.messages:
            print("ERROR: " + message, file=sys.stderr)
        return 1

    for line in report_lines(plan):
        print(line)
    if args.dry_run:
        print("Dry run: no files written.")
        return 0

    stem = os.path.splitext(out_pdf)[0]
    sidecar = stem + ".layout.json"
    try:
        folder = os.path.dirname(os.path.abspath(out_pdf))
        os.makedirs(folder, exist_ok=True)
        build_pdf(plan, out_pdf)
        written = [out_pdf]
        if not args.no_png:
            write_png(out_pdf, stem + ".png", args.png_dpi)
            written.append(stem + ".png")
        with open(sidecar, "w", encoding="utf-8") as handle:
            json.dump(sidecar_data(plan), handle, indent=2)
            handle.write("\n")
        written.append(sidecar)
    except (OSError, RuntimeError, ValueError) as err:
        print("ERROR: cannot write the output: %s" % err, file=sys.stderr)
        return 1
    print("Wrote: " + ", ".join(written))
    return 0


if __name__ == "__main__":
    sys.exit(main())
