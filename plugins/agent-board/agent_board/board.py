import os
import time

from agent_board import events as events_mod, model
from agent_board.config import CONFIG_NAME, DEFAULTS, load_config
from agent_board.derive import collisions
from agent_board.derive import columns as coldef
from agent_board.derive import forge, git_, jobs
from agent_board.render.layout import COLUMN_ORDER


SNAPSHOT_NAME = "board.json"
CARD_EVENTS = 3


def _age_days(committed_at):
    if not committed_at:
        return None
    return max(0.0, (time.time() - committed_at) / 86400.0)


def _rel(committed_at):
    age = _age_days(committed_at)
    if age is None:
        return "never"
    if age < 1 / 24.0:
        return "%dm ago" % max(1, int(age * 1440))
    if age < 1:
        return "%dh ago" % int(age * 24)
    return "%dd ago" % int(age)


def derive_thread(t, rows, wt_index, cfg, forge_data=None, jobs_data=None):
    """Recompute every display field. Nothing here is ever persisted."""
    d = {"has_open_nondraft_pr": False, "pr": None, "live_jobs": [],
         "dirty": 0, "ahead": 0, "behind": 0, "age_days": None,
         "missing_worktree": False, "lock_stale": False, "high_collision": False}
    d["live_jobs"] = ((jobs_data or {}).get("by_thread") or {}).get(t.get("id")) or []
    wt_lines, notes = [], []
    newest = None
    branch_refs = []
    for entry in t.get("worktrees") or []:
        path = entry.get("path")
        if not path:
            continue
        if not os.path.isdir(path):
            d["missing_worktree"] = True
            notes.append("missing worktree %s" % os.path.basename(path.rstrip("/")))
            continue
        rp = os.path.realpath(path)
        if rp not in wt_index:
            # `path` is agent-written and may point anywhere on disk,
            # including into a repo this project does not own. Probing it
            # with git_.status_v2 would trust THAT repo's own config (git
            # treats a repo's config as trusted code -- core.fsmonitor names
            # an executable git runs on `status`). Never call into a path
            # that this repo's own `git worktree list` does not know about;
            # treat it exactly like a missing worktree instead.
            d["missing_worktree"] = True
            notes.append("not a worktree of this repo: %s"
                         % os.path.basename(path.rstrip("/")))
            continue
        meta = wt_index[rp]
        if meta.get("prunable"):
            d["missing_worktree"] = True
            notes.append("prunable worktree %s" % os.path.basename(path.rstrip("/")))
            continue
        branch = meta.get("branch")            # short form -- DISPLAY only
        branch_ref = meta.get("branch_ref")     # full refs/heads/... -- IDENTITY
        # `rows` (git_.branch_rows) is keyed on the full ref. Looking up by
        # the short/display name was the F5 bug: `feature/auth` and a flat
        # `auth` both display-collapse to a basename, so a flat sibling with
        # the same tail silently substituted its ahead/behind onto the wrong
        # card (and the branch NAME shown was wrong too).
        row = rows.get(branch_ref) if branch_ref else None
        status = git_.status_v2(path)
        # Exclude our own config from the dirty COUNT as well. Left in, an
        # `abd init` in a clean repo made every thread owning that worktree look
        # dirty, which silently reclassified PARKED cards as ACTIVE -- the tool
        # perturbing the measurement it exists to report.
        dirty = len([f for f in status["dirty"]
                     if os.path.basename(f) != CONFIG_NAME])
        d["dirty"] += dirty
        ahead = (row or {}).get("ahead")
        behind = (row or {}).get("behind")
        d["ahead"] += ahead or 0
        d["behind"] += behind or 0
        committed_at = (row or {}).get("committed_at")
        if committed_at and (newest is None or committed_at > newest):
            newest = committed_at
        if branch:
            branch_refs.append(branch)
        wt_lines.append("%s  +%s -%s *%d  %s" % (
            branch or "(detached)",
            "?" if ahead is None else ahead,
            "?" if behind is None else behind,
            dirty, _rel(committed_at)))
    d["age_days"] = _age_days(newest)

    # PR mapping is by BRANCH, and a detached worktree has none -- it is excluded
    # rather than guessed at.
    prs = (forge_data or {}).get("prs") or {}
    merged = set((forge_data or {}).get("merged") or [])
    for name in branch_refs:
        pr = prs.get(name)
        if pr:
            d["pr"] = pr
            # Draft PRs deliberately do NOT put a thread IN REVIEW: nobody is
            # waiting on the human yet.
            if not pr.get("isDraft"):
                d["has_open_nondraft_pr"] = True
            break
    if d["pr"] is None:
        for name in branch_refs:
            if name in merged:
                # The squash-merge remedy: a landed branch reports its full
                # changed set forever under squash, so surface it as "mark this
                # done" and let R1 absorb the rest once they do.
                d["pr"] = {"state": "MERGED", "number": None, "isDraft": False}
                break
    return d, wt_lines, notes


