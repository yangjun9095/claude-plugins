"""`abd show`, `abd event add`, and the two on-demand board views."""
import io
import json
import os

from agent_board import board as boardmod
from agent_board import cli, events as events_mod, model, show as showmod
from agent_board.derive import forge, jobs as jobsmod
from tests.conftest import git


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


def _no_signals(monkeypatch):
    monkeypatch.setattr(forge, "load", lambda *a, **k: {
        "prs": {}, "merged": [], "cli": None, "error": None, "stale": False})
    monkeypatch.setattr(jobsmod, "load", lambda *a, **k: {
        "by_thread": {}, "unattributed": [], "scheduler": None, "error": None})


# --- the board now carries structured fields the detail view needs -----------

def test_cards_carry_reasons_as_a_list_not_only_a_badge_string(
        repo_with_worktrees, tmp_path, monkeypatch):
    """`show --json` must not have to re-split rendered prose to learn why a thread
    needs attention."""
    _no_signals(monkeypatch)
    monkeypatch.delenv("ABD_THREADS_DIR", raising=False)
    main, _wts = repo_with_worktrees
    store_dir = _store(tmp_path)
    _thread(store_dir, "waiter", blocked_by=["ghost"])
    board = boardmod.build_board(store_dir, str(main), allow_probe=False)
    card, column = showmod.find_card(board, "waiter")
    assert column == "ACTIVE"
    assert card["attention"] == ["dangling_blocker"]
    assert card["column"] == "ACTIVE"
    # The rendered badge must carry the SAME order as the structured list, or a card
    # and its `abd show` detail disagree -- which is what reusing the board's
    # derivation is meant to make impossible.
    badge = [text for key, text in card["badges"] if key == "needs_attention"][0]
    assert badge == ", ".join(card["attention"])


def test_card_jobs_field_carries_real_rows(repo_with_worktrees, tmp_path,
                                           monkeypatch):
    """`assert card["jobs"] == []` under a stub that returns no jobs asserts the
    FIXTURE, not the code: it survives replacing the field with a literal []. This
    version fails if the plumbing drops the rows."""
    monkeypatch.delenv("ABD_THREADS_DIR", raising=False)
    monkeypatch.setattr(forge, "load", lambda *a, **k: {
        "prs": {}, "merged": [], "cli": None, "error": None, "stale": False})
    monkeypatch.setattr(jobsmod, "load", lambda *a, **k: {
        "by_thread": {"t": [{"id": "77", "state": "RUNNING", "name": "mhb_1"}]},
        "unattributed": [], "scheduler": "slurm", "error": None})
    main, _wts = repo_with_worktrees
    store_dir = _store(tmp_path)
    _thread(store_dir, "t")
    board = boardmod.build_board(store_dir, str(main), allow_probe=False)
    card, _col = showmod.find_card(board, "t")
    assert [j["id"] for j in card["jobs"]] == ["77"]
    detail, _err = showmod.build(board, store_dir, "t")
    assert detail["jobs"][0]["state"] == "RUNNING"


# --- abd show ----------------------------------------------------------------

def test_show_reports_a_missing_thread_rather_than_an_empty_view():
    detail, error = showmod.build({"columns": {}}, "/nowhere", "ghost")
    assert detail is None and "ghost" in error


def test_show_collects_only_this_threads_collisions():
    board = {"columns": {"ACTIVE": [{"id": "me", "title": "T"}]},
             "collisions": [{"a": "me", "b": "you", "severity": "HIGH",
                             "files": ["f.py"]},
                            {"a": "x", "b": "y", "severity": "HIGH",
                             "files": ["g.py"]}]}
    detail, error = showmod.build(board, "/nowhere", "me")
    assert error is None
    assert len(detail["collisions"]) == 1
    assert detail["collisions"][0]["b"] == "you"


def test_show_names_the_other_party_when_this_thread_is_slot_b():
    """derive/collisions.py emits pairs from `sorted(ids)` with b drawn from
    ids[i+1:], so the lexicographically LATER thread is always 'b'. A fixture that
    only ever puts the thread under test in slot 'a' never exercises the else
    branch, and would pass even if it named the wrong thread."""
    board = {"columns": {"ACTIVE": [{"id": "zeta", "title": "T"}]},
             "collisions": [{"a": "alpha", "b": "zeta", "severity": "HIGH",
                             "files": ["f.py"]}]}
    detail, _error = showmod.build(board, "/nowhere", "zeta")
    text = "\n".join(showmod.render(detail))
    assert "HIGH with alpha" in text
    assert "with zeta" not in text          # never names itself as the other party


