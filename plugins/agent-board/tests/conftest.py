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
