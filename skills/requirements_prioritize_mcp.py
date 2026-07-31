"""
BABOK 5.3 — Prioritize Requirements
MCP tools for prioritizing requirements and designs.

Tools:
  - start_prioritization_session  — open a session, choose a method (MoSCoW / WSJF /
                                    ImpactEffort / TimeBoxing), get the requirement list
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
    load_ba_plan, planned_prioritization, reg_norm,
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

# Time Boxing / Budgeting (BABOK 10.33.3 .3) — value ranking that fills a fixed box.
# Numerically identical to MOSCOW_WEIGHTS today, and deliberately NOT the same
# constant: MOSCOW_WEIGHTS is a scoring weight that only makes sense paired with
# MOSCOW_THRESHOLDS, while this is a rank order. Recalibrating the aggregation
# weights must not silently re-order the fill.
VALUE_ORDER = {"Must": 4, "Should": 3, "Could": 2, "Won't": 1}

# 7.1's create_* tools write High/Medium/Low into the SAME `priority` field 5.3
# writes MoSCoW labels into. The graph fallback has to read both; 7.5 already makes
# the same accommodation with MUST_PRIORITIES = {"Must", "High"}.
GRAPH_PRIORITY_TO_VALUE = {"High": "Must", "Medium": "Should", "Low": "Could"}

# Used when neither this session nor the graph says anything about value.
DEFAULT_VALUE_LABEL = "Could"


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

def _fmt_num(value) -> str:
    """40.0 → '40', 2.5 → '2.5'. Capacities and costs read as numbers, not floats."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value)
    return str(int(f)) if f == int(f) else str(round(f, 2))


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


