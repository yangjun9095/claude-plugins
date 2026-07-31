---
name: agent-board
description: Open, update, park or close an agent-board thread, and show the board of parallel worktree efforts. Use at session kickoff, at wrap-up, or when the user asks "what am I working on", "show the board", "what's blocked", or wants to start/park/finish a named effort.
allowed-tools: [Bash(abd *), Bash(git *), Read, AskUserQuestion]
---

# agent-board

A **thread** is one named effort that owns one or more git worktrees. The board
tracks threads, not worktrees, so an effort spanning three worktrees is one card.

Your entire writing burden is **one line of declared prose per session**: the next
concrete step. Everything else on the card — ahead/behind, dirty files, PR state,
live jobs, collisions, column, last activity — is recomputed on every render. If you
find yourself wanting to write down something the board could compute, don't.

## Step 0 — Gather context

Run these before deciding anything, as ordinary Bash calls.

Do **not** add the shell pre-fetch syntax to this file — an exclamation mark
immediately followed by a backtick-quoted command, which Claude Code runs while
loading the skill. It executes in a separate sandbox that ignores the session's own
sandbox settings and dies on some Linux hosts with `pivot_root: Invalid argument`.
(Spelling that pattern out literally here would trigger it, which is why this
paragraph describes it instead.)

```bash
abd --version || echo "abd not on PATH"
pwd
```

The launcher is on `PATH` as `abd` after a plugin install and a restart. If it is
missing, fall back to `<base directory>/../../bin/abd` — the Skill tool tells you the
base directory at the top of this file's injection. Never hardcode an absolute path.

If `abd` cannot be found either way, say so once and continue without it. The board
is a convenience; failing to reach it must never block the user's actual work.

## At kickoff — at most two commands

1. **If a thread card was already injected into this session's context, you are
   done.** The SessionStart hook did this work; re-running `abd board` to learn what
   you have just been told is waste.

2. Otherwise, check whether a thread already owns this worktree:

   ```bash
   abd board --json
   ```

   Look for a thread whose `worktrees` contain `$PWD`. If one exists, adopt it —
   do not open a second.

3. If none exists **and the user is starting something new**, open one and pin it:

   ```bash
   abd thread new --title "<at most 8 words>" --goal "<1-2 sentences>" --worktree "$PWD"
   abd thread use <id>
   ```

   `thread new` prints the id. The pin is what makes the card appear in later
   sessions regardless of which directory `claude` was launched from — without it,
   attribution falls back to guessing from the launch cwd.

4. **If the card lists `blocked_by`, say so and ask before proceeding.** A blocker
   is not resolved because it looks stale. That is a question for the user.

## At wrap-up — exactly one command

```bash
abd thread set <id> --next-action "<the single next concrete step, one line>"
```

Write what a person returning in three days needs in order to resume: the *next
action*, not a summary of what happened. "Wire `parse_v2` into the CLI dispatcher"
is useful. "Made good progress on parsing" is not.

Add these **only if they actually changed**:

```bash
abd thread set <id> --add-worktree "<path>"     # this effort grew a worktree
abd thread set <id> --rm-worktree "<path>"      # it no longer owns one
abd thread set <id> --blocked-by <other-id>     # it now waits on another thread
abd thread set <id> --clear-blocked-by          # its blockers are genuinely resolved
abd thread set <id> --issue <n>                 # it tracks an issue
abd thread set <id> --job-prefix <prefix>       # its scheduler jobs share a prefix
```

`--clear-blocked-by` is the only way to unblock a thread, since editing
`thread.json` is forbidden. Use it when you have *checked* that the blockers are
done — not because the board still shows BLOCKED and that seems inconvenient.

If something happened that the next reader genuinely needs and `--next-action`
cannot carry — a dead end worth not repeating, a decision and its reason — add one
event. This is **optional**, and it does not replace the next action:

```bash
abd event add <id> --kind note --text "<one sentence>"
```

Resist the urge to narrate. The timeline earns its value by being short.

If the effort is finished: `abd thread done <id>`.
If it is going on ice: `abd thread park <id> --reason "<why>"`.

## When the user asks about the board

| They ask | Run |
|---|---|
| "show the board", "what am I working on" | `abd board` |
| "what happened on this one", "catch me up" | `abd show <id>` |
| "what's blocked" | `abd board --column BLOCKED` |
| "what am I not tracking" | `abd board --all` |
| "why aren't my jobs showing up" | `abd board --unattributed` |
| "is anything colliding" | `abd board` — collisions print under the lanes |
| "why is the board wrong / empty" | `abd doctor` |
| "share this" | `abd board --html <path>` |

Read the collision section out loud when it is non-empty. **HIGH** means two threads
have uncommitted edits to the same file — a merge conflict being written right now,
and the single most useful thing on the board.

## Never

- **Never write `thread.json` yourself**, with `Write`, `Edit`, or a shell redirect.
  Only `abd` takes the lock and bumps `rev`; a direct write silently loses a
  concurrent update from another session.
- **Never record derived state.** No "5 commits ahead", no "3 dirty files", no "PR
  is green" in `goal` or `next_action`. It is stale the moment you write it and the
  board already shows it live.
- **Never run `abd board --watch`, or `abd board` in a loop, from inside a session.**
  Watch mode is for a human's second terminal.
- **Never run a mutating git command on the board's behalf** — no `fetch`, `reset`,
  `worktree add`, `gc`. The board is strictly read-only about the user's repos, and
  so are you when acting for it.
- **Never open one thread per worktree** when a single effort spans several. Use
  `--add-worktree`.
- **Never invent a `blocked_by` id.** Check `abd board --json` first: a dangling id
  raises a badge on somebody else's card.
- **Never mark a thread done because its PR merged.** A merge raises a *suggestion*
  on the card; the human decides when an effort is over.
- **Never open a thread unprompted** for a one-off question or a two-minute fix. A
  board full of trivia is the same problem as no board.
