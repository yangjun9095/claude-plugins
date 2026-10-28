"""Tests for scripts/prose_mask.py. All text in this file is made up."""
import os
import random
import re
import subprocess
import sys
import time
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "scripts"))

import prose_mask as pm  # noqa: E402

OPEN, CLOSE = "\ue000", "\ue001"
SHOW = re.compile(OPEN + "(\\d+)" + CLOSE)
FORMATS = ("latex", "markdown", "text")


def show(masked):
    """Return the masked text with each placeholder written as <i>."""
    return SHOW.sub(lambda m: "<%s>" % m.group(1), masked.text)


def pieces(masked):
    return [pm.piece(masked, i) for i in range(len(masked.spans))]


# Each case: label, source, shown masked text, span kinds, optional hidden pieces.
LATEX_CASES = [
    # Rule 1: preamble and tail.
    ("preamble and tail",
     "\\documentclass{article}\n\\usepackage{x}\n\\begin{document}\nHello.\n\\end{document}\nAfter.\n",
     "<0>\nHello.\n<1>", "env env",
     ["\\documentclass{article}\n\\usepackage{x}\n\\begin{document}", "\\end{document}\nAfter.\n"]),
    ("preamble text is hidden", "\\title{A made-up title}\n\\begin{document}\nBody.\n\\end{document}",
     "<0>\nBody.\n<1>", "env env"),
    ("begin document in a comment", "% \\begin{document}\nProse here.\n", "<0>\nProse here.\n", "comment"),
    ("no begin document", "\\usepackage{x}\nProse.\n", "<0>\nProse.\n", "command"),
    ("begin document in verbatim", "\\begin{verbatim}\n\\begin{document}\n\\end{verbatim}\nProse.\n",
     "<0>\nProse.\n", "env"),
    ("end document without begin", "Prose.\n\\end{document}\nMore prose.\n",
     "Prose.\n<0>\nMore prose.\n", "env"),
    # Rule 2: comments.
    ("comment keeps the newline", "a % a note\nb\n", "a <0>\nb\n", "comment", ["% a note"]),
    ("escaped percent", "50\\% of cases\n", "50<0> of cases\n", "command", ["\\%"]),
    ("double backslash then percent", "a \\\\% note\nb", "a <0><1>\nb", "command comment",
     ["\\\\", "% note"]),
    ("triple backslash then percent", "a \\\\\\% b", "a <0><1> b", "command command", ["\\\\", "\\%"]),
    ("comment with CRLF", "a % note\r\nb\r\n", "a <0>\r\nb\r\n", "comment", ["% note"]),
    ("comment hides math and commands", "% \\section{X} $y\nText\n", "<0>\nText\n", "comment"),
    ("comment at the end without newline", "a % tail", "a <0>", "comment"),
    # Rule 3: environments that are masked whole.
    ("verbatim", "Before \\begin{verbatim}\n% x $ \\section{Y}\n\\end{verbatim} after", "Before <0> after", "env"),
    ("nested tabular",
     "\\begin{tabular}{ll}\n\\begin{tabular}{c}a\\end{tabular}\nb\\end{tabular} after", "<0> after", "env"),
    ("starred equation", "\\begin{equation*}\nx\n\\end{equation*}\nText.", "<0>\nText.", "env"),
    ("unclosed tabular", "Text \\begin{tabular}{l} a & b\nmore", "Text <0>", "env"),
    ("commented end inside tabular", "\\begin{tabular}{l}\n% \\end{tabular}\na\n\\end{tabular} after",
     "<0> after", "env"),
    ("verbatim ends at the first end", "\\begin{verbatim}\n% \\end{verbatim}\n\\end{verbatim} after",
     "<0>\n<1> after", "env env"),
    ("lstlisting with options", "\\begin{lstlisting}[language=C]\nint x;\n\\end{lstlisting}\nText",
     "<0>\nText", "env"),
    # Rule 4: math.
    ("inline math", "$x^2$", "<0>", "math"),
    ("two inline maths", "Let $a$ and $b$ be.", "Let <0> and <1> be.", "math math"),
    ("display dollars", "$$a+b$$ text", "<0> text", "math"),
    ("paren and bracket math", "\\(a\\) and \\[b\\]", "<0> and <1>", "math math"),
    ("escaped dollar", "\\$5 and \\$6", "<0>5 and <1>6", "command command", ["\\$", "\\$"]),
    ("escaped dollar inside math", "$a\\$b$ c", "<0> c", "math"),
    ("unclosed dollar", "a $x b\n\nNext para.\n", "a <0>\n\nNext para.\n", "math", ["$x b"]),
    ("unclosed dollar over lines", "a $x\nstill\n\nNext.", "a <0>\n\nNext.", "math"),
    ("unclosed display dollars", "$$x\n\nNext", "<0>\n\nNext", "math"),
    ("unclosed dollar with CRLF", "a $x b\r\n\r\nNext\r\n", "a <0>\r\n\r\nNext\r\n", "math"),
    ("closing dollar in the next paragraph", "a $x\n\nb$ c", "a <0>\n\nb<1>", "math math", ["$x", "$ c"]),
    ("stray dollar at the end", "cost $", "cost <0>", "math"),
    # Rule 5: other environment tokens.
    ("figure",
     "\\begin{figure}\n\\includegraphics[width=3cm]{f.png}\n\\caption{Cells divide.}\n\\end{figure}\n",
     "<0>\n<1>\n<2>Cells divide.<3>\n<4>\n", "env command command command env",
     ["\\begin{figure}", "\\includegraphics[width=3cm]{f.png}", "\\caption{", "}", "\\end{figure}"]),
    ("itemize", "\\begin{itemize}\n\\item First point.\n\\item Second.\n\\end{itemize}",
     "<0>\n<1> First point.\n<2> Second.\n<3>", "env command command env"),
    ("document has no arguments", "\\begin{document}{x}\nBody.", "<0>{x}\nBody.", "env"),
    ("title of begin with a space stays visible", "\\begin{theorem}[Cauchy's theorem]\nText.",
     "<0>[Cauchy's theorem]\nText.", "env", ["\\begin{theorem}"]),
    ("title of begin without a space is hidden", "\\begin{theorem}[Name] Text", "<0> Text", "env",
     ["\\begin{theorem}[Name]"]),
    ("figure placement is hidden", "\\begin{figure}[t]\nText.", "<0>\nText.", "env", ["\\begin{figure}[t]"]),
    ("long placement is hidden", "\\begin{figure}[htbp]\nText.", "<0>\nText.", "env", ["\\begin{figure}[htbp]"]),
    ("key and value options are hidden", "\\begin{itemize}[leftmargin=*]\n\\item x", "<0>\n<1> x", "env command",
     ["\\begin{itemize}[leftmargin=*]", "\\item"]),
    ("width option is hidden", "\\begin{minipage}[width=3cm]\nText.", "<0>\nText.", "env"),
    ("subfigure arguments are hidden", "\\begin{subfigure}[b]{0.45\\textwidth}\nText.", "<0>\nText.", "env",
     ["\\begin{subfigure}[b]{0.45\\textwidth}"]),
    ("minipage argument is hidden", "\\begin{minipage}{0.5\\textwidth}\nText.", "<0>\nText.", "env"),
    ("multicols argument is hidden", "\\begin{multicols}{2}\nText.", "<0>\nText.", "env", ["\\begin{multicols}{2}"]),
    ("wrapfigure arguments are hidden", "\\begin{wrapfigure}{r}{0.5\\textwidth}\nText.", "<0>\nText.", "env"),
    ("bracket before the braces is hidden", "\\begin{wrapfigure}[12]{r}{5cm}\nText.", "<0>\nText.", "env"),
    ("bibliography width is hidden", "\\begin{thebibliography}{9}\n\\bibitem{a} Text.", "<0>\n<1> Text.",
     "env command", ["\\begin{thebibliography}{9}", "\\bibitem{a}"]),
    ("argument with nested braces is hidden", "\\begin{minipage}{\\dimexpr 0.5\\textwidth-{2pt}}\nText.", "<0>\nText.", "env"),
    ("brace group that closes on a later line hides the first line only", "\\begin{figure}[t]{\nWe delve.\n\nNew para.\n}",
     "<0>\nWe delve.\n\nNew para.\n}", "env", ["\\begin{figure}[t]{"]),
    ("bracket group that spans lines stays visible", "\\begin{x}[a\nb] Text", "<0>[a\nb] Text", "env"),
    ("bracket group with a bracket inside and no space is hidden", "\\begin{x}[a[b]c] Text", "<0> Text", "env",
     ["\\begin{x}[a[b]c]"]),
    ("bracket group with a braced bracket inside is hidden",
     "\\begin{tcolorbox}[title={Fig[1]},colback=red]Overall, we delve.", "<0>Overall, we delve.", "env",
     ["\\begin{tcolorbox}[title={Fig[1]},colback=red]"]),
    ("bracket group with a bracket in a brace group is hidden", "\\begin{enumerate}[label={[\\arabic*]}]\n\\item x",
     "<0>\n<1> x", "env command", ["\\begin{enumerate}[label={[\\arabic*]}]", "\\item"]),
    ("percent sign in a bracket group starts a comment", "\\begin{x}[%]We delve.\nNext line.",
     "<0>[<1>\nNext line.", "env comment", ["\\begin{x}", "%]We delve."]),
    ("escaped bracket does not close a bracket group", "\\begin{x}[a\\]b]We delve.", "<0>We delve.", "env",
     ["\\begin{x}[a\\]b]"]),
    ("bracket group with a bracket inside and a space stays visible", "\\begin{x}[a [b] c] Text",
     "<0>[a [b] c] Text", "env"),
    ("bracket group with a tab stays visible", "\\begin{x}[a\tb] Text", "<0>[a\tb] Text", "env"),
    ("bracket group with no balanced close stays visible", "\\begin{x}[a}b] Text", "<0>[a}b] Text", "env"),
    ("bracket group in a brace group closes inside it", "\\begin{x}[label={[a]}] Text", "<0> Text", "env",
     ["\\begin{x}[label={[a]}]"]),
    ("brace group on the next line stays visible", "\\begin{minipage}\n{abc} Text", "<0>\n{abc} Text", "env"),
    ("brace group after a blank stays visible", "\\begin{minipage} {abc} Text", "<0> {abc} Text", "env"),
    ("unbalanced argument hides the rest of the line only", "\\begin{minipage}{0.5\nText after.", "<0>\nText after.", "env",
     ["\\begin{minipage}{0.5"]),
    ("arguments end inside a prose argument", "\\textbf{a \\begin{x}{1} b}", "<0>a <1> b<2>", "command env command",
     ["\\textbf{", "\\begin{x}{1}", "}"]),
    ("end token has no argument", "\\end{figure}[t] Text", "<0>[t] Text", "env", ["\\end{figure}"]),
    ("subequations keep their tokens", "\\begin{subequations}\n\\begin{equation}\nx\n\\end{equation}\n\\end{subequations}",
     "<0>\n<1>\n<2>", "env env env"),
    # Rule 6: commands with a prose argument.
    ("section", "\\section{Results}\nText.", "<0>Results<1>\nText.", "command command",
     ["\\section{", "}"]),
    ("starred section", "\\section*{Methods}", "<0>Methods<1>", "command command"),
    ("caption with short form", "\\caption[Short]{Long text.}", "<0>Long text.<1>", "command command",
     ["\\caption[Short]{", "}"]),
    ("nested prose commands", "\\textbf{bold \\emph{nested} word}", "<0>bold <1>nested<2> word<3>",
     "command command command command"),
    ("space before the brace", "\\section {Spaced}", "<0>Spaced<1>", "command command"),
    ("unbalanced prose command", "\\section{Intro\nMore text.", "<0>\nMore text.", "command", ["\\section{Intro"]),
    ("math inside a prose argument", "\\section{On $x$ here}", "<0>On <1> here<2>", "command math command"),
    ("prose command without a brace", "\\emph word", "<0> word", "command"),
    ("cite inside a prose argument", "\\textbf{see \\cite{a}}", "<0>see <1><2>", "command cite command"),
    ("closing brace after a comment", "\\emph{a % }\nb} c", "<0>a <1>\nb<2> c", "command comment command"),
    ("interval bracket inside a prose argument", "\\textbf{a $[0,1)$ b} c", "<0>a <1> b<2> c",
     "command math command"),
    # Rule 7: cite, ref, url and href.
    ("cite", "Text \\cite{a,b} more", "Text <0> more", "cite", ["\\cite{a,b}"]),
    ("cite with optional arguments", "\\citep[see][p.~3]{key}.", "<0>.", "cite", ["\\citep[see][p.~3]{key}"]),
    ("two cites with a tie", "\\cite{a}~\\cite{b}", "<0>~<1>", "cite cite"),
    ("label", "\\label{sec:one}", "<0>", "ref"),
    ("url command", "\\url{http://x.org/a_b} here", "<0> here", "url"),
    ("href hides its text", "\\href{http://x.org}{link text} done", "<0> done", "url",
     ["\\href{http://x.org}{link text}"]),
    # Rule 8: every other command.
    ("textcolor hides its word", "\\textcolor{red}{word} here", "<0> here", "command"),
    ("vspace", "\\vspace{1em} text", "<0> text", "command"),
    ("newcommand", "\\newcommand{\\x}[1]{#1} done", "<0> done", "command"),
    ("unknown macro", "\\unknownmacro{some text} after", "<0> after", "command"),
    ("spaces between arguments", "\\foo [a] {b} c", "<0> c", "command"),
    ("control symbols", "a \\& b \\, c \\\\ d \\ e", "a <0> b <1> c <2> d <3>e",
     "command command command command", ["\\&", "\\,", "\\\\", "\\ "]),
    ("command without arguments", "\\item text", "<0> text", "command"),
    ("newline between command and brace", "\\centering\n{\\small x}", "<0>\n{<1> x}", "command command"),
    ("starred command", "\\foo*{x} y", "<0> y", "command"),
    ("lone backslash at the end", "a \\", "a <0>", "command"),
    ("control symbol before a newline", "a \\\nb", "a <0>\nb", "command", ["\\"]),
    ("control symbol before a lone CR", "a \\\rb", "a <0>\rb", "command", ["\\"]),
    # Rule 9: unbalanced braces.
    ("unclosed brace to line end", "\\foo{bar\nnext line\n", "<0>\nnext line\n", "command"),
    ("unclosed brace at the end", "\\foo{bar", "<0>", "command"),
    ("balanced then unbalanced", "\\foo{a}{b\nline2", "<0>\nline2", "command", ["\\foo{a}{b"]),
    ("unclosed cite", "\\cite{a\nmore", "<0>\nmore", "cite"),
    ("stray closing brace", "a } b ] c", "a } b ] c", ""),
    ("brace in a comment is ignored", "\\foo{a % }\n b} c", "<0> c", "command"),
    ("escaped brace inside an argument", "\\foo{a \\} b} c", "<0> c", "command"),
    # Rule 10: the tie.
    ("tie stays", "a~b", "a~b", ""),
    ("tie before ref", "Fig.~\\ref{x}", "Fig.~<0>", "ref"),
    # Inline verbatim, URLs, and what LaTeX does not mask.
    ("verb with a brace", "\\verb|a{b| and $y$", "<0> and <1>", "code math"),
    ("verb without a closing bar stops at the line end", "\\verb|abc\nnext | $x$", "<0>\nnext | <1>", "code math",
     ["\\verb|abc", "$x$"]),
    ("urls in latex text", "See https://example.org/a_b, and 10.1234/abc.5 or mail me@example.org.",
     "See <0>, and <1> or mail <2>.", "url url url"),
    ("plain citations stay in latex", "(Smith et al., 2020) and [12]", "(Smith et al., 2020) and [12]", ""),
]

