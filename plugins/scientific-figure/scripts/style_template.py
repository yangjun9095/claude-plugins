"""One locked style for every AgenticCRE manuscript figure.

Why this module exists
----------------------
Figure 1 was assembled by hand in Affinity Designer and Figure 2 was built by a script with
its own private copy of the style constants. The two figures therefore drifted: different
line weights, two vocabularies for the same sub-agent, and panel letters set in different
sizes. Everything that decides how a mark looks now lives here, and both figures import it.

What it fixes, in the order the drift happened
----------------------------------------------
* :func:`apply` sets the whole rcParam block: the Avenir Light font chain, 8 pt for titles
  and axis labels, 6 pt for everything smaller, hairline spines, editable text in both PDF
  (TrueType, ``pdf.fonttype = 42``) and SVG (live text, ``svg.fonttype = "none"``), and
  ``savefig.bbox = "standard"`` so a figure keeps the exact width it was built at.
* :data:`WONG` is the Okabe-Ito colour-blind-safe palette. Nothing in either figure may use
  a colour that is not drawn from it or from the named semantic maps below.
* :data:`NAME` is the single source of truth for display names. A sub-agent is called the
  same thing in Figure 1, Figure 2 and the manuscript body, because all three read this dict.
* :func:`width_in` converts a Nature-Methods column count to inches, so a panel is never
  sized by eye.

Usage
-----
::

    import sys; sys.path.insert(0, "<this directory>")
    from agstyle import apply, WONG, NAME, width_in, panel_letter, save_all
    apply()
    fig = plt.figure(figsize=(width_in("full"), 2.4))
"""
from __future__ import annotations

import logging
from pathlib import Path

import matplotlib as mpl

__all__ = [
    "apply", "WONG", "FAMILY", "FAMILY_NAME", "ORGANISM", "OUTCOME", "AGENT", "AGENT_INK",
    "NAME", "FIG1_LABEL", "SHORT", "width_in", "MM", "HALF", "FULL", "BODY", "SMALL", "TINY",
    "panel_letter", "save_all", "tidy", "hairline", "GREY", "ax_at", "tint",
    "BASE", "TRACK", "OPTIM",
    "ACCENT", "STRUCT",
]

# ---------------------------------------------------------------------------
# Geometry.  Nature Methods: one column 85 mm, two columns 170 mm.
# ---------------------------------------------------------------------------

MM = 1 / 25.4
HALF = 85 * MM          # 3.35 in
FULL = 170 * MM         # 6.69 in
_WIDTHS = {"half": HALF, "full": FULL, "third": 56 * MM, "twothird": 113 * MM}


def width_in(which: str = "full", fraction: float = 1.0) -> float:
    """Width in inches of a panel spanning *which* column block.

    ``width_in("full")`` is 6.69 in (170 mm); ``width_in("full", 0.5)`` is half of that.
    """
    try:
        base = _WIDTHS[which]
    except KeyError:
        raise KeyError(f"unknown width {which!r}; valid: {', '.join(_WIDTHS)}") from None
    if not 0 < fraction <= 1.0:
        raise ValueError(f"fraction must be in (0, 1], got {fraction}")
    return base * fraction


# ---------------------------------------------------------------------------
# Type.  Nothing in a published panel may fall below TINY.
# ---------------------------------------------------------------------------

BODY, SMALL, TINY = 8, 6, 5        # titles/axis labels; ticks/legends/footers; superscripts
PANEL_LETTER_PT = 9

#: Avenir Light is licensed and installed per user (~/.local/share/fonts); it is never
#: committed. Without it the build falls back to Nunito Sans Light with no code change,
#: and the figure still renders at the same metrics.
FONT_CHAIN = ["Avenir Light", "Avenir", "Nunito Sans Light", "Arial", "DejaVu Sans"]
#: One cut heavier, for a panel letter or a word that must carry emphasis.
EMPH_CHAIN = ["Avenir", "Nunito Sans", "Arial", "DejaVu Sans"]

# ---------------------------------------------------------------------------
# Colour.  Okabe-Ito, colour-blind safe.  Every semantic map below draws from it.
# ---------------------------------------------------------------------------