def _aggregate_timebox(scores_by_sh: dict, influence_by_sh: dict,
                       repo: dict, capacity: float, overrides: dict = None) -> dict:
    """
    Fills a box of fixed capacity — BABOK 10.33.3 .3 Time Boxing/Budgeting.

    scores_by_sh[sh_id][req_id] = {"cost": float|None, "value": "Must"|None}

    Value ranking follows a three-step precedence, recorded per requirement in
    `value_source`: scores given in THIS session (influence-weighted, through the
    shared MoSCoW aggregator) → the priority already stored in the 5.1 graph
    (High/Medium/Low normalised) → an explicit default.

    Requirements nobody costed come back with priority=None. They cannot be placed
    in a capacity box, and calling them "Won't" would be a conclusion drawn from
    missing data — the tool says LESS instead (class CH3-D).
    """
    # The box is drawn over the WHOLE backlog, not just what was scored: the
    # deliverable of this technique is "what of the scope fits", and a requirement
    # the BA forgot to estimate must be named, not silently absent from a document
    # that goes to stakeholders. The other three methods report only on what was
    # scored — a deliberate difference, recorded in ADR-093.
    # Same filter start_prioritization_session applies when listing what to score.
    all_reqs = {n["id"] for n in repo.get("requirements", [])
                if n.get("type", "") not in NON_REQUIREMENT_NODE_TYPES
                and n.get("status") != "deprecated"}
    # Union with the scored ids, never a replacement: save_prioritization_result
    # names ids that match no node (a stakeholder scoring the typo "FR-01"), and
    # dropping them here would silently disable that warning for TimeBoxing.
    for sh_scores in scores_by_sh.values():
        all_reqs.update(sh_scores.keys())

    # Cost: a team estimate, averaged WITHOUT influence weighting — the same
    # treatment WSJF gives Job Size. A size estimate is not an opinion.
    cost_by_req = {}
    spread_by_req = {}
    for req_id in all_reqs:
        costs = [sh_scores[req_id].get("cost")
                 for sh_scores in scores_by_sh.values()
                 if req_id in sh_scores and sh_scores[req_id].get("cost") is not None]
        if costs:
            cost_by_req[req_id] = round(sum(costs) / len(costs), 2)
            spread_by_req[req_id] = round(max(costs) - min(costs), 2)
        else:
            cost_by_req[req_id] = None
            spread_by_req[req_id] = 0.0

    # Value, step 1 — whatever stakeholders scored in THIS session, aggregated by
    # the SAME MoSCoW code rather than a second copy of the rule (two copies of a
    # decision rule is how 5.5's dashboard and baseline gate drifted apart).
    # Projected to the shape _aggregate_moscow expects; stakeholders who gave no
    # value simply do not appear for that requirement and so cannot dilute the vote.
    projection = {}
    for sh_id, sh_scores in scores_by_sh.items():
        voted = {rid: v["value"] for rid, v in sh_scores.items() if v.get("value")}
        if voted:
            projection[sh_id] = voted
    session_values = _aggregate_moscow(projection, influence_by_sh) if projection else {}

    nodes_by_id = {n["id"]: n for n in repo.get("requirements", [])}

    overrides = overrides or {}

    result = {}
    for req_id in all_reqs:
        if req_id in overrides:
            # A conflict the BA resolved. In this method `priority` is an OUTPUT of
            # the fill, so a resolution has to re-enter as the requirement's VALUE
            # and let the box be filled again — writing it straight into `priority`
            # produced rows reading "cut" and "Must" at once.
            label, source = overrides[req_id], "resolved"
        elif req_id in session_values:
            label, source = session_values[req_id]["priority"], "session"
        else:
            stored = str(nodes_by_id.get(req_id, {}).get("priority") or "").strip()
            if stored == "Won't":
                # NOT authoritative. `Won't` in the graph may simply be the outcome
                # of an earlier box — this method writes its own cuts there — and
                # reading it back as a decision demoted a requirement permanently:
                # cut once by a small capacity, never allowed to compete again, and
                # a mistyped capacity rewrote a whole backlog in one call. An
                # explicit "not this time" is expressed by scoring it in THIS
                # session, where it is unambiguous.
                label, source = DEFAULT_VALUE_LABEL, "default"
            elif stored in VALUE_ORDER:
                label, source = stored, "graph"
            elif stored in GRAPH_PRIORITY_TO_VALUE:
                label, source = GRAPH_PRIORITY_TO_VALUE[stored], "graph"
            else:
                label, source = DEFAULT_VALUE_LABEL, "default"
        result[req_id] = {
            "priority": None,
            "in_box": False,
            "cost": cost_by_req[req_id],
            "cost_spread": spread_by_req[req_id],
            "cumulative": None,
            "value_label": label,
            "value_source": source,
        }

    # Two populations never reach the fill, and neither may consume capacity:
    #
    #  - value `Won't` declared in THIS session (or by a resolved conflict) is a
    #    decision not to take the requirement. Letting it into the box produced a
    #    page that filed a requirement under "Won't" and marked it committed at the
    #    same time, and spent the team's capacity on it.
    #  - a scored id that is not a requirement of this project's backlog — a typo
    #    (`FR-01`), or a risk/goal node someone scored. It was eating capacity and
    #    cutting real requirements; the existing "not saved" warning fires only at
    #    finalisation and never mentioned the capacity it took.
    backlog_ids = {n["id"] for n in repo.get("requirements", [])
                   if n.get("type", "") not in NON_REQUIREMENT_NODE_TYPES
                   and n.get("status") != "deprecated"}
    for req_id, data in result.items():
        if req_id not in backlog_ids:
            data["off_backlog"] = True
        elif data["value_label"] == "Won't" and data["value_source"] in ("session",
                                                                        "resolved"):
            # A decision, so it holds whether or not anyone estimated the item —
            # but then it must be reported ONCE, as excluded, and not also listed
            # under "not estimated — no priority written" while carrying Won't.
            data["excluded_by_decision"] = True
            data["priority"] = "Won't"

    # Fill order: value desc, then cheapest first, then id. The third key is not
    # cosmetic — without it a re-run on identical data can produce a different box.
    order = sorted(
        (r for r in all_reqs
         if result[r]["cost"] is not None
         and not result[r].get("off_backlog")
         and not result[r].get("excluded_by_decision")),
        key=lambda r: (-VALUE_ORDER.get(result[r]["value_label"], 0),
                       result[r]["cost"], r),
    )

    cumulative = 0.0
    for req_id in order:
        cost = result[req_id]["cost"]
        # Round BEFORE comparing, not only when storing: costs are ordinary floats
        # (person-days, half-point stories), and 0.1 + 0.2 == 0.30000000000000004
        # in binary floating point — an unrounded comparison cuts a requirement
        # that fits the capacity exactly. Costs are already rounded to 2 places,
        # so rounding their running total to 2 places is exact, not a fudge.
        running_total = round(cumulative + cost, 2)
        if running_total <= capacity:
            cumulative = running_total
            result[req_id]["in_box"] = True
            result[req_id]["cumulative"] = cumulative
            result[req_id]["priority"] = result[req_id]["value_label"]
        else:
            # continue-fill: a requirement that does not fit is skipped and cheaper
            # ones below it are still considered. Every skip is named in the report.
            result[req_id]["priority"] = "Won't"
            result[req_id]["remaining_at_skip"] = round(capacity - cumulative, 2)

    # Mark the cut requirements that cheaper ones jumped over, so the report can
    # say what the fill order actually cost.
    taken_below = False
    for req_id in reversed(order):
        if result[req_id]["in_box"]:
            taken_below = True
        elif taken_below:
            result[req_id]["skipped_over"] = True

    return result


def _find_dependency_violations(repo: dict, priorities: dict,
                                unplaced: set = None) -> list:
    """
    Looks for dependency violations: a requirement with Must/Should depends on a lower-priority requirement.
    Returns a list of {"req_id", "depends_on", "req_priority", "dep_priority"}

    `unplaced` (TimeBoxing only) names requirements that carry no priority at all
    because they were never placed in the box — nobody estimated them, or they are
    not part of this backlog. A committed requirement depending on one of those
    makes the box just as infeasible as depending on a cut one, but the priority
    comparison alone cannot see it: `None` fails the `if from_prio and to_prio`
    guard, so the edge was skipped and the tool reported no violations at all.
    Silence in a section that prints a count reads as "checked and clean".
    """
    violations = []
    order = VALUE_ORDER
    unplaced = unplaced or set()

    for edge in repo.get("links", []):
        if edge.get("relation") != "depends":
            continue
        from_id = edge.get("from")
        to_id = edge.get("to")
        from_prio = priorities.get(from_id, {}).get("priority") if isinstance(
            priorities.get(from_id), dict) else priorities.get(from_id)
        to_prio = priorities.get(to_id, {}).get("priority") if isinstance(
            priorities.get(to_id), dict) else priorities.get(to_id)

        if from_prio and to_id in unplaced:
            violations.append({
                "req_id": from_id,
                "depends_on": to_id,
                "req_priority": from_prio,
                "dep_priority": "not placed",
            })
        elif from_prio and to_prio:
            if order.get(from_prio, 0) > order.get(to_prio, 0):
                violations.append({
                    "req_id": from_id,
                    "depends_on": to_id,
                    "req_priority": from_prio,
                    "dep_priority": to_prio,
                })
    return violations


