import io
import json
import os

from agent_board import cli, doctor


def _by_name(rows, name):
    return [r for r in rows if r["name"] == name]


def _status(rows, name):
    hits = _by_name(rows, name)
    assert hits, "no row named %r in %r" % (name, [r["name"] for r in rows])
    return hits[0]["status"]


def _settings(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh)


# --- structural guarantees ---------------------------------------------------

def test_a_dying_check_becomes_a_fail_row_not_a_crash(monkeypatch, tmp_path):
    """Doctor reports rather than fails open. Swallowing a dead check would leave
    a silent gap in the one report whose purpose is completeness."""
    def boom(start, repo):
        raise RuntimeError("nope")

    monkeypatch.setattr(doctor, "CHECKS", (("exploder", boom),))
    rows = doctor.run_checks(str(tmp_path), str(tmp_path))
    assert len(rows) == 1
    assert rows[0]["status"] == doctor.FAIL
    assert "nope" in rows[0]["detail"]
    assert doctor.exit_code(rows) == 1


def test_exit_code_is_zero_for_warns_and_one_for_fails():
    """A warn that returned non-zero would train people to ignore the code."""
    assert doctor.exit_code([doctor._row("a", doctor.WARN, "d")]) == 0
    assert doctor.exit_code([doctor._row("a", doctor.PENDING, "d")]) == 0
    assert doctor.exit_code([doctor._row("a", doctor.OK, "d")]) == 0
    assert doctor.exit_code([doctor._row("a", doctor.WARN, "d"),
                             doctor._row("b", doctor.FAIL, "d")]) == 1


def test_format_text_includes_remedies_and_a_tally():
    rows = [doctor._row("thing", doctor.WARN, "it is off", "turn it on")]
    text = "\n".join(doctor.format_text(rows))
    assert "WARN" in text and "it is off" in text and "turn it on" in text
    assert "0 ok, 1 warn, 0 fail, 0 pending" in text


# --- anchor ------------------------------------------------------------------

def test_anchor_ok_in_a_real_repo(repo_with_worktrees):
    main, wts = repo_with_worktrees
    for path in [main] + list(wts):
        assert _status(doctor.check_anchor(str(path)), "git anchor") == doctor.OK


def test_anchor_warns_outside_a_repo(tmp_path):
    assert _status(doctor.check_anchor(str(tmp_path)), "git anchor") == doctor.WARN


def test_anchor_fails_when_the_two_resolvers_disagree(
        monkeypatch, repo_with_worktrees):
    """Not cosmetic: the hook uses the pure resolver and the CLI the subprocess
    one, so disagreement means cards written to one store and read from another."""
    main, _wts = repo_with_worktrees
    from agent_board import anchor
    monkeypatch.setattr(anchor, "git_common_dir_pure", lambda s=None: "/somewhere/else")
    rows = doctor.check_anchor(str(main))
    assert _status(rows, "git anchor") == doctor.FAIL
    assert "DISAGREE" in rows[0]["detail"]


# --- storage -----------------------------------------------------------------

def test_storage_default_mode_is_ok_and_reports_the_path(
        repo_with_worktrees, monkeypatch):
    monkeypatch.delenv("ABD_THREADS_DIR", raising=False)
    main, _wts = repo_with_worktrees
    rows = doctor.check_storage(str(main))
    assert _status(rows, "storage") == doctor.OK
    assert "agent-board" in _by_name(rows, "storage")[0]["detail"]
    assert _by_name(rows, "storage.location") == []      # nothing to complain about


def test_storage_fails_when_the_threads_dir_is_inside_the_working_tree(
        repo_with_worktrees, monkeypatch):
    """The measured regression: a relative threads_dir resolves against cwd and
    lands in the working tree, where `git status` shows it as untracked and
    `git clean -xdn` offers to delete the board."""
    main, _wts = repo_with_worktrees
    inside = main / ".abd-board"
    inside.mkdir()
    # A file, not just the directory: git reports no empty directories, so an
    # empty one would make the corroboration below vacuous.
    (inside / "active-thread").write_text("t1\n")
    monkeypatch.setenv("ABD_THREADS_DIR", str(inside))
    rows = doctor.check_storage(str(main))
    assert _status(rows, "storage.location") == doctor.FAIL
    detail = _by_name(rows, "storage.location")[0]["detail"]
    assert "INSIDE the working tree" in detail
    # The claim must be true of the real repo, not just of our string formatting.
    from tests.conftest import git
    assert ".abd-board" in git(main, "status", "--porcelain", "-uall")
    assert ".abd-board" in git(main, "clean", "-xdn")


