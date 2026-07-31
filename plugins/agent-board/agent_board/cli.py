import os
import sys

from agent_board import __version__


def _hook(argv):
    """Hook entry. Fails open: prints nothing, always returns 0.

    The import is inside the try because an ImportError here -- a half-installed
    package, a syntax error from a bad edit -- must still exit 0 rather than
    print a traceback into the user's session.
    """
    try:
        from agent_board import hookimpl
        return hookimpl.hook_main(argv)
    except BaseException:
        return 0


def _repo_root(start):
    """The worktree root for `start`, falling back to `start` itself.

    dirname('/repo/.git') is the worktree root; a bare repo has no worktree, so
    return the common dir rather than emitting its parent directory.
    """
    from agent_board import anchor
    common = anchor.git_common_dir(start)
    if not common:
        return start, None
    if os.path.basename(common) == ".git":
        return os.path.dirname(common), common
    return common, common


def _cmd_doctor(argv):
    import argparse
    import json as _json

    from agent_board import doctor

    ap = argparse.ArgumentParser(prog="abd doctor")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--root")
    args = ap.parse_args(argv)

    start = args.root or os.getcwd()
    repo, _common = _repo_root(start)
    rows = doctor.run_checks(start, repo)
    if args.json:
        sys.stdout.write(_json.dumps({"checks": rows}, indent=2, sort_keys=True) + "\n")
    else:
        for line in doctor.format_text(rows):
            sys.stdout.write(line + "\n")
    return doctor.exit_code(rows)


def _cmd_install_hooks(argv):
    import argparse

    from agent_board import install

    ap = argparse.ArgumentParser(prog="abd install-hooks")
    ap.add_argument("--scope", choices=list(install.SCOPES), default="local")
    ap.add_argument("--root")
    args = ap.parse_args(argv)

    start = args.root or os.getcwd()
    repo_root, common = _repo_root(start)
    if not common and args.scope != "user":
        sys.stderr.write("abd: not in a git repository; use --scope user\n")
        return 2

    abd_path = os.path.join(os.environ.get("ABD_ROOT")
                            or os.path.dirname(os.path.dirname(
                                os.path.abspath(__file__))), "bin", "abd")
    rc, messages = install.install(args.scope, abd_path, repo_root,
                                   common_dir=common)
    stream = sys.stdout if rc == 0 else sys.stderr
    for line in messages:
        stream.write(line + "\n")
    return rc


