import json
import os

import pytest

from agent_board import model, store


@pytest.fixture
def tdir(tmp_path):
    d = tmp_path / "agent-board"
    (d / "threads").mkdir(parents=True)
    return str(d)


def test_slugify_charset_and_length():
    assert model.slugify("MHB 16 hpf agent-native demo") == "mhb-16-hpf-agent-native-demo"
    assert model.slugify("Café  ---  Déjà vu!!") == "cafe-deja-vu"
    long = model.slugify("word " * 40)
    assert len(long) <= 48 and not long.endswith("-")
    assert all(c.isalnum() or c == "-" for c in long)


def test_slugify_never_returns_empty():
    assert model.slugify("!!!") != ""


def test_new_thread_writes_the_documented_schema(tdir):
    t = model.new_thread(tdir, "My Effort", goal="do a thing")
    assert t["id"] == "my-effort"
    assert t["schema_version"] == model.SCHEMA_VERSION
    assert t["rev"] == 1
    assert t["title"] == "My Effort" and t["goal"] == "do a thing"
    assert t["blocked_by"] == [] and t["worktrees"] == [] and t["issues"] == []
    assert t["parked"] is False and t["done"] is False
    assert t["created_at"].endswith("Z") and t["updated_at"].endswith("Z")
    on_disk = json.loads(open(os.path.join(tdir, "threads", "my-effort", "thread.json")).read())
    assert on_disk["id"] == "my-effort"


def test_new_thread_id_collision_gets_a_numeric_suffix(tdir):
    model.new_thread(tdir, "Same Name")
    second = model.new_thread(tdir, "Same Name")
    assert second["id"] == "same-name-2"


def test_reserved_ids_are_suffixed(tdir):
    for reserved in ("archive", "config", "cache", "threads"):
        t = model.new_thread(tdir, reserved)
        assert t["id"] == reserved + "-thread"


def test_mutate_bumps_rev_and_updated_at(tdir):
    t = model.new_thread(tdir, "E")
    before = t["updated_at"]
    out = model.mutate(tdir, "e", {"next_action": "step 2"}, actor="cli")
    assert out["rev"] == 2
    assert out["next_action"] == "step 2"
    assert out["updated_at"] >= before


def test_mutate_preserves_unknown_fields(tdir):
    model.new_thread(tdir, "E")
    p = os.path.join(tdir, "threads", "e", "thread.json")
    obj = json.loads(open(p).read())
    obj["future_field"] = {"keep": "me"}
    store.atomic_write_json(p, obj)
    out = model.mutate(tdir, "e", {"goal": "g"}, actor="cli")
    assert out["future_field"] == {"keep": "me"}


def test_worktree_string_is_upgraded_to_a_record_on_read(tdir):
    model.new_thread(tdir, "E")
    p = os.path.join(tdir, "threads", "e", "thread.json")
    obj = json.loads(open(p).read())
    obj["worktrees"] = ["/abs/path/wt"]
    store.atomic_write_json(p, obj)
    t = model.load_thread(tdir, "e")
    assert t["worktrees"] == [{"path": "/abs/path/wt", "branch": None, "added_at": None}]


@pytest.mark.parametrize("body,expected", [
    ("", "empty"),
    ("{not json", "corrupt_json"),
    ('{"schema_version": 99, "id": "x"}', "rejected"),
])
def test_corrupt_files_are_reported_not_raised(tdir, body, expected):
    d = os.path.join(tdir, "threads", "x")
    os.makedirs(d)
    with open(os.path.join(d, "thread.json"), "w") as fh:
        fh.write(body)
    t = model.load_thread(tdir, "x")
    assert t["_status"] == expected
    assert t["id"] == "x", "a broken thread must still be renderable"


def test_not_utf8_is_reported(tdir):
    d = os.path.join(tdir, "threads", "x")
    os.makedirs(d)
    with open(os.path.join(d, "thread.json"), "wb") as fh:
        fh.write(b"\xff\xfe\x00")
    assert model.load_thread(tdir, "x")["_status"] == "not_utf8"


def test_load_all_skips_dotfiles_and_isolates_failures(tdir):
    model.new_thread(tdir, "Good One")
    bad = os.path.join(tdir, "threads", "bad")
    os.makedirs(bad)
    with open(os.path.join(bad, "thread.json"), "w") as fh:
        fh.write("{broken")
    os.makedirs(os.path.join(tdir, "threads", ".hidden"))
    all_t = model.load_all(tdir)
    assert set(all_t) == {"good-one", "bad"}
    assert all_t["good-one"]["_status"] == "ok"
    assert all_t["bad"]["_status"] == "corrupt_json"


def test_rejected_thread_is_never_written(tdir):
    d = os.path.join(tdir, "threads", "x")
    os.makedirs(d)
    with open(os.path.join(d, "thread.json"), "w") as fh:
        fh.write('{"schema_version": 99, "id": "x"}')
    with pytest.raises(model.ThreadRejected):
        model.mutate(tdir, "x", {"goal": "g"}, actor="cli")
