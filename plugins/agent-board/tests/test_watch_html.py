import io
import re
import time
import xml.etree.ElementTree as ET

from agent_board import watch
from agent_board.render import html


class FakeKeys(object):
    """Scripted keypresses. Returns them in order, then None forever."""

    def __init__(self, keys=()):
        self.queue = list(keys)
        self.polls = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def poll(self, timeout):
        self.polls += 1
        return self.queue.pop(0) if self.queue else None


BOARD = {"meta": {"project": "p", "open": 1, "live_jobs": 0, "collisions": 0,
                  "branch": "main", "head": "abc1234"},
         "columns": {"ACTIVE": [{"id": "t1", "title": "T", "goal": "G",
                                 "next_action": "N", "badges": [], "notes": [],
                                 "worktrees": ["feat +0 -0 *1  1m ago"]}]},
         "collisions": [], "signals": {}}


# --- interval floor ----------------------------------------------------------

def test_interval_floor_is_fifteen_seconds():
    """Faster is not more informative -- git status over a network filesystem is
    the cost -- and it turns a monitor into a load generator on a shared node."""
    assert watch.clamp_interval(None) == 15.0
    assert watch.clamp_interval(1) == 15.0
    assert watch.clamp_interval(0) == 15.0
    assert watch.clamp_interval(-99) == 15.0
    assert watch.clamp_interval(60) == 60.0


def test_interval_garbage_falls_back_to_the_floor():
    assert watch.clamp_interval("nonsense") == 15.0
    assert watch.clamp_interval(object()) == 15.0


# --- the refresher runs off the main thread ----------------------------------

def test_refresher_does_not_block_the_caller():
    """A cold scan measured 32s of I/O wait. On the main loop that would freeze the
    display and swallow the keypress meant to quit it."""
    release = []

    def slow():
        while not release:
            time.sleep(0.005)
        return {"ok": True}

    r = watch.Refresher(slow)
    r.start()
    data, _err, _stamp, busy = r.latest()      # must return immediately
    assert data is None and busy is True
    release.append(1)
    for _ in range(400):
        data, _err, _stamp, busy = r.latest()
        if data is not None:
            break
        time.sleep(0.01)
    assert data == {"ok": True}


def test_refresher_keeps_the_last_good_board_when_a_refresh_fails():
    calls = []

    def build():
        calls.append(1)
        if len(calls) == 1:
            return {"n": 1}
        raise RuntimeError("probe exploded")

    r = watch.Refresher(build)
    r.start()
    _wait_idle(r)
    assert r.latest()[0] == {"n": 1}
    r.trigger()
    _wait_idle(r)
    data, error, _stamp, _busy = r.latest()
    assert data == {"n": 1}                    # last good board survives
    assert "probe exploded" in error


def test_refresher_will_not_start_a_second_scan_while_one_runs():
    release = []

    def slow():
        while not release:
            time.sleep(0.005)
        return {}

    r = watch.Refresher(slow)
    assert r.trigger() is True
    assert r.trigger() is False                # already busy
    release.append(1)
    _wait_idle(r)


def _wait_idle(r, limit=400):
    for _ in range(limit):
        if not r.latest()[3]:
            return
        time.sleep(0.01)
    raise AssertionError("refresher never went idle")


# --- the loop ----------------------------------------------------------------

def _run(keys, build=None, **kw):
    out = io.StringIO()
    rc = watch.run(build or (lambda: dict(BOARD)),
                   lambda board, notes: out.write("FRAME:%s\n" % ";".join(notes)),
                   out=out, keys=FakeKeys(keys), **kw)
    return rc, out.getvalue()


def test_q_quits():
    rc, text = _run(["q"])
    assert rc == 0
    assert "FRAME" in text


def test_ctrl_c_byte_quits():
    assert _run(["\x03"])[0] == 0


def test_r_forces_a_refresh_then_q_quits():
    calls = []

    def build():
        calls.append(1)
        return dict(BOARD)
    rc, _text = _run(["r", "q"], build=build)
    assert rc == 0
    assert len(calls) >= 2                     # initial scan plus the forced one