def _cmd_thread(argv):
    import argparse

    from agent_board import anchor, model
    from agent_board.timeutil import utcnow_z

    ap = argparse.ArgumentParser(prog="abd thread")
    sub = ap.add_subparsers(dest="verb", required=True)
    p_new = sub.add_parser("new")
    p_new.add_argument("--title", required=True)
    p_new.add_argument("--goal")
    p_new.add_argument("--worktree", action="append", default=[])
    p_new.add_argument("--issue", action="append", type=int, default=[])
    p_new.add_argument("--job-prefix", dest="job_name_prefix")
    p_set = sub.add_parser("set")
    p_set.add_argument("id")
    p_set.add_argument("--title")
    p_set.add_argument("--goal")
    p_set.add_argument("--next-action", dest="next_action")
    p_set.add_argument("--blocked-by", dest="blocked_by", action="append")
    p_set.add_argument("--clear-blocked-by", dest="clear_blocked_by",
                       action="store_true")
    p_set.add_argument("--add-worktree", dest="add_worktree")
    p_set.add_argument("--rm-worktree", dest="rm_worktree")
    p_set.add_argument("--issue", dest="issues", action="append", type=int)
    p_set.add_argument("--job-prefix", dest="job_name_prefix")
    for verb in ("park", "done", "reopen", "use", "archive"):
        pv = sub.add_parser(verb)
        pv.add_argument("id")
        if verb == "park":
            pv.add_argument("--reason")
    args = ap.parse_args(argv)

    threads_dir = anchor.resolve_threads_dir(os.getcwd())
    if not threads_dir:
        sys.stderr.write("abd: not in a git repository; set ABD_THREADS_DIR\n")
        return 2

    try:
        if args.verb == "new":
            wts = [{"path": os.path.abspath(w), "branch": None,
                    "added_at": None} for w in args.worktree]
            t = model.new_thread(threads_dir, args.title, goal=args.goal,
                                 worktrees=wts, issues=args.issue,
                                 job_name_prefix=args.job_name_prefix)
            sys.stdout.write("%s\n" % t["id"])
            return 0
        if args.verb == "set":
            changes = {}
            for field in ("title", "goal", "next_action", "blocked_by",
                          "job_name_prefix"):
                val = getattr(args, field, None)
                if val is not None:
                    changes[field] = val
            if args.clear_blocked_by:
                # Without this there is no way to unblock a thread except editing
                # thread.json by hand, which is exactly what the skill forbids.
                changes["blocked_by"] = []
            appends, removes = {}, {}
            if args.issues:
                appends["issues"] = list(args.issues)
            if args.add_worktree:
                # Pass it as an APPEND so the merge happens inside mutate's lock.
                # Precomputing `cur + [new]` here loses a concurrent add: the CAS
                # sees a matching rev and overwrites the other writer's entry.
                appends["worktrees"] = [
                    {"path": os.path.abspath(args.add_worktree),
                     "branch": None, "added_at": utcnow_z()}]
            if args.rm_worktree:
                # Symmetric, and for the same reason: a precomputed filtered list
                # would discard whatever a concurrent writer appended.
                removes["worktrees"] = [
                    {"path": os.path.abspath(args.rm_worktree)}]
            model.mutate(threads_dir, args.id, changes, actor="cli",
                         appends=appends or None, removes=removes or None)
            return 0
        if args.verb == "park":
            model.mutate(threads_dir, args.id,
                         {"parked": True, "parked_reason": args.reason}, actor="cli")
            return 0
        if args.verb == "done":
            model.mutate(threads_dir, args.id,
                         {"done": True, "done_at": utcnow_z()}, actor="cli")
            return 0
        if args.verb == "reopen":
            model.mutate(threads_dir, args.id,
                         {"done": False, "done_at": None, "parked": False}, actor="cli")
            return 0
        if args.verb == "archive":
            dst = model.archive_thread(threads_dir, args.id)
            sys.stdout.write("moved to %s (reverse it with a plain mv)\n" % dst)
            return 0
        if args.verb == "use":
            # The pin the SessionStart hook consults second, after ABD_THREAD.
            # load_thread first so a typo'd id cannot pin a thread that does not
            # exist -- a silent wrong-card bug that would look like a hook fault.
            from agent_board import hookimpl, store
            t = model.load_thread(threads_dir, args.id)
            if t.get("_status") == "missing":
                raise model.ThreadNotFound(args.id)
            store.makedirs_private(threads_dir)
            store.atomic_write_text(
                os.path.join(threads_dir, hookimpl.PIN_NAME), args.id + "\n")
            return 0
    except model.ThreadIdUnavailable as exc:
        sys.stderr.write("abd: %s\n" % exc)
        return 2
    except model.ThreadNotFound as exc:
        sys.stderr.write("abd: no thread %r (list them with: abd board --json)\n"
                         % str(exc))
        return 2
    except model.ThreadRejected as exc:
        sys.stderr.write("abd: %s\n" % exc)
        return 2
    except model.ThreadCorrupt as exc:
        sys.stderr.write("abd: %s\n" % exc)
        return 2
    except RuntimeError as exc:
        sys.stderr.write("abd: %s\n" % exc)
        return 75
    except OSError as exc:
        # A filesystem failure is a one-line rc 2, like every other error in this
        # command and like the new init/export verbs -- not a traceback. Pre-existing
        # for `thread use` on an unwritable store; archive made it reachable with a
        # cross-device rename, and the fix covers both.
        sys.stderr.write("abd: %s\n" % exc)
        return 2
    return 2


def resolve_color(flag):
    if flag is not None:
        return bool(flag)
    if os.environ.get("NO_COLOR") is not None:      # PRESENCE, not truthiness
        return False
    if os.environ.get("CLICOLOR_FORCE") not in (None, "0"):
        return True
    return sys.stdout.isatty()


def resolve_width(arg):
    import shutil
    if arg:
        return int(arg)
    size = shutil.get_terminal_size((120, 40))
    if not sys.stdout.isatty():
        return 100          # documented clamp: the fallback is echoed back, not detected
    return size.columns