MARKDOWN_CASES = [
    ("front matter", "---\ntitle: Made up\n---\nText.\n", "<0>\nText.\n", "markup", ["---\ntitle: Made up\n---"]),
    ("front matter with CRLF", "---\r\ntitle: x\r\n---\r\nText\r\n", "<0>\r\nText\r\n", "markup"),
    ("unclosed front matter", "---\ntext\n", "---\ntext\n", ""),
    ("rule not on line one", "Text\n---\nmore\n---\n", "Text\n---\nmore\n---\n", ""),
    ("backtick fence", "Before\n\n```python\nx = 1\n```\n\nAfter\n", "Before\n\n<0>\n\nAfter\n", "code",
     ["```python\nx = 1\n```"]),
    ("tilde fence", "~~~\ncode\n~~~\nAfter", "<0>\nAfter", "code"),
    ("unclosed fence", "Text\n```\ncode\nmore\n", "Text\n<0>", "code"),
    ("longer closing fence", "````\na\n```\n# b\n````\nAfter\n", "<0>\nAfter\n", "code"),
    ("fence with CRLF", "a\r\n```\r\nx\r\n```\r\nb\r\n", "a\r\n<0>\r\nb\r\n", "code"),
    ("fence under a list item with a blank line inside",
     "1. Step\n\n    ```sh\n    run it\n\n    again\n    ```\n", "<0> Step\n\n    <1>\n", "markup code",
     ["1.", "```sh\n    run it\n\n    again\n    ```"]),
    ("tab-indented fence", "- Step\n\n\t```sh\n\trun it\n\t```\ntext", "<0> Step\n\n\t<1>\ntext", "markup code"),
    ("top-level fence indented four spaces", "Text\n\n    ```\n    code\n    ```\nAfter", "Text\n\n    <0>\nAfter", "code"),
    ("closing fence indented deeper than the opening", "- a\n\n  ```\n  x\n      ```\nAfter",
     "<0> a\n\n  <1>\nAfter", "markup code"),
    ("closing fence indented less than the opening", "    ```\nx\n```\nAfter", "    <0>\nAfter", "code"),
    ("inline code", "Use `x = 1` here.", "Use <0> here.", "code", ["`x = 1`"]),
    ("double backtick code", "A ``a ` b`` c", "A <0> c", "code"),
    ("unclosed backtick", "a ` b", "a ` b", ""),
    ("escaped backticks", "\\`x\\` y", "\\`x\\` y", ""),
    ("link target", "See [the paper](http://x.org/a_(b)) now.", "See [the paper]<0> now.", "url",
     ["(http://x.org/a_(b))"]),
    ("image path keeps the alt text", "![A cell](img/cell.png) text", "![A cell]<0> text", "url"),
    ("unclosed link target", "[a](b c", "[a](b c", ""),
    ("html tags", "a <b>bold</b> c<br/>", "a <0>bold<1> c<2>", "markup markup markup"),
    ("html comment", "<!-- hidden\nmulti -->after", "<0>after", "markup"),
    ("less than is not a tag", "a < b and c > d", "a < b and c > d", ""),
    ("inline math", "Let $x^2$ be.", "Let <0> be.", "math"),
    ("display math", "$$\na\n$$\ntext", "<0>\ntext", "math"),
    ("dollar amounts are not math", "costs $5 and $10 each", "costs $5 and $10 each", ""),
    ("escaped dollars", "\\$5 and \\$6", "\\$5 and \\$6", ""),
    ("reference definition", "[1]: http://x.org \"T\"\ntext", "<0>\ntext", "markup"),
    ("footnote definition is prose", "[^1]: Note text.", "[^1]: Note text.", ""),
    ("table rows", "| a | b |\n|---|---|\ntext\n", "<0>\n<1>\ntext\n", "markup markup"),
    ("table row indented by spaces", "  | a | b |\ntext", "  <0>\ntext", "markup", ["| a | b |"]),
    ("list marker with a parenthesis", "2) item\n", "<0> item\n", "markup", ["2)"]),
    ("heading marker", "## Title\nText\n", "<0>Title\nText\n", "markup", ["## "]),
    ("hashtag is not a heading", "#hashtag here", "#hashtag here", ""),
    ("empty heading", "#\ntext", "<0>\ntext", "markup"),
    ("list markers", "- item\n* item\n+ item\n1. item\n", "<0> item\n<1> item\n<2> item\n<3> item\n",
     "markup markup markup markup", ["-", "*", "+", "1."]),
    ("emphasis is not a list marker", "**bold** x\n-5 degrees\n", "**bold** x\n-5 degrees\n", ""),
    ("numeric and author-year citations",
     "Text [12] and [3-5] and [1, 4, 7] and (Smith et al., 2020).",
     "Text <0> and <1> and <2> and <3>.", "cite cite cite cite"),
    ("pandoc citation", "Seen in cells [@smith20].", "Seen in cells <0>.", "cite", ["[@smith20]"]),
    ("pandoc citations in one bracket", "Seen [@a; @b:c-d] here.", "Seen <0> here.", "cite", ["[@a; @b:c-d]"]),
    ("pandoc citation with a minus sign", "Seen [-@smith20].", "Seen <0>.", "cite", ["[-@smith20]"]),
    ("pandoc citation with a locator", "Seen [@a, p. 3].", "Seen <0>.", "cite", ["[@a, p. 3]"]),
    ("pandoc citation with a lead word", "Seen [see @a].", "Seen <0>.", "cite", ["[see @a]"]),
    ("pandoc citations with a lead word in the second", "Seen [@a; see @b].", "Seen <0>.", "cite", ["[@a; see @b]"]),
    ("pandoc citations without a space after the semicolon", "Seen [@a;@b].", "Seen <0>.", "cite"),
    ("link text with an at sign is a cite", "See [@user](https://example.org/user).", "See <0><1>.", "cite url",
     ["[@user]", "(https://example.org/user)"]),
    ("pandoc group ends at the first bracket", "Seen [@a] and [b] here.", "Seen <0> and [b] here.", "cite", ["[@a]"]),
    ("not a pandoc citation: bare at sign", "Seen [@] and [a@b] and @c.", "Seen [@] and [a@b] and @c.", ""),
    ("not a pandoc citation: at sign inside a word", "Seen [x a@b.c] and [a@b].", "Seen [x a@b.c] and [a@b].", ""),
    ("url in markdown", "See https://example.org/a_b.", "See <0>.", "url"),
    ("code hides what follows inside it", "`[12] $x$` and [3]", "<0> and <1>", "code cite"),
]

