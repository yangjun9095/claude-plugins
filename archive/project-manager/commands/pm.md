---
allowed-tools:
  - Bash(git *)
  - Bash(gh *)
  - Bash(date *)
  - Bash(find *)
  - Read
  - Glob
  - Grep
  - AskUserQuestion
description: Project manager — sprint planning, session kickoff, status snapshot, and session handoff via GitHub Issues
---

# Project Manager (`/pm`)

Coordinate work across git worktrees and development areas using GitHub Issues as the source of truth.

**Usage:** `/pm <command>`

| Command | When | What it does |
|---------|------|--------------|
| `/pm sprint` | Weekly (Monday) | Sync CLAUDE.md priorities → GitHub Issues; set up current sprint |
| `/pm start` | Session kickoff | What to work on today: sprint issues, worktrees, PRs |
| `/pm status` | Midway check | Sprint health %, worktree↔issue map, blockers, PRs |
| `/pm handoff` | Session end | Log progress on issues; set up next session |

---

## Instructions

### Step 0: Gather Context

Run ALL of these commands before doing anything else — do not skip any:

```bash
date '+%Y-%m-%d %A (Week %V)'
```

```bash
git worktree list --porcelain 2>/dev/null || echo 'NOT_IN_GIT_REPO'
```

```bash
gh issue list --json number,title,labels,milestone,state,body --limit 100 2>/dev/null || echo 'GH_CLI_UNAVAILABLE'
```

```bash
gh pr list --json number,title,headRefName,state,isDraft,reviewDecision,url --limit 30 2>/dev/null || echo 'GH_CLI_UNAVAILABLE'
```

```bash
gh label list --json name --limit 50 2>/dev/null || echo 'NO_LABELS'
```

```bash
gh milestone list --json number,title,dueOn,state --limit 20 2>/dev/null || echo 'NO_MILESTONES'
```

Read `CLAUDE.md` if it exists in the current directory. Extract:
- **P0 / Priority Tasks** section
- **P1 / Next Up** section
- **P2 / Future Work** section
- **Recently Completed** sections (to avoid recreating closed work)

Parse `$ARGUMENTS` to determine the sub-command:
- Contains `sprint` → **SPRINT**
- Contains `start` → **START**
- Contains `status` → **STATUS**
- Contains `handoff` → **HANDOFF**
- Empty or unrecognized → ask user to pick one of the four

---

## Sub-command: SPRINT (Weekly Planning)

**Goal:** Turn CLAUDE.md priorities into GitHub Issues; assign them to the current sprint.

### S1 — Ensure Labels Exist

Check the fetched label list. Create any that are missing:

```bash
gh label create "p0" --color "d73a4a" --description "Critical / blocking"
gh label create "p1" --color "e4e669" --description "High priority — next sprint"
gh label create "p2" --color "cfd3d7" --description "Future work — backlog"
gh label create "in-progress" --color "0075ca" --description "Actively being worked on"
gh label create "blocked" --color "e11d48" --description "Cannot proceed — needs unblocking"
gh label create "ready-to-review" --color "7057ff" --description "PR open, awaiting review"
gh label create "engineering" --color "bfd4f2" --description "Software engineering task"
gh label create "scientific" --color "d4c5f9" --description "Scientific / research task"
gh label create "documentation" --color "0075ca" --description "Docs or context update"
gh label create "sprint-current" --color "f9d0c4" --description "In this week's sprint"
gh label create "sprint-next" --color "fef2c0" --description "Planned for next sprint"
```

Only run `gh label create` for labels NOT already in the fetched list.

### S2 — Ensure Sprint Milestone Exists

Calculate the current ISO week (e.g., `Sprint 2026-W12`). Check if a matching milestone exists.
If not, create it with the coming Friday as the due date:

```bash
gh milestone create "Sprint YYYY-WNN" --due-date "YYYY-MM-DD" --description "Week NN sprint"
```

### S3 — Parse CLAUDE.md Priorities

From the CLAUDE.md content, build a list of priority items:
- Each item gets: **title** (short imperative), **description** (from CLAUDE.md context), **priority** (p0/p1/p2), **type** (engineering or scientific — infer from content)
- Skip items that appear in "Recently Completed" sections

For each item, check if a **matching issue already exists** by scanning issue titles for keyword overlap (≥2 key nouns in common = match). If matched, note the issue number.

### S4 — Propose Issues for Approval

Present:

```
## Sprint YYYY-WNN Planning

### Already Tracked
- #N [p0] <title> (<status>)
...

### Proposed New Issues
**P0 — sprint-current:**
1. "<title>"
   Type: engineering | Labels: p0, engineering, sprint-current
   From CLAUDE.md: "<quote>"

**P1 — sprint-next:**
2. "<title>"
   Type: scientific | Labels: p1, scientific, sprint-next
   From CLAUDE.md: "<quote>"

**P2 — backlog:**
3. "<title>"
   ...
```

Use **AskUserQuestion** to ask: "Which of these issues should I create?" with multiSelect: true and one option per proposed issue, plus "Create all" and "Skip all" options.

### S5 — Create Approved Issues

For each approved issue:

