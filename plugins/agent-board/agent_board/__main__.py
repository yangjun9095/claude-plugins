import sys


def _reconfigure_stdout():
    # Mandatory: under LC_ALL=C, printing non-ASCII raises UnicodeEncodeError.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except (AttributeError, ValueError):
            pass


def main():
    _reconfigure_stdout()

    # Fail-open guarantee for hook invocations: must exit 0 with empty output,
    # even if import or dispatch fails. Check if this is a hook BEFORE importing.
    is_hook = len(sys.argv) > 1 and sys.argv[1] == "hook"

    try:
        from agent_board.cli import main as cli_main
        raise SystemExit(cli_main(sys.argv[1:]))
    except BaseException:
        if is_hook:
            raise SystemExit(0)
        raise


if __name__ == "__main__":
    main()
