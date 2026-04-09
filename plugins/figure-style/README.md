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

### Typography
- Title: 8pt, everything else: 6pt (compact, data-dominant style)
- Consistent font family (Helvetica/Arial)
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

### Export
- 300 DPI for publication, 150 for screen
- `bbox_inches='tight'` (no clipped labels)
- Descriptive file names

## Verification harness

The core differentiator. Every figure passes through 14 automated checks:

| Check | What it catches | Severity |
|-------|----------------|----------|
| `axis_labels` | Missing x/y labels | WARN |
| `lowercase_labels` | Title-case labels ("Expression" not "expression") | WARN |
| `font_sizes` | Fonts deviating from 8pt title / 6pt body | WARN |
| `font_consistency` | Mixed font families | WARN |
| `title_present` | No title (informational) | WARN |
| `figure_size` | Extreme dimensions/aspect ratio | WARN |
| `clean_spines` | Top/right spines visible | WARN |
| `no_gridlines` | Any gridlines visible | WARN |
| `legend_overlap` | Legend covers >40% of axes | WARN |
| `colorbar_overlap` | Colorbar overlaps data | FAIL |
| `dpi` | Below minimum resolution | WARN |
| `text_overlap` | Text elements overlapping each other | WARN |
| `text_data_overlap` | Labels/titles intruding into data area (>15%) | FAIL |
| `background` | Non-white background | WARN |

FAIL = must fix before saving. WARN = fix recommended.

## Standalone usage (without Claude)

```python
import sys
sys.path.insert(0, "path/to/figure-style/scripts")

from figure_helpers import apply_style, save_figure, get_palette
apply_style()

import matplotlib.pyplot as plt

fig, ax = plt.subplots()
ax.scatter(x, y, c=get_palette(3)[0])
ax.set_xlabel("X label (units)")
ax.set_ylabel("Y label (units)")
save_figure(fig, "output.png")  # verifies, then saves at 300 DPI
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
    figure_helpers.py            # Helper library (style, palette, verification)
    publication.mplstyle         # matplotlib style file
  examples/
    generate_samples.py          # Good vs bad comparison figures
```

## Relationship to `generate-slides`

- `/figure-style` makes individual figures publication-quality
- `/generate-slides` assembles figures into a PPTX deck

Use them together: activate `/figure-style` during analysis, then `/generate-slides` when you're ready to present.

## License

MIT
