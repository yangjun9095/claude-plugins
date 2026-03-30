---
allowed-tools:
  - Read
  - Write
  - Glob
  - Grep
  - AskUserQuestion
  - Bash(ls *)
  - Bash(find * -name)
  - Bash(find * -maxdepth)
  - Bash(find * -type)
  - Bash(file *)
  - Bash(identify *)
  - Bash(wc *)
  - Bash(date *)
  - Bash(mkdir *)
  - Bash(pip install *)
  - Bash(pip list *)
  - Bash(python *)
  - Bash(cp *)
description: "Generate a PPTX slide deck from session artifacts. Interactive outline brainstorming, then programmatic PPTX generation via python-pptx."
---

# Generate Slides

Generate a polished PPTX slide deck from the current session's figures, analysis artifacts, and findings. Uses **interactive outline brainstorming** with the user via AskUserQuestion, then programmatically generates a `.pptx` file using `python-pptx`.

**Arguments:** `$ARGUMENTS`

Format: `[time_or_slides] [-- audience-name or path/to/report-style-*.md]`

Examples:
- `/generate-slides` -> default 15-min deck, auto-detect audience
- `/generate-slides 20min` -> ~20-slide deck
- `/generate-slides 10 slides` -> 10-slide deck
- `/generate-slides 15min -- loic` -> 15-min deck, match report-style-loic*.md
- `/generate-slides 8 slides -- ./report-style-team.md` -> 8-slide deck with explicit style

---

## Instructions

Follow these steps carefully. The key differentiator of this skill is the **interactive outline brainstorming** before generating the PPTX.

---

### Step 0: Prerequisites & Context Gathering

**0a. Check python-pptx is installed:**

```bash
python -c "import pptx; print(f'python-pptx {pptx.__version__} OK')" 2>&1 || echo "NEED_INSTALL"
```

If `NEED_INSTALL`, run: `pip install python-pptx`

**0b. Locate the pptx_helpers library.** Check these locations in order:

```bash
ls -1 ~/.claude/plugins/marketplaces/*/plugins/generate-slides/scripts/pptx_helpers.py ~/.claude/plugins/cache/*/generate-slides/*/scripts/pptx_helpers.py 2>/dev/null | head -1
```

Store the directory containing `pptx_helpers.py` (the `scripts/` dir) — it will be added to `sys.path` in the generated script. If not found, the helpers will be defined inline in the generated script.

**0b2. Locate slide style config.** Search for a project-specific style override:

```bash
ls -1 ./slide-style.yaml ./docs/slide-style.yaml ./.claude/slide-style.yaml 2>/dev/null | head -1
```

If found, the generated script should call `load_style("path")` after importing pptx_helpers.
If not found, the bundled default (YJK minimal) is used automatically.

**0c. Gather context — run these commands in parallel:**

```bash
date '+%Y-%m-%d %A'
```
```bash
pwd
```
```bash
find . -maxdepth 5 \( -name "*.png" -o -name "*.jpg" -o -name "*.jpeg" -o -name "*.svg" \) -not -path "./.git/*" -not -path "./.claude/*" -not -path "*/node_modules/*" -not -path "*/__pycache__/*" -not -path "*/site-packages/*" -printf "%T@ %p\n" 2>/dev/null | sort -n | awk '{print $2}' | tail -100
```
```bash
find . -maxdepth 5 \( -name "*.ipynb" -o -name "*.py" \) -not -path "./.git/*" -not -path "./.claude/*" -not -path "*/node_modules/*" -not -path "*/__pycache__/*" -not -path "*/site-packages/*" -not -name "setup.py" -not -name "conftest.py" -printf "%T@ %p\n" 2>/dev/null | sort -n | awk '{print $2}' | tail -30
```
```bash
find . -maxdepth 3 -name "*.md" -not -path "./.git/*" -not -path "./.claude/*" -not -name "LICENSE*" | head -30
```
```bash
ls -1 report-style*.md docs/report-style*.md .claude/report-style*.md 2>/dev/null || echo "NO_REPORT_STYLE_FILES"
```

**0d. Parse `$ARGUMENTS`:**
- **Duration/slide count**: Number of minutes or explicit slide count. Default: 15 minutes (~15 slides at 1 slide/min).
- **Audience**: After `--`, either a path to a report-style file or a name to fuzzy-match against available `report-style-*.md` files.
- If a report-style file is found, read it for audience preferences.

**0e. Read key project files** for context:
- `CLAUDE.md` or `README.md` (project overview)
- Memory files if available (`~/.claude/projects/*/memory/MEMORY.md`)
- Result/report docs (`docs/results-*.md`, `docs/report-*.md`)
- Recent notebooks (skim markdown cells for narrative)

