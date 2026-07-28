import os

from agent_board import anchor
from tests.conftest import git


def test_pure_and_subprocess_agree_from_main_worktree(repo_with_worktrees):
    main, _ = repo_with_worktrees
    assert anchor.git_common_dir_pure(str(main)) == anchor.git_common_dir(str(main))
    assert anchor.git_common_dir(str(main)) == os.path.join(str(main), ".git")


def test_pure_and_subprocess_agree_from_linked_worktree(repo_with_worktrees):
    main, wts = repo_with_worktrees
    for wt in wts:
        assert anchor.git_common_dir_pure(str(wt)) == anchor.git_common_dir(str(wt))
        # a linked worktree resolves to the MAIN repo's .git -- one shared board
        assert anchor.git_common_dir(str(wt)) == os.path.join(str(main), ".git")


def test_agree_from_subdirectory_of_a_worktree(repo_with_worktrees):
    main, wts = repo_with_worktrees
    sub = wts[0] / "deep" / "nested"
    sub.mkdir(parents=True)
    got = anchor.git_common_dir_pure(str(sub))
    assert got == anchor.git_common_dir(str(sub))
    assert got == os.path.join(str(main), ".git")


def test_bare_repo_common_dir_is_the_bare_dir_itself(bare_repo_with_worktree):
    bare, wt = bare_repo_with_worktree
    assert anchor.git_common_dir(str(bare)) == str(bare)
    assert anchor.git_common_dir_pure(str(bare)) == str(bare)
    got = anchor.git_common_dir_pure(str(wt))
    assert got == anchor.git_common_dir(str(wt))
    assert got == str(bare)


def test_project_name_strips_dot_git_and_never_returns_the_parent():
    # /srv/x/proj.git must be "proj", not "x"
    assert anchor.project_name("/srv/x/proj.git") == "proj"
    # /srv/x/proj/.git must be "proj"
    assert anchor.project_name("/srv/x/proj/.git") == "proj"


def test_threads_dir_is_inside_the_common_dir(repo_with_worktrees):
    main, wts = repo_with_worktrees
    expected = os.path.join(str(main), ".git", "agent-board")
    assert anchor.resolve_threads_dir(str(main)) == expected
    # every linked worktree resolves to the SAME board
    assert anchor.resolve_threads_dir(str(wts[1])) == expected


def test_env_override_wins(repo_with_worktrees, tmp_path, monkeypatch):
    main, _ = repo_with_worktrees
    monkeypatch.setenv("ABD_THREADS_DIR", str(tmp_path / "elsewhere"))
    assert anchor.resolve_threads_dir(str(main)) == str(tmp_path / "elsewhere")


def test_not_a_repo_returns_none(tmp_path):
    assert anchor.git_common_dir(str(tmp_path)) is None
    assert anchor.resolve_threads_dir(str(tmp_path)) is None


def test_threads_dir_is_invisible_to_git(repo_with_worktrees):
    """The single most important portability property: no .gitignore edit ever."""
    main, _ = repo_with_worktrees
    d = anchor.resolve_threads_dir(str(main))
    os.makedirs(os.path.join(d, "threads", "demo"))
    with open(os.path.join(d, "threads", "demo", "thread.json"), "w") as fh:
        fh.write("{}")
    assert git(main, "status", "--porcelain").strip() == ""
    assert git(main, "clean", "-xdn").strip() == ""


def test_both_resolvers_reject_a_non_directory_start(repo_with_worktrees):
    """The invariant is agreement on EVERY input."""
    main, _ = repo_with_worktrees
    f = main / "base.txt"
    assert f.is_file()
    assert anchor.git_common_dir(str(f)) is None
    assert anchor.git_common_dir_pure(str(f)) is None


def test_submodule_resolves_to_the_superproject(repo_with_submodule):
    """A session inside a submodule must land on the SUPERPROJECT board. Without
    _demodulize it lands on .git/modules/<name>, a different and empty board."""
    outer, sub = repo_with_submodule
    expected = os.path.join(str(outer), ".git")
    assert anchor.git_common_dir(str(sub)) == expected
    assert anchor.git_common_dir_pure(str(sub)) == expected
    assert anchor.resolve_threads_dir(str(sub)) == os.path.join(expected, "agent-board")
