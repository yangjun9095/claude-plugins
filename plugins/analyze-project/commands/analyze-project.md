---
allowed-tools:
  - Bash(git *)
  - Bash(gh *)
  - Bash(date *)
  - Bash(wc *)
  - Bash(find *)
  - Bash(ls *)
  - Bash(mkdir *)
  - Read
  - Write
  - Glob
  - Grep
  - Task
description: Comprehensive project status analysis — achievements, gaps, and priorities
---

# Project Status Analysis

Perform a comprehensive audit of a software project by scanning documentation, code structure, git history, and CI/issue state. Produce a structured report mapping **what's done**, **what's missing**, and **what to focus on next**.

**Argument:** `$ARGUMENTS`

Modes:
- `/analyze-project` — full analysis (default)
- `/analyze-project --quick` — abbreviated scan (skip deep code analysis)
- `/analyze-project --focus areas` — focus on specific areas (e.g., `--focus testing,docs`)
- `/analyze-project 2w` — set the planning horizon for priorities (default: 2 weeks)

## Pre-fetched Context

Current date:
```
!`date '+%Y-%m-%d %A'`
```

Repository root:
```
!`git rev-parse --show-toplevel 2>/dev/null || echo 'NOT_IN_GIT_REPO'`
```

Git remote:
```
!`git remote get-url origin 2>/dev/null || echo 'NO_REMOTE'`
```

Recent commit count (last 90 days):
```
!`git log --oneline --since="90 days ago" origin/main 2>/dev/null | wc -l`
```

Branch count:
```
!`git branch -r 2>/dev/null | wc -l`
```

Open PRs (if gh available):
```
!`gh pr list --json number,title,headRefName,state,isDraft,createdAt --limit 20 2>/dev/null || echo 'GH_CLI_UNAVAILABLE'`
```

Recently merged PRs (last 90 days):
```
!`gh pr list --state merged --json number,title,headRefName,mergedAt,url --limit 50 2>/dev/null || echo 'GH_CLI_UNAVAILABLE'`
```

Open issues:
```
!`gh issue list --json number,title,labels,createdAt --limit 20 2>/dev/null || echo 'GH_CLI_UNAVAILABLE'`
```

## Instructions

Follow these steps carefully. Use the Task tool to parallelize independent data-gathering steps.

### Step 0: Parse Arguments

Read `$ARGUMENTS`. Determine:
- **Mode**: `full` (default), `quick`, or `focus`
- **Focus areas** (if `--focus`): comma-separated list from `[docs, code, tests, infra, git]`
- **Planning horizon**: extract duration like `2w`, `1m`, `3d` (default: `2w` = 2 weeks)

### Step 1: Discover Project Structure

Identify the project's shape by scanning key files and directories. Run these in parallel:

1. **Project identity files:**
   ```
   Glob for: README.md, CLAUDE.md, .claude/*, package.json, pyproject.toml,
   Cargo.toml, go.mod, Makefile, setup.py, setup.cfg, docker-compose.yml
   ```

2. **Documentation tree:**
   ```
   Glob for: docs/**/*.md, *.md (root level)
   Count total docs, list top-level doc directories
   ```

3. **Source code tree:**
   ```
   Glob for: src/**/*.py, lib/**/*.*, app/**/*.*, cmd/**/*.*
   Count files by extension, identify main source directories
   ```

4. **Test tree:**
   ```
   Glob for: tests/**/*.*, test/**/*.*, *_test.*, *.test.*
   Count test files, identify test framework (pytest, jest, go test, etc.)
   ```

5. **CI/CD and infra:**
   ```
   Glob for: .github/workflows/*.yml, Dockerfile*, .gitlab-ci.yml,
   Jenkinsfile, scripts/**/*.sh
   ```

### Step 2: Read Key Documents

