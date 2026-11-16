---
allowed-tools:
  - Read
  - Write
  - Glob
  - Grep
  - Bash(python3 *)
  - Bash(python *)
  - Bash(ls *)
  - Bash(find * -name)
  - Bash(find * -maxdepth)
  - Bash(du *)
  - Bash(stat *)
  - Bash(date *)
  - Bash(hostname *)
  - Bash(git log *)
  - Bash(git status *)
  - Bash(git diff --stat *)
description: "Email a threaded status/report from this session — for long or unattended runs. Sends via a local MTA (no OAuth, no API key)."
---

# Email Report

Send the user a readable report of what this session did, as an email that **threads** with earlier
reports from the same run. Built for long or unattended work where the user is not watching.

**Arguments:** `$ARGUMENTS`

Forms:
- `/email-report` — report on this session; infer subject from the project
- `/email-report 3/8 scoring` — with a stage tag
- `/email-report -- me@lab.org` — explicit recipient
- `/email-report --check` — just test whether this host can send mail at all

---

## Step 0: Preflight — do this FIRST, always

Delivery depends on an MTA listening on `localhost:25`. Many HPC and cluster nodes have one;
**laptops and containers usually do not.** Check before composing anything, so you do not write a
long report and then discover it cannot be sent:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/send_report_email.py" --check
```

- `OK` → continue.
- `FAIL … refused` → there is no local MTA. **Stop and tell the user plainly**, offer the options:
  send from a cluster node, pass `--smtp-host <relay>` if they know a reachable relay, or write the
  report to a file instead. Do not silently give up, and do not try to substitute an unrelated
  email tool without saying so.

If the user passed `--check`, report the result and stop here.

## Step 1: Work out recipient and subject

| | source, in order |
|---|---|
| recipient | `$ARGUMENTS` after `--` → `$EMAIL_REPORT_TO` → **ask the user** |
| subject | `$ARGUMENTS` → `$EMAIL_REPORT_SUBJECT` → propose one from the repo/project name |

**The subject must stay constant across a run** — it is what the reader's client groups on. If a
thread file already exists (below), reuse the subject already in use rather than inventing a new one.

## Step 2: Decide on threading

Threading is what turns 12 mails into one conversation. Pass `--thread-file <path>`, using a stable
per-project location, e.g. `.email-report-thread` at the repo root or beside the campaign's
bookkeeping. It accumulates Message-IDs; the script handles `In-Reply-To`/`References`.

- **Same logical run** (stage 1, stage 2, …) → same thread file, same subject.
- **Unrelated one-off** → omit `--thread-file` so it stands alone.
- Add the thread file to `.gitignore` — it is per-clone state, not shared history.

## Step 3: Write a report worth reading

This is the part that matters, and the part that is usually done badly. **Do not send "task
complete."** Write what a colleague who was asleep needs in order to act.

Include, in this order:

1. **The headline, first line.** What is true now that was not before. If something failed, that is
   the headline.
2. **Numbers, with their units and n.** "ipTM 0.87 across 24 designs", not "good results".
3. **What you changed** — files, commits, jobs submitted.
4. **What is still running or queued**, with how to check it.
5. **What you could not do, and why.** Blocked, skipped, or uncertain items belong in the mail, not
   only in your head. A report that omits the failures is worse than no report.
6. **Filepaths for anything not attached.** Absolute paths.

Prefer plain text with short sections and a blank line between them. The body is read in a mail
client, so avoid wide tables and heavy markdown; simple aligned columns survive, pipe tables do not.

Write the body to a temp file and pass `--body-file` rather than shell-quoting a long string —
backticks and quotes in a `--body` argument will be mangled by the shell.

## Step 4: Attachments — budget-aware

The cap is **7 MB raw (~9.4 MB encoded)** by default, because MIME inflates by ~4/3 and relays
reject oversized payloads with `552 5.3.4 Message size exceeds fixed limit`.

- Attach small artefacts that carry the argument: a key figure, a results CSV, a compressed PDF.
- **Do not attach movies or large binaries.** Reference them by absolute path in the body.
- Anything over budget is skipped automatically and **named in the body with its path** — so the
  reader learns it exists. Check the script's output line for `SKIPPED` and make sure that is what
  you intended.
- If the user asked for something large, consider producing a smaller variant (downscaled figure,
  compressed PDF) and say in the body that the full-resolution version is on disk.

## Step 5: Send

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/send_report_email.py" \
  --to "<recipient>" \
  --subject "<constant subject>" \
  --stage "<short tag>" \
  --body-file /tmp/report.txt \
  --thread-file .email-report-thread \
  --attach fig.png
```

Useful flags:

| flag | when |
|---|---|
| `--dry-run` | build and size the message without sending — good for checking the attachment budget |
| `--lenient` | exit 0 even on failure; for unattended pipelines where a stage must not die. **Accepts silent loss** — do not use interactively |
| `--smtp-host` / `--smtp-port` | a relay other than `localhost:25` |
| `--max-attach-mb` | if you know the relay's real limit |

## Step 6: Confirm to the user

Report the actual outcome, including the thread position and any skipped attachments. If the send
failed, say so — **never imply a mail went out when it did not.** The script prints one summary
line; relay that faithfully rather than paraphrasing it as success.
