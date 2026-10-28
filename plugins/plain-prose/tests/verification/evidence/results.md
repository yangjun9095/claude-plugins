# Verification record

This record covers the checks that the spec names in section 11: a precision pilot, a rewrite pilot, a discovery check and a blind sample for the author. The pilots ran on 2026-10-23 and 2026-10-24. All text in the fixtures is invented. No manuscript text and no voice sample of the author entered the repository.

## 1. What the checks show and what they do not

The precision pilot measures false alarms of the detector on 60 invented paragraphs. The paragraphs were written by a model, so the seeded patterns are the patterns that a model writes. The figures describe those paragraphs and no other text. The assistant that built the plugin read every row and wrote the labels. The author has not read the rows. In this record, "I" means that assistant.

The rewrite pilot measures whether the command text lets a model produce a safe pass over a manuscript. It checks the guards and the text of the command. It does not measure the quality of the rewrites for a real author.

Four things were not reached:

- No held-out precision. The five rules that I tuned after the first measure were tuned on the paragraphs that exposed their false alarms. The figures after tuning are optimistic.
- No live interactive session. The questions of Step 5 (`AskUserQuestion`), the Overleaf hook, the `Edit` prompts and the commit question ran only as scripted answers in agent sessions. The headless discovery check lists the command and does not run it.
- No real manuscript. The author must run the tools on their own text before they trust the figures.
- The expansion of `${CLAUDE_PLUGIN_ROOT}` inside `allowed-tools` was not tested. The agent runs replaced the variable by hand.

## 2. Precision pilot

Method. `precision.py rows` runs the detector on each of the 60 paragraphs (30 seeded, 30 clean) and prints one row for each flagged finding. The assistant read every row with its paragraph and labeled it before it looked at any figure. The label rule was fixed first:

- `right`: the flagged text is an instance of the pattern that the family names, whatever the author decides to do with it.
- `wrong`: the flagged text is not an instance, for example a literal or technical use.

For a density family I labeled each hit by the same rule. A paragraph of about 70 words crosses a density threshold easily, so a single hit in a paragraph can flag where the same hit in a manuscript would not. That artifact is reported apart.

The tables give counts beside each figure. No pooled figure is given, because the families differ and a pooled number describes none of them.

### Precision per family

| Family | Before tuning | After tuning |
|---|---|---|
| vocabulary-excess | 0.88 (7 of 8) | 1.00 (7 of 7) |
| vocabulary-density | 0.75 (12 of 16) | 0.92 (12 of 13) |
| figurative-load | 0.25 (1 of 4) | 1.00 (1 of 1) |
| binary-contrast | 1.00 (2 of 2) | 1.00 (2 of 2) |
| importance-puffery | 1.00 (1 of 1) | 1.00 (1 of 1) |
| participial-benefit | 1.00 (1 of 1) | 1.00 (1 of 1) |
| weasel-attribution | 1.00 (4 of 4) | 1.00 (4 of 4) |
| fake-strong-verb | 1.00 (1 of 1) | 1.00 (1 of 1) |
| throat-clearing | 1.00 (2 of 2) | 1.00 (2 of 2) |
| recap-opener | 1.00 (5 of 5) | 1.00 (5 of 5) |
| em-dash | 0.88 (7 of 8) | 0.88 (7 of 8) |
| colon-reveal | 1.00 (2 of 2) | 1.00 (2 of 2) |
| rhetorical-question | 0.75 (3 of 4) | 0.75 (3 of 4) |
| assistant-residue | 1.00 (4 of 4) | 1.00 (4 of 4) |
| hedge-stack | 1.00 (6 of 6) | 1.00 (6 of 6) |
| repeated-openers | 1.00 (4 of 4) | 1.00 (4 of 4) |
| staccato-run | 1.00 (4 of 4) | 1.00 (4 of 4) |

Each family rests on 1 to 13 findings. A figure of 1.00 on 2 findings shows nothing about the next 20. The row for figurative-load after tuning rests on one finding (`tapestry`), because the word `landscape` became an info finding.

### Findings on clean paragraphs

Before tuning the detector flagged 12 findings on 9 of the 30 clean paragraphs. After tuning it flags 5 findings on 5 clean paragraphs:

| Paragraph | Family | Text | Label |
|---|---|---|---|
| p09 | em-dash | one em dash that a human wrote | wrong (density artifact of a short paragraph) |
| p10 | recap-opener | `Taken together,` | right (an instance that a human wrote on purpose) |
| p35 | recap-opener | `Taken together,` | right (same) |
| p39 | rhetorical-question | a genuine open question | wrong |
| p52 | vocabulary-density | `paradigm` in `adapted this paradigm` | wrong |

The rule for rhetorical questions cannot tell a genuine open question from a rhetorical one. The author can disable the family in `prose-style.yaml` with `enabled: false`. The `Taken together,` rows show a deliberate choice: the detector flags the opener and the author decides.

### Recall of the seeded labels (before any tuning)

