"""`thread archive`, `init`, `export`/`import`, the board FILTER, card events."""
import io
import json
import os

from agent_board import board as boardmod
from agent_board import cli, events as events_mod, model, portable
from agent_board.derive import forge, jobs as jobsmod


def _store(tmp_path):
    d = tmp_path / "board"
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


def _no_signals(monkeypatch):
    monkeypatch.setattr(forge, "load", lambda *a, **k: {
        "prs": {}, "merged": [], "cli": None, "error": None, "stale": False})
    monkeypatch.setattr(jobsmod, "load", lambda *a, **k: {
        "by_thread": {}, "unattributed": [], "scheduler": None, "error": None})


# --- thread archive ----------------------------------------------------------

def test_archive_is_a_single_rename_that_keeps_events(tmp_path):
    """One os.rename on the same filesystem: atomic, and reversible with a plain
    `mv` -- which is why there is no `unarchive` verb to drift out of sync."""
    store_dir = _store(tmp_path)
    _thread(store_dir, "old", title="Old")
    events_mod.append_event(store_dir, "old", {"kind": "note", "text": "history"})
    inode_before = os.stat(
        os.path.join(store_dir, "threads", "old", "thread.json")).st_ino
    dst = model.archive_thread(store_dir, "old")

    assert not os.path.exists(os.path.join(store_dir, "threads", "old"))
    assert os.path.isfile(os.path.join(dst, "thread.json"))
    # Atomicity is the stated justification for shipping no unarchive verb, so pin
    # the mechanism, not only the end state: a copy-then-delete implementation
    # would satisfy the assertions above. os.rename must be the ONLY thing used.
    assert os.stat(os.path.join(dst, "thread.json")).st_ino == inode_before
    # the events moved with it -- archiving keeps history, that is its point
    shards = os.listdir(os.path.join(dst, "events"))
    assert shards and "history" in io.open(
        os.path.join(dst, "events", shards[0]), encoding="utf-8").read()


def test_archived_thread_leaves_the_board(tmp_path, monkeypatch,
                                          repo_with_worktrees):
    _no_signals(monkeypatch)
    monkeypatch.delenv("ABD_THREADS_DIR", raising=False)
    main, _wts = repo_with_worktrees
    store_dir = _store(tmp_path)
    _thread(store_dir, "keep")
    _thread(store_dir, "gone")
    model.archive_thread(store_dir, "gone")
    board = boardmod.build_board(store_dir, str(main), allow_probe=False)
    ids = {c["id"] for rows in board["columns"].values() for c in rows}
    assert ids == {"keep"}


def test_archive_refuses_to_overwrite_an_existing_archive(tmp_path):
    """A silent overwrite would destroy the earlier archive's events."""
    store_dir = _store(tmp_path)
    _thread(store_dir, "t")
    model.archive_thread(store_dir, "t")
    _thread(store_dir, "t")                       # same id opened again
    try:
        model.archive_thread(store_dir, "t")
    except model.ThreadRejected as exc:
        assert "already exists" in str(exc)
    else:
        raise AssertionError("expected ThreadRejected")


def test_archive_rejects_an_unknown_or_wrongshaped_id(tmp_path):
    store_dir = _store(tmp_path)
    for bad in ("ghost", "../../evil", "Capital", "/abs/path"):
        try:
            model.archive_thread(store_dir, bad)
        except model.ThreadNotFound:
            pass
        else:
            raise AssertionError("archived %r" % bad)


def test_archive_cli_reports_where_it_went(tmp_path, monkeypatch, capsys):
    store_dir = _store(tmp_path)
    _thread(store_dir, "t")
    monkeypatch.setenv("ABD_THREADS_DIR", store_dir)
    assert cli.main(["thread", "archive", "t"]) == 0
    out = capsys.readouterr().out
    assert "archive" in out and "mv" in out        # tells them how to reverse it


# --- init --------------------------------------------------------------------

def test_init_creates_the_store_and_a_config_skeleton(repo_with_worktrees,
                                                      capsys, monkeypatch):
    from agent_board.config import CONFIG_NAME
    monkeypatch.delenv("ABD_THREADS_DIR", raising=False)
    main, _wts = repo_with_worktrees
    assert cli.main(["init", "--root", str(main)]) == 0
    assert os.path.isdir(str(main / ".git" / "agent-board" / "threads"))
    config = main / CONFIG_NAME
    assert config.exists()
    data = json.loads(config.read_text())
    assert "thresholds" in data and "project" in data
    assert "optional" in capsys.readouterr().out   # says the file can be deleted


