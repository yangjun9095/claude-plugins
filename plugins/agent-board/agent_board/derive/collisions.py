"""Collision detection: which threads are editing the same files.

This is the feature that answers "my agents collide". Two measured facts shape all
of it.

**Three-dot, not two-dot.** `BASE..HEAD` answers "what differs between main's tip
and this branch" -- mostly *what main did* -- and built a 1633-file noise wall
whose top entries were main's newest commits. Three-dot over 64 real worktrees
gives 539 distinct files with a ubiquity histogram of {1: 527, 2: 12}. There is no
noise wall once three-dot is used.

**The dirty union is the point.** Both real source collisions in the reference repo
are dirty-only on one side, so a committed-diff-only scan finds NEITHER. That is
why `-uall` is unconditional and why R2 (both sides uncommitted) is the top
severity band.
"""
import fnmatch
import os
import re

from agent_board import cache

CACHE_NAME = "collisions.json"

# Lockfiles, binaries and build caches ONLY. Adding the "obvious" docs/**,
# analysis/**, *.md set drops the collision count 4 -> 2 and destroys the 9-file
# docs/manuscript/ collision -- exactly the "two agents editing the paper"
# interference this tool exists to catch. Do NOT default-ignore docs or markdown.
DEFAULT_IGNORE_GLOBS = (
    "**/*.lock", "**/package-lock.json", "**/poetry.lock", "**/uv.lock",
    "**/Pipfile.lock", "**/yarn.lock", "**/pnpm-lock.yaml", "**/Cargo.lock",
    "**/go.sum",
    "**/*.png", "**/*.jpg", "**/*.jpeg", "**/*.gif", "**/*.pdf", "**/*.svg",
    "**/*.ico",
    "**/*.h5", "**/*.h5ad", "**/*.npz", "**/*.npy", "**/*.pkl", "**/*.parquet",
    "**/*.zip", "**/*.pptx",
    "**/__pycache__/**", "**/node_modules/**", "**/dist/**", "**/build/**",
    "**/*.egg-info/**",
    "**/.DS_Store", "**/*.pyc",
    # Our OWN config. `abd init` writes it into the working tree, where -uall sees
    # it as untracked -- and two threads sharing one worktree then both listed it as
    # dirty, manufacturing a HIGH collision out of a file this tool created.
    ".agent-board.json", "**/.agent-board.json",
)
# Documented blind spot, stated here rather than buried: .png is the single most
# common extension in the three-dot union (204 of 539 files) and analysis/ the
# largest top-level dir, so two threads regenerating the same figure set are NOT
# flagged. Deliberate -- binary conflicts are not diff-resolvable.

LIVE = ("ACTIVE", "BLOCKED", "IN REVIEW")


def build_ignore_matcher(globs):
    """A path -> bool matcher.

    The empty case is a real bug, not a formality: `"|".join([])` is `""`, and
    `re.compile("").match(x)` is TRUTHY, so an empty sub-list would make this
    return True for every path and the board would silently report zero
    collisions -- a total feature failure that looks like good news.
    """
    globs = list(globs or [])
    if not globs:
        return lambda p: False
    # A bare `**/*.png` should match at any depth, including the top level, which
    # fnmatch.translate("**/*.png") alone does not do -- so basename-match those.
    base = [g[3:] for g in globs if g.startswith("**/") and "/" not in g[3:]]
    base_re = re.compile("|".join(fnmatch.translate(g) for g in base)) if base else None
    # `**/node_modules/**` translates to `.*/node_modules/.*`, which requires at
    # least one component BEFORE the directory -- so a top-level node_modules/ was
    # not ignored. `**/` has to mean "zero or more leading components", so every
    # such glob also contributes its leading-`**/`-stripped form.
    patterns = list(globs)
    patterns += [g[3:] for g in globs if g.startswith("**/") and "/" in g[3:]]
    full_re = re.compile("|".join(fnmatch.translate(g) for g in patterns))

    def ignored(path):
        if base_re is not None and base_re.match(os.path.basename(path)):
            return True
        return bool(full_re.match(path))
    return ignored


def severity(col_a, col_b, overlap, both_dirty, one_dirty):
    """Deterministic, first match wins. Pure and total: it CONSUMES derived
    status and never computes it. |S| never crosses a band -- it only orders
    cards within one."""
    if not overlap:
        return "NONE"
    if col_a == "DONE" or col_b == "DONE":
        return "LOW"
    both_live = col_a in LIVE and col_b in LIVE
    if both_dirty and both_live:
        return "HIGH"
    if one_dirty and both_live:
        return "MEDIUM"
    if both_live:
        return "MEDIUM"
    if (col_a in LIVE) != (col_b in LIVE):
        return "LOW"
    return "LOW"


def scan_worktrees(paths, base, workers):
    """{path: {"changed": set, "dirty": set, "failed": bool}}.

    Parallel because serial is not viable: 64 worktrees x 4 git calls is 20.66 s
    serial versus 2.50 s at 8 workers. 8, not 16 -- 16 saves 1.1 s of wall but
    costs 44 s of system time, which is antisocial on a shared login node.
    """
    from concurrent.futures import ThreadPoolExecutor

    from agent_board.derive import git_

    out = {}
    if not paths:
        return out

    def probe(path):
        status = git_.status_v2(path)
        # status_v2 returns its empty sentinel for a failed probe as well as for
        # a genuinely clean worktree; branch-None with no dirt on an existing
        # directory is the only signal available without changing _git.
        failed = (status["branch"] is None and not status["detached"]
                  and not status["dirty"])
        changed = git_.changed_files(path, base) if base else set()
        return path, {"changed": changed | status["dirty"],
                      "dirty": set(status["dirty"]), "failed": failed}

    limit = max(1, min(int(workers or 8), (os.cpu_count() or 4) * 2, len(paths)))
    with ThreadPoolExecutor(max_workers=limit) as pool:
        for path, result in pool.map(probe, paths):
            out[path] = result
    return out


