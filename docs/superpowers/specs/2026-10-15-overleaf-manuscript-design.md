# Overleaf manuscript plugin: design

Date: 2026-10-15
Status: implemented. The author approved the design with amendments C1 to C3 on 2026-10-15. Sections 7 and 8 hold the live-session results of 2026-10-16.
Sources: a handoff document from the author (2026-10-15), a scan of four manuscript repos on this machine, and the two claude.ai skills named in section 3.

## 1. Purpose and scope

The plugin adds three things that the claude.ai skills `manuscript-write` and `agenticcre-manuscript` cannot do. It detects how a manuscript folder syncs with Overleaf. It checks prose mechanically. It asks before any edit to a LaTeX file.

Rules, working method and house style live in `manuscript-write`. Project facts live in a project skill such as `agenticcre-manuscript`. The plugin points to both and restates neither.

Out of scope:
- An Overleaf API client. All work happens on local files.
- Automatic edits. Claude drafts in chat and writes to disk only after approval.
- Edits to any manuscript repo or its `CLAUDE.md`. Each is a follow-up step that needs its own approval.
- Edits to the two claude.ai skills. The author owns them in claude.ai.

## 2. Decisions

| ID | Decision | Source |
|---|---|---|
| X1 | The plugin is generic. Project facts live in project skills. | User, 2026-10-15 |
| X2 | House style governs `.tex` text and chat drafts of it. The global ASD-STE100 rules govern all other replies and the "I am lost" restart mode. | User, 2026-10-15 |
| X3 | Plugin name and skill name are both `overleaf-manuscript`. | Proposed |
| X4 | The plugin ships an ask-before-edit hook (section 7). | User, 2026-10-15 |
| X5 | The plugin is thin (audit item C1). It restates no rule, style text or project fact. | User, 2026-10-15 |
| X6 | `audit_terms.json` mirrors the word lists in `manuscript-write` section 3. Both change together (audit item C3). | User, 2026-10-15 |

Audit item C2 sits outside the plugin: the author pastes corrected text into `manuscript-write` section 5 in claude.ai.

## 3. Facts that shape the design

I verified these on this machine on 2026-10-15.

- Four manuscript folders exist, and all four have `.git`.
  - Folder A: origin is a GitHub repository.
  - Folder B: a second clone of that origin, on a feature branch.
  - Folder C: an older clone of the same project, with an SSH origin on GitHub.
  - Folder D: a different project. Its origin is `git.overleaf.com`.
- The handoff describes a Dropbox mirror with no `.git`. That setup exists on the laptop, so the plugin handles a fourth mode, no `.git`.
- `manuscript-write` and `agenticcre-manuscript` were created on 2026-10-15. They sync from claude.ai plugins, so a local edit is overwritten. `manuscript-write` holds hard rules 1 to 7, the working method, house style, honesty rules and LaTeX hygiene. `agenticcre-manuscript` holds the AgenticCRE project state.
- `manuscript-write` section 5 says cloud-synced folders typically have no `.git` and cannot be branched. That is wrong on this machine.
- The `CLAUDE.md` in folder A has 300 lines. It still uses a banned framing term. `agenticcre-manuscript` section 3 names that term. Folders A and B carry identical copies.
- I did not verify which branch Overleaf tracks for the GitHub-linked repo.

## 4. Layout

```
plugins/overleaf-manuscript/
  .claude-plugin/plugin.json
  skills/overleaf-manuscript/
    SKILL.md              sync protocol and pointers, target 300 words
    audit_terms.json      banned words, constructions, spelling lists
    scripts/preflight.sh
    scripts/audit.py
  hooks/hooks.json
  hooks/guard_tex_edit.py
  tests/
```

The plugin also needs an entry in `.claude-plugin/marketplace.json`. `CONTRIBUTING.md` says to declare skills with `"skills": "./skills/<name>"` in `plugin.json`. The `agent-board` manifest has no such field. The build step follows `CONTRIBUTING.md` and confirms discovery with a test install.

## 5. Session protocol (`SKILL.md`)

1. Load `manuscript-write` for the rules and style. Load the project skill when one exists, for example `agenticcre-manuscript`.
2. Run `bash scripts/preflight.sh <repo>`. It prints the sync mode, branch, ahead and behind counts after a fetch, and uncommitted files.
3. Act on the mode.
   - `overleaf-git`: the remote host is `git.overleaf.com`. One branch reaches Overleaf. Run `git pull --ff-only` before any edit.
   - `github-linked`: the remote is GitHub. Feature branches are allowed. Only the branch that Overleaf links reaches Overleaf. Run `git pull --ff-only` before any edit.
   - `no-git`: Claude cannot pull. Claude asks the author to confirm that Overleaf has synced and is closed.
   - If a fast-forward fails, stop and ask. Never resolve LaTeX conflicts without approval.
4. Work by the rules in `manuscript-write`. The hook backs rules 1, 3 and 4.
5. After each batch of writes, run `python3 scripts/audit.py` on the touched files. Re-grep line numbers before the next batch.

## 6. Audit script

