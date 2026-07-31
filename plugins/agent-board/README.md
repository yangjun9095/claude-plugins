# agent-board

A live kanban board over parallel Claude Code agents working in git worktrees.

## Installation

Install via Claude Code's plugin marketplace:

```bash
claude plugin install agent-board
```

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

## Gotchas

1. **Restart Claude Code after install.** Plugin `bin/` directories join `PATH` and hooks register at session start. If the command is not available immediately after install, restart the Claude Code session.

2. **Directory-source marketplaces copy into `~/.claude/plugins/cache/`.** Local edits to a directory-source plugin need to be refreshed in Claude Code. After modifying files, run `claude plugin update agent-board` to pick up changes.

3. **Uninstall requires disabling first.** The `claude plugin uninstall` command refuses to uninstall while the plugin is enabled at project scope. Disable the plugin before attempting to uninstall it.
