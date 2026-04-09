"""Figure styling helpers for Claude Code figure-style skill.

Provides:
- apply_style()       — load the bundled mplstyle + set seaborn defaults
- verify_figure(fig)  — run all quality checks on a matplotlib Figure
- save_figure(fig, path, **kw) — save with verification + sane defaults

Usage:
    from figure_helpers import apply_style, save_figure
    apply_style()

    fig, ax = plt.subplots()
    ax.plot(x, y)
    ax.set_xlabel("X label")
    ax.set_ylabel("Y label")
    save_figure(fig, "output.png")   # verifies before saving
"""

import subprocess
import sys
from pathlib import Path

try:
    import matplotlib
except ImportError:
    subprocess.check_call(
        [sys.executable, "-m", "pip", "install", "matplotlib", "-q"],
        stdout=subprocess.DEVNULL,
    )
    import matplotlib

import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.figure import Figure

try:
    import seaborn as sns
    _HAS_SEABORN = True
except ImportError:
    _HAS_SEABORN = False

try:
    import yaml as _yaml
except ImportError:
    _yaml = None

# ============================================================================
# Paths
# ============================================================================
_SCRIPT_DIR = Path(__file__).resolve().parent
_DEFAULT_MPLSTYLE = _SCRIPT_DIR / "publication.mplstyle"


# ============================================================================
# Style Application
# ============================================================================

def apply_style(mplstyle_path=None, seaborn_context="notebook",
                seaborn_style="white", font_scale=1.0):
    """Apply the publication style globally.

    Args:
        mplstyle_path: Path to a custom .mplstyle file. If None, uses the
            bundled publication.mplstyle.
        seaborn_context: Seaborn context preset ("notebook", "talk", "paper",
            "poster"). Controls relative scaling of font/line elements.
        seaborn_style: Seaborn style preset ("white", "whitegrid", "dark", etc.)
        font_scale: Additional font scaling multiplier for seaborn.
    """
    style_path = Path(mplstyle_path) if mplstyle_path else _DEFAULT_MPLSTYLE
    if style_path.exists():
        plt.style.use(str(style_path))
    else:
        print(f"WARNING: Style file not found: {style_path}. Using matplotlib defaults.")

    if _HAS_SEABORN:
        sns.set_context(seaborn_context, font_scale=font_scale)
        sns.set_style(seaborn_style)
        # Re-apply our style on top (seaborn resets some rcParams)
        if style_path.exists():
            plt.style.use(str(style_path))


def apply_style_talk():
    """Shortcut: larger fonts/lines for presentations."""
    apply_style(seaborn_context="talk", font_scale=1.2)


def apply_style_paper():
    """Shortcut: compact sizing for journal figures."""
    apply_style(seaborn_context="paper", font_scale=1.0)


def apply_style_poster():
    """Shortcut: largest elements for posters."""
    apply_style(seaborn_context="poster", font_scale=1.3)


# ============================================================================
# Color Palettes
# ============================================================================

# Colorblind-safe qualitative palette (8 colors, Wong 2011 + extensions)
PALETTE_QUAL = [
    "#036DEA",  # blue
    "#E6550D",  # orange
    "#31A354",  # green
    "#756BB1",  # purple
    "#E7298A",  # pink
    "#66C2A5",  # teal
    "#FC8D62",  # salmon
    "#8DA0CB",  # periwinkle
]

# Diverging palette endpoints
PALETTE_DIV = {"low": "#2166AC", "mid": "#F7F7F7", "high": "#B2182B"}

# Sequential palette
PALETTE_SEQ = {"low": "#F7FBFF", "high": "#08306B"}


def get_palette(n=None, name="qual"):
    """Get a color palette.

    Args:
        n: Number of colors needed. For 'qual', wraps if n > 8.
        name: 'qual' (qualitative), 'div' (diverging), 'seq' (sequential).
    """
    if name == "qual":
        if n is None:
            return list(PALETTE_QUAL)
        return [PALETTE_QUAL[i % len(PALETTE_QUAL)] for i in range(n)]
    elif name == "div" and _HAS_SEABORN:
        return sns.diverging_palette(220, 15, as_cmap=True, center="light")
    elif name == "seq" and _HAS_SEABORN:
        return sns.light_palette(PALETTE_SEQ["high"], as_cmap=True)
    return list(PALETTE_QUAL[:n])


