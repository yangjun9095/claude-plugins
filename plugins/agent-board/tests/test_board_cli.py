import json
import os
import subprocess
import sys

import pytest

from agent_board import board, cli, model
from agent_board.derive import git_
from tests.conftest import _init, commit, git


def test_resolve_color_no_color_is_presence_based(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "")          # empty but PRESENT -> disable
    assert cli.resolve_color(None) is False


def test_resolve_color_clicolor_force(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("CLICOLOR_FORCE", "1")
    assert cli.resolve_color(None) is True


def test_resolve_color_clicolor_force_zero_is_not_force(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setenv("CLICOLOR_FORCE", "0")
    assert cli.resolve_color(None) is False      # falls through to isatty (False here)


def test_explicit_flag_overrides_env(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    assert cli.resolve_color(True) is True


def test_resolve_width_explicit_wins(monkeypatch):
    assert cli.resolve_width(150) == 150


def test_resolve_width_clamps_to_100_when_not_a_tty(monkeypatch):
    monkeypatch.delenv("COLUMNS", raising=False)
    assert cli.resolve_width(None) == 100


def test_build_board_puts_a_fresh_thread_in_active(repo_with_worktrees, tmp_path):
    main, wts = repo_with_worktrees
    tdir = str(tmp_path / "tb")
    os.makedirs(os.path.join(tdir, "threads"))
    model.new_thread(tdir, "Fresh Effort",
                     worktrees=[{"path": str(wts[0]), "branch": None, "added_at": None}])
    b = board.build_board(tdir, str(main), None)
    assert [c["id"] for c in b["columns"]["ACTIVE"]] == ["fresh-effort"]


def test_build_board_puts_a_done_thread_in_done(repo_with_worktrees, tmp_path):
    main, wts = repo_with_worktrees
    tdir = str(tmp_path / "tb")
    os.makedirs(os.path.join(tdir, "threads"))
    model.new_thread(tdir, "Finished")
    model.mutate(tdir, "finished", {"done": True}, actor="cli")
    b = board.build_board(tdir, str(main), None)
    assert [c["id"] for c in b["columns"]["DONE"]] == ["finished"]


def test_build_board_marks_a_missing_worktree(repo_with_worktrees, tmp_path):
    main, _ = repo_with_worktrees
    tdir = str(tmp_path / "tb")
    os.makedirs(os.path.join(tdir, "threads"))
    model.new_thread(tdir, "Gone",
                     worktrees=[{"path": "/nonexistent/path",
                                 "branch": None, "added_at": None}])
    b = board.build_board(tdir, str(main), None)
    card = (b["columns"]["ACTIVE"] + b["columns"]["PARKED"])[0]
    assert any("missing" in n for n in card["notes"]), card


def test_build_board_survives_a_corrupt_thread(repo_with_worktrees, tmp_path):
    main, _ = repo_with_worktrees
    tdir = str(tmp_path / "tb")
    os.makedirs(os.path.join(tdir, "threads", "broken"))
    with open(os.path.join(tdir, "threads", "broken", "thread.json"), "w") as fh:
        fh.write("{not json")
    model.new_thread(tdir, "Good")
    b = board.build_board(tdir, str(main), None)
    ids = [c["id"] for cards in b["columns"].values() for c in cards]
    assert "good" in ids and "broken" in ids


@pytest.mark.parametrize("field", ["title", "goal", "next_action"])
@pytest.mark.parametrize("bad_value", [12345, True, ["a", "b"], {"k": 1}])
def test_a_wrong_typed_leaf_does_not_take_down_the_whole_board(
        repo_with_worktrees, tmp_path, field, bad_value):
    """F3: invariant 6 ('one corrupt thread must never take down the board')
    was falsified by a single wrong-typed LEAF (not a wrong-typed list
    container, which the loader already coerced). Measured pre-fix:
    {"title": 12345} rendered rc 1 and ZERO cards -- including the healthy
    thread sharing the same store."""
    main, _ = repo_with_worktrees
    tdir = str(tmp_path / "tb")
    os.makedirs(os.path.join(tdir, "threads", "broken"))
    with open(os.path.join(tdir, "threads", "broken", "thread.json"), "w") as fh:
        json.dump({"schema_version": 1, "id": "broken", field: bad_value}, fh)
    model.new_thread(tdir, "Good")

    rc = cli.main(["board", "--root", str(main), "--store", tdir])
    assert rc == 0

    b = board.build_board(tdir, str(main), None)
    ids = [c["id"] for cards in b["columns"].values() for c in cards]
    assert "good" in ids, "the healthy thread must still render"
    assert "broken" in ids, "the malformed thread must still render (degraded)"
    broken = model.load_thread(tdir, "broken")
    assert broken["_status"] == "degraded"
    assert any(field in p for p in broken["_problems"]), broken["_problems"]


@pytest.mark.parametrize("field,bad_value", [
    ("worktrees", [{"path": 99}]),
    ("blocked_by", [["u"]]),
])
def test_a_nested_malformed_field_does_not_take_down_the_whole_board(
        repo_with_worktrees, tmp_path, field, bad_value):
    """F3 residual: the flat-leaf fix wave (title/goal/next_action/...) missed
    these two NESTED shapes. Both loaded with _status="ok" (not even flagged
    as degraded) and crashed later: {"worktrees":[{"path":99}]} raised
    AttributeError at board.py:41 (int has no .rstrip); {"blocked_by":[["u"]]}
    raised TypeError at columns.py:10 (unhashable list used as a dict key).
    Either crash previously took the WHOLE board down -- zero cards, not one --
    including the healthy thread sharing the same store; that is the invariant
    under test, so this asserts count == 2, not just rc 0."""
    main, _ = repo_with_worktrees
    tdir = str(tmp_path / "tb")
    os.makedirs(os.path.join(tdir, "threads", "broken"))
    with open(os.path.join(tdir, "threads", "broken", "thread.json"), "w") as fh:
        json.dump({"schema_version": 1, "id": "broken", field: bad_value}, fh)
    model.new_thread(tdir, "Good")

    rc = cli.main(["board", "--root", str(main), "--store", tdir])
    assert rc == 0

    b = board.build_board(tdir, str(main), None)
    ids = [c["id"] for cards in b["columns"].values() for c in cards]
    assert ids.count("good") == 1, "the healthy thread must still render"
    assert ids.count("broken") == 1, "the malformed thread must still render (degraded)"
    broken = model.load_thread(tdir, "broken")
    assert broken["_status"] == "degraded"
    assert any(field in p for p in broken["_problems"]), broken["_problems"]


def test_board_survives_a_malformed_config_section(repo_with_worktrees, tmp_path):
    """F4 end-to-end: `{"thresholds": 5}` made `board.build_board`'s
    `cfg.get("thresholds") or DEFAULTS["thresholds"]` keep the truthy int 5,
    and `columns.column()` subscripting `thresholds["active_commit_days"]`
    tracebacked with rc 1. Fixed entirely in config.load_config -- board.py
    is unchanged."""
    main, _ = repo_with_worktrees
    (main / ".agent-board.json").write_text(json.dumps({"thresholds": 5}))
    tdir = str(tmp_path / "tb")
    os.makedirs(os.path.join(tdir, "threads"))
    model.new_thread(tdir, "Effort One")
    rc = cli.main(["board", "--root", str(main), "--store", tdir])
    assert rc == 0


def test_board_json_output_is_machine_readable(repo_with_worktrees, tmp_path, capsys):
    main, wts = repo_with_worktrees
    tdir = str(tmp_path / "tb")
    os.makedirs(os.path.join(tdir, "threads"))
    model.new_thread(tdir, "Effort One")
    rc = cli.main(["board", "--json", "--root", str(main), "--store", tdir])
    assert rc == 0
    payload = json.loads(capsys.readouterr().out)
    assert "columns" in payload and "meta" in payload


def test_board_renders_without_a_tty(repo_with_worktrees, tmp_path, capsys):
    main, _ = repo_with_worktrees
    tdir = str(tmp_path / "tb")
    os.makedirs(os.path.join(tdir, "threads"))
    model.new_thread(tdir, "Effort One", goal="a goal")
    assert cli.main(["board", "--root", str(main), "--store", tdir]) == 0
    out = capsys.readouterr().out
    assert "effort-one" in out and "ACTIVE" in out


def test_board_with_no_threads_prints_a_hint(repo_with_worktrees, tmp_path, capsys):
    main, _ = repo_with_worktrees
    tdir = str(tmp_path / "tb")
    os.makedirs(os.path.join(tdir, "threads"))
    assert cli.main(["board", "--root", str(main), "--store", tdir]) == 0
    assert "no threads yet" in capsys.readouterr().out.lower()


def test_sigpipe_under_head_exits_141(repo_with_worktrees, tmp_path):
    """`abd board --width 240 | head -1` must exit 141, not traceback.

    The board MUST be large enough to fill the pipe buffer, or no broken pipe
    ever occurs and this test certifies nothing. Proven: with a single-thread
    fixture, deleting the `except BrokenPipeError: return 141` handler outright
    still left the test green. The guard below checks `len(size.stdout)`, which
    is a CHARACTER count (subprocess ran with text=True), not a byte count --
    materially smaller than the real byte size here because the board is full
    of multi-byte box-drawing glyphs. Measured directly at width 240, against
    the same two-worktree repo shape this fixture builds: 200 threads ->
    65,636 bytes / 36,873 chars (bytes barely clear 64 KB, chars do not); 300
    threads -> 97,511 bytes / 54,948 chars (chars still short); 400 threads ->
    129,386 bytes / 73,023 chars -- comfortably past 64 KB on BOTH measures,
    so 400 is used for margin on both, not just the byte count the buffer
    itself cares about.
    """
    main, _ = repo_with_worktrees
    tdir = str(tmp_path / "tb")
    os.makedirs(os.path.join(tdir, "threads"))
    for i in range(400):
        model.new_thread(tdir, "Effort number %d with a deliberately long title" % i)
    env = dict(os.environ, PYTHONPATH=os.path.dirname(
        os.path.dirname(os.path.abspath(cli.__file__))))
    size = subprocess.run(
        [sys.executable, "-m", "agent_board", "board", "--width", "240",
         "--root", str(main), "--store", tdir],
        capture_output=True, text=True, env=env)
    assert len(size.stdout) > 65536, (
        "board is only %d bytes; too small to trigger SIGPIPE, so this test "
        "would pass with no handler at all" % len(size.stdout))
    proc = subprocess.run(
        "set -o pipefail; %s -m agent_board board --width 240 --root %s "
        "--store %s | head -1" % (sys.executable, str(main), tdir),
        shell=True, capture_output=True, text=True, env=env,
        executable="/bin/bash")
    assert "Traceback" not in proc.stderr, proc.stderr
    assert proc.returncode == 141, "expected 141, got %d" % proc.returncode


def test_a_prunable_worktree_degrades_one_field(repo_with_worktrees, tmp_path):
    """The existing prunable fixture rmtree's the directory, so os.path.isdir is
    False and the FIRST branch fires -- the `prunable` check was never reached.

    Git's own `prunable` detection (verified directly against `git worktree
    list --porcelain`) checks whether the path recorded in the ADMIN side's
    `.git/worktrees/<id>/gitdir` file still exists -- it does NOT re-read the
    linked worktree's `.git` file content. Overwriting `wt/.git` with a bogus
    `gitdir: ...` pointer (as originally proposed) leaves that recorded path
    existing (just with bad content), so git never reports it prunable, and
    this test would fail. Removing the file outright is what makes the
    recorded path vanish and actually triggers `prunable`.
    """
    main, wts = repo_with_worktrees
    wt = wts[0]
    os.remove(os.path.join(str(wt), ".git"))
    tdir = str(tmp_path / "tb")
    os.makedirs(os.path.join(tdir, "threads"))
    model.new_thread(tdir, "Pruned", worktrees=[
        {"path": str(wt), "branch": None, "added_at": None}])
    b = board.build_board(tdir, str(main), None)
    cards = [c for cards in b["columns"].values() for c in cards]
    assert cards, "the board must still render"
    assert any("missing" in n or "prunable" in n
               for c in cards for n in c["notes"]), cards[0]["notes"]


def test_column_filter_does_not_claim_the_store_is_empty(
        repo_with_worktrees, tmp_path, capsys):
    main, _ = repo_with_worktrees
    tdir = str(tmp_path / "tb")
    os.makedirs(os.path.join(tdir, "threads"))
    model.new_thread(tdir, "Effort One")
    assert cli.main(["board", "--column", "DONE", "--root", str(main),
                     "--store", tdir]) == 0
    out = capsys.readouterr().out
    assert "no threads yet" not in out, out
    assert "DONE" in out


def test_board_does_not_execute_a_foreign_repos_fsmonitor_payload(
        repo_with_worktrees, tmp_path):
    """F2: a thread's recorded worktree path is agent-written and may point
    anywhere on disk -- including into a repo this project does not own. Git
    treats a repository's own config as trusted code: `core.fsmonitor` names
    an arbitrary script that git executes on `status`. Reproduced pre-fix: a
    plain `abd board` ran the payload and touched the marker file.
    """
    main, _ = repo_with_worktrees
    unrelated = _init(tmp_path / "unrelated", branch="trunk")
    commit(unrelated, "f.txt")
    marker = tmp_path / "pwned.marker"
    payload = tmp_path / "payload.sh"
    payload.write_text("#!/bin/sh\ntouch '%s'\nexit 1\n" % marker)
    payload.chmod(0o755)
    git(unrelated, "config", "core.fsmonitor", str(payload))

    tdir = str(tmp_path / "tb")
    os.makedirs(os.path.join(tdir, "threads"))
    model.new_thread(tdir, "Untrusted", worktrees=[
        {"path": str(unrelated), "branch": None, "added_at": None}])

    rc = cli.main(["board", "--root", str(main), "--store", tdir])
    assert rc == 0
    assert not marker.exists(), \
        "abd board executed a foreign repo's fsmonitor payload"


def _derive_for_worktree(main, wt):
    """Build the (rows, wt_index) pair build_board would, then call
    derive_thread directly for a single-worktree thread -- precise enough to
    assert on ahead/behind/age_days without going through card rendering."""
    base = git_.default_branch(str(main))
    rows = git_.branch_rows(str(main), base)
    wt_index = {}
    for row in git_.list_worktrees(str(main)):
        if row.get("bare"):
            continue
        wt_index[os.path.realpath(row["worktree"])] = row
    t = {"worktrees": [{"path": str(wt), "branch": None, "added_at": None}]}
    return board.derive_thread(t, rows, wt_index, {})


def test_derive_thread_picks_the_hierarchical_branch_not_a_flat_namesake(
        tmp_path):
    """F5: a worktree on `feature/auth` (1 ahead) with a FLAT `auth` branch
    also present (0 ahead, same basename). Measured pre-fix: the card showed
    `auth +0 -0 *0` -- the WRONG branch name and the OTHER branch's numbers,
    with no `?` and no badge."""
    main = _init(tmp_path / "main", branch="trunk")
    commit(main, "base.txt")
    git(main, "branch", "auth")                    # flat sibling, 0 ahead
    wt = tmp_path / "wt-auth"
    git(main, "worktree", "add", "-q", "-b", "feature/auth", str(wt))
    commit(wt, "featurework.txt")                   # feature/auth -> 1 ahead

    d, wt_lines, _ = _derive_for_worktree(main, wt)
    assert d["ahead"] == 1 and d["behind"] == 0, d
    assert "feature/auth" in wt_lines[0], wt_lines
    assert wt_lines[0].split()[0] == "feature/auth", wt_lines


def test_derive_thread_reports_real_numbers_for_a_solo_hierarchical_branch(
        tmp_path):
    """F5: a worktree on `feature/solo` with NO flat sibling. Measured
    pre-fix: `+? -? *0 never` -- age_days is None, so PARKED (spec rule 6)
    and the `unpushed` needs_attention reason can never fire for it."""
    main = _init(tmp_path / "main", branch="trunk")
    commit(main, "base.txt")
    wt = tmp_path / "wt-solo"
    git(main, "worktree", "add", "-q", "-b", "feature/solo", str(wt))
    commit(wt, "solowork.txt")

    d, wt_lines, _ = _derive_for_worktree(main, wt)
    assert d["ahead"] == 1 and d["behind"] == 0, d
    assert d["age_days"] is not None, "age_days must not be None for a real commit"
    assert "+?" not in wt_lines[0] and "-?" not in wt_lines[0], wt_lines


def test_an_unknown_column_is_rejected(repo_with_worktrees, tmp_path, capsys):
    main, _ = repo_with_worktrees
    tdir = str(tmp_path / "tb")
    os.makedirs(os.path.join(tdir, "threads"))
    model.new_thread(tdir, "Effort One")
    assert cli.main(["board", "--column", "FOO", "--root", str(main),
                     "--store", tdir]) == 2
    assert "unknown column" in capsys.readouterr().err
