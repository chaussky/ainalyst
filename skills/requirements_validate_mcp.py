"""
BABOK 7.3 — Validate Requirements
MCP tools for validating requirements: checking alignment with business objectives,
managing assumptions, success criteria, the validated status.

Tools:
  - set_business_context       — create/update the project's business context (Ch.6 surrogate)
  - check_business_alignment   — check traceability of reqs to business objectives (BFS + matching)
  - set_success_criteria       — attach a measurable success criterion to a req
  - log_assumption             — record an assumption (AS-001, ...)
  - resolve_assumption         — close an assumption (confirmed/refuted)
  - mark_req_validated         — status verified -> validated (warnings, not blocks)
  - get_validation_report      — summary report: coverage matrix, orphans, assumptions, verdict

ADR-030: {project}_business_context.json — a Chapter 6 surrogate
ADR-031: {project}_assumptions.json — the assumptions registry
ADR-032: set_success_criteria — an optional pipeline step
ADR-033: mark_req_validated — warnings, not hard blocks

Reads: repository 5.1 ({project}_traceability_repo.json)
Writes: {project}_business_context.json, {project}_assumptions.json,
        the validated status in 5.1
Output: Validation Report -> 7.5 (Design Options)

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
from collections import deque
from datetime import date
from typing import Optional
from mcp.server.fastmcp import FastMCP
from skills.common import save_artifact, logger, DATA_DIR, data_path, normalize_project_id

mcp = FastMCP("BABOK_Requirements_Validate")

REPO_FILENAME = "traceability_repo.json"
CONTEXT_FILENAME = "business_context.json"
ASSUMPTIONS_FILENAME = "assumptions.json"


# ---------------------------------------------------------------------------
# Utilities — paths and file loading
# ---------------------------------------------------------------------------

def _safe(project_id: str) -> str:
    return normalize_project_id(project_id)


def _repo_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{REPO_FILENAME}")


def _context_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{CONTEXT_FILENAME}")


def _assumptions_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{ASSUMPTIONS_FILENAME}")


def _load_repo(project_id: str) -> dict:
    path = _repo_path(project_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"project": project_id, "requirements": [], "links": [], "history": []}


def _save_repo(repo: dict) -> None:
    project_id = repo["project"]
    path = _repo_path(project_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    repo["updated"] = str(date.today())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(repo, f, ensure_ascii=False, indent=2)
    logger.info(f"Repository 5.1 updated (7.3): {path}")


def _load_context(project_id: str) -> Optional[dict]:
    path = _context_path(project_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _save_context(data: dict) -> None:
    path = _context_path(data["project_id"])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data["updated_at"] = str(date.today())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"Business context saved: {path}")


def _load_assumptions(project_id: str) -> dict:
    path = _assumptions_path(project_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "project": project_id,
        "assumptions": {},
        "stats": {"open": 0, "confirmed": 0, "refuted": 0},
        "created": str(date.today()),
        "updated": str(date.today()),
    }


def _save_assumptions(data: dict) -> None:
    path = _assumptions_path(data["project"])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data["updated"] = str(date.today())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"Assumptions updated: {path}")


def _next_assumption_id(data: dict) -> str:
    existing = [k for k in data["assumptions"].keys() if k.startswith("AS-")]
    if not existing:
        return "AS-001"
    nums = [int(k.split("-")[1]) for k in existing if k.split("-")[1].isdigit()]
    return f"AS-{(max(nums) + 1):03d}" if nums else "AS-001"


def _find_req(repo: dict, req_id: str) -> Optional[dict]:
    for r in repo["requirements"]:
        if r["id"] == req_id:
            return r
    return None


# ---------------------------------------------------------------------------
# BFS search of traceability to business objectives (ADR-030)
# ---------------------------------------------------------------------------

def _bfs_to_business(repo: dict, start_id: str) -> list:
    """
    BFS traversal of the 5.1 traceability graph. Returns the list of 'business'-type nodes
    reachable from start_id. Used by check_business_alignment.
    """
    links = repo.get("links", [])
    reqs_by_id = {r["id"]: r for r in repo.get("requirements", [])}

    visited = set()
    queue = deque([start_id])
    business_nodes = []

    while queue:
        current = queue.popleft()
        if current in visited:
            continue
        visited.add(current)

        node = reqs_by_id.get(current)
        if node and current != start_id:
            if node.get("type") == "business":
                business_nodes.append(node)

        # Traverse all edges (in either direction)
        for link in links:
            neighbor = None
            if link.get("from") == current:
                neighbor = link.get("to")
            elif link.get("to") == current:
                neighbor = link.get("from")
            if neighbor and neighbor not in visited:
                queue.append(neighbor)

    return business_nodes


def _title_matches_goal(req_title: str, goal_title: str) -> bool:
    """
    Simple title matching: checks the overlap of keywords (≥3 characters).
    Used as a second alignment-detection method.
    """
    req_words = set(w.lower() for w in req_title.split() if len(w) >= 5)
    goal_words = set(w.lower() for w in goal_title.split() if len(w) >= 5)
    return bool(req_words & goal_words)


# ---------------------------------------------------------------------------
# 7.3.1 — set_business_context (ADR-030)
# ---------------------------------------------------------------------------

@mcp.tool()
def set_business_context(
    project_id: str,
    business_goals_json: str,
    future_state: str,
    solution_scope: str,
    potential_value: str = "",
    from_current_state_project_id: str = "",
    from_strategy_project_id: str = "",
) -> str:
    """
    BABOK 7.3 — Creates or updates the project's business context.
    ADR-030: a Chapter 6 surrogate (Strategy Analysis). Migrate when 6.1/6.2 is implemented.

    ⚠️ Call once at the start of validation work. On update — a warning.

    Args:
        project_id:          Project identifier.
        business_goals_json: JSON list of business objectives:
                             '[{"id":"BG-001","title":"...","description":"...","kpi":"..."}]'.
                             id must start with BG-.
        future_state:        Description of the desired future state (Free State).
        solution_scope:      Solution boundaries: what is in, what is out.
        potential_value:          Potential value/benefit (optional).
        from_current_state_project_id: ⚠️ DEPRECATED — use from_strategy_project_id.
                                 Prefills from 6.1 data. Kept for compatibility (ADR-055).
        from_strategy_project_id: Reads data from 6.1 AND 6.2 and prefills objectives, future_state,
                                 scope (ADR-065). Replaces from_current_state_project_id.

    Returns:
        Confirmation with a short summary of the business context.
    """
    logger.info(f"set_business_context: project_id=\'{project_id}\'")

    # ADR-065: the new parameter from_strategy_project_id reads 6.1 + 6.2
    prefill_status = ""
    if from_strategy_project_id.strip():
        safe_sp = from_strategy_project_id.lower().replace(" ", "_")
        fs_goals_path = data_path(safe_sp, f"{safe_sp}_future_state_goals.json")
        fs_state_path = data_path(safe_sp, f"{safe_sp}_future_state.json")
        fs_scope_path = data_path(safe_sp, f"{safe_sp}_future_state_scope.json")
        cs_needs_path = data_path(safe_sp, f"{safe_sp}_business_needs.json")

        try:
            prefill_parts = []

            # Prefill business_goals from the 6.2 BG objectives
            if os.path.exists(fs_goals_path) and (not business_goals_json.strip() or business_goals_json.strip() == "[]"):
                with open(fs_goals_path, "r", encoding="utf-8") as f_g:
                    goals_data = json.load(f_g)
                bg_list = goals_data.get("goals", [])
                if bg_list:
                    auto_goals = [
                        {
                            "id": g["id"],
                            "title": g["goal_title"],
                            "description": g.get("description", ""),
                            "kpi": "; ".join(
                                f"{o.get('title', '')}: {o.get('baseline', '?')} → {o.get('target', '?')}"
                                for o in g.get("objectives", [])
                            ),
                        }
                        for g in bg_list
                    ]
                    business_goals_json = json.dumps(auto_goals, ensure_ascii=False)
                    prefill_parts.append(f"✅ Business objectives prefilled from 6.2 ({len(auto_goals)} BG objectives)")

            # Prefill future_state from the 6.2 description
            if os.path.exists(fs_state_path) and not future_state.strip():
                with open(fs_state_path, "r", encoding="utf-8") as f_s:
                    fs_data = json.load(f_s)
                elem_descs = [
                    f"{k}: {v.get('description', '')[:100]}"
                    for k, v in fs_data.get("elements", {}).items()
                    if v.get("description")
                ]
                if elem_descs:
                    future_state = "Future state: " + "; ".join(elem_descs[:3])
                    prefill_parts.append("✅ future_state prefilled from the 6.2 elements")

            # Prefill solution_scope from the 6.2 scope
            if os.path.exists(fs_scope_path) and not solution_scope.strip():
                with open(fs_scope_path, "r", encoding="utf-8") as f_sc:
                    scope_data_62 = json.load(f_sc)
                elements = scope_data_62.get("elements_in_scope", [])
                initiative = scope_data_62.get("initiative_type", "")
                if elements:
                    solution_scope = f"Scope elements: {', '.join(elements)}. Type: {initiative}."
                    prefill_parts.append("✅ solution_scope prefilled from the 6.2 scope")

            # Fallback: if objectives are not filled yet — try from 6.1 BN
            if (not business_goals_json.strip() or business_goals_json.strip() == "[]") and os.path.exists(cs_needs_path):
                with open(cs_needs_path, "r", encoding="utf-8") as f_n:
                    needs_data = json.load(f_n)
                needs_list = needs_data.get("needs", [])
                if needs_list:
                    auto_goals = [
                        {
                            "id": f"BG-{idx_n:03d}",
                            "title": need.get("need_title", f"Need {idx_n}"),
                            "description": need.get("description", ""),
                            "kpi": need.get("cost_of_inaction", ""),
                            "source_bn": need.get("id", ""),
                        }
                        for idx_n, need in enumerate(needs_list, 1)
                    ]
                    business_goals_json = json.dumps(auto_goals, ensure_ascii=False)
                    prefill_parts.append(f"✅ Business objectives prefilled from 6.1 BN ({len(auto_goals)} items)")

            if prefill_parts:
                prefill_status = "\n\n## Auto-fill from 6.1+6.2 (ADR-065)\n\n" + "\n".join(prefill_parts)
            else:
                prefill_status = f"\n\n⚠️ Data for 6.1/6.2 for project `{from_strategy_project_id}` not found."

        except (json.JSONDecodeError, KeyError, IOError) as e:
            prefill_status = f"\n\n⚠️ Could not read 6.1/6.2 data: {e}."

    # ADR-055: prefill from 6.1 if from_current_state_project_id is passed (deprecated)
    elif from_current_state_project_id.strip():
        prefill_status = "\n\n⚠️ The `from_current_state_project_id` parameter is deprecated. Use `from_strategy_project_id` (ADR-065)."
        safe_cs = from_current_state_project_id.lower().replace(" ", "_")
        needs_path = data_path(safe_cs, f"{safe_cs}_business_needs.json")
        scope_path = data_path(safe_cs, f"{safe_cs}_current_state_scope.json")

        if os.path.exists(needs_path):
            try:
                with open(needs_path, "r", encoding="utf-8") as f_n:
                    needs_data = json.load(f_n)
                needs_list = needs_data.get("needs", [])

                if (not business_goals_json.strip() or business_goals_json.strip() == "[]") and needs_list:
                    auto_goals = []
                    for idx_n, need in enumerate(needs_list, 1):
                        auto_goals.append({
                            "id": f"BG-{idx_n:03d}",
                            "title": need.get("need_title", f"Need {idx_n}"),
                            "description": need.get("description", ""),
                            "kpi": need.get("cost_of_inaction", ""),
                            "source_bn": need.get("id", ""),
                        })
                    business_goals_json = json.dumps(auto_goals, ensure_ascii=False)
                    mapping_parts = []
                    for i, n in enumerate(needs_list, 1):
                        mapping_parts.append(n.get("id", "?") + "→BG-" + str(i).zfill(3))
                    mapping = ", ".join(mapping_parts)
                    prefill_status += (
                        f"\n\n## Auto-fill from 6.1 (ADR-055)\n\n"
                        f"✅ Business objectives prefilled from {len(auto_goals)} "
                        f"business needs of `{from_current_state_project_id}`.\n"
                        f"Mapping: {mapping}"
                    )

                if not solution_scope.strip() and os.path.exists(scope_path):
                    with open(scope_path, "r", encoding="utf-8") as f_s:
                        scope_data = json.load(f_s)
                    elements = scope_data.get("elements_in_scope", [])
                    initiative = scope_data.get("initiative_type", "")
                    problems = scope_data.get("known_problems", "")
                    if elements:
                        solution_scope = (
                            "The analysis covers the elements: " + ", ".join(elements) + ". "
                            "Initiative type: " + str(initiative) + ". "
                            "Context: " + str(problems[:200])
                        )

            except (json.JSONDecodeError, KeyError, IOError) as e:
                prefill_status += f"\n\n⚠️ Could not read 6.1 data: {e}."
        else:
            prefill_status += (
                f"\n\n⚠️ The 6.1 business-needs file not found: `{needs_path}`.\n"
                f"Complete task 6.1 for project `{from_current_state_project_id}`."
            )

    # ADR-055: prefill from 6.1 (old block placeholder removed)
    try:
        goals = json.loads(business_goals_json)
        if not isinstance(goals, list) or not goals:
            raise ValueError("The list must not be empty")
        for g in goals:
            if not isinstance(g, dict) or "id" not in g or "title" not in g:
                raise ValueError("Each objective must contain the fields 'id' and 'title'")
    except (json.JSONDecodeError, ValueError) as e:
        return (
            f"❌ Error parsing business_goals_json: {e}\n\n"
            f"Expected a JSON list: "
            f'\'[{{"id":"BG-001","title":"Reduce processing time","description":"...","kpi":"..."}}]\''
        )

    if not future_state.strip():
        return "❌ future_state cannot be empty — describe the desired future state."

    if not solution_scope.strip():
        return "❌ solution_scope cannot be empty — describe the solution boundaries."

    existing = _load_context(project_id)
    is_update = existing is not None

    data = {
        "project_id": project_id,
        "business_goals": goals,
        "future_state": future_state,
        "solution_scope": solution_scope,
        "potential_value": potential_value,
        "created_at": existing["created_at"] if existing else str(date.today()),
        "updated_at": str(date.today()),
    }

    _save_context(data)

    lines = [
        f"{'⚠️ Business context UPDATED' if is_update else '✅ Business context created'} — **{project_id}**",
        "",
        f"> ⚠️ **Temporary Chapter 6 surrogate** — migrate when tasks 6.1/6.2 are implemented (ADR-030)",
        "",
        f"**Date:** {date.today()}",
        "",
        f"## Business objectives ({len(goals)})",
        "",
    ]

    for g in goals:
        kpi = f" | KPI: {g['kpi']}" if g.get("kpi") else ""
        desc = f" — {g['description'][:80]}..." if g.get("description") and len(g.get("description","")) > 80 \
               else (f" — {g['description']}" if g.get("description") else "")
        lines.append(f"- **{g['id']}** {g['title']}{desc}{kpi}")

    lines += [
        "",
        f"## Future state",
        "",
        future_state[:200] + ("..." if len(future_state) > 200 else ""),
        "",
        f"## Solution boundaries",
        "",
        solution_scope[:200] + ("..." if len(solution_scope) > 200 else ""),
    ]

    if potential_value:
        lines += [
            "",
            f"## Potential value",
            "",
            potential_value[:200] + ("..." if len(potential_value) > 200 else ""),
        ]

    lines += [
        "",
        "---",
        "",
        "**Next step:**",
        f"`check_business_alignment(project_id='{project_id}')` — check req traceability to BG",
    ]

    if prefill_status:
        lines.append(prefill_status)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7.3.2 — check_business_alignment (ADR-030)
# ---------------------------------------------------------------------------

@mcp.tool()
def check_business_alignment(
    project_id: str,
    req_ids: str = "",
) -> str:
    """
    BABOK 7.3 — Checks traceability of requirements to business objectives.
    Methods: BFS search over 'business'-type nodes in repository 5.1 +
            title matching against BG-xxx from business_context.json.

    ADR-030: business objectives are taken from {project}_business_context.json.

    Args:
        project_id: Project identifier.
        req_ids:    JSON list of IDs to check: '["US-001", "FR-001"]'.
                    If empty — checks all verified reqs of the project.

    Returns:
        Coverage matrix: aligned / orphan / needs_review per req.
        Additionally: which BG are not covered by any req.
    """
    logger.info(f"check_business_alignment: project_id='{project_id}', req_ids='{req_ids}'")

    ctx = _load_context(project_id)
    if ctx is None:
        return (
            f"❌ Business context for project `{project_id}` not found.\n\n"
            f"First call: `set_business_context(project_id='{project_id}', ...)`"
        )

    repo = _load_repo(project_id)
    all_reqs = repo.get("requirements", [])

    if not all_reqs:
        return (
            f"⚠️ Repository 5.1 for project `{project_id}` is empty or not found.\n\n"
            f"Make sure requirements were created via the 7.1 tools."
        )

    # Filter
    if req_ids.strip():
        try:
            ids_to_check = json.loads(req_ids)
            if not isinstance(ids_to_check, list):
                raise ValueError
        except (json.JSONDecodeError, ValueError):
            return f"❌ Error parsing req_ids: expected a JSON list, e.g.: '[\"US-001\", \"FR-001\"]'"
        reqs_to_check = [r for r in all_reqs if r["id"] in ids_to_check]
        not_found = [i for i in ids_to_check if i not in {r["id"] for r in all_reqs}]
    else:
        # Take verified reqs (and validated — re-running is harmless)
        target_statuses = {"verified", "validated"}
        reqs_to_check = [r for r in all_reqs if r.get("status", "") in target_statuses]
        not_found = []

    if not reqs_to_check:
        return (
            f"ℹ️ No verified/validated requirements to check in project `{project_id}`.\n\n"
            f"Verify requirements via the 7.2 tools (`mark_req_verified`) "
            f"before validation."
        )

    goals = ctx.get("business_goals", [])
    goal_ids = {g["id"] for g in goals}
    goals_by_id = {g["id"]: g for g in goals}

    # Check each req
    aligned_reqs = []
    orphan_reqs = []
    needs_review_reqs = []

    # For the coverage matrix: which BG are covered
    covered_goals: set = set()

    for req in reqs_to_check:
        req_id = req["id"]
        req_type = req.get("type", "")

        # Skip the repo's own business nodes and test nodes
        if req_type in ("business", "test"):
            continue

        # Method 1: BFS to 'business'-type nodes
        bfs_nodes = _bfs_to_business(repo, req_id)
        bfs_goal_ids = {n["id"] for n in bfs_nodes if n["id"] in goal_ids}

        # Method 2: title matching against BG-xxx
        title_matched_goals = set()
        for g in goals:
            if _title_matches_goal(req.get("title", ""), g["title"]):
                title_matched_goals.add(g["id"])

        found_goals = bfs_goal_ids | title_matched_goals

        if found_goals:
            covered_goals |= found_goals
            aligned_reqs.append({
                "req_id": req_id,
                "title": req.get("title", ""),
                "aligned_goals": sorted(found_goals),
                "method": "bfs" if bfs_goal_ids else "title_match",
            })
        else:
            orphan_reqs.append({
                "req_id": req_id,
                "title": req.get("title", ""),
                "type": req_type,
            })

    # BG without coverage
    uncovered_goals = [g for g in goals if g["id"] not in covered_goals]

    # Build the report
    total = len(aligned_reqs) + len(orphan_reqs) + len(needs_review_reqs)
    aligned_pct = round(len(aligned_reqs) / total * 100, 1) if total > 0 else 0.0

    lines = [
        f"<!-- BABOK 7.3 — Business Alignment | Project: {project_id} | {date.today()} -->",
        "",
        f"# 🎯 Alignment with business objectives — {project_id}",
        "",
        f"**Date:** {date.today()}  ",
        f"**Reqs checked:** {total}  ",
        f"**Business objectives:** {len(goals)}",
        "",
        "## Summary",
        "",
        "| Status | Count |",
        "|--------|-----------|",
        f"| ✅ Aligned (has traceability to BG) | {len(aligned_reqs)} ({aligned_pct}%) |",
        f"| ❌ Orphan (no traceability to BG) | {len(orphan_reqs)} |",
        "",
    ]

    if not_found:
        lines += [
            f"⚠️ Not found in the repository: {', '.join(f'`{i}`' for i in not_found)}",
            "",
        ]

    # Coverage matrix
    lines += [
        "## Coverage Matrix — Business objectives",
        "",
        "| BG ID | Title | Req coverage |",
        "|-------|----------|-------------|",
    ]
    for g in goals:
        covered = g["id"] in covered_goals
        icon = "✅" if covered else "❌"
        covering_reqs = [r["req_id"] for r in aligned_reqs if g["id"] in r["aligned_goals"]]
        req_list = ", ".join(f"`{r}`" for r in covering_reqs[:5])
        if len(covering_reqs) > 5:
            req_list += f" +{len(covering_reqs)-5} more"
        lines.append(f"| `{g['id']}` | {g['title']} | {icon} {req_list or '—'} |")
    lines.append("")

    # Aligned req
    if aligned_reqs:
        lines += [
            "## ✅ Aligned requirements",
            "",
        ]
        for r in aligned_reqs:
            method_note = " _(BFS)_" if r["method"] == "bfs" else " _(title-match)_"
            goals_str = ", ".join(f"`{g}`" for g in r["aligned_goals"])
            lines.append(f"- `{r['req_id']}` — {r['title']} → {goals_str}{method_note}")
        lines.append("")

    # Orphan req
    if orphan_reqs:
        lines += [
            "## ❌ Requirements without traceability to business objectives (Orphans)",
            "",
            "> These requirements are not linked to any business objective.",
            "> They may be redundant or traceability via 5.1 is needed.",
            "",
        ]
        for r in orphan_reqs:
            lines.append(f"- `{r['req_id']}` ({r['type']}) — {r['title']}")
        lines.append("")

    # Uncovered BG
    if uncovered_goals:
        lines += [
            "## ⚠️ Business objectives without req coverage",
            "",
            "> These business objectives are not covered by any verified requirement.",
            "> Additional requirements may be needed.",
            "",
        ]
        for g in uncovered_goals:
            lines.append(f"- `{g['id']}` — {g['title']}")
        lines.append("")

    lines += [
        "---",
        "",
        "## Next steps",
        "",
    ]

    if orphan_reqs:
        lines.append("1. For each Orphan: check whether the req is needed and add traceability via 5.1 "
                     "(`add_trace_link`) or remove it as redundant.")
    if uncovered_goals:
        lines.append("2. For uncovered BG: create the missing reqs via the 7.1 tools.")
    lines += [
        "3. Record assumptions: `log_assumption(project_id=...)` for risky assumptions.",
        "4. Set success criteria: `set_success_criteria(project_id=...)` for critical reqs.",
        f"5. After resolving the problems: `mark_req_validated(project_id='{project_id}', req_ids='[...]')`",
    ]

    content = "\n".join(lines)
    save_artifact(content, prefix="7_3_business_alignment", project_id=project_id)
    return content


# ---------------------------------------------------------------------------
# 7.3.3 — set_success_criteria (ADR-032)
# ---------------------------------------------------------------------------

@mcp.tool()
def set_success_criteria(
    project_id: str,
    req_id: str,
    criteria_json: str,
) -> str:
    """
    BABOK 7.3 — Attaches a measurable success criterion to a requirement.
    An optional pipeline step (ADR-032). Recommended for critical reqs.

    The data is written to the success_criteria field of the req node in repository 5.1.
    Link to 8.1 (Measure Solution Performance): this data becomes the input.

    Args:
        project_id:    Project identifier.
        req_id:        Requirement ID (US-001, FR-003, etc.).
        criteria_json: JSON with the criteria:
                       '{"baseline":"...", "target":"...",
                         "measurement_method":"...", "kpi_ref":"BG-001"}'.

    Returns:
        Confirmation + a KPI hint from the linked business objective.
    """
    logger.info(f"set_success_criteria: project_id='{project_id}', req_id='{req_id}'")

    try:
        criteria = json.loads(criteria_json)
        if not isinstance(criteria, dict):
            raise ValueError("Expected a JSON object")
        required_fields = {"baseline", "target", "measurement_method"}
        missing = required_fields - set(criteria.keys())
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(sorted(missing))}")
    except (json.JSONDecodeError, ValueError) as e:
        return (
            f"❌ Error parsing criteria_json: {e}\n\n"
            f"Expected: "
            f'\'{{\"baseline\":\"current metric\",\"target\":\"target metric\","'
            f'"measurement_method\":\"how we measure\",\"kpi_ref\":\"BG-001\"}}\''
        )

    repo = _load_repo(project_id)
    req = _find_req(repo, req_id)

    if not req:
        return (
            f"❌ Requirement `{req_id}` not found in repository 5.1 of project `{project_id}`.\n"
            f"Available reqs: {', '.join(r['id'] for r in repo.get('requirements', [])[:10])}"
        )

    # KPI hint from the linked business objective
    kpi_hint = ""
    kpi_ref = criteria.get("kpi_ref", "")
    if kpi_ref:
        ctx = _load_context(project_id)
        if ctx:
            goals_by_id = {g["id"]: g for g in ctx.get("business_goals", [])}
            if kpi_ref in goals_by_id:
                goal = goals_by_id[kpi_ref]
                if goal.get("kpi"):
                    kpi_hint = f"\n💡 KPI of business objective `{kpi_ref}`: {goal['kpi']}"

    # Write into the req
    req["success_criteria"] = {
        "baseline": criteria.get("baseline", ""),
        "target": criteria.get("target", ""),
        "measurement_method": criteria.get("measurement_method", ""),
        "kpi_ref": kpi_ref,
        "set_date": str(date.today()),
    }

    repo["history"].append({
        "action": "success_criteria_set",
        "req_id": req_id,
        "source": "7.3_validate",
        "date": str(date.today()),
    })

    _save_repo(repo)

    lines = [
        f"✅ Success criterion attached to **{req_id}**",
        "",
        f"| Field | Value |",
        f"|------|----------|",
        f"| Requirement | `{req_id}` — {req.get('title', '')} |",
        f"| Baseline | {criteria['baseline']} |",
        f"| Target | {criteria['target']} |",
        f"| Measurement method | {criteria['measurement_method']} |",
        f"| KPI ref | {kpi_ref or '—'} |",
        f"| Date | {date.today()} |",
    ]

    if kpi_hint:
        lines.append("")
        lines.append(kpi_hint)

    lines += [
        "",
        "---",
        "",
        f"**Link to 8.1:** the success_criteria from 7.3 become the input for "
        f"Measure Solution Performance (Chapter 8).",
        "",
        f"Continue: `mark_req_validated` or add criteria for other reqs.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7.3.4 — log_assumption (ADR-031)
# ---------------------------------------------------------------------------

@mcp.tool()
def log_assumption(
    project_id: str,
    description: str,
    req_ids: str,
    risk_level: str,
    assigned_to: str = "",
) -> str:
    """
    BABOK 7.3 — Records an assumption with a risk_level and linked reqs.
    ADR-031: stored in {project}_assumptions.json, numbering AS-001/AS-002/...

    Args:
        project_id:  Project identifier.
        description: Text of the assumption.
        req_ids:     JSON list of linked reqs: '["US-001", "FR-003"]'.
        risk_level:  Risk level: high | medium | low.
        assigned_to: Whom it is assigned to for confirmation. Empty by default.

    Returns:
        Confirmation with the ID of the created assumption.
    """
    logger.info(f"log_assumption: project_id='{project_id}', risk_level='{risk_level}'")

    valid_risk_levels = {"high", "medium", "low"}
    if risk_level not in valid_risk_levels:
        return (
            f"❌ Invalid risk_level: '{risk_level}'.\n"
            f"Allowed values: high | medium | low"
        )

    if not description.strip():
        return "❌ description cannot be empty — describe the assumption."

    try:
        req_ids_list = json.loads(req_ids)
        if not isinstance(req_ids_list, list):
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        return (
            f"❌ Error parsing req_ids: expected a JSON list, "
            f"e.g.: '[\"US-001\", \"FR-001\"]'"
        )

    data = _load_assumptions(project_id)
    assumption_id = _next_assumption_id(data)

    data["assumptions"][assumption_id] = {
        "assumption_id": assumption_id,
        "description": description,
        "req_ids": req_ids_list,
        "risk_level": risk_level,
        "status": "open",
        "assigned_to": assigned_to or "",
        "created_at": str(date.today()),
        "resolved_at": None,
        "resolution_note": "",
    }

    # Update statistics
    _update_assumption_stats(data)
    _save_assumptions(data)

    risk_icons = {"high": "🔴", "medium": "🟡", "low": "🟢"}
    icon = risk_icons.get(risk_level, "")

    lines = [
        f"✅ Assumption recorded: **{assumption_id}**",
        "",
        f"| Field | Value |",
        f"|------|----------|",
        f"| ID | `{assumption_id}` |",
        f"| Risk level | {icon} {risk_level} |",
        f"| Linked reqs | {', '.join(f'`{r}`' for r in req_ids_list) or '—'} |",
        f"| Assigned to | {assigned_to or '—'} |",
        f"| Status | open |",
        f"| Date | {date.today()} |",
        "",
        f"**Description:** {description}",
    ]

    if risk_level == "high":
        lines += [
            "",
            f"> 🔴 **High risk assumption:** `mark_req_validated` will issue a warning "
            f"for reqs {', '.join(f'`{r}`' for r in req_ids_list)} "
            f"while this assumption remains open.",
        ]

    lines += [
        "",
        "---",
        "",
        f"**Next step:** confirm or refute the assumption:",
        f"`resolve_assumption(project_id='{project_id}', assumption_id='{assumption_id}', "
        f"resolution='confirmed|refuted', resolution_note='...')`",
    ]

    return "\n".join(lines)


def _update_assumption_stats(data: dict) -> None:
    """Recomputes the assumptions statistics."""
    all_assum = list(data["assumptions"].values())
    data["stats"]["open"] = sum(1 for a in all_assum if a["status"] == "open")
    data["stats"]["confirmed"] = sum(1 for a in all_assum if a["status"] == "confirmed")
    data["stats"]["refuted"] = sum(1 for a in all_assum if a["status"] == "refuted")


# ---------------------------------------------------------------------------
# 7.3.5 — resolve_assumption (ADR-031)
# ---------------------------------------------------------------------------

@mcp.tool()
def resolve_assumption(
    project_id: str,
    assumption_id: str,
    resolution: str,
    resolution_note: str,
) -> str:
    """
    BABOK 7.3 — Closes an assumption as confirmed or refuted.
    ADR-031: on refuted — a warning about the linked reqs.

    Args:
        project_id:      Project identifier.
        assumption_id:   Assumption ID: AS-001, AS-002, etc.
        resolution:      confirmed | refuted
        resolution_note: Exactly what confirmed or refuted the assumption.

    Returns:
        Confirmation of closure. On refuted — the list of reqs to revisit.
    """
    logger.info(f"resolve_assumption: project_id='{project_id}', assumption_id='{assumption_id}'")

    valid_resolutions = {"confirmed", "refuted"}
    if resolution not in valid_resolutions:
        return (
            f"❌ Invalid resolution: '{resolution}'.\n"
            f"Allowed values: confirmed | refuted"
        )

    if not resolution_note.strip():
        return "❌ resolution_note cannot be empty — describe exactly what confirmed/refuted it."

    data = _load_assumptions(project_id)

    if assumption_id not in data["assumptions"]:
        open_list = [k for k, v in data["assumptions"].items() if v["status"] == "open"]
        return (
            f"❌ Assumption `{assumption_id}` not found in project `{project_id}`.\n"
            f"Open: {', '.join(open_list) or 'none'}"
        )

    assumption = data["assumptions"][assumption_id]

    if assumption["status"] != "open":
        return (
            f"ℹ️ Assumption `{assumption_id}` is already closed "
            f"({assumption['status']}, {assumption.get('resolved_at', '?')}).\n"
            f"Resolution: {assumption.get('resolution_note', '—')}"
        )

    req_ids_affected = assumption.get("req_ids", [])

    assumption["status"] = resolution
    assumption["resolved_at"] = str(date.today())
    assumption["resolution_note"] = resolution_note

    _update_assumption_stats(data)
    _save_assumptions(data)

    icon = "✅" if resolution == "confirmed" else "❌"
    lines = [
        f"{icon} Assumption **{assumption_id}** closed as **{resolution}**.",
        "",
        f"| Field | Value |",
        f"|------|----------|",
        f"| ID | `{assumption_id}` |",
        f"| Resolution | {resolution} |",
        f"| Closed date | {date.today()} |",
        "",
        f"**Resolution note:** {resolution_note}",
        "",
        "---",
        "",
    ]

    if resolution == "refuted":
        lines += [
            "## ⚠️ Assumption refuted",
            "",
            "The linked requirements need to be revisited:",
            "",
        ]
        for req_id in req_ids_affected:
            lines.append(f"- `{req_id}` — check relevance in light of the refuted assumption")
        lines += [
            "",
            "> Rework of the requirements or a new round of elicitation (4.1–4.3) may be needed.",
        ]
    else:
        lines += [
            f"✅ Assumption confirmed. Requirements {', '.join(f'`{r}`' for r in req_ids_affected)} "
            f"remain relevant.",
        ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7.3.6 — mark_req_validated (ADR-033)
# ---------------------------------------------------------------------------

@mcp.tool()
def mark_req_validated(
    project_id: str,
    req_ids: str,
    force: bool = False,
) -> str:
    """
    BABOK 7.3 — Sets the 'validated' status in repository 5.1.
    Preconditions (ADR-033): warnings, not hard blocks.

    Checks:
      (1) req status = verified (from 7.2)
      (2) no open high-risk assumptions for the req in {project}_assumptions.json
      (3) traceability to a business objective exists (BFS or title matching)

    Args:
        project_id: Project identifier.
        req_ids:    JSON list of IDs: '["US-001", "FR-001"]'.
        force:      True — set validated even with warnings (override).

    Returns:
        A result per req: validated / warning.
    """
    logger.info(f"mark_req_validated: project_id='{project_id}', req_ids='{req_ids}'")

    try:
        ids_list = json.loads(req_ids)
        if not isinstance(ids_list, list) or not ids_list:
            raise ValueError
    except (json.JSONDecodeError, ValueError):
        return "❌ req_ids must be a non-empty JSON list: '[\"US-001\", \"FR-001\"]'"

    repo = _load_repo(project_id)
    data_assum = _load_assumptions(project_id)
    ctx = _load_context(project_id)
    goals = ctx.get("business_goals", []) if ctx else []
    goal_ids = {g["id"] for g in goals}

    results = []
    validated_count = 0
    warned_count = 0
    not_found_count = 0

    for req_id in ids_list:
        req = _find_req(repo, req_id)
        if not req:
            results.append({
                "req_id": req_id,
                "outcome": "not_found",
                "message": f"❌ `{req_id}` — not found in repository 5.1",
                "warnings": [],
            })
            not_found_count += 1
            continue

        warnings = []

        # Precondition 1: verified status
        current_status = req.get("status", "draft")
        if current_status not in ("verified", "validated"):
            warnings.append(
                f"Status '{current_status}' (expected 'verified'). "
                f"Verify the req via the 7.2 tools before validation."
            )

        # Precondition 2: open high-risk assumptions
        open_high_risk = [
            a for a in data_assum["assumptions"].values()
            if a["status"] == "open"
            and a.get("risk_level") == "high"
            and req_id in a.get("req_ids", [])
        ]
        if open_high_risk:
            ids_str = ", ".join(f"`{a['assumption_id']}`" for a in open_high_risk)
            warnings.append(
                f"There are open high-risk assumptions for this req: {ids_str}. "
                f"Close them via `resolve_assumption` or use force=True."
            )

        # Precondition 3: traceability to a business objective
        if goals:
            bfs_nodes = _bfs_to_business(repo, req_id)
            bfs_goal_ids = {n["id"] for n in bfs_nodes if n["id"] in goal_ids}
            title_matched = {
                g["id"] for g in goals
                if _title_matches_goal(req.get("title", ""), g["title"])
            }
            if not (bfs_goal_ids | title_matched):
                warnings.append(
                    f"No traceability to business objectives. "
                    f"Check `check_business_alignment` or add links in 5.1."
                )

        # Make the decision
        if warnings and not force:
            warned_count += 1
            results.append({
                "req_id": req_id,
                "outcome": "warned",
                "message": f"⚠️ `{req_id}` — warnings (not updated)",
                "warnings": warnings,
            })
        else:
            old_status = current_status
            req["status"] = "validated"

            repo["history"].append({
                "action": "req_validated",
                "req_id": req_id,
                "old_status": old_status,
                "new_status": "validated",
                "force": force,
                "source": "7.3_validate",
                "date": str(date.today()),
            })

            validated_count += 1
            outcome = "validated_with_warnings" if (warnings and force) else "validated"
            results.append({
                "req_id": req_id,
                "outcome": outcome,
                "message": f"✅ `{req_id}` — validated (was: {old_status})"
                           + (" [force override]" if force and warnings else ""),
                "warnings": warnings if force else [],
            })

    if validated_count > 0:
        _save_repo(repo)

    lines = [
        f"# Validation result — {project_id}",
        "",
        f"**Date:** {date.today()}  ",
        f"**Processed:** {len(ids_list)} requirements  ",
        f"**Validated:** ✅ {validated_count}  ",
        f"**With warnings (not updated):** ⚠️ {warned_count}  ",
        f"**Not found:** ❌ {not_found_count}",
        "",
        "## Details",
        "",
    ]

    for r in results:
        lines.append(r["message"])
        for w in r["warnings"]:
            lines.append(f"  ⚠️ {w}")

    if warned_count > 0:
        lines += [
            "",
            "---",
            "",
            f"⚠️ {warned_count} reqs were not updated due to warnings.",
            "Resolve the warnings or call again with `force=True` to override.",
            f"Example: `mark_req_validated(project_id='{project_id}', "
            f"req_ids='{req_ids}', force=True)`",
        ]

    if validated_count > 0:
        lines += [
            "",
            "---",
            "",
            f"✅ The `validated` status is set in repository 5.1.",
            f"Next step: `get_validation_report(project_id='{project_id}')` for the summary report.",
        ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 7.3.7 — get_validation_report
# ---------------------------------------------------------------------------

@mcp.tool()
def get_validation_report(
    project_id: str,
) -> str:
    """
    BABOK 7.3 — Generates a summary report on project validation.

    Contains:
      - % validated out of verified
      - Coverage matrix (BG -> req)
      - List of "orphans" without traceability to objectives
      - Open assumptions by risk_level
      - % of reqs with success_criteria
      - Verdict on readiness for 7.5 (Design Options)

    Saves Markdown via save_artifact.

    Args:
        project_id: Project identifier.

    Returns:
        Validation Report in Markdown.
    """
    logger.info(f"get_validation_report: project_id='{project_id}'")

    repo = _load_repo(project_id)
    all_reqs = repo.get("requirements", [])

    if not all_reqs:
        return (
            f"⚠️ No active requirements in the repository for project `{project_id}`.\n"
            f"Create requirements via the 7.1 tools before validation."
        )

    ctx = _load_context(project_id)
    data_assum = _load_assumptions(project_id)

    # Statistics by requirements
    skip_statuses = {"deprecated", "superseded", "retired"}
    skip_types = {"business", "test"}
    active_reqs = [
        r for r in all_reqs
        if r.get("status") not in skip_statuses
        and r.get("type", "") not in skip_types
    ]
    total = len(active_reqs)

    if total == 0:
        return (
            f"⚠️ No active requirements of a suitable type in project `{project_id}`.\n"
            f"Check that requirements were created via the 7.1 tools."
        )

    validated = [r for r in active_reqs if r.get("status") == "validated"]
    verified_only = [r for r in active_reqs if r.get("status") == "verified"]
    with_criteria = [r for r in active_reqs if r.get("success_criteria")]

    validated_pct = round(len(validated) / total * 100, 1) if total > 0 else 0.0
    criteria_pct = round(len(with_criteria) / total * 100, 1) if total > 0 else 0.0

    # Assumptions statistics
    all_assum = list(data_assum["assumptions"].values())
    open_assum = [a for a in all_assum if a["status"] == "open"]
    open_high = [a for a in open_assum if a.get("risk_level") == "high"]
    open_medium = [a for a in open_assum if a.get("risk_level") == "medium"]
    open_low = [a for a in open_assum if a.get("risk_level") == "low"]

    # Coverage matrix
    goals = ctx.get("business_goals", []) if ctx else []
    goal_ids = {g["id"] for g in goals}
    covered_goals: set = set()
    orphan_reqs = []

    for req in active_reqs:
        req_id = req["id"]
        if not goals:
            break
        bfs_nodes = _bfs_to_business(repo, req_id)
        bfs_goal_ids = {n["id"] for n in bfs_nodes if n["id"] in goal_ids}
        title_matched = {g["id"] for g in goals if _title_matches_goal(req.get("title", ""), g["title"])}
        found = bfs_goal_ids | title_matched
        if found:
            covered_goals |= found
        else:
            orphan_reqs.append(req)

    uncovered_goals = [g for g in goals if g["id"] not in covered_goals]

    # Readiness verdict for 7.5
    ready = (
        validated_pct >= 80
        and len(open_high) == 0
        and len(orphan_reqs) == 0
    )
    ready_label = "✅ Ready for 7.5 Design Options" if ready else "❌ Not ready for 7.5"

    # Build the report
    lines = [
        f"<!-- BABOK 7.3 — Validation Report | Project: {project_id} | {date.today()} -->",
        "",
        f"# 📋 Requirements validation report",
        "",
        f"**Project:** {project_id}  ",
        f"**Report date:** {date.today()}  ",
        f"**Readiness:** {ready_label}",
        "",
        "---",
        "",
        "## Requirements summary",
        "",
        "| Metric | Value |",
        "|------------|----------|",
        f"| Total active reqs | {total} |",
        f"| ✅ Validated | {len(validated)} ({validated_pct}%) |",
        f"| 🔍 Verified (not yet validated) | {len(verified_only)} |",
        f"| 📐 With success_criteria | {len(with_criteria)} ({criteria_pct}%) |",
        "",
    ]

    # Progress bar
    filled = int(validated_pct / 10)
    bar = "█" * filled + "░" * (10 - filled)
    lines.append(f"**Validation progress:** `[{bar}]` {validated_pct}%")
    lines.append("")

    # Assumptions
    lines += [
        "## Assumptions summary",
        "",
        "| Metric | Value |",
        "|------------|----------|",
        f"| Total assumptions | {len(all_assum)} |",
        f"| 🔴 Open high-risk | {len(open_high)} |",
        f"| 🟡 Open medium-risk | {len(open_medium)} |",
        f"| 🟢 Open low-risk | {len(open_low)} |",
        f"| ✅ Closed | {len([a for a in all_assum if a['status'] != 'open'])} |",
        "",
    ]

    # Coverage matrix
    if goals:
        lines += [
            "## Coverage Matrix — Business objectives",
            "",
            "| BG ID | Title | Covered? | Req |",
            "|-------|----------|---------|-----|",
        ]
        for g in goals:
            covered = g["id"] in covered_goals
            icon = "✅" if covered else "❌"
            covering_reqs = []
            for req in active_reqs:
                bfs_nodes = _bfs_to_business(repo, req["id"])
                bfs_ids = {n["id"] for n in bfs_nodes if n["id"] in goal_ids}
                title_m = {gi["id"] for gi in goals if _title_matches_goal(req.get("title",""), gi["title"])}
                if g["id"] in (bfs_ids | title_m):
                    covering_reqs.append(req["id"])
            req_str = ", ".join(f"`{r}`" for r in covering_reqs[:3])
            if len(covering_reqs) > 3:
                req_str += f" +{len(covering_reqs)-3}"
            lines.append(f"| `{g['id']}` | {g['title'][:40]} | {icon} | {req_str or '—'} |")
        lines.append("")

    # Orphan req
    if orphan_reqs:
        lines += [
            "## ❌ Reqs without traceability to business objectives",
            "",
            "> Reconsider whether these requirements are needed.",
            "",
        ]
        for r in orphan_reqs:
            lines.append(f"- `{r['id']}` ({r.get('type','')}) — {r.get('title','')}")
        lines.append("")

    # Uncovered BG
    if uncovered_goals:
        lines += [
            "## ⚠️ Business objectives without coverage",
            "",
        ]
        for g in uncovered_goals:
            lines.append(f"- `{g['id']}` — {g['title']}")
        lines.append("")

    # Open high-risk assumptions
    if open_high:
        lines += [
            "## 🔴 Open High-Risk Assumptions",
            "",
            "| AS ID | Description | Req | Assigned |",
            "|-------|----------|-----|-----------|",
        ]
        for a in open_high:
            desc_short = a["description"][:60] + ("..." if len(a["description"]) > 60 else "")
            req_str = ", ".join(f"`{r}`" for r in a.get("req_ids", []))
            lines.append(
                f"| `{a['assumption_id']}` | {desc_short} | {req_str} | {a.get('assigned_to') or '—'} |"
            )
        lines.append("")

    # Success criteria coverage
    if with_criteria:
        lines += [
            "## 📐 Criteria Success Coverage",
            "",
            f"**{len(with_criteria)}/{total} reqs** ({criteria_pct}%) have success_criteria.",
            "",
        ]
        if criteria_pct < 50:
            lines.append("⚠️ Fewer than 50% of reqs have success_criteria — add criteria for critical reqs via `set_success_criteria`.")
        lines.append("")

    # Validated reqs by type
    if validated:
        lines += [
            "## ✅ Validated requirements",
            "",
        ]
        by_type: dict = {}
        for r in validated:
            t = r.get("type", "other")
            by_type.setdefault(t, []).append(r["id"])
        for req_type, ids in sorted(by_type.items()):
            lines.append(f"**{req_type}:** {', '.join(f'`{i}`' for i in sorted(ids))}")
        lines.append("")

    # Verdict
    lines += [
        "---",
        "",
        "## Verdict and next steps",
        "",
    ]

    if ready:
        lines += [
            "### ✅ Ready for 7.5 Design Options",
            "",
            f"- **{len(validated)}** reqs in status `validated` are ready for solution-design work.",
            f"- No open high-risk assumptions.",
            f"- All reqs trace to business objectives.",
            "",
            "**Hand this report to 7.5:** proceed to defining design options.",
        ]
    else:
        reasons = []
        if validated_pct < 80:
            reasons.append(f"📊 Only {validated_pct}% of reqs validated (recommended ≥ 80%)")
        if open_high:
            reasons.append(f"🔴 {len(open_high)} open high-risk assumptions")
        if orphan_reqs:
            reasons.append(f"❌ {len(orphan_reqs)} reqs without traceability to business objectives")

        lines += [
            "### ❌ Not ready for 7.5",
            "",
        ]
        for r in reasons:
            lines.append(f"- {r}")
        lines += [
            "",
            "**Actions:**",
            "1. Close high-risk assumptions via `resolve_assumption`.",
            "2. Fix orphan reqs — add traceability or remove redundant ones.",
            f"3. Validate the remaining reqs via `mark_req_validated`.",
            f"4. Re-run `get_validation_report` for the updated status.",
        ]

    content = "\n".join(lines)
    save_artifact(content, prefix="7_3_validation_report", project_id=project_id)
    return content


if __name__ == "__main__":
    mcp.run()
