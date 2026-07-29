import copy

import pytest

from agent_board.render import palette
from agent_board.render.emit_plain import emit_plain, strip_ansi
from agent_board.render.layout import (
    MIN_WIDTH, Span, _lane, clip, col_widths, cw, render_board)

WIDTHS = (80, 100, 120, 160, 200, 240)

BOARD = {
    "meta": {"project": "agenticCRE", "branch": "main", "head": "f361567",
             "fetched": "3d ago", "open": 5, "live_jobs": 2, "collisions": 3,
             "clock": "14:07", "derived_s": 0.71},
    "columns": {
        "ACTIVE": [
            {"id": "mhb-agent-demo", "title": "MHB 16 hpf agent-native demo",
             "goal": "4-step demo: pareto_rank + MasterReport 1.1 + fasta",
             "next_action": "rerun step 3 once job 35061 lands",
             "badges": [("live_job", "2 jobs: 1 RUNNING 1 PENDING")],
             "worktrees": ["mhb-agent-demo  +5 -12 *3   2h ago"],
             "notes": ["notochord-design . src/agenticcre/agent.py"]},
            {"id": "artifact-backfill", "title": "Backfill analysis/ artifacts",
             "goal": "promote figures + sequences from 6 worktrees",
             "next_action": "coordinate docs/manuscript",
             "badges": [], "worktrees": ["artifact-backfill  +7 -31 *0  19h ago"],
             "notes": []},
        ],
        "BLOCKED": [
            {"id": "manuscript-audit", "title": "Manuscript <-> code audit",
             "goal": "manuscript still describes the retired pre-SDK arch",
             "next_action": "blocked: needs artifact-backfill figure paths",
             "badges": [("blocked", "blocked_by artifact-backfill")],
             "worktrees": ["manuscript-drafts  +2 -86 *1   6d ago"], "notes": []},
        ],
        "DONE": [
            {"id": "ui-redesign", "title": "terminal UI violet theme",
             "goal": None, "next_action": None, "badges": [],
             "worktrees": [], "notes": []},
        ],
    },
    "collisions": [
        {"a": "artifact-backfill", "b": "manuscript-audit",
         "files": ["docs/manuscript/fig1.md"], "severity": "HIGH"},
    ],
}


def test_cw_counts_wide_characters_as_two():
    assert cw("abc") == 3
    assert cw("你好") == 4          # CJK, class W
    assert cw("✓") == 1                # our glyphs are class N


def test_clip_never_exceeds_the_budget():
    assert cw(clip("a" * 50, 10, "…")) <= 10
    assert clip("abc", 10, "…") == "abc"


def test_clip_uses_the_supplied_ellipsis_only():
    out = clip("a" * 50, 10, "...")
    assert out.endswith("...") and all(ord(c) < 128 for c in out)


@pytest.mark.parametrize("width", WIDTHS)
def test_col_widths_exactly_fill_the_terminal(width):
    cols = col_widths(width)
    assert sum(cols) + 2 * (len(cols) - 1) == width, cols


@pytest.mark.parametrize("width", WIDTHS)
def test_col_widths_differ_by_at_most_one(width):
    cols = col_widths(width)
    assert max(cols) - min(cols) <= 1, "remainder must be distributed, not dropped"


def test_col_widths_is_one_column_at_eighty():
    assert col_widths(80) == [80]


@pytest.mark.parametrize("width", WIDTHS)
@pytest.mark.parametrize("ascii_mode", (False, True))
def test_no_rendered_line_exceeds_the_target_width(width, ascii_mode):
    lines = render_board(BOARD, width, ascii_mode=ascii_mode)
    for line in lines:
        text = emit_plain(line, palette.DARK, color=False)
        assert cw(text) <= width, "overflow at width=%d: %r (%d)" % (
            width, text, cw(text))


@pytest.mark.parametrize("width", WIDTHS)
def test_max_line_width_equals_the_target(width):
    lines = render_board(BOARD, width)
    widest = max(cw(emit_plain(l, palette.DARK, color=False)) for l in lines)
    assert widest == width, "expected exactly %d, got %d" % (width, widest)


@pytest.mark.parametrize("width", WIDTHS)
def test_ascii_mode_output_is_pure_ascii(width):
    lines = render_board(BOARD, width, ascii_mode=True)
    text = "\n".join(emit_plain(l, palette.DARK, color=False) for l in lines)
    bad = [c for c in text if ord(c) >= 128]
    assert not bad, "non-ascii in --ascii output: %r" % sorted(set(bad))


def test_no_trailing_whitespace_on_any_line():
    for line in render_board(BOARD, 120):
        text = emit_plain(line, palette.DARK, color=False)
        assert text == text.rstrip(), repr(text)


