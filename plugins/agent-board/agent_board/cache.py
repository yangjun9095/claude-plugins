"""TTL cache under <threads_dir>/cache/.

Every probe that costs real time (the forge is ~0.6-0.7 s, ~90% of a cold
render) writes here, and every reader tolerates a miss. A stale entry is served
deliberately rather than blocking a render on a network call: the board says
`stale` and stays useful offline.
"""
import io
import json
import os
import time

from agent_board import store


def path(threads_dir, name):
    return os.path.join(threads_dir, "cache", name)


def read(threads_dir, name, ttl_seconds):
    """(payload, age_seconds, fresh). payload is None on any miss.

    `fresh` is separate from `payload is None` on purpose: an expired entry is
    still worth serving with a marker when the live probe fails.
    """
    target = path(threads_dir, name)
    try:
        age = time.time() - os.stat(target).st_mtime
    except OSError:
        return None, None, False
    try:
        with io.open(target, "r", encoding="utf-8", errors="replace") as fh:
            payload = json.load(fh)
    except (IOError, OSError, ValueError):
        return None, None, False
    return payload, age, age <= ttl_seconds


def write(threads_dir, name, payload):
    """Best effort. A cache that cannot be written must never fail a render."""
    try:
        store.makedirs_private(os.path.join(threads_dir, "cache"))
        # fsync=False: this is a rebuildable cache, and the durability cost is
        # pure waste on a shared filesystem. Torn reads are still impossible --
        # atomic_write_json renames into place either way.
        store.atomic_write_json(path(threads_dir, name), payload, fsync=False)
        return True
    except BaseException:
        return False
