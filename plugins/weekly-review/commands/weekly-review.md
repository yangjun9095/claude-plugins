---
allowed-tools:
  - Bash(git *)
  - Bash(gh *)
  - Bash(date *)
  - Bash(mkdir *)
  - Bash(wc *)
  - Write
  - Read
  - Glob
description: Generate a weekly development review across all git worktrees
---

# Weekly Development Review

Generate a structured weekly report summarizing work across all git worktrees, including merged PRs, active branches, and next-week priorities.

**Argument:** `$ARGUMENTS` (optional: number of weeks to look back, default 1)

## Pre-fetched Context

Current date:
```
!`date '+%Y-%m-%d %A'`
```

Git worktree list:
```
!`git worktree list 2>/dev/null || echo 'NOT_IN_GIT_REPO'`
```

Main branch recent log:
```
!`git log --oneline -20 --since="4 weeks ago" 2>/dev/null || echo 'NO_GIT_LOG'`
```

Open PRs (if gh available):
```
!`gh pr list --state open --limit 50 --json number,title,headRefName,updatedAt,url,isDraft,reviewDecision 2>/dev/null || echo 'GH_CLI_UNAVAILABLE'`
```

Recently merged PRs (last 50):
```
!`gh pr list --state merged --limit 50 --json number,title,headRefName,mergedAt,url 2>/dev/null || echo 'GH_CLI_UNAVAILABLE'`
```

## Instructions

Follow these steps carefully to generate the weekly review report.

### Step 0: Parse Arguments and Compute Date Range

- Read `$ARGUMENTS`. If it contains a number, use that as `weeks_back`. Default to `1`.
- Compute the start date: `today - (weeks_back * 7) days`. Use the `date` command.
- Compute the end date: today.
- Format the date range as `YYYY-MM-DD to YYYY-MM-DD`.

### Step 1: Ensure Output Directory Exists

```bash
mkdir -p docs/weekly
```

If the current directory is not a git repo (e.g., invoked from home), skip file writing and only display the report in chat.

### Step 2: Collect Per-Worktree Data

Parse the pre-fetched worktree list. For EACH worktree path:

1. **Verify accessibility:** Check if the path exists. If not, mark as `broken`.
2. **Get branch name:** Extract from worktree list output. If detached HEAD, note it.
3. **Count commits in date range:**
   ```bash
   git -C <worktree_path> log --oneline --since="<start_date>" --until="<end_date>" --format="%h %s" 2>/dev/null
   ```
4. **Ahead/behind main:** (skip for detached HEAD or main itself)
   ```bash
   git -C <worktree_path> rev-list --left-right --count origin/main...HEAD 2>/dev/null
   ```
5. **Dirty files count:**
   ```bash
   git -C <worktree_path> status --porcelain 2>/dev/null | wc -l
   ```
6. **Last commit date:**
   ```bash
   git -C <worktree_path> log -1 --format="%ci" 2>/dev/null
   ```

Collect all this data before proceeding.

### Step 3: Match Branches to PRs

Using the pre-fetched PR data:
- Match each branch name to any open or merged PR by `headRefName`.
- Note PR number, title, status (open/merged/draft), and URL.
- Branches without PRs are noted as "no PR".

### Step 4: Categorize Branches

Assign each branch to exactly one category:

| Category | Criteria |
|----------|----------|
| **Completed** | Has a merged PR in the date range, OR branch is deleted/merged |
| **Active** | Has commits in date range, OR has an open PR, OR has dirty files |
| **Stale** | No commits in date range AND no open PR AND no dirty files (but worktree exists) |

The `main` branch is always excluded from categorization (it's the reference).

### Step 5: Generate the Report

Use the exact template below. Replace all `{{placeholders}}` with actual data.

---

BEGIN TEMPLATE:

```markdown
# Weekly Development Review

**Period:** {{start_date}} to {{end_date}} ({{weeks_back}} week lookback)
**Generated:** {{today}}
**Worktrees:** {{total_worktrees}} total ({{active_count}} active, {{stale_count}} stale, {{completed_count}} completed)

---

## Accomplishments

{{#if merged_prs}}
### Merged PRs
{{#each merged_pr}}
- **PR #{{number}}** — {{title}} ([link]({{url}}))
  - Branch: `{{branch}}`
  - Merged: {{merged_date}}
{{/each}}
{{/if}}

### Key Commits on Main
{{#each main_commits}}
- `{{hash}}` {{message}}
{{/each}}

---

## In Progress

{{#each active_branch}}
### `{{branch_name}}`
- **Status:** {{ahead}} ahead, {{behind}} behind main | {{dirty_count}} dirty files
- **PR:** {{pr_status}}
- **Recent commits ({{commit_count}}):**
{{#each recent_commits}}
  - `{{hash}}` {{message}}
{{/each}}
{{/each}}

{{#if no_active}}
_No active branches this period._
{{/if}}

---

## Next Week Priorities

### Branches Needing Attention
{{#each stale_branches}}
- [ ] `{{branch}}` — stale since {{last_commit_date}} (consider archiving or resuming)
{{/each}}

### PRs Needing Action
{{#each prs_needing_action}}
- [ ] PR #{{number}} ({{title}}) — {{action_needed}}
{{/each}}

### Suggested Actions
{{#each suggestions}}
- [ ] {{suggestion}}
{{/each}}

---

## Branch Health Summary

| Branch | Category | Commits | Ahead/Behind | Dirty | PR | Last Commit |
|--------|----------|---------|--------------|-------|----|-------------|
{{#each all_branches}}
| `{{name}}` | {{category}} | {{commits_in_range}} | {{ahead}}/{{behind}} | {{dirty}} | {{pr_info}} | {{last_commit}} |
{{/each}}
```

END TEMPLATE

---

### Step 6: Write Report and Display Summary

1. **Write the full report** to `docs/weekly/{{today_YYYY-MM-DD}}.md` (if in a git repo).
2. **Display a condensed summary in chat** with:
   - Date range
   - Number of merged PRs and key highlights
   - Active branch count and any that need attention
   - Top 3 priorities for next week
   - Path to the full report file

Do NOT dump the entire report into chat. Keep the chat summary to ~20 lines max.

### Edge Case Handling

- **`gh` CLI unavailable:** If the pre-fetched PR data says `GH_CLI_UNAVAILABLE`, skip all PR-related sections. Add a note: "GitHub CLI not available — PR data omitted."
- **Detached HEAD worktrees:** Include them in the branch health table. Show "detached" for branch name. Skip ahead/behind calculation.
- **Broken worktree paths:** If the path doesn't exist, mark as "broken" in the table and suggest removal.
- **No activity in date range:** Still generate the report. Focus the "Next Week Priorities" section on stale branches and pending work.
- **Not in a git repo:** Display the report in chat only, do not attempt to write a file.
- **Re-run same day:** Overwrite the existing report file for that date.

### Suggested Actions Logic

Generate contextual suggestions based on the data:
- If any branch is >20 commits behind main: "Rebase `<branch>` onto main ({{N}} commits behind)"
- If any branch has >5 dirty files: "Review uncommitted changes in `<branch>` ({{N}} files)"
- If any branch has had no commits in >2 weeks: "Archive or resume work on `<branch>`"
- If any open PR has no review decision: "Request review for PR #{{N}}"
- If any open PR is marked as draft: "Finalize draft PR #{{N}} ({{title}})"
- If no branches are stale and all PRs are reviewed: "All clear — consider starting new feature work"
