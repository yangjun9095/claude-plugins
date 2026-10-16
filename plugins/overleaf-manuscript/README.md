# overleaf-manuscript

Three tools for LaTeX manuscripts that sync with Overleaf.

- `preflight.sh` reports the sync mode and whether the local copy is current. The mode is `overleaf-git`, `github-linked`, `other` (any other remote) or `no-git`. The `no-git` mode covers any folder that is not a git work tree, such as a Dropbox copy.
- `audit.py` checks prose for banned words, constructions, em-dash density, spelling and figure references. It reports and never edits.
- A hook asks for approval before Claude edits a `.tex`, `.sty`, `.cls` or `.bib` file in a manuscript folder. A folder counts when it holds `main.tex`, or when `main.tex` sits up to four levels above the file.

The rules and house style live in the claude.ai skill `manuscript-write`. This plugin points to it and repeats nothing.

Run the tests from this folder: `python3 -m unittest discover -s tests -v`.
