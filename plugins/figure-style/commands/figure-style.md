# Figure Style

Activate publication-quality figure styling with automated verification. When this skill is active, every matplotlib/seaborn figure Claude generates must pass a quality harness before being saved.

**Arguments:** `$ARGUMENTS`

---

## Instructions

### Step 0: Setup

**0a. Locate the helper library:**

```bash
ls -1 ~/.claude/plugins/marketplaces/*/plugins/figure-style/scripts/figure_helpers.py ~/.claude/plugins/cache/*/figure-style/*/scripts/figure_helpers.py 2>/dev/null | head -1
```

Store the directory — it will be added to `sys.path` in generated scripts.

**0b. Check matplotlib is available:**

```bash
python -c "import matplotlib; print(f'matplotlib {matplotlib.__version__} OK')" 2>&1 || echo "NEED_INSTALL"
```

If missing, `figure_helpers.py` auto-installs it on import.

**0c. If `$ARGUMENTS` is non-empty**, treat it as a context hint for what kind of figures are being made (e.g., "UMAP plots", "heatmaps", "bar charts for presentation"). Adjust advice accordingly.

---

### Step 1: Apply Style at Script Start

Every generated script that produces figures MUST begin with:

```python
import sys
from pathlib import Path

# Load figure-style helpers
_helpers_dirs = [
    *Path.home().glob(".claude/plugins/marketplaces/*/plugins/figure-style/scripts"),
    *Path.home().glob(".claude/plugins/cache/*/figure-style/*/scripts"),
]
for d in _helpers_dirs:
    if (d / "figure_helpers.py").exists():
        sys.path.insert(0, str(d))
        break

from figure_helpers import apply_style, save_figure, get_palette, verify_figure
apply_style()
```

For presentation figures, use `apply_style_talk()`. For paper figures, use `apply_style_paper()`.

---

### Step 2: Figure Construction Rules

These rules are MANDATORY. They are what separates a good figure from a bad one.

#### 2a. Labels & Text (NON-NEGOTIABLE)

- **Every axis MUST have a label.** No exceptions. If the data is obvious (e.g., UMAP), still label it ("UMAP 1", "UMAP 2").
- **Labels must be lowercase.** Use "expression (log₂ CPM)", not "Expression (log₂ CPM)". Exceptions: all-caps abbreviations (UMAP, PCA, DNA, RNA) stay uppercase.
- **Labels must include units** when applicable: "distance (nm)", "time (hours)", "expression (log₂ CPM)". The unit is part of the label, not optional.
- **Font sizes: title = 8pt, everything else = 6pt.** The mplstyle enforces this. Do NOT override with larger fonts. The harness checks that all text matches these sizes.
- **Figure size should match the font size.** With 6pt body text, use compact figures (default 4x3 inches). The data should fill the figure — not be surrounded by whitespace with oversized labels.
- **Use consistent fonts.** The mplstyle handles this — don't override with random font choices.
- **No gridlines.** Ever. The data speaks for itself. The harness enforces this.

#### 2b. Color (CRITICAL for scientific figures)

- **Use the bundled palette** (`get_palette(n)`) or intentional, named colors. NEVER use matplotlib defaults without thought.
- **Categorical data → qualitative palette** (distinct hues). `get_palette(n, "qual")`
- **Sequential data → sequential colormap** (viridis, mako, or `get_palette(name="seq")`)
- **Diverging data → diverging colormap** (centered at meaningful zero). `get_palette(name="div")`
- **Colorblind safety:** The bundled qualitative palette is colorblind-safe. If using custom colors, verify with at least 3 distinguishable channels.
- **Color must encode meaning, not decoration.** If two things are the same color, the viewer assumes they're related. If they're different colors, the viewer assumes they're different.
- **Consistent colors across related figures.** If Cluster A is blue in Figure 1, it must be blue in Figure 2. Pass explicit color mappings, don't rely on default ordering.

#### 2c. Layout & Composition

- **One message per figure.** If a figure tries to say two things, split it into two figures.
- **Remove chart junk:** no top/right spines (handled by mplstyle), **no gridlines ever** (harness enforces this), no 3D effects, no gradient fills.
- **White background.** Always. No grey, no colored backgrounds.
- **Legends should not occlude data.** Place outside the axes (`bbox_to_anchor=(1.05, 1)`) or in a data-sparse corner. If >8 items, consider a separate legend panel or direct labeling.
- **Colorbars MUST NOT overlap the plot area.** Use a dedicated axes:
  ```python
  fig.subplots_adjust(right=0.88)
  cbar_ax = fig.add_axes([0.90, 0.15, 0.02, 0.7])
  fig.colorbar(mappable, cax=cbar_ax)
  ```
- **Subplots:** share axes when comparing (`sharex=True, sharey=True`). Align them. Use `fig.align_ylabels()`.
- **Aspect ratio:** default to ~1.6:1 (golden ratio). Square for scatter/UMAP. Tall for heatmaps. Match the data geometry.

#### 2d. Data Presentation