def _cmd_init(argv):
    import argparse

    from agent_board import anchor, store
    from agent_board.config import CONFIG_NAME, DEFAULTS

    ap = argparse.ArgumentParser(prog="abd init")
    ap.add_argument("--force", action="store_true",
                    help="overwrite an existing config file")
    ap.add_argument("--root")
    args = ap.parse_args(argv)

    start = args.root or os.getcwd()
    threads_dir = anchor.resolve_threads_dir(start)
    if not threads_dir:
        sys.stderr.write("abd: not in a git repository; set ABD_THREADS_DIR\n")
        return 2
    try:
        store.makedirs_private(os.path.join(threads_dir, "threads"))
    except OSError as exc:
        sys.stderr.write("abd: cannot create %s (%s)\n" % (threads_dir, exc))
        return 2
    sys.stdout.write("store ready at %s\n" % threads_dir)

    # The config file is optional -- every key has a default and a repo with no
    # config works. init writes a commented skeleton so the knobs are discoverable
    # without reading the source.
    # Where load_config will ACTUALLY read it. load_config(start) looks only at
    # <start>/.agent-board.json with no upward search, and every consumer passes cwd
    # -- so writing to the main worktree root (what _repo_root returns) produced a
    # file that is never read from a linked worktree, which is the normal case for a
    # tool about parallel worktrees. ABD_CONFIG wins, as it does everywhere else.
    config_path = os.environ.get("ABD_CONFIG") or os.path.join(start, CONFIG_NAME)
    if os.path.exists(config_path) and not args.force:
        sys.stdout.write("%s exists; leaving it alone (--force overwrites)\n"
                         % config_path)
        return 0
    skeleton = {"config_version": DEFAULTS["config_version"],
                "project": dict(DEFAULTS["project"]),
                "thresholds": dict(DEFAULTS["thresholds"]),
                "collisions": {"ignore_globs_extra": []},
                "scan": dict(DEFAULTS["scan"])}
    try:
        store.atomic_write_json(config_path, skeleton)
    except OSError as exc:
        sys.stderr.write("abd: cannot write %s (%s)\n" % (config_path, exc))
        return 2
    sys.stdout.write("wrote %s (every key is optional; delete it to use "
                     "defaults)\n" % config_path)
    # The BOARD is invisible to git by design -- it lives in .git/. The config is
    # not board state, it is an ordinary project file, so it does show up as
    # untracked. Say so, because the surprising consequence is that `git clean -xdn`
    # lists it, and because whether to share it is the user's call, not ours:
    # install-hooks could write .git/info/exclude unasked precisely because
    # settings.local.json is never shareable, and thresholds are.
    from agent_board.derive import git_
    inside_worktree = git_._git(os.path.dirname(config_path) or ".",
                                "rev-parse", "--is-inside-work-tree")
    if (inside_worktree or "").strip() == "true":
        sys.stdout.write(
            "note: unlike the board itself, this config is a normal file in your "
            "working tree.\n"
            "      commit it to share thresholds with collaborators, or exclude it:\n"
            "        printf '%s\\n' >> "
            "\"$(git rev-parse --git-common-dir)/info/exclude\"\n"
            "      until you do one or the other, `git clean -xdn` will list it.\n"
            % os.path.basename(config_path))
    else:
        # A bare repo has no working tree, so neither claim in that note holds:
        # nothing tracks the file and git clean has nothing to clean.
        sys.stdout.write("note: this repository is bare, so the config sits beside "
                         "HEAD and git will neither track nor clean it.\n")
    return 0


def _cmd_export(argv):
    import argparse

    from agent_board import anchor, portable

    ap = argparse.ArgumentParser(prog="abd export")
    ap.add_argument("path")
    ap.add_argument("--root")
    args = ap.parse_args(argv)
    threads_dir = anchor.resolve_threads_dir(args.root or os.getcwd())
    if not threads_dir:
        sys.stderr.write("abd: not in a git repository; set ABD_THREADS_DIR\n")
        return 2
    bundle = portable.build_bundle(threads_dir)
    try:
        portable.write_bundle(args.path, bundle)
    except OSError as exc:
        sys.stderr.write("abd: cannot write %s (%s)\n" % (args.path, exc))
        return 2
    sys.stdout.write("exported %d thread(s) and %d archived to %s\n"
                     % (len(bundle["threads"]), len(bundle["archived"]),
                        args.path))
    for row in bundle.get("unexportable") or []:
        # Named, not silently omitted: the on-disk record is damaged and is the
        # only copy of whatever is still recoverable.
        sys.stderr.write("abd: skipped %s (%s) -- damaged on disk, not exported\n"
                         % (row["id"], row["status"]))
    for tid in bundle.get("truncated") or []:
        sys.stderr.write("abd: %s had more events than the export cap; only the "
                         "newest %d are in the bundle\n"
                         % (tid, portable.DEFAULT_EVENT_CAP))
    return 2 if bundle.get("unexportable") else 0


