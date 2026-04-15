# figure-style

Enforce publication-quality figure styling with automated verification. Activates on demand via `/figure-style` — zero context cost when not in use.

## Install

```bash
# Add the marketplace (one-time)
/plugin marketplace add yangjun9095/claude-plugins

# Install the plugin
/plugin install figure-style@yangjun9095-plugins
```

matplotlib is auto-installed if missing. No manual `pip install` needed.

## Usage

```
/figure-style                    # activate for current session
/figure-style UMAP plots         # activate with context hint
/figure-style heatmaps for paper # activate with context hint
```

Once activated, Claude will:
1. Apply the publication mplstyle to all generated figures
2. Follow strict rules for labels, colors, layout, and export
3. Run a verification harness on every figure before saving
4. Fix any issues the harness catches

## What it enforces

### Principle: Data-Ink Ratio (Tufte)
Every mark must encode information. If it can be erased without information loss, erase it. The harness measures your data-ink ratio and flags non-data ink.

### Typography
- Title: 8pt, everything else: 6pt (compact, data-dominant style)
- Font: Avenir Light (fallback: Arial)
- Labels on every axis, lowercase, with units where applicable

### Color
- Colorblind-safe qualitative palette (8 colors)
- Sequential/diverging colormaps for continuous data
- Consistent colors across related figures
- Color encodes meaning, not decoration

### Layout
- White background, no top/right spines, **no gridlines**
- Compact figure sizes (default 4x3in) matched to small font sizes
- Legends outside data area (or in data-sparse corner)
- Colorbars on dedicated axes (never overlapping plot)
- Appropriate aspect ratios (square for scatter, golden for line plots)

### Embedding Plots (UMAP / tSNE)
- Axes are arbitrary — remove them entirely with `strip_embedding_axes(ax)`
- The harness detects embedding plots and warns if axes are still present

### Export
- **Always saves both PNG (300 DPI) and PDF (vector, editable text)**
- `pdf.fonttype = 42` — text remains editable in Illustrator/Inkscape
- The harness verifies PDF text is not fragmented into individual characters
- `bbox_inches='tight'` (no clipped labels)

## Verification harness

The core differentiator. Every figure passes through 18 automated checks:

| Check | What it catches | Severity |
|-------|----------------|----------|
| `axis_labels` | Missing x/y labels (skips stripped axes) | WARN |
| `lowercase_labels` | Title-case labels ("Expression" not "expression") | WARN |
| `font_sizes` | Fonts deviating from 8pt title / 6pt body | WARN |
| `font_consistency` | Mixed font families | WARN |
| `title_present` | No title (informational) | WARN |
| `figure_size` | Extreme dimensions/aspect ratio | WARN |
| `clean_spines` | Top/right spines visible | WARN |
| `no_gridlines` | Any gridlines visible | WARN |
| `non_data_ink` | Box frames, heavy ticks (Tufte erasure test) | WARN |
| `embedding_axes` | UMAP/tSNE with axes still present | WARN |
| `legend_overlap` | Legend covers >40% of axes | WARN |
| `colorbar_overlap` | Colorbar overlaps data | FAIL |
| `dpi` | Below minimum resolution | WARN |
| `text_overlap` | Text elements overlapping each other | WARN |
| `text_data_overlap` | Labels/titles intruding into data area (>15%) | FAIL |
| `background` | Non-white background | WARN |
| `data_ink_ratio` | Approximate data-to-chrome ratio | INFO |
| `pdf_text_editable` | PDF text not editable / fragmented chars | FAIL |

FAIL = must fix. WARN = fix recommended. INFO = awareness only.

## Standalone usage (without Claude)

```python
import sys
sys.path.insert(0, "path/to/figure-style/scripts")

from figure_helpers import apply_style, save_figure, get_palette
apply_style()

import matplotlib.pyplot as plt

fig, ax = plt.subplots()
ax.scatter(x, y, c=get_palette(3)[0])
ax.set_xlabel("x label (units)")
ax.set_ylabel("y label (units)")
save_figure(fig, "output.png")  # saves .png + .pdf, verifies both
```

## Presets

```python
apply_style()           # Default (notebook context)
apply_style_talk()      # Larger fonts for presentations
apply_style_paper()     # Compact for journal figures
apply_style_poster()    # Largest for posters
```

## What's included

```
figure-style/
  commands/figure-style.md       # Skill prompt (rules + harness instructions)
  scripts/
    figure_helpers.py            # Helper library (style, palette, verification, PDF check)
    publication.mplstyle         # matplotlib style file (Avenir Light, 8/6pt, pdf.fonttype=42)
  references/
    figure-style-guide.md        # Full style guide (Tufte principles, all rules)
  examples/
    generate_samples.py          # Good vs bad comparison figures (PNG + PDF)
```

## Relationship to `generate-slides`

- `/figure-style` makes individual figures publication-quality
- `/generate-slides` assembles figures into a PPTX deck

Use them together: activate `/figure-style` during analysis, then `/generate-slides` when you're ready to present.

## License

MIT
