"""Fills and charts for the design linter: what color sits behind text and marks.

Chart reading works on the XML of the chart part. A fill reader gives ("solid", hex),
("none", None) or ("unknown", None). A color with a transform, or a theme color that
this module cannot resolve, is unknown.
"""
import re
from collections import namedtuple

from pptx.oxml.ns import qn

import pptx_resolve as rs


def srgb(solid_fill):
    """Return "#RRGGBB" for an a:solidFill with one plain srgbClr, else None."""
    children = [child for child in solid_fill if isinstance(child.tag, str)]
    if len(children) != 1 or children[0].tag != qn("a:srgbClr") or len(children[0]):
        return None
    value = children[0].get("val") or ""
    return "#" + value.upper() if re.fullmatch(r"[0-9A-Fa-f]{6}", value) else None


def fill_of(props):
    """Return ("solid", hex), ("none", None), ("unknown", None), or None when props has no fill element."""
    for child in [] if props is None else list(props):
        if child.tag == qn("a:noFill"):
            return "none", None
        if child.tag == qn("a:solidFill"):
            color = srgb(child)
            return ("solid", color) if color else ("unknown", None)
        if child.tag in rs.FILL_TAGS:
            return "unknown", None
    return None


def _truthy(element, default="1"):
    return element is not None and element.get("val", default) in ("1", "true")


def _shows(dlbls):
    return any(_truthy(dlbls.find(qn(tag))) for tag in ("c:showVal", "c:showSerName"))


_LINE_PLOTS = frozenset(qn(name) for name in ("c:lineChart", "c:scatterChart", "c:radarChart"))
_AXES = frozenset(qn(name) for name in ("c:catAx", "c:valAx", "c:dateAx", "c:serAx"))
_SHOW_FLAGS = ".//c:showVal | .//c:showSerName | .//c:showCatName | .//c:showPercent"
Series = namedtuple("Series", "name colors labelled")


class Chart(object):
    """The colors, the text and the fill of a chart, read from the XML of its part.

    `texts` lists (size in pt or None, color or None) for each text element that shows.
    `background` is the hex color behind the marks and the text, or None with the reason in `why`.
    `slide_background` is the color that shows through when no chart level sets a fill.
    """

    def __init__(self, shape, name, slide_background):
        self.shape, self.name, self.texts, self.series = shape, name, [], []
        self.background, self.why = slide_background, "slide background unresolved"
        try:
            root = shape.chart_part._element
        except rs.READ_ERRORS:
            return
        self._read_background(root)
        self._read_texts(root)
        self.series = [self._read_series(ser) for ser in root.xpath(".//c:ser")]

    def _read_background(self, root):
        """The plot area wins over the chart area. A level with no fill lets the next level show through."""
        for path in ("c:chart/c:plotArea/c:spPr", "c:spPr"):
            found = fill_of((root.xpath(path) or [None])[0])
            if found is not None and found[0] != "none":
                self.background, self.why = found[1], "chart fill unknown"
                return

    def _read_texts(self, root):
        default = self._text_props((root.xpath("c:txPr//a:defRPr") or [None])[0], (None, None))
        elements = root.xpath("c:chart/c:title | c:chart/c:legend")
        axes = [el for el in root.xpath("c:chart/c:plotArea/*") if el.tag in _AXES]
        elements += [axis for axis in axes if not _truthy(axis.find(qn("c:delete")))]
        elements += [d for d in root.xpath(".//c:dLbls") if any(_truthy(f) for f in d.xpath(_SHOW_FLAGS))]
        for element in elements:
            for props in element.xpath(".//a:defRPr | .//a:rPr") or [None]:
                record = self._text_props(props, default)
                if record not in self.texts:
                    self.texts.append(record)

    @staticmethod
    def _text_props(props, default):
        """Return (size, color) of an a:defRPr or a:rPr. A value that props does not set comes from `default`."""
        size, color = default
        raw = None if props is None else props.get("sz")
        if raw is not None:
            size = int(raw) / 100.0 if re.fullmatch(r"[0-9]+", raw) and int(raw) > 0 else None
        fill = None if props is None else props.find(qn("a:solidFill"))
        return size, (color if fill is None else srgb(fill))

    @staticmethod
    def _mark_color(props, line_is_mark):
        """Return the color of the mark that an a:spPr or c:spPr draws, or None.

        A direct a:solidFill gives the color. Any other direct fill element (no fill, a gradient) gives None.
        Without a direct fill element, the theme fills a bar or an area, so the color is unknown. A line,
        scatter or radar series (line_is_mark) is drawn by its line, and then the line of a:ln gives the color.
        """
        direct = props.find(qn("a:solidFill"))
        if direct is not None:
            return srgb(direct)
        if not line_is_mark or any(child.tag in rs.FILL_TAGS for child in props):
            return None
        line = props.find(qn("a:ln"))
        solid = None if line is None else line.find(qn("a:solidFill"))
        return None if solid is None else srgb(solid)

    @staticmethod
    def _read_series(ser):
        """Return the name, the explicit colors and whether the series has data labels."""
        colors = []
        line_is_mark = ser.getparent().tag in _LINE_PLOTS
        for path in ("c:spPr", "c:dPt/c:spPr", "c:marker/c:spPr", "c:dPt/c:marker/c:spPr"):
            for props in ser.xpath(path):
                # The line of a marker is its edge, which can be white on a marker that the theme fills.
                color = Chart._mark_color(props, line_is_mark and "marker" not in path)
                if color and color not in colors:
                    colors.append(color)
        own = ser.find(qn("c:dLbls"))
        if own is not None:  # the labels of the series replace the labels of the plot
            labelled = _shows(own) or any(not _truthy(d.find(qn("c:delete"))) for d in own.findall(qn("c:dLbl")))
        else:
            shared = ser.getparent().find(qn("c:dLbls"))
            labelled = shared is not None and _shows(shared)
        title = ser.xpath("c:tx//c:v")
        return Series(title[0].text if title and title[0].text else "unnamed", colors, labelled)


def fill_and_color(slide, target, is_cell):
    """Return the fill state ("solid", "none", "unknown") and the color of a shape or a table cell.

    pptx_resolve says "unknown" for a placeholder with no fill element, because its layout or master
    may fill it. This function asks inherited_fill_state(). A placeholder that no level fills has no fill.
    """
    state = rs.fill_state(target)
    if state == "solid":
        return state, rs.fill_color(target)
    if state == "unknown" and not is_cell and rs.placeholder_element(target) is not None:
        return rs.inherited_fill_state(slide, target), rs.inherited_fill_color(slide, target)
    return state, None