WONG = dict(
    black="#000000", amber="#E69F00", sky="#56B4E9", green="#009E73",
    yellow="#F0E442", blue="#0072B2", vermillion="#D55E00", purple="#CC79A7",
)

#: Neutral greys for chrome. Nothing that encodes data may use these.
#:
#: ``band`` is the fill for a reference band that must survive an uncoated press. ``faint``
#: is a 10% step from paper, which a laser print can drop; ``band`` is a 17% step and is the
#: floor for any area fill a title's claim is checked against.
GREY = dict(rule="#B4B4B4", text="#6E6E6E", faint="#E6E6E6", mid="#8C8C8C", band="#D4D4D4")

#: Quiet greys carry the structure of a schematic; one accent marks the thing the figure
#: argues for, and nothing else in that panel may take it.
STRUCT = dict(
    text="#1F2328", muted="#6E7781", faint="#9AA4B2",
    card="#F4F6F8", edge="#CFD6DD", arrow="#7D8590",
)
ACCENT = WONG["blue"]
ACCENT_BG = "#E8F0FB"

#: Rubric families (Figure 2).
FAMILY = {"BIO": WONG["blue"], "DEC": WONG["purple"], "VER": WONG["vermillion"]}
FAMILY_NAME = {"BIO": "biology", "DEC": "decisions", "VER": "verification"}

#: Species (Figure 2 panel a).
ORGANISM = {"zebrafish": WONG["green"], "human": WONG["amber"], "mouse": WONG["sky"]}

#: Benchmark outcome. Ordered best-to-worst; the figure must keep this order everywhere.
#:
#: ``no verdict`` is a missing conclusion, and grey is the only honest colour for it: the
#: four hues above each name something the agent decided, and this names the absence of a
#: decision. It is nonetheless DATA, so it carries its own value and is not an entry of
#: :data:`GREY` -- a reader has to be able to tell a mark that encodes something from the
#: chrome around it, and a panel drawing this category in a chrome grey would also be
#: drawing a colour the chrome is free to change under it.
#:
#: It is darker than ``GREY["rule"]``, which it used to borrow. The one glyph that carries
#: it is an open ring, and at 181 printed grey a ring cannot lay down enough ink to read as
#: a mark without growing until it collides with the ``label unresolved`` annulus.
#:
#: The value is set by the PAIR it binds on, which is itself against ``label unresolved``:
#: those two are the only open rings in the vocabulary, so a reader separates them by tone
#: and by the dash and by nothing else. Amber sits at CIE L* 70.6. At ``#949494`` this grey
#: sat at L* 61.3, 9.3 apart, which falls to 5.8 under simulated protanopia -- two pale
#: rings a sixth of a lightness step apart. ``#767676`` is L* 49.6, which takes the pair to
#: 21.0 and keeps both inside the Okabe-Ito discipline, since only the neutral moves.
#: ``panel_fig2a.check_marks`` records all five L* values and asserts this pair on every
#: build.
#:
#: What makes it a data colour is not its distance from the chrome but its OWNERSHIP: it is
#: declared here, under this name, and the chrome cannot move it. It prints within a level
#: of ``STRUCT["muted"]``, which is type and never a mark, and 45 levels from the hairline
#: the brackets are drawn in.
OUTCOME = {
    "feasible": WONG["green"],
    "resolution-limited": WONG["sky"],
    "label unresolved": WONG["amber"],
    "biology impossible": WONG["vermillion"],
    "no verdict": "#767676",
}

#: The three sub-agents (Figure 1). One colour each, used in both panel a and panel b
#: so a reader can carry the mapping from the architecture into the worked example.
AGENT = {
    "orchestrator": WONG["black"],
    "biologist": WONG["green"],
    "aiml": WONG["blue"],
    "comp": WONG["purple"],
}

# ---------------------------------------------------------------------------
# Biological encodings.  These are SEPARATE from AGENT on purpose.
# ---------------------------------------------------------------------------

