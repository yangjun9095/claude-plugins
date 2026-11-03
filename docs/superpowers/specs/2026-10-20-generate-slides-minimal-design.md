# generate-slides-minimal: design

Date: 2026-10-20
Status: the plugin exists in `plugins/generate-slides-minimal`, and this spec describes it.
Sources: four research notes of 2026-10-20 (kept in the plugin as `references/research-notes/`), and the existing plugin `generate-slides` (v1), which stays unchanged.

## 1. Purpose and scope

`generate-slides-minimal` is a new plugin with one command, `/generate-slides-minimal`. It builds a `.pptx` slide deck from the artifacts of a project (figures, notebooks, notes). It differs from v1 in four ways:

1. It starts from the message of the talk, not from the list of figures.
2. It builds the outline as a story with one claim per slide.
3. It checks the finished deck with a design linter whose every rule carries an evidence tier.
4. It drafts speaker notes by default, so the slide text can stay short.

Out of scope:
- Any change to `plugins/generate-slides`. A review check confirms that `git diff main -- plugins/generate-slides` is empty.
- Animations, Keynote and Google Slides output. `python-pptx` cannot write animations.
- Any claim that these slides raise audience understanding. The research shows that no study isolates a single element, and no study tests working scientists.
- Font embedding. The deck names Avenir Light. A machine without that font substitutes another one. The README says so.

## 2. Decisions

| ID | Decision | Source |
|---|---|---|
| D1 | A separate plugin named `generate-slides-minimal`. It shares no code with v1 at run time. | Author, 2026-10-20 |
| D2 | The default audience profile is `peers`. The others are `lab-meeting` and `general`. | Author, 2026-10-20 |
| D3 | The default look is Avenir Light on a white background, with the Biohub purple as the accent. A dark theme is optional. | Author, 2026-10-20 |
| D4 | Speaker-note drafting is on by default. `--no-notes` turns it off. | Author, 2026-10-20 |
| D5 | The four research notes are committed as references. | Author, 2026-10-20 |
| D6 | Every threshold in the profiles is labelled with its evidence tier. Only legibility, contrast, empty-title, off-slide and `aspect` rules block, and so do `words-per-slide` above its error limit and a deck with no visible slide. The rest warn. | Proposed |
| D7 | The project style file is `slide-style-minimal.yaml`, so it never collides with the `slide-style.yaml` of v1. | Proposed |
| D8 | The look is sharp: one saturated accent (the deep brand violet), no tint fills, thin rules, 28 pt titles at the top of the slide with no line under them, and a taller evidence area. | Author, 2026-10-20 (demo review) |

The Biohub purple comes from the author's Biohub Purple palette. A web search found no published brand value, so that palette is the source.

## 3. What the research supports

Counts come from the four research notes. "T1 (transcript)" in the Jobs research note means "seen in a transcript". In the other research notes T1 means a controlled study or a standard.

| Area | Principles | T1 | T2 | T3 |
|---|---|---|---|---|
| How Jobs built talks | 15 | 9 (transcript) | 5 | 1 |
| What the best-known presenters teach | 15 | 2 | 12 | 1 |
| Evidence for scientific slides | 16 | 6 | 9 | 1 |
| Measurable lint rules | 21 | 3 | 14 | 4 |

Findings that shape the design:
- Jobs published no slide rules. A transcript of the 2007 iPhone keynote, the 1998 iMac launch and the 2005 Stanford speech supports the rule of three, problem then solution, a simple labelled chart of the problem, numbers made concrete against a baseline, and a closing anchor line. His words per slide, font size and background are unverified. "No bullets, ever" is Gallo's claim.
- What does not transfer to a data talk: hype, unsourced numbers, and persuasion over information.
- Three or more authors agree on: one message per talk, one idea per slide, slides that support the speaker, removed noise, and detail kept in a separate document.
- Text density is contested: Godin allows 6 words, Alley averages about 21 plus one figure, and Tufte calls 40 words too thin. The audience profile therefore sets the word budget.
- The assertion-evidence slide (a sentence headline over one visual) has the only controlled tests. Their limits: undergraduate subjects, several changes bundled together, an author who co-wrote the studies, and one replication that missed significance.
- Best-supported craft rules: remove decoration, label inside the figure, cue the key datum, and put keywords on the slide while the speaker says the full sentence.
- One result argues against pure minimalism: bullets helped recall of secondary statistics. Numbers the audience must recall exactly stay on the slide.

## 4. Architecture

```
plugins/generate-slides-minimal/
  .claude-plugin/plugin.json
  commands/generate-slides-minimal.md        the command (workflow)
  scripts/
    design_color.py                          hex parsing, WCAG luminance and contrast, red/green test
    style.py                                 loads and merges default, theme, profile and project styles
    styles/default.yaml
    styles/themes/light.yaml, dark.yaml
    styles/profiles/peers.yaml, lab-meeting.yaml, general.yaml
    slide_helpers.py                         builds slides; layouts; notes; alt text
    pptx_resolve.py                          resolves inherited font size, family and color from the XML
    design_lint.py                           the linter (library and command line)
    title_check.py                           the title heuristics of the linter (topic labels, verbs)
    design_chart.py                          chart and fill reading for the linter
    render_check.py                          optional LibreOffice render check
  references/
    design-principles.md                     the distilled principles, with tiers and sources
    research-notes/README.md and four research notes
  examples/generate_sample_deck.py, sample-deck.pptx
  tests/
  README.md
```