# ============================================================================
# Verification Harness
# ============================================================================

class FigureCheck:
    """Result of a single quality check."""

    def __init__(self, name, passed, severity="warn", details=""):
        self.name = name
        self.passed = passed
        self.severity = severity  # "warn" or "fail"
        self.details = details

    def __repr__(self):
        status = "PASS" if self.passed else self.severity.upper()
        s = f"  [{status}] {self.name}"
        if self.details:
            s += f" — {self.details}"
        return s


def _is_auxiliary_axes(ax):
    """Check if an axes is a colorbar, inset, or manually-placed axes."""
    if hasattr(ax, '_colorbar_info') or ax.get_label() == '<colorbar>':
        return True
    # Axes created via fig.add_axes() for colorbars are often very narrow
    pos = ax.get_position()
    if pos.width < 0.06 or pos.height < 0.06:
        return True
    return False


def _check_labels(fig):
    """Every axis should have x and y labels (non-empty)."""
    issues = []
    data_axes = [ax for ax in fig.get_axes() if not _is_auxiliary_axes(ax)]

    # Detect shared axes: if axes share x or y, only one needs the label
    for i, ax in enumerate(data_axes):
        ax_id = f"Axes[{i}]"
        xl = ax.get_xlabel().strip()
        yl = ax.get_ylabel().strip()

        # For shared axes, skip label check if a sibling has the label
        if not xl:
            shared_x = ax.get_shared_x_axes().get_siblings(ax)
            if not any(s.get_xlabel().strip() for s in shared_x if s is not ax):
                issues.append(f"{ax_id}: missing x-label")
        if not yl:
            shared_y = ax.get_shared_y_axes().get_siblings(ax)
            if not any(s.get_ylabel().strip() for s in shared_y if s is not ax):
                issues.append(f"{ax_id}: missing y-label")
    if issues:
        return FigureCheck("axis_labels", False, "warn",
                           "; ".join(issues))
    return FigureCheck("axis_labels", True)


def _check_font_sizes(fig, min_size=7):
    """All text elements should be at least min_size pt."""
    small = []
    for text_obj in fig.findobj(matplotlib.text.Text):
        txt = text_obj.get_text().strip()
        if not txt:
            continue
        size = text_obj.get_fontsize()
        if size < min_size:
            preview = txt[:30] + ("..." if len(txt) > 30 else "")
            small.append(f'"{preview}" is {size:.0f}pt (min {min_size}pt)')
    if small:
        return FigureCheck("font_sizes", False, "warn",
                           "; ".join(small[:5]))
    return FigureCheck("font_sizes", True)


def _check_font_consistency(fig):
    """All text should use the same font family (excluding math)."""
    families = set()
    for text_obj in fig.findobj(matplotlib.text.Text):
        txt = text_obj.get_text().strip()
        if not txt or txt.startswith("$"):
            continue
        families.add(text_obj.get_fontfamily()[0] if text_obj.get_fontfamily() else "unknown")
    # Allow up to 2 families (one body + one mono is OK)
    if len(families) > 2:
        return FigureCheck("font_consistency", False, "warn",
                           f"Found {len(families)} font families: {', '.join(sorted(families))}")
    return FigureCheck("font_consistency", True)


def _check_title(fig):
    """Figure or axes should have a title (informational, not enforced)."""
    has_title = bool(fig._suptitle and fig._suptitle.get_text().strip())
    if not has_title:
        for ax in fig.get_axes():
            if ax.get_title().strip():
                has_title = True
                break
    if not has_title:
        return FigureCheck("title_present", True, "warn",
                           "No title set (OK if captioned externally)")
    return FigureCheck("title_present", True)


