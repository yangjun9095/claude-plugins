---
allowed-tools:
  - Read
  - Edit
  - Write
  - Glob
  - Grep
  - Bash(gh api *)
  - Bash(gh auth status*)
  - Bash(gh repo view *)
  - Bash(gh run list *)
  - Bash(gh run view *)
  - Bash(gh run download *)
  - Bash(gh workflow run *)
  - Bash(python3 *)
  - Bash(git status*)
  - Bash(git diff*)
  - Bash(git log*)
  - Bash(git rev-parse*)
  - Bash(git branch --show-current)
description: Audit a GitHub repo's CodeQL Code Quality findings through the GitHub REST API (gh api) and fix them. A SARIF workflow is the fallback for findings the API does not return.
---

# CodeQL Quality Review

Audit and fix the CodeQL Code Quality findings of a GitHub repository.
The command fetches the findings with `gh api` and summarizes them with a bundled script.
It then fixes the findings in the working tree and re-checks the result.

**Argument:** `$ARGUMENTS`

Modes (all optional):
- `/codeql-quality-review`: fetch the open findings, fix them, and re-check.
- `/codeql-quality-review --dry-run`: fetch and summarize. Edit nothing.
- `/codeql-quality-review --include-dismissed`: also fetch the dismissed findings and report their count.
- `/codeql-quality-review --fallback`: skip the API and use the SARIF workflow in the Fallback section.
- `/codeql-quality-review --branch <branch>`: choose the branch for a fallback workflow run. The API has no branch parameter.

## Rules for every GitHub call

Every `gh api` call in this command is a GET.
Never pass `-X` or `--method` with a method other than GET.
Never pass `-f`, `-F`, `--field`, `--raw-field` or `--input`, because `gh api` then sends a POST.
Put every query parameter in the URL.
This command never closes or dismisses a finding.
This command never merges a pull request.
When a finding needs a dismissal, tell the user to dismiss it in the web interface.

## What the API covers

- `GET /repos/{owner}/{repo}/code-quality/findings` lists the findings of a repository.
- `GET /repos/{owner}/{repo}/code-quality/findings/{finding_number}` returns one finding.
- The API is a public preview on github.com. It is not available on GitHub Enterprise Server.
- The endpoints return CodeQL findings. The documentation does not mention the AI tab of `/security/quality`.
- Treat "the AI tab findings appear in the API" as unverified. Step 2 includes a check against the web page.
- The documentation does not say what an omitted `state` parameter returns. Always pass `state` in the URL.

Each finding has `number`, `state`, `url`, `rule`, `location`, `message` and `created_at`.
The `rule` object has `id`, `title`, `description`, `severity` (error, warning, note, none) and `category` (none, maintainability, reliability).
The `location` object has `path`, `start_line`, `start_column`, `end_line` and `end_column`.

## Reference material

Read these files with the `Read` tool:
- `${CLAUDE_PLUGIN_ROOT}/references/rule-fixes.md`: the fix playbook per CodeQL rule, with known false-positive cases. Read it before Step 3.
- `${CLAUDE_PLUGIN_ROOT}/scripts/summarize_findings.py`: summarizes the JSON from the API. Step 2 uses it.
- `${CLAUDE_PLUGIN_ROOT}/scripts/codeql-quality-artifact.yml`: the fallback workflow.
- `${CLAUDE_PLUGIN_ROOT}/scripts/parse_sarif.py`: summarizes the SARIF files of the fallback.

## Steps

### Step 0: Preflight

1. Run `gh auth status`. If it fails, ask the user to run `gh auth login`.
2. Check the host in the output. If it is not `github.com`, the API is not available. Go to the Fallback section.
3. A classic token needs the `repo` scope (`public_repo` for a public repository). For a fine-grained token, ask the user to read the documentation page of the endpoint.
4. Run `gh repo view --json nameWithOwner --jq .nameWithOwner`. This prints `OWNER/REPO`.
5. Tell the user the repository name in one sentence and continue.

### Step 1: Fetch the findings

Choose a temporary directory. Use the scratchpad directory if the session names one. Otherwise use `$TMPDIR`.

