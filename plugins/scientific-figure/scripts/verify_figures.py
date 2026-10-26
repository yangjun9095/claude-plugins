"""The gate every AgenticCRE figure passes before it reaches the manuscript.

A panel can look right and still be wrong in a way a reader will catch: type below the
journal's floor, a colour nobody can name, a path pointing at an AI mock-up, text outlined
so the author cannot edit it. Each check below exists because that failure is cheap to make
and expensive to find in proof.

Run it with no arguments to check everything:

    python verify_figures.py

It exits non-zero if any check fails, so it can gate a build.
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIGS = HERE.parent / "figures"
MM = 25.4 / 72          # points -> mm

#: Nature Methods: 170 mm across two columns. A figure that is not this wide will be scaled
#: by the typesetter, and every type size in it will move with it.
TARGET_W_PT = 170 / MM  # 481.89 pt
W_TOL_PT = 0.5

#: Anything a reader must read sits at 6 pt. 5 pt is allowed only for a unit or a scale-bar
#: label. Below 5 pt is a defect whatever it says.
MIN_PT = 5.0

MAIN = ["Figure1", "Figure2", "FigureSI"]

failures: list[str] = []
warnings: list[str] = []


def fail(msg):
    failures.append(msg)
    print(f"  FAIL  {msg}")


def warn(msg):
    warnings.append(msg)
    print(f"  warn  {msg}")


def ok(msg):
    print(f"  ok    {msg}")


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True).stdout


# ---------------------------------------------------------------- geometry
def check_geometry():
    print("\nGEOMETRY  (170 mm wide, height derived not guessed)")
    for name in MAIN:
        pdf = FIGS / f"{name}.pdf"
        if not pdf.exists():
            fail(f"{name}.pdf is missing")
            continue
        out = run(["pdfinfo", str(pdf)])
        m = re.search(r"Page size:\s+([\d.]+) x ([\d.]+)", out)
        if not m:
            fail(f"{name}: could not read page size")
            continue
        w, h = float(m.group(1)), float(m.group(2))
        if abs(w - TARGET_W_PT) > W_TOL_PT:
            fail(f"{name}: width {w:.2f} pt = {w * MM:.2f} mm, expected {TARGET_W_PT:.2f} pt (170 mm)")
        else:
            ok(f"{name}: {w * MM:.1f} x {h * MM:.1f} mm")
        if h > 235 / MM:
            fail(f"{name}: height {h * MM:.0f} mm exceeds a 235 mm page")


# ---------------------------------------------------------------- text
def check_text_editable():
    print("\nTEXT  (embedded subsets, still editable, nothing outlined)")
    for name in MAIN:
        pdf = FIGS / f"{name}.pdf"
        if not pdf.exists():
            continue
        fonts = run(["pdffonts", str(pdf)])
        rows = [r for r in fonts.splitlines()[2:] if r.strip()]
        if not rows:
            fail(f"{name}: no fonts at all -- text was converted to outlines and cannot be edited")
            continue
        not_embedded = [r.split()[0] for r in rows if " no " in f" {r.split()[3] if len(r.split()) > 3 else ''} "]
        txt = run(["pdftotext", "-q", str(pdf), "-"])
        words = [w for w in txt.split() if len(w) > 2]
        if len(words) < 10:
            fail(f"{name}: only {len(words)} extractable words -- text is probably fragmented")
        else:
            ok(f"{name}: {len(rows)} font subsets, {len(words)} extractable words")
        if not_embedded:
            fail(f"{name}: fonts not embedded: {not_embedded}")


# ---------------------------------------------------------------- type size
def check_type_size():
    print(f"\nTYPE SIZE  (nothing below {MIN_PT} pt)")
    pat = re.compile(r"fontsize\s*=\s*([0-9.]+)")
    for script in sorted(HERE.glob("panel_*.py")):
        src = script.read_text()
        small = sorted({float(v) for v in pat.findall(src) if float(v) < MIN_PT})
        if small:
            fail(f"{script.name}: literal fontsize below {MIN_PT} pt: {small}")
        else:
            ok(f"{script.name}: no literal size below {MIN_PT} pt")


# ---------------------------------------------------------------- provenance
def check_no_mockups():
    print("\nPROVENANCE  (no AI mock-up may reach a published figure)")
    # A line that forbids the path is not a line that uses it. Skip guards, negations and
    # prose; flag only something that reads like a path actually being consumed.
    GUARD = re.compile(r"assert|not in|never|!=|raise|forbid|must not", re.I)
    bad = []
    for script in sorted(HERE.glob("*.py")):
        if script.name == Path(__file__).name:
            continue
        for i, line in enumerate(script.read_text().splitlines(), 1):
            if "imagegen" not in line and "mockup" not in line.lower():
                continue
            if GUARD.search(line) or line.lstrip().startswith("#"):
                continue
            bad.append(f"{script.name}:{i}: {line.strip()[:90]}")
    if bad:
        for b in bad:
            fail(f"references AI mock-up art: {b}")
    else:
        ok("no panel script references imagegen/ or a mockup file")


# ---------------------------------------------------------------- colour
def check_palette():
    print("\nCOLOUR  (every colour from agstyle; a literal hex in a panel is a bug)")
    hexpat = re.compile(r"[\"']#[0-9A-Fa-f]{3,8}[\"']")
    # Pure white and pure black are not palette choices: they are paper and ink, and a
    # contrast test legitimately picks between them.
    NEUTRAL = {"#fff", "#ffffff", "#000", "#000000"}
    for script in sorted(HERE.glob("panel_*.py")):
        hits = []
        for i, line in enumerate(script.read_text().splitlines(), 1):
            found = [h.strip("\"'").lower() for h in hexpat.findall(line)]
            found = [h for h in found if h not in NEUTRAL]
            if found:
                s = line.strip()
                if s.startswith("#"):
                    continue
                hits.append(f"{i}: {s[:80]}")
        if hits:
            warn(f"{script.name}: {len(hits)} literal hex colour(s); first is {hits[0]}")
        else:
            ok(f"{script.name}: no literal hex")


# ---------------------------------------------------------------- data
def check_data_assertions():
    print("\nDATA  (every Figure 2 number re-derived from source)")
    r = subprocess.run([sys.executable, str(HERE / "fig2data.py")],
                       capture_output=True, text=True)
    if r.returncode != 0:
        fail("fig2data.py self-check failed:\n" + (r.stderr or "")[-700:])
    else:
        for line in r.stdout.strip().splitlines():
            ok(line.strip())


# ---------------------------------------------------------------- raster
def check_raster_budget():
    print("\nRASTER  (reused BioRender art must clear 300 dpi at its printed size)")
    for name in MAIN:
        pdf = FIGS / f"{name}.pdf"
        if not pdf.exists():
            continue
        out = run(["pdfimages", "-list", str(pdf)])
        rows = [r.split() for r in out.splitlines()[2:] if r.strip()]
        if not rows:
            ok(f"{name}: fully vector, no raster objects")
            continue
        low = []
        for r in rows:
            try:
                xppi = int(r[12])
            except (IndexError, ValueError):
                continue
            if xppi < 300:
                low.append(xppi)
        if low:
            fail(f"{name}: {len(low)} raster object(s) below 300 ppi: {sorted(low)[:6]}")
        else:
            ok(f"{name}: {len(rows)} raster object(s), all at or above 300 ppi")


def main():
    print("=" * 74)
    print("AgenticCRE figure verification")
    print("=" * 74)
    check_geometry()
    check_text_editable()
    check_type_size()
    check_no_mockups()
    check_palette()
    check_data_assertions()
    check_raster_budget()
    print("\n" + "=" * 74)
    if failures:
        print(f"{len(failures)} FAILURE(S), {len(warnings)} warning(s)")
        for f in failures:
            print(f"  - {f}")
        return 1
    print(f"all checks passed, {len(warnings)} warning(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