Build a mental model of: what the project is about, what was accomplished this session, what figures exist, and what story to tell.

---

### Step 1: Catalog Artifacts

From the figure list, build a categorized inventory:

1. **By naming patterns**: `fig1_*`, `umap_*`, `heatmap_*`, `qc_*`, etc.
2. **By directory**: `figures/results/`, `figures/qc/`, `outputs/`, etc.
3. **By type inference**:
   - **Key Results**: `result`, `final`, `summary`, `comparison`, `pearson`, `loss` in name
   - **QC/Diagnostic**: `qc`, `diagnostic`, `distribution`, `histogram` in name
   - **Methodology**: `workflow`, `pipeline`, `schematic`, `architecture` in name
   - **Exploration**: `explore`, `test`, `draft`, `tmp`, `debug` in name

4. Read any available figure-generating scripts to understand what each figure shows.

---

### Step 2: Interactive Outline Brainstorming

This is the core of the skill. Use `AskUserQuestion` to collaboratively design the slide outline.

**Question 1: Narrative Style**

Use AskUserQuestion to ask:

> "What narrative style works best for this presentation?"

Options:
- **Journey/Timeline**: Show the progression of work (exploration -> discovery -> results)
- **Results-First**: Lead with key findings, then supporting evidence
- **Technical Deep-Dive**: Methods and architecture focus, for expert audience
- (User can always pick "Other" for custom)

**Question 2: Present the proposed outline**

Based on artifacts, session context, and the chosen narrative style, draft a slide-by-slide outline. Present it to the user with AskUserQuestion:

> "Here's my proposed {N}-slide outline. What would you like to change?"

When presenting the outline, be specific about:
- Slide number and **action title** (see Action Title Rule below)
- Which figures go on which slides (use full paths)
- Which slides are text-only vs figure-heavy
- Backup/supplementary slides at the end

Options:
- **Looks good, generate it**: Proceed to PPTX generation
- **Add/remove slides**: User will specify changes
- **Change figure assignments**: User will specify which figures go where
- **Change emphasis/narrative**: User will describe the desired changes

If the user wants changes, iterate: apply feedback -> present revised outline -> repeat until approved.

**Action Title Rule (MANDATORY):**

Every slide title MUST be a **complete sentence stating the takeaway**, not a topic label. This is the single most important rule for effective scientific/technical presentations.

- BAD: "Results", "Model Performance", "ATAC-seq Analysis"
- GOOD: "LoRA fine-tuning improves RNA prediction by 67% over heads-only baseline"
- GOOD: "GradNorm automatically rebalances loss, outperforming hand-tuned weights"
- GOOD: "ATAC generalizes poorly across replicates while RNA transfers robustly"

**Ghost Deck Test:** After drafting the outline, read all action titles in sequence. They alone — without any bullet text or figures — should tell the complete story. If the narrative has gaps when reading only titles, revise until it flows as a coherent argument.

**Outline structure should follow this pattern** (adjust based on narrative style):

| Slide | Purpose | Typical Allocation |
|-------|---------|-------------------|
| 1 | Title slide | Always |
| 2 | Motivation / Big Picture | Always |
| 3-4 | Background / Methods | Optional per audience |
| 5-(N-3) | Key Results (bulk) | ~60% of slides |
| N-2 | Conclusions (key takeaways) | Always — stays on screen during Q&A |
| N-1 | Next Steps | Always |
| N+ | Supplementary / Backup | 2-4 slides |

**IMPORTANT:** End the main deck with a **Conclusions** slide (not "Thank You" or "Questions?"). The conclusions slide stays visible during Q&A, keeping the audience focused on your key findings.

---

### Step 3: Early Preview (2-3 Slides)

Before generating the full deck, create a **quick preview** of 2-3 representative slides so the user can give early feedback on design, layout, and aesthetics. This avoids generating 15+ slides only to discover the style needs adjusting.

**3a. Pick preview slides.** Select 2-3 slides that cover different types:
- 1 content slide with bullets (tests typography, spacing, emphasis style)
- 1 figure/results slide (tests figure sizing, placement, annotation style)
- Optionally: 1 table or comparison slide (if the deck has one)

Do NOT include the title slide in the preview — it's a special layout that doesn't represent the bulk of the deck.

**3b. Generate the preview script.** Write a small script (e.g., `scripts/generate_slides_preview.py`) that generates only these 2-3 slides using the same helpers and style as the full deck. Run it:

```bash
python scripts/generate_slides_preview.py
```

**3c. Present to user for feedback.** Use AskUserQuestion:

