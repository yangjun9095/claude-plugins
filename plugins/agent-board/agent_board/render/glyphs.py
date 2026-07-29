import unicodedata

GLYPH = {
    "ok":               "✓",   # v  check
    "warn":             "⚠",   # !  U+26A0 warning sign
    "bad":              "✕",   # x  multiplication x
    "live_job":         "⣿",   # *  braille full cell
    "needs_attention":  "⚑",   # !  black flag
    "blocked":          "⊘",   # #  circled division slash
    "worktree":         "▸",   # >  small right triangle
    "collision":        "‼",   # !! double exclamation
    "ahead":            "▴",   # +  small up triangle
    "behind":           "▾",   # -  small down triangle
    "dirty":            "▪",   # *  small black square
    "logo":             "⬢",   # #  black hexagon
    "next_action":      "⏵",   # >> black right pointer
    "ellipsis":         "…",
    "separator":        "·",
}

ASCII = {
    "ok": "v", "warn": "!", "bad": "x", "live_job": "*",
    "needs_attention": "!", "blocked": "#", "worktree": ">",
    "collision": "!!", "ahead": "+", "behind": "-", "dirty": "*",
    "logo": "#", "next_action": ">>", "ellipsis": "...", "separator": " | ",
}

# States that must be distinguishable at a glance. Uniqueness is asserted on the
# UNICODE table only -- single ASCII chars cannot be unique across 15 keys, and
# in ascii mode the surrounding text carries the meaning.
SEMANTIC = ("ok", "warn", "bad", "blocked", "collision", "needs_attention")

# Import-time guards so a future edit cannot regress alignment.
# The rule is "not W and not F", NOT "N or Na only". Measured facts that settle it:
#   * cw() counts only W and F as two cells, so those are the only classes that
#     can shift a card border.
#   * EVERY card frame character is class A -- U+2500 U+2502 U+256D U+256E U+2570
#     U+256F U+2501 all measure A. Banning class A in a 15-entry glyph table while
#     drawing ~120 class-A frame cells per card would be incoherent: if class A
#     were unsafe the frame would already be broken.
#   * Class A renders one cell in a Western locale and two only in a CJK context,
#     and a CJK locale auto-routes to the ASCII table anyway (LC_* ^(zh|ja|ko)).
# The N/Na form of this rule wrongly rejected `…` U+2026 and `·` U+00B7, both of
# which the spec's own board mockup uses throughout. `⛔` U+26D4 stays banned --
# it is class W and cw() measures it at 2, which was the original real bug.

# Each assertion carries a diagnostic. A violation fails at IMPORT, which is a
# collection error for the whole test file -- so the nicely-formatted messages in
# test_glyphs.py never run in the one scenario they were written for, and a bare
# AssertionError would name neither the key nor the codepoint.
_wide = [(k, c, unicodedata.east_asian_width(c))
         for k, g in GLYPH.items() for c in g
         if unicodedata.east_asian_width(c) in ("W", "F")]
assert not _wide, "double-width glyph(s) shift the card border: %s" % _wide

_vs16 = [k for k, g in GLYPH.items() if "️" in g]
assert not _vs16, "VS16 makes a codepoint class A; found in: %s" % _vs16

_dupes = {}
for _k in SEMANTIC:
    _dupes.setdefault(GLYPH[_k], []).append(_k)
_collided = {g: ks for g, ks in _dupes.items() if len(ks) > 1}
assert not _collided, "semantic states share a glyph: %s" % _collided

assert set(ASCII) == set(GLYPH), (
    "ASCII/GLYPH key mismatch: only-GLYPH=%s only-ASCII=%s"
    % (sorted(set(GLYPH) - set(ASCII)), sorted(set(ASCII) - set(GLYPH))))


def table(ascii_mode):
    return ASCII if ascii_mode else GLYPH
