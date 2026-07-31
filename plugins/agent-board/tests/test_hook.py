import io
import json
import os
import time

import pytest

from agent_board import anchor, cli, hookimpl, model


def _store(tmp_path):
    d = tmp_path / "board"
    (d / "threads").mkdir(parents=True)
    return str(d)


def _thread(threads_dir, tid, **fields):
    t = dict(model.DECLARED_DEFAULTS)
    t.update({"id": tid, "schema_version": 1, "rev": 1})
    t.update(fields)
    d = os.path.join(threads_dir, "threads", tid)
    os.makedirs(d, exist_ok=True)
    with io.open(os.path.join(d, "thread.json"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps(t))
    return t


# --- fail-open contract ------------------------------------------------------

def test_hook_main_always_returns_zero_on_garbage_stdin(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("not json at all"))
    assert hookimpl.hook_main(["session-start"]) == 0
    assert capsys.readouterr().out == ""


def test_hook_main_unknown_subcommand_is_silent_zero(capsys):
    assert hookimpl.hook_main(["what-is-this"]) == 0
    assert hookimpl.hook_main([]) == 0
    assert capsys.readouterr().out == ""


def test_hook_main_survives_an_exploding_session_start(monkeypatch, capsys):
    monkeypatch.setattr("sys.stdin", io.StringIO("{}"))
    monkeypatch.setattr(hookimpl, "session_start",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert hookimpl.hook_main(["session-start"]) == 0
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "YES"])
def test_abd_disable_allowlist_disables(monkeypatch, value):
    monkeypatch.setenv("ABD_DISABLE", value)
    assert hookimpl._disabled() is True


@pytest.mark.parametrize("value", ["0", "false", "no", "off", ""])
def test_abd_disable_other_values_do_not_disable(monkeypatch, value):
    """The footgun: `ABD_DISABLE=0` is the natural way to re-enable, and a plain
    truthiness check would silently disable the tool instead -- with no output to
    explain why cards stopped appearing."""
    monkeypatch.setenv("ABD_DISABLE", value)
    monkeypatch.setattr(os.path, "exists", lambda p: False)
    assert hookimpl._disabled() is False


# --- no-op paths produce ZERO stdout ----------------------------------------

def test_payload_without_cwd_is_a_noop(tmp_path):
    """Must never fall back to os.getcwd(): that made empty stdin emit a card for
    whatever directory the hook happened to run in."""
    store_dir = _store(tmp_path)
    assert hookimpl.session_start({}, threads_dir=store_dir) is None
    assert hookimpl.session_start({"cwd": ""}, threads_dir=store_dir) is None
    assert hookimpl.session_start({"cwd": 17}, threads_dir=store_dir) is None


def test_missing_threads_dir_is_a_noop(tmp_path):
    assert hookimpl.session_start({"cwd": str(tmp_path)},
                                  threads_dir=str(tmp_path / "nope")) is None


def test_empty_store_is_a_noop(tmp_path):
    assert hookimpl.session_start({"cwd": str(tmp_path)},
                                  threads_dir=_store(tmp_path)) is None


# --- thread selection --------------------------------------------------------

def test_selection_prefers_env_over_pin(tmp_path, monkeypatch):
    store_dir = _store(tmp_path)
    _thread(store_dir, "aa")
    _thread(store_dir, "bb")
    with io.open(os.path.join(store_dir, "active-thread"), "w") as fh:
        fh.write("bb\n")
    monkeypatch.setenv("ABD_THREAD", "aa")
    threads = model.load_all(store_dir)
    assert hookimpl.select_thread(store_dir, threads, str(tmp_path)) == ("aa", "env")


def test_selection_uses_pin_when_no_env(tmp_path, monkeypatch):
    store_dir = _store(tmp_path)
    _thread(store_dir, "aa")
    _thread(store_dir, "bb")
    monkeypatch.delenv("ABD_THREAD", raising=False)
    with io.open(os.path.join(store_dir, "active-thread"), "w") as fh:
        fh.write("bb\n")
    threads = model.load_all(store_dir)
    assert hookimpl.select_thread(store_dir, threads, str(tmp_path)) == ("bb", "pin")


