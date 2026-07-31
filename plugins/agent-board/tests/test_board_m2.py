"""M2 integration: forge, jobs and collisions reaching the rendered board."""
import io
import json
import os

from agent_board import board as boardmod
from agent_board import model
from agent_board.derive import forge, jobs
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
    """Neutralise both external probes so a test can assert on one signal only."""
    monkeypatch.setattr(forge, "load", lambda *a, **k: {
        "prs": {}, "merged": [], "cli": None, "error": None, "stale": False})
    monkeypatch.setattr(jobs, "load", lambda *a, **k: {
        "by_thread": {}, "unattributed": [], "scheduler": None, "error": None,
        "stale": False})


def _card(data, tid):
    for rows in data["columns"].values():
        for card in rows:
            if card["id"] == tid:
                return card
    return None


def _column_of(data, tid):
    for name, rows in data["columns"].items():
        if any(c["id"] == tid for c in rows):
            return name
    return None


# --- collisions reach the board ---------------------------------------------

def test_high_collision_reaches_the_card_badge(repo_with_worktrees, tmp_path,
                                               monkeypatch):
    _no_signals(monkeypatch)
    monkeypatch.delenv("ABD_THREADS_DIR", raising=False)
    main, wts = repo_with_worktrees
    (main / "shared.py").write_text("v = 0\n")
    git(main, "add", "-A")
    git(main, "commit", "-qm", "shared")
    for wt in wts:
        git(wt, "merge", "-q", "trunk")
        (wt / "shared.py").write_text("edit from %s\n" % wt.name)

    store_dir = _store(tmp_path)
    _thread(store_dir, "alpha", title="A", worktrees=[{"path": str(wts[0])}])
    _thread(store_dir, "beta", title="B", worktrees=[{"path": str(wts[1])}])

    data = boardmod.build_board(store_dir, str(main), allow_probe=False)
    assert data["meta"]["collisions"] == 1
    assert data["collisions"][0]["severity"] == "HIGH"
    badges = dict(_card(data, "alpha")["badges"])
    assert "high_collision" in badges["needs_attention"]
    assert "high_collision" in dict(_card(data, "beta")["badges"])["needs_attention"]


def test_done_threads_are_excluded_from_the_scan(repo_with_worktrees, tmp_path,
                                                 monkeypatch):
    """The performance cap: derivation is limited to worktrees of non-DONE threads.
    A finished thread must not raise a collision at all."""
    _no_signals(monkeypatch)
    monkeypatch.delenv("ABD_THREADS_DIR", raising=False)
    main, wts = repo_with_worktrees
    (main / "shared.py").write_text("v = 0\n")
    git(main, "add", "-A")
    git(main, "commit", "-qm", "shared")
    for wt in wts:
        git(wt, "merge", "-q", "trunk")
        (wt / "shared.py").write_text("edit from %s\n" % wt.name)

    store_dir = _store(tmp_path)
    _thread(store_dir, "alpha", worktrees=[{"path": str(wts[0])}])
    _thread(store_dir, "closed", done=True, worktrees=[{"path": str(wts[1])}])
    data = boardmod.build_board(store_dir, str(main), allow_probe=False)
    assert data["collisions"] == []
    assert _column_of(data, "closed") == "DONE"


def test_signals_block_reports_the_ubiquity_constants(repo_with_worktrees,
                                                      tmp_path, monkeypatch):
    """Both constants are unvalidated against a real noisy repo, so every render
    must surface them or drift is invisible."""
    _no_signals(monkeypatch)
    monkeypatch.delenv("ABD_THREADS_DIR", raising=False)
    main, wts = repo_with_worktrees
    store_dir = _store(tmp_path)
    _thread(store_dir, "alpha", worktrees=[{"path": str(wts[0])}])
    data = boardmod.build_board(store_dir, str(main), allow_probe=False)
    sig = data["signals"]["collisions"]
    assert sig["demote_at"] >= 4
    assert set(sig) == {"demote_at", "demoted", "considered", "degraded",
                        "failed_probes"}


# --- forge reaches the board -------------------------------------------------

