import io
import json
import os
import subprocess
import time

from agent_board import cache
from agent_board.derive import forge, jobs


def _store(tmp_path):
    d = tmp_path / "board"
    (d / "threads").mkdir(parents=True)
    return str(d)


class _Proc(object):
    def __init__(self, rc=0, out="", err=""):
        self.returncode, self.stdout, self.stderr = rc, out, err


# --- forge -------------------------------------------------------------------

def test_detect_cli_prefers_gh_then_glab(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/" + n)
    assert forge.detect_cli("auto") == "gh"
    monkeypatch.setattr("shutil.which", lambda n: None if n == "gh" else "/usr/bin/glab")
    assert forge.detect_cli("auto") == "glab"
    monkeypatch.setattr("shutil.which", lambda n: None)
    assert forge.detect_cli("auto") is None


def test_detect_cli_none_disables_and_explicit_must_exist(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda n: "/usr/bin/" + n)
    assert forge.detect_cli("none") is None
    assert forge.detect_cli("glab") == "glab"
    monkeypatch.setattr("shutil.which", lambda n: None)
    assert forge.detect_cli("glab") is None


def test_probe_indexes_open_prs_by_branch(monkeypatch):
    rows = [{"number": 7, "headRefName": "feat-x", "title": "T", "isDraft": False,
             "mergeable": "MERGEABLE", "reviewDecision": "APPROVED",
             "url": "u", "state": "OPEN"}]

    def fake(cmd, **kw):
        if "merged" in cmd:
            return _Proc(0, json.dumps([{"number": 3, "headRefName": "landed"}]))
        return _Proc(0, json.dumps(rows))
    monkeypatch.setattr(subprocess, "run", fake)
    prs, merged, error = forge.probe("/repo", "gh")
    assert error is None
    assert prs["feat-x"]["number"] == 7
    assert prs["feat-x"]["isDraft"] is False
    assert merged == {"landed"}


def test_probe_rc0_with_unparseable_output_is_a_FAILED_probe(monkeypatch):
    """Enablement requires parseable JSON, not merely a zero exit -- that is the
    whole reason forge.enabled is derived rather than declared."""
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: _Proc(0, "not json"))
    prs, merged, error = forge.probe("/repo", "gh")
    assert prs == {} and merged == set() and error


def test_probe_keeps_the_first_stderr_line_as_the_reason(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: _Proc(
        1, "", "HTTP 401: Bad credentials\nsecond line"))
    _prs, _merged, error = forge.probe("/repo", "gh")
    assert error == "HTTP 401: Bad credentials"


def test_probe_survives_a_timeout(monkeypatch):
    def boom(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, 10)
    monkeypatch.setattr(subprocess, "run", boom)
    prs, _merged, error = forge.probe("/repo", "gh")
    assert prs == {} and error


def test_load_serves_a_fresh_cache_without_probing(tmp_path, monkeypatch):
    store_dir = _store(tmp_path)
    cache.write(store_dir, forge.CACHE_NAME,
                {"prs": {"b": {"number": 1}}, "merged": [], "cli": "gh"})

    def explode(*a, **kw):
        raise AssertionError("probed despite a fresh cache")
    monkeypatch.setattr(forge, "probe", explode)
    out = forge.load(store_dir, "/repo", {"forge": {"cache_ttl_seconds": 300}})
    assert out["prs"]["b"]["number"] == 1
    assert out["stale"] is False


def test_load_serves_a_STALE_cache_when_the_probe_fails(tmp_path, monkeypatch):
    """Yesterday's PR state is far closer to the truth than none, and it is
    labelled rather than silently presented as current."""
    store_dir = _store(tmp_path)
    cache.write(store_dir, forge.CACHE_NAME,
                {"prs": {"b": {"number": 1}}, "merged": [], "cli": "gh"})
    old = time.time() - 10_000
    os.utime(cache.path(store_dir, forge.CACHE_NAME), (old, old))
    monkeypatch.setattr(forge, "detect_cli", lambda *a, **k: "gh")
    monkeypatch.setattr(forge, "probe", lambda *a, **k: ({}, set(), "offline"))
    out = forge.load(store_dir, "/repo", {})
    assert out["prs"]["b"]["number"] == 1
    assert out["stale"] is True
    assert out["error"] == "offline"