- **Scatter plots:** use alpha (0.3-0.7) when points overlap. Show point density, not point count.
- **Error bars:** show them when you have replicates. Use SEM for inference, SD for description. State which one in the caption.
- **Heatmaps:** include a colorbar with a label. Row/column labels must be readable. Consider clustering rows/columns.
- **Bar charts:** start y-axis at 0 (unless there's a scientific reason not to). Add individual data points on top when n < 30.
- **Line plots:** use distinct line styles (solid, dashed, dotted) in addition to color for colorblind accessibility.

#### 2e. Export

- **DPI: 300** for publication, 150 for screen/slides. `save_figure()` defaults to 300.
- **Format: PNG** for raster (photos, complex plots). **PDF/SVG** for vector (line plots, diagrams).
- **`bbox_inches='tight'`** — always. Prevents label clipping. `save_figure()` does this automatically.
- **File names:** descriptive, no spaces. `fig_umap_celltype_by_timepoint.png`, not `figure1.png`.

---

### Step 3: Verification (MANDATORY before saving)

Every figure MUST be verified before saving. Use `save_figure()` which runs verification automatically:

```python
save_figure(fig, "figures/my_plot.png")
```

Or verify manually:

```python
results = verify_figure(fig)
```

The harness checks:

| Check | What it catches | Severity |
|-------|----------------|----------|
| `axis_labels` | Missing x/y labels | WARN |
| `lowercase_labels` | Title-case labels ("Expression" instead of "expression") | WARN |
| `font_sizes` | Fonts deviating from 8pt title / 6pt body | WARN |
| `font_consistency` | Mixed font families (>2) | WARN |
| `title_present` | No title (informational) | WARN |
| `figure_size` | Too small, too large, extreme aspect ratio | WARN |
| `clean_spines` | Top/right spines visible | WARN |
| `no_gridlines` | Any gridlines visible | WARN |
| `legend_overlap` | Legend covers >40% of axes | WARN |
| `colorbar_overlap` | Colorbar overlaps data area | FAIL |
| `dpi` | Below minimum DPI | WARN |
| `text_overlap` | Text elements overlapping each other | WARN |
| `text_data_overlap` | Labels/titles intruding into data area (>15%) | FAIL |
| `background` | Non-white background | WARN |

**FAIL = must fix. WARN = review and fix if possible.**

If verification reports warnings, fix them before proceeding. The goal is 100% pass rate.

---

### Step 4: Common Patterns

#### UMAP / tSNE scatter

```python
fig, ax = plt.subplots(figsize=(8, 8))  # square
palette = dict(zip(categories, get_palette(len(categories))))
for cat in categories:
    mask = labels == cat
    ax.scatter(embedding[mask, 0], embedding[mask, 1],
               c=palette[cat], label=cat, s=5, alpha=0.5, rasterized=True)
ax.set_xlabel("UMAP 1")
ax.set_ylabel("UMAP 2")
ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', markerscale=3)
save_figure(fig, "figures/umap_by_celltype.png")
```

#### Heatmap

```python
fig, ax = plt.subplots(figsize=(10, 8))
im = ax.imshow(data, cmap='viridis', aspect='auto')
fig.subplots_adjust(right=0.85)
cbar_ax = fig.add_axes([0.88, 0.15, 0.03, 0.7])
fig.colorbar(im, cax=cbar_ax, label="Expression (log₂ CPM)")
ax.set_xlabel("Genes")
ax.set_ylabel("Cells")
save_figure(fig, "figures/heatmap_expression.png")
```

#### Multi-panel comparison

```python
fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharex=True, sharey=True)
for ax, (name, data) in zip(axes, datasets.items()):
    ax.scatter(data[:, 0], data[:, 1], s=3, alpha=0.4)
    ax.set_title(name)
    ax.set_xlabel("UMAP 1")
axes[0].set_ylabel("UMAP 2")
fig.align_ylabels()
save_figure(fig, "figures/comparison_3panel.png")
```

---

### Step 5: Iterate on Feedback

After saving, if the user asks for adjustments:
1. Make the change
2. Re-run `verify_figure(fig)` 
3. Confirm all checks pass
4. Save again

Never skip verification on iteration.

---

## What This Skill Does NOT Do

- Does not generate figures from scratch (that's your job as the analyst)
- Does not choose what data to plot (that's a scientific decision)
- Does not replace domain-specific plotting libraries (scanpy, seaborn, etc.)

It ensures that whatever you plot looks clean, readable, and publication-ready.

---

## Quick Reference

```python
from figure_helpers import (
    apply_style,           # Load publication defaults
    apply_style_talk,      # Larger fonts for talks
    apply_style_paper,     # Compact for papers
    apply_style_poster,    # Largest for posters
    get_palette,           # Color palettes
    verify_figure,         # Run all quality checks
    save_figure,           # Save with verification
    PALETTE_QUAL,          # 8-color qualitative list
)
```

## Edge Cases

- **Scanpy plots:** `sc.pl.*` functions create their own figures. Capture with `fig = plt.gcf()` then `verify_figure(fig)` before saving.
- **Seaborn FacetGrid:** Access the figure via `g.fig`, then `verify_figure(g.fig)`.
- **Interactive notebooks:** Call `apply_style()` once per notebook, at the top. Verification runs on `save_figure()` calls.
- **Existing figures to fix:** Load the script, `apply_style()`, recreate the figure, verify, save. Don't try to patch a saved PNG.