def _cmd_import(argv):
    import argparse

    from agent_board import anchor, portable

    ap = argparse.ArgumentParser(prog="abd import")
    ap.add_argument("path")
    ap.add_argument("--force", action="store_true",
                    help="overwrite threads that already exist here")
    ap.add_argument("--root")
    args = ap.parse_args(argv)
    threads_dir = anchor.resolve_threads_dir(args.root or os.getcwd())
    if not threads_dir:
        sys.stderr.write("abd: not in a git repository; set ABD_THREADS_DIR\n")
        return 2
    bundle, error = portable.read_bundle(args.path)
    if error:
        sys.stderr.write("abd: %s: %s\n" % (args.path, error))
        return 2
    imported, skipped, problems = portable.import_bundle(
        threads_dir, bundle, force=args.force)
    sys.stdout.write("imported %d thread(s)\n" % len(imported))
    if skipped:
        sys.stdout.write(
            "skipped %d that already exist here (--force to overwrite): %s\n"
            % (len(skipped), ", ".join(skipped[:8])))
    for problem in problems:
        sys.stderr.write("abd: %s\n" % problem)
    return 2 if problems else 0


def _cmd_show(argv):
    import argparse
    import json as _json
    import signal

    from agent_board import anchor, board as boardmod, show as showmod

    # Same guard as the board: a detail view is long enough to fill a pipe buffer,
    # and `abd show <id> | head -1` raised BrokenPipeError as an 11-line traceback.
    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    ap = argparse.ArgumentParser(prog="abd show")
    ap.add_argument("id")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--ascii", action="store_true")
    ap.add_argument("--root")
    ap.add_argument("--store")
    ap.add_argument("--offline", action="store_true")
    args = ap.parse_args(argv)

    repo = args.root or os.getcwd()
    threads_dir = args.store or anchor.resolve_threads_dir(repo)
    if not threads_dir:
        sys.stderr.write("abd: not in a git repository; set ABD_THREADS_DIR\n")
        return 2
    board = boardmod.build_board(threads_dir, repo, None,
                                 allow_probe=not args.offline)
    detail, error = showmod.build(board, threads_dir, args.id)
    if error:
        sys.stderr.write("abd: %s (list them with: abd board --json)\n" % error)
        return 2
    if args.json:
        sys.stdout.write(_json.dumps(detail, indent=2, sort_keys=True) + "\n")
        return 0
    ascii_mode = args.ascii or (os.environ.get("ABD_ASCII") == "1")
    try:
        for line in showmod.render(detail, ascii_mode=ascii_mode):
            sys.stdout.write(line + "\n")
    except BrokenPipeError:
        return 141
    return 0


