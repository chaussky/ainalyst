"""
BABOK 5.4 — Assess Requirements Changes
MCP tools for assessing requirements changes (Change Request pipeline).

Tools:
  - open_cr          — register a CR in the 5.1 repository
  - run_cr_impact    — BFS impact analysis, create modifies links
  - score_cr         — scoring across 5 axes + recommendation
  - resolve_cr       — record the decision, update statuses, generate a Decision Record

Storage:
  - The CR is stored as a "change_request" node in {project}_traceability_repo.json (5.1)
  - CR→requirement links: relation "modifies"
  - The CR Decision Record is saved via save_artifact

Integration:
  In:  5.1 repository (graph), 5.2 attributes (stability), 5.3 priorities, governance 3.3
  Out: CR Decision Record → 4.4 (communication), 5.5 (audit)
       under_change status on affected requirements → 5.2 (content update)

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
from datetime import date, datetime
from typing import Literal, Optional
from mcp.server.fastmcp import FastMCP
from skills.common import save_artifact, logger, DATA_DIR, data_path, normalize_project_id

mcp = FastMCP("BABOK_Requirements_Assess_Changes")

REPO_FILENAME = "traceability_repo.json"

# Relation types — the originals from 5.1 plus the new "modifies" for CRs
VALID_RELATIONS = {"derives", "depends", "satisfies", "verifies", "modifies"}

# CR Score thresholds for the preliminary verdict
SCORE_APPROVE = 8.0
SCORE_MODIFY = 4.0
SCORE_DEFER = 1.0

# Axis weights for the scoring formula
# Score = Benefit*2 + Urgency*1.5 + Impact*1 - Cost*1.5 - Schedule_Risk*1
SCORE_WEIGHTS = {
    "benefit": 2.0,
    "urgency": 1.5,
    "impact": 1.0,
    "cost": -1.5,          # High cost=3 → penalty -4.5; Low cost=1 → penalty -1.5
    "schedule_risk": -1.0, # High risk=3 → penalty -3.0; Low risk=1 → penalty -1.0
}

# Mapping of text ratings to numbers
BENEFIT_MAP = {"High": 3, "Medium": 2, "Low": 1}
COST_MAP = {"High": 3, "Medium": 2, "Low": 1}   # High cost = high penalty (not inverted)
URGENCY_MAP = {"Critical": 3, "High": 2, "Normal": 1}
IMPACT_MAP = {"High": 3, "Medium": 2, "Low": 1}
SCHEDULE_MAP = {"High": 3, "Medium": 2, "Low": 1}  # High risk = high penalty (matches the formula)


# ---------------------------------------------------------------------------
# Utilities — file layer
# ---------------------------------------------------------------------------

def _repo_path(project_name: str) -> str:
    safe = normalize_project_id(project_name)
    return data_path(project_name, f"{safe}_{REPO_FILENAME}")


def _load_repo(project_name: str) -> dict:
    path = _repo_path(project_name)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"project": project_name, "requirements": [], "links": [], "history": []}


def _save_repo(project_name: str, repo: dict) -> None:
    path = _repo_path(project_name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    repo["updated"] = str(date.today())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(repo, f, ensure_ascii=False, indent=2)


def _find_node(repo: dict, node_id: str) -> Optional[dict]:
    """Finds a node (requirement or CR) by ID."""
    for r in repo["requirements"]:
        if r["id"] == node_id:
            return r
    return None


def _find_links(repo: dict, node_id: str) -> list:
    """Returns all links where node_id appears as from or to."""
    return [lnk for lnk in repo["links"]
            if lnk["from"] == node_id or lnk["to"] == node_id]


def _bfs_impact(repo: dict, start_ids: list) -> list:
    """
    BFS traversal of the graph starting from a list of nodes.
    Returns a list of affected nodes with their relation types.
    """
    visited = set(start_ids)
    queue = list(start_ids)
    affected = []

    while queue:
        current_id = queue.pop(0)
        links = _find_links(repo, current_id)
        for lnk in links:
            neighbor_id = lnk["to"] if lnk["from"] == current_id else lnk["from"]
            relation = lnk.get("relation", "unknown")
            # Don't traverse modifies links recursively (CR→req, not req→req)
            if relation == "modifies":
                continue
            if neighbor_id not in visited:
                visited.add(neighbor_id)
                neighbor = _find_node(repo, neighbor_id)
                if neighbor:
                    affected.append({
                        "id": neighbor_id,
                        "title": neighbor.get("title", "—"),
                        "type": neighbor.get("type", "unknown"),
                        "relation": relation,
                        "via": current_id,
                        "status": neighbor.get("status", "unknown"),
                        "version": neighbor.get("version", "1.0"),
                        "stability": neighbor.get("stability", "Unknown"),
                        "priority": neighbor.get("priority", "—"),
                    })
                    queue.append(neighbor_id)

    return affected


def _calc_score(benefit: int, cost: int, urgency: int,
                impact: int, schedule_risk: int) -> float:
    """Calculates the CR Score using the weighted formula."""
    return (
        benefit * SCORE_WEIGHTS["benefit"]
        + urgency * SCORE_WEIGHTS["urgency"]
        + impact * SCORE_WEIGHTS["impact"]
        + cost * SCORE_WEIGHTS["cost"]              # High cost=3 → -4.5 (penalty)
        + schedule_risk * SCORE_WEIGHTS["schedule_risk"]  # High risk=3 → -3.0 (penalty)
    )


def _score_verdict(score: float) -> str:
    if score >= SCORE_APPROVE:
        return "✅ Approve"
    elif score >= SCORE_MODIFY:
        return "🟡 Modify"
    elif score >= SCORE_DEFER:
        return "⏳ Defer"
    else:
        return "❌ Reject"


def _get_version_minor(version_str: str) -> int:
    """Extracts the minor version from a string: '1.3' → 3."""
    try:
        parts = str(version_str).split(".")
        return int(parts[1]) if len(parts) > 1 else 0
    except (ValueError, IndexError):
        return 0


# ---------------------------------------------------------------------------
# 5.4.1 — Open a CR
# ---------------------------------------------------------------------------

@mcp.tool()
def open_cr(
    project_name: str,
    cr_id: str,
    title: str,
    description: str,
    initiator: str,
    cr_type: Literal["new_requirement", "change_existing", "delete", "architectural"],
    formality: Literal["standard", "high"],
    target_req_ids_json: str,
    urgency: Literal["Critical", "High", "Normal"] = "Normal",
    project_phase: Literal["discovery", "development", "pre_release", "post_release"] = "development",
    related_cr_ids_json: str = "[]",
    regulatory: bool = False,
) -> str:
    """
    BABOK 5.4 — Step 1: Register a Change Request in the 5.1 repository.

    The CR is created as a "change_request" node. Links to the target requirements
    are added during the run_cr_impact step (relation 'modifies').

    Args:
        project_name:          Project name.
        cr_id:                 Unique CR ID. Recommended format: CR-001, CR-002.
        title:                 Short CR title (up to 80 characters).
        description:           Detailed description of what needs to change and why.
        initiator:             Who requested the CR (role or stakeholder name).
        cr_type:               Type of change:
                               - new_requirement: adding a new requirement
                               - change_existing: changing an existing one
                               - delete: removing a requirement
                               - architectural: architectural change
        formality:             Assessment formality level:
                               - standard: a regular CR
                               - high: predictive project, close to release, regulatory
        target_req_ids_json:   JSON list of requirement IDs the CR affects directly.
                               Example: '["FR-001", "FR-003"]'
        urgency:               Urgency: Critical (regulator/safety) / High / Normal.
        project_phase:         Project phase (affects the automatic Schedule Risk).
        related_cr_ids_json:   JSON list of related CR IDs (if several CRs affect
                               the same requirements). Example: '["CR-001"]'
        regulatory:            True if the CR is driven by a change in law or regulation.
                               Automatically sets urgency = Critical.

    Returns:
        Confirmation that the CR was registered, with instructions for the next step.
    """
    logger.info(f"open_cr: {cr_id} / {project_name}")

    # Parse JSON parameters
    try:
        target_req_ids = json.loads(target_req_ids_json)
    except json.JSONDecodeError:
        return "❌ Error: `target_req_ids_json` must be a valid JSON list. Example: '[\"FR-001\"]'"

    try:
        related_cr_ids = json.loads(related_cr_ids_json)
    except json.JSONDecodeError:
        related_cr_ids = []

    # Regulatory CR → always Critical urgency
    if regulatory:
        urgency = "Critical"

    repo = _load_repo(project_name)

    # Check: does a CR with this ID already exist?
    if _find_node(repo, cr_id):
        return (
            f"⚠️ CR `{cr_id}` already exists in the `{project_name}` project repository.\n"
            f"Use a different ID, or review the existing CR."
        )

    # Check: do the target requirements exist?
    missing = [rid for rid in target_req_ids if not _find_node(repo, rid)]
    if missing:
        return (
            f"⚠️ The following requirements were not found in the repository: {missing}\n"
            f"Check the ID, or add the requirements via `init_traceability_repo` (5.1)."
        )

    # Create the CR node
    cr_node = {
        "id": cr_id,
        "type": "change_request",
        "title": title,
        "description": description,
        "initiator": initiator,
        "cr_type": cr_type,
        "formality": formality,
        "urgency": urgency,
        "project_phase": project_phase,
        "regulatory": regulatory,
        "target_req_ids": target_req_ids,
        "related_cr_ids": related_cr_ids,
        "status": "open",
        "opened_date": str(date.today()),
        "impact_analysis": None,
        "score": None,
        "decision": None,
    }

    repo["requirements"].append(cr_node)

    # History
    repo.setdefault("history", []).append({
        "date": str(date.today()),
        "action": "cr_opened",
        "cr_id": cr_id,
        "initiator": initiator,
    })

    _save_repo(project_name, repo)

    # Warnings
    warnings = []
    if project_phase == "pre_release":
        warnings.append("⚠️ Project in the pre_release phase — Schedule Risk will be raised automatically.")
    if regulatory:
        warnings.append("⚠️ Regulatory CR: Urgency = Critical, Reject is not allowed.")
    if related_cr_ids:
        warnings.append(f"ℹ️ Related to CR: {related_cr_ids} — recommended to assess together.")

    lines = [
        f"<!-- BABOK 5.4 — Open CR, Project: {project_name}, CR: {cr_id}, Date: {date.today()} -->",
        "",
        f"## ✅ CR registered: {cr_id}",
        "",
        f"**Title:** {title}",
        f"**Type:** {cr_type} | **Formality:** {formality} | **Urgency:** {urgency}",
        f"**Initiator:** {initiator}",
        f"**Target requirements:** {', '.join(target_req_ids)}",
        f"**Project phase:** {project_phase}",
        "",
    ]

    if warnings:
        lines += ["### Warnings", ""] + warnings + [""]

    lines += [
        "---",
        "",
        "## ➡️ Next step — Step 2: Impact analysis",
        "",
        f"Call `run_cr_impact` with parameters:",
        f"  - `project_name`: \"{project_name}\"",
        f"  - `cr_id`: \"{cr_id}\"",
        "",
        "The tool will run a BFS traversal of the 5.1 graph and show all affected requirements.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 5.4.2 — Impact analysis
# ---------------------------------------------------------------------------

@mcp.tool()
def run_cr_impact(
    project_name: str,
    cr_id: str,
) -> str:
    """
    BABOK 5.4 — Step 2: BFS impact analysis of the CR through the 5.1 traceability graph.

    Traverses the graph starting from the CR's target requirements, identifying all affected nodes.
    Creates 'modifies' links from the CR to the target requirements.
    Automatically computes the technical Impact and Schedule Risk axes.

    Args:
        project_name:  Project name.
        cr_id:         ID of a previously opened CR (from open_cr).

    Returns:
        Impact report: affected requirements by link type,
        automatic Impact and Schedule Risk ratings, warnings.
    """
    logger.info(f"run_cr_impact: {cr_id} / {project_name}")

    repo = _load_repo(project_name)
    cr = _find_node(repo, cr_id)

    if not cr:
        return f"❌ CR `{cr_id}` not found. Run `open_cr` first."

    if cr.get("type") != "change_request":
        return f"❌ `{cr_id}` is not a CR. Make sure you're passing a CR ID, not a requirement ID."

    if cr.get("status") != "open":
        return f"⚠️ CR `{cr_id}` has status `{cr['status']}`. Impact analysis only applies to open CRs."

    target_req_ids = cr.get("target_req_ids", [])

    # Create modifies links: CR → target requirements
    existing_modifies = {
        lnk["to"] for lnk in repo["links"]
        if lnk.get("from") == cr_id and lnk.get("relation") == "modifies"
    }
    for req_id in target_req_ids:
        if req_id not in existing_modifies:
            repo["links"].append({
                "from": cr_id,
                "to": req_id,
                "relation": "modifies",
                "added_date": str(date.today()),
            })

    # BFS traversal from the target requirements
    affected = _bfs_impact(repo, target_req_ids)

    # Group affected items by link type
    by_relation: dict = {}
    for item in affected:
        rel = item["relation"]
        by_relation.setdefault(rel, []).append(item)

    # Automatic Impact calculation
    total_affected = len(affected) + len(target_req_ids)
    if total_affected >= 8:
        impact_auto = "High"
        impact_score = 3
    elif total_affected >= 3:
        impact_auto = "Medium"
        impact_score = 2
    else:
        impact_auto = "Low"
        impact_score = 1

    # Automatic Schedule Risk calculation.
    # Non-inverted (High risk = 3): the formula subtracts ScheduleRisk*1, so a higher
    # risk value must yield a bigger penalty. High risk=3 → -3.0, Low risk=1 → -1.0.
    project_phase = cr.get("project_phase", "development")
    if project_phase == "pre_release":
        schedule_auto = "High"
        schedule_score = 3
    elif total_affected >= 8 or project_phase == "post_release":
        schedule_auto = "High"
        schedule_score = 3
    elif total_affected >= 3:
        schedule_auto = "Medium"
        schedule_score = 2
    else:
        schedule_auto = "Low"
        schedule_score = 1

    # Warnings: volatile requirements
    # Check both the affected (BFS) set and the target_req_ids themselves
    target_nodes = [_find_node(repo, rid) for rid in target_req_ids]
    target_nodes = [n for n in target_nodes if n]
    all_for_volatile = {item["id"]: item for item in affected}
    for n in target_nodes:
        all_for_volatile[n["id"]] = n
    volatile_reqs = [
        item for item in all_for_volatile.values()
        if _get_version_minor(item.get("version", "1.0")) >= 3
    ]

    # Warnings: priority conflicts
    priority_conflicts = []
    won_t_targets = [
        _find_node(repo, rid) for rid in target_req_ids
        if _find_node(repo, rid) and _find_node(repo, rid).get("priority") == "Won't"
    ]
    if won_t_targets:
        priority_conflicts = [r["id"] for r in won_t_targets if r]

    # Check traceability to a BR
    def _has_br_path(repo, req_id, visited=None):
        if visited is None:
            visited = set()
        if req_id in visited:
            return False
        visited.add(req_id)
        node = _find_node(repo, req_id)
        if node and node.get("type") == "business":
            return True
        for lnk in repo["links"]:
            # derives: from=child, to=parent. Follow from req_id toward parent (to)
            if lnk.get("from") == req_id and lnk.get("relation") == "derives":
                if _has_br_path(repo, lnk["to"], visited):
                    return True
        return False

    no_br_trace = [
        rid for rid in target_req_ids
        if not _has_br_path(repo, rid)
    ]

    # Save the impact analysis results to the CR node
    impact_data = {
        "affected_count": total_affected,
        "affected_ids": [item["id"] for item in affected] + target_req_ids,
        "impact_auto": impact_auto,
        "impact_score": impact_score,
        "schedule_auto": schedule_auto,
        "schedule_score": schedule_score,
        "by_relation": {k: [i["id"] for i in v] for k, v in by_relation.items()},
        "volatile_req_ids": [item["id"] for item in volatile_reqs],
        "priority_conflicts": priority_conflicts,
        "no_br_trace": no_br_trace,
        "analysis_date": str(date.today()),
    }
    cr["impact_analysis"] = impact_data

    _save_repo(project_name, repo)

    # Build the report
    lines = [
        f"<!-- BABOK 5.4 — Impact Analysis, Project: {project_name}, CR: {cr_id}, Date: {date.today()} -->",
        "",
        f"## 🔍 Impact analysis: {cr_id} — {cr['title']}",
        "",
        f"**Target requirements:** {', '.join(target_req_ids)}",
        f"**Total nodes affected:** {total_affected}",
        "",
        "### Automatic ratings of technical axes",
        "",
        f"| Axis | Value | Basis |",
        f"|------|-------|-------|",
        f"| Impact | **{impact_auto}** | {total_affected} affected nodes |",
        f"| Schedule Risk | **{schedule_auto}** | Phase: {project_phase}, scale: {total_affected} |",
        "",
    ]

    # Affected items by link type
    if affected:
        lines += ["### Affected nodes by link type", ""]
        relation_comments = {
            "depends": "dependents → may lose meaning",
            "verifies": "tests → need to be reviewed/rewritten",
            "satisfies": "code components → need to be redone",
            "derives": "child requirements → may inherit the change",
        }
        for rel, items in by_relation.items():
            comment = relation_comments.get(rel, "")
            lines.append(f"**`{rel}`** — {comment}")
            for item in items:
                priority_str = f" | priority: {item['priority']}" if item['priority'] != "—" else ""
                lines.append(
                    f"  - `{item['id']}` {item['title']} "
                    f"(v{item['version']}, {item['status']}{priority_str})"
                )
        lines.append("")
    else:
        lines += ["### Affected nodes", "", "✅ Isolated change — no related nodes found.", ""]

    # Warnings
    warnings_section = []
    if no_br_trace:
        warnings_section.append(
            f"🔴 **No traceability to a business requirement:** {no_br_trace}\n"
            f"   The CR must trace to a BR. Clarify the business rationale."
        )
    if priority_conflicts:
        warnings_section.append(
            f"🔴 **Priority conflict:** the target requirements {priority_conflicts} "
            f"are prioritized Won't. The CR changes that decision — requires explicit review in 5.3."
        )
    if volatile_reqs:
        volatile_ids = [r["id"] for r in volatile_reqs]
        warnings_section.append(
            f"🟡 **Volatile requirements:** {volatile_ids} (version 1.3+).\n"
            f"   An unstable requirement + a CR = double the uncertainty."
        )

    if warnings_section:
        lines += ["### ⚠️ Warnings", ""] + warnings_section + [""]

    lines += [
        "---",
        "",
        "## ➡️ Next step — Step 3: Score the CR",
        "",
        "The technical axes are filled in automatically. Provide the business axes and call `score_cr`:",
        "",
        f"  - `project_name`: \"{project_name}\"",
        f"  - `cr_id`: \"{cr_id}\"",
        f"  - `benefit`: High / Medium / Low — what does the business gain?",
        f"  - `cost`: Low / Medium / High — total cost including opportunity cost",
        f"  - `urgency`: {cr.get('urgency', 'Normal')} (already set in open_cr, can be changed)",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 5.4.3 — Score the CR
# ---------------------------------------------------------------------------

@mcp.tool()
def score_cr(
    project_name: str,
    cr_id: str,
    benefit: Literal["High", "Medium", "Low"],
    cost: Literal["Low", "Medium", "High"],
    urgency: Literal["Critical", "High", "Normal"] = "Normal",
    ba_notes: str = "",
) -> str:
    """
    BABOK 5.4 — Step 3: Score the CR across five axes + recommendation.

    The technical axes (Impact, Schedule Risk) come from run_cr_impact.
    The business axes (Benefit, Cost, Urgency) are entered by the BA.

    Formula: Score = Benefit*2 + Urgency*1.5 + Impact*1 - Cost*1.5 - ScheduleRisk*1

    Thresholds:
      ≥ 8.0 → Approve | 4.0–7.9 → Modify | 1.0–3.9 → Defer | < 1.0 → Reject

    Args:
        project_name:  Project name.
        cr_id:         CR ID (must have gone through run_cr_impact).
        benefit:       Business benefit: High / Medium / Low.
        cost:          Total cost of implementation (including opportunity cost):
                       Low / Medium / High.
        urgency:       Urgency (can override the value set in open_cr):
                       Critical / High / Normal.
        ba_notes:      Additional context from the BA to support the recommendation.

    Returns:
        CR Score, the formula's preliminary verdict, a text recommendation,
        results of automatic checks, instructions for the next step.
    """
    logger.info(f"score_cr: {cr_id} / {project_name}")

    repo = _load_repo(project_name)
    cr = _find_node(repo, cr_id)

    if not cr:
        return f"❌ CR `{cr_id}` not found. Run `open_cr` first."

    if cr.get("type") != "change_request":
        return f"❌ `{cr_id}` is not a CR."

    if not cr.get("impact_analysis"):
        return (
            f"❌ Impact analysis has not been run for CR `{cr_id}`.\n"
            f"Run `run_cr_impact` first."
        )

    impact_data = cr["impact_analysis"]

    # Numeric axis values
    benefit_n = BENEFIT_MAP[benefit]
    cost_n = COST_MAP[cost]          # High cost=3 → penalty via the negative weight
    urgency_n = URGENCY_MAP[urgency]
    impact_n = impact_data["impact_score"]
    schedule_n = impact_data["schedule_score"]  # High risk=3, Low risk=1 (penalty via negative weight)

    # Score calculation
    score = _calc_score(benefit_n, cost_n, urgency_n, impact_n, schedule_n)
    score = round(score, 1)
    verdict = _score_verdict(score)

    # Regulatory CR — Reject is not allowed
    regulatory = cr.get("regulatory", False)
    if regulatory and score < SCORE_DEFER:
        verdict = "⏳ Defer (Reject not allowed — regulatory CR)"

    # Automatic checks
    checks = []
    no_br_trace = impact_data.get("no_br_trace", [])
    priority_conflicts = impact_data.get("priority_conflicts", [])
    volatile_reqs = impact_data.get("volatile_req_ids", [])

    if no_br_trace:
        checks.append(f"🔴 No traceability to a BR: {no_br_trace} — clarify the business rationale")
    if priority_conflicts:
        checks.append(f"🔴 Conflict with Won't priorities: {priority_conflicts} — requires review in 5.3")
    if volatile_reqs:
        checks.append(f"🟡 Volatile requirements in the impact zone: {volatile_reqs}")

    # Text recommendation (contextual)
    recommendation_parts = []

    if score >= SCORE_APPROVE:
        recommendation_parts.append(
            f"The CR demonstrates high value (Benefit: {benefit}) at an acceptable cost "
            f"(Cost: {cost}). The impact scale {impact_data['impact_auto']} ({impact_data['affected_count']} nodes) "
            f"is manageable."
        )
        if urgency == "Critical":
            recommendation_parts.append("Critical urgency further justifies immediate acceptance.")
    elif score >= SCORE_MODIFY:
        recommendation_parts.append(
            f"The CR has potential, but the current value/cost balance needs review. "
            f"Consider narrowing the scope to reduce Cost or Schedule Risk."
        )
        if impact_data["impact_auto"] == "High":
            recommendation_parts.append(
                f"The impact scale is high ({impact_data['affected_count']} nodes) — "
                f"it may make sense to split the CR into several smaller ones."
            )
    elif score >= SCORE_DEFER:
        recommendation_parts.append(
            f"The CR is not justified for the current iteration. The value ({benefit}) does not outweigh "
            f"the cost ({cost}) and schedule risk ({impact_data['schedule_auto']})."
        )
        recommendation_parts.append("Recommend revisiting the CR in a future iteration with a refined rationale.")
    else:
        recommendation_parts.append(
            f"The cost of implementing the CR significantly exceeds the expected value. "
            f"Cost: {cost}, Schedule Risk: {impact_data['schedule_auto']}, Benefit: {benefit}."
        )
        if not regulatory:
            recommendation_parts.append("Recommend rejecting with an explicit rationale for the audit trail.")

    if ba_notes:
        recommendation_parts.append(f"\n**Context from the BA:** {ba_notes}")

    if checks:
        recommendation_parts.append(
            "\n**Note:** issues were found (see automatic checks below) "
            "that may affect the final decision regardless of the score."
        )

    # Save the scoring to the CR node
    score_data = {
        "benefit": benefit,
        "benefit_n": benefit_n,
        "cost": cost,
        "cost_n": cost_n,
        "urgency": urgency,
        "urgency_n": urgency_n,
        "impact_auto": impact_data["impact_auto"],
        "impact_n": impact_n,
        "schedule_auto": impact_data["schedule_auto"],
        "schedule_n": schedule_n,
        "total_score": score,
        "formula_verdict": verdict,
        "ba_notes": ba_notes,
        "scored_date": str(date.today()),
    }
    cr["score"] = score_data
    cr["urgency"] = urgency  # update urgency if it was overridden

    _save_repo(project_name, repo)

    # Build the report
    lines = [
        f"<!-- BABOK 5.4 — CR Score, Project: {project_name}, CR: {cr_id}, Score: {score}, Date: {date.today()} -->",
        "",
        f"## 📊 CR scoring: {cr_id} — {cr['title']}",
        "",
        "### Axis ratings",
        "",
        "| Axis | Value | Num. | Source |",
        "|------|-------|------|--------|",
        f"| Benefit (×2.0) | {benefit} | {benefit_n} | BA |",
        f"| Cost (×1.5, inv.) | {cost} | {cost_n} | BA |",
        f"| Urgency (×1.5) | {urgency} | {urgency_n} | BA |",
        f"| Impact (×1.0) | {impact_data['impact_auto']} | {impact_n} | Auto (5.1) |",
        f"| Schedule Risk (×1.0, inv.) | {impact_data['schedule_auto']} | {schedule_n} | Auto (5.1) |",
        "",
        "### Result",
        "",
        f"**CR Score: {score}**",
        "",
        f"**Formula's preliminary verdict: {verdict}**",
        "",
        "### Recommendation",
        "",
        " ".join(recommendation_parts),
        "",
    ]

    if checks:
        lines += ["### ⚠️ Automatic checks", ""] + [f"- {c}" for c in checks] + [""]

    lines += [
        "---",
        "",
        "## ➡️ Next step — Step 4: Record the decision",
        "",
        "Get a decision from an authorized stakeholder (from governance 3.3) and call `resolve_cr`:",
        "",
        f"  - `project_name`: \"{project_name}\"",
        f"  - `cr_id`: \"{cr_id}\"",
        f"  - `decision`: Approved / Approved_with_Modification / Deferred / Rejected",
        f"  - `decided_by`: who made the decision",
        f"  - `rationale`: rationale (required for the audit trail)",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 5.4.4 — Record the decision
# ---------------------------------------------------------------------------

@mcp.tool()
def resolve_cr(
    project_name: str,
    cr_id: str,
    decision: Literal["Approved", "Approved_with_Modification", "Deferred", "Rejected"],
    decided_by: str,
    rationale: str,
    modification_notes: str = "",
) -> str:
    """
    BABOK 5.4 — Step 4: Record the decision on a CR.

    For Approved / Approved_with_Modification:
      - The status of affected requirements changes to 'under_change'
      - A CR Decision Record (Markdown) is generated via save_artifact

    For Deferred / Rejected:
      - Requirements are not changed
      - The CR is saved in the repository with status deferred/rejected (audit trail)
      - A CR Decision Record is generated

    Args:
        project_name:         Project name.
        cr_id:                CR ID (must have gone through score_cr).
        decision:             Decision:
                              - Approved: accept the CR in full
                              - Approved_with_Modification: accept with a modified scope
                              - Deferred: postpone until a future iteration
                              - Rejected: reject
        decided_by:           Who made the decision (role/name from governance 3.3).
        rationale:            Rationale for the decision. Required — used in the audit trail.
        modification_notes:   Description of scope changes (only for Approved_with_Modification).

    Returns:
        The CR Decision Record (Markdown), saved via save_artifact.
        The status of updated requirements when Approved.
        Instructions for the next steps.
    """
    logger.info(f"resolve_cr: {cr_id} / {decision} / {project_name}")

    repo = _load_repo(project_name)
    cr = _find_node(repo, cr_id)

    if not cr:
        return f"❌ CR `{cr_id}` not found. Run `open_cr` first."

    if cr.get("type") != "change_request":
        return f"❌ `{cr_id}` is not a CR."

    if not cr.get("score"):
        return (
            f"❌ Scoring has not been done for CR `{cr_id}`.\n"
            f"Run `score_cr` first."
        )

    # Check: a regulatory CR cannot be Rejected
    if decision == "Rejected" and cr.get("regulatory"):
        return (
            f"❌ Regulatory CR `{cr_id}` cannot be rejected.\n"
            f"Regulatory requirements are mandatory. "
            f"Use Deferred if you need to postpone it for scheduling reasons."
        )

    # Update the CR status
    cr["status"] = decision.lower().replace("_with_modification", "_modified")
    cr["decision"] = {
        "verdict": decision,
        "decided_by": decided_by,
        "rationale": rationale,
        "modification_notes": modification_notes,
        "decision_date": str(date.today()),
    }

    # On Approved — change the status of affected requirements to under_change
    updated_reqs = []
    if decision in ("Approved", "Approved_with_Modification"):
        impact_data = cr.get("impact_analysis", {})
        affected_ids = impact_data.get("affected_ids", []) + cr.get("target_req_ids", [])
        affected_ids = list(set(affected_ids))  # deduplicate

        for req_id in affected_ids:
            req = _find_node(repo, req_id)
            if req and req.get("type") != "change_request":
                old_status = req.get("status", "unknown")
                req["status"] = "under_change"
                req.setdefault("history", []).append({
                    "date": str(date.today()),
                    "action": "status_changed",
                    "from": old_status,
                    "to": "under_change",
                    "reason": f"CR {cr_id} approved by {decided_by}",
                })
                updated_reqs.append(req_id)

    # History in the repository
    repo.setdefault("history", []).append({
        "date": str(date.today()),
        "action": "cr_resolved",
        "cr_id": cr_id,
        "decision": decision,
        "decided_by": decided_by,
        "updated_requirements": updated_reqs,
    })

    _save_repo(project_name, repo)

    # Build the CR Decision Record
    score_data = cr["score"]
    impact_data = cr.get("impact_analysis", {})

    decision_icon = {
        "Approved": "✅",
        "Approved_with_Modification": "✅🔧",
        "Deferred": "⏳",
        "Rejected": "❌",
    }.get(decision, "—")

    record_lines = [
        f"<!-- BABOK 5.4 — CR Decision Record, Project: {project_name}, CR: {cr_id}, Date: {date.today()} -->",
        "",
        f"# CR Decision Record: {cr_id}",
        f"**Project:** {project_name}  ",
        f"**Date:** {date.today()}  ",
        f"**Decision:** {decision_icon} {decision}  ",
        f"**Decided by:** {decided_by}  ",
        "",
        "---",
        "",
        "## CR description",
        "",
        f"**Title:** {cr['title']}  ",
        f"**Type:** {cr.get('cr_type', '—')} | **Initiator:** {cr.get('initiator', '—')}  ",
        f"**Opened:** {cr.get('opened_date', '—')}  ",
        f"**Regulatory:** {'Yes' if cr.get('regulatory') else 'No'}  ",
        "",
        f"{cr.get('description', '')}",
        "",
        "---",
        "",
        "## Impact analysis",
        "",
        f"**Target requirements:** {', '.join(cr.get('target_req_ids', []))}  ",
        f"**Total nodes affected:** {impact_data.get('affected_count', '—')}  ",
        f"**Impact:** {impact_data.get('impact_auto', '—')} | **Schedule Risk:** {impact_data.get('schedule_auto', '—')}  ",
        "",
        "---",
        "",
        "## Scoring",
        "",
        "| Axis | Value |",
        "|------|-------|",
        f"| Benefit | {score_data.get('benefit', '—')} |",
        f"| Cost | {score_data.get('cost', '—')} |",
        f"| Urgency | {score_data.get('urgency', '—')} |",
        f"| Impact | {score_data.get('impact_auto', '—')} |",
        f"| Schedule Risk | {score_data.get('schedule_auto', '—')} |",
        f"| **CR Score** | **{score_data.get('total_score', '—')}** |",
        f"| Formula verdict | {score_data.get('formula_verdict', '—')} |",
        "",
    ]

    if score_data.get("ba_notes"):
        record_lines += [f"**BA context:** {score_data['ba_notes']}  ", ""]

    record_lines += [
        "---",
        "",
        "## Decision",
        "",
        f"**{decision_icon} {decision}**  ",
        f"**Decided by:** {decided_by}  ",
        f"**Decision date:** {date.today()}  ",
        "",
        f"**Rationale:**  ",
        f"{rationale}",
        "",
    ]

    if modification_notes:
        record_lines += [
            f"**Scope changes:**  ",
            f"{modification_notes}",
            "",
        ]

    # Next steps
    next_steps = []
    if decision in ("Approved", "Approved_with_Modification"):
        if updated_reqs:
            next_steps.append(
                f"1. Update the content of requirements {updated_reqs} via `update_requirement` (5.2)"
            )
        next_steps.append("2. Review the priorities of affected requirements in 5.3")
        next_steps.append("3. Send the Decision Record to stakeholders via `prepare_communication_package` (4.4)")
        next_steps.append(f"4. Record the decision in the Decision Log via `log_decision` (4.5)")
    elif decision == "Deferred":
        next_steps.append("1. Revisit the CR in a future iteration — re-review Benefit/Cost")
        next_steps.append("2. Notify the CR initiator of the postponement via `prepare_communication_package` (4.4)")
    else:  # Rejected
        next_steps.append("1. Notify the CR initiator of the rejection with the rationale (4.4)")
        next_steps.append("2. The CR is kept in the repository for the audit trail")

    if next_steps:
        record_lines += ["## Next steps", ""] + next_steps + [""]

    record_lines += ["---", "", "*Generated by: AInalyst BABOK 5.4*"]

    artifact_content = "\n".join(record_lines)
    save_path = save_artifact(artifact_content, prefix=f"5_4_cr_decision_{cr_id}", project_id=project_name)

    # Final output
    output_lines = [
        f"## {decision_icon} CR {cr_id} — {decision}",
        "",
        f"**Decided by:** {decided_by}  ",
        f"**Rationale:** {rationale}",
        "",
    ]

    if updated_reqs:
        output_lines += [
            f"### Updated requirements",
            "",
            f"The following requirements were moved to status `under_change`:",
            ", ".join(f"`{r}`" for r in updated_reqs),
            "",
            "⚠️ Update the requirements' content via `update_requirement` (5.2).",
            "",
        ]

    if modification_notes:
        output_lines += [
            "### Scope changes",
            "",
            modification_notes,
            "",
        ]

    output_lines += [
        "### Next steps",
        "",
    ] + next_steps + ["", save_path]

    return "\n".join(output_lines)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
