"""
BABOK 6.1 — Analyze Current State
MCP tools for analyzing the organization's current state.

Tools:
  - scope_current_state              — scope the analysis: initiative type, depth, elements
  - capture_current_state_element    — capture one of the 8 current-state elements
  - run_root_cause_analysis          — run RCA and save a normalized result
  - define_business_needs            — formulate a business need + register in 5.1
  - check_current_state_completeness — check the analysis completeness (coverage check)
  - save_current_state               — finalize + Markdown report + push to 7.3

Storage:
  - {project}_current_state_scope.json   — analysis scope (contract)
  - {project}_current_state.json         — data on 8 elements + RCA
  - {project}_business_needs.json        — business needs registry
  - {project}_current_state_analysis.md  — readable report (via save_artifact)

Integration:
  In: results from 4.3 (session_ids to import a draft)
  Out: BN nodes in the 5.1 repository, data for 7.3 set_business_context

ADR-054: business_need as a node type in the 5.1 repository
ADR-055: backward compatibility with set_business_context (7.3)
ADR-056: normalized RCA output regardless of technique
ADR-057: import from 4.3 via session_ids
ADR-058: scope_current_state as an explicit contract
ADR-059: capture_current_state_element — iterative pattern

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst (AI Платформа AIналитик). Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
from datetime import date, datetime
from typing import Literal, Optional
from mcp.server.fastmcp import FastMCP
from skills.common import save_artifact, logger, DATA_DIR, data_path, normalize_project_id

mcp = FastMCP("BABOK_CurrentState")

SCOPE_FILENAME = "current_state_scope.json"
STATE_FILENAME = "current_state.json"
NEEDS_FILENAME = "business_needs.json"
REPO_FILENAME = "traceability_repo.json"

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


def _needs_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{NEEDS_FILENAME}")


def _repo_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{REPO_FILENAME}")


def _load_scope(project_id: str) -> Optional[dict]:
    path = _scope_path(project_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _save_scope(data: dict) -> str:
    path = _scope_path(data["project_id"])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"Analysis scope saved: {path}")
    return path


def _load_state(project_id: str) -> dict:
    path = _state_path(project_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "project_id": project_id,
        "scope_ref": f"{_safe(project_id)}_{SCOPE_FILENAME}",
        "elements": {},
        "root_causes": [],
        "created": str(date.today()),
        "updated": str(date.today()),
    }


def _save_state(data: dict) -> str:
    path = _state_path(data["project_id"])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data["updated"] = str(date.today())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"Current state data saved: {path}")
    return path


def _load_needs(project_id: str) -> dict:
    path = _needs_path(project_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "project_id": project_id,
        "needs": [],
        "created": str(date.today()),
        "updated": str(date.today()),
    }


def _save_needs(data: dict) -> str:
    path = _needs_path(data["project_id"])
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data["updated"] = str(date.today())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"Business needs saved: {path}")
    return path


def _load_repo(project_id: str) -> Optional[dict]:
    path = _repo_path(project_id)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _save_repo(repo: dict) -> None:
    project_id = repo["project"]
    path = _repo_path(project_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    repo["updated"] = str(date.today())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(repo, f, ensure_ascii=False, indent=2)
    logger.info(f"Traceability repository updated from 6.1: {path}")


def _next_need_id(needs_data: dict) -> str:
    existing = [n["id"] for n in needs_data["needs"] if n["id"].startswith("BN-")]
    if not existing:
        return "BN-001"
    nums = [int(n.split("-")[1]) for n in existing if n.split("-")[1].isdigit()]
    return f"BN-{(max(nums) + 1):03d}" if nums else "BN-001"


def _next_rca_id(state: dict) -> str:
    existing = [r["rca_id"] for r in state["root_causes"] if r["rca_id"].startswith("RCA-")]
    if not existing:
        return "RCA-001"
    nums = [int(r.split("-")[1]) for r in existing if r.split("-")[1].isdigit()]
    return f"RCA-{(max(nums) + 1):03d}" if nums else "RCA-001"


# ---------------------------------------------------------------------------
# 6.1.1 — Scoping the current-state analysis
# ---------------------------------------------------------------------------

@mcp.tool()
def scope_current_state(
    project_id: str,
    initiative_type: Literal[
        "process_improvement", "new_system", "regulatory",
        "cost_reduction", "market_opportunity", "other"
    ],
    analysis_depth: Literal["light", "standard", "deep"],
    known_problems: str,
    elements_in_scope: str = "",
    session_ids: str = "",
) -> str:
    """
    BABOK 6.1 — First step: scope the current-state analysis.
    Establishes an explicit contract between the BA and the system (ADR-058).
    Called once at the start of work on 6.1.

    Args:
        project_id:        Project identifier.
        initiative_type:   Initiative type:
                           - process_improvement — process improvement
                           - new_system          — new system implementation
                           - regulatory          — regulatory compliance
                           - cost_reduction      — cost reduction
                           - market_opportunity  — market opportunity
                           - other               — other
        analysis_depth:    Analysis depth:
                           - light    — 3-4 elements, a quick pass
                           - standard — 5-6 elements, most projects
                           - deep     — all 8 elements, strategic initiatives
        known_problems:    Brief description of the problems or opportunities that triggered the work.
        elements_in_scope: Optional — override the element list manually.
                           JSON list of keys, e.g.:
                           '["business_needs","capabilities","technology"]'
                           Valid keys: business_needs | org_structure | capabilities |
                           technology | policies | architecture | assets | external
        session_ids:       Optional — list of session_id values from 4.3 to import a draft.
                           JSON list of strings: '["session_001","session_002"]'
                           The system marks the elements as a draft for later refinement.

    Returns:
        Scope confirmation + recommended elements.
    """
    logger.info(f"scope_current_state: {project_id}, type={initiative_type}, depth={analysis_depth}")

    # Determine the elements in scope
    if elements_in_scope.strip():
        try:
            custom_elements = json.loads(elements_in_scope)
            invalid = [e for e in custom_elements if e not in VALID_ELEMENTS]
            if invalid:
                return (
                    f"❌ Unknown elements: {invalid}\n"
                    f"Valid: {VALID_ELEMENTS}"
                )
            chosen_elements = custom_elements
            elements_source = "specified manually"
        except json.JSONDecodeError as e:
            return f"❌ Error parsing elements_in_scope: {e}"
    else:
        # Auto-select by type and depth
        base_elements = DEFAULT_ELEMENTS_BY_TYPE.get(initiative_type, ["business_needs", "capabilities"])
        if analysis_depth == "deep":
            chosen_elements = VALID_ELEMENTS
        elif analysis_depth == "light":
            chosen_elements = base_elements[:3]
        else:  # standard
            chosen_elements = base_elements
        elements_source = f"recommended for {initiative_type}/{analysis_depth}"

    # Parse session_ids
    imported_sessions = []
    if session_ids.strip():
        try:
            imported_sessions = json.loads(session_ids)
        except json.JSONDecodeError:
            return f"❌ Error parsing session_ids: expected a JSON list of strings"

    # Check for an existing scope
    existing = _load_scope(project_id)
    is_update = existing is not None

    scope_data = {
        "project_id": project_id,
        "initiative_type": initiative_type,
        "analysis_depth": analysis_depth,
        "known_problems": known_problems,
        "elements_in_scope": chosen_elements,
        "session_ids_imported": imported_sessions,
        "created": existing["created"] if existing else str(date.today()),
        "updated": str(date.today()),
    }

    path = _save_scope(scope_data)

    # If session_ids are given — initialize draft entries in the state
    if imported_sessions:
        state = _load_state(project_id)
        for elem in chosen_elements:
            if elem not in state["elements"]:
                state["elements"][elem] = {
                    "description": "",
                    "pain_points": [],
                    "metrics": {},
                    "sources": ["elicitation"],
                    "notes": f"Draft: data from sessions {imported_sessions}. Refine via capture_current_state_element.",
                    "draft": True,
                    "last_updated": str(date.today()),
                }
        _save_state(state)

    # Build the response
    depth_labels = {
        "light": "Light (3-4 elements, a quick pass)",
        "standard": "Standard (5-6 elements)",
        "deep": "Deep (all 8 elements)",
    }
    type_labels = {
        "process_improvement": "Process Improvement",
        "new_system": "New System Implementation",
        "regulatory": "Regulatory Compliance",
        "cost_reduction": "Cost Reduction",
        "market_opportunity": "Market Opportunity",
        "other": "Other",
    }

    lines = [
        f"{'⚠️ Scope UPDATED' if is_update else '✅ Analysis scope defined'} — **{project_id}**",
        "",
        f"**Initiative type:** {type_labels.get(initiative_type, initiative_type)}",
        f"**Analysis depth:** {depth_labels.get(analysis_depth, analysis_depth)}",
        f"**Date:** {date.today()}",
        "",
        "## Problem / opportunity description",
        "",
        known_problems,
        "",
        f"## Elements in scope ({len(chosen_elements)} of 8) — {elements_source}",
        "",
    ]

    for i, elem in enumerate(chosen_elements, 1):
        label = ELEMENT_LABELS.get(elem, elem)
        lines.append(f"{i}. **{elem}** — {label}")

    not_in_scope = [e for e in VALID_ELEMENTS if e not in chosen_elements]
    if not_in_scope:
        lines += ["", "### Elements out of scope (not analyzed):"]
        for elem in not_in_scope:
            lines.append(f"- ~~{elem}~~ — {ELEMENT_LABELS.get(elem, elem)}")

    if imported_sessions:
        lines += [
            "",
            f"## Import from 4.3",
            "",
            f"Sessions to import: {imported_sessions}",
            f"A draft was created for each element. Refine the data via `capture_current_state_element`.",
        ]

    lines += [
        "",
        "---",
        "",
        "## Next steps",
        "",
        "1. `capture_current_state_element` — fill in each element from the scope",
        "2. `run_root_cause_analysis` — run RCA on the key problems",
        "3. `define_business_needs` — formulate the business needs",
        "4. `check_current_state_completeness` — check completeness",
        "5. `save_current_state` — finalize the analysis",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 6.1.2 — Iterative data capture by element
# ---------------------------------------------------------------------------

@mcp.tool()
def capture_current_state_element(
    project_id: str,
    element: Literal[
        "business_needs", "org_structure", "capabilities",
        "technology", "policies", "architecture", "assets", "external"
    ],
    description: str,
    pain_points: str = "[]",
    metrics: str = "{}",
    sources: str = '["elicitation"]',
    notes: str = "",
) -> str:
    """
    BABOK 6.1 — Capture one current-state element (ADR-059).
    Iterative pattern: called once per element, possibly across different sessions.
    A repeated call updates the record (idempotent on element).

    Args:
        project_id:   Project identifier.
        element:      One of 8 elements:
                      business_needs | org_structure | capabilities | technology |
                      policies | architecture | assets | external
        description:  Substantive description of the element (the main field).
        pain_points:  List of problems and symptoms in this element.
                      JSON list of strings: '["The process is slow","Data is lost"]'
        metrics:      Current measurable indicators.
                      JSON object: '{"processing_time": "8 hours", "error_rate": "12%"}'
        sources:      Where the data comes from: JSON list of valid values.
                      Valid: elicitation | document | observation | interview | other
        notes:        Free-form notes (context, clarification questions).

    Returns:
        Confirmation of the record + status across all scoped elements.
    """
    logger.info(f"capture_current_state_element: {project_id}, element={element}")

    # Validate the JSON fields
    try:
        pain_list = json.loads(pain_points) if pain_points.strip() else []
        if not isinstance(pain_list, list):
            return "❌ pain_points must be a JSON list of strings: '[\"problem1\",\"problem2\"]'"
    except json.JSONDecodeError as e:
        return f"❌ Error parsing pain_points: {e}"

    try:
        metrics_dict = json.loads(metrics) if metrics.strip() else {}
        if not isinstance(metrics_dict, dict):
            return "❌ metrics must be a JSON object: '{\"indicator\": \"value\"}'"
    except json.JSONDecodeError as e:
        return f"❌ Error parsing metrics: {e}"

    try:
        sources_list = json.loads(sources) if sources.strip() else ["elicitation"]
        if not isinstance(sources_list, list):
            return "❌ sources must be a JSON list"
    except json.JSONDecodeError as e:
        return f"❌ Error parsing sources: {e}"

    if not description.strip():
        return "❌ description cannot be empty — describe the element's current state."

    # Check the scope
    scope = _load_scope(project_id)
    scope_warning = ""
    if scope and element not in scope.get("elements_in_scope", []):
        scope_warning = f"\n⚠️ Element `{element}` is not in the current scope. Add it to the scope via a repeat call to `scope_current_state`."

    # Load and update the state
    state = _load_state(project_id)
    is_update = element in state["elements"] and not state["elements"][element].get("draft", False)
    was_draft = element in state["elements"] and state["elements"].get(element, {}).get("draft", False)

    state["elements"][element] = {
        "description": description,
        "pain_points": pain_list,
        "metrics": metrics_dict,
        "sources": sources_list,
        "notes": notes,
        "draft": False,
        "last_updated": str(date.today()),
    }

    _save_state(state)

    label = ELEMENT_LABELS.get(element, element)
    action = "UPDATED" if is_update else ("saved (from draft)" if was_draft else "saved")

    lines = [
        f"✅ Element **{label}** (`{element}`) {action}",
        "",
        f"**Description:** {description[:200]}{'...' if len(description) > 200 else ''}",
    ]

    if pain_list:
        lines += ["", "**Problems and symptoms:**"]
        for p in pain_list:
            lines.append(f"- {p}")

    if metrics_dict:
        lines += ["", "**Metrics:**"]
        for k, v in metrics_dict.items():
            lines.append(f"- {k}: {v}")

    lines += ["", f"**Sources:** {', '.join(sources_list)}"]

    if scope_warning:
        lines.append(scope_warning)

    # Progress against the scope
    if scope:
        elements_in_scope = scope.get("elements_in_scope", [])
        filled = [e for e in elements_in_scope if e in state["elements"] and not state["elements"][e].get("draft", True)]
        remaining = [e for e in elements_in_scope if e not in state["elements"] or state["elements"][e].get("draft", True)]

        lines += [
            "",
            f"## Analysis progress: {len(filled)}/{len(elements_in_scope)} elements",
            "",
        ]
        for e in elements_in_scope:
            elem_label = ELEMENT_LABELS.get(e, e)
            if e in filled:
                status = "✅"
            elif e in state["elements"] and state["elements"][e].get("draft"):
                status = "📝 (draft)"
            else:
                status = "⬜"
            lines.append(f"{status} {elem_label}")

        if remaining:
            lines += ["", f"**Next element:** `{remaining[0]}`"]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 6.1.3 — Root Cause Analysis
# ---------------------------------------------------------------------------

@mcp.tool()
def run_root_cause_analysis(
    project_id: str,
    problem_statement: str,
    technique_used: Literal["fishbone", "five_whys", "problem_tree"],
    root_cause: str,
    contributing_factors: str = "[]",
    evidence: str = "[]",
    affected_elements: str = "[]",
) -> str:
    """
    BABOK 6.1 — Run RCA and save a normalized result (ADR-056).
    Normalized format: the output is the same regardless of technique.
    The technique is a thinking tool. The MCP saves the result.

    Args:
        project_id:          Project identifier.
        problem_statement:   A clear, measurable problem statement.
                             Example: "Application processing time grew from 2 to 8 hours over 6 months"
        technique_used:      RCA technique used:
                             - fishbone   — Ishikawa diagram by category
                             - five_whys  — 5 Whys, a linear chain
                             - problem_tree — problem tree (causes + effects)
        root_cause:          A single primary root cause (not a symptom!).
                             Example: "The 2012 approval policy has 3 redundant levels"
        contributing_factors: Factors that reinforce the root cause.
                             JSON list of strings:
                             '["No notification automation","Managers duplicate checks"]'
        evidence:            Data confirming the cause-and-effect relationship.
                             JSON list of strings:
                             '["5.5 of 8 hours go to approval (system data, Q1 2025)"]'
        affected_elements:   Which of the 8 current-state elements are affected.
                             JSON list of keys: '["capabilities","policies","technology"]'

    Returns:
        RCA card with an ID + recommendations on linking to business needs.
    """
    logger.info(f"run_root_cause_analysis: {project_id}, technique={technique_used}")

    if not problem_statement.strip():
        return "❌ problem_statement cannot be empty."
    if not root_cause.strip():
        return "❌ root_cause cannot be empty."

    try:
        factors = json.loads(contributing_factors) if contributing_factors.strip() else []
    except json.JSONDecodeError as e:
        return f"❌ Error parsing contributing_factors: {e}"

    try:
        evidence_list = json.loads(evidence) if evidence.strip() else []
    except json.JSONDecodeError as e:
        return f"❌ Error parsing evidence: {e}"

    try:
        affected = json.loads(affected_elements) if affected_elements.strip() else []
        invalid_affected = [e for e in affected if e not in VALID_ELEMENTS]
        if invalid_affected:
            return f"❌ Unknown elements in affected_elements: {invalid_affected}"
    except json.JSONDecodeError as e:
        return f"❌ Error parsing affected_elements: {e}"

    state = _load_state(project_id)
    rca_id = _next_rca_id(state)

    rca_record = {
        "rca_id": rca_id,
        "problem_statement": problem_statement,
        "technique_used": technique_used,
        "root_cause": root_cause,
        "contributing_factors": factors,
        "evidence": evidence_list,
        "affected_elements": affected,
        "created": datetime.now().isoformat(timespec="seconds"),
    }

    state["root_causes"].append(rca_record)
    _save_state(state)

    technique_labels = {
        "fishbone": "Fishbone / Ishikawa Diagram",
        "five_whys": "5 Whys",
        "problem_tree": "Problem Tree",
    }

    lines = [
        f"✅ RCA recorded: **{rca_id}**",
        "",
        f"**Technique:** {technique_labels.get(technique_used, technique_used)}",
        f"**Date:** {date.today()}",
        "",
        "## Problem",
        "",
        problem_statement,
        "",
        "## Root cause",
        "",
        f"🎯 {root_cause}",
    ]

    if factors:
        lines += ["", "## Contributing factors", ""]
        for f in factors:
            lines.append(f"- {f}")

    if evidence_list:
        lines += ["", "## Evidence", ""]
        for ev in evidence_list:
            lines.append(f"- {ev}")

    if affected:
        lines += ["", "## Affected current-state elements", ""]
        for elem in affected:
            lines.append(f"- `{elem}` — {ELEMENT_LABELS.get(elem, elem)}")

    total_rca = len(state["root_causes"])
    lines += [
        "",
        "---",
        "",
        f"Total RCAs in the project: **{total_rca}**",
        "",
        f"**Next step:** record a business need via `define_business_needs`",
        f"and link it to this RCA via the `root_cause_ids: [\"{rca_id}\"]` parameter",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 6.1.4 — Formulating business needs
# ---------------------------------------------------------------------------

@mcp.tool()
def define_business_needs(
    project_id: str,
    need_title: str,
    description: str,
    need_type: Literal["problem", "opportunity", "regulatory", "strategic"],
    priority: Literal["Critical", "High", "Medium", "Low"],
    source: str,
    cost_of_inaction: str = "",
    expected_benefits: str = "",
    root_cause_ids: str = "[]",
    register_in_traceability: bool = True,
) -> str:
    """
    BABOK 6.1 — Formulate a business need.
    Optionally registers a business_need node in the 5.1 repository (ADR-054).

    Args:
        project_id:              Project identifier.
        need_title:              Short title of the need (up to 100 characters).
        description:             Full description of the need — a clear, measurable statement.
        need_type:               Type of need:
                                 - problem      — an existing problem that needs solving
                                 - opportunity  — a market or operational opportunity
                                 - regulatory   — a regulator / legislative requirement
                                 - strategic    — a strategic initiative
        priority:                Priority: Critical | High | Medium | Low
        source:                  Source of the need (stakeholder, document, analysis).
                                 Example: "Director of Operations, interview 2025-03-15"
        cost_of_inaction:        Cost of inaction — what happens if nothing changes.
                                 Example: "18% customer loss per year, ~$240K"
        expected_benefits:       Expected benefits from satisfying the need.
        root_cause_ids:          List of RCA artifact IDs explaining this need.
                                 JSON list: '["RCA-001","RCA-002"]'
        register_in_traceability: If True — create a business_need node in the 5.1 repository.
                                 Default: True. Disable if the 5.1 repository doesn't exist yet.

    Returns:
        Business need card with an ID + confirmation of registration in 5.1.
    """
    logger.info(f"define_business_needs: {project_id}, title='{need_title[:50]}'")

    if not need_title.strip():
        return "❌ need_title cannot be empty."
    if not description.strip():
        return "❌ description cannot be empty."
    if not source.strip():
        return "❌ source cannot be empty — specify the source of the need."

    try:
        rca_ids = json.loads(root_cause_ids) if root_cause_ids.strip() else []
    except json.JSONDecodeError as e:
        return f"❌ Error parsing root_cause_ids: {e}"

    # Validate the RCA IDs
    if rca_ids:
        state = _load_state(project_id)
        existing_rca = {r["rca_id"] for r in state["root_causes"]}
        unknown_rca = [r for r in rca_ids if r not in existing_rca]
        if unknown_rca:
            return (
                f"⚠️ RCAs not found: {unknown_rca}\n"
                f"Existing: {list(existing_rca)}\n"
                f"Create the RCA via `run_root_cause_analysis` or remove the unknown IDs."
            )

    needs_data = _load_needs(project_id)
    need_id = _next_need_id(needs_data)

    need_record = {
        "id": need_id,
        "need_title": need_title,
        "description": description,
        "need_type": need_type,
        "priority": priority,
        "source": source,
        "cost_of_inaction": cost_of_inaction,
        "expected_benefits": expected_benefits,
        "root_cause_ids": rca_ids,
        "created": str(date.today()),
    }
    needs_data["needs"].append(need_record)
    _save_needs(needs_data)

    # Register in the 5.1 repository (ADR-054)
    traceability_status = ""
    if register_in_traceability:
        repo = _load_repo(project_id)
        if repo is None:
            traceability_status = (
                "\n\n⚠️ The 5.1 traceability repository was not found.\n"
                "Create it via `init_traceability_repo` (5.1), "
                f"then the `{need_id}` node of type `business_need` will be added automatically.\n"
                "To add it manually, use `init_traceability_repo` with this requirement in the list."
            )
        else:
            existing_ids = {r["id"] for r in repo["requirements"]}
            if need_id not in existing_ids:
                repo["requirements"].append({
                    "id": need_id,
                    "type": "business_need",
                    "title": need_title,
                    "version": "1.0",
                    "status": "confirmed",
                    "source_artifact": f"6.1/{_safe(project_id)}_business_needs.json",
                    "added": str(date.today()),
                })
                repo["history"].append({
                    "action": "node_added",
                    "id": need_id,
                    "type": "business_need",
                    "source": "6.1 define_business_needs",
                    "date": str(date.today()),
                })
                _save_repo(repo)
                traceability_status = f"\n\n✅ Node `{need_id}` (business_need) registered in the 5.1 repository."
            else:
                traceability_status = f"\n\nℹ️ Node `{need_id}` already exists in the 5.1 repository."

    type_labels = {
        "problem": "Problem",
        "opportunity": "Opportunity",
        "regulatory": "Regulatory Requirement",
        "strategic": "Strategic Initiative",
    }

    priority_icons = {"Critical": "🔴", "High": "🟠", "Medium": "🟡", "Low": "🟢"}

    lines = [
        f"✅ Business need recorded: **{need_id}**",
        "",
        f"**{priority_icons.get(priority, '')} {need_title}**",
        "",
        f"**Type:** {type_labels.get(need_type, need_type)}  ",
        f"**Priority:** {priority}  ",
        f"**Source:** {source}  ",
        f"**Date:** {date.today()}",
        "",
        "## Description",
        "",
        description,
    ]

    if cost_of_inaction:
        lines += ["", "## Cost of inaction", "", cost_of_inaction]

    if expected_benefits:
        lines += ["", "## Expected benefits", "", expected_benefits]

    if rca_ids:
        lines += ["", f"**Linked RCAs:** {', '.join(rca_ids)}"]

    total_needs = len(needs_data["needs"])
    lines += [
        "",
        "---",
        "",
        f"Total business needs in the project: **{total_needs}**",
        traceability_status,
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 6.1.5 — Analysis completeness check
# ---------------------------------------------------------------------------

@mcp.tool()
def check_current_state_completeness(
    project_id: str,
) -> str:
    """
    BABOK 6.1 — Check the completeness of the current-state analysis before finalizing.
    Doesn't block — it informs and warns.

    What it checks:
    - Are all scoped elements filled in (not drafts)?
    - Is there at least one RCA?
    - Is there at least one business need?
    - Are the business needs linked to an RCA?

    Args:
        project_id: Project identifier.

    Returns:
        Coverage report with recommendations and a readiness verdict.
    """
    logger.info(f"check_current_state_completeness: {project_id}")

    scope = _load_scope(project_id)
    state = _load_state(project_id)
    needs_data = _load_needs(project_id)

    if not scope:
        return (
            "⚠️ The analysis scope has not been defined.\n"
            "Start with `scope_current_state` — this is a mandatory first step."
        )

    elements_in_scope = scope.get("elements_in_scope", [])
    elements_data = state.get("elements", {})
    rca_list = state.get("root_causes", [])
    needs_list = needs_data.get("needs", [])

    # Check the elements
    filled_elements = []
    draft_elements = []
    missing_elements = []

    for elem in elements_in_scope:
        if elem in elements_data and not elements_data[elem].get("draft", True):
            filled_elements.append(elem)
        elif elem in elements_data and elements_data[elem].get("draft", True):
            draft_elements.append(elem)
        else:
            missing_elements.append(elem)

    # Check RCA
    has_rca = len(rca_list) > 0

    # Check business needs
    has_needs = len(needs_list) > 0

    # Check the BN → RCA link
    needs_with_rca = [n for n in needs_list if n.get("root_cause_ids")]
    needs_without_rca = [n for n in needs_list if not n.get("root_cause_ids")]

    # Verdict
    warnings = []
    if missing_elements:
        warnings.append(f"{len(missing_elements)} elements from the scope are not filled in")
    if draft_elements:
        warnings.append(f"{len(draft_elements)} elements are in draft — need refinement")
    if not has_rca:
        warnings.append("No RCA has been performed — the causes of the problems are not identified")
    if not has_needs:
        warnings.append("No business need has been defined — the analysis result is not formulated")
    if needs_without_rca:
        warnings.append(f"{len(needs_without_rca)} business needs are not linked to an RCA")

    ready = len(warnings) == 0

    # Readiness percentage
    total_checks = len(elements_in_scope) + 2  # elements + RCA + needs
    passed_checks = len(filled_elements) + (1 if has_rca else 0) + (1 if has_needs else 0)
    readiness_pct = round(passed_checks / total_checks * 100) if total_checks else 0

    lines = [
        f"# {'✅ Analysis ready for finalization' if ready else '⚠️ Analysis not ready yet'}",
        "",
        f"**Project:** {project_id}  ",
        f"**Readiness:** {readiness_pct}%  ",
        f"**Date:** {date.today()}",
        "",
        "## Current-state elements",
        "",
        f"| Status | Count |",
        f"|--------|------------|",
        f"| ✅ Filled in | {len(filled_elements)} |",
        f"| 📝 Drafts (need refinement) | {len(draft_elements)} |",
        f"| ⬜ Not filled in | {len(missing_elements)} |",
        f"| **Total in scope** | **{len(elements_in_scope)}** |",
        "",
    ]

    if missing_elements:
        lines += ["### Elements not filled in:"]
        for e in missing_elements:
            lines.append(f"- ⬜ `{e}` — {ELEMENT_LABELS.get(e, e)}")
        lines.append("")

    if draft_elements:
        lines += ["### Drafts (refine via capture_current_state_element):"]
        for e in draft_elements:
            lines.append(f"- 📝 `{e}` — {ELEMENT_LABELS.get(e, e)}")
        lines.append("")

    lines += [
        "## Root Cause Analysis",
        "",
        f"{'✅' if has_rca else '❌'} RCA performed: {len(rca_list)} {'analysis' if len(rca_list) == 1 else 'analyses'}",
        "",
        "## Business Needs",
        "",
        f"{'✅' if has_needs else '❌'} Business needs: {len(needs_list)} {'need' if len(needs_list) == 1 else 'needs'}",
    ]

    if needs_list:
        lines += [""]
        for n in needs_list:
            rca_linked = "✅" if n.get("root_cause_ids") else "⚠️ no RCA"
            lines.append(f"- `{n['id']}` {n['need_title']} — {rca_linked}")

    if warnings:
        lines += ["", "## ⚠️ Warnings", ""]
        for w in warnings:
            lines.append(f"- {w}")
        lines += [
            "",
            "> These are warnings, not blockers.",
            "> You can continue via `save_current_state`, but closing the gaps is recommended.",
        ]
    else:
        lines += [
            "",
            "---",
            "",
            "✅ All checks passed. The analysis is ready for finalization.",
            "",
            "**Next step:** `save_current_state` — create the final report.",
        ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 6.1.6 — Finalization and report creation
# ---------------------------------------------------------------------------

@mcp.tool()
def save_current_state(
    project_id: str,
    project_title: str,
    push_to_business_context: bool = False,
    analyst_notes: str = "",
) -> str:
    """
    BABOK 6.1 — Finalize the current-state analysis.
    Creates a readable Markdown report. Optionally pushes data to 7.3 (ADR-055).

    Args:
        project_id:              Project identifier.
        project_title:           Readable project name for the report heading.
        push_to_business_context: If True — automatically calls set_business_context (7.3)
                                 with data pre-filled from 6.1 (ADR-055).
                                 Default: False — the BA calls 7.3 themselves when needed.
        analyst_notes:           Concluding analyst comments for the report.

    Returns:
        Save confirmation + links to the artifacts.
    """
    logger.info(f"save_current_state: {project_id}")

    scope = _load_scope(project_id)
    state = _load_state(project_id)
    needs_data = _load_needs(project_id)

    if not scope:
        return (
            "⚠️ Analysis scope not found. Start with `scope_current_state`."
        )

    elements_in_scope = scope.get("elements_in_scope", [])
    elements_data = state.get("elements", {})
    rca_list = state.get("root_causes", [])
    needs_list = needs_data.get("needs", [])

    # Draft warnings
    draft_warnings = []
    for elem in elements_in_scope:
        if elem in elements_data and elements_data[elem].get("draft"):
            draft_warnings.append(elem)

    type_labels = {
        "process_improvement": "Process Improvement",
        "new_system": "New System Implementation",
        "regulatory": "Regulatory Compliance",
        "cost_reduction": "Cost Reduction",
        "market_opportunity": "Market Opportunity",
        "other": "Other",
    }
    depth_labels = {
        "light": "Light",
        "standard": "Standard",
        "deep": "Deep",
    }
    technique_labels = {
        "fishbone": "Fishbone / Ishikawa",
        "five_whys": "5 Whys",
        "problem_tree": "Problem Tree",
    }
    priority_icons = {"Critical": "🔴", "High": "🟠", "Medium": "🟡", "Low": "🟢"}
    need_type_labels = {
        "problem": "Problem",
        "opportunity": "Opportunity",
        "regulatory": "Regulatory Requirement",
        "strategic": "Strategic Initiative",
    }

    # Build the Markdown report
    report_lines = [
        f"<!-- BABOK 6.1 — Current State Analysis | Project: {project_id} | {date.today()} -->",
        "",
        f"# Current State Analysis: {project_title}",
        "",
        f"**Project:** {project_id}  ",
        f"**Initiative type:** {type_labels.get(scope.get('initiative_type', ''), scope.get('initiative_type', ''))}  ",
        f"**Analysis depth:** {depth_labels.get(scope.get('analysis_depth', ''), scope.get('analysis_depth', ''))}  ",
        f"**Date:** {date.today()}",
        "",
        "## Context and known problems",
        "",
        scope.get("known_problems", "—"),
        "",
        "---",
        "",
        "## Current state: analysis by element",
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

            if elem_data.get("pain_points"):
                report_lines += ["", "**Problems and symptoms:**"]
                for p in elem_data["pain_points"]:
                    report_lines.append(f"- {p}")

            if elem_data.get("metrics"):
                report_lines += ["", "**Current-state metrics:**"]
                for k, v in elem_data["metrics"].items():
                    report_lines.append(f"- {k}: {v}")

            if elem_data.get("notes"):
                report_lines += ["", f"*Notes: {elem_data['notes']}*"]
        else:
            report_lines.append("*Element not filled in*")

        report_lines.append("")

    # RCA section
    if rca_list:
        report_lines += [
            "---",
            "",
            "## Root Cause Analysis",
            "",
        ]
        for rca in rca_list:
            report_lines += [
                f"### {rca['rca_id']} — {technique_labels.get(rca['technique_used'], rca['technique_used'])}",
                "",
                f"**Problem:** {rca['problem_statement']}",
                "",
                f"**Root cause:** {rca['root_cause']}",
                "",
            ]
            if rca.get("contributing_factors"):
                report_lines += ["**Contributing factors:**"]
                for f in rca["contributing_factors"]:
                    report_lines.append(f"- {f}")
                report_lines.append("")
            if rca.get("evidence"):
                report_lines += ["**Evidence:**"]
                for ev in rca["evidence"]:
                    report_lines.append(f"- {ev}")
                report_lines.append("")

    # Business needs
    if needs_list:
        report_lines += [
            "---",
            "",
            "## Business Needs",
            "",
        ]
        for need in needs_list:
            icon = priority_icons.get(need.get("priority", ""), "")
            report_lines += [
                f"### {need['id']} — {icon} {need['need_title']}",
                "",
                f"**Type:** {need_type_labels.get(need.get('need_type', ''), need.get('need_type', ''))}  ",
                f"**Priority:** {need.get('priority', '—')}  ",
                f"**Source:** {need.get('source', '—')}",
                "",
                need.get("description", "—"),
            ]
            if need.get("cost_of_inaction"):
                report_lines += ["", f"**Cost of inaction:** {need['cost_of_inaction']}"]
            if need.get("expected_benefits"):
                report_lines += ["", f"**Expected benefits:** {need['expected_benefits']}"]
            if need.get("root_cause_ids"):
                report_lines += ["", f"**Linked RCAs:** {', '.join(need['root_cause_ids'])}"]
            report_lines.append("")

    if analyst_notes:
        report_lines += [
            "---",
            "",
            "## Analyst's conclusion",
            "",
            analyst_notes,
            "",
        ]

    if draft_warnings:
        report_lines += [
            "---",
            "",
            f"⚠️ **Drafts:** elements {draft_warnings} contain unrefined data from the import.",
            "",
        ]

    report_lines += [
        "---",
        "",
        f"*Current-state analysis performed per BABOK v3 methodology, task 6.1.*  ",
        f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*",
    ]

    report_content = "\n".join(report_lines)
    save_artifact(report_content, prefix=f"6_1_current_state_{_safe(project_id)}", project_id=project_id)

    # Push to 7.3 (ADR-055)
    push_status = ""
    if push_to_business_context and needs_list:
        push_status = (
            "\n\n## Integration with 7.3\n\n"
            f"Data prepared for handoff to `set_business_context` (7.3).\n"
            f"Call: `set_business_context(project_id='{project_id}', "
            f"from_current_state_project_id='{project_id}', ...)`\n"
            f"The `from_current_state_project_id` parameter will pre-fill business goals from {len(needs_list)} business needs."
        )

    result_lines = [
        f"✅ Current-state analysis finalized: **{project_id}**",
        "",
        f"**Project:** {project_title}",
        f"**Date:** {date.today()}",
        "",
        "## Artifact summary",
        "",
        f"- 📄 **Report:** saved via save_artifact (`6_1_current_state_{_safe(project_id)}`)",
        f"- 📊 **Data:** `{_safe(project_id)}_{STATE_FILENAME}`",
        f"- 📋 **Scope:** `{_safe(project_id)}_{SCOPE_FILENAME}`",
        f"- 🎯 **Business needs:** `{_safe(project_id)}_{NEEDS_FILENAME}` ({len(needs_list)} total)",
        "",
        "## Statistics",
        "",
        f"- Elements analyzed: {len([e for e in elements_in_scope if e in elements_data])} / {len(elements_in_scope)}",
        f"- RCAs performed: {len(rca_list)}",
        f"- Business needs: {len(needs_list)}",
    ]

    if draft_warnings:
        result_lines += [
            "",
            f"⚠️ Drafts: {len(draft_warnings)} elements have unrefined data: {draft_warnings}",
        ]

    result_lines += [
        push_status,
        "",
        "---",
        "",
        "**Next steps:**",
        "- Use the results in task **6.2** (Define Future State) for gap analysis",
        "- Call `set_business_context` in task **7.3** with `from_current_state_project_id` for autofill",
        "- Business needs (BN-xxx) are available in the 5.1 repository as upstream traceability nodes",
    ]

    return "\n".join(result_lines)


if __name__ == "__main__":
    mcp.run()
