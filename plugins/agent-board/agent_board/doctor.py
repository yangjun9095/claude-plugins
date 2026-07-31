"""`abd doctor` -- report what is actually configured, detected and installed.

Doctor's whole value is telling the truth about a machine, so it does two things
no other verb does. It reports **derived** state (which is why no `*.enabled` key
exists in the config schema -- enablement is proven, never declared), and it names
the failure modes that are otherwise silent: an org-set `disableAllHooks` that
only managed settings can undo, a threads_dir that lands inside the working tree,
two resolvers disagreeing about which repo you are in.

Every check is independent and its own exception becomes a `fail` row. A doctor
that dies on its fifth check tells you less than one that reports the fifth as
broken -- the opposite of the hook path, where silence is the correct failure.
"""
import io
import json
import os
import subprocess
import sys

OK, WARN, FAIL, PENDING = "ok", "warn", "fail", "pending"

SHARD_WARN_BYTES = 50 * 1024 * 1024
MANAGED_SETTINGS = ("/etc/claude-code/managed-settings.json",)
MANAGED_SETTINGS_DIR = "/etc/claude-code/managed-settings.d"
SDK_TOKENS = ("claude_agent_sdk", "ClaudeAgentOptions")
SDK_SCAN_MAX_FILES = 4000
PY_CANDIDATES = ("python3.14", "python3.13", "python3.12", "python3.11",
                 "python3.10", "python3.9", "python3.8", "python3")


def _row(name, status, detail, remedy=None):
    return {"name": name, "status": status, "detail": detail, "remedy": remedy}


def _read_json_file(path):
    """(obj, error). Never raises."""
    try:
        with io.open(path, "r", encoding="utf-8", errors="replace") as fh:
            return json.load(fh), None
    except (IOError, OSError) as exc:
        return None, str(exc)
    except ValueError as exc:
        return None, "invalid JSON: %s" % exc


# --- interpreter -------------------------------------------------------------

def _probe(path):
    """(has_rich, has_pip) for one interpreter, in ONE spawn.

    -I for the same reason the launcher uses it: without it the caller's cwd is
    on sys.path and a stray ./rich.py would be executed by this very probe.
    """
    code = ("import importlib.util as u\n"
            "print(int(u.find_spec('rich') is not None),"
            " int(u.find_spec('pip') is not None))\n")
    try:
        proc = subprocess.run([path, "-I", "-c", code], capture_output=True,
                              text=True, timeout=10)
    except (subprocess.SubprocessError, OSError):
        return None
    if proc.returncode != 0:
        return None
    parts = (proc.stdout or "").split()
    if len(parts) != 2:
        return None
    return parts[0] == "1", parts[1] == "1"


def check_interpreter():
    """rich is an opportunistic upgrade, never a requirement -- the plain ANSI
    renderer is the guaranteed one. The remediation has to be interpreter-aware:
    naming an interpreter whose pip is absent or too old is advice that fails."""
    rows = [_row("interpreter", OK, "%s (%d.%d.%d)" % (
        sys.executable, sys.version_info[0], sys.version_info[1],
        sys.version_info[2]))]

    import shutil
    found = []
    for name in PY_CANDIDATES:
        path = shutil.which(name)
        if not path or path in [f[0] for f in found]:
            continue
        probed = _probe(path)
        if probed is not None:
            found.append((path, probed[0], probed[1]))

    with_rich = [p for p, rich, _pip in found if rich]
    if with_rich:
        rows.append(_row("render.rich", OK,
                         "rich importable from %s" % ", ".join(with_rich[:3])))
        return rows

    with_pip = [p for p, _rich, pip in found if pip]
    if with_pip:
        remedy = "%s -m pip install --user rich" % with_pip[0]
    else:
        remedy = ("no interpreter on PATH has pip; try "
                  "`python3.12 -m ensurepip --user && python3.12 -m pip "
                  "install --user rich`, or point at an env that has it: "
                  "`ABD_PYTHON=/path/to/python abd board`")
    rows.append(_row("render.rich", OK,
                     "not importable from any of %d interpreters; using the "
                     "plain renderer (guaranteed, not a degradation)" % len(found),
                     remedy))
    return rows


# --- anchor and storage ------------------------------------------------------

def check_anchor(start):
    from agent_board import anchor

    subproc = anchor.git_common_dir(start)
    pure = anchor.git_common_dir_pure(start)
    if not subproc and not pure:
        return [_row("git anchor", WARN, "%s is not inside a git repository" % start,
                     "run abd from a repo, or set ABD_THREADS_DIR")]
    if subproc != pure:
        # The hook uses the pure resolver and the CLI uses the subprocess one, so
        # a disagreement is not cosmetic: it is two different boards for one repo,
        # with cards written to one and read from the other.
        return [_row("git anchor", FAIL,
                     "resolvers DISAGREE: cli=%s hook=%s" % (subproc, pure),
                     "report this -- the hook and the CLI would use different stores")]
    return [_row("git anchor", OK, subproc)]