def _cmd_event(argv):
    import argparse

    from agent_board import anchor, events as events_mod, model

    ap = argparse.ArgumentParser(prog="abd event")
    sub = ap.add_subparsers(dest="verb", required=True)
    p_add = sub.add_parser("add")
    p_add.add_argument("id")
    p_add.add_argument("--kind", default="note")
    p_add.add_argument("--text", required=True)
    p_add.add_argument("--actor", default="cli")
    args = ap.parse_args(argv)

    if args.kind not in events_mod.VALID_KINDS:
        sys.stderr.write("abd: unknown kind %r (want: %s)\n"
                         % (args.kind, ", ".join(events_mod.VALID_KINDS)))
        return 2
    threads_dir = anchor.resolve_threads_dir(os.getcwd())
    if not threads_dir:
        sys.stderr.write("abd: not in a git repository; set ABD_THREADS_DIR\n")
        return 2
    # Refuse an id with no thread rather than creating a shard under it: an event
    # on a nonexistent thread is unreadable by every consumer and looks like data
    # loss later.
    status = model.load_thread(threads_dir, args.id).get("_status")
    if status not in ("ok", "degraded"):
        # NOT `== "missing"`: an id whose shape thread_dir rejects (a capitalised
        # typo, `../../evil`) comes back as "loader_crash", so the old guard let it
        # through and append_event silently swallowed the failure -- rc 0, nothing
        # written, no message.
        sys.stderr.write("abd: cannot write to thread %r (%s); list them with: "
                         "abd board --json\n" % (args.id, status))
        return 2
    # A long free-form --actor pushed the serialised record past MAX_LINE, and the
    # truncation pass only shortens text/goal/next_action -- so the whole --text was
    # replaced by a fields_dropped stub, rc 0, silently.
    if len(args.actor) > 64:
        sys.stderr.write("abd: --actor is limited to 64 characters\n")
        return 2
    locked = events_mod.append_event_locked(
        threads_dir, args.id,
        {"kind": args.kind, "actor": args.actor, "text": args.text})
    if not locked:
        sys.stderr.write("abd: warning: wrote without the lock (timed out); safe on "
                         "one node, at risk across nodes\n")
    return 0