#: The four DNA bases.
#:
#: These may not borrow from :data:`AGENT`. AGENT means "which sub-agent owns this", and
#: painting adenine in the Biologist's green would assert a relationship between a base and a
#: role that does not exist. A colour in this figure names one thing; a colour that names two
#: is a colour a reader has to disambiguate from context, which is the work the figure is
#: meant to be doing for them.
#: Disjoint from AGENT as well as from TRACK. Green and blue are the Biologist and the AI/ML
#: Scientist, and a green adenine sitting inside the AI/ML column would be the Biologist's
#: colour appearing where the Biologist is not. That leaves amber, sky, vermillion and
#: yellow. Yellow is the weakest of the eight on white, which is why it is last in WONG; it
#: is tolerable here only because a base cell is a filled square with a stroke, not a line or
#: a dot.
#:
#: This map applies to art THIS CODE DRAWS. A cartoon reused from the author's own masters
#: carries the colours the author chose, and recolouring someone's finished art to satisfy a
#: palette is not a thing this module asks for.
BASE = {
    "A": WONG["amber"],
    "C": WONG["sky"],
    "G": WONG["vermillion"],
    "T": WONG["yellow"],
}

#: Predicted activity tracks, one per cell type, in the sequence-to-function cartoon.
#:
#: Disjoint from :data:`BASE`. The author's original art shares three hues between its base
#: colours and its cell-type track colours, so in that drawing a reader meeting a teal mark
#: cannot tell whether it means adenine or cell type 1 without checking which half of the
#: cartoon they are in. Keeping the two sets disjoint removes the question.
#:
#: The target track takes the AI/ML Scientist's own blue, and that reuse is deliberate.
#: THE RULE: a column may mark its OWN signal in its OWN agent colour; it may never use
#: another agent's colour. The tracks are the AI/ML Scientist's output, drawn inside the
#: AI/ML Scientist's column, so blue there reads as "this column's result". Purple in that
#: column would be the Comp Biologist's colour appearing where the Comp Biologist is not,
#: which is the error this rule exists to prevent.
#:
#: The off-targets are greys, so target against off-target is a figure-and-ground rather
#: than three equal series. That is also what the data says: one track is being optimized
#: and the others are being held down.
TRACK = {
    "target": WONG["blue"],
    "off1": GREY["mid"],
    "off2": GREY["rule"],
}

#: Target against off-target, for the optimization curve. The target rises and the
#: off-targets stay flat, so the pair is a figure-and-ground and not two equal series.
OPTIM = {"target": WONG["blue"], "offtarget": GREY["mid"]}

#: The darkened cut of each agent colour, for a STROKE or for TYPE. :data:`AGENT` stays the
#: fill, and the hue is unchanged, so a reader still carries one colour per sub-agent across
#: the figure.
#:
#: Okabe-Ito is safe for colour-vision deficiency and says nothing about luminance, and the
#: three Figure 1 roles come out of it at relative luminances that are 1.8 apart end to end:
#: ``#009E73`` 0.257, ``#0072B2`` 0.153, ``#CC79A7`` 0.312. Two things follow on the page.
#: Against white, 8 pt type in the green and the purple carries 3.42:1 and 3.06:1, both under
#: the 4.5:1 floor for text that size. And in a greyscale proof the purple column prints 38
#: levels paler than the blue one, which says the Computational Biologist's work is
#: secondary -- a weighting no panel of Figure 1 intends.
#:
#: Each value below is its ``AGENT`` colour scaled in sRGB until it prints at one greyscale
#: level, 118 by the Rec.709 conversion ``grey8`` uses, which also puts all three at 4.5:1
#: or better: green 4.52, blue 4.57, purple 4.56. Hue angle is untouched, so a deuteranope
#: still separates the three by the same CIELAB distances to within 4 units of the
#: undarkened set.
AGENT_INK = {
    "orchestrator": WONG["black"],
    "biologist": "#008762",
    "aiml": "#007BC0",
    "comp": "#A36185",
}

# ---------------------------------------------------------------------------
# Names.  The manuscript, Figure 1 and Figure 2 all read these.
# ---------------------------------------------------------------------------

