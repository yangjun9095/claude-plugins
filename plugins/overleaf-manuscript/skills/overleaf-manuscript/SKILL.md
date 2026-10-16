---
name: overleaf-manuscript
description: Use when starting work in a LaTeX manuscript folder that syncs with Overleaf (a main.tex with an Overleaf or GitHub remote, or a Dropbox copy of an Overleaf project), before pulling, editing or checking its prose.
---

# Overleaf manuscript sync

**REQUIRED BACKGROUND:** Use `manuscript-write` for the rules and house style. Use the project skill when one exists, for example `agenticcre-manuscript`. This skill repeats neither.

`<base>` below means the base directory shown when this skill loads.

## Session start

Run `bash <base>/scripts/preflight.sh <manuscript-folder>` before you read or edit any file there. Then act on `mode:` and on the final `action:` line.

| `mode:` | What it means |
|---|---|
| `overleaf-git` | The remote is `git.overleaf.com`. One branch reaches Overleaf. |
| `github-linked` | The remote is GitHub. Only the branch that Overleaf links reaches Overleaf. Ask the author which branch that is before you merge or push. |
| `no-git` | A Dropbox copy. You cannot pull. Ask the author to confirm that Overleaf has synced and is closed. |
| `other` | Unknown sync path. Ask the author. |

Run `git pull --ff-only` only when `action:` says so. If it says stop, stop and ask. If `git pull --ff-only` fails, stop and ask. Never resolve a pull conflict without approval.

## During the session

- A hook asks permission for every edit to a `.tex`, `.sty` or `.bib` file. Do not route around it with `sed -i`, `tee` or shell redirection.
- After each batch of approved edits, run `python3 <base>/scripts/audit.py --spelling <oxford|american|off> <touched files>`. Take the spelling value from the project skill, or use `off`.
- Fix audit hits in text you wrote this turn. Ask before you change anything else. A `todo-cite` row is an inventory entry, not an error.