def _timebox_unplaced(aggregated: dict) -> set:
    """Requirements a TimeBoxing run left without any priority at all."""
    return {r for r, d in aggregated.items()
            if isinstance(d, dict) and not d.get("priority")}


def _detect_stakeholder_conflicts(scores_by_sh: dict, method: str) -> list:
    """
    Looks for conflicts between stakeholders.
    MoSCoW: a spread of ≥ 2 categories.
    Returns a list of {"req_id", "conflict_type", "scores", "severity"}
    """
    if method not in ("MoSCoW", "TimeBoxing"):
        return []  # for WSJF and IE, conflicts surface through aggregation

    order = VALUE_ORDER
    conflicts = []

    all_reqs = set()
    for sh_scores in scores_by_sh.values():
        all_reqs.update(sh_scores.keys())

    for req_id in all_reqs:
        # TimeBoxing carries two axes per requirement, and only value is an opinion:
        # disagreement about cost is an estimate spread, reported by the aggregator,
        # not a stakeholder conflict.
        req_scores = {}
        for sh_id, sh_scores in scores_by_sh.items():
            if req_id not in sh_scores:
                continue
            raw = sh_scores[req_id]
            label = raw.get("value") if isinstance(raw, dict) else raw
            if label:
                req_scores[sh_id] = label
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
    # Entries with no priority (TimeBoxing: nobody costed them, so they were never
    # placed) must not dilute the denominator — the ratio is about scored items.
    # No-op for MoSCoW / WSJF / ImpactEffort, where every entry carries a priority.
    scored = {k: v for k, v in priorities.items()
              if (v.get("priority") if isinstance(v, dict) else v)}
    if not scored:
        return {"inflated": False, "must_ratio": 0.0}
    must_count = sum(1 for v in scored.values()
                     if (v.get("priority") if isinstance(v, dict) else v) == "Must")
    ratio = must_count / len(scored)
    return {"inflated": ratio > MUST_INFLATION_THRESHOLD, "must_ratio": round(ratio, 2)}


def _planned_approach_block(project_name: str, session: dict) -> list:
    """BABOK 3.3 element .3 vs what the session actually did — [] when nothing is planned.

    Reconciles the three planned parts (technique, participants, criteria) against the
    method the session used and the stakeholders who actually scored. It reports; it
    decides nothing. `method` and `stakeholder_influence` are the BA's explicit inputs
    and between them determine every priority in the document below — a plan quietly
    overriding either would change the result, not describe it.

    Everything here goes through `planned_prioritization`, so a hand-edited plan cannot
    put an unknown technique or a per-character participant list into a delivered report.
    """
    plan, _plan_note = load_ba_plan(project_name)
    planned = planned_prioritization(plan)
    if not any(planned.values()):
        return []

    method = session.get("method", "")
    lines = ["## Planned approach (3.3)", ""]
    if planned["technique"]:
        match = "✅" if planned["technique"] == method else "⚠️"
        lines.append(
            f"**Technique:** {planned['technique']} planned — {method} used {match}  ")
    else:
        # Said plainly rather than omitted: the three parts are independent, and a
        # block that silently skips the technique row reads as though one was planned
        # and matched.
        lines.append("**Technique:** not planned in 3.3  ")

    if planned["criteria"]:
        lines.append(f"**Criteria:** {', '.join(planned['criteria'])}  ")

    planned_names = planned["participants"]
    if planned_names:
        scorers = list(session.get("stakeholder_scores", {}).keys())
        scored = [p for p in planned_names
                  if any(reg_norm(p) == reg_norm(s) for s in scorers)]
        missing = [p for p in planned_names if p not in scored]
        extra = [s for s in scorers
                 if not any(reg_norm(p) == reg_norm(s) for p in planned_names)]
        lines.append(f"**Participation:** {len(scored)} of {len(planned_names)} "
                     f"planned participants scored.  ")
        if missing:
            lines.append(f"- Did not score: {', '.join(missing)}  ")
        if extra:
            lines.append(f"- Scored without being planned: {', '.join(extra)}  ")

    lines.append("")
    return lines