#: Canonical display names. "AI/ML Research Scientist" is the agreed term; "ML coordinator"
#: is wrong and must never appear.
NAME = {
    "orchestrator": "Orchestrator",
    "biologist": "Biologist",
    "aiml": "AI/ML Research Scientist",
    "comp": "Comp Biologist",
    "harness": "knowledge harness",
    "bench": "CRE-DesignBench",
}

#: The spelling every Figure 1 panel PRINTS. ``NAME`` holds the agreed term, which is what
#: the manuscript body uses; this dict holds the one spelling a reader carries from panel a
#: to panel b to panel c. The two have to be separable, because panel a sets the name
#: inside a chip and panel c inside a legend row, and neither can hold "AI/ML Research
#: Scientist" at 8 pt. Panel b printed "AI/ML Research Scientist" and "Computational
#: Biologist" while panels a and c printed "AI/ML Scientist" and "Comp Biologist", so two
#: of the three roles changed spelling between the panels the colour key runs across.
#: Every Figure 1 panel reads this dict; nothing shortens a name locally.
FIG1_LABEL = dict(NAME, aiml="AI/ML Scientist")

#: Compact forms for a tick label or a glyph caption that cannot fit NAME.
SHORT = {
    "orchestrator": "orchestrator",
    "biologist": "biologist",
    "aiml": "AI/ML",
    "comp": "comp biol",
}


# ---------------------------------------------------------------------------
# Style
# ---------------------------------------------------------------------------

def _base_style():
    """Apply the figure-style plugin's defaults first, if it is installed.

    This module used to set every rcParam itself, which quietly forked a style that already
    had an owner. The `figure-style` skill is the general matplotlib layer: it sets the
    Tufte defaults, the type sizes and the editable-text flags, and it carries eighteen
    per-axes checks. This module is the MANUSCRIPT layer on top: exact column widths,
    canonical display names, semantic colour maps kept disjoint, and inch-from-top-left
    placement. Those are things a general plotting style has no business knowing.

    Starting from the plugin means a later improvement there reaches these figures, and it
    means one answer to "what is the house font size" instead of two that agree by luck.
    Missing plugin is not an error: the overrides below are complete on their own.
    """
    import sys
    from pathlib import Path
    for d in sorted(Path.home().glob(".claude/plugins/cache/*/figure-style/*/scripts")):
        if (d / "figure_helpers.py").exists():
            sys.path.insert(0, str(d))
            try:
                from figure_helpers import apply_style
                apply_style()
                return str(d)
            except Exception:
                return None
    return None


def apply() -> dict:
    """Apply the house style. Returns the resolved font family, for a build log."""
    logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
    base = _base_style()
    mpl.rcParams.update({
        # Naming the chain in font.family (not font.sans-serif) makes matplotlib fall back
        # per glyph, which matters because Nunito Sans has no Greek glyphs.
        "font.family": FONT_CHAIN,
        "font.sans-serif": FONT_CHAIN,
        "font.size": BODY,
        "axes.titlesize": BODY,
        "axes.labelsize": BODY,
        "xtick.labelsize": SMALL,
        "ytick.labelsize": SMALL,
        "legend.fontsize": SMALL,
        "legend.frameon": False,
        "legend.handlelength": 1.1,
        "legend.handletextpad": 0.5,
        "legend.columnspacing": 1.1,
        "legend.borderpad": 0.0,
        "axes.linewidth": 0.4,
        "xtick.major.width": 0.4,
        "ytick.major.width": 0.4,
        "xtick.major.size": 2.5,
        "ytick.major.size": 2.5,
        "xtick.minor.size": 1.5,
        "ytick.minor.size": 1.5,
        "lines.linewidth": 0.9,
        "patch.linewidth": 0.5,
        "axes.grid": False,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.facecolor": "white",
        "figure.facecolor": "white",
        "savefig.facecolor": "white",
        "savefig.dpi": 300,
        "figure.dpi": 150,
        # Editable text downstream: TrueType in the PDF, live text in the SVG.
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
        "svg.fonttype": "none",
        "svg.hashsalt": "agenticcre-figures",   # stable element ids across builds
        "figure.autolayout": False,
        # Keep the whole canvas, so a declared width stays exact and panels align when
        # two separately built figures sit on the same page.
        "savefig.bbox": "standard",
    })
    import matplotlib.font_manager as fm
    have = {f.name for f in fm.fontManager.ttflist}
    resolved = next((n for n in FONT_CHAIN if n in have), "DejaVu Sans")
    return {"font": resolved, "avenir": "Avenir Light" in have, "base": base}