def _cmd_board(argv):
    import argparse
    import json as _json
    import signal

    from agent_board import anchor, board as boardmod
    from agent_board.render import palette
    from agent_board.render.emit_plain import emit_plain
    from agent_board.render.layout import COLUMN_ORDER, render_board

    if hasattr(signal, "SIGPIPE"):
        signal.signal(signal.SIGPIPE, signal.SIG_DFL)

    ap = argparse.ArgumentParser(prog="abd board")
    ap.add_argument("filter", nargs="*", metavar="FILTER",
                    help="substring match on thread id, title or worktree path")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--width", type=int)
    ap.add_argument("--ascii", action="store_true")
    ap.add_argument("--color", dest="color", action="store_true", default=None)
    ap.add_argument("--no-color", dest="color", action="store_false")
    ap.add_argument("--column")
    ap.add_argument("--root")
    ap.add_argument("--store")
    ap.add_argument("--offline", action="store_true",
                    help="never probe the forge; serve whatever the cache holds")
    ap.add_argument("--cached", action="store_true",
                    help="render the last snapshot instantly instead of scanning")
    ap.add_argument("--watch", nargs="?", const=15, type=float, default=None,
                    metavar="SECS",
                    help="repaint on an interval (15s floor); q quits, r refreshes")
    ap.add_argument("--html", metavar="PATH",
                    help="write a self-contained HTML snapshot and exit")
    ap.add_argument("--all", dest="show_all", action="store_true",
                    help="also list worktrees no thread owns (probes every one)")
    ap.add_argument("--unattributed", action="store_true",
                    help="list scheduler jobs that matched no thread")
    args = ap.parse_args(argv)

    repo = args.root or os.getcwd()
    threads_dir = args.store or anchor.resolve_threads_dir(repo)
    if not threads_dir:
        sys.stderr.write("abd: not in a git repository; set ABD_THREADS_DIR\n")
        return 2

    from agent_board import cache as _cache

    def _build():
        return boardmod.build_board(threads_dir, repo, None,
                                    allow_probe=not args.offline,
                                    include_unowned=args.show_all)

    ascii_mode = args.ascii or (os.environ.get("ABD_ASCII") == "1")

    # Refuse rather than swallow. Every one of these combinations previously ran,
    # printed one view, and silently dropped the other flag -- while still paying
    # its cost: `--watch --all` re-probed every worktree on every 15 s refresh
    # forever and never rendered a single unowned row.
    if args.watch is not None:
        for flag, present in (("--all", args.show_all),
                              ("--unattributed", args.unattributed),
                              ("--html", bool(args.html)),
                              ("--json", args.json),
                              ("a FILTER", bool([t for t in args.filter if t]))):
            if present:
                sys.stderr.write("abd: --watch cannot be combined with %s\n" % flag)
                return 2
    if args.unattributed and [t for t in args.filter if t]:
        sys.stderr.write("abd: --unattributed lists jobs, so a thread FILTER "
                         "cannot apply to it\n")
        return 2
    if args.unattributed and args.show_all:
        sys.stderr.write("abd: --unattributed and --all are separate views; "
                         "run them one at a time\n")
        return 2

    if args.watch is not None:
        from agent_board import watch as watchmod
        width = resolve_width(args.width)
        color = resolve_color(args.color)

        def paint(board, notes):
            for line in render_board(board, width, ascii_mode=ascii_mode):
                sys.stdout.write(emit_plain(line, palette.DARK, color) + "\n")
            for note in notes:
                sys.stdout.write("  %s\n" % note)

        def build_and_cache():
            board = _build()
            _cache.write(threads_dir, boardmod.SNAPSHOT_NAME, board)
            return board
        return watchmod.run(build_and_cache, paint, interval=args.watch)

    # A cold scan on a large repo over a network filesystem is genuinely slow
    # (measured 32 s cold / 2.5 s warm on a 65-worktree repo, all of it I/O wait),
    # so the last derived board is persisted and can be rendered instantly.
    import time as _time
    data = None
    if args.cached:
        snapshot, age, _fresh = _cache.read(threads_dir, boardmod.SNAPSHOT_NAME,
                                            10 ** 9)
        if snapshot is not None:
            data = snapshot
            data.setdefault("signals", {})["snapshot_age_s"] = age
        else:
            sys.stderr.write("abd: no snapshot yet; scanning\n")
    if data is None:
        if args.show_all:
            # Honest rather than silent: --all probes every worktree, and on a
            # 64-worktree repo that is seconds, not milliseconds. A stderr notice
            # beats an animated spinner, which would need its own thread purely to
            # decorate a one-shot command.
            sys.stderr.write("abd: --all probes every worktree; this takes a few "
                             "seconds on a large repo...\n")
            sys.stderr.flush()
        started = _time.time()
        data = boardmod.build_board(threads_dir, repo, None,
                                    allow_probe=not args.offline,
                                    include_unowned=args.show_all)
        elapsed = _time.time() - started
        _cache.write(threads_dir, boardmod.SNAPSHOT_NAME, data)
        if elapsed > 5.0:
            sys.stderr.write(
                "abd: scan took %.0fs (cold filesystem cache); "
                "`abd board --cached` renders this snapshot instantly\n" % elapsed)
    # Decide emptiness against the UNFILTERED board. Checking after the filter
    # cannot tell "no threads at all" from "this lane is empty right now".
    store_is_empty = not any(data["columns"].values())
    if [t for t in args.filter if t]:
        # Every term must match somewhere on the card (AND), each term matching
        # any of id / title / worktree line. Applied AFTER store_is_empty is
        # decided, so "no threads at all" stays distinguishable from "nothing
        # matched" -- the same reason --column is applied here rather than earlier.
        # Drop empty terms: `abd board ""` is not a filter, and keeping it produced
        # a no-match message naming an empty filter with a trailing space.
        terms = [t.lower() for t in args.filter if t]

        def _matches(card):
            haystack = " ".join([str(card.get("id") or ""),
                                 str(card.get("title") or ""),
                                 " ".join(card.get("worktree_paths") or [])]).lower()
            return all(term in haystack for term in terms)
        data["columns"] = {name: [c for c in rows if _matches(c)]
                           for name, rows in (data.get("columns") or {}).items()}
    if args.column:
        if args.column not in COLUMN_ORDER:
            sys.stderr.write("abd: unknown column %r (known: %s)\n"
                             % (args.column, ", ".join(COLUMN_ORDER)))
            return 2
        data["columns"] = {k: v for k, v in data["columns"].items()
                           if k == args.column}
    if args.json:
        sys.stdout.write(_json.dumps(data, indent=2, sort_keys=True) + "\n")
        return 0

    if args.unattributed:
        from agent_board import show as showmod
        signals = data.get("signals") or {}
        rows = signals.get("unattributed_jobs")
        if rows is None:
            # A snapshot written before this view existed has the COUNT but not the
            # rows. Printing "none" would contradict that same snapshot's footer.
            sys.stderr.write("abd: this snapshot predates the unattributed view; "
                             "re-run without --cached\n")
            return 2
        lines = showmod.render_unattributed(rows, ascii_mode=ascii_mode)
        age = signals.get("snapshot_age_s")
        if age is not None:
            from agent_board.render.layout import _ago
            lines.append("")
            lines.append("snapshot from %s ago - re-run without --cached to refresh"
                         % _ago(age))
        for line in lines:
            sys.stdout.write(line + "\n")
        return 0

    if store_is_empty and not args.show_all:
        sys.stdout.write(
            "no threads yet - open one with: abd thread new --title \"...\"\n")
        return 0
    if store_is_empty:
        sys.stdout.write(
            "no threads yet - open one with: abd thread new --title \"...\"\n\n")
    elif not any(data["columns"].values()):
        what = []
        if args.column:
            what.append("column %s" % args.column)
        terms = [t for t in args.filter if t]
        if terms:
            # Echoing the raw term put arbitrary text on stdout unsanitised: an
            # ANSI escape stuck, a newline broke the one-line contract, and
            # --ascii stopped being ASCII.
            from agent_board.show import _s
            what.append("filter %s" % _s(" ".join(terms), ascii_mode))
        sys.stdout.write("no threads matching %s\n"
                         % (" and ".join(what) or "that view"))
        if not args.show_all:
            return 0

    if args.html:
        import io as _io
        import time as _tm

        from agent_board import model as _model
        from agent_board.render.html import export
        # The DAG needs the raw threads and their columns, which the rendered
        # board flattens away.
        threads = _model.load_all(threads_dir)
        if [t for t in args.filter if t]:
            # The DAG iterates threads_by_id, so passing every thread on disk drew
            # nodes for threads the filter had removed -- and labelled their column
            # from the filtered board, i.e. wrongly.
            visible = {c["id"] for rows in (data.get("columns") or {}).values()
                       for c in rows}
            threads = {k: v for k, v in threads.items() if k in visible}
        cols = {}
        for tid, thread in threads.items():
            for name, rows in (data.get("columns") or {}).items():
                if any(c["id"] == tid for c in rows):
                    cols[tid] = name
                    break
        page = export(data, threads_by_id=threads, columns=cols,
                      generated_at=_tm.strftime("%Y-%m-%d %H:%M"))
        try:
            with _io.open(args.html, "w", encoding="utf-8") as fh:
                fh.write(page)
        except OSError as exc:
            sys.stderr.write("abd: cannot write %s (%s)\n" % (args.html, exc))
            return 2
        sys.stdout.write("wrote %s (%d bytes)\n" % (args.html, len(page)))
        return 0

    width = resolve_width(args.width)
    color = resolve_color(args.color)
    try:
        if not store_is_empty:
            for line in render_board(data, width, ascii_mode=ascii_mode):
                sys.stdout.write(emit_plain(line, palette.DARK, color) + "\n")
        if args.show_all:
            from agent_board import show as showmod
            unowned = data.get("unowned")
            if not store_is_empty:
                sys.stdout.write("\n")
            if unowned is None:
                # None means NOT COMPUTED (a snapshot from a run without --all);
                # [] means computed and genuinely empty. Collapsing the two let
                # `--all --cached` assert "every worktree belongs to a thread"
                # about data it had never looked at.
                sys.stdout.write("unowned worktrees were not computed for this "
                                 "snapshot - re-run without --cached\n")
            else:
                for line in showmod.render_unowned(unowned, ascii_mode=ascii_mode):
                    sys.stdout.write(line + "\n")
    except BrokenPipeError:
        return 141
    return 0


def main(argv):
    if not argv:
        sys.stdout.write(
            "usage: abd {board,show,thread,event,init,export,import,hook,"
            "install-hooks,doctor} ...\n")
        return 2
    cmd = argv[0]
    if cmd in ("--version", "-V"):
        sys.stdout.write("agent-board %s\n" % __version__)
        return 0
    if cmd == "hook":
        return _hook(argv[1:])
    if cmd == "thread":
        return _cmd_thread(argv[1:])
    if cmd == "board":
        return _cmd_board(argv[1:])
    if cmd == "install-hooks":
        return _cmd_install_hooks(argv[1:])
    if cmd == "doctor":
        return _cmd_doctor(argv[1:])
    if cmd == "show":
        return _cmd_show(argv[1:])
    if cmd == "event":
        return _cmd_event(argv[1:])
    if cmd == "init":
        return _cmd_init(argv[1:])
    if cmd == "export":
        return _cmd_export(argv[1:])
    if cmd == "import":
        return _cmd_import(argv[1:])
    sys.stderr.write("abd: unknown command %r\n" % cmd)
    return 2
