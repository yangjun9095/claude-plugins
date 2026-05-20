---
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - Grep
  - Bash(git *)
  - Bash(gh *)
  - Bash(curl *)
  - Bash(mkdir *)
  - Bash(ls *)
  - Bash(cat *)
  - Bash(head *)
  - Bash(tail *)
  - Bash(grep *)
  - Bash(find *)
  - Bash(sed *)
  - Bash(awk *)
  - Bash(wc *)
  - Bash(python3 *)
  - Bash(date *)
  - Bash(echo *)
  - Bash(sleep *)
description: Audit a GitHub repo's CodeQL Code Quality findings (Standard + AI tabs at /security/quality) and fix them. Works around the lack of public REST API for code-quality results by deploying a manual workflow that uploads SARIF as a downloadable artifact.
---

# CodeQL Quality Review

Audit and fix the CodeQL **Code Quality** findings on a GitHub repo's `/security/quality` page (Standard + AI tabs).

**Argument:** `$ARGUMENTS`

Modes (optional):
- `/codeql-quality-review` → full flow on the current repo's default branch
- `/codeql-quality-review --branch <branch>` → run on a specific branch
- `/codeql-quality-review --dry-run` → just deploy workflow + trigger + parse; don't fix
- `/codeql-quality-review --fix-only` → assume workflow + SARIF already present; jump to fix-and-recheck loop

## Why this skill exists

GitHub's Code Quality findings (the `/security/quality` page, Standard + AI tabs) are
**not exposed via the public REST API**. The standard `/code-scanning/alerts`
endpoint only returns Security CodeQL — Code Quality SARIF is uploaded to a
separate UI-only endpoint.

This skill bypasses that by deploying a manual GitHub Actions workflow that
runs CodeQL with the `python-code-quality.qls` and `python-code-quality-extended.qls`
suites, then uploads the SARIF as a regular workflow artifact you can download
and parse locally.

## Prerequisites (check before starting)

1. **`gh` CLI authenticated** with at least `repo` scope. Verify:
   ```bash
   gh auth status
   ```
2. **Working directory is a git checkout** of the target repo (or use `-R owner/repo` consistently).
3. **The repo has CodeQL enabled** (default setup OR advanced — either works; this skill runs alongside).
4. **`python3` available locally** for SARIF parsing (no extra deps needed; stdlib only).

If any prerequisite is missing, surface it to the user before proceeding.

## Reference material

This skill bundles two helpers (you can read them directly via `Read`):
- `scripts/codeql-quality-artifact.yml` — the GitHub Actions workflow file to deploy
- `scripts/parse_sarif.py` — Python script that summarizes a SARIF file (count by rule, detail per location)
- `references/rule-fixes.md` — playbook of fixes per CodeQL rule (USE THIS when deciding how to address each finding)

Always read `references/rule-fixes.md` early — it has the rule-to-action mapping and known false-positive caveats.

## Steps

### Step 0 — Identify target repo and branch

- Determine `OWNER/REPO` from `gh repo view --json owner,name --jq '.owner.login + "/" + .name'`.
- Determine target branch from `$ARGUMENTS` (`--branch <branch>`) or default to the repo's default branch (`gh repo view --json defaultBranchRef`).
- Confirm with the user (one short sentence).

### Step 1 — Deploy the workflow file (if not already present)

Check if `.github/workflows/codeql-quality-artifact.yml` exists on the target branch.

If absent:
1. Read the workflow template from the plugin's `scripts/codeql-quality-artifact.yml`.
2. Write it to `.github/workflows/codeql-quality-artifact.yml` in the working tree.
3. Open a PR via `gh pr create` and ask the user to merge. **The workflow must be on the default branch to be triggerable** — even though you can `gh workflow run --ref <other>` to use a different branch's *definition*, GitHub Actions requires the workflow file to exist on the default branch for it to register at all.

If present: skip to Step 2.

### Step 2 — Trigger + wait

```bash
gh workflow run codeql-quality-artifact.yml --ref <branch>
```

Note the run ID from the URL in the output. Then poll with `gh run view <id> --json status,conclusion`. CodeQL DB build + analyze typically takes 2–4 minutes for small/medium Python repos.

For long waits, use `ScheduleWakeup` for ~3–5 minute checks instead of busy-polling.

If the workflow run fails:
- Most common cause: CodeQL CLI download URL changed. Check the "Install CodeQL CLI" step log. The official asset name is `codeql-linux64.zip` (NOT `.tar.gz`). If GitHub changes the format, update the workflow template.
- Surface the error to the user; offer to fix the workflow template.

### Step 3 — Download SARIF + parse

