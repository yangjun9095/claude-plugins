---
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - AskUserQuestion
  - Bash(ls *)
  - Bash(find * -name)
  - Bash(find * -maxdepth)
  - Bash(file *)
  - Bash(identify *)
  - Bash(wc *)
  - Bash(date *)
  - Bash(mkdir *)
  - Bash(cp *)
  - Bash(git *)
  - Bash(pwd *)
  - Bash(echo *)
  - Bash(head *)
  - Bash(tail *)
  - Bash(grep *)
  - Bash(sed *)
  - WebFetch
description: Convert analysis session artifacts into a structured report — slide deck, document, or Anthropic Science blog-style write-up
---

# Prep Report

Convert the current analysis session's figures, notebooks, conversation history, and findings into a structured report. Three output formats supported: **slides**, **doc**, and **blog** (Anthropic Science blog style).

**Arguments:** `$ARGUMENTS`

Format: `[time_or_slides] [format] [-- path/to/report-style-*.md or audience name]`

Examples:
- `/prep-report 15min` → ~15-slide deck outline
- `/prep-report 8 slides` → 8-slide deck
- `/prep-report 30min doc` → long-form document outline
- `/prep-report blog` → Anthropic Science blog-style write-up (interactive)
- `/prep-report blog -- vibe-physics` → blog post using the Vibe Physics template
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
ls -1 report-style*.md docs/report-style*.md .claude/report-style*.md /hpc/projects/data.science/yangjoon.kim/report-style*.md 2>/dev/null || echo "NO_REPORT_STYLE_FILES"
```
```bash
find . -maxdepth 2 -type d -not -path "./.git*" -not -path "./.claude*" -not -path "*/__pycache__*" 2>/dev/null | head -40
```

Then parse `$ARGUMENTS` to determine:
- **Duration/slide count**: Number of minutes or slides. Default: 10 minutes (~10 slides at 1 slide/min). Ignored for `blog` mode.
- **Format**: "slides" (default), "doc", "confluence", or **"blog"** (Anthropic Science blog-style write-up).
- **Report style**: If `--` separator is present, the value after it is either:
  - A full path to a style file (e.g., `./report-style-loic-royer.md`)
  - A short name to fuzzy-match against available `report-style-*.md` files (e.g., `loic` matches `report-style-loic-royer.md`)
  - If not provided, check the pre-fetched list of available style files. If exactly one exists, use it. If multiple exist, list them and ask the user which audience to target.

If a report-style file was found, read it carefully. It defines audience preferences:
- Narrative vs. technical depth preference
- Key stakeholders and their focus areas
- Preferred structure/template
- Any specific sections required

**MODE DISPATCH:** If `format == "blog"`, **skip Steps 1-7 below** and jump to **"Blog Mode Workflow"** at the end of this document. The blog flow uses a different pipeline (conversation transcript + figure inventory + interactive interview + outline approval gate + section-by-section drafting). The slides/doc flow remains as Steps 1-7.

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

### Step 7: Archive Report (Structured Save)

After writing the draft outline and displaying the summary, offer to archive the report to a permanent location.

1. **Detect the project's main repo root**. Check if the current directory is a git worktree or the main repo:
   ```bash
   git rev-parse --show-toplevel
   ```
   ```bash
   git worktree list
   ```
   If in a worktree, identify the main worktree path (first line of `git worktree list`).

2. **Derive a topic name** from the report title or the current branch name. Sanitize it (lowercase, hyphens, no spaces):
   - From branch: `cross-locus-comparison` → topic `cross-locus-comparison`
   - From title: "Cross-Locus ISM Comparison" → topic `cross-locus-ism-comparison`

3. **Derive the audience name** from the `--` argument or report-style file:
   - `-- loic` → `loic-royer`
   - `-- ./report-style-loic-royer.md` → `loic-royer`
   - No audience specified → `general`

4. **Construct the archive path**:
   ```
   {main_repo_root}/reports/{topic}/{YYYY-MM-DD}_{audience}.md
   ```
   Example: `reports/cross-locus-comparison/2026-03-24_loic-royer.md`

5. **Ask the user** using AskUserQuestion:
   - "Archive this report outline to `reports/{topic}/{date}_{audience}.md` in the main repo?"
   - Options: "Yes, archive it", "No, keep only the local draft", "Yes, but change the topic/path"
   - If "change the topic/path", ask for the corrected topic name

6. **If yes**, execute:
   ```bash
   mkdir -p {main_repo_root}/reports/{topic}
   cp {draft_path} {main_repo_root}/reports/{topic}/{YYYY-MM-DD}_{audience}.md
   ```

7. **Check if `reports/` is gitignored**. If it is, inform the user:
   > "Note: `reports/` is currently gitignored. The archive is saved on disk but won't be tracked by git. To track report outlines, remove `reports/` from `.gitignore`."

   If it is NOT gitignored, inform the user:
   > "Report archived and will be tracked by git. Commit when ready."

8. **Update the draft file** with a header noting where the archive copy lives:
   ```markdown
   <!-- Archived to: {archive_path} -->
   ```

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

---

# Blog Mode Workflow

Triggered when `format == "blog"`. Produces an Anthropic Science blog-style write-up from the current Claude Code session (transcript + memory + figures). The flow is **interactive** — there are two mandatory stop points: the **interview** (Step B2) and the **outline approval** (Step B4). Do not draft prose until both are cleared.

## Step B-Style: Load the blog style guide

Read the plugin-bundled style guide. Try these paths in order, take the first that exists:

```bash
ls -1 ~/.claude/plugins/marketplaces/*/plugins/prep-report/references/anthropic-blog-style.md ~/.claude/plugins/cache/*/prep-report/*/references/anthropic-blog-style.md 2>/dev/null | head -1
```

Read it. It defines:
- The hook pattern (open question, not announcement)
- Three structural templates (BioMystery / Vibe Physics / Long-Running Claude)
- Voice rules (first-person, hedging language, terse figure captions)
- The "honest-about-failures" requirement
- Anti-patterns to avoid

**Anchor every drafting decision to this guide.** When in doubt, re-read it.

## Step B0: Locate the conversation transcript

The most context-rich input for a blog is the actual session transcript. Auto-detect candidates for the current working directory:

```bash
cwd_enc=$(pwd | sed 's|[/.]|-|g')
ls -t ~/.claude/projects/$cwd_enc/*.jsonl 2>/dev/null | head -3
```

For each candidate, get its size and rough turn count:

```bash
for f in <top_3_paths>; do
  echo "$f  size=$(wc -c < "$f")  lines=$(wc -l < "$f")"
done
```

Use AskUserQuestion to confirm the source. Options:
- **Auto-detected (most recent)**: `<filename>` (N lines, last modified <date>)
- **Pick a different transcript**: list the next two
- **Use a saved markdown file instead**: ask for path
- **Multiple sources**: combine a transcript + a `notes.md`

If the user picks a transcript, parse it (each line is a JSON event). Extract only the substantive content:
- User text messages (skip `<system-reminder>`, `<command-name>`, hook outputs)
- Assistant text outputs (skip raw tool-call JSON dumps; keep summaries)
- Tool-call summaries that show what was done (file edits, bash commands run, figures saved)

Do NOT load the entire transcript into context if it's large (>500 lines). Sample: first 50 lines, last 100 lines, plus any line containing keywords like "figure", "result", "found", "wrong", "problem", "solved".

## Step B1: Load supporting context

In addition to the transcript, gather:

```bash
# Memory file
ls ~/.claude/projects/$cwd_enc/memory/MEMORY.md 2>/dev/null

# CLAUDE.md anywhere up the tree
find . -maxdepth 4 -name "CLAUDE.md" -not -path "./.git/*" 2>/dev/null

# Project context / notes
find . -maxdepth 3 \( -name "context.md" -o -name "notes.md" -o -iname "*notes*.md" \) -not -path "./.git/*" 2>/dev/null

# Recent figures (prefer figure-style outputs — PNG with matching PDF)
find . -maxdepth 5 -name "*.png" -not -path "./.git/*" -not -path "*/node_modules/*" -printf "%T@ %p\n" 2>/dev/null | sort -rn | head -30
```

For each PNG, check whether a matching PDF exists in the same directory (signature of a figure-style verified figure). Mark these as **verified** in the inventory — they're the strongest candidates for the post.

## Step B2: Interview the user (MANDATORY STOP — do NOT skip)

The hook is the single most important thing in a science blog post. You cannot guess it from the transcript alone. **Stop here and ask.**

Use AskUserQuestion with these questions (batch into one call):

1. **Through-line / hook framing**: Based on the transcript, your best guess of the through-line is "<one-sentence guess>". State the actual open question or claim you want this post to land. (free text)
2. **Audience**: Who reads this?
   - "Lab internal — colleagues who know the project"
   - "Bioinformatics / domain peers — know the science, not this work"
   - "ML/AI-curious scientists — care about the methodology"
   - "General technical — explain everything briefly"
   - "Other (specify)"
3. **Voice**: Which of the three templates fits best?
   - "BioMystery (we-voice, methodology + results)"
   - "Vibe Physics (I-voice, narrative arc with reversals)"
   - "Long-Running Claude (we-voice, practical methodology)"
   - "Mix / let me describe"
4. **Required + forbidden**: Anything that MUST appear (specific result, figure, person to credit)? Anything to keep out (private data, unfinished claims, internal jargon)?

After the answers come back, summarize what you heard in 3 lines. If anything is unclear or contradicts the transcript, **ask one follow-up** before moving on. Do not rush to the outline.

## Step B3: Extract the narrative skeleton

Now that you know the hook, audience, and voice, distill the transcript into a structured skeleton (internal — not shown to user yet):

1. **Opening question** — the user's first substantive prompt (or your reframing of it)
2. **Setup / motivation** — what was the goal, why did it matter
3. **Decision points** — places the user redirected, pushed back, or changed scope
4. **Dead ends / failures** — failed attempts, errors, "wait that's wrong" moments. **These are required for the post.** If the transcript shows none, ask the user explicitly: "Were there any wrong turns, surprises, or things you tried that didn't work?"
5. **The eventual finding** — what artifact, conclusion, or working system came out
6. **Direct quotes (2-4)** — verbatim user/assistant exchanges that capture pivotal moments. Quoting real exchanges makes the post concrete.
7. **Figures to feature** — pick 2-5 from the inventory, prioritizing verified figures and ones tied to specific moments in the narrative

## Step B4: Propose the outline (BULLET LEVEL — STOP for approval)

Output a markdown outline at **bullet-point depth — NOT prose yet**. Write it to `blog-outline-{topic}-{YYYY-MM-DD}.md` in the cwd. Use this template:

```markdown
# {{working title}}

**Hook (2-3 sentences):**
- Option A: {{hook proposal #1}}
- Option B (alternate): {{hook #2}}

**Audience:** {{from interview}}
**Template:** {{BioMystery / Vibe Physics / Long-Running Claude / Mix}}
**Estimated length:** {{800-2000 words}}

---

## §1 — {{punchy header}}
- {{bullet}}
- {{bullet}}
- {{bullet}}
- _Figure_: `figures/{{filename}}` — {{caption idea}}

## §2 — {{punchy header}}
- ...

## §3 — {{punchy header}}
- ...

## §4 — What didn't work
- {{failure 1}}
- {{failure 2}}

## §5 — What's next
- {{open question}}
- {{follow-up}}

## Appendix (optional)
- {{numbers / metrics}}
- {{links / references}}
```

Then ask via AskUserQuestion:

- "Approve this outline as-is — proceed to drafting prose"
- "Iterate on a specific section (which one, what change)"
- "Regenerate with a different angle / restart interview"
- "Drop or merge sections (specify)"
- "Swap a figure (specify section + new figure path)"

**Loop on this step until the user approves.** Each revision should be quick — keep updating the same outline file. **Do not write prose until approval.**

## Step B5: Draft the prose

Once the outline is approved, draft section by section. For each section, follow these rules from the style guide:

- **2-4 short paragraphs**, each ≤4 sentences
- **First-person voice** (per the user's choice — singular or plural)
- **Concrete**: quote the conversation if you can, show actual code or output, include real numbers
- **Hedge honestly**: "we found", "it appears", "in our setup", "we can't fully rule out"
- **Inline figures** using markdown image syntax with terse one-line captions:
  ```
  ![Fig N: <one-line statement>](figures/filename.png)
  ```
- **Avoid** marketing copy, vague figure references, recap conclusions, jargon walls

Write the draft to `blog-{topic}-{YYYY-MM-DD}.md` in the cwd. After writing, print:
- Total word count
- Estimated reading time (≈200 wpm)
- Section-by-section word counts (catch over-long sections)

## Step B6: Review and iterate

After the draft, offer via AskUserQuestion:

- "Read the draft back to me / show word count breakdown"
- "Tighten section X (cut Y%)"
- "Expand section X (need more depth on Z)"
- "Swap figure in section X"
- "Change a header (which one, to what)"
- "I'll edit by hand from here"
- "Looks good — archive it"

## Step B7: Archive (same as Step 7 above)

When the user approves, archive to:

```
{main_repo_root}/reports/{topic}/blog_{YYYY-MM-DD}.md
```

Same git/gitignore checks as Step 7. Note in the draft footer where the archive copy lives.

## Edge cases for blog mode

- **Transcript not found**: Ask the user to point at one or fall back to filesystem-only narrative (note this clearly in the post — "this draft is reconstructed from artifacts, not the conversation").
- **Transcript too large to read fully**: Sample (first 50, last 100, keyword matches). Tell the user: "I sampled the transcript — let me know if I missed a key moment."
- **No failures in the transcript**: Required by the style. Ask the user explicitly: "What went wrong or was harder than expected?"
- **No figures**: A blog can run on prose alone, but offer to point at a `figures/` directory or generate one with `/figure-style`.
- **User wants to use a non-Anthropic style** (e.g., Distill, Substack technical): Ask for an example URL, fetch it with WebFetch, derive a one-shot style guide for this post (do not modify the bundled `anthropic-blog-style.md`).
- **Multiple disconnected sessions on the same topic**: Offer to combine 2-3 transcripts. Read each, build a unified skeleton, note in the interview that the timeline spans multiple sessions.

