import os
import subprocess

DEFAULT_CANDIDATES = ("main", "master", "trunk", "develop", "default")

# %(refname) -- the FULL, unambiguous ref -- not %(refname:short). Verified on
# git 2.43.7: with a tag and a branch both named `amb`, %(refname:short)
# returns `heads/amb` (git's shortening falls back to a type-qualified form to
# disambiguate), so a Python-side `rsplit("/refs/heads/")`-style match against
# %(refname:short) output can STILL mismatch. %(refname) has no such ambiguity
# and is exactly what `git worktree list --porcelain`'s own `branch` line
# already gives verbatim (`branch refs/heads/...`), so keying on it lets
# list_worktrees and branch_rows meet on one unambiguous key.
FMT = ("%(refname)%09%(ahead-behind:{base})%09%(committerdate:unix)"
       "%09%(worktreepath)%09%(subject)")

_HEADS_PREFIX = "refs/heads/"


def _short_branch(ref):
    """Display-only shortening: strip the known `refs/heads/` prefix (never
    basename/rsplit -- that is exactly the bug this module had for
    hierarchical names like `feature/auth`). A worktree's `branch` porcelain
    field is always a `refs/heads/...` ref, never a tag, so this is safe."""
    return ref[len(_HEADS_PREFIX):] if ref.startswith(_HEADS_PREFIX) else ref


def _git(cwd, *args, **kw):
    """The ONE git entry point. --no-optional-locks is mandatory on every call.

    `cwd` may be a worktree path recorded by a coding agent -- untrusted,
    prompt-injectable input. Git treats a repository's OWN config as trusted
    code (core.fsmonitor, core.hooksPath, diff.external all name executables
    git will run), so every invocation neutralises the config keys that turn
    a read into code execution. Measured: `-c core.fsmonitor=false` stops a
    planted payload from running; the same command without it executes the
    payload. `diff.external=` matters once `changed_files` (M2) runs `git
    diff` inside caller-supplied worktrees.
    """
    timeout = kw.pop("timeout", 30)
    env = dict(os.environ, GIT_OPTIONAL_LOCKS="0", GIT_TERMINAL_PROMPT="0")
    cmd = ["git", "--no-optional-locks",
           "-c", "core.fsmonitor=false",
           "-c", "core.hooksPath=/dev/null",
           "-c", "diff.external=",
           "-C", cwd] + list(args)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True,
                              timeout=timeout, env=env)
    except (subprocess.TimeoutExpired, OSError):
        return None
    return proc.stdout if proc.returncode == 0 else None


def list_worktrees(repo):
    """-z avoids C-quoting of unusual paths (git >= 2.36). `locked` and
    `prunable` carry a REASON STRING, not a bare flag.

    `branch_ref` is the FULL, unmodified `refs/heads/...` value porcelain
    reports -- the identity to key into `branch_rows` with (see FMT). `branch`
    is a DISPLAY-only short form (prefix-stripped, never basename'd) so a
    hierarchical name like `feature/auth` still reads correctly on a card.
    Measured pre-fix: `branch` was `val.rsplit("/", 1)[-1]`, which collapsed
    `refs/heads/feature/auth` to `auth` -- indistinguishable from a flat `auth`
    branch, and board.py joined on THAT collapsed value.
    """
    out = _git(repo, "worktree", "list", "--porcelain", "-z")
    if out is None:
        out = _git(repo, "worktree", "list", "--porcelain")
        if out is None:
            return []
        tokens = [l for l in out.split("\n")]
    else:
        tokens = out.split("\0")
    rows, cur = [], None
    for tok in tokens:
        if not tok:
            if cur:
                rows.append(cur)
                cur = None
            continue
        key, _, val = tok.partition(" ")
        if key == "worktree":
            if cur:
                rows.append(cur)
            cur = {"worktree": val, "HEAD": None, "branch": None,
                   "branch_ref": None, "detached": False, "bare": False,
                   "locked": None, "prunable": None}
        elif cur is None:
            continue
        elif key == "HEAD":
            cur["HEAD"] = val
        elif key == "branch":
            cur["branch_ref"] = val or None
            cur["branch"] = _short_branch(val) if val else None
        elif key == "detached":
            cur["detached"] = True
        elif key == "bare":
            cur["bare"] = True
        elif key in ("locked", "prunable"):
            cur[key] = val or key
    if cur:
        rows.append(cur)
    return rows


def ref_exists(repo, ref):
    if not ref or ref == "HEAD":
        return False
    for full in ("refs/heads/%s" % ref, "refs/remotes/%s" % ref, ref):
        if _git(repo, "rev-parse", "--verify", "--quiet", full) is not None:
            return True
    return False


