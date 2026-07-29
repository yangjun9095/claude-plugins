import os
import subprocess

from agent_board.derive import git_
from tests.conftest import _init, commit, git


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
    --count is 'behind ahead'. Pin the orientation in ONE helper.

    Keyed on the FULL ref (refs/heads/feat), not the short name -- see F5:
    %(refname:short) is ambiguity-dependent (a tag and branch sharing a name
    make it return "heads/<name>"), so branch_rows keys on %(refname) instead
    and callers must match on the full ref too.
    """
    main = repo_with_ahead_behind
    rows = git_.branch_rows(str(main), "trunk")
    assert rows["refs/heads/feat"]["ahead"] == 2
    assert rows["refs/heads/feat"]["behind"] == 5


def test_branch_rows_maps_branch_to_worktree_path(repo_with_worktrees):
    main, wts = repo_with_worktrees
    rows = git_.branch_rows(str(main), "trunk")
    assert os.path.realpath(rows["refs/heads/wt-a"]["worktree"]) == \
        os.path.realpath(str(wts[0]))


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


def test_status_v2_preserves_paths_containing_spaces(repo_with_worktrees):
    main, wts = repo_with_worktrees
    wt = wts[0]
    (wt / "my file.txt").write_text("y")
    (wt / "deep dir").mkdir()
    (wt / "deep dir" / "two words.py").write_text("y")
    (wt / "plain.txt").write_text("y")
    git(wt, "add", "my file.txt")
    dirty = git_.status_v2(str(wt))["dirty"]
    assert "my file.txt" in dirty
    assert "deep dir/two words.py" in dirty
    assert "plain.txt" in dirty
    assert "file.txt" not in dirty, "fabricated path from a truncated split"
    assert "words.py" not in dirty, "fabricated path from a truncated split"


def test_status_v2_records_both_sides_of_a_staged_rename(repo_with_worktrees):
    """A "2 " entry's origin path is the NEXT NUL token; failing to consume it
    desynchronises the whole token stream for that worktree."""
    main, wts = repo_with_worktrees
    wt = wts[1]
    (wt / "old name.txt").write_text("content\n")
    git(wt, "add", "old name.txt")
    git(wt, "commit", "-qm", "add old")
    git(wt, "mv", "old name.txt", "new name.txt")
    (wt / "after.txt").write_text("z")
    dirty = git_.status_v2(str(wt))["dirty"]
    assert "new name.txt" in dirty and "old name.txt" in dirty, dirty
    assert "after.txt" in dirty, "stream desynchronised after the rename entry"


def test_branch_rows_keys_a_hierarchical_name_by_its_full_ref(tmp_path):
    """F5, at the git_ layer directly: %(refname) must be the full ref, so a
    hierarchical branch name is never collapsed to (and confused with) a flat
    basename sibling."""
    main = _init(tmp_path / "main", branch="trunk")
    commit(main, "base.txt")
    git(main, "checkout", "-q", "-b", "feature/auth")
    commit(main, "featurework.txt")
    git(main, "checkout", "-q", "trunk")
    rows = git_.branch_rows(str(main), "trunk")
    assert "refs/heads/feature/auth" in rows, rows
    assert rows["refs/heads/feature/auth"]["ahead"] == 1


def test_default_branch_strips_a_hierarchical_remote_head_by_prefix_not_rsplit(
        tmp_path):
    """F5 audit: default_branch's remote-HEAD parsing had the SAME rsplit
    bug as list_worktrees. Measured pre-fix: a remote HEAD at
    refs/remotes/origin/release/2.0 rsplit-collapsed to '2.0' instead of
    'release/2.0'."""
    upstream = _init(tmp_path / "upstream", branch="release/2.0")
    commit(upstream, "base.txt")
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(upstream), str(clone)],
                   check=True, capture_output=True)
    assert git_.default_branch(str(clone)) == "release/2.0"


def test_config_branch_is_a_deliberate_override_even_over_the_remote_default(
        repo_local_master_remote_trunk):
    """Explicit config wins over auto-detection -- the remote-first rule governs
    detection order, not user intent."""
    repo = str(repo_local_master_remote_trunk)
    assert git_.default_branch(repo) == "trunk"
    assert git_.default_branch(repo, cfg_branch="master") == "master"
