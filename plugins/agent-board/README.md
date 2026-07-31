# agent-board

A live kanban board over parallel Claude Code agents working in git worktrees.

## Installation

Install via Claude Code's plugin marketplace:

```bash
claude plugin install agent-board
```

## The skill — so you stop typing the commands

The plugin ships a skill, so the agent maintains the board itself. It fires at
session kickoff and wrap-up, or when you ask "what am I working on", "show the
board", "what's blocked", or say you're starting or finishing a named effort.

Its whole writing burden is **one line per session** — the next concrete step.
Everything else on the card is derived, so there is nothing else to write. If the
skill ever needs a third mandatory write, the declared/derived split has failed.

It is also explicitly told what *not* to do: never write `thread.json` directly
(only `abd` takes the lock and bumps `rev`), never record derived state like "5
commits ahead" into a goal, never run `--watch` from inside a session, never mark a
thread done because a PR merged — a merge is a suggestion and the human decides —
and never open a thread for a two-minute fix, because a board full of trivia is the
same problem as no board.

## Hooks — how the board stays fresh

Two hooks, and only two. **SessionStart** injects the active thread's card into a
new session's context, so an agent picking work up days later starts with the
goal, the next action, and what the thread is blocked on. **SessionEnd** appends
one `session_snapshot` event recording where the session left off. Both are
registered by `hooks/hooks.json` when the plugin is installed — nothing to run.

```bash
abd thread new --title "Fix the resolver" --worktree "$PWD"
abd thread use <id>      # pin it, so the card is injected regardless of launch dir
```

Which thread gets injected, in order: `ABD_THREAD` → the `abd thread use` pin →
longest-prefix match of the session's cwd against thread worktrees →
`CLAUDE_PROJECT_DIR` → the only open thread. With several open threads and no
match it **never guesses**: it says so and asks you to pin one. The cwd match
alone is not enough, because a session launched from the main worktree may be
working in a linked one.

`abd install-hooks --scope local` is the **fallback** for a skills-dir install or
a bare checkout, where `${CLAUDE_PLUGIN_ROOT}` is never substituted. It merges
only the `hooks` key, is idempotent, preserves your other hooks, and refuses to
touch a settings file it cannot parse. It adds `.claude/settings.local.json` to
`.git/info/exclude` — never to `.gitignore`, which is tracked and would ship the
edit into the repo.

**Turning it off**, cheapest first:

| | scope |
|---|---|
| `export ABD_DISABLE=1` | one shell (`0`, `false` and `no` do **not** disable — only `1/true/TRUE/yes/YES`) |
| `touch ~/.agent-board-DISABLED` | the whole machine, no file edits |
| `"disableAllHooks": true` in a settings file | every hook, that scope down |
| remove the `enabledPlugins` entry | the project; picked up with no restart |

A hook that fails does so **invisibly**: every path exits 0 and prints nothing.
Un-opted repositories cost one directory check — no store is created and nothing
is printed. Linux, macOS and WSL; Windows is not supported in v1, where the
failure is a silent no-op.

## Watching, and sharing

```bash
abd board --watch          # repaint every 15s; q quits, r refreshes now
abd board --watch 60       # slower is fine, faster is not (15s floor)
abd board --html board.html
```

`--watch` runs the scan on a **worker thread**, so a slow filesystem never freezes
the display or swallows the keypress meant to quit. A failed refresh keeps the last
good board and says so. Repaints clear the screen rather than moving the cursor up,
because the frame's height changes between refreshes as dirty state and job counts
change. Without a tty (a pipe, CI, `watch abd board`) it degrades to interval-only
instead of failing.

The 15-second floor is deliberate: `git status` over a network filesystem is the
cost, faster polling is not more informative, and on a shared login node it turns a
monitor into a load generator.

`--html` writes **one self-contained file** — no scripts, no external assets, safe
to email or drop in a PR. Lanes reflow to phone width with no media query, DONE
collapses via native `<details>`, it follows the reader's light/dark preference, and
`blocked_by` renders as an inline SVG dependency graph with blockers laid out to the
left of what they block. Links to PRs are real links; nothing else is fetched or
executed. It is a frozen snapshot on purpose — there is no auto-refresh, because
reloading a static file cannot show new data.

## Collisions, PR state and jobs

**Collisions** answer "are my agents stepping on each other". Every non-DONE
thread's worktrees are diffed three-dot against the default branch and unioned
with their uncommitted changes; any file two threads both touch is a collision.

