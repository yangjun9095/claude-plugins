"""Write a made-up LaTeX manuscript from the 60 fixture paragraphs.

Command line: `python3 make_manuscript.py OUT_DIR`. The tool writes `main.tex` and `refs.bib` into
OUT_DIR and nothing else. It creates OUT_DIR when the folder does not exist. It stops with exit code 2
and a message on stderr when OUT_DIR holds any file or folder, or when it cannot write.

The output is the same on every run. The manuscript holds four sections, a figure environment, two
equations, a table and `\\cite` commands. Each fixture paragraph appears once, as one line of text.

How the tool treats a paragraph.
- It escapes the LaTeX special characters, so `81%` becomes `81\\%`.
- It turns a citation such as `(Brantwick et al., 2018)` into `\\citep{brantwick2018}` and adds
  the key to `refs.bib`. The names in the fixtures are invented.
- It assigns paragraph p01 to p12 to the Introduction, p13 to p27 to the Methods, p28 to p47 to
  the Results and p48 to p60 to the Discussion. The assignment follows the order of the ids.
"""
import argparse
import io
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PARAGRAPHS = os.path.join(HERE, "fixtures", "paragraphs.json")
PROG = "make_manuscript.py"

# Each section takes the paragraphs from `first` up to, but not including, `stop` (zero-based).
SECTIONS = (("Introduction", 0, 12), ("Methods", 12, 27), ("Results", 27, 47), ("Discussion", 47, 60))
EQUATIONS_AFTER = ("Methods", 1)
FIGURE_AFTER = ("Results", 2)
TABLE_AFTER = ("Results", 5)
CAPTION_KEYS = ("brantwick2018", "quenby2020")

_CITATION = re.compile(r"\(([A-Z][a-z]+ et al\., \d{4}(?:; [A-Z][a-z]+ et al\., \d{4})*)\)")
_ONE_CITATION = re.compile(r"([A-Z][a-z]+) et al\., (\d{4})")
_ESCAPES = {
    "\\": r"\textbackslash{}", "&": r"\&", "%": r"\%", "$": r"\$", "#": r"\#", "_": r"\_",
    "{": r"\{", "}": r"\}", "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
}

PREAMBLE = r"""\documentclass[11pt]{article}
\usepackage[utf8]{inputenc}
\usepackage[T1]{fontenc}
\usepackage{amsmath}
\usepackage{graphicx}
\usepackage{natbib}

\title{A Made-Up Manuscript on Moss, Fern and Lichen}
\author{An Imaginary Author}
\date{}

\begin{document}
\maketitle

\begin{abstract}
This manuscript is made up. It joins short passages on moss, fern, lichen and midge biology. Every
organism, assay and number in it is invented.
\end{abstract}
"""

EQUATION_BLOCK = r"""Equations~\eqref{eq:growth} and \eqref{eq:decay} give the growth model and the decay model.

\begin{equation}
\frac{dN}{dt} = r N \left(1 - \frac{N}{K}\right)
\label{eq:growth}
\end{equation}

\begin{equation}
S(t) = S_0 \, e^{-\lambda t}
\label{eq:decay}
\end{equation}
"""

FIGURE_BLOCK = r"""Figure~\ref{fig:design} shows the design of the made-up assay.

\begin{figure}[ht]
\centering
\framebox[0.6\textwidth]{\rule{0pt}{3cm}}
\caption{Made-up design of the assay, after \cite{brantwick2018}.}
\label{fig:design}
\end{figure}
"""

TABLE_BLOCK = r"""Table~\ref{tab:assays} lists three made-up assays.

\begin{table}[ht]
\centering
\caption{Made-up summary of three assays, as in \cite{quenby2020}.}
\label{tab:assays}
\begin{tabular}{lrr}
\hline
Assay & Samples & Mean signal \\
\hline
Ring-flux & 36 & 2.4 \\
Spore-lift & 40 & 1.9 \\
Gill-clearing & 15 & 0.7 \\
\hline
\end{tabular}
\end{table}
"""

