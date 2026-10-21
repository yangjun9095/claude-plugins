# Comparison of generate-slides and generate-slides-minimal

The script build_results.py computed this file from the saved score files. Do not edit it by hand.

All 6 decks were scored with the peers profile for 12 minutes, with the light theme and notes on. build_results.py scored each of the 6 decks again, and each new score matched.

## Results per run

| Variant | Run | All slides | Errors | Warnings | Words on the busiest slide | Flagged titles |
|---|---|---|---|---|---|---|
| v1 | 1 | 12 | 24 | 81 | 115 | 12 |
| v1 | 2 | 15 | 27 | 104 | 96 | 15 |
| v1 | 3 | 15 | 25 | 104 | 91 | 15 |
| minimal | 1 | 10 | 0 | 2 | 51 | 2 |
| minimal | 2 | 11 | 0 | 1 | 51 | 1 |
| minimal | 3 | 13 | 0 | 1 | 51 | 1 |

## Summary per variant

| Variant | Runs | All slides per run | Errors | Warnings | Warnings per run | Runs without errors | Words on the busiest slide | Flagged titles |
|---|---|---|---|---|---|---|---|---|
| v1 | 3 | 14.0 | 76 | 289 | 96.3 | 0 of 3 | 115 | 42 |
| minimal | 3 | 11.3 | 0 | 4 | 1.3 | 3 of 3 | 51 | 4 |

## Comparison

- The minimal decks have fewer errors than the v1 decks: 0 against 76 in total.
- The minimal decks have fewer warnings than the v1 decks: 4 against 289 in total. Skip notes raise the warning count.
- The minimal decks have fewer flagged titles than the v1 decks: 4 against 42 in total.
- The minimal decks have fewer slides than the v1 decks: 11.3 against 14.0 on average.
- The busiest slide of the minimal decks holds fewer words than the busiest slide of the v1 decks: 51 against 115.

## Findings per rule

A skip note is a warning and counts under its rule.

| Rule | v1 | minimal |
|---|---|---|
| alt-text | 22 | 0 |
| body-font | 79 | 0 |
| fonts-per-slide | 42 | 0 |
| lines-per-paragraph | 16 | 0 |
| margin | 39 | 0 |
| notes | 42 | 0 |
| slide-count | 2 | 0 |
| text-contrast | 42 | 0 |
| title-empty | 42 | 0 |
| title-sentence | 0 | 4 |
| words-per-slide | 39 | 0 |

## Ghost decks

A v1 slide reads "(no title)" here because v1 builds titles as text boxes, so "Ghost decks as read by the controller" holds them.

### v1 run 1 (12 slides)

1. (no title)
2. (no title)
3. (no title)
4. (no title)
5. (no title)
6. (no title)
7. (no title)
8. (no title)
9. (no title)
10. (no title)
11. (no title)
12. (no title)

### v1 run 2 (15 slides)

1. (no title)
2. (no title)
3. (no title)
4. (no title)
5. (no title)
6. (no title)
7. (no title)
8. (no title)
9. (no title)
10. (no title)
11. (no title)
12. (no title)
13. (no title)
14. (no title)
15. (no title)

### v1 run 3 (15 slides)

1. (no title)
2. (no title)
3. (no title)
4. (no title)
5. (no title)
6. (no title)
7. (no title)
8. (no title)
9. (no title)
10. (no title)
11. (no title)
12. (no title)
13. (no title)
14. (no title)
15. (no title)

### minimal run 1 (10 slides)

1. The Osprey score picks designs that bind Target T
2. The Osprey score picked designs that bound Target T: the hit rate rose from 20 percent to 70 percent across four rounds.
3. Only 20 percent of the designs in Round 1 bound Target T.
4. The Osprey score ranks each design before the assay.
5. The hit rate rose from 20 percent to 70 percent across the four rounds.
6. Every design with an Osprey score of 9 or more gave a signal above 60 au.
7. On Target C the designed set beat the control, 80 percent to 10 percent.
8. The Batched pipeline cost 41 units per design, against 100 for the Manual pipeline.
9. Each of the three results improves on its baseline.
10. The 40-residue peptide gave 24.9 au and the 8-residue peptide gave 60.6 au.

