# claude-plugins

Personal Claude Code plugin marketplace by [Yang Joon Kim](https://github.com/yangjun9095).

## Install

Add this marketplace to Claude Code:

```bash
/plugin marketplace add yangjun9095/claude-plugins
```

Then install individual plugins:

```bash
/plugin install weekly-review@yangjun9095-plugins
/plugin install prep-report@yangjun9095-plugins
```

## Plugins

### `weekly-review`

Generates a structured weekly development report across all git worktrees.

- Summarizes merged PRs, active branches, and stale worktrees
- Highlights uncommitted work and PRs needing attention
- Suggests next-week priorities
- Writes a full report to `docs/weekly/YYYY-MM-DD.md`

**Usage:** `/weekly-review` or `/weekly-review 2` (2-week lookback)

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

### `paperbanana`

Turn ideas into publication-quality diagrams and plots. Powered by [PaperBanana](https://github.com/claytonlin1110/paperbanana), a multi-agent pipeline that retrieves reference examples, plans layout, applies styling, renders the image, and refines with a critic loop.

- Generate methodology diagrams from text descriptions or ideas
- Generate statistical plots from CSV/JSON data
- Iteratively refine diagrams with natural-language feedback
- Uses Google Gemini free tier by default (no cost)

**Commands:**

```
/visualize "Our system extracts features with a CNN, fuses them with attention, and classifies"
/visualize method.txt "Overview of the pipeline"
/plot results.csv "Grouped bar chart comparing accuracy across models"
/refine-diagram "Make the arrows thicker and use a blue palette"
```

**Setup:** Requires a Google API key (free). Run `paperbanana setup` after installing, or set `GOOGLE_API_KEY` in your `.env`.

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
