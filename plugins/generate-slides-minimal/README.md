# generate-slides-minimal

This plugin builds a `.pptx` slide deck from the artifacts of a project. It starts from the message of the talk. Each slide has a sentence headline over one visual. The plugin drafts speaker notes by default. A design linter checks the finished deck and labels each rule with its evidence tier.

This is version 0.1.0. The plugin has one command, `/generate-slides-minimal`.

## Install

```bash
/plugin marketplace add yangjun9095/claude-plugins
/plugin install generate-slides-minimal@yangjun9095-plugins
```

The plugin needs these parts.

- Python 3 with `python-pptx`, `PyYAML` and Pillow. The command installs each of them when it is missing. If pip says `externally-managed-environment`, create a virtual environment. Install the three packages in it. Start Claude Code from a shell where that environment is active.
- The font Avenir Light on the computer that opens the deck. See the section "Fonts".
- Optional: LibreOffice (`soffice`) and `pdftotext`. The render check needs both.

## Usage

```
/generate-slides-minimal                                   # asks for the minutes and the profile
/generate-slides-minimal 15min                             # a talk of 15 minutes
/generate-slides-minimal 12 slides --profile lab-meeting   # 12 main slides
/generate-slides-minimal 20min --theme dark --no-notes     # dark theme, no speaker notes
```

| Argument | Meaning |
|---|---|
| `15min` or `N slides` | The length of the talk in minutes, or the number of main slides. The command asks when you give neither. |
| `--profile` | The audience: `peers` (default), `lab-meeting` or `general`. |
| `--theme` | The look: `light` (default) or `dark`. |
| `--no-notes` | Draft no speaker notes. The linter then runs with `--no-notes` too. |

The command works in eight steps.

0. Preflight: it installs missing libraries and reads `slide-style-minimal.yaml`.
1. Catalog: it lists the figures, notebooks and documents of the project.
2. Message first: it asks for one sentence that the audience must keep, at most three take-homes, the minutes, the profile and the title-slide fields.
3. Outline: it drafts a story with the spine need, approach, evidence and take-homes. You approve it after the ghost-deck test, where the headlines alone tell the story.
4. Preview: it builds two or three slides for your review.
5. Generate: it writes a Python script, runs it and saves the deck.
6. Lint: it runs the linter and repairs each error, at most twice. It asks whether to fix the warnings. It then reviews what the linter cannot judge.
7. Report: it shows the ghost deck, the lint summary and the tier legend.

The command writes the builder script to `docs/slides/build-<project>-<date>.py` and the deck to `docs/slides/<project>-<date>.pptx`.

Three rules hold in every step. The command never paraphrases your own words. Each number comes from an artifact and carries a source line. The speaker notes are drafts, and you rewrite them in your own voice.

## The look

The look is sharp.

- All text uses Avenir Light, with PT Mono for code. No text is bold.
- The light theme has a white background and near-black text (`#111111`).
- One accent carries every mark and every accent word. It is a deep violet, `#6D4BD6`.
- Text boxes have no fill. Call-outs are plain text with a thin accent rule at the left.
- Titles are 28 pt, left aligned and anchored at the top of the slide. There is no line under the title.
- A chart uses grey for context and the accent for the key datum. A table highlights a row with accent text.
- The dark theme (`--theme dark`) uses the background `#14111F`, light text and the accent `#9D7BFF`. It is opt-in.

## Profiles

A profile sets the numbers of the linter and the sizes that the helpers use. The research notes disagree on text density, so the profile sets the word budget. No source tests the mapping from audience to profile. It is a judgment.

| Profile | Audience | Words per slide (warn, error) | Body text warns below | Slides per minute | Objects per slide |
|---|---|---|---|---|---|
| `peers` | Colleagues who inspect evidence | 25, 40 | 24 pt, 20 pt for secondary text | 1 | 6 |
| `lab-meeting` | A group that gives feedback | 40, 60 | 18 pt | 1.5 | 6 |
| `general` | An audience outside the field | 15, 25 | 28 pt, 24 pt for secondary text | 1 | 4 |

## The linter

Run the linter on any `.pptx` deck.

```bash
python3 scripts/design_lint.py DECK.pptx --profile peers --minutes 12
```

