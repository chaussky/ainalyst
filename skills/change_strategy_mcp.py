"""
BABOK 6.4 — Define Change Strategy
MCP tools for defining the change strategy.

Tools:
  - scope_change_strategy       — initialization + auto-import from 6.1, 6.2, 6.3
  - define_solution_scope       — capabilities by category + explicitly_excluded
  - assess_enterprise_readiness — 6 readiness dimensions x score 1-5 -> readiness_score
  - add_strategy_option         — strategy option card
  - compare_strategy_options    — weighted matrix -> winner + opportunity cost
  - define_transition_states    — transition phases with capabilities, gaps, risks, value
  - save_change_strategy        — finalize: JSON + Markdown + opt. push to 5.1

Storage:
  - {project}_change_strategy_scope.json  — scope and context
  - {project}_change_strategy.json        — final artifact (contract for 7.x, 8.x)

Integration:
  In: 6.1 (business_needs), 6.2 (future_state, gap_analysis), 6.3 (risk_assessment)
  Out: change_strategy.json -> 7.1, 7.4, 7.5, 7.6, 8.x;
       solution + satisfies node -> 5.1 (optional)

ADR-077: scope_change_strategy — auto-import from 6.1+6.2+6.3, graceful degradation
ADR-078: GAP embedded in define_solution_scope (gap_severity + gap_source)
ADR-079: 6 readiness dimensions (change_history added to the base 5)
ADR-080: do_nothing is added automatically as OPT-000
ADR-081: default 6 criteria + optional custom ones
ADR-082: new node type `solution` in the 5.1 repository
ADR-083: JSON contract — a single file with solution_scope + change_strategy sections

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst (AI Платформа AIналитик). Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
from datetime import date
from typing import Literal, Optional
from mcp.server.fastmcp import FastMCP
from skills.common import save_artifact, logger, DATA_DIR, data_path, normalize_project_id

mcp = FastMCP("BABOK_ChangeStrategy")

SCOPE_FILENAME = "change_strategy_scope.json"
STRATEGY_FILENAME = "change_strategy.json"
REPO_FILENAME = "traceability_repo.json"

# Files from previous tasks (optional sources)
BUSINESS_NEEDS_FILENAME = "business_needs.json"
FUTURE_STATE_FILENAME = "future_state.json"
GAP_FILENAME = "gap_analysis.json"
RISK_ASSESSMENT_FILENAME = "risk_assessment.json"

VALID_CHANGE_TYPES = ["transformation", "process_improvement", "technology_implementation", "regulatory_compliance", "other"]
VALID_METHODOLOGIES = ["agile", "waterfall", "hybrid"]
VALID_STRATEGY_TYPES = ["big_bang", "phased", "pilot_first", "do_nothing"]
VALID_INVESTMENT_LEVELS = ["high", "medium", "low"]
VALID_RISK_IMPACTS = ["mitigates", "exacerbates", "neutral"]
VALID_CAP_CATEGORIES = ["process", "technology", "data", "people", "org_structure", "knowledge", "location"]
VALID_GAP_SEVERITIES = ["none", "low", "medium", "high"]
VALID_VERDICTS = ["ready", "proceed_with_caution", "not_ready"]

DEFAULT_CRITERIA_WEIGHTS = {
    "alignment_to_goals": 25,
    "risk_mitigation": 20,
    "cost": 20,
    "time_to_value": 15,
    "org_readiness_fit": 10,
    "feasibility": 10,
}

DO_NOTHING_OPTION_ID = "OPT-000"


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _safe(project_id: str) -> str:
    return normalize_project_id(project_id)


def _scope_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{SCOPE_FILENAME}")


def _strategy_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{STRATEGY_FILENAME}")


def _repo_path(project_id: str, repo_project_id: Optional[str] = None) -> str:
    pid = repo_project_id or project_id
    return data_path(pid, f"{_safe(pid)}_{REPO_FILENAME}")


def _safe_load_json(path: str) -> Optional[dict]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def _load_strategy(project_id: str) -> dict:
    path = _strategy_path(project_id)
    if not os.path.exists(path):
        return _empty_strategy(project_id)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_strategy(data: dict, project_id: str):
    os.makedirs(os.path.dirname(_strategy_path(project_id)), exist_ok=True)
    data["updated"] = str(date.today())
    with open(_strategy_path(project_id), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _empty_strategy(project_id: str) -> dict:
    return {
        "project_id": project_id,
        "created": str(date.today()),
        "updated": str(date.today()),
        "scope": {},
        "imported_context": {
            "business_needs": [],
            "business_goals": [],
            "risks": [],
        },
        "solution_scope": {
            "capabilities": [],
            "explicitly_excluded": [],
            "scope_summary": "",
        },
        "enterprise_readiness": {},
        "change_strategy": {
            "options": [],
            "selected_option_id": None,
            "rejected_alternatives": [],
            "opportunity_cost": "",
        },
        "transition_states": [],
    }


def _next_option_id(options: list) -> str:
    """Generates the next OPT-xxx ID (skips OPT-000)."""
    existing_nums = []
    for o in options:
        oid = o.get("option_id", "")
        if oid.startswith("OPT-") and oid[4:].isdigit():
            n = int(oid[4:])
            if n > 0:
                existing_nums.append(n)
    if not existing_nums:
        return "OPT-001"
    return f"OPT-{max(existing_nums) + 1:03d}"


def _readiness_verdict(score: float) -> str:
    if score >= 4.0:
        return "ready"
    elif score >= 2.5:
        return "proceed_with_caution"
    else:
        return "not_ready"


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def scope_change_strategy(
    project_id: str,
    change_type: Literal["transformation", "process_improvement", "technology_implementation", "regulatory_compliance", "other"],
    time_horizon_months: int,
    methodology: Literal["agile", "waterfall", "hybrid"],
    source_project_ids: str = "[]",
    ba_notes: str = "",
) -> str:
    """
    Step 1 of the 6.4 pipeline: initialize the change strategy.

    Locks in the change type, horizon, and methodology.
    Automatically imports context from 6.1 (business_needs), 6.2 (future_state, gap_analysis),
    6.3 (risk_assessment). Adds do_nothing as OPT-000.
    Graceful degradation: missing artifacts are skipped with a warning.

    Args:
        project_id: Project identifier
        change_type: Change type (transformation/process_improvement/technology_implementation/regulatory_compliance/other)
        time_horizon_months: Target horizon in months
        methodology: Methodology (agile/waterfall/hybrid)
        source_project_ids: JSON list of project_id from 6.1/6.2/6.3 for auto-import, e.g. '["crm_upgrade"]'
        ba_notes: Additional context
    """
    try:
        source_ids = json.loads(source_project_ids) if source_project_ids.strip() else []
    except json.JSONDecodeError:
        return "❌ Error: source_project_ids must be a JSON array, e.g. '[\"crm\"]'"

    if time_horizon_months <= 0:
        return "❌ time_horizon_months must be > 0"

    scope = {
        "project_id": project_id,
        "change_type": change_type,
        "time_horizon_months": time_horizon_months,
        "methodology": methodology,
        "source_project_ids": source_ids,
        "ba_notes": ba_notes,
        "created": str(date.today()),
    }

    os.makedirs(os.path.dirname(_scope_path(project_id)), exist_ok=True)
    with open(_scope_path(project_id), "w", encoding="utf-8") as f:
        json.dump(scope, f, ensure_ascii=False, indent=2)

    strategy = _load_strategy(project_id)
    strategy["scope"] = scope

    # --- Auto-import context ---
    warnings = []
    imported_bn = []
    imported_bg = []
    imported_risks = []

    if not source_ids:
        source_ids = [project_id]

    for src_id in source_ids:
        # 6.1: business_needs
        needs_path = data_path(src_id, f"{_safe(src_id)}_{BUSINESS_NEEDS_FILENAME}")
        needs_data = _safe_load_json(needs_path)
        if needs_data:
            for bn in needs_data.get("business_needs", []):
                imported_bn.append({
                    "id": bn.get("id", ""),
                    "title": bn.get("title", bn.get("description", ""))[:80],
                    "priority": bn.get("priority", ""),
                    "source_project": src_id,
                })
        else:
            warnings.append(f"⚠️ 6.1 business_needs not found for '{src_id}'")

        # 6.2: future_state (goals)
        fs_path = data_path(src_id, f"{_safe(src_id)}_{FUTURE_STATE_FILENAME}")
        fs_data = _safe_load_json(fs_path)
        if fs_data:
            for bg in fs_data.get("goals", []):
                imported_bg.append({
                    "id": bg.get("id", ""),
                    "title": bg.get("title", bg.get("description", ""))[:80],
                    "source_project": src_id,
                })
        else:
            warnings.append(f"⚠️ 6.2 future_state not found for '{src_id}'")

        # 6.3: risk_assessment
        risk_path = data_path(src_id, f"{_safe(src_id)}_{RISK_ASSESSMENT_FILENAME}")
        risk_data = _safe_load_json(risk_path)
        if risk_data:
            for rk in risk_data.get("risks", []):
                if rk.get("status") == "identified":
                    imported_risks.append({
                        "id": rk.get("risk_id", ""),
                        "description": rk.get("description", "")[:80],
                        "zone": rk.get("zone", "medium"),
                        "risk_score": rk.get("risk_score", 0),
                        "response_strategy": rk.get("response_strategy", ""),
                        "source_project": src_id,
                    })
        else:
            warnings.append(f"⚠️ 6.3 risk_assessment not found for '{src_id}'")

    strategy["imported_context"] = {
        "business_needs": imported_bn,
        "business_goals": imported_bg,
        "risks": imported_risks,
    }

    # do_nothing is added automatically (ADR-080)
    existing_options = strategy["change_strategy"].get("options", [])
    if not any(o.get("option_id") == DO_NOTHING_OPTION_ID for o in existing_options):
        existing_options.insert(0, {
            "option_id": DO_NOTHING_OPTION_ID,
            "name": "Do Nothing (status quo)",
            "strategy_type": "do_nothing",
            "investment_level": "low",
            "timeline_months": 0,
            "linked_risks": [],
            "risk_impact": "exacerbates",
            "pros": ["No cost of change", "No operational rollout risk"],
            "cons": [
                "Business needs remain unmet",
                "Competitive gap keeps widening",
                "Current problems worsen over time",
            ],
            "weighted_score": None,
            "selected": False,
            "auto_added": True,
        })
    strategy["change_strategy"]["options"] = existing_options

    _save_strategy(strategy, project_id)

    # --- Output formatting ---
    lines = [
        f"✅ Change strategy initialized\n\n",
        f"  Project:     {project_id}\n",
        f"  Type:        {change_type}\n",
        f"  Horizon:     {time_horizon_months} months\n",
        f"  Methodology: {methodology}\n\n",
    ]

    if imported_bn or imported_bg or imported_risks:
        lines.append("**Imported context:**\n")
        if imported_bn:
            lines.append(f"  📋 Business needs (6.1): {len(imported_bn)} — "
                         + ", ".join(bn["id"] for bn in imported_bn if bn["id"]) + "\n")
        if imported_bg:
            lines.append(f"  🎯 Business goals (6.2): {len(imported_bg)} — "
                         + ", ".join(bg["id"] for bg in imported_bg if bg["id"]) + "\n")
        if imported_risks:
            high_risks = [r for r in imported_risks if r.get("zone") == "high"]
            lines.append(f"  ⚠️  Risks (6.3):          {len(imported_risks)}"
                         + (f" ({len(high_risks)} High)" if high_risks else "") + "\n")

    if warnings:
        lines.append("\n**Warnings (graceful degradation):**\n")
        for w in warnings:
            lines.append(f"  {w}\n")

    lines.append(
        f"\n  ℹ️ OPT-000 (do_nothing) added automatically as the baseline.\n\n"
        f"**Next step:** `define_solution_scope` — define the solution capabilities."
    )

    return "".join(lines)


@mcp.tool()
def define_solution_scope(
    project_id: str,
    capabilities_json: str,
    explicitly_excluded: str = "[]",
    scope_summary: str = "",
) -> str:
    """
    Step 2 of the 6.4 pipeline: define the solution scope via capabilities.

    Each capability has a category (process/technology/data/people/org_structure/knowledge/location),
    a gap_severity (none/low/medium/high), and an in_scope flag.
    explicitly_excluded records what is deliberately out of scope — prevents scope creep.

    Args:
        project_id: Project identifier
        capabilities_json: JSON array of capabilities. Object format:
            {"name": "...", "category": "technology", "description": "...",
             "gap_severity": "high", "gap_source": "6.2:gap_analysis", "in_scope": true}
        explicitly_excluded: JSON list of strings — what is explicitly NOT in scope
        scope_summary: 2-3 sentences: what we are doing and what we are not doing
    """
    try:
        capabilities = json.loads(capabilities_json)
    except json.JSONDecodeError:
        return "❌ Error parsing capabilities_json. Check the JSON syntax."

    if not isinstance(capabilities, list):
        return "❌ capabilities_json must be a JSON array."

    try:
        excluded = json.loads(explicitly_excluded) if explicitly_excluded.strip() else []
    except json.JSONDecodeError:
        excluded = []

    # Validate capabilities
    valid_caps = []
    errors = []
    for i, cap in enumerate(capabilities):
        name = cap.get("name", "")
        category = cap.get("category", "")
        gap_severity = cap.get("gap_severity", "medium")
        if not name:
            errors.append(f"Capability #{i+1}: missing 'name' field")
            continue
        if category not in VALID_CAP_CATEGORIES:
            errors.append(f"Capability '{name}': invalid category '{category}'. Allowed: {', '.join(VALID_CAP_CATEGORIES)}")
            continue
        if gap_severity not in VALID_GAP_SEVERITIES:
            errors.append(f"Capability '{name}': invalid gap_severity '{gap_severity}'")
            continue
        valid_caps.append({
            "name": name,
            "category": category,
            "description": cap.get("description", ""),
            "gap_severity": gap_severity,
            "gap_source": cap.get("gap_source", "manual"),
            "in_scope": cap.get("in_scope", True),
        })

    if errors:
        return "❌ Errors in capabilities_json:\n" + "\n".join(f"  • {e}" for e in errors)

    strategy = _load_strategy(project_id)
    strategy["solution_scope"] = {
        "capabilities": valid_caps,
        "explicitly_excluded": excluded,
        "scope_summary": scope_summary,
    }
    _save_strategy(strategy, project_id)

    in_scope = [c for c in valid_caps if c.get("in_scope", True)]
    out_of_scope = [c for c in valid_caps if not c.get("in_scope", True)]

    # Stats by category
    cats = {}
    for c in in_scope:
        cats[c["category"]] = cats.get(c["category"], 0) + 1

    # Stats by gap_severity
    gaps = {"high": 0, "medium": 0, "low": 0, "none": 0}
    for c in in_scope:
        gaps[c["gap_severity"]] = gaps.get(c["gap_severity"], 0) + 1

    lines = [
        f"✅ Solution scope defined\n\n",
        f"  Capabilities in scope: {len(in_scope)}\n",
        f"  Explicit exclusions:   {len(excluded)}\n\n",
    ]

    if cats:
        lines.append("**Capabilities by category:**\n")
        for cat, cnt in sorted(cats.items()):
            lines.append(f"  {cat}: {cnt}\n")

    lines.append("\n**Distribution by gap_severity:**\n")
    if gaps["high"] > 0:
        lines.append(f"  🔴 high:   {gaps['high']} (critical gaps — will drive the phase structure)\n")
    if gaps["medium"] > 0:
        lines.append(f"  🟡 medium: {gaps['medium']}\n")
    if gaps["low"] > 0:
        lines.append(f"  🟢 low:    {gaps['low']}\n")
    if gaps["none"] > 0:
        lines.append(f"  ⚪ none:   {gaps['none']} (capability already exists)\n")

    if excluded:
        lines.append("\n**Explicit exclusions from scope:**\n")
        for ex in excluded:
            lines.append(f"  • {ex}\n")

    if scope_summary:
        lines.append(f"\n**Scope summary:** {scope_summary}\n")

    lines.append(
        f"\n→ Next step: `assess_enterprise_readiness` — assess the organization's readiness."
    )

    return "".join(lines)


@mcp.tool()
def assess_enterprise_readiness(
    project_id: str,
    leadership_commitment: int,
    cultural_readiness: int,
    resource_availability: int,
    operational_readiness: int,
    technical_readiness: int,
    change_history: int,
    leadership_rationale: str = "",
    cultural_rationale: str = "",
    resource_rationale: str = "",
    operational_rationale: str = "",
    technical_rationale: str = "",
    change_history_rationale: str = "",
) -> str:
    """
    Step 3 of the 6.4 pipeline: assess the organization's readiness for change.

    Rates 6 dimensions on a 1-5 scale. Computes the readiness_score (average) and a verdict:
    ready (>=4.0) / proceed_with_caution (2.5-3.9) / not_ready (<2.5).
    ADR-079: change_history added to the base 5 dimensions.

    Args:
        project_id: Project identifier
        leadership_commitment: Leadership commitment 1-5
        cultural_readiness: Cultural readiness 1-5
        resource_availability: Resource availability 1-5
        operational_readiness: Operational readiness 1-5
        technical_readiness: Technical readiness 1-5
        change_history: Organization's track record with change 1-5
        leadership_rationale: Rationale for the leadership rating
        cultural_rationale: Rationale for the culture rating
        resource_rationale: Rationale for the resource rating
        operational_rationale: Rationale for the operational rating
        technical_rationale: Rationale for the technical rating
        change_history_rationale: Rationale for the change_history rating
    """
    dimensions = {
        "leadership_commitment": leadership_commitment,
        "cultural_readiness": cultural_readiness,
        "resource_availability": resource_availability,
        "operational_readiness": operational_readiness,
        "technical_readiness": technical_readiness,
        "change_history": change_history,
    }
    rationales = {
        "leadership_commitment": leadership_rationale,
        "cultural_readiness": cultural_rationale,
        "resource_availability": resource_rationale,
        "operational_readiness": operational_rationale,
        "technical_readiness": technical_rationale,
        "change_history": change_history_rationale,
    }

    errors = []
    for dim, val in dimensions.items():
        if not 1 <= val <= 5:
            errors.append(f"{dim} must be between 1 and 5, got: {val}")
    if errors:
        return "❌ Validation errors:\n" + "\n".join(f"  • {e}" for e in errors)

    score = sum(dimensions.values()) / len(dimensions)
    score = round(score, 2)
    verdict = _readiness_verdict(score)

    readiness_data = {
        "dimensions": {
            dim: {"score": val, "rationale": rationales.get(dim, "")}
            for dim, val in dimensions.items()
        },
        "readiness_score": score,
        "verdict": verdict,
        "assessed_on": str(date.today()),
    }

    strategy = _load_strategy(project_id)
    strategy["enterprise_readiness"] = readiness_data
    _save_strategy(strategy, project_id)

    verdict_emoji = {"ready": "🟢", "proceed_with_caution": "🟡", "not_ready": "🔴"}
    verdict_text = {
        "ready": "The organization is ready for change",
        "proceed_with_caution": "There are gaps — preparatory measures are needed",
        "not_ready": "A dedicated organizational readiness program is required",
    }

    weak_dims = [(dim, val) for dim, val in dimensions.items() if val <= 2]
    medium_dims = [(dim, val) for dim, val in dimensions.items() if val == 3]

    lines = [
        f"✅ Readiness assessment complete\n\n",
        f"  Readiness Score: {score:.1f} / 5.0\n",
        f"  Verdict: {verdict_emoji[verdict]} {verdict} — {verdict_text[verdict]}\n\n",
        f"**Profile by dimension:**\n",
    ]

    dim_labels = {
        "leadership_commitment": "Leadership commitment",
        "cultural_readiness": "Cultural readiness",
        "resource_availability": "Resource availability",
        "operational_readiness": "Operational readiness",
        "technical_readiness": "Technical readiness",
        "change_history": "Change history",
    }
    score_bar = {1: "▪▫▫▫▫", 2: "▪▪▫▫▫", 3: "▪▪▪▫▫", 4: "▪▪▪▪▫", 5: "▪▪▪▪▪"}

    for dim, val in dimensions.items():
        bar = score_bar.get(val, "?????")
        label = dim_labels.get(dim, dim)
        lines.append(f"  {bar} {val}/5  {label}\n")

    if weak_dims:
        lines.append("\n**⚠️ Critical gaps (score ≤ 2):**\n")
        for dim, val in weak_dims:
            rat = rationales.get(dim, "")
            lines.append(f"  • {dim_labels.get(dim, dim)}: {val}/5"
                         + (f" — {rat}" if rat else "") + "\n")
        if verdict != "not_ready":
            lines.append(
                "  → Consider a pilot_first or phased strategy\n"
                "     and add a preparatory Phase 0 to the transition states\n"
            )

    if verdict == "proceed_with_caution" and medium_dims:
        lines.append("\n**🟡 Dimensions needing attention (score = 3):**\n")
        for dim, val in medium_dims:
            lines.append(f"  • {dim_labels.get(dim, dim)}: {val}/5\n")

    lines.append(
        f"\n→ Next step: `add_strategy_option` — add strategy options (min 1 real one).\n"
        f"  OPT-000 (do_nothing) has already been added automatically."
    )

    return "".join(lines)


@mcp.tool()
def add_strategy_option(
    project_id: str,
    name: str,
    strategy_type: Literal["big_bang", "phased", "pilot_first"],
    investment_level: Literal["high", "medium", "low"],
    timeline_months: int,
    pros: str,
    cons: str,
    linked_risks: str = "[]",
    risk_impact: Literal["mitigates", "exacerbates", "neutral"] = "neutral",
) -> str:
    """
    Step 4 of the 6.4 pipeline: add a strategy option.

    do_nothing (OPT-000) is added automatically — no need to add it again.
    Minimum 1 real option. Optimally 2-3 real options + do_nothing.

    Args:
        project_id: Project identifier
        name: Option name (e.g. "Phased CRM replacement")
        strategy_type: Strategy type (big_bang/phased/pilot_first)
        investment_level: Investment level (high/medium/low)
        timeline_months: Implementation timeline in months
        pros: JSON list of advantages, e.g. '["Fast time-to-value", "Low risk"]'
        cons: JSON list of disadvantages, e.g. '["High cost", "Long timeline"]'
        linked_risks: JSON list of RK-xxx risks, e.g. '["RK-001", "RK-003"]'
        risk_impact: How the option affects linked_risks (mitigates/exacerbates/neutral)
    """
    try:
        pros_list = json.loads(pros) if pros.strip() else []
    except json.JSONDecodeError:
        return "❌ Error parsing pros. Must be a JSON array of strings."

    try:
        cons_list = json.loads(cons) if cons.strip() else []
    except json.JSONDecodeError:
        return "❌ Error parsing cons. Must be a JSON array of strings."

    try:
        risks_list = json.loads(linked_risks) if linked_risks.strip() else []
    except json.JSONDecodeError:
        risks_list = []

    if timeline_months <= 0:
        return "❌ timeline_months must be > 0"
    if not name.strip():
        return "❌ name cannot be empty"

    strategy = _load_strategy(project_id)
    options = strategy["change_strategy"].get("options", [])

    option_id = _next_option_id(options)

    option = {
        "option_id": option_id,
        "name": name,
        "strategy_type": strategy_type,
        "investment_level": investment_level,
        "timeline_months": timeline_months,
        "linked_risks": risks_list,
        "risk_impact": risk_impact,
        "pros": pros_list,
        "cons": cons_list,
        "weighted_score": None,
        "selected": False,
    }

    options.append(option)
    strategy["change_strategy"]["options"] = options
    _save_strategy(strategy, project_id)

    total_real = len([o for o in options if o.get("strategy_type") != "do_nothing"])
    risks_hint = f"\n  Linked risks: {', '.join(risks_list)} ({risk_impact})" if risks_list else ""

    return (
        f"✅ Strategy option added: {option_id}\n\n"
        f"  Name:        {name}\n"
        f"  Type:        {strategy_type}\n"
        f"  Investment:  {investment_level}\n"
        f"  Timeline:    {timeline_months} mo.\n"
        f"  Pros:        {len(pros_list)}\n"
        f"  Cons:        {len(cons_list)}\n"
        f"{risks_hint}\n\n"
        f"  Real options in the register: {total_real}\n\n"
        f"→ Add another option (`add_strategy_option`) or move on to `compare_strategy_options`."
    )


@mcp.tool()
def compare_strategy_options(
    project_id: str,
    scores_json: str,
    opportunity_cost: str,
    weights_json: str = "{}",
    custom_criteria_json: str = "{}",
) -> str:
    """
    Step 5 of the 6.4 pipeline: compare options via a weighted matrix.

    Computes the weighted_score for each option, determines the winner,
    and records the opportunity cost of the rejected options.

    Args:
        project_id: Project identifier
        scores_json: JSON matrix of 1-5 scores per criterion.
            Format: {"OPT-001": {"alignment_to_goals": 4, "risk_mitigation": 3, "cost": 3,
                                 "time_to_value": 4, "org_readiness_fit": 3, "feasibility": 4}}
            OPT-000 (do_nothing) should be included for a correct comparison.
        opportunity_cost: What we give up by choosing the winner over the rest (required text)
        weights_json: Optional — override the default criteria weights.
            The sum of all weights (including custom ones) must be 100.
            Format: {"alignment_to_goals": 30, "risk_mitigation": 25, ...}
        custom_criteria_json: Optional — add custom criteria with weights.
            Format: {"regulatory_compliance": {"weight": 15, "description": "..."}}
    """
    if not opportunity_cost.strip():
        return "❌ opportunity_cost is required. Describe what we give up by choosing the best option over the rest."

    try:
        scores = json.loads(scores_json)
    except json.JSONDecodeError:
        return "❌ Error parsing scores_json. Check the JSON syntax."

    try:
        weights_override = json.loads(weights_json) if weights_json.strip() else {}
    except json.JSONDecodeError:
        weights_override = {}

    try:
        custom_criteria = json.loads(custom_criteria_json) if custom_criteria_json.strip() else {}
    except json.JSONDecodeError:
        custom_criteria = {}

    # Final weights
    final_weights = dict(DEFAULT_CRITERIA_WEIGHTS)
    if weights_override:
        final_weights.update(weights_override)

    # Add custom criteria
    for crit_name, crit_data in custom_criteria.items():
        if isinstance(crit_data, dict):
            final_weights[crit_name] = crit_data.get("weight", 0)
        else:
            final_weights[crit_name] = int(crit_data)

    total_weight = sum(final_weights.values())
    if abs(total_weight - 100) > 1:
        return f"❌ The sum of weights must be 100, got: {total_weight}. Adjust weights_json."

    strategy = _load_strategy(project_id)
    options = strategy["change_strategy"].get("options", [])

    if not options:
        return "⚠️ No strategy options. Add one via `add_strategy_option`."

    # Compute weighted_score
    scored_options = []
    for opt in options:
        oid = opt["option_id"]
        opt_scores = scores.get(oid, {})
        if not opt_scores and oid != DO_NOTHING_OPTION_ID:
            continue

        if oid == DO_NOTHING_OPTION_ID and oid not in scores:
            # do_nothing without explicit scores — use minimal ones
            opt_scores = {crit: 1 for crit in final_weights}

        weighted = 0.0
        for crit, weight in final_weights.items():
            crit_score = opt_scores.get(crit, 0)
            weighted += crit_score * (weight / 100)

        opt["weighted_score"] = round(weighted, 2)
        opt["scores_detail"] = opt_scores
        scored_options.append(opt)

    if not scored_options:
        return "⚠️ No scored options. Check that the option_id values in scores_json match the options you added."

    # Determine the winner (highest score among non-do_nothing options)
    real_options = [o for o in scored_options if o.get("strategy_type") != "do_nothing"]
    if not real_options:
        return "⚠️ No real options (other than do_nothing). Add one via `add_strategy_option`."

    winner = max(real_options, key=lambda o: o.get("weighted_score", 0))
    winner_id = winner["option_id"]

    # Update selected
    for opt in options:
        opt["selected"] = (opt["option_id"] == winner_id)

    # Build rejected_alternatives
    rejected = []
    for opt in scored_options:
        if opt["option_id"] != winner_id:
            rejected.append({
                "option_id": opt["option_id"],
                "name": opt.get("name", ""),
                "weighted_score": opt.get("weighted_score"),
                "rationale": f"Lost to {winner_id} on weighted score: "
                             f"{opt.get('weighted_score', 0):.2f} vs {winner.get('weighted_score', 0):.2f}",
            })

    strategy["change_strategy"]["options"] = options
    strategy["change_strategy"]["selected_option_id"] = winner_id
    strategy["change_strategy"]["rejected_alternatives"] = rejected
    strategy["change_strategy"]["opportunity_cost"] = opportunity_cost
    strategy["change_strategy"]["criteria_weights_used"] = final_weights
    strategy["change_strategy"]["compared_on"] = str(date.today())

    _save_strategy(strategy, project_id)

    # --- Output formatting ---
    lines = [
        f"✅ Comparison of options complete\n\n",
        f"  **Winner: {winner_id} — {winner.get('name', '')}**\n",
        f"  Weighted Score: {winner.get('weighted_score', 0):.2f} / 5.00\n",
        f"  Strategy type: {winner.get('strategy_type', '')}\n",
        f"  Timeline: {winner.get('timeline_months', 0)} mo. | Investment: {winner.get('investment_level', '')}\n\n",
        f"**Comparison matrix:**\n",
    ]

    # Table
    header_opts = [o["option_id"] for o in scored_options]
    lines.append(f"  {'Criterion':<25} | " + " | ".join(f"{oid:>8}" for oid in header_opts) + " | Weight\n")
    lines.append(f"  {'-'*25}-+-" + "-+-".join(["-"*8]*len(header_opts)) + "-+-----\n")
    for crit, weight in final_weights.items():
        row = f"  {crit:<25} | "
        for opt in scored_options:
            val = opt.get("scores_detail", {}).get(crit, "-")
            row += f"{val:>8} | "
        row += f"{weight}%\n"
        lines.append(row)
    lines.append(f"  {'TOTAL (weighted)':<25} | ")
    for opt in scored_options:
        lines[-1] += f"{opt.get('weighted_score', 0):>8.2f} | "
    lines[-1] += "\n"

    lines.append(f"\n**Opportunity Cost:**\n  {opportunity_cost}\n")

    lines.append(
        f"\n→ Next step: `define_transition_states` — describe the transition phases."
    )

    return "".join(lines)


@mcp.tool()
def define_transition_states(
    project_id: str,
    phase_number: int,
    phase_name: str,
    duration_months: int,
    capabilities_delivered: str,
    gaps_closed: str,
    risks_remaining: str,
    value_realizable: str,
) -> str:
    """
    Step 6 of the 6.4 pipeline: describe a transition state (phase).

    Call this for each phase. For big_bang — a single phase.
    For phased — 2-5 phases. Each phase should deliver standalone value.

    Args:
        project_id: Project identifier
        phase_number: Phase number (1, 2, 3...)
        phase_name: Phase name (e.g. "Pilot: basic CRM")
        duration_months: Phase duration in months
        capabilities_delivered: JSON list of capability names delivered in this phase
        gaps_closed: JSON list of gap names closed by the end of this phase
        risks_remaining: JSON list of RK-xxx risks that remain active after this phase
        value_realizable: Value realized by the end of the phase (for the sponsor)
    """
    try:
        caps = json.loads(capabilities_delivered) if capabilities_delivered.strip() else []
    except json.JSONDecodeError:
        return "❌ Error parsing capabilities_delivered. Must be a JSON array of strings."

    try:
        gaps = json.loads(gaps_closed) if gaps_closed.strip() else []
    except json.JSONDecodeError:
        gaps = []

    try:
        risks = json.loads(risks_remaining) if risks_remaining.strip() else []
    except json.JSONDecodeError:
        risks = []

    if phase_number <= 0:
        return "❌ phase_number must be > 0"
    if duration_months <= 0:
        return "❌ duration_months must be > 0"
    if not phase_name.strip():
        return "❌ phase_name cannot be empty"
    if not value_realizable.strip():
        return "⚠️ value_realizable is not filled in — every phase should deliver concrete value."

    transition_state = {
        "phase": phase_number,
        "name": phase_name,
        "duration_months": duration_months,
        "capabilities_delivered": caps,
        "gaps_closed": gaps,
        "risks_remaining": risks,
        "value_realizable": value_realizable,
    }

    strategy = _load_strategy(project_id)
    states = strategy.get("transition_states", [])

    # Replace if this phase was already defined
    states = [s for s in states if s.get("phase") != phase_number]
    states.append(transition_state)
    states.sort(key=lambda s: s.get("phase", 0))
    strategy["transition_states"] = states

    _save_strategy(strategy, project_id)

    total_caps = sum(len(s.get("capabilities_delivered", [])) for s in states)
    total_months = sum(s.get("duration_months", 0) for s in states)

    risks_note = ""
    if risks:
        risks_note = f"\n  Remaining risks: {', '.join(risks)}"

    return (
        f"✅ Phase {phase_number} recorded\n\n"
        f"  Name:          {phase_name}\n"
        f"  Duration:      {duration_months} mo.\n"
        f"  Capabilities:  {len(caps)}\n"
        f"  Gaps closed:   {len(gaps)}\n"
        f"{risks_note}\n"
        f"  Value:         {value_realizable[:80]}{'...' if len(value_realizable) > 80 else ''}\n\n"
        f"  Total phases defined: {len(states)} | "
        f"Total: {total_caps} capabilities, {total_months} mo.\n\n"
        f"→ Add the next phase or call `save_change_strategy` to finalize."
    )


@mcp.tool()
def save_change_strategy(
    project_id: str,
    push_to_traceability: bool = False,
    traceability_project_id: str = "",
) -> str:
    """
    Step 7 of the 6.4 pipeline: finalize the change strategy.

    Saves {project}_change_strategy.json (a contract for 7.x, 8.x) and generates
    a Markdown report via save_artifact. Optionally registers the solution in
    the 5.1 repository as a 'solution'-type node with 'satisfies' links.

    Args:
        project_id: Project identifier
        push_to_traceability: Register the solution in the 5.1 repository (default: False)
        traceability_project_id: project_id of the 5.1 repository (if different from the main one)
    """
    strategy = _load_strategy(project_id)
    scope = strategy.get("solution_scope", {})
    readiness = strategy.get("enterprise_readiness", {})
    cs = strategy.get("change_strategy", {})
    states = strategy.get("transition_states", [])

    capabilities = scope.get("capabilities", [])
    selected_id = cs.get("selected_option_id")
    options = cs.get("options", [])

    if not capabilities:
        return "⚠️ Solution scope is not defined. Call `define_solution_scope`."
    if not selected_id:
        return "⚠️ No strategy option selected. Call `compare_strategy_options`."
    if not readiness:
        return "⚠️ Readiness assessment is not filled in. Call `assess_enterprise_readiness`."
    if not states:
        return "⚠️ Transition states are not defined. Call `define_transition_states`."

    selected_option = next((o for o in options if o.get("option_id") == selected_id), None)
    if not selected_option:
        return f"⚠️ Selected option {selected_id} not found in the register."

    # --- Optional push to the 5.1 traceability repository (ADR-082) ---
    traceability_notes = []
    if push_to_traceability:
        repo_pid = traceability_project_id or project_id
        repo_path = _repo_path(project_id, repo_pid)
        if os.path.exists(repo_path):
            with open(repo_path, encoding="utf-8") as f:
                repo = json.load(f)

            existing_ids = {r["id"] for r in repo.get("requirements", [])}
            sol_id = "SOL-001"

            # solution node
            if sol_id not in existing_ids:
                repo.setdefault("requirements", []).append({
                    "id": sol_id,
                    "type": "solution",
                    "title": f"Solution Scope — {project_id}",
                    "version": "1.0",
                    "status": "approved",
                    "added": str(date.today()),
                })
                existing_ids.add(sol_id)
                traceability_notes.append(f"✅ Node {sol_id} (solution) added to 5.1")

            # satisfies links to business_goals
            added_links = 0
            bg_list = strategy.get("imported_context", {}).get("business_goals", [])
            for bg in bg_list:
                bg_id = bg.get("id", "")
                if bg_id and bg_id in existing_ids:
                    repo.setdefault("links", []).append({
                        "from": sol_id,
                        "to": bg_id,
                        "relation": "satisfies",
                        "rationale": f"Solution scope fulfills {bg_id}",
                        "added": str(date.today()),
                    })
                    added_links += 1

            if added_links:
                traceability_notes.append(f"✅ Added {added_links} satisfies links → BG")

            repo["updated"] = str(date.today())
            with open(repo_path, "w", encoding="utf-8") as f:
                json.dump(repo, f, ensure_ascii=False, indent=2)
        else:
            traceability_notes.append(
                f"⚠️ 5.1 traceability repository not found for '{repo_pid}' "
                f"— push skipped. Initialize the repository first."
            )

    # --- Markdown report ---
    verdict = readiness.get("verdict", "")
    readiness_score = readiness.get("readiness_score", 0)
    excluded = scope.get("explicitly_excluded", [])
    in_scope_caps = [c for c in capabilities if c.get("in_scope", True)]

    md_lines = [
        f"# Change Strategy — {project_id}",
        f"**Date:** {date.today()}  ",
        f"**Change type:** {strategy.get('scope', {}).get('change_type', '')}  ",
        f"**Horizon:** {strategy.get('scope', {}).get('time_horizon_months', '')} months  ",
        f"**Methodology:** {strategy.get('scope', {}).get('methodology', '')}",
        "",
        "---",
        "",
        "## Selected Strategy",
        "",
        f"**{selected_id} — {selected_option.get('name', '')}**",
        f"- Type: {selected_option.get('strategy_type', '')}",
        f"- Investment: {selected_option.get('investment_level', '')}",
        f"- Implementation timeline: {selected_option.get('timeline_months', '')} mo.",
        f"- Weighted Score: {selected_option.get('weighted_score', 'N/A')}",
        "",
    ]

    if selected_option.get("pros"):
        md_lines.append("**Pros:**")
        for p in selected_option["pros"]:
            md_lines.append(f"- {p}")
        md_lines.append("")

    if selected_option.get("cons"):
        md_lines.append("**Risks / drawbacks:**")
        for c in selected_option["cons"]:
            md_lines.append(f"- {c}")
        md_lines.append("")

    if cs.get("opportunity_cost"):
        md_lines.extend([
            "**Opportunity Cost:**",
            cs["opportunity_cost"],
            "",
        ])

    # Rejected alternatives
    rejected = cs.get("rejected_alternatives", [])
    if rejected:
        md_lines.extend(["## Rejected Options", ""])
        for rej in rejected:
            rej_opt = next((o for o in options if o.get("option_id") == rej["option_id"]), {})
            md_lines.append(
                f"- **{rej['option_id']} — {rej.get('name', '')}** "
                f"(score: {rej.get('weighted_score', 'N/A')}): {rej.get('rationale', '')}"
            )
        md_lines.append("")

    md_lines.extend([
        "---",
        "",
        "## Solution Scope",
        "",
        f"**Capabilities ({len(in_scope_caps)}):**",
        "",
    ])

    cats = {}
    for cap in in_scope_caps:
        cats.setdefault(cap["category"], []).append(cap)
    for cat, caps_list in sorted(cats.items()):
        md_lines.append(f"### {cat}")
        for cap in caps_list:
            gap_icon = {"high": "🔴", "medium": "🟡", "low": "🟢", "none": "⚪"}.get(cap["gap_severity"], "")
            md_lines.append(
                f"- {cap['name']} {gap_icon} gap:{cap['gap_severity']} | {cap.get('description', '')}"
            )
        md_lines.append("")

    if excluded:
        md_lines.extend(["**Explicitly out of scope:**", ""])
        for ex in excluded:
            md_lines.append(f"- {ex}")
        md_lines.append("")

    md_lines.extend([
        "---",
        "",
        "## Enterprise Readiness",
        "",
        f"**Readiness Score: {readiness_score:.1f} / 5.0 — {verdict}**",
        "",
    ])

    dims = readiness.get("dimensions", {})
    dim_labels = {
        "leadership_commitment": "Leadership commitment",
        "cultural_readiness": "Cultural readiness",
        "resource_availability": "Resource availability",
        "operational_readiness": "Operational readiness",
        "technical_readiness": "Technical readiness",
        "change_history": "Change history",
    }
    for dim, data in dims.items():
        sc = data.get("score", "?")
        rat = data.get("rationale", "")
        md_lines.append(f"- {dim_labels.get(dim, dim)}: {sc}/5" + (f" — {rat}" if rat else ""))
    md_lines.append("")

    if states:
        md_lines.extend([
            "---",
            "",
            "## Transition States",
            "",
        ])
        for st in states:
            md_lines.extend([
                f"### Phase {st['phase']}: {st['name']} ({st.get('duration_months', 0)} mo.)",
                "",
            ])
            if st.get("capabilities_delivered"):
                md_lines.append("**Capabilities:**")
                for cap in st["capabilities_delivered"]:
                    md_lines.append(f"- {cap}")
            if st.get("gaps_closed"):
                md_lines.append("\n**Gaps closed:**")
                for g in st["gaps_closed"]:
                    md_lines.append(f"- {g}")
            if st.get("risks_remaining"):
                md_lines.append(f"\n**Remaining risks:** {', '.join(st['risks_remaining'])}")
            md_lines.extend([
                f"\n**Value:** {st.get('value_realizable', '')}",
                "",
            ])

    md_content = "\n".join(md_lines)
    artifact_result = save_artifact(md_content, f"6_4_change_strategy_{_safe(project_id)}", project_id=project_id)

    # Finalize the JSON
    strategy["status"] = "finalized"
    strategy["finalized_on"] = str(date.today())
    _save_strategy(strategy, project_id)

    json_path = _strategy_path(project_id)
    total_months = sum(s.get("duration_months", 0) for s in states)

    output = [
        f"✅ Change strategy finalized\n\n",
        f"  Project:    {project_id}\n",
        f"  Strategy:   {selected_id} — {selected_option.get('name', '')}\n",
        f"  Type:       {selected_option.get('strategy_type', '')}\n",
        f"  Phases:     {len(states)} | Total timeline: {total_months} mo.\n",
        f"  Readiness:  {readiness_score:.1f}/5.0 — {verdict}\n\n",
        f"  📄 JSON (for 7.x, 8.x): `{json_path}`\n",
        artifact_result, "\n",
    ]

    if traceability_notes:
        output.extend(["\n"] + traceability_notes + ["\n"])

    output.append(
        f"\n**Next steps:**\n"
        f"• 7.1 Specify Requirements → scope from `solution_scope.capabilities`\n"
        f"• 7.4 Define Requirements Architecture → phases from `transition_states`\n"
        f"• 7.5 Define Design Options → selected option + rejected alternatives\n"
    )

    if verdict != "ready":
        weak = [(d, v["score"]) for d, v in dims.items() if v["score"] <= 2]
        if weak:
            output.append(
                f"\n⚠️ Pay attention to the low readiness dimensions: "
                + ", ".join(f"{d}={s}" for d, s in weak)
                + " — prepare a mitigation plan before kickoff.\n"
            )

    return "".join(output)


if __name__ == "__main__":
    mcp.run()
