import json
import os
import re

import pytest

from agent_board import config, timeutil


def test_utcnow_z_format():
    ts = timeutil.utcnow_z()
    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$", ts), ts


def test_defaults_have_exactly_the_documented_leaf_keys():
    leaves = set()

    def walk(d, prefix=""):
        for k, v in d.items():
            path = "%s%s" % (prefix, k)
            if isinstance(v, dict):
                walk(v, path + ".")
            else:
                leaves.add(path)

    walk(config.DEFAULTS)
    assert leaves == {
        "config_version",
        "project.name", "project.default_branch",
        "storage.mode", "storage.threads_dir", "storage.fsync",
        "forge.cli", "forge.remote", "forge.cache_ttl_seconds",
        "jobs.scheduler", "jobs.cache_ttl_seconds",
        "thresholds.active_commit_days", "thresholds.parked_idle_days",
        "thresholds.needs_attention_idle_hours",
        "collisions.enabled", "collisions.ignore_globs_extra",
        "render.engine",
        "scan.workers",
    }


def test_no_derived_enablement_keys():
    # forge/jobs enablement is DERIVED, never configured -- it caused two real
    # detection bugs. collisions.enabled is a legitimate user preference.
    assert "enabled" not in config.DEFAULTS["forge"]
    assert "enabled" not in config.DEFAULTS["jobs"]
    assert config.DEFAULTS["collisions"]["enabled"] is True


def test_no_replaceable_ignore_globs_key():
    # A replaceable list would silently drop all 30 defaults when a user adds one.
    assert "ignore_globs" not in config.DEFAULTS["collisions"]
    assert config.DEFAULTS["collisions"]["ignore_globs_extra"] == []


def test_deep_merge_merges_dicts_but_replaces_lists():
    base = {"a": {"x": 1, "y": 2}, "l": [1, 2, 3]}
    over = {"a": {"y": 9}, "l": [7]}
    out = config.deep_merge(base, over)
    assert out == {"a": {"x": 1, "y": 9}, "l": [7]}
    assert base == {"a": {"x": 1, "y": 2}, "l": [1, 2, 3]}  # not mutated


def test_missing_config_file_yields_defaults(tmp_path):
    cfg = config.load_config(str(tmp_path))
    assert cfg["thresholds"]["active_commit_days"] == 3
    assert cfg["scan"]["workers"] == 8


def test_project_config_file_overrides_defaults(tmp_path):
    (tmp_path / ".agent-board.json").write_text(
        json.dumps({"thresholds": {"active_commit_days": 10}}))
    cfg = config.load_config(str(tmp_path))
    assert cfg["thresholds"]["active_commit_days"] == 10
    assert cfg["thresholds"]["parked_idle_days"] == 7  # sibling default survives


def test_env_overrides_beat_config_file(tmp_path, monkeypatch):
    (tmp_path / ".agent-board.json").write_text(
        json.dumps({"project": {"default_branch": "from-file"}}))
    monkeypatch.setenv("ABD_DEFAULT_BRANCH", "from-env")
    cfg = config.load_config(str(tmp_path))
    assert cfg["project"]["default_branch"] == "from-env"


def test_corrupt_config_file_falls_back_to_defaults_without_raising(tmp_path):
    (tmp_path / ".agent-board.json").write_text("{not json")
    cfg = config.load_config(str(tmp_path))
    assert cfg["scan"]["workers"] == 8
    assert cfg["_problems"], "a corrupt config must be reported, not silently ignored"


@pytest.mark.parametrize("body", ["[1, 2, 3]", '"a string"', "null", "42"])
def test_valid_json_that_is_not_an_object_is_reported(tmp_path, body):
    """Falling back to defaults is right; doing it silently is not."""
    (tmp_path / ".agent-board.json").write_text(body)
    cfg = config.load_config(str(tmp_path))
    assert cfg["scan"]["workers"] == 8
    assert cfg["_problems"], "a non-dict config must be reported"


def test_unreadable_config_file_is_reported(tmp_path):
    if os.getuid() == 0:
        pytest.skip("root bypasses file permissions")
    p = tmp_path / ".agent-board.json"
    p.write_text('{"scan": {"workers": 2}}')
    p.chmod(0o000)
    try:
        cfg = config.load_config(str(tmp_path))
    finally:
        p.chmod(0o600)          # so tmp_path cleanup cannot fail
    assert cfg["scan"]["workers"] == 8, "must not inherit the unreadable value"
    assert cfg["_problems"], "an unreadable config must be reported"


def test_absent_config_file_reports_no_problem(tmp_path):
    """The contrast that makes the two tests above meaningful: a missing file is
    the normal case and must stay silent."""
    assert config.load_config(str(tmp_path))["_problems"] == []