`slide_helpers.py` starts from the helper library of v1 (same author, MIT licence). It is a copy, so v1 stays unchanged. The copy sets an explicit font name, size and color on every run, so the linter reads exact values without resolving inheritance for decks that this plugin builds. The resolver exists for decks that other tools built.

Layouts:

| Layout | Content |
|---|---|
| `title` | Title, author, affiliation, date. |
| `assertion_evidence` | A sentence headline, one evidence element (figure, chart or table), at most two call-outs, one source line. |
| `big_number` | A sentence headline, one statistic, a label, its baseline, its source. |
| `roadmap` | The one-sentence message and 3 to 5 sections with one line each. |
| `take_home` | At most three claims, each with its baseline. This slide ends the main deck and stays on screen during questions. |
| `backup` | An `assertion_evidence` slide after the main deck. It does not count toward the pace rule. |

## 5. Look

Defaults (the `light` theme): Avenir Light for all text, PT Mono for code, no bold, a white background, near-black text. The look is "sharp", as the author approved on 2026-10-20 after a demo:
- Titles are 28 pt, left aligned, anchored at the top of the slide (0.3 inch from the edge), with no line under them. The evidence area starts at 1.5 inch and is 5.2 inch tall.
- One saturated accent carries every mark and every accent word. There are no tint fills. Call-outs are plain text with a thin accent rule (0.03 inch) at their left.
- Context marks in charts are grey. The key datum is the accent.
- A table highlights a row with accent-colored text, not a fill.
- Charts have a transparent chart area and plot area, so one chart works on both themes.

The palette is the author's Biohub Purple palette. A computation with the WCAG formula on 2026-10-20:

| Color | Contrast | Use |
|---|---|---|
| `#6D4BD6` (deep brand violet) on white | 5.79 | `accent` and `accent_ink` in the light theme: marks, rules and accent text. Passes 4.5:1. |
| `#9D7BFF` (brand violet) on white | 3.13 | Not used on white. It looked soft beside v1's blue (about 4.8:1). |
| `#CCCCFF` (classic periwinkle) on white | 1.54 | Not used. |
| `#111111` on white | 18.88 | Body text. |
| `#6B7280` on white | 4.83 | Muted text and source lines. |
| `#9CA3AF` on white | 2.54 | Context marks that carry data labels. The mark-contrast rule exempts marks with data labels. |

The `dark` theme uses the background `#14111F` of the Biohub Purple palette with text `#F3F0FA` (16.51:1), muted text `#9A92B3` (6.32:1), the accent `#9D7BFF` (5.94:1), `accent_ink` `#B79BFF` (8.10:1) and context marks `#6E6788` (3.50:1). It is opt-in with `--theme dark`.

The data palette for multi-series charts is the Okabe-Ito set. The hex values come from a secondary source, and the research note `measurable.md` says that the name-to-hex mapping comes from a search snippet. The unit tests check only that the eight colors are distinct and valid.

## 6. The command

Arguments: `/generate-slides-minimal [15min | N slides] [--profile peers|lab-meeting|general] [--theme light|dark] [--no-notes]`.

Steps:
0. Preflight: install `python-pptx`, `PyYAML` and Pillow if missing, read `slide-style-minimal.yaml` from `./`, `docs/` or `.claude/`, and resolve the profile and theme.
1. Catalog the artifacts: figures, notebooks and documents.
2. Message first. Ask for one sentence that the audience must keep, at most three take-homes, the minutes, the profile (default `peers`), and the title-slide fields when no artifact holds them. A call of `AskUserQuestion` holds at most four questions, so the title-slide question can need a second call.
3. Story spine and outline. The spine is need, approach, evidence, take-homes (a three-act form, as Duarte and Atkinson describe). Each slide in the outline has a layout, a sentence headline, one evidence element, one cue (what to highlight in it) and, if notes are on, a script. The ghost-deck test applies: the headlines alone tell the story. The user approves the outline.
4. Preview two or three slides.
5. Generate a Python script, run it, and save the deck.
6. Lint. Run `design_lint.py`. Fix every error and re-run, at most twice. Show the warnings with their tiers, and ask whether to fix them.
7. Report the ghost deck, the lint summary, and the tier legend. Say that the notes are drafts for the author to rewrite in their own voice.

The user's own wording is never paraphrased. Numbers come from the artifacts and carry a source line.

## 7. The linter

Command line: `python3 design_lint.py DECK.pptx --profile peers --minutes N [--theme light|dark] [--render]`. Output: one row per finding, as `slide:rule:severity:tier: message`, then a summary. Exit codes: 0 no findings of severity error, 1 at least one error, 2 usage or read error.

Rules for version 0.1. The tier is the tier of the threshold. "T1/WCAG" means a standard.

