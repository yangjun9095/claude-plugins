import json
import os
import re
import unicodedata

from agent_board import store
from agent_board.events import append_event
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

# F3: leaves the loader coerces the same way it already coerces list
# CONTAINERS (worktrees/blocked_by/issues/tags above). A wrong-typed leaf here
# is not hypothetical -- it is the single most natural mistake an
# agent-written thread.json makes ("goal": ["step1", "step2"]) -- and it
# crashed the renderer (layout.py's `clip`/`cw`/string concatenation all
# assume `str`), taking down every OTHER thread's card with it. Coerce with
# str(), never drop: the user should still see whatever was there.
STRING_LEAF_KEYS = ("title", "goal", "next_action", "notes", "parked_reason",
                    "created_at", "done_at", "created_by", "job_name_prefix")


class ThreadRejected(Exception):
    """schema_version is newer than we understand: render read-only, never write."""


class ThreadNotFound(Exception):
    """No such thread id. A typo is the most likely user error, so it must
    produce a one-line message and rc 2 -- never a traceback, and never an
    attempt to write a record into a directory that was never allocated."""


class ThreadIdUnavailable(Exception):
    """All numeric suffixes for this slug are taken. Must reach the user as one
    line and rc 2, not a bare ValueError traceback."""


class ThreadCorrupt(Exception):
    """The on-disk record cannot be safely read: _status is one of not_utf8,
    unreadable, empty, corrupt_json, loader_crash. mutate refuses to write
    over it -- writing a fresh skeleton would silently destroy whatever
    recoverable data still survives in the damaged file (measured: a 478-byte
    torn write became a 394-byte skeleton, title/next_action/created_at gone,
    rc 0, no warning). `degraded` is NOT this status -- it is the deliberate
    in-memory-only schema migration path and mutate must still be able to
    write it."""


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


_MAX_SUFFIX_LEN = len("-9")  # widest suffix _allocate_id appends: "-2".."-9"

# NOTE (deviation from the reviewer's literal regex `[a-z0-9-]{0,47}`, total
# length <= ID_MAX=48): _allocate_id can append a 2-char numeric suffix
# ("-2".."-9") to a base that is ALREADY at ID_MAX after slugify's own
# truncation, so a legitimately-allocated id can be up to ID_MAX + 2 = 50
# characters. Measured: two threads titled "x"*100 both slugify their base to
# exactly 48 x's; the second becomes that base + "-2" (50 chars), and the
# reviewer's literal bound raised ThreadNotFound on it -- i.e. a normal
# id-collision, not an attack, would have started failing every subsequent
# `abd thread set` on that thread. Widened by _MAX_SUFFIX_LEN so the
# guarantee the reviewer stated ("no legitimately allocated id is newly
# rejected") actually holds; still rejects the traversal/absolute-path shapes
# that motivated the guard, since both contain '/' or exceed the new bound.
_TID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,%d}$" % (47 + _MAX_SUFFIX_LEN))