| Option | Meaning |
|---|---|
| `--profile` | `peers` (default), `lab-meeting` or `general`. |
| `--minutes N` | The length of the talk, for the slide-count rule. Without it the linter prints `deck: slide-count: warn: T2: no --minutes given; rule skipped` and counts one warning. |
| `--theme` | `light` (default) or `dark`. It loads the theme file and has no effect on the findings. |
| `--no-notes` | Switch the notes rules off. |
| `--render` | Also run the render check. |
| `--project-dir DIR` | The folder that holds `slide-style-minimal.yaml`. Without it the linter reads no project file. |

The linter reads a title only from the title placeholder or a shape named `Title`, and v1 decks and many hand-made decks use text boxes. Such a deck gets a `title-empty` error on every slide. It can also get a `margin` warning for its first text box.

Each finding prints as `slide N: rule: severity: tier: message`. A finding about the whole deck starts with `deck:`. Two lines follow: `errors: E` and `warnings: W`.

Exit codes: `0` means no errors, `1` means at least one error, and `2` means the check could not run. A finding with the severity `error` sets the exit code to 1. All other findings are warnings.

Each finding carries the evidence tier of its threshold.

| Tier | Meaning |
|---|---|
| T1 | A standard or a study backs the threshold. |
| T2 | A named source states the number and cites no evidence. |
| T3 | Folklore, a number that the author derived, or no source. |

The linter never guesses. It skips a rule for a value that it cannot resolve, such as text on a picture or a size that a deck inherits. It groups the skipped checks of a slide by rule and reason, and it writes one warning for each group. A main slide is any slide except the title slide and the backup slides.

| Rule | What it checks | Severity | Tier |
|---|---|---|---|
| `title-sentence` | A title has 6 to 20 words, a verb, and is not a topic label. | warn | T3 |
| `title-unique` | No two slides share a title. | warn | T2 |
| `words-per-slide` | Words on a slide, without the title, the source line and figure text. | warn, error | T3 |
| `take-home-words` | A claim and a baseline each hold at most 15 words. | warn | T3 |
| `bullets` | At most 4 bullets in a list and 1 list on a slide. | warn | T2 |
| `objects` | At most 6 objects on a slide for `peers`. | warn | T2 |
| `lines-per-paragraph` | At most 2 lines in a paragraph. The count is an estimate. | warn | T2 |
| `body-font` | Body text of at least 18 pt. The profile sets the warning size. The source line needs 12 pt, at tier T3. | warn, error | T2 |
| `title-font` | A title of at least 28 pt. | warn | T2 |
| `fonts-per-slide` | At most 2 font families and 3 sizes. | warn | T2 |
| `text-contrast` | Contrast below 3:1 is an error. Contrast below 4.5:1 warns, or below 3:1 for text of 18 pt or more. | warn, error | T1 |
| `mark-contrast` | Chart marks and shapes that carry data reach 3:1. Marks with data labels are exempt. | warn | T1 |
| `red-green` | No red and green pair with a luminance ratio below 3:1. | warn | T2 |
| `inside-slide` | No shape extends beyond the edge of the slide. | error | T3 |
| `margin` | A shape keeps 0.5 in from the edge. | warn | T3 |
| `aspect` | The slide is 16:9. | error | T2 |
| `picture-ppi` | A picture shows at 144 ppi or more. | warn | T3 |
| `alt-text` | Each picture and chart has alt text that is not a file name. | warn | T2 |
| `slide-count` | Main slides do not exceed the minutes times the pace of the profile. | warn | T2 |
| `take-homes` | At most 3 claims on the take-home slide and 5 sections on the roadmap. | warn | T2 |
| `notes` | Each main slide has notes. A warning follows when over 80 percent of the slide words appear in them. | warn | T3 |

Four more rows exist.

| Rule | What it checks | Severity | Tier |
|---|---|---|---|
| `title-empty` | Each slide has title text. | error | T2 |
| `slide-count` | The deck has at least one slide that is shown. | error | T2 |
| `unreadable-shape` | python-pptx can read each shape. | warn | T3 |
| `style-key` | A project file holds no lint key that no rule reads. | warn | T3 |

The linter does not judge five things. These are whether a figure supports its headline, the glance test, color as the only code in a raster figure, text inside images, and whitespace. The command asks the model to review the first three.

