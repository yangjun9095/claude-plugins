#!/usr/bin/env python
"""Send a threaded status/report email from a long-running or unattended session.

Purpose
-------
Long agent runs are opaque while they happen. This mails a report per stage so the whole run
arrives as ONE email thread rather than a pile of unrelated messages, and so a run that finishes
at 3am is readable at 9am.

Why smtplib and not `mail`/`mailx`
----------------------------------
Real threading needs `Message-ID`, `In-Reply-To` and `References` headers. The RHEL `mailx` CLI
will not let you set them, so every message would arrive as its own conversation. Building the
message with `email.message` also gives clean MIME attachments for free.

How delivery actually works
---------------------------
It hands the message to an MTA on `localhost:25`. Many HPC/cluster nodes run one that accepts
unauthenticated mail and relays it onward -- no credentials, no OAuth, no API key. This is the
load-bearing assumption and the usual reason the script fails elsewhere: on a laptop or inside a
container there is typically NO local MTA, so the connection is refused.

    Run `--check` first. It tells you in one line whether this host can send at all.

Threading
---------
`--thread-file` is a small state file accumulating every Message-ID this thread has sent. The first
report starts the thread; each later one replies to the most recent and carries the whole
References chain, which is what Gmail groups on. Omit it and each message stands alone.

Attachment budget
-----------------
Capped on the BASE64-ENCODED size, not raw bytes: MIME inflates attachments by ~4/3, and relays
reject oversized payloads with `552 5.3.4 Message size exceeds fixed limit`. Anything over budget
is skipped and *named in the body with its path* rather than silently dropped, so the reader knows
a figure exists and where to find it.

Exit status
-----------
Non-zero on failure by DEFAULT, so an interactive caller notices. Pass `--lenient` for unattended
pipelines where a stage must not die because mail was briefly unavailable -- but know that you are
choosing possible silent loss.

Usage
-----
    python send_report_email.py --check
    python send_report_email.py --to me@lab.org --subject "run-42" \
        --stage "3/8 scoring" --body-file report.md --attach fig.png \
        --thread-file .mail_thread
"""

import argparse
import mimetypes
import os
import smtplib
import socket
import sys
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path
from typing import List, Tuple

# Env fallbacks so a project can set these once instead of repeating them on every call.
# Deliberately 3.6-compatible: on many HPC nodes the default `python3` is 3.6, and a plugin that
# needs 3.7+ syntax fails with a SyntaxError that looks nothing like "wrong interpreter".
if sys.version_info < (3, 6):
    sys.stderr.write("[email-report] needs Python 3.6+; got %s\n" % sys.version.split()[0])
    raise SystemExit(1)

ENV_TO = "EMAIL_REPORT_TO"
ENV_SUBJECT = "EMAIL_REPORT_SUBJECT"
ENV_HOST = "EMAIL_REPORT_SMTP_HOST"
ENV_PORT = "EMAIL_REPORT_SMTP_PORT"

DEFAULT_MAX_ATTACH_MB = 7.0  # ~9.4 MB encoded; sends reliably through typical relays
BASE64_OVERHEAD = 4 / 3


def check_mta(host, port, timeout=5.0):
    # type: (str, int, float) -> Tuple[bool, str]
    """Can this host hand off mail at all? Returns (ok, human-readable reason).

    Worth running before anything else: the single most common failure is that there is no local
    MTA, and the resulting traceback looks nothing like "you cannot send mail from here".
    """
    try:
        with smtplib.SMTP(host, port, timeout=timeout) as s:
            code, banner = s.noop()
        return True, f"{host}:{port} reachable (NOOP {code})"
    except (socket.timeout, TimeoutError):
        return False, f"{host}:{port} timed out after {timeout:g}s -- firewalled?"
    except ConnectionRefusedError:
        return (
            False,
            f"{host}:{port} refused -- no local MTA on this host. This script needs one "
            "(common on HPC login/compute nodes, usually absent on laptops and in containers). "
            "Point --smtp-host at a relay you can reach, or send from a node that has one.",
        )
    except Exception as exc:  # noqa: BLE001 - report whatever the stack actually said
        return False, f"{host}:{port} unavailable -- {type(exc).__name__}: {exc}"


def load_thread(path):
    # type: (Path) -> List[str]
    if not path.exists():
        return []
    return [ln.strip() for ln in path.read_text().splitlines() if ln.strip()]


def sender_domain(addr):
    # type: (str) -> str
    """Domain for Message-ID. Using the recipient's domain keeps IDs plausible to the relay."""
    return addr.rsplit("@", 1)[-1] if "@" in addr else socket.getfqdn()


