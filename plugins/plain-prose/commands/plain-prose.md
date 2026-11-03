---
description: "Find the writing patterns of large language models in a manuscript. A script checks each proposed rewrite, and the author can approve by group before any file changes."
allowed-tools:
  - Read
  - Write
  - Edit
  - AskUserQuestion
  - Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/prose_lint.py" *)
  - Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/voice_profile.py" *)
  - Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/prose_verify.py" *)
  - Bash(mkdir -p docs/prose)
  - Bash(python3 -m pip install PyYAML*)
  - Bash(git status *)
  - Bash(git add *)
  - Bash(git commit -m *)
---

# Plain prose

Find patterns that large language models (LLMs) often write in scientific text, and propose plain rewrites. A script finds the patterns and you write each rewrite. A second script checks it. The author can approve by group, and no file changes before the approval.

**Arguments:** `$ARGUMENTS`

Usage: `/plain-prose <path...> [--report-only] [--voice <sample...>] [--format auto|latex|markdown|text] [--max-rounds N]`

- `<path...>` names files or folders. A folder gives every `.tex`, `.md` and `.txt` file under it.
- `--report-only` stops after Step 1 and changes nothing.
- `--voice <sample...>` names files of the author's own writing. Step 2 measures them.
- `--format` sets the format of every path. The default `auto` reads the file extension.
- `--max-rounds N` sets how many more tries a rejected proposal gets. The default is 2.

In each command below, replace `<paths>` with the paths that the author gave. When the author gave `--format`, add it to every call of the three scripts.

## Rules for every step

- Change the words of the author only inside a proposal that the author approves.
- Write `after` and `reason` in each proposal. Add `hedge_reason` or `delete` only when they apply.
- Copy every other field of the window from the output of `prose_lint.py --windows`. A widened proposal and a neighbor sentence change some of them. Step 3 shows how.
- Never edit `before` to make a guard pass.
- Apply only an approval that the author gives in the current turn. Never apply an approval from an earlier turn.
- Write a manuscript file with `Edit` only. Never use `sed`, `tee` or a script to write a file.
- `Read` takes an absolute path. Join the working folder and each relative path.
- Run `mkdir -p docs/prose` once, before the first write to that folder.
- Use no network, except the `pip` install that Step 0 describes.
- Never read, quote or copy a voice sample. The script reads it.
- Make no claim about artificial intelligence (AI) detectors or about authorship. A finding is a style flag.

## Step 0: Preflight

Check that Python 3.6 or later and PyYAML work. The detector imports PyYAML, so its help text is the check. The check passes when the usage text shows and the exit code is 0.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/prose_lint.py" --help
```

Stop in two cases and tell the author why. The shell can say `command not found`, or the output can hold `SyntaxError`. Then the command needs Python 3.6 or later. The output can say `can't open file`. Then Claude Code did not expand `${CLAUDE_PLUGIN_ROOT}`, and the script path does not exist.

If the error names `yaml`, ask the author to agree to the install. After the author agrees, run this command and the check again.

```bash
python3 -m pip install PyYAML
```

If `pip` refuses, ask the author to run the install. Do not try another way to install.

Then use `Read` on each project file in the working folder: `prose-style.yaml`, `docs/prose-style.yaml`, `.claude/prose-style.yaml`, `prose-voice.json`, `docs/prose-voice.json` and `.claude/prose-voice.json`. A `Read` error for a missing file is no error of the command.

If a style file exists, tell the author which families it changes. The scripts find it by themselves.

## Step 1: Detect

Run the detector on the paths.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/prose_lint.py" <paths>
```

The detector exits with code 0 when it flags nothing and with code 1 when it flags a finding. It exits with code 2 when the check cannot run.

On code 2, show the message and stop. On code 0, say that the detector flags nothing and stop.

The output has one block for each file. A block starts with one line for each finding: `file:line:col: family: tier: severity: "text" (strategy)`. The severity is `flag` or `info`. Then a line gives the words of the file and its flagged and info counts. An indented line for each family follows: `family: N hits, R per 1000 words`. N counts the flagged and info findings together. The last line of the output reads `flagged: X info: Y`.

On code 1, show one table for each file, with its words. Each row gives a family, its tiers, its count and its rate. Take the count and the rate from the family line, and the tiers from the finding lines. Then give the totals of the last line. Do not count the findings of a family by severity.

With `--report-only`, also list each flagged finding as `file:line:col`, family and text. Then stop and write no file.

## Step 2: Voice

Create the output folder. Steps 2 and 3 write into `docs/` and `docs/prose/`.

```bash
mkdir -p docs/prose
```

With `--voice` samples, measure them. The profile holds numbers and one-word openers, and no sentence of a sample.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/voice_profile.py" <sample...> --out docs/prose-voice.json
```

