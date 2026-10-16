# Archived plugins

These plugins left the marketplace on 2026-10-15 after a usage audit. Nothing was deleted. Git history keeps every change.

Usage window: 2026-08-03 to 2026-10-15. The count covers Skill tool calls and slash commands in 94 top-level Claude Code sessions and 3,031 subagent transcripts. Use before August is not visible.

| Plugin | Version | Last commit | Calls in window | Why archived |
|---|---|---|---|---|
| `weekly-review` | 1.0.0 | 2026-03-20 | 0 | agent-board shows worktree, PR and dirty-file state on each render. session-wrap covers wrap-up. |
| `project-manager` | 1.0.0 | 2026-03-22 | 0 | It plans sprints through GitHub Issues. agent-board covers the same coordination job. |
| `analyze-project` | 1.0.0 | 2026-03-16 | 0 | The follow-up agent in session-wrap and agent-board cover part of the job. |
| `paperbanana` | 1.0.0 | 2026-03-23 | 0 | The `paperbanana` command is not installed on the HPC and needs a Google API key. |

Three user-level commands were archived with them: `weekly-review.md`, `gh-create-issues.md` and `gh-setup-labels.md`. A fourth item, the old `build-kg` copy, left `~/.claude/skills`. All four sit in `~/.claude/archive/2026-10-15/` with a `MANIFEST.txt` that lists their original paths.

## Restore a plugin

1. Run `git mv archive/<name> plugins/<name>`.
2. Add an entry to `.claude-plugin/marketplace.json` with `name`, `source` set to `./plugins/<name>`, the version from the table, and the description from `plugins/<name>/.claude-plugin/plugin.json`.
3. Clear the plugin cache as `CONTRIBUTING.md` describes, then reinstall.
