---
allowed-tools:
  - Read
  - Write
  - Glob
  - Grep
  - Bash(ls *)
  - Bash(find * -name)
  - Bash(file *)
  - Bash(identify *)
  - Bash(wc *)
  - Bash(date *)
  - Bash(mkdir *)
description: Convert analysis session artifacts into a structured report/slide deck outline
---

# Prep Report

Convert the current analysis session's figures, notebooks, and findings into a structured report outline (slide deck, Google Doc, or Confluence page).

**Arguments:** `$ARGUMENTS`

Format: `[time_or_slides] [format] [-- path/to/report-style-*.md or audience name]`

Examples:
- `/prep-report 15min` → ~15-slide deck outline
- `/prep-report 8 slides` → 8-slide deck
- `/prep-report 30min doc` → long-form document outline
- `/prep-report 10min -- loic` → 10-min deck using report-style-loic-royer.md
- `/prep-report 10min -- ./report-style-loic-royer.md` → explicit path to style file
- `/prep-report` → default: 10-min slide deck, auto-detect report-style*.md

## Instructions

Follow these steps to generate the report outline.

### Step 0: Gather Context and Parse Arguments

First, run these Bash commands to collect context:

```bash
date '+%Y-%m-%d %A'
```
```bash
pwd
```
```bash
find . -maxdepth 5 \( -name "*.png" -o -name "*.jpg" -o -name "*.jpeg" -o -name "*.svg" -o -name "*.pdf" -o -name "*.html" \) -not -path "./.git/*" -not -path "./.claude/*" -not -path "*/node_modules/*" -not -path "*/__pycache__/*" -printf "%T@ %p\n" 2>/dev/null | sort -n | awk '{print $2}' | tail -200
```
```bash
find . -maxdepth 5 \( -name "*.ipynb" -o -name "*.py" \) -not -path "./.git/*" -not -path "./.claude/*" -not -path "*/node_modules/*" -not -path "*/__pycache__/*" -not -path "*/site-packages/*" -not -name "setup.py" -not -name "conftest.py" -printf "%T@ %p\n" 2>/dev/null | sort -n | awk '{print $2}' | tail -50
```
```bash
ls -1 report-style*.md docs/report-style*.md .claude/report-style*.md 2>/dev/null || echo "NO_REPORT_STYLE_FILES"
```
```bash
find . -maxdepth 2 -type d -not -path "./.git*" -not -path "./.claude*" -not -path "*/__pycache__*" 2>/dev/null | head -40
```

Then parse `$ARGUMENTS` to determine:
- **Duration/slide count**: Number of minutes or slides. Default: 10 minutes (~10 slides at 1 slide/min).
- **Format**: "slides" (default), "doc", or "confluence".
- **Report style**: If `--` separator is present, the value after it is either:
  - A full path to a style file (e.g., `./report-style-loic-royer.md`)
  - A short name to fuzzy-match against available `report-style-*.md` files (e.g., `loic` matches `report-style-loic-royer.md`)
  - If not provided, check the pre-fetched list of available style files. If exactly one exists, use it. If multiple exist, list them and ask the user which audience to target.

If a report-style file was found, read it carefully. It defines audience preferences:
- Narrative vs. technical depth preference
- Key stakeholders and their focus areas
- Preferred structure/template
- Any specific sections required

### Step 1: Catalog Artifacts

From the pre-fetched figure list, categorize each figure:

1. **Read the filenames and paths** to infer categories:
   - Naming patterns (e.g., `umap_*.png`, `histogram_*.png`, `heatmap_*.png`)
   - Directory grouping (e.g., `figures/clustering/`, `figures/qc/`)
   - Temporal ordering (modification time, already sorted in pre-fetched data)

2. **Identify figure types** by name/path patterns:
   - **QC/Diagnostic**: files with `qc`, `diagnostic`, `check`, `distribution`, `histogram` in name
   - **Key Results**: files with `result`, `final`, `summary`, `comparison` in name
   - **Exploration**: files with `explore`, `test`, `draft`, `tmp`, `debug` in name
   - **Methodology**: files with `workflow`, `pipeline`, `schematic`, `method` in name
   - **Supplementary**: everything else

