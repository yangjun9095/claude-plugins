"""SessionStart / SessionEnd behaviour.

One absolute contract, both events: **exit 0, always, whatever happens.** A
traceback here lands inside the user's session, and a non-zero exit prints
stderr into it. Every failure path in this module returns 0 and prints nothing.

SessionStart's stdout IS the feature (it becomes additionalContext), so it must
be a single valid-JSON write. SessionEnd's stdout is discarded -- it runs with
`async: true` -- so it writes only to the event shard.
"""
import hashlib
import io
import json
import os
import sys
import time

CARD_MAX = 4000
EVENTS_SHOWN = 10
COLLISION_MAX_AGE_S = 24 * 3600
NUDGE_INTERVAL_S = 7 * 24 * 3600
PIN_NAME = "active-thread"

_OPEN = "<agent-board-thread>"
_CLOSE = "</agent-board-thread>"

# An explicit allow-list, NOT `if os.environ.get("ABD_DISABLE")`. Any non-empty
# value is truthy, so `ABD_DISABLE=0` -- the natural way to re-enable -- would
# silently disable the tool, and it fails silently, so the user never learns why
# their cards stopped appearing.
_DISABLE_TRUTHY = ("1", "true", "TRUE", "yes", "YES")


def _disabled():
    for value in _DISABLE_TRUTHY:
        if os.environ.get("ABD_DISABLE") == value:
            return True
    return os.path.exists(os.path.expanduser("~/.agent-board-DISABLED"))