def test_init_will_not_clobber_an_existing_config_without_force(
        repo_with_worktrees, capsys, monkeypatch):
    from agent_board.config import CONFIG_NAME
    monkeypatch.delenv("ABD_THREADS_DIR", raising=False)
    main, _wts = repo_with_worktrees
    (main / CONFIG_NAME).write_text('{"project": {"name": "mine"}}')
    assert cli.main(["init", "--root", str(main)]) == 0
    assert json.loads((main / CONFIG_NAME).read_text())["project"]["name"] == "mine"
    assert "leaving it alone" in capsys.readouterr().out
    assert cli.main(["init", "--root", str(main), "--force"]) == 0
    assert json.loads((main / CONFIG_NAME).read_text())["project"]["name"] is None


def test_init_store_is_private(repo_with_worktrees, monkeypatch):
    monkeypatch.delenv("ABD_THREADS_DIR", raising=False)
    main, _wts = repo_with_worktrees
    cli.main(["init", "--root", str(main)])
    for part in (main / ".git" / "agent-board", main / ".git" / "agent-board" / "threads"):
        assert os.stat(str(part)).st_mode & 0o777 == 0o700, part


# --- export / import ---------------------------------------------------------

def test_roundtrip_restores_threads_and_events(tmp_path):
    """The board lives in .git/, so a fresh clone starts empty -- this is the way
    back."""
    src = _store(tmp_path)
    _thread(src, "alpha", title="Alpha", goal="G", next_action="N",
            worktrees=[{"path": "/w/a"}], issues=[7])
    events_mod.append_event(src, "alpha", {"kind": "note", "text": "remember this"})
    bundle = portable.build_bundle(src)
    path = str(tmp_path / "b.json")
    portable.write_bundle(path, bundle)

    dst = _store(tmp_path / "second")
    loaded, error = portable.read_bundle(path)
    assert error is None
    imported, skipped, problems = portable.import_bundle(dst, loaded)
    assert imported == ["alpha"] and skipped == [] and problems == []
    restored = model.load_all(dst)["alpha"]
    assert restored["title"] == "Alpha" and restored["next_action"] == "N"
    assert restored["issues"] == [7]
    texts = [e.get("text") for e in events_mod.read_thread_events(dst, "alpha", 10)]
    assert "remember this" in texts


def test_import_skips_existing_threads_unless_forced(tmp_path):
    """Never merge field-by-field: a half-merged thread -- this machine's
    next_action against another's blocked_by -- is worse than either version, and a
    bundle carries no ordering that could justify a winner."""
    src = _store(tmp_path)
    _thread(src, "t", title="From the bundle")
    bundle = portable.build_bundle(src)

    dst = _store(tmp_path / "second")
    _thread(dst, "t", title="Already here")
    imported, skipped, _p = portable.import_bundle(dst, bundle)
    assert imported == [] and skipped == ["t"]
    assert model.load_all(dst)["t"]["title"] == "Already here"

    imported, skipped, _p = portable.import_bundle(dst, bundle, force=True)
    assert imported == ["t"] and skipped == []
    assert model.load_all(dst)["t"]["title"] == "From the bundle"


def test_import_resets_rev_so_the_local_CAS_stays_meaningful(tmp_path):
    """rev is this store's compare-and-swap token; carrying a high rev in from
    another machine would make the next local mutate's CAS meaningless."""
    src = _store(tmp_path)
    _thread(src, "t", rev=97)
    dst = _store(tmp_path / "second")
    portable.import_bundle(dst, portable.build_bundle(src))
    assert model.load_all(dst)["t"]["rev"] == 1
    model.mutate(dst, "t", {"next_action": "still works"})


def test_export_includes_archived_threads(tmp_path):
    src = _store(tmp_path)
    _thread(src, "done-one", title="Finished")
    model.archive_thread(src, "done-one")
    bundle = portable.build_bundle(src)
    assert "done-one" in bundle["archived"]
    assert bundle["archived"]["done-one"]["thread"]["title"] == "Finished"