def _worktree_roots(repo):
    # The porcelain key is "worktree", NOT "path" -- reading "path" here returned
    # [] for every repo, which silently disabled the storage.location check below
    # rather than failing it.
    from agent_board.derive import git_
    try:
        return [w.get("worktree") for w in git_.list_worktrees(repo) or []
                if isinstance(w, dict) and w.get("worktree")]
    except BaseException:
        return []


def check_storage(start):
    from agent_board import anchor
    from agent_board.config import load_config

    rows = []
    cfg = load_config(start)
    mode = ((cfg.get("storage") or {}).get("mode")) or "git-common-dir"
    threads_dir = anchor.resolve_threads_dir(start)
    if not threads_dir:
        return [_row("storage", WARN, "no threads dir could be resolved")]

    env_override = bool(os.environ.get("ABD_THREADS_DIR"))
    rows.append(_row("storage", OK, "%s (mode=%s%s)"
                     % (threads_dir, mode,
                        ", ABD_THREADS_DIR override" if env_override else "")))

    # Review finding: a non-default threads_dir voids the portability guarantee.
    # A relative path resolves against cwd and lands in the working tree, where
    # `git status` shows it and `git clean -xdn` offers to delete the board.
    if mode != "git-common-dir" or env_override:
        common = anchor.git_common_dir(start)
        inside = None
        for root in _worktree_roots(start) or ([os.path.dirname(common)] if common else []):
            real_root = os.path.realpath(root)
            real_dir = os.path.realpath(threads_dir)
            if real_dir == real_root or real_dir.startswith(real_root + os.sep):
                if common and real_dir.startswith(os.path.realpath(common) + os.sep):
                    continue            # inside .git/ is the intended location
                inside = real_root
                break
        if inside:
            rows.append(_row(
                "storage.location", FAIL,
                "%s is INSIDE the working tree %s -- git will show it as "
                "untracked and `git clean -xdn` will offer to delete the board"
                % (threads_dir, inside),
                "point storage.threads_dir outside the working tree, or drop the "
                "setting to use the default <git-common-dir>/agent-board"))

    if os.path.isdir(threads_dir):
        try:
            mode_bits = os.stat(threads_dir).st_mode & 0o777
        except OSError:
            mode_bits = None
        if mode_bits is not None and mode_bits & 0o077:
            rows.append(_row("storage.permissions", WARN,
                             "%s is mode %o (group/other readable)" % (threads_dir,
                                                                       mode_bits),
                             "left as-is deliberately: chmod 0700 would also clear "
                             "an inherited setgid bit; tighten it yourself if the "
                             "wider mode was not intentional"))
    return rows


def check_config(start):
    from agent_board.config import CONFIG_NAME, load_config

    cfg = load_config(start)
    path = os.environ.get("ABD_CONFIG") or os.path.join(start, CONFIG_NAME)
    problems = cfg.get("_problems") or []
    if problems:
        return [_row("config", WARN, "%s: %s" % (path, "; ".join(problems)),
                     "fix the file, or delete it -- every key is optional")]
    exists = os.path.exists(path)
    return [_row("config", OK, "%s%s" % (path, "" if exists else " (absent; all defaults)"))]


def check_default_branch(start):
    """Two silent poisoners, both worth a line.

    A configured branch that no longer matches the remote default poisons every
    ahead/behind number and every merge-base; and a base guessed from a LOCAL ref
    when a remote exists is the reproduced `master`-vs-`trunk` case.
    """
    from agent_board.config import load_config
    from agent_board.derive import git_

    cfg = load_config(start)
    remote = (cfg.get("forge") or {}).get("remote") or "origin"
    configured = (cfg.get("project") or {}).get("default_branch")
    resolved = git_.default_branch(start, configured, remote)
    if not resolved:
        return [_row("default branch", WARN, "could not be determined",
                     "set project.default_branch; until then the board degrades "
                     "to dirty-only")]

    has_remote = git_.remote_url(start, remote) is not None
    remote_side = None
    if has_remote:
        for cand in git_.DEFAULT_CANDIDATES:
            # ref_exists tries refs/remotes/<ref> for a "<remote>/<name>" form
            if git_.ref_exists(start, "%s/%s" % (remote, cand)):
                remote_side = cand
                break

    if configured and remote_side and configured != remote_side:
        return [_row("default branch", WARN,
                     "configured %r but %s's default looks like %r"
                     % (configured, remote, remote_side),
                     "a stale project.default_branch poisons every ahead/behind "
                     "number and merge-base")]
    if has_remote and not remote_side:
        return [_row("default branch", WARN,
                     "%r guessed from a local ref while remote %r exists"
                     % (resolved, remote),
                     "set project.default_branch, or fetch the remote so its refs "
                     "can be probed")]
    return [_row("default branch", OK, resolved)]


