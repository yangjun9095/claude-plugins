import io
import os
import subprocess

from agent_board.config import load_config


def _read_first_line(path):
    try:
        with io.open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.readline().strip()
    except (IOError, OSError):
        return None


def git_common_dir_pure(start=None):
    """Resolve the git common dir WITHOUT spawning git. Used by the SessionStart
    hook, whose budget forbids a subprocess. Must agree with git_common_dir()."""
    # realpath, NOT abspath: `git rev-parse` resolves symlinks, so an abspath
    # here makes the two resolvers disagree for a symlinked repo path -- and
    # since the hook uses the pure resolver while the CLI uses the subprocess
    # one, that means TWO DIFFERENT BOARDS for one repo.
    cur = os.path.realpath(start or os.getcwd())
    # The isdir guard is required for parity, not defensiveness: git_common_dir()
    # returns None for a non-directory, and without this the pure resolver would
    # happily walk up from a FILE's parent and return a real .git.
    if not os.path.isdir(cur):
        return None
    while True:
        dot = os.path.join(cur, ".git")
        if os.path.isdir(dot):
            return _demodulize(dot)
        if os.path.isfile(dot):
            line = _read_first_line(dot) or ""
            if line.startswith("gitdir:"):
                gitdir = line[len("gitdir:"):].strip()
                if not os.path.isabs(gitdir):
                    gitdir = os.path.join(cur, gitdir)
                gitdir = os.path.abspath(gitdir)
                commondir = _read_first_line(os.path.join(gitdir, "commondir"))
                if commondir:
                    if not os.path.isabs(commondir):
                        commondir = os.path.join(gitdir, commondir)
                    return _demodulize(os.path.abspath(commondir))
                return _demodulize(gitdir)
            return None
        # a bare repo: HEAD + objects + refs directly in this dir
        if all(os.path.exists(os.path.join(cur, n)) for n in ("HEAD", "objects", "refs")):
            return cur
        parent = os.path.dirname(cur)
        if parent == cur:
            return None
        cur = parent


def _demodulize(path):
    """A session inside a submodule must land on the SUPERPROJECT board, not a
    separate empty one. Truncate at the /.git/modules/ boundary."""
    marker = os.sep + ".git" + os.sep + "modules" + os.sep
    idx = path.find(marker)
    if idx != -1:
        return path[:idx + len(os.sep + ".git")]
    return path


def git_common_dir(start=None):
    """Subprocess resolution. --path-format=absolute is mandatory: the plain form
    returns a relative `.git` from the main worktree and absolute from linked ones."""
    cwd = os.path.abspath(start or os.getcwd())
    if not os.path.isdir(cwd):
        return None
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0")
    try:
        proc = subprocess.run(
            ["git", "--no-optional-locks", "-C", cwd, "rev-parse",
             "--path-format=absolute", "--git-common-dir"],
            capture_output=True, text=True, timeout=30, env=env)
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        return None
    out = proc.stdout.strip()
    return _demodulize(os.path.realpath(out)) if out else None


def project_name(common):
    """Display name. basename(common)=='.git' -> the parent dir's name;
    otherwise strip a trailing '.git' so /srv/x/proj.git is 'proj', not 'x'."""
    common = os.path.abspath(common).rstrip(os.sep)
    base = os.path.basename(common)
    if base == ".git":
        return os.path.basename(os.path.dirname(common))
    if base.endswith(".git"):
        return base[:-len(".git")]
    return base


def resolve_threads_dir(start=None):
    start = start or os.getcwd()
    env = os.environ.get("ABD_THREADS_DIR")
    if env:
        return os.path.abspath(os.path.expanduser(os.path.expandvars(env)))
    cfg = load_config(start)
    storage = cfg.get("storage") or {}
    if storage.get("mode") == "explicit" and storage.get("threads_dir"):
        return os.path.abspath(os.path.expanduser(
            os.path.expandvars(storage["threads_dir"])))
    common = git_common_dir(start)
    if not common:
        return None
    return os.path.join(common, "agent-board")
