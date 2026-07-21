#!/usr/bin/env python3
# Copyright (c) 2026 Anatoly Chaussky
"""
migrate_solution_scope.py — migrates 6.4 solution-scope nodes written before the
type rename (ADR-082, revised).

WHY
---
The literal `solution` used to mean two different things in the same `type` field:

  * the BABOK requirement CLASS of the 5.1 vocabulary
    (business | stakeholder | solution | transition) — how `init_traceability_repo`,
    the Confluence import and hand-written repositories label ordinary FR/NFR;
  * the SOLUTION SCOPE node 6.4 pushes (SOL-001).

Since the first meaning is a real requirement, the scope node could not be excluded
from any requirement filter without dropping requirements too. So the scope node was
counted as a requirement everywhere: 5.1 demanded a test case for it, 5.2 an owner,
5.3 a MoSCoW vote from a stakeholder. It also carried `status="approved"`, meaning
"the scope is settled", which 7.2 read as 5.5's "the stakeholders signed".

6.4 now writes `type="solution_scope"`, `status="defined"`. This script brings graphs
written earlier into line.

HOW THE SCOPE NODE IS IDENTIFIED
--------------------------------
The two populations are NOT distinguishable by the type literal alone — that is the
whole problem. They are distinguishable by what the producer writes: 6.4 emits exactly
one node, with the fixed id `SOL-001` and the title `Solution Scope — <project>`.
Both must match. A requirement a BA happened to number SOL-001 keeps its title, and a
node titled like the scope but carrying another id is left alone too.

Nothing is deleted and nothing else is touched: only the `type` literal, plus
`status` when it still holds the colliding default. A status the analyst changed
themselves (deprecated, superseded, …) is their record and is preserved.

USAGE
-----
    python migrate_solution_scope.py            # report what would change
    python migrate_solution_scope.py --apply    # write the changes
"""

import json
import os
import sys

LEGACY_TYPE = "solution"
NEW_TYPE = "solution_scope"
LEGACY_STATUS = "approved"
NEW_STATUS = "defined"

SCOPE_NODE_ID = "SOL-001"
SCOPE_TITLE_PREFIX = "Solution Scope"

DATA_DIR = os.path.join("governance_plans", "data")
REPO_SUFFIX = "_traceability_repo.json"


def _is_legacy_scope_node(node: dict) -> bool:
    """Both the id AND the title must match the shape 6.4 writes.

    Requiring both is deliberate. The id alone would rename a requirement a BA
    numbered SOL-001; the title alone would rename a requirement someone described as
    "Solution Scope for reporting". Migrating a real requirement into a
    non-requirement type is the one failure this script must not have — it would
    silently drop that requirement out of every coverage count.
    """
    if node.get("type") != LEGACY_TYPE:
        return False
    if node.get("id") != SCOPE_NODE_ID:
        return False
    return str(node.get("title", "")).startswith(SCOPE_TITLE_PREFIX)


def migrate_repo_file(path: str, apply: bool = True) -> dict:
    """Migrates one traceability repository. Returns {"migrated": n, "nodes": [...]}.

    With apply=False the file is only inspected, never written.
    """
    stats = {"migrated": 0, "nodes": [], "path": path}

    try:
        with open(path, encoding="utf-8") as f:
            repo = json.load(f)
    except (OSError, ValueError) as exc:
        stats["error"] = f"{type(exc).__name__}: {exc}"
        return stats

    if not isinstance(repo, dict) or not isinstance(repo.get("requirements"), list):
        stats["error"] = "not a traceability repository (no `requirements` list)"
        return stats

    for node in repo["requirements"]:
        if not isinstance(node, dict) or not _is_legacy_scope_node(node):
            continue
        node["type"] = NEW_TYPE
        # Only the colliding default is rewritten; anything the analyst set stays.
        if node.get("status") == LEGACY_STATUS:
            node["status"] = NEW_STATUS
        stats["migrated"] += 1
        stats["nodes"].append(node.get("id"))

    if stats["migrated"] and apply:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(repo, f, ensure_ascii=False, indent=2)

    return stats


def find_repositories(root: str = DATA_DIR) -> list:
    """Every traceability repository under governance_plans/data, flat or per-project."""
    found = []
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            if name.endswith(REPO_SUFFIX):
                found.append(os.path.join(dirpath, name))
    return sorted(found)


def main(argv) -> int:
    apply = "--apply" in argv
    repos = find_repositories()

    if not repos:
        print(f"No traceability repositories found under {DATA_DIR}/ — nothing to do.")
        return 0

    total = 0
    for path in repos:
        stats = migrate_repo_file(path, apply=apply)
        if stats.get("error"):
            print(f"⚠️  {path}: {stats['error']}")
            continue
        if stats["migrated"]:
            total += stats["migrated"]
            verb = "migrated" if apply else "would migrate"
            print(f"✅ {path}: {verb} {', '.join(stats['nodes'])} "
                  f"→ type={NEW_TYPE}")

    print()
    if not total:
        print(f"Scanned {len(repos)} repositories — no legacy scope nodes found.")
    elif apply:
        print(f"Done: {total} scope node(s) migrated across {len(repos)} repositories.")
    else:
        print(f"Dry run: {total} scope node(s) would be migrated. "
              f"Re-run with --apply to write the changes.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
