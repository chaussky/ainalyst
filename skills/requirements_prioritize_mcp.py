"""
BABOK 5.3 — Prioritize Requirements
MCP tools for prioritizing requirements and designs.

Tools:
  - start_prioritization_session  — open a session, choose a method, get the requirement list
  - add_stakeholder_scores        — add one stakeholder's scores
  - run_aggregation               — aggregate scores, surface conflicts and dependency violations
  - resolve_conflict              — record a conflict resolution decision
  - save_prioritization_result    — finalize the session, update the 5.1 repository

Storage:
  - Priorities are written to {project}_traceability_repo.json (the priority field on each requirement)
  - Session snapshots are stored in {project}_prioritization.json

Integration:
  In:  5.1 repository (dependencies), 5.2 attributes (stability), 4.2 registry (influence)
  Out: prioritized requirements → 6.3 (Assess Risks)

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
from datetime import date, datetime
from typing import Literal, Optional
from mcp.server.fastmcp import FastMCP
from skills.common import (save_artifact, logger, DATA_DIR, data_path,
                           normalize_project_id, NON_REQUIREMENT_NODE_TYPES,
    read_json_artifact, guard_artifact_errors, parse_json_dict_list,
)

mcp = FastMCP("BABOK_Requirements_Prioritize")

REPO_FILENAME = "traceability_repo.json"
PRIO_FILENAME = "prioritization.json"

# MoSCoW numeric weights for aggregation
MOSCOW_WEIGHTS = {"Must": 4, "Should": 3, "Could": 2, "Won't": 1}
MOSCOW_THRESHOLDS = [("Must", 3.5), ("Should", 2.5), ("Could", 1.5), ("Won't", 0.0)]

# Influence weights for weighted voting
INFLUENCE_WEIGHTS = {"High": 3, "Medium": 2, "Low": 1}

# Must Inflation threshold
MUST_INFLATION_THRESHOLD = 0.6

# Stability — minor-version thresholds (match 5.2)
VOLATILITY_WARNING = 3   # 1.3+
VOLATILITY_CRITICAL = 4  # 1.4+


# ---------------------------------------------------------------------------
# Utilities — file layer
# ---------------------------------------------------------------------------

def _repo_path(project_name: str) -> str:
    safe = normalize_project_id(project_name)
    return data_path(project_name, f"{safe}_{REPO_FILENAME}")


def _prio_path(project_name: str) -> str:
    safe = normalize_project_id(project_name)
    return data_path(project_name, f"{safe}_{PRIO_FILENAME}")


def _load_repo(project_name: str) -> dict:
    path = _repo_path(project_name)
    if os.path.exists(path):
        # Raises CorruptArtifactError, converted to a ❌ line by guard_artifact_errors
        # at the tool boundary. A bare json.load here made a damaged file a protocol
        # error in every downstream tool.
        return read_json_artifact(path, "5.1 traceability repository")
    return {"project": project_name, "requirements": [], "links": [], "history": []}


def _save_repo(project_name: str, repo: dict) -> None:
    path = _repo_path(project_name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    repo["updated"] = str(date.today())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(repo, f, ensure_ascii=False, indent=2)


def _load_prio(project_name: str) -> dict:
    path = _prio_path(project_name)
    if os.path.exists(path):
        # Raises CorruptArtifactError, converted to a ❌ line by guard_artifact_errors
        # at the tool boundary. A bare json.load here made a damaged file a protocol
        # error in every downstream tool.
        return read_json_artifact(path, "5.3 prioritization file")
    return {"project": project_name, "sessions": []}


def _save_prio(project_name: str, prio: dict) -> None:
    path = _prio_path(project_name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(prio, f, ensure_ascii=False, indent=2)


def _find_session(sessions: list, label: str) -> Optional[dict]:
    for s in sessions:
        if s["label"] == label:
            return s
    return None


# ---------------------------------------------------------------------------
# Utilities — method logic
# ---------------------------------------------------------------------------

def _minor_version(version_str: str) -> int:
    """Extracts the minor part of the version: '1.3' → 3"""
    try:
        parts = str(version_str).split(".")
        if len(parts) >= 2:
            return int(parts[1])
        return 0
    except (ValueError, IndexError):
        return 0


def _stability_flag(node: dict) -> Optional[str]:
    """Returns a stability flag, or None if all is fine."""
    version = node.get("version", "1.0")
    minor = _minor_version(version)
    if minor >= VOLATILITY_CRITICAL:
        return "critical"
    if minor >= VOLATILITY_WARNING:
        return "warning"
    if node.get("stability") == "Unknown":
        return "unknown"
    return None


def _aggregate_moscow(scores_by_sh: dict, influence_by_sh: dict) -> dict:
    """
    Aggregates MoSCoW scores from multiple stakeholders, weighted by influence.
    Returns {req_id: {"priority": "Must"|..., "weighted_score": float}}
    """
    # Collect all req_id's
    all_reqs = set()
    for sh_scores in scores_by_sh.values():
        all_reqs.update(sh_scores.keys())

    result = {}
    for req_id in all_reqs:
        total_weight = 0.0
        weighted_sum = 0.0
        for sh_id, sh_scores in scores_by_sh.items():
            if req_id not in sh_scores:
                continue
            raw = sh_scores[req_id]
            score = MOSCOW_WEIGHTS.get(raw, 2)
            weight = INFLUENCE_WEIGHTS.get(influence_by_sh.get(sh_id, "Medium"), 2)
            weighted_sum += score * weight
            total_weight += weight

        if total_weight == 0:
            result[req_id] = {"priority": "Could", "weighted_score": 2.0}
            continue

        ws = weighted_sum / total_weight
        priority = "Won't"
        for label, threshold in MOSCOW_THRESHOLDS:
            if ws >= threshold:
                priority = label
                break
        result[req_id] = {"priority": priority, "weighted_score": round(ws, 2)}

    return result


def _aggregate_wsjf(scores_by_sh: dict, influence_by_sh: dict) -> dict:
    """
    Aggregates WSJF scores.
    scores_by_sh[sh_id][req_id] = {"bv": N, "tc": N, "rr": N, "js": N}
    Returns {req_id: {"priority_score": float, "wsjf": float, "cod": float, "js": float}}
    """
    all_reqs = set()
    for sh_scores in scores_by_sh.values():
        all_reqs.update(sh_scores.keys())

    result = {}
    for req_id in all_reqs:
        bv_sum = tc_sum = rr_sum = js_sum = 0.0
        total_weight = 0.0

        for sh_id, sh_scores in scores_by_sh.items():
            if req_id not in sh_scores:
                continue
            s = sh_scores[req_id]
            weight = INFLUENCE_WEIGHTS.get(influence_by_sh.get(sh_id, "Medium"), 2)
            bv_sum += s.get("bv", 0) * weight
            tc_sum += s.get("tc", 0) * weight
            rr_sum += s.get("rr", 0) * weight
            # Job Size — a technical estimate, not weighted by influence
            js_sum += s.get("js", 1)
            total_weight += weight

        if total_weight == 0:
            continue

        cod = (bv_sum + tc_sum + rr_sum) / total_weight
        # Average JS over the number of stakeholders who provided it
        n_sh = sum(1 for sh_scores in scores_by_sh.values() if req_id in sh_scores)
        js = js_sum / n_sh if n_sh > 0 else 1.0
        wsjf = round(cod / js, 2) if js > 0 else 0.0

        result[req_id] = {
            "priority_score": wsjf,
            "wsjf": wsjf,
            "cod": round(cod, 2),
            "js": round(js, 2),
        }

    # Normalize to MoSCoW-compatible labels for consistency
    if result:
        scores = [v["wsjf"] for v in result.values()]
        max_s = max(scores) if scores else 1
        for req_id, v in result.items():
            ratio = v["wsjf"] / max_s if max_s > 0 else 0
            if ratio >= 0.7:
                v["priority"] = "Must"
            elif ratio >= 0.4:
                v["priority"] = "Should"
            elif ratio >= 0.2:
                v["priority"] = "Could"
            else:
                v["priority"] = "Won't"

    return result


def _aggregate_impact_effort(scores_by_sh: dict, influence_by_sh: dict,
                              quadrant_mapping: dict) -> dict:
    """
    Aggregates Impact/Effort scores.
    scores_by_sh[sh_id][req_id] = {"impact": "High"|"Medium"|"Low", "effort": ...}
    quadrant_mapping: {"QuickWins": "Must", "BigBets": "Should", ...}
    """
    level_num = {"High": 3, "Medium": 2, "Low": 1}
    all_reqs = set()
    for sh_scores in scores_by_sh.values():
        all_reqs.update(sh_scores.keys())

    result = {}
    for req_id in all_reqs:
        imp_sum = eff_sum = total_weight = 0.0

        for sh_id, sh_scores in scores_by_sh.items():
            if req_id not in sh_scores:
                continue
            s = sh_scores[req_id]
            weight = INFLUENCE_WEIGHTS.get(influence_by_sh.get(sh_id, "Medium"), 2)
            imp_sum += level_num.get(s.get("impact", "Medium"), 2) * weight
            eff_sum += level_num.get(s.get("effort", "Medium"), 2) * weight
            total_weight += weight

        if total_weight == 0:
            continue

        avg_imp = imp_sum / total_weight
        avg_eff = eff_sum / total_weight

        # Determine the quadrant
        if avg_imp >= 2.5 and avg_eff < 2.5:
            quadrant = "QuickWins"
        elif avg_imp >= 2.5 and avg_eff >= 2.5:
            quadrant = "BigBets"
        elif avg_imp < 2.5 and avg_eff < 2.5:
            quadrant = "FillIns"
        else:
            quadrant = "ThanklessTasks"

        priority = quadrant_mapping.get(quadrant, "Could")
        result[req_id] = {
            "priority": priority,
            "quadrant": quadrant,
            "avg_impact": round(avg_imp, 2),
            "avg_effort": round(avg_eff, 2),
        }

    return result


def _find_dependency_violations(repo: dict, priorities: dict) -> list:
    """
    Looks for dependency violations: a requirement with Must/Should depends on a lower-priority requirement.
    Returns a list of {"req_id", "depends_on", "req_priority", "dep_priority"}
    """
    violations = []
    order = {"Must": 4, "Should": 3, "Could": 2, "Won't": 1}

    for edge in repo.get("links", []):
        if edge.get("relation") != "depends":
            continue
        from_id = edge.get("from")
        to_id = edge.get("to")
        from_prio = priorities.get(from_id, {}).get("priority") if isinstance(
            priorities.get(from_id), dict) else priorities.get(from_id)
        to_prio = priorities.get(to_id, {}).get("priority") if isinstance(
            priorities.get(to_id), dict) else priorities.get(to_id)

        if from_prio and to_prio:
            if order.get(from_prio, 0) > order.get(to_prio, 0):
                violations.append({
                    "req_id": from_id,
                    "depends_on": to_id,
                    "req_priority": from_prio,
                    "dep_priority": to_prio,
                })
    return violations


def _detect_stakeholder_conflicts(scores_by_sh: dict, method: str) -> list:
    """
    Looks for conflicts between stakeholders.
    MoSCoW: a spread of ≥ 2 categories.
    Returns a list of {"req_id", "conflict_type", "scores", "severity"}
    """
    if method != "MoSCoW":
        return []  # for WSJF and IE, conflicts surface through aggregation

    order = {"Must": 4, "Should": 3, "Could": 2, "Won't": 1}
    conflicts = []

    all_reqs = set()
    for sh_scores in scores_by_sh.values():
        all_reqs.update(sh_scores.keys())

    for req_id in all_reqs:
        req_scores = {sh_id: sh_scores[req_id]
                      for sh_id, sh_scores in scores_by_sh.items()
                      if req_id in sh_scores}
        if len(req_scores) < 2:
            continue

        values = [order.get(v, 2) for v in req_scores.values()]
        spread = max(values) - min(values)
        # Detect ANY disagreement (spread >= 1). run_aggregation applies the
        # caller's conflict_threshold (Strict=1 / Normal=2 / Loose=3) afterwards.
        # A hard floor here would make the Strict threshold unreachable.
        if spread >= 1:
            severity = "🔴 Critical" if spread >= 3 else "🟠 Significant"
            conflicts.append({
                "req_id": req_id,
                "conflict_type": "stakeholder_conflict",
                "scores": req_scores,
                "spread": spread,
                "severity": severity,
                "resolved": False,
                "resolution": None,
            })

    return conflicts


def _check_must_inflation(priorities: dict) -> dict:
    """Checks for Must Inflation. Returns {"inflated": bool, "must_ratio": float}"""
    if not priorities:
        return {"inflated": False, "must_ratio": 0.0}
    must_count = sum(1 for v in priorities.values()
                     if (v.get("priority") if isinstance(v, dict) else v) == "Must")
    ratio = must_count / len(priorities)
    return {"inflated": ratio > MUST_INFLATION_THRESHOLD, "must_ratio": round(ratio, 2)}


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def start_prioritization_session(
    project_name: str,
    session_label: str,
    method: Literal["MoSCoW", "WSJF", "ImpactEffort"],
    wsjf_scale: Literal["Fibonacci", "Linear"] = "Fibonacci",
    quadrant_mapping_json: str = "",
) -> str:
    """
    Open a new prioritization session.

    Reads requirements from the 5.1 repository, checks stability (5.2),
    and prepares the requirement list for scoring.

    Parameters:
    - project_name: project name (must match the name used in 5.1)
    - session_label: session label, e.g. "MVP scope" or "Sprint 3 planning"
    - method: prioritization method — MoSCoW / WSJF / ImpactEffort
    - wsjf_scale: scale for WSJF — Fibonacci (1,2,3,5,8,13) or Linear (1-10)
    - quadrant_mapping_json: JSON quadrant mapping for ImpactEffort.
      Format: {"QuickWins": "Must", "BigBets": "Should", "FillIns": "Could", "ThanklessTasks": "Won't"}
      If empty — the default mapping is used.
    """
    logger.info(f"5.3 start_prioritization_session: {project_name} / {session_label}")

    repo = _load_repo(project_name)
    prio_data = _load_prio(project_name)

    # Check that a session with this name doesn't already exist
    existing = _find_session(prio_data["sessions"], session_label)
    if existing:
        return (f"⚠️ Session '{session_label}' already exists for project '{project_name}'.\n"
                f"Use a different name or continue working with the existing session.")

    # Default quadrant mapping
    default_qmap = {
        "QuickWins": "Must",
        "BigBets": "Should",
        "FillIns": "Could",
        "ThanklessTasks": "Won't",
    }
    quadrant_mapping = default_qmap
    if quadrant_mapping_json.strip():
        try:
            quadrant_mapping = {**default_qmap, **json.loads(quadrant_mapping_json)}
        except json.JSONDecodeError:
            return "❌ Error parsing quadrant_mapping_json. Check the JSON format."

    # Get requirements from the repository
    # Only requirements go to a prioritisation vote. Selecting by status alone offered
    # stakeholders a Must/Should/Could/Won't choice on business objectives, risks and
    # change requests — none of which are scoped items a stakeholder can rank.
    nodes = [
        n for n in repo.get("requirements", [])
        if n.get("type", "") not in NON_REQUIREMENT_NODE_TYPES
        and n.get("status") != "deprecated"
    ]
    if not nodes:
        return (f"⚠️ Repository '{project_name}' has no requirements, or doesn't exist.\n"
                f"First create the repository via 5.1 (init_traceability_repo).")

    # Check stability
    stability_warnings = []
    stability_critical = []
    for node in nodes:
        flag = _stability_flag(node)
        if flag == "critical":
            stability_critical.append(node["id"])
        elif flag in ("warning", "unknown"):
            stability_warnings.append(node["id"])

    # Create the session
    session = {
        "label": session_label,
        "method": method,
        "wsjf_scale": wsjf_scale if method == "WSJF" else None,
        "quadrant_mapping": quadrant_mapping if method == "ImpactEffort" else None,
        "date": str(date.today()),
        "status": "open",
        "stakeholder_scores": {},
        "conflicts": [],
        "dependency_violations": [],
        "aggregated": {},
        "result": {},
    }
    prio_data["sessions"].append(session)
    _save_prio(project_name, prio_data)

    # Build the report
    lines = [
        f"<!-- BABOK 5.3 — Prioritize Requirements, Project: {project_name}, "
        f"Session: {session_label}, Method: {method}, Date: {date.today()} -->",
        "",
        f"# Prioritization session: {session_label}",
        f"**Project:** {project_name}  ",
        f"**Method:** {method}  ",
        f"**Opened on:** {date.today()}",
        "",
        "---",
        "",
        f"## Requirements to score ({len(nodes)})",
        "",
    ]

    if method == "MoSCoW":
        lines.append("| ID | Title | Type | Current priority | Stability |")
        lines.append("|-----|----------|-----|-------------------|-----------|")
        for n in nodes:
            flag = _stability_flag(n)
            stab_icon = {"critical": "🔴 Critical", "warning": "🟡 Caution",
                         "unknown": "🟡 Unknown"}.get(flag, "🟢 Stable")
            lines.append(f"| {n['id']} | {n.get('title','—')} | {n.get('type','—')} "
                         f"| {n.get('priority','—')} | {stab_icon} |")
    elif method == "WSJF":
        lines.append(f"**Scale:** {wsjf_scale}  ")
        if wsjf_scale == "Fibonacci":
            lines.append("**Values:** 1, 2, 3, 5, 8, 13 (relative, pick a reference = 3)")
        else:
            lines.append("**Values:** 1–10 (absolute)")
        lines.append("")
        lines.append("| ID | Title | Components to score: BV, TC, RR, JS |")
        lines.append("|-----|----------|---------------------------------------|")
        for n in nodes:
            lines.append(f"| {n['id']} | {n.get('title','—')} | BV=?, TC=?, RR=?, JS=? |")
    else:  # ImpactEffort
        lines.append("**Quadrant mapping:**")
        for q, p in quadrant_mapping.items():
            q_label = {"QuickWins": "Quick Wins (High Impact, Low Effort)",
                       "BigBets": "Big Bets (High Impact, High Effort)",
                       "FillIns": "Fill-ins (Low Impact, Low Effort)",
                       "ThanklessTasks": "Thankless Tasks (Low Impact, High Effort)"}.get(q, q)
            lines.append(f"- {q_label} → **{p}**")
        lines.append("")
        lines.append("| ID | Title | Impact (Low/Medium/High) | Effort (Low/Medium/High) |")
        lines.append("|-----|----------|--------------------------|--------------------------|")
        for n in nodes:
            lines.append(f"| {n['id']} | {n.get('title','—')} | ? | ? |")

    if stability_critical:
        lines += [
            "",
            "---",
            "",
            "## ⚠️ Stability warnings",
            "",
            "### 🔴 Critically unstable (version 1.4+)",
            "Assigning Must creates a high risk of rework.",
            "",
        ]
        for rid in stability_critical:
            lines.append(f"- `{rid}`")

    if stability_warnings:
        lines += [
            "",
            "### 🟡 Unstable (version 1.3+) or with unknown stability",
            "",
        ]
        for rid in stability_warnings:
            lines.append(f"- `{rid}`")

    lines += [
        "",
        "---",
        "",
        "## Next steps",
        "",
        "1. Call `add_stakeholder_scores` for each stakeholder",
        "2. After collecting all scores — call `run_aggregation`",
        "3. Resolve conflicts (`resolve_conflict`) if any",
        "4. Finalize: `save_prioritization_result`",
    ]

    return "\n".join(lines)


@mcp.tool()
@guard_artifact_errors
def add_stakeholder_scores(
    project_name: str,
    session_label: str,
    stakeholder_id: str,
    stakeholder_influence: Literal["High", "Medium", "Low"],
    scores_json: str,
) -> str:
    """
    Add one stakeholder's scores for the current session.

    Called once per stakeholder.
    A repeat call for the same stakeholder replaces the previous scores.

    Parameters:
    - stakeholder_id: ID from the stakeholder registry (4.2), e.g. "SH-001"
    - stakeholder_influence: the stakeholder's level of influence
    - scores_json: scores, depending on method:

      MoSCoW:
        [{"req_id": "FR-001", "score": "Must"}, ...]

      WSJF:
        [{"req_id": "FR-001", "bv": 5, "tc": 3, "rr": 2, "js": 3}, ...]
        (js — Job Size, an effort estimate from the development team)

      ImpactEffort:
        [{"req_id": "FR-001", "impact": "High", "effort": "Low"}, ...]
    """
    logger.info(f"5.3 add_stakeholder_scores: {project_name}/{session_label} ← {stakeholder_id}")

    prio_data = _load_prio(project_name)
    session = _find_session(prio_data["sessions"], session_label)
    if not session:
        return f"❌ Session '{session_label}' not found. Call start_prioritization_session first."

    if session["status"] == "closed":
        return f"❌ Session '{session_label}' is already closed."

    # Elements are read as objects (`item.get("req_id")`) immediately below, so the
    # shape has to be checked here rather than discovered by an AttributeError.
    raw_scores, shape_error = parse_json_dict_list(
        scores_json, "scores_json", required=True,
        example='[{"req_id": "FR-001", "score": "Must"}]')
    if shape_error:
        return shape_error

    # Validate and normalize scores by method
    method = session["method"]
    normalized = {}

    if method == "MoSCoW":
        valid_vals = set(MOSCOW_WEIGHTS.keys())
        for item in raw_scores:
            rid = item.get("req_id")
            score = item.get("score")
            if not rid:
                return f"❌ Missing req_id in: {item}"
            if score not in valid_vals:
                return (f"❌ Invalid value '{score}' for {rid}. "
                        f"Allowed: Must / Should / Could / Won't")
            normalized[rid] = score

    elif method == "WSJF":
        for item in raw_scores:
            rid = item.get("req_id")
            if not rid:
                return f"❌ Missing req_id in: {item}"
            normalized[rid] = {
                "bv": float(item.get("bv", 0)),
                "tc": float(item.get("tc", 0)),
                "rr": float(item.get("rr", 0)),
                "js": float(item.get("js", 1)),
            }

    elif method == "ImpactEffort":
        valid_ie = {"Low", "Medium", "High"}
        for item in raw_scores:
            rid = item.get("req_id")
            impact = item.get("impact", "Medium")
            effort = item.get("effort", "Medium")
            if not rid:
                return f"❌ Missing req_id in: {item}"
            if impact not in valid_ie or effort not in valid_ie:
                return (f"❌ Invalid impact/effort value for {rid}. "
                        f"Allowed: Low / Medium / High")
            normalized[rid] = {"impact": impact, "effort": effort}

    # Save the scores and influence
    session["stakeholder_scores"][stakeholder_id] = normalized
    if "stakeholder_influence" not in session:
        session["stakeholder_influence"] = {}
    session["stakeholder_influence"][stakeholder_id] = stakeholder_influence

    _save_prio(project_name, prio_data)

    is_update = "(updated)" if stakeholder_id in session.get("stakeholder_influence", {}) else ""
    lines = [
        f"✅ Scores for stakeholder **{stakeholder_id}** ({stakeholder_influence} influence) "
        f"saved {is_update}",
        "",
        f"**Project:** {project_name}  ",
        f"**Session:** {session_label}  ",
        f"**Method:** {method}  ",
        f"**Requirements scored:** {len(normalized)}",
        "",
        f"**Stakeholders with scores:** {len(session['stakeholder_scores'])}",
        "",
        "Once all stakeholders have scored the requirements — call `run_aggregation`.",
    ]
    return "\n".join(lines)


@mcp.tool()
@guard_artifact_errors
def run_aggregation(
    project_name: str,
    session_label: str,
    conflict_threshold: Literal["Strict", "Normal", "Loose"] = "Normal",
) -> str:
    """
    Aggregate stakeholder scores, compute priorities, surface conflicts.

    - Strict: conflict at a spread ≥ 1 category
    - Normal: conflict at a spread ≥ 2 categories (recommended)
    - Loose: conflict only for Must vs Won't

    Detects:
    - 🔴 Inter-stakeholder conflicts
    - ⚠️ Dependency violations (Must/Should depends on a lower-priority item)
    - 🟡 Must Inflation (>60% of requirements at Must)
    - 🟡 Unstable requirements at high priority
    """
    logger.info(f"5.3 run_aggregation: {project_name}/{session_label}")

    prio_data = _load_prio(project_name)
    session = _find_session(prio_data["sessions"], session_label)
    if not session:
        return f"❌ Session '{session_label}' not found."

    if not session["stakeholder_scores"]:
        return "⚠️ No stakeholder scores yet. Call add_stakeholder_scores first."

    repo = _load_repo(project_name)
    method = session["method"]
    scores_by_sh = session["stakeholder_scores"]
    influence_by_sh = session.get("stakeholder_influence", {})

    # Aggregation by method
    if method == "MoSCoW":
        aggregated = _aggregate_moscow(scores_by_sh, influence_by_sh)
    elif method == "WSJF":
        aggregated = _aggregate_wsjf(scores_by_sh, influence_by_sh)
    else:
        qmap = session.get("quadrant_mapping") or {
            "QuickWins": "Must", "BigBets": "Should",
            "FillIns": "Could", "ThanklessTasks": "Won't"
        }
        aggregated = _aggregate_impact_effort(scores_by_sh, influence_by_sh, qmap)

    session["aggregated"] = aggregated

    # Stakeholder conflicts (for MoSCoW)
    threshold_spread = {"Strict": 1, "Normal": 2, "Loose": 3}[conflict_threshold]
    conflicts = _detect_stakeholder_conflicts(scores_by_sh, method)
    conflicts = [c for c in conflicts if c["spread"] >= threshold_spread]
    session["conflicts"] = conflicts

    # Dependency violations
    violations = _find_dependency_violations(repo, aggregated)
    session["dependency_violations"] = violations

    # Must Inflation
    inflation = _check_must_inflation(aggregated)

    # Unstable items at Must
    volatile_must = []
    nodes_by_id = {n["id"]: n for n in repo.get("requirements", [])}
    for req_id, agg in aggregated.items():
        prio = agg.get("priority") if isinstance(agg, dict) else agg
        if prio == "Must":
            node = nodes_by_id.get(req_id, {})
            flag = _stability_flag(node)
            if flag in ("critical", "warning"):
                volatile_must.append({"req_id": req_id, "flag": flag,
                                      "version": node.get("version", "?")})

    _save_prio(project_name, prio_data)

    # Report
    lines = [
        f"<!-- BABOK 5.3 — Aggregation, {project_name}/{session_label}, {date.today()} -->",
        "",
        f"# Aggregation results: {session_label}",
        f"**Project:** {project_name}  ",
        f"**Method:** {method}  ",
        f"**Stakeholders:** {len(scores_by_sh)}  ",
        f"**Conflict threshold:** {conflict_threshold}",
        "",
        "---",
        "",
        "## Final priorities",
        "",
    ]

    if method == "MoSCoW":
        lines.append("| ID | Priority | Weighted score |")
        lines.append("|-----|-----------|-----------------|")
        for req_id, data in sorted(aggregated.items(),
                                   key=lambda x: x[1].get("weighted_score", 0) if isinstance(x[1], dict) else 0,
                                   reverse=True):
            prio = data.get("priority", "—") if isinstance(data, dict) else data
            ws = data.get("weighted_score", "—") if isinstance(data, dict) else "—"
            icon = {"Must": "🔴", "Should": "🟠", "Could": "🟡", "Won't": "🟢"}.get(prio, "")
            lines.append(f"| {req_id} | {icon} {prio} | {ws} |")

    elif method == "WSJF":
        lines.append("| ID | Priority | WSJF | CoD | JS |")
        lines.append("|-----|-----------|------|-----|----|")
        for req_id, data in sorted(aggregated.items(),
                                   key=lambda x: x[1].get("wsjf", 0) if isinstance(x[1], dict) else 0,
                                   reverse=True):
            prio = data.get("priority", "—") if isinstance(data, dict) else data
            icon = {"Must": "🔴", "Should": "🟠", "Could": "🟡", "Won't": "🟢"}.get(prio, "")
            lines.append(f"| {req_id} | {icon} {prio} | {data.get('wsjf','—')} "
                         f"| {data.get('cod','—')} | {data.get('js','—')} |")

    else:
        lines.append("| ID | Priority | Quadrant | Avg Impact | Avg Effort |")
        lines.append("|-----|-----------|----------|------------|------------|")
        for req_id, data in aggregated.items():
            prio = data.get("priority", "—") if isinstance(data, dict) else data
            icon = {"Must": "🔴", "Should": "🟠", "Could": "🟡", "Won't": "🟢"}.get(prio, "")
            lines.append(f"| {req_id} | {icon} {prio} | {data.get('quadrant','—')} "
                         f"| {data.get('avg_impact','—')} | {data.get('avg_effort','—')} |")

    # Must Inflation
    if inflation["inflated"]:
        lines += [
            "",
            "---",
            "",
            f"## 🟠 Must Inflation — {int(inflation['must_ratio']*100)}% of requirements at Must",
            "",
            "Recommendation: re-run the session using a \"fixed budget\" technique.",
            "Ask the stakeholders: \"If we could only ship 40% — what would you pick?\"",
        ]

    # Conflicts
    if conflicts:
        lines += [
            "",
            "---",
            "",
            f"## 🔴 Stakeholder conflicts ({len(conflicts)})",
            "",
            "Require resolution before finalizing.",
            "",
        ]
        for c in conflicts:
            lines.append(f"### Requirement `{c['req_id']}` — {c['severity']}")
            lines.append("")
            for sh_id, score in c["scores"].items():
                infl = influence_by_sh.get(sh_id, "Medium")
                lines.append(f"- **{sh_id}** ({infl}): **{score}**")
            lines.append("")
            lines.append("Call `resolve_conflict` to record the decision.")
            lines.append("")
    else:
        lines += ["", "---", "", "## ✅ Stakeholder conflicts", "", "No conflicts found.", ""]

    # Dependency violations
    if violations:
        lines += [
            "---",
            "",
            f"## ⚠️ Dependency Violations ({len(violations)})",
            "",
            "Logical contradictions: a high-priority requirement depends on a lower-priority one.",
            "",
        ]
        for v in violations:
            lines.append(f"- `{v['req_id']}` (**{v['req_priority']}**) depends on "
                         f"`{v['depends_on']}` (**{v['dep_priority']}**)")
        lines += [
            "",
            "Options: raise the dependency's priority / lower the requirement's / decompose it.",
            "Record the decision via `resolve_conflict`.",
            "",
        ]

    # Unstable items at Must
    if volatile_must:
        lines += [
            "---",
            "",
            "## 🟡 Unstable requirements at Must",
            "",
        ]
        for item in volatile_must:
            icon = "🔴" if item["flag"] == "critical" else "🟡"
            lines.append(f"- {icon} `{item['req_id']}` (version {item['version']}) — risk of rework")
        lines.append("")

    lines += [
        "---",
        "",
        "## Next steps",
        "",
    ]
    has_open = conflicts or violations
    if has_open:
        lines.append("1. Resolve conflicts → `resolve_conflict`")
        lines.append("2. After resolving all conflicts → `save_prioritization_result`")
    else:
        lines.append("1. No conflicts remain → you can call `save_prioritization_result`")

    return "\n".join(lines)


@mcp.tool()
@guard_artifact_errors
def resolve_conflict(
    project_name: str,
    session_label: str,
    req_id: str,
    conflict_type: Literal["stakeholder_conflict", "dependency_violation", "inflation"],
    final_priority: Literal["Must", "Should", "Could", "Won't"],
    rationale: str,
    decided_by: str,
) -> str:
    """
    Record a prioritization conflict-resolution decision.

    Parameters:
    - req_id: ID of the requirement in conflict
    - conflict_type: conflict type
    - final_priority: final priority after resolution
    - rationale: rationale for the decision
    - decided_by: who made the decision (stakeholder_id or a role, e.g. "Sponsor")
    """
    logger.info(f"5.3 resolve_conflict: {project_name}/{session_label} req={req_id}")

    prio_data = _load_prio(project_name)
    session = _find_session(prio_data["sessions"], session_label)
    if not session:
        return f"❌ Session '{session_label}' not found."

    # Update the aggregated value
    if req_id in session["aggregated"]:
        if isinstance(session["aggregated"][req_id], dict):
            session["aggregated"][req_id]["priority"] = final_priority
            session["aggregated"][req_id]["resolved"] = True
        else:
            session["aggregated"][req_id] = {
                "priority": final_priority, "resolved": True
            }
    else:
        session["aggregated"][req_id] = {"priority": final_priority, "resolved": True}

    # Mark the conflict as resolved
    resolution = {
        "req_id": req_id,
        "conflict_type": conflict_type,
        "final_priority": final_priority,
        "rationale": rationale,
        "decided_by": decided_by,
        "resolved_at": str(date.today()),
        "resolved": True,
    }

    found = False
    for c in session["conflicts"]:
        if c["req_id"] == req_id and c["conflict_type"] == conflict_type:
            c["resolved"] = True
            c["resolution"] = resolution
            found = True
            break
    for v in session["dependency_violations"]:
        if v["req_id"] == req_id:
            v["resolved"] = True
            v["resolution"] = resolution
            found = True
            break

    if not found:
        # Add as a standalone entry (manual resolution)
        session["conflicts"].append({
            "req_id": req_id,
            "conflict_type": conflict_type,
            "resolved": True,
            "resolution": resolution,
        })

    _save_prio(project_name, prio_data)

    # Check whether unresolved conflicts remain
    open_conflicts = [c for c in session["conflicts"] if not c.get("resolved")]
    open_violations = [v for v in session["dependency_violations"] if not v.get("resolved")]

    lines = [
        f"✅ Conflict on `{req_id}` resolved",
        "",
        f"**Final priority:** {final_priority}  ",
        f"**Decided by:** {decided_by}  ",
        f"**Rationale:** {rationale}",
        "",
    ]

    if open_conflicts or open_violations:
        total_open = len(open_conflicts) + len(open_violations)
        lines.append(f"⚠️ **{total_open}** unresolved conflict(s)/violation(s) remain.")
        lines.append("Keep calling `resolve_conflict` for each.")
    else:
        lines.append("✅ All conflicts resolved. You can call `save_prioritization_result`.")

    return "\n".join(lines)


@mcp.tool()
@guard_artifact_errors
def save_prioritization_result(
    project_name: str,
    session_label: str,
) -> str:
    """
    Finalize the prioritization session.

    Actions:
    1. Checks that all conflicts are resolved
    2. Updates the priority field in the 5.1 repository
    3. Closes the session in {project}_prioritization.json
    4. Saves the Markdown report

    Warns if unresolved conflicts remain (but allows saving anyway).
    """
    logger.info(f"5.3 save_prioritization_result: {project_name}/{session_label}")

    prio_data = _load_prio(project_name)
    session = _find_session(prio_data["sessions"], session_label)
    if not session:
        return f"❌ Session '{session_label}' not found."

    open_conflicts = [c for c in session["conflicts"] if not c.get("resolved")]
    open_violations = [v for v in session["dependency_violations"] if not v.get("resolved")]

    # Update the 5.1 repository
    repo = _load_repo(project_name)
    updated_count = 0
    priority_summary = {}

    for req_id, agg_data in session["aggregated"].items():
        priority = agg_data.get("priority") if isinstance(agg_data, dict) else agg_data
        if not priority:
            continue
        for node in repo.get("requirements", []):
            if node["id"] == req_id:
                old_priority = node.get("priority", "—")
                node["priority"] = priority
                updated_count += 1
                priority_summary.setdefault(priority, []).append(req_id)

                # Change history
                if "history" not in repo:
                    repo["history"] = []
                repo["history"].append({
                    "date": str(date.today()),
                    "action": "priority_updated",
                    "req_id": req_id,
                    "old_priority": old_priority,
                    "new_priority": priority,
                    "session": session_label,
                    "method": session["method"],
                })
                break

    _save_repo(project_name, repo)

    # Close the session
    session["status"] = "closed"
    session["closed_at"] = str(date.today())
    _save_prio(project_name, prio_data)

    # Markdown report
    lines = [
        f"<!-- BABOK 5.3 — Prioritize Requirements (result), "
        f"Project: {project_name}, Session: {session_label}, Date: {date.today()} -->",
        "",
        f"# Prioritization results: {session_label}",
        f"**Project:** {project_name}  ",
        f"**Method:** {session['method']}  ",
        f"**Date:** {date.today()}  ",
        f"**Requirements updated:** {updated_count}",
        "",
        "---",
        "",
        "## Final priorities",
        "",
    ]

    for prio_label in ["Must", "Should", "Could", "Won't"]:
        reqs = priority_summary.get(prio_label, [])
        icon = {"Must": "🔴", "Should": "🟠", "Could": "🟡", "Won't": "🟢"}[prio_label]
        lines.append(f"### {icon} {prio_label} ({len(reqs)})")
        if reqs:
            for rid in reqs:
                lines.append(f"- `{rid}`")
        else:
            lines.append("*(no requirements)*")
        lines.append("")

    # Session metadata
    total_conflicts = len(session["conflicts"])
    resolved_conflicts = sum(1 for c in session["conflicts"] if c.get("resolved"))
    total_violations = len(session["dependency_violations"])
    resolved_violations = sum(1 for v in session["dependency_violations"] if v.get("resolved"))

    lines += [
        "---",
        "",
        "## Session statistics",
        "",
        f"- Stakeholders: {len(session['stakeholder_scores'])}",
        f"- Conflicts: {total_conflicts} (resolved: {resolved_conflicts})",
        f"- Dependency violations: {total_violations} (resolved: {resolved_violations})",
        "",
    ]

    if open_conflicts or open_violations:
        lines += [
            "---",
            "",
            "## ⚠️ Unresolved conflicts",
            "",
            f"Still unresolved: {len(open_conflicts)} conflict(s), {len(open_violations)} violation(s).",
            "The result has been saved, but recommend recording decisions via `resolve_conflict`.",
            "",
        ]

    lines += [
        "---",
        "",
        "## Next steps",
        "",
        "- Priorities have been written to the 5.1 repository",
        "- Results are available for 6.3 (Assess Risks)",
        "- If the context changes — run a new prioritization session",
    ]

    content = "\n".join(lines)
    saved = save_artifact(content, prefix=f"5_3_prioritization_{project_name.lower().replace(' ', '_')}", project_id=project_name)
    return content + saved


if __name__ == "__main__":
    mcp.run()
