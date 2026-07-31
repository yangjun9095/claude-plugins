import errno
import glob
import io
import json
import os

import pytest

from agent_board import store


def test_atomic_write_creates_parseable_json(tmp_path):
    p = tmp_path / "t.json"
    store.atomic_write_json(str(p), {"a": 1})
    assert json.loads(p.read_text()) == {"a": 1}


def test_atomic_write_leaves_no_temp_files(tmp_path):
    p = tmp_path / "t.json"
    store.atomic_write_json(str(p), {"a": 1})
    assert glob.glob(str(tmp_path / ".*tmp")) == []


def test_atomic_write_output_is_stable_and_newline_terminated(tmp_path):
    p = tmp_path / "t.json"
    store.atomic_write_json(str(p), {"b": 1, "a": 2})
    text = p.read_text()
    assert text.endswith("\n")
    assert text.index('"a"') < text.index('"b"'), "keys must be sorted for stable diffs"


def test_temp_file_is_created_in_the_target_directory(tmp_path, monkeypatch):
    """rename(2) is atomic only within one filesystem, and $TMPDIR here is a
    node-local /tmp -> EXDEV. Capture the temp path to prove it stays put."""
    seen = []
    real_open = os.open

    def spy(path, flags, mode=0o777, *a, **kw):
        if str(path).endswith(".tmp"):
            seen.append(str(path))
        return real_open(path, flags, mode, *a, **kw)

    monkeypatch.setattr(os, "open", spy)
    p = tmp_path / "sub" / "t.json"
    p.parent.mkdir()
    store.atomic_write_json(str(p), {"a": 1})
    assert seen, "no temp file was opened"
    assert os.path.dirname(seen[0]) == str(p.parent)


def test_write_over_an_existing_file_replaces_it(tmp_path):
    p = tmp_path / "t.json"
    store.atomic_write_json(str(p), {"v": 1})
    store.atomic_write_json(str(p), {"v": 2})
    assert json.loads(p.read_text()) == {"v": 2}


def test_failed_serialization_leaves_target_and_dir_clean(tmp_path):
    p = tmp_path / "t.json"
    store.atomic_write_json(str(p), {"v": 1})

    class Unserializable:
        pass

    with pytest.raises(TypeError):
        store.atomic_write_json(str(p), {"bad": Unserializable()})
    assert json.loads(p.read_text()) == {"v": 1}, "target must be untouched"
    assert glob.glob(str(tmp_path / ".*tmp")) == [], "temp must be cleaned up"


def test_read_text_resilient_ok(tmp_path):
    p = tmp_path / "a.txt"
    p.write_text("hello")
    assert store.read_text_resilient(str(p)) == ("hello", None)


def test_read_text_resilient_missing(tmp_path):
    text, err = store.read_text_resilient(str(tmp_path / "nope.txt"))
    assert text is None and err == "missing"


def test_read_text_resilient_not_utf8(tmp_path):
    p = tmp_path / "bad.bin"
    p.write_bytes(b"\xff\xfe\x00garbage")
    text, err = store.read_text_resilient(str(p))
    assert text is None and err == "not_utf8"


def test_read_text_resilient_retries_estale_then_succeeds(tmp_path, monkeypatch):
    p = tmp_path / "a.txt"
    p.write_text("ok")
    calls = {"n": 0}
    real = io.open

    def flaky(*a, **kw):
        calls["n"] += 1
        if calls["n"] == 1:
            raise IOError(errno.ESTALE, "Stale file handle")
        return real(*a, **kw)

    monkeypatch.setattr(io, "open", flaky)
    assert store.read_text_resilient(str(p)) == ("ok", None)
    assert calls["n"] == 2


def test_refresh_dir_never_raises_on_a_missing_dir(tmp_path):
    store.refresh_dir(str(tmp_path / "does-not-exist"))  # must not raise


def test_read_text_resilient_never_raises_on_a_nul_byte_path():
    """`io.open` raises ValueError -- NOT OSError -- for an embedded NUL."""
    text, err = store.read_text_resilient("/tmp/bad\x00path")
    assert text is None and err == "bad_path"


def test_read_text_resilient_reports_estale_giveup_after_exhausting_retries(
        tmp_path, monkeypatch):
    p = tmp_path / "a.txt"
    p.write_text("ok")
    calls = {"n": 0}

    def always_estale(*a, **kw):
        calls["n"] += 1
        raise IOError(errno.ESTALE, "Stale file handle")

    monkeypatch.setattr(io, "open", always_estale)
    monkeypatch.setattr(store.time, "sleep", lambda s: None)   # keep it fast
    text, err = store.read_text_resilient(str(p))
    assert text is None
    assert err == "estale_giveup", "got %r -- the give-up branch is unreachable" % err
    assert calls["n"] == store._ESTALE_TRIES


def test_not_utf8_is_not_misreported_as_bad_path(tmp_path):
    """UnicodeDecodeError subclasses ValueError; wrong arm order breaks this."""
    p = tmp_path / "bad.bin"
    p.write_bytes(b"\xff\xfe\x00garbage")
    assert store.read_text_resilient(str(p)) == (None, "not_utf8")


def test_refresh_dir_on_an_existing_dir_is_a_noop(tmp_path):
    (tmp_path / "f").write_text("x")
    store.refresh_dir(str(tmp_path))
    assert (tmp_path / "f").read_text() == "x"


def test_makedirs_private_applies_0700_to_every_component(tmp_path):
    """os.makedirs(path, 0o700) passes the mode to the LAST component only;
    intermediates get 0o777 & ~umask. Measured before the fix: a 755
    .git/agent-board containing a 700 threads/ -- the data was unreadable but
    the board's existence and its thread ids were not."""
    import os
    from agent_board import store

    deep = tmp_path / "a" / "b" / "c"
    store.makedirs_private(str(deep))
    for part in (tmp_path / "a", tmp_path / "a" / "b", deep):
        assert os.stat(str(part)).st_mode & 0o777 == 0o700, part


def test_makedirs_private_leaves_an_existing_wider_dir_alone(tmp_path):
    """chmod 0o700 on an existing dir would also clear an inherited setgid bit,
    and a deliberately widened directory is the user's decision."""
    import os
    from agent_board import store

    wide = tmp_path / "wide"
    wide.mkdir()
    os.chmod(str(wide), 0o755)
    store.makedirs_private(str(wide / "child"))
    assert os.stat(str(wide)).st_mode & 0o777 == 0o755
    assert os.stat(str(wide / "child")).st_mode & 0o777 == 0o700


def test_makedirs_private_is_idempotent(tmp_path):
    from agent_board import store
    target = str(tmp_path / "x" / "y")
    store.makedirs_private(target)
    store.makedirs_private(target)          # must not raise