On code 2, show the message and go on without a profile. After the script writes the profile, `Read` it. The model checks of Step 4 use its numbers.

With no samples and a saved `prose-voice.json`, `Read` it. With neither, use the plain-writing rules of `rewrite-rules.md`. Tell the author which case applies.

## Step 3: Propose

Before the first proposal, `Read` the file `${CLAUDE_PLUGIN_ROOT}/references/rewrite-rules.md` and the file `${CLAUDE_PLUGIN_ROOT}/references/model-checks.md`.

Run the detector again with `--windows`. The output is one JavaScript Object Notation (JSON) list of windows. An empty list means nothing to propose.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/prose_lint.py" <paths> --windows
```

The detector exits with code 1 when it lists windows. Only code 2 is a failure.

A window is one sentence that holds a flagged finding. It has the fields `id`, `file`, `start`, `end`, `before`, `occurrences`, `families` and `hits`. `families` names the flagged families only. An info finding in the sentence stays out of the proposal, and Step 7 counts it.

For each window, `Read` the paragraph around the line of its first finding. Apply the strategy of each family of the window. Follow the rules of the references.

Write the proposals with `Write` to `docs/prose/proposals-<name>-<date>.json`. The file holds one JSON list of proposals. The name is the file name of the first path without its extension. The date is today, as `YYYY-MM-DD`, from the session.

```json
[{"id": "w001", "file": "examples/made-up-manuscript.tex", "start": 382, "end": 460,
  "before": "Here we delve into the intricate response of its shoots to three light levels.",
  "occurrences": 1, "families": ["vocabulary-excess"],
  "hits": [{"family": "vocabulary-excess", "line": 14, "text": "delve"},
           {"family": "vocabulary-excess", "line": 14, "text": "intricate"}],
  "after": "Here we describe the response of its shoots to three light levels.",
  "reason": "Plain words replace two style words."}]
```

Escape each backslash and each double quote in a JSON string. A LaTeX `\cite` becomes `\\cite` in `before` and in `after`. Write a line break as `\n`, and as `\r\n` in a CRLF file. `Read` hides the CR, but the offsets of `--windows` count it.

- One proposal covers one window, so it covers all findings of one sentence. Proposals never overlap.
- Set `delete` to true only when every family of the proposal allows a deleted sentence. The rules file says which. Then set `after` to an empty string.
- Never widen a `delete: true` proposal. It covers one window. For a series, write a rewrite or leave the series to the author.
- Set `hedge_reason` when the rewrite changes the number of hedge words. Say why in one sentence. The guard counts only these words: `may might could suggest suggests suggested appear appears appeared likely possibly perhaps seem seems seemed probably`.
- A window can get no proposal, for example a strong human sentence or a term of art. Leave it alone and say why in Step 5.
- Keep every number, citation and name. Add no fact. Make the minimum effective edit.
- When `occurrences` is more than 1, `before` is not unique. Add a neighbor sentence to `before` and to `after`, unchanged.
- A neighbor before the window moves `start` back by its length plus the blank between. A neighbor after the window moves `end` forward by the same count.
- When two windows share one neighbor sentence, write one proposal that covers both windows and the neighbor.

Widened proposals. A proposal for a finding of the family `staccato-run`, `repeated-openers` or `rhetorical-question` covers the whole series. The window holds only the third fragment, the third opener or the question.

For such a proposal, set `start` to the start of the first sentence of the series. Set `end` to the end of the last window of the series. For a question, set `end` to the end of the answer sentence.

Take the text between the new `start` and `end` from the `Read` output of the file. Copy it as `before`. Never retype it from memory.

Compute the new offsets from the window. Count from the window start. The offsets of the window already include the text before it. Count every character of the text that you add, with the blanks and the line breaks. A CRLF line break counts as two characters. A `before` of the windows output that spans a line break holds `\r\n` when the file uses CRLF. The guard `exact-before` rejects a wrong copy or a wrong count.

A widened proposal covers every inner window of the series. It takes `id`, `occurrences` and `hits` from its first window. It carries the union of the `families` of those windows, in the order of the windows, first window first. No separate proposal exists for an inner window.

A staccato series of more than three fragments gets one proposal for the first three. Step 7 shows what remains. A series of repeated openers has one window for each opener from the third on. Set `end` to the end of the last of these windows.

## Step 4: Verify

Verify every proposal with `prose_verify.py` before you show it. Add `--voice <profile>` when a profile exists.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/prose_verify.py" docs/prose/proposals-<name>-<date>.json
```