| Rule | Peers threshold | Severity | Tier |
|---|---|---|---|
| Title is a sentence | 6 to 20 words, has a verb, not a topic label | warn | T3 |
| Title is not empty and not repeated | non-empty, unique | error (empty), warn (repeat) | T2 |
| Words per slide, excluding title, figure labels and source line (not on `take_home` slides) | warn above 25, error above 40 | warn, error | T3 default, contested |
| Words on a `take_home` slide | each claim and each baseline at most 15 words | warn | T3 |
| Bullets | at most 4 per list, at most 1 list | warn | T2 |
| Objects per slide | at most 6 | warn | T2 |
| Lines per paragraph | at most 2 (estimated) | warn | T2 |
| Body font size | error below 18 pt. Primary text warns below 24 pt. Secondary text (call-outs, table cells, chart text, subtitle, take-home baselines) warns below 20 pt. Source line at least 12 pt | error, warn | T2 (source line: T3) |
| Title font size | at least 28 pt | warn | T2 |
| Fonts per slide | at most 2 families, at most 3 sizes | warn | T2 |
| Text contrast | error below 3:1, warn below 4.5:1 (3:1 for large text) | error, warn | T1/WCAG |
| Mark contrast | at least 3:1 for chart series and shapes that carry data. Marks with data labels are exempt | warn | T1/WCAG |
| Red and green | no red and green pair without a luminance ratio of 3:1 | warn | T2 |
| Inside the slide, margin | 0 EMU outside, margin at least 0.5 in | error, warn | T3 |
| Aspect ratio | 16:9 | error | T2 |
| Picture resolution | effective at least 144 ppi | warn | T3 |
| Alt text | present and not the file name | warn | T2 |
| Slide count | main slides at most the minutes (peers) | warn (error for a deck with no slide or no visible slide) | T2 |
| Take-homes | at most 3 claims on the `take_home` slide; at most 5 sections on `roadmap` | warn | T2 |
| Notes | when notes are on: present on every main slide; warn when more than 80% of a slide's words appear in its notes | warn | T3 |

Profiles change the numbers. `lab-meeting`: words warn above 40 and error above 60, body font warn below 18 for primary and secondary text, at most 1.5 slides per minute. `general`: words warn above 15 and error above 25, primary body font warn below 28 and secondary below 24, at most 4 objects per slide.

What the linter does not judge: whether a figure supports its headline, the glance test, color as the only code in a raster figure, text inside images, whitespace and hierarchy. The command asks the model to review these, and the report says they are not scripted.

`pptx_resolve.py` resolves a size, family or color through run, paragraph list style, shape list style, layout, master and the presentation default. `python-pptx` 0.6.23 returns None for each inherited value, so the resolver reads the XML. It reports "unresolved" instead of guessing, and the linter skips a rule for a value it cannot resolve and says so.

`render_check.py` is optional. It converts the deck to PDF with LibreOffice (`soffice`), reads word heights with `pdftotext -bbox`, and flags rendered text below the font floor and words that vanished from the page (clipped text). It exits cleanly with a message when `soffice` is missing.

## 8. Verification plan

The plan follows `superpowers:writing-skills` and the pilot-then-scale method in the author's global instructions.

- **Unit tests.** Contrast values from the research (white on black 21.00, `#767676` on white 4.54, `#777777` on white 4.48, red on green 1.39). Style merging order. Each layout stays inside the slide and sets explicit fonts. Each lint rule fires on a seeded defect and stays quiet on a clean deck. The resolver returns the sizes that a LibreOffice render shows. The suite runs on Python 3.6.8 with `unittest`.
- **Principles check.** A test requires that every principle in `design-principles.md` carries a tier and a source key that resolves to a URL in the research notes.
- **Command check.** A test parses the front matter, checks that `allowed-tools` covers what the text runs and holds nothing else, and checks that every script and reference the text names exists.
- **Comparison.** Build one synthetic project (generated figures, made-up numbers). Run `/generate-slides` (v1) and `/generate-slides-minimal` three times each on it, with the same scripted answers. Lint all six decks with the `peers` profile. Read the ghost decks. Report the findings per rule. This measures compliance with the rules. It does not measure audience outcomes.
- **Visual check.** Render the sample deck with LibreOffice and read every slide image against the demo that the author approved on 2026-10-20. Check that titles sit at the top, no line sits under them, and no text collides with a shape.
- **Discovery.** In a headless session with the plugin loaded, check that the command appears. The interactive prompts are not testable headlessly. The report says so.
- **Final review.** A whole-branch review on the most capable model, one fix pass, one scoped re-review.

## 9. Risks

- The thresholds are mostly T2 and T3. The tier on every finding says how much weight it deserves. The author can override any threshold in `slide-style-minimal.yaml`.
- The deep violet `#6D4BD6` is darker than the brand violet `#9D7BFF` that the Biohub Purple palette uses on a dark background. The dark theme keeps `#9D7BFF`.
- LibreOffice renders text with a substitute font when Avenir is missing, so rendered sizes can differ slightly from PowerPoint.
- The comparison uses scripted answers, so it tests the command text and the helpers, not a live conversation.

## 10. Open items

- Whether a later version should share one helper library with v1.
