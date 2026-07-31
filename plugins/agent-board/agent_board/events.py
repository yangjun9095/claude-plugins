import io
import json
import os
import re

from agent_board import store
from agent_board.timeutil import utcnow_z

MAX_LINE = 4096
VALID_KINDS = ("opened", "set", "session_snapshot", "note", "parked", "done", "reopened")


def shard_name():
    """One shard per host. A hostname containing a slash would otherwise be a
    path traversal or an unopenable file."""
    safe = re.sub(r"[^a-z0-9._-]", "-", store.HOST)
    return "%s.jsonl" % (safe or "unknown")


def _shard_path(threads_dir, tid):
    # Route through model.thread_dir so a malformed/absolute tid is rejected
    # by the SAME guard `mutate` uses, instead of events.py growing its own
    # copy of the id-shape rule. Imported lazily: model.py imports
    # append_event from this module at load time, so a top-level import here
    # would be circular.
    from agent_board.model import thread_dir
    return os.path.join(thread_dir(threads_dir, tid), "events", shard_name())


def append_event(threads_dir, tid, record):
    """Append ONE line with ONE os.write under O_APPEND. Never locks, never
    raises -- an event is a convenience, not a correctness dependency."""
    try:
        rec = dict(record or {})
        rec.setdefault("ts", utcnow_z())
        rec.setdefault("host", store.HOST)
        rec.setdefault("kind", "note")
        line = json.dumps(rec, ensure_ascii=False, sort_keys=True)
        if len(line.encode("utf-8")) > MAX_LINE:
            for field in ("text", "goal", "next_action"):
                if isinstance(rec.get(field), str):
                    rec[field] = rec[field][:512] + "…"
            rec["truncated"] = True
            line = json.dumps(rec, ensure_ascii=False, sort_keys=True)
        if len(line.encode("utf-8")) > MAX_LINE:
            # NEVER slice serialised JSON. Slicing by characters while the bound
            # is measured in BYTES is a no-op for multi-byte text, and appending
            # '"}' to an already-closed object yields invalid JSON that the
            # reader silently skips -- so the event is DROPPED, not truncated.
            # Measured: three 2000-char CJK fields -> 4747 bytes, unparseable,
            # reader saw 0 records. Emit a minimal VALID record instead.
            line = json.dumps({
                "ts": str(rec.get("ts"))[:32],
                "host": str(rec.get("host"))[:64],
                "kind": str(rec.get("kind"))[:64],
                "actor": str(rec.get("actor"))[:64],
                "truncated": True,
                "fields_dropped": True,
            }, ensure_ascii=False, sort_keys=True)
        path = _shard_path(threads_dir, tid)
        d = os.path.dirname(path)
        # Refuse to CREATE the thread's directory. makedirs here resurrected a
        # thread that `abd thread archive` had just renamed away -- mutate's
        # trailing append_event runs outside the lock, so it recreated
        # threads/<id>/events/ with no thread.json, producing a phantom card that
        # no verb could remove. An event for a thread that is not there is a
        # convenience to drop, never a reason to invent the thread.
        if not os.path.isdir(os.path.dirname(d)):
            return
        # exist_ok, not check-then-create: two hosts racing the FIRST event for a
        # thread both pass an isdir() check, and the loser's FileExistsError is
        # swallowed by the outer handler -- dropping the event entirely.
        store.makedirs_private(d)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, (line + "\n").encode("utf-8"))
        finally:
            os.close(fd)
    except BaseException:
        return


def append_event_locked(threads_dir, tid, record):
    """append_event, but holding the thread's O_EXCL lock.

    The lock-free path is safe only for SINGLE-NODE O_APPEND. Cross-node appends to
    one file lose 73-74% on NFS, because each client computes the offset from its own
    cached size -- and a compute node writing to a login node's store is exactly that
    case. Per-host shards make the common path safe; this makes the shared-shard case
    safe too, for the one verb a batch job calls.

    Returns True when the lock was held, False when it was bypassed after the
    timeout -- the caller can then say so rather than implying a guarantee it did
    not get.
    """
    from agent_board.model import thread_dir

    lk = None
    try:
        lk = store.acquire_thread_lock(thread_dir(threads_dir, tid))
    except BaseException:
        lk = None
    try:
        append_event(threads_dir, tid, record)
    finally:
        try:
            store.release_thread_lock(lk)
        except BaseException:
            pass
    return lk is not None


def _tail_bytes(path, nbytes):
    """Return (buf, head_truncated).

    Reads one byte of LOOKBEHIND before the window so the caller can tell
    whether the window began at a record boundary. Using `len(buf) >= nbytes`
    as a proxy for "the first record is truncated" is WRONG: when the seek
    lands exactly on a newline the first record is complete, and dropping it
    silently loses the oldest event. Reproduced on a byte-exact fixture (a
    65536-byte block of fixed-width records preceded by an arbitrary
    newline-terminated prefix, so the tail window is exactly that block):
    the proxy version returned 1023 of 1024 records, missing the first
    (k000000), which was fully intact and valid JSON.
    """
    with io.open(path, "rb") as fh:
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        start = size - nbytes
        if start <= 0:
            fh.seek(0)
            return fh.read(), False          # whole file: nothing truncated
        fh.seek(start - 1)                   # one byte of lookbehind
        buf = fh.read()
        if buf[:1] == b"\n":
            return buf[1:], False            # window began at a record boundary
        return buf, True                     # first record really is truncated


def read_events_tail(path, n):
    """Tolerate partial lines -- that is the NORMAL case, not an edge case.

    The window is sized from the BUDGET, not fixed at 64 KiB. A fixed window makes
    the achievable count 65536/mean_line_bytes, so `abd show`'s budget of 50
    silently delivered 21 once events averaged ~3 KB -- and the header reported
    those 21 as the whole tail. A line may legally reach MAX_LINE, so n * MAX_LINE
    is the smallest window that can always satisfy n.
    """
    try:
        # Sized from the budget alone. A 64 KiB FLOOR meant a 3-event card read and
        # json-parsed the same 64 KiB per shard per thread as the 50-event detail
        # view -- measured 4.1x slower board renders once cards carried events.
        buf, head_truncated = _tail_bytes(path, max(4096, n * MAX_LINE))
    except (IOError, OSError):
        return []
    if not buf.endswith(b"\n"):
        buf = buf.rpartition(b"\n")[0]          # drop the in-flight fragment
    out = []
    parts = buf.split(b"\n")
    if head_truncated and len(parts) > 1:
        parts = parts[1:]                       # drop a truncated leading record
    for raw in parts:
        if not raw.strip():
            continue
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except Exception:
            continue                            # completes on the next render
        if isinstance(parsed, dict):            # a bare scalar/array would crash
            out.append(parsed)                  # the ts sort in read_thread_events
    return out[-n:]


def read_thread_events(threads_dir, tid, n):
    d = os.path.join(threads_dir, "threads", tid, "events")
    store.refresh_dir(d)
    records = []
    try:
        shards = sorted(os.listdir(d))
    except OSError:
        return []
    for name in shards:
        if name.endswith(".jsonl"):
            records.extend(read_events_tail(os.path.join(d, name), n))
    # str(): a non-string ts from a hand-edited or future record would otherwise
    # raise TypeError out of the one function whose job is catching a human up.
    records.sort(key=lambda r: str(r.get("ts") or ""))
    return records[-n:]
