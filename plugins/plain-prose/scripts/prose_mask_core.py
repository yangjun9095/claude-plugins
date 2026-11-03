"""Shared pieces of the masker: the span type and the scan helpers.

Both prose_mask.py (LaTeX, API) and prose_mask_md.py (Markdown) import this file.
It imports nothing from them.
"""
import re
from collections import namedtuple

Span = namedtuple("Span", "start end kind")

# The placeholder of span number i is OPEN + str(i) + CLOSE. Both ends are private-use characters.
OPEN, CLOSE = "\ue000", "\ue001"

EOL = re.compile(r"[\r\n]")
PARA_BREAK = re.compile(r"\r?\n[ \t\r]*\n")
ESCAPE_OR_DOLLAR = re.compile(r"\\[\s\S]|\$")
_BLANKS = re.compile(r"[ \t]*")


class NextMatch(object):
    """Offset of the first match of a pattern at or after a position, or the end of the text.

    It remembers the last stretch, so a run of calls inside one stretch costs one search.
    """

    def __init__(self, pattern, text):
        self.pattern, self.text, self.low, self.high = pattern, text, 1, 0

    def __call__(self, i):
        if not self.low <= i <= self.high:
            m = self.pattern.search(self.text, i)
            self.low, self.high = i, (m.start() if m else len(self.text))
        return self.high


def skip_blanks(text, i):
    """Offset of the first character at or after i that is not a space or a tab."""
    return _BLANKS.match(text, i).end()
