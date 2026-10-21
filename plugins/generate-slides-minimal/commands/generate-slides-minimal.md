---
description: "Build a .pptx deck from the artifacts of a project. It starts from the message of the talk, drafts speaker notes, and lints the deck against rules that carry an evidence tier."
allowed-tools:
  - Read
  - Write
  - Edit
  - Glob
  - Grep
  - AskUserQuestion
  - Bash(ls *)
  - Bash(mkdir -p docs/slides)
  - Bash(date +%Y-%m-%d)
  - Bash(python3 -m pip install python-pptx*)
  - Bash(python3 -m pip install PyYAML*)
  - Bash(python3 -m pip install Pillow*)
  - Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design_lint.py" *)
  - Bash(python3 docs/slides/build-*.py)
---

# Generate slides (minimal)

Build a `.pptx` deck from the figures, notebooks and notes of the current project. The deck starts from the message of the talk. Each slide has a sentence headline over one visual. A design linter checks the finished deck.

**Arguments:** `$ARGUMENTS`

Format: `/generate-slides-minimal [15min | N slides] [--profile peers|lab-meeting|general] [--theme light|dark] [--no-notes]`

- `/generate-slides-minimal 15min` builds a deck for a talk of 15 minutes.
- `/generate-slides-minimal 12 slides --profile lab-meeting` builds a deck with 12 main slides.
- `/generate-slides-minimal --theme dark --no-notes` builds a dark deck with no speaker notes.

The defaults are the profile `peers`, the theme `light` and speaker notes on.

## Rules for every step

- Never paraphrase the words of the user. Use a sentence that the user gives exactly as written.
- A message of more than 20 words gets a `title-sentence` warning on the roadmap slide. A take-home claim of more than 15 words gets a `take-home-words` warning. If the user wrote the sentence, keep it as written. Let the warning stand.
- Take every number from an artifact. Add `source` to each slide that has a `source` parameter and shows a number.
- The title slide shows no number from the data. The roadmap slide and the take-home slide show only numbers that another slide sources with its own source line.
- If no artifact holds a number, ask the user. Never estimate a number.
- With `--no-notes`, draft no notes. Run the linter with `--no-notes`.
- The notes are drafts. The author rewrites them in their own voice.
- The linter does not judge three things. These are the fit of a figure to its headline, the glance test and color-only codes. You review them in Step 6.

## Step 0: Preflight