# --- hooks -------------------------------------------------------------------

def _settings_candidates(repo):
    home = os.path.expanduser("~")
    return [("user", os.path.join(home, ".claude", "settings.json")),
            ("project", os.path.join(repo, ".claude", "settings.json")),
            ("local", os.path.join(repo, ".claude", "settings.local.json"))]


def _managed_files():
    out = [p for p in MANAGED_SETTINGS if os.path.exists(p)]
    try:
        for name in sorted(os.listdir(MANAGED_SETTINGS_DIR)):
            if name.endswith(".json"):
                out.append(os.path.join(MANAGED_SETTINGS_DIR, name))
    except OSError:
        pass
    return out


def check_hooks(start, repo):
    from agent_board.install import _is_ours

    rows = []
    root = os.environ.get("ABD_ROOT") or os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))
    manifest = os.path.join(root, "hooks", "hooks.json")
    if os.path.exists(manifest):
        obj, err = _read_json_file(manifest)
        if err:
            rows.append(_row("hooks.manifest", FAIL, "%s: %s" % (manifest, err)))
        else:
            events = sorted((obj or {}).get("hooks") or {})
            rows.append(_row("hooks.manifest", OK,
                             "%s registers %s" % (manifest, ", ".join(events))))
    else:
        rows.append(_row("hooks.manifest", WARN,
                         "no hooks/hooks.json under %s" % root,
                         "a plugin install registers hooks from this file"))

    registered = []
    for scope, path in _settings_candidates(repo):
        if not os.path.exists(path):
            continue
        obj, err = _read_json_file(path)
        if err or not isinstance(obj, dict):
            rows.append(_row("hooks.%s" % scope, WARN, "%s: %s"
                             % (path, err or "not a JSON object")))
            continue
        hooks = obj.get("hooks") if isinstance(obj.get("hooks"), dict) else {}
        if any(_is_ours(e) for arr in hooks.values()
               if isinstance(arr, list) for e in arr):
            registered.append(scope)
    rows.append(_row("hooks.settings", OK,
                     "agent-board entries in: %s" % ", ".join(registered)
                     if registered else
                     "no settings-file entries (the plugin manifest covers a "
                     "marketplace install; `abd install-hooks` is for skills-dir "
                     "or bare-checkout installs)"))

    # An org-set disableAllHooks is the inverse risk: it kills the tool silently
    # and NOTHING but managed settings can re-enable it, so it must be named.
    for path in _managed_files():
        obj, err = _read_json_file(path)
        if err or not isinstance(obj, dict):
            continue
        if obj.get("disableAllHooks"):
            rows.append(_row("hooks.disabled", FAIL,
                             "disableAllHooks is set in MANAGED settings (%s)" % path,
                             "only managed settings can undo this -- ask whoever "
                             "administers this machine; the CLI still works"))
    for scope, path in _settings_candidates(repo):
        obj, _err = _read_json_file(path)
        if isinstance(obj, dict) and obj.get("disableAllHooks"):
            rows.append(_row("hooks.disabled", WARN,
                             "disableAllHooks is set in %s settings (%s)"
                             % (scope, path),
                             "remove that key to let the hooks run"))

    from agent_board import hookimpl
    if hookimpl._disabled():
        rows.append(_row("hooks.killswitch", WARN,
                         "a kill switch is active (ABD_DISABLE or "
                         "~/.agent-board-DISABLED)",
                         "unset ABD_DISABLE / remove the file to re-enable"))
    return rows


def check_sdk_launchers(repo):
    """SDK sessions do not get filesystem hooks -- only plugins passed via
    options.plugins survive `--setting-sources ""`. If this repo launches the SDK
    itself, the fix is one line, so print it with the path already resolved."""
    root = os.environ.get("ABD_ROOT") or os.path.dirname(
        os.path.dirname(os.path.abspath(__file__)))
    hits, scanned, capped = [], 0, False
    for dirpath, dirnames, filenames in os.walk(repo):
        dirnames[:] = [d for d in dirnames
                       if d not in (".git", "node_modules", "__pycache__", ".venv")]
        for name in filenames:
            if not name.endswith(".py"):
                continue
            scanned += 1
            if scanned > SDK_SCAN_MAX_FILES:
                capped = True
                break
            path = os.path.join(dirpath, name)
            try:
                with io.open(path, "r", encoding="utf-8", errors="replace") as fh:
                    text = fh.read()
            except (IOError, OSError):
                continue
            if any(tok in text for tok in SDK_TOKENS) and "plugins=" not in text:
                hits.append(os.path.relpath(path, repo))
        if capped:
            break

    detail_suffix = (" (scan capped at %d .py files)" % SDK_SCAN_MAX_FILES
                     if capped else "")
    if not hits:
        return [_row("sdk launchers", OK,
                     "no SDK launcher missing plugins=%s" % detail_suffix)]
    # Shallowest first, NOT alphabetical. Plain sorting put five _archive/ paths
    # at the front on this repo and hid src/agenticcre/agent.py -- the live
    # launcher and the only one worth editing.
    sample = sorted(hits, key=lambda p: (p.count(os.sep), p))[:5]
    return [_row("sdk launchers", WARN,
                 "%d SDK launcher(s) pass neither plugins= nor setting_sources=: "
                 "%s%s" % (len(hits), ", ".join(sample), detail_suffix),
                 'add: plugins=[{"type": "local", "path": "%s"}]' % root)]


