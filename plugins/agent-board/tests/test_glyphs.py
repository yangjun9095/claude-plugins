import unicodedata

from agent_board.render import glyphs, palette


def test_no_glyph_is_double_width():
    """Only class W and F occupy two cells under cw(), so only those can shift a
    card border. U+26D4 (class W) was the real bug. Class A is fine: it renders
    one cell outside a CJK locale, a CJK locale auto-routes to the ASCII table,
    and every card frame character (U+2500 etc.) is itself class A."""
    for key, g in glyphs.GLYPH.items():
        for ch in g:
            eaw = unicodedata.east_asian_width(ch)
            assert eaw not in ("W", "F"), "%s (%r U+%04X) is class %s" % (
                key, ch, ord(ch), eaw)


def test_the_card_frame_is_class_A_so_the_rule_cannot_ban_class_A():
    """Pins the reason the rule is W/F rather than N/Na -- if a future edit
    tightens it back, this fails and explains why."""
    for ch in "─│╭╮╰╯━":
        assert unicodedata.east_asian_width(ch) == "A"


def test_no_variation_selector_16():
    """VS16 makes anything class A."""
    assert "️" not in "".join(glyphs.GLYPH.values())


def test_semantic_glyphs_are_unique():
    seen = [glyphs.GLYPH[k] for k in glyphs.SEMANTIC]
    assert len(set(seen)) == len(seen), "two states share a glyph: %s" % seen


def test_ascii_table_covers_every_key_and_is_pure_ascii():
    assert set(glyphs.ASCII) == set(glyphs.GLYPH)
    for key, g in glyphs.ASCII.items():
        assert all(ord(c) < 128 for c in g), "%s -> %r is not ASCII" % (key, g)


def test_table_switches_on_ascii_mode():
    assert glyphs.table(False) is glyphs.GLYPH
    assert glyphs.table(True) is glyphs.ASCII


def test_ellipsis_and_separator_come_from_the_table():
    """--ascii output still contained U+00B7 and U+2026 from a hardcoded
    ell='...' default, so PYTHONIOENCODING=ascii --ascii raised
    UnicodeEncodeError -- failing in exactly the scenario the flag exists for."""
    assert "ellipsis" in glyphs.GLYPH and "separator" in glyphs.GLYPH
    assert glyphs.ASCII["ellipsis"] == "..."


def test_contrast_ratio_reference_values():
    assert round(palette.contrast_ratio("#ffffff", "#000000"), 1) == 21.0
    assert round(palette.contrast_ratio("#000000", "#000000"), 1) == 1.0


def test_dark_palette_text_colours_meet_wcag_aa():
    bg = palette.DARK["bg"]
    for key in ("ok", "warn", "bad", "chrome", "txt", "dim", "faint"):
        cr = palette.contrast_ratio(palette.DARK[key], bg)
        assert cr >= 4.5, "DARK[%s] contrast %.2f < 4.5" % (key, cr)


def test_light_palette_text_colours_meet_wcag_aa():
    bg = palette.LIGHT["bg"]
    for key in ("ok", "warn", "bad", "chrome", "txt", "dim"):
        cr = palette.contrast_ratio(palette.LIGHT[key], bg)
        assert cr >= 4.5, "LIGHT[%s] contrast %.2f < 4.5" % (key, cr)


def test_dark_hexes_are_not_reused_on_the_light_background():
    """They score 1.77 / 1.83 / 3.60 / 2.09 on white -- all failing AA."""
    for key in ("ok", "warn", "chrome"):
        assert palette.DARK[key] != palette.LIGHT[key]