TEXT_CASES = [
    ("numeric citation", "Seen in cells [12].", "Seen in cells <0>.", "cite"),
    ("range citation", "See [3-5].", "See <0>.", "cite"),
    ("list citation", "See [1, 4, 7].", "See <0>.", "cite"),
    ("author-year et al", "Large (Smith et al., 2020) effect.", "Large <0> effect.", "cite"),
    ("two authors and two items", "(Smith and Jones, 2019; Lee, 2021)", "<0>", "cite"),
    ("author year without comma", "(Lee 2021)", "<0>", "cite"),
    ("the pandoc form is a Markdown rule", "Seen [@a] and [see @b].", "Seen [@a] and [see @b].", ""),
    ("not a citation: p value", "(p < 0.05)", "(p < 0.05)", ""),
    ("not a citation: n", "(n = 12)", "(n = 12)", ""),
    ("not a citation: see figure", "(see Fig. 2)", "(see Fig. 2)", ""),
    ("not a citation: figure", "(Fig. 2)", "(Fig. 2)", ""),
    ("not a citation: year alone", "(2020)", "(2020)", ""),
    ("url", "Go to https://example.org/x?a=1&b=2.", "Go to <0>.", "url"),
    ("url in parentheses", "(see https://example.org/x).", "(see <0>).", "url"),
    ("doi", "doi 10.1234/abc.def5 ends", "doi <0> ends", "url"),
    ("email", "Write to me@example.org today.", "Write to <0> today.", "url"),
    ("doi inside a url is one span", "see https://doi.org/10.1234/abc.5 now", "see <0> now", "url"),
    ("not an email", "a @ b and x@y", "a @ b and x@y", ""),
    ("domain must end in two letters", "a@b.c and a@b.1 and x@y.12", "a@b.c and a@b.1 and x@y.12", ""),
    ("two-letter domain is an email", "mail a@b.co now", "mail <0> now", "url"),
    ("balanced parenthesis stays in a url", "see https://x.org/a_(b) now", "see <0> now", "url"),
    ("brackets that are not citations", "see [a] and [] and [12345] and [1,]", "see [a] and [] and [12345] and [1,]", ""),
    ("years out of range are not citations", "(Smith 1492) and (Smith 2101)", "(Smith 1492) and (Smith 2101)", ""),
    ("latex syntax is plain text", "\\section{X} $y$ % c", "\\section{X} $y$ % c", ""),
    ("markdown syntax is plain text", "# Title\n- item\n`code`", "# Title\n- item\n`code`", ""),
]

