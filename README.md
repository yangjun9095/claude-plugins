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
/plugin install prep-report@yangjun9095-plugins
```

## Plugins

### `weekly-review`

Generates a structured weekly development report across all git worktrees.

- Summarizes merged PRs, active branches, and stale worktrees
- Highlights uncommitted work and PRs needing attention
- Suggests next-week priorities
- Writes a full report to `docs/weekly/YYYY-MM-DD.md`

**Usage:** `/weekly-review` or `/weekly-review 2` (2-week lookback)

### `prep-report`

Converts analysis session artifacts into a structured report or slide deck outline. Designed for data analysis workflows where you generate many figures/plots during a Claude Code session and need to turn them into a coherent presentation.

- Scans working directory for all generated figures (png, jpg, svg, pdf, html)
- Reads jupytext/Jupyter notebooks to reconstruct the analysis narrative
- Loads audience preferences from an optional `report-style.md` file
- Categorizes every figure as **Include**, **Backup**, or **Skip**
- Generates a slide-by-slide outline with figure assignments, key messages, talking points, and speaker notes
- Supports slide deck (default), long-form document, and Confluence page formats

**Usage:**

```
/prep-report                              # default: 10-min slide deck
/prep-report 15min                        # 15-slide deck
/prep-report 8 slides                     # exactly 8 slides
/prep-report 30min doc                    # long-form document outline
/prep-report 10min -- ./report-style.md   # with explicit audience preferences
```

**Tip:** Create a `report-style.md` in your project to capture your audience's preferences (narrative vs. technical, detail level, required sections). The plugin will auto-detect it from `./report-style.md`, `./docs/report-style.md`, or `./.claude/report-style.md`.
