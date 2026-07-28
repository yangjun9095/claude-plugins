import errno
import json
import os
import subprocess
import sys
import textwrap

from agent_board import store


def test_acquire_then_release_roundtrip(tmp_path):
    lk = store.acquire_thread_lock(str(tmp_path))
    assert lk is not None
    assert os.path.exists(os.path.join(str(tmp_path), ".lock"))
    store.release_thread_lock(lk)
    assert not os.path.exists(os.path.join(str(tmp_path), ".lock"))


def test_release_none_is_a_noop(tmp_path):
    """Regression: an unconditional finally on a None lock deleted the LIVE
    holder's lockfile and admitted a third writer."""
    lk = store.acquire_thread_lock(str(tmp_path))
    store.release_thread_lock(None)          # must not raise, must not unlink
    assert os.path.exists(os.path.join(str(tmp_path), ".lock")), \
        "release(None) must never touch another holder's lock"
    store.release_thread_lock(lk)


def test_second_acquire_fails_open_after_timeout(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "LOCK_TIMEOUT_S", 0.2)
    held = store.acquire_thread_lock(str(tmp_path))
    assert held is not None
    assert store.acquire_thread_lock(str(tmp_path)) is None, "must fail open, not wedge"
    store.release_thread_lock(held)


def test_lockfile_records_holder_identity(tmp_path):
    lk = store.acquire_thread_lock(str(tmp_path))
    meta = json.loads(open(lk.path).read())
    assert meta["pid"] == os.getpid()
    assert meta["host"] == store.HOST
    assert isinstance(meta["ts"], float)
    store.release_thread_lock(lk)


def test_eight_concurrent_writers_preserve_all_eight_mutations(tmp_path):
    """The measurement that overturned the no-lock design: unlocked RMW lost
    5 of 6 updates. With the O_EXCL lock all 8 must survive."""
    target = tmp_path / "thread.json"
    store.atomic_write_json(str(target), {"id": "t"})
    script = textwrap.dedent(
        """
        import json, sys, time
        sys.path.insert(0, %r)
        from agent_board import store
        d, key = sys.argv[1], sys.argv[2]
        p = d + "/thread.json"
        for _ in range(40):
            lk = store.acquire_thread_lock(d)
            if lk is None:
                time.sleep(0.01); continue
            try:
                obj = json.loads(open(p).read())
                obj[key] = 1
                store.atomic_write_json(p, obj)
            finally:
                store.release_thread_lock(lk)
            break
        """
    ) % (os.path.dirname(os.path.dirname(os.path.abspath(store.__file__))),)
    runner = tmp_path / "w.py"
    runner.write_text(script)
    procs = [subprocess.Popen([sys.executable, str(runner), str(tmp_path), "k%d" % i])
             for i in range(8)]
    for p in procs:
        assert p.wait(timeout=60) == 0
    obj = json.loads(target.read_text())
    missing = [("k%d" % i) for i in range(8) if ("k%d" % i) not in obj]
    assert not missing, "lost updates: %s" % missing


def test_failure_after_open_leaves_no_orphan_lockfile(tmp_path, monkeypatch):
    """A failure between O_EXCL succeeding and the metadata being written must
    remove the file we just created. Otherwise the orphan poisons the thread
    permanently: every later acquire sees EEXIST and fails open forever."""
    def enospc(fd, data):
        raise OSError(errno.ENOSPC, "No space left on device")

    monkeypatch.setattr(os, "write", enospc)
    assert store.acquire_thread_lock(str(tmp_path)) is None
    monkeypatch.undo()
    assert not os.path.exists(os.path.join(str(tmp_path), ".lock")), \
        "orphan lockfile would poison this thread forever"
    # and the thread is still usable afterwards
    lk = store.acquire_thread_lock(str(tmp_path))
    assert lk is not None
    store.release_thread_lock(lk)
