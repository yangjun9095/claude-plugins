# email-report

Email yourself a **threaded** status report from a long-running or unattended Claude session — so a
run that finishes at 3am is readable at 9am, and twelve stage reports arrive as one conversation
instead of twelve unrelated messages.

No OAuth, no API key, no MCP server. It hands the message to a mail relay already running on the
machine.

```bash
/email-report                    # report on this session
/email-report 3/8 scoring        # with a stage tag
/email-report --check            # can this host send mail at all?
```

## Check this first

Delivery needs an MTA listening on `localhost:25`.

```bash
python3 scripts/send_report_email.py --check
# [email-report] OK   localhost:25 reachable (NOOP 250)
```

**HPC login and compute nodes usually have one. Laptops and containers usually do not.** If you get
`refused`, this plugin cannot send from that host — run it from a cluster node, or point
`--smtp-host` at a relay you can reach. `--check` exists so you find that out in one second rather
than after writing a long report.

## Why not `mail`, or a Gmail integration?

- **`mail` / `mailx`** cannot set `Message-ID`, `In-Reply-To` or `References`, so every report
  arrives as its own conversation. Threading is the whole point.
- **Gmail-style integrations** need interactive OAuth, which hangs on headless nodes — and some
  expose only draft creation, with no way to actually send.

This uses Python's stdlib `smtplib` plus `email.message`, which also gives clean MIME attachments.

## Threading

`--thread-file` is a small state file accumulating every `Message-ID` sent. The first report starts
the thread; each later one replies to the newest and carries the whole `References` chain, which is
what Gmail groups on.

```bash
--thread-file .email-report-thread     # same file + same subject == one conversation
```

Keep the **subject constant** across a run; put the varying part in `--stage`, which appears in the
body. Add the thread file to `.gitignore` — it is per-clone state. Omit the flag for a one-off.

## Attachments

Capped at **7 MB raw (~9.4 MB encoded)**: MIME inflates by ~4/3 and relays reject oversized payloads
with `552 5.3.4 Message size exceeds fixed limit`.

Over-budget or missing files are **skipped and named in the body with their absolute path**, so the
reader learns the artefact exists and where to find it. Check the output line for `SKIPPED`.

Attach figures, CSVs, compressed PDFs. Reference movies and large binaries by path.

## Options

| flag | purpose |
|---|---|
| `--check` | test MTA reachability, send nothing |
| `--dry-run` | build and size the message without sending |
| `--stage` | short tag shown in the body, not the subject |
| `--thread-file` | state file that makes reports thread |
| `--lenient` | exit 0 even on failure, for unattended pipelines — **accepts silent loss** |
| `--smtp-host` / `--smtp-port` | a relay other than `localhost:25` |
| `--max-attach-mb` | override the budget if you know the relay's real limit |

Environment fallbacks so a project sets them once: `EMAIL_REPORT_TO`, `EMAIL_REPORT_SUBJECT`,
`EMAIL_REPORT_SMTP_HOST`, `EMAIL_REPORT_SMTP_PORT`.

## Exit status

**Non-zero on failure by default**, so an interactive caller notices. `--lenient` flips that for
pipelines where a stage must not die because mail was briefly down — at the cost of possible silent
loss. Choose deliberately.

## Compatibility

Pure standard library, **Python 3.6+**. The 3.6 floor is deliberate: on many HPC nodes the default
`python3` is 3.6, and a script needing 3.7+ syntax fails with a `SyntaxError` that looks nothing
like "wrong interpreter". Verified on 3.6.8 and 3.12.

## Two failure modes worth knowing

**`set_content` after `add_attachment` raises.** `add_attachment` converts the message to a
multipart, and `set_content` is then invalid. The script therefore decides what to attach *first*,
writes the body once, and attaches afterwards. The natural one-pass version crashes only when one
attachment succeeds *and* another is skipped — which is why it can hide for a long time.

**Silent success is the real risk.** With `--lenient`, a failed send returns 0. If you rely on these
reports to know a run finished, do not use `--lenient` without also checking stderr or the log.
