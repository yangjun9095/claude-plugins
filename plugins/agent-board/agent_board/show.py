"""`abd show <id>` -- one thread in full.

The board is a scan; this is a drill-down. It reuses the board's derivation rather
than recomputing anything, so a card and its detail view can never disagree -- the
same reason nothing here is persisted.

Event budget is 50, deliberately larger than the card's 3 and the injected card's 10:
this is the view a human opens when they have lost the thread and want the history.
"""
import os

from agent_board.render.layout import sanitize

EVENTS_SHOWN = 50


def _s(value, ascii_mode=False):
    """Every agent-written string reaches the terminal through here.

    `sanitize` strips ANSI SGR runs and replaces remaining C0 controls and DEL --
    without it a title containing \x1b[41m left a sticky colour on the user's
    terminal, a \x1b[2J cleared their screen, and an embedded newline turned one
    rendered line into two physical ones, breaking the "one line per element"
    contract the caller relies on. render_board has always done this (layout.py);
    show.py did not, so `abd board` was clean and `abd show` was not on the same
    thread.

    In ascii mode the fold to '?' goes further than sanitize: the flag exists so
    output survives a non-UTF-8 terminal, and a CJK branch or directory name would
    otherwise still emit multi-byte text.
    """
    text = sanitize("" if value is None else str(value), ascii_mode)
    if ascii_mode:
        text = "".join(c if ord(c) < 128 else "?" for c in text)
    return text


def find_card(board, tid):
    for name, rows in (board.get("columns") or {}).items():
        for card in rows:
            if card.get("id") == tid:
                return card, name
    return None, None


def build(board, threads_dir, tid, events_shown=EVENTS_SHOWN):
    """(detail, error). `error` is a message when the thread does not exist."""
    from agent_board import events as events_mod

    card, column = find_card(board, tid)
    if card is None:
        return None, "no thread %r" % tid
    collisions = [c for c in (board.get("collisions") or [])
                  if tid in (c.get("a"), c.get("b"))]
    return {
        "id": tid,
        "column": column,
        "title": card.get("title"),
        "goal": card.get("goal"),
        "next_action": card.get("next_action"),
        "worktrees": card.get("worktrees") or [],
        "attention": card.get("attention") or [],
        "jobs": card.get("jobs") or [],
        "pr": card.get("pr"),
        "notes": card.get("notes") or [],
        "collisions": collisions,
        "events": events_mod.read_thread_events(threads_dir, tid, events_shown),
    }, None


