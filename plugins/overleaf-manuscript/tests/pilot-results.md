# Pilot audit results

Run on 2026-10-16 with `audit.py` from this plugin. Sample: seed 20261015, two files per repository plus the largest and smallest.

The first run exposed two recall defects (`fig-ref` and the Oxford `-ise` list). I fixed both and reran the same sample with the same options. The tables below hold the rerun. The first run's hit counts sit in "Before the fix".

After the final review I fixed the paragraph-initial rule for prose directly under a heading. I reran the same 15 files with the same options. The count for each rule is unchanged (74 hits), so the labels and the precision figures below still hold. The 15 files hold no paragraph that starts with Furthermore, Moreover or Additionally, so this rerun cannot show the effect of the heading fix. The unit tests show it.

The manuscripts are unpublished and this repository is public. This file holds rule names, counts and labels. It names no repository, folder or file, and it quotes no manuscript text and no manuscript number. Manuscripts A, B and C are three copies of one project. Manuscript D is a different project.

## Sample

| Manuscript | Files audited | Spelling mode | Hits |
|---|---|---|---|
| A | 4 | oxford | 16 |
| B | 4 | oxford | 12 |
| C | 4 | oxford | 28 |
| D | 3 | off | 18 |

The sample holds 15 files and 74 hits. The seed picked 3 files for manuscript D, because one random pick was also the largest or the smallest.

## How I labelled

I read each hit in its paragraph. TP means the hit is a real instance of the problem the rule names, even if the author may accept it. FP means the rule misfired. Precision is TP divided by hits. One reader made every label. The author may relabel.

I read all 9 hits that the fix added (7 `spelling:-ise form`, 2 `fig-ref`) in their paragraphs. All 9 are TP.

## Results

| Rule | Hits | TP | FP | Precision | Note |
|---|---|---|---|---|---|
| `emdash:paragraph` | 4 | 4 | 0 | 1.00 | too few to judge |
| `fig-ref` | 2 | 2 | 0 | 1.00 | too few to judge |
| `spelling:-ise form` | 15 | 15 | 0 | 1.00 | |
| `spelling:-or/-er form` | 2 | 2 | 0 | 1.00 | too few to judge |
| `todo-cite` | 33 | 33 | 0 | 1.00 | inventory rule, never fails the run |
| `vocab:comprehensive` | 6 | 6 | 0 | 1.00 | |
| `vocab:facilitate` | 1 | 1 | 0 | 1.00 | too few to judge |
| `vocab:landscape` | 5 | 3 | 2 | 0.60 | |
| `vocab:leverage` | 2 | 2 | 0 | 1.00 | too few to judge |
| `vocab:navigate` | 1 | 1 | 0 | 1.00 | too few to judge |
| `vocab:robust` | 3 | 2 | 1 | 0.67 | too few to judge |

Per family, using the audit's own count lines:

| Family | Hits | TP | FP | Precision |
|---|---|---|---|---|
| `vocab` | 18 | 15 | 3 | 0.83 |
| `spelling` | 17 | 17 | 0 | 1.00 |
| `emdash` | 4 | 4 | 0 | 1.00 |
| `fig-ref` | 2 | 2 | 0 | 1.00 |
| `todo-cite` | 33 | 33 | 0 | 1.00 |
| All rules except `todo-cite` | 41 | 38 | 3 | 0.93 |

`todo-cite` is an inventory of placeholders, so it stays out of the last row.

Manuscripts A, B and C share text, so their hits are not independent samples. One `vocab:landscape` sentence and one `emdash:paragraph` paragraph appear in two manuscripts. Seven `todo-cite` marker occurrences appear in two or more manuscripts. They hold 6 distinct texts.

## Before the fix

Hit counts of the first run, which used the earlier `FIG_REF` pattern and `-ise` list. Only two rules changed.

| Rule | Hits before | Hits after |
|---|---|---|
| `fig-ref` | 0 | 2 |
| `spelling:-ise form` | 8 | 15 |
| every other rule | unchanged | unchanged |

The first run held 65 hits. The rerun holds 74.

## Recall change for the two fixed rules

I compared the audit with a separate scan. The scan strips `%` comments and `comment` blocks, then classifies matches of loose patterns by hand. It prints counts only here.

| Rule | Occurrences found by the independent scan | Flagged before the fix | Flagged after the fix |
|---|---|---|---|
| `fig-ref` (untied `Fig.` followed by a reference command; 15 files) | 2 | 0 | 2 |
| `spelling:-ise form` (British `-ise` forms; the 12 files run with `--spelling oxford`) | 18 | 8 | 15 |