def test_show_tolerates_a_collision_row_missing_a_key():
    """cache/collisions.json is JSON on disk and hand-editable; a row without "a"
    raised KeyError out of the renderer."""
    board = {"columns": {"ACTIVE": [{"id": "me"}]},
             "collisions": [{"b": "me", "severity": "HIGH", "files": ["f.py"]}]}
    detail, _error = showmod.build(board, "/nowhere", "me")
    assert len(detail["collisions"]) == 1
    showmod.render(detail)                 # must not raise


def test_show_timeline_budget_is_larger_than_the_cards(tmp_path):
    """50 here, 3 on a card, 10 injected: this is the view a human opens when they
    have lost the thread and want the history."""
    store_dir = _store(tmp_path)
    _thread(store_dir, "t")
    for i in range(60):
        events_mod.append_event(store_dir, "t", {"kind": "note", "actor": "cli",
                                                 "text": "e%02d" % i})
    board = {"columns": {"ACTIVE": [{"id": "t", "title": "T"}]}, "collisions": []}
    detail, _error = showmod.build(board, store_dir, "t")
    assert showmod.EVENTS_SHOWN == 50
    assert len(detail["events"]) == 50
    assert detail["events"][-1]["text"] == "e59"        # newest kept, not oldest


def test_show_render_survives_a_thread_with_nothing_declared():
    detail, _error = showmod.build(
        {"columns": {"PARKED": [{"id": "bare"}]}, "collisions": []},
        "/nowhere", "bare")
    text = "\n".join(showmod.render(detail))
    assert "bare" in text and "[PARKED]" in text
    assert "TIMELINE (empty)" in text


def test_show_render_includes_every_section_when_present():
    detail = {"id": "t", "column": "IN REVIEW", "title": "T", "goal": "G",
              "next_action": "N",
              "worktrees": ["feat +1 -0 *2  1h ago"],
              "attention": ["changes_requested"],
              "jobs": [{"id": "9", "state": "RUNNING", "name": "mhb_1",
                        "workdir": "/w", "attributed_by": "name"}],
              "pr": {"number": 7, "state": "OPEN", "reviewDecision": "APPROVED",
                     "url": "https://example.invalid/pr/7"},
              "notes": ["degraded: something"],
              "collisions": [{"a": "t", "b": "other", "severity": "HIGH",
                              "files": ["x.py"]}],
              "events": [{"ts": "2026-01-01T00:00:00Z", "kind": "note",
                          "actor": "cli", "text": "hello"}]}
    text = "\n".join(showmod.render(detail))
    for token in ("[IN REVIEW]", "GOAL", "NEXT ACTION", "#7", "APPROVED",
                  "WORKTREES", "JOBS", "mhb_1", "NEEDS ATTENTION",
                  "changes_requested", "COLLISIONS", "HIGH with other", "x.py",
                  "NOTES", "TIMELINE (last 1)", "hello"):
        assert token in text, token


def test_show_render_ascii_mode_is_pure_ascii():
    detail = {"id": "t", "column": "ACTIVE", "title": "T", "worktrees": ["w"],
              "attention": ["a"], "jobs": [], "notes": ["n"], "collisions": [],
              "events": [], "pr": None}
    text = "\n".join(showmod.render(detail, ascii_mode=True))
    assert all(ord(c) < 128 for c in text)


def test_show_cli_end_to_end(repo_with_worktrees, tmp_path, monkeypatch, capsys):
    _no_signals(monkeypatch)
    main, wts = repo_with_worktrees
    store_dir = _store(tmp_path)
    monkeypatch.setenv("ABD_THREADS_DIR", store_dir)
    _thread(store_dir, "t", title="T", goal="G", worktrees=[{"path": str(wts[0])}])
    assert cli.main(["show", "t", "--root", str(main), "--offline"]) == 0
    out = capsys.readouterr().out
    assert "t  [ACTIVE]" in out and "GOAL" in out