3. **Read notebook files** (jupytext .py or .ipynb) to understand:
   - What analyses were performed (read markdown cells / comments)
   - The logical flow of the analysis
   - Which figures were generated in which context
   - Key findings noted in comments or markdown cells

   IMPORTANT: For .py jupytext files, look for `# %%` cell markers and `# %% [markdown]` sections. Read at least the first 100 lines and any markdown cells to understand the narrative. For large notebooks, skim headers and markdown cells rather than reading every code line.

4. **Build a master artifact list** as a table:

   | # | File | Type | Category | Context/Description |
   |---|------|------|----------|-------------------|
   | 1 | ./figures/umap_clusters.png | UMAP | Key Result | Cluster visualization |
   | ... | ... | ... | ... | ... |

### Step 2: Reconstruct the Analysis Narrative

Using the conversation context (what you can see from this session) AND the notebook contents:

1. **Identify the research question / objective** — what was the session trying to answer?
2. **Map the analysis flow** — what steps were taken, in what order?
3. **Note key decision points** — where did the analysis pivot or course-correct?
4. **Extract key findings** — what were the main results, insights, or conclusions?
5. **Note any caveats or limitations** mentioned during the analysis

If conversation context has been compressed and you cannot reconstruct the full narrative, say so explicitly and rely more heavily on notebook contents and figure names.

### Step 3: Design the Report Structure

Based on the format, duration, and audience preferences:

#### For Slide Deck (default):

Apply the **1 slide per minute** rule. Structure as:

| Slide | Purpose | Typical Allocation |
|-------|---------|-------------------|
| 1 | Title + context | Always |
| 2 | Objective / research question | Always |
| 3-4 | Background / methodology (if audience needs it) | Optional per report-style.md |
| 5-(N-2) | Key results (bulk of the deck) | ~60-70% of slides |
| N-1 | Summary / conclusions | Always |
| N | Next steps / discussion | Always |

Adjust based on report-style.md preferences:
- **"Big picture" audience**: Fewer methodology slides, more conclusion/implication slides
- **"Technical" audience**: Include methodology, QC, and supplementary details
- **"Executive" audience**: Lead with conclusions, then supporting evidence

#### For Document (doc/confluence):

Structure as:
1. Executive Summary (1 paragraph)
2. Background & Objective
3. Methods (brief unless technical audience)
4. Results (with inline figures)
5. Discussion & Interpretation
6. Next Steps
7. Appendix (supplementary figures, detailed methods)

### Step 4: Assign Figures to Slides/Sections

For each slide or section:
1. Select the most relevant figure(s) from the artifact catalog
2. Limit to **1-2 figures per slide** (more = cluttered)
3. Prioritize "Key Result" figures over "QC/Diagnostic" ones for main slides
4. QC figures go in backup/appendix slides
5. Exploratory/draft figures are usually excluded unless they show important negative results

Explicitly note which figures are:
- **INCLUDE**: Goes in the main report
- **BACKUP**: Available if questions arise
- **SKIP**: Not relevant or superseded by a better version

### Step 5: Generate the Report Outline

Output the report outline using this template:

---

BEGIN TEMPLATE:

