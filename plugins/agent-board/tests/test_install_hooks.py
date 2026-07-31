import io
import json
import os

from agent_board import install


def _read(path):
    with io.open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def test_hook_entries_match_the_plugin_manifest():
    """install-hooks writes the SAME two entries as hooks/hooks.json, with
    ${CLAUDE_PLUGIN_ROOT} resolved -- nothing substitutes it outside the plugin
    loader. If the two drift, a fallback install behaves differently from a
    marketplace one and nobody notices."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    manifest = _read(os.path.join(here, "hooks", "hooks.json"))["hooks"]
    ours = install.hook_entries("/opt/abd/bin/abd")

    assert sorted(manifest) == sorted(ours) == ["SessionEnd", "SessionStart"]
    for event in manifest:
        assert manifest[event][0]["matcher"] == ours[event][0]["matcher"]
        m_hook = manifest[event][0]["hooks"][0]
        o_hook = ours[event][0]["hooks"][0]
        assert m_hook["timeout"] == o_hook["timeout"]
        assert m_hook.get("async") == o_hook.get("async")
        assert m_hook.get("statusMessage") == o_hook.get("statusMessage")
        # same verb and the same stderr suppression, different path source
        verb = "session-start" if event == "SessionStart" else "session-end"
        assert ("hook %s 2>/dev/null" % verb) in m_hook["command"]
        assert ("hook %s 2>/dev/null" % verb) in o_hook["command"]


def test_session_end_is_async_and_session_start_is_not():
    """async on SessionEnd makes it free (measured 6440 ms -> 4397 ms); async
    stdout is DISCARDED, and SessionStart's stdout is the entire feature."""
    entries = install.hook_entries("/opt/abd/bin/abd")
    assert entries["SessionEnd"][0]["hooks"][0]["async"] is True
    assert "async" not in entries["SessionStart"][0]["hooks"][0]


def test_matchers_exclude_the_mid_life_events():
    entries = install.hook_entries("/opt/abd/bin/abd")
    start = entries["SessionStart"][0]["matcher"]
    end = entries["SessionEnd"][0]["matcher"]
    # compact excluded: a freshly-compacted context must not be re-charged
    assert "compact" not in start
    # clear/resume excluded: mid-life events would write a bogus "ended" snapshot
    # every time the user types /clear
    assert "clear" not in end and "resume" not in end


def test_install_creates_the_file_and_is_idempotent(tmp_path):
    rc, messages = install.install("local", "/opt/abd/bin/abd", str(tmp_path))
    assert rc == 0
    path = install.settings_path("local", str(tmp_path))
    data = _read(path)
    assert len(data["hooks"]["SessionStart"]) == 1
    assert any("installed" in m for m in messages)

    rc2, messages2 = install.install("local", "/opt/abd/bin/abd", str(tmp_path))
    assert rc2 == 0
    assert len(_read(path)["hooks"]["SessionStart"]) == 1     # not duplicated
    assert any("already installed" in m for m in messages2)


def test_install_replaces_a_stale_agent_board_entry_not_appends(tmp_path):
    path = install.settings_path("local", str(tmp_path))
    os.makedirs(os.path.dirname(path))
    with io.open(path, "w", encoding="utf-8") as fh:
        json.dump({"hooks": {"SessionStart": [
            {"matcher": "startup", "hooks": [
                {"type": "command", "command": '"/old/path/abd" hook session-start'}]}
        ]}}, fh)
    assert install.install("local", "/new/abd", str(tmp_path))[0] == 0
    entries = _read(path)["hooks"]["SessionStart"]
    assert len(entries) == 1
    assert "/new/abd" in entries[0]["hooks"][0]["command"]


def test_install_preserves_foreign_hooks_in_the_same_event(tmp_path):
    path = install.settings_path("local", str(tmp_path))
    os.makedirs(os.path.dirname(path))
    foreign = {"matcher": "startup", "hooks": [
        {"type": "command", "command": "echo somebody-elses-hook"}]}
    with io.open(path, "w", encoding="utf-8") as fh:
        json.dump({"hooks": {"SessionStart": [foreign]},
                   "model": "opus", "permissions": {"allow": ["Bash"]}}, fh)
    assert install.install("local", "/opt/abd/bin/abd", str(tmp_path))[0] == 0
    data = _read(path)
    assert foreign in data["hooks"]["SessionStart"]
    assert len(data["hooks"]["SessionStart"]) == 2
    assert data["model"] == "opus"                    # unrelated keys untouched
    assert data["permissions"] == {"allow": ["Bash"]}


