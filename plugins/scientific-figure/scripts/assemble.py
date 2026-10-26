#!/usr/bin/env python
"""Stack the finished AgenticCRE panel PDFs into the final figure pages, keeping vector.

What this does
--------------
Each panel is already a complete one-page PDF, 170 mm wide, drawn by its own
``panel_*.py`` script with its own panel letter. This script only places those pages
onto a taller page. It draws nothing. It adds no panel letters. It does not rasterise.

    Figure1.pdf   = panel_fig1a + panel_fig1b + panel_fig1c, top to bottom
    Figure2.pdf   = panel_fig2a + panel_fig2b + panel_fig2c, top to bottom
    FigureSI.pdf  = panel_figSI, copied byte for byte (it is already a composite)

Why pypdf and not matplotlib
----------------------------
Re-drawing a panel through matplotlib, or pasting a PNG of it, would throw away the
embedded font subsets and the vector paths. ``pypdf.PageObject.merge_transformed_page``
copies the panel's content stream and its resource dictionary onto a blank page under a
translation, so the glyphs stay glyphs and the lines stay lines.

The interpreter at /home/yang-joon.kim/.conda/envs/litemind_env/bin/python carries
pypdf 6.19.0, so the pypdf path is the one this script uses and the one that was tested.
There is no ghostscript fallback. A ghostscript composition path would be untested dead
code here, so if pypdf is ever missing the script stops and prints the pip command
instead of guessing.

Page geometry
-------------
The page width is 170 mm = 481.889764 pt, the width every panel already has.
The page height is a sum, never a constant:

    height = 2 * margin + sum(panel heights) + gap * (number of panels - 1)

The margin is vertical only. The panels are already exactly page-width, so a left or
right margin would push them off the page. Every panel is placed at x = 0, which makes
the left edges align by construction rather than by eye.

Re-running
----------
Panels are rebuilt by other processes while this runs. The script re-reads every panel
from disk on each run and overwrites its outputs, so re-running after a panel changes is
the normal way to use it. A figure whose panels are not all present yet is skipped with
a message naming each missing file, and the other figures are still built. The exit
status is 1 if anything was skipped.

Usage
-----
    python assemble.py                      # all three figures, 2 mm gap, 1 mm margin
    python assemble.py --gap 3 --margin 1.5 # tune spacing without editing this file
    python assemble.py --only fig1          # rebuild one figure
    python assemble.py --no-png             # skip the 300 dpi renders
"""
import argparse
import os
import shutil
import subprocess
import sys

MM = 72.0 / 25.4                      # points per millimetre
PAGE_W_MM = 170.0
PAGE_W = PAGE_W_MM * MM               # 481.889764 pt
WIDTH_TOL = 1.0                       # pt; a panel further off than this is an error

FIGDIR = "/hpc/projects/data.science/yangjoon.kim/github_repos/agenticCRE/analysis/manuscript-figs/figures"

# name -> (list of panel stems, output stem).  An empty panel list means "copy through".
FIGURES = {
    "fig1": (["panel_fig1a", "panel_fig1b", "panel_fig1c"], "Figure1"),
    "fig2": (["panel_fig2a", "panel_fig2b", "panel_fig2c"], "Figure2"),
    "figSI": (["panel_figSI"], "FigureSI"),
}
PASSTHROUGH = {"figSI"}               # copied unchanged, not re-composed


def die(msg):
    print("ERROR: " + msg, file=sys.stderr)
    raise SystemExit(2)


try:
    from pypdf import PdfReader, PdfWriter, Transformation
except ImportError:                                           # pragma: no cover
    die("pypdf is not installed for %s.\n"
        "       Install it with:  %s -m pip install --user pypdf\n"
        "       This script has no ghostscript fallback; see the module docstring."
        % (sys.executable, sys.executable))


# --------------------------------------------------------------------------------------
# Composition
# --------------------------------------------------------------------------------------

def panel_path(stem, figdir):
    return os.path.join(figdir, stem + ".pdf")


def missing_panels(stems, figdir):
    """Return the panel paths that are not on disk or are empty."""
    out = []
    for stem in stems:
        p = panel_path(stem, figdir)
        if not os.path.exists(p) or os.path.getsize(p) == 0:
            out.append(p)
    return out