def test_load_reports_no_cli_without_pretending_to_know(tmp_path, monkeypatch):
    monkeypatch.setattr(forge, "detect_cli", lambda *a, **k: None)
    out = forge.load(_store(tmp_path), "/repo", {})
    assert out["prs"] == {} and out["cli"] is None and out["error"]


def test_abd_allow_network_zero_pins_to_cache(tmp_path, monkeypatch):
    store_dir = _store(tmp_path)
    monkeypatch.setenv("ABD_ALLOW_NETWORK", "0")
    monkeypatch.setattr(forge, "detect_cli", lambda *a, **k: "gh")

    def explode(*a, **kw):
        raise AssertionError("probed with ABD_ALLOW_NETWORK=0")
    monkeypatch.setattr(forge, "probe", explode)
    out = forge.load(store_dir, "/repo", {})
    assert out["prs"] == {}


def test_normalize_handles_glab_key_names():
    row = {"iid": 12, "source_branch": "x", "title": "T", "work_in_progress": True,
           "merge_status": "can_be_merged", "web_url": "u", "state": "opened"}
    out = forge._normalize(row)
    assert out["number"] == 12 and out["isDraft"] is True
    assert out["state"] == "OPENED" and out["url"] == "u"


# --- jobs --------------------------------------------------------------------

def test_attribution_prefers_declared_prefix_over_workdir():
    """Empirical, not stylistic: only 53 of 728 real jobs (7.3%) ran from under any
    worktree. A WorkDir-only scheme reports 'no jobs' for almost everything."""
    threads = {
        "named": {"job_name_prefix": "mhb_", "worktrees": []},
        "located": {"job_name_prefix": None, "worktrees": [{"path": "/w/a"}]},
    }
    job = {"name": "mhb_run_7", "workdir": "/w/a"}
    assert jobs.attribute(job, threads) == ("named", "name")


def test_attribution_longest_name_prefix_wins():
    threads = {"short": {"job_name_prefix": "mhb"},
               "long": {"job_name_prefix": "mhb_ism"}}
    assert jobs.attribute({"name": "mhb_ism_1"}, threads) == ("long", "name")


def test_attribution_longest_workdir_prefix_wins(tmp_path):
    """'/x/agenticCRE' is a genuine path prefix of '/x/agenticCRE-ui-redesign', and
    Claude Code's own worktrees nest at <repo>/.claude/worktrees/<name>. First-match
    on unordered iteration attributes the nested job to the parent."""
    parent = tmp_path / "repo"
    nested = parent / ".claude" / "worktrees" / "feat"
    nested.mkdir(parents=True)
    threads = {"parent": {"worktrees": [{"path": str(parent)}]},
               "nested": {"worktrees": [{"path": str(nested)}]}}
    assert jobs.attribute({"name": "x", "workdir": str(nested)},
                          threads) == ("nested", "workdir")


def test_attribution_does_not_match_a_sibling_sharing_a_prefix(tmp_path):
    repo = tmp_path / "repo"
    sibling = tmp_path / "repo-old"
    repo.mkdir()
    sibling.mkdir()
    threads = {"t": {"worktrees": [{"path": str(repo)}]}}
    assert jobs.attribute({"name": "x", "workdir": str(sibling)},
                          threads) == (None, "unattributed")


def test_attribution_returns_unattributed_rather_than_guessing():
    threads = {"t": {"job_name_prefix": "abc", "worktrees": [{"path": "/w"}]}}
    assert jobs.attribute({"name": "zzz", "workdir": "/elsewhere"},
                          threads) == (None, "unattributed")


def test_summarize_is_stable_and_counts_states():
    out = jobs.summarize([{"state": "RUNNING"}, {"state": "PENDING"},
                          {"state": "RUNNING"}])
    assert out == "3 jobs: 2 RUNNING 1 PENDING"
    assert jobs.summarize([{"state": "RUNNING"}]) == "1 job: 1 RUNNING"
    assert jobs.summarize([]) == ""


def test_probe_slurm_parses_the_format_string(monkeypatch):
    line = "12345|mhb_ism_1|RUNNING|1:02:03|gpu|/scratch/run\n"
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: _Proc(0, line))
    out, error = jobs.probe_slurm("me")
    assert error is None
    assert out[0]["id"] == "12345" and out[0]["name"] == "mhb_ism_1"
    assert out[0]["state"] == "RUNNING" and out[0]["workdir"] == "/scratch/run"


