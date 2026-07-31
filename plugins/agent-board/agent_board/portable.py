"""`abd export` / `abd import` -- one JSON bundle of threads plus their events.

The board lives at <git-common-dir>/agent-board, which is what makes it invisible
to git and free of any per-repo setup. The cost of that choice is that a fresh
clone starts empty and `rm -rf` on a worktree takes the board with it. This is the
way out: a single portable file you can keep anywhere, commit deliberately, or
carry to another machine.

Deliberately NOT a git commit of the threads dir. Six concurrent
`git add -A && git commit` runs were measured to lose five of six to
`index.lock` -- git's index lock is fail-fast, not a queue -- so the board must
never auto-commit anything.
"""
import io
import json
import os

BUNDLE_VERSION = 1
DEFAULT_EVENT_CAP = 1000
KIND = "agent-board-bundle"


def build_bundle(threads_dir, events_per_thread=DEFAULT_EVENT_CAP):
    """Everything needed to reconstruct the store, and nothing derived.

    Cache and the active-thread pin are excluded on purpose: the cache is
    rebuildable and the pin is machine-local (it names what THIS checkout was
    working on). Archived threads are included -- the point of archiving is to
    keep history, so dropping it here would defeat it.
    """
    from agent_board import events as events_mod, model

    threads, unexportable, truncated = {}, [], []
    for tid, thread in model.load_all(threads_dir).items():
        status = thread.get("_status")
        if status not in ("ok", "degraded"):
            # load_all FABRICATES a skeleton (title = the id, everything else the
            # default) for a corrupt, torn or unreadable record. Exporting that
            # would launder damaged data into a clean-looking empty thread and
            # destroy the only copy of whatever was still recoverable on disk.
            unexportable.append({"id": tid, "status": status,
                                 "problems": thread.get("_problems") or []})
            continue
        record = {k: v for k, v in thread.items() if not k.startswith("_")}
        events = events_mod.read_thread_events(threads_dir, tid,
                                               events_per_thread + 1)
        if len(events) > events_per_thread:
            # Say so rather than silently dropping the oldest. A bundle that
            # quietly loses history is worse than one that admits it.
            truncated.append(tid)
            events = events[-events_per_thread:]
        threads[tid] = {"thread": record, "events": events, "status": status}

    archived = {}
    archive_root = os.path.join(threads_dir, "archive")
    try:
        names = sorted(os.listdir(archive_root))
    except OSError:
        names = []
    for name in names:
        path = os.path.join(archive_root, name, "thread.json")
        try:
            with io.open(path, "r", encoding="utf-8", errors="replace") as fh:
                record = json.load(fh)
        except (IOError, OSError, ValueError):
            continue
        # Archiving is one rename, so the events came with it. Exporting the record
        # without them would defeat the only reason to archive instead of delete.
        events = []
        events_dir = os.path.join(archive_root, name, "events")
        try:
            shards = sorted(os.listdir(events_dir))
        except OSError:
            shards = []
        for shard in shards:
            if shard.endswith(".jsonl"):
                events.extend(events_mod.read_events_tail(
                    os.path.join(events_dir, shard), events_per_thread))
        events.sort(key=lambda r: str(r.get("ts") or ""))
        archived[name] = {"thread": record, "events": events[-events_per_thread:]}

    return {"kind": KIND, "bundle_version": BUNDLE_VERSION,
            "threads": threads, "archived": archived,
            "unexportable": unexportable, "truncated": truncated}


def write_bundle(path, bundle):
    with io.open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(bundle, indent=2, sort_keys=True) + "\n")


def read_bundle(path):
    """(bundle, error). Never raises."""
    try:
        with io.open(path, "r", encoding="utf-8", errors="replace") as fh:
            data = json.load(fh)
    except (IOError, OSError) as exc:
        return None, str(exc)
    except ValueError as exc:
        return None, "not valid JSON: %s" % exc
    except RecursionError as exc:
        # A deeply nested document. RecursionError is not a ValueError, so it
        # escaped both this function's "never raises" contract and _cmd_import,
        # producing a traceback and rc 1 on untrusted input.
        return None, "too deeply nested to parse (%s)" % exc
    if not isinstance(data, dict):
        return None, "top level is not an object"
    if data.get("kind") != KIND:
        # Refuse an unrelated JSON file rather than importing whatever happens to
        # parse -- this verb writes into the user's store.
        return None, "not an agent-board bundle (kind=%r)" % data.get("kind")
    version = data.get("bundle_version")
    if not isinstance(version, int) or version > BUNDLE_VERSION:
        return None, ("bundle_version %r is newer than this abd understands (%d)"
                      % (version, BUNDLE_VERSION))
    if not isinstance(data.get("threads"), dict):
        return None, "bundle has no threads object"
    return data, None


