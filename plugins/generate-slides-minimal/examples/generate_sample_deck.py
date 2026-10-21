#!/usr/bin/env python3
"""Build the sample deck of generate-slides-minimal.

Run:  python3 generate_sample_deck.py [--output PATH]
Out:  sample-deck.pptx in the folder of this script, or the PATH that you give.

The deck has eight slides and uses all six layouts. Every number is made up. Pillow draws
the one picture into a temporary folder. The script adds the scripts folder of the plugin
to sys.path from its own location, so it runs from any folder.

The deck is also a model for the builder script that the command writes: it loads the style,
builds each slide with a helper, passes alt text for the picture and the chart, passes
a sentence headline to the take-home slide, and writes notes for every slide but the title slide.
The test tests/test_docs.py lints the committed deck under the peers profile for 12 minutes.
"""
import argparse
import shutil
import sys
import tempfile
from collections import OrderedDict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "scripts"))

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

import slide_helpers as sh  # noqa: E402
import style as st  # noqa: E402

DEFAULT_OUTPUT = HERE / "sample-deck.pptx"
SOURCE = "Made-up data for this sample deck."

# Pillow draws the picture. These names are tried in turn. With none of them the figure uses the
# small default font of Pillow, which is hard to read at slide size.
FONT_NAMES = ("DejaVuSans.ttf", "LiberationSans-Regular.ttf", "Arial.ttf", "Helvetica.ttc")
FIGURE_PPI = 240  # pixels per inch over the evidence area


def load_font(size):
    for name in FONT_NAMES:
        try:
            return ImageFont.truetype(name, size)
        except (IOError, OSError):
            continue
    return ImageFont.load_default()


def text_size(draw, text, font):
    """Return (width, height) of a text in pixels."""
    if hasattr(draw, "textbbox"):
        left, top, right, bottom = draw.textbbox((0, 0), text, font=font)
        return right - left, bottom - top
    return draw.textsize(text, font=font)