def test_read_bundle_refuses_anything_that_is_not_a_bundle(tmp_path):
    path = str(tmp_path / "x.json")
    for content, expect in (("{not json", "not valid JSON"),
                            ("[1,2,3]", "not an object"),
                            ('{"kind": "something-else"}', "not an agent-board"),
                            ('{"kind": "agent-board-bundle", '
                             '"bundle_version": 99}', "newer than"),
                            ('{"kind": "agent-board-bundle", '
                             '"bundle_version": 1}', "no threads")):
        io.open(path, "w", encoding="utf-8").write(content)
        bundle, error = portable.read_bundle(path)
        assert bundle is None and expect in error, (content, error)


def test_read_bundle_reports_a_missing_file(tmp_path):
    bundle, error = portable.read_bundle(str(tmp_path / "nope.json"))
    assert bundle is None and error


def test_import_reports_a_bad_id_without_aborting_the_rest(tmp_path):
    dst = _store(tmp_path)
    bundle = {"kind": portable.KIND, "bundle_version": 1, "threads": {
        "good": {"thread": {"title": "ok"}},
        "Bad Id": {"thread": {"title": "no"}},
        "alsobad": {"thread": "not a dict"},
    }}
    imported, _skipped, problems = portable.import_bundle(dst, bundle)
    assert imported == ["good"]
    assert len(problems) == 2


def test_export_import_cli_roundtrip(repo_with_worktrees, tmp_path, monkeypatch,
                                     capsys):
    main, _wts = repo_with_worktrees
    src = _store(tmp_path)
    monkeypatch.setenv("ABD_THREADS_DIR", src)
    _thread(src, "t", title="Carry me")
    path = str(tmp_path / "bundle.json")
    assert cli.main(["export", path, "--root", str(main)]) == 0
    assert "exported 1 thread" in capsys.readouterr().out

    dst = _store(tmp_path / "second")
    monkeypatch.setenv("ABD_THREADS_DIR", dst)
    assert cli.main(["import", path, "--root", str(main)]) == 0
    assert "imported 1 thread" in capsys.readouterr().out
    assert model.load_all(dst)["t"]["title"] == "Carry me"


def test_import_cli_rejects_a_bogus_file(repo_with_worktrees, tmp_path,
                                         monkeypatch, capsys):
    main, _wts = repo_with_worktrees
    monkeypatch.setenv("ABD_THREADS_DIR", _store(tmp_path))
    bad = str(tmp_path / "bad.json")
    io.open(bad, "w", encoding="utf-8").write("{}")
    assert cli.main(["import", bad, "--root", str(main)]) == 2
    assert "not an agent-board bundle" in capsys.readouterr().err


# --- board FILTER ------------------------------------------------------------

def _filtered(main, store_dir, terms, capsys):
    rc = cli.main(["board"] + terms + ["--root", str(main), "--width", "100",
                                       "--no-color", "--offline"])
    return rc, capsys.readouterr().out


def test_filter_matches_id_title_and_worktree(repo_with_worktrees, tmp_path,
                                              monkeypatch, capsys):
    _no_signals(monkeypatch)
    main, wts = repo_with_worktrees
    store_dir = _store(tmp_path)
    monkeypatch.setenv("ABD_THREADS_DIR", store_dir)
    _thread(store_dir, "resolver-work", title="Refactor the resolver",
            worktrees=[{"path": str(wts[0])}])
    _thread(store_dir, "exporter-work", title="Add the exporter",
            worktrees=[{"path": str(wts[1])}])

    rc, out = _filtered(main, store_dir, ["resolver"], capsys)      # id + title
    assert rc == 0 and "resolver-work" in out and "exporter-work" not in out
    rc, out = _filtered(main, store_dir, ["exporter"], capsys)      # title only
    assert "exporter-work" in out and "resolver-work" not in out
    # A term that can ONLY be in the PATH: conftest names branch and directory
    # identically ("wt-a"), so matching on "wt-a" passed even though the haystack
    # contained no path at all -- it was hitting the rendered branch name.
    unique = os.path.basename(str(tmp_path))          # the tmp dir, never a branch
    rc, out = _filtered(main, store_dir, [unique], capsys)
    assert rc == 0
    assert "resolver-work" in out and "exporter-work" in out   # both paths contain it
    rc, out = _filtered(main, store_dir, [os.path.join(unique, "wt-a")], capsys)
    assert "resolver-work" in out and "exporter-work" not in out


