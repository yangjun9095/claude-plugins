# Measured taste of main figures

This file records how the main figures of the scientists that the science-style lab profiled are composed. It is the evidence behind `check_main_figure.py` and behind the questions the skill asks the author.

## Where the numbers come from

On 2026-11-03 a script measured Figures 1 and 2 of 11 open-access papers from 6 labs with PyMuPDF: 20 main figures in all, because 2 papers yielded only Figure 1. Four vision readers described the same 20 figures. Seven figures from 4 papers and 3 labs were clean enough for statistics; the other 13 failed one or more tests (see Limits):

| Lab | Paper | Figures |
|---|---|---|
| Royer | DaXi, Nature Methods 2022, doi:10.1038/s41592-022-01417-2 | 1, 2 |
| Royer | Self-supervised protein localization, Nature Methods 2022, doi:10.1038/s41592-022-01541-z | 1 |
| Garcia | eLife 73395 (2022), doi:10.7554/eLife.73395 | 1, 2 |
| Shendure | PRDM9 evolution, Nature Communications 2014, doi:10.1038/ncomms5370 | 1, 2 |

Royer holds 3 of the 7, so his figures weigh most. The sample is small. Treat each range as the span of 7 figures, not as a population value.

## Ranges (min, median, max over 7 figures)

| Measure | Min | Median | Max | Checker |
|---|---|---|---|---|
| Width of the figure (mm) | 139.4 | 154.5 | 180.1 | G1 |
| Fill of the slot the journal gave | 0.78 | 0.86 | 1.01 | G1 |
| Aspect, width / height | 1.30 | 2.39 | 4.63 | G3 |
| Ink share of the box | 0.13 | 0.20 | 0.51 | G4 |
| Panel letter (pt) | 6 | 8 | 8 | L4 |
| Smallest label (pt) | 3.0 | 4.5 | 6.0 | T2 |
| Distinct type sizes | 2 | 3 | 4 | T1 |
| Any blank row run of 1.2 mm or more (mm, n = 3) | 1.65 | 3.56 | 3.94 | none |
| Any blank column run of 1.2 mm or more (mm, n = 10) | 1.78 | 4.32 | 8.26 | none |
| Median stroke (pt) | 0.235 | 0.311 | 0.842 | K1 (reported, not judged) |
| Caption characters | 294 | 985 | 2216 | none |

The journals re-set the type, so the type sizes are the journals' and the positions are the authors'.

## Calibration of the checker on the same 7 figures

`check_main_figure.py` ran on each exemplar, boxed by the figure-finding script (2026-11-03). Its own method gave these ranges, and the checker uses them:

| Measure | Range over 7 figures | Checker |
|---|---|---|
| Largest empty rectangle, share of the box | 0.031 to 0.225 (median 0.084) | G5 |
| Distinct type sizes, by the checker's count | 2 to 5 (6 of 7 at 4 or fewer) | T1 |
| Gap between panels, rows (n = 4) | 2.5 to 3.9 mm | S1, rows |
| Gap between panels, columns (n = 4) | 4.2 to 8.1 mm | S1, columns |
| Coloured share of pixels | 0.03 to 0.12 (median 0.06) | C1 |
| Hue peaks | 1 to 5 | C2 |
| Words in the figure | 15 to 102 (median 56) | X2 |
| Words in one panel (5 lettered figures) | 1 to 41 | X2 |
| Lines of 6 or more words | 0 in every figure | X1 |
| Longest panel title | 1 to 2 words | X3 |

The last two rows support the rule that text goes to the legend: no exemplar prints a sentence inside a panel.

## Rules the exemplars agree on

1. The outer box is fixed and the inner splits are free. Each row is divided for what it holds, so the gutters of one row do not line up with the next. Do not snap panels to a column grid. In Garcia's Figure 1 a header is a "narrower header, roughly centred", not a header locked to the column grid.
2. Spacing has three levels: about 0.2 mm between tiles of one montage, 0.7 to 2 mm between sub-blocks of one panel, and a wider gap between panels. The vision readers put the gap between panels at 4 to 9 mm; the measurement gives 2.5 to 3.9 mm between rows and 4.2 to 8.1 mm between columns. The order of the levels is the rule: the white between panels must be wider than any white inside a panel. A sparse panel with wide white inside it forces a wider gap than the exemplars use.
3. Panel letters are bold sans, about 2 mm cap height, and lowercase except where the journal sets capitals (eLife, in both Garcia figures). Each letter stands left of every other mark of its panel, and the letters of one row share one baseline.
4. Nothing is boxed. Whitespace or a flat tint groups panels. The frames in the eLife figures are a journal convention; do not copy them.
5. A legend draws the real mark, has no frame, and sits in the panel that first uses its vocabulary.
6. The headline number is printed inside the panel, so a reader can state it without the caption.
7. Colour is rationed, and one hue leads. The vision readers put it at 5 to 16 per cent of pixels and 2 to 4 hues that carry meaning; the checker's own count gives 3 to 12 per cent and 1 to 5 hue peaks, and the checker uses those.
8. The aspect follows the panel count: few panels give a wide figure.

## Where the exemplars disagree: ask the author once

Do not average these. Ask the author in one message before you compose, and record the answer as a ruling. The evidence here comes from the vision reads of all 20 figures, so it also names labs outside the 7 measured figures (Pinello, Zou, Rives) and Royer's CARE figures.

| Question | What the exemplars do |
|---|---|
| Where does the panel letter go? | Outside left of all ink (Royer, Pinello, Garcia Figure 2), or inside a tinted title bar (Garcia Figure 1). |
| Panel titles: none, a short label, or a sentence? | Royer's CARE figures set a short label on the letter's line ("b Network architecture"); DaXi centres a coloured title over two panels; other Royer figures use none. |
| How dense? | Gutters vary about threefold between two figures of one author (Rives: 2.4 to 5.2 mm against 0.85 to 1.9 mm). |
| Despine the plots? | Royer's lab uses three conventions in one group of papers. |
| Does one hue keep one meaning across panels? | Kept in Pinello's Genome Biology figures and by Garcia across a paper; broken in Zou's Nature Communications Figure 1, which uses red for four unrelated things. |
| Reading order strictly a, b, c? | DaXi Figure 1 runs a, b c d h, e f g; most figures run left to right, top to bottom. |

## Refusals

- Do not snap panels to a column grid (rule 1).
- Do not add air between panels to fill a page. Enlarge a panel or let the figure be shorter.

## Author rulings override

An author's ruling overrides a rule above. Example: an author may set the letters in a light face at 6 to 8 pt; then run the checker with `--letter-weight regular` or `any`, and say so in NOTES.md.

## Text inside the figure

The exemplars print labels, keys and the headline number inside the panels. Method details, caveats, sample sizes, seeds and sentences sit in the legend. Garcia's and Shendure's figures carry no legend box at all; they name each mark once, at its first appearance. The checker counts words (X2) and flags long lines (X1) and long titles (X3). Its ceilings come from the calibration above.

## Limits

- 7 figures from 3 labs. Trapnell is absent (closed access). Two Royer preprints (Ultrack, inTRACKtive) could not be fetched.
- 13 of the 20 figures are out of the ranges, some for more than one reason: 6 were flattened rasters, 4 renders were clipped, 2 boxes ran past the page, 1 caption box failed, and the letter detector over-counted letters in 1 figure.
- Journals re-set the type, so the type ranges describe the journals as much as the authors.
