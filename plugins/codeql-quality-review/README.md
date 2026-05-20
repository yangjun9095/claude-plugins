# codeql-quality-review

Audit and fix CodeQL **Code Quality** findings on `/security/quality` (Standard + AI tabs).

## Why this exists

GitHub's Code Quality findings aren't exposed via the public REST API — only the UI shows them. This plugin works around that by deploying a manual GitHub Actions workflow that runs CodeQL with the Python code-quality suites and uploads the SARIF as a downloadable workflow artifact.

## Install

```bash
/plugin marketplace add yangjun9095/claude-plugins
/plugin install codeql-quality-review@yangjun9095-plugins
```

## Usage

In a working git checkout of the target GitHub repo:

```
/codeql-quality-review
```

Or with options:

- `/codeql-quality-review --branch <branch>` — run on a specific branch
- `/codeql-quality-review --dry-run` — just deploy + trigger + parse; don't fix
- `/codeql-quality-review --fix-only` — assume SARIF already present; jump to fix loop

The skill will:

1. Check prerequisites (`gh` auth, repo state)
2. Deploy `.github/workflows/codeql-quality-artifact.yml` to the target branch (opens a PR if needed)
3. Trigger the workflow + wait
4. Download the SARIF, parse it, and group findings by rule
5. Categorize findings by severity tier and recommend actions (fix vs dismiss)
6. Apply fixes per `references/rule-fixes.md`
7. Re-scan + verify; iterate until 0 or stable
8. Open a PR with a summary

## What's in the box

| File | Purpose |
|---|---|
| `commands/codeql-quality-review.md` | The slash-command instructions Claude follows |
| `scripts/codeql-quality-artifact.yml` | The GitHub Actions workflow file that gets deployed to target repos |
| `scripts/parse_sarif.py` | Standalone Python script to summarize a SARIF file by rule + location |
| `references/rule-fixes.md` | Rule-by-rule fix playbook (uses ruff where possible; documents known false-positive caveats) |

## Known limitations

- **Python only.** For other languages, swap the query-suite name in the workflow (e.g., `codeql/javascript-queries:codeql-suites/javascript-code-quality.qls`).
- **Doesn't surface Copilot Autofix suggestions** that aren't part of a CodeQL query suite. Those live in a separate UI-only data store.
- **`py/unused-parameter` findings are mostly false positives** — see `references/rule-fixes.md` for the dismissal pattern.

## Development notes

This plugin was extracted from a multi-session publication-prep code review of [czbiohub-sf/DanioDecima](https://github.com/czbiohub-sf/DanioDecima) where the Code Quality vs Security CodeQL API gap was discovered and worked around. The flow has been validated on multiple iterations of that repo.