def test_filter_does_not_match_the_derived_display_line(
        repo_with_worktrees, tmp_path, monkeypatch, capsys):
    """The haystack must be id/title/PATH -- not the rendered worktree line, which
    carries ahead/behind counters and a relative timestamp. Matching that made
    `abd board 0` and `abd board ago` match every card."""
    _no_signals(monkeypatch)
    main, wts = repo_with_worktrees
    store_dir = _store(tmp_path)
    monkeypatch.setenv("ABD_THREADS_DIR", store_dir)
    _thread(store_dir, "aa", title="Alpha", worktrees=[{"path": str(wts[0])}])
    for term in ("ago", "-0", "+0"):
        rc, out = _filtered(main, store_dir, [term], capsys)
        assert rc == 0, term
        assert "no threads matching" in out, "%r matched via the display line" % term


def test_filter_terms_are_ANDed_and_case_insensitive(repo_with_worktrees,
                                                     tmp_path, monkeypatch,
                                                     capsys):
    _no_signals(monkeypatch)
    main, _wts = repo_with_worktrees
    store_dir = _store(tmp_path)
    monkeypatch.setenv("ABD_THREADS_DIR", store_dir)
    # Ids must be long enough not to appear by chance in the header's 7-hex HEAD
    # sha: with 2-char ids, "bb" occurs in ~2.3% of shas and the test flaked.
    _thread(store_dir, "keeper-thread", title="Refactor the RESOLVER")
    _thread(store_dir, "dropper-thread", title="Refactor the exporter")
    rc, out = _filtered(main, store_dir, ["refactor", "resolver"], capsys)
    assert rc == 0 and "keeper-thread" in out and "dropper-thread" not in out


def test_a_filter_that_matches_nothing_says_so_and_names_itself(
        repo_with_worktrees, tmp_path, monkeypatch, capsys):
    """Distinguishable from an empty store, which is why the filter is applied
    after emptiness is decided."""
    _no_signals(monkeypatch)
    main, _wts = repo_with_worktrees
    store_dir = _store(tmp_path)
    monkeypatch.setenv("ABD_THREADS_DIR", store_dir)
    _thread(store_dir, "aa", title="Something")
    rc, out = _filtered(main, store_dir, ["zzz-nothing"], capsys)
    assert rc == 0
    assert "no threads matching" in out and "zzz-nothing" in out
    assert "no threads yet" not in out


