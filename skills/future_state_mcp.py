"""
BABOK 6.2 — Define Future State
MCP tools for defining the organization's future state.

Tools:
  - scope_future_state                — analysis scope: initiative type, depth, elements
  - capture_future_state_element      — capture one of the 8 future-state elements
  - define_goals_and_objectives       — SMART goals with KPIs + registration in 5.1 as business_goal
  - capture_constraints               — constraints register by category
  - run_gap_analysis                  — gap analysis current vs. future (direct input for 6.4)
  - assess_potential_value            — qualitative assessment of potential value (context for 7.6)
  - check_future_state_completeness   — coverage check before finalization
  - save_future_state                 — finalization + Markdown report + push to 7.3

Storage:
  - {project}_future_state_scope.json   — analysis scope (contract)
  - {project}_future_state.json         — elements, goals, constraints, value, status
  - {project}_future_state_goals.json   — goals and KPIs (+ BG registration in 5.1)
  - {project}_gap_analysis.json         — gap analysis results for 6.4
  - {project}_future_state_analysis.md  — human-readable report (via save_artifact)

Integration:
  In: 6.1 data (optional) — business_needs, current_state, current_state_scope
  Out: BG nodes in the 5.1 repository, gap_analysis for 6.4, data for 7.3 set_business_context

ADR-060: link between 6.2 and 6.1 is modular (6.1 is optional; auto-imported when present)
ADR-061: 6.2 elements are the same 8 domains as in 6.1 + separate tools for goals and constraints
ADR-062: business_goal as a node type in the 5.1 repository
ADR-063: gap analysis as a separate explicit tool
ADR-064: potential value in 6.2 is qualitative and structured
ADR-065: from_strategy_project_id — single parameter for 7.3
ADR-066: check_future_state_completeness — separate tool following the 6.1 pattern

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
from datetime import date, datetime
from typing import Literal, Optional
from mcp.server.fastmcp import FastMCP
from skills.common import (save_artifact, logger, DATA_DIR, data_path,
                           normalize_project_id, pick_field,
                           unrecognized_records_error)

mcp = FastMCP("BABOK_FutureState")

SCOPE_FILENAME = "future_state_scope.json"
STATE_FILENAME = "future_state.json"
GOALS_FILENAME = "future_state_goals.json"
GAP_FILENAME = "gap_analysis.json"
REPO_FILENAME = "traceability_repo.json"

# 6.1 files (optional source)
CS_SCOPE_FILENAME = "current_state_scope.json"
CS_STATE_FILENAME = "current_state.json"
CS_NEEDS_FILENAME = "business_needs.json"

VALID_ELEMENTS = [
    "business_needs", "org_structure", "capabilities",
    "technology", "policies", "architecture", "assets", "external"
]

ELEMENT_LABELS = {
    "business_needs": "Business Needs",
    "org_structure": "Organizational Structure and Culture",
    "capabilities": "Capabilities and Processes",
    "technology": "Technology and Infrastructure",
    "policies": "Policies",
    "architecture": "Business Architecture",
    "assets": "Internal Assets",
    "external": "External Influencers",
}

DEFAULT_ELEMENTS_BY_TYPE = {
    "process_improvement": ["business_needs", "capabilities", "technology", "policies"],
    "new_system": ["business_needs", "capabilities", "technology", "architecture"],
    "regulatory": ["business_needs", "policies", "technology", "external"],
    "cost_reduction": ["business_needs", "capabilities", "assets", "external"],
    "market_opportunity": VALID_ELEMENTS,
    "other": ["business_needs", "capabilities", "technology"],
}


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _safe(project_id: str) -> str:
    return normalize_project_id(project_id)


def _scope_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{SCOPE_FILENAME}")


def _state_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{STATE_FILENAME}")


def _goals_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{GOALS_FILENAME}")


def _gap_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{GAP_FILENAME}")


def _repo_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{REPO_FILENAME}")


def _cs_scope_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{CS_SCOPE_FILENAME}")


def _cs_state_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{CS_STATE_FILENAME}")


def _cs_needs_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{CS_NEEDS_FILENAME}")


def _load_json(path: str) -> Optional[dict]:
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _save_json(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _load_scope(project_id: str) -> Optional[dict]:
    return _load_json(_scope_path(project_id))


def _save_scope(data: dict) -> str:
    path = _scope_path(data["project_id"])
    _save_json(path, data)
    logger.info(f"Future state scope saved: {path}")
    return path


def _load_state(project_id: str) -> dict:
    data = _load_json(_state_path(project_id))
    if data:
        return data
    return {
        "project_id": project_id,
        "scope_ref": f"{_safe(project_id)}_{SCOPE_FILENAME}",
        "elements": {},
        "constraints": [],
        "potential_value": None,
        "gap_analysis_done": False,
        "created": str(date.today()),
        "updated": str(date.today()),
    }


def _save_state(data: dict) -> str:
    path = _state_path(data["project_id"])
    data["updated"] = str(date.today())
    _save_json(path, data)
    logger.info(f"Future state data saved: {path}")
    return path


def _load_goals(project_id: str) -> dict:
    data = _load_json(_goals_path(project_id))
    if data:
        return data
    return {
        "project_id": project_id,
        "goals": [],
        "created": str(date.today()),
        "updated": str(date.today()),
    }


def _save_goals(data: dict) -> str:
    path = _goals_path(data["project_id"])
    data["updated"] = str(date.today())
    _save_json(path, data)
    logger.info(f"Future state goals saved: {path}")
    return path


def _load_gap(project_id: str) -> Optional[dict]:
    return _load_json(_gap_path(project_id))


def _save_gap(data: dict) -> str:
    path = _gap_path(data["project_id"])
    _save_json(path, data)
    logger.info(f"Gap analysis saved: {path}")
    return path


def _load_repo(project_id: str) -> Optional[dict]:
    return _load_json(_repo_path(project_id))


def _save_repo(repo: dict) -> None:
    path = _repo_path(repo["project"])
    repo["updated"] = str(date.today())
    _save_json(path, repo)
    logger.info(f"Traceability repository updated from 6.2: {path}")


def _next_goal_id(goals_data: dict) -> str:
    existing = [g["id"] for g in goals_data["goals"] if g["id"].startswith("BG-")]
    if not existing:
        return "BG-001"
    nums = [int(g.split("-")[1]) for g in existing if g.split("-")[1].isdigit()]
    return f"BG-{(max(nums) + 1):03d}" if nums else "BG-001"


def _validate_smart(goal_title: str, description: str, objectives: list) -> list:
    """Checks SMART criteria for a goal. Returns a list of issues."""
    issues = []
    if len(goal_title.strip()) < 10:
        issues.append("S (Specific): the goal title is too short — add more specifics")
    if not objectives:
        issues.append("M (Measurable): no target metric defined — add a KPI")
    else:
        for obj in objectives:
            if not obj.get("target"):
                issues.append(f"M (Measurable): metric '{obj.get('title', '?')}' has no target value")
            if not obj.get("baseline"):
                issues.append(f"M (Measurable): metric '{obj.get('title', '?')}' has no baseline (current value)")
            if not obj.get("deadline"):
                issues.append(f"T (Time-bound): metric '{obj.get('title', '?')}' has no deadline")
    return issues


# ---------------------------------------------------------------------------
# 6.2.1 — Scoping the future-state analysis
# ---------------------------------------------------------------------------

@mcp.tool()
def scope_future_state(
    project_id: str,
    initiative_type: Literal[
        "process_improvement", "new_system", "regulatory",
        "cost_reduction", "market_opportunity", "other"
    ],
    analysis_depth: Literal["light", "standard", "deep"],
    known_goals: str = "",
    elements_in_scope: str = "",
) -> str:
    """
    BABOK 6.2 — First step: scope the future-state analysis.
    Mirrors scope_current_state (6.1) — an explicit contract (ADR-058/ADR-060).
    If 6.1 data exists, it is automatically read in as context.

    Args:
        project_id:        Project identifier (the same one used in 6.1).
        initiative_type:   Initiative type:
                           - process_improvement — process improvement
                           - new_system          — new system implementation
                           - regulatory          — regulatory compliance
                           - cost_reduction      — cost reduction
                           - market_opportunity  — market opportunity
                           - other               — other
        analysis_depth:    Analysis depth:
                           - light    — 3-4 elements, a strategic snapshot
                           - standard — 5-6 elements, most projects
                           - deep     — all 8 elements, strategic initiatives
        known_goals:       Optional — known goals from the sponsor (free text).
        elements_in_scope: Optional — override the element list manually.
                           JSON list of keys:
                           '[\"business_needs\",\"capabilities\",\"technology\"]'
                           Valid keys: business_needs | org_structure | capabilities |
                           technology | policies | architecture | assets | external

    Returns:
        Scope confirmation + context from 6.1 (if available) + next steps.
    """
    logger.info(f"scope_future_state: {project_id}, type={initiative_type}, depth={analysis_depth}")

    # Determine the elements in scope
    if elements_in_scope.strip():
        try:
            custom_elements = json.loads(elements_in_scope)
            invalid = [e for e in custom_elements if e not in VALID_ELEMENTS]
            if invalid:
                return (
                    f"❌ Unknown elements: {invalid}\n"
                    f"Allowed: {VALID_ELEMENTS}"
                )
            chosen_elements = custom_elements
            elements_source = "specified manually"
        except json.JSONDecodeError as e:
            return f"❌ Error parsing elements_in_scope: {e}"
    else:
        base_elements = DEFAULT_ELEMENTS_BY_TYPE.get(initiative_type, ["business_needs", "capabilities"])
        if analysis_depth == "deep":
            chosen_elements = VALID_ELEMENTS
        elif analysis_depth == "light":
            chosen_elements = base_elements[:3]
        else:
            chosen_elements = base_elements
        elements_source = f"recommended for {initiative_type}/{analysis_depth}"

    # Read 6.1 data if available (ADR-060)
    cs_scope = _load_json(_cs_scope_path(project_id))
    cs_needs = _load_json(_cs_needs_path(project_id))
    has_current_state = cs_scope is not None

    existing = _load_scope(project_id)
    is_update = existing is not None

    scope_data = {
        "project_id": project_id,
        "initiative_type": initiative_type,
        "analysis_depth": analysis_depth,
        "known_goals": known_goals,
        "elements_in_scope": chosen_elements,
        "has_current_state_data": has_current_state,
        "created": existing["created"] if existing else str(date.today()),
        "updated": str(date.today()),
    }

    _save_scope(scope_data)

    type_labels = {
        "process_improvement": "Process Improvement",
        "new_system": "New System Implementation",
        "regulatory": "Regulatory Compliance",
        "cost_reduction": "Cost Reduction",
        "market_opportunity": "Market Opportunity",
        "other": "Other",
    }
    depth_labels = {
        "light": "Light (3-4 elements, a quick pass)",
        "standard": "Standard (5-6 elements)",
        "deep": "Deep (all 8 elements)",
    }

    lines = [
        f"{'⚠️ Scope UPDATED' if is_update else '✅ Future-state analysis scope defined'} — **{project_id}**",
        "",
        f"**Initiative type:** {type_labels.get(initiative_type, initiative_type)}",
        f"**Analysis depth:** {depth_labels.get(analysis_depth, analysis_depth)}",
        f"**Date:** {date.today()}",
        "",
        f"## Elements in scope ({len(chosen_elements)} of 8) — {elements_source}",
        "",
    ]

    for i, elem in enumerate(chosen_elements, 1):
        label = ELEMENT_LABELS.get(elem, elem)
        lines.append(f"{i}. **{elem}** — {label}")

    not_in_scope = [e for e in VALID_ELEMENTS if e not in chosen_elements]
    if not_in_scope:
        lines += ["", "### Elements out of scope:"]
        for elem in not_in_scope:
            lines.append(f"- ~~{elem}~~ — {ELEMENT_LABELS.get(elem, elem)}")

    # Context from 6.1
    if has_current_state:
        bn_count = len(cs_needs.get("needs", [])) if cs_needs else 0
        cs_elements = cs_scope.get("elements_in_scope", [])
        lines += [
            "",
            "## ✅ Data from 6.1 found",
            "",
            f"- Current-state elements: {len(cs_elements)}",
            f"- Business needs: {bn_count}",
            "",
            "When filling in elements (`capture_future_state_element`) the system will show",
            "the current state alongside the future one — use it as a reference point.",
            "Goals (`define_goals_and_objectives`) can be linked to existing BN-xxx.",
        ]
    else:
        lines += [
            "",
            "ℹ️ No 6.1 data found — the gap analysis will run without a current-state baseline.",
            "If 6.1 has not been performed yet, it's recommended to start there.",
        ]

    if known_goals:
        lines += [
            "",
            "## Known goals",
            "",
            known_goals,
        ]

    lines += [
        "",
        "---",
        "",
        "## Next steps",
        "",
        "1. `capture_future_state_element` — fill in each element from the scope",
        "2. `define_goals_and_objectives` — capture SMART goals with KPIs",
        "3. `capture_constraints` — capture constraints",
        "4. `run_gap_analysis` — compare current and future state",
        "5. `assess_potential_value` — assess potential value",
        "6. `check_future_state_completeness` — check readiness",
        "7. `save_future_state` — finalize the analysis",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 6.2.2 — Iterative data capture for future-state elements
# ---------------------------------------------------------------------------

@mcp.tool()
def capture_future_state_element(
    project_id: str,
    element: Literal[
        "business_needs", "org_structure", "capabilities",
        "technology", "policies", "architecture", "assets", "external"
    ],
    description: str,
    target_metrics: str = "{}",
    linked_business_needs: str = "[]",
    sources: str = '["elicitation"]',
    notes: str = "",
) -> str:
    """
    BABOK 6.2 — Capture one future-state element (ADR-061).
    Iterative pattern: called once for each element.
    When 6.1 data exists, shows the current state alongside it ("past next to future").

    Args:
        project_id:             Project identifier.
        element:                One of the 8 elements:
                                business_needs | org_structure | capabilities | technology |
                                policies | architecture | assets | external
        description:            Description of the element's target state ("how it should be").
                                Outcome-oriented, not implementation-process-oriented.
        target_metrics:         Target measurable metrics for this element.
                                JSON object: '{\"processing_time\": \"2 hours\", \"error_rate\": \"<2%\"}'
        linked_business_needs:  List of BN-xxx from 6.1 that this element addresses.
                                JSON list of strings: '[\"BN-001\",\"BN-002\"]'
        sources:                Where the data comes from: JSON list of sources.
                                Allowed: elicitation | document | workshop | interview | other
        notes:                  Free-form notes (assumptions, questions, open items).

    Returns:
        Capture confirmation + current state from 6.1 (if available) + progress.
    """
    logger.info(f"capture_future_state_element: {project_id}, element={element}")

    if not description.strip():
        return "❌ description cannot be empty — describe the element's target state."

    try:
        target_dict = json.loads(target_metrics) if target_metrics.strip() else {}
        if not isinstance(target_dict, dict):
            return "❌ target_metrics must be a JSON object: '{\"metric\": \"value\"}'"
    except json.JSONDecodeError as e:
        return f"❌ Error parsing target_metrics: {e}"

    try:
        bn_list = json.loads(linked_business_needs) if linked_business_needs.strip() else []
        if not isinstance(bn_list, list):
            return "❌ linked_business_needs must be a JSON list of strings"
    except json.JSONDecodeError as e:
        return f"❌ Error parsing linked_business_needs: {e}"

    try:
        sources_list = json.loads(sources) if sources.strip() else ["elicitation"]
        if not isinstance(sources_list, list):
            return "❌ sources must be a JSON list"
    except json.JSONDecodeError as e:
        return f"❌ Error parsing sources: {e}"

    # Check the scope
    scope = _load_scope(project_id)
    scope_warning = ""
    if scope and element not in scope.get("elements_in_scope", []):
        scope_warning = (
            f"\n⚠️ Element `{element}` is not part of the current scope. "
            f"Add it by calling `scope_future_state` again."
        )

    # Load and update the state
    state = _load_state(project_id)
    is_update = element in state["elements"]

    state["elements"][element] = {
        "description": description,
        "target_metrics": target_dict,
        "linked_business_needs": bn_list,
        "sources": sources_list,
        "notes": notes,
        "draft": False,
        "last_updated": str(date.today()),
    }
    _save_state(state)

    label = ELEMENT_LABELS.get(element, element)
    action = "UPDATED" if is_update else "saved"

    lines = [
        f"✅ Future-state element **{label}** (`{element}`) {action}",
        "",
        f"**Description:** {description[:200]}{'...' if len(description) > 200 else ''}",
    ]

    if target_dict:
        lines += ["", "**Target metrics:**"]
        for k, v in target_dict.items():
            lines.append(f"- {k}: {v}")

    if bn_list:
        lines += ["", f"**Linked business needs:** {', '.join(bn_list)}"]

    lines += ["", f"**Sources:** {', '.join(sources_list)}"]

    if scope_warning:
        lines.append(scope_warning)

    # Current state from 6.1 (UX pattern: "past next to future")
    cs_state = _load_json(_cs_state_path(project_id))
    if cs_state and element in cs_state.get("elements", {}):
        cs_elem = cs_state["elements"][element]
        cs_desc = cs_elem.get("description", "")
        if cs_desc:
            lines += [
                "",
                "---",
                "",
                f"### 🔍 For comparison — current state (`{element}` from 6.1):",
                "",
                cs_desc[:300] + ("..." if len(cs_desc) > 300 else ""),
            ]
            cs_metrics = cs_elem.get("metrics", {})
            if cs_metrics:
                lines += ["", "**Current metrics:**"]
                for k, v in cs_metrics.items():
                    lines.append(f"- {k}: {v}")
            lines += ["", "---"]

    # Progress against the scope
    if scope:
        elements_in_scope = scope.get("elements_in_scope", [])
        filled = [e for e in elements_in_scope if e in state["elements"] and not state["elements"][e].get("draft", True)]
        remaining = [e for e in elements_in_scope if e not in state["elements"] or state["elements"][e].get("draft", True)]

        lines += [
            "",
            f"## Progress: {len(filled)}/{len(elements_in_scope)} elements",
            "",
        ]
        for e in elements_in_scope:
            elem_label = ELEMENT_LABELS.get(e, e)
            status = "✅" if e in filled else "⬜"
            lines.append(f"{status} {elem_label}")

        if remaining:
            lines += ["", f"**Next element:** `{remaining[0]}`"]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 6.2.3 — Business goals and KPIs
# ---------------------------------------------------------------------------

@mcp.tool()
def define_goals_and_objectives(
    project_id: str,
    goal_title: str,
    description: str,
    objectives_json: str,
    linked_business_needs: str = "[]",
    register_in_traceability: bool = True,
) -> str:
    """
    BABOK 6.2 — Capture a business goal with KPIs. SMART validation (ADR-062).
    Registers the goal as a business_goal node in the 5.1 repository.
    Establishes traceability BN → derives → BG.

    Args:
        project_id:              Project identifier.
        goal_title:              Short goal title (up to 100 characters).
        description:             Goal description — what will be achieved and why it matters.
        objectives_json:         List of target metrics (KPIs) — JSON list of objects.
                                 Each object:
                                 {
                                   \"title\": \"Reduce request processing time\",
                                   \"metric\": \"Processing time (hours)\",
                                   \"baseline\": \"8 hours (Q1 2025)\",
                                   \"target\": \"2 hours\",
                                   \"deadline\": \"2025-12-31\"
                                 }
        linked_business_needs:   List of BN-xxx from 6.1 that the goal is linked to.
                                 JSON list of strings: '[\"BN-001\",\"BN-002\"]'
        register_in_traceability: If True — create a business_goal node in the 5.1 repository.
                                 Default: True. Disable if the 5.1 repository has not been created.

    Returns:
        Goal card with ID + SMART notes + 5.1 registration status.
    """
    logger.info(f"define_goals_and_objectives: {project_id}, title='{goal_title[:50]}'")

    if not goal_title.strip():
        return "❌ goal_title cannot be empty."
    if not description.strip():
        return "❌ description cannot be empty."

    try:
        objectives = json.loads(objectives_json) if objectives_json.strip() else []
        if not isinstance(objectives, list):
            return "❌ objectives_json must be a JSON list of objects."
    except json.JSONDecodeError as e:
        return f"❌ Error parsing objectives_json: {e}"

    try:
        bn_list = json.loads(linked_business_needs) if linked_business_needs.strip() else []
        if not isinstance(bn_list, list):
            return "❌ linked_business_needs must be a JSON list of strings."
    except json.JSONDecodeError as e:
        return f"❌ Error parsing linked_business_needs: {e}"

    # Normalise the objective spellings BEFORE the SMART validation reads them.
    # `objective` and `name` are the near-misses an LLM writes for `title`. Reading only
    # `title` rendered "### 1. —" into the goal card AND made the SMART validator emit
    # "metric '?' has no baseline" — a quality finding manufactured out of a field the
    # tool had failed to read, which is worse than the missing heading.
    OBJECTIVE_NAME_KEYS = ("title", "objective", "name")
    objectives = [
        {
            **o,
            "title": pick_field(o, *OBJECTIVE_NAME_KEYS),
            "metric": pick_field(o, "metric", "kpi", "measure"),
        }
        for o in objectives if isinstance(o, dict)
    ] + [o for o in objectives if not isinstance(o, dict)]
    if objectives and not any(
            isinstance(o, dict) and o.get("title") for o in objectives):
        return unrecognized_records_error(
            "objectives_json", OBJECTIVE_NAME_KEYS,
            '[{"title": "Processing time", "metric": "hours", "baseline": "8", '
            '"target": "2", "deadline": "2026-12-31"}]')

    # SMART validation
    smart_issues = _validate_smart(goal_title, description, objectives)

    goals_data = _load_goals(project_id)
    goal_id = _next_goal_id(goals_data)

    goal_record = {
        "id": goal_id,
        "goal_title": goal_title,
        "description": description,
        "objectives": objectives,
        "linked_business_needs": bn_list,
        "smart_validated": len(smart_issues) == 0,
        "created": str(date.today()),
    }
    goals_data["goals"].append(goal_record)
    _save_goals(goals_data)

    # Registration in the 5.1 repository (ADR-062)
    traceability_status = ""
    if register_in_traceability:
        repo = _load_repo(project_id)
        if repo is None:
            traceability_status = (
                "\n\n⚠️ The 5.1 traceability repository was not found.\n"
                "Create it via `init_traceability_repo` (5.1); "
                f"the `{goal_id}` node of type `business_goal` will then be added automatically."
            )
        else:
            existing_ids = {r["id"] for r in repo["requirements"]}
            if goal_id not in existing_ids:
                repo["requirements"].append({
                    "id": goal_id,
                    "type": "business_goal",
                    "title": goal_title,
                    "version": "1.0",
                    "status": "confirmed",
                    "source_artifact": f"6.2/{_safe(project_id)}_future_state_goals.json",
                    "added": str(date.today()),
                })
                # Add BN → BG links
                for bn_id in bn_list:
                    repo["links"].append({
                        "from": goal_id,
                        "to": bn_id,
                        "relation": "derives",
                        "rationale": f"Business goal derives from business need {bn_id}",
                        "added": str(date.today()),
                    })
                repo["history"].append({
                    "action": "node_added",
                    "id": goal_id,
                    "type": "business_goal",
                    "source": "6.2 define_goals_and_objectives",
                    "date": str(date.today()),
                })
                _save_repo(repo)
                trace_chain = " → ".join([f"{bn}" for bn in bn_list]) + f" → {goal_id}" if bn_list else goal_id
                traceability_status = (
                    f"\n\n✅ Node `{goal_id}` (business_goal) registered in the 5.1 repository."
                    + (f"\n   Traceability: {trace_chain}" if bn_list else "")
                )
            else:
                traceability_status = f"\n\nℹ️ Node `{goal_id}` already exists in the 5.1 repository."

    lines = [
        f"✅ Business goal captured: **{goal_id}**",
        "",
        f"**{goal_title}**",
        "",
        f"**Date:** {date.today()}",
        "",
        "## Description",
        "",
        description,
    ]

    if objectives:
        lines += ["", "## Target metrics (KPIs)", ""]
        for i, obj in enumerate(objectives, 1):
            lines += [
                f"### {i}. {obj.get('title', '—')}",
                f"- **Metric:** {obj.get('metric', '—')}",
                f"- **Baseline:** {obj.get('baseline', '—')}",
                f"- **Target:** {obj.get('target', '—')}",
                f"- **Deadline:** {obj.get('deadline', '—')}",
                "",
            ]

    if bn_list:
        lines += [f"**Linked business needs:** {', '.join(bn_list)}"]

    # SMART notes
    if smart_issues:
        lines += [
            "",
            "## ⚠️ SMART notes",
            "",
            "> The goal has been saved. Address these notes to meet SMART criteria:",
            "",
        ]
        for issue in smart_issues:
            lines.append(f"- {issue}")
    else:
        lines += ["", "✅ SMART criteria met."]

    total_goals = len(goals_data["goals"])
    lines += [
        "",
        "---",
        "",
        f"Total business goals in the project: **{total_goals}**",
        traceability_status,
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 6.2.4 — Constraints register
# ---------------------------------------------------------------------------

@mcp.tool()
def capture_constraints(
    project_id: str,
    constraint_title: str,
    category: Literal["budget", "time", "technology", "policy", "resources", "compliance", "other"],
    description: str,
    status: Literal["confirmed", "assumed"],
    linked_elements: str = "[]",
) -> str:
    """
    BABOK 6.2 — Capture a constraint that narrows the solution space (ADR-061).
    Constraints are checked in 7.5 when developing design options.

    Args:
        project_id:       Project identifier.
        constraint_title: Short constraint title.
        category:         Constraint category:
                          - budget     — financial limit
                          - time       — timeframe, deadlines
                          - technology — technology standards
                          - policy     — internal policies and rules
                          - resources  — team, competencies, capacity
                          - compliance — regulatory and legal requirements
                          - other      — other
        description:      Full description of the constraint and its impact.
        status:           Confirmation status:
                          - confirmed — confirmed in documentation or by an authorized person
                          - assumed   — the BA assumes the constraint exists
        linked_elements:  Future-state elements affected by the constraint.
                          JSON list of keys: '[\"technology\",\"capabilities\"]'

    Returns:
        Constraint card + the project's overall constraints register.
    """
    logger.info(f"capture_constraints: {project_id}, category={category}, title='{constraint_title[:40]}'")

    if not constraint_title.strip():
        return "❌ constraint_title cannot be empty."
    if not description.strip():
        return "❌ description cannot be empty."

    try:
        elements_list = json.loads(linked_elements) if linked_elements.strip() else []
        invalid = [e for e in elements_list if e not in VALID_ELEMENTS]
        if invalid:
            return f"❌ Unknown elements in linked_elements: {invalid}"
    except json.JSONDecodeError as e:
        return f"❌ Error parsing linked_elements: {e}"

    state = _load_state(project_id)

    # Check for a duplicate by title
    existing_titles = [c["title"] for c in state.get("constraints", [])]
    is_duplicate = constraint_title in existing_titles

    constraint_record = {
        "title": constraint_title,
        "category": category,
        "description": description,
        "status": status,
        "linked_elements": elements_list,
        "created": str(date.today()),
    }

    if is_duplicate:
        # Update the existing one
        state["constraints"] = [c for c in state["constraints"] if c["title"] != constraint_title]
    state["constraints"].append(constraint_record)
    _save_state(state)

    category_labels = {
        "budget": "Financial limit",
        "time": "Timeframe",
        "technology": "Technology standards",
        "policy": "Internal policies",
        "resources": "Resources and competencies",
        "compliance": "Regulatory requirements",
        "other": "Other",
    }

    status_icons = {"confirmed": "✅ Confirmed", "assumed": "🔶 Assumption"}

    lines = [
        f"{'⚠️ Constraint UPDATED' if is_duplicate else '✅ Constraint captured'}",
        "",
        f"**{constraint_title}**",
        f"**Category:** {category_labels.get(category, category)}  ",
        f"**Status:** {status_icons.get(status, status)}  ",
        f"**Date:** {date.today()}",
        "",
        "## Description",
        "",
        description,
    ]

    if elements_list:
        lines += ["", f"**Affected elements:** {', '.join(elements_list)}"]

    if status == "assumed":
        lines += [
            "",
            "⚠️ The constraint is marked as an assumption.",
            "It's recommended to validate it with an authorized person before starting solution design.",
        ]

    # Overall register
    all_constraints = state.get("constraints", [])
    confirmed = [c for c in all_constraints if c.get("status") == "confirmed"]
    assumed = [c for c in all_constraints if c.get("status") == "assumed"]

    lines += [
        "",
        "---",
        "",
        f"## Project constraints register: {len(all_constraints)} total",
        f"✅ Confirmed: {len(confirmed)}  |  🔶 Assumed: {len(assumed)}",
        "",
    ]
    by_cat: dict = {}
    for c in all_constraints:
        cat = c.get("category", "other")
        by_cat.setdefault(cat, []).append(c)
    for cat, items in by_cat.items():
        lines.append(f"**{category_labels.get(cat, cat)}:** {', '.join(i['title'] for i in items)}")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 6.2.5 — Gap analysis
# ---------------------------------------------------------------------------

@mcp.tool()
def run_gap_analysis(
    project_id: str,
) -> str:
    """
    BABOK 6.2 — Run a gap analysis: compare current and future state (ADR-063).
    A separate explicit tool: the BA runs it deliberately after filling in all elements.
    The result is a direct input for 6.4 (Define Change Strategy).

    For each future-state element:
    - Compares it with the current state from 6.1 (if available)
    - States the gap (gap_summary)
    - Determines the change type: new | improve | eliminate | replace
    - Assesses complexity: low | medium | high

    Args:
        project_id: Project identifier.

    Returns:
        Gap cards for every element + summary + the {project}_gap_analysis.json artifact.
    """
    logger.info(f"run_gap_analysis: {project_id}")

    state = _load_state(project_id)
    elements_data = state.get("elements", {})

    if not elements_data:
        return (
            "⚠️ No future-state data found.\n"
            "First fill in the elements via `capture_future_state_element`."
        )

    # Read 6.1 data for comparison
    cs_state = _load_json(_cs_state_path(project_id))
    cs_elements = cs_state.get("elements", {}) if cs_state else {}
    has_current_state = bool(cs_elements)

    gaps = []
    for element, fs_data in elements_data.items():
        if fs_data.get("draft"):
            continue
        cs_elem = cs_elements.get(element, {})
        current_desc = cs_elem.get("description") if cs_elem else None
        future_desc = fs_data.get("description", "")

        # Automatic classification of the change type
        if not current_desc:
            change_type = "new"
            gap_summary = f"No current state — the element is being created from scratch. Target: {future_desc[:100]}"
            complexity = "medium"
        else:
            change_type = "improve"
            gap_summary = f"Current: {current_desc[:80]}... → Target: {future_desc[:80]}..."
            # Simple complexity heuristic
            current_pain = len(cs_elem.get("pain_points", []))
            target_metrics = fs_data.get("target_metrics", {})
            if current_pain >= 3 or len(target_metrics) >= 3:
                complexity = "high"
            elif current_pain >= 1 or len(target_metrics) >= 1:
                complexity = "medium"
            else:
                complexity = "low"

        gap_record = {
            "element": element,
            "element_label": ELEMENT_LABELS.get(element, element),
            "current_description": current_desc,
            "future_description": future_desc,
            "gap_summary": gap_summary,
            "change_type": change_type,
            "complexity": complexity,
        }
        gaps.append(gap_record)

    gap_data = {
        "project_id": project_id,
        "has_current_state_baseline": has_current_state,
        "gaps": gaps,
        "created": str(date.today()),
        "updated": str(date.today()),
    }
    _save_gap(gap_data)

    # Update the flag in state
    state["gap_analysis_done"] = True
    _save_state(state)

    # Build the report
    complexity_icons = {"low": "🟢", "medium": "🟡", "high": "🔴"}
    change_labels = {
        "new": "🆕 New",
        "improve": "⬆️ Improve",
        "eliminate": "🗑️ Eliminate",
        "replace": "🔄 Replace",
    }

    lines = [
        f"✅ Gap analysis completed — **{project_id}**",
        "",
        f"**Date:** {date.today()}",
        f"**Elements analyzed:** {len(gaps)}",
        f"**Current-state baseline:** {'✅ from 6.1' if has_current_state else '⚠️ missing (gap = null → future)'}",
        "",
        "---",
        "",
    ]

    for gap in gaps:
        lines += [
            f"## {gap['element_label']} (`{gap['element']}`)",
            "",
            f"**Change type:** {change_labels.get(gap['change_type'], gap['change_type'])}  ",
            f"**Complexity:** {complexity_icons.get(gap['complexity'], '')} {gap['complexity'].capitalize()}",
            "",
        ]
        if gap["current_description"]:
            lines += [
                f"**Current state:** {gap['current_description'][:150]}{'...' if len(gap['current_description']) > 150 else ''}",
            ]
        else:
            lines.append("**Current state:** *(no 6.1 data)*")
        lines += [
            f"**Target state:** {gap['future_description'][:150]}{'...' if len(gap['future_description']) > 150 else ''}",
            "",
            f"**Gap:** {gap['gap_summary']}",
            "",
        ]

    # Summary
    by_type: dict = {}
    by_complexity: dict = {}
    for g in gaps:
        by_type[g["change_type"]] = by_type.get(g["change_type"], 0) + 1
        by_complexity[g["complexity"]] = by_complexity.get(g["complexity"], 0) + 1

    lines += [
        "---",
        "",
        "## Gap analysis summary",
        "",
        "### By change type:",
    ]
    for ct, cnt in by_type.items():
        lines.append(f"- {change_labels.get(ct, ct)}: {cnt}")
    lines += ["", "### By complexity:"]
    for cx, cnt in by_complexity.items():
        lines.append(f"- {complexity_icons.get(cx, '')} {cx.capitalize()}: {cnt}")

    lines += [
        "",
        "---",
        "",
        f"**Artifact:** `{_safe(project_id)}_{GAP_FILENAME}`",
        "",
        "**Next step:**",
        "- `assess_potential_value` — assess the potential value of the changes",
        "- In task **6.4** this gap analysis becomes the foundation for the change strategy",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 6.2.6 — Potential value
# ---------------------------------------------------------------------------

@mcp.tool()
def assess_potential_value(
    project_id: str,
    benefits_json: str,
    investment_level: Literal["low", "medium", "high", "unknown"],
    value_summary: str = "",
) -> str:
    """
    BABOK 6.2 — Preliminary qualitative assessment of potential value (ADR-064).
    No formula — a structured list of benefits. This is context for 7.6, not a replacement.

    Args:
        project_id:       Project identifier.
        benefits_json:    List of benefits. JSON list of objects:
                          [
                            {
                              \"benefit_title\": \"Reduced processing time\",
                              \"benefit_type\": \"operational\",
                              \"magnitude\": \"high\",
                              \"confidence\": \"medium\",
                              \"description\": \"Benefit description\",
                              \"linked_business_needs\": [\"BN-001\"],
                              \"linked_goals\": [\"BG-001\"]
                            }
                          ]
                          benefit_type: financial | operational | strategic | compliance
                          magnitude: high | medium | low
                          confidence: high | medium | low
        investment_level: Qualitative investment level:
                          - low     — minor changes, no development needed
                          - medium  — moderate development / procurement, 3-12 months
                          - high    — transformational project, 12+ months
                          - unknown — cannot be estimated yet
        value_summary:    Overall value statement for communicating with the sponsor.

    Returns:
        Structured potential-value card + "benefit / investment" profile.
    """
    logger.info(f"assess_potential_value: {project_id}")

    try:
        benefits = json.loads(benefits_json) if benefits_json.strip() else []
        if not isinstance(benefits, list):
            return "❌ benefits_json must be a JSON list of objects."
    except json.JSONDecodeError as e:
        return f"❌ Error parsing benefits_json: {e}"

    if not benefits:
        return "❌ benefits_json cannot be empty — add at least one benefit."

    valid_types = {"financial", "operational", "strategic", "compliance"}
    valid_magnitude = {"high", "medium", "low"}
    valid_confidence = {"high", "medium", "low"}

    for i, b in enumerate(benefits):
        if b.get("benefit_type") not in valid_types:
            return f"❌ Benefit {i+1}: benefit_type must be one of {valid_types}"
        if b.get("magnitude") not in valid_magnitude:
            return f"❌ Benefit {i+1}: magnitude must be one of {valid_magnitude}"
        if b.get("confidence") not in valid_confidence:
            return f"❌ Benefit {i+1}: confidence must be one of {valid_confidence}"

    value_data = {
        "benefits": benefits,
        "investment_level": investment_level,
        "value_summary": value_summary,
        "assessed_date": str(date.today()),
    }

    state = _load_state(project_id)
    state["potential_value"] = value_data
    _save_state(state)

    type_labels = {
        "financial": "💰 Financial",
        "operational": "⚙️ Operational",
        "strategic": "🎯 Strategic",
        "compliance": "📋 Compliance",
    }
    magnitude_icons = {"high": "🔺 High", "medium": "▶️ Medium", "low": "🔻 Low"}
    confidence_icons = {"high": "✅ High", "medium": "🟡 Medium", "low": "⚠️ Low"}
    investment_labels = {
        "low": "Low (no significant development)",
        "medium": "Medium (moderate development/procurement)",
        "high": "High (transformational project)",
        "unknown": "Unknown (needs clarification)",
    }

    lines = [
        f"✅ Potential value assessed — **{project_id}**",
        "",
        f"**Date:** {date.today()}",
        f"**Investment level:** {investment_labels.get(investment_level, investment_level)}",
        "",
    ]

    if value_summary:
        lines += [
            "## Overall assessment",
            "",
            value_summary,
            "",
        ]

    lines += ["## Benefit breakdown", ""]

    for i, b in enumerate(benefits, 1):
        lines += [
            f"### {i}. {b.get('benefit_title', '—')}",
            f"**Type:** {type_labels.get(b.get('benefit_type', ''), b.get('benefit_type', ''))}  ",
            f"**Magnitude:** {magnitude_icons.get(b.get('magnitude', ''), b.get('magnitude', ''))}  ",
            f"**Confidence:** {confidence_icons.get(b.get('confidence', ''), b.get('confidence', ''))}",
            "",
        ]
        if b.get("description"):
            lines.append(b["description"])
            lines.append("")
        if b.get("linked_business_needs"):
            lines.append(f"*Linked to BN:* {', '.join(b['linked_business_needs'])}")
        if b.get("linked_goals"):
            lines.append(f"*Linked to BG:* {', '.join(b['linked_goals'])}")
        lines.append("")

    # Value profile
    high_mag = sum(1 for b in benefits if b.get("magnitude") == "high")
    med_mag = sum(1 for b in benefits if b.get("magnitude") == "medium")
    high_conf = sum(1 for b in benefits if b.get("confidence") == "high")

    lines += [
        "---",
        "",
        "## Potential-value profile",
        "",
        f"- Benefits with high magnitude: {high_mag}/{len(benefits)}",
        f"- Benefits with high confidence: {high_conf}/{len(benefits)}",
        f"- Investment level: {investment_level}",
        "",
    ]

    # Simplified profile assessment
    if high_mag >= len(benefits) // 2 and investment_level in ("low", "medium"):
        profile = "🟢 Attractive profile — high value at moderate investment"
    elif investment_level == "high" and high_mag < len(benefits) // 2:
        profile = "🔴 Needs justification — high investment with unclear value"
    else:
        profile = "🟡 Average profile — refine in 7.6 with a detailed calculation"

    lines += [
        profile,
        "",
        "**Next step:** `check_future_state_completeness` → `save_future_state`",
        "",
        "ℹ️ This data will be available in **7.6** as context for a detailed value assessment.",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 6.2.7 — Completeness check
# ---------------------------------------------------------------------------

@mcp.tool()
def check_future_state_completeness(
    project_id: str,
) -> str:
    """
    BABOK 6.2 — Check the completeness of the future-state analysis before finalization (ADR-066).
    Follows the check_current_state_completeness (6.1) pattern. Does not block — informs.

    What it checks:
    - Are all scoped elements filled in (not drafts)?
    - Is there at least one goal with a KPI?
    - Are BNs linked to goals (if 6.1 data exists)?
    - Is there at least one constraint?
    - Has the gap analysis been run?
    - Is there a preliminary potential-value assessment?

    Args:
        project_id: Project identifier.

    Returns:
        Coverage report with verdicts and recommendations.
    """
    logger.info(f"check_future_state_completeness: {project_id}")

    scope = _load_scope(project_id)
    state = _load_state(project_id)
    goals_data = _load_goals(project_id)

    if not scope:
        return (
            "⚠️ The analysis scope has not been defined.\n"
            "Start with `scope_future_state` — a mandatory first step."
        )

    elements_in_scope = scope.get("elements_in_scope", [])
    elements_data = state.get("elements", {})
    constraints = state.get("constraints", [])
    potential_value = state.get("potential_value")
    gap_done = state.get("gap_analysis_done", False)
    goals_list = goals_data.get("goals", [])

    # Check elements
    filled_elements = []
    draft_elements = []
    missing_elements = []
    for elem in elements_in_scope:
        if elem in elements_data and not elements_data[elem].get("draft", True):
            filled_elements.append(elem)
        elif elem in elements_data:
            draft_elements.append(elem)
        else:
            missing_elements.append(elem)

    # Check goals
    has_goals = len(goals_list) > 0
    goals_with_kpi = [g for g in goals_list if g.get("objectives")]
    goals_without_kpi = [g for g in goals_list if not g.get("objectives")]

    # Check BN → BG linkage (if 6.1 data exists)
    cs_needs = _load_json(_cs_needs_path(project_id))
    bn_coverage_issue = None
    if cs_needs:
        bn_ids = {n["id"] for n in cs_needs.get("needs", [])}
        linked_bns = set()
        for g in goals_list:
            linked_bns.update(g.get("linked_business_needs", []))
        uncovered_bns = bn_ids - linked_bns
        if uncovered_bns:
            bn_coverage_issue = f"BN not linked to any goal: {', '.join(sorted(uncovered_bns))}"

    # Collect warnings
    warnings = []
    if missing_elements:
        warnings.append(f"{len(missing_elements)} elements from the scope are not filled in")
    if draft_elements:
        warnings.append(f"{len(draft_elements)} elements are in draft")
    if not has_goals:
        warnings.append("No business goals defined — the 6.2 outcome is not formulated")
    if goals_without_kpi:
        warnings.append(f"{len(goals_without_kpi)} goals have no KPI (SMART violation)")
    if not constraints:
        warnings.append("No constraints captured — the solution space is unconstrained")
    if not gap_done:
        warnings.append("Gap analysis not run — a mandatory input for 6.4")
    if not potential_value:
        warnings.append("Potential value not assessed — no context for 7.6")
    if bn_coverage_issue:
        warnings.append(bn_coverage_issue)

    ready = len(warnings) == 0

    # Readiness percentage
    total_checks = len(elements_in_scope) + 4  # elements + goals + constraints + gap + value
    passed = (
        len(filled_elements)
        + (1 if has_goals and not goals_without_kpi else 0)
        + (1 if constraints else 0)
        + (1 if gap_done else 0)
        + (1 if potential_value else 0)
    )
    readiness_pct = round(passed / total_checks * 100) if total_checks else 0

    lines = [
        f"# {'✅ Analysis ready for finalization' if ready else '⚠️ Analysis not yet ready'}",
        "",
        f"**Project:** {project_id}  ",
        f"**Readiness:** {readiness_pct}%  ",
        f"**Date:** {date.today()}",
        "",
        "## Future-state elements",
        "",
        f"| Status | Count |",
        f"|--------|------------|",
        f"| ✅ Filled in | {len(filled_elements)} |",
        f"| 📝 Drafts | {len(draft_elements)} |",
        f"| ⬜ Not filled in | {len(missing_elements)} |",
        f"| **Total in scope** | **{len(elements_in_scope)}** |",
        "",
    ]

    if missing_elements:
        lines += ["### Elements not filled in:"]
        for e in missing_elements:
            lines.append(f"- ⬜ `{e}` — {ELEMENT_LABELS.get(e, e)}")
        lines.append("")

    lines += [
        "## Business goals",
        "",
        f"{'✅' if goals_with_kpi else '❌'} Goals with KPI: {len(goals_with_kpi)}  ",
        f"{'⚠️' if goals_without_kpi else ''} Goals without KPI: {len(goals_without_kpi)}",
        "",
        "## Constraints",
        "",
        f"{'✅' if constraints else '❌'} Constraints captured: {len(constraints)}",
        "",
        "## Gap analysis",
        "",
        f"{'✅' if gap_done else '❌'} Gap analysis: {'completed' if gap_done else 'NOT completed'}",
        "",
        "## Potential value",
        "",
        f"{'✅' if potential_value else '❌'} Potential-value assessment: {'present' if potential_value else 'missing'}",
    ]

    if cs_needs and bn_coverage_issue:
        lines += ["", f"## BN coverage", "", f"⚠️ {bn_coverage_issue}"]

    if warnings:
        lines += [
            "",
            "## ⚠️ Warnings",
            "",
        ]
        for w in warnings:
            lines.append(f"- {w}")
        lines += [
            "",
            "> These are warnings, not blockers.",
            "> You can proceed via `save_future_state`, but it's recommended to close the gaps.",
        ]
    else:
        lines += [
            "",
            "---",
            "",
            "✅ All checks passed. The analysis is ready for finalization.",
            "",
            "**Next step:** `save_future_state` — create the final report.",
        ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 6.2.8 — Finalization and report generation
# ---------------------------------------------------------------------------

@mcp.tool()
def save_future_state(
    project_id: str,
    project_title: str,
    push_to_business_context: bool = False,
    analyst_notes: str = "",
) -> str:
    """
    BABOK 6.2 — Finalize the future-state analysis.
    Creates a human-readable Markdown report. Optionally pushes data to 7.3 (ADR-065).

    Args:
        project_id:              Project identifier.
        project_title:           Human-readable project name for the report title.
        push_to_business_context: If True — 6.2 data will be available for
                                 `set_business_context(from_strategy_project_id=...)` in 7.3.
                                 Default: False.
        analyst_notes:           Closing comments from the analyst.

    Returns:
        Save confirmation + links to artifacts + next steps.
    """
    logger.info(f"save_future_state: {project_id}")

    scope = _load_scope(project_id)
    state = _load_state(project_id)
    goals_data = _load_goals(project_id)
    gap_data = _load_gap(project_id)

    if not scope:
        return "⚠️ Analysis scope not found. Start with `scope_future_state`."

    elements_in_scope = scope.get("elements_in_scope", [])
    elements_data = state.get("elements", {})
    constraints = state.get("constraints", [])
    potential_value = state.get("potential_value")
    goals_list = goals_data.get("goals", [])

    # Draft warnings
    draft_warnings = [
        e for e in elements_in_scope
        if e in elements_data and elements_data[e].get("draft")
    ]

    type_labels = {
        "process_improvement": "Process Improvement",
        "new_system": "New System Implementation",
        "regulatory": "Regulatory Compliance",
        "cost_reduction": "Cost Reduction",
        "market_opportunity": "Market Opportunity",
        "other": "Other",
    }
    depth_labels = {"light": "Light", "standard": "Standard", "deep": "Deep"}
    change_labels = {
        "new": "🆕 New",
        "improve": "⬆️ Improve",
        "eliminate": "🗑️ Eliminate",
        "replace": "🔄 Replace",
    }

    # Build the Markdown report
    report_lines = [
        f"<!-- BABOK 6.2 — Define Future State | Project: {project_id} | {date.today()} -->",
        "",
        f"# Future-State Analysis: {project_title}",
        "",
        f"**Project:** {project_id}  ",
        f"**Initiative type:** {type_labels.get(scope.get('initiative_type', ''), scope.get('initiative_type', ''))}  ",
        f"**Analysis depth:** {depth_labels.get(scope.get('analysis_depth', ''), scope.get('analysis_depth', ''))}  ",
        f"**Date:** {date.today()}",
        "",
    ]

    if scope.get("known_goals"):
        report_lines += [
            "## Known goals (from the sponsor)",
            "",
            scope["known_goals"],
            "",
        ]

    report_lines += [
        "---",
        "",
        "## Future state: analysis by element",
        "",
    ]

    for elem in elements_in_scope:
        label = ELEMENT_LABELS.get(elem, elem)
        report_lines.append(f"### {label}")
        report_lines.append("")
        if elem in elements_data:
            elem_data = elements_data[elem]
            draft_mark = " *(draft)*" if elem_data.get("draft") else ""
            report_lines.append(elem_data.get("description", "—") + draft_mark)
            if elem_data.get("target_metrics"):
                report_lines += ["", "**Target metrics:**"]
                for k, v in elem_data["target_metrics"].items():
                    report_lines.append(f"- {k}: {v}")
            if elem_data.get("linked_business_needs"):
                report_lines.append(f"\n*Addresses BN:* {', '.join(elem_data['linked_business_needs'])}")
            if elem_data.get("notes"):
                report_lines.append(f"\n*Notes: {elem_data['notes']}*")
        else:
            report_lines.append("*Element not filled in*")
        report_lines.append("")

    # Business goals
    if goals_list:
        report_lines += [
            "---",
            "",
            "## Business Goals and KPIs",
            "",
        ]
        for goal in goals_list:
            smart_mark = "✅ SMART" if goal.get("smart_validated") else "⚠️ needs refinement"
            report_lines += [
                f"### {goal['id']} — {goal['goal_title']} ({smart_mark})",
                "",
                goal.get("description", "—"),
            ]
            if goal.get("objectives"):
                report_lines += ["", "**Target metrics:**"]
                for obj in goal["objectives"]:
                    report_lines.append(
                        f"- **{obj.get('title', '—')}**: {obj.get('baseline', '?')} → {obj.get('target', '?')} by {obj.get('deadline', '?')}"
                    )
            if goal.get("linked_business_needs"):
                report_lines.append(f"\n*Addresses BN:* {', '.join(goal['linked_business_needs'])}")
            report_lines.append("")

    # Constraints
    if constraints:
        category_labels = {
            "budget": "Financial limit",
            "time": "Timeframe",
            "technology": "Technology standards",
            "policy": "Internal policies",
            "resources": "Resources",
            "compliance": "Regulatory requirements",
            "other": "Other",
        }
        report_lines += [
            "---",
            "",
            "## Constraints",
            "",
        ]
        for c in constraints:
            status_mark = "✅" if c.get("status") == "confirmed" else "🔶 assumption"
            report_lines += [
                f"### {c['title']} ({category_labels.get(c.get('category', 'other'), c.get('category', 'other'))}) — {status_mark}",
                "",
                c.get("description", "—"),
                "",
            ]

    # Gap analysis
    if gap_data and gap_data.get("gaps"):
        report_lines += [
            "---",
            "",
            "## Gap Analysis",
            "",
            f"*Current-state baseline: {'available (6.1)' if gap_data.get('has_current_state_baseline') else 'missing'}*",
            "",
        ]
        for gap in gap_data["gaps"]:
            report_lines += [
                f"### {gap['element_label']}",
                f"- **Change type:** {change_labels.get(gap['change_type'], gap['change_type'])}",
                f"- **Complexity:** {gap['complexity']}",
                f"- **Gap:** {gap['gap_summary']}",
                "",
            ]

    # Potential value
    if potential_value:
        report_lines += [
            "---",
            "",
            "## Potential Value",
            "",
        ]
        if potential_value.get("value_summary"):
            report_lines += [potential_value["value_summary"], ""]
        report_lines.append(f"**Investment level:** {potential_value.get('investment_level', '—')}")
        report_lines.append("")
        for b in potential_value.get("benefits", []):
            report_lines.append(
                f"- **{b.get('benefit_title', '—')}** ({b.get('benefit_type', '—')}): "
                f"magnitude={b.get('magnitude', '—')}, confidence={b.get('confidence', '—')}"
            )
        report_lines.append("")

    if analyst_notes:
        report_lines += [
            "---",
            "",
            "## Analyst's Conclusion",
            "",
            analyst_notes,
            "",
        ]

    if draft_warnings:
        report_lines += [
            "---",
            "",
            f"⚠️ **Drafts:** elements {draft_warnings} contain unconfirmed data.",
            "",
        ]

    report_lines += [
        "---",
        "",
        f"*Future-state analysis performed per BABOK v3 methodology, task 6.2.*  ",
        f"*Generated: {datetime.now().strftime('%d.%m.%Y %H:%M')}*",
    ]

    report_content = "\n".join(report_lines)
    save_artifact(report_content, prefix=f"6_2_future_state_{_safe(project_id)}", project_id=project_id)

    # Push to 7.3 (ADR-065)
    push_status = ""
    if push_to_business_context:
        goals_summary = [
            {"id": g["id"], "title": g["goal_title"]}
            for g in goals_list
        ]
        push_status = (
            "\n\n## Integration with 7.3\n\n"
            f"6.2 data has been prepared for `set_business_context` (7.3).\n"
            f"Call: `set_business_context(project_id='{project_id}', "
            f"from_strategy_project_id='{project_id}', ...)`\n"
            f"The `from_strategy_project_id` parameter will pre-fill business goals from {len(goals_list)} BG goals.\n"
            f"(ADR-065: a single parameter for 6.1 + 6.2 data)"
        )

    result_lines = [
        f"✅ Future-state analysis finalized: **{project_id}**",
        "",
        f"**Project:** {project_title}",
        f"**Date:** {date.today()}",
        "",
        "## Artifact summary",
        "",
        f"- 📄 **Report:** saved (`6_2_future_state_{_safe(project_id)}`)",
        f"- 📊 **Data:** `{_safe(project_id)}_{STATE_FILENAME}`",
        f"- 📋 **Scope:** `{_safe(project_id)}_{SCOPE_FILENAME}`",
        f"- 🎯 **Goals:** `{_safe(project_id)}_{GOALS_FILENAME}` ({len(goals_list)} total)",
    ]

    if gap_data:
        result_lines.append(f"- 🔍 **Gap analysis:** `{_safe(project_id)}_{GAP_FILENAME}` ({len(gap_data.get('gaps', []))} elements)")

    result_lines += [
        "",
        "## Statistics",
        "",
        f"- Elements analyzed: {len([e for e in elements_in_scope if e in elements_data])} / {len(elements_in_scope)}",
        f"- Business goals with KPIs: {len([g for g in goals_list if g.get('objectives')])}",
        f"- Constraints: {len(constraints)}",
        f"- Gap analysis: {'✅ completed' if gap_data else '⚠️ not completed'}",
        f"- Potential value: {'✅ assessed' if potential_value else '⚠️ not assessed'}",
    ]

    if draft_warnings:
        result_lines += [
            "",
            f"⚠️ Drafts: {len(draft_warnings)} elements — {draft_warnings}",
        ]

    result_lines += [
        push_status,
        "",
        "---",
        "",
        "**Next steps:**",
        "- Use `{project}_gap_analysis.json` in task **6.4** (Define Change Strategy)",
        "- Call `set_business_context` in task **7.3** with `from_strategy_project_id`",
        "- Business goals (BG-xxx) are available in the 5.1 repository for requirements traceability",
        "- Potential-value data is available in **7.6** as context for value assessment",
    ]

    return "\n".join(result_lines)


if __name__ == "__main__":
    mcp.run()