def check_shards(start):
    from agent_board import anchor

    threads_dir = anchor.resolve_threads_dir(start)
    if not threads_dir:
        return []
    big = []
    root = os.path.join(threads_dir, "threads")
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if not name.endswith(".jsonl"):
                continue
            path = os.path.join(dirpath, name)
            try:
                size = os.stat(path).st_size
            except OSError:
                continue
            if size > SHARD_WARN_BYTES:
                big.append((os.path.relpath(path, threads_dir), size))
    if not big:
        return [_row("event shards", OK, "none over %d MB"
                     % (SHARD_WARN_BYTES // (1024 * 1024)))]
    return [_row("event shards", WARN,
                 "; ".join("%s is %.0f MB" % (p, s / 1024.0 / 1024.0)
                           for p, s in sorted(big, key=lambda x: -x[1])[:5]),
                 "reading them is still cheap -- this is a memory bound, not a "
                 "latency one -- but archive the thread if it is finished")]


def check_tools():
    """Presence only. Enablement is PROVEN by running the real command, which
    lands with the forge and jobs layers -- reporting a tool as enabled here
    because the binary exists is exactly the detection bug the schema removed."""
    import shutil
    rows = []
    forge = next((n for n in ("gh", "glab") if shutil.which(n)), None)
    sched = next((n for n in ("squeue", "qstat", "bjobs") if shutil.which(n)), None)
    rows.append(_row("forge cli", OK if forge else PENDING,
                     "%s at %s" % (forge, shutil.which(forge)) if forge
                     else "none found (gh, glab); PR state stays empty"))
    rows.append(_row("scheduler", OK if sched else PENDING,
                     "%s at %s" % (sched, shutil.which(sched)) if sched
                     else "none found (squeue, qstat, bjobs); job state stays empty"))
    rows.append(_row("forge/jobs probe", PENDING,
                     "enablement is proven by running the real command; that "
                     "probe ships with the forge and jobs layers"))
    return rows


CHECKS = (
    ("interpreter", lambda start, repo: check_interpreter()),
    ("anchor", lambda start, repo: check_anchor(start)),
    ("config", lambda start, repo: check_config(start)),
    ("storage", lambda start, repo: check_storage(start)),
    ("default_branch", lambda start, repo: check_default_branch(start)),
    ("hooks", lambda start, repo: check_hooks(start, repo)),
    ("sdk", lambda start, repo: check_sdk_launchers(repo)),
    ("shards", lambda start, repo: check_shards(start)),
    ("tools", lambda start, repo: check_tools()),
)


def run_checks(start, repo):
    rows = []
    for name, fn in CHECKS:
        try:
            rows.extend(fn(start, repo) or [])
        except BaseException as exc:
            # Doctor reports rather than fails open: a check that died is itself
            # a finding, and swallowing it would leave a silent gap in a report
            # whose entire purpose is completeness.
            rows.append(_row(name, FAIL, "check raised %r" % (exc,)))
    return rows


_MARK = {OK: "ok  ", WARN: "WARN", FAIL: "FAIL", PENDING: "--  "}


def format_text(rows):
    out = []
    for row in rows:
        out.append("%s %-18s %s" % (_MARK.get(row["status"], "?   "),
                                    row["name"], row["detail"]))
        if row.get("remedy"):
            out.append("%s %-18s -> %s" % ("    ", "", row["remedy"]))
    counts = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    out.append("")
    out.append("%d ok, %d warn, %d fail, %d pending"
               % (counts.get(OK, 0), counts.get(WARN, 0),
                  counts.get(FAIL, 0), counts.get(PENDING, 0)))
    return out


def exit_code(rows):
    """0 unless something is actually broken. A warn is information, not a
    failure -- making warns non-zero would train people to ignore the code."""
    return 1 if any(r["status"] == FAIL for r in rows) else 0
