"""
BABOK 5.3 — Prioritize Requirements
MCP-инструменты для приоритизации требований и дизайнов.

Tools:
  - start_prioritization_session  — open a session, choose a method (MoSCoW / WSJF /
                                    ImpactEffort / TimeBoxing), get the requirement list
  - add_stakeholder_scores        — add one stakeholder's scores
  - run_aggregation               — aggregate scores, surface conflicts and dependency violations
  - resolve_conflict              — record a conflict resolution decision
  - save_prioritization_result    — finalize the session, update the 5.1 repository

Хранение:
  - Приоритеты пишутся в {project}_traceability_repo.json (поле priority в каждом требовании)
  - Снапшоты сессий хранятся в {project}_prioritization.json

Интеграция:
  Вход:  репозиторий 5.1 (зависимости), атрибуты 5.2 (стабильность), реестр 4.2 (influence)
  Выход: приоритизированные требования → 6.3 (Оценка рисков)

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst (AI Платформа AIналитик). Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
from datetime import date, datetime
from typing import Literal, Optional
from mcp.server.fastmcp import FastMCP
from skills.common import (write_json_artifact, save_artifact, logger, DATA_DIR, data_path,
                           normalize_project_id, NON_REQUIREMENT_NODE_TYPES,
    read_json_artifact, guard_artifact_errors, parse_json_dict_list,
    load_ba_plan, planned_prioritization, reg_norm,
    planned_party_status, PARTY_UNPLANNED, PARTY_PLANNED, PARTY_UNBRIDGEABLE,
    pick_field, unrecognized_records_error,
)

from skills.plural_ru import plural_ru

mcp = FastMCP("BABOK_Requirements_Prioritize")

REPO_FILENAME = "traceability_repo.json"
PRIO_FILENAME = "prioritization.json"

# MoSCoW числовые веса для агрегации
MOSCOW_WEIGHTS = {"Must": 4, "Should": 3, "Could": 2, "Won't": 1}
MOSCOW_THRESHOLDS = [("Must", 3.5), ("Should", 2.5), ("Could", 1.5), ("Won't", 0.0)]

# Influence веса для взвешенного голосования
INFLUENCE_WEIGHTS = {"High": 3, "Medium": 2, "Low": 1}

# Порог Must Inflation
MUST_INFLATION_THRESHOLD = 0.6

# Стабильность — пороги minor-версии (совпадают с 5.2)
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
# Утилиты — файловый слой
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
    write_json_artifact(path, repo)


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
    write_json_artifact(path, prio)


def _find_session(sessions: list, label: str) -> Optional[dict]:
    for s in sessions:
        if s["label"] == label:
            return s
    return None


# ---------------------------------------------------------------------------
# Утилиты — логика методов
# ---------------------------------------------------------------------------

def _fmt_num(value) -> str:
    """40.0 → '40', 2.5 → '2.5'. Capacities and costs read as numbers, not floats."""
    try:
        f = float(value)
    except (TypeError, ValueError):
        return str(value)
    return str(int(f)) if f == int(f) else str(round(f, 2))


def _minor_version(version_str: str) -> int:
    """Извлекает minor-часть версии: '1.3' → 3"""
    try:
        parts = str(version_str).split(".")
        if len(parts) >= 2:
            return int(parts[1])
        return 0
    except (ValueError, IndexError):
        return 0


def _stability_flag(node: dict) -> Optional[str]:
    """Возвращает флаг стабильности или None если всё ок."""
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
    Агрегирует MoSCoW-оценки нескольких стейкхолдеров с весами influence.
    Возвращает {req_id: {"priority": "Must"|..., "weighted_score": float}}
    """
    # Собираем все req_id
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
    Агрегирует WSJF-оценки.
    scores_by_sh[sh_id][req_id] = {"bv": N, "tc": N, "rr": N, "js": N}
    Возвращает {req_id: {"priority_score": float, "wsjf": float, "cod": float, "js": float}}
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
            # Job Size — техническая оценка, не взвешивается по influence
            js_sum += s.get("js", 1)
            total_weight += weight

        if total_weight == 0:
            continue

        cod = (bv_sum + tc_sum + rr_sum) / total_weight
        # JS усредняем по числу стейкхолдеров кто его дал
        n_sh = sum(1 for sh_scores in scores_by_sh.values() if req_id in sh_scores)
        js = js_sum / n_sh if n_sh > 0 else 1.0
        wsjf = round(cod / js, 2) if js > 0 else 0.0

        result[req_id] = {
            "priority_score": wsjf,
            "wsjf": wsjf,
            "cod": round(cod, 2),
            "js": round(js, 2),
        }

    # Нормализуем в MoSCoW-совместимые метки для единообразия
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
    Агрегирует Impact/Effort оценки.
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

        # Определяем квадрант
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
                "dep_priority": "не размещено",
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
    Ищет конфликты между стейкхолдерами.
    MoSCoW: расхождение ≥ 2 категории.
    Возвращает список {"req_id", "conflict_type", "scores", "severity"}
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
    plan, plan_note = load_ba_plan(project_name)
    planned = planned_prioritization(plan)
    if not any(planned.values()):
        # An unreadable plan removes this whole section from a SIGNED report, leaving
        # output identical to a project that never planned an approach. That is the
        # one case where silence is a claim, so the document says it.
        return ["## Запланированный подход (3.3)", "", plan_note, ""] if plan_note else []

    method = session.get("method", "")
    lines = ["## Запланированный подход (3.3)", ""]
    if planned["technique"]:
        match = "✅" if planned["technique"] == method else "⚠️"
        lines.append(
            f"**Technique:** {planned['technique']} planned — {method} used {match}  ")
    else:
        # Said plainly rather than omitted: the three parts are independent, and a
        # block that silently skips the technique row reads as though one was planned
        # and matched.
        lines.append("**Техника:** в 3.3 не запланирована  ")

    if planned["criteria"]:
        lines.append(f"**Criteria:** {', '.join(planned['criteria'])}  ")

    planned_names = planned["participants"]
    if planned_names:
        scorers = list(session.get("stakeholder_scores", {}).keys())
        # One matcher for all three lists, and it is the registry-bridged one: a plan
        # naming roles and a session naming people made this paragraph state "0 of 2
        # planned participants scored" over a session in which both of them did.
        scored = [p for p in planned_names
                  if any(planned_party_status(project_name, [p], s) == PARTY_PLANNED
                         for s in scorers)]
        missing = [p for p in planned_names if p not in scored]
        extra, unmatched = [], []
        for s in scorers:
            status = planned_party_status(project_name, planned_names, s)
            if status == PARTY_UNPLANNED:
                extra.append(s)
            elif status == PARTY_UNBRIDGEABLE:
                unmatched.append(s)
        # Silence is right for an ACCUSATION and wrong for a COUNT. An unbridgeable
        # scorer belongs to neither list, so the paragraph reported "0 of 2 planned
        # participants scored" over a session both of them scored — and, by dropping
        # the only line that named them, deleted the evidence against its own number.
        # The count is stated only when it can be trusted; otherwise the document says
        # what it does not know.
        if unmatched:
            lines.append(
                f"**Участие:** оценки дали {len(scorers)} "
                f"{plural_ru(len(scorers), 'стейкхолдер', 'стейкхолдера', 'стейкхолдеров')}; "
                f"платформа не может определить, кто из запланированных участников это был.  ")
            lines.append(
                f"- Сопоставить с планом не удалось: {', '.join(unmatched)}  ")
            lines.append(
                "- 3.3 планирует роли, а сессия записывает людей. Заведите реестр "
                "стейкхолдеров (3.2 / 4.2) — и одно с другим сойдётся.  ")
        else:
            lines.append(f"**Участие:** оценки дали {len(scored)} из "
                         f"{len(planned_names)} запланированных участников.  ")
            if missing:
                lines.append(f"- Не оценивали: {', '.join(missing)}  ")
            # One person can legitimately hold two planned roles, and then one scorer
            # closes two rows. Stating the count without stating that is a claim about
            # how many PEOPLE took part that nobody made.
            if len(scored) > len(scorers):
                lines.append(
                    f"- Замечание: {len(scorers)} "
                    f"{plural_ru(len(scorers), 'стейкхолдер закрыл', 'стейкхолдера закрыли', 'стейкхолдеров закрыли')} "
                    f"вместе {len(scored)} запланированных ролей.  ")
        if extra:
            lines.append(f"- Оценивали, не будучи запланированными: {', '.join(extra)}  ")

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
            "⚠️ У этой сессии не записана пригодная ёмкость, поэтому в коробку ничего "
            "не поместилось. Откройте новую сессию TimeBoxing с capacity > 0.",
            "",
        ]

    lines += [
        f"**Box:** {_fmt_num(used)} / {_fmt_num(capacity)} {unit} ({pct}%) · "
        f"в коробке: {len(in_box)} · отрезано: {len(cut)} · исключено: {len(excluded)} · "
        f"не оценено: {len(unestimated)}",
        "",
        # `Value` and `Priority` are different things here and both belong on the
        # row: a cut requirement keeps its value (Should) while its outcome is
        # Won't. Printing only the outcome, with the value appearing in a note
        # further down, put two labels for one requirement in one document.
        f"| ID | В коробке | Ценность | Приоритет | Источник ценности | Стоимость, {unit} | Накопительно |",
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
        lines += ["", "**Пропущены (более дешёвые под ними всё же взяты):**", ""]
        for req_id in skipped:
            d = placed[req_id]
            # Phrased so it reads correctly for any unit and any remainder: a
            # free-form unit string ("story points", "USD") cannot be pluralised
            # reliably, and "1 story points were left" is in a stakeholder document.
            lines.append(f"- `{req_id}` ({d['value_label']}, {_fmt_num(d['cost'])} {unit}) "
                         f"— остаток ёмкости на тот момент: "
                         f"{_fmt_num(d['remaining_at_skip'])} {unit}.")

    spread = sorted((r for r, d in placed.items() if d.get("cost_spread")),
                    key=lambda r: -placed[r]["cost_spread"])
    if spread:
        lines += ["", "**Оценки расходятся (разброс усреднён в стоимость выше):**", ""]
        for req_id in spread:
            lines.append(f"- `{req_id}` — разброс {_fmt_num(placed[req_id]['cost_spread'])} "
                         f"{unit} вокруг {_fmt_num(placed[req_id]['cost'])}.")

    if excluded:
        lines += ["", "**Исключены решением (Won't — ёмкость на них не тратилась):**", ""]
        for req_id in excluded:
            lines.append(f"- `{req_id}` — в этой сессии оценено как Won\'t, поэтому за "
                         f"место в коробке не конкурировало.")

    if off_backlog:
        lines += ["", "**⚠️ Оценено, но не является требованием этого проекта "
                  "(в коробку не берётся):**", ""]
        for req_id in off_backlog:
            lines.append(f"- `{req_id}`")
        lines.append("")
        lines.append("Этим id не соответствует ни одно требование в репозитории 5.1 — "
                     "опечатка (`FR-01` вместо `FR-001`) либо узел риска / цели / границ "
                     "решения, оценённый по ошибке. Ёмкость они не расходуют. Исправьте "
                     "id и оцените заново, иначе оценка потеряется.")

    if cut:
        # The label this method writes for a capacity cut is read by other chapters
        # as a scope decision (7.5 maps Won't to out_of_scope; 5.4 flags a change
        # request that touches one). 5.3 itself deliberately refuses to read a
        # stored Won't back as a decision, so the BA has to know the asymmetry.
        lines += [
            "",
            "Отрезанные здесь требования пишутся в граф требований как `Won\'t` — та же "
            "метка, что и у явного «не в этот раз». Глава 7.5 читает её как «вне границ», "
            "а 5.4 помечает затрагивающие их запросы на изменение. Если требование "
            "отрезано лишь из-за ёмкости этого периода, перезапустите коробку при "
            "изменении ёмкости, а не оставляйте метку говорить за себя.",
        ]

    if unestimated:
        lines += ["", "**⚠️ Не оценено — не размещено (приоритет не пишется):**", ""]
        for req_id in unestimated:
            lines.append(f"- `{req_id}`")
        lines.append("")
        lines.append("Требование без стоимости нельзя положить в коробку ёмкости. "
                     "Пометить его Won\'t значило бы сделать вывод из отсутствующих "
                     "данных — добавьте оценку и повторите агрегацию.")
    return lines


# ---------------------------------------------------------------------------
# MCP-инструменты
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
      Пример: '{"QuickWins": "Must", "BigBets": "Could"}' — частичный маппинг сливается
      с дефолтным, поэтому передавай только те квадранты, которые меняешь.
      If empty — the default mapping is used.
    - capacity: box size for TimeBoxing — what the team can deliver in the period,
      or the fixed budget. Required (> 0) for method="TimeBoxing", ignored otherwise.
    - capacity_unit: unit for capacity and for the per-requirement costs
      ("story points", "person-days", "USD"). Blank → "units".
    """
    logger.info(f"5.3 start_prioritization_session: {project_name} / {session_label}")

    repo = _load_repo(project_name)
    prio_data = _load_prio(project_name)

    # Проверяем что сессия с таким именем не существует
    existing = _find_session(prio_data["sessions"], session_label)
    if existing:
        return (f"⚠️ Сессия '{session_label}' уже существует для проекта '{project_name}'.\n"
                f"Используйте другое название или продолжите работу с существующей сессией.")

    # Дефолтный маппинг квадрантов
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
            return "❌ Ошибка парсинга quadrant_mapping_json. Проверьте формат JSON."

    # Time Boxing/Budgeting prioritises by the allocation of a fixed resource
    # (BABOK 10.33.3 .3). Without a box there is nothing to fill.
    capacity_note = ""
    if method == "TimeBoxing":
        try:
            capacity_value = float(capacity)
        except (TypeError, ValueError):
            capacity_value = 0.0
        if capacity_value <= 0:
            return ("❌ Методу TimeBoxing нужен `capacity` > 0 — это размер коробки: "
                    "то, что команда выдаёт за период, либо фиксированный бюджет.\n"
                    "Пример: capacity=40, capacity_unit=\"story points\".")
        capacity_unit_value = capacity_unit.strip() or "units"
    else:
        capacity_value = None
        capacity_unit_value = None
        if capacity:
            # wsjf_scale and quadrant_mapping are dropped silently because they only
            # shape a report. A capacity is a promise about scope: dropped silently,
            # it leaves the BA believing a budget was applied when it never was.
            capacity_note = (f"⚠️ `capacity` не учитывается: метод — {method}. "
                             f"Ограничение по ёмкости применимо только к сессиям TimeBoxing.")

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
        return (f"⚠️ Репозиторий '{project_name}' не содержит требований или не существует.\n"
                f"Сначала создайте репозиторий через 5.1 (init_traceability_repo).")

    # Проверяем стабильность
    stability_warnings = []
    stability_critical = []
    for node in nodes:
        flag = _stability_flag(node)
        if flag == "critical":
            stability_critical.append(node["id"])
        elif flag in ("warning", "unknown"):
            stability_warnings.append(node["id"])

    # Создаём сессию
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
    plan, plan_note = load_ba_plan(project_name)
    planned_technique = planned_prioritization(plan)["technique"]
    governance_note = plan_note if plan_note else ""
    if planned_technique and planned_technique != method:
        governance_note = ((governance_note + "\n\n" if governance_note else "") +
            f"⚠️ Эта сессия использует **{method}**, а в 3.3 запланирована техника "
            f"**{planned_technique}**.\n"
            f"   Сессия продолжается с {method}: `method` — ваш явный выбор, и он "
            f"определяет весь алгоритм агрегации. Если план устарел, перепланируйте 3.3 "
            f"через `plan_ba_governance`.")

    # Build the report
    lines = [
        f"<!-- BABOK 5.3 — Prioritize Requirements, Проект: {project_name}, "
        f"Сессия: {session_label}, Метод: {method}, Дата: {date.today()} -->",
        "",
        f"# Сессия приоритизации: {session_label}",
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
        f"## Требования для оценки ({len(nodes)} шт.)",
        "",
    ]

    if method == "MoSCoW":
        lines.append("| ID | Название | Тип | Текущий приоритет | Stability |")
        lines.append("|-----|----------|-----|-------------------|-----------|")
        for n in nodes:
            flag = _stability_flag(n)
            stab_icon = {"critical": "🔴 Критично", "warning": "🟡 Внимание",
                         "unknown": "🟡 Unknown"}.get(flag, "🟢 Stable")
            lines.append(f"| {n['id']} | {n.get('title','—')} | {n.get('type','—')} "
                         f"| {n.get('priority','—')} | {stab_icon} |")
    elif method == "WSJF":
        lines.append(f"**Шкала:** {wsjf_scale}  ")
        if wsjf_scale == "Fibonacci":
            lines.append("**Значения:** 1, 2, 3, 5, 8, 13 (относительные, выберите эталон = 3)")
        else:
            lines.append("**Значения:** 1–10 (абсолютные)")
        lines.append("")
        lines.append("| ID | Название | Компоненты для оценки: BV, TC, RR, JS |")
        lines.append("|-----|----------|---------------------------------------|")
        for n in nodes:
            lines.append(f"| {n['id']} | {n.get('title','—')} | BV=?, TC=?, RR=?, JS=? |")
    elif method == "TimeBoxing":
        lines.append("**Ранжирование по ценности:** `value`, который вы задаёте в этой "
                     "сессии; там, где не задан, берётся текущий приоритет требования ниже.")
        lines.append("")
        lines.append(f"| ID | Название | Текущий приоритет | Стоимость, {capacity_unit_value} | Стабильность |")
        lines.append("|-----|----------|-------------------|------|-----------|")
        for n in nodes:
            flag = _stability_flag(n)
            stab_icon = {"critical": "🔴 Critical", "warning": "🟡 Caution",
                         "unknown": "🟡 Unknown"}.get(flag, "🟢 Stable")
            lines.append(f"| {n['id']} | {n.get('title','—')} | {n.get('priority','—')} "
                         f"| ? | {stab_icon} |")
    else:  # ImpactEffort
        lines.append("**Маппинг квадрантов:**")
        for q, p in quadrant_mapping.items():
            q_label = {"QuickWins": "Quick Wins (высокий эффект, малые усилия)",
                       "BigBets": "Big Bets (высокий эффект, большие усилия)",
                       "FillIns": "Fill-ins (низкий эффект, малые усилия)",
                       "ThanklessTasks": "Thankless Tasks (низкий эффект, большие усилия)"}.get(q, q)
            lines.append(f"- {q_label} → **{p}**")
        lines.append("")
        lines.append("| ID | Название | Impact (Low/Medium/High) | Effort (Low/Medium/High) |")
        lines.append("|-----|----------|--------------------------|--------------------------|")
        for n in nodes:
            lines.append(f"| {n['id']} | {n.get('title','—')} | ? | ? |")

    if stability_critical:
        lines += [
            "",
            "---",
            "",
            "## ⚠️ Предупреждения о стабильности",
            "",
            "### 🔴 Критически нестабильные (версия 1.4+)",
            "Присвоение Must создаёт высокий риск переделок.",
            "",
        ]
        for rid in stability_critical:
            lines.append(f"- `{rid}`")

    if stability_warnings:
        lines += [
            "",
            "### 🟡 Нестабильные (версия 1.3+) или с неизвестной стабильностью",
            "",
        ]
        for rid in stability_warnings:
            lines.append(f"- `{rid}`")

    lines += [
        "",
        "---",
        "",
        "## Следующие шаги",
        "",
        "1. Вызвать `add_stakeholder_scores` для каждого стейкхолдера",
        "2. После сбора всех оценок — вызвать `run_aggregation`",
        "3. Разрешить конфликты (`resolve_conflict`) если они есть",
        "4. Финализировать: `save_prioritization_result`",
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
    Добавить оценки одного стейкхолдера для текущей сессии.

    Вызывается по одному разу на стейкхолдера.
    Повторный вызов для того же стейкхолдера заменяет предыдущие оценки.

    Parameters:
    - stakeholder_id: who is scoring — a name or a role, as recorded in the
      stakeholder registry (3.2/4.2), e.g. "John Smith" or "Product Owner".
      (The registry keys people by name; there are no "SH-00n" ids. If 3.3 planned
      the prioritization participants, the registry is what lets a name entered here
      match a role planned there.)
    - stakeholder_influence: the stakeholder's level of influence
    - scores_json: scores, depending on method:

      MoSCoW:
        [{"req_id": "FR-001", "score": "Must"}, ...]

      WSJF:
        [{"req_id": "FR-001", "bv": 5, "tc": 3, "rr": 2, "js": 3}, ...]
        (js — Job Size, оценка усилий от команды разработки)

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
        return f"❌ Сессия '{session_label}' не найдена. Сначала вызовите start_prioritization_session."

    if session["status"] == "closed":
        return f"❌ Сессия '{session_label}' уже закрыта."

    # Elements are read as objects (`item.get("req_id")`) immediately below, so the
    # shape has to be checked here rather than discovered by an AttributeError.
    raw_scores, shape_error = parse_json_dict_list(
        scores_json, "scores_json", required=True,
        example='[{"req_id": "FR-001", "score": "Must"}]')
    if shape_error:
        return shape_error

    # Валидация и нормализация оценок по методу
    method = session["method"]
    normalized = {}

    if method == "MoSCoW":
        valid_vals = set(MOSCOW_WEIGHTS.keys())
        for item in raw_scores:
            rid = pick_field(item, "req_id", "requirement_id", "id")
            # `priority` is what this concept is called EVERYWHERE else in the
            # platform: the graph node's field, this module's own aggregation output
            # (`{req_id: {"priority": ...}}`), and 7.1's writer. Only the input here
            # said `score`, so the natural spelling was rejected — and rejected as a
            # bad VALUE ("Invalid value 'None'"), sending the analyst to re-check
            # priorities they had written correctly.
            score = pick_field(item, "score", "priority", "moscow")
            if not rid:
                return f"❌ Не задан req_id в: {item}"
            if not score:
                return unrecognized_records_error(
                    "scores_json", ("score", "priority", "moscow"),
                    '[{"req_id": "FR-001", "score": "Must"}]')
            if score not in valid_vals:
                return (f"❌ Недопустимое значение '{score}' для {rid}. "
                        f"Допустимо: Must / Should / Could / Won't")
            normalized[rid] = score

    elif method == "WSJF":
        for item in raw_scores:
            rid = pick_field(item, "req_id", "requirement_id", "id")
            if not rid:
                return f"❌ Отсутствует req_id в: {item}"
            normalized[rid] = {
                "bv": float(item.get("bv", 0)),
                "tc": float(item.get("tc", 0)),
                "rr": float(item.get("rr", 0)),
                "js": float(item.get("js", 1)),
            }

    elif method == "ImpactEffort":
        valid_ie = {"Low", "Medium", "High"}
        for item in raw_scores:
            rid = pick_field(item, "req_id", "requirement_id", "id")
            impact = pick_field(item, "impact", "value") or "Medium"
            effort = pick_field(item, "effort", "cost", "size") or "Medium"
            if not rid:
                return f"❌ Отсутствует req_id в: {item}"
            if impact not in valid_ie or effort not in valid_ie:
                return (f"❌ Недопустимое значение impact/effort для {rid}. "
                        f"Допустимо: Low / Medium / High")
            normalized[rid] = {"impact": impact, "effort": effort}

    elif method == "TimeBoxing":
        valid_vals = set(MOSCOW_WEIGHTS.keys())
        for item in raw_scores:
            rid = pick_field(item, "req_id", "requirement_id", "id")
            if not rid:
                return f"❌ Не задан req_id в: {item}"
            if "cost" not in item:
                return (f"❌ Не задан `cost` для {rid}. TimeBoxing требует оценку "
                        f"размера/стоимости по каждому требованию, в единицах ёмкости сессии.")
            try:
                cost = float(item["cost"])
            except (TypeError, ValueError):
                return (f"❌ Некорректный `cost` для {rid}: {item['cost']!r} — не число.")
            if cost < 0:
                return f"❌ Некорректный `cost` для {rid}: {_fmt_num(cost)} — должен быть ≥ 0."
            value = item.get("value")
            if value is not None and value not in valid_vals:
                return (f"❌ Некорректный `value` '{value}' для {rid}. "
                        f"Допустимо: Must / Should / Could / Won't — либо не задавайте его, "
                        f"и тогда берётся текущий приоритет требования.")
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
        f"✅ Оценки стейкхолдера **{stakeholder_id}** (влияние: {stakeholder_influence}) "
        f"сохранены{is_update}",
        "",
        f"**Проект:** {project_name}  ",
        f"**Сессия:** {session_label}  ",
        f"**Метод:** {method}  ",
        f"**Требований оценено:** {len(normalized)}",
        "",
        f"**Стейкхолдеров с оценками:** {len(session['stakeholder_scores'])}",
        "",
    ]

    # BABOK 3.3 element .3 — the plan names who takes part in prioritization. The
    # scores are ALREADY saved above: an unplanned scorer is a fact to report, not a
    # reason to lose the input. `stakeholder_influence` is likewise untouched — it
    # weights the aggregation, and deriving it from the plan would move priorities.
    plan, plan_note = load_ba_plan(project_name)
    planned_participants = planned_prioritization(plan)["participants"]
    # Through the registry bridge: 3.3 plans ROLES and this parameter is usually a
    # person, so a bare comparison accused every scorer on a correctly-planned project.
    # PARTY_UNBRIDGEABLE (no registry to tie the two together) says nothing at all —
    # a guess stated as a finding is worse than no finding.
    if planned_party_status(project_name, planned_participants,
                            stakeholder_id) == PARTY_UNPLANNED:
        lines += [
            f"⚠️ `{stakeholder_id}` нет среди участников, запланированных в 3.3: "
            f"{', '.join(planned_participants)}.",
            "   Оценки всё равно записаны — если список участников устарел, "
            "перепланируйте 3.3 через `plan_ba_governance`.",
            "",
        ]
    if plan_note:
        lines += [plan_note, ""]

    lines.append(
        "Когда все стейкхолдеры оценят требования — вызови `run_aggregation`.")
    return "\n".join(lines)


@mcp.tool()
@guard_artifact_errors
def run_aggregation(
    project_name: str,
    session_label: str,
    conflict_threshold: Literal["Strict", "Normal", "Loose"] = "Normal",
) -> str:
    """
    Агрегировать оценки стейкхолдеров, рассчитать приоритеты, выявить конфликты.

    - Strict: конфликт при расхождении ≥ 1 категории
    - Normal: конфликт при расхождении ≥ 2 категории (рекомендуется)
    - Loose: конфликт только Must vs Won't

    Детектирует:
    - 🔴 Межстейкхолдерские конфликты
    - ⚠️ Dependency violations (Must/Should зависит от ниже-приоритетного)
    - 🟡 Must Inflation (>60% требований в Must)
    - 🟡 Нестабильные требования в высоком приоритете
    """
    logger.info(f"5.3 run_aggregation: {project_name}/{session_label}")

    prio_data = _load_prio(project_name)
    session = _find_session(prio_data["sessions"], session_label)
    if not session:
        return f"❌ Сессия '{session_label}' не найдена."

    # A finalised session is a signed record. Re-aggregating it changed the numbers
    # the report renders while the 5.1 graph kept the priorities written at closing
    # time — the artefact and the graph told stakeholders different stories.
    # add_stakeholder_scores already refuses on a closed session; this is the same
    # rule for the other two mutating tools.
    if session.get("status") == "closed":
        return (f"❌ Сессия '{session_label}' уже закрыта, и её результат записан в "
                f"репозиторий 5.1. Чтобы переприоритизировать, откройте новую сессию.")

    if not session["stakeholder_scores"]:
        return "⚠️ Нет оценок стейкхолдеров. Сначала вызовите add_stakeholder_scores."

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

    # Нестабильные в Must
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

    # Отчёт
    lines = [
        f"<!-- BABOK 5.3 — Агрегация, {project_name}/{session_label}, {date.today()} -->",
        "",
        f"# Результаты агрегации: {session_label}",
        f"**Проект:** {project_name}  ",
        f"**Метод:** {method}  ",
        f"**Стейкхолдеров:** {len(scores_by_sh)}  ",
        f"**Порог конфликта:** {conflict_threshold}",
        "",
        "---",
        "",
        "## Итоговые приоритеты",
        "",
    ]

    if method == "MoSCoW":
        lines.append("| ID | Приоритет | Взвешенный балл |")
        lines.append("|-----|-----------|-----------------|")
        for req_id, data in sorted(aggregated.items(),
                                   key=lambda x: x[1].get("weighted_score", 0) if isinstance(x[1], dict) else 0,
                                   reverse=True):
            prio = data.get("priority", "—") if isinstance(data, dict) else data
            ws = data.get("weighted_score", "—") if isinstance(data, dict) else "—"
            icon = {"Must": "🔴", "Should": "🟠", "Could": "🟡", "Won't": "🟢"}.get(prio, "")
            lines.append(f"| {req_id} | {icon} {prio} | {ws} |")

    elif method == "WSJF":
        lines.append("| ID | Приоритет | WSJF | CoD | JS |")
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
        lines.append("| ID | Приоритет | Квадрант | Avg Impact | Avg Effort |")
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
            f"## 🟠 Must Inflation — {int(inflation['must_ratio']*100)}% требований в Must",
            "",
            "Рекомендация: проведите сессию заново с method=\"TimeBoxing\" — задайте "
            "ёмкость, которую команда действительно выдаёт, и пусть коробка решит, что "
            "помещается.",
            "Спросите стейкхолдеров: «Если бы мы могли выпустить только 40% — что бы вы "
            "выбрали?»",
        ]

    # Конфликты
    if conflicts:
        lines += [
            "",
            "---",
            "",
            f"## 🔴 Конфликты стейкхолдеров ({len(conflicts)} шт.)",
            "",
            "Требуют разрешения перед финализацией.",
            "",
        ]
        for c in conflicts:
            lines.append(f"### Требование `{c['req_id']}` — {c['severity']}")
            lines.append("")
            for sh_id, score in c["scores"].items():
                infl = influence_by_sh.get(sh_id, "Medium")
                lines.append(f"- **{sh_id}** ({infl}): **{score}**")
            lines.append("")
            lines.append("Вызовите `resolve_conflict` для фиксации решения.")
            lines.append("")
    else:
        lines += ["", "---", "", "## ✅ Конфликты стейкхолдеров", "", "Конфликтов не обнаружено.", ""]

    # Dependency violations
    if violations:
        lines += [
            "---",
            "",
            f"## ⚠️ Нарушения зависимостей ({len(violations)} шт.)",
            "",
            "Логические противоречия: требование с высоким приоритетом зависит от низкоприоритетного.",
            "",
        ]
        for v in violations:
            lines.append(f"- `{v['req_id']}` (**{v['req_priority']}**) зависит от "
                         f"`{v['depends_on']}` (**{v['dep_priority']}**)")
        lines += [
            "",
            "Варианты: поднять зависимость / понизить требование / декомпозировать.",
            "Зафиксируйте решение через `resolve_conflict`.",
            "",
        ]

    # Нестабильные в Must
    if volatile_must:
        lines += [
            "---",
            "",
            "## 🟡 Нестабильные требования в Must",
            "",
        ]
        for item in volatile_must:
            icon = "🔴" if item["flag"] == "critical" else "🟡"
            lines.append(f"- {icon} `{item['req_id']}` (версия {item['version']}) — риск переделок")
        lines.append("")

    lines += [
        "---",
        "",
        "## Следующие шаги",
        "",
    ]
    has_open = conflicts or violations
    if has_open:
        lines.append("1. Разрешить конфликты → `resolve_conflict`")
        lines.append("2. После разрешения всех конфликтов → `save_prioritization_result`")
    else:
        lines.append("1. Все конфликты отсутствуют → можно вызывать `save_prioritization_result`")

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
    Зафиксировать решение по конфликту приоритизации.

    Параметры:
    - req_id: ID требования с конфликтом
    - conflict_type: тип конфликта
    - final_priority: итоговый приоритет после разрешения
    - rationale: обоснование решения
    - decided_by: кто принял решение (stakeholder_id или роль, например "Sponsor")
    """
    logger.info(f"5.3 resolve_conflict: {project_name}/{session_label} req={req_id}")

    prio_data = _load_prio(project_name)
    session = _find_session(prio_data["sessions"], session_label)
    if not session:
        return f"❌ Сессия '{session_label}' не найдена."

    # Update the aggregated value.
    # TimeBoxing is different in kind: for the other three methods `priority` IS the
    # decision, but here it is the OUTCOME of filling the box. So the decision is
    # recorded as the requirement's value and the box is filled again — otherwise a
    # resolved requirement could read "✂️ cut" and "Must" on the same row, and a
    # priority that the capacity does not support would reach the 5.1 graph.
    if session.get("status") == "closed":
        return (f"❌ Сессия '{session_label}' уже закрыта, и её результат записан в "
                f"репозиторий 5.1. Записанное сейчас решение попало бы в "
                f"перегенерированный отчёт, но до графа не дошло бы. Чтобы пересмотреть "
                f"приоритеты, откройте новую сессию.")

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
                f"\n⚠️ У `{req_id}` в этой сессии нет оценки стоимости, поэтому коробку "
                f"под него пересобрать не удалось — решение записано, но вступит в силу "
                f"только после того, как оценка будет добавлена и `run_aggregation` "
                f"вызван снова.")
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

    # Помечаем конфликт как разрешённый
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
        # Добавляем как отдельную запись (ручное разрешение)
        session["conflicts"].append({
            "req_id": req_id,
            "conflict_type": conflict_type,
            "resolved": True,
            "resolution": resolution,
        })

    _save_prio(project_name, prio_data)

    # Проверяем остались ли нерешённые конфликты
    open_conflicts = [c for c in session["conflicts"] if not c.get("resolved")]
    open_violations = [v for v in session["dependency_violations"] if not v.get("resolved")]

    lines = [
        f"✅ Конфликт по `{req_id}` разрешён",
        "",
        f"**Итоговый приоритет:** {final_priority}  ",
        f"**Принял решение:** {decided_by}  ",
        f"**Обоснование:** {rationale}",
        "",
    ]
    if timebox_note:
        lines += [timebox_note, ""]

    if open_conflicts or open_violations:
        total_open = len(open_conflicts) + len(open_violations)
        lines.append(f"⚠️ Остаётся **{total_open}** нерешённых конфликтов/violations.")
        lines.append("Продолжайте вызывать `resolve_conflict` для каждого.")
    else:
        lines.append("✅ Все конфликты разрешены. Можно вызывать `save_prioritization_result`.")

    return "\n".join(lines)