A seeded label is a pair of a paragraph and a family that the paragraph was written to hold. A right finding of that family in that paragraph covers the label. 36 of 54 labels are covered. By family: vocabulary-excess 3 of 4, vocabulary-density 1 of 1, figurative-load 1 of 3, binary-contrast 2 of 4, importance-puffery 1 of 4, participial-benefit 1 of 3, weasel-attribution 2 of 3, fake-strong-verb 1 of 3, throat-clearing 2 of 5, recap-opener 3 of 3, em-dash 1 of 1, colon-reveal 2 of 3, rhetorical-question 3 of 3, assistant-residue 2 of 3, hedge-stack 4 of 4, repeated-openers 3 of 3, staccato-run 4 of 4.

I read each of the 18 silent labels. Two are not gaps. `leverage` is a density word by design, so the seed label was wrong. `serves as an indicator` stays silent on purpose, because the rule for `serves as` uses a closed allow-list. The other 16 are gaps of the word and phrase lists. I recorded them and did not patch them, because a rule tuned to the paragraphs that measure recall inflates recall. The gaps are: `linchpin`, `delicate dance`, the cleft contrast `It is not X that ..., but Y`, `is not simply X; it is Y`, `of paramount importance`, `of immense significance`, `landmark dataset with far-reaching implications`, `, enabling a direct comparison`, `, allowing researchers to compare`, `This section describes`, `Next, we turn to`, `constitutes`, `stands as`, `The outcome was unambiguous:`, `I do not have access to your raw data` and `Specialists widely recognize`.

### Tuning

I tuned five rules in one pass, only for false alarms that the pilot labeled wrong. The pilot rows fell from 76 to 69. The seven rows that disappeared were all labeled wrong. No right row was lost.

- `pivotal` now stays quiet in `pivotal Phase 3 trial`.
- `landscape` is an info finding, with more technical adjectives in its exception.
- `foster` stays quiet in `pups fostered within`.
- `paradigm` stays quiet for named behavioral paradigms such as `open-field`.
- `streamline` stays quiet next to `eddies` and `vortex`.

Gaps that remain after tuning: `pivotal Phase 3 clinical trial` (two qualifiers) still fires, and `adapted this paradigm` still fires.

## 3. Rewrite pilot

Five agent runs followed the text of `/plain-prose` on a made-up LaTeX manuscript of 3,352 words, with scripted answers. Each run started from the same files in its own folder: `main.tex`, `refs.bib` and a voice sample made of the 30 clean paragraphs. The scripted answers approved every passing proposal except deletions, approved a deletion only for `assistant-residue`, declined every proposal that ended as "failed guard", and answered no to the commit question. The agents had no human to ask, and they logged every sentence of the text that was unclear, wrong or in conflict with a script.

| Run | Model | Command text | Applied | Failed guard | Edit failures | Text defects | Flagged before to after | Paragraph blocks (base 77) |
|---|---|---|---|---|---|---|---|---|
| A | sonnet | first | 38 | 1 | 0 | 14 | 59 to 2 | 76 |
| B | sonnet | first | 40 | 0 | 0 | 13 | 59 to 1 | 76 |
| C | opus | first | 40 | 0 | 0 | 15 | 59 to 0 | 76 |
| D | sonnet | after the round that fixed A to C | 39 | 0 | 0 | 10 | 59 to 2 | 77 |
| E | opus | final | 38 | 0 | 0 | 8 | 59 to 3 | 77 |

In all five runs the masked spans (83) and the numeric tokens (258) are identical before and after. Runs A, B, D and E differ from run C in 10, 8, 12 and 11 lines of the manuscript, so the runs produce nearly the same text. The words of the manuscript fell from 3,352 to between 3,232 and 3,240.

Runs D and E left a few flagged windows alone on purpose, for example a tested denial (`binary-contrast`) in both runs. Info findings rose from 15 to between 16 and 18, because a density family drops from flag to info when the density of the file falls.

### What the scripts caught and what they missed

The guards worked as designed. In runs A to C a model check (the portability test) sent two proposals back, and the rewrites that named the subject then failed `numbers`, `no-new-names` and `not-longer`. Those two sentences needed two or three tries, and one ended as "failed guard" in run A. The text of the first version made this likely: the check asks for a sentence that names its subject, and the guards reject a rewrite that adds a name or a number. After the text change, runs D and E needed no second try.

I read all 54 changed sentences of run C as an editor. Most are good: `plays a crucial role` became `contributes to`, `acts as a powerful driver` became `drives`, and the staccato series became one sentence. Four rewrites pass every guard and still change the text in a way that an editor would query:

- `Counts rose. They peaked. They fell in week 12.` became `Counts rose, peaked and fell in week 12.` The time now attaches to all three verbs.
- `Taken together, these results illustrate the multifaceted nature of the response.` became `These results show that body temperature and metabolic rate both respond to cold.` The new sentence holds content that the old one lacked.
- Two rewrites of a claim about unnamed sources inserted the mark `[citation needed from the author]` into the manuscript.
- One rewrite turned an answer to a question into a causal statement with `because`.

The scripts do not check meaning, and the README says so. The command text now tells the model to keep each time and each quantity with its verb, to add no fact that the sentence lacks and to add no mark to the manuscript.