def render(detail, ascii_mode=False):
    """Plain lines. No geometry, no colour -- `show` is a linear read, not a board,
    so it deliberately does not go through the card layout engine."""
    bullet = "-" if ascii_mode else "·"
    out = ["%s  [%s]" % (_s(detail["id"], ascii_mode),
                         _s(detail["column"], ascii_mode)),
           _s(detail.get("title") or "", ascii_mode)]
    if detail.get("goal"):
        out.append("")
        out.append("GOAL         %s" % _s(detail["goal"], ascii_mode))
    if detail.get("next_action"):
        out.append("NEXT ACTION  %s" % _s(detail["next_action"], ascii_mode))

    pr = detail.get("pr") or {}
    if pr:
        bits = [_s(pr.get("state") or "?", ascii_mode)]
        if pr.get("number"):
            bits.insert(0, "#%s" % pr["number"])
        if pr.get("reviewDecision"):
            bits.append(_s(pr["reviewDecision"], ascii_mode))
        if pr.get("isDraft"):
            bits.append("draft")
        out.append("PR           %s" % " ".join(bits))
        if pr.get("url"):
            out.append("             %s" % _s(pr["url"], ascii_mode))

    if detail.get("worktrees"):
        out.append("")
        out.append("WORKTREES")
        for line in detail["worktrees"]:
            out.append("  %s %s" % (bullet, _s(line, ascii_mode)))

    if detail.get("jobs"):
        out.append("")
        out.append("JOBS")
        for job in detail["jobs"]:
            out.append("  %s %-10s %-9s %s" % (
                bullet, _s(job.get("id") or "?", ascii_mode),
                _s(job.get("state") or "?", ascii_mode),
                _s(job.get("name") or "", ascii_mode)))
            if job.get("workdir"):
                out.append("      %s (%s)" % (
                    _s(job["workdir"], ascii_mode),
                    _s(job.get("attributed_by") or "?", ascii_mode)))

    if detail.get("attention"):
        out.append("")
        out.append("NEEDS ATTENTION")
        for reason in detail["attention"]:
            out.append("  %s %s" % (bullet, _s(reason, ascii_mode)))

    if detail.get("collisions"):
        out.append("")
        out.append("COLLISIONS")
        for c in detail["collisions"]:
            # .get, not []: cache/collisions.json is JSON on disk and
            # hand-editable, and a row missing "a" raised KeyError out of the
            # renderer.
            other = c.get("b") if c.get("a") == detail["id"] else c.get("a")
            out.append("  %s %s with %s" % (
                bullet, _s(c.get("severity"), ascii_mode),
                _s(other, ascii_mode)))
            for path in c.get("files") or []:
                out.append("      %s" % _s(path, ascii_mode))

    if detail.get("notes"):
        out.append("")
        out.append("NOTES")
        for note in detail["notes"]:
            out.append("  %s %s" % (bullet, _s(note, ascii_mode)))

    out.append("")
    events = detail.get("events") or []
    # Spelled out rather than relying on `%` binding tighter than the conditional:
    # that precedence trap already produced one real bug in this project.
    if events:
        out.append("TIMELINE (last %d)" % len(events))
    else:
        out.append("TIMELINE (empty)")
    for ev in events:
        detail_text = ev.get("text") or ev.get("reason") or ""
        fields = ev.get("fields")
        if not detail_text and isinstance(fields, list):
            detail_text = ", ".join(str(f) for f in fields)
        out.append("  %s  %-17s %-6s %s" % (
            _s(ev.get("ts") or "?", ascii_mode),
            _s(ev.get("kind") or "?", ascii_mode),
            _s(ev.get("actor") or "?", ascii_mode),
            _s(detail_text, ascii_mode)))
    return out


def render_unowned(unowned, ascii_mode=False):
    """The `--all` section: worktrees no thread claims.

    This is the answer to "what have I forgotten about" -- and the reason it is
    opt-in is that probing every worktree costs seconds, not that the list is
    uninteresting.
    """
    if not unowned:
        return ["no unowned worktrees - every worktree belongs to a thread"]
    bullet = "-" if ascii_mode else "·"
    out = ["UNOWNED WORKTREES (%d) - no thread claims these" % len(unowned)]
    for row in unowned:
        out.append("  %s %-28s %s  +%s -%s *%d  %s" % (
            bullet,
            _s(os.path.basename(row["path"].rstrip("/")) or row["path"],
               ascii_mode),
            _s(row.get("branch") or "(detached)", ascii_mode),
            "?" if row.get("ahead") is None else row["ahead"],
            "?" if row.get("behind") is None else row["behind"],
            row.get("dirty") or 0,
            row.get("last_commit") or "never"))
    out.append("")
    out.append("adopt one with: abd thread new --title \"...\" --worktree <path>")
    return out


def render_unattributed(jobs_list, ascii_mode=False):
    """The `--unattributed` view. Never a default panel: at 675 of 728 real jobs it
    is noise, which is exactly why it is a separate flag."""
    if not jobs_list:
        return ["no unattributed jobs"]
    bullet = "-" if ascii_mode else "·"
    out = ["UNATTRIBUTED JOBS (%d) - matched no thread" % len(jobs_list)]
    for job in jobs_list:
        out.append("  %s %-10s %-9s %s" % (
            bullet, _s(job.get("id") or "?", ascii_mode),
            _s(job.get("state") or "?", ascii_mode),
            _s(job.get("name") or "", ascii_mode)))
        if job.get("workdir"):
            out.append("      %s" % _s(job["workdir"], ascii_mode))
    out.append("")
    out.append("declare job_name_prefix on a thread to see its jobs: "
               "abd thread set <id> --job-prefix <prefix>")
    return out