def test_every_column_with_cards_appears():
    text = "\n".join(emit_plain(l, palette.DARK, color=False)
                     for l in render_board(BOARD, 120))
    for name in ("ACTIVE", "BLOCKED", "DONE"):
        assert name in text
    assert "IN REVIEW" not in text, "empty columns must not render a lane"


def test_collisions_panel_renders():
    text = "\n".join(emit_plain(l, palette.DARK, color=False)
                     for l in render_board(BOARD, 120))
    assert "docs/manuscript/fig1.md" in text


def test_done_collapses_to_a_single_line():
    lines = render_board(BOARD, 120)
    texts = [emit_plain(l, palette.DARK, color=False) for l in lines]
    idx = [i for i, t in enumerate(texts) if "DONE" in t][0]
    after = [t for t in texts[idx + 1:] if t.strip()]
    assert "ui-redesign" in after[0]
    assert not any("╭" in t or "+-" in t for t in after[:2]), \
        "DONE threads must not render full cards"


def test_emit_plain_with_color_emits_ansi_that_strips_back_to_the_same_text():
    line = [Span("hello", "ok"), Span(" world", None)]
    plain = emit_plain(line, palette.DARK, color=False)
    colored = emit_plain(line, palette.DARK, color=True)
    assert plain == "hello world"
    assert "\x1b[" in colored
    assert strip_ansi(colored) == plain


@pytest.mark.parametrize("width", WIDTHS)
@pytest.mark.parametrize("ascii_mode", (False, True))
def test_long_metadata_never_overflows_the_header(width, ascii_mode):
    """The header clipped only its LEFT segment and appended the right one
    unclipped. Measured pre-fix with this repo's own names: width 80 -> 107 cells,
    width 120 -> 133."""
    board = copy.deepcopy(BOARD)
    board["meta"].update({
        "project": "claude-plugins-agent-board-m1",
        "branch": "feature/notochord-temporal-daniocell-integration",
        "head": "d5ad8ce12", "open": 12, "collisions": 11, "live_jobs": 4})
    for line in render_board(board, width, ascii_mode=ascii_mode):
        text = emit_plain(line, palette.DARK, color=False)
        assert cw(text) <= width, "overflow %d > %d: %r" % (cw(text), width, text)


@pytest.mark.parametrize("width", [0, 1, 10, 20, 30, 40, 49, 50, 51])
def test_narrow_widths_are_clamped_not_broken(width):
    lines = render_board(BOARD, width)
    target = max(width, MIN_WIDTH)
    widths = [cw(emit_plain(l, palette.DARK, color=False)) for l in lines]
    assert max(widths) == target, "max %d != clamped target %d" % (max(widths), target)


@pytest.mark.parametrize("width", WIDTHS)
@pytest.mark.parametrize("ascii_mode", (False, True))
def test_control_characters_do_not_split_the_reported_line_count(width, ascii_mode):
    """F6: cw() measured `\\n`, `\\t` and `\\x1b` as one cell each, so a title
    containing them falsified render_board's documented contract ("returns a
    list of lines") -- a `\\n` split one card row into two PHYSICAL lines --
    and let a raw SGR escape reach stdout. Measured at --width 60 via `cat -A`.
    """
    board = copy.deepcopy(BOARD)
    board["columns"]["ACTIVE"][0]["title"] = (
        "alpha\nbeta line two\x1b[41;97mSTICKY\ta\tb\tc\x7f")
    lines = render_board(board, width, ascii_mode=ascii_mode)
    full_text = "\n".join(emit_plain(l, palette.DARK, color=False) for l in lines)
    physical_lines = full_text.split("\n")
    assert len(physical_lines) == len(lines), (
        "render_board's contract is 'returns a list of lines' -- an embedded "
        "control character must not silently add a physical line: got %d "
        "physical lines for %d reported lines" % (len(physical_lines), len(lines)))
    assert "\x1b" not in full_text, repr(full_text)
    assert "\x7f" not in full_text, repr(full_text)
    for line in lines:
        text = emit_plain(line, palette.DARK, color=False)
        assert cw(text) <= width, "overflow at width=%d: %r" % (width, text)
    widest = max(cw(emit_plain(l, palette.DARK, color=False)) for l in lines)
    assert widest == max(width, MIN_WIDTH), \
        "max line width must still equal the clamped target"


def test_a_long_column_name_does_not_overflow_its_lane():
    line = _lane("A" * 200, 9999, 80, False)
    assert cw(emit_plain(line, palette.DARK, color=False)) <= 80
