#!/usr/bin/env python3
"""Build the synthetic project for the comparison of generate-slides and generate-slides-minimal.

Run:  python3 make_project.py DEST
Out:  DEST/figures/fig1.png to fig8.png, DEST/notes.md and DEST/results.csv.

Every name and every number is made up. The study in notes.md does not exist. Four figures are bar
charts, three are scatter plots and one is a line plot. results.csv holds the numbers that the figures
show. Each number in the Results section of notes.md comes from results.csv by the rule that the
sentence names.

The study agrees with itself. Every group has a stated size, and every percentage follows from it.
Fig3, fig4 and fig6 plot the same 40 designs of the Heron set. The hit rates of the four rounds add up
to the number of fig3 points at or above the hit level. Each design that the notes name by an extreme
is the only one with that value.

The output is the same on every run on one machine. The script uses random.Random(42) in a fixed order.
It draws every text with the small default font of Pillow. It writes no time stamp, no text chunk and
no font path into a PNG. The script builds all files in memory and then writes them. It writes only
inside DEST and never overwrites a file.

Exit codes: 0 done, 2 when DEST cannot be used. DEST must be missing or an empty folder. The folder
above DEST must exist. After a write error the script removes what it wrote.
"""
import argparse
import csv
import io
import math
import random
import re
import sys
from collections import namedtuple
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

SEED = 42
WIDTH, HEIGHT = 2000, 1350
INK, GRID, ACCENT, GREY, DARK = "#111111", "#E5E7EB", "#6D4BD6", "#9CA3AF", "#374151"
PALETTE = (ACCENT, GREY, DARK)
FONT = ImageFont.load_default()
PLOT = (300, 230, WIDTH - 90, HEIGHT - 250)  # left, top, right, bottom of the plot area
CSV_COLUMNS = ("figure", "kind", "series", "x", "y")
NUMBER = re.compile(r"[0-9]+(?:\.[0-9]+)?")


def fmt(value):
    """Return a number as text: an integer without a decimal point, any other number with one decimal."""
    return str(int(value)) if value == int(value) else "{:.1f}".format(value)


# ---------------------------------------------------------------------------
# The made-up numbers
# ---------------------------------------------------------------------------

GROUP = 10  # designs in each round of the Heron set, and in each group of fig2
ROUND_HITS = (2, 3, 5, 7)  # hits among the designs of Round 1 to Round 4
TARGET_HITS = (("Designed", (6, 4, 8, 3, 5)), ("Control", (1, 2, 1, 1, 2)))  # hits on Target A to Target E
HIT_LEVEL = 50  # a hit has a binding signal of at least this many au
FILTER_LEVEL = 4  # the Mallard filter drops each design with an Osprey score below this value
OSPREY_RANGE = ((4.0, 6.8), (4.4, 7.6), (5.0, 9.0), (6.0, 10.0))  # the Osprey scores rise from round to round
ATTEMPTS = 5000

Design = namedtuple("Design", "osprey length signal melting")


def figure(number, kind, title, xlabel, ylabel, series):
    return {"id": "fig{}".format(number), "kind": kind, "title": title, "xlabel": xlabel, "ylabel": ylabel,
            "series": series}


def draw_design(rng, round_index):
    """Return one design. The signal rises with the Osprey score and falls with the length of the peptide."""
    osprey = round(rng.uniform(*OSPREY_RANGE[round_index]), 1)
    length = rng.randint(8, 40)
    signal = max(0.0, round(50 + 8 * (osprey - 7) - 0.9 * (length - 24) + rng.gauss(0, 9), 1))
    melting = round(45 + 3 * osprey + rng.gauss(0, 4), 1)
    return Design(osprey, length, signal, melting)


def draw_heron_set(rng):
    """Return the 40 designs of the Heron set, GROUP for each round. Round i holds ROUND_HITS[i] hits."""
    designs = []
    for index, hits in enumerate(ROUND_HITS):
        for _ in range(ATTEMPTS):
            batch = [draw_design(rng, index) for _ in range(GROUP)]
            if sum(1 for design in batch if design.signal >= HIT_LEVEL) == hits:
                designs += batch
                break
        else:
            raise RuntimeError("no batch of {} designs with {} hits".format(GROUP, hits))
    return designs


def unique_extreme(values, pick):
    """Return True when exactly one value equals the largest (pick=max) or the smallest (pick=min)."""
    values = list(values)
    return values.count(pick(values)) == 1


