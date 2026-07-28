import json
import os
import re
import unicodedata

from agent_board import store
from agent_board.timeutil import utcnow_z

SCHEMA_VERSION = 1
ID_MAX = 48
RESERVED = ("archive", "config", "cache", "threads")

DECLARED_DEFAULTS = {
    "title": None, "goal": None, "next_action": None,
    "blocked_by": [], "worktrees": [], "issues": [], "tags": [],
    "job_name_prefix": None,
    "parked": False, "parked_reason": None,
    "done": False, "done_at": None,
    "notes": None,
}


class ThreadRejected(Exception):
    """schema_version is newer than we understand: render read-only, never write."""


class ThreadNotFound(Exception):
    """No such thread id. A typo is the most likely user error, so it must
    produce a one-line message and rc 2 -- never a traceback, and never an
    attempt to write a record into a directory that was never allocated."""


class ThreadIdUnavailable(Exception):
    """All numeric suffixes for this slug are taken. Must reach the user as one
    line and rc 2, not a bare ValueError traceback."""


def slugify(title):
    s = unicodedata.normalize("NFKD", title or "")
    s = s.encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    if len(s) > ID_MAX:
        s = s[:ID_MAX].rsplit("-", 1)[0] if "-" in s[:ID_MAX] else s[:ID_MAX]
        s = s.strip("-")
    if s in RESERVED:
        s = s + "-thread"
    return s or "thread"


def thread_dir(threads_dir, tid):
    return os.path.join(threads_dir, "threads", tid)


def _thread_path(threads_dir, tid):
    return os.path.join(thread_dir(threads_dir, tid), "thread.json")


# Which field of an appended record establishes identity. Whole-record equality
# is WRONG for worktrees: the CLI stamps a fresh `added_at` on every invocation,
# so `--add-worktree /same/path` twice at different times would append the same
# worktree twice and render it twice on one card.
_APPEND_KEYS = {"worktrees": "path"}


def _append_identity(field, item):
    key = _APPEND_KEYS.get(field)
    if key and isinstance(item, dict):
        return json.dumps(item.get(key), sort_keys=True)
    return json.dumps(item, sort_keys=True)


def _as_list(value):
    """Persisted JSON is user- and future-writable, so a field declared as a list
    can legally arrive as anything. `for x in value or []` raises TypeError on a
    truthy non-iterable (5, true, 1.5) and silently SHREDS a bare string into
    per-character entries -- which mutate then writes back, persisting the
    corruption. Measured: {"worktrees": "/abs/path"} produced 9 garbage records.
    """
    return list(value) if isinstance(value, (list, tuple)) else []


def _normalize_worktrees(value):
    out = []
    for entry in _as_list(value):
        if isinstance(entry, str):
            out.append({"path": entry, "branch": None, "added_at": None})
        elif isinstance(entry, dict):
            out.append({"path": entry.get("path"),
                        "branch": entry.get("branch"),
                        "added_at": entry.get("added_at")})
    return out


def _skeleton(tid, status, problems):
    t = {"id": tid, "schema_version": SCHEMA_VERSION, "rev": 0}
    t.update({k: (list(v) if isinstance(v, list) else v)
              for k, v in DECLARED_DEFAULTS.items()})
    t["title"] = tid
    t["_status"] = status
    t["_problems"] = problems
    return t


def _load_thread_inner(threads_dir, tid):
    path = _thread_path(threads_dir, tid)
    store.refresh_dir(os.path.dirname(path))
    text, err = store.read_text_resilient(path)
    if err == "missing":
        return _skeleton(tid, "missing", ["thread.json not found"])
    if err == "not_utf8":
        return _skeleton(tid, "not_utf8", ["file is not valid UTF-8"])
    if err:
        return _skeleton(tid, "unreadable", [err])
    if not (text or "").strip():
        return _skeleton(tid, "empty", ["file is empty"])
    try:
        obj = json.loads(text)
    except ValueError as exc:
        return _skeleton(tid, "corrupt_json", [str(exc)])
    if not isinstance(obj, dict):
        return _skeleton(tid, "corrupt_json", ["top level is not an object"])

    problems = []
    ver = obj.get("schema_version")
    if not isinstance(ver, int):
        status, problems = "degraded", ["schema_version missing"]
        ver = SCHEMA_VERSION
    elif ver > SCHEMA_VERSION:
        status = "rejected"
        problems = ["schema_version %s is newer than %s" % (ver, SCHEMA_VERSION)]
    elif ver < SCHEMA_VERSION:
        status = "degraded"          # migrate IN MEMORY ONLY, never write on read
        problems = ["migrated in memory from schema_version %s" % ver]
    else:
        status = "ok"

    out = dict(obj)                  # preserve every unknown field
    for k, default in DECLARED_DEFAULTS.items():
        out.setdefault(k, list(default) if isinstance(default, list) else default)
    out["id"] = obj.get("id") or tid
    out["rev"] = obj.get("rev") if isinstance(obj.get("rev"), int) else 0
    raw_worktrees = out.get("worktrees")
    out["worktrees"] = _normalize_worktrees(raw_worktrees)
    if raw_worktrees is not None and not isinstance(raw_worktrees, (list, tuple)):
        # Coercing without flagging would leave the headline field of this very
        # bug silently dropping data -- un-crashed but still invisible.
        problems.append("worktrees was not a list; ignored")
        if status == "ok":
            status = "degraded"
    for key in ("blocked_by", "issues", "tags"):
        coerced = _as_list(out.get(key))
        if coerced != out.get(key):
            problems.append("%s was not a list; ignored" % key)
            if status == "ok":
                status = "degraded"
        out[key] = coerced
    out["_status"] = status
    out["_problems"] = problems
    return out


