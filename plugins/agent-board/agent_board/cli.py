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
    sys.stderr.write("abd: unknown command %r\n" % cmd)
    return 2
