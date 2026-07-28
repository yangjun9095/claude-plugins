import os

from agent_board.derive import git_
from tests.conftest import commit, git


def test_git_helper_always_passes_no_optional_locks(repo_with_worktrees, monkeypatch):
    """A monitoring tool that breaks the agents it monitors is worse than none:
    plain `git status` took index.lock and failed 13/80 agent operations."""
    main, _ = repo_with_worktrees
    seen = {}
    import subprocess as sp
    real = sp.run

    def spy(cmd, **kw):
        seen["cmd"] = cmd
        seen["env"] = kw.get("env") or {}
        return real(cmd, **kw)

    monkeypatch.setattr(sp, "run", spy)
    git_._git(str(main), "status", "--porcelain")
    assert "--no-optional-locks" in seen["cmd"]
    assert seen["env"].get("GIT_OPTIONAL_LOCKS") == "0"


def test_git_helper_returns_none_on_nonzero_rc(tmp_path):
    assert git_._git(str(tmp_path), "status") is None


def test_list_worktrees_finds_all_three(repo_with_worktrees):
    main, wts = repo_with_worktrees
    rows = git_.list_worktrees(str(main))
    paths = {os.path.realpath(r["worktree"]) for r in rows}
    assert os.path.realpath(str(main)) in paths
    for wt in wts:
        assert os.path.realpath(str(wt)) in paths
    by_path = {os.path.realpath(r["worktree"]): r for r in rows}
    assert by_path[os.path.realpath(str(wts[0]))]["branch"] == "wt-a"


def test_prunable_worktree_is_flagged_with_a_reason_string(repo_with_prunable_worktree):
    main, gone = repo_with_prunable_worktree
    rows = git_.list_worktrees(str(main))
    row = [r for r in rows if os.path.realpath(r["worktree"]) == os.path.realpath(str(gone))]
    assert row, "a deleted worktree still appears in porcelain"
    # `prunable` carries a REASON STRING, not a bare flag
    assert isinstance(row[0]["prunable"], str) and row[0]["prunable"]


def test_detached_worktree_has_no_branch(repo_with_detached_worktree):
    main, det = repo_with_detached_worktree
    rows = git_.list_worktrees(str(main))
    row = [r for r in rows
           if os.path.realpath(r["worktree"]) == os.path.realpath(str(det))][0]
    assert row["detached"] is True and row["branch"] is None


def test_default_branch_prefers_the_remote_over_a_local_ref(repo_local_master_remote_trunk):
    """The measured defect: local-first silently resolves to `master`."""
    assert git_.default_branch(str(repo_local_master_remote_trunk)) == "trunk"


def test_default_branch_falls_back_to_a_local_ref_with_no_remote(repo_with_worktrees):
    main, _ = repo_with_worktrees
    assert git_.default_branch(str(main)) == "trunk"


def test_default_branch_never_returns_the_literal_HEAD(repo_with_worktrees):
    """merge-base HEAD HEAD makes every changed-set empty and the board reports
    'no collisions' while completely blind."""
    main, _ = repo_with_worktrees
    assert git_.default_branch(str(main)) != "HEAD"


def test_config_branch_is_ignored_when_the_ref_does_not_exist(repo_with_worktrees):
    """Without the precheck, for-each-ref exits 128 with ZERO rows and the board
    goes totally blank."""
    main, _ = repo_with_worktrees
    assert git_.default_branch(str(main), cfg_branch="no-such-branch") == "trunk"


def test_ahead_behind_orientation(repo_with_ahead_behind):
    """for-each-ref %(ahead-behind:X) is 'ahead behind'; rev-list --left-right
    --count is 'behind ahead'. Pin the orientation in ONE helper."""
    main = repo_with_ahead_behind
    rows = git_.branch_rows(str(main), "trunk")
    assert rows["feat"]["ahead"] == 2
    assert rows["feat"]["behind"] == 5


def test_branch_rows_maps_branch_to_worktree_path(repo_with_worktrees):
    main, wts = repo_with_worktrees
    rows = git_.branch_rows(str(main), "trunk")
    assert os.path.realpath(rows["wt-a"]["worktree"]) == os.path.realpath(str(wts[0]))


def test_status_v2_reports_dirty_paths(repo_with_worktrees):
    main, wts = repo_with_worktrees
    (wts[0] / "untracked.txt").write_text("u")
    (wts[0] / "base.txt").write_text("modified")
    st = git_.status_v2(str(wts[0]))
    assert st["branch"] == "wt-a"
    assert "untracked.txt" in st["dirty"], "-uall must include untracked files"
    assert "base.txt" in st["dirty"]


def test_status_v2_on_a_clean_worktree_is_empty(repo_with_worktrees):
    main, wts = repo_with_worktrees
    assert git_.status_v2(str(wts[1]))["dirty"] == set()


def test_merge_base_is_empty_for_an_orphan_branch(repo_with_orphan_branch):
    main = repo_with_orphan_branch
    git(main, "checkout", "-q", "orphan")
    assert git_.merge_base(str(main), "trunk") is None


def test_changed_files_uses_three_dot_semantics(repo_with_ahead_behind):
    """Two-dot answers 'what differs between base tip and this branch' -- i.e.
    mostly what BASE did -- and built a 1633-file noise wall."""
    main = repo_with_ahead_behind
    git(main, "checkout", "-q", "feat")
    changed = git_.changed_files(str(main), "trunk")
    assert changed == {"feat0.txt", "feat1.txt"}
    assert not any(f.startswith("trunk") for f in changed)