def _check_figure_size(fig, min_w=3, min_h=2, max_w=20, max_h=15):
    """Figure dimensions should be reasonable."""
    w, h = fig.get_size_inches()
    issues = []
    if w < min_w or h < min_h:
        issues.append(f"Figure too small: {w:.1f}x{h:.1f}in (min {min_w}x{min_h})")
    if w > max_w or h > max_h:
        issues.append(f"Figure too large: {w:.1f}x{h:.1f}in (max {max_w}x{max_h})")
    aspect = w / h if h > 0 else 999
    if aspect > 4 or aspect < 0.25:
        issues.append(f"Extreme aspect ratio: {aspect:.1f}:1")
    if issues:
        return FigureCheck("figure_size", False, "warn", "; ".join(issues))
    return FigureCheck("figure_size", True,
                       details=f"{w:.1f}x{h:.1f}in, aspect {w/h:.2f}:1")


def _check_spines(fig):
    """Top and right spines should be hidden (clean style)."""
    issues = []
    for i, ax in enumerate(fig.get_axes()):
        if hasattr(ax, '_colorbar_info') or ax.get_label() == '<colorbar>':
            continue
        top = ax.spines['top'].get_visible()
        right = ax.spines['right'].get_visible()
        if top and right:
            issues.append(f"Axes[{i}]: top+right spines visible")
    if issues:
        return FigureCheck("clean_spines", False, "warn",
                           "; ".join(issues[:3]))
    return FigureCheck("clean_spines", True)


def _check_legend_overlap(fig):
    """Legend should not overlap the data area significantly."""
    issues = []
    for i, ax in enumerate(fig.get_axes()):
        legend = ax.get_legend()
        if legend is None:
            continue
        # Check if legend is inside axes and potentially large
        bbox = legend.get_window_extent(fig.canvas.get_renderer())
        ax_bbox = ax.get_window_extent(fig.canvas.get_renderer())
        if bbox.width > ax_bbox.width * 0.4:
            issues.append(f"Axes[{i}]: legend is >{40}% of axes width — consider placing outside")
    if issues:
        return FigureCheck("legend_overlap", False, "warn", "; ".join(issues))
    return FigureCheck("legend_overlap", True)


def _check_colorbar_overlap(fig):
    """Colorbars should not overlap plot data area."""
    # This is a heuristic: if there's a colorbar axes that significantly
    # overlaps with a non-colorbar axes, flag it.
    axes_list = fig.get_axes()
    cbar_axes = []
    data_axes = []
    for ax in axes_list:
        if hasattr(ax, '_colorbar_info') or ax.get_label() == '<colorbar>':
            cbar_axes.append(ax)
        else:
            data_axes.append(ax)

    issues = []
    renderer = fig.canvas.get_renderer()
    for cb_ax in cbar_axes:
        cb_bbox = cb_ax.get_window_extent(renderer)
        for d_ax in data_axes:
            d_bbox = d_ax.get_window_extent(renderer)
            overlap = cb_bbox.intersection(cb_bbox, d_bbox)
            if overlap is not None and overlap.width > 5 and overlap.height > 5:
                issues.append("Colorbar overlaps a data axes")
                break

    if issues:
        return FigureCheck("colorbar_overlap", False, "fail", "; ".join(issues))
    return FigureCheck("colorbar_overlap", True)


def _check_dpi(fig, min_dpi=150):
    """Figure DPI should meet minimum for the intended use."""
    dpi = fig.get_dpi()
    if dpi < min_dpi:
        return FigureCheck("dpi", False, "warn",
                           f"DPI is {dpi:.0f} (min {min_dpi} for screen, 300 for print)")
    return FigureCheck("dpi", True, details=f"{dpi:.0f} DPI")


def _check_overlapping_text(fig):
    """Detect text elements that overlap each other."""
    renderer = fig.canvas.get_renderer()
    text_objs = [t for t in fig.findobj(matplotlib.text.Text)
                 if t.get_text().strip() and t.get_visible()]
    bboxes = []
    for t in text_objs:
        try:
            bb = t.get_window_extent(renderer)
            if bb.width > 0 and bb.height > 0:
                bboxes.append((t.get_text().strip()[:20], bb))
        except Exception:
            continue

    overlaps = []
    for i in range(len(bboxes)):
        for j in range(i + 1, len(bboxes)):
            inter = bboxes[i][1].intersection(bboxes[i][1], bboxes[j][1])
            if inter is not None:
                area_i = bboxes[i][1].width * bboxes[i][1].height
                area_inter = inter.width * inter.height
                if area_i > 0 and area_inter / area_i > 0.3:
                    overlaps.append(f'"{bboxes[i][0]}" overlaps "{bboxes[j][0]}"')
    if overlaps:
        return FigureCheck("text_overlap", False, "warn",
                           "; ".join(overlaps[:3]))
    return FigureCheck("text_overlap", True)