The output has one line for each proposal. A line reads `id: pass`, or `id: FAIL` with the failed guards and their messages. The last line gives `passed: P failed: F`. The verifier exits with code 0 when all pass and with code 1 when one fails. It exits with code 2 when the check cannot run.

On code 2, read the message, fix the proposals file and run the verifier again. A fix after code 2 does not count against `--max-rounds`.

Take each proposal that fails a guard. Read the names and messages of its guards. Change `after` and nothing else. Use `Edit` on the proposals file, escape as in Step 3 and verify again.

If `exact-before` fails on a widened proposal, the copy or the count was wrong. Redo both from the `Read` output. Do not adjust `before` to fit.

The guard `no-new-names` fails when `after` adds a name that `before` lacks. A capitalized word that opens a sentence only gives a warning, printed as `(warning: ...)`. A common word such as `They` gives no warning.

The guard `not-longer` allows `after` at most 15 percent more words than `before`, or one more word, whichever is larger.

Then run the checks of `model-checks.md` on each proposal that passes. Answer each check with yes or no. After a no, rewrite `after`, verify it again and check it again.

Each rewrite after a failed guard or a no uses one try. The tries stop after `--max-rounds` rewrites, 2 by default. After the last try, the proposal shows as "failed guard" if the verifier failed it last. Otherwise it shows as "failed check".

## Step 5: Show

Before the table, run `git status --short -- <file>` for each file that holds a deletion. If the output is not empty, the file is untracked or modified. If git says that the folder is not a git repository, no history exists. In both cases, the question tells the author that the original text will not be in git history.

Group the proposals by the first entry of `families`. Show one table for each group. The columns are `id`, `file:line`, `before`, `after` and `reason`. Take the line from the first entry of `hits`. Give each text in full.

Mark every deletion with the word "delete" in the `after` column. Show each warning beside its proposal.

After the groups, list the proposals that failed a guard or a check. Give the guards or the check and the messages. The command never applies them. Then list each window that got no proposal under "left alone", with its id and the reason.

Then ask the author to approve by group. Use `AskUserQuestion`. It allows 1 to 4 questions with 2 to 4 options each, so it cannot list every proposal.

- Ask one question with `multiSelect` set to true. The answer "none" overrides the other options.
- The options are: all passing proposals except deletions, all proposals of one family, all deletions, and none.
- One family means every passing proposal whose first `families` entry is that family.
- After the author picks one family, ask which one in a second call. With more families than the tool allows options, list them in a numbered table and ask in text. A choice by proposal id works only in the text reply.
- The reply of the author is the approval. Apply it in the turn that holds it.

## Step 6: Apply

A hook may ask for each `Edit`. Before the first `Edit`, tell the author to expect the prompts. Never bypass them.

In the same turn as the approval, call `Edit` once for each approved id. For a rewrite, set the old text to `before` and the new text to `after`. Apply nothing else.

For `delete: true`, never set the new text to an empty string. The `Edit` tool then also removes the line break after the old text, and two paragraphs merge. `Read` the paragraph again before each deletion, and copy the neighbor sentence exactly. The blank is the space or the line break between two sentences.

- If a sentence precedes the window in its paragraph, the old text is that sentence, the blank and `before`. The new text is that sentence.
- Otherwise, if a sentence follows, the old text is `before`, the blank and that sentence. The new text is that sentence.
- Otherwise leave the sentence to the author and say so.

This holds in every format, LaTeX included. The original stays in git history once a commit holds the file. A `%` comment would hide the rest of a line when the sentence sits in the middle of it.

If an `Edit` fails, the text changed or is not unique. Report the id. Never retry with other text.

After at least one edit, run `git status --short`. If git says that the folder is not a git repository, skip the commit. Otherwise ask once with `AskUserQuestion` whether to commit. On yes, run `git add <file>` for each edited file. Then run `git commit -m "<message>"`. Never push.

## Step 7: Report

Run the detector again on the same paths.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/prose_lint.py" <paths>
```

Show the totals `flagged` and `info` before and after. Show the table of Step 1 again, with the count of each family before and after. List each remaining flagged finding as `file:line:col`, family and text, from the finding lines with severity `flag`. Name each family whose count rose. A density family can drop from flag to info when the density of the file falls. Its findings then stay in the text. An edit can join a sentence to its neighbor and create a finding.

Say what the scripts did not check: rule-of-three padding, synonym cycling, meaning and voice. The model checks of Step 4 cover them in part. The author must read each changed passage.

The plugin makes no claim about AI detectors or about authorship. A finding is a style flag.