The `fig-ref` scan found 2 untied references. Both have no space between `Fig.` and the command, and both sit in one file of manuscript D. The scan found no untied reference with a space.

Before the fix the audit missed 10 of the 18 `-ise` forms, so it missed more than half. After the fix it misses 3. Those 3 hold 2 stems that are not in the list. I did not add them, because the fix names its stems.

Two checks for new false alarms. First, the 12 files held 9 occurrences of ordinary words that end like an `-ise` form. The new pattern flagged none. Second, I ran the new pattern with `--spelling oxford` on every `.tex` file at the root and in `sections/` of all four folders, sampled or not. It matched 9 distinct words, and all 9 are British `-ise` forms.

## Decision

No rule has 5 or more hits and a precision below 0.5. Among rules with 5 or more hits, `spelling:-ise form` is at 1.00 and `vocab:landscape` is at 0.60, the lowest. The decision rule asked for no change. I made the two changes below for recall, after review.

- `audit.py`: `FIG_REF` now matches zero or more whitespace characters after `Fig.` or `Figs.`, so `Fig.\ref` with no tie is flagged. The tied form `Fig.~\ref` still passes.
- `audit_terms.json`: the `-ise form` pattern gained the suffixes `er` and `ers`, 16 stems and the verb forms of `synthesise`. The `oxford` and `american` copies stay identical.

The `-ise` list mirrors `manuscript-write` section 3 (decision X6). The author should apply the same extension there. The tests for both changes are in class `PilotGaps` of `tests/test_audit.py`.

## The false alarms

- `vocab:landscape`, 2 FP. Both hits are one sentence, copied into two manuscripts. It uses landscape as an optimization term of art for a search space. The 3 TP hits use the word as a figure of speech in manuscript D.
- `vocab:robust`, 1 FP. The hit is the noun form, used for a measured property with a stated scope. The 2 TP hits use the adjective with no stated scope. This label is borderline.

The 0.60 for `vocab:landscape` rests on 3 of 5 labels. If the author counts the optimization sentence as a TP, precision is 1.00. If the author counts the three figurative uses as acceptable, none of the 5 hits is a problem in the author's view, and precision falls to 0 of 5. The 5 hits are 4 distinct sentences, because one sentence appears in two manuscripts. By raw count that meets the decision rule's threshold (5 or more hits and precision below 0.5), and by distinct sentences it is below the threshold. The rule needs a narrower pattern only if the author's view changes.

## Reconciliation with an independent search

I searched the same 15 files with my own patterns and compared the counts with the audit.

- The independent search found no paragraph that starts with Furthermore, Moreover or Additionally. The audit reported none.
- It found two uses of "not only" and no "but also" within range. The audit reported no `not only ... but also` row.
- It found no "worth noting", "important to note" or "key role". The audit reported none.
- It found 2 untied figure references. The first audit run reported 0 and the rerun reports 2.
- No file exceeded its em-dash allowance by my count. The audit reported no `emdash:density` row.

## Not reached

Files not sampled:

- Manuscript A: 3 files. Manuscript B: 3 files. Manuscript C: 2 files. Manuscript D: 9 files.
- The sample skips `main.tex` and four other files that hold no manuscript prose, by design. It also skips `.sty` and `.bib` files and any file outside `sections/` and the folder root.

Rules not measured:

- Rules with zero hits: the three constructions, `construction:paragraph-initial`, `emdash:density`, 23 of the 29 vocabulary terms, and `spelling:organizm`. The independent search agrees with the zeros for the constructions and the density rule. The pilot never saw these rules fire on real text. The fixtures in `tests/fixtures` show that they fire.
- `--spelling american` was never run on the sample. Manuscript D ran with `--spelling off`, so its spelling is untested.
- Seven of the 11 rule rows have fewer than 5 hits, so their precision figures are weak. `vocab:landscape` has 5 hits but only 4 independent ones, and `todo-cite` has 33 hits but fewer distinct markers.

Recall gaps recorded before the pilot, still open:

- A heading directly before prose hides the paragraph-initial rule.
- `\\%`, an inline `\begin{comment}` and a few citation-like commands are not handled.

Gaps the pilot found, still open. I confirmed each with made-up probe text.

- A full-line `%` comment inside a paragraph splits that paragraph for `emdash:paragraph` and `construction:paragraph-initial`. LaTeX does not split it. One `emdash:paragraph` row in the sample counted fewer dashes than the paragraph holds. A sentence that opens with Furthermore after a comment line inside a paragraph would raise a false `construction:paragraph-initial` row. The sample held no such case.
- The Oxford `-ise` list still misses 3 of the 18 `-ise` forms in the sample. Their stems are not in the list.
