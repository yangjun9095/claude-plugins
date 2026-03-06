# claude-plugins

Personal Claude Code plugin marketplace by [Yang Joon Kim](https://github.com/yangjun9095).

## Install

Add this marketplace to Claude Code:

```bash
/plugin marketplace add yangjun9095/claude-plugins
```

Then install individual plugins:

```bash
/plugin install weekly-review@yangjun9095-plugins
```

## Plugins

### `weekly-review`

Generates a structured weekly development report across all git worktrees.

- Summarizes merged PRs, active branches, and stale worktrees
- Highlights uncommitted work and PRs needing attention
- Suggests next-week priorities
- Writes a full report to `docs/weekly/YYYY-MM-DD.md`

**Usage:** `/weekly-review` or `/weekly-review 2` (2-week lookback)