### A data-safety defect that the pilot found

All three runs on the first text ended with one paragraph block fewer than the base. The cause is the `Edit` tool. When the new text is empty, the tool also removes the line break that follows the old text. I confirmed this on a scratch file: the old text ` Third sentence.` and an empty new text turned `...Second sentence. Third sentence.` followed by a line break and `Next paragraph line.` into `...Second sentence.Next paragraph line.`. A deletion at the end of a line therefore merged two paragraphs and the tool reported success.

The command now never uses an empty new text. A deletion replaces the previous sentence plus the sentence to delete with the previous sentence alone (or, at the start of a paragraph, the sentence to delete plus the next sentence with the next sentence alone). Runs D and E kept all 77 blocks. A test pins the wording of the recipe. The test rests on a model of the tool that I fitted to one observation, so a later change of the tool would not fail it.

### Text defects

The five runs logged 14, 13, 15, 10 and 8 places where the text was unclear, wrong or in conflict with a script. I fixed the defects that the first four runs showed, apart from the open points at the end of this section. The main fixes were the recipe for proposal fields, the handling of the `no-new-names` warning, the labels "failed guard" and "failed check", the options of the approval question, the Step 1 and Step 7 tables (they now read the text output of the detector), the escapes in the proposal file and the offsets of a widened proposal on a file with CRLF line ends.

Run E logged eight defects that I did not fix, because the rounds stopped after the fifth. None of them is a safety defect:

1. The rule to state the claim first conflicts with the rule to keep an info opener such as `It is worth noting that`.
2. The phrase "only fault of the sentence" has no definition.
3. Two series that share one window get different `end` rules (staccato run and repeated openers). The agent chose the larger span.
4. The weasel-attribution example drops the number of sources that another line asks the model to keep.
5. The voice check has no unit and no tolerance for the numbers of the profile.
6. Step 7 does not name the density families, so a drop from flag to info is not predictable for `recap-opener`.
7. The "left alone" list does not say how to list a window that another proposal covers.
8. Step 3 does not say that one `Read` of the whole file serves all windows.

Other open points: the strategy text of the family `weasel-attribution` in the data still reads "state the claim as your own or delete it" (the wording of the source guide), and the instruction to count the characters of a widened proposal by hand has no tool support. The guard `exact-before` rejects a wrong count, and the widened proposals of runs D and E passed on the first try.

## 4. Discovery check

A headless session ran once with the plugin folder as `--plugin-dir`, one turn and the prompt `Reply with the single word ok.`. The `init` event lists the command `plain-prose:plain-prose`, and the plugin loads as `plain-prose` version 0.1.0. The command itself did not run. The interactive questions cannot be tested headlessly.

## 5. Blind sample for the author

`ab-sample.md` holds ten before-and-after pairs from run C, chosen with the fixed seed 7 among the reworded sentences, in random order as A and B. The file does not say which side is the revised one. The key stayed outside the repository until the author answered. The author is the only judge of voice. The result goes in the record as the author gave it, without a score.

The pairs come from invented text that a model wrote to hold the patterns. They show whether the rewrites read well. They do not show whether the rewrites sound like the author.

### The author's choices

The author read the ten pairs on 2026-10-28 and gave one answer for each item. The revised version was A in items 1, 2, 3, 4 and 6, and B in items 5, 7, 8, 9 and 10.

| Item | Author's choice | Version chosen |
|---|---|---|
| 1 | B | original |
| 2 | A | revised |
| 3 | A | revised |
| 4 | A | revised |
| 5 | A | original |
| 6 | A | revised |
| 7 | B | revised |
| 8 | B | revised |
| 9 | B | revised |
| 10 | B | revised |

The author kept the original in item 1 (`plays a crucial role` against `contributes to`) and in item 5 (the clause `, ensuring uniform germination across all lines`). The clause may carry information that the author wants in a Methods sentence, and the phrase may be one that the author accepts in their own voice. One reading of ten pairs does not settle either point.

## 6. How to repeat this

- `python3 tests/verification/precision.py rows` prints the rows. `python3 tests/verification/precision.py report evidence/labels.json` prints the table, the recall and the clean-paragraph findings. The labels in `labels.json` are the labels of this record. After a change of the pattern data the report exits 2 when a label has no finding or a finding has no label, so a change of the data forces a new reading.
- `python3 tests/verification/make_manuscript.py OUT_DIR` builds the manuscript of the rewrite pilot.
- `python3 tests/verification/diff_report.py ORIGINAL REVISED` prints the counts per family, the identity of the masked spans and the numbers, and the changed sentences. `rewrite-pilot-run-C-changes.txt` and `rewrite-pilot-run-E-changes.txt` are its output for runs C and E.
- `python3 tests/verification/ab_sample.py ORIGINAL REVISED --n 10 --seed 7 --out DIR` builds a blind sample.
- To measure precision on a manuscript of your own, label its findings with `precision.py rows` (the `--paragraphs` option takes your own paragraph file) and keep the labels outside any public repository.

This evidence folder holds the change lists of runs C and E. The other counts come from session logs outside the repository.