> "I've generated a 2-3 slide preview at `{preview_path}`. Please open it and let me know how the design looks."

Options:
- **Looks great, generate the full deck**: Proceed to Step 4
- **Adjust styling**: User will describe what to change (font size, spacing, figure placement, etc.)
- **Adjust content/layout**: User will describe structural changes

If the user wants changes, apply them to the preview script, regenerate, and ask again. **Iterate on these 2-3 slides until the user approves the style.** Only then proceed to the full deck.

---

### Step 4: Generate the Full PPTX

Once the user approves the preview style, generate the complete slide deck.

**4a. Write the generation script.**

Create a self-contained Python script at `scripts/generate_slides.py` (or a timestamped variant if one already exists, e.g., `scripts/generate_slides_YYYYMMDD.py`). Carry over any styling adjustments from the preview iteration. The script should:

1. Import the helper library. Resolve the path found in Step 0b:

```python
import sys
from pathlib import Path

# Try plugin locations for pptx_helpers (lives in scripts/ subdir)
_helpers_dirs = [
    *Path.home().glob(".claude/plugins/marketplaces/*/plugins/generate-slides/scripts"),
    *Path.home().glob(".claude/plugins/cache/*/generate-slides/*/scripts"),
]
for d in _helpers_dirs:
    if (d / "pptx_helpers.py").exists():
        sys.path.insert(0, str(d))
        break

from pptx_helpers import *

# Override style if project has a custom slide-style.yaml
for p in [Path("slide-style.yaml"), Path("docs/slide-style.yaml"), Path(".claude/slide-style.yaml")]:
    if p.exists():
        load_style(p)
        from pptx_helpers import *  # re-import updated constants
        break
```

2. Define one function per slide (`slide_01_title`, `slide_02_motivation`, etc.)
3. Each function creates slide content using the helpers
4. A `main()` that calls all slide functions and saves the PPTX

**4b. Styling rules for the generated script:**