SAMPLE_LATEX = (
    "\\documentclass{article}\n\\usepackage{amsmath}\n% preamble note\n\\begin{document}\n"
    "\\section{Zorbian moss}\nThe moss grew 3.5 cm \\cite{lee2020,moss2021} in a week.\n"
    "Let $g(x)=x^2$ be the growth rate, and\n\\[ g'(x)=2x \\]\nholds. % a note\n\n"
    "\\begin{figure}[t]\n\\includegraphics[width=3cm]{moss.png}\n"
    "\\caption{Moss in the lab, see Fig.~\\ref{fig:moss}.}\n\\label{fig:moss}\n\\end{figure}\n\n"
    "\\begin{tabular}{ll}\nA & B \\\\\n1 & 2 \\\\\n\\end{tabular}\n\n"
    "Costs were \\$5 per plant.\n\\end{document}\n")
SAMPLE_MARKDOWN = (
    "---\ntitle: Zorbian moss\n---\n# Moss growth\n\nThe moss grew 3.5 cm [1, 2] in a week "
    "(Lee et al., 2020).\n\n- Plants grew `fast`.\n- See [the notes](http://example.org/notes_(1)).\n\n"
    "| plant | cm |\n|---|---|\n| moss | 3.5 |\n\n```python\nprint(1)\n```\n\n$$\ng(x)=x^2\n$$\n\n"
    "<!-- internal -->\nCosts were $5 per plant. See <b>this</b>.\n\n[1]: http://example.org\n")