```bash
gh api --paginate \
  -H "X-GitHub-Api-Version: 2026-03-10" \
  -H "Accept: application/vnd.github+json" \
  "repos/OWNER/REPO/code-quality/findings?state=open&per_page=100" \
  > "<tmpdir>/codeql-findings-open.json"
```

With `--include-dismissed`, make a second call with `state=dismissed`. Write it to `<tmpdir>/codeql-findings-dismissed.json`.
Keep the two states in separate files. Summarize each file on its own.

If `gh` exits with an error, ignore the output file. `gh` prints the HTTP status on stderr, for example `gh: Not Found (HTTP 404)`. Handle the status like this:

- 403: GitHub denies access to Code Quality for this repository. Code Quality is off, or the token lacks access. Ask the user to check the repository settings and the token scope (`gh auth status`). If the message mentions a rate limit, wait and retry.
- 404: The repository name is wrong, or the Code Quality preview is not enabled for this repository. Check the name with `gh repo view`. Then ask the user to check that the preview is on.
- 503: GitHub reports that the service is unavailable. Tell the user to retry later.
- Any other status: show the message from `gh` and stop.

Pagination is unverified against a live repository. `--paginate` should follow the `Link` header.
If the total in Step 2 is a nonzero multiple of 100, check for a cut-off. Run the call again with `-i` and without `--paginate`. Read the `Link` header for a `next` link.