def test_show_cli_json_is_parseable(
        repo_with_worktrees, tmp_path, monkeypatch, capsys):
    _no_signals(monkeypatch)
    main, _wts = repo_with_worktrees
    store_dir = _store(tmp_path)
    monkeypatch.setenv("ABD_THREADS_DIR", store_dir)
    _thread(store_dir, "t", title="T")
    assert cli.main(["show", "t", "--json", "--root", str(main), "--offline"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["id"] == "t" and data["column"] == "ACTIVE"
    assert isinstance(data["events"], list)


def test_show_cli_unknown_id_is_rc_2(
        repo_with_worktrees, tmp_path, monkeypatch, capsys):
    _no_signals(monkeypatch)
    main, _wts = repo_with_worktrees
    monkeypatch.setenv("ABD_THREADS_DIR", _store(tmp_path))
    assert cli.main(["show", "ghost", "--root", str(main), "--offline"]) == 2
    assert "ghost" in capsys.readouterr().err


# --- abd event add -----------------------------------------------------------

def test_event_add_appends_a_note(tmp_path, monkeypatch):
    store_dir = _store(tmp_path)
    _thread(store_dir, "t")
    monkeypatch.setenv("ABD_THREADS_DIR", store_dir)
    assert cli.main(["event", "add", "t", "--kind", "note",
                     "--text", "afternoon on the token stream"]) == 0
    records = events_mod.read_thread_events(store_dir, "t", 10)
    assert len(records) == 1
    assert records[0]["text"] == "afternoon on the token stream"
    assert records[0]["kind"] == "note" and records[0]["actor"] == "cli"


def test_event_add_rejects_an_unknown_kind(tmp_path, monkeypatch, capsys):
    store_dir = _store(tmp_path)
    _thread(store_dir, "t")
    monkeypatch.setenv("ABD_THREADS_DIR", store_dir)
    assert cli.main(["event", "add", "t", "--kind", "bogus", "--text", "x"]) == 2
    err = capsys.readouterr().err
    assert "unknown kind" in err and "session_snapshot" in err
    assert events_mod.read_thread_events(store_dir, "t", 10) == []


def test_event_add_refuses_an_unknown_thread(tmp_path, monkeypatch, capsys):
    """An event under a nonexistent thread is unreadable by every consumer and
    looks like data loss later."""
    store_dir = _store(tmp_path)
    monkeypatch.setenv("ABD_THREADS_DIR", store_dir)
    assert cli.main(["event", "add", "ghost", "--text", "x"]) == 2
    assert "ghost" in capsys.readouterr().err
    assert not os.path.exists(os.path.join(store_dir, "threads", "ghost"))


def test_event_add_defaults_to_note_and_honours_actor(tmp_path, monkeypatch):
    store_dir = _store(tmp_path)
    _thread(store_dir, "t")
    monkeypatch.setenv("ABD_THREADS_DIR", store_dir)
    assert cli.main(["event", "add", "t", "--text", "x", "--actor", "slurm"]) == 0
    record = events_mod.read_thread_events(store_dir, "t", 10)[0]
    assert record["kind"] == "note" and record["actor"] == "slurm"


def test_append_event_locked_takes_the_lock(tmp_path):
    """The lock-free path is safe only for single-node O_APPEND; a cross-node append
    to one file loses 73-74% on NFS. A compute node calls this verb."""
    store_dir = _store(tmp_path)
    _thread(store_dir, "t")
    assert events_mod.append_event_locked(store_dir, "t", {"text": "a"}) is True
    assert len(events_mod.read_thread_events(store_dir, "t", 10)) == 1


def test_append_event_locked_still_writes_when_the_lock_is_bypassed(
        tmp_path, monkeypatch):
    """An event is a convenience, not a correctness dependency: losing it because a
    stale lock timed out would be worse than writing unlocked and saying so."""
    store_dir = _store(tmp_path)
    _thread(store_dir, "t")
    monkeypatch.setattr("agent_board.store.acquire_thread_lock", lambda d: None)
    assert events_mod.append_event_locked(store_dir, "t", {"text": "a"}) is False
    assert len(events_mod.read_thread_events(store_dir, "t", 10)) == 1


def test_event_add_warns_when_it_could_not_lock(tmp_path, monkeypatch, capsys):
    store_dir = _store(tmp_path)
    _thread(store_dir, "t")
    monkeypatch.setenv("ABD_THREADS_DIR", store_dir)
    monkeypatch.setattr("agent_board.store.acquire_thread_lock", lambda d: None)
    assert cli.main(["event", "add", "t", "--text", "x"]) == 0
    assert "without the lock" in capsys.readouterr().err


# --- board --all -------------------------------------------------------------

def test_all_lists_worktrees_no_thread_owns(
        repo_with_worktrees, tmp_path, monkeypatch):
    _no_signals(monkeypatch)
    monkeypatch.delenv("ABD_THREADS_DIR", raising=False)
    main, wts = repo_with_worktrees
    store_dir = _store(tmp_path)
    _thread(store_dir, "owner", worktrees=[{"path": str(wts[0])}])
    board = boardmod.build_board(store_dir, str(main), allow_probe=False,
                                 include_unowned=True)
    paths = {row["path"] for row in board["unowned"]}
    assert os.path.realpath(str(wts[1])) in paths      # unclaimed
    assert os.path.realpath(str(main)) in paths        # the main worktree too
    assert os.path.realpath(str(wts[0])) not in paths  # owned, so excluded


def test_unowned_is_NOT_COMPUTED_by_default(repo_with_worktrees, tmp_path,
                                            monkeypatch):
    """None, not []: the two must stay distinguishable. A snapshot written without
    --all carries "no data"; [] means "looked, found none". Collapsing them let
    `--all --cached` assert every worktree was owned about data it never read."""
    _no_signals(monkeypatch)
    monkeypatch.delenv("ABD_THREADS_DIR", raising=False)
    main, _wts = repo_with_worktrees
    board = boardmod.build_board(_store(tmp_path), str(main), allow_probe=False)
    assert board["unowned"] is None


def test_unowned_skips_a_prunable_worktree(
        repo_with_prunable_worktree, tmp_path, monkeypatch):
    """A worktree whose directory was deleted still appears in porcelain; probing it
    fatals rc 128, so it must never be listed as something to adopt."""
    _no_signals(monkeypatch)
    monkeypatch.delenv("ABD_THREADS_DIR", raising=False)
    main, gone = repo_with_prunable_worktree
    board = boardmod.build_board(_store(tmp_path), str(main), allow_probe=False,
                                 include_unowned=True)
    paths = {row["path"] for row in board["unowned"]}
    assert os.path.realpath(str(gone)) not in paths


def test_unowned_renders_dirty_and_branch(
        repo_with_worktrees, tmp_path, monkeypatch):
    _no_signals(monkeypatch)
    monkeypatch.delenv("ABD_THREADS_DIR", raising=False)
    main, wts = repo_with_worktrees
    (wts[1] / "scratch.txt").write_text("x\n")
    board = boardmod.build_board(_store(tmp_path), str(main), allow_probe=False,
                                 include_unowned=True)
    row = [r for r in board["unowned"]
           if r["path"] == os.path.realpath(str(wts[1]))][0]
    # The fixture names the directory and the branch identically ("wt-b"), so
    # `"wt-b" in text` was satisfied by the printed BASENAME and passed even with
    # the branch field replaced by a constant. Assert the fields, not the blob.
    assert row["dirty"] == 1
    assert row["branch"] == "wt-b"
    assert row["ahead"] == 0 and row["behind"] == 0
    assert row["last_commit"] and row["last_commit"] != "never"
    text = "\n".join(showmod.render_unowned(board["unowned"]))
    assert "abd thread new" in text
    # branch, ahead/behind and last_commit must all reach the rendered line
    line = [ln for ln in text.splitlines() if "wt-b" in ln][0]
    assert "+0 -0" in line and "*1" in line
    assert row["last_commit"] in line


def test_unowned_render_ascii_is_pure_ascii():
    """render_unattributed had this test and render_unowned did not, so its
    non-ASCII bullet went unnoticed under --ascii."""
    rows = [{"path": "/x/wt", "branch": "feat", "ahead": 1, "behind": 2,
             "dirty": 3, "last_commit": "2d ago"}]
    text = "\n".join(showmod.render_unowned(rows, ascii_mode=True))
    assert all(ord(c) < 128 for c in text), text


def test_unowned_render_folds_non_ascii_paths_under_ascii_mode():
    rows = [{"path": "/x/wt-caf\u00e9", "branch": "fe\u00e1t", "ahead": 0,
             "behind": 0, "dirty": 0, "last_commit": "never"}]
    text = "\n".join(showmod.render_unowned(rows, ascii_mode=True))
    assert all(ord(c) < 128 for c in text), text


def test_unowned_render_says_so_when_everything_is_claimed():
    assert "every worktree belongs" in "\n".join(showmod.render_unowned([]))


def test_all_flag_end_to_end_prints_the_section(
        repo_with_worktrees, tmp_path, monkeypatch, capsys):
    _no_signals(monkeypatch)
    main, wts = repo_with_worktrees
    store_dir = _store(tmp_path)
    monkeypatch.setenv("ABD_THREADS_DIR", store_dir)
    _thread(store_dir, "owner", worktrees=[{"path": str(wts[0])}])
    assert cli.main(["board", "--all", "--root", str(main), "--width", "100",
                     "--no-color", "--offline"]) == 0
    captured = capsys.readouterr()
    assert "UNOWNED WORKTREES" in captured.out
    assert "probes every worktree" in captured.err     # honest about the cost


# --- board --unattributed ----------------------------------------------------

def test_unattributed_jobs_are_exposed_as_rows_not_only_a_count(
        repo_with_worktrees, tmp_path, monkeypatch):
    """The footer's count is a count; the view needs the rows, or it silently prints
    'no unattributed jobs' while the footer says three."""
    main, _wts = repo_with_worktrees
    monkeypatch.delenv("ABD_THREADS_DIR", raising=False)
    monkeypatch.setattr(forge, "load", lambda *a, **k: {
        "prs": {}, "merged": [], "cli": None, "error": None, "stale": False})
    monkeypatch.setattr(jobsmod, "load", lambda *a, **k: {
        "by_thread": {}, "scheduler": "slurm", "error": None,
        "unattributed": [{"id": "42", "state": "RUNNING", "name": "x",
                          "workdir": "/w"}]})
    board = boardmod.build_board(_store(tmp_path), str(main), allow_probe=False)
    assert board["signals"]["jobs"]["unattributed"] == 1
    assert board["signals"]["unattributed_jobs"][0]["id"] == "42"


def test_unattributed_view_end_to_end(
        repo_with_worktrees, tmp_path, monkeypatch, capsys):
    main, _wts = repo_with_worktrees
    store_dir = _store(tmp_path)
    monkeypatch.setenv("ABD_THREADS_DIR", store_dir)
    _thread(store_dir, "t")
    monkeypatch.setattr(forge, "load", lambda *a, **k: {
        "prs": {}, "merged": [], "cli": None, "error": None, "stale": False})
    monkeypatch.setattr(jobsmod, "load", lambda *a, **k: {
        "by_thread": {}, "scheduler": "slurm", "error": None,
        "unattributed": [{"id": "42", "state": "RUNNING", "name": "v4-peakspec",
                          "workdir": "/scratch/run"}]})
    assert cli.main(["board", "--unattributed", "--root", str(main),
                     "--offline"]) == 0
    out = capsys.readouterr().out
    assert "UNATTRIBUTED JOBS (1)" in out
    assert "v4-peakspec" in out and "/scratch/run" in out
    assert "--job-prefix" in out                      # tells them the remedy


def test_unattributed_view_when_there_are_none():
    assert showmod.render_unattributed([]) == ["no unattributed jobs"]


def test_unattributed_render_ascii_is_pure_ascii():
    text = "\n".join(showmod.render_unattributed(
        [{"id": "1", "state": "R", "name": "n", "workdir": "/w"}], ascii_mode=True))
    assert all(ord(c) < 128 for c in text)


# --- fixes for the review's confirmed findings -------------------------------

def test_all_still_lists_unowned_when_the_store_has_no_threads(
        repo_with_worktrees, tmp_path, monkeypatch, capsys):
    """An empty store is --all's PRIMARY use case -- nothing is tracked yet, so
    every worktree is unowned. The empty-store early return used to swallow the
    whole section after paying for the probe."""
    _no_signals(monkeypatch)
    main, _wts = repo_with_worktrees
    monkeypatch.setenv("ABD_THREADS_DIR", _store(tmp_path))
    assert cli.main(["board", "--all", "--root", str(main), "--width", "100",
                     "--no-color", "--offline"]) == 0
    out = capsys.readouterr().out
    assert "no threads yet" in out
    assert "UNOWNED WORKTREES (3)" in out          # main + wt-a + wt-b


def test_unattributed_still_works_when_the_store_has_no_threads(
        repo_with_worktrees, tmp_path, monkeypatch, capsys):
    """With zero threads, 100% of jobs are unattributed -- the one state where this
    view matters most is the one where it printed 'no threads yet' and exited."""
    main, _wts = repo_with_worktrees
    monkeypatch.setenv("ABD_THREADS_DIR", _store(tmp_path))
    monkeypatch.setattr(forge, "load", lambda *a, **k: {
        "prs": {}, "merged": [], "cli": None, "error": None, "stale": False})
    monkeypatch.setattr(jobsmod, "load", lambda *a, **k: {
        "by_thread": {}, "scheduler": "slurm", "error": None,
        "unattributed": [{"id": "9", "state": "RUNNING", "name": "orphan"}]})
    assert cli.main(["board", "--unattributed", "--root", str(main),
                     "--offline"]) == 0
    out = capsys.readouterr().out
    assert "UNATTRIBUTED JOBS (1)" in out and "orphan" in out
    assert "no threads yet" not in out


def test_all_with_cached_refuses_to_claim_ownership_it_never_checked(
        repo_with_worktrees, tmp_path, monkeypatch, capsys):
    """A snapshot from a run WITHOUT --all has no unowned data. Rendering [] made it
    assert 'every worktree belongs to a thread' about worktrees it never probed."""
    _no_signals(monkeypatch)
    main, wts = repo_with_worktrees
    store_dir = _store(tmp_path)
    monkeypatch.setenv("ABD_THREADS_DIR", store_dir)
    _thread(store_dir, "t", worktrees=[{"path": str(wts[0])}])
    assert cli.main(["board", "--root", str(main), "--width", "100",
                     "--no-color", "--offline"]) == 0          # writes a snapshot
    capsys.readouterr()
    assert cli.main(["board", "--all", "--cached", "--root", str(main),
                     "--width", "100", "--no-color"]) == 0
    out = capsys.readouterr().out
    assert "were not computed" in out
    assert "every worktree belongs" not in out


def test_unattributed_on_a_pre_diff_snapshot_refuses_rather_than_saying_none(
        repo_with_worktrees, tmp_path, monkeypatch, capsys):
    """The realistic upgrade path: a snapshot written before this view existed has
    the COUNT but not the rows, so printing 'none' contradicts its own footer."""
    from agent_board import cache
    main, _wts = repo_with_worktrees
    store_dir = _store(tmp_path)
    monkeypatch.setenv("ABD_THREADS_DIR", store_dir)
    cache.write(store_dir, boardmod.SNAPSHOT_NAME, {
        "meta": {"open": 1}, "columns": {"ACTIVE": [{"id": "t", "title": "T"}]},
        "collisions": [], "signals": {"jobs": {"unattributed": 3}}})
    assert cli.main(["board", "--unattributed", "--cached",
                     "--root", str(main)]) == 2
    captured = capsys.readouterr()
    assert "predates" in captured.err
    assert "no unattributed jobs" not in captured.out


def test_cached_unattributed_states_the_snapshot_age(repo_with_worktrees,
                                                     tmp_path, monkeypatch,
                                                     capsys):
    from agent_board import cache
    main, _wts = repo_with_worktrees
    store_dir = _store(tmp_path)
    monkeypatch.setenv("ABD_THREADS_DIR", store_dir)
    cache.write(store_dir, boardmod.SNAPSHOT_NAME, {
        "meta": {"open": 1}, "columns": {"ACTIVE": [{"id": "t", "title": "T"}]},
        "collisions": [],
        "signals": {"unattributed_jobs": [{"id": "9", "state": "R", "name": "n"}]}})
    assert cli.main(["board", "--unattributed", "--cached",
                     "--root", str(main)]) == 0
    out = capsys.readouterr().out
    assert "snapshot from" in out                  # never presented as live


def test_watch_refuses_flags_it_cannot_honour(repo_with_worktrees, tmp_path,
                                              monkeypatch, capsys):
    """--watch previously swallowed --all while STILL paying its per-worktree probe
    on every refresh, forever, and never painting a single unowned row."""
    main, _wts = repo_with_worktrees
    monkeypatch.setenv("ABD_THREADS_DIR", _store(tmp_path))
    for flag in ("--all", "--unattributed", "--json"):
        assert cli.main(["board", "--watch", flag, "--root", str(main)]) == 2
        assert "cannot be combined" in capsys.readouterr().err


def test_unattributed_and_all_are_refused_together(repo_with_worktrees, tmp_path,
                                                   monkeypatch, capsys):
    main, _wts = repo_with_worktrees
    monkeypatch.setenv("ABD_THREADS_DIR", _store(tmp_path))
    assert cli.main(["board", "--unattributed", "--all",
                     "--root", str(main), "--offline"]) == 2
    assert "separate views" in capsys.readouterr().err


def test_unowned_skips_a_locked_worktree_whose_directory_is_gone(
        repo_with_worktrees, tmp_path, monkeypatch):
    """git does NOT report `prunable` for a worktree locked and then deleted, so it
    stayed in porcelain and was offered for adoption."""
    import shutil
    _no_signals(monkeypatch)
    monkeypatch.delenv("ABD_THREADS_DIR", raising=False)
    main, _wts = repo_with_worktrees
    locked = tmp_path / "locked-gone"
    git(main, "worktree", "add", "--lock", "-q", "-b", "lk", str(locked))
    shutil.rmtree(str(locked))
    board = boardmod.build_board(_store(tmp_path), str(main), allow_probe=False,
                                 include_unowned=True)
    paths = {row["path"] for row in board["unowned"]}
    assert os.path.realpath(str(locked)) not in paths


def test_show_sanitises_control_characters_from_agent_written_fields(tmp_path):
    """A title with \\x1b[41m left a sticky colour on the terminal, \\x1b[2J cleared
    the screen, and an embedded newline turned one rendered element into two
    physical lines -- breaking the caller's one-line-per-element contract."""
    detail = {"id": "t", "column": "ACTIVE",
              "title": "alpha\nbeta\x1b[41;97mSTICKY\x7f",
              "goal": "g1\ng2", "next_action": "n\rcarriage",
              "worktrees": ["wt\x1b[2Jcleared"], "attention": [], "jobs": [],
              "notes": ["note\nsplit"], "collisions": [], "pr": None,
              "events": [{"ts": "x", "kind": "note", "actor": "cli",
                          "text": "log\x1b[2Jcleared\nsecond"}]}
    lines = showmod.render(detail)
    blob = "\n".join(lines)
    assert "\x1b" not in blob and "\x7f" not in blob and "\r" not in blob
    # one rendered element must stay one physical line
    assert all("\n" not in line for line in lines)


def test_show_timeline_reaches_its_documented_budget_for_large_events(tmp_path):
    """The read window was fixed at 64 KiB, so a 50-event budget silently delivered
    21 once events averaged ~3 KB -- and the header called those 21 the whole tail.
    Every line here is legal (under events.MAX_LINE)."""
    store_dir = _store(tmp_path)
    _thread(store_dir, "big")
    for i in range(60):
        events_mod.append_event(store_dir, "big", {
            "kind": "note", "actor": "cli", "text": "e%02d " % i + "x" * 2900})
    board = {"columns": {"ACTIVE": [{"id": "big", "title": "T"}]},
             "collisions": []}
    detail, _error = showmod.build(board, store_dir, "big")
    assert len(detail["events"]) == 50, len(detail["events"])
    assert detail["events"][-1]["text"].startswith("e59")


def test_offline_jobs_probe_does_not_poison_the_cache(tmp_path, monkeypatch):
    """Writing [] after an offline run stamped a fresh mtime on an empty result, so
    the next ONLINE render served 'no jobs' from cache for the whole TTL."""
    from agent_board import cache
    store_dir = _store(tmp_path)
    monkeypatch.setattr(jobsmod, "detect_scheduler", lambda *a, **k: "slurm")
    out = jobsmod.load(store_dir, {}, {}, allow_probe=False)
    assert out["by_thread"] == {}
    payload, _age, _fresh = cache.read(store_dir, jobsmod.CACHE_NAME, 60)
    assert payload is None, "an offline run must not write a probe result"