**0a. Check the libraries.** Run the linter with `--help`. The check imports python-pptx, PyYAML and Pillow.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design_lint.py" --help
```

If the error names `pptx`, install python-pptx. If it names `yaml`, install PyYAML. If it names `PIL` or `Image`, install Pillow. Run the check again after each install.

```bash
python3 -m pip install python-pptx
python3 -m pip install PyYAML
python3 -m pip install Pillow
```

If pip refuses with a permission error, ask the user to run `! python3 -m pip install --user <package>` themselves.
If pip says `externally-managed-environment`, ask the user to create a virtual environment or to run the install with `--break-system-packages` themselves.

**0b. Find the style file of the project.** The file is `slide-style-minimal.yaml`. It can sit in the project folder, in `docs` or in `.claude`.

```bash
ls slide-style-minimal.yaml docs/slide-style-minimal.yaml .claude/slide-style-minimal.yaml 2>/dev/null
```

If a file exists, `Read` it and tell the user which values it changes. The builder script finds the file by itself.

**0c. Read the arguments.**
- `15min` sets the talk length. The number before `min` is the number of minutes.
- `N slides` sets the number of main slides. A main slide is any slide except the title slide and the backup slides.
- For `N slides`, pass the linter the smallest whole number of minutes that allows N main slides. That number is N for `peers` and `general`. It is N divided by 1.5, rounded up, for `lab-meeting`.
- With no length, ask for the minutes in Step 2.
- `--profile` and `--theme` set the profile and the theme. `--no-notes` switches the notes off.

**0d. Set the date and the output folder.**

```bash
date +%Y-%m-%d
mkdir -p docs/slides
```

## Step 1: Catalog the artifacts

Use `Glob` to list the figures, the notebooks and the documents of the project. Skip `.git`, `node_modules`, `site-packages` and `docs/slides`.

- Figures: `**/*.png`, `**/*.jpg`, `**/*.jpeg`. The helpers also embed GIF, BMP, TIFF and WMF files.
- An SVG or PDF figure needs a raster copy. Ask the user to export one.
- Notebooks and scripts: `**/*.ipynb` and `**/*.py`.
- Documents: `README.md`, result notes and any `report-style` file.

Use `Grep` to find the notebook or script that writes each figure. Search for `savefig` and for the file name. `Read` the producers, the README and the result notes. If no script writes a figure, write the data file or the note that holds its numbers as the source.

Build an inventory of each figure: its path, its script, what it shows, and its numbers and sources.

## Step 2: Message first

Ask with `AskUserQuestion`. A call holds at most four questions, so ask the title-slide question in a second call when five questions remain. Skip a question that the arguments already answer.

1. Message: "Which sentence must the audience keep?" Offer two or three sentences that you draft from the artifacts. The user can choose one or write their own.
2. Take-homes: "Which claims go on the last slide?" Allow at most three. Each claim needs a baseline: a control, a prior value or chance.
3. Minutes: the length of the talk.
4. Profile: `peers` (the default), `lab-meeting` or `general`. Say in one line what each profile changes.
5. Title slide: the title, the author, the affiliation and the date, when the artifacts do not hold them.

If the user writes a sentence of their own, keep it as written. Use that sentence as the message or as a claim.

Before you start Step 3, `Read` `${CLAUDE_PLUGIN_ROOT}/references/design-principles.md`. It lists each principle with its evidence tier. Apply it to the outline.

## Step 3: Story spine and outline

The spine has four parts: need, approach, evidence and take-homes. Duarte and Atkinson describe this three-act form.

Draft the outline as a table with one row for each slide. The columns are the number, the layout, the headline, the evidence element, the cue and, with notes on, the script.

- Layout: one of `title`, `roadmap`, `assertion_evidence`, `big_number`, `take_home` or `backup`.
- Headline: one sentence of 6 to 20 words with a verb. It states the claim and fits in two lines.
- Evidence element: a picture with its path, a chart with its numbers and source, or a table.
- Cue: the part of the evidence to highlight, such as one bar, one curve or one row.
- Script: a few sentences that the speaker says aloud. Keep each script short enough to say in about one minute.

Follow these rules for the order and the content.

- Slide 1 is the `title` slide. It shows the title slide fields of Step 2.
- Slide 2 is the `roadmap` slide. It states the message and 3 to 5 sections. A section name takes one line: about 9 characters for 5 sections, 12 for 4 and 16 for 3.
- Put the need before the first finding. If no figure shows the need, use the baseline number on a `big_number` slide. You can also use a table of two or three terms that the audience must know.
- An `assertion_evidence` slide has one evidence element, at most two call-outs and one source line.
- A `big_number` slide has a number of at most 7 characters, its label, its baseline and its source.
- The `take_home` slide ends the main deck. It holds one to three claims. Each claim and each baseline hold at most 15 words. The `words-per-slide` rule does not check this slide.
- A `backup` slide has the same shape as an `assertion_evidence` slide and follows the take-home slide.
- Split a complex figure over consecutive slides, one layer for each slide. The plugin writes no animations.
- Keep each slide short. For `peers`, `lab-meeting` and `general`, the linter warns above 25, 40 and 15 words and gives an error above 40, 60 and 25.
- Keep the main slides within the pace of the profile: one slide per minute, or 1.5 for `lab-meeting`.

Apply the ghost-deck test. Read the headlines in order. They alone must tell the story. Repair any gap before you show the outline.

Show the outline and ask for approval with `AskUserQuestion`. Offer these answers: approve, change the slides, change the evidence, change the story. Repeat until the user approves.

## Step 4: Preview two or three slides

Pick two or three slides of different layouts, for example one picture slide, one `big_number` slide and the `take_home` slide. Skip the title slide.

Write the builder script as Step 5 describes, with only these slides. Save the preview builder as `docs/slides/build-<project>-<date>-preview.py`. Save the deck as `docs/slides/<project>-<date>-preview.pptx`. Run it with `python3 docs/slides/build-<project>-<date>-preview.py`. If the script fails, repair it with `Edit`. Run it again.

Tell the user to open the preview file. Ask with `AskUserQuestion` whether the look and the wording suit them.

To change a color, a font or a size, offer to write `slide-style-minimal.yaml` in the project folder. Fix the wording in the script and build the preview again if the user asks.

## Step 5: Generate the deck

`<project>` is the name of the project folder in lowercase, with hyphens for spaces. `<date>` is the date of Step 0d.

Use `Write` to save the builder script as `docs/slides/build-<project>-<date>.py`. The script saves the deck as `docs/slides/<project>-<date>.pptx`.

Start the script with this code. The `sys.path.insert` line holds the scripts folder of this plugin. Write that absolute path in the script. The script runs outside Claude Code, so it cannot expand a variable.

```python
import sys
from pathlib import Path

sys.path.insert(0, "${CLAUDE_PLUGIN_ROOT}/scripts")
import slide_helpers as sh
import style as st

ROOT = Path(__file__).resolve().parents[2]  # the project folder
STYLE = st.load_style("peers", "light", project_dir=ROOT)  # your profile and theme
prs = sh.new_presentation(STYLE)
```

Call the helpers with these signatures. Pass `prs` and `STYLE` as the first two arguments of each call. A call with text that does not fit raises `ValueError` and names the cause. Shorten your own text with `Edit`. A sentence of the user stays as written. Run the script again.

```python
sh.new_presentation(style)
sh.add_title_slide(prs, style, title, author="", affiliation="", date="", notes=None)
sh.add_roadmap_slide(prs, style, message, sections, notes=None)
sh.add_assertion_evidence_slide(prs, style, headline, evidence, callouts=(), source="", notes=None, backup=False)
sh.add_big_number_slide(prs, style, headline, number, label, baseline, source="", notes=None)
sh.add_take_home_slide(prs, style, claims, notes=None, headline=None)
```

The `sections` argument is a list of 3 to 5 pairs of a name and a line. The `claims` argument is a list of 1 to 3 pairs of a claim and a baseline. The `callouts` argument is a list of at most two strings. The `evidence` argument is one of these dicts.

```python
{"kind": "picture", "path": ROOT / "figures/fig1.png", "alt": "A sentence that states what the figure shows."}
{"kind": "table", "rows": [["Setting", "Value"], ["A", "1"]], "highlight": (1, 0)}
{"kind": "chart", "chart": "bar", "categories": ["A", "B"], "series": {"Name": [1, 2]}, "highlight": "B", "alt": "A sentence."}
{"kind": "chart", "chart": "line", "categories": ["A", "B"], "series": {"Name": [1, 2], "Other": [2, 3]}, "highlight": "Name", "alt": "A sentence."}
```

Follow these rules in the script.

- Give `alt` to each picture and each chart. Write it as one sentence that states what the figure shows.
- Give `add_take_home_slide` a sentence as `headline`. The default title of that helper is a fallback only. Draft that sentence from the claims. It has 6 to 20 words and a verb. For example, "Three results support the message of this talk."
- Add `source` to each slide that has a `source` parameter and shows a number.
- The title slide shows no number from the data. The roadmap slide and the take-home slide show only numbers that another slide sources with its own source line.
- Add `notes` to each slide, unless `--no-notes` is set. Write what the slide does not say, such as the spoken explanation, the caveat and the source of a number. Do not repeat the words of the slide. The linter warns when more than 80 percent of the words of a slide appear in its notes.
- Mark the cue of a chart or a table with `highlight`. A chart with one series takes a category name or index as `highlight`. A chart with several series takes a series name. For a picture, name the cue in a call-out.
- The roadmap message fits two lines at 28 pt, about 104 characters. If the helper rejects the message of the user, ask the user for a shorter sentence with `AskUserQuestion`. Never shorten it yourself.
- Keep a call-out to about 35 characters for `peers` and `lab-meeting` and to about 25 characters for `general`. Shorten a call-out that raises `ValueError`.
- Add the backup slides last, with `backup=True`.
- Set `prs.core_properties.title` to the title of the talk. Set `author` and `last_modified_by` on `prs.core_properties` to the author.
- End with `prs.save`, and write the path of the deck.

The file `${CLAUDE_PLUGIN_ROOT}/examples/generate_sample_deck.py` shows a complete builder script. Run your script from the project folder.

```bash
python3 docs/slides/build-<project>-<date>.py
```

## Step 6: Lint and review

Run the linter on the deck. Use the profile and the minutes of Steps 0 and 2. Add `--no-notes` when notes are off.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/design_lint.py" docs/slides/<project>-<date>.pptx --profile <profile> --minutes <minutes> --theme <theme> --project-dir .
```

Each finding prints as `slide N: rule: severity: tier: message`. The exit code is 0 for no errors, 1 for at least one error, and 2 when the linter could not run. For code 2, report the message and stop. A deck with code 2 is not checked.

Fix every error in the builder script with `Edit`. Build the deck again. Run the linter again. Stop after two rounds of repair. Report the errors that remain.

Show the warnings with their rules and tiers. Ask with `AskUserQuestion` whether to fix them. If the user says yes, fix the warnings in the builder script with `Edit`. Run the script again. Run the linter again.

Then review what the linter cannot judge. `Read` each figure file and judge each slide on three points.

1. Does the figure show what the headline claims?
2. Does the slide pass a glance of three seconds, with one idea and one focal element?
3. Does a raster figure use color as the only code?

Note each concern in one line for its slide. Label each line "model judgment".

## Step 7: Report

Report these items in this order.

1. The ghost deck: the headlines in order, one for each line. Say that you drafted the take-home headline.
2. The lint summary: the counts of errors and warnings, and each warning that remains, with its rule and its tier. A warning can concern a sentence of the user. Say that the warning stays because the sentence is theirs and that they can shorten it.
3. The tier legend, as in the table below this list.
4. Your review of the three points of Step 6. Say that the linter does not check them.
5. The paths of the deck and of the builder script.

| Tier | Meaning |
|---|---|
| T1 | A standard or a study backs the threshold. |
| T2 | A named source states the number and cites no evidence. |
| T3 | Folklore, a number that the author derived, or no source. |

Then say three things. The notes are drafts for the author to rewrite in their own voice. The deck names the font Avenir Light, and a computer without that font shows another one. The checks measure compliance with design rules and do not measure audience understanding.