def import_bundle(threads_dir, bundle, force=False):
    """(imported, skipped, problems). Existing threads are SKIPPED unless force.

    Never merges a thread record field-by-field. A half-merged thread -- this
    machine's next_action against another machine's blocked_by -- is worse than
    either version alone, and there is no ordering information in a bundle that
    could justify picking a winner. Whole records only, and by default the copy
    already on disk wins.
    """
    from agent_board import events as events_mod, model, store

    imported, skipped, problems = [], [], []
    for tid in sorted(bundle.get("threads") or {}):
        entry = (bundle["threads"] or {}).get(tid) or {}
        record = entry.get("thread")
        if not isinstance(record, dict):
            problems.append("%s: no thread record" % tid)
            continue
        try:
            target_dir = model.thread_dir(threads_dir, tid)
        except model.ThreadNotFound:
            problems.append("%s: not a valid thread id" % tid)
            continue
        exists = os.path.isdir(target_dir)
        if exists and not force:
            skipped.append(tid)
            continue

        record = dict(record)
        record.setdefault("id", tid)
        record.setdefault("schema_version", model.SCHEMA_VERSION)
        # rev restarts at 1 rather than carrying the source's: rev is the CAS
        # token for THIS store's lock, and importing a high rev from elsewhere
        # would make the next local mutate's compare-and-swap meaningless.
        record["rev"] = 1
        # Invariant 4: a mutation takes the O_EXCL lock. Without it an import could
        # land between a concurrent `abd thread set`'s read and its write.
        lk = None
        try:
            lk = store.acquire_thread_lock(target_dir)
        except BaseException:
            lk = None
        try:
            store.makedirs_private(target_dir)
            store.atomic_write_json(os.path.join(target_dir, "thread.json"),
                                    record)
        except OSError as exc:
            problems.append("%s: %s" % (tid, exc))
            continue
        finally:
            try:
                store.release_thread_lock(lk)
            except BaseException:
                pass

        _replay_events(threads_dir, tid, entry.get("events") or [], events_mod)
        imported.append(tid)

    # The archive is part of the bundle, so it is part of the restore. Importing
    # threads while silently discarding `archived` contradicted export, the
    # README and this module's own docstring.
    archive_root = os.path.join(threads_dir, "archive")
    for tid in sorted(bundle.get("archived") or {}):
        entry = (bundle["archived"] or {}).get(tid) or {}
        record = entry.get("thread")
        if not isinstance(record, dict):
            problems.append("archived %s: no thread record" % tid)
            continue
        try:
            model.thread_dir(threads_dir, tid)      # id-shape validation only
        except model.ThreadNotFound:
            problems.append("archived %s: not a valid thread id" % tid)
            continue
        target = os.path.join(archive_root, tid)
        if os.path.lexists(target) and not force:
            skipped.append("archive/" + tid)
            continue
        try:
            store.makedirs_private(target)
            store.atomic_write_json(os.path.join(target, "thread.json"),
                                    dict(record, id=record.get("id") or tid))
        except OSError as exc:
            problems.append("archived %s: %s" % (tid, exc))
            continue
        _write_archived_events(target, entry.get("events") or [])
        imported.append("archive/" + tid)
    return imported, skipped, problems


def _replay_events(threads_dir, tid, events, events_mod):
    """Append only events this store does not already have.

    A bare O_APPEND replay duplicated every event on each --force re-import, and
    re-running the documented command twice is the most ordinary thing a user does.
    Identity is the whole record, which is what makes a genuine repeat -- two
    identical notes at different times differ by `ts`.
    """
    import json as _json

    have = {_json.dumps(r, sort_keys=True)
            for r in events_mod.read_thread_events(threads_dir, tid, 5000)}
    for event in events:
        if not isinstance(event, dict):
            continue
        # Re-appended through the normal writer so shard naming and the size bound
        # apply on THIS host, rather than trusting the bundle's filenames.
        if _json.dumps(event, sort_keys=True) in have:
            continue
        events_mod.append_event(threads_dir, tid, dict(event))


def _write_archived_events(target, events):
    """Archived threads have no live writer, so their shard is written directly --
    read_thread_events is not used on archive/ and append_event refuses to create a
    directory outside threads/."""
    import json as _json

    from agent_board import events as events_mod, store

    rows = [e for e in events if isinstance(e, dict)]
    if not rows:
        return
    events_dir = os.path.join(target, "events")
    try:
        store.makedirs_private(events_dir)
        path = os.path.join(events_dir, events_mod.shard_name())
        with io.open(path, "w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(_json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    except OSError:
        return
