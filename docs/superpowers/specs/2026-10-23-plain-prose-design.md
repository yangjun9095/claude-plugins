# plain-prose: design

Status: implemented. The code, the data, the tests and the documents of this spec exist in `plugins/plain-prose/`. Agent sessions ran the precision pilot, the rewrite pilot and the discovery check (`tests/verification/evidence/results.md`). No person has run one of them, and the author's voice check is open. Section 13 lists the open items.

Date: 2026-10-23. The repository owner requested the plugin. The assistant wrote this spec from the brainstorming answers.

## 1. Purpose and scope

The plugin `plain-prose` finds LLM-style patterns in scientific text and proposes plain replacements. The author approves each replacement before any file changes.

The cause of the request: text from `/manuscript-write` carries patterns such as `load-bearing` and `this is X, not Y`. The plugin runs after drafting. It also works on text that the author wrote.

In scope:
- A detector script for LaTeX, Markdown and plain text.
- A voice profile that a script measures from samples of the author's writing.
- A flow in which the model proposes rewrites, a script verifies them, and the author approves them.
- A pattern list with an evidence tier on every entry.

Out of scope:
- Any claim about AI-detector scores or about who wrote a text. The plugin is a style linter.
- A judgment of scientific correctness.
- Word files (`.docx`). They can come in a later version.
- Changes to the claude.ai skill `manuscript-write`. The repository owner can paste one line into it (see section 10).

## 2. Decisions

