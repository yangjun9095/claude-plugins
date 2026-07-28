# agent-board

A live kanban board over parallel Claude Code agents working in git worktrees.

## Installation

Install via Claude Code's plugin marketplace:

```bash
claude plugin install agent-board
```

## Gotchas

1. **Restart Claude Code after install.** Plugin `bin/` directories join `PATH` and hooks register at session start. If the command is not available immediately after install, restart the Claude Code session.

2. **Directory-source marketplaces copy into `~/.claude/plugins/cache/`.** Local edits to a directory-source plugin need to be refreshed in Claude Code. After modifying files, run `claude plugin update agent-board` to pick up changes.

3. **Uninstall requires disabling first.** The `claude plugin uninstall` command refuses to uninstall while the plugin is enabled at project scope. Disable the plugin before attempting to uninstall it.
