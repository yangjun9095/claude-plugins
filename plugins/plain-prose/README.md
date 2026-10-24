# plain-prose

Find patterns that large language models (LLMs) often write in LaTeX, Markdown and plain-text manuscripts. The plugin proposes plain rewrites, and you approve by group before any file changes.

The plugin is a style linter. It makes no claim about detectors of artificial intelligence (AI) text or about who wrote a text.

Version 0.1.0.

## Install

```
/plugin marketplace add yangjun9095/claude-plugins
/plugin install plain-prose@yangjun9095-plugins
```

The plugin needs Python 3.6 or later and PyYAML. The command asks before it installs PyYAML. No script uses the network.

## Usage

```
/plain-prose <path...> [--report-only] [--voice <sample...>] [--format auto|latex|markdown|text] [--max-rounds N]
```

- `<path...>` names files or folders. A folder gives every `.tex`, `.md` and `.txt` file under it.
- `--report-only` runs the detector, shows a summary and stops. It changes no file.
- `--voice <sample...>` names files of your own writing. The command measures them and writes a voice profile.
- `--format` sets the format of every path. The default `auto` reads the file extension.
- `--max-rounds N` sets how many more tries a rejected proposal gets. The default is 2.

Two examples follow.

```
/plain-prose main.tex --report-only
/plain-prose sections/ --voice earlier-paper.tex
```

## What it detects

