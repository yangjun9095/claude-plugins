# Verification tools

This folder holds the fixtures and the tools that measure the detector and the rewrite pass. All text here is invented.

Run every command from the plugin folder, with the interpreter: `python3 tests/verification/TOOL.py ...`.

## Contents

| File | Use |
|---|---|
| `fixtures/paragraphs.json` | 60 invented paragraphs: 30 seeded and 30 clean |
| `make_manuscript.py` | Builds a made-up LaTeX manuscript from the 60 paragraphs |
| `precision.py` | Lists the flagged findings and computes the precision of each family |
| `diff_report.py` | Compares a manuscript before and after a rewrite pass |
| `ab_sample.py` | Draws a blind A/B sample of reworded sentences |
| `evidence/` | Holds the results of the controller run |

## The fixtures

Each paragraph in `fixtures/paragraphs.json` has four fields. They are `id`, `text`, `seeded` and `legit`.

- `id` runs from `p01` to `p60`. A shuffle with seed 20261023 set the order.
- `seeded` lists the family ids that the paragraph holds on purpose. It is empty for a clean paragraph.
- `legit` names the legitimate science uses in a clean paragraph. Examples are a hedge, a passive Methods sentence and one em dash.

A seeded paragraph holds one to three patterns, written the way a model writes them. Each of the 15 families that prose can seed has at least three seeded paragraphs. The families `em-dash` and `vocabulary-density` need density, so each has one dense paragraph.

A clean paragraph holds plain science prose of 3 to 6 sentences. It covers Introduction, Methods, Results, Discussion and figure legend text.

The organisms, genes, assays and numbers are invented. So are the names in the citations: Brantwick, Quenby, Marchbanks, Ludgrove and Fenwhistle.

## Rule: do not tune the fixtures to the detector

The writer of the fixtures finished all 60 paragraphs before the first run of the detector. The writer did not read the regular expressions or the word lists.

After that run, no paragraph changed to alter the result. The clean paragraphs that the detector flags stay in the file. They are known false positives, and the precision measure needs them.

`tests/test_verification_tools.py` lists these flags in `EXPECTED_CLEAN_FLAGS`. The test fails when the list changes. Rewrite a clean paragraph only when it holds a construction that a model writes.

After you change the pattern data, run the tests and read each new or lost flag. Then update `EXPECTED_CLEAN_FLAGS` and record the reason in the commit message.

## Tools

### make_manuscript.py

`python3 tests/verification/make_manuscript.py OUT_DIR` writes `main.tex` and `refs.bib` into `OUT_DIR`.

- The manuscript has four sections, a figure environment, two equations, a table and `\cite` commands. It uses all 60 paragraphs.
- The output is the same on every run.
- The tool stops with exit code 2 when `OUT_DIR` holds any file. It writes nothing outside `OUT_DIR`.

### precision.py

`python3 tests/verification/precision.py rows` prints one row for each flagged finding. A row has five fields, separated by tabs. They are the key, the family, the kind of paragraph, the text and the sentence.

The key has the form `p07:3`. It names the paragraph and the number of the flagged finding in it. The key stays the same while the fixtures and the pattern data stay the same.

To measure precision, write a file that maps each key to `right` or `wrong`. Then run `python3 tests/verification/precision.py report LABELS.json`.

- The report gives the precision of each family: right / (right + wrong), with the counts.
- It gives the recall of the seeded labels for each family. A right finding of the family in the seeded paragraph covers one label.
- It lists the seeded labels that no right finding covers.
- It lists the flagged findings on clean paragraphs with their labels.

The report never adds the families together, because the families differ too much for one figure to describe them. The tool exits with code 2 in three cases. A flagged finding has no label, a label has no finding, or a label is not `right` or `wrong`.

### diff_report.py

`python3 tests/verification/diff_report.py ORIGINAL REVISED` compares two files. The option `--format auto|latex|markdown|text` sets the format of both files. The default `auto` uses the extension of `ORIGINAL`.

- It prints the words before and after, and the flagged findings of each family before and after.
- It tells whether the masked spans are identical, and lists each span that only one file holds.
- It tells whether the numbers are identical, and lists the others.
- It lists each changed sentence as before and after.

The exit code is 0 when the masked spans and the numbers match. It is 1 when a number changes, a citation drops or any other masked span changes. It is 2 when the tool cannot read a file.

### ab_sample.py

`python3 tests/verification/ab_sample.py ORIGINAL REVISED --out DIR` draws 10 reworded sentences. The options `--n` and `--seed` change the count and the seed. The default seed is 7.

- `DIR/ab-sample.md` shows each pair as options A and B in a random order. Give this file to the reader.
- `DIR/ab-key.json` tells which option holds the revised text. Keep it from the reader until the reader has answered.
- The same files and the same seed give the same output.
- The tool exits with code 2 and writes nothing when fewer than `n` sentences changed. It also refuses to overwrite an earlier sample.

## How to read the output

A precision figure describes one family only. Read the counts beside it: a family with 3 findings gives a coarse figure.

A recall count below the number of seeded labels means a miss. Either the detector missed the pattern or the seeded sentence does not hold it. Read the sentence before you decide.

A flagged finding on a clean paragraph is a false positive when the sentence uses the word legitimately. The `legit` field of the paragraph names that use.

## Limits

`precision.py` runs the detector on one paragraph at a time. A density family counts findings per 1000 words, so a short paragraph passes the threshold with one finding. The same finding in a whole manuscript can stay `info`. One em dash in a paragraph of 71 words is flagged for this reason.

The detector sees each fixture as plain text. It does not see LaTeX markup here. `make_manuscript.py` gives the LaTeX case.

`ab_sample.py` leaves out deleted sentences and added sentences, because they have no second version to compare.
