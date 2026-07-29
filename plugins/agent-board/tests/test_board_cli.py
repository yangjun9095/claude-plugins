import json
import os
import subprocess
import sys

import pytest

from agent_board import board, cli, model
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


def test_an_unknown_column_is_rejected(repo_with_worktrees, tmp_path, capsys):
    main, _ = repo_with_worktrees
    tdir = str(tmp_path / "tb")
    os.makedirs(os.path.join(tdir, "threads"))
    model.new_thread(tdir, "Effort One")
    assert cli.main(["board", "--column", "FOO", "--root", str(main),
                     "--store", tdir]) == 2
    assert "unknown column" in capsys.readouterr().err