def build_board(threads_dir, repo, cfg=None, allow_probe=True,
                write_cache=True, include_unowned=False):
    cfg = cfg or load_config(repo)
    thresholds = cfg.get("thresholds") or DEFAULTS["thresholds"]
    threads = model.load_all(threads_dir)

    base = git_.default_branch(repo, (cfg.get("project") or {}).get("default_branch"),
                               (cfg.get("forge") or {}).get("remote") or "origin")
    rows = git_.branch_rows(repo, base) if base else {}
    wt_index = {}
    for row in git_.list_worktrees(repo):
        if row.get("bare"):
            continue
        wt_index[os.path.realpath(row["worktree"])] = row

    forge_data = forge.load(threads_dir, repo, cfg, allow_probe=allow_probe)
    jobs_data = jobs.load(threads_dir, cfg, threads, allow_probe=allow_probe)

    # PASS 1 -- per-thread derivation and columns. Collision severity CONSUMES
    # the column, so every column must exist before any pair is scored.
    derived, wt_lines_by, notes_by, columns = {}, {}, {}, {}
    for tid in sorted(threads):
        t = threads[tid]
        d, wt_lines, notes = derive_thread(t, rows, wt_index, cfg,
                                           forge_data=forge_data,
                                           jobs_data=jobs_data)
        derived[tid], wt_lines_by[tid], notes_by[tid] = d, wt_lines, notes
        columns[tid] = coldef.column(t, threads, d, thresholds)

    # PASS 2 -- collisions over the worktrees of non-DONE threads only. The cap is
    # the performance rule from the spec: a full 64-worktree scan is 2.5 s.
    scan_paths = set()
    for tid, t in threads.items():
        if columns.get(tid) == "DONE":
            continue
        for entry in t.get("worktrees") or []:
            path = entry.get("path") if isinstance(entry, dict) else None
            if isinstance(path, str) and path:
                real = os.path.realpath(path)
                if real in wt_index and not wt_index[real].get("prunable"):
                    scan_paths.add(real)
    coll = collisions.detect(threads_dir, threads, columns, scan_paths, base, cfg,
                             write_cache=write_cache)
    high = collisions.high_by_thread(coll["collisions"])

    # PASS 3 -- badges, now that high_collision is known.
    out = {name: [] for name in COLUMN_ORDER}
    for tid in sorted(threads):
        t = threads[tid]
        d = derived[tid]
        d["high_collision"] = bool(high.get(tid))
        reasons = coldef.needs_attention(t, threads, d)
        badges = []
        if reasons:
            # Join `reasons` as-is. needs_attention already dedupes and returns a
            # deterministic order; re-sorting here made the rendered badge disagree
            # with the `attention` list on the same card, which defeats the point of
            # show reusing the board's derivation instead of recomputing it.
            badges.append(("needs_attention", ", ".join(reasons)))
        if d["live_jobs"]:
            badges.append(("live_jobs", jobs.summarize(d["live_jobs"])))
        notes = notes_by[tid]
        if t["_status"] != "ok":
            notes = notes + ["%s: %s" % (t["_status"],
                                         "; ".join(t.get("_problems") or []))]
        out[columns[tid]].append({
            "id": tid,
            "title": t.get("title") or tid,
            "goal": t.get("goal"),
            "next_action": t.get("next_action"),
            "badges": badges,
            "worktrees": wt_lines_by[tid],
            "notes": notes,
            "pr": d.get("pr"),
            # Structured alongside the rendered badge string: `abd show --json`
            # and any other consumer needs the reasons as a list, not as prose
            # they would have to re-split.
            "attention": reasons,
            "jobs": d["live_jobs"],
            "column": columns[tid],
            # The display budget: 3 on a card, 10 injected at session start, 50 in
            # `abd show`. Loading 30 threads' events was measured at 0.011 s --
            # three orders of magnitude under one `git status`, so this is free
            # relative to what the render already pays for.
            "events": events_mod.read_thread_events(threads_dir, tid, CARD_EVENTS),
            # The real paths, for FILTER. The rendered `worktrees` lines carry the
            # BRANCH plus ahead/behind/dirty counters and a relative timestamp --
            # no path at all -- so filtering on them matched "0" and "ago" against
            # everything while never matching the path the help text promises.
            "worktree_paths": [w.get("path") for w in (t.get("worktrees") or [])
                               if isinstance(w, dict) and w.get("path")],
        })

    # None, not [] -- the two must be distinguishable. A snapshot written without
    # --all carries "no data"; [] means "looked, found none". Collapsing them let
    # `--all --cached` positively claim every worktree was owned.
    unowned = None
    if include_unowned:
        unowned = []
        owned = set()
        for t in threads.values():
            for entry in t.get("worktrees") or []:
                path = entry.get("path") if isinstance(entry, dict) else None
                if isinstance(path, str) and path:
                    owned.add(os.path.realpath(path))
        for real, meta in sorted(wt_index.items()):
            if real in owned or meta.get("prunable"):
                continue
            # git does NOT report prunable for a worktree that was locked and then
            # deleted, so porcelain still lists it and it would be offered for
            # adoption. The owned path has this same isdir guard (above); the
            # unowned path lacked it, and probing a vanished dir also fatals.
            if not os.path.isdir(real):
                continue
            status = git_.status_v2(real)
            row = rows.get(meta.get("branch_ref")) if meta.get("branch_ref") else None
            unowned.append({
                "path": real,
                "branch": meta.get("branch"),
                "ahead": (row or {}).get("ahead"),
                "behind": (row or {}).get("behind"),
                "dirty": len(status["dirty"]),
                "last_commit": _rel((row or {}).get("committed_at")),
            })

    return {
        "unowned": unowned,
        "meta": {"project": os.path.basename(os.path.abspath(repo)),
                 "branch": base or "?",
                 "head": (git_._git(repo, "rev-parse", "--short", "HEAD") or "?").strip(),
                 "open": sum(len(v) for k, v in out.items() if k != "DONE"),
                 "live_jobs": sum(len(v) for v in
                                  (jobs_data.get("by_thread") or {}).values()),
                 "collisions": len(coll["collisions"]),
                 "clock": time.strftime("%H:%M", time.localtime())},
        "columns": out,
        "collisions": coll["collisions"],
        "signals": {
            "forge": {"cli": forge_data.get("cli"), "stale": forge_data.get("stale"),
                      "error": forge_data.get("error")},
            "jobs": {"scheduler": jobs_data.get("scheduler"),
                     "error": jobs_data.get("error"),
                     "unattributed": len(jobs_data.get("unattributed") or [])},
            # The rows themselves, for `abd board --unattributed`. Kept out of the
            # jobs block above so the footer's count stays a count -- but the list
            # has to exist somewhere, or that view silently prints "none".
            "unattributed_jobs": jobs_data.get("unattributed") or [],
            # Logged on every render so drift in the two unvalidated ubiquity
            # constants is visible and they can be retuned on a noisier repo.
            "collisions": {"demote_at": coll["demote_at"],
                           "demoted": len(coll["demoted"]),
                           "considered": coll["considered"],
                           "degraded": coll["degraded"],
                           "failed_probes": len(coll["failed_probes"])},
            "stale_blocks": coldef.stale_blocks(threads),
            "block_cycles": coldef.block_cycles(threads),
        },
    }
