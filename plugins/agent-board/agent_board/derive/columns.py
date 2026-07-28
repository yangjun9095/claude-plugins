LIVE = ("ACTIVE", "BLOCKED", "IN REVIEW")


def column(t, threads, derived, thresholds):
    """Ordered, first match wins. Each rule is an iff because it implicitly
    negates every earlier one."""
    if t.get("done"):
        return "DONE"
    for dep in t.get("blocked_by") or []:
        other = (threads or {}).get(dep)          # .get, never [] -- see the test
        if other is not None and not other.get("done"):
            return "BLOCKED"
    if t.get("parked"):
        return "PARKED"
    if derived.get("has_open_nondraft_pr"):
        return "IN REVIEW"
    age = derived.get("age_days")
    dirty = derived.get("dirty") or 0
    # active_commit_days alone decides the PARKED cutoff; parked_idle_days only
    # bounds how long uncommitted work still counts. No clamp is needed: if a
    # config inverts them (active > parked) the dirt band [active, parked) is
    # simply empty, which a max() would produce identically -- measured, max()
    # changed the outcome in 0 of 360 (age, dirty, active, parked) combinations.
    active_days = thresholds["active_commit_days"]
    dirt_days = thresholds["parked_idle_days"]
    if derived.get("live_jobs"):
        return "ACTIVE"
    if age is not None and age < active_days:
        return "ACTIVE"                       # recent commit
    if dirty > 0 and age is not None and age < dirt_days:
        return "ACTIVE"                       # uncommitted work, still fresh
    if age is not None and age >= active_days:
        return "PARKED"                       # idle AND clean
    return "ACTIVE"                           # age unknown only


def needs_attention(t, threads, derived):
    """Returns the reason list; truthiness IS needs_attention. A badge, never
    a column -- it can apply to a card in any state."""
    reasons = []
    pr = derived.get("pr") or {}
    if pr.get("reviewDecision") == "CHANGES_REQUESTED":
        reasons.append("changes_requested")
    if pr.get("mergeable") == "CONFLICTING":
        reasons.append("pr_conflicting")
    if pr.get("state") == "MERGED" and not t.get("done"):
        reasons.append("pr_merged_thread_open")
    ahead = derived.get("ahead") or 0
    age = derived.get("age_days")
    if ahead > 0 and age is not None and age > 1:
        reasons.append("unpushed")
    if derived.get("high_collision"):
        reasons.append("high_collision")
    if derived.get("missing_worktree"):
        reasons.append("missing_worktree")
    if derived.get("lock_stale"):
        reasons.append("lock_stale")
    # `not t.get("done")` mirrors stale_blocks(): a DONE card must not advertise
    # a stale_block for a dependency that is also done.
    if not t.get("done"):
        for dep in t.get("blocked_by") or []:
            other = (threads or {}).get(dep)
            if other is None:
                reasons.append("dangling_blocker")
            elif other.get("done"):
                reasons.append("stale_block")
    # dedupe: two done dependencies otherwise emit stale_block twice, which a
    # per-reason badge renderer would draw as a duplicate icon.
    seen, out = set(), []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def stale_blocks(threads):
    """The highest value-per-line in the whole signal layer: pure dict
    traversal, O(edges), no I/O."""
    out = []
    for tid, t in (threads or {}).items():
        if t.get("done"):
            continue
        for dep in t.get("blocked_by") or []:
            other = threads.get(dep)
            if other is None:
                out.append((tid, dep, "MISSING"))
            elif other.get("done"):
                out.append((tid, dep, "DONE"))
    return out


def block_cycles(threads):
    """Detect cycles so transitive rendering cannot recurse forever."""
    threads = threads or {}
    cycles, state = [], {}

    def visit(node, stack):
        if state.get(node) == "done":
            return
        if node in stack:
            cycles.append(stack[stack.index(node):])
            return
        stack.append(node)
        for dep in (threads.get(node) or {}).get("blocked_by") or []:
            if dep in threads:
                visit(dep, stack)
        stack.pop()
        state[node] = "done"

    for tid in sorted(threads):
        visit(tid, [])
    return cycles