def test_repaint_clears_the_screen_rather_than_moving_the_cursor_up():
    """Line counts vary with width AND between refreshes as dirty state and job
    counts change, so cursor-up-by-N desynchronises the moment anything resizes."""
    _rc, text = _run(["q"])
    assert watch.CLEAR in text
    assert "\x1b[" in watch.CLEAR and "2J" in watch.CLEAR


def test_the_frame_states_the_interval_and_the_keys():
    _rc, text = _run(["q"], interval=30)
    assert "watching every 30s" in text and "q quits" in text


def test_a_scanning_placeholder_shows_before_the_first_board():
    """Otherwise a 32s cold scan looks like a hang."""
    out = io.StringIO()
    watch.run(lambda: None, lambda b, n: out.write("FRAME\n"),
              out=out, keys=FakeKeys(["q"]), max_loops=1)
    assert "scanning" in out.getvalue()


def test_max_loops_bounds_the_loop_for_tests():
    rc, _text = _run([], max_loops=2)
    assert rc == 0


def test_a_build_that_always_fails_still_exits_cleanly():
    def boom():
        raise RuntimeError("nope")
    rc, _text = _run(["q"], build=boom)
    assert rc == 0


# --- key reader degradation --------------------------------------------------

def test_key_reader_degrades_when_stdin_is_not_a_tty():
    """A pipe, a CI log or `watch abd board` has nothing to read, and cbreak mode
    would raise -- so the loop must fall back to interval-only."""
    class NotATty(object):
        def isatty(self):
            return False

    with watch.KeyReader(NotATty()) as reader:
        started = time.time()
        assert reader.poll(0.02) is None
        assert time.time() - started >= 0.015   # it slept rather than busy-looping


def test_key_reader_survives_a_stream_that_raises_on_isatty():
    class Hostile(object):
        def isatty(self):
            raise OSError("no")

    with watch.KeyReader(Hostile()) as reader:
        assert reader.poll(0.001) is None


# --- HTML export -------------------------------------------------------------

def _page(**kw):
    return html.export(BOARD, generated_at="2026-07-31 12:00", **kw)


def test_export_has_no_executable_or_fetching_constructs():
    """The invariant is about EXECUTION and FETCHING, not links."""
    page = _page()
    for pattern in (r"<script", r"\son[a-z]+\s*=", r"javascript:", r"\bsrc\s*=",
                    r"<link", r"@import", r"<iframe",
                    r"http-equiv\s*=\s*[\"']?refresh"):
        assert not re.search(pattern, page, re.I), pattern


def test_export_permits_an_href_to_a_pull_request():
    """Counting href=0 as a win makes every PR reference render as inert text. An
    href runs no code, fetches nothing, and degrades to a dead link offline."""
    board = dict(BOARD)
    board["columns"] = {"ACTIVE": [dict(BOARD["columns"]["ACTIVE"][0],
                                        pr={"number": 232,
                                            "url": "https://github.com/o/r/pull/232"})]}
    page = html.export(board)
    assert 'href="https://github.com/o/r/pull/232"' in page
    assert "PR #232" in page


def test_export_refuses_a_javascript_url_in_an_agent_written_field():
    board = dict(BOARD)
    board["columns"] = {"ACTIVE": [dict(BOARD["columns"]["ACTIVE"][0],
                                        pr={"number": 1,
                                            "url": "javascript:alert(1)"})]}
    page = html.export(board)
    assert "javascript:" not in page.lower()


def test_export_escapes_html_in_thread_fields():
    board = dict(BOARD)
    board["columns"] = {"ACTIVE": [dict(BOARD["columns"]["ACTIVE"][0],
                                        title="<img onerror=x>&\"'")]}
    page = html.export(board)
    assert "<img" not in page
    assert "&lt;img" in page


def test_export_is_responsive_dark_aware_and_print_friendly():
    page = _page().replace(" ", "")
    assert "repeat(auto-fill,minmax(320px,1fr))" in page
    assert "prefers-color-scheme:dark" in page
    assert "break-inside:avoid" in page