SAMPLE_TEXT = (
    "The moss grew 3.5 cm [1, 2] in a week (Lee et al., 2020).\nMail me@example.org or see "
    "https://example.org/moss.\n\nCosts were $5 per plant; p < 0.05 (see Fig. 2).\n")


class Invariants(unittest.TestCase):
    def check_invariants(self, masked, text):
        end = 0
        for s in masked.spans:
            self.assertIn(s.kind, pm.KINDS)
            self.assertLess(s.start, s.end)
            self.assertGreaterEqual(s.start, end)
            self.assertLessEqual(s.end, len(text))
            self.assertFalse(text[s.start - 1:s.start + 1] == "\r\n" and s.start > 0)
            self.assertFalse(text[s.end - 1:s.end + 1] == "\r\n")
            end = s.end
        self.assertEqual(masked.original, text)
        self.assertEqual(pm.unmask(masked), text)

    def check_offset_map(self, masked):
        om = pm.offset_map(masked)
        self.assertEqual(len(om), len(masked.text) + 1)
        self.assertEqual(om[-1], len(masked.original))
        k, inside = -1, False
        for i, ch in enumerate(masked.text):
            if ch == OPEN:
                k, inside = k + 1, True
            if inside:
                self.assertEqual(om[i], masked.spans[k].start)
            else:
                self.assertEqual(masked.original[om[i]], ch)
            if ch == CLOSE:
                inside = False
                self.assertEqual(om[i + 1], masked.spans[k].end)

    def test_round_trip_samples(self):
        for fmt, text in (("latex", SAMPLE_LATEX), ("markdown", SAMPLE_MARKDOWN), ("text", SAMPLE_TEXT)):
            for variant in (text, text.replace("\n", "\r\n"), ""):
                with self.subTest(fmt=fmt, crlf="\r" in variant, empty=variant == ""):
                    m = pm.mask(variant, fmt)
                    self.check_invariants(m, variant)
                    self.check_offset_map(m)

    def test_samples_mask_something_in_every_format(self):
        self.assertEqual(len(pm.mask("", "latex").spans), 0)
        self.assertEqual(pm.mask("", "markdown").text, "")
        kinds = {fmt: set(s.kind for s in pm.mask(t, fmt).spans)
                 for fmt, t in (("latex", SAMPLE_LATEX), ("markdown", SAMPLE_MARKDOWN), ("text", SAMPLE_TEXT))}
        self.assertEqual(kinds["latex"], {"env", "comment", "math", "cite", "ref", "command"})
        self.assertEqual(kinds["markdown"], {"markup", "cite", "code", "math", "url"})
        self.assertEqual(kinds["text"], {"cite", "url"})

    def check_string(self, text, fmt):
        m = pm.mask(text, fmt)
        self.check_invariants(m, text)
        self.check_offset_map(m)
        raw = pm._raw_spans(text, fmt)
        self.assertEqual(raw, sorted(raw))
        self.assertTrue(all(a.end <= b.start for a, b in zip(raw, raw[1:])), (fmt, text))

    def test_random_strings(self):
        alphabet = list("\\{}$%[]()`#-*|~<>!.,;") + list("abcxyzEMT019") + [" ", "\n", OPEN, CLOSE]
        for fmt in FORMATS:
            rng = random.Random(20261023)
            for k in range(3000):
                self.check_string("".join(rng.choice(alphabet) for _ in range(rng.randint(0, 40))), fmt)

    def test_random_strings_with_crlf_nul_and_surrogates(self):
        alphabet = (list("\\{}$%[]()`#-*|~<>!.,;") + list("abc019 ") +
                    ["\n", "\r\n", "\r", "\x00", "\ud800", OPEN, CLOSE])
        for fmt in FORMATS:
            rng = random.Random(7)
            for k in range(1500):
                self.check_string("".join(rng.choice(alphabet) for _ in range(rng.randint(0, 40))), fmt)

    def test_random_token_strings(self):
        tokens = ["\\begin{tabular}", "\\end{tabular}", "\\begin{equation}", "\\end{equation}", "\\verb|",
                  "\\cite{a}", "\\section{", "}", "$", "$$", "\\(", "\\)", "\\[", "\\]", "%", "\\%", "\\\\", "~",
                  "http://x.org", "[1,", "](", "<!--", "-->", "`", "```", "(Smith, 2020)", "\n", "\r\n", "\n\n",
                  "moss", "grew", "the", "cells", " ", OPEN]
        for fmt in FORMATS:
            rng = random.Random(1023)
            for k in range(1500):
                self.check_string("".join(rng.choice(tokens) for _ in range(rng.randint(0, 25))), fmt)

    def test_unmask_uses_the_placeholders(self):
        m = pm.mask("a $x$ b", "latex")
        self.assertEqual(m.text, "a " + OPEN + "0" + CLOSE + " b")
        broken = pm.Masked("a " + OPEN + "0" + CLOSE + " c", m.spans, m.original)
        self.assertEqual(pm.unmask(broken), "a $x$ c")