def read_panels(stems, figdir, allow_width_mismatch):
    """Open every panel and return [(stem, reader, page, width, height)].

    The readers are returned with the pages because pypdf resolves a merged page's
    indirect objects lazily. A reader that is garbage-collected before the writer runs
    takes its content stream with it.
    """
    panels = []
    for stem in stems:
        path = panel_path(stem, figdir)
        try:
            reader = PdfReader(path)
        except Exception as exc:
            die("cannot read %s as a PDF (%s). The panel may be mid-rebuild; "
                "re-run this script." % (path, exc))
        if len(reader.pages) != 1:
            die("%s has %d pages; a panel must have exactly 1."
                % (path, len(reader.pages)))
        page = reader.pages[0]
        w = float(page.mediabox.width)
        h = float(page.mediabox.height)
        if abs(w - PAGE_W) > WIDTH_TOL and not allow_width_mismatch:
            die("%s is %.3f pt wide, not the expected %.3f pt (%g mm). Rebuild the "
                "panel at full width, or pass --allow-width-mismatch to centre it."
                % (path, w, PAGE_W, PAGE_W_MM))
        panels.append((stem, reader, page, w, h))
    return panels


def compose(stems, out_pdf, figdir, gap_pt, margin_pt, allow_width_mismatch):
    """Stack the panel pages top to bottom onto one page. Returns the page height."""
    panels = read_panels(stems, figdir, allow_width_mismatch)

    heights = [h for (_, _, _, _, h) in panels]
    page_h = 2.0 * margin_pt + sum(heights) + gap_pt * (len(heights) - 1)

    writer = PdfWriter()
    sheet = writer.add_blank_page(width=PAGE_W, height=page_h)

    # PDF user space has its origin at the bottom-left, so "top to bottom" counts down
    # from the top of the sheet.
    cursor = page_h - margin_pt
    placed = []
    for i, (stem, _reader, page, w, h) in enumerate(panels):
        cursor -= h
        tx = -float(page.mediabox.left)
        if allow_width_mismatch and abs(w - PAGE_W) > WIDTH_TOL:
            tx += (PAGE_W - w) / 2.0
        ty = cursor - float(page.mediabox.bottom)
        sheet.merge_transformed_page(page, Transformation().translate(tx, ty),
                                     over=True, expand=False)
        placed.append((stem, w, h, tx, cursor))
        if i < len(panels) - 1:
            cursor -= gap_pt

    tmp = out_pdf + ".tmp"
    with open(tmp, "wb") as fh:
        writer.write(fh)
    os.replace(tmp, out_pdf)           # atomic: a reader never sees a half-written page

    print("  stacked %d panel(s):" % len(placed))
    for stem, w, h, tx, y in placed:
        print("    %-14s %8.3f x %7.3f pt   at x=%.3f  y=%.3f" % (stem, w, h, tx, y))
    print("  page: %.3f x %.3f pt  (%.2f x %.2f mm)"
          % (PAGE_W, page_h, PAGE_W / MM, page_h / MM))
    print("  height = 2*%.3f margin + %.3f panels + %d*%.3f gaps"
          % (margin_pt, sum(heights), len(heights) - 1, gap_pt))
    return page_h


def passthrough(stems, out_pdf, figdir):
    """Copy a panel that is already a finished composite."""
    src = panel_path(stems[0], figdir)
    shutil.copyfile(src, out_pdf)
    print("  copied %s unchanged" % src)
    try:
        return float(PdfReader(out_pdf).pages[0].mediabox.height)
    except Exception:
        return None


# --------------------------------------------------------------------------------------
# Verification
# --------------------------------------------------------------------------------------