Read the following files (skip any that don't exist):

**Tier 1 — Always read (project identity):**
- `README.md` — project overview, claimed features, quick start
- `CLAUDE.md` — development context, priorities, architecture notes
- `CONTRIBUTING.md` — development workflow
- `pyproject.toml` / `package.json` / `Cargo.toml` — dependencies and project metadata

**Tier 2 — Read if they exist (roadmap/planning):**
- Any file matching: `*ROADMAP*`, `*TODO*`, `*PLAN*`, `*CHANGELOG*`, `*IMPROVEMENT*`
- `docs/design/**/*.md` (read titles + first 20 lines of each)
- `.github/ISSUE_TEMPLATE/*` — what issue types are defined

**Tier 3 — Skim in `--full` mode only (deep context):**
- `docs/architecture/**/*.md`
- `docs/guides/**/*.md`
- Key source files identified by README or CLAUDE.md as "entry points"

For each document, extract:
- **Stated goals**: What does the project claim to do?
- **Stated priorities**: What's listed as P0/P1/P2 or "next up"?
- **Stated status**: What's marked as "done", "in progress", "planned"?
- **Stale claims**: Anything that references dates >3 months old or features that may not exist

### Step 3: Analyze Git History

Collect quantitative data about the project's development trajectory:

1. **Timeline:**
   ```bash
   git log --format="%as" --reverse origin/main | head -1    # first commit date
   git log --format="%as" origin/main | head -1               # most recent commit
   git log --oneline origin/main | wc -l                      # total commits
   ```

2. **Activity by month** (last 6 months):
   ```bash
   git log --format="%as" --since="6 months ago" origin/main | cut -d- -f1,2 | sort | uniq -c | sort -rn
   ```

3. **Contributors:**
   ```bash
   git shortlog -sn --no-merges origin/main | head -10
   ```

4. **PR velocity** (from pre-fetched data):
   - Count merged PRs per month
   - Identify any open PRs that are stale (>2 weeks old, no activity)

5. **Commit message patterns:**
   ```bash
   git log --oneline --since="3 months ago" origin/main | head -40
   ```
   Look for: conventional commits, feature/fix/refactor ratio, common prefixes

### Step 4: Scan Code Implementation

Map what's actually implemented vs. what's claimed in docs:

1. **Module inventory:**
   - List all top-level packages/modules with line counts
   - Identify entry points (main files, CLI, API endpoints)
   - Flag any placeholder/stub files (files with `TODO`, `NotImplementedError`, `pass`, `not_configured`)

2. **Test coverage signals:**
   - Count test files vs source files (ratio)
   - Check for test configuration (pytest.ini, jest.config, etc.)
   - Look for CI test commands in workflow files
   - Flag source modules with no corresponding test file

3. **Dependency health:**
   - Count direct dependencies
   - Check for pinned vs unpinned versions
   - Look for deprecated packages (if recognizable)

4. **Infrastructure completeness:**
   - CI/CD: Are there workflow files? Do they run tests?
   - Docker: Is there a Dockerfile? Is it used?
   - Linting: Is there a linter config (.eslintrc, ruff.toml, .golangci.yml)?

### Step 5: Cross-Reference and Identify Gaps

Compare what's **claimed** (docs, README, CLAUDE.md) with what's **actual** (code, tests, git):

**For each claimed feature/capability:**
1. Is there corresponding code? → If not, mark as **CLAIMED BUT MISSING**
2. Is there a test for it? → If not, mark as **UNTESTED**
3. Has it been touched recently (last 30 days)? → If not, mark as **POTENTIALLY STALE**
4. Is there a merged PR for it? → If yes, mark as **VERIFIED DONE**

**For each priority item in CLAUDE.md / roadmap:**
1. Is there evidence of progress (commits, PRs, branches)?
2. Is it blocked by something?
3. Has the priority shifted (newer commits suggest different focus)?

**Documentation-reality mismatches:**
- File paths referenced in docs that don't exist
- Features described in README that aren't implemented
- Architecture docs that don't match current code structure
- Stale dates or version references

### Step 6: Generate the Report

Write the report using this template:

```markdown
# Project Status Analysis

**Project:** {{project_name}}
**Analyzed:** {{today}}
**Planning horizon:** {{horizon}}
**Repository:** {{remote_url}}

---

## Project Snapshot

| Metric | Value |
|--------|-------|
| First commit | {{first_commit_date}} |
| Total commits | {{total_commits}} |
| Contributors | {{contributor_count}} |
| PRs merged (last 90d) | {{merged_pr_count}} |
| Source files | {{source_file_count}} |
| Test files | {{test_file_count}} |
| Documentation files | {{doc_file_count}} |
| Dependencies | {{dep_count}} |

### Activity Trend (last 6 months)

```
{{monthly_commit_counts_as_bar_chart}}
```

---

## What's Done (Achievements)

Group achievements by category. For each, cite evidence (PR, commit, or code path).

### {{Category 1}} (e.g., Core Architecture)
- **{{Feature}}** — {{one-line description}} | Evidence: PR #{{N}}, `{{file_path}}`
- ...

### {{Category 2}} (e.g., Testing)
- ...

### {{Category 3}} (e.g., Documentation)
- ...

---

## What's Missing (Gaps)

Rank gaps by severity: CRITICAL > MAJOR > MODERATE > MINOR

### CRITICAL — Blocks core functionality or proof of value
{{#each critical_gaps}}
- **{{gap_name}}**: {{description}}
  - **Expected:** {{what_docs_claim}}
  - **Actual:** {{what_code_shows}}
  - **Impact:** {{why_it_matters}}
{{/each}}

### MAJOR — Significant capability missing
{{#each major_gaps}}
- **{{gap_name}}**: {{description}}
{{/each}}

### MODERATE — Quality/completeness issues
{{#each moderate_gaps}}
- **{{gap_name}}**: {{description}}
{{/each}}

### MINOR — Polish, nice-to-have
{{#each minor_gaps}}
- **{{gap_name}}**: {{description}}
{{/each}}

---

## Documentation Health

| Issue Type | Count | Examples |
|------------|-------|---------|
| Stale references | {{N}} | {{examples}} |
| Missing file paths | {{N}} | {{examples}} |
| Outdated dates | {{N}} | {{examples}} |
| Feature claims without code | {{N}} | {{examples}} |

---

## Recommended Focus (next {{horizon}})

Based on gap severity, project trajectory, and stated priorities:

### Top Priority (do first)
1. **{{task}}** — {{rationale}}
   - Estimated effort: {{S/M/L}}
   - Unblocks: {{what_it_enables}}

### Should Do
2. **{{task}}** — {{rationale}}
3. **{{task}}** — {{rationale}}

### Can Wait
4. **{{task}}** — {{rationale}}
5. **{{task}}** — {{rationale}}

---

## Branch / PR Landscape

### Open PRs Needing Attention
{{#each open_prs}}
- PR #{{number}} — {{title}} ({{age}}, {{status}})
{{/each}}

### Stale Branches (no activity >30 days)
{{#each stale_branches}}
- `{{branch}}` — last commit {{date}}, {{behind}} behind main
{{/each}}

---

## Raw Data

<details>
<summary>Module inventory (click to expand)</summary>

| Module | Files | Lines | Tests | Last Modified |
|--------|-------|-------|-------|---------------|
{{#each modules}}
| `{{name}}` | {{files}} | {{lines}} | {{test_status}} | {{last_modified}} |
{{/each}}

</details>

<details>
<summary>Commit activity by month</summary>

| Month | Commits | PRs Merged |
|-------|---------|------------|
{{#each months}}
| {{month}} | {{commits}} | {{prs}} |
{{/each}}

</details>
```

### Step 7: Write Report and Display Summary

1. **Write the full report** to `docs/project-status/{{today_YYYY-MM-DD}}.md`
   - Create the directory if it doesn't exist
   - If not in a git repo, display only (skip file write)

2. **Display a condensed summary in chat** (~30 lines max):
   - Project snapshot (key metrics)
   - Top 3 achievements
   - Top 3 gaps (with severity)
   - Recommended focus for the planning horizon
   - Path to the full report

### Edge Cases

- **Not a git repo:** Skip git analysis entirely. Analyze only file structure and docs.
- **No README or CLAUDE.md:** Note as a gap. Proceed with code-only analysis.
- **Monorepo:** If multiple `package.json` / `pyproject.toml` found, ask which sub-project to analyze, or analyze the one at the repo root.
- **Very large repo (>10k files):** Use `--quick` mode automatically. Sample rather than exhaustively scan.
- **No PRs / gh unavailable:** Skip PR analysis. Note in report.
- **Empty repo:** Report "project is empty" with suggested first steps.

### Focus Area Filters (`--focus`)

When `--focus` is specified, only run the relevant steps:

| Focus | Steps to run |
|-------|-------------|
| `docs` | Steps 2, 5 (doc-reality cross-ref), 6 (doc health section) |
| `code` | Steps 4, 5 (code gaps), 6 (module inventory) |
| `tests` | Steps 4.2, 5 (untested modules), 6 (test coverage) |
| `infra` | Steps 1.5, 4.4, 6 (CI/CD section) |
| `git` | Steps 3, 6 (activity trend, branch landscape) |