- **Action titles**: Every slide title is a complete sentence stating the takeaway (not a topic label). See the Action Title Rule in Step 2.
- **Title slide**: White background, black text — clean and minimal
- **Content slides**: White background, black text, action title at top
- **No bold anywhere**: Hierarchy is conveyed through font size and spacing only. Never set `bold=True`.
- **Font**: Avenir Light (`FONT_NAME`) for all text, PT Mono (`CODE_FONT`) for code blocks
- **Font sizes**: 40pt titles, 28pt subtitles, 22pt body, 16pt tables, 14pt footnotes, 12pt code
- **Title position**: Top-aligned (~0.15" from top) to maximize content area
- **Colors**: Use color very sparingly. Black text (#000000), single blue accent (#036DEA). No colored text boxes.
- **Bullet emphasis**: Use blue accent color on key-term prefixes instead of bold (tuples render the first element in blue)
- **Callout boxes**: White background with thin grey border, NOT colored backgrounds
- **Tables**: Light grey header (#F5F5F5), no bold in any cells
- **Figures**: Centered, scaled to ~80% of slide width (or half-width for side-by-side)
- **Code boxes**: Light grey (#F8FAFC) background, PT Mono font, thin border
- **Positive values**: Green (#059669), Negative: Red (#DC2626) — only for data values, not decorative

**4c. Figure handling:**

- For each figure referenced in the outline, verify the file exists before embedding
- Use `add_figure(slide, fig_path, left, top, width=Inches(X))` — scale width to fit
- `add_figure` automatically clamps images to slide bounds (no overflow), but prefer explicit sizing
- For side-by-side figures: width ~5.5-6.0 inches each
- For full-width figures: width ~10.0-11.0 inches
- Place figures below the title area (top >= Inches(1.2))
- **Never place figures that extend past the right edge** (`left + width <= Inches(13.0)`) **or bottom edge** (`top + height <= Inches(7.2)`)

**4d. Content guidelines per slide type:**

- **Title slide**: Use `make_title_slide()` — white bg, title, author, affiliation, date
- **Content slides**: Use `make_content_slide()` then `add_bullets()` — 3-5 bullets max, no bold
- **Results slides**: Table or figure + 2-3 interpretation bullets below/beside
- **Comparison slides**: Side-by-side layout (figure left + text right, or two figures)
- **Conclusions slide**: 3-4 numbered takeaways, 1 line each. This is the last main slide (stays visible during Q&A).
- **ASCII diagrams**: Use `add_code_box()` for architecture, pipelines, etc.
- **Takeaway boxes**: Use `add_callout_box()` for key messages

**4e. Run the script:**

```bash
python scripts/generate_slides.py
```

Verify the output:
```python
python -c "
from pptx import Presentation
prs = Presentation('OUTPUT_PATH')
print(f'Generated {len(prs.slides)} slides')
total_img = sum(1 for s in prs.slides for sh in s.shapes if sh.shape_type == 13)
print(f'Embedded {total_img} images')
"
```

**4f. Run the verification harness.**

```bash
python ${CLAUDE_SKILL_DIR}/scripts/verify_slides.py OUTPUT_PATH
```

The verifier checks: action titles, figure bounds, font consistency, no "Thank You" ending, and content density. If any check fails, fix the issue in the generation script and re-run Steps 4e-4f before proceeding. The ghost deck test output is informational — review it to confirm the title sequence tells a coherent story.

---

### Step 5: Report to User

Display a concise summary:

```
Generated: {output_path}
- {N} slides ({M} main + {K} supplementary)
- {P} figures embedded
- File size: {size} KB

Slide overview:
1. {title}
2. {title}
...
```

Then ask if they want adjustments (swap figures, add/remove slides, change text, etc.).

---

## Output Path Convention

Default: `docs/slides/{project-name}-{YYYY-MM-DD}.pptx`

If `docs/slides/` doesn't exist, create it. If a file with the same name exists, append `-v2`, `-v3`, etc.

---

## Helper Library & Style Customization

For the full helper function reference, style YAML schema, and color/layout/typography constants, see [references/style-guide.md](../references/style-guide.md).

Quick reference: `scripts/pptx_helpers.py` provides `new_presentation()`, `add_blank_slide()`, `add_slide_title()`, `add_bullets()`, `add_figure()`, `add_table()`, `add_code_box()`, `add_callout_box()`, `make_title_slide()`, `make_content_slide()`, `load_style()`.

To customize the style, place a `slide-style.yaml` in your project root (partial YAML OK — only specified keys override defaults). See the style guide for the full schema.

---

## Verification Harness

The bundled verifier at `scripts/verify_slides.py` performs automated quality checks:

| Check | What it catches |
|-------|----------------|
| **Action titles** | Topic-label titles ("Results") instead of sentence takeaways |
| **Ghost deck test** | Prints all titles sequentially — do they tell a story? |
| **Figure bounds** | Images overflowing slide edges |
| **Margin compliance** | Shapes extending past left/right/bottom margins |
| **Shape overlaps** | Title vs accent line, text vs figure collisions |
| **Text alignment** | Text boxes with inconsistent left-edge positioning |
| **Font consistency** | Fonts not matching the style config |
| **Conclusions ending** | Last slide being "Thank You" or "Questions?" |
| **Content density** | Slides with >6 bullets |

Run after generation: `python ${CLAUDE_SKILL_DIR}/scripts/verify_slides.py output.pptx`

---

## Edge Cases

- **No figures found**: Generate text-only slides. Note the limitation and suggest pointing to the correct directory.
- **python-pptx not installed**: Install automatically with `pip install python-pptx`.
- **pptx_helpers.py not found**: Define all helper functions inline in the generated script (copy essential functions).
- **Very many figures (>30)**: Group by directory, select representatives for main slides, put rest in supplementary.
- **Conversation context compressed**: Rely on filesystem artifacts (docs, notebooks, figures). Read key markdown docs to reconstruct the narrative. Be transparent about limitations.
- **Script already exists**: Use a timestamped name like `scripts/generate_slides_YYYYMMDD.py` to avoid overwriting.
- **User provides very specific slide content**: Honor their exact wording — don't paraphrase or "improve" their text.
- **Mixed content in directory**: Ask user which project/analysis to focus on.
- **Custom slide-style.yaml**: Partial overrides OK — only specified keys are overridden. The rest use the bundled default.

---

## Tips

- **Action titles are mandatory**: "LoRA improves RNA R by 67%" beats "Results" every time. The ghost deck test catches weak titles.
- **1 slide per minute** is a good default for scientific talks.
- **Key message per slide**: Every slide should have exactly ONE takeaway — the title IS that takeaway.
- **Preview first**: Always generate 2-3 slides for early feedback. Iterating on style with 2 slides is 10x faster than with 15.
- **End with Conclusions, not "Thank You"**: The conclusions slide stays visible during Q&A, keeping the audience engaged with your findings.
- **Figure-to-text ratio**: ~50% of content slides should have a figure.
- **Supplementary slides**: Put QC, detailed methods, and backup figures here for Q&A.
- **Blue-accent prefixes on bullets** improve scannability without using bold — pass `("Key term: ", "explanation")` tuples.
- **Tables**: Keep to 5-7 rows max. Use GREEN/RED only for data values, not decoration.
- **No bold**: Resist the urge. Size and spacing provide enough hierarchy with Avenir Light.