## The render check

The option `--render` converts a copy of the deck to a PDF with LibreOffice. It reads the word heights with `pdftotext -bbox`. It needs `soffice` and `pdftotext` on the `PATH`. Without them, the output ends with one line: `render check skipped: soffice or pdftotext not found`.

| Rule | What it checks | Tier |
|---|---|---|
| `render-font` | A word renders below the source-line floor of 12 pt. | T2 |
| `render-missing-text` | A word of the deck is missing from its page, for example clipped text. | T3 |
| `render-check` | The check failed. | T3 |

The command does not run the render check. Run it yourself when you want the extra test.

## The style file

Put `slide-style-minimal.yaml` in the project folder, in `docs` or in `.claude`. The loader merges the default, the theme, the profile and the project file in that order. A later layer wins. Dicts merge deeply. The top-level keys are `typography`, `colors`, `layout`, `style` and `lint`.

```yaml
colors:
  accent: "#0B6E4F"
  accent_ink: "#0B6E4F"
lint:
  words_per_slide: {warn: 30, error: 45}
```

The linter reads the project file only with `--project-dir`. The command passes `--project-dir .` for you. A project file can change the number or the tier of any rule. The linter warns about a lint key that no rule reads. Such a key is often a typo.

## Fonts

The deck names Avenir Light and does not embed it. Install Avenir Light on the computer that opens the deck. Without it, PowerPoint and LibreOffice show another font, and the layout can shift. You can name another font with `typography.body_font` in the style file.

## Limits

- A chart in Calibri at 12 to 16 pt, inside a deck whose other text is Avenir Light, can give a false `render-font` row. Decks from the plugin helpers are not affected, because the chart helper sets the font.
- The render check does not test right-to-left words for presence in the render.
- Bold and italic text is not calibrated in the render check. The check can miss small italic text.
- The check that a title has a verb is a heuristic with known misses. The Limits section of `scripts/title_check.py` lists them.
- The lines-per-paragraph rule is an estimate. It does not use font metrics.
- Avenir Light must be installed for the intended look. Otherwise the render falls back to another font. A substitute font can be wider, so a headline near the two-line limit can wrap to three lines.
- The plugin writes no animations, because python-pptx cannot write them.
- The plugin makes no claim about audience outcomes. No study isolates one element of these slides, and no study tests working scientists.
- The tests and the scenario runs opened the decks in LibreOffice only. Nobody tried PowerPoint.
- The tests ran with python-pptx 0.6.23 on Python 3.6.8 only. On Python 3.8 and later, pip installs python-pptx 1.0.x, and nobody ran the plugin with it.
- A builder script in `docs/slides` holds the absolute path of the plugin. The script stops working after the plugin moves or updates. Run the command again to write a new script.
- A helper rejects text that holds a control character, such as NUL or U+000B, before it makes a slide. A line break that you copy from another deck arrives as U+000B. Write it as a newline.

## Relationship to `generate-slides`

The plugin `generate-slides` (v1) is unchanged and independent. The two plugins share no code at run time. The file `scripts/slide_helpers.py` started as a copy of the helper library of v1, by the same author. The style file here has the name `slide-style-minimal.yaml`, so it never collides with the `slide-style.yaml` of v1. You can install both plugins.

## Research notes

The folder `references/research-notes/` holds four research notes of 2026-10-20. They cover how Jobs built keynotes, what the best-known presenters teach, the evidence for slides in scientific talks, and measurable rules for a linter. The file `references/design-principles.md` distills them into principles. Each principle carries a tier and source keys, and a test checks that each key resolves to a URL.

## Example deck

The script `examples/generate_sample_deck.py` builds `examples/sample-deck.pptx` from made-up data. The deck has eight slides and all six layouts. It lints with no finding under `peers` for 12 minutes.

```bash
python3 examples/generate_sample_deck.py
python3 scripts/design_lint.py examples/sample-deck.pptx --profile peers --minutes 12
```

## Tests

```bash
cd plugins/generate-slides-minimal
python3 -B -m unittest discover -s tests
```

The tests use no network. The tests that render a deck skip themselves when `soffice` or `pdftotext` is missing.

## Licence

MIT.
