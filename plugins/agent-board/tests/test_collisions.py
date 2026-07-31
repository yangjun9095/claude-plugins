import io
import json
import os

import pytest

from agent_board import model
from agent_board.derive import collisions
from tests.conftest import git


def _store(tmp_path, name="board"):
    d = tmp_path / name
    (d / "threads").mkdir(parents=True)
    return str(d)


def _thread(threads_dir, tid, **fields):
    t = dict(model.DECLARED_DEFAULTS)
    t.update({"id": tid, "schema_version": 1, "rev": 1})
    t.update(fields)
    d = os.path.join(threads_dir, "threads", tid)
    os.makedirs(d, exist_ok=True)
    with io.open(os.path.join(d, "thread.json"), "w", encoding="utf-8") as fh:
        fh.write(json.dumps(t))
    return t


# --- the ignore matcher's total-failure bug ---------------------------------

def test_empty_glob_list_ignores_NOTHING():
    """'|'.join([]) is '' and re.compile('').match(x) is TRUTHY, so the obvious
    implementation ignores EVERY path and the board silently reports zero
    collisions -- a total feature failure that reads as good news."""
    assert collisions.build_ignore_matcher([])("any/path.py") is False
    assert collisions.build_ignore_matcher(None)("any/path.py") is False


def test_default_globs_ignore_lockfiles_and_binaries_at_any_depth():
    ignored = collisions.build_ignore_matcher(collisions.DEFAULT_IGNORE_GLOBS)
    for path in ("uv.lock", "deep/nested/uv.lock", "fig.png", "a/b/fig.png",
                 "x/__pycache__/y.pyc", "node_modules/pkg/index.js", "out.h5ad"):
        assert ignored(path) is True, path


def test_default_globs_do_NOT_ignore_docs_or_markdown():
    """The measured anti-result: adding docs/**, *.md drops collisions 4 -> 2 and
    destroys the 9-file docs/manuscript/ collision -- exactly the 'two agents
    editing the paper' interference this exists to catch."""
    ignored = collisions.build_ignore_matcher(collisions.DEFAULT_IGNORE_GLOBS)
    for path in ("docs/manuscript/paper.md", "README.md", "analysis/notes.md",
                 "docs/design/plan.md", "src/main.py", "results.csv"):
        assert ignored(path) is False, path


def test_extra_globs_are_additive_not_replacing():
    ignored = collisions.build_ignore_matcher(
        list(collisions.DEFAULT_IGNORE_GLOBS) + ["**/*.generated.py"])
    assert ignored("x/y.generated.py") is True
    assert ignored("uv.lock") is True                  # defaults survive
    assert ignored("src/main.py") is False


# --- severity table, every rule ---------------------------------------------

def test_severity_r0_empty_overlap_is_none():
    assert collisions.severity("ACTIVE", "ACTIVE", set(), set(), set()) == "NONE"


def test_severity_r1_done_beats_everything_including_both_dirty():
    """R1 is checked BEFORE R2 on purpose: a finished thread must not raise a HIGH
    against a live one, however dirty both trees are."""
    assert collisions.severity("DONE", "ACTIVE", {"f"}, {"f"}, set()) == "LOW"
    assert collisions.severity("ACTIVE", "DONE", {"f"}, {"f"}, set()) == "LOW"


def test_severity_r2_both_dirty_and_both_live_is_high():
    """The top band, and empirically justified: both real source collisions in the
    reference repo are dirty-only on one side, so a committed-only scan finds
    neither."""
    for a in collisions.LIVE:
        for b in collisions.LIVE:
            assert collisions.severity(a, b, {"f"}, {"f"}, set()) == "HIGH"


def test_severity_r3_one_dirty_both_live_is_medium():
    assert collisions.severity("ACTIVE", "IN REVIEW", {"f"}, set(), {"f"}) == "MEDIUM"


def test_severity_r4_both_live_clean_is_medium():
    assert collisions.severity("ACTIVE", "BLOCKED", {"f"}, set(), set()) == "MEDIUM"


def test_severity_r5_one_live_is_low():
    assert collisions.severity("ACTIVE", "PARKED", {"f"}, {"f"}, set()) == "LOW"