class Seeded(unittest.TestCase):
    def run_cases(self, fmt, cases):
        for case in cases:
            label, src, shown, kinds = case[:4]
            with self.subTest(label=label):
                m = pm.mask(src, fmt)
                self.assertEqual(show(m), shown)
                self.assertEqual([s.kind for s in m.spans], kinds.split())
                if len(case) > 4:
                    self.assertEqual(pieces(m), case[4])
                self.assertEqual(pm.unmask(m), src)

    def test_latex(self):
        self.run_cases("latex", LATEX_CASES)

    def test_markdown(self):
        self.run_cases("markdown", MARKDOWN_CASES)

    def test_text(self):
        self.run_cases("text", TEXT_CASES)

    def test_whole_environments_every_name(self):
        names = ("verbatim lstlisting minted tikzpicture tabular tabularx longtable equation align gather "
                 "multline eqnarray displaymath math split alignat flalign dmath IEEEeqnarray empheq").split()
        for name in names:
            for star in ("", "*"):
                with self.subTest(name=name + star):
                    m = pm.mask("a \\begin{%s%s}x\\end{%s%s} b" % (name, star, name, star), "latex")
                    self.assertEqual(show(m), "a <0> b")
                    self.assertEqual([s.kind for s in m.spans], ["env"])

    def test_prose_argument_commands_every_name(self):
        for name in pm.PROSE_ARG_COMMANDS:
            with self.subTest(name=name):
                m = pm.mask("\\%s{x}" % name, "latex")
                self.assertEqual(show(m), "<0>x<1>")
                self.assertEqual(pieces(m), ["\\%s{" % name, "}"])
        self.assertEqual(len(pm.PROSE_ARG_COMMANDS), 15)

    def test_cite_and_ref_commands_every_name(self):
        for name in pm.CITE_COMMANDS:
            with self.subTest(name=name):
                m = pm.mask("a \\%s{k} b" % name, "latex")
                self.assertEqual((show(m), [s.kind for s in m.spans]), ("a <0> b", ["cite"]))
        for name in pm.REF_COMMANDS:
            with self.subTest(name=name):
                m = pm.mask("a \\%s{k} b" % name, "latex")
                self.assertEqual((show(m), [s.kind for s in m.spans]), ("a <0> b", ["ref"]))
        self.assertEqual((len(pm.CITE_COMMANDS), len(pm.REF_COMMANDS)), (24, 7))
        names = ("citealp citealt Citep Citet Citealp footcite supercite citeyearpar citenum cites parencites "
                 "textcites Parencite Textcite citetitle").split()
        for name in names:
            self.assertIn(name, pm.CITE_COMMANDS)

    def test_placeholder_characters_in_the_input(self):
        for fmt in FORMATS:
            for ch in (OPEN, CLOSE):
                with self.subTest(fmt=fmt, char=hex(ord(ch))):
                    m = pm.mask("a" + ch + "b", fmt)
                    self.assertEqual(show(m), "a<0>b")
                    self.assertEqual([(s.kind, pm.piece(m, 0)) for s in m.spans], [("markup", ch)])
        m = pm.mask(OPEN + "7" + CLOSE, "text")
        self.assertEqual(show(m), "<0>7<1>")
        self.assertEqual(pm.unmask(m), OPEN + "7" + CLOSE)
        m = pm.mask("% " + OPEN + "\nx", "latex")
        self.assertEqual(show(m), "<0>\nx")

    def test_placeholder_format(self):
        m = pm.mask("$x$ and $y$", "latex")
        self.assertEqual(m.text, OPEN + "0" + CLOSE + " and " + OPEN + "1" + CLOSE)

    def test_crlf_never_splits_a_span(self):
        m = pm.mask("a \\\r\nb", "latex")
        self.assertEqual(show(m), "a <0>\r\nb")
        self.assertEqual(pieces(m), ["\\"])

    def test_piece_and_offset_map(self):
        m = pm.mask("ab \\cite{x} cd", "latex")
        self.assertEqual(pm.piece(m, 0), "\\cite{x}")
        om = pm.offset_map(m)
        self.assertEqual(om[:4], [0, 1, 2, 3])
        self.assertEqual(om[3:6], [3, 3, 3])
        self.assertEqual(om[6], 11)
        self.assertEqual(om[-1], 14)

    def test_normalize_repairs_bad_spans(self):
        span = pm.Span
        text = "ab\r\ncd" + "x" * 10
        cases = [
            ([span(5, 6, "math"), span(0, 2, "env")], [span(0, 2, "env"), span(5, 6, "math")]),
            ([span(0, 5, "env"), span(3, 8, "math")], [span(0, 5, "env"), span(5, 8, "math")]),
            ([span(0, 5, "env"), span(1, 2, "math")], [span(0, 5, "env")]),
            ([span(0, 3, "env")], [span(0, 2, "env")]),
            ([span(3, 6, "env")], [span(4, 6, "env")]),
            ([span(3, 3, "env"), span(7, 7, "math")], []),
        ]
        for bad, good in cases:
            with self.subTest(bad=bad):
                self.assertEqual(pm._normalize(bad, text), good)

    def test_failed_searches_are_not_repeated(self):
        # This test patches two functions of prose_mask_md by name: _link_target_end and
        # _markdown_math_close. If you rename either one, update this test.
        import prose_mask_md
        counts = {}
        for name, source in (("_link_target_end", "](" * 1000), ("_markdown_math_close", "$a " * 1000)):
            original = getattr(prose_mask_md, name)
            counts[name] = 0

            def counting(*args, _original=original, _name=name):
                counts[_name] += 1
                return _original(*args)

            setattr(prose_mask_md, name, counting)
            try:
                pm.mask(source, "markdown")
            finally:
                setattr(prose_mask_md, name, original)
        self.assertEqual(counts, {"_link_target_end": 1, "_markdown_math_close": 1})

    def test_unknown_format_raises(self):
        with self.assertRaises(ValueError):
            pm.mask("x", "rtf")

    def test_odd_characters_do_not_crash(self):
        for fmt in FORMATS:
            for text in ("a\x00b $x$ \x00", "lone \ud800 surrogate $y$", "\\\x00", "x" * 5000 + "\n" * 3):
                m = pm.mask(text, fmt)
                self.assertEqual(pm.unmask(m), text)