def load_thread(threads_dir, tid):
    """Never raises. Always returns something renderable carrying _status.

    The guarantee is structural: _load_thread_inner does the work and ANY
    escaping exception becomes a loader_crash record. Enumerating field types
    is not sufficient on its own -- persisted JSON is future- and
    hand-writable, so the set of malformed shapes is open-ended.
    """
    try:
        return _load_thread_inner(threads_dir, tid)
    except BaseException as exc:
        return _skeleton(tid, "loader_crash", [repr(exc)])


def load_all(threads_dir):
    root = os.path.join(threads_dir, "threads")
    store.refresh_dir(root)
    try:
        names = sorted(os.listdir(root))
    except OSError:
        return {}
    out = {}
    for name in names:
        if name.startswith("."):
            continue
        if not os.path.isdir(os.path.join(root, name)):
            continue
        try:
            out[name] = load_thread(threads_dir, name)
        except BaseException as exc:      # a loader crash must not kill the board
            out[name] = _skeleton(name, "loader_crash", [repr(exc)])
    return out


def _allocate_id(threads_dir, base):
    root = os.path.join(threads_dir, "threads")
    # exist_ok on the SHARED parent is correct and required: two first-ever
    # `abd thread new` calls race here and the loser got an uncaught
    # FileExistsError. The prohibition on exist_ok applies to the PER-ID
    # directory below, where it would let two nodes adopt one id.
    os.makedirs(root, 0o700, exist_ok=True)
    for suffix in [""] + ["-%d" % n for n in range(2, 10)]:
        tid = base + suffix
        try:
            # bare mkdir, NOT makedirs(exist_ok=True): EEXIST is how the race is
            # decided across nodes. exist_ok would let two nodes adopt one id.
            os.mkdir(os.path.join(root, tid), 0o700)
            return tid
        except OSError:
            continue
    raise ThreadIdUnavailable(
        "could not allocate an id for %r; use a different title" % base)


def new_thread(threads_dir, title, **kw):
    tid = _allocate_id(threads_dir, slugify(title))
    now = utcnow_z()
    t = {"schema_version": SCHEMA_VERSION, "rev": 1, "id": tid,
         "created_at": now, "updated_at": now,
         "created_by": kw.pop("created_by", "cli")}
    for k, default in DECLARED_DEFAULTS.items():
        t[k] = list(default) if isinstance(default, list) else default
    t["title"] = title
    for k, v in kw.items():
        if k in DECLARED_DEFAULTS:
            t[k] = v
    t["worktrees"] = _normalize_worktrees(t.get("worktrees"))
    store.atomic_write_json(_thread_path(threads_dir, tid), t)
    return dict(t, _status="ok", _problems=[])


def mutate(threads_dir, tid, changes, actor="cli", appends=None):
    """Locked read-modify-write with a rev CAS. Retries 3x on a rev mismatch.

    `appends` merges list items INSIDE the lock, after the fresh re-read --
    unlike `changes`, which replaces a field wholesale. A caller that
    precomputes `cur + [new]` outside the lock and passes it via `changes`
    reads the same base as a concurrent writer, and the CAS cannot catch it:
    both readers saw the same rev, so the second writer's field-level append
    silently overwrites the first's -- a lost update one layer above the very
    lock this function holds. Do not "simplify" this back into a precomputed
    list passed through `changes`.
    """
    d = thread_dir(threads_dir, tid)
    path = _thread_path(threads_dir, tid)
    for _ in range(3):
        current = load_thread(threads_dir, tid)
        if current["_status"] == "missing":
            # Without this, the write path fails deep inside atomic_write_json
            # with a raw FileNotFoundError traceback and rc 1 -- measured on a
            # one-character id typo, which is the likeliest user error there is.
            raise ThreadNotFound(tid)
        if current["_status"] == "rejected":
            raise ThreadRejected(current["_problems"][0])
        expected_rev = current["rev"]
        lk = store.acquire_thread_lock(d)
        bypassed = lk is None
        try:
            fresh = load_thread(threads_dir, tid)
            if fresh["rev"] != expected_rev:
                continue                              # CAS miss: re-read, re-apply
            out = {k: v for k, v in fresh.items() if not k.startswith("_")}
            for k, v in (changes or {}).items():
                out[k] = v
            for k, items in (appends or {}).items():
                base = _as_list(out.get(k))
                seen = {_append_identity(k, x) for x in base}
                for item in items:
                    ident = _append_identity(k, item)
                    if ident not in seen:
                        base.append(item)
                        seen.add(ident)
                out[k] = base
            out["worktrees"] = _normalize_worktrees(out.get("worktrees"))
            out["rev"] = expected_rev + 1
            out["updated_at"] = utcnow_z()
            store.atomic_write_json(path, out)
        finally:
            store.release_thread_lock(lk)
        append_event(threads_dir, tid, {
            "kind": "set", "actor": actor,
            "fields": sorted((changes or {}).keys()),
            "lock_bypassed": bypassed,
        })
        return dict(out, _status="ok", _problems=[])
    raise RuntimeError("thread busy, retry")          # surfaced as rc 75 by the CLI


# TODO(Task 7): delete this stub and replace with
# `from agent_board.events import append_event` once agent_board/events.py lands.
# Event shards have their own concurrency design and belong to Task 7 -- this
# is a temporary no-op so `mutate()` above has something to call.
def append_event(*a, **kw):
    pass