### Step 2: Summarize and check completeness

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/summarize_findings.py" "<tmpdir>/codeql-findings-open.json"
```

The script prints the total and the counts by severity, category and rule. It then prints the ten files with the most findings and one line per finding, grouped by rule.
It exits with code 2 and a one-line message when the file is not a list of findings. Show that message to the user.

The documentation does not say which branch the findings describe. Assume the default branch and tell the user.
Ask the user for the finding counts on `/security/quality`, on the Standard tab and on the AI tab.
If the AI tab shows more findings than the API returned, the API does not cover the AI tab. Offer the Fallback section.
If the total is 0 and the user sees findings on the web page, offer the Fallback section.

With `--dry-run`, stop here and write the report.

### Step 3: Itemize and prioritize

Use `category` and `severity` from the summary as a guide. Group the findings by tier:

1. Reliability bugs: `py/uninitialized-local-variable`, `py/empty-except`, `py/raise-not-implemented`, `py/non-standard-exception-special-method`, `py/call/wrong-named-argument`, `py/unreachable-statement`. Fix these first.
2. Shadowing and clarity issues: `py/local-shadows-global`, `py/redundant-comparison`. Fix these next. Most need a one-line rename.
3. Auto-fixable maintainability: `py/unused-import` (`ruff F401`), `py/unused-local-variable` (`ruff F841`), `py/ineffectual-statement`, `py/explicit-returns-mixed-with-implicit-returns` (`ruff RET503`), `py/commented-out-code`. For `py/ineffectual-statement`, wrap notebook cell displays in `print()` and update both the `.py` and the `.ipynb`. Review `py/commented-out-code` by hand and delete obvious dead blocks.
4. Findings that are often false positives: `py/unused-parameter`, and `py/local-shadows-global` in tight scopes. Read `references/rule-fixes.md`. Often the right action is a dismissal in the web interface, for example for PyTorch Lightning callback signatures.

Show the user the breakdown and the recommended action per tier. Get an explicit OK before you fix in bulk.

### Step 4: Apply the fixes

Follow `references/rule-fixes.md`. Use the `ruff` of the project environment if it exists. Find it with `which ruff` or in the conda environment directories.

- Run `git add` with explicit file names. Never run `git add -A`, because untracked files from other branches enter the commit.
- Do not prefix an unused parameter with `_`. CodeQL ignores that convention, and the rename breaks callers that pass the parameter by keyword. Remove the parameter after `grep -rn 'PARAM='` finds no keyword callers. Otherwise tell the user to dismiss the finding.
- Fix notebooks in both the `.py` and the `.ipynb`. An edit to the `.py` alone is lost at the next `jupytext --sync`.
- `ruff` accepts `.ipynb` paths, for example `ruff check --fix --select F401 notebook.ipynb`.
- Commit at logical boundaries. Only the git read commands are pre-approved, so each commit asks the user for permission.

### Step 5: Re-check

The API reports the findings that GitHub has analysed. Your local edits do not change them. The documentation does not say when the findings update after a merge.
Check the fixes locally first with `ruff` and the tests of the project.
Then ask the user to push the branch, open the pull request and merge it. This command never merges.
After the merge, wait for the Code Quality analysis to finish on the default branch. Repeat Step 1 and Step 2.
Compare the new total with the first total. List the findings that remain with their rule ids.
Stop when the total is 0 or when only false positives remain. Tell the user to dismiss those in the web interface.

### Step 6: Hand off

Ask the user before you push a branch or open a pull request. `git push` and `gh pr create` are not pre-approved.
A pull request body has four parts:
- The first count and its breakdown by rule.
- The fixes, per file or per rule, with a short reason.
- The findings left for dismissal, with the reason for each.
- The summary output from the final re-check.

## Fallback: the SARIF workflow

Use this section in one of three cases:
- The host is GitHub Enterprise Server.
- The API did not return findings that the AI tab shows.
- The user passes `--fallback`.

After a 403, 404 or 503, tell the user why the API call failed before you start this section.

The workflow `codeql-quality-artifact.yml` runs CodeQL with the Python code-quality query suites. It uploads the SARIF files as a workflow artifact. It does not change the code scanning results of the repository.
The workflow runs the standard and the extended suite. The playbook treats the extended suite as the source of the AI tab. That mapping is unverified.

1. Check that the workflow file exists on the default branch with `gh api repos/OWNER/REPO/contents/.github/workflows/codeql-quality-artifact.yml`. If the call returns 404, write the file from `scripts/codeql-quality-artifact.yml` on a new branch. Ask the user to push the branch and merge the pull request. GitHub needs the workflow file on the default branch before `gh workflow run` can trigger it.
2. Run `gh workflow run codeql-quality-artifact.yml --ref <branch>`. The branch defaults to the default branch. After the fixes, use the fix branch to check them before the merge.
3. Find the run with `gh run list --workflow codeql-quality-artifact.yml --limit 1 --json databaseId,status,conclusion`. Check it with `gh run view <id> --json status,conclusion`. The run takes a few minutes. Wait between checks with a scheduled wakeup if the session has one. Otherwise ask the user to tell you when the run ends.
4. If the run fails, read the log of the step "Install CodeQL CLI" first (`gh run view <id> --log-failed`). The release asset is `codeql-linux64.zip`. If GitHub changed the asset format, offer to update the workflow template.
5. Download and parse the SARIF files:

```bash
gh run download <run-id> --name codeql-quality-sarif --dir "<tmpdir>/codeql-sarif"
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/parse_sarif.py" \
  "<tmpdir>/codeql-sarif/quality.sarif" \
  "<tmpdir>/codeql-sarif/quality-extended.sarif"
```

6. Continue at Step 3 with these findings. For the re-check in Step 5, repeat items 2 to 5 on the fix branch.

The workflow file stays in the repository. It runs only when triggered by hand and costs nothing when idle.
If the repository uses a custom CodeQL configuration (Advanced Setup), give the upload a category such as `/code-quality:python`. This avoids an overlap with the existing category.

## Output

Write a short report for the user, at most 200 words:
- The first and final finding counts, and the path you used (API or fallback).
- The result of the AI tab check: done with the counts, or skipped.
- The remaining findings with their rule ids and a recommended dismissal reason for each.
- The links to the pull requests.

## Known limits

- The fix playbook covers Python rules. The API documentation names no language limit.
- The fallback workflow targets Python. For another language, change the query suite and the database language in the workflow. Example suite: `codeql/javascript-queries:codeql-suites/javascript-code-quality.qls`.
- The API documentation does not mention Copilot Autofix suggestions. A user can name a finding that neither the API nor the SARIF files contain. Then ask for the finding text and the file path.
