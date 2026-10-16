# claude-plugins

Personal Claude Code plugin marketplace by [Yang Joon Kim](https://github.com/yangjun9095).

## Install

Add this marketplace to Claude Code:

```bash
/plugin marketplace add yangjun9095/claude-plugins
```

Then install individual plugins:

```bash
/plugin install prep-report@yangjun9095-plugins
```

## Plugins

### `prep-report`

Converts analysis session artifacts into a structured report or slide deck outline. Designed for data analysis workflows where you generate many figures/plots during a Claude Code session and need to turn them into a coherent presentation.

- Scans working directory for all generated figures (png, jpg, svg, pdf, html)
- Reads jupytext/Jupyter notebooks to reconstruct the analysis narrative
- Loads audience preferences from an optional `report-style.md` file
- Categorizes every figure as **Include**, **Backup**, or **Skip**
- Generates a slide-by-slide outline with figure assignments, key messages, talking points, and speaker notes
- Supports slide deck (default), long-form document, and Confluence page formats

**Usage:**

```
/prep-report                              # default: 10-min slide deck
/prep-report 15min                        # 15-slide deck
/prep-report 8 slides                     # exactly 8 slides
/prep-report 30min doc                    # long-form document outline
/prep-report 10min -- ./report-style.md   # with explicit audience preferences
```

**Tip:** Create a `report-style.md` in your project to capture your audience's preferences (narrative vs. technical, detail level, required sections). The plugin will auto-detect it from `./report-style.md`, `./docs/report-style.md`, or `./.claude/report-style.md`.

### `generate-slides`

Generates a polished `.pptx` slide deck from session artifacts. Builds on `prep-report` by adding **interactive outline brainstorming** (via AskUserQuestion) and **programmatic PPTX generation** using `python-pptx`.

- Scans for figures (png, jpg, svg) and reads docs/notebooks for context
- Asks the user to choose a narrative style (Journey, Results-First, Technical)
- Proposes a slide outline with figure assignments — iterates until approved
- Generates a self-contained Python script using a bundled `pptx_helpers.py` library
- Produces a clean, academic-style PPTX (16:9, Calibri, white bg, blue accents)
- Handles tables, code/ASCII boxes, callout boxes, embedded figures

**Usage:**

```
/generate-slides                              # default: 15-min deck
/generate-slides 20min                        # 20-slide deck
/generate-slides 10 slides                    # exactly 10 slides
/generate-slides 15min -- loic                # with audience style
/generate-slides 8 slides -- ./report-style.md  # explicit style file
```

**Requires:** `python-pptx` (auto-installed on first use)

**Relationship to `prep-report`:** Use `/prep-report` when you want a markdown outline only. Use `/generate-slides` when you want a ready-to-present PPTX file with embedded figures.

### `figure-style`

Enforce publication-quality figure styling with an automated verification harness. Activates on demand — zero context cost when not in use.

- Applies a clean matplotlib style (Helvetica, no top/right spines, white background)
- Provides colorblind-safe palettes (qualitative, sequential, diverging)
- Runs 11 automated quality checks on every figure before saving
- Catches: missing labels, small fonts, colorbar overlaps, legend occlusion, low DPI, text overlap
- Presets for different contexts: `apply_style_talk()`, `apply_style_paper()`, `apply_style_poster()`

**Usage:**

```
/figure-style                    # activate for current session
/figure-style UMAP plots         # activate with context hint
```

**Dependencies auto-installed.** Works with matplotlib, seaborn, and scanpy.

**Relationship to `generate-slides`:** Use `/figure-style` to make individual figures publication-quality during analysis. Use `/generate-slides` to assemble them into a deck.

### `overleaf-manuscript`

Sync preflight, a prose audit and an ask-before-edit hook for LaTeX manuscripts that sync with Overleaf. Works with the `manuscript-write` skill.

**Install:** `/plugin install overleaf-manuscript@yangjun9095-plugins`

## Archived

Plugins retired on 2026-10-15 live in [`archive/`](archive/README.md). They are not in the marketplace. The archive README says why and how to restore each one.