def extremes_are_unique(designs):
    """Return True when each extreme that notes.md names belongs to one design only."""
    osprey, length, signal, melting = zip(*designs)
    return (unique_extreme(osprey, max) and unique_extreme(length, max) and unique_extreme(length, min)
            and unique_extreme(signal, max) and unique_extreme(melting, max))


def assemble(rng, designs):
    """Return the eight figures as dicts. Each series is a list of (x, y) pairs."""
    rounds = ["Round 1", "Round 2", "Round 3", "Round 4"]
    targets = ["Target A", "Target B", "Target C", "Target D", "Target E"]
    yields = ["Design {}".format(i) for i in range(1, 7)]
    times = [0, 10, 20, 30, 40, 50, 60]

    def percent(hits):
        return [100 * count // GROUP for count in hits]

    return [
        figure(1, "bar", "Hit rate by round of the Heron set", "Round", "Hit rate (percent)",
               [("Heron set", list(zip(rounds, percent(ROUND_HITS))))]),
        figure(2, "bar", "Hit rate by target", "Target", "Hit rate (percent)",
               [(name, list(zip(targets, percent(hits)))) for name, hits in TARGET_HITS]),
        figure(3, "scatter", "Binding signal against Osprey score", "Osprey score", "Binding signal (au)",
               [("Heron set", sorted((d.osprey, d.signal) for d in designs))]),
        figure(4, "scatter", "Binding signal against peptide length", "Peptide length (residues)",
               "Binding signal (au)", [("Heron set", sorted((d.length, d.signal) for d in designs))]),
        figure(5, "bar", "Expression yield by design", "Design", "Yield (mg/L)",
               [("Heron set", list(zip(yields, [12, 30, 18, 44, 9, 27])))]),
        figure(6, "scatter", "Melting temperature against Osprey score", "Osprey score", "Melting temperature (C)",
               [("Heron set", sorted((d.osprey, d.melting) for d in designs))]),
        figure(7, "bar", "Cost per design by pipeline", "Pipeline", "Cost (units)",
               [("Cost", list(zip(["Manual", "Filtered", "Batched"], [100, 64, 41])))]),
        figure(8, "line", "Binding signal over time by concentration", "Time (minutes)", "Binding signal (au)",
               [("1 uM", saturating(rng, 30.0, 25.0, times)), ("5 uM", saturating(rng, 60.0, 20.0, times)),
                ("25 uM", saturating(rng, 95.0, 15.0, times))]),
    ]


def saturating(rng, vmax, tau, times):
    return [(t, round(max(0.0, vmax * (1 - math.exp(-t / tau)) + rng.gauss(0, 1.5)), 1)) for t in times]


def build_figures():
    """Return the eight figures. The loop redraws the study until no two results share a number and each extreme is unique."""
    rng = random.Random(SEED)
    for _ in range(ATTEMPTS):
        designs = draw_heron_set(rng)
        figures = assemble(rng, designs)
        numbers = [number for _, values in result_claims(figures) for number in values if NUMBER.fullmatch(number)]
        if extremes_are_unique(designs) and len(set(numbers)) == len(numbers):
            return figures
    raise RuntimeError("no study with unique extremes and distinct results")


def csv_bytes(figures):
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    for fig in figures:
        for name, points in fig["series"]:
            for x, y in points:
                writer.writerow([fig["id"], fig["kind"], name, x if isinstance(x, str) else fmt(x), fmt(y)])
    return buffer.getvalue().encode("utf-8")


# ---------------------------------------------------------------------------
# The notes
# ---------------------------------------------------------------------------

def lookup(figures, fig_id, series, x):
    for fig in figures:
        if fig["id"] == fig_id:
            for name, points in fig["series"]:
                if name == series:
                    return fmt(dict(points)[x])
    raise KeyError((fig_id, series, x))


def extreme(figures, fig_id, which, axis):
    """Return the point with the largest or smallest value on axis 0 (x) or 1 (y) of the first series of a figure."""
    points = next(fig for fig in figures if fig["id"] == fig_id)["series"][0][1]
    return (max if which == "max" else min)(points, key=lambda point: point[axis])


def result_claims(figures):
    """Return (sentence template, values) for each sentence of the Results section.

    A value is the text of a number or of a label such as Design 4. The template holds one {} for each value.
    """
    top_x = extreme(figures, "fig3", "max", 0)
    long_x, short_x = extreme(figures, "fig4", "max", 0), extreme(figures, "fig4", "min", 0)
    tm_top = extreme(figures, "fig6", "max", 1)
    best, worst = extreme(figures, "fig5", "max", 1), extreme(figures, "fig5", "min", 1)
    return [
        ("- The hit rate rose from {} percent in Round 1 to {} percent in Round 4 (fig1).",
         [lookup(figures, "fig1", "Heron set", "Round 1"), lookup(figures, "fig1", "Heron set", "Round 4")]),
        ("- On Target C the designed set reached {} percent and the control reached {} percent (fig2).",
         [lookup(figures, "fig2", "Designed", "Target C"), lookup(figures, "fig2", "Control", "Target C")]),
        ("- The design with the highest Osprey score, {}, gave a signal of {} au (fig3).",
         [fmt(top_x[0]), fmt(top_x[1])]),
        ("- The longest peptide, {} residues, gave {} au. The shortest, {} residues, gave {} au (fig4).",
         [fmt(long_x[0]), fmt(long_x[1]), fmt(short_x[0]), fmt(short_x[1])]),
        ("- {} gave the best yield, {} mg/L. {} gave the lowest, {} mg/L (fig5).",
         [best[0], fmt(best[1]), worst[0], fmt(worst[1])]),
        ("- The most stable design melted at {} C and had an Osprey score of {} (fig6).",
         [fmt(tm_top[1]), fmt(tm_top[0])]),
        ("- The Batched pipeline cost {} units per design. The Manual pipeline cost {} units (fig7).",
         [lookup(figures, "fig7", "Cost", "Batched"), lookup(figures, "fig7", "Cost", "Manual")]),
        ("- At 60 minutes the 25 uM series read {} au and the 1 uM series read {} au (fig8).",
         [lookup(figures, "fig8", "25 uM", 60), lookup(figures, "fig8", "1 uM", 60)]),
    ]


def figure_lines(figures):
    """Return the lines of the Figures section. Each count comes from the data of the figure."""
    size = dict((fig["id"], len(fig["series"][0][1])) for fig in figures)
    fig8 = next(fig for fig in figures if fig["id"] == "fig8")
    return [
        "- Fig1 shows the hit rate of each of the {} rounds of the Heron set. Each round holds {} designs.".format(
            size["fig1"], GROUP),
        "- Fig2 shows the hit rate on each of {} targets for {} designed peptides and for {} control peptides. "
        "These peptides do not belong to the Heron set.".format(size["fig2"], GROUP, GROUP),
        "- Fig3 plots the binding signal against the Osprey score of the {} designs of the Heron set.".format(
            size["fig3"]),
        "- Fig4 plots the binding signal against the peptide length of the same {} designs.".format(size["fig4"]),
        "- Fig5 shows the expression yield of {} designs of the Heron set.".format(size["fig5"]),
        "- Fig6 plots the melting temperature against the Osprey score of the same {} designs.".format(size["fig6"]),
        "- Fig7 shows the cost per design of {} pipelines.".format(size["fig7"]),
        "- Fig8 shows the binding signal of one reference design at {} concentrations. Each concentration has "
        "{} readings.".format(len(fig8["series"]), len(fig8["series"][0][1])),
    ]


def notes_bytes(figures):
    designs = len(next(fig for fig in figures if fig["id"] == "fig3")["series"][0][1])
    text = "\n".join([
        "# Kestrel assay study (made-up data)",
        "",
        "Every name and every number in this file is invented. The study did not take place.",
        "",
        "## Question",
        "",
        "Does the Osprey score pick designs that bind Target T in the Kestrel assay?",
        "",
        "## Methods",
        "",
        "- The Heron set holds {} designs of a fictional peptide family. The team built it in {} rounds of {} "
        "designs each.".format(designs, len(ROUND_HITS), GROUP),
        "- The Kestrel assay is a plate assay. It reads a binding signal in arbitrary units (au) every 10 minutes "
        "for 60 minutes.",
        "- The signal of a design is the reading at 60 minutes.",
        "- The Osprey score ranks a design from 0 to 10 before the assay.",
        "- The Mallard filter drops each design with an Osprey score below {}. Each design of the Heron set passed "
        "the filter.".format(FILTER_LEVEL),
        "- A hit is a design with a binding signal of at least {} au. The hit rate of a group is the share of its "
        "designs that are hits.".format(HIT_LEVEL),
        "",
        "## Figures",
        "",
    ] + figure_lines(figures) + [
        "",
        "## Results",
        "",
    ] + [template.format(*values) for template, values in result_claims(figures)] + [
        "",
        "## Caveats",
        "",
        "- The study ran once, on one plate layout.",
        "- The control peptides were not matched to the designed peptides for length.",
        "- Each number in the Results section comes from results.csv. Each figure shows numbers from the same file.",
        "",
    ])
    return text.encode("ascii")


# ---------------------------------------------------------------------------
# The figures
# ---------------------------------------------------------------------------

def put_text(image, x, y, string, color=INK, scale=4, align="left"):
    """Draw a text with the default font, enlarged by a whole factor so that it stays legible at slide size."""
    mask_size = FONT.getmask(string).size
    small = Image.new("L", mask_size, 0)
    ImageDraw.Draw(small).text((0, 0), string, fill=255, font=FONT)
    big = small.resize((mask_size[0] * scale, mask_size[1] * scale), Image.NEAREST)
    if align == "center":
        x -= big.size[0] // 2
    elif align == "right":
        x -= big.size[0]
    image.paste(color, (int(x), int(y)), big)


def nice_step(value):
    """Return the smallest of 1, 2, 2.5, 5 and 10 times a power of ten that is at least `value`."""
    magnitude = 10 ** math.floor(math.log10(value))
    for factor in (1, 2, 2.5, 5, 10):
        if value <= factor * magnitude:
            return factor * magnitude
    return 10 * magnitude


def y_limit(values):
    """Return the top of the y axis: five equal steps that hold the largest value with a margin."""
    return 5 * nice_step(max(values) * 1.05 / 5.0)


def x_limits(values):
    """Return (low, high, step) for a numeric x axis. The largest value lies inside the range."""
    low, high = min(values), max(values)
    step = nice_step((high - low) / 5.0)
    low = math.floor(low / step) * step
    end = low + math.ceil((high - low) / step) * step
    return low, (end + step if end <= high else end), step


def axis_frame(image, draw, fig, y_max, x_ticks):
    """Draw the title, the labels, the grid and the y ticks. `x_ticks` is a list of (pixel, label)."""
    left, top, right, bottom = PLOT
    put_text(image, left, 60, fig["title"], scale=6)
    put_text(image, left, top - 80, fig["ylabel"], DARK, scale=4)
    put_text(image, (left + right) // 2, bottom + 150, fig["xlabel"], DARK, scale=4, align="center")
    for step in range(6):
        value = y_max * step / 5.0
        y = bottom - (bottom - top) * step / 5.0
        draw.line([(left, y), (right, y)], fill=GRID, width=3)
        put_text(image, left - 24, y - 22, "{:g}".format(value), DARK, scale=4, align="right")
    draw.line([(left, top), (left, bottom)], fill=INK, width=5)
    draw.line([(left, bottom), (right, bottom)], fill=INK, width=5)
    for x, label in x_ticks:
        draw.line([(x, bottom), (x, bottom + 16)], fill=INK, width=4)
        put_text(image, x, bottom + 30, label, DARK, scale=4, align="center")


def legend(image, draw, names):
    _, top, right, _ = PLOT
    x = right
    for index in reversed(range(len(names))):
        width = FONT.getmask(names[index]).size[0] * 4
        x -= width
        put_text(image, x, top - 80, names[index], DARK, scale=4)
        draw.rectangle([x - 50, top - 76, x - 14, top - 40], fill=PALETTE[index % len(PALETTE)])
        x -= 110


def draw_bars(image, draw, fig):
    left, top, right, bottom = PLOT
    series = fig["series"]
    labels = [x for x, _ in series[0][1]]
    y_max = y_limit([y for _, points in series for _, y in points])
    slot = (right - left) / float(len(labels))
    bar = slot * 0.7 / len(series)
    ticks = [(left + slot * (i + 0.5), label) for i, label in enumerate(labels)]
    axis_frame(image, draw, fig, y_max, ticks)
    for s, (_, points) in enumerate(series):
        for i, (_, y) in enumerate(points):
            x0 = left + slot * i + slot * 0.15 + bar * s
            y0 = bottom - (bottom - top) * y / y_max
            draw.rectangle([x0, y0, x0 + bar, bottom - 3], fill=PALETTE[s % len(PALETTE)])
            put_text(image, x0 + bar / 2, y0 - 50, fmt(y), INK, scale=4, align="center")
    if len(series) > 1:
        legend(image, draw, [name for name, _ in series])


def x_position(value, low, high):
    left, _, right, _ = PLOT
    return left + (right - left) * (value - low) / float(high - low)


def draw_scatter(image, draw, fig):
    _, top, _, bottom = PLOT
    points = fig["series"][0][1]
    low, high, step = x_limits([x for x, _ in points])
    y_max = y_limit([y for _, y in points])
    values = [low + step * i for i in range(int(round((high - low) / step)) + 1)]
    ticks = [(x_position(v, low, high), "{:g}".format(v)) for v in values]
    axis_frame(image, draw, fig, y_max, ticks)
    for x, y in points:
        cx, cy = x_position(x, low, high), bottom - (bottom - top) * y / y_max
        draw.ellipse([cx - 13, cy - 13, cx + 13, cy + 13], fill=ACCENT)


def draw_lines(image, draw, fig):
    _, top, _, bottom = PLOT
    series = fig["series"]
    xs = [x for x, _ in series[0][1]]
    low, high = min(xs), max(xs)
    y_max = y_limit([y for _, points in series for _, y in points])
    ticks = [(x_position(v, low, high), "{:g}".format(v)) for v in xs]
    axis_frame(image, draw, fig, y_max, ticks)
    for s, (_, points) in enumerate(series):
        path = [(x_position(x, low, high), bottom - (bottom - top) * y / y_max) for x, y in points]
        draw.line(path, fill=PALETTE[s % len(PALETTE)], width=9)
        for cx, cy in path:
            draw.ellipse([cx - 14, cy - 14, cx + 14, cy + 14], fill=PALETTE[s % len(PALETTE)])
    legend(image, draw, [name for name, _ in series])


DRAWERS = {"bar": draw_bars, "scatter": draw_scatter, "line": draw_lines}


def png_bytes(fig):
    image = Image.new("RGB", (WIDTH, HEIGHT), "#FFFFFF")
    DRAWERS[fig["kind"]](image, ImageDraw.Draw(image), fig)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")  # no pnginfo, so no text chunk and no time chunk
    return buffer.getvalue()


# ---------------------------------------------------------------------------
# The files
# ---------------------------------------------------------------------------

def build_files():
    """Return a sorted list of (relative path, bytes) for every file of the project."""
    figures = build_figures()
    files = [("figures/{}.png".format(fig["id"]), png_bytes(fig)) for fig in figures]
    files += [("notes.md", notes_bytes(figures)), ("results.csv", csv_bytes(figures))]
    return sorted(files)


def check_dest(dest):
    """Return an error message when DEST cannot be used, else None."""
    if not dest.parent.is_dir():
        return "the folder above {} does not exist".format(dest)
    if dest.exists() or dest.is_symlink():
        if not dest.is_dir():
            return "{} exists and is not a folder".format(dest)
        if any(dest.iterdir()):
            return "{} is not empty".format(dest)
    return None


def write_files(dest, files):
    """Write the files into DEST. After a write error, remove what this call wrote and re-raise."""
    made_dest = False
    written, folders = [], []
    try:
        if not dest.exists():
            dest.mkdir()
            made_dest = True  # set after mkdir, so a failed mkdir leaves no folder to remove
        for relative, data in files:
            path = dest / relative
            if not path.parent.exists():
                path.parent.mkdir()
                folders.append(path.parent)
            with open(str(path), "xb") as handle:  # "x" refuses to overwrite
                written.append(path)
                handle.write(data)
    except OSError:
        for path in written:
            path.unlink()
        for folder in folders:
            folder.rmdir()
        if made_dest:
            dest.rmdir()
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(prog="make_project.py", description=__doc__.split("\n")[0])
    parser.add_argument("dest", metavar="DEST", help="the folder to fill; it must be missing or empty")
    args = parser.parse_args(argv)
    dest = Path(args.dest)
    problem = check_dest(dest)
    if problem is None:
        files = build_files()
        try:
            write_files(dest, files)
        except OSError as error:
            problem = "cannot write {}: {}".format(dest, error)
    if problem is not None:
        sys.stderr.write("make_project.py: error: {}\n".format(problem))
        return 2
    sys.stdout.write("wrote {} files to {}\n".format(len(files), dest))
    return 0


if __name__ == "__main__":
    sys.exit(main())