def test_open_nondraft_pr_puts_a_thread_in_review(repo_with_worktrees, tmp_path,
                                                  monkeypatch):
    main, wts = repo_with_worktrees
    monkeypatch.delenv("ABD_THREADS_DIR", raising=False)
    monkeypatch.setattr(jobs, "load", lambda *a, **k: {
        "by_thread": {}, "unattributed": [], "scheduler": None, "error": None})
    monkeypatch.setattr(forge, "load", lambda *a, **k: {
        "prs": {"wt-a": {"number": 5, "isDraft": False, "state": "OPEN",
                         "reviewDecision": None, "mergeable": "MERGEABLE"}},
        "merged": [], "cli": "gh", "error": None, "stale": False})
    store_dir = _store(tmp_path)
    _thread(store_dir, "alpha", worktrees=[{"path": str(wts[0])}])
    data = boardmod.build_board(store_dir, str(main), allow_probe=False)
    assert _column_of(data, "alpha") == "IN REVIEW"
    assert _card(data, "alpha")["pr"]["number"] == 5


def test_a_DRAFT_pr_does_not_put_a_thread_in_review(repo_with_worktrees, tmp_path,
                                                    monkeypatch):
    """Nobody is waiting on the human yet."""
    main, wts = repo_with_worktrees
    monkeypatch.delenv("ABD_THREADS_DIR", raising=False)
    monkeypatch.setattr(jobs, "load", lambda *a, **k: {
        "by_thread": {}, "unattributed": [], "scheduler": None, "error": None})
    monkeypatch.setattr(forge, "load", lambda *a, **k: {
        "prs": {"wt-a": {"number": 5, "isDraft": True, "state": "OPEN"}},
        "merged": [], "cli": "gh", "error": None, "stale": False})
    store_dir = _store(tmp_path)
    _thread(store_dir, "alpha", worktrees=[{"path": str(wts[0])}])
    data = boardmod.build_board(store_dir, str(main), allow_probe=False)
    assert _column_of(data, "alpha") != "IN REVIEW"


def test_changes_requested_raises_needs_attention(repo_with_worktrees, tmp_path,
                                                  monkeypatch):
    main, wts = repo_with_worktrees
    monkeypatch.delenv("ABD_THREADS_DIR", raising=False)
    monkeypatch.setattr(jobs, "load", lambda *a, **k: {
        "by_thread": {}, "unattributed": [], "scheduler": None, "error": None})
    monkeypatch.setattr(forge, "load", lambda *a, **k: {
        "prs": {"wt-a": {"number": 5, "isDraft": False, "state": "OPEN",
                         "reviewDecision": "CHANGES_REQUESTED",
                         "mergeable": "CONFLICTING"}},
        "merged": [], "cli": "gh", "error": None, "stale": False})
    store_dir = _store(tmp_path)
    _thread(store_dir, "alpha", worktrees=[{"path": str(wts[0])}])
    data = boardmod.build_board(store_dir, str(main), allow_probe=False)
    reasons = dict(_card(data, "alpha")["badges"])["needs_attention"]
    assert "changes_requested" in reasons and "pr_conflicting" in reasons


def test_a_merged_pr_asks_the_user_to_close_the_thread(
        repo_with_worktrees, tmp_path, monkeypatch):
    """The squash-merge remedy: under squash the merge-base stays put and a landed
    branch reports its full changed set forever, so surface 'mark this done'."""
    main, wts = repo_with_worktrees
    monkeypatch.delenv("ABD_THREADS_DIR", raising=False)
    monkeypatch.setattr(jobs, "load", lambda *a, **k: {
        "by_thread": {}, "unattributed": [], "scheduler": None, "error": None})
    monkeypatch.setattr(forge, "load", lambda *a, **k: {
        "prs": {}, "merged": ["wt-a"], "cli": "gh", "error": None, "stale": False})
    store_dir = _store(tmp_path)
    _thread(store_dir, "alpha", worktrees=[{"path": str(wts[0])}])
    data = boardmod.build_board(store_dir, str(main), allow_probe=False)
    reasons = dict(_card(data, "alpha")["badges"])["needs_attention"]
    assert "pr_merged_thread_open" in reasons


def test_no_forge_cli_degrades_without_breaking_the_board(repo_with_worktrees,
                                                          tmp_path, monkeypatch):
    """IN REVIEW is simply never derived; the board still renders."""
    _no_signals(monkeypatch)
    monkeypatch.delenv("ABD_THREADS_DIR", raising=False)
    main, wts = repo_with_worktrees
    store_dir = _store(tmp_path)
    _thread(store_dir, "alpha", worktrees=[{"path": str(wts[0])}])
    data = boardmod.build_board(store_dir, str(main), allow_probe=False)
    assert data["signals"]["forge"]["cli"] is None
    assert _column_of(data, "alpha") is not None


