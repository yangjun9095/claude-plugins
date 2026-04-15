# Figure Style

Activate publication-quality figure styling with automated verification. Grounded in Tufte's data-ink ratio principle: every mark must encode information — if it can be erased without information loss, erase it.

When active, every matplotlib/seaborn figure must pass an 18-check harness before saving. Figures are always saved as **both PNG and PDF** (with editable text).

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

If missing, `figure_helpers.py` auto-installs it on import. `pypdf` is also auto-installed for PDF verification.

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

from figure_helpers import (
    apply_style, save_figure, get_palette, verify_figure,
    strip_embedding_axes, verify_pdf,
)
apply_style()
```

This sets: Avenir Light font (fallback: Arial), 8pt titles / 6pt body, no gridlines, no top/right spines, thin frame (0.4pt), `pdf.fonttype=42` for editable text.

For presentation figures, use `apply_style_talk()`. For paper figures, use `apply_style_paper()`.

---

### Step 2: Figure Construction Rules

These are grounded in Tufte's data-ink principle. The harness enforces them.

#### 2a. Labels & Text

- **Every axis MUST have a label** — unless axes are stripped (UMAP/tSNE)
- **Labels must be lowercase.** Use "expression (log₂ CPM)", not "Expression". Exceptions: all-caps abbreviations (UMAP, PCA, DNA, RNA, ATAC)
- **Include units** when applicable: "distance (nm)", "time (hours)"
- **Font sizes: title = 8pt, everything else = 6pt.** Do NOT override
- **Font: Avenir Light** (fallback: Arial). Do NOT use other fonts
- **No gridlines.** Ever. Data speaks for itself
- **Figure size matches font size.** Default 4x3in for 6pt body. Data should fill the figure

#### 2b. Color

- **Use `get_palette(n)`** or intentional, named colors. Never matplotlib defaults
- **Categorical → qualitative palette** (colorblind-safe). `get_palette(n, "qual")`
- **Sequential → viridis** (default). Or `get_palette(name="seq")`
- **Diverging → centered at meaningful zero.** `get_palette(name="div")`
- **Color encodes meaning, not decoration.** Consistent across related figures
- **White = zero/no-data in heatmaps** (not grey — grey is non-data ink)

#### 2c. Layout & Data-Ink

- **Tufte erasure test:** for every element, ask "can I remove this without losing information?" If yes, remove it
- **No top/right spines.** No box frames (harness catches 4-spine boxes)
- **No gridlines.** The harness fails them
- **Thin frame:** 0.4pt spines, 0.4pt ticks. Heavy chrome steals attention from data
- **White background.** Always
- **Legends outside the data area** (`bbox_to_anchor=(1.05, 1)`) or data-sparse corner. If ≤3 items, consider direct labeling instead
- **Colorbars on dedicated axes** — never overlapping the plot:
  ```python
  fig.subplots_adjust(right=0.88)
  cbar_ax = fig.add_axes([0.90, 0.15, 0.02, 0.7])
  fig.colorbar(mappable, cax=cbar_ax)
  ```
- **Shared axes** for multi-panel comparisons (`sharex=True, sharey=True`)

#### 2d. UMAP / tSNE (MANDATORY)

UMAP and tSNE coordinates are **arbitrary** — axes encode zero information. **Strip them:**

```python
strip_embedding_axes(ax)  # removes all spines, ticks, labels
```

The harness detects UMAP/tSNE plots (by label text) and warns if axes are still present. The gold standard: scatter data + title + colorbar/legend, nothing else.

#### 2e. Data Presentation

- **Scatter:** alpha (0.3-0.5) for overlapping points. `rasterized=True` for large n
- **Error bars:** SEM for inference, SD for description. State which
- **Heatmaps:** colorbar with a label. White for zero values. Consider clustering
- **Bar charts:** y-axis starts at 0. Data points on top when n < 30
- **Line plots:** distinct line styles in addition to color (accessibility)

#### 2f. Export (MANDATORY — dual save)

`save_figure()` **always saves both formats:**

```python
save_figure(fig, "figures/my_plot.png")
# Produces:
#   figures/my_plot.png  — 300 DPI raster
#   figures/my_plot.pdf  — vector, editable text (pdf.fonttype=42)
```

The PDF is verified for text editability after saving. If text is fragmented into individual characters (common matplotlib pitfall), the harness **FAIL**s.

- **DPI: 300** for publication, 150 for screen
- **File names:** descriptive, no spaces. `fig_umap_celltype_by_timepoint.png`

---

### Step 3: Verification (MANDATORY before saving)

`save_figure()` runs verification automatically. The harness has **18 checks**:

| Check | What it catches | Severity |
|-------|----------------|----------|
| `axis_labels` | Missing x/y labels (skips stripped axes) | WARN |
| `lowercase_labels` | Title-case labels | WARN |
| `font_sizes` | Fonts deviating from 8pt title / 6pt body | WARN |
| `font_consistency` | Mixed font families (>2) | WARN |
| `title_present` | No title (informational) | WARN |
| `figure_size` | Extreme dimensions/aspect ratio | WARN |
| `clean_spines` | Top/right spines visible | WARN |
| `no_gridlines` | Any gridlines visible | WARN |
| `non_data_ink` | Box frames, heavy ticks (Tufte erasure) | WARN |
| `embedding_axes` | UMAP/tSNE with axes still present | WARN |
| `legend_overlap` | Legend covers >40% of axes | WARN |
| `colorbar_overlap` | Colorbar overlaps data | FAIL |
| `dpi` | Below minimum resolution | WARN |
| `text_overlap` | Text elements overlapping | WARN |
| `text_data_overlap` | Labels intruding >15% into data area | FAIL |
| `background` | Non-white background | WARN |
| `data_ink_ratio` | Approximate data-to-chrome ratio | INFO |
| `pdf_text_editable` | PDF text not editable / fragmented | FAIL |

**FAIL = must fix. WARN = fix recommended. INFO = awareness.**

The goal is 100% pass rate (all PASS, no WARN or FAIL).

---

### Step 4: Common Patterns

#### UMAP / tSNE scatter (gold standard)

```python
fig, ax = plt.subplots(figsize=(4, 3.5))
palette = dict(zip(categories, get_palette(len(categories))))
for cat in categories:
    mask = labels == cat
    ax.scatter(embedding[mask, 0], embedding[mask, 1],
               c=palette[cat], label=cat, s=3, alpha=0.5, rasterized=True)
