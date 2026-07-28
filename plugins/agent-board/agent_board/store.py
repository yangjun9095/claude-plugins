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


def acquire_thread_lock(thread_dir):
    """Return a Lock, or None meaning FAILED OPEN.

    O_CREAT|O_EXCL is the ONLY permitted primitive: $HOME is mounted
    nolock,local_lock=all, so flock/fcntl are client-local and give no
    cross-node exclusion. Never blocks unboundedly. NEVER breaks another
    holder's lock -- an mtime-based 'break if older than T' branch is the
    classic unlink race and was demonstrated to put two writers in the
    critical section. Stale cleanup is the board's job, not an agent's.
    """
    p = os.path.join(thread_dir, ".lock")
    deadline = time.time() + LOCK_TIMEOUT_S
    while True:
        try:
            fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.write(fd, json.dumps(
                {"host": HOST, "pid": os.getpid(), "ts": time.time()}).encode("utf-8"))
            os.fsync(fd)
            return Lock(fd, p)
        except OSError as exc:
            if exc.errno != errno.EEXIST:
                return None                       # fail open
            if time.time() > deadline:
                return None                       # fail open, never wedge
            time.sleep(0.01 + random.random() * 0.02)


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
