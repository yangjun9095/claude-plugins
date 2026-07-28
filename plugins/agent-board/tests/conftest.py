import subprocess

import pytest


def git(cwd, *args):
    return subprocess.run(
        ["git", "--no-optional-locks", "-C", str(cwd), *args],
        capture_output=True, text=True, check=True,
        env={"GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0",
             "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null",
             "HOME": str(cwd), "PATH": "/usr/bin:/bin"},
    ).stdout


def _init(path, branch="trunk"):
    path.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init", "-q", "-b", branch, str(path)], check=True,
                   capture_output=True)
    git(path, "config", "user.email", "t@t.invalid")
    git(path, "config", "user.name", "t")
    return path


def commit(path, name, text="x"):
    (path / name).write_text(text)
    git(path, "add", "-A")
    git(path, "commit", "-qm", "add %s" % name)


@pytest.fixture
def repo_with_worktrees(tmp_path):
    """Fixture 1: main worktree + 2 linked worktrees, default branch `trunk`,
    no remote. Returns (main_path, [wt_a, wt_b])."""
    main = _init(tmp_path / "main", branch="trunk")
    commit(main, "base.txt")
    wts = []
    for name in ("wt-a", "wt-b"):
        p = tmp_path / name
        git(main, "worktree", "add", "-q", "-b", name, str(p))
        wts.append(p)
    return main, wts


@pytest.fixture
def bare_repo_with_worktree(tmp_path):
    """Fixture 2: bare repo + 1 linked worktree. Kills `dirname(common)`."""
    seed = _init(tmp_path / "seed", branch="trunk")
    commit(seed, "base.txt")
    bare = tmp_path / "proj.git"
    subprocess.run(["git", "clone", "-q", "--bare", str(seed), str(bare)],
                   check=True, capture_output=True)
    wt = tmp_path / "wt-feat"
    git(bare, "worktree", "add", "-q", "-b", "feat", str(wt))
    return bare, wt


@pytest.fixture
def repo_with_submodule(tmp_path):
    """A superproject with a submodule. Returns (outer, sub_path).

    A real submodule's `.git` file holds a RELATIVE `gitdir:` pointing into
    `<outer>/.git/modules/<name>` -- exactly the path shape _demodulize must
    truncate back to the superproject.
    """
    inner = _init(tmp_path / "inner", branch="trunk")
    commit(inner, "inner.txt")
    outer = _init(tmp_path / "outer", branch="trunk")
    commit(outer, "outer.txt")
    subprocess.run(["git", "-C", str(outer), "-c", "protocol.file.allow=always",
                    "submodule", "add", "-q", str(inner), "sub"],
                   check=True, capture_output=True)
    git(outer, "commit", "-qm", "add submodule")
    return outer, outer / "sub"


@pytest.fixture
def repo_local_master_remote_trunk(tmp_path):
    """Fixture 3: local branch `master`, remote default `trunk`. With a naive
    'local refs first' order this silently resolves to master, poisoning every
    ahead/behind number and every collision merge-base."""
    upstream = _init(tmp_path / "up", branch="trunk")
    commit(upstream, "base.txt")
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(upstream), str(clone)],
                   check=True, capture_output=True)
    git(clone, "config", "user.email", "t@t.invalid")
    git(clone, "config", "user.name", "t")
    git(clone, "checkout", "-q", "-b", "master")
    return clone


@pytest.fixture
def repo_with_prunable_worktree(tmp_path):
    """Fixture 4: a worktree whose directory was deleted. It still appears in
    porcelain with `prunable`, and `git -C <path> status` fatals rc 128."""
    import shutil
    main = _init(tmp_path / "main", branch="trunk")
    commit(main, "base.txt")
    gone = tmp_path / "gone"
    git(main, "worktree", "add", "-q", "-b", "gone", str(gone))
    shutil.rmtree(str(gone))
    return main, gone


@pytest.fixture
def repo_with_detached_worktree(tmp_path):
    """Fixture 5: a detached-HEAD worktree."""
    main = _init(tmp_path / "main", branch="trunk")
    commit(main, "base.txt")
    sha = git(main, "rev-parse", "HEAD").strip()
    det = tmp_path / "det"
    git(main, "worktree", "add", "-q", "--detach", str(det), sha)
    return main, det


@pytest.fixture
def repo_with_orphan_branch(tmp_path):
    """Fixture 6: an orphan branch -- merge-base is empty."""
    main = _init(tmp_path / "main", branch="trunk")
    commit(main, "base.txt")
    git(main, "checkout", "-q", "--orphan", "orphan")
    (main / "only.txt").write_text("x")
    git(main, "add", "-A")
    git(main, "commit", "-qm", "orphan root")
    git(main, "checkout", "-q", "trunk")
    return main


@pytest.fixture
def repo_with_ahead_behind(tmp_path):
    """A branch that is asymmetric, to pin the reversed-API footgun."""
    main = _init(tmp_path / "main", branch="trunk")
    commit(main, "base.txt")
    git(main, "checkout", "-q", "-b", "feat")
    for i in range(2):
        commit(main, "feat%d.txt" % i)
    git(main, "checkout", "-q", "trunk")
    for i in range(5):
        commit(main, "trunk%d.txt" % i)
    return main