```bash
gh issue create \
  --title "<title>" \
  --body "<expanded description based on CLAUDE.md context, including acceptance criteria>" \
  --label "<p0,engineering,sprint-current>" \
  --milestone "<Sprint YYYY-WNN>"
```

### S6 — Output Sprint Plan

```
## Sprint YYYY-WNN Plan (Mon DD – Fri DD)

### This Week (sprint-current) — N issues
- #N [p0] <title> — <worktree or "not started">
- #N [p0] <title> — <worktree or "not started">

### Up Next (sprint-next) — N issues
- #N [p1] <title>

### Backlog — N issues

### Open PRs
- PR #N <title> — <ready to merge | needs review | draft>
```

---

## Sub-command: START (Session Kickoff)

**Goal:** Orient the developer at the start of a session — what to work on today.

### A1 — Worktree Activity

For each non-main worktree, get recent activity:

```bash
git -C <path> log --oneline -3 --since="1 week ago" 2>/dev/null
git -C <path> status --porcelain 2>/dev/null | wc -l
git -C <path> rev-list --count origin/main..HEAD 2>/dev/null
```

### A2 — Map Worktrees to Issues

For each worktree branch name, find matching open issues by keyword overlap between branch name and issue titles. Note unlinked worktrees separately.

### A3 — Rank Recommended Actions

Rank by urgency:
1. **PRs ready to merge** — open, not draft, APPROVED or no blocking review
2. **Sprint-current issues** with `in-progress` label + active worktree
3. **Sprint-current issues** not yet started (no worktree, no in-progress label), ordered by priority
4. **Blocked issues** — show what's blocking them
5. **Draft PRs** that need to be finalized

### A4 — Output Session Plan

```
## Session Kickoff — <weekday>, <date>

Sprint YYYY-WNN health: N/M sprint-current issues closed (X%)

### Recommended Focus (top 3)
1. **[Action]** — <title>
   <one-line rationale>

2. **[Action]** — <title>
   <one-line rationale>

3. **[Action]** — <title>
   <one-line rationale>

### Active Worktrees
- `<branch>` → #N <issue title> | N commits ahead | N dirty files
- `<branch>` → ⚠ no linked issue

### Blocked
- #N <title> — <reason>
```

---

## Sub-command: STATUS (Progress Snapshot)

**Goal:** Quick health check of the sprint and all in-flight work.

### T1 — Sprint Metrics

Count sprint-current issues: total, closed, in-progress, not-started. Compute `% complete = closed / total`.

### T2 — Worktree Table

For each active (non-main) worktree:

```bash
git -C <path> log -1 --format="%cr: %s" 2>/dev/null
git -C <path> status --porcelain 2>/dev/null | wc -l
git -C <path> rev-list --count origin/main..HEAD 2>/dev/null
```

### T3 — Output Status

```
## Project Status — <date>

### Sprint YYYY-WNN: X% complete (N closed / M total)

| # | Title | Priority | Status | Worktree |
|---|-------|----------|--------|----------|
| N | QC Framework | p0 | in-progress | agenticCRE-qc |
| N | E2E test | p0 | not-started | — |

### Active Worktrees
| Branch | Last Commit | Dirty | Ahead | Issue |
|--------|-------------|-------|-------|-------|
| qc-framework | 2h: add scoring | 3 | 5 | #12 |

### Open PRs
| PR | Title | Status |
|----|-------|--------|
| #51 | fix/test-debt | Ready to merge |

### Blocked
- <none or list>
```

---

## Sub-command: HANDOFF (Session End)

**Goal:** Log progress on issues and prepare the next session.

### H1 — Ask for Session Summary

Use **AskUserQuestion** to ask:
- Which issues made progress this session?
- Which issues are complete and should be closed?
- Any new blockers discovered?

(If the user already included a summary in `$ARGUMENTS`, parse it directly and skip this question.)

### H2 — Update Issues

For each **completed** issue (with user confirmation):

```bash
gh issue close <number> --comment "Completed in session $(date '+%Y-%m-%d'). <summary>"
```

For each **in-progress** issue:

```bash
gh issue comment <number> --body "**Progress ($(date '+%Y-%m-%d')):** <summary of what was done and what remains>"
```

### H3 — Output Handoff Summary

```
## Session Handoff — <date>

### Completed This Session
- #N <title> — closed ✓

### In Progress
- #N <title>
  Done: <what was accomplished>
  Remaining: <what's left>

### Next Session: Recommended Start
1. <highest priority unfinished item>
2. <next sprint item>

### New Blockers
- <any blockers discovered, or "none">
```

---

## Edge Cases

- **`gh` CLI unavailable or not authenticated**: All sub-commands require `gh`. Show: "Run `gh auth login` to authenticate, then retry."
- **No CLAUDE.md**: For `/pm sprint`, inform user and offer to use README.md or ask them to paste priorities manually.
- **No existing issues**: For `/pm start` and `/pm status`, suggest running `/pm sprint` first to populate the issue tracker.
- **Worktree path inaccessible**: Mark as `broken` in output. Suggest `git worktree prune`.
- **GitHub repo not detected**: If `gh` commands fail because no remote is configured, show a warning and display what context is available (worktrees, CLAUDE.md) without issue tracking.