ax.set_title(f"cell types (n = {len(labels):,})")
strip_embedding_axes(ax)  # MANDATORY for UMAP/tSNE
ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', markerscale=3)
save_figure(fig, "figures/umap_by_celltype.png")
```

#### Heatmap

```python
fig, ax = plt.subplots(figsize=(5, 4))
im = ax.imshow(data, cmap='viridis', aspect='auto')
fig.subplots_adjust(right=0.85)
cbar_ax = fig.add_axes([0.88, 0.15, 0.02, 0.7])
fig.colorbar(im, cax=cbar_ax, label="expression (z-score)")
ax.set_xlabel("genes")
ax.set_ylabel("cells")
save_figure(fig, "figures/heatmap_expression.png")
```

#### Multi-panel UMAP comparison

```python
fig, axes = plt.subplots(1, 3, figsize=(9, 3))
for ax, (name, data) in zip(axes, datasets.items()):
    ax.scatter(data[:, 0], data[:, 1], s=1, alpha=0.4, rasterized=True)
    ax.set_title(name)
    strip_embedding_axes(ax)  # strip each panel
save_figure(fig, "figures/comparison_3panel.png")
```

#### Line plot with error bars

```python
fig, ax = plt.subplots(figsize=(4, 3))
palette = get_palette(3)
for i, (name, vals) in enumerate(groups.items()):
    ax.plot(time, vals.mean(0), c=palette[i], label=name)
    ax.fill_between(time, vals.mean(0) - vals.std(0),
                    vals.mean(0) + vals.std(0), color=palette[i], alpha=0.15)
ax.set_xlabel("time (hpf)")
ax.set_ylabel("expression (log₂ CPM)")
ax.legend(frameon=False)
save_figure(fig, "figures/temporal_expression.png")
```

---

### Step 5: Iterate on Feedback

After saving, if the user asks for adjustments:
1. Make the change
2. `save_figure()` re-runs verification automatically
3. Confirm all checks pass (including PDF editability)

Never skip verification on iteration.

---

## Quick Reference

```python
from figure_helpers import (
    apply_style,              # Load publication defaults (Avenir Light, 8/6pt)
    apply_style_talk,         # Larger fonts for talks
    apply_style_paper,        # Compact for papers
    apply_style_poster,       # Largest for posters
    get_palette,              # Color palettes
    strip_embedding_axes,     # Remove axes from UMAP/tSNE
    verify_figure,            # Run all 18 quality checks
    verify_pdf,               # Check PDF text editability
    save_figure,              # Save PNG + PDF with verification
    PALETTE_QUAL,             # 8-color qualitative list
)
```

## Edge Cases

- **Scanpy plots:** `sc.pl.*` functions create their own figures. Capture with `fig = plt.gcf()` then `save_figure(fig, path)`.
- **Seaborn FacetGrid:** Access the figure via `g.fig`, then `save_figure(g.fig, path)`.
- **Interactive notebooks:** Call `apply_style()` once per notebook, at the top.
- **Existing figures to fix:** `apply_style()`, recreate the figure, `save_figure()`.
- **Scanpy UMAPs:** After `sc.pl.umap()`, do `strip_embedding_axes(plt.gca())` then `save_figure(plt.gcf(), path)`.

## What This Skill Does NOT Do

- Does not generate figures from scratch (that's analysis)
- Does not choose what data to plot (that's a scientific decision)
- Does not replace scanpy/seaborn (it wraps and verifies them)
- It ensures that whatever you plot maximizes data-ink ratio
