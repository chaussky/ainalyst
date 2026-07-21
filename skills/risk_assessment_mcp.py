"""
BABOK 6.3 — Assess Risks
MCP tools for assessing the risks of an initiative.

Tools:
  - scope_risk_assessment         — scope: initiative type, depth, sources
  - import_risks_from_context     — draft risks from 6.1, 6.2, 4.2
  - add_risk                      — add/confirm a risk in the register
  - set_risk_tolerance            — tolerance level + max_acceptable_score
  - run_risk_matrix               — zone matrix, cumulative profile
  - generate_recommendation       — recommendation type + narrative
  - save_risk_assessment          — finalize: JSON + Markdown + opt. push to 5.1

Storage:
  - {project}_risk_assessment_scope.json  — scope
  - {project}_risk_assessment.json        — risk register (contract for 6.4)
  - {project}_risk_assessment_*.md        — report (via save_artifact)

Integration:
  In: 6.1 (current_state, business_needs), 6.2 (future_state, gap_analysis), 4.2 (elicitation)
  Out: risk_assessment.json → 6.4; risk + threatens nodes → 5.1 (optional)

ADR-070: hybrid storage (own JSON + optional push to 5.1)
ADR-071: import_risks_from_context — draft mode
ADR-072: 1-5 x 1-5 scale, Low/Medium/High zones
ADR-073: generate_recommendation — hybrid approach (logic + Claude narrative)
ADR-074: node type `risk` and relation `threatens` in the 5.1 repository
ADR-075: risk card structure (14 fields)
ADR-076: export format for 6.4

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
from datetime import date, datetime
from typing import Literal, Optional
from mcp.server.fastmcp import FastMCP
from skills.common import save_artifact, logger, DATA_DIR, data_path, normalize_project_id

mcp = FastMCP("BABOK_RiskAssessment")

SCOPE_FILENAME = "risk_assessment_scope.json"
ASSESSMENT_FILENAME = "risk_assessment.json"
REPO_FILENAME = "traceability_repo.json"

# 6.1 files (optional source)
CS_STATE_FILENAME = "current_state.json"
CS_NEEDS_FILENAME = "business_needs.json"

# 6.2 files (optional source)
FS_STATE_FILENAME = "future_state.json"
GAP_FILENAME = "gap_analysis.json"

# 4.2 files (optional source)
ELICITATION_FILENAME = "elicitation_results.json"

VALID_CATEGORIES = ["strategic", "operational", "financial", "technical", "regulatory", "people", "external"]
VALID_SOURCES = ["change", "current_state", "future_state", "requirement", "stakeholder", "assumption", "constraint"]
VALID_STRATEGIES = ["accept", "mitigate", "transfer", "avoid"]
VALID_HORIZONS = ["immediate", "short_term", "medium_term", "long_term"]
VALID_TOLERANCE = ["risk_averse", "neutral", "risk_seeking"]
VALID_DEPTH = ["quick", "standard", "comprehensive"]
VALID_INITIATIVE_TYPES = ["process_improvement", "new_system", "regulatory", "cost_reduction", "market_opportunity", "other"]

ZONE_LABELS = {
    "low": "🟢 Low",
    "medium": "🟡 Medium",
    "high": "🔴 High",
}


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _safe(project_id: str) -> str:
    return normalize_project_id(project_id)


def _scope_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{SCOPE_FILENAME}")


def _assessment_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{ASSESSMENT_FILENAME}")


def _repo_path(project_id: str, repo_project_id: Optional[str] = None) -> str:
    pid = repo_project_id or project_id
    return data_path(pid, f"{_safe(pid)}_{REPO_FILENAME}")


def _cs_state_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{CS_STATE_FILENAME}")


def _cs_needs_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{CS_NEEDS_FILENAME}")


def _fs_state_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{FS_STATE_FILENAME}")


def _gap_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{GAP_FILENAME}")


def _elicitation_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{ELICITATION_FILENAME}")


def _load_assessment(project_id: str) -> dict:
    path = _assessment_path(project_id)
    if not os.path.exists(path):
        return _empty_assessment(project_id)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_assessment(data: dict, project_id: str):
    os.makedirs(os.path.dirname(_assessment_path(project_id)), exist_ok=True)
    data["updated"] = str(date.today())
    with open(_assessment_path(project_id), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _empty_assessment(project_id: str) -> dict:
    return {
        "project_id": project_id,
        "created": str(date.today()),
        "updated": str(date.today()),
        "scope": {},
        "risk_tolerance": {
            "level": "neutral",
            "max_acceptable_score": 15,
            "organization_context": "",
            "sponsor_risk_appetite": "",
            "mandatory_avoid_categories": [],
            "escalation_threshold": 15,
        },
        "risks": [],
        "risk_matrix": {},
        "cumulative_profile": {},
        "recommendation": {},
    }


def _next_risk_id(risks: list) -> str:
    if not risks:
        return "RK-001"
    existing_nums = []
    for r in risks:
        rid = r.get("risk_id", "")
        if rid.startswith("RK-") and rid[3:].isdigit():
            existing_nums.append(int(rid[3:]))
    if not existing_nums:
        return "RK-001"
    return f"RK-{max(existing_nums) + 1:03d}"


def _zone_for_score(score: int, max_acceptable: int) -> str:
    if score >= max_acceptable:
        return "high"
    elif score >= 6:
        return "medium"
    else:
        return "low"


def _safe_load_json(path: str) -> Optional[dict]:
    """Loads JSON, returns None if the file is not found or corrupted."""
    if not os.path.exists(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, IOError):
        return None
    # The return type says dict and every caller immediately does `.get(...)`, but a
    # JSON file may legally hold a list or a scalar at the top level. A file corrupted
    # into a list would raise AttributeError in all five import branches at once.
    return data if isinstance(data, dict) else None


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def scope_risk_assessment(
    project_id: str,
    initiative_type: Literal["process_improvement", "new_system", "regulatory", "cost_reduction", "market_opportunity", "other"],
    analysis_depth: Literal["quick", "standard", "comprehensive"],
    source_project_ids: str = "[]",
    ba_notes: str = "",
) -> str:
    """
    Step 1 of the 6.3 pipeline: lock in the scope of the risk assessment.

    Determines the initiative type, analysis depth, and data sources.
    Sources (6.1, 6.2, 4.2) are used in import_risks_from_context.

    Args:
        project_id: Project identifier
        initiative_type: Initiative type (process_improvement/new_system/regulatory/cost_reduction/market_opportunity/other)
        analysis_depth: Analysis depth (quick=3-5 risks / standard=7-15 / comprehensive=15-30)
        source_project_ids: JSON list of project_id from 6.1/6.2 for auto-import, e.g. '["crm_upgrade"]'
        ba_notes: Additional context or constraints
    """
    try:
        source_ids = json.loads(source_project_ids) if source_project_ids.strip() else []
    except json.JSONDecodeError:
        return "❌ Error: source_project_ids must be a JSON array, e.g. '[\"crm\"]'"

    scope = {
        "project_id": project_id,
        "initiative_type": initiative_type,
        "analysis_depth": analysis_depth,
        "source_project_ids": source_ids,
        "ba_notes": ba_notes,
        "created": str(date.today()),
    }

    os.makedirs(os.path.dirname(_scope_path(project_id)), exist_ok=True)
    with open(_scope_path(project_id), "w", encoding="utf-8") as f:
        json.dump(scope, f, ensure_ascii=False, indent=2)

    # Initialize an empty risk register
    assessment = _load_assessment(project_id)
    assessment["scope"] = scope
    _save_assessment(assessment, project_id)

    depth_guide = {
        "quick": "3-5 risks (key threats, ~1 hour)",
        "standard": "7-15 risks (core analysis, ~2-3 hours)",
        "comprehensive": "15-30 risks (full analysis, ~half a day)",
    }

    sources_hint = ""
    if source_ids:
        sources_hint = f"\n  Sources for import: {', '.join(source_ids)}"
        sources_hint += "\n  → Call `import_risks_from_context` to automatically collect drafts"
    else:
        sources_hint = "\n  No 6.1/6.2 sources specified → add risks manually via `add_risk`"

    return (
        f"✅ Risk assessment scope locked in\n\n"
        f"  Project:    {project_id}\n"
        f"  Initiative: {initiative_type}\n"
        f"  Depth:      {analysis_depth} — {depth_guide[analysis_depth]}\n"
        f"{sources_hint}\n\n"
        f"**Next step:** `import_risks_from_context` (if 6.1/6.2 data exists) "
        f"or go straight to `add_risk` for the first risk."
    )


@mcp.tool()
def import_risks_from_context(
    project_id: str,
    source_project_ids: str = "[]",
) -> str:
    """
    Step 2 of the 6.3 pipeline: collect draft risks from 6.1, 6.2, 4.2 artifacts.

    Scans available artifacts and proposes draft risks with status 'draft'.
    The BA reviews the drafts and confirms the relevant ones via add_risk.
    Graceful degradation: missing artifacts are skipped with a warning.

    Args:
        project_id: Project identifier
        source_project_ids: JSON list of project_id to scan (default: the current project)
    """
    try:
        source_ids = json.loads(source_project_ids) if source_project_ids.strip() else []
    except json.JSONDecodeError:
        source_ids = []

    if not source_ids:
        source_ids = [project_id]

    drafts = []
    warnings = []

    for src_id in source_ids:
        # --- 6.2: constraints ---
        fs_data = _safe_load_json(_fs_state_path(src_id))
        if fs_data:
            constraints = fs_data.get("constraints", [])
            for c in constraints:
                desc = c.get("description", "")
                category = c.get("category", "")
                if desc:
                    # 6.2 and 6.3 name the same idea differently. `capture_constraints`
                    # offers budget/time/technology/policy/resources/compliance/other —
                    # `regulatory` is not in that vocabulary at all, so comparing
                    # against it meant a compliance constraint always became an
                    # `operational` risk. That is the one category an analyst is most
                    # likely to put in `mandatory_avoid_categories`, so the
                    # misclassification quietly cost the constraint its override.
                    _CONSTRAINT_TO_RISK_CATEGORY = {
                        "compliance": "regulatory",
                        "regulatory": "regulatory",
                        "policy": "regulatory",
                        "budget": "financial",
                        "time": "operational",
                        "technology": "technical",
                        "resources": "operational",
                    }
                    risk_cat = _CONSTRAINT_TO_RISK_CATEGORY.get(
                        str(category).strip().lower(), "operational")
                    drafts.append({
                        "status": "draft",
                        "import_source": f"6.2 constraint ({src_id})",
                        "category": risk_cat,
                        "source": "constraint",
                        "description": f"If the constraint “{desc}” is not overcome, then the project goals may not be achieved",
                        "likelihood": 3,
                        "impact": 3,
                        "response_strategy": "mitigate",
                    })
        else:
            warnings.append(f"⚠️ 6.2 future_state not found for '{src_id}' — skipping")

        # --- 6.2: gap analysis ---
        gap_data = _safe_load_json(_gap_path(src_id))
        if gap_data:
            gaps = gap_data.get("gaps", [])
            for g in gaps:
                complexity = g.get("complexity", "")
                element = g.get("element", g.get("name", ""))
                if complexity == "high" and element:
                    drafts.append({
                        "status": "draft",
                        "import_source": f"6.2 gap_analysis ({src_id})",
                        "category": "technical",
                        "source": "future_state",
                        "description": f"If the gap in the “{element}” element turns out harder than expected, then the transition to the future state will be delayed",
                        "likelihood": 3,
                        "impact": 4,
                        "response_strategy": "mitigate",
                    })

        # --- 6.1: root causes ---
        cs_data = _safe_load_json(_cs_state_path(src_id))
        if cs_data:
            # 6.1 stores root_causes at the TOP level; each record's cause is `root_cause`.
            root_causes = cs_data.get("root_causes", [])
            for rc in root_causes:
                desc = rc if isinstance(rc, str) else rc.get("root_cause", rc.get("description", ""))
                if desc:
                    drafts.append({
                        "status": "draft",
                        "import_source": f"6.1 root_cause_analysis ({src_id})",
                        "category": "operational",
                        "source": "current_state",
                        "description": f"If the root cause “{desc}” is not eliminated during the project, then the problem will resurface",
                        "likelihood": 2,
                        "impact": 3,
                        "response_strategy": "mitigate",
                    })
        else:
            warnings.append(f"⚠️ 6.1 current_state not found for '{src_id}' — skipping")

        # --- 6.1: high-priority business needs ---
        needs_data = _safe_load_json(_cs_needs_path(src_id))
        if needs_data:
            # 6.1 stores needs under `needs`; title is `need_title`; priority is capitalized.
            needs = needs_data.get("needs", [])
            for need in needs:
                if str(need.get("priority", "")).lower() in ("high", "critical"):
                    bn_id = need.get("id", "BN-?")
                    title = need.get("need_title", need.get("title", need.get("description", "")))
                    if title:
                        drafts.append({
                            "status": "draft",
                            "import_source": f"6.1 business_needs ({src_id})",
                            "category": "strategic",
                            "source": "current_state",
                            "description": f"If business need {bn_id} “{title}” is not delivered in full, then the expected value will not be achieved",
                            "likelihood": 2,
                            "impact": 4,
                            "response_strategy": "mitigate",
                            "linked_bn": bn_id,
                        })

        # --- 4.2: risks mentioned by stakeholders ---
        elicitation_data = _safe_load_json(_elicitation_path(src_id))
        if elicitation_data:
            risks_mentioned = elicitation_data.get("risks_mentioned", [])
            for rm in risks_mentioned:
                if isinstance(rm, dict):
                    desc = rm.get("description", rm.get("risk", ""))
                    stakeholder = rm.get("stakeholder", rm.get("source", "stakeholder"))
                else:
                    desc = str(rm)
                    stakeholder = "stakeholder"
                if desc:
                    drafts.append({
                        "status": "draft",
                        "import_source": f"4.2 elicitation ({src_id})",
                        "category": "operational",
                        "source": "stakeholder",
                        "description": f"A stakeholder ({stakeholder}) flagged a risk: {desc}",
                        "likelihood": 3,
                        "impact": 3,
                        "response_strategy": "mitigate",
                    })
        else:
            warnings.append(
                f"⚠️ 4.2 elicitation results not found for '{src_id}' — skipping "
                f"(run `process_elicitation_results` with `risks_json` to produce it)"
            )

    if not drafts and not warnings:
        return (
            "ℹ️ No data found in the import sources.\n\n"
            "Possible reasons:\n"
            "  • 6.1/6.2 artifacts are not filled in yet\n"
            "  • project_id does not match the one specified in source_project_ids\n\n"
            "→ Add risks manually via `add_risk`."
        )

    # Save the drafts into the assessment
    assessment = _load_assessment(project_id)
    existing_drafts = [r for r in assessment["risks"] if r.get("status") == "draft"]
    # Clear old drafts and add the new ones
    assessment["risks"] = [r for r in assessment["risks"] if r.get("status") != "draft"]
    assessment["risks"].extend(drafts)
    _save_assessment(assessment, project_id)

    lines = [f"✅ Imported risk drafts: {len(drafts)}\n"]

    if warnings:
        lines.append("**Warnings:**")
        lines.extend(warnings)
        lines.append("")

    lines.append("**Drafts (require confirmation via `add_risk`):**\n")
    for i, d in enumerate(drafts, 1):
        lines.append(
            f"{i}. [{d['category']}] {d['description'][:100]}{'...' if len(d['description']) > 100 else ''}\n"
            f"   Source: {d['import_source']} | Default: L={d['likelihood']} × I={d['impact']} → score {d['likelihood'] * d['impact']}\n"
        )

    lines.append(
        "\n**Next step:** call `add_risk` for each relevant draft "
        "(you can adjust the ratings). Skip the irrelevant ones."
    )

    return "\n".join(lines)


@mcp.tool()
def add_risk(
    project_id: str,
    category: Literal["strategic", "operational", "financial", "technical", "regulatory", "people", "external"],
    source: Literal["change", "current_state", "future_state", "requirement", "stakeholder", "assumption", "constraint"],
    description: str,
    likelihood: int,
    impact: int,
    response_strategy: Literal["accept", "mitigate", "transfer", "avoid"],
    likelihood_rationale: str = "",
    impact_rationale: str = "",
    time_horizon: str = "",
    mitigation_plan: str = "",
    owner: str = "",
    linked_bn: str = "",
    linked_bg: str = "",
    linked_req: str = "",
) -> str:
    """
    Step 3 of the 6.3 pipeline: add a risk to the register.

    Automatically assigns a risk_id (RK-001...) and computes risk_score = likelihood x impact.
    Used both for confirming drafts from import_risks_from_context
    and for adding new risks.

    Args:
        project_id: Project identifier
        category: Risk category (strategic/operational/financial/technical/regulatory/people/external)
        source: Risk source (change/current_state/future_state/requirement/stakeholder/assumption/constraint)
        description: Description in "If X, then Y" format
        likelihood: Likelihood 1-5 (1=<10%, 2=10-30%, 3=30-60%, 4=60-80%, 5=>80%)
        impact: Impact 1-5 (1=Negligible, 2=Minor, 3=Moderate, 4=Major, 5=Critical)
        response_strategy: Response strategy (accept/mitigate/transfer/avoid)
        likelihood_rationale: Rationale for the likelihood rating
        impact_rationale: Rationale for the impact rating
        time_horizon: Risk horizon (immediate/short_term/medium_term/long_term)
        mitigation_plan: Mitigation plan (required when strategy=mitigate)
        owner: stakeholder_id from the 3.2 registry
        linked_bn: Business need ID (BN-xxx)
        linked_bg: Business goal ID (BG-xxx)
        linked_req: Requirement ID (FR-xxx, BR-xxx...)
    """
    # Validation
    if not 1 <= likelihood <= 5:
        return f"❌ likelihood must be between 1 and 5, got: {likelihood}"
    if not 1 <= impact <= 5:
        return f"❌ impact must be between 1 and 5, got: {impact}"
    if response_strategy == "mitigate" and not mitigation_plan:
        return "⚠️ When strategy=mitigate, it is recommended to fill in mitigation_plan"

    assessment = _load_assessment(project_id)

    # Remove drafts with a matching description (draft confirmation)
    assessment["risks"] = [
        r for r in assessment["risks"]
        if not (r.get("status") == "draft" and r.get("description", "")[:80] == description[:80])
    ]

    risk_id = _next_risk_id([r for r in assessment["risks"] if r.get("status") != "draft"])
    score = likelihood * impact

    risk = {
        "risk_id": risk_id,
        "category": category,
        "source": source,
        "description": description,
        "likelihood": likelihood,
        "likelihood_rationale": likelihood_rationale,
        "impact": impact,
        "impact_rationale": impact_rationale,
        "risk_score": score,
        "time_horizon": time_horizon,
        "response_strategy": response_strategy,
        "mitigation_plan": mitigation_plan,
        "owner": owner,
        "linked_bn": linked_bn,
        "linked_bg": linked_bg,
        "linked_req": linked_req,
        "status": "identified",
        "added": str(date.today()),
    }

    assessment["risks"].append(risk)
    _save_assessment(assessment, project_id)

    # Determine a preliminary zone (before set_risk_tolerance, there may be no tolerance yet)
    max_acc = assessment.get("risk_tolerance", {}).get("max_acceptable_score", 15)
    zone = _zone_for_score(score, max_acc)
    zone_label = ZONE_LABELS[zone]

    total_identified = len([r for r in assessment["risks"] if r.get("status") == "identified"])

    warn = ""
    if response_strategy == "mitigate" and not mitigation_plan:
        warn = "\n  ⚠️ It is recommended to add a mitigation_plan"

    return (
        f"✅ Risk added: {risk_id}\n\n"
        f"  Category:    {category}\n"
        f"  Description: {description[:80]}{'...' if len(description) > 80 else ''}\n"
        f"  Rating:      L={likelihood} × I={impact} = score {score} {zone_label}\n"
        f"  Strategy:    {response_strategy}\n"
        f"{warn}\n"
        f"  Total risks in the register: {total_identified}\n\n"
        f"→ Keep going with `add_risk` or move on to `set_risk_tolerance`."
    )


@mcp.tool()
def set_risk_tolerance(
    project_id: str,
    tolerance_level: Literal["risk_averse", "neutral", "risk_seeking"],
    max_acceptable_score: int = 15,
    organization_context: str = "",
    sponsor_risk_appetite: str = "",
    mandatory_avoid_categories: str = "[]",
    escalation_threshold: int = 0,
) -> str:
    """
    Step 4 of the 6.3 pipeline: set the risk tolerance.

    Defines the strategic stance and the numeric threshold for High risks.
    Risks with score >= max_acceptable_score are considered High and require active response.

    Args:
        project_id: Project identifier
        tolerance_level: Tolerance level (risk_averse/neutral/risk_seeking)
        max_acceptable_score: High-risk threshold (1-25). Risks >= threshold = High. Default: 15
        organization_context: Organizational context (industry, specifics)
        sponsor_risk_appetite: Sponsor's stance (direct quote or interpretation)
        mandatory_avoid_categories: JSON list of categories that always → avoid, e.g. '["regulatory"]'
        escalation_threshold: Score for escalation to the sponsor (0 = equal to max_acceptable_score)
    """
    if not 1 <= max_acceptable_score <= 25:
        return f"❌ max_acceptable_score must be between 1 and 25, got: {max_acceptable_score}"

    try:
        avoid_cats = json.loads(mandatory_avoid_categories) if mandatory_avoid_categories.strip() else []
    except json.JSONDecodeError:
        avoid_cats = []

    esc_threshold = escalation_threshold if escalation_threshold > 0 else max_acceptable_score

    assessment = _load_assessment(project_id)
    assessment["risk_tolerance"] = {
        "level": tolerance_level,
        "max_acceptable_score": max_acceptable_score,
        "organization_context": organization_context,
        "sponsor_risk_appetite": sponsor_risk_appetite,
        "mandatory_avoid_categories": avoid_cats,
        "escalation_threshold": esc_threshold,
        "set_on": str(date.today()),
    }
    _save_assessment(assessment, project_id)

    # Calibration hints
    hints = {
        "risk_averse": "Recommended threshold range: 10–12. All Medium+ risks require an active plan.",
        "neutral": "Recommended threshold range: 14–16. Standard corporate approach.",
        "risk_seeking": "Recommended threshold range: 18–20. Speed and opportunity matter more than predictability.",
    }

    avoid_note = ""
    if avoid_cats:
        avoid_note = f"\n  Mandatory avoid: {', '.join(avoid_cats)}"

    return (
        f"✅ Risk tolerance set\n\n"
        f"  Level:               {tolerance_level}\n"
        f"  High-risk threshold: score ≥ {max_acceptable_score} → 🔴 High\n"
        f"  Escalation threshold: score ≥ {esc_threshold} → requires a conversation with the sponsor\n"
        f"{avoid_note}\n\n"
        f"  {hints[tolerance_level]}\n\n"
        f"→ Next step: `run_risk_matrix` to classify all risks."
    )


@mcp.tool()
def run_risk_matrix(project_id: str) -> str:
    """
    Step 5 of the 6.3 pipeline: build the risk matrix and cumulative profile.

    Classifies all risks into zones (Low/Medium/High) based on tolerance,
    and computes the cumulative profile. The result is used in generate_recommendation.

    Args:
        project_id: Project identifier
    """
    assessment = _load_assessment(project_id)
    identified_risks = [r for r in assessment["risks"] if r.get("status") == "identified"]

    if not identified_risks:
        return (
            "⚠️ The risk register is empty. Add at least one risk via `add_risk` before running the matrix."
        )

    tolerance = assessment.get("risk_tolerance", {})
    max_acc = tolerance.get("max_acceptable_score", 15)
    mandatory_avoid = tolerance.get("mandatory_avoid_categories", [])

    classified = []
    for r in identified_risks:
        score = r.get("risk_score", r.get("likelihood", 1) * r.get("impact", 1))
        # mandatory_avoid overrides the strategy
        if r.get("category") in mandatory_avoid and r.get("response_strategy") != "avoid":
            zone = "high"
            note = " ⚠️ category is in mandatory_avoid — strategy should be avoid"
        else:
            note = ""
            zone = _zone_for_score(score, max_acc)

        # Write the zone back onto the STORED risk, not only into this copy.
        #
        # The zone is a decision, not a restatement of the score: it honours the
        # analyst's `max_acceptable_score` and forces any category in
        # `mandatory_avoid_categories` to high regardless of the number. Keeping it
        # only in `risk_matrix.classified_risks` meant every consumer —
        # generate_recommendation, the 6.3 report itself, and 6.4 scope_change_strategy
        # — fell back to `_zone_for_score(raw)` and silently lost the override, so the
        # summary table and the sections below it could disagree about the same risk.
        r["zone"] = zone
        r["zone_note"] = note
        classified.append({**r, "zone": zone, "zone_note": note})

    high_risks = [r for r in classified if r["zone"] == "high"]
    medium_risks = [r for r in classified if r["zone"] == "medium"]
    low_risks = [r for r in classified if r["zone"] == "low"]

    total_score = sum(r.get("risk_score", 0) for r in classified)
    avg_score = total_score / len(classified) if classified else 0

    cumulative_profile = {
        "total_risks": len(classified),
        "high_risks_count": len(high_risks),
        "medium_risks_count": len(medium_risks),
        "low_risks_count": len(low_risks),
        "above_threshold": len(high_risks),
        "total_score": total_score,
        "avg_score": round(avg_score, 1),
        "max_acceptable_score": max_acc,
    }

    assessment["risk_matrix"] = {
        "classified_risks": classified,
        "run_on": str(date.today()),
    }
    assessment["cumulative_profile"] = cumulative_profile
    _save_assessment(assessment, project_id)

    # --- Output formatting ---
    lines = [
        f"✅ Risk matrix built\n",
        f"  Total risks: {len(classified)} | High threshold: score ≥ {max_acc}\n",
        f"  🔴 High: {len(high_risks)} | 🟡 Medium: {len(medium_risks)} | 🟢 Low: {len(low_risks)}\n",
        f"  Total score: {total_score} | Average: {avg_score:.1f}\n",
    ]

    if high_risks:
        lines.append("\n**🔴 High risks (require immediate attention):**\n")
        for r in sorted(high_risks, key=lambda x: -x["risk_score"]):
            lines.append(
                f"  {r['risk_id']} [{r['category']}] score={r['risk_score']} "
                f"(L={r['likelihood']}×I={r['impact']}) — {r['description'][:70]}...\n"
                f"    Strategy: {r['response_strategy']}"
                + (f"{r.get('zone_note', '')}" if r.get("zone_note") else "") + "\n"
            )

    if medium_risks:
        lines.append("\n**🟡 Medium risks:**\n")
        for r in sorted(medium_risks, key=lambda x: -x["risk_score"]):
            lines.append(
                f"  {r['risk_id']} [{r['category']}] score={r['risk_score']} — "
                f"{r['description'][:60]}...\n"
            )

    if low_risks:
        lines.append(f"\n**🟢 Low risks:** {len(low_risks)} (details in JSON)\n")

    lines.append(
        f"\n→ Next step: `generate_recommendation` to produce a recommendation for the sponsor."
    )

    return "".join(lines)


@mcp.tool()
def generate_recommendation(
    project_id: str,
    potential_value_summary: str = "",
    value_vs_risk: Literal["", "value_exceeds_risk", "comparable", "risk_exceeds_value"] = "",
) -> str:
    """
    Step 6 of the 6.3 pipeline: generate a recommendation (type + narrative).

    Deterministic logic determines the recommendation type per ADR-073.
    Claude writes a 2-4 sentence narrative with concrete data.

    Args:
        project_id: Project identifier
        potential_value_summary: Short description of the expected value from 6.2 (if not filled in automatically)
        value_vs_risk: The BA's judgement on whether the expected value justifies the
            cumulative risk exposure. ADR-073 defines `seek_higher_value` for
            "potential value < cumulative risk exposure", but that comparison has no
            honest arithmetic here: 6.2 states value qualitatively, and the cumulative
            exposure is a sum of 1-25 risk scores — the units are not comparable, so a
            numeric comparison would be false precision. The trade-off is therefore a
            judgement the BA makes explicitly (the precise numeric version lives in 7.6,
            which scores value against a risk penalty).
            - "risk_exceeds_value" → recommendation `seek_higher_value`
            - "" (default) → the type is decided by the risk logic alone, as before.
    """
    assessment = _load_assessment(project_id)
    profile = assessment.get("cumulative_profile", {})
    tolerance = assessment.get("risk_tolerance", {})
    risks = [r for r in assessment.get("risks", []) if r.get("status") == "identified"]

    if not profile:
        return "⚠️ Run `run_risk_matrix` first — a cumulative profile is needed."

    max_acc = tolerance.get("max_acceptable_score", 15)
    tol_level = tolerance.get("level", "neutral")
    high_count = profile.get("high_risks_count", 0)
    total_score = profile.get("total_score", 0)
    total_risks = profile.get("total_risks", 0)

    # Attempt to auto-load potential_value from 6.2
    if not potential_value_summary:
        scope = assessment.get("scope", {})
        for src_id in scope.get("source_project_ids", [project_id]):
            fs_data = _safe_load_json(_fs_state_path(src_id))
            if fs_data:
                pv = fs_data.get("potential_value") or {}
                # 6.2 `assess_potential_value` stores the analyst's text under
                # `value_summary`. Reading `summary`/`description` — neither of which
                # that producer ever writes — meant the sponsor recommendation never
                # once mentioned the value the analyst had assessed, while the
                # truthy-dict check made the miss silent and stopped the search.
                # Legacy spellings stay accepted.
                summary = (pv.get("value_summary") or pv.get("summary")
                           or pv.get("description") or "")
                if summary:
                    potential_value_summary = summary
                    break

    # --- Deterministic type-selection logic ---
    high_risks = [r for r in risks if r.get("zone", _zone_for_score(r.get("risk_score", 0), max_acc)) == "high"]
    critical_without_mitigation = [
        r for r in high_risks
        if r.get("impact") == 5 and r.get("response_strategy") == "accept" and not r.get("mitigation_plan")
    ]

    # ADR-073 order: an unresolvable critical risk outranks everything; otherwise, if
    # the BA judges the exposure to outweigh the value, the answer is to revisit scope
    # rather than to proceed. Without that judgement the type follows the risk logic alone.
    if critical_without_mitigation:
        rec_type = "do_not_proceed"
    elif value_vs_risk == "risk_exceeds_value":
        rec_type = "seek_higher_value"
    elif not high_risks:
        rec_type = "proceed_despite_risk"
    else:
        rec_type = "proceed_with_mitigation"

    # Type descriptions
    rec_descriptions = {
        "proceed_despite_risk": "Proceed without additional measures",
        "proceed_with_mitigation": "Proceed while implementing the risk mitigation plans",
        "seek_higher_value": "Revisit the scope or approach to increase value",
        "do_not_proceed": "Do not proceed until the critical risks are resolved",
    }

    # Top-3 High risks for the narrative
    top_risks = sorted(high_risks, key=lambda x: -x.get("risk_score", 0))[:3]
    top_risk_summary = "; ".join([
        f"{r['risk_id']} (score {r['risk_score']}, {r['response_strategy']})"
        for r in top_risks
    ]) or "none"

    mitigation_risks = [r for r in high_risks if r.get("response_strategy") == "mitigate"]

    recommendation = {
        "type": rec_type,
        "description": rec_descriptions[rec_type],
        "value_vs_risk": value_vs_risk or "not_assessed",
        "high_risks_addressed": len(mitigation_risks),
        "rationale": (
            f"Of {total_risks} identified risks, {high_count} are in the High zone "
            f"(score ≥ {max_acc}). Cumulative risk profile: {total_score}. "
            f"Key High risks: {top_risk_summary}. "
            f"Organizational tolerance: {tol_level}. "
            + (f"Expected value: {potential_value_summary}. " if potential_value_summary else "")
            + (
                "The BA judged the cumulative risk exposure to outweigh the expected value. "
                if value_vs_risk == "risk_exceeds_value" else ""
            )
            + (
                f"Once the {len(mitigation_risks)} mitigation plans are executed, the risk profile will decrease."
                if rec_type == "proceed_with_mitigation" else ""
            )
        ),
        "generated_on": str(date.today()),
    }

    assessment["recommendation"] = recommendation
    _save_assessment(assessment, project_id)

    rec_emoji = {
        "proceed_despite_risk": "🟢",
        "proceed_with_mitigation": "🟡",
        "seek_higher_value": "🟠",
        "do_not_proceed": "🔴",
    }

    output = [
        f"✅ Recommendation generated\n\n",
        f"  {rec_emoji.get(rec_type, '◯')} **{rec_type}** — {rec_descriptions[rec_type]}\n\n",
        f"  **Rationale:** {recommendation['rationale']}\n\n",
    ]

    if rec_type == "proceed_with_mitigation" and top_risks:
        output.append("  **Priority actions (High risks):**\n")
        for r in top_risks:
            plan = r.get("mitigation_plan", "—")
            output.append(f"  • {r['risk_id']}: {plan[:80]}\n")

    if rec_type == "do_not_proceed":
        output.append(
            "\n  ⚠️ Recommendation 'do_not_proceed' — a critical outcome.\n"
            "  Immediate escalation to the sponsor is required.\n"
        )

    if rec_type == "seek_higher_value":
        output.append(
            "\n  🟠 The risks are manageable, but you judged them to outweigh the expected value.\n"
            "  Revisit scope or approach in 6.4 (`add_strategy_option`) to raise the value,\n"
            "  or narrow the scope so the exposure drops.\n"
        )

    if not value_vs_risk and high_risks:
        output.append(
            "\n  ℹ️ Value vs risk was not assessed. With High risks present, state whether the\n"
            "  expected value still justifies the exposure: pass `value_vs_risk=` \n"
            "  (value_exceeds_risk / comparable / risk_exceeds_value).\n"
        )

    output.append(
        f"\n→ Next step: `save_risk_assessment` to finalize and generate the report."
    )

    return "".join(output)


@mcp.tool()
def save_risk_assessment(
    project_id: str,
    push_to_traceability: bool = False,
    traceability_project_id: str = "",
) -> str:
    """
    Step 7 of the 6.3 pipeline: finalize the risk assessment.

    Saves {project}_risk_assessment.json (input for 6.4) and generates
    a Markdown report via save_artifact. Optionally registers risks
    in the 5.1 repository as 'risk'-type nodes with 'threatens' links.

    Args:
        project_id: Project identifier
        push_to_traceability: Register risks in the 5.1 repository (default: False)
        traceability_project_id: project_id of the 5.1 repository (if different from the main one)
    """
    assessment = _load_assessment(project_id)
    risks = [r for r in assessment.get("risks", []) if r.get("status") == "identified"]
    profile = assessment.get("cumulative_profile", {})
    tolerance = assessment.get("risk_tolerance", {})
    recommendation = assessment.get("recommendation", {})

    if not risks:
        return "⚠️ The risk register is empty. Add at least one risk via `add_risk`."
    if not recommendation:
        return "⚠️ Call `generate_recommendation` first."

    # --- Optional push to 5.1 traceability ---
    traceability_notes = []
    if push_to_traceability:
        repo_pid = traceability_project_id or project_id
        repo_path = _repo_path(project_id, repo_pid)
        if os.path.exists(repo_path):
            with open(repo_path, encoding="utf-8") as f:
                repo = json.load(f)

            existing_ids = {r["id"] for r in repo.get("requirements", [])}
            # Existing threatens edges — so a re-run (re-finalize) does not duplicate them.
            existing_threatens = {
                (l.get("from"), l.get("to"))
                for l in repo.get("links", [])
                if l.get("relation") == "threatens"
            }
            added_nodes = 0
            added_links = 0
            missing_targets = []

            for risk in risks:
                rid = risk["risk_id"]
                if rid not in existing_ids:
                    repo.setdefault("requirements", []).append({
                        "id": rid,
                        "type": "risk",
                        "title": risk["description"][:80],
                        "version": "1.0",
                        "status": risk.get("status", "identified"),
                        "added": str(date.today()),
                    })
                    existing_ids.add(rid)
                    added_nodes += 1

                # threatens links (deduplicated by from/to so re-runs don't pile up)
                for linked_field in ["linked_bn", "linked_bg", "linked_req"]:
                    linked_id = risk.get(linked_field, "")
                    if linked_id and linked_id not in existing_ids:
                        # The existence check is right, but reporting only the count
                        # made its effect invisible: "+0 threatens links" beside a ✅
                        # reads as success, when in fact every target was missing.
                        missing_targets.append((rid, linked_id))
                        continue
                    if linked_id and linked_id in existing_ids and (rid, linked_id) not in existing_threatens:
                        repo.setdefault("links", []).append({
                            "from": rid,
                            "to": linked_id,
                            "relation": "threatens",
                            "rationale": f"Risk threatens {linked_id}",
                            "added": str(date.today()),
                        })
                        existing_threatens.add((rid, linked_id))
                        added_links += 1

            repo["updated"] = str(date.today())
            with open(repo_path, "w", encoding="utf-8") as f:
                json.dump(repo, f, ensure_ascii=False, indent=2)

            traceability_notes.append(
                f"✅ 5.1 traceability updated: +{added_nodes} risk nodes, +{added_links} threatens links"
            )
            if missing_targets:
                # Without this the analyst reads "+0 links" as "nothing needed doing".
                pairs = ", ".join(f"`{r}` → `{t}`" for r, t in missing_targets[:5])
                more = f" (+{len(missing_targets) - 5} more)" if len(missing_targets) > 5 else ""
                traceability_notes.append(
                    f"⚠️ {len(missing_targets)} link(s) NOT written — the target is not a "
                    f"node in the 5.1 repository: {pairs}{more}.\n"
                    f"   Register the objective or requirement first, then re-run the push."
                )
        else:
            traceability_notes.append(
                f"⚠️ 5.1 traceability repository not found for '{repo_pid}' "
                f"— push skipped. Initialize the repository first via `init_traceability_repo`."
            )

    # --- Markdown report ---
    high_risks = [r for r in risks if r.get("zone", _zone_for_score(r.get("risk_score", 0), tolerance.get("max_acceptable_score", 15))) == "high"]
    medium_risks = [r for r in risks if r.get("zone", _zone_for_score(r.get("risk_score", 0), tolerance.get("max_acceptable_score", 15))) == "medium"]
    low_risks = [r for r in risks if r.get("zone", _zone_for_score(r.get("risk_score", 0), tolerance.get("max_acceptable_score", 15))) == "low"]

    rec_type = recommendation.get("type", "")
    rec_emoji = {"proceed_despite_risk": "🟢", "proceed_with_mitigation": "🟡", "seek_higher_value": "🟠", "do_not_proceed": "🔴"}

    md_lines = [
        f"# Risk Assessment — {project_id}",
        f"**Date:** {date.today()}  ",
        f"**Tolerance:** {tolerance.get('level', 'neutral')} | High threshold: {tolerance.get('max_acceptable_score', 15)}",
        "",
        "---",
        "",
        "## Summary",
        "",
        f"| Parameter | Value |",
        f"|----------|---------|",
        f"| Total risks | {profile.get('total_risks', len(risks))} |",
        f"| 🔴 High | {profile.get('high_risks_count', len(high_risks))} |",
        f"| 🟡 Medium | {profile.get('medium_risks_count', len(medium_risks))} |",
        f"| 🟢 Low | {profile.get('low_risks_count', len(low_risks))} |",
        f"| Total score | {profile.get('total_score', 0)} |",
        f"| Average score | {profile.get('avg_score', 0)} |",
        "",
        f"## Recommendation",
        "",
        f"{rec_emoji.get(rec_type, '◯')} **{rec_type}** — {recommendation.get('description', '')}",
        "",
        f"{recommendation.get('rationale', '')}",
        "",
        "---",
        "",
        "## Risk Register",
        "",
    ]

    def _risks_section(title: str, risk_list: list) -> list:
        if not risk_list:
            return []
        out = [f"### {title}", ""]
        for r in sorted(risk_list, key=lambda x: -x.get("risk_score", 0)):
            out.extend([
                f"#### {r['risk_id']} — {r['description'][:60]}",
                f"- **Category:** {r['category']} | **Source:** {r['source']}",
                f"- **Rating:** L={r['likelihood']} × I={r['impact']} = score {r['risk_score']}",
                f"- **Strategy:** {r['response_strategy']}",
            ])
            if r.get("mitigation_plan"):
                out.append(f"- **Mitigation plan:** {r['mitigation_plan']}")
            if r.get("owner"):
                out.append(f"- **Owner:** {r['owner']}")
            out.append("")
        return out

    md_lines.extend(_risks_section("🔴 High Risks", high_risks))
    md_lines.extend(_risks_section("🟡 Medium Risks", medium_risks))
    md_lines.extend(_risks_section("🟢 Low Risks", low_risks))

    md_content = "\n".join(md_lines)
    artifact_result = save_artifact(md_content, f"6_3_risk_assessment_{_safe(project_id)}", project_id=project_id)

    # Finalize the JSON
    assessment["status"] = "finalized"
    assessment["finalized_on"] = str(date.today())
    _save_assessment(assessment, project_id)

    json_path = _assessment_path(project_id)

    output = [
        f"✅ Risk assessment finalized\n\n",
        f"  Project: {project_id}\n",
        f"  Risks: {len(risks)} | High: {len(high_risks)} | Medium: {len(medium_risks)} | Low: {len(low_risks)}\n",
        f"  Recommendation: {rec_emoji.get(rec_type, '')} {rec_type}\n\n",
        f"  📄 JSON (for 6.4): `{json_path}`\n",
        artifact_result, "\n",
    ]

    if traceability_notes:
        output.extend(["\n"] + traceability_notes)

    output.append(
        f"\n\n**Next step:**\n"
        f"• For the sponsor: provide the Markdown report\n"
        f"• For 6.4 Define Change Strategy: hand off `{json_path}`\n"
    )
    if high_risks:
        output.append(f"• Priority: assign owners for {len(high_risks)} High risks\n")

    return "".join(output)


if __name__ == "__main__":
    mcp.run()