def draw_schedule_figure(path, style):
    """Draw three 24-hour bars, one for each light schedule. The 16-hour bar has the accent color."""
    colors = style["colors"]
    width = int(round(style["layout"]["evidence_width"] * FIGURE_PPI))
    height = int(round(style["layout"]["evidence_height"] * FIGURE_PPI))
    image = Image.new("RGB", (width, height), colors["background"])
    draw = ImageDraw.Draw(image)
    label_font, small_font = load_font(60), load_font(50)
    left, right = 330, width - 70
    track_color = "#E5E7EB"
    rows = (("8 h", 8, colors["context"], colors["text"]),
            ("12 h", 12, colors["context"], colors["text"]),
            ("16 h", 16, colors["accent"], "#FFFFFF"))
    top, bar_height, gap = 130, 220, 110
    for index, (name, hours, fill, ink) in enumerate(rows):
        y = top + index * (bar_height + gap)
        draw.rectangle([left, y, right, y + bar_height], fill=track_color)
        edge = left + (right - left) * hours // 24
        draw.rectangle([left, y, edge, y + bar_height], fill=fill)
        label_width, label_height = text_size(draw, name, label_font)
        draw.text((left - 40 - label_width, y + (bar_height - label_height) // 2 - 8), name,
                  fill=colors["text"], font=label_font)
        _, light_height = text_size(draw, "light on", small_font)
        draw.text((left + 40, y + (bar_height - light_height) // 2 - 6), "light on", fill=ink, font=small_font)
        if index == 0:
            dark_width, dark_height = text_size(draw, "dark", small_font)
            draw.text((right - 40 - dark_width, y + (bar_height - dark_height) // 2 - 6), "dark",
                      fill=colors["muted"], font=small_font)
    axis_y = top + 3 * bar_height + 2 * gap + 40
    for hour in (0, 6, 12, 18, 24):
        x = left + (right - left) * hour // 24
        draw.line([x, axis_y - 20, x, axis_y], fill=colors["muted"], width=5)
        tick = str(hour)
        tick_width, _ = text_size(draw, tick, small_font)
        draw.text((x - tick_width // 2, axis_y + 8), tick, fill=colors["text"], font=small_font)
    title = "Hour of the day"
    title_width, _ = text_size(draw, title, small_font)
    draw.text(((left + right - title_width) // 2, axis_y + 86), title, fill=colors["text"], font=small_font)
    image.save(str(path))
    return path


def build(output):
    """Build the deck and save it to `output`."""
    style = st.load_style("peers", "light")
    prs = sh.new_presentation(style)
    props = prs.core_properties
    props.title = "Sample deck of generate-slides-minimal"
    props.author = props.last_modified_by = "Sample Author"

    folder = tempfile.mkdtemp()
    try:
        figure = draw_schedule_figure(Path(folder) / "schedules.png", style)

        sh.add_title_slide(
            prs, style, "Seedlings grow faster under a 16-hour light schedule",
            author="Sample Author", affiliation="Sample deck with made-up data", date="October 2026")

        sh.add_roadmap_slide(
            prs, style, "A longer light schedule raises seedling height in this made-up trial",
            [("Need", "Indoor seedlings lag"), ("Approach", "Three light schedules"),
             ("Evidence", "Height by day 20"), ("Take-homes", "Longer light helps")],
            notes="The talk has four parts. First the need: indoor seedlings grow slowly. Then the approach, "
                  "a trial with three schedules. Then the evidence from the height curves. Last, the results "
                  "that you should take with you.")

        sh.add_assertion_evidence_slide(
            prs, style, "Indoor seedlings reach less than half the field height by day 20",
            {"kind": "table",
             "rows": [["Setting", "Height on day 20"], ["Field plot", "24 cm"], ["Indoor, 8 h light", "10 cm"]],
             "highlight": (2, 0)},
            callouts=["A gap of 14 cm on day 20"], source=SOURCE,
            notes="This is the need. A field plot gives seedlings 24 centimeters on day 20. The same seedlings "
                  "indoors, with the usual eight hours of light, reach 10. Ask the room what a grower loses "
                  "with that gap before you show the trial.")

        sh.add_assertion_evidence_slide(
            prs, style, "The trial compares three light schedules on 90 seedlings",
            {"kind": "picture", "path": figure,
             "alt": "Three bars on a 24-hour axis show light on for 8, 12 and 16 hours. The 16-hour bar is purple."},
            callouts=["30 seedlings per schedule", "Same soil, water and temperature"], source=SOURCE,
            notes="Each bar is one day. The light is on for the shaded part. The 16-hour schedule is the new one, "
                  "so it carries the accent color. We changed nothing else: each group has 30 seedlings in the "
                  "same soil, with the same water and temperature.")

        sh.add_assertion_evidence_slide(
            prs, style, "The 16-hour schedule gives the tallest seedlings by day 20",
            {"kind": "chart", "chart": "line",
             "categories": ["Day 0", "Day 5", "Day 10", "Day 15", "Day 20"],
             "series": OrderedDict([("8 h", [2.0, 4.1, 6.3, 8.2, 10.0]), ("12 h", [2.0, 4.4, 7.0, 9.4, 11.5]),
                                    ("16 h", [2.0, 4.8, 7.9, 10.9, 14.0])]),
             "highlight": "16 h",
             "alt": "Line chart of mean seedling height from day 0 to day 20 for three light schedules. "
                    "The 16-hour line ends highest, at 14 centimeters."},
            callouts=["Height in cm, mean of 30 seedlings", "The gap opens by day 10"], source=SOURCE,
            notes="All three groups start at 2 centimeters. The lines part by day 10, when the 16-hour group "
                  "stands at 7.9 against 6.3 for the 8-hour group. On day 20 the order is clear. The curves show "
                  "means, so say that the spread sits on the backup slide.")

        sh.add_big_number_slide(
            prs, style, "The 16-hour schedule adds 40 percent to the height on day 20",
            "+40%", "taller than the 8-hour schedule", "Baseline: the 8-hour schedule, 10 cm on day 20.",
            source=SOURCE,
            notes="Forty percent is 14 centimeters against 10. The 12-hour schedule gives 11.5, which is 15 "
                  "percent. Name the baseline out loud, because a percentage means little without it.")

        sh.add_take_home_slide(
            prs, style,
            [("The 16-hour schedule raised height by 40 percent", "Baseline: the 8-hour schedule, 10 cm on day 20"),
             ("The 12-hour schedule raised height by 15 percent", "Baseline: the same 8-hour schedule"),
             ("The 16-hour group led by day 10, at 7.9 cm", "Baseline: the 8-hour group, 6.3 cm on day 10")],
            headline="Longer light gave taller seedlings, and the gain grew with the hours",
            notes="Leave this slide up during questions. Say the three claims in your own words. Each one "
                  "names its baseline, so a question about a number has an answer on the screen.")

        sh.add_assertion_evidence_slide(
            prs, style, "Mean height on day 20 rises with the hours of light",
            {"kind": "table",
             "rows": [["Schedule", "Mean (cm)", "SD (cm)", "n"], ["8 h", "10.0", "1.1", "30"],
                      ["12 h", "11.5", "1.3", "30"], ["16 h", "14.0", "1.6", "30"]],
             "highlight": (3, 0)},
            source=SOURCE, backup=True,
            notes="Use this slide if someone asks about the spread. The standard deviation grows a little with "
                  "the hours of light. Each group has 30 seedlings.")

        prs.save(str(output))
    finally:
        shutil.rmtree(folder)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build the sample deck of generate-slides-minimal.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT), help="the .pptx file to write")
    args = parser.parse_args(argv)
    build(Path(args.output))
    print("wrote {}".format(args.output))


if __name__ == "__main__":
    main()