def test_severity_r6_neither_live_is_low():
    assert collisions.severity("PARKED", "PARKED", {"f"}, {"f"}, set()) == "LOW"


def test_severity_is_total_over_unknown_columns():
    """Pure and TOTAL: it consumes a derived status and never computes one, so an
    unexpected value must still return a band rather than raise."""
    assert collisions.severity(None, "weird", {"f"}, set(), set()) == "LOW"


# --- ubiquity valve ----------------------------------------------------------

def test_ubiquity_valve_does_not_fire_on_a_normal_repo():
    """On the reference repo (28 considered) demote_at is 15 and nothing is
    demoted -- it correctly never fires and all 4 collisions survive."""
    # The real measured histogram: 539 distinct files, {1: 527, 2: 12} -- max
    # ubiquity 2 of 28 threads (7%), nowhere near demote_at.
    changed = {("t%d" % i): {"src/f%d.py" % i} for i in range(28)}
    for i in range(12):                      # 12 files shared by exactly 2 threads
        changed["t%d" % i].add("pair%d.py" % (i // 2))
    ubiquitous, demote_at, considered = collisions.ubiquity_valve(changed)
    assert considered == 28
    assert demote_at == 15
    assert ubiquitous == set()


def test_ubiquity_valve_demotes_a_genuinely_ubiquitous_file():
    changed = {("t%d" % i): {"src/f%d.py" % i, "CHANGELOG.md"} for i in range(12)}
    ubiquitous, demote_at, _considered = collisions.ubiquity_valve(changed)
    assert demote_at == 7
    assert ubiquitous == {"CHANGELOG.md"}


def test_ubiquity_floor_is_four_so_tiny_projects_never_demote():
    """max(4, ...) matters: with 2 threads, half-plus-one is 2, which would demote
    every single shared file and report no collisions at all."""
    changed = {"a": {"shared.py"}, "b": {"shared.py"}}
    ubiquitous, demote_at, _ = collisions.ubiquity_valve(changed)
    assert demote_at == 4
    assert ubiquitous == set()


def test_empty_threads_are_not_counted_as_considered():
    changed = {"a": {"f.py"}, "b": set(), "c": set()}
    _ubiq, _demote, considered = collisions.ubiquity_valve(changed)
    assert considered == 1


# --- pairwise ----------------------------------------------------------------

def _pairwise(changed, dirty, columns):
    ubiq, _d, _c = collisions.ubiquity_valve(changed)
    return collisions.pairwise({}, changed, dirty, columns, ubiq)


def test_pairwise_emits_one_row_per_colliding_pair():
    pairs = _pairwise({"a": {"f.py"}, "b": {"f.py"}, "c": {"other.py"}},
                      {"a": set(), "b": set(), "c": set()},
                      {"a": "ACTIVE", "b": "ACTIVE", "c": "ACTIVE"})
    assert len(pairs) == 1
    assert (pairs[0]["a"], pairs[0]["b"]) == ("a", "b")
    assert pairs[0]["files"] == ["f.py"]


def test_pairwise_separates_both_dirty_from_one_dirty():
    pairs = _pairwise({"a": {"x.py", "y.py"}, "b": {"x.py", "y.py"}},
                      {"a": {"x.py", "y.py"}, "b": {"x.py"}},
                      {"a": "ACTIVE", "b": "ACTIVE"})
    assert pairs[0]["both_dirty"] == ["x.py"]
    assert pairs[0]["one_dirty"] == ["y.py"]
    assert pairs[0]["severity"] == "HIGH"


def test_pairwise_skips_a_pair_whose_whole_overlap_is_demoted(monkeypatch):
    changed = {("t%d" % i): {"CHANGELOG.md"} for i in range(12)}
    ubiq, _d, _c = collisions.ubiquity_valve(changed)
    assert ubiq == {"CHANGELOG.md"}
    pairs = collisions.pairwise({}, changed, {k: set() for k in changed},
                                {k: "ACTIVE" for k in changed}, ubiq)
    assert pairs == []


def test_demoted_files_are_reported_not_silently_dropped():
    changed = {("t%d" % i): {"CHANGELOG.md"} for i in range(12)}
    changed["t0"] = {"CHANGELOG.md", "real.py"}
    changed["t1"] = {"CHANGELOG.md", "real.py"}
    ubiq, _d, _c = collisions.ubiquity_valve(changed)
    pairs = collisions.pairwise({}, changed, {k: set() for k in changed},
                                {k: "ACTIVE" for k in changed}, ubiq)
    hit = [p for p in pairs if {p["a"], p["b"]} == {"t0", "t1"}]
    assert hit and hit[0]["files"] == ["real.py"]
    assert hit[0]["demoted_files"] == ["CHANGELOG.md"]


def test_pairwise_orders_high_before_medium_then_by_size():
    changed = {"a": {"1", "2", "3"}, "b": {"1", "2", "3"}, "c": {"1"}, "d": {"1"}}
    dirty = {"a": set(), "b": set(), "c": {"1"}, "d": {"1"}}
    cols = {k: "ACTIVE" for k in changed}
    pairs = collisions.pairwise({}, changed, dirty, cols, set())
    assert pairs[0]["severity"] == "HIGH"
    assert {pairs[0]["a"], pairs[0]["b"]} == {"c", "d"}
    mediums = [p for p in pairs if p["severity"] == "MEDIUM"]
    assert len(mediums[0]["files"]) >= len(mediums[-1]["files"])


# --- against a real repo -----------------------------------------------------

def test_three_dot_excludes_what_the_base_branch_did(repo_with_worktrees):
    """Two-dot answers 'what differs between main's tip and this branch' -- mostly
    what MAIN did -- and built a 1633-file noise wall. Three-dot must not report a
    file that only the base advanced."""
    from agent_board.derive import git_
    main, wts = repo_with_worktrees
    wt_a = wts[0]
    (wt_a / "mine.py").write_text("x = 1\n")
    git(wt_a, "add", "-A")
    git(wt_a, "commit", "-qm", "mine")
    # advance trunk with an unrelated file
    for i in range(3):
        (main / ("base%d.txt" % i)).write_text("b\n")
    git(main, "add", "-A")
    git(main, "commit", "-qm", "base moves on")

    changed = git_.changed_files(str(wt_a), "trunk")
    assert "mine.py" in changed
    assert not any(p.startswith("base") for p in changed), changed


def test_real_two_worktrees_dirty_on_both_sides_is_high(
        repo_with_worktrees, tmp_path):
    """The end-to-end case the feature exists for: two threads with uncommitted
    edits to the same file."""
    main, wts = repo_with_worktrees
    (main / "shared.py").write_text("v = 0\n")
    git(main, "add", "-A")
    git(main, "commit", "-qm", "add shared")
    for wt in wts:
        git(wt, "merge", "-q", "trunk")
        (wt / "shared.py").write_text("v = %r\n" % str(wt))   # dirty, uncommitted

    store_dir = _store(tmp_path)
    threads = {
        "alpha": _thread(store_dir, "alpha", worktrees=[{"path": str(wts[0])}]),
        "beta": _thread(store_dir, "beta", worktrees=[{"path": str(wts[1])}]),
    }
    result = collisions.detect(
        store_dir, threads, {"alpha": "ACTIVE", "beta": "ACTIVE"},
        {str(wts[0]), str(wts[1])}, "trunk",
        {"collisions": {}, "scan": {"workers": 2}})
    assert len(result["collisions"]) == 1
    pair = result["collisions"][0]
    assert pair["severity"] == "HIGH"
    assert "shared.py" in pair["files"]
    assert "shared.py" in pair["both_dirty"]


def test_real_one_side_committed_one_dirty_is_medium(repo_with_worktrees, tmp_path):
    """A committed-diff-only scan would find this at all; a dirty-only scan would
    miss it. The union is what catches both."""
    main, wts = repo_with_worktrees
    (main / "shared.py").write_text("v = 0\n")
    git(main, "add", "-A")
    git(main, "commit", "-qm", "add shared")
    for wt in wts:
        git(wt, "merge", "-q", "trunk")
    (wts[0] / "shared.py").write_text("committed change\n")
    git(wts[0], "add", "-A")
    git(wts[0], "commit", "-qm", "committed")
    (wts[1] / "shared.py").write_text("dirty change\n")        # not committed

    store_dir = _store(tmp_path)
    threads = {
        "alpha": _thread(store_dir, "alpha", worktrees=[{"path": str(wts[0])}]),
        "beta": _thread(store_dir, "beta", worktrees=[{"path": str(wts[1])}]),
    }
    result = collisions.detect(
        store_dir, threads, {"alpha": "ACTIVE", "beta": "ACTIVE"},
        {str(wts[0]), str(wts[1])}, "trunk",
        {"collisions": {}, "scan": {"workers": 2}})
    assert len(result["collisions"]) == 1
    assert result["collisions"][0]["severity"] == "MEDIUM"
    assert result["collisions"][0]["one_dirty"] == ["shared.py"]


def test_no_collision_when_the_two_touch_different_files(
        repo_with_worktrees, tmp_path):
    main, wts = repo_with_worktrees
    (wts[0] / "a.py").write_text("a\n")
    (wts[1] / "b.py").write_text("b\n")
    store_dir = _store(tmp_path)
    threads = {
        "alpha": _thread(store_dir, "alpha", worktrees=[{"path": str(wts[0])}]),
        "beta": _thread(store_dir, "beta", worktrees=[{"path": str(wts[1])}]),
    }
    result = collisions.detect(
        store_dir, threads, {"alpha": "ACTIVE", "beta": "ACTIVE"},
        {str(wts[0]), str(wts[1])}, "trunk",
        {"collisions": {}, "scan": {"workers": 2}})
    assert result["collisions"] == []


def test_detect_writes_the_cache_the_hook_reads(repo_with_worktrees, tmp_path):
    """`abd board` owns writing cache/collisions.json; the SessionEnd hook
    deliberately does not. If the board is never run, HIGH collisions stop
    appearing in injected cards after 24 h."""
    from agent_board import hookimpl
    main, wts = repo_with_worktrees
    (main / "shared.py").write_text("v = 0\n")
    git(main, "add", "-A")
    git(main, "commit", "-qm", "add shared")
    for wt in wts:
        git(wt, "merge", "-q", "trunk")
        (wt / "shared.py").write_text("v = %r\n" % str(wt))

    store_dir = _store(tmp_path)
    threads = {
        "alpha": _thread(store_dir, "alpha", worktrees=[{"path": str(wts[0])}]),
        "beta": _thread(store_dir, "beta", worktrees=[{"path": str(wts[1])}]),
    }
    collisions.detect(
        store_dir, threads, {"alpha": "ACTIVE", "beta": "ACTIVE"},
        {str(wts[0]), str(wts[1])}, "trunk",
        {"collisions": {}, "scan": {"workers": 2}})
    # the hook's reader must find it, unchanged, through its own public path
    found = hookimpl.read_collisions(store_dir, "alpha")
    assert found and "shared.py" in found[0]
    assert "beta" in found[0]


def test_ignored_paths_never_reach_the_rollup(repo_with_worktrees, tmp_path):
    main, wts = repo_with_worktrees
    for wt in wts:
        (wt / "uv.lock").write_text(str(wt))
    store_dir = _store(tmp_path)
    threads = {
        "alpha": _thread(store_dir, "alpha", worktrees=[{"path": str(wts[0])}]),
        "beta": _thread(store_dir, "beta", worktrees=[{"path": str(wts[1])}]),
    }
    result = collisions.detect(
        store_dir, threads, {"alpha": "ACTIVE", "beta": "ACTIVE"},
        {str(wts[0]), str(wts[1])}, "trunk",
        {"collisions": {}, "scan": {"workers": 2}})
    assert result["collisions"] == []


def test_high_by_thread_marks_both_sides():
    pairs = [{"a": "x", "b": "y", "severity": "HIGH"},
             {"a": "y", "b": "z", "severity": "MEDIUM"}]
    assert collisions.high_by_thread(pairs) == {"x": True, "y": True}


def test_scan_of_zero_worktrees_is_not_an_error():
    assert collisions.scan_worktrees([], "trunk", 8) == {}


@pytest.mark.parametrize("workers", [0, 1, 8, 999])
def test_worker_count_is_always_clamped_to_something_runnable(
        repo_with_worktrees, workers):
    main, wts = repo_with_worktrees
    out = collisions.scan_worktrees([str(w) for w in wts], "trunk", workers)
    assert set(out) == {str(w) for w in wts}