The dirty union is the whole point — in the reference repo both real source
collisions were uncommitted on one side, so a committed-only scan finds neither.
Severity follows from that: **HIGH** = both sides have uncommitted edits to the
same file (a merge conflict being built right now), **MEDIUM** = one side does, or
both are live and committed, **LOW** = a finished or parked thread is involved.
Only HIGH raises a card badge and reaches the injected session card.

Three-dot matters as much: two-dot answers "what differs between the base tip and
this branch" — mostly *what the base did* — and builds a noise wall out of the base
branch's newest commits.

The default ignore list is **lockfiles, binaries and build caches only**. Docs and
markdown are deliberately *not* ignored: adding them dropped the collision count
4→2 in testing and destroyed a 9-file `docs/manuscript/` collision, which is
exactly the "two agents editing the paper" case worth catching. Add your own with
`collisions.ignore_globs_extra` — it is additive, so you cannot lose the defaults.
Known blind spot: `.png` is ignored, so two threads regenerating the same figures
are not flagged. Binary conflicts are not diff-resolvable.

**PR state** comes from `gh` or `glab` and puts a thread IN REVIEW once it has a
non-draft open PR (a draft does not — nobody is waiting on you yet). Cached 300 s;
a merged PR raises "mark this thread done". With no CLI, IN REVIEW is simply never
derived and the footer says so rather than quietly understating severities.

**Jobs** come from `squeue` and are attributed by `job_name_prefix` first, then by
WorkDir. Declare the prefix — only 7% of real jobs ran from inside a worktree, so
WorkDir alone finds almost nothing:

```bash
abd thread set <id> --job-prefix mhb_ism_
```

A live job forces a thread ACTIVE regardless of commit age.

**Speed.** Warm render is ~2.5 s on a 65-worktree repo. A *cold* filesystem cache
can take 30 s or more — all I/O wait — so every render saves a snapshot and
`abd board --cached` replays it in ~0.1 s with its age in the footer. `--offline`
skips the network probe entirely (or set `ABD_ALLOW_NETWORK=0`).

The board never writes inside a worktree and never runs a mutating git command.
Every git call carries `--no-optional-locks`, because plain `git status` rewrites
the index and takes a lock — measured, that broke 13 of 80 concurrent agent
commits. A monitoring tool that breaks the agents it monitors is worse than none.

## `abd doctor`

Reports what is actually configured, detected and installed — not what the config
file claims. Nothing here is declarative: there is deliberately no `*.enabled` key
anywhere in the schema, because enablement that is *declared* goes stale and
enablement that is *proven* cannot.

```bash
abd doctor          # human-readable; rc 0 unless something is genuinely broken
abd doctor --json   # same rows, for scripting
```

`warn` rows keep the exit code at 0 — a warn that returned non-zero would train
you to ignore the code. Only a `fail` makes it 1.

It exists mainly to name the failures that are otherwise **silent**:

- an org-set `disableAllHooks` in managed settings, which kills the tool where
  nothing but managed settings can re-enable it
- a `threads_dir` that resolves *inside* the working tree, where `git status`
  shows the board as untracked and `git clean -xdn` offers to delete it
- the pure and subprocess git resolvers disagreeing — the hook uses one and the
  CLI the other, so disagreement means two different boards for one repo
- a `project.default_branch` that no longer matches the remote, or a base guessed
  from a local ref while a remote exists; either silently poisons every
  ahead/behind number and every merge-base
- an SDK launcher in this repo passing neither `plugins=` nor `setting_sources=`,
  which is why hooks do not fire in SDK sessions. Doctor prints the exact line to
  add, with the plugin root resolved, and lists the shallowest paths first so a
  live launcher is not buried under archived ones.

`rich` missing is reported as **ok**, never as a failure: the plain ANSI renderer
is the guaranteed one and rich is an opportunistic upgrade. The remediation is
interpreter-aware, because naming an interpreter whose `pip` is absent or too old
is advice that fails.

## Gotchas

1. **Restart Claude Code after install.** Plugin `bin/` directories join `PATH` and hooks register at session start. If the command is not available immediately after install, restart the Claude Code session.

2. **Directory-source marketplaces copy into `~/.claude/plugins/cache/`.** Local edits to a directory-source plugin need to be refreshed in Claude Code. After modifying files, run `claude plugin update agent-board` to pick up changes.

3. **Uninstall requires disabling first.** The `claude plugin uninstall` command refuses to uninstall while the plugin is enabled at project scope. Disable the plugin before attempting to uninstall it.