def ax_at(fig, x_in, y_top_in, w_in, h_in, frame=False):
    """Place an axes by absolute inches, measured from the TOP-left of the figure.

    A page is read from the top down, so a layout written that way can be checked against
    the printed figure without arithmetic. A panel holding a schematic or an image starts
    with no axis furniture at all; a plot panel opts back in with ``frame=True``.
    """
    W, H = fig.get_size_inches()
    ax = fig.add_axes([x_in / W, 1 - (y_top_in + h_in) / H, w_in / W, h_in / H])
    if not frame:
        ax.set_xticks([])
        ax.set_yticks([])
        for s in ax.spines.values():
            s.set_visible(False)
    else:
        tidy(ax)
    return ax


def tint(color, amount=0.75):
    """Interpolate *color* toward white by *amount* (1.0 is white).

    A filled glyph uses the tint as its face and the saturated colour as its edge, so the
    glyph reads as one hue at two strengths rather than as two colours.
    """
    import matplotlib.colors as mcolors
    r, g, b = mcolors.to_rgb(color)
    return (r + (1 - r) * amount, g + (1 - g) * amount, b + (1 - b) * amount)


def hairline(ax, which=("left", "bottom"), color="#000000"):
    """Keep only the named spines, at hairline weight."""
    for side, spine in ax.spines.items():
        spine.set_visible(side in which)
        spine.set_linewidth(0.4)
        spine.set_color(color)


def tidy(ax, keep=("left", "bottom")):
    """Hairline spines, ticks only where a spine survives, no grid."""
    hairline(ax, keep)
    ax.tick_params(
        left="left" in keep, bottom="bottom" in keep,
        right=False, top=False,
        labelleft="left" in keep, labelbottom="bottom" in keep,
        width=0.4, length=2.5, pad=1.8, colors="#000000",
    )
    ax.grid(False)
    ax.set_axisbelow(True)


def panel_letter(fig_or_ax, letter, x=0.0, y=1.0, **kw):
    """Place a panel letter in the house weight and size.

    Letters are lowercase and bold, set from the figure's coordinate system so that two
    panels of different heights still carry their letters on the same baseline.
    """
    kw.setdefault("fontsize", PANEL_LETTER_PT)
    kw.setdefault("fontweight", "bold")
    kw.setdefault("fontfamily", EMPH_CHAIN)
    kw.setdefault("va", "top")
    kw.setdefault("ha", "left")
    return fig_or_ax.text(x, y, letter, **kw)


def save_all(fig, stem, verify=True):
    """Write PNG, PDF and SVG of *fig* to *stem* (a path without an extension).

    Returns the three paths. The PDF carries TrueType text and the SVG live text, so both
    stay editable in Illustrator and Affinity.
    """
    stem = Path(stem)
    stem.parent.mkdir(parents=True, exist_ok=True)
    out = {}
    for ext in ("png", "pdf", "svg"):
        p = stem.with_suffix("." + ext)
        fig.savefig(p, bbox_inches=None)
        out[ext] = p
    if verify:
        _verify_pdf_text(out["pdf"])
    return out


def _verify_pdf_text(path):
    """Warn if the PDF's text was broken into per-character runs, which makes it
    uneditable downstream. This is the failure mode that pdf.fonttype 42 prevents."""
    try:
        from pypdf import PdfReader
    except ImportError:
        return None
    try:
        txt = PdfReader(str(path)).pages[0].extract_text() or ""
    except Exception:
        return None
    words = [w for w in txt.split() if len(w) > 2]
    if txt and not words:
        print(f"  ! {path.name}: PDF text looks fragmented (no multi-character words)")
    return len(words)
