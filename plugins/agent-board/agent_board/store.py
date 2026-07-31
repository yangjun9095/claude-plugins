import binascii
import errno
import io
import json
import os
import random
import socket
import time

_ESTALE_TRIES = 4


def rand6():
    return binascii.hexlify(os.urandom(3)).decode("ascii")


def refresh_dir(d):
    """One listdir to defeat NFS negative-dentry caching: a file created on
    another node was invisible to a peer for 29.55 s without this, 0.003 s with.
    ~1 ms on lustre; ship it unconditionally. Never fatal."""
    try:
        os.listdir(d)
    except OSError:
        pass


def atomic_write_json(path, obj, fsync=True):
    """Write via tempfile-in-the-same-directory + os.replace.

    The temp MUST live in dirname(target): rename(2) is atomic only within one
    filesystem, and $TMPDIR here is a node-local /tmp (EXDEV). Never rewrite in
    place -- in-place O_TRUNC produced torn reads 21% (lustre) / 54% (NFS).
    """
    d = os.path.dirname(os.path.abspath(path))
    tmp = os.path.join(d, ".%s.%d.%s.tmp" % (os.path.basename(path), os.getpid(), rand6()))
    data = json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with io.open(fd, "w", encoding="utf-8") as fh:
            fh.write(data)
            fh.flush()
            if fsync:
                os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    if fsync:  # make the dirent itself durable
        try:
            dfd = os.open(d, os.O_RDONLY)
            try:
                os.fsync(dfd)
            finally:
                os.close(dfd)
        except OSError:
            pass


def atomic_write_text(path, text):
    """Same tmp-in-the-same-directory + os.replace dance as atomic_write_json,
    for the one-line files that are not JSON (the active-thread pin). Kept
    separate rather than generalising atomic_write_json, whose JSON encoding and
    fsync behaviour are pinned by tests."""
    d = os.path.dirname(os.path.abspath(path))
    tmp = os.path.join(d, ".%s.%d.%s.tmp" % (os.path.basename(path), os.getpid(), rand6()))
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with io.open(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def read_text_resilient(path):
    """Return (text, None) or (None, reason). NEVER raises, for ANY input."""
    for k in range(_ESTALE_TRIES):
        try:
            with io.open(path, "r", encoding="utf-8") as fh:
                return fh.read(), None
        except UnicodeDecodeError:            # MUST precede ValueError
            return None, "not_utf8"
        except ValueError:                    # embedded NUL byte in the path
            return None, "bad_path"
        except OSError as exc:
            if exc.errno == errno.ESTALE:
                if k < _ESTALE_TRIES - 1:
                    time.sleep(0.01 * (k + 1))
                    continue
                return None, "estale_giveup"  # reachable, unlike a post-loop return
            if exc.errno == errno.ENOENT:
                return None, "missing"
            return None, "io:%s" % errno.errorcode.get(exc.errno, exc.errno)
    return None, "estale_giveup"              # defensive; loop always returns


HOST = socket.gethostname().split(".")[0].lower()
LOCK_TIMEOUT_S = 5.0


class Lock(object):
    __slots__ = ("fd", "path")

    def __init__(self, fd, path):
        self.fd = fd
        self.path = path


def _discard_own_lock(fd, path):
    """Close and remove a lockfile THIS process just created with O_EXCL.

    Not the forbidden "break another holder's lock" -- O_EXCL succeeding proves
    ownership. Both operations are individually guarded so a failing close
    cannot prevent the unlink, which is the one that matters: a surviving file
    poisons the thread permanently.
    """
    try:
        os.close(fd)
    except OSError:
        pass
    try:
        os.unlink(path)
    except OSError:
        pass


def acquire_thread_lock(thread_dir):
    """Return a Lock, or None meaning FAILED OPEN.

    O_CREAT|O_EXCL is the ONLY permitted primitive: $HOME is mounted
    nolock,local_lock=all, so flock/fcntl are client-local and give no
    cross-node exclusion. Never blocks unboundedly. NEVER breaks another
    holder's lock -- an mtime-based 'break if older than T' branch is the
    classic unlink race and was demonstrated to put two writers in the
    critical section. Stale cleanup is the board's job, not an agent's.

    Creation (O_EXCL open) and population (write the identity metadata) are
    deliberately TWO separate try/except blocks, not one -- do not merge
    them. Once O_EXCL succeeds, this process is the sole owner of that
    inode, so a failure while writing metadata (ENOSPC / EIO -- $HOME on
    this cluster runs ~97% full, so ENOSPC is not hypothetical) MUST unlink
    the file it just created before returning None. Unlinking our OWN
    just-created lock here is not the forbidden "break another holder's
    lock" -- that prohibition is about files created by OTHER processes.
    Skipping this and returning None straight from a single merged
    try/except leaves the orphaned file on disk: every later acquire then
    sees EEXIST and fails open, permanently, since stale-lock cleanup is
    board-side and human-driven, not this function's job.
    """
    p = os.path.join(thread_dir, ".lock")
    deadline = time.time() + LOCK_TIMEOUT_S
    while True:
        try:
            fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                return None                       # fail open
            if time.time() > deadline:
                return None                       # fail open, never wedge
            time.sleep(0.01 + random.random() * 0.02)
            continue
        # O_EXCL succeeded, so this process owns the file. Any failure from
        # here MUST remove it -- unlinking our OWN just-created lock is not
        # the forbidden "break another holder's lock".
        try:
            os.write(fd, json.dumps(
                {"host": HOST, "pid": os.getpid(), "ts": time.time()}).encode("utf-8"))
            os.fsync(fd)
        except OSError:
            _discard_own_lock(fd, p)
            return None                           # fail open, nothing left behind
        except BaseException:
            # Same failure, different exception type. Mirrors
            # atomic_write_json's own `except BaseException: ...; raise`.
            # Re-raise rather than returning None: a signal or an exhausted heap
            # is not a "lock unavailable" condition and must not be downgraded.
            _discard_own_lock(fd, p)
            raise
        return Lock(fd, p)


def release_thread_lock(lk):
    if lk is None:
        return                                    # REQUIRED GUARD -- see the test
    try:
        os.close(lk.fd)
    except OSError:
        pass
    try:
        os.unlink(lk.path)
    except OSError:
        pass
