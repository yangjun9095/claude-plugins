"""The SKILL.md contract.

The point of this file is one guard: **every `abd` command the skill tells an agent
to run must actually work.** It was written after the skill shipped referencing
`abd thread set --job-prefix`, which did not exist -- so an agent following the
documented wrap-up would have hit `usage:` and rc 2. Prose and CLI drift silently;
this makes the drift fail a test.
"""
import io
import os
import re

import pytest

SKILL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                     "skills", "agent-board", "SKILL.md")

# Placeholders the skill writes for the human to fill in.
SUBS = {
    "<id>": "t", "<other-id>": "other", "<n>": "42", "<prefix>": "mhb_",
    "<path>": ".", "<at most 8 words>": "T", "<1-2 sentences>": "G",
    "<the single next concrete step, one line>": "next step",
    "<why>": "on ice", "<base directory>": ".", "<one sentence>": "a note",
}
# A placeholder missing from this map makes its command silently unverified -- the
# newest one, `abd event add`, was dropped exactly that way. The test below asserts
# the count, so an unmapped placeholder now shows up as a failure.
EXPECTED_COMMAND_COUNT = 21


def _text():
    with io.open(SKILL, encoding="utf-8") as fh:
        return fh.read()


def skill_commands():
    """Every `abd ...` invocation in the file, as an argv list ready to run.

    Extracts from BOTH fenced bash blocks and inline code spans -- the table of
    "when the user asks X, run Y" is inline, and an earlier version of this regex
    was anchored to line starts, so it silently matched none of that table and the
    tests below passed while checking almost nothing.
    """
    import shlex
    # Stop at the prohibitions: that section NAMES commands in order to forbid
    # them. An earlier version scanned it too, extracted `abd board --watch`, ran
    # it, and hung the suite in the watch loop for two minutes.
    text = _text().split("## Never", 1)[0]
    lines = []
    for block in re.findall(r"```bash\n(.*?)```", text, re.S):
        lines.extend(block.splitlines())
    lines.extend(re.findall(r"`([^`\n]+)`", text))

    out = []
    for raw in lines:
        line = raw.strip()
        if not line.startswith("abd "):
            continue
        line = line.split("||")[0]                  # `abd --version || echo ...`
        line = re.sub(r"\s+#.*$", "", line)         # trailing explanatory comment
        for token, value in SUBS.items():
            line = line.replace(token, value)
        line = line.replace("$PWD", ".")
        if "<" in line and ">" in line:             # unsubstituted placeholder
            continue
        try:
            argv = shlex.split(line)                # honours the quoting as written
        except ValueError:
            continue
        if len(argv) > 1:
            out.append(tuple(argv[1:]))             # drop the leading "abd"
    return sorted(set(out))


# --- the file itself ---------------------------------------------------------

def test_frontmatter_is_wellformed_and_names_match_the_directory():
    text = _text()
    match = re.match(r"^---\n(.*?)\n---\n", text, re.S)
    assert match, "SKILL.md must open with a YAML frontmatter block"
    front = match.group(1)
    assert re.search(r"^name:\s*agent-board\s*$", front, re.M)
    assert re.search(r"^description:\s*\S", front, re.M)
    assert re.search(r"^allowed-tools:", front, re.M)
    assert os.path.basename(os.path.dirname(SKILL)) == "agent-board"


def test_no_shell_prefetch_syntax_anywhere():
    """A bang followed by a backticked command runs while the skill LOADS, in a
    separate sandbox that ignores session settings and dies on RHEL8. Even the
    paragraph forbidding it must not spell it out."""
    assert not re.search(r"!`", _text())


def test_no_hardcoded_absolute_paths():
    """The Skill tool supplies the base directory; a baked path breaks on every
    other machine and after every plugin update."""
    text = _text()
    assert "/hpc/" not in text
    assert "/home/" not in text
    assert not re.search(r"~/\.claude/plugins", text)


def test_the_documented_launcher_fallback_actually_resolves():
    fallback = os.path.join(os.path.dirname(SKILL), "..", "..", "bin", "abd")
    assert os.path.isfile(fallback), fallback
    assert os.access(fallback, os.X_OK)


def test_the_skill_states_the_one_line_writing_burden():
    text = _text()
    assert "--next-action" in text
    assert re.search(r"one line", text, re.I)


@pytest.mark.parametrize("rule", [
    "thread.json",          # never write it directly
    "derived",              # never record derived state
    "--watch",              # never run watch from inside a session
    "--add-worktree",       # never one thread per worktree
    "blocked_by",           # never invent a blocker id
])
def test_the_prohibitions_survive_edits(rule):
    """Each of these is a measured failure mode, not style. If an edit drops one,
    this fails rather than the guidance quietly disappearing."""
    never = _text().split("## Never", 1)
    assert len(never) == 2, "the Never section must exist"
    assert rule in never[1]


# --- every command it names must run -----------------------------------------

def test_extraction_found_the_commands_at_all():
    """A guard on the guard: a regex that silently matches nothing would make every
    command test below vacuously pass."""
    commands = skill_commands()
    assert len(commands) == EXPECTED_COMMAND_COUNT, (
        "expected %d commands, extracted %d -- if you added one to SKILL.md bump the "
        "constant; if it DROPPED, a placeholder is missing from SUBS and that "
        "command is going unverified:\n%s"
        % (EXPECTED_COMMAND_COUNT, len(commands),
           "\n".join("abd " + " ".join(c) for c in commands)))
    assert any(c[:2] == ("event", "add") for c in commands)
    assert any(c[:2] == ("thread", "new") for c in commands)
    assert any(c[:2] == ("thread", "set") and "--next-action" in c
               for c in commands)
    assert ("board",) in commands, commands
    assert any("--column" in c for c in commands), "the inline table was not scanned"


def test_every_command_the_skill_names_is_accepted_by_the_cli(
        repo_with_worktrees, tmp_path, monkeypatch, capsys):
    """Runs each one for real. argparse exits 2 on an unknown flag, so a documented
    command that does not exist fails here instead of in a user's session."""
    from agent_board import cli, model

    main, _wts = repo_with_worktrees
    store_dir = tmp_path / "board"
    (store_dir / "threads").mkdir(parents=True)
    monkeypatch.setenv("ABD_THREADS_DIR", str(store_dir))
    monkeypatch.setenv("ABD_ALLOW_NETWORK", "0")
    monkeypatch.chdir(main)
    model.new_thread(str(store_dir), "T", worktrees=[{"path": str(main)}])
    model.new_thread(str(store_dir), "Other")

    failures = []
    for argv in skill_commands():
        argv = list(argv)
        # Belt and braces alongside the extraction cutoff: this test must never
        # enter an interactive loop, whatever a future edit adds to the file.
        assert "--watch" not in argv, "SKILL.md must not instruct --watch"
        if "--html" in argv:
            argv[argv.index("--html") + 1] = str(tmp_path / "out.html")
        try:
            rc = cli.main(argv)
        except SystemExit as exc:               # argparse's own exit
            rc = exc.code if isinstance(exc.code, int) else 2
        except BaseException as exc:
            failures.append("abd %s -> raised %r" % (" ".join(argv), exc))
            continue
        capsys.readouterr()
        if rc == 2:
            failures.append("abd %s -> rc 2 (unknown verb or flag)" % " ".join(argv))
    assert not failures, "commands documented in SKILL.md that do not work:\n" + \
                         "\n".join(failures)
