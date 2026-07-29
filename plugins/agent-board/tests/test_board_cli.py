import json
import os
import subprocess
import sys

import pytest

from agent_board import board, cli, model
from tests.conftest import commit, git


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
    """`abd board --width 240 | head -1` must exit 141, not traceback."""
    main, _ = repo_with_worktrees
    tdir = str(tmp_path / "tb")
    os.makedirs(os.path.join(tdir, "threads"))
    model.new_thread(tdir, "Effort One")
    env = dict(os.environ, PYTHONPATH=os.path.dirname(
        os.path.dirname(os.path.abspath(cli.__file__))))
    proc = subprocess.run(
        "%s -m agent_board board --width 240 --root %s --store %s | head -1"
        % (sys.executable, str(main), tdir),
        shell=True, capture_output=True, text=True, env=env)
    assert "Traceback" not in proc.stderr, proc.stderr
