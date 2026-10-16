# codeql-quality-review

Audit and fix the CodeQL Code Quality findings of a GitHub repository.

## How it works

The command reads the findings with `gh api` from the GitHub REST endpoint `GET /repos/{owner}/{repo}/code-quality/findings`.
A bundled script summarizes the JSON by severity, category, rule and file.
The command then fixes the findings in your working tree and fetches them again to confirm the result.

The API is a public preview on github.com. It is not available on GitHub Enterprise Server.
GitHub announced the endpoints on 2026-06-23. The documentation covers CodeQL findings and does not mention the AI tab of `/security/quality`.

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

1. Check `gh auth status` and resolve the repository with `gh repo view`.
2. Fetch the open findings with `gh api --paginate`.
3. Summarize them with `scripts/summarize_findings.py` and compare the total with the web page.
4. Group the findings by tier and recommend an action for each tier.
5. Apply the fixes with the playbook in `references/rule-fixes.md`.
6. Ask you to merge the fix. Then fetch the findings again and compare the totals.

The API returns an error status in three documented cases. The command gives a specific message for each:

- 403: Code Quality is off for the repository, or the token lacks access.
- 404: The repository name is wrong, or the preview is not enabled.
- 503: The service is unavailable. Retry later.

## Read-only use of GitHub

Every `gh api` call in the command is a GET.
The command never passes `-X` with another method, and it never passes `-f`, `-F` or `--input`.
The command never closes or dismisses a finding, and it never merges a pull request.
You dismiss false positives in the web interface.

The `allowed-tools` list in the command grants `gh api`, `gh auth status`, `gh repo view`, `gh run list`, `gh run view`, `gh run download`, `gh workflow run`, `python3` and the git read commands. It does not grant a blanket `gh *`.

## Fallback: the SARIF workflow

Use the fallback in these cases:

- The host is GitHub Enterprise Server.
- The AI tab shows findings that the API did not return.
- You pass `--fallback`.

The workflow `scripts/codeql-quality-artifact.yml` runs the Python code-quality and code-quality-extended query suites. It uploads the SARIF files as the artifact `codeql-quality-sarif`.
The command triggers the workflow with `gh workflow run`, downloads the artifact with `gh run download`, and parses it with `scripts/parse_sarif.py`.
GitHub needs the workflow file on the default branch before it can trigger the workflow.

## What is in the plugin

| File | Purpose |
|---|---|
| `commands/codeql-quality-review.md` | The slash-command instructions Claude follows |
| `scripts/summarize_findings.py` | Summarizes the JSON from the API. It reads a file or standard input |
| `scripts/codeql-quality-artifact.yml` | The fallback workflow that gets deployed to the target repository |
| `scripts/parse_sarif.py` | Summarizes the SARIF files of the fallback by rule and location |
| `references/rule-fixes.md` | The fix playbook per rule, with known false-positive cases |
| `tests/test_summarize_findings.py` | Unit tests for the summary script |

## Summary script

`scripts/summarize_findings.py` accepts three input shapes:

- One JSON array of findings.
- Several JSON arrays one after another, with one array per page.
- One array of arrays. This is what `gh api --paginate --slurp` prints.

On 2026-10-16, `gh` 2.87.3 printed one merged array for `gh api --paginate` and an array of arrays with `--slurp`.
The check used a different array endpoint (the public repository list of a user). The script reads all three shapes, so it does not depend on the `gh` version.

It prints the total and the counts by severity, category and rule. It also prints the ten files with the most findings. Then it prints one line per finding as `path:start_line: rule-id: message`.
It exits with code 0 on success. It exits with code 2 and a one-line message on stderr for unreadable or non-finding input.

Run the tests from the plugin directory:

```bash
python3 -B -m unittest discover -s tests
```

## Verification status

The endpoint schema comes from the GitHub documentation. The tests use made-up findings that follow that schema.
On 2026-10-16 the author sent read-only GET requests for 8 of the author's repositories. All 8 returned HTTP 404, so no live response has been seen.
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
- The command no longer grants `Bash(gh *)`, `Bash(git *)` or the other broad shell rules of 1.0.0.
- `scripts/parse_sarif.py` runs on Python 3.6.

## Development notes

The plugin came from a multi-session publication-prep code review of [czbiohub-sf/DanioDecima](https://github.com/czbiohub-sf/DanioDecima).
In that review, the Code Quality findings had no REST endpoint. The first version of this plugin worked around the gap with the SARIF workflow.
