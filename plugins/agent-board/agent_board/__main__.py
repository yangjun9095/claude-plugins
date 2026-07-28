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
    from agent_board.cli import main as cli_main
    raise SystemExit(cli_main(sys.argv[1:]))


if __name__ == "__main__":
    main()
