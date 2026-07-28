import pytest

from agent_board.config import DEFAULTS
from agent_board.derive import columns

TH = DEFAULTS["thresholds"]


def T(tid, **kw):
    t = {"id": tid, "done": False, "parked": False, "blocked_by": []}
    t.update(kw)
    return t


def D(**kw):
    d = {"has_open_nondraft_pr": False, "age_days": 0.0, "dirty": 0,
         "live_jobs": [], "ahead": 0, "pr": None,
         "missing_worktree": False, "lock_stale": False}
    d.update(kw)
    return d


def test_done_wins_over_everything():
    t = T("a", done=True, parked=True, blocked_by=["b"])
    threads = {"a": t, "b": T("b")}
    assert columns.column(t, threads, D(has_open_nondraft_pr=True), TH) == "DONE"


def test_blocked_when_a_dependency_is_not_done():
    t = T("a", blocked_by=["b"])
    threads = {"a": t, "b": T("b")}
    assert columns.column(t, threads, D(), TH) == "BLOCKED"


def test_a_done_dependency_does_not_block():
    t = T("a", blocked_by=["b"])
    threads = {"a": t, "b": T("b", done=True)}
    assert columns.column(t, threads, D(), TH) == "ACTIVE"


def test_a_missing_dependency_does_not_block_and_does_not_raise():
    """A dangling id raised KeyError and took the whole board down. Declared
    state is user-authored and a thread file can be deleted at any time."""
    t = T("a", blocked_by=["ghost"])
    assert columns.column(t, {"a": t}, D(), TH) == "ACTIVE"


def test_parked_beats_an_open_pr():
    """Explicit user intent must beat derived PR state."""
    t = T("a", parked=True)
    assert columns.column(t, {"a": t}, D(has_open_nondraft_pr=True), TH) == "PARKED"


def test_in_review_with_an_open_nondraft_pr():
    t = T("a")
    assert columns.column(t, {"a": t}, D(has_open_nondraft_pr=True), TH) == "IN REVIEW"


def test_live_job_forces_active_even_when_old():
    t = T("a")
    assert columns.column(t, {"a": t}, D(age_days=99.0, live_jobs=[{"id": 1}]), TH) == "ACTIVE"


def test_recent_commit_is_active():
    t = T("a")
    assert columns.column(t, {"a": t}, D(age_days=1.0), TH) == "ACTIVE"


def test_old_and_dirty_is_PARKED_not_active():
    """The measured miscalibration: 15 of 64 worktrees are dirty but 13 of those
    last committed 41-104 days ago. Ungated, the board lights up ~17 ACTIVE
    cards for a repo with 2 live efforts."""
    t = T("a")
    assert columns.column(t, {"a": t}, D(age_days=60.0, dirty=10), TH) == "PARKED"


def test_recent_and_dirty_is_active():
    t = T("a")
    assert columns.column(t, {"a": t}, D(age_days=5.0, dirty=3), TH) == "ACTIVE"


def test_old_and_clean_is_parked():
    t = T("a")
    assert columns.column(t, {"a": t}, D(age_days=30.0), TH) == "PARKED"


def test_unknown_age_defaults_to_active():
    t = T("a")
    assert columns.column(t, {"a": t}, D(age_days=None), TH) == "ACTIVE"


@pytest.mark.parametrize("derived,reason", [
    (D(pr={"reviewDecision": "CHANGES_REQUESTED"}), "changes_requested"),
    (D(pr={"mergeable": "CONFLICTING"}), "pr_conflicting"),
    (D(ahead=3, age_days=2.0), "unpushed"),
    (D(missing_worktree=True), "missing_worktree"),
    (D(lock_stale=True), "lock_stale"),
])
def test_needs_attention_reasons(derived, reason):
    t = T("a")
    assert reason in columns.needs_attention(t, {"a": t}, derived)


def test_empty_review_decision_is_not_an_attention_reason():
    """reviewDecision is the EMPTY STRING, not null, when there is no decision."""
    t = T("a")
    assert columns.needs_attention(t, {"a": t}, D(pr={"reviewDecision": ""})) == []


