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
    return os.path.join(threads_dir, "threads", tid, "events", shard_name())


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
                line = line[:MAX_LINE - 2] + '"}'
        path = _shard_path(threads_dir, tid)
        d = os.path.dirname(path)
        if not os.path.isdir(d):
            os.makedirs(d, 0o700)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        try:
            os.write(fd, (line + "\n").encode("utf-8"))
        finally:
            os.close(fd)
    except BaseException:
        return


def _tail_bytes(path, nbytes):
    with io.open(path, "rb") as fh:
        try:
            fh.seek(-nbytes, os.SEEK_END)
        except (IOError, OSError):
            fh.seek(0)
        return fh.read()


def read_events_tail(path, n):
    """Tolerate partial lines -- that is the NORMAL case, not an edge case."""
    try:
        buf = _tail_bytes(path, 65536)
    except (IOError, OSError):
        return []
    if not buf.endswith(b"\n"):
        buf = buf.rpartition(b"\n")[0]          # drop the in-flight fragment
    out = []
    parts = buf.split(b"\n")
    if len(buf) >= 65536 and len(parts) > 1:
        parts = parts[1:]                       # drop a truncated leading record
    for raw in parts:
        if not raw.strip():
            continue
        try:
            out.append(json.loads(raw.decode("utf-8")))
        except Exception:
            continue                            # completes on the next render
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
    records.sort(key=lambda r: r.get("ts") or "")
    return records[-n:]
