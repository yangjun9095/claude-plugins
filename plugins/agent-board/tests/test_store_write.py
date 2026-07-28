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