def _timebox_report_block(aggregated: dict, capacity: float, unit: str) -> list:
    """Renders the box: summary line, in/out table and the three note sections.

    Shared by run_aggregation and save_prioritization_result on purpose — two copies
    of a rendering rule is how the 5.5 dashboard and its baseline gate drifted apart.
    """
    # Four populations, and they must not be conflated: a requirement the BA decided
    # against is not "cut by capacity", and a mistyped id is not a requirement at all.
    # Counting either as a cut misstates how much of the backlog the box actually
    # rejected.
    off_backlog = sorted(r for r, d in aggregated.items() if d.get("off_backlog"))
    excluded = sorted(r for r, d in aggregated.items()
                      if d.get("excluded_by_decision"))
    placed = {r: d for r, d in aggregated.items()
              if d.get("cost") is not None and not d.get("off_backlog")
              and not d.get("excluded_by_decision")}
    in_box = [r for r, d in placed.items() if d.get("in_box")]
    cut = [r for r, d in placed.items() if not d.get("in_box")]
    unestimated = sorted(r for r, d in aggregated.items()
                         if d.get("cost") is None and not d.get("off_backlog")
                         and not d.get("excluded_by_decision"))
    used = max((placed[r]["cumulative"] for r in in_box), default=0.0)
    pct = int(round(used / capacity * 100)) if capacity else 0

    lines = []
    if not capacity or capacity <= 0:
        # start_prioritization_session rejects capacity <= 0, so this is only
        # reachable through a session file edited or truncated on disk. Say so
        # rather than render a 0/0 box in which every requirement reads Won't.
        lines += [
            "⚠️ This session has no usable capacity on record, so nothing could be "
            "placed in the box. Open a new TimeBoxing session with a capacity > 0.",
            "",
        ]

    lines += [
        f"**Box:** {_fmt_num(used)} / {_fmt_num(capacity)} {unit} ({pct}%) · "
        f"in: {len(in_box)} · cut: {len(cut)} · excluded: {len(excluded)} · "
        f"not estimated: {len(unestimated)}",
        "",
        # `Value` and `Priority` are different things here and both belong on the
        # row: a cut requirement keeps its value (Should) while its outcome is
        # Won't. Printing only the outcome, with the value appearing in a note
        # further down, put two labels for one requirement in one document.
        f"| ID | In box | Value | Priority | Value source | Cost, {unit} | Cumulative |",
        "|-----|--------|-------|----------|--------------|------|------------|",
    ]
    for req_id in sorted(placed,
                         key=lambda r: (not placed[r]["in_box"],
                                        -VALUE_ORDER.get(placed[r]["value_label"], 0),
                                        placed[r]["cost"], r)):
        d = placed[req_id]
        mark = "✅" if d["in_box"] else "✂️"
        icon = {"Must": "🔴", "Should": "🟠", "Could": "🟡",
                "Won't": "🟢"}.get(d["priority"], "")
        cumulative = _fmt_num(d["cumulative"]) if d["in_box"] else "—"
        lines.append(f"| {req_id} | {mark} | {d['value_label']} | {icon} {d['priority']} "
                     f"| {d['value_source']} | {_fmt_num(d['cost'])} | {cumulative} |")

    skipped = sorted(r for r, d in placed.items() if d.get("skipped_over"))
    if skipped:
        lines += ["", "**Skipped over (cheaper requirements below them were taken):**", ""]
        for req_id in skipped:
            d = placed[req_id]
            # Phrased so it reads correctly for any unit and any remainder: a
            # free-form unit string ("story points", "USD") cannot be pluralised
            # reliably, and "1 story points were left" is in a stakeholder document.
            lines.append(f"- `{req_id}` ({d['value_label']}, {_fmt_num(d['cost'])} {unit}) "
                         f"— remaining capacity at that point: "
                         f"{_fmt_num(d['remaining_at_skip'])} {unit}.")

    spread = sorted((r for r, d in placed.items() if d.get("cost_spread")),
                    key=lambda r: -placed[r]["cost_spread"])
    if spread:
        lines += ["", "**Estimates disagree (spread averaged into the cost above):**", ""]
        for req_id in spread:
            lines.append(f"- `{req_id}` — spread {_fmt_num(placed[req_id]['cost_spread'])} "
                         f"{unit} around {_fmt_num(placed[req_id]['cost'])}.")

    if excluded:
        lines += ["", "**Excluded by decision (Won't — no capacity spent on them):**", ""]
        for req_id in excluded:
            lines.append(f"- `{req_id}` — scored Won't in this session, so it never "
                         f"competed for a place.")

    if off_backlog:
        lines += ["", "**⚠️ Scored, but not a requirement in this project "
                  "(excluded from the box):**", ""]
        for req_id in off_backlog:
            lines.append(f"- `{req_id}`")
        lines.append("")
        lines.append("These ids match no requirement in the 5.1 repository — a typo "
                     "(`FR-01` for `FR-001`), or a risk / objective / scope node that "
                     "was scored by mistake. They spend none of the capacity. Fix the "
                     "id and re-score, or the estimate is lost.")

    if cut:
        # The label this method writes for a capacity cut is read by other chapters
        # as a scope decision (7.5 maps Won't to out_of_scope; 5.4 flags a change
        # request that touches one). 5.3 itself deliberately refuses to read a
        # stored Won't back as a decision, so the BA has to know the asymmetry.
        lines += [
            "",
            "Requirements cut here are written to the requirements graph as `Won't` "
            "— the same label an explicit \"not this time\" carries. Chapter 7.5 "
            "reads it as out of scope and 5.4 flags change requests that touch it. "
            "If a cut was only about this period's capacity, re-run the box when the "
            "capacity changes rather than leaving the label to speak for itself.",
        ]

    if unestimated:
        lines += ["", "**⚠️ Not estimated — not placed (no priority written):**", ""]
        for req_id in unestimated:
            lines.append(f"- `{req_id}`")
        lines.append("")
        lines.append("A requirement with no cost cannot be placed in a capacity box. "
                     "Marking it Won't would be a conclusion drawn from missing data — "
                     "add an estimate and re-run the aggregation.")
    return lines