class Packaging(unittest.TestCase):
    def test_loads_by_file_path_with_only_the_scripts_folder_on_the_path(self):
        scripts = os.path.join(os.path.dirname(HERE), "scripts")
        code = (
            "import sys\n"
            "sys.path.insert(0, %r)\n"
            "from importlib.machinery import SourceFileLoader\n"
            "mod = SourceFileLoader('masker_by_path', %r).load_module()\n"
            "m = mod.mask('# Title\\n\\nUse `x` here [1].\\n', 'markdown')\n"
            "print(m.text.count('\\ue000'), 'prose_mask' in sys.modules)\n"
        ) % (scripts, os.path.join(scripts, "prose_mask.py"))
        result = subprocess.run([sys.executable, "-I", "-B", "-c", code],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "3 False")


class DetectFormat(unittest.TestCase):
    def test_extensions(self):
        for path, fmt in (("a.tex", "latex"), ("a.sty", "latex"), ("a.cls", "latex"), ("a.bib", "latex"),
                          ("dir/A.TEX", "latex"), ("a.md", "markdown"), ("a.markdown", "markdown"),
                          ("B.MD", "markdown"), ("a.txt", "text"), ("a", "text"), ("a.rst", "text"),
                          ("a.tex.bak", "text"), ("notes.md/readme", "text")):
            with self.subTest(path=path):
                self.assertEqual(pm.detect_format(path), fmt)


