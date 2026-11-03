#!/usr/bin/env python3
"""Score one deck for the comparison of generate-slides and generate-slides-minimal.

Run:  python3 score_deck.py DECK --minutes N [--profile peers] [--theme light|dark] [--no-notes]
Out:  five parts on stdout, as UTF-8 text that build_results.py reads with a strict parser.

    settings: profile=peers minutes=12 theme=light notes=on
    findings:
    slide 3: words-per-slide: warn: T3: 31 words on the slide; keep at most 25. Cut the text ...
    deck: slide-count: warn: T2: 14 main slides for 12 minutes; keep at most 12. Cut slides ...
    ghost deck:
    slide 1: A made up talk about binder design
    slide 2: (no title)
    words per slide:
    slide 1: 6 words
    slide 2: 12 words
    errors: 0 warnings: 2

The findings use the rows of design_lint.format_finding. The ghost deck lists the title of every slide in
order. It finds each title with pptx_resolve.find_title.

The word count of a slide is the count that the words-per-slide rule uses. It covers all words of all
shapes, except the title, the source line and the footer shapes. The count covers every slide, also a
take-home slide, which the rule skips.

A slide that python-pptx cannot read shows as `(unreadable)` and `unreadable`. A hidden slide is listed
and counted, but the linter applies no rule to it.

Exit codes: 0 when the deck has no finding of severity error, 1 when it has at least one. 2 when the deck
or an option cannot be used, and also for any error that nobody expected, with one message on stderr.
The script calls design_lint.lint in the same process with the arguments that design_lint.main passes.
"""
import argparse
import os
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[2] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from pptx.oxml.ns import qn  # noqa: E402

import design_lint as dl  # noqa: E402
import pptx_resolve as rs  # noqa: E402
import style  # noqa: E402

NO_TITLE = "(no title)"
UNREADABLE_TITLE = "(unreadable)"
UNREADABLE_WORDS = "unreadable"


def write_utf8(stream, text):
    """Write text to a stream as UTF-8 bytes, whatever the locale says. A lone surrogate becomes "?"."""
    buffer = getattr(stream, "buffer", None)
    if buffer is None:  # a stream of text only, such as the stand-in of a test
        stream.write(text)
        return
    stream.flush()
    buffer.write(text.encode("utf-8", "replace"))
    buffer.flush()


def settings_line(profile, minutes, theme, notes):
    return "settings: profile={} minutes={:g} theme={} notes={}".format(profile, minutes, theme,
                                                                         "on" if notes else "off")


def title_text(slide):
    """Return the title text on one line, or "(no title)". The text joins the paragraphs as the title rule does."""
    title = rs.find_title(slide)
    element = None if title is None else getattr(title, "_element", None)
    if element is None:
        return NO_TITLE
    text = " ".join(rs.paragraph_text(p) for p in element.iter(qn("a:p")))
    return " ".join(text.split()) or NO_TITLE


def slide_rows(path, profile, theme):
    """Return [(number, title, words)] for every slide in order. words is None for a slide that cannot be read."""
    prs = dl._open(path)
    cfg = style.load_style(profile, theme, None)
    slides, unreadable = dl._slides(prs)
    by_number = dict(slides)
    cache = {}
    rows = []
    for number in range(1, len(slides) + len(unreadable) + 1):
        if number in unreadable:
            rows.append((number, UNREADABLE_TITLE, None))
            continue
        slide = by_number[number]
        ctx = dl._Slide(prs, slide, number, cfg, cache)
        # The same sum as the words-per-slide rule: a leaf with a role (title, source, chrome) does not count.
        words = sum(leaf.words for leaf in ctx.leaves if leaf.role is None)
        rows.append((number, title_text(slide), words))
    return rows


def score_text(path, minutes, profile="peers", theme="light", notes=True):
    """Return (text, errors). Raise ValueError or OSError for a deck or an option that cannot be used."""
    findings = dl.lint(path, profile, minutes, theme, notes, None)
    rows = slide_rows(path, profile, theme)
    errors = sum(1 for finding in findings if finding.severity == "error")
    lines = [settings_line(profile, minutes, theme, notes), "findings:"]
    lines += [dl.format_finding(finding) for finding in findings]
    lines.append("ghost deck:")
    lines += ["slide {}: {}".format(number, title) for number, title, _ in rows]
    lines.append("words per slide:")
    lines += ["slide {}: {}".format(number, UNREADABLE_WORDS if words is None else "{} words".format(words))
              for number, _, words in rows]
    lines.append("errors: {} warnings: {}".format(errors, len(findings) - errors))
    return "\n".join(lines) + "\n", errors


def main(argv=None):
    parser = argparse.ArgumentParser(prog="score_deck.py", description="Score a .pptx deck with the design linter.")
    parser.add_argument("deck", metavar="DECK", help="the .pptx file")
    parser.add_argument("--minutes", type=dl._minutes, required=True, help="the length of the talk in minutes")
    parser.add_argument("--profile", default="peers", choices=style.PROFILES)
    parser.add_argument("--theme", default="light", choices=style.THEMES)
    parser.add_argument("--no-notes", action="store_true", help="switch the notes rules off")
    args = parser.parse_args(argv)
    try:
        if not os.path.isfile(args.deck):
            raise OSError("no such file: {}".format(args.deck))
        text, errors = score_text(args.deck, args.minutes, args.profile, args.theme, not args.no_notes)
        write_utf8(sys.stdout, text)
    except (ValueError, OSError) as error:  # these errors have a message by design, so no type name
        dl._write(sys.stderr, "score_deck.py: error: {}\n".format(dl._clean(error, 300)))
        return 2
    except Exception as error:  # a defect that nobody expected: report it with its type and exit 2
        dl._write(sys.stderr, "score_deck.py: error: {}: {}\n".format(type(error).__name__, dl._clean(error, 300)))
        return 2
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