# ---------------------------------------------------------------------------
# MCP tools
# ---------------------------------------------------------------------------

@mcp.tool()
@guard_artifact_errors
def start_prioritization_session(
    project_name: str,
    session_label: str,
    method: Literal["MoSCoW", "WSJF", "ImpactEffort", "TimeBoxing"],
    wsjf_scale: Literal["Fibonacci", "Linear"] = "Fibonacci",
    quadrant_mapping_json: str = "",
    capacity: float = 0,
    capacity_unit: str = "",
) -> str:
    """
    Open a new prioritization session.

    Reads requirements from the 5.1 repository, checks stability (5.2),
    and prepares the requirement list for scoring.

    Parameters:
    - project_name: project name (must match the name used in 5.1)
    - session_label: session label, e.g. "MVP scope" or "Sprint 3 planning"
    - method: prioritization method — MoSCoW / WSJF / ImpactEffort / TimeBoxing
    - wsjf_scale: scale for WSJF — Fibonacci (1,2,3,5,8,13) or Linear (1-10)
    - quadrant_mapping_json: JSON quadrant mapping for ImpactEffort.
      Format: {"QuickWins": "Must", "BigBets": "Should", "FillIns": "Could", "ThanklessTasks": "Won't"}
      If empty — the default mapping is used.
    - capacity: box size for TimeBoxing — what the team can deliver in the period,
      or the fixed budget. Required (> 0) for method="TimeBoxing", ignored otherwise.
    - capacity_unit: unit for capacity and for the per-requirement costs
      ("story points", "person-days", "USD"). Blank → "units".
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

    # Time Boxing/Budgeting prioritises by the allocation of a fixed resource
    # (BABOK 10.33.3 .3). Without a box there is nothing to fill.
    capacity_note = ""
    if method == "TimeBoxing":
        try:
            capacity_value = float(capacity)
        except (TypeError, ValueError):
            capacity_value = 0.0
        if capacity_value <= 0:
            return ("❌ Method TimeBoxing requires `capacity` > 0 — the size of the box: "
                    "what the team can deliver in the period, or the fixed budget.\n"
                    "Example: capacity=40, capacity_unit=\"story points\".")
        capacity_unit_value = capacity_unit.strip() or "units"
    else:
        capacity_value = None
        capacity_unit_value = None
        if capacity:
            # wsjf_scale and quadrant_mapping are dropped silently because they only
            # shape a report. A capacity is a promise about scope: dropped silently,
            # it leaves the BA believing a budget was applied when it never was.
            capacity_note = (f"⚠️ `capacity` ignored: method is {method}. "
                             f"A capacity limit only applies to TimeBoxing sessions.")

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
        "capacity": capacity_value,
        "capacity_unit": capacity_unit_value,
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

    # BABOK 3.3 element .3 — the plan names a technique; this session picks the
    # algorithm. `method` is the BA's explicit choice and is NEVER overridden: it
    # selects the whole aggregation algorithm, and a plan silently switching it would
    # change every priority the session produces. So this warns, and nothing else.
    plan, _plan_note = load_ba_plan(project_name)
    planned_technique = planned_prioritization(plan)["technique"]
    governance_note = ""
    if planned_technique and planned_technique != method:
        governance_note = (
            f"⚠️ This session uses **{method}**, but 3.3 plans the technique "
            f"**{planned_technique}**.\n"
            f"   The session proceeds with {method} — `method` is your explicit "
            f"choice and selects the whole aggregation algorithm. Re-plan 3.3 with "
            f"`plan_ba_governance` if the plan is out of date.")

    # Build the report
    lines = [
        f"<!-- BABOK 5.3 — Prioritize Requirements, Project: {project_name}, "
        f"Session: {session_label}, Method: {method}, Date: {date.today()} -->",
        "",
        f"# Prioritization session: {session_label}",
        f"**Project:** {project_name}  ",
        f"**Method:** {method}  ",
    ]
    if method == "TimeBoxing":
        lines.append(f"**Capacity:** {_fmt_num(capacity_value)} {capacity_unit_value}  ")
    lines.append(f"**Opened on:** {date.today()}")
    if capacity_note:
        lines += ["", capacity_note]
    # Next to the capacity note rather than at the foot of the document: both are
    # warnings about how this session was SET UP, and the BA reads the head of the
    # session sheet before scoring, not the tail of it afterwards.
    if governance_note:
        lines += ["", governance_note]
    lines += [
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
    elif method == "TimeBoxing":
        lines.append("**Value ranking:** the `value` you supply in this session; "
                     "where you supply none, the requirement's current priority below.")
        lines.append("")
        lines.append(f"| ID | Title | Current priority | Cost, {capacity_unit_value} | Stability |")
        lines.append("|-----|----------|-------------------|------|-----------|")
        for n in nodes:
            flag = _stability_flag(n)
            stab_icon = {"critical": "🔴 Critical", "warning": "🟡 Caution",
                         "unknown": "🟡 Unknown"}.get(flag, "🟢 Stable")
            lines.append(f"| {n['id']} | {n.get('title','—')} | {n.get('priority','—')} "
                         f"| ? | {stab_icon} |")
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

      TimeBoxing:
        [{"req_id": "FR-001", "cost": 5, "value": "Must"}, ...]
        (cost — size/budget estimate in the session's capacity unit, required;
         value — optional: omit it and the requirement's current priority is used.
         cost is a team estimate and is averaged WITHOUT influence weighting,
         the same treatment WSJF gives Job Size.)
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

    elif method == "TimeBoxing":
        valid_vals = set(MOSCOW_WEIGHTS.keys())
        for item in raw_scores:
            rid = item.get("req_id")
            if not rid:
                return f"❌ Missing req_id in: {item}"
            if "cost" not in item:
                return (f"❌ Missing `cost` for {rid}. TimeBoxing needs a size/cost "
                        f"estimate for every requirement, in the session's capacity unit.")
            try:
                cost = float(item["cost"])
            except (TypeError, ValueError):
                return (f"❌ Invalid `cost` for {rid}: {item['cost']!r} is not a number.")
            if cost < 0:
                return f"❌ Invalid `cost` for {rid}: {_fmt_num(cost)} — must be ≥ 0."
            value = item.get("value")
            if value is not None and value not in valid_vals:
                return (f"❌ Invalid `value` '{value}' for {rid}. "
                        f"Allowed: Must / Should / Could / Won't — or omit it, and the "
                        f"requirement's current priority is used instead.")
            normalized[rid] = {"cost": cost, "value": value}

    # Whether this is a repeat has to be decided BEFORE the key is inserted: the
    # check used to run afterwards, so every first entry announced itself as an
    # update. Affects all four methods.
    is_repeat = stakeholder_id in session["stakeholder_scores"]

    # Save the scores and influence
    session["stakeholder_scores"][stakeholder_id] = normalized
    if "stakeholder_influence" not in session:
        session["stakeholder_influence"] = {}
    session["stakeholder_influence"][stakeholder_id] = stakeholder_influence

    _save_prio(project_name, prio_data)

    is_update = " (updated)" if is_repeat else ""
    lines = [
        f"✅ Scores for stakeholder **{stakeholder_id}** ({stakeholder_influence} influence) "
        f"saved{is_update}",
        "",
        f"**Project:** {project_name}  ",
        f"**Session:** {session_label}  ",
        f"**Method:** {method}  ",
        f"**Requirements scored:** {len(normalized)}",
        "",
        f"**Stakeholders with scores:** {len(session['stakeholder_scores'])}",
        "",
    ]

    # BABOK 3.3 element .3 — the plan names who takes part in prioritization. The
    # scores are ALREADY saved above: an unplanned scorer is a fact to report, not a
    # reason to lose the input. `stakeholder_influence` is likewise untouched — it
    # weights the aggregation, and deriving it from the plan would move priorities.
    plan, _plan_note = load_ba_plan(project_name)
    planned_participants = planned_prioritization(plan)["participants"]
    if planned_participants and not any(
            reg_norm(p) == reg_norm(stakeholder_id) for p in planned_participants):
        lines += [
            f"⚠️ `{stakeholder_id}` is not among the participants planned in 3.3: "
            f"{', '.join(planned_participants)}.",
            "   The scores are recorded anyway — re-plan 3.3 with `plan_ba_governance` "
            "if the participant list is out of date.",
            "",
        ]

    lines.append(
        "Once all stakeholders have scored the requirements — call `run_aggregation`.")
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

    # A finalised session is a signed record. Re-aggregating it changed the numbers
    # the report renders while the 5.1 graph kept the priorities written at closing
    # time — the artefact and the graph told stakeholders different stories.
    # add_stakeholder_scores already refuses on a closed session; this is the same
    # rule for the other two mutating tools.
    if session.get("status") == "closed":
        return (f"❌ Session '{session_label}' is already closed and its result has "
                f"been written to the 5.1 repository. Open a new session to "
                f"re-prioritise.")

    if not session["stakeholder_scores"]:
        return "⚠️ No stakeholder scores yet. Call add_stakeholder_scores first."

    repo = _load_repo(project_name)
    method = session["method"]
    scores_by_sh = session["stakeholder_scores"]
    influence_by_sh = session.get("stakeholder_influence", {})

    capacity = session.get("capacity") or 0
    capacity_unit = session.get("capacity_unit") or "units"

    # Aggregation by method
    if method == "MoSCoW":
        aggregated = _aggregate_moscow(scores_by_sh, influence_by_sh)
    elif method == "WSJF":
        aggregated = _aggregate_wsjf(scores_by_sh, influence_by_sh)
    elif method == "TimeBoxing":
        aggregated = _aggregate_timebox(scores_by_sh, influence_by_sh, repo,
                                        capacity, session.get("value_overrides"))
    else:
        qmap = session.get("quadrant_mapping") or {
            "QuickWins": "Must", "BigBets": "Should",
            "FillIns": "Could", "ThanklessTasks": "Won't"
        }
        aggregated = _aggregate_impact_effort(scores_by_sh, influence_by_sh, qmap)

    session["aggregated"] = aggregated

    # Stakeholder conflicts (for MoSCoW and TimeBoxing)
    # A resolution recorded earlier has to be carried across, because the list is
    # rebuilt from the raw scores and those still disagree. For the other methods
    # both halves of a resolution are discarded together and the session stays
    # self-consistent; TimeBoxing keeps its half (`value_overrides`), so dropping
    # the record alone would make the final artefact warn about a conflict the BA
    # settled.
    # Keyed by (req_id, conflict_type): a value override is per REQUIREMENT, but a
    # resolution is per CONFLICT. Matching on req_id alone let a resolved dependency
    # violation silently close a separate stakeholder disagreement on the same
    # requirement, and the artefact then counted it resolved with no rationale.
    prior_resolutions = {(c["req_id"], c.get("conflict_type")): c.get("resolution")
                         for c in session.get("conflicts", [])
                         if c.get("resolved")}
    threshold_spread = {"Strict": 1, "Normal": 2, "Loose": 3}[conflict_threshold]
    conflicts = _detect_stakeholder_conflicts(scores_by_sh, method)
    conflicts = [c for c in conflicts if c["spread"] >= threshold_spread]
    for c in conflicts:
        key = (c["req_id"], c.get("conflict_type"))
        if key in prior_resolutions:
            c["resolved"] = True
            c["resolution"] = prior_resolutions[key]
    session["conflicts"] = conflicts

    # Dependency violations. Only TimeBoxing can leave a requirement with no
    # priority, so only it passes the `unplaced` set — the other three methods keep
    # exactly the behaviour they had.
    violations = _find_dependency_violations(
        repo, aggregated,
        _timebox_unplaced(aggregated) if method == "TimeBoxing" else None)
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

    elif method == "TimeBoxing":
        # Read once: the dispatcher above fills the box with this same value, and
        # two independent lookups could drift into a box and a rendering that
        # disagree about its size.
        lines += _timebox_report_block(aggregated, capacity, capacity_unit)

    else:
        lines.append("| ID | Priority | Quadrant | Avg Impact | Avg Effort |")
        lines.append("|-----|-----------|----------|------------|------------|")
        for req_id, data in aggregated.items():
            prio = data.get("priority", "—") if isinstance(data, dict) else data
            icon = {"Must": "🔴", "Should": "🟠", "Could": "🟡", "Won't": "🟢"}.get(prio, "")
            lines.append(f"| {req_id} | {icon} {prio} | {data.get('quadrant','—')} "
                         f"| {data.get('avg_impact','—')} | {data.get('avg_effort','—')} |")

    # Must Inflation. Not offered to a TimeBoxing session: the advice is "re-run
    # using a fixed-budget technique", and this IS one. The ratio is also a property
    # of the capacity there rather than of stakeholder discipline — a smaller box
    # changes it mechanically.
    if inflation["inflated"] and method != "TimeBoxing":
        lines += [
            "",
            "---",
            "",
            f"## 🟠 Must Inflation — {int(inflation['must_ratio']*100)}% of requirements at Must",
            "",
            "Recommendation: re-run the session with method=\"TimeBoxing\" — set the "
            "capacity the team can actually deliver, and the box decides what fits.",
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

    # Update the aggregated value.
    # TimeBoxing is different in kind: for the other three methods `priority` IS the
    # decision, but here it is the OUTCOME of filling the box. So the decision is
    # recorded as the requirement's value and the box is filled again — otherwise a
    # resolved requirement could read "✂️ cut" and "Must" on the same row, and a
    # priority that the capacity does not support would reach the 5.1 graph.
    if session.get("status") == "closed":
        return (f"❌ Session '{session_label}' is already closed and its result has "
                f"been written to the 5.1 repository. A decision recorded now would "
                f"appear in a regenerated report but never reach the graph. Open a "
                f"new session to revise priorities.")

    timebox_note = ""
    if session.get("method") == "TimeBoxing":
        session.setdefault("value_overrides", {})[req_id] = final_priority
        repo_for_refill = _load_repo(project_name)
        session["aggregated"] = _aggregate_timebox(
            session.get("stakeholder_scores", {}),
            session.get("stakeholder_influence", {}),
            repo_for_refill,
            session.get("capacity") or 0,
            session["value_overrides"],
        )
        entry = session["aggregated"].get(req_id)
        # The refill can flip many priorities at once — a requirement pulled into the
        # box displaces another — so violations computed against the old fill are
        # stale, and a stale violation points the BA at the wrong pair.
        # The rebuild returns fresh rows with no `resolved` flags, and the loop
        # further down marks only the requirement being resolved right now. Without
        # carrying earlier decisions across, resolving a second violation reopened
        # the first, and "All conflicts resolved" became unreachable.
        settled = {(v["req_id"], v["depends_on"]): v.get("resolution")
                   for v in session.get("dependency_violations", [])
                   if v.get("resolved")}
        session["dependency_violations"] = _find_dependency_violations(
            repo_for_refill, session["aggregated"],
            _timebox_unplaced(session["aggregated"]))
        for v in session["dependency_violations"]:
            key = (v["req_id"], v["depends_on"])
            if key in settled:
                v["resolved"] = True
                v["resolution"] = settled[key]
        # A `Won't` decision takes effect immediately — it excludes the requirement
        # whether or not anyone estimated it — so the "needs an estimate first" note
        # would be false for that case.
        if final_priority != "Won't" and (entry is None
                                          or entry.get("cost") is None):
            # No value can PLACE a requirement nobody costed. Saying "✅ resolved"
            # while the box is unchanged would be a confident answer about data the
            # BA never supplied.
            timebox_note = (
                f"\n⚠️ `{req_id}` has no cost estimate in this session, so the box "
                f"could not be refilled for it — the decision is recorded, but it "
                f"takes effect only once an estimate is added and `run_aggregation` "
                f"is called again.")
    elif req_id in session["aggregated"]:
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
    if timebox_note:
        lines += [timebox_note, ""]

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

    # A session already finalised is re-rendered, not re-applied. Calling this twice
    # used to write a second set of priority_updated rows into the graph history for
    # the same decisions — the history stops being a record of what happened and
    # starts being a record of how often the BA pressed the button. Regenerating the
    # report is a legitimate reason to call again, so this warns instead of refusing.
    already_closed = session.get("status") == "closed"
    refinalise_note = ""
    if already_closed:
        refinalise_note = (
            f"⚠️ This session was already finalised on "
            f"{session.get('closed_at', 'an earlier date')}. The report below was "
            f"regenerated from the stored result; the 5.1 repository was NOT written "
            f"to again. To change priorities, open a new session.")

    # Update the 5.1 repository
    repo = _load_repo(project_name)
    updated_count = 0
    priority_summary = {}
    # Scores whose req_id matches NO repository node — a stakeholder scored a typo
    # ("FR-01" for FR-001"). They rendered in the aggregation report and then
    # vanished here without a word: "Requirements updated: 4" under a table
    # showing 5 priorities, a count with no explanation of the difference.
    not_found_ids = []
    # Scores whose id matches a node that is NOT a requirement (goal/risk/CR/scope).
    not_req_ids = []

    for req_id, agg_data in session["aggregated"].items():
        priority = agg_data.get("priority") if isinstance(agg_data, dict) else agg_data
        if not priority:
            continue
        node = next((n for n in repo.get("requirements", []) if n["id"] == req_id), None)
        if node is None:
            not_found_ids.append(req_id)
            continue
        # Priority is a REQUIREMENT attribute. start_prioritization_session already hides
        # non-requirement nodes; guard the write too, so a stakeholder scoring a
        # business_goal / risk / change_request / solution_scope id does not stamp a
        # MoSCoW/wsjf value onto a node that other chapters read.
        if node.get("type", "") in NON_REQUIREMENT_NODE_TYPES:
            not_req_ids.append(req_id)
            continue
        old_priority = node.get("priority", "—")
        updated_count += 1
        priority_summary.setdefault(priority, []).append(req_id)

        # The summary above is rebuilt on every call so a re-render still shows the
        # stored result; only the WRITES are skipped for an already-finalised session.
        if already_closed:
            continue

        node["priority"] = priority
        # WSJF sessions also persist the score: 5.5's rejection analysis reads
        # `wsjf_score` off the node to warn "you are rejecting a high-value
        # requirement" — a reader that existed with no writer, so the warning
        # could never fire.
        if isinstance(agg_data, dict) and agg_data.get("wsjf") is not None:
            node["wsjf_score"] = agg_data["wsjf"]

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

    if not already_closed:
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
    ]
    if refinalise_note:
        lines += [refinalise_note, ""]

    # BABOK 3.3 element .3 reconciled against what actually happened. Appended BELOW
    # the header block on purpose: the two `lines.insert(7, ...)` calls further down
    # address a FIXED index, so a block added above the header would swallow the
    # "scored a typo" warning into this section instead of the header.
    lines += _planned_approach_block(project_name, session)

    lines += [
        "---",
        "",
        "## Final priorities",
        "",
    ]
    if not_found_ids:
        listed = ", ".join(f"`{r}`" for r in sorted(not_found_ids))
        lines.insert(7, "")
        lines.insert(
            7,
            f"⚠️ **{len(not_found_ids)} scored id(s) match no repository node and "
            f"were NOT saved:** {listed}. Check for typos (e.g. `FR-01` for "
            f"`FR-001`) and re-score, or the priority is lost.",
        )

    if not_req_ids:
        listed_nr = ", ".join(f"`{r}`" for r in sorted(not_req_ids))
        lines.insert(7, "")
        lines.insert(
            7,
            f"⚠️ **{len(not_req_ids)} scored id(s) are NOT requirements** (business goal / "
            f"risk / change request / solution scope) and were NOT prioritised: {listed_nr}.",
        )

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

    # The box belongs in the signed artefact too, not only in the working
    # aggregation output: this is the document that states what the team committed
    # to, what was cut, and what nobody estimated. Same renderer, so the two
    # documents cannot drift.
    if session["method"] == "TimeBoxing":
        lines += ["---", ""]
        if not session.get("aggregated"):
            # "in: 0 · cut: 0 · not estimated: 0" over an empty aggregate is a
            # signed statement that nothing was cut and nothing is missing an
            # estimate, when in fact the backlog was never considered at all.
            lines += [
                "## Box", "",
                "⚠️ No box was built: `run_aggregation` was never called for this "
                "session, so no requirement was weighed against the capacity. The "
                "counts below are not a statement about the backlog.",
                "",
            ]
        else:
            lines += _timebox_report_block(session["aggregated"],
                                           session.get("capacity") or 0,
                                           session.get("capacity_unit") or "units")
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
            # This used to send the BA to `resolve_conflict`, which refuses on a
            # closed session — the document instructed a step the platform rejects.
            "The result has been saved with these left open, and the session is now "
            "closed. To settle them, open a new prioritization session: a decision "
            "recorded against a closed one would appear in a regenerated report but "
            "never reach the requirements graph.",
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
