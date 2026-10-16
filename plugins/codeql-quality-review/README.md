# codeql-quality-review

Audit and fix the CodeQL Code Quality findings of a GitHub repository.

## How it works

The command reads the findings with `gh api` from the GitHub REST endpoint `GET /repos/{owner}/{repo}/code-quality/findings`.
A bundled script summarizes the JSON by severity, category, rule and file.
The command then fixes the findings in your working tree and fetches them again to confirm the result.

The GitHub changelog entry of 2026-06-23 announces the endpoints as a public preview on github.com. The entry says they are not available on GitHub Enterprise Server. The REST documentation page does not state either point.
Source: https://github.blog/changelog/2026-06-23-fetch-code-quality-findings-via-rest-api
The documentation covers CodeQL findings and does not mention the AI tab of `/security/quality`.
On 2026-10-16, one repository returned HTTP 200 with 0 findings for `state=open`, `state=dismissed` and no `state`. This confirms the endpoint, the version header and the empty-response path.

A fallback path stays in the plugin for findings the API does not return. It deploys a manual GitHub Actions workflow that uploads CodeQL SARIF files as a workflow artifact. A second script parses the SARIF files.

## Install

```bash
/plugin marketplace add yangjun9095/claude-plugins
/plugin install codeql-quality-review@yangjun9095-plugins
```

## Requirements

- The `gh` CLI, signed in to github.com. A classic token needs the `repo` scope (`public_repo` for a public repository).
- Code Quality enabled on the repository, with access to the public preview.
- Python 3.6 or later for the bundled scripts. They use only the standard library.

## Usage

Run the command in a git checkout of the target repository:

```
/codeql-quality-review
```

Options:

- `/codeql-quality-review --dry-run`: fetch and summarize the findings. Edit nothing.
- `/codeql-quality-review --include-dismissed`: also fetch the dismissed findings and report their count.
- `/codeql-quality-review --fallback`: skip the API and use the SARIF workflow.
- `/codeql-quality-review --branch <branch>`: choose the branch for a fallback workflow run. The API has no branch parameter.

The command runs these steps:

1. Check `gh auth status`. Resolve the repository, its host and its default branch with `gh repo view`.
2. Check the current branch. On the default branch, the command plans a branch named `fix/codeql-quality-<date>`. On another branch, it asks you which branch gets the fixes.
3. Fetch the open findings with `gh api --paginate`.
4. Summarize them with `scripts/summarize_findings.py` and compare the total with the web page.
5. Group the findings by tier and recommend an action for each tier.
6. Apply the fixes with the playbook in `references/rule-fixes.md`.
7. Ask you to merge the fix. Then fetch the findings again into a second file and compare the totals.

Commits, pushes and pull request creation prompt you for permission. The `ruff`, test and `grep` commands of the fix step can prompt as well.

The API returns an error status in three documented cases. The command gives a specific message for each:

- 403: Code Quality is off for the repository, or the token lacks access. The run stops until you choose to fix the access or use the fallback.
- 404: The repository name is wrong, or the preview is not enabled. The run stops until you choose to fix the setup or use the fallback.
- 503: The service is unavailable. Retry later. The command does not start the fallback.

## Read-only use of GitHub

Every `gh api` call in the command is a GET.
The command never passes `-X` with another method, and it never passes `-f`, `-F` or `--input`.
The command never closes or dismisses a finding, and it never merges a pull request.
You dismiss false positives in the web interface.

The `allowed-tools` list in the command grants `gh api`, `gh auth status` (without options), `gh repo view`, `gh run list`, `gh run view`, `gh run download` and `gh workflow run`.
It grants `python3` only for the two bundled scripts, `summarize_findings.py` and `parse_sarif.py`. It grants four exact git commands: `git branch --show-current`, `git status --short`, `git switch -c fix/codeql-quality-*` and `git diff`. It also grants `date +%Y-%m-%d`.
It does not grant a blanket `gh *` or a blanket `python3 *`. The two script patterns use a `*` before the script name, so `python3 -c '...' summarize_findings.py` would match them. The patterns narrow the grant and do not block a determined misuse.

## Fallback: the SARIF workflow