def default_branch(repo, cfg_branch=None, remote="origin"):
    """Probe REMOTE refs before local. Never return the literal 'HEAD'.

    `cfg_branch` is a DELIBERATE override and is honoured first, even when it
    names a local ref that differs from the remote default. That is what
    configuration means -- the same principle as an explicitly parked thread
    beating derived PR state. The remote-before-local rule governs
    AUTO-DETECTION, not explicit user intent.

    The cost is real and accepted: a stale `project.default_branch` silently
    poisons every ahead/behind number and every merge-base. `abd doctor` (M3)
    warns when the configured branch differs from the resolved remote default.
    """
    if cfg_branch and ref_exists(repo, cfg_branch):
        return cfg_branch
    out = _git(repo, "symbolic-ref", "--quiet", "refs/remotes/%s/HEAD" % remote)
    if out:
        # SAME BUG CLASS as list_worktrees had: rsplit("/", 1)[-1] takes the
        # last PATH COMPONENT, not the part after the known prefix. Measured:
        # a remote HEAD at refs/remotes/origin/release/2.0 rsplit-collapsed to
        # "2.0" instead of "release/2.0". Strip the literal prefix instead.
        ref = out.strip()
        prefix = "refs/remotes/%s/" % remote
        name = ref[len(prefix):] if ref.startswith(prefix) else ref.rsplit("/", 1)[-1]
        if name and name != "HEAD":
            return name
    for cand in DEFAULT_CANDIDATES:                       # REMOTE FIRST
        if _git(repo, "rev-parse", "--verify", "--quiet",
                "refs/remotes/%s/%s" % (remote, cand)) is not None:
            return cand
    init_default = _git(repo, "config", "--get", "init.defaultBranch")
    if init_default:
        name = init_default.strip()
        if name and ref_exists(repo, name):
            return name
    for cand in DEFAULT_CANDIDATES:
        if _git(repo, "rev-parse", "--verify", "--quiet",
                "refs/heads/%s" % cand) is not None:
            return cand
    head = _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    if head:
        name = head.strip()
        if name and name != "HEAD":
            return name
    return None


def branch_rows(repo, base):
    """All branches in ONE process. A bad base ref makes for-each-ref exit 128
    with ZERO rows, so the ref_exists precheck is mandatory."""
    if not base or not ref_exists(repo, base):
        return {}
    out = _git(repo, "for-each-ref", "--format=" + FMT.format(base=base), "refs/heads")
    if out is None:
        return {}
    rows = {}
    for line in out.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 5:
            parts = parts + [""] * (5 - len(parts))
        name, ab, cdate, wtpath, subject = parts[:5]
        ahead = behind = None
        bits = (ab or "").split()
        if len(bits) == 2:
            try:
                ahead, behind = int(bits[0]), int(bits[1])   # ahead FIRST
            except ValueError:
                ahead = behind = None
        try:
            committed_at = int(cdate)
        except ValueError:
            committed_at = None
        rows[name] = {"ahead": ahead, "behind": behind,
                      "committed_at": committed_at,
                      "worktree": wtpath or None, "subject": subject}
    return rows


# Number of SPACE-SEPARATED header fields before the path in each porcelain-v2
# entry type. Under -z the path is last and UNQUOTED, so it may contain spaces:
# `split(" ")[-1]` returns only the last WORD. Measured: a repo with
# "my file.txt" and "deep dir/two words.py" produced
# {'file.txt','words.py','plain.txt'} -- two real paths missing and two
# FABRICATED ones present.
_V2_FIELDS = {"1": 8, "2": 9, "u": 10, "?": 1, "!": 1}


def _v2_path(tok):
    """Return the path from a porcelain-v2 -z entry, spaces intact."""
    nfields = _V2_FIELDS.get(tok[:1])
    if nfields is None:
        return None
    parts = tok.split(" ", nfields)
    return parts[nfields] if len(parts) > nfields else None


def status_v2(wt):
    """--porcelain=v2 -z -b -uall. -uall costs only 1.7% over normal and gives
    complete dirty sets; -uno is 3.5x faster but destroys the headline feature."""
    empty = {"branch": None, "detached": False, "dirty": set(),
             "ahead": None, "behind": None}
    if not os.path.isdir(wt):
        return empty
    out = _git(wt, "status", "--porcelain=v2", "-z", "-b", "-uall")
    if out is None:
        return empty
    res = {"branch": None, "detached": False, "dirty": set(),
           "ahead": None, "behind": None}
    tokens = out.split("\0")
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        i += 1
        if not tok:
            continue
        if tok.startswith("# branch.head "):
            name = tok[len("# branch.head "):].strip()
            if name == "(detached)":
                res["detached"] = True
            else:
                res["branch"] = name
        elif tok.startswith("# branch.ab "):
            bits = tok[len("# branch.ab "):].split()
            try:
                res["ahead"] = int(bits[0].lstrip("+"))
                res["behind"] = int(bits[1].lstrip("-"))
            except (IndexError, ValueError):
                pass
        elif tok.startswith("#"):
            continue
        elif tok[:1] in ("1", "?", "u"):
            path = _v2_path(tok)
            if path:
                res["dirty"].add(path)
        elif tok[:1] == "2":
            # a rename: the ORIGIN path is the NEXT NUL token. Consume it, add both.
            path = _v2_path(tok)
            if path:
                res["dirty"].add(path)
            if i < len(tokens):
                if tokens[i]:
                    res["dirty"].add(tokens[i])
                i += 1
    return res


def merge_base(wt, base):
    if not base:
        return None
    out = _git(wt, "merge-base", base, "HEAD")
    return (out or "").strip() or None


def changed_files(wt, base):
    """Three-dot semantics, computed explicitly so the merge-base can be cached
    and its empty case detected. --no-renames is mandatory: it is 9.5x faster
    AND a strict superset (194 paths were lost by -M, 0 gained)."""
    mb = merge_base(wt, base)
    if not mb:
        return set()
    out = _git(wt, "diff", "--name-only", "--no-renames", "-z", mb, "HEAD")
    if out is None:
        return set()
    return {p for p in out.split("\0") if p}