def test_done_collapses_with_native_details_and_no_script():
    board = dict(BOARD)
    board["columns"] = dict(BOARD["columns"],
                            DONE=[{"id": "old", "title": "Old"}])
    page = html.export(board)
    assert "<details>" in page and "<summary>" in page
    assert "<script" not in page


def test_collision_table_carries_severity_classes_and_demotions():
    board = dict(BOARD)
    board["collisions"] = [{"a": "x", "b": "y", "severity": "HIGH",
                            "files": ["a.py"], "demoted_files": ["CHANGELOG.md"]}]
    page = html.export(board)
    assert "sev-high" in page and "a.py" in page
    assert "1 ubiquitous demoted" in page


# --- the dependency graph ----------------------------------------------------

def test_layering_puts_a_blocker_before_the_thread_it_blocks():
    layer = html.layer_nodes(["a", "b"], [("a", "b")])   # a blocked by b
    assert layer["b"] < layer["a"]


def test_layering_terminates_on_a_cycle():
    """Bounded by len(nodes) so a cycle cannot hang the export."""
    layer = html.layer_nodes(["a", "b"], [("a", "b"), ("b", "a")])
    assert set(layer) == {"a", "b"}


def test_graph_is_empty_without_edges():
    assert html.graph_svg({"a": {"blocked_by": []}}, {}) == ""


def test_graph_ignores_a_dangling_blocker():
    assert html.graph_svg({"a": {"blocked_by": ["ghost"]}}, {}) == ""


def test_graph_svg_is_valid_xml_and_uses_one_shared_marker():
    threads = {"a": {"blocked_by": ["b", "c"], "title": "A"},
               "b": {"blocked_by": [], "title": "B"},
               "c": {"blocked_by": [], "title": "C"}}
    svg = html.graph_svg(threads, {"a": "BLOCKED", "b": "ACTIVE", "c": "ACTIVE"})
    ET.fromstring(svg.replace("&#183;", "&#xB7;"))
    assert svg.count('<marker id="ah"') == 1
    assert svg.count("url(#ah)") == 2                  # one per edge
    assert svg.count("<path class=\"edge\"") == 2


def test_graph_places_blockers_left_of_the_blocked_node():
    threads = {"a": {"blocked_by": ["b"], "title": "A"},
               "b": {"blocked_by": [], "title": "B"}}
    svg = html.graph_svg(threads, {"a": "BLOCKED", "b": "ACTIVE"})
    xs = {m.group(1): int(m.group(2)) for m in
          re.finditer(r'<title>([\w-]+)[^<]*</title>\s*<rect x="(\d+)"', svg)}
    assert xs["b"] < xs["a"]


def test_graph_layout_is_deterministic():
    """The same board must export the same SVG, or every re-export is a diff."""
    threads = {("t%d" % i): {"blocked_by": ["t0"] if i else [], "title": "T"}
               for i in range(6)}
    cols = {t: "ACTIVE" for t in threads}
    assert html.graph_svg(threads, cols) == html.graph_svg(threads, cols)


def test_the_refreshing_indicator_is_actually_reachable():
    """Keying repaints on the timestamp alone means a repaint only happens once a
    scan has FINISHED, by which point busy is False -- so the indicator would be
    dead code. Repaint on the busy flag too."""
    gate = []
    calls = []

    def build():
        calls.append(1)
        if len(calls) == 1:
            return dict(BOARD)
        while not gate:                     # second scan hangs until released
            time.sleep(0.005)
        return dict(BOARD)

    frames = []
    out = io.StringIO()

    def paint(board, notes):
        frames.append(list(notes))
        if len(frames) >= 3:
            gate.append(1)

    watch.run(build, paint, out=out, keys=FakeKeys(["r", None, None, None, "q"]),
              max_loops=40)
    gate.append(1)
    assert any("refreshing..." in " ".join(f) for f in frames), frames