def test_stale_block_is_flagged_when_the_dependency_is_done():
    t = T("a", blocked_by=["b"])
    threads = {"a": t, "b": T("b", done=True)}
    assert "stale_block" in columns.needs_attention(t, threads, D())


def test_stale_blocks_reports_done_and_missing():
    threads = {"alpha": T("alpha", blocked_by=["beta", "ghost"]),
               "beta": T("beta", done=True)}
    got = set(columns.stale_blocks(threads))
    assert got == {("alpha", "beta", "DONE"), ("alpha", "ghost", "MISSING")}


@pytest.mark.parametrize("age,dirty,expected", [
    (5.0, 0, "PARKED"),    # idle 5d and clean -> not active
    (5.0, 3, "ACTIVE"),    # idle 5d but uncommitted work -> active
    (60.0, 10, "PARKED"),  # the measured case: old dirt is stale junk
    (1.0, 0, "ACTIVE"),    # recent commit wins regardless
])
def test_dirty_is_load_bearing(age, dirty, expected):
    """`dirty` must actually change the column. It changed nothing in 0 of 16
    age values -- the motivating measurement was unimplemented.

    Only the (5.0, 0, PARKED) case actually falsifies the pre-fix bug; the other
    three overlap existing tests and are kept for readability as a contrast set.
    Do not read the parametrisation as four independent proofs."""
    t = T("a")
    assert columns.column(t, {"a": t}, D(age_days=age, dirty=dirty), TH) == expected


@pytest.mark.parametrize("age,dirty,expected", [
    (8.0, 0, "ACTIVE"),    # config says <10d is recent, so 8d IS recent
    (8.0, 9, "ACTIVE"),
    (11.0, 0, "PARKED"),   # past active_commit_days -> idle
    (11.0, 9, "PARKED"),   # dirt band [10,7) is empty, so dirt cannot rescue it
])
def test_inverted_thresholds_have_defined_semantics(age, dirty, expected):
    """CHARACTERISATION test, not a regression test -- it pins behaviour, it does
    not discriminate this fix from its predecessors.

    With active_commit_days > parked_idle_days the dirt band degenerates to empty
    and active_commit_days alone decides. That is coherent, not a bug: an earlier
    version asserted PARKED for age=8, contradicting the user's own config saying
    anything under 10 days is recent.

    Structural limit, verified by reimplementing all three historical versions of
    column() and running these four cases against each: they produce IDENTICAL
    output under the pre-fix, round-1-clamped, and final logic. Rule 1
    (age < active_days) absorbs the whole zone where rule 3's cutoff choice would
    differ, so NO age value under an inverted config can discriminate that line.
    The value here is catching a future gross regression (an unconditional
    `if dirty: ACTIVE`, or a dirt_days larger than 11), not proving this diff."""
    t = T("a")
    bad = {"active_commit_days": 10, "parked_idle_days": 7,
           "needs_attention_idle_hours": 24}
    assert columns.column(t, {"a": t}, D(age_days=age, dirty=dirty), bad) == expected


def test_a_done_thread_does_not_advertise_a_stale_block():
    a = T("a", done=True, blocked_by=["b"])
    b = T("b", done=True)
    threads = {"a": a, "b": b}
    assert columns.needs_attention(a, threads, D()) == []
    assert columns.stale_blocks(threads) == []


def test_a_done_thread_does_not_advertise_a_dangling_blocker():
    """DONE threads suppress dangling_blocker just as they suppress stale_block,
    mirroring stale_blocks() which skips DONE threads entirely."""
    a = T("a", done=True, blocked_by=["ghost"])
    assert columns.needs_attention(a, {"a": a}, D()) == []


def test_attention_reasons_are_deduplicated():
    a = T("a", blocked_by=["b", "c"])
    threads = {"a": a, "b": T("b", done=True), "c": T("c", done=True)}
    assert columns.needs_attention(a, threads, D()).count("stale_block") == 1


def test_block_cycle_is_detected_and_does_not_recurse_forever():
    threads = {"a": T("a", blocked_by=["b"]), "b": T("b", blocked_by=["a"])}
    cycles = columns.block_cycles(threads)
    assert cycles and set(cycles[0]) == {"a", "b"}
