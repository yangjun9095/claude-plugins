---
name: figure-main-style
description: Use when assembling finished panels into a main figure for a paper, when a composed figure has mismatched panel letters, uneven gaps between panels, too many type sizes or footnotes printed inside it, or when an author wants a main figure in the style of the scientists the science-style lab profiled (Royer, Garcia, Shendure).
---

# Figure main style

A main figure is one page that the reader takes in as a whole. This skill composes that page from finished panels. It holds the page to the taste measured in 7 exemplar figures from the Royer, Garcia and Shendure labs (`references/measured-taste.md`) and to the author's own rulings, which win.

`<skill>` below is `${CLAUDE_PLUGIN_ROOT}/skills/figure-main-style`. Run the Python tools with an interpreter that has PyMuPDF and numpy.

## What you deliver

Every run writes these files to one output folder:

| File | Content |
|---|---|
| `Figure.pdf`, `Figure.png` | the composed figure: vector, every panel at 100% |
| `layout.json` | the layout the composer read |
| `legend.md` | the legend draft: every sentence, method detail, caveat, definition and long title taken out of the panels, verbatim, under its panel letter |
| `check.txt` | the checker's output on the final PDF |
| `review.json` | the referee's verdict on the final PNG |
| `NOTES.md` | the rulings used, each remaining WARN with its reason, each referee finding you did not act on with the reason, and the changes the panel scripts need |

## Steps

1. **Inventory the panels.** Run `check_main_figure.py <panel.pdf> --panel` on each panel. Note its size, type sizes, any letter drawn inside it, hues, and every line that X1, X2 or X3 flags.
2. **Make the figure-level decisions once, for all panels.** One type ladder of 2 to 4 sizes. One letter face, size and case. A label of 1 to 3 words that names what the whole panel shows, or no label. One meaning per hue across all panels. The list of text that moves to the legend: X1 and X3 lines, footnotes, methods, caveats, definitions.
3. **Ask the author the open questions in one message.** Take them from "Where the exemplars disagree" in `references/measured-taste.md`, and add each conflict from step 2. If the author cannot answer, rule, and write each ruling in NOTES.md.
4. **Apply the decisions where the panel is made.** Copy each string you take out into `legend.md`, verbatim.
   - With the panel scripts: change the scripts and re-render. Keep the scripts' own checks passing.
   - With PDFs only: list the text to remove in the layout (`remove_text`, `remove_letter`); the composer redacts it and keeps the vector art. It refuses rotated text and stops when a redaction would damage other text; change such text in the script. Crop freed space with `clip_mm`. To move a sub-block, such as a key, build a prepared copy of the page from two clipped parts of the original (PyMuPDF `show_pdf_page`, which keeps both vector), and compose the copy. To change a hue, rewrite the colour operators on a copy, and list the colour of every drawing and span before and after. Write the script changes in NOTES.md, so that the next panel build does not undo them.
5. **Compose.** Write `layout.json` and run `compose_figure.py layout.json`. Keep panels at 100%, because a scaled panel scales its type. Make the gap between panels wider than the widest white inside any panel (checker S2 measures each panel in both directions, and WARNs when a gutter inside a panel is wider than the gap between panels). The exemplars use 2.5 to 3.9 mm between rows and 4.2 to 8.1 mm between columns; set them with `row_gap_mm` and `col_gap_mm`. When a panel holds wide white inside, first move its sub-blocks closer, then widen the gap.
6. **Check.** Run `check_main_figure.py Figure.pdf --slot-mm <W> --max-height-mm <H>`, with the letter options that your rulings need. Fix every FAIL. Keep a WARN only with a reason in NOTES.md.
7. **Review with a second model.** Look at the PNG at print width yourself first. Then run `bash <skill>/scripts/review_figure.sh Figure.png brief.txt <W>`, where `brief.txt` says what each panel must show. Sort each finding:
   - Layout of the page or of a panel's annotations (gaps, margins, where labels, keys, p values and ticks sit, text that belongs in the legend): fix it.
   - Data encoding (axis scales and limits, what is plotted, mark types): record it in NOTES.md for the author.
   Question why the referee thinks so (`${CLAUDE_PLUGIN_ROOT}/references/review-loop.md`). Repeat steps 5 to 7 until the findings stop being real, at most 3 rounds of fixes. The last review must read the final PNG; after any later change, review again before you write `review.json`.

## When you are tempted to stop early

| Thought | Do this instead |
|---|---|
| "The panels are finished; the fixes belong in the scripts." | Letters, the type ladder, hue meanings and the text budget are figure-level decisions, so they are this skill's job. Change the scripts, or edit a copy and list the script changes. A list for the author alone fixes nothing. |
| "Earlier review rounds of this panel settled that." | Those rounds judged the panel alone. If the fix moves annotations and keeps the encoding, make it. |
| "This caveat is an honesty commitment, so it stays in the figure." | The legend carries it verbatim. Move it. |
| "The gap looks right." | Measure it. Checker S2 must pass. |
| "Nature requires X." | Quote the journal's current guide, or call it a house setting. Never quote a journal rule from memory. |
| "I reviewed the render myself." | Run the referee. It sees what the composer stopped seeing. |
| "No bold cut is installed, so I add a stroke." | Search the font folders and collections for a real face the author accepts. A stroke is a fake weight. |
| "The figure is short for the page, so I add air." | Leave the figure short, or enlarge a panel. Never pad the gaps. |

## Tools

- `scripts/compose_figure.py`: places the panels from `layout.json`, sets the letters and labels, and redacts listed text. `--help` lists the layout keys.
- `scripts/check_main_figure.py`: measures geometry, type, letters, spacing, colour, frames and text volume against the exemplar ranges. It exits 1 on any FAIL.
- `scripts/review_figure.sh`: the Codex referee for a whole figure. It does not know the measured taste, so it judges as a referee would.