def _reconfigure():
    """utf-8 + errors="replace" BEFORE any output.

    __main__ already does this for every entry point; doing it again is free and
    keeps hook_main correct when called directly (tests, or any future embedder).
    Under LC_ALL=C sys.stdout.encoding becomes ANSI_X3.4-1968 and printing a
    title containing a non-ASCII character raises UnicodeEncodeError -- which,
    for a hook whose entire job is printing, is a session-breaking bug.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def read_payload(text):
    """The hook payload, or {} for anything unparseable."""
    try:
        obj = json.loads(text)
    except Exception:
        return {}
    return obj if isinstance(obj, dict) else {}


def _under(path, base):
    """Path containment on a component boundary. '/a/bc' is NOT under '/a/b'."""
    if not path or not base:
        return False
    base = base.rstrip(os.sep)
    if not base:                        # base was "/" -- everything is under it
        return path.startswith(os.sep)
    return path == base or path.startswith(base + os.sep)


def _owning_thread(threads, target):
    """Longest-prefix match of `target` against every thread's worktree paths.

    Longest wins so a nested worktree beats its parent. Ties break on sorted id
    for determinism -- an arbitrary dict order would make the injected card
    depend on filesystem listing order.
    """
    best, best_len = None, -1
    for tid in sorted(threads):
        for wt in threads[tid].get("worktrees") or []:
            path = wt.get("path") if isinstance(wt, dict) else None
            if not isinstance(path, str) or not path:
                continue
            real = os.path.realpath(path)
            if _under(target, real) and len(real) > best_len:
                best, best_len = tid, len(real)
    return best


def read_pin(threads_dir):
    try:
        with io.open(os.path.join(threads_dir, PIN_NAME), "r",
                     encoding="utf-8", errors="replace") as fh:
            return fh.readline().strip() or None
    except (IOError, OSError):
        return None


def select_thread(threads_dir, threads, cwd):
    """Return (tid, how). Never guesses.

    `cwd` is where `claude` was LAUNCHED, not where the agent later works, so a
    cwd match alone is insufficient: launching from the main worktree while the
    agent operates in a linked one would give the wrong card, or none. Hence the
    explicit pin and the env var rank above it.
    """
    env = os.environ.get("ABD_THREAD")
    if env and env in threads:
        return env, "env"
    pin = read_pin(threads_dir)
    if pin and pin in threads:
        return pin, "pin"
    if cwd:
        hit = _owning_thread(threads, os.path.realpath(cwd))
        if hit:
            return hit, "cwd"
    project = os.environ.get("CLAUDE_PROJECT_DIR")
    if project:
        hit = _owning_thread(threads, os.path.realpath(project))
        if hit:
            return hit, "project"
    live = sorted(tid for tid, t in threads.items() if not t.get("done"))
    if len(live) == 1:
        return live[0], "only"
    if live:
        return None, "ambiguous"
    return None, "none"


def read_collisions(threads_dir, tid, now=None):
    """HIGH-severity collisions for this thread, read from the cache `abd board`
    writes. Never computed here -- the scan costs hundreds of milliseconds.

    A stale set is worse than none (it names files that may have been merged
    hours ago), so the whole file is ignored past 24 h. The row shape is
    defensive on purpose: M2 owns the writer, and a reader that crashes on an
    unexpected field would take the card down with it.
    """
    path = os.path.join(threads_dir, "cache", "collisions.json")
    try:
        mtime = os.stat(path).st_mtime
    except OSError:
        return []
    if (now if now is not None else time.time()) - mtime > COLLISION_MAX_AGE_S:
        return []
    try:
        with io.open(path, "r", encoding="utf-8", errors="replace") as fh:
            data = json.load(fh)
    except Exception:
        return []
    rows = data.get("collisions") if isinstance(data, dict) else None
    out = []
    for row in rows or []:
        if not isinstance(row, dict) or row.get("severity") != "HIGH":
            continue
        parties = row.get("threads")
        parties = list(parties) if isinstance(parties, (list, tuple)) else []
        if parties and tid not in parties:
            continue
        path_s = row.get("path")
        if not isinstance(path_s, str):
            continue
        others = [str(p) for p in parties if p != tid]
        out.append("%s%s" % (path_s, " (also: %s)" % ", ".join(others) if others else ""))
    return out[:5]


def build_card(t, events, collisions):
    tid = t.get("id") or "(unknown)"
    # NOT `"...%s" % t.get("title") or t.get("id")` -- that parses as
    # ("...%s" % title) or id, and the left operand is never empty, so the
    # fallback is dead code and a title-less thread renders the literal "None".
    title = t.get("title") or tid or "(untitled)"
    out = ["## agent-board thread: %s" % title, "id: %s" % tid]
    if t.get("done"):
        out.append("STATUS: DONE -- closed. Do not resume this work unless asked.")
    elif t.get("parked"):
        reason = t.get("parked_reason")
        out.append("STATUS: PARKED%s" % (" -- %s" % reason if reason else ""))
    for label, key in (("GOAL", "goal"), ("NEXT ACTION", "next_action")):
        if t.get(key):
            out.append("%s: %s" % (label, t[key]))
    blocked = [b for b in (t.get("blocked_by") or []) if isinstance(b, str)]
    if blocked:
        out.append("BLOCKED BY: %s" % ", ".join(blocked))
        out.append("  Do not assume these are resolved -- check before proceeding.")
    issues = t.get("issues") or []
    if issues:
        out.append("ISSUES: %s" % ", ".join("#%s" % i for i in issues))
    if collisions:
        out.append("FILE COLLISIONS (HIGH) -- another thread is editing these:")
        out.extend("  - %s" % c for c in collisions)
    if events:
        out.append("RECENT:")
        for ev in events:
            detail = ev.get("text") or ev.get("reason") or ""
            out.append("  %s %s%s" % (ev.get("ts") or "?", ev.get("kind") or "?",
                                      " %s" % detail if detail else ""))
    out.append("Before you finish, record where you left off: "
               "abd thread set %s --next-action \"...\"" % tid)
    return "\n".join(out)


def build_disambiguation(threads):
    live = sorted(tid for tid, t in threads.items() if not t.get("done"))
    return ("## agent-board\n"
            "%d open threads and none owns this directory, so no card was "
            "injected. Pin one with `abd thread use <id>`: %s"
            % (len(live), ", ".join(live[:12])))


def build_nudge():
    return ("## agent-board\n"
            "This worktree is not tracked by any open thread. If this session is "
            "a distinct effort, open one: abd thread new --title \"...\" "
            "--worktree \"$PWD\"")


def _nudged_recently(threads_dir, worktree, now):
    """True if we should stay quiet.

    Keyed on sha1(realpath) -- NOT on a truncation of the mangled path, which
    collides for worktrees sharing a long suffix and would permanently silence
    one of them. The stamp is written BEFORE the caller emits, so a crash after
    this point cannot turn into a nag on every subsequent session.
    """
    from agent_board import store

    key = hashlib.sha1(os.path.realpath(worktree).encode("utf-8")).hexdigest()[:16]
    directory = os.path.join(threads_dir, "cache", "nudge")
    path = os.path.join(directory, key)
    try:
        if now - os.stat(path).st_mtime < NUDGE_INTERVAL_S:
            return True
    except OSError:
        pass
    try:
        store.makedirs_private(directory)
        with io.open(path, "w", encoding="utf-8") as fh:
            fh.write("")
    except OSError:
        return True                 # cannot stamp -> do not nag
    return False


def wrap_card(body):
    budget = CARD_MAX - len(_OPEN) - len(_CLOSE) - 2
    if len(body) > budget:
        tail = "\n... (truncated)"
        body = body[:max(0, budget - len(tail))] + tail
    return "%s\n%s\n%s" % (_OPEN, body, _CLOSE)


def session_start(payload, threads_dir=None, now=None):
    """Return the additionalContext string, or None for a no-op.

    Every no-op path returns None so the caller writes NOTHING. In particular a
    payload with no `cwd` is a no-op and must never fall back to os.getcwd():
    doing that made empty stdin emit a card for whatever directory the hook
    happened to run in.
    """
    from agent_board import anchor, events as events_mod, model

    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        return None
    if threads_dir is None:
        threads_dir = anchor.resolve_threads_dir_pure(cwd)
    if not threads_dir or not os.path.isdir(os.path.join(threads_dir, "threads")):
        return None                 # the zero-cost path for every un-opted repo
    threads = model.load_all(threads_dir)
    if not threads:
        return None

    tid, how = select_thread(threads_dir, threads, cwd)
    if tid is None:
        # Two different situations, deliberately handled differently. Several
        # open threads and none owns this directory is ANSWERABLE -- say so every
        # time, because the agent genuinely has no card. No open thread at all is
        # a suggestion, so it is rate-limited to once a week per worktree.
        if how == "ambiguous":
            return wrap_card(build_disambiguation(threads))
        if now is None:
            now = time.time()
        if _nudged_recently(threads_dir, cwd, now):
            return None
        return wrap_card(build_nudge())

    events = events_mod.read_thread_events(threads_dir, tid, EVENTS_SHOWN)
    collisions = read_collisions(threads_dir, tid, now=now)
    return wrap_card(build_card(threads[tid], events, collisions))


def session_end(payload, threads_dir=None):
    """Append ONE line to this host's event shard. Never locks, never touches
    thread.json -- that is the entire reason events live in per-host shards."""
    from agent_board import anchor, events as events_mod, model
    from agent_board.derive.git_ import head_short

    cwd = payload.get("cwd")
    if not isinstance(cwd, str) or not cwd:
        return 0
    if threads_dir is None:
        threads_dir = anchor.resolve_threads_dir_pure(cwd)
    if not threads_dir or not os.path.isdir(os.path.join(threads_dir, "threads")):
        return 0
    threads = model.load_all(threads_dir)
    if not threads:
        return 0
    tid, _how = select_thread(threads_dir, threads, cwd)
    if tid is None:
        return 0

    record = {"kind": "session_snapshot", "actor": "hook",
              "worktree": os.path.realpath(cwd)}
    for src, dst in (("session_id", "session_id"), ("reason", "reason")):
        value = payload.get(src)
        if isinstance(value, str) and value:
            record[dst] = value
    # `head` is a historical anchor: where this session left off. Derived state
    # (branch, ahead/behind, dirty) is deliberately NOT recorded -- a stored copy
    # can only ever disagree with the live board, and capturing it was what made
    # this hook cost 5 git calls instead of 1.
    head = head_short(cwd)
    if head:
        record["head"] = head
    events_mod.append_event(threads_dir, tid, record)
    return 0


def hook_main(argv):
    try:
        if _disabled():
            return 0
        _reconfigure()
        which = argv[0] if argv else ""
        if which == "session-start":
            try:
                raw = sys.stdin.read()
            except BaseException:
                return 0
            text = session_start(read_payload(raw))
            if text:
                # ONE write of valid JSON. Claude sniffs the first character: a
                # leading '{' that does not parse is silently discarded, so a
                # partial or hand-escaped write loses the card outright.
                sys.stdout.write(json.dumps({"hookSpecificOutput": {
                    "hookEventName": "SessionStart",
                    "additionalContext": text}}))
            return 0
        if which == "session-end":
            try:
                raw = sys.stdin.read()
            except BaseException:
                return 0
            return session_end(read_payload(raw))
        return 0
    except BaseException:
        return 0
