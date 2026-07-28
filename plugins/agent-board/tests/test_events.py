import json
import os
import subprocess
import sys
import textwrap

from agent_board import events, model


def _tdir(tmp_path):
    d = tmp_path / "agent-board"
    (d / "threads" / "t").mkdir(parents=True)
    return str(d)


def test_shard_name_is_filesystem_safe(monkeypatch):
    monkeypatch.setattr(events.store, "HOST", "login-02.cluster/weird")
    assert "/" not in events.shard_name()
    assert events.shard_name().endswith(".jsonl")


def test_append_then_read_roundtrip(tmp_path):
    d = _tdir(tmp_path)
    events.append_event(d, "t", {"kind": "note", "actor": "cli", "text": "hello"})
    got = events.read_thread_events(d, "t", 10)
    assert len(got) == 1
    assert got[0]["kind"] == "note" and got[0]["text"] == "hello"
    assert got[0]["ts"].endswith("Z") and got[0]["host"]


def test_records_are_one_line_each(tmp_path):
    d = _tdir(tmp_path)
    for i in range(3):
        events.append_event(d, "t", {"kind": "note", "text": "line %d" % i})
    path = os.path.join(d, "threads", "t", "events", events.shard_name())
    assert len(open(path).read().strip().split("\n")) == 3


def test_oversized_record_is_truncated_not_rejected(tmp_path):
    d = _tdir(tmp_path)
    events.append_event(d, "t", {"kind": "note", "text": "x" * 10000})
    got = events.read_thread_events(d, "t", 10)
    assert len(got) == 1
    path = os.path.join(d, "threads", "t", "events", events.shard_name())
    assert max(len(l) for l in open(path).read().splitlines()) <= 4096


def test_tail_drops_an_in_flight_partial_final_line(tmp_path):
    """Measured: a reader tailing a live shard saw 5.0% unparseable lines, and a
    killed writer leaves a permanently truncated final line forever."""
    p = tmp_path / "h.jsonl"
    p.write_text('{"kind":"a","ts":"t"}\n{"kind":"b","ts":"t"}\n{"kind":"trunc"')
    got = events.read_events_tail(str(p), 10)
    assert [r["kind"] for r in got] == ["a", "b"]


def test_tail_skips_a_garbage_line_in_the_middle(tmp_path):
    p = tmp_path / "h.jsonl"
    p.write_text('{"kind":"a"}\nNOT JSON\n{"kind":"c"}\n')
    assert [r["kind"] for r in events.read_events_tail(str(p), 10)] == ["a", "c"]


def test_tail_returns_only_the_last_n(tmp_path):
    p = tmp_path / "h.jsonl"
    p.write_text("".join('{"kind":"k%d"}\n' % i for i in range(50)))
    got = events.read_events_tail(str(p), 3)
    assert [r["kind"] for r in got] == ["k47", "k48", "k49"]


def test_missing_shard_returns_empty(tmp_path):
    assert events.read_events_tail(str(tmp_path / "nope.jsonl"), 5) == []


def test_tail_keeps_every_record_when_the_window_lands_on_a_boundary(tmp_path):
    """`len(buf) >= 65536` is not the same question as "is the first record
    truncated". When the seek lands exactly on a newline the first record is
    complete, and the proxy silently dropped it.

    Construction note: trimming a large blob at an earlier newline does NOT
    by itself guarantee the *resulting standalone file's own* 65536-byte tail
    window starts on a boundary -- that only holds if the post-cut portion is
    exactly 65536 bytes long. A naive "trim the source blob at some newline
    before the cutoff" construction (varint-width `k%d` records) landed 4
    bytes into the following record in practice, which is a genuinely
    truncated fragment whose loss is correct, by-design behavior (a strict
    64 KiB tail read), not the proxy bug -- both the buggy proxy and the
    fixed lookbehind version drop that fragment identically, so that
    construction cannot discriminate between them. Fixed-width (64-byte)
    records make the alignment exact and deterministic: a 65536-byte `real`
    portion preceded by an arbitrary newline-terminated prefix reproduces the
    exact bug -- verified the buggy proxy drops the genuinely-complete first
    record here (1023 of 1024 returned, missing k000000)."""
    p = tmp_path / "h.jsonl"

    def _line(i):
        rec = {"kind": "k%06d" % i, "ts": "t", "pad": ""}
        used = len(json.dumps(rec)) + 1          # +1 for the trailing newline
        rec["pad"] = "x" * (64 - used)
        line = json.dumps(rec) + "\n"
        assert len(line) == 64
        return line.encode()

    n = 65536 // 64
    real = b"".join(_line(i) for i in range(n))
    assert len(real) == 65536
    junk = b"J" * 776 + b"\n"                    # arbitrary prefix ending in a newline
    p.write_bytes(junk + real)                   # window == `real` exactly: a clean boundary
    got = events.read_events_tail(str(p), 10 ** 6)
    assert len(got) == n, "lost %d record(s)" % (n - len(got))
    assert got[0]["kind"] == "k%06d" % 0
    assert got[-1]["kind"] == "k%06d" % (n - 1)


def test_tail_drops_only_the_truncated_leading_record(tmp_path):
    """The complement: when the window really does start mid-record, that
    fragment must be dropped rather than parsed."""
    p = tmp_path / "h.jsonl"
    recs = [json.dumps({"kind": "k%d" % i, "ts": "t"}) + "\n" for i in range(4000)]
    blob = "".join(recs).encode()
    nl = blob.rfind(b"\n", 0, len(blob) - 65536)
    p.write_bytes(blob[nl + 5:])             # start deliberately mid-record
    got = events.read_events_tail(str(p), 10 ** 6)
    assert got, "should still return the intact records"
    assert all("kind" in r for r in got)


def test_short_file_never_drops_its_first_record(tmp_path):
    p = tmp_path / "h.jsonl"
    p.write_text('{"kind":"first","ts":"t"}\n{"kind":"second","ts":"t"}\n')
    got = events.read_events_tail(str(p), 10)
    assert [r["kind"] for r in got] == ["first", "second"]


def test_eight_concurrent_appenders_lose_nothing(tmp_path):
    """8 appenders x 300 lines must yield exactly 2400 parseable lines."""
    d = _tdir(tmp_path)
    script = textwrap.dedent(
        """
        import sys
        sys.path.insert(0, %r)
        from agent_board import events
        d, tag = sys.argv[1], sys.argv[2]
        for i in range(300):
            events.append_event(d, "t", {"kind": "note", "text": tag + str(i)})
        """
    ) % (os.path.dirname(os.path.dirname(os.path.abspath(events.__file__))),)
    runner = tmp_path / "a.py"
    runner.write_text(script)
    procs = [subprocess.Popen([sys.executable, str(runner), d, "w%d" % i])
             for i in range(8)]
    for p in procs:
        assert p.wait(timeout=120) == 0
    path = os.path.join(d, "threads", "t", "events", events.shard_name())
    lines = [l for l in open(path).read().splitlines() if l.strip()]
    assert len(lines) == 2400, "lost appends: got %d" % len(lines)
    for l in lines:
        json.loads(l)          # every line must be intact