def _check_white_background(fig):
    """Figure and axes backgrounds should be white (or transparent)."""
    fig_color = fig.get_facecolor()
    # (1,1,1,1) is white, (1,1,1,0) is transparent — both OK
    if fig_color[:3] != (1.0, 1.0, 1.0) and fig_color[3] != 0.0:
        return FigureCheck("background", False, "warn",
                           f"Figure background is not white: {fig_color}")
    return FigureCheck("background", True)


# ── Main Verifier ──────────────────────────────────────────────

ALL_CHECKS = [
    _check_labels,
    _check_font_sizes,
    _check_font_consistency,
    _check_title,
    _check_figure_size,
    _check_spines,
    _check_legend_overlap,
    _check_colorbar_overlap,
    _check_dpi,
    _check_overlapping_text,
    _check_white_background,
]


def verify_figure(fig, checks=None, verbose=True):
    """Run quality checks on a matplotlib Figure.

    Args:
        fig: A matplotlib Figure object.
        checks: List of check functions to run. Defaults to ALL_CHECKS.
        verbose: If True, print results.

    Returns:
        list of FigureCheck results.
    """
    if checks is None:
        checks = ALL_CHECKS

    # Force a draw so bounding boxes are computed
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        fig.canvas.draw()

    results = []
    for check_fn in checks:
        try:
            result = check_fn(fig)
            results.append(result)
        except Exception as e:
            results.append(FigureCheck(
                check_fn.__name__.lstrip("_check_"), False, "warn",
                f"Check failed with error: {e}"))

    if verbose:
        n_pass = sum(1 for r in results if r.passed)
        n_total = len(results)
        fails = [r for r in results if not r.passed and r.severity == "fail"]
        warns = [r for r in results if not r.passed and r.severity == "warn"]

        print(f"\n{'='*60}")
        print(f"  Figure Quality Report: {n_pass}/{n_total} checks passed")
        print(f"{'='*60}")
        for r in results:
            print(r)
        if fails:
            print(f"\n  {len(fails)} FAIL(s) — must fix before saving")
        if warns:
            print(f"  {len(warns)} WARNING(s) — review recommended")
        if not fails and not warns:
            print(f"\n  All checks passed.")
        print()

    return results


def has_failures(results):
    """Return True if any check has severity='fail'."""
    return any(not r.passed and r.severity == "fail" for r in results)


# ============================================================================
# Save with Verification
# ============================================================================

def save_figure(fig, path, dpi=300, verify=True, halt_on_fail=True, **kwargs):
    """Save a figure with optional pre-save verification.

    Args:
        fig: matplotlib Figure.
        path: Output file path.
        dpi: Resolution (default 300 for publication).
        verify: Run verification checks before saving.
        halt_on_fail: If True and a 'fail' severity check triggers,
            raise ValueError instead of saving.
        **kwargs: Passed to fig.savefig().

    Returns:
        list of FigureCheck results (or empty list if verify=False).
    """
    results = []
    if verify:
        results = verify_figure(fig, verbose=True)
        if halt_on_fail and has_failures(results):
            raise ValueError(
                "Figure has FAIL-level issues. Fix them or pass halt_on_fail=False. "
                "Issues: " + "; ".join(r.details for r in results if not r.passed and r.severity == "fail")
            )

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    kwargs.setdefault("dpi", dpi)
    kwargs.setdefault("bbox_inches", "tight")
    kwargs.setdefault("facecolor", "white")
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", UserWarning)
        fig.savefig(str(path), **kwargs)

    size_kb = path.stat().st_size / 1024
    print(f"Saved: {path} ({size_kb:.0f} KB, {dpi} DPI)")
    return results