def test_selection_ignores_a_pin_naming_a_dead_thread(tmp_path, monkeypatch):
    store_dir = _store(tmp_path)
    _thread(store_dir, "aa")
    monkeypatch.delenv("ABD_THREAD", raising=False)
    with io.open(os.path.join(store_dir, "active-thread"), "w") as fh:
        fh.write("deleted-thread\n")
    threads = model.load_all(store_dir)
    assert hookimpl.select_thread(store_dir, threads, str(tmp_path)) == ("aa", "only")


def test_selection_longest_prefix_wins(tmp_path, monkeypatch):
    """A nested worktree must beat its parent, or a session in the nested one
    gets the outer thread's card."""
    monkeypatch.delenv("ABD_THREAD", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    store_dir = _store(tmp_path)
    outer = tmp_path / "repo"
    inner = outer / "nested"
    inner.mkdir(parents=True)
    _thread(store_dir, "outer-t", worktrees=[{"path": str(outer)}])
    _thread(store_dir, "inner-t", worktrees=[{"path": str(inner)}])
    threads = model.load_all(store_dir)
    assert hookimpl.select_thread(store_dir, threads, str(inner)) == ("inner-t", "cwd")
    assert hookimpl.select_thread(store_dir, threads, str(outer)) == ("outer-t", "cwd")


def test_selection_does_not_match_a_sibling_sharing_a_prefix(tmp_path, monkeypatch):
    """'/x/repo-old' must not match the thread owning '/x/repo'. A plain
    startswith would, and would inject a completely unrelated card."""
    monkeypatch.delenv("ABD_THREAD", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    store_dir = _store(tmp_path)
    (tmp_path / "repo").mkdir()
    sibling = tmp_path / "repo-old"
    sibling.mkdir()
    _thread(store_dir, "t-repo", worktrees=[{"path": str(tmp_path / "repo")}])
    _thread(store_dir, "t-other", worktrees=[{"path": str(tmp_path / "elsewhere")}])
    threads = model.load_all(store_dir)
    tid, how = hookimpl.select_thread(store_dir, threads, str(sibling))
    assert (tid, how) != ("t-repo", "cwd")
    assert how == "ambiguous"


def test_selection_falls_back_to_claude_project_dir(tmp_path, monkeypatch):
    monkeypatch.delenv("ABD_THREAD", raising=False)
    store_dir = _store(tmp_path)
    work = tmp_path / "work"
    work.mkdir()
    _thread(store_dir, "p1", worktrees=[{"path": str(work)}])
    _thread(store_dir, "p2", worktrees=[{"path": str(tmp_path / "other")}])
    monkeypatch.setenv("CLAUDE_PROJECT_DIR", str(work))
    threads = model.load_all(store_dir)
    elsewhere = tmp_path / "unrelated"
    elsewhere.mkdir()
    assert hookimpl.select_thread(store_dir, threads,
                                  str(elsewhere)) == ("p1", "project")


def test_selection_never_guesses_between_two(tmp_path, monkeypatch):
    monkeypatch.delenv("ABD_THREAD", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    store_dir = _store(tmp_path)
    _thread(store_dir, "aa")
    _thread(store_dir, "bb")
    threads = model.load_all(store_dir)
    assert hookimpl.select_thread(store_dir, threads,
                                  str(tmp_path)) == (None, "ambiguous")


def test_selection_skips_done_threads_for_the_single_case(tmp_path, monkeypatch):
    monkeypatch.delenv("ABD_THREAD", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    store_dir = _store(tmp_path)
    _thread(store_dir, "live")
    _thread(store_dir, "closed", done=True)
    threads = model.load_all(store_dir)
    assert hookimpl.select_thread(store_dir, threads, str(tmp_path)) == ("live", "only")


# --- card content ------------------------------------------------------------

def test_card_falls_back_to_id_when_title_is_missing():
    """`"...%s" % t.get("title") or t.get("id")` parses as ("...%s" % title) or
    id -- the left operand is never empty, so the fallback is dead code and the
    header renders the literal 'None'."""
    card = hookimpl.build_card({"id": "my-thread", "title": None}, [], [])
    assert "## agent-board thread: my-thread" in card
    assert "None" not in card.splitlines()[0]


def test_card_reports_blocked_by_with_the_do_not_assume_warning():
    card = hookimpl.build_card(
        {"id": "t", "title": "T", "blocked_by": ["dep-a", "dep-b"]}, [], [])
    assert "BLOCKED BY: dep-a, dep-b" in card
    assert "do not assume" in card.lower()


def test_card_shows_done_and_parked_banners():
    done = hookimpl.build_card({"id": "t", "done": True}, [], [])
    assert "STATUS: DONE" in done
    parked = hookimpl.build_card(
        {"id": "t", "parked": True, "parked_reason": "waiting on review"}, [], [])
    assert "STATUS: PARKED" in parked and "waiting on review" in parked


def test_card_is_truncated_and_stays_wrapped():
    body = hookimpl.build_card({"id": "t", "goal": "g" * 8000}, [], [])
    wrapped = hookimpl.wrap_card(body)
    assert len(wrapped) <= hookimpl.CARD_MAX
    assert wrapped.startswith("<agent-board-thread>")
    assert wrapped.endswith("</agent-board-thread>")
    assert "truncated" in wrapped


def test_card_round_trips_quotes_and_newlines_through_json(tmp_path, monkeypatch):
    """Never hand-roll the JSON escaping: a multi-line goal with embedded quotes
    must survive, and Claude discards output whose leading '{' does not parse."""
    monkeypatch.delenv("ABD_THREAD", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    store_dir = _store(tmp_path)
    _thread(store_dir, "q", title='say "hi"', goal="line one\nline \"two\"")
    monkeypatch.setattr("sys.stdin", io.StringIO(
        json.dumps({"cwd": str(tmp_path)})))
    monkeypatch.setattr(anchor, "resolve_threads_dir_pure", lambda s=None: store_dir)
    import sys
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    assert hookimpl.hook_main(["session-start"]) == 0
    payload = json.loads(buf.getvalue())
    text = payload["hookSpecificOutput"]["additionalContext"]
    assert 'say "hi"' in text
    assert 'line "two"' in text
    assert payload["hookSpecificOutput"]["hookEventName"] == "SessionStart"


def test_non_ascii_title_does_not_raise_under_c_locale(tmp_path, monkeypatch):
    card = hookimpl.build_card({"id": "t", "title": "café → naïve"}, [], [])
    assert "café" in card


# --- collisions cache --------------------------------------------------------

def _write_collisions(threads_dir, obj, age_s=0):
    d = os.path.join(threads_dir, "cache")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, "collisions.json")
    with io.open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(obj))
    if age_s:
        old = time.time() - age_s
        os.utime(path, (old, old))
    return path


def test_high_collisions_are_read_from_cache(tmp_path):
    """The row schema here is the one derive/collisions.py actually writes: one
    row per PAIR, keyed a/b with a files list. An earlier version of this test
    asserted a {"path", "threads"} shape that no writer ever produced, so it
    passed while the reader returned [] for every real cache file."""
    store_dir = _store(tmp_path)
    _write_collisions(store_dir, {"collisions": [
        {"a": "me", "b": "them", "severity": "HIGH", "files": ["src/a.py"]},
        {"a": "me", "b": "them", "severity": "LOW", "files": ["src/b.py"]},
    ]})
    out = hookimpl.read_collisions(store_dir, "me")
    assert len(out) == 1 and "src/a.py" in out[0] and "them" in out[0]


def test_collision_row_for_another_pair_is_not_shown(tmp_path):
    store_dir = _store(tmp_path)
    _write_collisions(store_dir, {"collisions": [
        {"a": "x", "b": "y", "severity": "HIGH", "files": ["src/a.py"]}]})
    assert hookimpl.read_collisions(store_dir, "me") == []


def test_long_file_lists_are_summarised(tmp_path):
    store_dir = _store(tmp_path)
    _write_collisions(store_dir, {"collisions": [
        {"a": "me", "b": "them", "severity": "HIGH",
         "files": ["f%d.py" % i for i in range(9)]}]})
    out = hookimpl.read_collisions(store_dir, "me")
    assert "+6 more" in out[0]


def test_stale_collisions_are_ignored_entirely(tmp_path):
    store_dir = _store(tmp_path)
    _write_collisions(store_dir, {"collisions": [
        {"a": "me", "b": "them", "severity": "HIGH", "files": ["src/a.py"]}]},
        age_s=25 * 3600)
    assert hookimpl.read_collisions(store_dir, "me") == []


def test_absent_or_malformed_collisions_cache_is_not_fatal(tmp_path):
    store_dir = _store(tmp_path)
    assert hookimpl.read_collisions(store_dir, "me") == []
    _write_collisions(store_dir, {"collisions": "not-a-list"})
    assert hookimpl.read_collisions(store_dir, "me") == []
    _write_collisions(store_dir, [1, 2, 3])
    assert hookimpl.read_collisions(store_dir, "me") == []


# --- nudge -------------------------------------------------------------------

def test_nudge_stamps_before_emitting_and_then_stays_quiet(tmp_path, monkeypatch):
    """The stamp is written BEFORE the nudge is emitted so a crash afterwards
    cannot turn into a nag on every subsequent session."""
    monkeypatch.delenv("ABD_THREAD", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    store_dir = _store(tmp_path)
    _thread(store_dir, "closed", done=True)          # >=1 thread, none live
    now = time.time()
    first = hookimpl.session_start({"cwd": str(tmp_path)},
                                   threads_dir=store_dir, now=now)
    assert first is not None and "not tracked by any open thread" in first
    second = hookimpl.session_start({"cwd": str(tmp_path)},
                                    threads_dir=store_dir, now=now + 60)
    assert second is None


def test_nudge_key_distinguishes_worktrees_with_a_long_shared_suffix(tmp_path):
    """sha1 of the realpath, NOT a truncation of the mangled path: two worktrees
    sharing a long suffix would collide and one would be silenced forever."""
    a = tmp_path / "alpha" / "worktrees" / "a-very-long-shared-suffix-name"
    b = tmp_path / "beta" / "worktrees" / "a-very-long-shared-suffix-name"
    a.mkdir(parents=True)
    b.mkdir(parents=True)
    store_dir = _store(tmp_path)
    now = time.time()
    assert hookimpl._nudged_recently(store_dir, str(a), now) is False
    assert hookimpl._nudged_recently(store_dir, str(b), now) is False
    assert hookimpl._nudged_recently(store_dir, str(a), now) is True


def test_ambiguity_prompt_is_not_rate_limited(tmp_path, monkeypatch):
    monkeypatch.delenv("ABD_THREAD", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    store_dir = _store(tmp_path)
    _thread(store_dir, "aa")
    _thread(store_dir, "bb")
    now = time.time()
    for _ in range(3):
        out = hookimpl.session_start({"cwd": str(tmp_path)},
                                     threads_dir=store_dir, now=now)
        assert out is not None and "abd thread use" in out


# --- session end -------------------------------------------------------------

def test_session_end_appends_one_snapshot_and_never_touches_thread_json(
        tmp_path, monkeypatch, repo_with_worktrees):
    monkeypatch.delenv("ABD_THREAD", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    main, _wts = repo_with_worktrees
    store_dir = _store(tmp_path)
    _thread(store_dir, "t1", worktrees=[{"path": str(main)}])
    thread_json = os.path.join(store_dir, "threads", "t1", "thread.json")
    before = io.open(thread_json, "rb").read()

    rc = hookimpl.session_end(
        {"cwd": str(main), "session_id": "sess-42", "reason": "prompt_input_exit"},
        threads_dir=store_dir)
    assert rc == 0
    assert io.open(thread_json, "rb").read() == before

    from agent_board import events as events_mod
    records = events_mod.read_thread_events(store_dir, "t1", 10)
    assert len(records) == 1
    rec = records[0]
    assert rec["kind"] == "session_snapshot"
    assert rec["actor"] == "hook"
    assert rec["session_id"] == "sess-42"
    assert rec["reason"] == "prompt_input_exit"
    assert rec["worktree"] == os.path.realpath(str(main))
    assert len(rec["head"]) >= 4          # real repo -> a real abbreviated sha


def test_session_end_omits_head_outside_a_repo(tmp_path, monkeypatch):
    monkeypatch.delenv("ABD_THREAD", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    store_dir = _store(tmp_path)
    plain = tmp_path / "not-a-repo"
    plain.mkdir()
    _thread(store_dir, "t1", worktrees=[{"path": str(plain)}])
    assert hookimpl.session_end({"cwd": str(plain)}, threads_dir=store_dir) == 0
    from agent_board import events as events_mod
    records = events_mod.read_thread_events(store_dir, "t1", 10)
    assert len(records) == 1
    assert "head" not in records[0]


def test_session_end_is_a_noop_with_no_owning_thread(tmp_path, monkeypatch):
    monkeypatch.delenv("ABD_THREAD", raising=False)
    monkeypatch.delenv("CLAUDE_PROJECT_DIR", raising=False)
    store_dir = _store(tmp_path)
    _thread(store_dir, "aa")
    _thread(store_dir, "bb")                 # ambiguous -> no attribution
    assert hookimpl.session_end({"cwd": str(tmp_path)}, threads_dir=store_dir) == 0
    from agent_board import events as events_mod
    assert events_mod.read_thread_events(store_dir, "aa", 10) == []
    assert events_mod.read_thread_events(store_dir, "bb", 10) == []


# --- the pure resolver must agree with the subprocess one -------------------

def test_pure_and_subprocess_threads_dir_agree(repo_with_worktrees, monkeypatch):
    """The hook uses the pure resolver and the CLI uses the subprocess one;
    disagreement means two different boards for one repo."""
    monkeypatch.delenv("ABD_THREADS_DIR", raising=False)
    main, wts = repo_with_worktrees
    for path in [main] + list(wts):
        assert (anchor.resolve_threads_dir_pure(str(path))
                == anchor.resolve_threads_dir(str(path)))


def test_pure_resolver_honours_the_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("ABD_THREADS_DIR", str(tmp_path / "elsewhere"))
    assert anchor.resolve_threads_dir_pure(str(tmp_path)) == str(tmp_path / "elsewhere")


# --- thread use --------------------------------------------------------------

def test_thread_use_writes_the_pin_and_the_hook_reads_it(tmp_path, monkeypatch):
    monkeypatch.delenv("ABD_THREAD", raising=False)
    store_dir = _store(tmp_path)
    _thread(store_dir, "aa")
    _thread(store_dir, "bb")
    monkeypatch.setenv("ABD_THREADS_DIR", store_dir)
    assert cli.main(["thread", "use", "bb"]) == 0
    threads = model.load_all(store_dir)
    assert hookimpl.select_thread(store_dir, threads, str(tmp_path)) == ("bb", "pin")


def test_thread_use_rejects_an_unknown_id(tmp_path, monkeypatch, capsys):
    store_dir = _store(tmp_path)
    _thread(store_dir, "aa")
    monkeypatch.setenv("ABD_THREADS_DIR", store_dir)
    assert cli.main(["thread", "use", "nope"]) == 2
    assert not os.path.exists(os.path.join(store_dir, "active-thread"))
    assert "nope" in capsys.readouterr().err


# --- thread set: the flags the skill instructs agents to use ------------------

def _read_thread(store_dir, tid):
    with io.open(os.path.join(store_dir, "threads", tid, "thread.json"),
                 encoding="utf-8") as fh:
        return json.load(fh)


def test_job_prefix_can_be_set_after_creation(tmp_path, monkeypatch):
    """Shipped job attribution is useless if the prefix can only be declared at
    `thread new` time -- and the documented command was `thread set --job-prefix`."""
    store_dir = _store(tmp_path)
    _thread(store_dir, "t")
    monkeypatch.setenv("ABD_THREADS_DIR", store_dir)
    assert cli.main(["thread", "set", "t", "--job-prefix", "mhb_"]) == 0
    assert _read_thread(store_dir, "t")["job_name_prefix"] == "mhb_"


def test_issues_accumulate_and_do_not_duplicate(tmp_path, monkeypatch):
    store_dir = _store(tmp_path)
    _thread(store_dir, "t")
    monkeypatch.setenv("ABD_THREADS_DIR", store_dir)
    assert cli.main(["thread", "set", "t", "--issue", "7", "--issue", "9"]) == 0
    assert cli.main(["thread", "set", "t", "--issue", "9"]) == 0
    assert sorted(_read_thread(store_dir, "t")["issues"]) == [7, 9]


def test_clear_blocked_by_unblocks_without_hand_editing_json(tmp_path, monkeypatch):
    """The skill forbids writing thread.json directly, so a thread with no way to
    clear its blockers would be permanently stuck in BLOCKED."""
    store_dir = _store(tmp_path)
    _thread(store_dir, "t", blocked_by=["a", "b"])
    monkeypatch.setenv("ABD_THREADS_DIR", store_dir)
    assert cli.main(["thread", "set", "t", "--clear-blocked-by"]) == 0
    assert _read_thread(store_dir, "t")["blocked_by"] == []


def test_rm_worktree_removes_only_the_named_one(tmp_path, monkeypatch):
    store_dir = _store(tmp_path)
    keep, drop = tmp_path / "keep", tmp_path / "drop"
    keep.mkdir()
    drop.mkdir()
    _thread(store_dir, "t", worktrees=[{"path": str(keep)}, {"path": str(drop)}])
    monkeypatch.setenv("ABD_THREADS_DIR", store_dir)
    assert cli.main(["thread", "set", "t", "--rm-worktree", str(drop)]) == 0
    paths = [w["path"] for w in _read_thread(store_dir, "t")["worktrees"]]
    assert paths == [str(keep)]


def test_removal_happens_inside_the_lock_not_precomputed(tmp_path):
    """A precomputed filtered list would discard whatever a concurrent writer
    appended between the read and the write -- the same lost update `appends`
    exists to prevent, in the other direction."""
    from agent_board import model as m
    store_dir = _store(tmp_path)
    _thread(store_dir, "t", worktrees=[{"path": "/a"}, {"path": "/b"}])
    m.mutate(store_dir, "t", {}, appends={"worktrees": [{"path": "/c"}]},
             removes={"worktrees": [{"path": "/a"}]})
    paths = sorted(w["path"] for w in _read_thread(store_dir, "t")["worktrees"])
    assert paths == ["/b", "/c"]


def test_removing_an_absent_worktree_is_a_no_op(tmp_path):
    from agent_board import model as m
    store_dir = _store(tmp_path)
    _thread(store_dir, "t", worktrees=[{"path": "/a"}])
    m.mutate(store_dir, "t", {}, removes={"worktrees": [{"path": "/nope"}]})
    assert [w["path"] for w in _read_thread(store_dir, "t")["worktrees"]] == ["/a"]