def test_install_refuses_to_clobber_malformed_json(tmp_path):
    """A parse error is not licence to replace a file that may hold settings this
    tool knows nothing about."""
    path = install.settings_path("local", str(tmp_path))
    os.makedirs(os.path.dirname(path))
    with io.open(path, "w", encoding="utf-8") as fh:
        fh.write('{"hooks": {"SessionStart": [ ,,, ')
    rc, messages = install.install("local", "/opt/abd/bin/abd", str(tmp_path))
    assert rc == 2
    assert "left unchanged" in " ".join(messages)
    with io.open(path, "r", encoding="utf-8") as fh:
        assert fh.read() == '{"hooks": {"SessionStart": [ ,,, '


def test_install_refuses_a_non_object_settings_file(tmp_path):
    path = install.settings_path("local", str(tmp_path))
    os.makedirs(os.path.dirname(path))
    with io.open(path, "w", encoding="utf-8") as fh:
        fh.write("[1, 2, 3]")
    rc, _messages = install.install("local", "/opt/abd/bin/abd", str(tmp_path))
    assert rc == 2


def test_unknown_scope_is_rejected(tmp_path):
    rc, messages = install.install("global", "/opt/abd/bin/abd", str(tmp_path))
    assert rc == 2 and "unknown scope" in messages[0]


def test_scope_paths(tmp_path):
    home = str(tmp_path / "home")
    assert install.settings_path("user", str(tmp_path), home=home) == \
        os.path.join(home, ".claude", "settings.json")
    assert install.settings_path("project", str(tmp_path)) == \
        os.path.join(str(tmp_path), ".claude", "settings.json")
    assert install.settings_path("local", str(tmp_path)) == \
        os.path.join(str(tmp_path), ".claude", "settings.local.json")


def _isolate_git_ignores(monkeypatch, tmp_path):
    """Neutralise the developer's own global excludes file.

    On this machine ~/.config/git/ignore ALREADY ignores
    .claude/settings.local.json -- which is the very reason the spec says not to
    assume the file is ignored. Without this isolation the 'writes info/exclude'
    test fails outright and, worse, the 'already ignored' test below passes for
    the wrong reason, certifying nothing about the repo-level rule it claims to
    test.
    """
    home = tmp_path / "fake-home"
    home.mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(home))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(home))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", os.devnull)
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", os.devnull)


def test_exclude_writes_info_exclude_and_never_touches_gitignore(
        repo_with_worktrees, monkeypatch, tmp_path):
    """.gitignore is TRACKED -- appending to it is exactly the unrequested diff
    that gets committed into a public repo. info/exclude is per-clone."""
    main, _wts = repo_with_worktrees
    _isolate_git_ignores(monkeypatch, tmp_path)
    gitignore = main / ".gitignore"
    gitignore.write_text("*.pyc\n")
    before = gitignore.read_text()
    common = str(main / ".git")

    written = install.ensure_excluded(common, str(main))
    assert written and written.endswith(os.path.join("info", "exclude"))
    assert install.EXCLUDE_REL in io.open(written).read()
    assert gitignore.read_text() == before

    # idempotent: a second call must not add the line twice
    install.ensure_excluded(common, str(main))
    assert io.open(written).read().count(install.EXCLUDE_REL) == 1


def test_exclude_is_skipped_when_already_ignored(repo_with_worktrees, monkeypatch,
                                                 tmp_path):
    main, _wts = repo_with_worktrees
    _isolate_git_ignores(monkeypatch, tmp_path)
    # Control: with no rule at all, ensure_excluded WOULD write. Asserting that
    # first is what makes the None below evidence of the repo rule being honoured
    # rather than of check-ignore silently failing.
    assert install.ensure_excluded(str(main / ".git"), str(main)) is not None
    os.remove(os.path.join(str(main / ".git"), "info", "exclude"))
    (main / ".gitignore").write_text(".claude/settings.local.json\n")
    assert install.ensure_excluded(str(main / ".git"), str(main)) is None