@mcp.tool()
@guard_artifact_errors
def save_prioritization_result(
    project_name: str,
    session_label: str,
) -> str:
    """
    Финализировать сессию приоритизации.

    Действия:
    1. Проверяет что все конфликты разрешены
    2. Обновляет поле priority в репозитории 5.1
    3. Закрывает сессию в {project}_prioritization.json
    4. Сохраняет Markdown-отчёт

    Предупреждает если остались нерешённые конфликты (но позволяет сохранить).
    """
    logger.info(f"5.3 save_prioritization_result: {project_name}/{session_label}")

    prio_data = _load_prio(project_name)
    session = _find_session(prio_data["sessions"], session_label)
    if not session:
        return f"❌ Сессия '{session_label}' не найдена."

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
            f"⚠️ Эта сессия уже была завершена "
            f"{session.get('closed_at', 'ранее')}. Отчёт ниже был "
            f"перегенерирован из сохранённого результата; в репозиторий 5.1 повторно "
            f"НИЧЕГО не писалось. Чтобы изменить приоритеты, откройте новую сессию.")

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

    # An empty aggregate means there is no result to write and nothing to finalise.
    # Closing anyway cost the analyst the session — add_stakeholder_scores,
    # run_aggregation and resolve_conflict all refuse on a closed one — in exchange
    # for a document that recorded nothing. The production path in is one keystroke
    # wide: mistype the score field, every score is rejected (finding V-4), then
    # finalise.
    #
    # "Don't block — warn": the report is still produced, and it says plainly that
    # nothing was written. The session stays open so the work can continue.
    #
    # WHAT the report says, though, is a different question from what it DOES, and
    # this one condition used to answer both. An empty aggregate is "nothing was
    # WRITTEN"; it is not "nothing was COLLECTED". Scores live in `stakeholder_scores`
    # and reach `aggregated` only when `run_aggregation` is called, so a skipped
    # aggregation — an ordinary omission — was reported as an absence of scores, two
    # sections above the document's own "Stakeholders: N", with advice to enter them
    # again. The decision below is unchanged; only the diagnosis is now told apart.
    nothing_aggregated = not session.get("aggregated")
    scores_collected = bool(session.get("stakeholder_scores"))

    if not already_closed and not nothing_aggregated:
        _save_repo(project_name, repo)

    # Close the session
    if not nothing_aggregated:
        session["status"] = "closed"
        session["closed_at"] = str(date.today())
    _save_prio(project_name, prio_data)

    # Markdown отчёт
    lines = [
        f"<!-- BABOK 5.3 — Prioritize Requirements (результат), "
        f"Проект: {project_name}, Сессия: {session_label}, Дата: {date.today()} -->",
        "",
        f"# Результаты приоритизации: {session_label}",
        f"**Проект:** {project_name}  ",
        f"**Метод:** {session['method']}  ",
        f"**Дата:** {date.today()}  ",
        f"**Обновлено требований:** {updated_count}",
        "",
    ]
    if refinalise_note:
        lines += [refinalise_note, ""]

    if nothing_aggregated:
        # Said only where it is true: a session already closed on disk does not
        # "remain open" because this document says so.
        still_open = "" if already_closed else " Сессия остаётся открытой."
        if scores_collected:
            lines += [
                "⚠️ **Собранные здесь оценки так и не были агрегированы** — "
                "`run_aggregation` для этой сессии не вызывался, поэтому агрегат пуст, "
                "в репозиторий 5.1 ничего не записано, а цифры ниже ничего не утверждают "
                "о бэклоге." + still_open,
                "",
            ]
        else:
            lines += [
                "⚠️ **В этой сессии не собрано ни одной оценки** — агрегат пуст, поэтому "
                "в репозиторий 5.1 ничего не записано, а цифры ниже ничего не утверждают "
                "о бэклоге." + still_open,
                "",
            ]

    # BABOK 3.3 element .3 reconciled against what actually happened. Appended BELOW
    # the header block on purpose: the two `lines.insert(7, ...)` calls further down
    # address a FIXED index, so a block added above the header would swallow the
    # "scored a typo" warning into this section instead of the header.
    lines += _planned_approach_block(project_name, session)

    lines += [
        "---",
        "",
        "## Итоговые приоритеты",
        "",
    ]
    if not_found_ids:
        listed = ", ".join(f"`{r}`" for r in sorted(not_found_ids))
        lines.insert(7, "")
        lines.insert(
            7,
            f"⚠️ **Оценённых id, которым не соответствует ни один узел репозитория: "
            f"{len(not_found_ids)} — они НЕ сохранены:** {listed}. Проверьте опечатки "
            f"(например, `FR-01` вместо `FR-001`) и оцените заново, иначе приоритет "
            f"потеряется.",
        )

    if not_req_ids:
        listed_nr = ", ".join(f"`{r}`" for r in sorted(not_req_ids))
        lines.insert(7, "")
        lines.insert(
            7,
            f"⚠️ **Оценённых id, которые НЕ являются требованиями: {len(not_req_ids)}** "
            f"(бизнес-цель / риск / запрос на изменение / границы решения) — приоритет им "
            f"НЕ назначался: {listed_nr}.",
        )

    for prio_label in ["Must", "Should", "Could", "Won't"]:
        reqs = priority_summary.get(prio_label, [])
        icon = {"Must": "🔴", "Should": "🟠", "Could": "🟡", "Won't": "🟢"}[prio_label]
        lines.append(f"### {icon} {prio_label} ({len(reqs)} шт.)")
        if reqs:
            for rid in reqs:
                lines.append(f"- `{rid}`")
        else:
            lines.append("*(нет требований)*")
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
                "⚠️ Коробка не построена: `run_aggregation` для этой сессии не вызывался, "
                "поэтому ни одно требование не взвешивалось против ёмкости. Цифры ниже "
                "ничего не утверждают о бэклоге.",
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
        "## Статистика сессии",
        "",
        f"- Стейкхолдеров: {len(session['stakeholder_scores'])}",
        f"- Конфликтов: {total_conflicts} (разрешено: {resolved_conflicts})",
        f"- Нарушений зависимостей: {total_violations} (разрешено: {resolved_violations})",
        "",
    ]

    if open_conflicts or open_violations:
        lines += [
            "---",
            "",
            "## ⚠️ Нерешённые конфликты",
            "",
            f"Не разрешено: конфликтов — {len(open_conflicts)}, нарушений — {len(open_violations)}.",
            # This used to send the BA to `resolve_conflict`, which refuses on a
            # closed session — the document instructed a step the platform rejects.
            "Результат сохранён вместе с ними, и сессия теперь закрыта. Чтобы их "
            "уладить, откройте новую сессию приоритизации: решение, записанное в "
            "закрытую, попало бы в перегенерированный отчёт, но до графа требований "
            "не дошло бы.",
            "",
        ]

    # The next-steps block is built from what actually happened. As a fixed text it
    # advised handing on results that do not exist — the sharpest case being a session
    # with no scores at all, where the same document read "Requirements updated: 0"
    # and "Priorities have been written to the 5.1 repository".
    lines += ["---", "", "## Следующие шаги", ""]
    if nothing_aggregated:
        if scores_collected:
            lines += [
                "- ⚠️ **Собранные здесь оценки так и не были агрегированы, поэтому в "
                "репозиторий 5.1 не записан ни один приоритет.** Ничто выше не является "
                "утверждением о бэклоге.",
            ]
        else:
            lines += [
                "- ⚠️ **В этой сессии не собрано ни одной оценки, поэтому в репозиторий "
                "5.1 не записан ни один приоритет.** Ничто выше не является утверждением "
                "о бэклоге.",
            ]
        # The step to take next depends on the state the session is actually IN.
        # A closed one cannot be continued at all: `add_stakeholder_scores` and
        # `run_aggregation` both refuse on it, so naming either of them here would be
        # advice the platform rejects the moment it is followed.
        if already_closed:
            lines.append(
                "- Сессия ЗАКРЫТА и продолжена быть не может: `add_stakeholder_scores` и "
                "`run_aggregation` на закрытой сессии отказывают. Чтобы записать "
                "приоритеты, откройте новую сессию приоритизации.")
        elif scores_collected:
            lines.append(
                "- Сессия ещё ОТКРЫТА. Оценки в ней уже есть: запустите "
                "`run_aggregation` и завершите сессию снова.")
        else:
            lines.append(
                "- Сессия ещё ОТКРЫТА. Добавьте оценки через `add_stakeholder_scores` "
                "(поле называется `score`), затем `run_aggregation`, затем завершите снова.")
    elif already_closed:
        lines += [
            "- Этот отчёт перегенерирован из сохранённого результата — в репозиторий 5.1 "
            "повторно ничего не писалось.",
            "- Результаты доступны для 6.3 (Assess Risks)",
        ]
    else:
        lines += [
            f"- Приоритеты записаны в репозиторий 5.1 ({updated_count} "
            f"{plural_ru(updated_count, 'требование', 'требования', 'требований')})",
            "- Результаты доступны для 6.3 (Assess Risks)",
            "- Если контекст изменится — проведите новую сессию приоритизации",
        ]

    content = "\n".join(lines)
    saved = save_artifact(content, prefix=f"5_3_prioritization_{project_name.lower().replace(' ', '_')}", project_id=project_name)
    return content + saved


if __name__ == "__main__":
    mcp.run()
