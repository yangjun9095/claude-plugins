#!/usr/bin/env python3
"""PreToolUse hook: ask before Claude edits a LaTeX file in a manuscript folder.

Reads the hook payload as JSON on stdin. Prints a permission decision, or nothing.
Fails open: an error prints to stderr and exits 0, so a broken hook never blocks work.
"""
import json
import sys
from pathlib import Path

WATCHED = {".tex", ".sty", ".bib"}
TOOLS = {"Edit", "Write", "MultiEdit"}
LEVELS_UP = 4

# Rule numbers refer to section 1 of the manuscript-write skill.
REASONS = {
    "main.tex": ("Rule 4: main.tex is the file most prone to Overleaf conflicts. "
                 "Confirm that Overleaf is closed, then approve this edit."),
    ".sty": "Rule 3: this is a shared style file. Edit it only after the author approves.",
    ".bib": ("Rule 2: never invent BibTeX keys or ORCIDs. "
             "Edit the bibliography only after the author approves."),
    ".tex": "Rule 1: edit a .tex file only after explicit approval in the current turn.",
}


def in_manuscript(path):
    """True when path is main.tex or sits up to LEVELS_UP directories below a main.tex."""
    if path.name == "main.tex":
        return True
    return any((parent / "main.tex").is_file() for parent in list(path.parents)[:LEVELS_UP])


def decide(payload):
    if payload.get("tool_name") not in TOOLS:
        return None
    raw = (payload.get("tool_input") or {}).get("file_path")
    if not raw:
        return None
    path = Path(raw)
    if not path.is_absolute():
        path = Path(payload.get("cwd") or ".") / path
    suffix = path.suffix.lower()
    if suffix not in WATCHED or not in_manuscript(path):
        return None
    key = "main.tex" if path.name == "main.tex" else suffix
    return {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                   "permissionDecision": "ask",
                                   "permissionDecisionReason": REASONS[key]}}


def main():
    try:
        out = decide(json.load(sys.stdin))
    except Exception as exc:  # fail open
        print("guard_tex_edit: ignored error: %s" % exc, file=sys.stderr)
        return 0
    if out:
        print(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