# --- jobs reach the board ----------------------------------------------------

def test_live_jobs_badge_and_active_column(repo_with_worktrees, tmp_path,
                                           monkeypatch):
    main, wts = repo_with_worktrees
    monkeypatch.delenv("ABD_THREADS_DIR", raising=False)
    monkeypatch.setattr(forge, "load", lambda *a, **k: {
        "prs": {}, "merged": [], "cli": None, "error": None, "stale": False})
    monkeypatch.setattr(jobs, "load", lambda *a, **k: {
        "by_thread": {"alpha": [{"id": "1", "name": "mhb_a", "state": "RUNNING"},
                                {"id": "2", "name": "mhb_b", "state": "PENDING"}]},
        "unattributed": [{"id": "9"}], "scheduler": "slurm", "error": None})
    store_dir = _store(tmp_path)
    _thread(store_dir, "alpha", job_name_prefix="mhb_",
            worktrees=[{"path": str(wts[0])}])
    data = boardmod.build_board(store_dir, str(main), allow_probe=False)
    badges = dict(_card(data, "alpha")["badges"])
    assert badges["live_jobs"] == "2 jobs: 1 PENDING 1 RUNNING"
    assert data["meta"]["live_jobs"] == 2
    assert data["signals"]["jobs"]["unattributed"] == 1
    # a live job forces ACTIVE regardless of commit age
    assert _column_of(data, "alpha") == "ACTIVE"


# --- stale blockers ----------------------------------------------------------

def test_stale_and_dangling_blockers_are_surfaced(repo_with_worktrees, tmp_path,
                                                  monkeypatch):
    _no_signals(monkeypatch)
    monkeypatch.delenv("ABD_THREADS_DIR", raising=False)
    main, wts = repo_with_worktrees
    store_dir = _store(tmp_path)
    _thread(store_dir, "done-dep", done=True)
    _thread(store_dir, "waiter", blocked_by=["done-dep", "ghost"])
    data = boardmod.build_board(store_dir, str(main), allow_probe=False)
    kinds = {(tid, dep, why) for tid, dep, why in data["signals"]["stale_blocks"]}
    assert ("waiter", "done-dep", "DONE") in kinds
    assert ("waiter", "ghost", "MISSING") in kinds
    reasons = dict(_card(data, "waiter")["badges"])["needs_attention"]
    assert "stale_block" in reasons and "dangling_blocker" in reasons


def test_a_block_cycle_is_detected_and_does_not_recurse(repo_with_worktrees,
                                                        tmp_path, monkeypatch):
    _no_signals(monkeypatch)
    monkeypatch.delenv("ABD_THREADS_DIR", raising=False)
    main, _wts = repo_with_worktrees
    store_dir = _store(tmp_path)
    _thread(store_dir, "a", blocked_by=["b"])
    _thread(store_dir, "b", blocked_by=["a"])
    data = boardmod.build_board(store_dir, str(main), allow_probe=False)
    assert data["signals"]["block_cycles"]


# --- footer honesty ----------------------------------------------------------

def test_footer_says_when_pr_state_is_missing():
    """An understated severity that says so is usable; one that stays silent is a
    wrong answer."""
    from agent_board.render.layout import footer_notes
    notes = footer_notes({"signals": {"forge": {"error": "no forge cli on PATH"}}})
    assert any("PR state unavailable" in n and "understated" in n for n in notes)


def test_footer_distinguishes_stale_from_missing():
    from agent_board.render.layout import footer_notes
    notes = footer_notes({"signals": {"forge": {"stale": True, "error": None}}})
    assert any("from cache" in n for n in notes)


def test_footer_reports_demotions_and_degraded_scans():
    from agent_board.render.layout import footer_notes
    notes = footer_notes({"signals": {
        "collisions": {"degraded": True, "failed_probes": 4, "demoted": 3,
                       "demote_at": 7, "considered": 12}}})
    joined = " ".join(notes)
    assert "degraded" in joined and "4" in joined
    assert "demoted as ubiquitous" in joined and "demote_at=7" in joined


def test_footer_points_at_job_name_prefix_for_unattributed_jobs():
    from agent_board.render.layout import footer_notes
    notes = footer_notes({"signals": {"jobs": {"unattributed": 5}}})
    assert any("job_name_prefix" in n for n in notes)


