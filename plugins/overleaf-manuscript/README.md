# overleaf-manuscript

Three tools for LaTeX manuscripts that sync with Overleaf.

- `preflight.sh` reports how the folder syncs (Overleaf git, GitHub-linked, or a Dropbox copy) and whether the local copy is current.
- `audit.py` checks prose for banned words, constructions, em-dash density, spelling and figure references. It reports and never edits.
- A hook asks for approval before Claude edits a `.tex`, `.sty` or `.bib` file in a folder that holds `main.tex`.

The rules and house style live in the claude.ai skill `manuscript-write`. This plugin points to it and repeats nothing.

Run the tests from this folder: `python3 -m unittest discover -s tests -v`.
