# Evidence for the comparison

This folder holds the saved scores of three runs of `/generate-slides` (v1) and three runs of `/generate-slides-minimal`. The runs used the same synthetic project and the same scripted answers. The script `build_results.py` reads this folder and writes `results.md` in the folder above it.

## Files

| File | Required | Content |
|---|---|---|
| `v1-1.score.txt`, `v1-2.score.txt`, `v1-3.score.txt` | yes | The output of `score_deck.py` for the deck of each v1 run. |
| `minimal-1.score.txt`, `minimal-2.score.txt`, `minimal-3.score.txt` | yes | The same for the minimal runs. |
| `v1-1.pptx` to `minimal-3.pptx` | no | The deck of the run. With a deck present, `build_results.py` scores it again and compares. |
| `v1-1.titles.txt` to `minimal-3.titles.txt` | no | The titles of the run as the controller read them, one row for each slide. |
| `controller-notes.md` | no | The notes of the controller. `build_results.py` copies the file to the end of `results.md`. |
| `README.md` | no | This file. |

A score file with any other name that ends in `.score.txt` is an error. A titles file with any other name that ends in `.titles.txt` is an error too.

## How to fill the folder

Run each command from the plugin folder. Make a fresh copy of the project for each run.

```
python3 tests/verification/make_project.py /path/to/run-copy
```

Save the deck of each run in this folder. Score each deck with the same settings.

```
python3 tests/verification/score_deck.py tests/verification/evidence/v1-1.pptx --minutes 12 --profile peers > tests/verification/evidence/v1-1.score.txt
```

Build the results when all six score files exist.

```
python3 tests/verification/build_results.py tests/verification/evidence
```

## The grammar of a score file

The parser is strict. A line that matches no rule below is an error that names the file and the line. The file must end with a newline and hold no carriage return.

```
score    = settings findings ghost words summary
settings = "settings: profile=" NAME " minutes=" NUMBER " theme=" NAME " notes=" ("on" | "off") NL
findings = "findings:" NL { finding }
finding  = ("slide " N | "deck") ": " RULE ": " ("error" | "warn") ": " ("T1" | "T2" | "T3") ": " MESSAGE NL
ghost    = "ghost deck:" NL { "slide " N ": " TITLE NL }
words    = "words per slide:" NL { "slide " N ": " (COUNT " words" | "unreadable") NL }
summary  = "errors: " E " warnings: " W NL
```

N is a whole number from 1. A TITLE is the title of the slide on one line, or `(no title)`, or `(unreadable)`. A MESSAGE starts with a character that is not a space. The finding rows have the format of `design_lint.py`.

The first NAME is the profile and the second NAME is the theme. Each must be a name that the plugin knows. NUMBER is the length of the talk in minutes. It must be finite and above 0.

The parser also checks that the file agrees with itself.

- The slide numbers of the ghost deck run 1, 2, 3 and so on. The word counts list the same slides.
- E equals the number of `error` rows. W equals the number of `warn` rows.
- A finding names a slide that the ghost deck lists, or names the deck.
- A slide is `(unreadable)` in the ghost deck if and only if it is `unreadable` in the word counts.

The six files must carry the same settings line. A file with other settings is an error.

## An example

```
settings: profile=peers minutes=12 theme=light notes=on
findings:
slide 2: words-per-slide: warn: T3: 31 words on the slide; keep at most 25. Cut the text or move it to the notes
deck: slide-count: warn: T2: 14 main slides for 12 minutes; keep at most 12. Cut slides or move them to the backup
ghost deck:
slide 1: A made up talk about binder design
slide 2: Binder design succeeds for 12 of 15 targets
words per slide:
slide 1: 6 words
slide 2: 31 words
errors: 0 warnings: 2
```

## The titles file

A deck that builds its titles as plain text boxes has no title for the linter, so its ghost deck reads `(no title)` on every slide. The controller reads the titles from the slides by hand. The controller saves them in a titles file beside the score file of the run.

```
titles = { "slide " N ": " TITLE NL }
```

A row has the grammar of a ghost deck row. The slide numbers run 1, 2, 3 and so on. The file lists as many slides as the score file, and a file with another count is an error. The parser is as strict as the parser of the score file. The file must be UTF-8 with a newline at the end.

```
slide 1: A made up talk about binder design
slide 2: Binder design succeeds for 12 of 15 targets
```

The script `build_results.py` shows the titles in the section "Ghost decks as read by the controller", one block for each run. The tables keep the numbers of the linter.

## The notes of the controller

Write free text into `controller-notes.md`. The script `build_results.py` appends the text to `results.md` under the heading "Notes of the controller", after the section Limits. It copies the text byte for byte. It does not change, wrap or count anything in it. The file must be UTF-8.

## What the numbers mean

- The word count of a slide is the count of the words-per-slide rule. It leaves out the title, the source line and the footer shapes.
- The count covers every slide. The rule skips a take-home slide, so a high count there is not a finding.
- A hidden slide shows in the ghost deck and in the word counts. The linter applies no rule to it.
- A flagged title is a slide with a finding of the rule `title-empty`, `title-sentence` or `title-unique`.
- The busiest slide of a run is the slide with the most words. The column "Words on the busiest slide" shows its word count.
- The column "All slides" counts every slide of the deck. The slide-count rule of the linter counts visible main slides only.

## Exit codes

The script `score_deck.py` exits with 0 for no error and with 1 for at least one error. It exits with 2 for a deck or an option that it cannot use. It also exits with 2 for an error that nobody expected, with one message on stderr.

The script `build_results.py` exits with 1 and a message on stderr for each failure of a check, and it writes no file in that case. It exits with 2 for a usage error of the command line, with the usage message of `argparse`. The script writes `results.md` through a temporary file in the same folder and renames it. A write error cannot cut an existing `results.md`.