Command: `python3 audit.py [--spelling oxford|american|off] FILE...`. The default for `--spelling` is `off`. Claude passes the value that the project skill states.

The script strips `%` comments, then prints one row per hit as `file:line: rule: text`. It ends with a count per rule family, such as `vocab: 3`. It never edits a file. The rules:
- Em-dash density: more than one `---` in a paragraph, or more than one per 400 words in a file.
- Banned vocabulary, from `audit_terms.json`.
- Banned constructions: paragraph-initial Furthermore, Moreover or Additionally; "Not only ... but also"; "It is worth noting that".
- Spelling convention. Oxford means `-our` and `-re` with `-ize`, and keeps `analyse`.
- A figure reference `Fig. \ref` without the `~`.
- An inventory of `\todo{cite` markers.

## 7. Edit guard hook

`guard_tex_edit.py` runs as a PreToolUse hook on Edit, Write and MultiEdit. The hook acts when the target ends in `.tex`, `.sty`, `.cls` or `.bib`. It also needs `main.tex` in a directory up to four levels above the target. In that case it returns `permissionDecision: "ask"` with a reason that names the rule. A `.sty` or `.cls` file gets the Rule 3 reason, because rule 3 covers shared style and class files. Otherwise the hook stays silent.

Limits:
- A Bash write such as `sed -i` bypasses the hook. `manuscript-write` forbids edits without approval, and `SKILL.md` repeats that for Bash writes.
- Verified on 2026-10-16 with headless `claude -p` (Claude Code 2.1.301) and the plugin loaded by `--plugin-dir`: in the `default`, `acceptEdits` and `bypassPermissions` modes, the hook's `ask` blocked an Edit on `sections/results.tex`, the model saw the reason "Rule 1: edit a .tex file only after explicit approval in the current turn.", and the file stayed unchanged. Headless mode has nobody to answer an `ask`, so the Edit is denied. The interactive prompt, where a person approves the `ask`, was not tested.

## 8. Verification plan

The plan follows `superpowers:writing-skills` and the pilot-then-scale method in the global instructions.

- **Baseline.** Run four pressure scenarios on a fresh subagent with no skill, and record what it does:
  - a request to tighten a paragraph, with time pressure and a writable file;
  - a sentence that needs a citation;
  - a checkout that is behind origin;
  - a draft that invites em dashes and the word "leverage".
- **With the skills.** Rerun each scenario five times with the plugin and `manuscript-write` loaded. Read every transcript. The results are in `tests/pressure_tools/results.md`. Scenario 1 (tighten without approval) did not pass: all five runs wrote to the file. The failing rule is rule 1 of `manuscript-write`, which the author owns.
- **No restated rules.** Check that `SKILL.md` repeats no rule text from `manuscript-write`.
- **Audit script.**
  - Run it on a fixture that triggers each rule once, and on a clean fixture that must report zero.
  - Then run it on a pilot sample from the four repos. Take two sections per repo under a fixed seed, plus the largest and smallest section.
  - Read every flagged row and record precision per rule. Do this before anyone trusts a count.
- **`preflight.sh`.** Test against temporary repos for all four modes.
- **Hook.** Feed synthetic stdin for an in-scope file, an out-of-scope file, and a directory with no `main.tex`.
- **Install.** Clear the plugin cache as `CONTRIBUTING.md` describes, install from the local marketplace, and confirm the skill appears. Discovery was verified on 2026-10-16: in a headless session with the plugin loaded, the first tool call on a manuscript task was the Skill call for `overleaf-manuscript:overleaf-manuscript`. The CONTRIBUTING.md cache-clear install waits for a push. That install runs `claude plugin marketplace remove`, which uninstalls every plugin from the marketplace and deletes its options and data. To pick up a new version, run `claude plugin marketplace update` and then `claude plugin update overleaf-manuscript@<marketplace>`.

## 9. Handoff map

| Handoff section | Destination |
|---|---|
| 1. Hard rules | `manuscript-write` section 1. The hook backs rules 1, 3 and 4. |
| 2. How the author works | `manuscript-write` section 2 |
| 3. Style, banned words, spelling | `manuscript-write` section 3. `audit_terms.json` mirrors the lists. |
| 3. Terminology, including a banned framing term | `agenticcre-manuscript` section 3 |
| 4. Topology and sync | `SKILL.md` modes and `preflight.sh`. The laptop topology sits in `agenticcre-manuscript` section 6. |
| 5. Project state | `agenticcre-manuscript` section 1 |
| 6. Honesty commitments | `agenticcre-manuscript` section 2, with the general rules in `manuscript-write` section 4 |
| 7. Numbers, current and superseded | `agenticcre-manuscript` section 4 |
| 8. The transferable finding | `agenticcre-manuscript` section 5 |
| 9. Open decisions | `agenticcre-manuscript` section 7 |

## 10. Open items

- Which branch Overleaf tracks for folder A. The `github-linked` text in `SKILL.md` stays general until the author says.
- The `CLAUDE.md` in folder A still contradicts `agenticcre-manuscript` on a banned framing term. Trimming it to pointers is a follow-up that needs approval.
