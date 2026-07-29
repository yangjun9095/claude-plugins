import json
import os

import pytest

from agent_board import cli, model, store


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


def test_mutate_on_an_unknown_id_raises_cleanly(tdir):
    """A typo'd id must not reach the write path -- it failed there with a raw
    FileNotFoundError traceback and rc 1."""
    model.new_thread(tdir, "Real Effort")
    with pytest.raises(model.ThreadNotFound):
        model.mutate(tdir, "real-efort", {"goal": "typo"}, actor="cli")
    assert not os.path.exists(os.path.join(tdir, "threads", "real-efort")), \
        "a failed mutate must not create the thread directory"


@pytest.mark.parametrize("body", [
    '{"worktrees": 5}', '{"worktrees": true}', '{"worktrees": 1.5}',
    '{"blocked_by": 7}', '{"issues": "nope"}', '{"tags": {"a": 1}}',
])
def test_load_thread_never_raises_on_a_non_list_field(tdir, body):
    d = os.path.join(tdir, "threads", "x")
    os.makedirs(d)
    with open(os.path.join(d, "thread.json"), "w") as fh:
        fh.write(body)
    t = model.load_thread(tdir, "x")
    assert t["_status"] in ("degraded", "ok", "loader_crash")
    assert isinstance(t["worktrees"], list)
    assert isinstance(t["blocked_by"], list)


def test_a_bare_string_worktrees_is_not_shredded(tdir):
    d = os.path.join(tdir, "threads", "x")
    os.makedirs(d)
    with open(os.path.join(d, "thread.json"), "w") as fh:
        fh.write('{"schema_version": 1, "id": "x", "worktrees": "/abs/path"}')
    assert model.load_thread(tdir, "x")["worktrees"] == []


def test_concurrent_appends_do_not_lose_a_worktree(tdir):
    """The lost update the whole locking design exists to prevent."""
    model.new_thread(tdir, "Race Test")
    a = {"path": "/wt/a", "branch": None, "added_at": None}
    b = {"path": "/wt/b", "branch": None, "added_at": None}
    model.mutate(tdir, "race-test", {}, actor="cli", appends={"worktrees": [a]})
    model.mutate(tdir, "race-test", {}, actor="cli", appends={"worktrees": [b]})
    paths = [w["path"] for w in model.load_thread(tdir, "race-test")["worktrees"]]
    assert paths == ["/wt/a", "/wt/b"], "lost update: %s" % paths


def test_appends_are_idempotent(tdir):
    model.new_thread(tdir, "Dedup Test")
    a = {"path": "/wt/a", "branch": None, "added_at": None}
    model.mutate(tdir, "dedup-test", {}, actor="cli", appends={"worktrees": [a]})
    model.mutate(tdir, "dedup-test", {}, actor="cli", appends={"worktrees": [a]})
    assert len(model.load_thread(tdir, "dedup-test")["worktrees"]) == 1


def test_appends_dedup_by_path_not_whole_record(tdir):
    """The CLI stamps a fresh added_at every invocation, so whole-record equality
    would let `--add-worktree /same/path` run twice append the same worktree
    twice and render it twice on one card. Identity is the path."""
    model.new_thread(tdir, "Restamp Test")
    for stamp in ("2026-07-28T10:00:00Z", "2026-07-28T11:00:00Z"):
        model.mutate(tdir, "restamp-test", {}, actor="cli", appends={
            "worktrees": [{"path": "/wt/same", "branch": None, "added_at": stamp}]})
    wts = model.load_thread(tdir, "restamp-test")["worktrees"]
    assert [w["path"] for w in wts] == ["/wt/same"], wts
    assert wts[0]["added_at"] == "2026-07-28T10:00:00Z", "first add wins"


def test_malformed_worktrees_is_flagged_not_silently_dropped(tdir):
    """Un-crashing is not enough: the user must be told data was discarded."""
    d = os.path.join(tdir, "threads", "x")
    os.makedirs(d)
    with open(os.path.join(d, "thread.json"), "w") as fh:
        fh.write('{"schema_version": 1, "id": "x", "worktrees": "/abs/path"}')
    t = model.load_thread(tdir, "x")
    assert t["worktrees"] == []
    assert t["_status"] == "degraded"
    assert any("worktrees" in p for p in t["_problems"]), t["_problems"]


# --- F1a: mutate must never write over a record it cannot safely read -----

