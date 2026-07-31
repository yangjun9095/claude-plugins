"""Live scheduler jobs, attributed to threads.

Attribution is by DECLARED name prefix first, and that ordering is empirical, not
stylistic: over 30 days only 53 of 728 jobs (7.3%) ran from a directory under any
worktree. The other 92.7% ran from scratch and results trees no worktree prefix
will ever match, so a WorkDir-only scheme reports "no jobs" for almost everything.

Jobs are a per-thread liveness badge, never a collision card. The unattributed
bucket is on-demand only -- at 675 of 728 it is noise.
"""
import os
import shutil
import subprocess

from agent_board import cache

CACHE_NAME = "jobs.json"
PROBE_TIMEOUT = 3
SQUEUE_FORMAT = "%i|%j|%T|%M|%P|%Z"


def detect_scheduler(configured="auto"):
    if configured and configured not in ("auto", "none"):
        return configured if shutil.which(_binary(configured)) else None
    if configured == "none":
        return None
    for name, binary in (("slurm", "squeue"), ("pbs", "qstat"), ("lsf", "bjobs")):
        if shutil.which(binary):
            return name
    return None


def _binary(scheduler):
    return {"slurm": "squeue", "pbs": "qstat", "lsf": "bjobs"}.get(scheduler, scheduler)


def current_user():
    """`squeue -u ""` returns ZERO rows while hundreds of jobs are queued, so an
    unset USER would silently report "no jobs" -- a wrong answer that looks like
    a correct one."""
    import getpass
    for key in ("USER", "LOGNAME"):
        value = os.environ.get(key)
        if value:
            return value
    try:
        return getpass.getuser()
    except Exception:
        return None


def probe_slurm(user):
    """(jobs, error). A format string, not --json: it works on every Slurm
    version, is 2x faster, and avoids the 23.02 job_state string->list change."""
    if not user:
        return [], "no user could be determined"
    try:
        proc = subprocess.run(["squeue", "-u", user, "-h", "-o", SQUEUE_FORMAT],
                              capture_output=True, text=True, timeout=PROBE_TIMEOUT)
    except subprocess.TimeoutExpired:
        # Distinguishable from "no jobs" on purpose.
        return [], "job probe timed out"
    except (subprocess.SubprocessError, OSError) as exc:
        return [], str(exc)
    if proc.returncode != 0:
        return [], "squeue rc=%d" % proc.returncode
    jobs = []
    for line in (proc.stdout or "").splitlines():
        parts = line.split("|")
        if len(parts) < 6:
            continue
        jobs.append({"id": parts[0].strip(), "name": parts[1].strip(),
                     "state": parts[2].strip(), "elapsed": parts[3].strip(),
                     "partition": parts[4].strip(), "workdir": parts[5].strip()})
    return jobs, None


def attribute(job, threads):
    """(thread_id, how). Declared prefix beats WorkDir; longest match wins.

    Longest-prefix is required, not a nicety: '/x/agenticCRE' is a genuine string
    AND path prefix of '/x/agenticCRE-ui-redesign', and Claude Code's own
    worktrees land at <repo>/.claude/worktrees/<name> -- nested inside the parent.
    First-match on unordered iteration attributes the nested job to the parent.
    """
    ordered = sorted(threads.items(),
                     key=lambda kv: -len((kv[1].get("job_name_prefix") or "")))
    name = job.get("name") or ""
    for tid, t in ordered:
        prefix = t.get("job_name_prefix")
        if prefix and name.startswith(prefix):
            return tid, "name"

    workdir = job.get("workdir")
    if not workdir:
        return None, "unattributed"
    real = os.path.realpath(workdir)
    candidates = []
    for tid, t in threads.items():
        for entry in t.get("worktrees") or []:
            path = entry.get("path") if isinstance(entry, dict) else None
            if isinstance(path, str) and path:
                candidates.append((os.path.realpath(path), tid))
    for path, tid in sorted(candidates, key=lambda p: -len(p[0])):
        if real == path or real.startswith(path + os.sep):
            return tid, "workdir"
    return None, "unattributed"


def summarize(jobs):
    """'2 jobs: 1 RUNNING 1 PENDING' -- states in descending count, then name,
    so the badge text is stable between renders."""
    if not jobs:
        return ""
    counts = {}
    for job in jobs:
        state = job.get("state") or "?"
        counts[state] = counts.get(state, 0) + 1
    parts = ["%d %s" % (n, s) for s, n in
             sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]
    return "%d job%s: %s" % (len(jobs), "" if len(jobs) == 1 else "s",
                             " ".join(parts))


def load(threads_dir, cfg, threads, allow_probe=True):
    """Cached, attributed jobs.

    Returns {"by_thread": {tid: [job]}, "unattributed": [job],
             "scheduler": name|None, "error": str|None, "stale": bool}.
    """
    ttl = int(((cfg.get("jobs") or {}).get("cache_ttl_seconds")) or 60)
    payload, age, fresh = cache.read(threads_dir, CACHE_NAME, ttl)
    raw, error, scheduler = None, None, None

    if payload is not None and fresh:
        raw = payload.get("jobs")
        scheduler = payload.get("scheduler")
        error = payload.get("error")
        stale = False
    else:
        scheduler = detect_scheduler(((cfg.get("jobs") or {}).get("scheduler")) or "auto")
        if scheduler == "slurm" and allow_probe:
            raw, error = probe_slurm(current_user())
        elif scheduler and allow_probe:
            # pbs and lsf are detected and reported, never guessed at: emitting
            # an empty list as if probed would read as "no jobs".
            raw, error = [], "%s probing is not implemented" % scheduler
        else:
            raw, error = [], None
        stale = False
        if error == "job probe timed out" and payload is not None:
            raw = payload.get("jobs") or []
            stale = True
        elif not error:
            cache.write(threads_dir, CACHE_NAME,
                        {"jobs": raw, "scheduler": scheduler, "error": error})

    by_thread, unattributed = {}, []
    for job in raw or []:
        tid, how = attribute(job, threads)
        if tid is None:
            unattributed.append(job)
        else:
            job = dict(job)
            job["attributed_by"] = how
            by_thread.setdefault(tid, []).append(job)
    return {"by_thread": by_thread, "unattributed": unattributed,
            "scheduler": scheduler, "error": error, "stale": stale}