The data file `data/patterns.json` holds 17 families. Each rule of a family has a tier. The tiers are T1 (measured in a corpus), T2 (stated by a named guide) and T3 (the repository owner's own list).

A family in mode `each` flags every finding. The exception is a rule with severity `info`, which always shows as `info`, whatever the mode of its family. A family in mode `density` flags its findings only when the file exceeds the threshold, and shows them as `info` below it.

| Family | Mode | Tiers | What it finds | Rewrite strategy |
|---|---|---|---|---|
| `vocabulary-excess` | each | T1, T2, T3 | Vocabulary with excess in LLM text, and the repository owner's banned words (list as of 2026-10-23) | Replace the style word with the plain word, or with the fact that the word stands for. |
| `vocabulary-density` | density, above 3 per 1000 words | T1, T2, T3 | Rarer words with an excess in LLM text, flagged by density (list as of 2026-10-23) | Replace the style word with the plain word, or with the fact that the word stands for. |
| `figurative-load` | each | T1, T2, T3 | Figurative load words | Replace the figure with the literal term for the relation that the figure names. |
| `binary-contrast` | each | T2, T3 | Binary contrast | State the positive claim once. Drop the denied half unless a reader holds that view or a test addressed it. |
| `importance-puffery` | each | T2, T3 | Importance puffery | Replace the praise with the measured result or the cited fact that supports it. |
| `participial-benefit` | each | T1, T2 | Trailing participial benefit clause | Move the clause into its own sentence with a subject and a verb. Delete it when it states a benefit that the data do not show. |
| `weasel-attribution` | each | T2, T3 | Weasel attribution | Name the source with a citation. With no source, state the claim as your own or delete it. Never add a citation. |
| `fake-strong-verb` | each | T2 | Fake-strong verbs | Use the verb that names the action, or use `is`. |
| `throat-clearing` | density, above 2 per 1000 words | T2, T3 | Throat-clearing and signposting | Delete the opener and start with the claim. |
| `recap-opener` | density, above 1 per 1000 words | T2 | Recap openers | Delete the opener word and keep the statement when it draws a new inference. |
| `em-dash` | density, above 2.5 per 1000 words | T1, T2 | Em dash | Use commas or parentheses for an aside, a period for a second clause and a colon for a list. |
| `colon-reveal` | each | T3 | Colon reveal | State the finding as the main clause. |
| `rhetorical-question` | each | T3 | Rhetorical question answered at once | State the answer as a statement. |
| `assistant-residue` | each | T2, T3 | Assistant residue | Delete the whole span and tell the author to check the sentences that followed it. |
| `hedge-stack` | each | T3 | Hedge stacking | Keep the one hedge that the data support. Delete the other hedge word. |
| `repeated-openers` | each | T2 | Repeated sentence openers | Merge the sentences, or put the old information first so that each opener differs for a reason. |
| `staccato-run` | each | T2 | Staccato run | Join three or more fragments into one or two sentences. Put the new fact last. |

The detector masks everything that is not prose before it looks for a pattern. It hides math, commands, comments, citations, code and URLs. A finding keeps its offsets in the original file.

Run the detector alone from the plugin folder with `python3 scripts/prose_lint.py <path>`. From another folder, give the full path of the script. The exit code is 0 for no flagged finding, 1 for at least one, and 2 when the check could not run. The detector has these options:

- `--format auto|latex|markdown|text` sets the format of every path.
- `--project-dir DIR` names the folder to search for `prose-style.yaml`. The detector also searches `docs/` and `.claude/` of that folder. The default is the working folder.
- `--json` prints the findings, with their offsets, as JavaScript Object Notation (JSON).
- `--windows` prints one window for each sentence with a flagged finding. It exits with code 1 when it lists windows. The command uses it in Step 3.

## The flow

The command follows seven steps.

0. Preflight. The command checks Python 3.6 or later and PyYAML and finds the project files.
1. Detect. The detector runs and a summary shows. With `--report-only` the command stops here.
2. Voice. With samples, `voice_profile.py` writes a profile. Without samples, the command reads a saved profile.
3. Propose. The detector lists one window for each sentence with a flagged finding. The model writes a proposal for each window.
4. Verify. `prose_verify.py` runs ten guards on each proposal. The model then runs the checks of `references/model-checks.md`. After a failed guard or a failed check, the model rewrites the proposal, up to `--max-rounds` times in all.
5. Show. A table lists the proposals, grouped by the first entry of `families`, and then the proposals that failed. You approve by group.
6. Apply. In the same turn as your approval, the command calls `Edit` once for each approved proposal. It never applies an approval from an earlier turn.
7. Report. The detector runs again. The command shows the counts before and after and says what the scripts did not check.

The command writes the proposals to `docs/prose/proposals-<name>-<date>.json`. The detector skips the folder `docs/prose` when it scans a folder.

## The guards

`prose_verify.py` runs these ten guards on each proposal, in this order. A proposal passes when no guard fails.

| Order | Guard | Passes when |
|---|---|---|
| 1 | `exact-before` | The original text at `start` to `end` equals `before`, and `before` occurs once in the file. |
| 2 | `masked-spans` | `before` and `after` hold the same citations, labels, math and commands. |
| 3 | `numbers` | `before` and `after` hold the same numeric tokens, relation signs, quantifier phrases and number words. |
| 4 | `no-flag` | The detector finds no flagged finding in `after` for a family in mode `each`. |
| 5 | `sentence-length` | Every sentence of `after` is within the limit of the profile, or 35 words without a profile. |
| 6 | `no-new-names` | Every acronym, capitalized name and token with a digit in `after` also occurs in `before`. |
| 7 | `not-longer` | `after` is at most 15% longer than `before` (rounded up), or one word longer. |
| 8 | `no-empty` | `after` is not blank, unless the proposal sets `delete` and every family allows deletion. |
| 9 | `no-overlap` | The span does not overlap an earlier proposal of the same file. |
| 10 | `hedge-kept` | `after` holds as many hedge words as `before`, or the proposal gives a `hedge_reason`. A `hedge-stack` proposal also passes when `after` keeps at least one hedge word and no more than `before` has. |

## The voice profile

With `--voice`, the command measures your samples with `voice_profile.py` and writes `docs/prose-voice.json`. The profile holds these numbers:

- the words and the sentences counted;
- the length of a sentence: the mean and the 10th, 50th and 90th percentile;
- the share of sentences that start with "We", the hedge rate, the passive rate, and the average word length;
- the rate of em dashes and semicolons per 1000 words;
- the ten most common first words of a sentence, one word each.

The guard `sentence-length` reads the 90th percentile of the sentence length. The model reads the other numbers when it checks that a rewrite fits your voice. Without a profile, the model follows the plain-writing rules of `references/rewrite-rules.md`.

The privacy rule: the profile holds numbers and one-word openers and no sentence of a sample. Never copy a sample into the repository. The command never reads a sample itself, and the script refuses an `--out` path that names a sample. Open the profile before you commit it to a public repository.

## The project file

The file `prose-style.yaml` tunes the detector for one project. The scripts search `./`, `docs/` and `.claude/`. The key `families` changes a family: `enabled`, `max_per_1000`, `mode` and `disable_labels`. The key `extra_patterns` adds a family of one rule with tier T3.

```yaml
families:
  em-dash:
    max_per_1000: 5
  colon-reveal:
    enabled: false
  throat-clearing:
    disable_labels: [sentence adverb]
extra_patterns:
  - id: lab-term
    title: A word that the lab avoids
    words: [synergistic]
    strategy: Use the plain word.
    mode: each
```

A typo in a family id, a label or a key gives exit code 2 and a message that names it.

## Limits

The plugin finds style patterns. It does not decide what is true or who wrote a text.

- The plugin makes no claim about AI detectors. It scores no document. In `references/research-notes/corpus.md` (section 3, point 1), source S1 states that its method cannot identify single abstracts. Source S5 states that its evidence does not support authorship attribution of one abstract.
- The plugin makes no claim about authorship. A text without the listed words can still come from a model (section 3, point 6 of that note). In source S6, 4.23% of Discussion sections held an em dash before 30 November 2022, so a person writes em dashes too.
- The plugin gives no scientific judgment. It does not check that a result, a method or a citation is correct.
- The detector has false positives on legitimate scientific phrasing, such as a term of art that holds a style word. The plugin gives no precision figure for a manuscript. The figures in `tests/verification/evidence/results.md` describe 60 invented paragraphs and nothing else. Exceptions in the data, the density mode and your approval limit the harm.
- A rewrite can change the meaning. The ten guards check the form of a proposal. They do not read its meaning, and the model checks cover it only in part.
- A rewrite can flatten your voice. The voice profile and the guard `sentence-length` limit the change. Without samples and without a saved profile, no voice target exists, and the model follows the plain-writing rules of `references/rewrite-rules.md`.
- The pattern lists become outdated. `data/patterns.json` carries the date 2026-10-23 (`as_of`). In the corpus note, the T1 words describe 2023 and 2024 text. No measurement covers 2026 text.
- The families `binary-contrast` and `rhetorical-question` have no corpus support. The corpus note found no study that measures `not X but Y` in science text (section 3, point 9). One study of essays (source S16) counts rhetorical questions that assert a claim. It finds 2.28 for each document in LLM text and 5.55 and 5.11 in human text.
- When the LaTeX masker cannot parse a construct, it hides more text. So the detector can miss findings. The file stays intact.
- The masker leaves some constructs visible, so the detector can flag text there. These are the title in brackets after `\begin{name}`, the entries of `thebibliography` and the text of the environment `comment`. They also include the entries of a `.bib` file and indented code in Markdown.
- The detector cannot find the tag `utm_source=chatgpt.com`, because the masker hides URLs. The family `assistant-residue` reports a tool tag only when the tag stands in prose.
- The plugin does not handle Word files (`.docx`).
- The repository owner did not test whether Claude Code expands `${CLAUDE_PLUGIN_ROOT}` in the `allowed-tools` lines of the command. If it does not, the patterns may not match, and Claude Code then asks for approval of each script call.
- A widened proposal can need a retry. A series of fragments, a series of repeated openers and a question with its answer need one proposal over several sentences. The model counts the offsets, and the guard `exact-before` rejects a wrong count.
- The guard `no-flag` lints the rewritten text alone. A rewrite that merges into a neighbor sentence can show a finding only in the final file. The detector run of Step 7 catches it.
- The guard `no-new-names` cannot catch a new name at the start of a sentence. It gives a warning for such a word unless the word is a common word. It also misses a gene name in lower case with no digit.
- The guard `no-new-names` checks the names that `after` adds. A name that `after` drops passes every guard, unless it holds a digit that the guard `numbers` counts. No model check names the kept names, and no pilot seeded a dropped name.
- The guard `hedge-kept` counts the words of a closed list of hedge words: `may might could suggest suggests suggested appear appears appeared likely possibly perhaps seem seems seemed probably`. A false match, such as the month May, fails the guard. A `hedge_reason` waives it.
- `Edit` on a file with CRLF line endings is untested.
- A sentence to delete that holds a number or a citation fails a guard, so the author edits it by hand.

The guard `numbers` has these limits.

- The guard `numbers` counts each number and ignores its position. A rewrite that swaps two numbers passes.
- The unit list is closed (see `_UNITS` in `prose_text.py`). A unit outside it gives the bare number, so `100 rpm` to `100 rcf` passes.
- The guard does not check the noun after a number, so `12 mice` to `12 rats` passes.
- Number words stop at twelve. The list then continues with twenty, thirty, forty and fifty, with `hundred` to `billion`, and with `half`, `twice`, `double` and `triple`. The guard does not compare a word such as `thirteen` or `sixty`.
- Time-unit abbreviations do not fold. The tokens `48 h` and `48 hours` differ, so a rewrite from one to the other fails.
- A quantifier swap such as `about` to `roughly` fails by design.
- A quantity word used as an ordinary word counts. The word `over` in `over the plate` is one example.

The scripts do not check four things. The model checks of Step 4 cover them in part, and you must read each changed passage.

- rule-of-three padding: a list that gains a third item for rhythm;
- synonym cycling: two words for one thing in one paragraph;
- meaning: whether the rewrite keeps the claim;
- voice: whether the rewrite sounds like you.

## Decisions for the author

Deletions. A proposal with `delete: true` removes the sentence. The command applies it as a plain deletion in every format, LaTeX included. The `Edit` tool removes the line break after the old text when the new text is empty. So the command never uses an empty new text: it replaces the neighbor sentence with itself, and the deleted sentence goes. The original stays in git history once a commit holds the file. A `%` comment would hide the rest of a line when the sentence sits in the middle of it. The repository owner's skill `manuscript-write` prefers to comment out text with a one-line comment. Change Step 6 of the command text if you want comments.

Approval by group. The proposals table groups proposals by the first entry of `families`. A sentence with findings of two families shows once, under the first family. You approve by group: all passing proposals except deletions, all passing proposals of one family, all deletions, or none. You can pick several groups in one answer, and "none" overrides the others. The tool `AskUserQuestion` allows 1 to 4 questions with 2 to 4 options each, so it cannot list every proposal. To pick single proposals, name their ids in a text reply. Change Step 5 if you want to approve by paragraph.

## Relation to other tools

- `overleaf-manuscript`: run `/plain-prose` after drafting and before the audit. The audit keeps its own checks. In an Overleaf folder the hook of that plugin asks before each `Edit`. The command never bypasses it with `sed`, `tee` or a script.
- `manuscript-write`: this claude.ai skill is outside the repository, so the plugin cannot edit it. To chain the two, paste this line into the text of the skill: `Run /plain-prose on the draft before you hand it over.`
- `no-ai-slop`: this skill stays as the general-purpose tool. It comes from a third-party repository (`petergyang/no-ai-slop`). The research found no license in the local copy, so the plugin copies only family names and short examples from it.

## Research notes

The folder `references/research-notes/` holds five notes. Every rule of the data cites a key of a note.

- `corpus.md`: measured excess of words, phrases and punctuation in published science text, and the limits of each study.
- `wikipedia.md`: the signs of AI writing that a Wikipedia guide lists, read for scientific manuscripts.
- `guides.md`: the pattern lists, scoring rules and voice advice of other guides and tools.
- `authors.md`: the repository owner's own lists, rewrite preferences and checklist.
- `craft.md`: sources on how to rewrite scientific prose and which hedges to keep.

## Example and tests

The folder `examples/` holds `examples/made-up-manuscript.tex`, a LaTeX manuscript with seeded patterns and made-up text. The file `examples/made-up-manuscript.expected.txt` holds the output of the detector on it. Run the detector from this folder to compare.

```bash
python3 scripts/prose_lint.py examples/made-up-manuscript.tex
```

Run the tests from this folder.

```bash
python3 -B -m unittest discover -s tests
```