def run(cmd):
    """Run a command, return (ok, combined output). A missing tool is not fatal."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True)
    except FileNotFoundError:
        return False, "%s not found on PATH" % cmd[0]
    return p.returncode == 0, (p.stdout or "") + (p.stderr or "")


def render_png(pdf, dpi):
    stem = os.path.splitext(pdf)[0]
    ok, out = run(["pdftoppm", "-png", "-r", str(dpi), "-singlefile", pdf, stem])
    if not ok:
        print("  WARNING: pdftoppm failed: %s" % out.strip())
        return None
    png = stem + ".png"
    print("  rendered %s (%d dpi, %.1f kB)" % (png, dpi, os.path.getsize(png) / 1024.0))
    return png


def verify(pdf, expect_h):
    """Report page size, embedded fonts and raster object count. Returns True if sane."""
    ok_size = True

    ok, out = run(["pdfinfo", pdf])
    size_line = ""
    for line in out.splitlines():
        if line.startswith("Page size:"):
            size_line = line.strip()
    if size_line:
        print("  pdfinfo:  %s" % size_line)
        try:
            nums = size_line.split(":", 1)[1].replace("pts", "").split("x")
            w = float(nums[0]); h = float(nums[1])
            if abs(w - PAGE_W) > 0.05:
                print("  WARNING: width %.3f pt is not 170 mm (%.3f pt)" % (w, PAGE_W))
                ok_size = False
            if expect_h is not None and abs(h - expect_h) > 0.05:
                print("  WARNING: height %.3f pt is not the computed %.3f pt"
                      % (h, expect_h))
                ok_size = False
        except (IndexError, ValueError):
            pass
    else:
        print("  pdfinfo:  unavailable (%s)" % out.strip()[:80])

    ok, out = run(["pdffonts", pdf])
    rows = [l for l in out.splitlines()[2:] if l.strip()]
    # Columns run: name type encoding emb sub uni object-number generation-number.
    # Counting from the right survives a font name that contains a space.
    emb = sub = 0
    for l in rows:
        t = l.split()
        if len(t) >= 5:
            emb += t[-5] == "yes"
            sub += t[-4] == "yes"
    print("  pdffonts: %d font(s), %d embedded, %d subset(s)" % (len(rows), emb, sub))
    for l in rows:
        print("            %s" % l.rstrip())
    if rows and emb == 0:
        print("  WARNING: no embedded font. Text may have been converted to outlines.")

    ok, out = run(["pdfimages", "-list", pdf])
    irows = [l for l in out.splitlines()[2:] if l.strip()]
    print("  pdfimages: %d raster object(s) carried through" % len(irows))
    for l in irows[:12]:
        print("            %s" % l.rstrip())
    if len(irows) > 12:
        print("            ... %d more" % (len(irows) - 12))
    return ok_size


# --------------------------------------------------------------------------------------

def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Stack AgenticCRE panel PDFs into the final figures, keeping vector.")
    ap.add_argument("--gap", type=float, default=2.0,
                    help="inter-panel gap in mm (default 2)")
    ap.add_argument("--margin", type=float, default=1.0,
                    help="outer top/bottom margin in mm (default 1)")
    ap.add_argument("--dpi", type=int, default=300,
                    help="dpi for the PNG beside each PDF (default 300)")
    ap.add_argument("--figdir", default=FIGDIR,
                    help="directory holding the panels and the outputs")
    ap.add_argument("--only", action="append", choices=sorted(FIGURES),
                    help="build only this figure; repeatable")
    ap.add_argument("--no-png", action="store_true", help="skip the PNG render")
    ap.add_argument("--allow-width-mismatch", action="store_true",
                    help="centre an off-width panel instead of stopping")
    args = ap.parse_args(argv)

    if args.gap < 0 or args.margin < 0:
        die("--gap and --margin must not be negative")

    gap_pt = args.gap * MM
    margin_pt = args.margin * MM
    wanted = args.only or ["fig1", "fig2", "figSI"]

    print("figdir: %s" % args.figdir)
    print("gap:    %g mm (%.3f pt)      margin: %g mm (%.3f pt)"
          % (args.gap, gap_pt, args.margin, margin_pt))

    skipped, built, bad = [], [], []
    for name in wanted:
        stems, out_stem = FIGURES[name]
        out_pdf = os.path.join(args.figdir, out_stem + ".pdf")
        print("\n=== %s -> %s ===" % (name, out_pdf))

        gone = missing_panels(stems, args.figdir)
        if gone:
            print("  SKIPPED. Missing panel(s):")
            for p in gone:
                print("    %s" % p)
            skipped.append((name, gone))
            continue

        if name in PASSTHROUGH:
            page_h = passthrough(stems, out_pdf, args.figdir)
        else:
            page_h = compose(stems, out_pdf, args.figdir, gap_pt, margin_pt,
                             args.allow_width_mismatch)

        if not verify(out_pdf, page_h):
            bad.append(name)
        if not args.no_png:
            render_png(out_pdf, args.dpi)
        built.append(out_pdf)

    print("\n=== summary ===")
    for p in built:
        print("  built   %s" % p)
    for name, gone in skipped:
        print("  SKIPPED %s: %s" % (name, ", ".join(os.path.basename(g) for g in gone)))
    if bad:
        print("  CHECK   geometry warning on: %s" % ", ".join(bad))
    if skipped:
        print("\n%d figure(s) could not be built because panels are missing. "
              "Re-run once they exist." % len(skipped))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
