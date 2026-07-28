import unicodedata

GLYPH = {
    "ok":               "✓",   # v  check
    "warn":             "⚠",   # !  warning sign (class N -- NOT U+25B2, class A)
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
    "ellipsis":         "...",
    "separator":        "-",
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
assert all(unicodedata.east_asian_width(c) in ("N", "Na")
           for g in GLYPH.values() for c in g)
assert "️" not in "".join(GLYPH.values())
assert len({GLYPH[k] for k in SEMANTIC}) == len(SEMANTIC)
assert set(ASCII) == set(GLYPH)


def table(ascii_mode):
    return ASCII if ascii_mode else GLYPH