### minimal run 2 (11 slides)

1. The Osprey score picks designs that bind Target T
2. The Osprey score picked designs that bound Target T: the hit rate rose from 20 percent to 70 percent across four rounds.
3. Only 20 percent of Round 1 designs bound Target T.
4. The Osprey score ranks each design before the assay.
5. The hit rate rose from 20 percent in Round 1 to 70 percent in Round 4.
6. Binding signal rose with the Osprey score across the 40 designs.
7. Designed peptides beat control peptides on all five targets.
8. The Batched pipeline cost 41 units per design against 100 for the Manual pipeline.
9. Three results support the message of this talk.
10. The reference design gave a stronger signal at each higher concentration.
11. The longest peptide gave 24.9 au and the shortest gave 60.6 au.

### minimal run 3 (13 slides)

1. The Osprey score picks designs that bind Target T
2. The Osprey score picked designs that bound Target T: the hit rate rose from 20 percent to 70 percent across four rounds.
3. Only 20 percent of the designs in Round 1 bound Target T
4. The Osprey score ranks each design before the assay reads it
5. The reference design gave a signal that rose with concentration over 60 minutes
6. The hit rate of the Heron set rose from 20 to 70 percent across four rounds
7. Binding signal rose with the Osprey score across the 40 designs
8. Designed peptides beat control peptides on all five targets
9. The Batched pipeline cost 41 units per design against 100 for the Manual pipeline
10. The hit rate rose, the designs beat the control and the Batched pipeline cost less
11. Binding signal tended to fall as the peptide length rose
12. Melting temperature rose with the Osprey score
13. Expression yield ranged from 9 to 44 mg/L across six designs

## Ghost decks as read by the controller

The controller read these titles by hand. The tables keep the numbers of the linter.

No titles file for minimal-1, minimal-2, minimal-3.

### v1 run 1 (12 slides)

1. The Osprey score picks designs that bind Target T
2. A score that ranks designs before the assay helps only if high scores mean binding
3. The Kestrel assay scored 40 filtered designs, and a hit is a signal of at least 50 au
4. The hit rate rose from 20 percent to 70 percent in four rounds
5. All 6 designs with an Osprey score of 9 or higher were hits
6. On Target C the designed set beat the control, 80 percent to 10 percent
7. The Batched pipeline cost 41 units per design, against 100 units for the Manual pipeline
8. The study ran once on one plate layout, and the controls were not matched for length
9. The next run repeats the assay on a second plate layout with length-matched controls
10. Three results support the message: the hit rate rose, the designs beat the control, the cost fell
11. Backup: At 60 minutes the reference design read 94.5 au at 25 uM and 27.7 au at 1 uM
12. Backup: Binding signal fell with peptide length, 24.9 au at 40 residues and 60.6 au at 8 residues

### v1 run 2 (15 slides)

1. The Osprey score picks designs that bind Target T
2. The Osprey score is worth using only if the designs it picks bind Target T
3. The Mallard filter passed only designs with an Osprey score of 4 or higher
4. The Kestrel assay reads a signal that rises with concentration
5. The hit rate rose from 20 percent to 70 percent in four rounds
6. Designs with a higher Osprey score gave a higher binding signal
7. On Target C the designed set beat the control, 80 percent to 10 percent
8. The Batched pipeline cost 41 units per design
9. Binding signal tended to fall as peptide length rose in the Heron set
10. The study ran once, on one plate layout, with controls not matched for length
11. The next study repeats the assay on a second plate layout with length-matched controls
12. The Osprey score picked designs that bound Target T
13. Hit share rose from 2 of 13 designs to 7 of 9 across three Osprey score bands
14. Melting temperature rose with Osprey score, up to 81.1 C at a score of 9.3
15. Expression yield of the 6 designs ranged from 9 to 44 mg/L