def test_probe_slurm_skips_short_lines_without_dying(monkeypatch):
    monkeypatch.setattr(subprocess, "run",
                        lambda cmd, **kw: _Proc(0, "garbage\n1|2|3|4|5|6\n"))
    out, error = jobs.probe_slurm("me")
    assert error is None and len(out) == 1


def test_probe_slurm_timeout_is_distinguishable_from_no_jobs(monkeypatch):
    def boom(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, 3)
    monkeypatch.setattr(subprocess, "run", boom)
    out, error = jobs.probe_slurm("me")
    assert out == [] and error == "job probe timed out"


def test_probe_slurm_refuses_to_run_without_a_user(monkeypatch):
    """`squeue -u ""` returns zero rows while hundreds of jobs are queued, so an
    unset USER would report 'no jobs' -- a wrong answer that looks correct."""
    def explode(*a, **kw):
        raise AssertionError("ran squeue with no user")
    monkeypatch.setattr(subprocess, "run", explode)
    out, error = jobs.probe_slurm(None)
    assert out == [] and error


def test_current_user_prefers_env(monkeypatch):
    monkeypatch.setenv("USER", "alice")
    assert jobs.current_user() == "alice"
    monkeypatch.delenv("USER")
    monkeypatch.setenv("LOGNAME", "bob")
    assert jobs.current_user() == "bob"


def test_load_groups_by_thread_and_buckets_the_rest(tmp_path, monkeypatch):
    store_dir = _store(tmp_path)
    monkeypatch.setattr(jobs, "detect_scheduler", lambda *a, **k: "slurm")
    monkeypatch.setattr(jobs, "probe_slurm", lambda user: ([
        {"name": "mhb_1", "state": "RUNNING", "workdir": "/x"},
        {"name": "other", "state": "PENDING", "workdir": "/y"},
    ], None))
    threads = {"t": {"job_name_prefix": "mhb_", "worktrees": []}}
    out = jobs.load(store_dir, {}, threads)
    assert len(out["by_thread"]["t"]) == 1
    assert out["by_thread"]["t"][0]["attributed_by"] == "name"
    assert len(out["unattributed"]) == 1


def test_load_reports_an_unimplemented_scheduler_rather_than_empty(
        tmp_path, monkeypatch):
    """Emitting [] for pbs would render exactly like 'no jobs'."""
    monkeypatch.setattr(jobs, "detect_scheduler", lambda *a, **k: "pbs")
    out = jobs.load(_store(tmp_path), {}, {})
    assert out["by_thread"] == {} and "not implemented" in (out["error"] or "")


def test_load_with_no_scheduler_is_quiet(tmp_path, monkeypatch):
    monkeypatch.setattr(jobs, "detect_scheduler", lambda *a, **k: None)
    out = jobs.load(_store(tmp_path), {}, {})
    assert out["scheduler"] is None and out["error"] is None


# --- cache -------------------------------------------------------------------

def test_cache_miss_returns_none(tmp_path):
    payload, age, fresh = cache.read(_store(tmp_path), "nope.json", 60)
    assert payload is None and age is None and fresh is False


def test_cache_roundtrip_and_expiry(tmp_path):
    store_dir = _store(tmp_path)
    assert cache.write(store_dir, "x.json", {"a": 1}) is True
    payload, age, fresh = cache.read(store_dir, "x.json", 60)
    assert payload == {"a": 1} and fresh is True and age < 60
    old = time.time() - 120
    os.utime(cache.path(store_dir, "x.json"), (old, old))
    payload, age, fresh = cache.read(store_dir, "x.json", 60)
    assert payload == {"a": 1} and fresh is False       # still served, marked stale


def test_cache_tolerates_a_corrupt_entry(tmp_path):
    store_dir = _store(tmp_path)
    os.makedirs(os.path.join(store_dir, "cache"), exist_ok=True)
    with io.open(cache.path(store_dir, "x.json"), "w", encoding="utf-8") as fh:
        fh.write("{not json")
    payload, _age, fresh = cache.read(store_dir, "x.json", 60)
    assert payload is None and fresh is False


def test_cache_write_failure_is_not_fatal(tmp_path, monkeypatch):
    monkeypatch.setattr("agent_board.store.makedirs_private",
                        lambda p: (_ for _ in ()).throw(OSError("read-only")))
    assert cache.write(_store(tmp_path), "x.json", {"a": 1}) is False
