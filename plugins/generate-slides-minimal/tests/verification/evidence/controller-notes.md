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
