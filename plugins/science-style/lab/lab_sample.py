"""The sample of one person (spec section 8): targets, fallback, year bins and replacements.

Each cell (one group and one tier) has its own random generator. Python 3 seeds a generator from
a string through SHA-512, so the same seed gives the same draw on every run and machine.
"""
import random

GROUPS = ("senior", "first", "essay")
TIERS = ("high", "other")
TARGETS = {"senior": {"high": 5, "other": 3}, "first": {"high": 3, "other": 1}, "essay": {"high": 2, "other": 1}}
DEFAULT_SEED = 20261029
MANIFEST_FIELDS = ("work_id", "doi", "title", "year", "venue", "type", "tier", "group", "co_senior",
                   "pmcid", "preprint_doi", "arxiv_id")


def cell_name(group, tier):
    return group + "/" + tier


def cell_rng(seed, person_id, group, tier):
    return random.Random("{}:{}:{}:{}".format(seed, person_id, group, tier))


def allocate(pools, targets=TARGETS):
    """Return (allocation, shortfall) for the pool size of each cell.

    Step 1: inside a group, the spare slots of a short tier go to the other tier.
    Step 2: the spare slots of a short group go to the other two groups in the order senior,
    first, essay, the high tier first. Slots that find no paper add to the shortfall.
    """
    alloc = {}
    for g in GROUPS:
        for t in TIERS:
            alloc[cell_name(g, t)] = min(targets[g][t], pools.get(cell_name(g, t), 0))

    def room(g, t):
        return pools.get(cell_name(g, t), 0) - alloc[cell_name(g, t)]

    for g in GROUPS:
        for t in TIERS:
            short = targets[g][t] - alloc[cell_name(g, t)]
            other = TIERS[1 - TIERS.index(t)]
            add = min(short, room(g, other))
            if add > 0:
                alloc[cell_name(g, other)] += add
    shortfall = 0
    for g in GROUPS:
        spare = sum(targets[g].values()) - sum(alloc[cell_name(g, t)] for t in TIERS)
        for g2 in GROUPS:
            if g2 == g or spare <= 0:
                continue
            for t in TIERS:
                add = min(spare, room(g2, t))
                if add > 0:
                    alloc[cell_name(g2, t)] += add
                    spare -= add
        shortfall += max(spare, 0)
    return alloc, shortfall


def draw_cell(papers, k, rng):
    """Return (chosen, bins, queue) as work ids.

    The papers are sorted by year, then work id, and split into k bins of near-equal size. One
    paper comes from each bin. The rest form the replacement queue, shuffled by rng.
    """
    ordered = sorted(papers, key=lambda p: (p.get("year") or 0, p["work_id"]))
    ids = [p["work_id"] for p in ordered]
    n = len(ids)
    bins = [ids[(i * n) // k:((i + 1) * n) // k] for i in range(k)] if k > 0 else []
    chosen = [rng.choice(b) for b in bins]
    queue = [w for w in ids if w not in chosen]
    rng.shuffle(queue)
    return chosen, bins, queue


def manifest_paper(record, cell):
    paper = {field: record.get(field) for field in MANIFEST_FIELDS}
    paper.update({"cell": cell, "status": "chosen", "route": None, "text_version": None, "source_url": None})
    return paper


def count_papers(manifest):
    return sum(1 for p in manifest["papers"] if p["status"] != "replaced")


def build_sample(person_id, papers, seed=DEFAULT_SEED, targets=TARGETS, venues_version=None):
    """Return the manifest of one person from the records of the person's papers."""
    by_cell = {}
    for paper in papers:
        by_cell.setdefault(cell_name(paper["group"], paper["tier"]), []).append(paper)
    pools = {cell: len(members) for cell, members in by_cell.items()}
    alloc, shortfall = allocate(pools, targets)
    lookup = {p["work_id"]: p for p in papers}
    cells, chosen_papers = {}, []
    for g in GROUPS:
        for t in TIERS:
            cell = cell_name(g, t)
            chosen, bins, queue = draw_cell(by_cell.get(cell, []), alloc[cell], cell_rng(seed, person_id, g, t))
            cells[cell] = {"target": targets[g][t], "pool": pools.get(cell, 0), "allocated": alloc[cell],
                           "bins": bins, "queue": queue}
            chosen_papers.extend(manifest_paper(lookup[wid], cell) for wid in chosen)
    manifest = {"schema": 1, "person": person_id, "seed": seed, "venues_version": venues_version,
                "cells": cells, "shortfall": shortfall, "papers": chosen_papers, "replacements": []}
    manifest["n_papers"] = count_papers(manifest)
    return manifest


def replace(manifest, work_id, reason, lookup):
    """Mark a paper replaced and add its replacement. Return the replacement's work id or None.

    The replacement is the first unused paper of the same year bin in queue order, else the first
    unused paper of the cell's queue. The function raises ValueError for a work id that is not in
    the manifest or is already replaced. It raises KeyError if the lookup lacks the replacement. In
    each case the manifest stays unchanged.
    """
    paper = next((p for p in manifest["papers"] if p["work_id"] == work_id), None)
    if paper is None:
        raise ValueError("unknown work id: {}".format(work_id))
    if paper["status"] == "replaced":
        raise ValueError("already replaced: {}".format(work_id))
    cell = manifest["cells"][paper["cell"]]
    used = {p["work_id"] for p in manifest["papers"]}
    candidates = []
    for members in cell["bins"]:
        if work_id in members:
            candidates = [w for w in cell["queue"] if w in members and w not in used]
            break
    if not candidates:
        candidates = [w for w in cell["queue"] if w not in used]
    replacement = candidates[0] if candidates else None
    new_paper = manifest_paper(lookup[replacement], paper["cell"]) if replacement else None
    paper["status"] = "replaced"
    if new_paper:
        manifest["papers"].append(new_paper)
    manifest["replacements"].append({"replaced": work_id, "reason": reason, "replacement": replacement})
    manifest["n_papers"] = count_papers(manifest)
    return replacement


def seeded_subset(work_ids, k, seed_text):
    """Return k work ids drawn under seed_text, sorted. The input order does not matter."""
    ids = sorted(work_ids)
    return sorted(random.Random(seed_text).sample(ids, min(k, len(ids))))


def agreement_count(n):
    """Return the size of the agreement set: a fifth of n, rounded up, at least 3, at most n."""
    return min(n, max(3, -(-n // 5)))
