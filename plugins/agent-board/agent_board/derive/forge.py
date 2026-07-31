"""PR state via `gh` / `glab`.

Enablement is PROVEN by running the real command, never inferred from the binary
existing: `gh auth status` returning 0 only shows credentials exist, not that this
repo has a resolvable remote on that host. That is why no `forge.enabled` key
exists in the config schema.

The probe is the single most expensive thing the board does (~0.6-0.7 s, roughly
90% of a cold render), so it is cached for 300 s and a stale entry is served
rather than blocking. Without it, IN REVIEW is simply never derived -- an
understatement the footer admits to, not a silent wrong answer.
"""
import json
import os
import shutil
import subprocess

from agent_board import cache

CACHE_NAME = "forge.json"
FIELDS = "number,headRefName,title,isDraft,mergeable,reviewDecision,url,state"
PROBE_TIMEOUT = 10


def detect_cli(configured="auto"):
    if configured and configured not in ("auto", "none"):
        return configured if shutil.which(configured) else None
    if configured == "none":
        return None
    for name in ("gh", "glab"):
        if shutil.which(name):
            return name
    return None


def _run(cli, repo, args):
    try:
        proc = subprocess.run([cli] + args, cwd=repo, capture_output=True,
                              text=True, timeout=PROBE_TIMEOUT,
                              env=dict(os.environ, GIT_TERMINAL_PROMPT="0",
                                       NO_COLOR="1"))
    except (subprocess.SubprocessError, OSError) as exc:
        return None, str(exc)
    if proc.returncode != 0:
        # The four distinct real stderrs (401 Bad credentials, unknown GitHub
        # host, no remotes found, GH_HOST mismatch) all mean the same thing to
        # us: unusable. Keep the first line so `abd doctor` can show WHY.
        lines = (proc.stderr or "").strip().splitlines()
        return None, lines[0] if lines else "rc=%d" % proc.returncode
    return proc.stdout, None


def _parse(text):
    try:
        rows = json.loads(text or "[]")
    except ValueError:
        return None
    return rows if isinstance(rows, list) else None


def probe(repo, cli):
    """({headRefName: pr}, {merged headRefNames}, error). Never raises."""
    if cli == "gh":
        open_args = ["pr", "list", "--state", "open", "--limit", "200",
                     "--json", FIELDS]
        merged_args = ["pr", "list", "--state", "merged", "--limit", "100",
                       "--json", "number,headRefName"]
    elif cli == "glab":
        open_args = ["mr", "list", "--opened", "--output", "json"]
        merged_args = ["mr", "list", "--merged", "--output", "json"]
    else:
        return {}, set(), "no forge cli"

    out, err = _run(cli, repo, open_args)
    if out is None:
        return {}, set(), err
    rows = _parse(out)
    if rows is None:
        # rc 0 with unparseable output is still a failed probe -- enablement
        # requires parseable JSON, not merely a zero exit.
        return {}, set(), "unparseable output from %s" % cli

    by_branch = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        branch = row.get("headRefName") or row.get("source_branch")
        if isinstance(branch, str) and branch:
            by_branch[branch] = _normalize(row)

    merged = set()
    out2, _err2 = _run(cli, repo, merged_args)
    for row in _parse(out2 or "[]") or []:
        if isinstance(row, dict):
            branch = row.get("headRefName") or row.get("source_branch")
            if isinstance(branch, str) and branch:
                merged.add(branch)
    return by_branch, merged, None


def _normalize(row):
    """One shape regardless of cli. glab uses different key names."""
    draft = row.get("isDraft")
    if draft is None:
        draft = bool(row.get("draft") or row.get("work_in_progress"))
    return {
        "number": row.get("number") or row.get("iid"),
        "title": row.get("title"),
        "isDraft": bool(draft),
        "mergeable": row.get("mergeable") or row.get("merge_status"),
        "reviewDecision": row.get("reviewDecision"),
        "url": row.get("url") or row.get("web_url"),
        "state": (row.get("state") or "OPEN").upper(),
    }


def load(threads_dir, repo, cfg, allow_probe=True):
    """Cached PR state.

    Returns {"prs": {...}, "merged": [...], "cli": name|None,
             "error": str|None, "stale": bool, "age": seconds|None}.
    """
    # The forge is the only thing here that touches the network. ABD_ALLOW_NETWORK=0
    # pins the board to cache -- checked here rather than at the call sites so
    # every entry point honours it.
    if os.environ.get("ABD_ALLOW_NETWORK") == "0":
        allow_probe = False
    ttl = int(((cfg.get("forge") or {}).get("cache_ttl_seconds")) or 300)
    payload, age, fresh = cache.read(threads_dir, CACHE_NAME, ttl)
    if payload is not None and fresh:
        payload = dict(payload)
        payload["stale"] = False
        payload["age"] = age
        return payload

    cli = detect_cli(((cfg.get("forge") or {}).get("cli")) or "auto")
    if cli is None or not allow_probe:
        if payload is not None:
            payload = dict(payload)
            payload["stale"] = True
            payload["age"] = age
            return payload
        if cli:
            # Reporting error=None here would present "no PRs" as a successful
            # answer when nothing was ever asked. The footer needs to say so.
            reason = "offline: not probed"
        else:
            reason = "no forge cli on PATH"
        return {"prs": {}, "merged": [], "cli": cli, "stale": False, "age": None,
                "error": reason}

    prs, merged, error = probe(repo, cli)
    if error and payload is not None:
        # Serve the stale entry rather than dropping to "unknown": yesterday's
        # PR state is far closer to the truth than none, and it is labelled.
        payload = dict(payload)
        payload.update({"stale": True, "age": age, "error": error})
        return payload
    fresh_payload = {"prs": prs, "merged": sorted(merged), "cli": cli,
                     "error": error}
    if not error:
        cache.write(threads_dir, CACHE_NAME, fresh_payload)
    fresh_payload["stale"] = False
    fresh_payload["age"] = 0.0
    return fresh_payload