| ID | Decision | Made by |
|---|---|---|
| D1 | A new plugin that reuses the pattern families of `no-ai-slop` and the term lists of the Overleaf audit. It does not extend either. | Repository owner, 2026-10-21 |
| D2 | The rewrite aims at the author's voice, measured from samples. Without samples it follows the plain-writing rules. | Repository owner, 2026-10-21 |
| D3 | The tool proposes first. Edits apply only after approval, through the ask-before-edit step. | Repository owner, 2026-10-21 |
| D4 | Version 1 handles LaTeX, Markdown and plain text. | Repository owner, 2026-10-22 |
| D5 | A script detects, the model rewrites, a script verifies. | Repository owner, 2026-10-23 |
| D6 | The plugin is a style linter and makes no authorship claim. The studies in section 3 show that no per-document test works. | Assistant, from the evidence |
| D7 | Every pattern carries a tier: T1 (measured excess in a corpus), T2 (named guide) or T3 (the repository owner's own list). | Assistant, as in generate-slides-minimal |
| D8 | Scripts use Python 3.6.8, the standard library and PyYAML. They never use the network. | Assistant, from the environment |

## 3. Prior art and evidence

The research task of the plan opened each source and recorded it in `references/research-notes/`. The table below came from search summaries and from the files on the repository owner's machine. The notes exist now. Where a row and a note differ, the note decides.

| Source | What it gives |
|---|---|
| `no-ai-slop` (a skill on the repository owner's machine, from the third-party repository `petergyang/no-ai-slop`) | About 18 pattern families, a detect mode, an edit mode with voice rules and a checklist file (`eval.md`). General prose. No script and no tests. |
| `audit.py` of `overleaf-manuscript` | A script with term lists for vocabulary, constructions and paragraph openers. LaTeX only. |
| Humanizer (`blader/humanizer`, MIT) | 26 patterns in 6 sections at version 3.1.0 (`guides.md` S2), from Wikipedia "Signs of AI writing", with a final audit and a second rewrite pass. |
| stop-slop (MIT) | 76 phrase entries in 8 sections, 48 structure rows in 11 sections and a 5-part score (`guides.md` S1). Its README names 6 phrase categories. General prose. |
| claude-scientific-writer (K-Dense, MIT) | A drafting tool for papers and grants. It has no style check. Its layout is a model for the plugin folder. Four vendored folders carry their own license, and the plugin copies nothing from them (`guides.md` section 6). |
| Kobak et al., PubMed excess vocabulary | Words whose use jumped after ChatGPT in 15.1 million English abstracts of 2010 to 2024 (`corpus.md` K1). |
| Jansen, marker dictionary | Markers rose from 4.995 to 11.658 per 1000 words in 28,415 abstracts. Value framing, contribution signalling and connective phrases drove the rise. |
| Czuma, em dash in medRxiv | The em dash share of Discussion sections rose from about 4% to 12%. The paper calls it a population signal. |

No source measures "not X but Y" in scientific text. That family has tier T2 or T3 only.

The repository owner's own list is `~/.claude/forbidden.md`. The plugin reads no file outside the project and the plugin folder. The research task copies the list into the pattern data as T3 entries.

License rule: the plan records the license of each source. The plugin copies family names and short quoted examples. It copies no longer passage.

The skill `no-ai-slop` comes from a third-party repository (`petergyang/no-ai-slop`). The research task found no license in the local copy. So the plugin copies family names and short examples from it and nothing more.

## 4. Architecture

```
plugins/plain-prose/
  .claude-plugin/plugin.json
  README.md
  commands/plain-prose.md
  data/patterns.json            families, rules, tiers, source keys, exceptions
  scripts/
    prose_mask.py               mask and unmask, the LaTeX scanner
    prose_mask_core.py          the span type, the placeholder characters and the scan helpers
    prose_mask_md.py            the Markdown scanner
    prose_patterns.py           load and validate patterns.json and the project file
    prose_text.py               paragraphs, sentences, words and numeric tokens of masked text
    prose_lint.py               detector, command line
    voice_profile.py            voice profile, command line
    prose_verify.py             guards for proposals, command line
  references/
    rewrite-rules.md            one rewrite strategy per family, each with a tier and a source key
    model-checks.md             the checks that only the model can make
    research-notes/             one note per source group, with tiers and a "Pages opened" list
  examples/                     made-up-manuscript.tex with seeded patterns, and its expected report
  tests/
```

The project file is `prose-style.yaml`. The command searches `./`, `docs/` and `.claude/`. It can switch a family off, change a threshold and add a pattern with a tier T3.

The voice file is `prose-voice.json`, in the same folders. It holds numbers about the author's style and no sentences from the samples.

## 5. Masking

`prose_mask.mask(text, fmt)` returns a `Masked` value: the masked text, the list of spans and the original text. Each span has `start`, `end` and `kind`. The kind is one of `comment`, `math`, `env`, `command`, `cite`, `ref`, `url`, `code` or `markup`. The masker replaces span number `i` with the placeholder `"\ue000" + str(i) + "\ue001"`. The two private-use characters U+E000 and U+E001 stand around the index.

`prose_mask.unmask(masked)` is the inverse. It puts the original text of each span back in place of its placeholder. The round trip is the identity for every input. A test checks it on the examples and on random text. `prose_mask.offset_map(masked)` maps each offset of the masked text to an offset of the original, so every finding and every window keeps original offsets.

LaTeX masks these, from the safe side:
- comments, math (`$...$`, `$$...$$`, `\(...\)`, `\[...\]`, and the math environments), the environments `verbatim`, `lstlisting`, `minted`, `tikzpicture`, `tabular`, `tabularx` and `longtable`, and the preamble before `\begin{document}`;
- the tokens `\begin{name}` and `\end{name}` of every other environment, with the arguments of `\begin`. The text inside such an environment stays visible;
- the name and the arguments of every command, except the commands in a list whose argument is prose: `\section`, `\subsection`, `\subsubsection`, `\paragraph`, `\subparagraph`, `\chapter`, `\caption`, `\footnote`, `\emph`, `\textit`, `\textbf`, `\textsc`, `\textrm`, `\underline` and `\title`. For these commands the masker hides the name, the optional argument and the braces, and the text of the argument stays visible;
- the argument of an unknown command, so an unknown command hides its text. The citation, reference and URL commands get the kinds `cite`, `ref` and `url`.

The safe-side rule: a construct that the masker cannot parse hides more text and never less. The worst case is a missed finding, and the file stays intact.

Markdown masks front matter, fenced code, link targets and image paths, reference definitions, table rows, heading and list markers, inline code, HTML tags and comments, and math. The link text stays visible. Indented code stays visible, because a four-space line can continue a list item.

All formats also mask URLs, DOIs and e-mail addresses (kind `url`), and any U+E000 or U+E001 character of the input (kind `markup`), so that input cannot forge a placeholder.

Plain text and Markdown also mask numeric citations such as `[12]` and `[3-5]`, and author-year citations such as `(Smith et al., 2020)`. Markdown also masks the pandoc citations `[@key]`. A citation in the sentence is what lets the weasel-attribution rule stay quiet.

## 6. Pattern data

`data/patterns.json` holds 17 families. Each family has:
- `id`, `title`, `strategy` (one line for the rewrite) and `delete_ok` (true when the family allows a proposal that deletes the sentence);
- `mode`: `each` flags every finding; `density` flags the findings only when the file exceeds `max_per_1000` findings per 1000 words, and reports them as `info` below it. The project file can change the mode and the threshold of a family. A family with a `density` mode needs `max_per_1000` above zero;
- `rules`: regular expressions or word lists. Each rule has a `label`, a `tier` and `sources` (keys such as `corpus:S2`). A rule can also have an `unless` regular expression that the sentence must not match, `unless_citation` and `severity`.

The `severity` of a rule is `flag` (the default) or `info`. A finding of an `info` rule always shows as `info`, also in a family with mode `each`. A rule gets `info` when its pattern also appears in plain science text.

The tiers have one meaning in all of the data. T1 is a measurement in a corpus. T2 is a rule that a named guide states. T3 is the repository owner's own list. A rule with tier T1 cites a `corpus` key. A rule with tier T3 cites `authors` keys only.

Three families have no rules. A family of this kind runs a structural check and keeps `check`, `params`, `tier` and `sources` in place of `rules`. The checks are `question_answer`, `repeated_openers` and `staccato`.

The families follow, in the order of the data. The research task fixed the words, the thresholds and the tiers. The last column gives the tiers that the rules of the family hold.

| Family | Mode | Tiers |
|---|---|---|
| `vocabulary-excess`: words with a measured excess (delve, intricate, showcase and others) | each | T1, T2, T3 |
| `vocabulary-density`: rarer words with an excess, and common words that have an ordinary use (robust, crucial, facilitate and others) | density only. The author can set `mode: each` | T1, T2, T3 |
| `figurative-load`: figurative load words ("load-bearing", "cornerstone", "backbone", "tapestry", "landscape") | each | T1, T2, T3 |
| `binary-contrast`: ("not X but Y", "less about X, more about Y", "it isn't X, it is Y") | each | T2, T3 |
| `importance-puffery`: ("plays a pivotal role", "stands as a testament") | each | T2, T3 |
| `participial-benefit`: trailing participial benefit clause (", highlighting ...", ", underscoring ...", ", ensuring ...") | each | T1, T2 |
| `weasel-attribution`: ("studies show", "experts agree") with no citation in the sentence | each | T2, T3 |
| `fake-strong-verb`: ("serves as", "acts as a") | each | T2 |
| `throat-clearing`: throat-clearing and signposting ("It is worth noting that", "Importantly,", "Interestingly,") | density | T2, T3 |
| `recap-opener`: ("In conclusion,", "Overall,", "Taken together,") | density | T2 |
| `em-dash`: the em dash and the spaced dash | density | T1, T2 |
| `colon-reveal` | each | T3 |
| `rhetorical-question`: a question answered at once | each | T3 |
| `assistant-residue`: ("Certainly!", "Here is the revised", "As an AI"), and the tool-citation tags `oaicite` and `contentReference` | each | T2, T3 |
| `hedge-stack`: ("may possibly", "could potentially") | each | T3 |
| `repeated-openers`: repeated sentence openers (three in a row) | each | T2 |
| `staccato-run`: three sentences of five words or fewer | each | T2 |

The family `assistant-residue` also covers tool-citation tags such as `oaicite` and `contentReference`. The detector reports such a tag only when it stands in prose. The data holds no rule for `utm_source=chatgpt.com`, because the masker hides URLs.

Science exceptions live in the data and have tests. Hedges that state real uncertainty, the passive voice in Methods and "we" are not flagged. A single em dash is not flagged in a file of 400 words or more. "Ecosystem" and "landscape" are skipped near ecological or genomic context words. "Taken together" is density only.

The model checks of `references/model-checks.md` cover what no script can: rule-of-three padding, synonym cycling, fake-profound closers and a rewrite that flattens the voice. The file adapts the checklist of `no-ai-slop`.

## 7. The detector

`python3 prose_lint.py PATH... [--format auto|latex|markdown|text] [--project-dir DIR] [--json] [--windows]`

- `auto` picks the format from the file extension, and an unknown extension gives plain text. A path that is a folder gives every `.tex`, `.md` and `.txt` file under it. The walk skips hidden folders, `node_modules` and `docs/prose`.
- Each finding prints as `file:line:col: family: tier: severity: "text" (strategy)`. Severity is `flag` or `info`.
- The text output follows the findings of a file with the line `path: N words, F flagged, I info`. It then has one line `  family: N hits, X per 1000 words` for each family with a finding, and it ends with the totals line `flagged: N info: N`.
- `--json` gives the same data with the original offsets of the finding and of its sentence.
- `--windows` prints one JSON list, and nothing else. The list holds one window for each sentence that holds a flagged finding. A window has the fields `id`, `file`, `start`, `end`, `before`, `occurrences`, `families` and `hits`. `start` and `end` are offsets in the original text. `before` is the sentence, verbatim. `occurrences` counts how often `before` occurs in the file. `families` lists the families of the findings. `hits` lists the findings. A proposal starts from a window.
- The exit code is 0 for no flagged finding, 1 for at least one, and 2 when the check could not run.
- A sentence is the text between sentence-ending punctuation, after masking. A paragraph break also ends a sentence. So do a heading, a list item and the token of an environment, except a math environment. An abbreviation list prevents a false split ("et al.", "Fig.", "e.g.").

## 8. The voice profile

`python3 voice_profile.py SAMPLE... [--format auto|latex|markdown|text] [--out prose-voice.json]`

The profile holds: words and sentences counted; sentence length (the mean and the 10th, 50th and 90th percentile, over the sentences of at least 3 words); the share of sentences that start with "We"; the hedge rate per 100 sentences; the passive rate; the em dash and semicolon rate per 1000 words; the average word length; the ten most common first words of a sentence. The scripts read the samples and write the numbers only. A profile needs at least 200 words in all samples together. With fewer, the script exits with code 2 and writes nothing.

The profile feeds one guard (section 9) and the rewrite step of the command. Without a profile the command uses the plain-writing rules of `references/rewrite-rules.md`.

## 9. The command, the proposals and the guards

`/plain-prose <path...> [--report-only] [--voice <sample...>] [--format auto|latex|markdown|text] [--max-rounds N]`

Steps:
0. Preflight: check `python3` and PyYAML, then use `Read` on the six candidate paths of `prose-style.yaml` and `prose-voice.json` (`./`, `docs/` and `.claude/` of the working folder, joined into absolute paths). A `Read` error for a missing file is no error of the command.
1. Detect: run `prose_lint.py` with its text output (section 7). Show one table for each file: the tiers of each family from its finding lines, and its count and rate from the line `family: N hits, X per 1000 words`, which counts flagged and info findings together. Then give the totals of the line `flagged: N info: N`. The model does not count the findings of a family by severity. With `--report-only` stop here.
2. Voice: with samples, run `voice_profile.py` with `--out docs/prose-voice.json` (a folder that the scripts search), then read the profile. With a saved profile, read it.
3. Propose: run `prose_lint.py --windows`. The output is one JSON list of windows. For each window, read its paragraph and apply the strategy of its families. Write the proposals to `docs/prose/proposals-<name>-<date>.json`. The file holds one JSON list, and `<name>` is the file name of the first path without its extension. A proposal has `id`, `file`, `start`, `end` (offsets in the original text), `before`, `after`, `families` (a list), `reason`. The window gives `id`, `file`, `start`, `end`, `before` and `families`. It also holds `occurrences` and `hits`, which `prose_verify.py` ignores. The model adds `after` and `reason` and copies every other field. The `families` of a window names the flagged families only. An info finding in the sentence stays out of the proposal, and step 7 counts it. `prose_lint.py --windows` exits with code 1 when it lists windows. A proposal can also carry `delete` (true) and `hedge_reason` (a text). One proposal covers one window, so it covers all findings of one sentence. A staccato window holds the third fragment of its series, and `prose_lint.py` says that the command widens the window to the series. So one proposal can cover several windows. A series of repeated openers and a question with its answer sentence widen the same way. A widened proposal takes `start` or `end` and `before` from the file, and `id`, `occurrences` and `hits` from its first window. It covers every inner window of the series and carries the union of their `families`, in the order of the windows, first window first. A proposal with `delete: true` covers one window and is never widened. When `before` occurs more than once, the proposal adds a neighbor sentence to `before` and `after`, and `start` or `end` moves by the length of the neighbor and the blank between. A window can get no proposal, for example a strong human sentence or a term of art. Step 5 lists it as left alone, with the reason. Proposals do not overlap.
4. Verify: run `prose_verify.py`. The model rewrites a proposal that fails a guard. Then the model runs the checks of `model-checks.md` on each passing proposal, and a check that says no also asks for a rewrite. Each rewrite after a failed guard or a no uses one try, and the tries stop after `--max-rounds` rewrites (default 2). After the last try the proposal shows as failed guard when the verifier failed it last, and as failed check otherwise.
5. Show: a table of proposals grouped by the first entry of `families`, then the proposals that failed a guard or a check, then the windows left alone. Mark each deletion with the word "delete". Ask the author to approve by group: all passing except deletions, all passing proposals of one family (every passing proposal whose first `families` entry is that family), all deletions, or none. The question allows several answers, and none overrides the other options. `AskUserQuestion` allows 1 to 4 questions with 2 to 4 options each, so a numbered table lists the families when they exceed the options. A choice by proposal id works only in a text reply. Before the table, `git status --short -- <file>` shows whether the original of a deleted sentence stays in git history. The question says so when it does not.
6. Apply: in the same turn as the approval, call `Edit` for each approved proposal with `before` as the old text and `after` as the new text, except for a deletion. A proposal with `delete: true` is a plain deletion in every format, and the original stays in git history once a commit holds the file. The `Edit` tool removes the line break after the old text when the new text is empty, so a deletion never uses an empty new text. Its old text is the previous sentence, the blank and `before`, and its new text is the previous sentence. When the window opens its paragraph, the old text is `before`, the blank and the next sentence, and the new text is the next sentence. A paragraph of one sentence stays for the author. A hook may ask for each `Edit`, so before the first `Edit` the command tells the author to expect the prompts, and it never bypasses them. In a git work tree, ask before one commit.
7. Report: run the detector again with its text output. Show the totals and the count of each family before and after, and the remaining flagged findings from the finding lines with severity `flag`. Name each family whose count rose. A density family can drop from flag to info when the density of the file falls. Say what the scripts did not check.

Approval does not carry over between turns. Steps 5 and 6 run in one turn: the command asks, reads the answer and applies the approved edits in that turn. The command never applies an approval that the author gave in an earlier turn.

`python3 prose_verify.py PROPOSALS.json [--format auto|latex|markdown|text] [--voice FILE] [--project-dir DIR] [--json]` runs these guards on every proposal. The file holds the list of proposals, or an object with the list under `proposals`. The script reads each `file` of a proposal from the working directory. Each guard is a script check.

| Guard | Passes when |
|---|---|
| `exact-before` | The original text at `start` to `end` equals `before`, and `before` occurs once in the file. |
| `masked-spans` | `before` and `after` hold the same multiset of masked spans (citations, labels, math, commands). The guard masks each string alone, in the format of the file. |
| `numbers` | `before` and `after` hold the same multiset of numeric tokens, relation signs, quantifier phrases and number words. A numeric token is a number with its percent sign or unit, such as `12.5%`, `5mg`, `5mg/kg` or `3week`. The relation signs are `<`, `>`, `≤`, `≥`, `±`, `≈` and `~`. A tie in LaTeX is no sign. The quantifier phrases are `about`, `approximately`, `nearly`, `over`, `at least`, `at most`, `up to`, `more than`, `fewer than` and `less than`. The number words are `two` to `twelve`, `twenty` to `fifty`, `hundred`, `thousand`, `million`, `billion`, `half`, `twice`, `double` and `triple`. The words `one` and `a` do not count. The noun after a number is not checked, so `12 mice` to `12 rats` passes. The word `over` counts as a preposition too, so a rewrite that drops `over the plate` fails. |
| `no-flag` | The detector finds no flagged finding in `after` for a family in mode `each`. Density families are skipped. The guard lints `after` alone. A rewrite that merges into a neighbor or joins a series of repeated openers can show a finding only in the final file. The re-run of the detector in step 7 catches it. |
| `sentence-length` | Every sentence of `after` has at most `ceil(p90 * 1.25)` words from the profile, or 35 words without a profile. |
| `no-new-names` | Every acronym, every capitalized word inside a sentence and every token with a digit in `after` also occurs in `before`. A number is left to the `numbers` guard. A new name at the start of a sentence is not caught. The result lists such a word as a warning, unless it is a common word. |
| `not-longer` | `after` has at most `max(ceil(1.15 * n), n + 1)` words, for `n` words in `before`. |
| `no-empty` | `after` is not blank (white space only counts as blank), unless the proposal sets `delete: true` and every family in `families` allows deletion. A proposal with an empty `families` list cannot delete. |
| `no-overlap` | The span `start` to `end` does not overlap an earlier proposal of the same file. The later of two overlapping proposals fails. |
| `hedge-kept` | `after` holds as many hedge cues as `before`, or the proposal gives a `hedge_reason`, or `families` holds `hedge-stack` and `after` keeps at least one cue and adds none. |

The plan changed the first version of the guards in four ways.
- (a) A proposal carries `families`, a list. The first version had one family for each proposal. One sentence can hold findings of two families.
- (b) The ninth guard `no-overlap` is new. It fails the later one of two overlapping proposals of one file.
- (c) `not-longer` allows `max(ceil(1.15 * n), n + 1)` words. The term `n + 1` matters only when `before` has no word. Then `after` may have one word.
- (d) The tenth guard `hedge-kept` is new. It comes from `craft.md` section 4, point 6, and is backed by `craft:S17`. The cues are the closed list `may might could suggest suggests suggested appear appears appeared likely possibly perhaps seem seems seemed probably`. A false match makes the guard fail, which is the safe side.

The text output has one line for each proposal: `id: pass`, or `id: FAIL` with the failing guards and their messages in parentheses. A warning of the guard `no-new-names` follows as `(warning: ...)`. The last line is the totals line `passed: P failed: F`. With `--json` the output is one object with `results`, `passed` and `failed`. Each result has `id`, `ok`, `failed`, `detail` and `warnings`. The exit code is 0 when all pass, 1 otherwise, and 2 when the check could not run.

The command's `allowed-tools` lists exactly what the text runs: `Read`, `Write`, `Edit`, `AskUserQuestion`, one `Bash` pattern for each of the three scripts, `Bash(mkdir -p docs/prose)`, `Bash(python3 -m pip install PyYAML*)` for the preflight, and the git commands of the commit step (`git status`, `git add` and `git commit -m`). The pattern of a script ends in `*`, as in `Bash(python3 "${CLAUDE_PLUGIN_ROOT}/scripts/prose_lint.py" *)`, so the options of the script do not change the pattern. A test proves the match in both directions, as in generate-slides-minimal.

In an Overleaf folder the hook of `overleaf-manuscript` still asks for each `Edit`. The plugin does not bypass it with `sed`, `tee` or a script that writes the file.

## 10. Relation to other parts

- `overleaf-manuscript`: run `/plain-prose` after drafting and before the audit. The audit keeps its own checks. A later change can let `audit.py` call `prose_lint.py`. That change is out of scope.
- `manuscript-write` (claude.ai): the repository owner can paste one line, "Run `/plain-prose` on the draft before you hand it over." The plugin cannot edit that skill.
- `no-ai-slop` stays as the general-purpose skill.

## 11. Verification plan

The plan follows `superpowers:writing-skills` and the pilot-then-scale method of the repository owner's global instructions.

- **Unit tests.** Mask and unmask round trip. Each family fires on a seeded sentence and stays quiet on a clean sentence, including each science exception. The sentence splitter on abbreviations. Each guard on a passing and a failing proposal. The voice profile on a made-up sample with known numbers. The command front matter against the text, as in generate-slides-minimal.
- **Source check.** A test requires that every pattern in `patterns.json` and every rule in `rewrite-rules.md` carries a tier and a source key that resolves to a line of the source list in the research notes. That line holds a URL, or for the note `authors` a local file path.
- **Own text.** The README, the command text and the references pass the detector with zero flagged findings. Examples of bad patterns sit in code spans, which masking hides.
- **Precision pilot.** Run the detector on 60 made-up paragraphs, half seeded with patterns and half in plain science prose. Read every flagged row and label it right or wrong, per family. Publish the precision per family beside the counts. Do not publish a pooled figure.
- **Rewrite pilot.** Three runs of the command on a made-up LaTeX manuscript with scripted answers. Record the flagged findings before and after, the guards that failed, the proposals sent back, and the failures of `Edit`. Read every proposal.
- **Voice check.** Give the author a blind sample of ten before-and-after pairs. The author is the only judge of voice. The result goes in the record, without a score.
- **Discovery check.** A headless session lists the command, as in generate-slides-minimal. The interactive questions are not testable headlessly. The record says so.
- **Final review.** A whole-branch review on the most capable model, one fix pass, one scoped re-review.

Fixtures use made-up text only. The repository is public. No manuscript text and no voice sample enters it.

## 12. Risks

- A false positive on legitimate scientific phrasing. The mitigation is density mode, the `unless` field, the tests on exceptions and the author's approval of every edit.
- A rewrite that changes the meaning. The mitigation is the guards, the model checks and the approval step.
- A rewrite that flattens the voice. The mitigation is the profile, the length guard and the rule to make the minimum effective edit and to delete a sentence that has no content.
- A LaTeX construct that the masker mishandles. The mitigation is the safe-side rule: an unknown command hides its argument, so the worst case is a missed finding and the file stays intact.
- The license of reused material. The notes `guides.md` (section 6) and `authors.md` (section 5) record the license of each source. The plugin copies only family names and short examples, so the check is closed for version 1.
- Untested in a live session: whether Claude Code expands `${CLAUDE_PLUGIN_ROOT}` inside the `allowed-tools` lines. The README states the limit.

## 13. Open items

- The final name. The working name is `plain-prose`.
- Word files and a batch-patch apply mode, if the prompt count of `Edit` proves too high.
- The precision pilot, the rewrite pilot, the voice check and the discovery check of section 11. They stay open until a person runs each pilot and records the result. Agent sessions ran the precision pilot, the rewrite pilot and the discovery check on 2026-10-23 and 2026-10-24. The author has not run one.

Two items of the draft are closed. The data holds the threshold and the tier of each family. The plugin copies only family names and short examples from `no-ai-slop`, so version 1 needs no answer on its license.