def _torn_write(path):
    """Truncate an existing thread.json mid-object, simulating the torn write
    store.py's own comment calls non-hypothetical ($HOME on this cluster runs
    ~97% full). Returns the truncated bytes."""
    full = open(path, "rb").read()
    torn = full[: len(full) // 2]
    with open(path, "wb") as fh:
        fh.write(torn)
    return open(path, "rb").read()


def test_mutate_refuses_a_torn_write_record(tdir):
    t = model.new_thread(tdir, "Notochord temporal CRE design",
                         goal="a real goal", next_action="run ISM sweep")
    p = os.path.join(tdir, "threads", t["id"], "thread.json")
    before = _torn_write(p)
    assert model.load_thread(tdir, t["id"])["_status"] == "corrupt_json"
    with pytest.raises(model.ThreadCorrupt):
        model.mutate(tdir, t["id"], {"goal": "clobbered"}, actor="cli")
    after = open(p, "rb").read()
    assert after == before, "a torn record must be left byte-for-byte untouched"


def test_cli_thread_set_on_a_torn_record_is_rc2_and_leaves_it_untouched(
        tdir, monkeypatch):
    t = model.new_thread(tdir, "Notochord temporal CRE design",
                         goal="a real goal", next_action="run ISM sweep")
    p = os.path.join(tdir, "threads", t["id"], "thread.json")
    before = _torn_write(p)
    monkeypatch.setenv("ABD_THREADS_DIR", tdir)
    rc = cli.main(["thread", "set", t["id"], "--goal", "clobbered"])
    assert rc == 2
    assert open(p, "rb").read() == before


def test_degraded_records_are_still_writable_by_mutate(tdir):
    """`degraded` (e.g. an in-memory schema migration) is the one non-`ok`
    status mutate must still be able to write -- only ThreadCorrupt's five
    unreadable statuses are refused."""
    d = os.path.join(tdir, "threads", "x")
    os.makedirs(d)
    with open(os.path.join(d, "thread.json"), "w") as fh:
        fh.write('{"id": "x", "title": "no schema_version field"}')
    assert model.load_thread(tdir, "x")["_status"] == "degraded"
    out = model.mutate(tdir, "x", {"goal": "g"}, actor="cli")
    assert out["goal"] == "g"


# --- F1b: an absolute id must not escape the store -------------------------

def test_absolute_id_does_not_escape_the_store(tdir, tmp_path):
    victim_dir = tmp_path / "victim"
    victim_dir.mkdir()
    victim_file = victim_dir / "thread.json"
    victim_file.write_text("IMPORTANT USER DATA")
    with pytest.raises(model.ThreadNotFound):
        model.mutate(tdir, str(victim_dir), {"goal": "pwned"}, actor="cli")
    assert victim_file.read_text() == "IMPORTANT USER DATA"
    assert not (victim_dir / "events").exists()


def test_cli_thread_set_with_an_absolute_id_is_rejected(
        tdir, tmp_path, monkeypatch):
    victim_dir = tmp_path / "victim"
    victim_dir.mkdir()
    victim_file = victim_dir / "thread.json"
    victim_file.write_text("IMPORTANT USER DATA")
    monkeypatch.setenv("ABD_THREADS_DIR", tdir)
    rc = cli.main(["thread", "set", str(victim_dir), "--goal", "pwned"])
    assert rc == 2
    assert victim_file.read_text() == "IMPORTANT USER DATA", \
        "an absolute id must not write outside the store"
    assert not (victim_dir / "events").exists()


@pytest.mark.parametrize("verb,extra", [
    ("set", ["--goal", "pwned"]),
    ("park", []),
    ("done", []),
    ("reopen", []),
])
def test_cli_thread_verbs_all_reject_an_absolute_id(
        tdir, tmp_path, monkeypatch, verb, extra):
    victim_dir = tmp_path / ("victim-%s" % verb)
    victim_dir.mkdir()
    (victim_dir / "thread.json").write_text("IMPORTANT USER DATA")
    monkeypatch.setenv("ABD_THREADS_DIR", tdir)
    rc = cli.main(["thread", verb, str(victim_dir)] + extra)
    assert rc == 2
    assert (victim_dir / "thread.json").read_text() == "IMPORTANT USER DATA"


# --- F1c: the new id-shape guard must accept every id this tool allocates --

@pytest.mark.parametrize("title", [
    "a", "MHB 16 hpf agent-native demo", "Café  ---  Déjà vu!!",
    "archive", "config", "cache", "threads", "!!!",
    "word " * 40, "x" * 100,
])
def test_thread_dir_accepts_every_slugify_output(tdir, title):
    tid = model.slugify(title)
    assert model.thread_dir(tdir, tid).endswith(os.path.join("threads", tid))


def test_thread_dir_accepts_a_suffixed_id_at_the_length_boundary(tdir):
    """A title slugifying to exactly ID_MAX (48) chars, re-used so the second
    thread collides and gets a numeric suffix appended AFTER truncation --
    the allocated id can be up to ID_MAX + len('-9') = 50 characters, longer
    than a naive ID_MAX-only bound would allow."""
    title = "x" * 100
    assert len(model.slugify(title)) == model.ID_MAX
    first = model.new_thread(tdir, title)
    second = model.new_thread(tdir, title)
    assert second["id"] != first["id"]
    model.thread_dir(tdir, first["id"])       # must not raise
    model.thread_dir(tdir, second["id"])      # must not raise
