# Starting scripts

Working versions, lifted from a Nature Methods figure rebuild. Copy into the project's
`harness/` and adapt. They are a starting point, not a library to import.

| file | what it is | what to change |
|---|---|---|
| `style_template.py` | the one locked style: palette, semantic maps, canonical names, `ax_at()` inch placement from the top-left, `tint()`, `save_all()`. **It calls `figure-style`'s `apply_style()` first and then overrides** — extend that plugin, never fork it | the font chain, the page widths, and every semantic map. Keep the structure: named maps, kept disjoint, with the reason in the docstring |
| `codex_review.sh` | independent peer review of a rendered panel by `gpt-6-astra` | the judging criteria, if the figure is not a biology schematic. Keep `effort=high` and the last-balanced-JSON parse |
| `verify_figures.py` | the gate; exits non-zero | `TARGET_W_PT`, `MIN_PT`, and the list of figure stems |
| `assemble.py` | composes panel PDFs onto one page with pypdf, preserving vector | the stem-to-figure mapping |

`style_template.py` carries the Okabe-Ito palette and the rule that forced the semantic maps
apart: a colour means one thing, and a column may mark its own signal in its own colour but
never another owner's.
