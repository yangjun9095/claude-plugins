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
    p_set.add_argument("--add-worktree", dest="add_worktree")
    for verb in ("park", "done", "reopen", "use"):
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
            for field in ("title", "goal", "next_action", "blocked_by"):
                val = getattr(args, field, None)
                if val is not None:
                    changes[field] = val
            appends = None
            if args.add_worktree:
                # Pass it as an APPEND so the merge happens inside mutate's lock.
                # Precomputing `cur + [new]` here loses a concurrent add: the CAS
                # sees a matching rev and overwrites the other writer's entry.
                appends = {"worktrees": [
                    {"path": os.path.abspath(args.add_worktree),
                     "branch": None, "added_at": utcnow_z()}]}
            model.mutate(threads_dir, args.id, changes, actor="cli",
                         appends=appends)
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
    args = ap.parse_args(argv)

    repo = args.root or os.getcwd()
    threads_dir = args.store or anchor.resolve_threads_dir(repo)
    if not threads_dir:
        sys.stderr.write("abd: not in a git repository; set ABD_THREADS_DIR\n")
        return 2

    from agent_board import cache as _cache

    def _build():
        return boardmod.build_board(threads_dir, repo, None,
                                    allow_probe=not args.offline)

    ascii_mode = args.ascii or (os.environ.get("ABD_ASCII") == "1")

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
        started = _time.time()
        data = boardmod.build_board(threads_dir, repo, None,
                                    allow_probe=not args.offline)
        elapsed = _time.time() - started
        _cache.write(threads_dir, boardmod.SNAPSHOT_NAME, data)
        if elapsed > 5.0:
            sys.stderr.write(
                "abd: scan took %.0fs (cold filesystem cache); "
                "`abd board --cached` renders this snapshot instantly\n" % elapsed)
    # Decide emptiness against the UNFILTERED board. Checking after the filter
    # cannot tell "no threads at all" from "this lane is empty right now".
    store_is_empty = not any(data["columns"].values())
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
    if store_is_empty:
        sys.stdout.write(
            "no threads yet - open one with: abd thread new --title \"...\"\n")
        return 0
    if not any(data["columns"].values()):
        sys.stdout.write("no threads in %s\n" % args.column)
        return 0

    if args.html:
        import io as _io
        import time as _tm

        from agent_board import model as _model
        from agent_board.render.html import export
        # The DAG needs the raw threads and their columns, which the rendered
        # board flattens away.
        threads = _model.load_all(threads_dir)
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
        for line in render_board(data, width, ascii_mode=ascii_mode):
            sys.stdout.write(emit_plain(line, palette.DARK, color) + "\n")
    except BrokenPipeError:
        return 141
    return 0


def main(argv):
    if not argv:
        sys.stdout.write(
            "usage: abd {board,thread,hook,install-hooks,show,init,doctor} ...\n")
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
    sys.stderr.write("abd: unknown command %r\n" % cmd)
    return 2