### v1 run 3 (15 slides)

1. The Osprey score picks designs that bind Target T
2. A score helps only if its top-ranked designs bind Target T in the assay
3. Each design gets an Osprey score, passes the Mallard filter, and is assayed
4. The Kestrel assay reads binding at 60 minutes, and a hit needs at least 50 au
5. Three comparisons carry the result, and each one has its own baseline
6. The hit rate rose from 20 percent in Round 1 to 70 percent in Round 4
7. Designs with higher Osprey scores gave hits more often
8. On Target C the designed set beat the control, 80 percent to 10 percent
9. The Batched pipeline cost 41 units per design against 100 for the Manual pipeline
10. One plate layout and unmatched control lengths limit what these results show
11. The next test needs a second plate layout and length-matched controls
12. Higher Osprey scores gave more hits, and the hit rate rose from 20 to 70 percent
13. Longer peptides gave lower binding signals in the Heron set
14. Higher Osprey scores went with higher melting temperatures
15. Expression yield ranged from 9 mg/L for Design 5 to 44 mg/L for Design 4

## Limits

- The comparison has 3 runs per variant on one synthetic project.
- The subagents follow the command text. The interactive questions cannot run in a headless session.
- The linter belongs to the minimal plugin, so v1 is judged by rules that it did not set out to meet.
- The linter does not score what needs a judgment, such as whether a figure supports its headline.
- The controller read the ghost decks. That reading is a judgment, and this file does not score it.
- The word count covers every slide. The words-per-slide rule skips a take-home slide of the minimal plugin.
- The All slides column counts every slide. The slide-count rule of the linter counts visible main slides only.
- The comparison measures compliance with rules. It does not measure audience outcomes.

## Notes of the controller

These notes come from the assistant that ran the comparison, the controller. The numbers below come from the saved score files. The readings of the slides are my own judgment.

### How the runs were made

Six subagents ran the two commands, one run each, on fresh copies of the synthetic project that make_project.py builds. All six used the same model and the same answer sheet. The sheet gave one message sentence, three take-homes with baselines, a talk of 12 minutes, the profile peers, the title-slide fields and "looks good" for every approval. It said "no" to fixing warnings, so the decks show the first build.

The v1 runs used the committed plugin generate-slides, unchanged. The minimal runs used the command text as it stood after the second pilot round. Each agent read the command and followed it by hand. No agent called AskUserQuestion or the Skill tool.

Two pilot rounds came first. The first pilot found that the shell has no `python` or `pip`, so the harness now allows `python3`. It also found 8 gaps in the minimal command text and 6 contradictions between notes.md and results.csv in the synthetic project. The second pilot found 7 more gaps in the command text. I fixed all of them before the six runs of this file. The pilot decks are not part of this file.

### What the numbers do and do not say

The v1 plugin builds each title as a plain text box. The linter finds no title placeholder on a v1 slide, so every v1 slide has a `title-empty` error and the linter's ghost deck reads "(no title)". That one finding makes 42 of the 76 v1 errors and all 42 flagged titles. The other v1 errors are 33 slides above the 40-word limit of the peers profile and one font below the error floor.

Of the 289 v1 warnings, 126 are skip notes. A skip note says that a size, a color or a font comes from paragraph defaults and the linter skipped that check. A skip note is a warning and says nothing about the slide itself.

At run time the minimal decks had 7 warnings, all with the rule `title-sentence`. Three are the 22-word message of the user on the roadmap slide, one in each run. The command keeps that sentence as written, so the warning stays. The other four said that a headline has no verb the check knows. All four headlines have a verb, "cost" three times and "gave" once, so all four warnings were false alarms of the verb check. The three minimal decks hold 31 slides other than the title slide, so the false alarm rate on these runs was 4 of 31 headlines.