def test_storage_does_not_flag_the_default_location_under_dot_git(
        repo_with_worktrees, monkeypatch):
    """Control for the test above: the DEFAULT store also sits under the repo
    root, and flagging it would make the check fire on every healthy install."""
    main, _wts = repo_with_worktrees
    monkeypatch.setenv("ABD_THREADS_DIR", str(main / ".git" / "agent-board"))
    rows = doctor.check_storage(str(main))
    assert _by_name(rows, "storage.location") == []


def test_storage_warns_on_a_group_readable_store(repo_with_worktrees, monkeypatch):
    main, _wts = repo_with_worktrees
    wide = main.parent / "wide-store"
    wide.mkdir()
    os.chmod(str(wide), 0o755)
    monkeypatch.setenv("ABD_THREADS_DIR", str(wide))
    rows = doctor.check_storage(str(main))
    assert _status(rows, "storage.permissions") == doctor.WARN


# --- config ------------------------------------------------------------------

def test_config_ok_when_absent(repo_with_worktrees, monkeypatch):
    monkeypatch.delenv("ABD_CONFIG", raising=False)
    main, _wts = repo_with_worktrees
    rows = doctor.check_config(str(main))
    assert _status(rows, "config") == doctor.OK
    assert "absent" in _by_name(rows, "config")[0]["detail"]


def test_config_warns_and_names_the_problem(repo_with_worktrees, monkeypatch):
    main, _wts = repo_with_worktrees
    monkeypatch.delenv("ABD_CONFIG", raising=False)
    (main / ".agent-board.json").write_text('{"storage": "not-a-section"}')
    rows = doctor.check_config(str(main))
    assert _status(rows, "config") == doctor.WARN
    assert "storage" in _by_name(rows, "config")[0]["detail"]


# --- default branch ----------------------------------------------------------

def test_default_branch_ok_with_no_remote(repo_with_worktrees, monkeypatch):
    monkeypatch.delenv("ABD_DEFAULT_BRANCH", raising=False)
    main, _wts = repo_with_worktrees
    rows = doctor.check_default_branch(str(main))
    assert _status(rows, "default branch") == doctor.OK
    assert "trunk" in _by_name(rows, "default branch")[0]["detail"]


def test_default_branch_warns_when_guessed_from_a_local_ref(
        repo_local_master_remote_trunk, monkeypatch):
    """The reproduced master-vs-trunk case: a local branch shadowing the remote
    default poisons every ahead/behind number and every merge-base."""
    monkeypatch.delenv("ABD_DEFAULT_BRANCH", raising=False)
    clone = repo_local_master_remote_trunk
    from tests.conftest import git
    # drop the remote-side refs so nothing on the remote side can resolve, while
    # the remote itself still exists -- exactly "never fetched"
    for ref in git(clone, "for-each-ref", "--format=%(refname)",
                   "refs/remotes").split():
        git(clone, "update-ref", "-d", ref)
    rows = doctor.check_default_branch(str(clone))
    assert _status(rows, "default branch") == doctor.WARN
    assert "guessed from a local ref" in _by_name(rows, "default branch")[0]["detail"]


def test_default_branch_warns_when_config_disagrees_with_the_remote(
        repo_local_master_remote_trunk, monkeypatch):
    monkeypatch.setenv("ABD_DEFAULT_BRANCH", "master")
    rows = doctor.check_default_branch(str(repo_local_master_remote_trunk))
    assert _status(rows, "default branch") == doctor.WARN
    detail = _by_name(rows, "default branch")[0]["detail"]
    assert "master" in detail and "trunk" in detail


# --- hooks -------------------------------------------------------------------