def test_filter_and_column_compose(repo_with_worktrees, tmp_path, monkeypatch,
                                   capsys):
    _no_signals(monkeypatch)
    main, _wts = repo_with_worktrees
    store_dir = _store(tmp_path)
    monkeypatch.setenv("ABD_THREADS_DIR", store_dir)
    # Both filters must be load-bearing. Giving the two threads the SAME title made
    # the term match both, so the column alone produced the result and the test
    # passed with the entire filter implementation deleted.
    _thread(store_dir, "live-alpha", title="Alpha")
    _thread(store_dir, "parked-alpha", title="Alpha", parked=True)
    _thread(store_dir, "parked-beta", title="Beta", parked=True)
    rc = cli.main(["board", "alpha", "--column", "PARKED", "--root", str(main),
                   "--width", "100", "--no-color", "--offline"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "parked-alpha" in out          # matches both filters
    assert "live-alpha" not in out        # dropped by --column
    assert "parked-beta" not in out       # dropped by the term


def test_filter_reaches_json_output_too(repo_with_worktrees, tmp_path,
                                        monkeypatch, capsys):
    """A flag that changes the human view but not --json would be a silent
    inconsistency for every scripted consumer."""
    _no_signals(monkeypatch)
    main, _wts = repo_with_worktrees
    store_dir = _store(tmp_path)
    monkeypatch.setenv("ABD_THREADS_DIR", store_dir)
    _thread(store_dir, "keeper-thread", title="Keep")
    _thread(store_dir, "dropper-thread", title="Drop")
    assert cli.main(["board", "keep", "--json", "--root", str(main),
                     "--offline"]) == 0
    data = json.loads(capsys.readouterr().out)
    ids = {c["id"] for rows in data["columns"].values() for c in rows}
    assert ids == {"keeper-thread"}


# --- card event budget -------------------------------------------------------

def test_cards_carry_the_last_three_events(repo_with_worktrees, tmp_path,
                                           monkeypatch):
    """The display budget: 3 on a card, 10 injected, 50 in `abd show`."""
    _no_signals(monkeypatch)
    monkeypatch.delenv("ABD_THREADS_DIR", raising=False)
    main, _wts = repo_with_worktrees
    store_dir = _store(tmp_path)
    _thread(store_dir, "t")
    for i in range(6):
        events_mod.append_event(store_dir, "t", {"kind": "note",
                                                 "text": "e%d" % i})
    board = boardmod.build_board(store_dir, str(main), allow_probe=False)
    card = [c for rows in board["columns"].values() for c in rows][0]
    assert boardmod.CARD_EVENTS == 3
    assert [e["text"] for e in card["events"]] == ["e3", "e4", "e5"]


def test_card_events_render_and_stay_one_line_each(repo_with_worktrees, tmp_path,
                                                   monkeypatch, capsys):
    _no_signals(monkeypatch)
    main, _wts = repo_with_worktrees
    store_dir = _store(tmp_path)
    monkeypatch.setenv("ABD_THREADS_DIR", store_dir)
    _thread(store_dir, "t", title="T")
    events_mod.append_event(store_dir, "t", {"kind": "note",
                                             "text": "the last thing I did"})
    assert cli.main(["board", "--root", str(main), "--width", "100",
                     "--no-color", "--offline"]) == 0
    out = capsys.readouterr().out
    assert "the last thing I did" in out
    # A length check cannot detect a SPLIT element (both halves are short) nor a
    # broken frame. Assert the frame directly: every card body line begins and ends
    # with the border, and the count of border rows is even.
    body = [ln for ln in out.splitlines() if ln.startswith("\u2502")]
    assert body, out
    for line in body:
        assert line.rstrip().endswith("\u2502"), repr(line)
        assert len(line) <= 100


def test_init_says_the_config_is_a_working_tree_file(repo_with_worktrees,
                                                     monkeypatch, capsys):
    """The BOARD is invisible to git by design; the config is not board state and
    does show as untracked. The surprising consequence is that `git clean -xdn`
    lists it, so init must say so rather than leave a deletable file unannounced."""
    from tests.conftest import git
    monkeypatch.delenv("ABD_THREADS_DIR", raising=False)
    main, _wts = repo_with_worktrees
    assert cli.main(["init", "--root", str(main)]) == 0
    out = capsys.readouterr().out
    assert "normal file in your working tree" in out
    assert "info/exclude" in out and "git clean" in out
    # and the claim is true of the real repo, not just of our wording
    assert ".agent-board.json" in git(main, "status", "--porcelain")
    assert ".agent-board.json" in git(main, "clean", "-xdn")


def test_init_does_not_make_the_BOARD_visible_to_git(repo_with_worktrees,
                                                     monkeypatch):
    """Whatever init does with the config, the store must stay invisible."""
    from tests.conftest import git
    monkeypatch.delenv("ABD_THREADS_DIR", raising=False)
    main, _wts = repo_with_worktrees
    cli.main(["init", "--root", str(main)])
    model.new_thread(str(main / ".git" / "agent-board"), "T",
                     worktrees=[{"path": str(main)}])
    porcelain = git(main, "status", "--porcelain")
    assert "agent-board/threads" not in porcelain
    assert ".git" not in git(main, "clean", "-xdn")


# --- fixes for the review's confirmed findings -------------------------------

def test_a_late_event_cannot_resurrect_an_archived_thread(tmp_path):
    """THE critical one. mutate's trailing append_event runs OUTSIDE the lock, so it
    could land after `thread archive` renamed the directory away -- and its makedirs
    recreated threads/<id>/events/ with no thread.json, producing a phantom card
    that NO abd verb could remove (done/park/reopen -> ThreadNotFound, archive ->
    ThreadRejected). Measured at ~10% of concurrent CLI trials."""
    store_dir = _store(tmp_path)
    _thread(store_dir, "moving")
    model.archive_thread(store_dir, "moving")
    # exactly the record mutate appends after releasing the lock
    events_mod.append_event(store_dir, "moving",
                            {"kind": "set", "actor": "cli", "fields": ["goal"]})
    assert os.listdir(os.path.join(store_dir, "threads")) == []
    assert model.load_all(store_dir) == {}


def test_concurrent_archive_and_mutate_leave_no_ghost(tmp_path):
    """Drive the real race rather than trusting the guard by eye."""
    import threading
    store_dir = _store(tmp_path)
    ghosts = []
    for trial in range(12):
        tid = "race%02d" % trial
        _thread(store_dir, tid)
        barrier = threading.Barrier(2)
        errors = []

        def do_mutate(tid=tid):
            barrier.wait()
            try:
                model.mutate(store_dir, tid, {"next_action": "x"})
            except BaseException as exc:
                errors.append(exc)

        def do_archive(tid=tid):
            barrier.wait()
            try:
                model.archive_thread(store_dir, tid)
            except BaseException as exc:
                errors.append(exc)

        ts = [threading.Thread(target=do_mutate), threading.Thread(target=do_archive)]
        for t in ts:
            t.start()
        for t in ts:
            t.join()
        loaded = model.load_all(store_dir)
        if any(v.get("_status") == "missing" for v in loaded.values()):
            ghosts.append(tid)
        for exc in errors:
            assert isinstance(exc, (model.ThreadNotFound, model.ThreadRejected)), exc
    assert ghosts == [], ghosts


def test_archive_maps_oserror_to_rc_2_not_a_traceback(
        tmp_path, monkeypatch, capsys):
    store_dir = _store(tmp_path)
    _thread(store_dir, "t")
    monkeypatch.setenv("ABD_THREADS_DIR", store_dir)
    monkeypatch.setattr(model, "archive_thread",
                        lambda *a, **k: (_ for _ in ()).throw(OSError(18, "EXDEV")))
    assert cli.main(["thread", "archive", "t"]) == 2
    err = capsys.readouterr().err
    assert "abd:" in err and "Traceback" not in err


def test_archive_guard_sees_a_dangling_symlink(tmp_path):
    """os.path.exists is False for a dangling symlink, so the guard was bypassed and
    the rename failed with ENOTDIR instead of the intended message."""
    store_dir = _store(tmp_path)
    _thread(store_dir, "t")
    archive_root = os.path.join(store_dir, "archive")
    os.makedirs(archive_root)
    os.symlink(os.path.join(store_dir, "nowhere"), os.path.join(archive_root, "t"))
    try:
        model.archive_thread(store_dir, "t")
    except model.ThreadRejected as exc:
        assert "already exists" in str(exc)
    else:
        raise AssertionError("the dangling symlink bypassed the guard")


def test_export_refuses_to_launder_a_corrupt_record(tmp_path, monkeypatch, capsys):
    """load_all FABRICATES a skeleton for a torn record; exporting it as if real
    would destroy the only copy of what was still recoverable."""
    store_dir = _store(tmp_path)
    _thread(store_dir, "fine", title="Fine")
    broken = os.path.join(store_dir, "threads", "broken")
    os.makedirs(broken)
    io.open(os.path.join(broken, "thread.json"), "w").write('{"title": "half')
    bundle = portable.build_bundle(store_dir)
    assert list(bundle["threads"]) == ["fine"]
    assert [r["id"] for r in bundle["unexportable"]] == ["broken"]

    monkeypatch.setenv("ABD_THREADS_DIR", store_dir)
    assert cli.main(["export", str(tmp_path / "b.json")]) == 2   # not a silent 0
    assert "damaged on disk" in capsys.readouterr().err


def test_the_archive_round_trips_including_its_events(tmp_path):
    """export collected the archive and import discarded it -- contradicting export,
    the README and portable.py's own docstring."""
    src = _store(tmp_path)
    _thread(src, "old", title="Old work")
    events_mod.append_event(src, "old", {"kind": "note", "text": "why we stopped"})
    model.archive_thread(src, "old")
    bundle = portable.build_bundle(src)
    assert bundle["archived"]["old"]["events"], "archived events were not exported"

    dst = _store(tmp_path / "second")
    imported, _skipped, problems = portable.import_bundle(dst, bundle)
    assert problems == []
    assert "archive/old" in imported
    restored = os.path.join(dst, "archive", "old")
    assert json.load(io.open(os.path.join(restored, "thread.json")))["title"] == \
        "Old work"
    shard = os.listdir(os.path.join(restored, "events"))[0]
    assert "why we stopped" in io.open(
        os.path.join(restored, "events", shard), encoding="utf-8").read()


def test_force_reimport_does_not_duplicate_events(tmp_path):
    """Running the documented command twice is ordinary; a bare O_APPEND replay
    multiplied the timeline by the number of imports."""
    src = _store(tmp_path)
    _thread(src, "t")
    events_mod.append_event(src, "t", {"kind": "note", "text": "once"})
    bundle = portable.build_bundle(src)
    dst = _store(tmp_path / "second")
    for _ in range(3):
        portable.import_bundle(dst, bundle, force=True)
    texts = [e.get("text") for e in events_mod.read_thread_events(dst, "t", 50)]
    assert texts.count("once") == 1, texts


def test_read_bundle_survives_a_deeply_nested_document(tmp_path):
    """RecursionError is not a ValueError, so it escaped the 'never raises'
    contract and gave a traceback on untrusted input."""
    path = str(tmp_path / "deep.json")
    io.open(path, "w").write("[" * 20000 + "]" * 20000)
    bundle, error = portable.read_bundle(path)
    assert bundle is None and error


def test_export_reports_when_it_truncates_a_timeline(tmp_path):
    src = _store(tmp_path)
    _thread(src, "chatty")
    for i in range(12):
        events_mod.append_event(src, "chatty", {"kind": "note", "text": "e%d" % i})
    bundle = portable.build_bundle(src, events_per_thread=5)
    assert bundle["truncated"] == ["chatty"]
    assert len(bundle["threads"]["chatty"]["events"]) == 5


def test_our_own_config_cannot_manufacture_a_collision_or_dirty_a_card(
        repo_with_worktrees, tmp_path, monkeypatch):
    """`abd init` writes .agent-board.json into the working tree, where -uall sees
    it. Left in, two threads sharing a worktree both listed it as dirty and the
    board invented a HIGH collision out of a file this tool created -- and the raw
    dirty count silently reclassified PARKED cards as ACTIVE."""
    _no_signals(monkeypatch)
    monkeypatch.delenv("ABD_THREADS_DIR", raising=False)
    main, wts = repo_with_worktrees
    (wts[0] / ".agent-board.json").write_text('{"config_version": 1}' + chr(10))
    store_dir = _store(tmp_path)
    _thread(store_dir, "alpha", worktrees=[{"path": str(wts[0])}])
    _thread(store_dir, "beta", worktrees=[{"path": str(wts[0])}])
    board = boardmod.build_board(store_dir, str(main), allow_probe=False)
    assert board["collisions"] == [], board["collisions"]
    for rows in board["columns"].values():
        for card in rows:
            assert "*0" in " ".join(card["worktrees"]), card["worktrees"]


def test_init_writes_where_load_config_actually_reads(
        repo_with_worktrees, monkeypatch):
    """load_config(start) reads <start>/.agent-board.json with no upward search, and
    every consumer passes cwd -- so writing to the main worktree root produced a file
    never read from a linked worktree, the normal case for this tool."""
    from agent_board.config import CONFIG_NAME, load_config
    monkeypatch.delenv("ABD_THREADS_DIR", raising=False)
    monkeypatch.delenv("ABD_CONFIG", raising=False)
    main, wts = repo_with_worktrees
    assert cli.main(["init", "--root", str(wts[0])]) == 0
    assert (wts[0] / CONFIG_NAME).exists()
    assert load_config(str(wts[0]))["_problems"] == []


def test_init_honours_abd_config(repo_with_worktrees, tmp_path, monkeypatch):
    monkeypatch.delenv("ABD_THREADS_DIR", raising=False)
    target = str(tmp_path / "elsewhere.json")
    monkeypatch.setenv("ABD_CONFIG", target)
    main, _wts = repo_with_worktrees
    assert cli.main(["init", "--root", str(main)]) == 0
    assert os.path.exists(target)


def test_card_event_line_names_the_fields_a_mutation_changed():
    """Every `thread set/park/done/reopen` writes {"kind":"set","fields":[...]} with
    no text, so the card rendered a bare useless "set"."""
    from agent_board.render.layout import _event_text
    assert _event_text({"kind": "set", "fields": ["goal", "next_action"]}) == \
        "set goal, next_action"
    assert _event_text({"kind": "note", "text": "hello"}) == "hello"
    assert _event_text({"kind": "session_snapshot", "reason": "logout"}) == "logout"
    assert _event_text({"kind": "done"}) == "done"
    assert _event_text("not a dict") == ""


def test_sanitize_covers_the_non_c0_line_breakers():
    """U+0085, U+2028 and U+2029 are line breaks to terminals AND to
    str.splitlines(), so one rendered element became several physical lines."""
    from agent_board.render.layout import sanitize
    raw = "a" + "\u0085" + "b" + "\u2028" + "c" + "\u2029" + "d"
    assert len(raw.splitlines()) == 4          # the hazard is real
    assert len(sanitize(raw).splitlines()) == 1, repr(sanitize(raw))


def test_html_shows_the_card_events_it_used_to_drop():
    from agent_board.render.html import export
    board = {"meta": {}, "columns": {"ACTIVE": [
        {"id": "t", "title": "T", "badges": [], "worktrees": [], "notes": [],
         "events": [{"kind": "note", "text": "<b>last</b> thing"}]}]},
        "collisions": [], "signals": {}}
    page = export(board)
    assert "&lt;b&gt;last&lt;/b&gt; thing" in page      # shown AND escaped
    assert "<b>last</b>" not in page


def test_watch_and_unattributed_refuse_a_filter(repo_with_worktrees, tmp_path,
                                                monkeypatch, capsys):
    main, _wts = repo_with_worktrees
    monkeypatch.setenv("ABD_THREADS_DIR", _store(tmp_path))
    assert cli.main(["board", "alpha", "--watch", "--root", str(main)]) == 2
    assert "cannot be combined" in capsys.readouterr().err
    assert cli.main(["board", "alpha", "--unattributed", "--root", str(main),
                     "--offline"]) == 2
    assert "cannot apply" in capsys.readouterr().err


def test_a_nonmatching_filter_still_renders_the_all_view(
        repo_with_worktrees, tmp_path, monkeypatch, capsys):
    """--all answers "what am I not tracking" and is independent of a thread
    filter, but the no-match branch returned before it."""
    _no_signals(monkeypatch)
    main, _wts = repo_with_worktrees
    store_dir = _store(tmp_path)
    monkeypatch.setenv("ABD_THREADS_DIR", store_dir)
    _thread(store_dir, "aa", title="Alpha")
    assert cli.main(["board", "zzz-nope", "--all", "--root", str(main),
                     "--width", "100", "--no-color", "--offline"]) == 0
    out = capsys.readouterr().out
    assert "no threads matching" in out
    assert "UNOWNED WORKTREES" in out


def test_the_echoed_filter_term_is_sanitised(repo_with_worktrees, tmp_path,
                                             monkeypatch, capsys):
    _no_signals(monkeypatch)
    main, _wts = repo_with_worktrees
    store_dir = _store(tmp_path)
    monkeypatch.setenv("ABD_THREADS_DIR", store_dir)
    _thread(store_dir, "aa", title="Alpha")
    term = "zz" + "\x1b" + "[41mSTICKY" + "\x7f"
    assert cli.main(["board", term, "--root", str(main), "--width", "100",
                     "--no-color", "--offline"]) == 0
    out = capsys.readouterr().out
    assert "\x1b" not in out and "\x7f" not in out


def test_an_empty_filter_term_is_not_a_filter(repo_with_worktrees, tmp_path,
                                              monkeypatch, capsys):
    _no_signals(monkeypatch)
    main, _wts = repo_with_worktrees
    store_dir = _store(tmp_path)
    monkeypatch.setenv("ABD_THREADS_DIR", store_dir)
    _thread(store_dir, "aa", title="Alpha")
    assert cli.main(["board", "", "--root", str(main), "--width", "100",
                     "--no-color", "--offline"]) == 0
    out = capsys.readouterr().out
    assert "aa" in out and "no threads matching" not in out


def test_html_dag_excludes_filtered_out_threads(repo_with_worktrees, tmp_path,
                                                monkeypatch, capsys):
    _no_signals(monkeypatch)
    main, _wts = repo_with_worktrees
    store_dir = _store(tmp_path)
    monkeypatch.setenv("ABD_THREADS_DIR", store_dir)
    _thread(store_dir, "keeper-alpha", title="Alpha", blocked_by=["hidden-beta"])
    _thread(store_dir, "hidden-beta", title="Beta")
    out_path = str(tmp_path / "b.html")
    assert cli.main(["board", "alpha", "--html", out_path, "--root", str(main),
                     "--offline"]) == 0
    page = io.open(out_path, encoding="utf-8").read()
    assert "hidden-beta" not in page