def main():
    ap = argparse.ArgumentParser(
        description="Send a threaded report email via a local MTA.",
        epilog="Run --check first if you are unsure this host can send mail.",
    )
    ap.add_argument("--to", default=os.environ.get(ENV_TO), help=f"or ${ENV_TO}")
    ap.add_argument("--sender", default=None, help="defaults to --to so replies work")
    ap.add_argument(
        "--subject",
        default=os.environ.get(ENV_SUBJECT),
        help=f"kept CONSTANT across a thread; or ${ENV_SUBJECT}",
    )
    ap.add_argument("--stage", default="", help="short tag, shown in the body not the subject")
    ap.add_argument("--body", default="")
    ap.add_argument("--body-file", default=None)
    ap.add_argument("--attach", action="append", default=[])
    ap.add_argument(
        "--thread-file",
        default=None,
        help="state file of sent Message-IDs; omit for standalone messages",
    )
    ap.add_argument("--smtp-host", default=os.environ.get(ENV_HOST, "localhost"))
    ap.add_argument("--smtp-port", type=int, default=int(os.environ.get(ENV_PORT, "25")))
    ap.add_argument("--max-attach-mb", type=float, default=DEFAULT_MAX_ATTACH_MB)
    ap.add_argument(
        "--check", action="store_true", help="test MTA reachability and exit; sends nothing"
    )
    ap.add_argument(
        "--lenient",
        action="store_true",
        help="exit 0 even if sending fails (for unattended pipelines; risks silent loss)",
    )
    ap.add_argument("--dry-run", action="store_true", help="build the message but do not send")
    args = ap.parse_args()

    if args.check:
        ok, reason = check_mta(args.smtp_host, args.smtp_port)
        print(f"[email-report] {'OK  ' if ok else 'FAIL'} {reason}")
        return 0 if ok else 1

    missing = [n for n, v in (("--to", args.to), ("--subject", args.subject)) if not v]
    if missing:
        ap.error(f"missing required: {', '.join(missing)} (or set ${ENV_TO} / ${ENV_SUBJECT})")

    body = Path(args.body_file).read_text() if args.body_file else args.body
    if not body.strip():
        body = "(no body)"

    header = f"[{args.stage}]\n\n" if args.stage else ""
    # Provenance footer: when a report arrives at 3am, "which host, which job, which directory"
    # is the first thing you want and the last thing anyone remembers to include.
    footer = (
        f"\n\n---\nhost {socket.gethostname()}"
        f"  job {os.environ.get('SLURM_JOB_ID', 'interactive')}"
        f"  cwd {os.getcwd()}\n"
    )

    msg = EmailMessage()
    msg["Subject"] = args.subject
    msg["To"] = args.to
    msg["From"] = args.sender or args.to
    msg["Date"] = formatdate(localtime=True)
    mid = make_msgid(domain=sender_domain(args.sender or args.to))
    msg["Message-ID"] = mid

    prior = []  # type: List[str]
    thread_path = Path(args.thread_file) if args.thread_file else None
    if thread_path:
        prior = load_thread(thread_path)
        if prior:
            # Reply to the newest, but carry the WHOLE chain: clients that walk References
            # (Gmail among them) need it to keep every report in one conversation.
            msg["In-Reply-To"] = prior[-1]
            msg["References"] = " ".join(prior)

    # TWO PASSES, and the order is load-bearing: `add_attachment` turns the message into a
    # multipart, after which `set_content` raises "set_content not valid on multipart". So decide
    # what to attach FIRST, write the body once (including the skip note), and only then attach.
    # Doing it in one pass is the natural-looking mistake and it crashes whenever one attachment
    # succeeds and another is skipped.
    total = 0.0
    to_attach = []  # type: List[Path]
    skipped = []  # type: List[str]
    for path in args.attach:
        ap_path = Path(path)
        if not ap_path.exists():
            skipped.append("%s (missing)" % path)
            continue
        size_mb = ap_path.stat().st_size / 1e6
        if total + size_mb > args.max_attach_mb:
            skipped.append(
                f"{ap_path.name} ({size_mb:.1f} MB raw, over the {args.max_attach_mb:g} MB "
                f"budget) -- on disk at {ap_path.resolve()}"
            )
            continue
        to_attach.append(ap_path)
        total += size_mb

    note = ""
    if skipped:
        # Name them in the body. A reader who was promised a figure should learn where it is,
        # not silently receive a mail without it.
        note = "\n\nNOT ATTACHED:\n" + "\n".join("  - %s" % s for s in skipped)
    msg.set_content(header + body + note + footer)

    for ap_path in to_attach:
        ctype, _ = mimetypes.guess_type(ap_path.name)
        maintype, subtype = (ctype or "application/octet-stream").split("/", 1)
        msg.add_attachment(
            ap_path.read_bytes(), maintype=maintype, subtype=subtype, filename=ap_path.name
        )

    if args.dry_run:
        print(
            f"[email-report] DRY RUN '{args.subject}' -> {args.to}; "
            f"{len(args.attach) - len(skipped)} attachments, {total:.1f} MB raw "
            f"(~{total * BASE64_OVERHEAD:.1f} MB encoded); {len(skipped)} skipped"
        )
        return 0

    try:
        with smtplib.SMTP(args.smtp_host, args.smtp_port, timeout=60) as s:
            s.send_message(msg)
    except Exception as exc:  # noqa: BLE001
        ok, reason = check_mta(args.smtp_host, args.smtp_port)
        sys.stderr.write(
            f"[email-report] send FAILED: {type(exc).__name__}: {exc}\n"
            f"[email-report] MTA check: {reason}\n"
        )
        return 0 if args.lenient else 1

    if thread_path:
        thread_path.parent.mkdir(parents=True, exist_ok=True)
        with thread_path.open("a") as fh:
            fh.write(mid + "\n")

    pos = f"; thread position {len(prior) + 1}" if thread_path else ""
    print(
        f"[email-report] sent '{args.subject}'"
        + (f" stage='{args.stage}'" if args.stage else "")
        + f" to {args.to} ({len(args.attach) - len(skipped)} attachments, "
        f"{total:.1f} MB raw / ~{total * BASE64_OVERHEAD:.1f} MB encoded"
        + (f", {len(skipped)} SKIPPED" if skipped else "")
        + f"){pos}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
