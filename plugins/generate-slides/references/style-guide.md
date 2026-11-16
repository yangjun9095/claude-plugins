# Slide Style Guide — Detailed Reference

This file is loaded on-demand by the generate-slides skill when detailed style information is needed. The core workflow is in `commands/generate-slides.md`.

---

## Customizing the Style

The slide style (fonts, colors, layout, emphasis) is configurable via a `slide-style.yaml` file. The bundled default is Y.J. Kim's minimal style. To override, place a `slide-style.yaml` in your project:

**Search order:** `./slide-style.yaml` > `./docs/slide-style.yaml` > `./.claude/slide-style.yaml`

Partial YAML is fine — only the keys you specify are overridden:

```yaml
# Example: just change the font and accent color
typography:
  body_font: "Calibri"
colors:
  accent: "#7C3AED"
```

## Full YAML Schema

```yaml
typography:
  body_font: "Avenir Light"    # Main font for all text
  code_font: "PT Mono"         # Monospace font for code boxes
  title_size: 40               # Title font size (pt)
  subtitle_size: 28            # Subtitle font size (pt)
  body_size: 22                # Body text font size (pt)
  footnote_size: 14            # Footnote font size (pt)
  table_size: 16               # Table cell font size (pt)
  code_size: 12                # Code block font size (pt)

colors:
  accent: "#036DEA"            # Primary accent color (hex)
  positive: "#059669"          # Positive/good values
  negative: "#DC2626"          # Negative/bad values
  grey: "#6B7280"              # Secondary text, footnotes
  table_header: "#F5F5F5"     # Table header background

layout:
  left_margin: 0.8             # Left margin (inches)
  top_margin: 1.2              # Content top margin (inches)
  content_width: 11.7          # Content area width (inches)
  title_top: 0.15              # Title Y position (inches)
  accent_line_top: 1.05        # Accent line Y position (inches)

style:
  use_bold: false              # Allow bold text in titles
  title_slide_bg: "white"     # "white" or "dark" (dark navy)
  bullet_emphasis: "accent"   # "accent" (colored prefix) or "bold"
  callout_bg: "white"         # "white" (border only) or "accent" (tinted fill)
```

Requires PyYAML (`pip install pyyaml`). If PyYAML is not installed, the hardcoded defaults are used with a warning.

---

## Helper Library Reference

The reusable helper library is at `scripts/pptx_helpers.py`.

### Key functions:

| Function | Purpose |
|----------|---------|
| `new_presentation()` | Create 16:9 widescreen Presentation |
| `add_blank_slide(prs)` | Add blank slide |
| `set_slide_bg(slide, color)` | Set background color |
| `add_textbox(slide, l, t, w, h, text, ...)` | Simple text box |
| `add_rich_textbox(slide, l, t, w, h, paras)` | Multi-run rich text |
| `add_slide_title(slide, title, subtitle)` | Title + optional subtitle |
| `add_accent_line(slide)` | Accent line (available but not auto-added) |
| `add_figure(slide, path, l, t, width, height)` | Embed image (auto-clamps to bounds) |
| `add_code_box(slide, l, t, w, h, text)` | Monospace code/ASCII box |
| `add_callout_box(slide, l, t, w, h, label, text)` | Highlighted takeaway |
| `add_table(slide, l, t, w, h, rows, cols, data)` | Styled table |
| `add_bullets(slide, l, t, w, h, items)` | Bulleted list (str or (emphasis, rest) tuples) |
| `make_bullet_paragraphs(items)` | Convert items to paragraphs data |
| `make_title_slide(slide, title, author, affil, date)` | Title slide |
| `make_content_slide(slide, title, subtitle)` | Content slide with title |
| `make_section_slide(slide, title)` | Section divider |
| `load_style(path)` | Load style from YAML. Partial YAML OK. |

### Color constants:
`WHITE`, `BLACK`, `BLUE`, `GREEN`, `RED`, `GREY`, `LIGHT_GREY`, `TABLE_BORDER`

### Layout constants:
`SLIDE_W`, `SLIDE_H`, `LEFT_MARGIN` (0.8"), `TOP_MARGIN` (1.2"), `CONTENT_W` (11.7")

### Typography constants:
`FONT_NAME` ("Avenir Light"), `CODE_FONT` ("PT Mono"), `TITLE_SIZE` (40), `SUBTITLE_SIZE` (28), `BODY_SIZE` (22), `FOOTNOTE_SIZE` (14), `TABLE_SIZE` (16), `CODE_SIZE` (12)

### Style flags (set by `load_style()`):
`USE_BOLD` (false), `TITLE_SLIDE_BG` ("white"/"dark"), `BULLET_EMPHASIS` ("accent"/"bold"), `CALLOUT_BG` ("white"/"accent")

---

## Figure Generation Rules

When generating matplotlib figures that will be embedded in slides, follow these rules:

### Colorbar placement (MANDATORY)
- **Never place colorbars on top of or overlapping the plot area.** Colorbars that use `fig.colorbar(sc, ax=axes, shrink=...)` with default positioning often overlap scatter plots.
- **Always place colorbars on the far right** using a dedicated axes:
  ```python
  fig.subplots_adjust(right=0.88)
  cbar_ax = fig.add_axes([0.90, 0.15, 0.02, 0.7])
  cbar = fig.colorbar(sc, cax=cbar_ax)
  ```
- For single-panel figures, `fig.colorbar(sc, ax=ax, location='right', pad=0.08)` is acceptable.
- The key principle: **the plot data area must never be occluded by UI elements** (colorbars, legends that cover data points, etc.).
