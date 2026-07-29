import re

_ANSI = re.compile(r"\x1b\[[0-9;]*m")


def _fg(hex_color):
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return "\x1b[38;2;%d;%d;%dm" % (r, g, b)


def emit_plain(line, pal, color):
    """Colour spans. NEVER compute or adjust geometry here."""
    out = []
    for span in line:
        if color and span.style and span.style in pal:
            out.append(_fg(pal[span.style]) + span.text + "\x1b[0m")
        else:
            out.append(span.text)
    return "".join(out)


def strip_ansi(s):
    return _ANSI.sub("", s)
