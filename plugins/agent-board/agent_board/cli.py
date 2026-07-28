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
            if args.add_worktree:
                cur = model.load_thread(threads_dir, args.id)["worktrees"]
                changes["worktrees"] = cur + [
                    {"path": os.path.abspath(args.add_worktree),
                     "branch": None, "added_at": utcnow_z()}]
            model.mutate(threads_dir, args.id, changes, actor="cli")
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
    except model.ThreadRejected as exc:
        sys.stderr.write("abd: %s\n" % exc)
        return 2
    except RuntimeError as exc:
        sys.stderr.write("abd: %s\n" % exc)
        return 75
    return 2


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
    sys.stderr.write("abd: unknown command %r\n" % cmd)
    return 2