def rollup(threads, scanned, ignored):
    """(F, D) -- per-thread changed and dirty unions, minus ignored paths."""
    changed, dirty = {}, {}
    for tid, t in threads.items():
        acc_changed, acc_dirty = set(), set()
        for entry in t.get("worktrees") or []:
            path = entry.get("path") if isinstance(entry, dict) else None
            if not isinstance(path, str) or not path:
                continue
            hit = scanned.get(os.path.realpath(path)) or scanned.get(path)
            if not hit:
                continue
            acc_changed |= hit["changed"]
            acc_dirty |= hit["dirty"]
        changed[tid] = {p for p in acc_changed if not ignored(p)}
        dirty[tid] = {p for p in acc_dirty if not ignored(p)}
    return changed, dirty


def ubiquity_valve(changed):
    """(ubiquitous_paths, demote_at, considered_count).

    The portability net. On the reference repo (28 considered) demote_at is 15 and
    nothing is demoted -- it correctly never fires and all 4 collisions survive.
    On a synthetic 12-thread project where everyone edits CHANGELOG/README it cuts
    colliding pairs from 66/66 to 21/66. Both constants are UNVALIDATED against a
    real noisy repo, which is why every render logs demote_at and the demoted
    count: drift has to be visible before it can be retuned.
    """
    considered = [tid for tid, files in changed.items() if files]
    counts = {}
    for tid in considered:
        for path in changed[tid]:
            counts[path] = counts.get(path, 0) + 1
    demote_at = max(4, int(0.5 * len(considered)) + 1)
    return {p for p, n in counts.items() if n >= demote_at}, demote_at, len(considered)


def pairwise(threads, changed, dirty, columns, ubiquitous):
    """O(n^2) and measured free: 378 pairs in 0.0001 s at n=28."""
    ids = sorted(changed)
    out = []
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            overlap = changed[a] & changed[b]
            if not overlap:
                continue
            shared = overlap - ubiquitous
            demoted = overlap & ubiquitous
            if not shared:
                # Demoted files render collapsed, never silently dropped -- but a
                # pair whose ENTIRE overlap is ubiquitous is not a collision.
                continue
            both = shared & dirty.get(a, set()) & dirty.get(b, set())
            one = (shared & (dirty.get(a, set()) | dirty.get(b, set()))) - both
            out.append({
                "a": a, "b": b,
                "files": sorted(shared),
                "demoted_files": sorted(demoted),
                "both_dirty": sorted(both),
                "one_dirty": sorted(one),
                "severity": severity(columns.get(a), columns.get(b),
                                     shared, both, one),
            })
    rank = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "NONE": 3}
    out.sort(key=lambda c: (rank.get(c["severity"], 9), -len(c["files"]),
                            -len(c["both_dirty"]), c["a"], c["b"]))
    return out


def detect(threads_dir, threads, columns, wt_paths, base, cfg, write_cache=True):
    """Full pass. Returns a dict the board renders and the SessionStart hook reads.

    `abd board` owns writing cache/collisions.json on every render; the SessionEnd
    hook deliberately does not. If the board is never run, HIGH collisions stop
    appearing in injected cards after 24 h -- that ownership is assigned here.
    """
    collisions_cfg = cfg.get("collisions") or {}
    extra = collisions_cfg.get("ignore_globs_extra") or []
    # Only the ADDITIVE key exists in the schema: deep_merge replaces lists, so a
    # replaceable ignore_globs would let a user adding one pattern silently lose
    # all 31 defaults and get a flood of false positives.
    ignored = build_ignore_matcher(list(DEFAULT_IGNORE_GLOBS) + list(extra))

    workers = (cfg.get("scan") or {}).get("workers") or 8
    scanned = scan_worktrees(sorted(wt_paths), base, workers)
    failed = sorted(p for p, r in scanned.items() if r.get("failed"))

    changed, dirty = rollup(threads, scanned, ignored)
    ubiquitous, demote_at, considered = ubiquity_valve(changed)
    pairs = pairwise(threads, changed, dirty, columns, ubiquitous)

    result = {
        "collisions": pairs,
        "demote_at": demote_at,
        "demoted": sorted(ubiquitous),
        "considered": considered,
        # Marked degraded, but NOT retried with halved workers: a second pass on a
        # wedged filesystem doubles the wall time exactly when things are already
        # slow. Distinguishing a timeout from any other probe failure would need
        # _git to report why, which it deliberately does not.
        "degraded": len(failed) >= 3,
        "failed_probes": failed,
        "base": base,
    }
    if write_cache:
        cache.write(threads_dir, CACHE_NAME, result)
    return result


def high_by_thread(pairs):
    """{tid: True} for threads in at least one HIGH pair -- the input to the
    high_collision badge."""
    out = {}
    for pair in pairs or []:
        if pair.get("severity") == "HIGH":
            out[pair["a"]] = True
            out[pair["b"]] = True
    return out
