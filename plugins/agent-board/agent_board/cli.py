import os
import sys

from agent_board import __version__


def _hook(argv):
    """Hook entry. Fails open: prints nothing, always returns 0."""
    try:
        for truthy in ("1", "true", "TRUE", "yes", "YES"):
            if os.environ.get("ABD_DISABLE") == truthy:
                return 0
        if os.path.exists(os.path.expanduser("~/.agent-board-DISABLED")):
            return 0
        return 0  # real behaviour lands in M3
    except BaseException:
        return 0


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
    for verb in ("park", "done", "reopen"):
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
    from agent_board.render.layout import render_board

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
    args = ap.parse_args(argv)

    repo = args.root or os.getcwd()
    threads_dir = args.store or anchor.resolve_threads_dir(repo)
    if not threads_dir:
        sys.stderr.write("abd: not in a git repository; set ABD_THREADS_DIR\n")
        return 2

    data = boardmod.build_board(threads_dir, repo, None)
    if args.column:
        data["columns"] = {k: v for k, v in data["columns"].items()
                           if k == args.column}
    if args.json:
        sys.stdout.write(_json.dumps(data, indent=2, sort_keys=True) + "\n")
        return 0
    if not any(data["columns"].values()):
        sys.stdout.write(
            "no threads yet - open one with: abd thread new --title \"...\"\n")
        return 0

    ascii_mode = args.ascii or (os.environ.get("ABD_ASCII") == "1")
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
        sys.stdout.write("usage: abd {board,thread,show,hook,init,doctor} ...\n")
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
    sys.stderr.write("abd: unknown command %r\n" % cmd)
    return 2
