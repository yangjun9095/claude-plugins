#!/usr/bin/env python3
"""
Parse CodeQL SARIF output(s) and print findings grouped by rule and per location.

Usage:
    python3 parse_sarif.py <sarif_file> [<sarif_file> ...]
    python3 parse_sarif.py /tmp/sarif/quality.sarif /tmp/sarif/quality-extended.sarif

Output:
    For each file:
      <LABEL>: total findings + count per rule
      detail: rule | path:line | first-80-chars-of-message
"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def label_for(path: Path) -> str:
    stem = path.stem.lower()
    if "extended" in stem:
        return "EXTENDED"
    if "quality" in stem:
        return "STANDARD"
    return path.name.upper()


def parse_one(path: Path) -> None:
    try:
        sarif = json.loads(path.read_text())
    except FileNotFoundError:
        print(f"=== {label_for(path)}: file not found ({path}) ===")
        return
    except json.JSONDecodeError as e:
        print(f"=== {label_for(path)}: invalid JSON ({e}) ===")
        return

    runs = sarif.get("runs", [])
    total = 0
    by_rule: dict[str, int] = {}
    detail: list[tuple[str, str, str]] = []
    for run in runs:
        for r in run.get("results", []):
            total += 1
            rule = r.get("ruleId") or "?"
            by_rule[rule] = by_rule.get(rule, 0) + 1
            locs = r.get("locations", []) or []
            loc_str = ""
            if locs:
                pl = locs[0].get("physicalLocation", {})
                uri = pl.get("artifactLocation", {}).get("uri", "")
                line = pl.get("region", {}).get("startLine", "?")
                loc_str = f"{uri}:{line}"
            msg = (r.get("message", {}) or {}).get("text", "")[:80]
            detail.append((rule, loc_str, msg))

    print(f"=== {label_for(path)} TOTAL: {total} ===")
    for rule, count in sorted(by_rule.items(), key=lambda x: -x[1]):
        print(f"  {count:4d}  {rule}")
    if detail:
        print()
        for rule, loc, msg in detail:
            print(f"  {rule}  {loc}  — {msg}")
    print()


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 1
    for arg in argv:
        parse_one(Path(arg))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
