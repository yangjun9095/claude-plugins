import binascii
import errno
import io
import json
import os
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
    """Return (text, None) or (None, reason). Never raises."""
    for k in range(_ESTALE_TRIES):
        try:
            with io.open(path, "r", encoding="utf-8") as fh:
                return fh.read(), None
        except UnicodeDecodeError:
            return None, "not_utf8"
        except (IOError, OSError) as exc:
            if exc.errno == errno.ESTALE and k < _ESTALE_TRIES - 1:
                time.sleep(0.01 * (k + 1))
                continue
            if exc.errno == errno.ENOENT:
                return None, "missing"
            return None, "io:%s" % errno.errorcode.get(exc.errno, exc.errno)
    return None, "estale_giveup"