Use the fallback in these cases:

- The host is GitHub Enterprise Server.
- The AI tab shows findings that the API did not return.
- You pass `--fallback`.
- The API returned 403 or 404, and you choose the fallback.

The workflow `scripts/codeql-quality-artifact.yml` runs the Python code-quality and code-quality-extended query suites. It uploads the SARIF files as the artifact `codeql-quality-sarif`.
The command triggers the workflow with `gh workflow run`, downloads the artifact with `gh run download`, and parses it with `scripts/parse_sarif.py`.
GitHub needs the workflow file on the default branch before it can trigger the workflow.
The SARIF output has no severity, category or finding number. Step 3 of the command then uses the rule ids alone.

## What is in the plugin

| File | Purpose |
|---|---|
| `commands/codeql-quality-review.md` | The slash-command instructions Claude follows |
| `scripts/summarize_findings.py` | Summarizes the JSON from the API. It reads a file or standard input |
| `scripts/codeql-quality-artifact.yml` | The fallback workflow that gets deployed to the target repository |
| `scripts/parse_sarif.py` | Summarizes the SARIF files of the fallback by rule and location |
| `references/rule-fixes.md` | The fix playbook per rule, with known false-positive cases |
| `tests/test_summarize_findings.py` | Unit tests for the summary script |
| `tests/test_parse_sarif.py` | Tests that run `parse_sarif.py` in an ASCII locale |

## Summary script

`scripts/summarize_findings.py` accepts three input shapes:

- One JSON array of findings.
- Several JSON arrays one after another, with one array per page.
- One array of arrays. This is what `gh api --paginate --slurp` prints.

On 2026-10-16, `gh` 2.87.3 printed one merged array for `gh api --paginate` and an array of arrays with `--slurp`.
The check used a different array endpoint (the public repository list of a user). The script reads all three shapes, so it does not depend on the `gh` version.

It prints the total and the counts by severity, category and rule. Each rule line shows the severity and the category. It also prints the ten files with the most findings.
Then it prints one line per finding as `#number path:start_line: rule-id: message`. The number works with the single-finding endpoint `GET /repos/{owner}/{repo}/code-quality/findings/{number}`.
The script prints `?` for a field that the input lacks, such as `start_line`.
It exits with code 0 on success. It exits with code 2 and a one-line message on stderr for unreadable or non-finding input.

Run the tests from the plugin directory:

```bash
python3 -B -m unittest discover -s tests
```

## Verification status

The endpoint schema comes from the GitHub documentation. The tests use made-up findings that follow that schema.
On 2026-10-16 the author sent read-only GET requests for 8 of the author's repositories. All 8 returned HTTP 404.
One other repository returned HTTP 200 with 0 findings. No live response with findings has been seen, so the summarizer has not run on real findings.
These points remain unverified:

- Whether the AI tab findings appear in the API.
- Whether `--paginate` follows the `Link` header of this endpoint.
- Which branch the findings describe, and when they update after a merge.
- The result of an omitted `state` parameter. The command always passes `state`.

## Known limits

- The fix playbook covers Python rules. The API documentation names no language limit.
- The fallback workflow targets Python. For another language, change the query suite and the database language in the workflow.
- `py/unused-parameter` findings are mostly false positives. `references/rule-fixes.md` describes the dismissal pattern.

## Changes in 2.0.0

- The API path replaces the workflow as the main path. The workflow is now the fallback.
- New script `scripts/summarize_findings.py` and its tests.
- The `--fix-only` option is gone, because a fetch is now one command. The `--branch` option applies to the fallback only.
- The command no longer grants `Bash(gh *)`, `Bash(git *)`, `Bash(python3 *)` or the other broad shell rules of 1.0.0.
- The command now says which branch gets the fixes and plans a `fix/codeql-quality-<date>` branch.
- `scripts/parse_sarif.py` runs on Python 3.6 and in an ASCII locale.

## Development notes

The plugin came from a multi-session publication-prep code review of [czbiohub-sf/DanioDecima](https://github.com/czbiohub-sf/DanioDecima).
In that review, the Code Quality findings had no REST endpoint. The first version of this plugin worked around the gap with the SARIF workflow.