After the runs, a fix to the verb check stopped the three alarms for "cost 41". The score files in this folder come from the linter after that fix. They show 4 minimal warnings: the three messages and one "gave" headline. The same linter changed the text of the `title-empty` message, so the v1 score files carry the new text. The counts of the v1 findings did not change.

The linter does not measure whether a deck is good. The count of errors and warnings says how closely a deck follows the rules of the minimal plugin. It does not rank the decks.

### What I read in the decks

I rendered all six decks with LibreOffice and read every slide as an image at about 40 dpi. I read the pilot decks in the same way.

The v1 decks have action titles with verbs on every slide. Each content slide holds one figure with three labelled bullets beside it, and most hold a boxed baseline or message. The ghost decks of the three runs tell a complete story, and each run adds a slide on limits and a slide on next steps. All three runs add statistics that the notes do not hold, such as correlations and hit counts by score band. The slides are dense. In run 1 the bullets on slide 6 run into the baseline box. The pipeline box on slide 3 holds small monospace text in all three runs. The table slides of runs 2 and 3 hold small table text.

The minimal decks hold one figure or one claim on each slide, a sentence headline and at most two short call-outs. The look matches the demo that the author approved: 28 pt titles at the top with no line under them, one violet accent, no filled shapes. I found no overlap in the three decks.

Three defects remain in the minimal decks that the linter does not see.
- On the take-home slide the space before the baseline of claim 2 is larger than for claims 1 and 3. This happens in all three runs. A later change to the helper puts each claim and its baseline in one text box, which removes the gap in new decks. The six decks in this folder were built before that change and keep the gap.
- Some headlines leave one word alone on the second line, for example "rounds." and "percent." in run 1.
- The slide for the need or the approach is a table of two terms in all three runs. The agents judged this the weakest evidence element of the deck.

The minimal command has no step for limits or next steps. The three decks show the limits of the study only in a call-out or in the notes. The v1 decks give them a slide each. The author can decide whether the story spine needs a slot for limits.

The minimal command asks for a message, so all three minimal decks put the message sentence of the user on the roadmap slide as written. The v1 command never asks for a message. Runs 1 and 2 of v1 used it in call-outs, and run 3 did not use it.

### Changes after the runs

The minimal runs used the command text of the second pilot round. Three things in the command text changed later: the roadmap message limit (about 104 characters, measured against the helper), the title-slide fields (now asked in Step 2 with the other questions) and the advice for a pip install that the system refuses. The decks in this folder are the output of the earlier text.

### Commands outside allowed-tools

The agents listed each command that they ran outside the allowed-tools list of the command. These lists come from their reports.
- v1, all three runs: `pwd`, `head`, `tail`, `sort` and `awk`, because the v1 command text itself uses them and its list holds none of them. Run 3 also ran `echo` and `fc-list`.
- minimal, run 2: `python3 -c` to count the characters of the message, and `pwd`.
- minimal, runs 1 and 3: no command outside the list.

In a real session each such command asks the user for permission.

### Discovery check

I started `claude -p` with `--plugin-dir` on the plugin folder, with Claude Code 2.1.305. The init event listed the command `generate-slides-minimal:generate-slides-minimal` and the plugin `generate-slides-minimal` version 0.1.0. It listed the installed command `generate-slides:generate-slides` beside it, so the two names do not collide. The check made one model call that answered "ok". It did not run the command, so the questions of the command and the expansion of `${CLAUDE_PLUGIN_ROOT}` in the `allowed-tools` lines are still untested in a live session.

### Limits of this file

- Each variant has 3 runs on one project with one model. I made no statistical test.
- No agent rendered a deck. Their judgments of the figures rest on the PNG files and the text limits.
- The agents had no Glob or Grep tool in their sessions. They listed files with `ls`.
- No person opened a preview. The answer "looks good" came from the answer sheet.
- The v1 titles in the section "Ghost decks as read by the controller" come from the ghost-deck output of the verifier of v1, `verify_slides.py`.