def test_hooks_manifest_is_found_in_the_shipped_plugin(tmp_path):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    rows = doctor.check_hooks(str(tmp_path), str(tmp_path))
    manifest = _by_name(rows, "hooks.manifest")[0]
    assert manifest["status"] == doctor.OK
    assert "SessionStart" in manifest["detail"] and "SessionEnd" in manifest["detail"]
    assert root in manifest["detail"]


def test_hooks_reports_settings_registration(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = tmp_path / "repo"
    _settings(str(repo / ".claude" / "settings.local.json"),
              {"hooks": {"SessionStart": [{"matcher": "startup", "hooks": [
                  {"type": "command", "command": '"/x/abd" hook session-start'}]}]}})
    rows = doctor.check_hooks(str(repo), str(repo))
    assert "local" in _by_name(rows, "hooks.settings")[0]["detail"]


def test_hooks_says_so_when_nothing_is_registered(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    rows = doctor.check_hooks(str(tmp_path), str(tmp_path))
    assert "no settings-file entries" in _by_name(rows, "hooks.settings")[0]["detail"]


def test_managed_disable_all_hooks_is_a_fail_naming_who_can_undo_it(
        tmp_path, monkeypatch):
    """The inverse risk: an org-set disableAllHooks kills the tool and ONLY
    managed settings can re-enable it, so it must be named, not merely noted."""
    managed = tmp_path / "managed.json"
    managed.write_text(json.dumps({"disableAllHooks": True}))
    monkeypatch.setattr(doctor, "MANAGED_SETTINGS", (str(managed),))
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    rows = doctor.check_hooks(str(tmp_path), str(tmp_path))
    row = _by_name(rows, "hooks.disabled")[0]
    assert row["status"] == doctor.FAIL
    assert "MANAGED" in row["detail"]
    assert "administers" in (row["remedy"] or "")


def test_local_disable_all_hooks_is_a_warn(tmp_path, monkeypatch):
    monkeypatch.setattr(doctor, "MANAGED_SETTINGS", ())
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = tmp_path / "repo"
    _settings(str(repo / ".claude" / "settings.local.json"), {"disableAllHooks": True})
    rows = doctor.check_hooks(str(repo), str(repo))
    assert _status(rows, "hooks.disabled") == doctor.WARN


def test_active_kill_switch_is_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(doctor, "MANAGED_SETTINGS", ())
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("ABD_DISABLE", "1")
    rows = doctor.check_hooks(str(tmp_path), str(tmp_path))
    assert _status(rows, "hooks.killswitch") == doctor.WARN


def test_a_malformed_settings_file_is_reported_not_fatal(tmp_path, monkeypatch):
    monkeypatch.setattr(doctor, "MANAGED_SETTINGS", ())
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    repo = tmp_path / "repo"
    path = repo / ".claude" / "settings.local.json"
    os.makedirs(str(path.parent))
    path.write_text("{not json")
    rows = doctor.check_hooks(str(repo), str(repo))
    assert _status(rows, "hooks.local") == doctor.WARN


# --- sdk launchers -----------------------------------------------------------

def test_sdk_check_flags_a_launcher_missing_plugins(tmp_path):
    """SDK sessions get no filesystem hooks; only options.plugins survives
    --setting-sources "". The remedy must carry the resolved path."""
    (tmp_path / "run.py").write_text(
        "from claude_agent_sdk import query\n"
        "opts = ClaudeAgentOptions(model='opus')\n")
    rows = doctor.check_sdk_launchers(str(tmp_path))
    row = _by_name(rows, "sdk launchers")[0]
    assert row["status"] == doctor.WARN
    assert "run.py" in row["detail"]
    assert '"type": "local"' in row["remedy"]


def test_sdk_sample_shows_shallow_paths_before_deep_archived_ones(tmp_path):
    """Alphabetical order put five _archive/ paths first on the real repo and hid
    src/agenticcre/agent.py -- the live launcher and the only one worth editing."""
    body = "from claude_agent_sdk import query\nClaudeAgentOptions()\n"
    for rel in ("_archive/a/b/one.py", "_archive/a/b/two.py", "_archive/a/b/three.py",
                "_archive/a/b/four.py", "_archive/a/b/five.py", "_archive/a/b/six.py",
                "src/live.py"):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body)
    detail = _by_name(doctor.check_sdk_launchers(str(tmp_path)),
                      "sdk launchers")[0]["detail"]
    assert "src/live.py" in detail
    assert detail.index("src/live.py") < detail.index("_archive")


def test_sdk_check_is_quiet_when_plugins_is_already_passed(tmp_path):
    (tmp_path / "run.py").write_text(
        "from claude_agent_sdk import query\n"
        "opts = ClaudeAgentOptions(plugins=[{'type':'local','path':'/x'}])\n")
    assert _status(doctor.check_sdk_launchers(str(tmp_path)),
                   "sdk launchers") == doctor.OK


def test_sdk_check_announces_its_cap_rather_than_truncating_silently(
        tmp_path, monkeypatch):
    monkeypatch.setattr(doctor, "SDK_SCAN_MAX_FILES", 2)
    for i in range(5):
        (tmp_path / ("f%d.py" % i)).write_text("x = 1\n")
    row = _by_name(doctor.check_sdk_launchers(str(tmp_path)), "sdk launchers")[0]
    assert "capped" in row["detail"]


# --- shards ------------------------------------------------------------------

def test_shard_size_warning_fires_over_the_threshold(
        repo_with_worktrees, monkeypatch):
    main, _wts = repo_with_worktrees
    store_dir = main.parent / "store"
    events = store_dir / "threads" / "t1" / "events"
    events.mkdir(parents=True)
    with io.open(str(events / "host.jsonl"), "wb") as fh:
        fh.write(b"x" * 2048)
    monkeypatch.setenv("ABD_THREADS_DIR", str(store_dir))
    monkeypatch.setattr(doctor, "SHARD_WARN_BYTES", 1024)
    rows = doctor.check_shards(str(main))
    assert _status(rows, "event shards") == doctor.WARN
    assert "host.jsonl" in _by_name(rows, "event shards")[0]["detail"]


def test_shard_check_is_ok_when_small(repo_with_worktrees, monkeypatch):
    main, _wts = repo_with_worktrees
    monkeypatch.delenv("ABD_THREADS_DIR", raising=False)
    assert _status(doctor.check_shards(str(main)), "event shards") == doctor.OK


# --- tools / interpreter -----------------------------------------------------

def test_tools_never_claims_enabled_from_mere_presence():
    """Reporting a forge as enabled because the binary exists is exactly the
    detection bug that removing *.enabled from the schema was meant to prevent."""
    rows = doctor.check_tools()
    probe = _by_name(rows, "forge/jobs probe")[0]
    assert probe["status"] == doctor.PENDING
    assert "proven by running the real command" in probe["detail"]
    for row in rows:
        assert "enabled" not in row["detail"].lower() or row["status"] != doctor.OK


def test_interpreter_check_reports_and_never_calls_rich_a_failure():
    rows = doctor.check_interpreter()
    assert _status(rows, "interpreter") == doctor.OK
    rich = _by_name(rows, "render.rich")[0]
    assert rich["status"] == doctor.OK          # plain is guaranteed, not degraded
    if "not importable" in rich["detail"]:
        assert rich["remedy"]                   # and the advice must be actionable


# --- CLI wiring --------------------------------------------------------------

def test_cli_doctor_text_output(repo_with_worktrees, capsys, monkeypatch):
    monkeypatch.delenv("ABD_DISABLE", raising=False)
    main, _wts = repo_with_worktrees
    rc = cli.main(["doctor", "--root", str(main)])
    out = capsys.readouterr().out
    assert rc in (0, 1)
    assert "git anchor" in out and "storage" in out
    assert "ok," in out and "pending" in out


def test_cli_doctor_json_output_is_parseable(repo_with_worktrees, capsys):
    main, _wts = repo_with_worktrees
    cli.main(["doctor", "--root", str(main), "--json"])
    data = json.loads(capsys.readouterr().out)
    assert isinstance(data["checks"], list) and data["checks"]
    for row in data["checks"]:
        assert set(row) == {"name", "status", "detail", "remedy"}
        assert row["status"] in (doctor.OK, doctor.WARN, doctor.FAIL, doctor.PENDING)