class PandocCites(unittest.TestCase):
    # The regex that the masker used before the scan. The scan must find the same groups.
    OLD = re.compile(r"\[[^\[\]\r\n]*?(?<![A-Za-z0-9_])-?@[A-Za-z0-9_][^\[\]\r\n]*\]")
    PIECES = ["[", "]", "@", "-", "a", "B7", "_", " ", ";", "\n", "\r\n", ",", "p. 3", "(", "x@y"]

    def test_the_scan_equals_the_old_regex_on_random_strings(self):
        rng = random.Random(5)
        for _ in range(3000):
            text = "".join(rng.choice(self.PIECES) for _ in range(rng.randint(0, 30)))
            expected = [(m.start(), m.end(), "cite") for m in self.OLD.finditer(text)]
            self.assertEqual(pm._pandoc_cites(text), expected, repr(text))

    def test_the_scan_on_simple_strings(self):
        self.assertEqual(pm._pandoc_cites("a [@b] c [see @d; @e] f"), [(2, 6, "cite"), (9, 21, "cite")])
        self.assertEqual(pm._pandoc_cites("[@a [@b]"), [(4, 8, "cite")])
        self.assertEqual(pm._pandoc_cites("[x\n@a]"), [])
        self.assertEqual(pm._pandoc_cites("no brackets"), [])


class Speed(unittest.TestCase):
    """Long inputs must finish fast. The bound is generous; a quadratic scan misses it by far."""

    def timed(self, fmt, text):
        start = time.time()
        m = pm.mask(text, fmt)
        elapsed = time.time() - start
        self.assertEqual(pm.unmask(m), text)
        return elapsed

    def test_long_line_of_open_braces(self):
        text = "{" * 200000
        self.assertLess(self.timed("latex", text), 2)
        self.assertLess(self.timed("latex", "\\foo" + text), 2)
        self.assertLess(self.timed("latex", "\\section" + text), 2)

    def test_long_pathological_lines(self):
        pieces_ = ["\\a{", "\\a[", "\\a{b} ", "\\begin{x}", "\\verb|", "\\begin{tabular}", "$", "$ a ", "\\(", "$$",
                   "%", "\\\\", "\\", "[", "]", "[1,", "(", "(A ", "`", "``", "](", "](a ", "<", "<a ", "<!--",
                   "a@", "http://", "https://a.b/(", "10.1234/", "~", "- ", "| ", "# ", "$a ", "((", "\\a\\a ",
                   "\\textbf{", "\\cite{", "{", "}", "\n\n$", "\r\n"]
        for piece_ in pieces_:
            text = piece_ * max(1, 60000 // len(piece_))
            for fmt in FORMATS:
                with self.subTest(piece=piece_, fmt=fmt):
                    self.assertLess(self.timed(fmt, text), 10)

    def test_pandoc_brackets_take_linear_time(self):
        for label, text in (("one open bracket", "[" + "@a " * 40000 + "\n"),
                            ("many open brackets", "[@a " * 40000 + "\n"),
                            ("closed groups", "[x @a] " * 40000 + "\n"),
                            ("one long group", "[" + "@a " * 40000 + "]\n"),
                            ("groups without a key", "[x a] " * 40000 + "\n")):
            with self.subTest(label=label):
                self.assertLess(self.timed("markdown", text), 5)

    def test_nested_environment_arguments_take_linear_time(self):
        for label, text in (("nested brackets", "\\begin{x}[" * 20000 + " " + "]" * 20000),
                            ("nested braces", "\\begin{x}{" * 20000 + "}" * 20000),
                            ("unclosed brackets", "\\begin{x}[a\n" * 20000),
                            ("unclosed braces", "\\begin{x}{a\n" * 20000),
                            ("brackets without a blank", "\\begin{x}[a]" * 20000),
                            ("many brackets", "\\begin{x}" + "[" * 100000),
                            ("many open environments", "\\begin{x}[" * 100000)):
            with self.subTest(label=label):
                self.assertLess(self.timed("latex", text), 5)

    def test_many_unclosed_lines(self):
        for line in ("\\a{\n", "\\a[\n", "$x\n", "`x\n", "[a](b\n", "<!-- x\n", "\\begin{align}\n"):
            text = line * 30000
            for fmt in ("latex", "markdown"):
                with self.subTest(line=line, fmt=fmt):
                    self.assertLess(self.timed(fmt, text), 10)


if __name__ == "__main__":
    unittest.main()
