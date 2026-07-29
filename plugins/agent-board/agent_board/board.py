import os
import time

from agent_board import model
from agent_board.config import DEFAULTS, load_config
from agent_board.derive import columns as coldef
from agent_board.derive import git_
from agent_board.render.layout import COLUMN_ORDER


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


def derive_thread(t, rows, wt_index, cfg):
    """Recompute every display field. Nothing here is ever persisted."""
    d = {"has_open_nondraft_pr": False, "pr": None, "live_jobs": [],
         "dirty": 0, "ahead": 0, "behind": 0, "age_days": None,
         "missing_worktree": False, "lock_stale": False, "high_collision": False}
    wt_lines, notes = [], []
    newest = None
    for entry in t.get("worktrees") or []:
        path = entry.get("path")
        if not path:
            continue
        if not os.path.isdir(path):
            d["missing_worktree"] = True
            notes.append("missing worktree %s" % os.path.basename(path.rstrip("/")))
            continue
        meta = wt_index.get(os.path.realpath(path)) or {}
        if meta.get("prunable"):
            d["missing_worktree"] = True
            notes.append("prunable worktree %s" % os.path.basename(path.rstrip("/")))
            continue
        branch = meta.get("branch")
        row = rows.get(branch) if branch else None
        status = git_.status_v2(path)
        dirty = len(status["dirty"])
        d["dirty"] += dirty
        ahead = (row or {}).get("ahead")
        behind = (row or {}).get("behind")
        d["ahead"] += ahead or 0
        d["behind"] += behind or 0
        committed_at = (row or {}).get("committed_at")
        if committed_at and (newest is None or committed_at > newest):
            newest = committed_at
        wt_lines.append("%s  +%s -%s *%d  %s" % (
            branch or "(detached)",
            "?" if ahead is None else ahead,
            "?" if behind is None else behind,
            dirty, _rel(committed_at)))
    d["age_days"] = _age_days(newest)
    return d, wt_lines, notes


def build_board(threads_dir, repo, cfg=None):
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

    out = {name: [] for name in COLUMN_ORDER}
    for tid in sorted(threads):
        t = threads[tid]
        d, wt_lines, notes = derive_thread(t, rows, wt_index, cfg)
        col = coldef.column(t, threads, d, thresholds)
        reasons = coldef.needs_attention(t, threads, d)
        badges = []
        if reasons:
            badges.append(("needs_attention", ", ".join(sorted(set(reasons)))))
        if t["_status"] != "ok":
            notes = notes + ["%s: %s" % (t["_status"],
                                         "; ".join(t.get("_problems") or []))]
        out[col].append({
            "id": tid,
            "title": t.get("title") or tid,
            "goal": t.get("goal"),
            "next_action": t.get("next_action"),
            "badges": badges,
            "worktrees": wt_lines,
            "notes": notes,
        })

    return {
        "meta": {"project": os.path.basename(os.path.abspath(repo)),
                 "branch": base or "?",
                 "head": (git_._git(repo, "rev-parse", "--short", "HEAD") or "?").strip(),
                 "open": sum(len(v) for k, v in out.items() if k != "DONE"),
                 # jobs and collisions land in M2; M1 renders the zero state so
                 # the header layout is already exercised at final width.
                 "live_jobs": 0, "collisions": 0,
                 "clock": time.strftime("%H:%M", time.localtime())},
        "columns": out,
        "collisions": [],
    }