def test_footer_is_silent_when_everything_worked():
    from agent_board.render.layout import footer_notes
    assert footer_notes({"signals": {
        "forge": {"cli": "gh", "error": None, "stale": False},
        "jobs": {"scheduler": None, "error": None, "unattributed": 0},
        "collisions": {"degraded": False, "demoted": 0}}}) == []


def test_offline_forge_reports_not_probed_rather_than_success(
        tmp_path, monkeypatch):
    """cli=gh with error=None and no PRs would present 'no open PRs' as a
    successful answer when nothing was ever asked."""
    from agent_board.derive import forge as forgemod
    monkeypatch.delenv("ABD_ALLOW_NETWORK", raising=False)
    monkeypatch.setattr(forgemod, "detect_cli", lambda *a, **k: "gh")
    out = forgemod.load(_store(tmp_path), "/repo", {}, allow_probe=False)
    assert out["error"] == "offline: not probed"


def test_demoted_files_are_rendered_collapsed_not_dropped():
    from agent_board.render.layout import render_board
    board = {"meta": {}, "columns": {}, "collisions": [
        {"a": "x", "b": "y", "severity": "HIGH", "files": ["real.py"],
         "demoted_files": ["CHANGELOG.md", "README.md"]}]}
    text = "\n".join("".join(s.text for s in line)
                     for line in render_board(board, 100, ascii_mode=True))
    assert "real.py" in text
    assert "2 ubiquitous files demoted" in text


# --- snapshot rendering ------------------------------------------------------

def test_snapshot_age_is_stated_in_the_footer():
    """Rendering a snapshot without saying so would present stale state as live."""
    from agent_board.render.layout import footer_notes
    notes = footer_notes({"signals": {"snapshot_age_s": 3600}})
    assert any("snapshot from 1h ago" in n for n in notes)


def test_ago_formats_each_band():
    from agent_board.render.layout import _ago
    assert _ago(0) == "0s" and _ago(45) == "45s"
    assert _ago(600) == "10m"
    assert _ago(7200) == "2h"
    assert _ago(200000) == "2d"


def test_board_cached_renders_the_snapshot_and_does_not_scan(repo_with_worktrees,
                                                             tmp_path,
                                                             monkeypatch, capsys):
    from agent_board import cache, cli
    main, _wts = repo_with_worktrees
    store_dir = _store(tmp_path)
    monkeypatch.setenv("ABD_THREADS_DIR", store_dir)
    cache.write(store_dir, boardmod.SNAPSHOT_NAME, {
        "meta": {"project": "snap", "open": 1, "live_jobs": 0, "collisions": 0},
        "columns": {"ACTIVE": [{"id": "from-snapshot", "title": "T", "badges": [],
                                "worktrees": [], "notes": []}]},
        "collisions": [], "signals": {}})

    def explode(*a, **kw):
        raise AssertionError("scanned despite --cached")
    monkeypatch.setattr(boardmod, "build_board", explode)
    rc = cli.main(["board", "--cached", "--root", str(main), "--width", "100",
                   "--no-color"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "from-snapshot" in out
    assert "snapshot from" in out


def test_board_cached_falls_back_to_a_real_scan_when_no_snapshot_exists(
        repo_with_worktrees, tmp_path, monkeypatch, capsys):
    from agent_board import cli
    _no_signals(monkeypatch)
    main, wts = repo_with_worktrees
    store_dir = _store(tmp_path)
    monkeypatch.setenv("ABD_THREADS_DIR", store_dir)
    _thread(store_dir, "alpha", worktrees=[{"path": str(wts[0])}])
    rc = cli.main(["board", "--cached", "--root", str(main), "--width", "100",
                   "--no-color"])
    captured = capsys.readouterr()
    assert rc == 0
    assert "no snapshot yet" in captured.err
    assert "alpha" in captured.out


def test_a_live_render_writes_the_snapshot(
        repo_with_worktrees, tmp_path, monkeypatch):
    from agent_board import cache, cli
    _no_signals(monkeypatch)
    main, wts = repo_with_worktrees
    store_dir = _store(tmp_path)
    monkeypatch.setenv("ABD_THREADS_DIR", store_dir)
    _thread(store_dir, "alpha", worktrees=[{"path": str(wts[0])}])
    assert cli.main(["board", "--root", str(main), "--width", "100",
                     "--no-color"]) == 0
    snapshot, _age, _fresh = cache.read(store_dir, boardmod.SNAPSHOT_NAME, 10 ** 9)
    assert snapshot is not None
    assert any(c["id"] == "alpha" for rows in snapshot["columns"].values()
               for c in rows)
