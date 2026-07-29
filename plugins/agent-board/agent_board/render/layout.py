import collections
import unicodedata

from agent_board.render.glyphs import table as glyph_table

Span = collections.namedtuple("Span", "text style")

GUT = 2
CARD_W_PREF = 58

COLUMN_ORDER = ("ACTIVE", "IN REVIEW", "BLOCKED", "PARKED", "DONE")


def cw(s):
    """Display width. Class W and F occupy two cells."""
    return sum(2 if unicodedata.east_asian_width(c) in ("W", "F") else 1 for c in s)


def clip(s, width, ell):
    s = s or ""
    if cw(s) <= width:
        return s
    budget = width - cw(ell)
    if budget <= 0:
        return ell[:width]
    out, used = [], 0
    for ch in s:
        w = cw(ch)
        if used + w > budget:
            break
        out.append(ch)
        used += w
    return "".join(out) + ell


def pad(s, width):
    return s + " " * max(0, width - cw(s))


def col_widths(width):
    ncols = max(1, (width + GUT) // (CARD_W_PREF + GUT))
    avail = width - GUT * (ncols - 1)
    cardw = avail // ncols
    rem = avail - cardw * ncols
    return [cardw + (1 if i < rem else 0) for i in range(ncols)]


def _card_lines(card, width, g, ascii_mode):
    """A card is a box of exactly `width` display cells, `n` lines tall.

    Branch on the explicit ascii_mode flag, never on a glyph's value -- an
    earlier version inferred the mode from `g["ok"] != "v"`, which silently
    breaks the moment a glyph is retuned.
    """
    tl, tr, bl, br, h, v = ("+", "+", "+", "+", "-", "|") if ascii_mode \
        else ("╭", "╮", "╰", "╯", "─", "│")
    inner = width - 2
    badge = " ".join(g[k] for k, _ in card.get("badges") or [])
    title_bar = "%s%s %s " % (tl, h, clip(card["id"], inner - 6 - cw(badge), g["ellipsis"]))
    tail = (" %s %s%s" % (badge, h, tr)) if badge else ("%s%s" % (h, tr))
    fill = max(0, width - cw(title_bar) - cw(tail))
    lines = [[Span(title_bar + h * fill + tail, "chrome")]]

    def row(text, style):
        body = clip(text, inner - 2, g["ellipsis"])
        return [Span(v, "chrome"), Span(" " + pad(body, inner - 1), style),
                Span(v, "chrome")]

    lines.append(row(card.get("title") or "", "txt"))
    if card.get("goal"):
        lines.append(row("  " + card["goal"], "dim"))
    if card.get("next_action"):
        lines.append(row("%s %s" % (g["next_action"], card["next_action"]), "txt"))
    for wt in card.get("worktrees") or []:
        lines.append(row("%s %s" % (g["worktree"], wt), "dim"))
    for key, text in card.get("badges") or []:
        lines.append(row("%s %s" % (g[key], text), "warn" if key != "ok" else "ok"))
    for note in card.get("notes") or []:
        lines.append(row("%s %s" % (g["collision"], note), "bad"))
    lines.append([Span(bl + h * (width - 2) + br, "chrome")])
    return lines


def _join_row(cards_lines, widths):
    height = max(len(c) for c in cards_lines)
    out = []
    for i in range(height):
        spans = []
        for idx, cl in enumerate(cards_lines):
            if idx:
                spans.append(Span(" " * GUT, None))
            if i < len(cl):
                spans.extend(cl[i])
            else:
                spans.append(Span(" " * widths[idx], None))
        out.append(_rstrip(spans))
    return out


def _rstrip(spans):
    while spans:
        text = spans[-1].text.rstrip()
        if text:
            spans[-1] = Span(text, spans[-1].style)
            break
        spans.pop()
    return spans


def render_board(board, width, *, ascii_mode=False, meta=None):
    """The ONLY place geometry is computed. Returns a list of lines, each a list
    of Spans. Emit backends colour spans and must never re-derive widths.

    ascii_mode and meta are keyword-only (spec 8.2) so a positional call site
    cannot silently swap them.
    """
    g = glyph_table(ascii_mode)
    m = dict(board.get("meta") or {})
    m.update(meta or {})
    lines = []

    sep = g["separator"]
    left = "%s %s %s %s %s %s@%s" % (g["logo"], "agent-board", sep,
                                     m.get("project", "?"), sep,
                                     m.get("branch", "?"), m.get("head", "?"))
    right = "%d open %s %s%d %s %s%d %s %s" % (
        m.get("open", 0), sep, g["live_job"], m.get("live_jobs", 0), sep,
        g["collision"], m.get("collisions", 0), sep, m.get("clock", ""))
    gapw = max(1, width - cw(left) - cw(right))
    lines.append([Span(clip(left, width, g["ellipsis"]), "chrome"),
                  Span(" " * gapw, None), Span(right, "dim")])
    hline = "─" if not ascii_mode else "-"
    lines.append([Span(hline * width, "chrome")])

    widths = col_widths(width)
    for name in COLUMN_ORDER:
        cards = (board.get("columns") or {}).get(name) or []
        if not cards:
            continue
        lines.append(_lane(name, len(cards), width, ascii_mode))
        if name == "DONE":
            for card in cards:
                text = "  %s %s %s %s" % (g["ok"], card["id"], sep,
                                          card.get("title") or "")
                lines.append([Span(clip(text, width, g["ellipsis"]), "faint")])
            continue
        for start in range(0, len(cards), len(widths)):
            chunk = cards[start:start + len(widths)]
            cl = [_card_lines(c, widths[i], g, ascii_mode)
                  for i, c in enumerate(chunk)]
            lines.extend(_join_row(cl, widths[:len(chunk)]))

    cols = board.get("collisions") or []
    if cols:
        lines.append([Span(hline * width, "chrome")])
        for c in cols:
            text = "  %s %s %s %s %s %s" % (
                g["collision"], c["severity"], sep, c["a"], sep, c["b"])
            lines.append([Span(clip(text, width, g["ellipsis"]), "bad")])
            for f in c.get("files") or []:
                lines.append([Span(clip("      " + f, width, g["ellipsis"]), "dim")])
    return [_rstrip(list(l)) for l in lines]


def _lane(name, count, width, ascii_mode):
    bar = "━" if not ascii_mode else "="
    head = "%s %s (%d) " % (bar * 2, name, count)
    return [Span(head + bar * max(0, width - cw(head)), "chrome")]
