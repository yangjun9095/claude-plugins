import collections
import re
import unicodedata

from agent_board.render.emit_plain import strip_ansi
from agent_board.render.glyphs import table as glyph_table

Span = collections.namedtuple("Span", "text style")

# C0 controls (0x00-0x1F, incl. \n \t and a bare ESC not swallowed by
# strip_ansi below) plus DEL (0x7F).
# C0 (incl. \n \t and a bare ESC), DEL, plus three characters that terminals AND
# str.splitlines() treat as line breaks even though they are not C0: U+0085 NEL,
# U+2028 LINE SEPARATOR, U+2029 PARAGRAPH SEPARATOR. Without them one rendered
# element still became several physical lines.
_CONTROL_CHARS = re.compile(r"[\x00-\x1f\x7f\u0085\u2028\u2029]")


def sanitize(s, ascii_mode=False):
    """Neutralise text that would break the card frame or move the reader's
    cursor. Content NORMALISATION, not geometry -- lives here, not in cw()
    (which must stay a pure measurement), and runs BEFORE clip()/pad() so
    width accounting only ever sees the sanitised text.

    Two passes: (1) strip recognised ANSI SGR colour escapes outright via the
    shared `strip_ansi`, so an injected colour code leaves no residue; (2)
    replace any REMAINING C0 control character -- `\\n`, `\\t`, a bare ESC not
    part of a recognised SGR run -- and DEL with one visible placeholder
    cell. Measured pre-fix at --width 60: a `\\n` in a title split one card
    row into two PHYSICAL lines (falsifying render_board's "returns a list
    of lines" contract), and a raw SGR escape reached stdout unmodified.
    """
    if not s:
        return s
    s = strip_ansi(s)
    return _CONTROL_CHARS.sub("?" if ascii_mode else "�", s)


GUT = 2
CARD_W_PREF = 58

# Below this the card frame's fixed characters (rounded corners, rules, padding)
# cannot fit, and every line overflows no matter how content is clipped. Measured
# on a trivial one-card board: width 40 -> max line 44, width 30 -> 44, width 20
# -> 41. 50 is the first width that fits. Rendering wider than asked is a visible
# wrap; a broken frame is worse, so clamp and say so.
MIN_WIDTH = 50

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
        body = clip(sanitize(text, ascii_mode), inner - 2, g["ellipsis"])
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
    for ev in card.get("events") or []:
        lines.append(row("  %s" % _event_text(ev), "faint"))
    lines.append([Span(bl + h * (width - 2) + br, "chrome")])
    return lines


def _event_text(ev):
    """One line of last activity.

    `abd event add` writes `text`; the hook writes `reason`; but every MUTATION
    (`thread set/park/done/reopen`) writes only `{"kind": "set", "fields": [...]}`.
    Falling through to the bare kind rendered "set" and "logout" -- true, and
    useless. Name the fields that changed instead.
    """
    if not isinstance(ev, dict):
        return ""
    for key in ("text", "reason"):
        value = ev.get(key)
        if isinstance(value, str) and value:
            return value
    fields = ev.get("fields")
    kind = str(ev.get("kind") or "")
    if isinstance(fields, list) and fields:
        return "%s %s" % (kind or "changed",
                          ", ".join(str(f) for f in fields))
    return kind


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
    width = max(width, MIN_WIDTH)                # see MIN_WIDTH
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
    # Reserve space for `right` BEFORE clipping `left`, and clip `right` too.
    # The original clipped only `left` (against the FULL width) and appended
    # `right` unclipped, so any realistic metadata overflowed.
    right = clip(right, max(0, width - 1), g["ellipsis"])
    left = clip(left, max(0, width - cw(right) - 1), g["ellipsis"])
    gapw = width - cw(left) - cw(right)          # >= 1 by construction
    lines.append([Span(left, "chrome"),
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
                                          sanitize(card.get("title") or "", ascii_mode))
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
                g["collision"], sanitize(c["severity"], ascii_mode), sep,
                sanitize(c["a"], ascii_mode), sep, sanitize(c["b"], ascii_mode))
            lines.append([Span(clip(text, width, g["ellipsis"]), "bad")])
            for f in c.get("files") or []:
                line = "      " + sanitize(f, ascii_mode)
                lines.append([Span(clip(line, width, g["ellipsis"]), "dim")])
            demoted = c.get("demoted_files") or []
            if demoted:
                # Demoted files render COLLAPSED, never silently dropped.
                line = ("      + %d ubiquitous file%s demoted"
                        % (len(demoted), "" if len(demoted) == 1 else "s"))
                lines.append([Span(clip(line, width, g["ellipsis"]), "faint")])

    for note in footer_notes(board):
        lines.append([Span(clip("  " + sanitize(note, ascii_mode), width,
                                g["ellipsis"]), "faint")])
    return [_rstrip(list(l)) for l in lines]


def _ago(seconds):
    seconds = max(0, int(seconds or 0))
    if seconds < 90:
        return "%ds" % seconds
    if seconds < 3600:
        return "%dm" % (seconds // 60)
    if seconds < 172800:
        return "%dh" % (seconds // 3600)
    return "%dd" % (seconds // 86400)


def footer_notes(board):
    """What the board could NOT see. An understated severity that says so is
    usable; one that stays silent is a wrong answer."""
    signals = board.get("signals") or {}
    forge_sig = signals.get("forge") or {}
    jobs_sig = signals.get("jobs") or {}
    coll_sig = signals.get("collisions") or {}
    notes = []
    age = signals.get("snapshot_age_s")
    if age is not None:
        notes.append("snapshot from %s ago - re-run without --cached to refresh"
                     % _ago(age))
    if forge_sig.get("error"):
        notes.append("PR state unavailable (%s) - IN REVIEW is not derived and "
                     "severities may be understated" % forge_sig["error"])
    elif forge_sig.get("stale"):
        notes.append("PR state is from cache and may be out of date")
    if jobs_sig.get("error"):
        notes.append("job state unavailable (%s)" % jobs_sig["error"])
    if coll_sig.get("degraded"):
        notes.append("collision scan degraded: %d worktree probe(s) failed"
                     % (coll_sig.get("failed_probes") or 0))
    if coll_sig.get("demoted"):
        notes.append("%d file(s) demoted as ubiquitous (demote_at=%s over %s "
                     "threads)" % (coll_sig["demoted"], coll_sig.get("demote_at"),
                                   coll_sig.get("considered")))
    unattributed = jobs_sig.get("unattributed") or 0
    if unattributed:
        notes.append("%d scheduler job(s) matched no thread - declare "
                     "job_name_prefix to attribute them" % unattributed)
    return notes


def _lane(name, count, width, ascii_mode):
    """The head must be CLIPPED, not merely have its fill clamped to zero: a long
    column name or count could otherwise push the lane line past the target."""
    g = glyph_table(ascii_mode)
    bar = "━" if not ascii_mode else "="
    head = clip("%s %s (%d) " % (bar * 2, name, count), width, g["ellipsis"])
    return [Span(head + bar * max(0, width - cw(head)), "chrome")]