```bash
mkdir -p /tmp/claude/codeql-sarif
gh run download <run-id> --name codeql-quality-sarif --dir /tmp/claude/codeql-sarif
python3 <plugin>/scripts/parse_sarif.py \
    /tmp/claude/codeql-sarif/quality.sarif \
    /tmp/claude/codeql-sarif/quality-extended.sarif
```

The output reports findings grouped by rule and per location.

### Step 4 — Itemize findings and prioritize

Group findings by **severity tier** (this maps to user intent):

1. **Reliability bugs** (real or near-real bugs): `py/uninitialized-local-variable`, `py/empty-except`, `py/raise-not-implemented`, `py/non-standard-exception-special-method`, `py/call/wrong-named-argument`, `py/unreachable-statement` — **fix these first**.
2. **Shadowing / clarity issues**: `py/local-shadows-global`, `py/redundant-comparison` — **fix next** (usually one-line renames).
3. **Auto-fixable maintainability**: `py/unused-import` (`ruff F401`), `py/unused-local-variable` (`ruff F841`), `py/ineffectual-statement` (mostly notebook cell-output displays — wrap in `print()` and update BOTH `.py` and `.ipynb`), `py/explicit-returns-mixed-with-implicit-returns` (`ruff RET503`), `py/commented-out-code` (manual review — delete obvious dead blocks).
4. **False-positive prone** (`py/unused-parameter`, `py/local-shadows-global` in tight scopes): consult `references/rule-fixes.md`. Often the right action is to **dismiss in the UI** rather than rename — especially for PyTorch Lightning callback signatures.

Surface the breakdown to the user with the recommended action per tier. Get explicit OK before bulk-fixing.

### Step 5 — Apply fixes

Per the playbook in `references/rule-fixes.md`. Use the project's environment's `ruff` if available (find via `which ruff` or check common conda env paths like `~/.conda/envs/<env>/bin/ruff`).

**Key gotchas to internalize:**

- ❌ **Do NOT use `git add -A`** — untracked files from other branches sneak into commits. Always `git add <explicit-files>`.
- ❌ **Do NOT prefix unused parameters with `_`** to silence `py/unused-parameter` — CodeQL doesn't respect the convention AND the rename breaks callers that use kwarg syntax. Either remove the param entirely (verify no kwarg callers via `grep -rn 'PARAM='`) or dismiss the alert.
- ✅ **Notebook fixes go in BOTH `.py` and `.ipynb`** — if you edit only the `.py`, the next `jupytext --sync` reverts your fix.
- ✅ **`ruff` understands `.ipynb`** — you can pass notebook paths directly: `ruff check --fix --select F401 notebook.ipynb`.
- ✅ **Commit at logical boundaries**, not in one mega-commit — easier to bisect if something breaks.

### Step 6 — Re-scan + verify

Trigger the workflow again (Step 2), wait, download SARIF (Step 3), and confirm the count dropped.

Iterate until the count is 0 or stable at a set of dismissable false-positives. Surface the remaining items + their rule IDs to the user so they can dismiss in the `/security/quality` UI.

### Step 7 — Open PR + clean up

If working on a non-default branch:
1. Push the branch.
2. Open a PR via `gh pr create` with a clear title and body summarizing:
   - Initial findings count + breakdown by rule
   - What was fixed (per file or per rule, with brief justification)
   - What was deferred for dismissal (with reasons)
   - Final SARIF run URL(s) as evidence
3. Wait for merge confirmation from user.

The workflow file itself stays in the repo — leave it. It's manual-trigger only and has zero CI cost when idle.

## Output / report

At the end, write a short status report to the user (≤ 200 words) covering:
- Initial vs final finding count (Standard + Extended)
- Categorized list of remaining findings + recommended UI dismissal reasons
- Link(s) to the PRs you opened
- The workflow URL for future manual re-scans

## Out-of-scope / known limitations

- **Non-Python languages**: this skill targets Python. For JavaScript / TypeScript / Java / Go, swap the query-suite names in the workflow (e.g., `codeql/javascript-queries:codeql-suites/javascript-code-quality.qls`) and update the Code DB language argument.
- **AI-only findings (Copilot Autofix)**: the workflow's SARIF contains the Standard + Extended code-quality findings — most "AI tab" findings come from the extended suite. If the user reports an AI finding that doesn't appear in either SARIF, it may be a Copilot Autofix suggestion attached to an existing Security alert (see the regular `/security/code-scanning` page). In that case, ask the user to share the specific finding text/file path.
- **Default Setup vs Advanced Setup**: this skill works alongside Default Setup. If the user has Advanced Setup with a custom CodeQL config, ensure the manual workflow doesn't conflict with the category name (use `category: /code-quality:python` or similar to avoid overlap).