def thread_dir(threads_dir, tid):
    """`tid` reaches here verbatim from argv on the `set`/`park`/`done`/
    `reopen` CLI paths (only `new` runs it through `slugify`). Without a
    guard, `os.path.join` DISCARDS everything before an absolute component --
    `os.path.join(threads_dir, "threads", "/abs/path/victim")` returns
    "/abs/path/victim" unchanged, so an absolute id writes a thread record
    over an arbitrary file outside the store. A relative id containing ".."
    is already rejected upstream by ThreadNotFound (no such allocated
    directory); this closes the absolute-id escape the same way.

    The pattern is slugify's output alphabet (lowercase a-z0-9 and internal
    '-', never leading '-') plus ID_MAX=48 plus the widest numeric collision
    suffix _allocate_id can append -- see _TID_RE's comment for why the plain
    ID_MAX bound is insufficient.
    """
    if not _TID_RE.match(tid or ""):
        raise ThreadNotFound(tid)
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
    """F3 residual (measured): {"worktrees":[{"path":99}]} passed through this
    function unchanged with `_status="ok"` -- not even flagged -- and blew up
    one hop later at board.py:41 (`os.path.basename(path.rstrip("/"))`,
    AttributeError: 'int' object has no attribute 'rstrip'). str(99) would
    "fix" that crash by fabricating the path "99", which os.path.isdir then
    reports as missing -- a worse lie than just omitting the entry: it invents
    data that was never there. An empty or None path is the same defect by a
    different route -- there is no worktree without a real path -- so all
    three are dropped, never coerced, matching `_as_list`'s existing
    malformed-input-drops shape.

    Returns `(entries, dropped)`. `dropped` counts ONLY entries that were
    worktree-shaped (a bare string or a dict) but carried an unusable path --
    NOT the pre-existing, deliberately-silent drop of an entry that is neither
    (e.g. a bare `99` sitting directly in the list), which has never been
    flagged and must stay that way.
    """
    out, dropped = [], 0
    for entry in _as_list(value):
        if isinstance(entry, str):
            path, branch, added_at = entry, None, None
        elif isinstance(entry, dict):
            path = entry.get("path")
            branch = entry.get("branch")
            added_at = entry.get("added_at")
        else:
            continue  # not worktree-shaped at all; pre-existing silent drop
        if not isinstance(path, str) or not path:
            dropped += 1
            continue
        out.append({"path": path, "branch": branch, "added_at": added_at})
    return out, dropped


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
    normalized_worktrees, dropped_worktrees = _normalize_worktrees(raw_worktrees)
    out["worktrees"] = normalized_worktrees
    if raw_worktrees is not None and not isinstance(raw_worktrees, (list, tuple)):
        # Coercing without flagging would leave the headline field of this very
        # bug silently dropping data -- un-crashed but still invisible.
        problems.append("worktrees was not a list; ignored")
        if status == "ok":
            status = "degraded"
    elif dropped_worktrees:
        # F3 residual -- see _normalize_worktrees's docstring for the measured
        # crash (board.py:41 AttributeError) this closes. Un-crashing alone is
        # not enough: a user with no signal that entries were discarded is the
        # exact "un-crashed but silently dropped" defect this project has
        # already rejected once for the top-level not-a-list case above.
        problems.append(
            "worktrees had %d entr%s with an unusable path; dropped"
            % (dropped_worktrees, "y" if dropped_worktrees == 1 else "ies"))
        if status == "ok":
            status = "degraded"
    for key in ("blocked_by", "issues", "tags"):
        coerced = _as_list(out.get(key))
        if coerced != out.get(key):
            problems.append("%s was not a list; ignored" % key)
            if status == "ok":
                status = "degraded"
        if key == "blocked_by":
            # F3 residual (measured): {"blocked_by":[["u"]]} loaded with
            # _status="ok" and crashed one hop later at columns.py:10 --
            # `threads.get(dep)` raises TypeError: unhashable type: 'list'
            # (a dict element crashes the same way; also unhashable). A
            # thread id is always a string, so any non-string element can
            # never name a real dependency -- dropping it costs the user
            # nothing they could have used. Fixed here, not in columns.py,
            # which is a pure decision layer (zero imports) and must not grow
            # a defensive type check just to survive malformed input this
            # loader should never have handed it in the first place.
            filtered = [dep for dep in coerced if isinstance(dep, str)]
            if len(filtered) != len(coerced):
                problems.append("blocked_by had a non-string entry; dropped")
                if status == "ok":
                    status = "degraded"
            coerced = filtered
        out[key] = coerced
    for key in STRING_LEAF_KEYS:
        val = out.get(key)
        if val is not None and not isinstance(val, str):
            out[key] = str(val)
            problems.append("%s was not a string; coerced to text" % key)
            if status == "ok":
                status = "degraded"
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
    store.makedirs_private(root)
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
    t["worktrees"] = _normalize_worktrees(t.get("worktrees"))[0]
    store.atomic_write_json(_thread_path(threads_dir, tid), t)
    return dict(t, _status="ok", _problems=[])


def mutate(threads_dir, tid, changes, actor="cli", appends=None, removes=None):
    """Locked read-modify-write with a rev CAS. Retries 3x on a rev mismatch.

    `appends` merges list items INSIDE the lock, after the fresh re-read --
    unlike `changes`, which replaces a field wholesale. A caller that
    precomputes `cur + [new]` outside the lock and passes it via `changes`
    reads the same base as a concurrent writer, and the CAS cannot catch it:
    both readers saw the same rev, so the second writer's field-level append
    silently overwrites the first's -- a lost update one layer above the very
    lock this function holds. Do not "simplify" this back into a precomputed
    list passed through `changes`.

    `removes` exists for exactly the same reason, in the other direction: a
    precomputed `[x for x in cur if x != gone]` discards any entry a concurrent
    writer appended between the read and the write. Identity is the same
    `_append_identity` key appends uses, so removing a worktree matches on its
    path rather than on the whole dict.
    """
    d = thread_dir(threads_dir, tid)
    path = _thread_path(threads_dir, tid)
    for _ in range(3):
        current = load_thread(threads_dir, tid)
        status = current["_status"]
        if status == "missing":
            # Without this, the write path fails deep inside atomic_write_json
            # with a raw FileNotFoundError traceback and rc 1 -- measured on a
            # one-character id typo, which is the likeliest user error there is.
            raise ThreadNotFound(tid)
        if status == "rejected":
            raise ThreadRejected(current["_problems"][0])
        if status not in ("ok", "degraded"):
            # The other four skeleton statuses (not_utf8, unreadable, empty,
            # corrupt_json, loader_crash) mean the file on disk cannot be
            # safely read. Falling through here writes atomic_write_json's
            # skeleton OVER it -- measured: a 478-byte torn write became a
            # 394-byte skeleton, rc 0, no warning, title/next_action/
            # created_at gone. `degraded` is the deliberate in-memory schema
            # migration and is excluded on purpose -- it must still be
            # writable.
            raise ThreadCorrupt(
                "%s: refusing to write -- record is %s (%s); left untouched"
                % (path, status, "; ".join(current.get("_problems") or []) or "no detail"))
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
            for k, items in (removes or {}).items():
                drop = {_append_identity(k, x) for x in items}
                out[k] = [x for x in _as_list(out.get(k))
                          if _append_identity(k, x) not in drop]
            out["worktrees"] = _normalize_worktrees(out.get("worktrees"))[0]
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