CLOSING = r"""\bibliographystyle{plainnat}
\bibliography{refs}

\end{document}
"""


class ToolError(Exception):
    """The tool cannot run. The message goes to stderr and the exit code is 2."""


def escape(text):
    """Return the text with every LaTeX special character escaped."""
    return "".join(_ESCAPES.get(char, char) for char in text)


def convert(text, keys):
    """Return the paragraph as LaTeX. Add the key of each citation to the set `keys`."""
    parts, pos = [], 0
    for match in _CITATION.finditer(text):
        parts.append(escape(text[pos:match.start()]))
        found = [name.lower() + year for name, year in _ONE_CITATION.findall(match.group(1))]
        keys.update(found)
        parts.append("\\citep{" + ",".join(found) + "}")
        pos = match.end()
    parts.append(escape(text[pos:]))
    return "".join(parts)


def load_paragraphs(path=PARAGRAPHS):
    """Return the list of paragraph texts, in the order of the file."""
    try:
        with io.open(path, encoding="utf-8") as handle:
            rows = json.load(handle)
    except (OSError, ValueError) as error:
        raise ToolError("cannot read the fixtures %s: %s." % (path, error))
    try:
        texts = [row["text"] for row in rows]
    except (KeyError, TypeError):
        raise ToolError("the fixtures %s do not hold a list of paragraphs with a text." % path)
    if len(texts) != SECTIONS[-1][2]:
        raise ToolError("the fixtures hold %d paragraphs. The manuscript needs %d." % (len(texts), SECTIONS[-1][2]))
    return texts


def build(texts):
    """Return (main.tex, refs.bib) as two strings."""
    keys = set(CAPTION_KEYS)
    blocks = [PREAMBLE]
    extras = {EQUATIONS_AFTER: EQUATION_BLOCK, FIGURE_AFTER: FIGURE_BLOCK, TABLE_AFTER: TABLE_BLOCK}
    for name, first, stop in SECTIONS:
        blocks.append("\\section{%s}\n" % name)
        for number, text in enumerate(texts[first:stop]):
            blocks.append(convert(text, keys) + "\n")
            if (name, number) in extras:
                blocks.append(extras[(name, number)])
    blocks.append(CLOSING)
    tex = "\n".join(blocks)
    entries = []
    for key in sorted(keys):
        surname, year = key[:-4], key[-4:]
        entries.append(
            "@article{%s,\n  author = {%s, A.},\n  title = {A made-up report on moss, fern and lichen, number %s},\n"
            "  journal = {Journal of Imaginary Botany},\n  year = {%s}\n}\n" % (key, surname.capitalize(), year, year))
    return tex, "\n".join(entries)


def _check_target(out_dir):
    if os.path.exists(out_dir) and not os.path.isdir(out_dir):
        raise ToolError("%s is not a folder." % out_dir)
    if os.path.isdir(out_dir) and os.listdir(out_dir):
        raise ToolError("%s is not empty. Give an empty folder or a new one." % out_dir)


def _write(path, text):
    with io.open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def main(argv=None, err=None):
    """Run the command line. Return the exit code."""
    err = err or sys.stderr
    parser = argparse.ArgumentParser(prog=PROG, description="Write a made-up LaTeX manuscript.")
    parser.add_argument("out_dir", metavar="OUT_DIR", help="an empty folder, or a folder that does not exist")
    try:
        args = parser.parse_args(argv)
    except SystemExit as stop:
        return stop.code
    try:
        texts = load_paragraphs()
        tex, bib = build(texts)
        _check_target(args.out_dir)
        os.makedirs(args.out_dir, exist_ok=True)
        _write(os.path.join(args.out_dir, "main.tex"), tex)
        _write(os.path.join(args.out_dir, "refs.bib"), bib)
    except ToolError as error:
        err.write("%s: error: %s\n" % (PROG, error))
        return 2
    except OSError as error:
        err.write("%s: error: cannot write %s: %s.\n" % (PROG, args.out_dir, error.strerror or error))
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
