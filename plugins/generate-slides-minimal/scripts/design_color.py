"""Color helpers for the slide linter: WCAG 2.1 contrast and a red-green check.

A color is a hex string such as "#6D4BD6" or an (r, g, b) tuple.
Each channel is an integer from 0 to 255. No function rounds its result.
"""
import re
from fractions import Fraction

# A palette designed for readers with color vision deficiency (Okabe and Ito).
# The name-to-hex mapping comes from a secondary source.
OKABE_ITO = [
    "#000000",
    "#E69F00",
    "#56B4E9",
    "#009E73",
    "#F0E442",
    "#0072B2",
    "#D55E00",
    "#CC79A7",
]

# Contrast ratio below which a red and a green mark count as a conflict.
RED_GREEN_MIN_RATIO = 3.0

# Limits of the "red" and "green" hue bands. Hue is in degrees. The saturation
# and lightness limits are exact fractions, so no float rounding moves a color
# across a limit.
_RED_BELOW = 15
_RED_FROM = 345
_GREEN_FROM = 75
_GREEN_TO = 165
_MIN_SATURATION = Fraction(2, 5)
_MIN_LIGHTNESS = Fraction(3, 20)
_MAX_LIGHTNESS = Fraction(17, 20)

_HEX = re.compile(r"\A#?([0-9A-Fa-f]{6})\Z")


def parse_hex(text):
    """Return (r, g, b) for "#RRGGBB" or "RRGGBB". Raise ValueError otherwise."""
    if not isinstance(text, str):
        raise ValueError("a color must be a hex string, got {!r}".format(text))
    match = _HEX.match(text)
    if match is None:
        raise ValueError("not a #RRGGBB color: {!r}".format(text))
    digits = match.group(1)
    return (int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16))


def _to_rgb(color):
    """Return an (r, g, b) tuple for a hex string or a tuple of three channels."""
    if isinstance(color, str):
        return parse_hex(color)
    try:
        channels = tuple(color)
    except TypeError:
        raise ValueError("not a color: {!r}".format(color))
    valid = len(channels) == 3 and all(
        isinstance(v, int) and not isinstance(v, bool) and 0 <= v <= 255
        for v in channels
    )
    if not valid:
        raise ValueError("an rgb color needs three integers from 0 to 255: {!r}".format(color))
    return channels


def relative_luminance(rgb):
    """Return the WCAG 2.1 relative luminance, from 0.0 for black to 1.0 for white."""
    linear = []
    for value in _to_rgb(rgb):
        c = value / 255
        linear.append(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4)
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(a, b):
    """Return the WCAG 2.1 contrast ratio of two colors, from 1.0 to 21.0."""
    la = relative_luminance(a)
    lb = relative_luminance(b)
    light, dark = (la, lb) if la >= lb else (lb, la)
    return (light + 0.05) / (dark + 0.05)


def hue_band(rgb):
    """Return "red", "green" or "other" for a color.

    A color can be "red" or "green" only with saturation of at least 0.4
    and lightness from 0.15 to 0.85.
    """
    r, g, b = _to_rgb(rgb)
    high, low = max(r, g, b), min(r, g, b)
    spread = high - low
    total = high + low
    if spread == 0:
        return "other"
    lightness = Fraction(total, 510)
    saturation = Fraction(spread, total if total <= 255 else 510 - total)
    if saturation < _MIN_SATURATION or not _MIN_LIGHTNESS <= lightness <= _MAX_LIGHTNESS:
        return "other"
    if high == r:
        sector = Fraction(g - b, spread) % 6
    elif high == g:
        sector = Fraction(b - r, spread) + 2
    else:
        sector = Fraction(r - g, spread) + 4
    hue = 60 * sector
    if hue < _RED_BELOW or hue >= _RED_FROM:
        return "red"
    if _GREEN_FROM <= hue <= _GREEN_TO:
        return "green"
    return "other"


def red_green_conflict(a, b):
    """Return True when one color is red, the other is green, and the ratio is below 3.0."""
    bands = {hue_band(a), hue_band(b)}
    if bands != {"red", "green"}:
        return False
    return contrast_ratio(a, b) < RED_GREEN_MIN_RATIO
