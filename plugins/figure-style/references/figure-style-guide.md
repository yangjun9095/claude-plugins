# Figure Style Guide

## Core Principle: Data-Ink Ratio (Tufte)

> "Above all else, show the data."
> "Maximize the data-ink ratio."
> "Erase non-data-ink."
> "Erase redundant data-ink."

Every mark on the figure must encode information. If it can be erased without information loss, erase it. The verification harness applies this principle automatically.

---

## Font

| Element | Size | Font |
|---------|------|------|
| Title | 8pt | Avenir Light |
| Axis labels | 6pt | Avenir Light |
| Tick labels | 6pt | Avenir Light |
| Legend | 6pt | Avenir Light |
| Colorbar label | 6pt | Avenir Light |

- **Fallback order**: Avenir Light > Avenir > Arial > Helvetica > DejaVu Sans
- **Labels are lowercase**, except all-caps abbreviations (UMAP, PCA, RNA, ATAC, DNA)
- **No bold** anywhere in figures

## Figure Size

Default: **4 x 3 inches** (matched to 6pt body text). Adjust proportionally:

| Layout | Size |
|--------|------|
| Single panel | 4 x 3 in |
| Single panel, square (UMAP) | 4 x 3.5 in |
| Heatmap | 5 x 4 in |
| 2-panel side-by-side | 8 x 3 in |
| 3-panel side-by-side | 9 x 3 in |
| Multi-row grid | scale per row/col |

The principle: **data should fill the figure.** If there's more whitespace than data, the figure is too large for the content.

## Axes & Frame

- **No top spine. No right spine.** (Enforced by harness)
- **No gridlines.** Ever. (Enforced by harness)
- **Thin left/bottom spines**: 0.4pt linewidth
- **Thin ticks**: 0.4pt width, 3pt length
- **No box frames**: If all 4 spines are visible, the harness warns

### UMAP / tSNE Special Case

Embedding coordinates are **arbitrary** — axes carry no numeric meaning. Remove them:

```python
from figure_helpers import strip_embedding_axes
strip_embedding_axes(ax)  # removes all spines, ticks, labels
```

Keep only: scatter data, title, colorbar, legend. The harness detects UMAP/tSNE plots by label text and warns if axes are still present.

Gold standard: the Peak Specificity Tau UMAP — no axes, compact colorbar, informative title with sample size, transparency encoding a second variable.

## Color

| Data type | Palette |
|-----------|---------|
| Categorical (≤8 groups) | `get_palette(n)` — colorblind-safe |
| Sequential continuous | viridis (default) |
| Diverging (centered at zero) | `get_palette(name="div")` |
| Zero/no data in heatmaps | white (not grey) |

Rules:
- Color **encodes meaning, not decoration**
- If two things share a color, the viewer assumes they're related
- **Consistent colors across related figures** — pass explicit color mappings
- **Alpha transparency** (0.3-0.5) for dense scatter plots

## Export

**Always save both formats:**

```python
save_figure(fig, "figures/my_plot.png")
# Automatically produces:
#   figures/my_plot.png  (300 DPI raster)
#   figures/my_plot.pdf  (vector, editable text)
```

| Setting | Value |
|---------|-------|
| PNG DPI | 300 |
| PDF fonttype | 42 (TrueType — editable in Illustrator) |
| bbox_inches | tight |
| facecolor | white |

**The PDF must have editable text.** The harness verifies this by reading back the PDF and checking that text is extractable as words (not individual characters). If text is fragmented, `pdf.fonttype` was not set to 42.

## Tufte Erasure Test

The harness applies these questions automatically:

| Question | If yes... |
|----------|-----------|
| Can this spine be removed? | Remove it |
| Can this gridline be removed? | Remove it (always yes) |
| Can this legend be replaced by direct labels? | Replace it |
| Can this frame/border be removed? | Remove it |
| Is this tick/label redundant? | Remove it |
| Are there decorative fills that add nothing? | Remove them |

## Harness Checks (18 total)

| # | Check | What it catches | Severity |
|---|-------|----------------|----------|
| 1 | `axis_labels` | Missing x/y labels (skips stripped axes) | WARN |
| 2 | `lowercase_labels` | Title-case labels ("Expression" not "expression") | WARN |
| 3 | `font_sizes` | Fonts deviating from 8pt title / 6pt body | WARN |
| 4 | `font_consistency` | Mixed font families (>2) | WARN |
| 5 | `title_present` | No title (informational) | WARN |
| 6 | `figure_size` | Extreme dimensions/aspect ratio | WARN |
| 7 | `clean_spines` | Top/right spines visible | WARN |
| 8 | `no_gridlines` | Any gridlines visible | WARN |
| 9 | `non_data_ink` | Box frames, heavy ticks — Tufte erasure | WARN |
| 10 | `embedding_axes` | UMAP/tSNE with spines/ticks still present | WARN |
| 11 | `legend_overlap` | Legend covers >40% of axes | WARN |
| 12 | `colorbar_overlap` | Colorbar overlaps data | FAIL |
| 13 | `dpi` | Below minimum resolution | WARN |
| 14 | `text_overlap` | Text elements overlapping each other | WARN |
| 15 | `text_data_overlap` | Labels/titles intruding >15% into data area | FAIL |
| 16 | `background` | Non-white background | WARN |
| 17 | `data_ink_ratio` | Approximate data-to-chrome ratio (informational) | INFO |
| 18 | `pdf_text_editable` | PDF text not editable / fragmented characters | FAIL |

**FAIL** = must fix. **WARN** = fix recommended. **INFO** = awareness only.