```markdown
# Report Outline: {{title}}

**Date:** {{date}}
**Duration:** {{minutes}} minutes (~{{slide_count}} slides)
**Audience:** {{audience_description from report-style.md, or "General/Technical"}}
**Analysis Directory:** {{working_directory}}

---

## Narrative Arc

{{2-3 sentence summary of the story this report tells — from question to finding}}

---

## Slide-by-Slide Outline

### Slide 1: {{Title Slide}}
- **Title:** {{suggested title}}
- **Subtitle:** {{date, project name, presenter}}

### Slide 2: {{Objective}}
- **Key message:** {{one sentence}}
- **Talking points:**
  - {{point 1}}
  - {{point 2}}

### Slide 3: {{slide title}}
- **Key message:** {{one sentence — what should the audience take away?}}
- **Figure(s):** `{{path/to/figure.png}}`
- **Talking points:**
  - {{point 1}}
  - {{point 2}}
  - {{point 3}}
- **Speaker notes:** {{additional context, anticipated questions}}

... (repeat for each slide)

### Slide N: Next Steps
- **Key message:** {{what happens next}}
- **Talking points:**
  - {{next step 1}}
  - {{next step 2}}

---

## Backup Slides

### Backup 1: {{title}}
- **Figure(s):** `{{path/to/qc_figure.png}}`
- **When to use:** {{anticipated question this answers}}

---

## Artifact Summary

### Included ({{count}})
| Figure | Slide | Purpose |
|--------|-------|---------|
| `{{path}}` | {{#}} | {{why included}} |

### Backup ({{count}})
| Figure | Purpose |
|--------|---------|
| `{{path}}` | {{why kept as backup}} |

### Skipped ({{count}})
| Figure | Reason |
|--------|--------|
| `{{path}}` | {{why excluded}} |

---

## Suggested Narrative Script

{{Optional: if report-style.md requests it, or if user asked for "doc" format, include a 1-2 paragraph narrative per slide that could serve as speaker notes or document text}}
```

END TEMPLATE

---

### Step 6: Write Output and Display Summary

1. **Write the full outline** to `report-outline-{{YYYY-MM-DD}}.md` in the current working directory.

2. **Display a concise summary in chat** (~15-20 lines max) with:
   - Report title and format
   - Number of slides and time allocation
   - The narrative arc (2-3 sentences)
   - Count of figures: included / backup / skipped
   - Top 3 key messages
   - Path to the full outline file
   - Any warnings (e.g., "No report-style.md found — using default structure", "Conversation context was compressed — outline is based primarily on filesystem artifacts")

3. **Ask if the user wants to**:
   - Adjust the narrative arc
   - Swap any figures in/out
   - Change the emphasis (more technical / more high-level)
   - Generate a different format (switch from slides to doc)

### Edge Cases

- **No figures found**: Still generate the outline based on notebook contents and conversation. Note that no figures were discovered and suggest the user point to the correct directory.
- **No notebooks found**: Rely on conversation context and figure names. Note the limitation.
- **No report-style.md**: Use a balanced default (mix of narrative and technical). Note that creating a `report-style.md` would improve future outlines.
- **Very large number of figures (>50)**: Group by directory/category first, then select representatives. Don't list every figure in the main outline.
- **Mixed projects in directory**: If figures seem to belong to different analyses, ask the user which project/analysis to focus on.
- **Conversation context fully compressed**: Be transparent about this. Rely on filesystem artifacts and note that the outline may miss nuances from the discussion.
- **User asks for Google Slides / PowerPoint**: Explain that you can generate the outline and Markdown, but cannot directly create .pptx/.gslides files. Suggest using the outline to build slides manually, or using a tool like Marp or reveal.js for markdown-to-slides conversion.

### Tips for report-style.md

If no report-style.md exists, suggest creating one with this template:

```markdown
# Report Style Preferences

## Audience
- Primary: [e.g., "Project manager, non-technical"]
- Secondary: [e.g., "Computational biology team"]

## Preferences
- Focus: [narrative/technical/balanced]
- Detail level: [high-level/moderate/detailed]
- Figures: [prefer clean summary plots / OK with raw diagnostic plots]

## Structure
- Always include: [e.g., "executive summary", "next steps"]
- Skip unless asked: [e.g., "detailed methods", "QC diagnostics"]
- Max slides per topic: [e.g., 3]

## Style Notes
- [e.g., "PM prefers conclusions first, then evidence"]
- [e.g., "Always include timeline for next steps"]
- [e.g., "Use protein structure visualizations when possible"]
```
