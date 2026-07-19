"""
BABOK 3 — Business Analysis Planning and Monitoring
MCP tools for business analysis planning.

Tools:
  - suggest_ba_approach           — 3.1: choose a methodology (Predictive/Agile/Hybrid)
  - plan_stakeholder_engagement   — 3.2: Power/Interest stakeholder matrix + communication plan
  - plan_ba_governance            — 3.3: governance: change control, approval, escalation
  - plan_information_management   — 3.4: artifact storage and traceability architecture
  - evaluate_ba_performance       — 3.5: BA performance metrics + improvement plan

Storage:
  - {project}_ba_plan.json        — single JSON document with all plan sections
  - {project}_ba_plan_*.md        — Markdown report (via save_artifact)

Integration:
  Output: ba_plan.json → used in 4.x (stakeholder_registry),
         7.3 (business_context), 5.5 (governance for approval)

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
import os
from datetime import date
from typing import Literal, Optional
from mcp.server.fastmcp import FastMCP
from skills.common import (
    save_artifact, logger, DATA_DIR, data_path, normalize_project_id,
    APPROACH_MATRIX, REGULATORY_OVERRIDE, QUADRANT_STRATEGIES,
)

mcp = FastMCP("BABOK_Planning")

PLAN_FILENAME = "ba_plan.json"

# ---------------------------------------------------------------------------
# Templates (the APPROACH_MATRIX, REGULATORY_OVERRIDE, QUADRANT_STRATEGIES
# matrices live in common.py — single source of truth, ADR-REVIEW-5)
# ---------------------------------------------------------------------------

_GOVERNANCE_TEMPLATES = {
    "High": {
        "change_control": "Formal: Change Request (CR) → assessment → CAB approval",
        "approval":       "Requires sign-off from Sponsor + Product Owner",
        "review_cycle":   "Weekly status + formal review on every CR",
        "escalation":     "BA → PM → Steering Committee",
    },
    "Medium": {
        "change_control": "Adaptive: PO approves changes via the Backlog",
        "approval":       "Product Owner + Lead BA",
        "review_cycle":   "Bi-weekly review, retrospectives",
        "escalation":     "BA → PO → PM",
    },
    "Low": {
        "change_control": "Minimal: logged in Jira, verbal sign-off",
        "approval":       "Lead BA",
        "review_cycle":   "On request",
        "escalation":     "BA → PM",
    },
}

_TRACEABILITY_LEVELS = {
    "High":   "Full traceability: Business goals → Requirements → Test cases → Code",
    "Medium": "Requirements linked to Jira tickets and test cases",
    "Low":    "Basic: requirement numbering, links as needed",
}

_ISSUE_RECOMMENDATIONS = {
    "no templates":        "📋 Adopt standard requirement templates (SRS, User Story template)",
    "slow approval":       "⚡ Shorten the approval chain, delegate to PO",
    "conflicts":           "🔍 Introduce mandatory peer review of requirements before handoff to development",
    "weak traceability":   "🔗 Set up traceability in Jira: Epic → Story → Test",
    "no metrics":          "📊 Introduce BA quality metrics: Defect Rate, Rework Rate, Requirement Stability",
    "onboarding":          "🎓 Create a BA playbook and a project knowledge base",
    "no documentation":    "📝 Create a single versioned artifact repository",
    "scope creep":         "🎯 Strengthen governance: formalize the CR process via 5.4",
}


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _safe(project_id: str) -> str:
    return normalize_project_id(project_id)


def _plan_path(project_id: str) -> str:
    return data_path(project_id, f"{_safe(project_id)}_{PLAN_FILENAME}")


def _load_plan(project_id: str) -> dict:
    path = _plan_path(project_id)
    if not os.path.exists(path):
        return _empty_plan(project_id)
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save_plan(data: dict, project_id: str):
    path = _plan_path(project_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    data["updated"] = str(date.today())
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def _empty_plan(project_id: str) -> dict:
    return {
        "project_id": project_id,
        "created": str(date.today()),
        "updated": str(date.today()),
        "ba_approach": {},
        "stakeholder_engagement": {},
        "governance": {},
        "information_management": {},
        "performance": {},
    }


_LIST_EXAMPLE = '["Sponsor", "Product Owner"]'


def _parse_json_list(raw: str, field: str, required: bool = False) -> tuple:
    """Parses a JSON array. Returns (values, error_message).

    Shared by every Ch3 tool that takes a list, so the validation cannot drift apart
    between siblings. Malformed input is REPORTED, never silently coerced or dropped:
    swallowing it makes the tool answer about data the BA never actually supplied.
    """
    text = (raw or "").strip()
    if not text:
        if required:
            return [], f"❌ {field} is required. Expected a JSON array, e.g. '{_LIST_EXAMPLE}'."
        return [], ""

    try:
        value = json.loads(text)
    except json.JSONDecodeError as e:
        return [], (f"❌ Error parsing {field}: {e}\n"
                    f"Expected a JSON array, e.g. '{_LIST_EXAMPLE}'.")

    if not isinstance(value, list):
        return [], (f"❌ {field} must be a JSON array, got {type(value).__name__}. "
                    f"Example: '{_LIST_EXAMPLE}'.")

    if required and not value:
        return [], f"❌ {field} must be a non-empty JSON array."

    return value, ""


def _parse_string_list(raw: str, field: str, required: bool = False) -> tuple:
    """Parses a JSON array of strings. Returns (values, error_message).

    A list holding objects/numbers is a caller mistake (easy to make, since sibling
    parameters like metrics_json DO take objects). Rejecting it here keeps the failure
    a readable message instead of a TypeError escaping the tool at render time.
    """
    values, error = _parse_json_list(raw, field, required=required)
    if error:
        return [], error

    bad = next((v for v in values if not isinstance(v, str)), None)
    if bad is not None:
        return [], (f"❌ {field} must contain only strings — got "
                    f"{type(bad).__name__}: {json.dumps(bad, ensure_ascii=False)[:60]}. "
                    f"Example: '{_LIST_EXAMPLE}'.")
    return values, ""


def _classify_stakeholder(influence: str, interest: str) -> tuple:
    """Returns (quadrant, strategy, frequency) per the Power/Interest matrix."""
    key = (influence, interest)
    return QUADRANT_STRATEGIES.get(key, ("Crowd", "Monitor", "Quarterly"))


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool()
def suggest_ba_approach(
    project_id: str,
    change_frequency: Literal["Low", "Medium", "High"],
    uncertainty: Literal["Low", "Medium", "High"],
    regulatory_need: bool = False,
    ba_notes: str = "",
) -> str:
    """
    BABOK 3.1 — Determine the business analysis approach (Predictive / Agile / Hybrid).

    Selects a methodology from the BABOK matrix based on change frequency and uncertainty.
    Applies a compliance override when regulatory_need=True.
    Saves the decision to {project}_ba_plan.json, section 'ba_approach'.

    Args:
        project_id: Project identifier
        change_frequency: Expected frequency of requirement changes (Low/Medium/High)
        uncertainty: Level of project uncertainty (Low/Medium/High)
        regulatory_need: True if the project requires strict compliance/audit
        ba_notes: Additional context from the BA
    """
    approach, techniques = APPROACH_MATRIX.get(
        (change_frequency, uncertainty),
        ("Hybrid", ["Workshops", "Prioritization"])
    )

    original_approach = approach
    regulatory_note = ""
    if regulatory_need and approach in REGULATORY_OVERRIDE:
        approach = REGULATORY_OVERRIDE[approach]
        regulatory_note = f"\n  ⚠️ Regulatory override: {original_approach} → {approach}"

    plan = _load_plan(project_id)
    plan["ba_approach"] = {
        "change_frequency": change_frequency,
        "uncertainty": uncertainty,
        "regulatory_need": regulatory_need,
        "recommended_approach": approach,
        "techniques": techniques,
        "ba_notes": ba_notes,
        "decided_on": str(date.today()),
    }
    _save_plan(plan, project_id)

    approach_hints = {
        "Predictive (Waterfall)": "Clear requirements from the start. Document thoroughly.",
        "Hybrid": "Combine planning and flexibility. Plan phases, adapt within them.",
        "Adaptive (Agile)": "Work iteratively. User stories + backlog + retrospectives.",
        "Hybrid (Agile + compliance gates)": "Agile cadence + formal sign-off points for audit.",
        "Hybrid (with strengthened governance)": "Hybrid approach + stronger change control.",
    }
    hint = approach_hints.get(approach, "")

    return (
        f"✅ BA approach recorded\n\n"
        f"  Project:         {project_id}\n"
        f"  Change frequency: {change_frequency}\n"
        f"  Uncertainty:       {uncertainty}\n"
        f"  Regulatory:        {'Yes' if regulatory_need else 'No'}"
        f"{regulatory_note}\n\n"
        f"  **Recommended approach: {approach}**\n"
        f"  BABOK techniques: {', '.join(techniques)}\n\n"
        f"  💡 {hint}\n\n"
        f"→ Next step: `plan_stakeholder_engagement` — build the stakeholder map."
    )


@mcp.tool()
def plan_stakeholder_engagement(
    project_id: str,
    stakeholders_json: str,
) -> str:
    """
    BABOK 3.2 — Build the stakeholder engagement matrix (Power/Interest Grid).

    Classifies each stakeholder into a quadrant (Key Players / Context Setters /
    Subjects / Crowd) and assigns a strategy and communication frequency.
    Saves the registry to {project}_ba_plan.json, section 'stakeholder_engagement'.

    Args:
        project_id: Project identifier
        stakeholders_json: JSON array of stakeholders. Object format:
            {
              "name": "John Smith",
              "role": "Product Owner",
              "influence": "High",
              "interest": "High",
              "attitude": "Champion",
              "contact": "john@company.com"
            }
            influence/interest: Low | Medium | High
            attitude: Champion | Neutral | Blocker
    """
    try:
        stakeholders = json.loads(stakeholders_json)
    except json.JSONDecodeError as e:
        return f"❌ Error parsing stakeholders_json: {e}\n\nExpected a JSON array of objects."

    if not isinstance(stakeholders, list):
        return "❌ stakeholders_json must be a JSON array."

    if not stakeholders:
        return "⚠️ Stakeholder list is empty. Add at least one stakeholder."

    valid = []
    errors = []
    for i, s in enumerate(stakeholders):
        name = s.get("name", "")
        influence = s.get("influence", "")
        interest = s.get("interest", "")
        if not name:
            errors.append(f"Stakeholder #{i+1}: missing 'name' field")
            continue
        if influence not in ("Low", "Medium", "High"):
            errors.append(f"'{name}': influence must be Low/Medium/High, got '{influence}'")
            continue
        if interest not in ("Low", "Medium", "High"):
            errors.append(f"'{name}': interest must be Low/Medium/High, got '{interest}'")
            continue
        quadrant, strategy, frequency = _classify_stakeholder(influence, interest)
        valid.append({
            "name": name,
            "role": s.get("role", ""),
            "influence": influence,
            "interest": interest,
            "attitude": s.get("attitude", "Neutral"),
            "contact": s.get("contact", ""),
            "quadrant": quadrant,
            "strategy": strategy,
            "comm_frequency": frequency,
        })

    if errors:
        return "❌ Errors in stakeholders_json:\n" + "\n".join(f"  • {e}" for e in errors)

    plan = _load_plan(project_id)
    plan["stakeholder_engagement"] = {
        "stakeholders": valid,
        "total": len(valid),
        "updated_on": str(date.today()),
    }
    _save_plan(plan, project_id)

    # Quadrant statistics
    quadrants = {}
    for s in valid:
        q = s["quadrant"]
        quadrants[q] = quadrants.get(q, 0) + 1

    blockers = [s["name"] for s in valid if s.get("attitude") == "Blocker"]

    lines = [
        f"✅ Stakeholder registry saved\n\n",
        f"  Project:          {project_id}\n",
        f"  Stakeholders:     {len(valid)}\n\n",
        f"**Quadrant distribution:**\n",
    ]
    for q, cnt in sorted(quadrants.items()):
        lines.append(f"  {q}: {cnt}\n")

    lines.append("\n**Registry:**\n")
    for s in valid:
        lines.append(
            f"  • {s['name']} ({s['role']}) — {s['quadrant']} | {s['comm_frequency']}\n"
            f"    Strategy: {s['strategy']}\n"
        )

    if blockers:
        lines.append(f"\n⚠️ Blockers: {', '.join(blockers)} — require special attention\n")

    lines.append(
        f"\n→ Next step: `plan_ba_governance` — define decision-making rules."
    )
    return "".join(lines)


@mcp.tool()
def plan_ba_governance(
    project_id: str,
    project_criticality: Literal["Low", "Medium", "High"],
    decision_makers_json: str,
    change_control_process: str = "",
    ba_notes: str = "",
) -> str:
    """
    BABOK 3.3 — Define the business analysis governance plan.

    Records change control, approval, and escalation procedures.
    Project criticality determines the level of formalization.
    Saves to {project}_ba_plan.json, section 'governance'.

    Args:
        project_id: Project identifier
        project_criticality: Project criticality (Low/Medium/High)
        decision_makers_json: JSON list of decision-making roles, e.g. '["Sponsor", "PO", "Lead BA"]'
        change_control_process: Description of the change control process (optional — filled from a template)
        ba_notes: Additional agreements
    """
    decision_makers, error = _parse_string_list(
        decision_makers_json, "decision_makers_json", required=True)
    if error:
        return error

    tpl = _GOVERNANCE_TEMPLATES.get(project_criticality, _GOVERNANCE_TEMPLATES["Medium"])

    governance = {
        "project_criticality": project_criticality,
        "decision_makers": decision_makers,
        "change_control": change_control_process or tpl["change_control"],
        "approval_process": tpl["approval"],
        "review_cycle": tpl["review_cycle"],
        "escalation_path": tpl["escalation"],
        "ba_notes": ba_notes,
        "defined_on": str(date.today()),
    }

    plan = _load_plan(project_id)
    plan["governance"] = governance
    _save_plan(plan, project_id)

    criticality_hints = {
        "High": "⚠️ High criticality: formalize every CR, change nothing without sign-off.",
        "Medium": "📋 Medium criticality: standard process via PO/backlog.",
        "Low": "✅ Low criticality: flexible process, record only key decisions.",
    }

    return (
        f"✅ Governance plan recorded\n\n"
        f"  Project:            {project_id}\n"
        f"  Criticality:        {project_criticality}\n"
        f"  Decision makers:    {', '.join(decision_makers)}\n\n"
        f"  Change control:     {governance['change_control']}\n"
        f"  Approval:           {governance['approval_process']}\n"
        f"  Review cycle:       {governance['review_cycle']}\n"
        f"  Escalation:         {governance['escalation_path']}\n\n"
        f"  {criticality_hints.get(project_criticality, '')}\n\n"
        f"→ Next step: `plan_information_management` — define the storage architecture."
    )


@mcp.tool()
def plan_information_management(
    project_id: str,
    storage_tools_json: str,
    traceability_level: Literal["Low", "Medium", "High"] = "Medium",
    artifact_types_json: str = "[]",
    access_rules: str = "",
    ba_notes: str = "",
) -> str:
    """
    BABOK 3.4 — Plan business analysis information management.

    Defines where and how requirements and artifacts are stored, and the traceability level.
    Saves to {project}_ba_plan.json, section 'information_management'.

    Args:
        project_id: Project identifier
        storage_tools_json: JSON list of storage tools, e.g. '["Confluence", "Jira", "GitHub"]'
        traceability_level: Traceability level (Low/Medium/High)
        artifact_types_json: JSON list of artifact types, e.g. '["User Story", "BRD", "Test Case"]'
        access_rules: Access rules (who reads, who edits)
        ba_notes: Additional agreements
    """
    storage_tools, error = _parse_string_list(
        storage_tools_json, "storage_tools_json", required=True)
    if error:
        return error

    artifact_types, error = _parse_string_list(artifact_types_json, "artifact_types_json")
    if error:
        return error

    trace_desc = _TRACEABILITY_LEVELS.get(traceability_level, _TRACEABILITY_LEVELS["Medium"])

    info_mgmt = {
        "storage_tools": storage_tools,
        "traceability_level": traceability_level,
        "traceability_description": trace_desc,
        "artifact_types": artifact_types,
        "access_rules": access_rules or "BA edits, others read",
        "ba_notes": ba_notes,
        "defined_on": str(date.today()),
    }

    plan = _load_plan(project_id)
    plan["information_management"] = info_mgmt
    _save_plan(plan, project_id)

    artifacts_note = ""
    if artifact_types:
        artifacts_note = f"  Artifact types:    {', '.join(artifact_types)}\n"

    return (
        f"✅ Information management plan recorded\n\n"
        f"  Project:           {project_id}\n"
        f"  Tools:             {', '.join(storage_tools)}\n"
        f"  Traceability:      {traceability_level} — {trace_desc}\n"
        f"{artifacts_note}"
        f"  Access:            {info_mgmt['access_rules']}\n\n"
        f"→ Next step: `evaluate_ba_performance` — set performance metrics."
    )


@mcp.tool()
def evaluate_ba_performance(
    project_id: str,
    current_issues_json: str = "[]",
    metrics_json: str = "[]",
    ba_notes: str = "",
) -> str:
    """
    BABOK 3.5 — Evaluate BA performance and build an improvement plan.

    Matches identified issues with recommendations, records metrics.
    Saves to {project}_ba_plan.json, section 'performance'.

    Args:
        project_id: Project identifier
        current_issues_json: JSON list of current issues, e.g. '["no templates", "scope creep"]'
        metrics_json: JSON list of metrics to monitor, e.g.
            '[{"name": "Defect Rate", "baseline": "15%", "target": "5%"}]'
        ba_notes: Additional context
    """
    current_issues, error = _parse_string_list(current_issues_json, "current_issues_json")
    if error:
        return error

    # metrics entries may be objects ({name, baseline, target}) or plain strings
    metrics, error = _parse_json_list(metrics_json, "metrics_json")
    if error:
        return error

    # Match issues to recommendations
    recommendations = []
    unmatched = []
    for issue in current_issues:
        matched = False
        for keyword, rec in _ISSUE_RECOMMENDATIONS.items():
            if keyword.lower() in issue.lower():
                recommendations.append({"issue": issue, "recommendation": rec})
                matched = True
                break
        if not matched:
            unmatched.append(issue)
            recommendations.append({
                "issue": issue,
                "recommendation": f"⚠️ Requires manual analysis: «{issue}»"
            })

    if not current_issues:
        recommendations.append({
            "issue": "no explicit issues",
            "recommendation": "✅ Hold a retrospective once per quarter as a preventive measure."
        })

    performance = {
        "current_issues": current_issues,
        "recommendations": recommendations,
        "metrics": metrics,
        "ba_notes": ba_notes,
        "assessed_on": str(date.today()),
    }

    plan = _load_plan(project_id)
    plan["performance"] = performance
    _save_plan(plan, project_id)

    lines = [
        f"✅ BA performance assessment recorded\n\n",
        f"  Project:  {project_id}\n",
        f"  Issues:   {len(current_issues)}\n",
        f"  Metrics:  {len(metrics)}\n\n",
    ]

    if recommendations:
        lines.append("**Improvement recommendations:**\n")
        for r in recommendations:
            lines.append(f"  {r['recommendation']}\n")

    if metrics:
        lines.append("\n**Metrics to monitor:**\n")
        for m in metrics:
            if isinstance(m, dict):
                name = m.get("name", "")
                baseline = m.get("baseline", "")
                target = m.get("target", "")
                lines.append(f"  • {name}: {baseline} → {target}\n")
            else:
                lines.append(f"  • {m}\n")

    lines.append(
        f"\n→ BA plan for project `{project_id}` is ready.\n"
        f"  Call `save_ba_plan` to generate the Markdown report."
    )
    return "".join(lines)


@mcp.tool()
def save_ba_plan(
    project_id: str,
) -> str:
    """
    Finalize the BA plan: generate the Markdown report.

    Builds a readable document from all sections of {project}_ba_plan.json
    via save_artifact(). The JSON remains the contract for downstream tasks.

    Args:
        project_id: Project identifier
    """
    plan = _load_plan(project_id)

    approach = plan.get("ba_approach", {})
    engagement = plan.get("stakeholder_engagement", {})
    governance = plan.get("governance", {})
    info_mgmt = plan.get("information_management", {})
    performance = plan.get("performance", {})

    # `performance` counts too: the report renders a 3.5 section when it is present,
    # so omitting it here refused a plan that actually had content.
    if not any([approach, engagement, governance, info_mgmt, performance]):
        return (
            "⚠️ BA plan is empty or not filled in.\n"
            "Complete steps 3.1-3.5 before saving the report."
        )

    md_lines = [
        f"# BA Plan — {project_id}",
        f"**Date:** {date.today()}",
        "",
        "---",
        "",
    ]

    if approach:
        md_lines += [
            "## 3.1 Business Analysis Approach",
            "",
            f"| Parameter | Value |",
            f"|----------|---------|",
            f"| Change frequency | {approach.get('change_frequency', '')} |",
            f"| Uncertainty | {approach.get('uncertainty', '')} |",
            f"| Regulatory | {'Yes' if approach.get('regulatory_need') else 'No'} |",
            f"| **Recommended approach** | **{approach.get('recommended_approach', '')}** |",
            f"| BABOK techniques | {', '.join(approach.get('techniques', []))} |",
            "",
        ]

    if engagement:
        stakeholders = engagement.get("stakeholders", [])
        md_lines += [
            "## 3.2 Stakeholder Engagement",
            "",
            f"| Stakeholder | Role | Quadrant | Strategy | Frequency |",
            f"|-------------|------|----------|-----------|---------|",
        ]
        for s in stakeholders:
            md_lines.append(
                f"| {s['name']} | {s['role']} | {s['quadrant']} | {s['strategy']} | {s['comm_frequency']} |"
            )
        md_lines.append("")

    if governance:
        md_lines += [
            "## 3.3 Governance",
            "",
            f"| Parameter | Value |",
            f"|----------|---------|",
            f"| Criticality | {governance.get('project_criticality', '')} |",
            f"| Decision makers | {', '.join(governance.get('decision_makers', []))} |",
            f"| Change control | {governance.get('change_control', '')} |",
            f"| Approval | {governance.get('approval_process', '')} |",
            f"| Review cycle | {governance.get('review_cycle', '')} |",
            f"| Escalation | {governance.get('escalation_path', '')} |",
            "",
        ]

    if info_mgmt:
        md_lines += [
            "## 3.4 Information Management",
            "",
            f"- **Tools:** {', '.join(info_mgmt.get('storage_tools', []))}",
            f"- **Traceability:** {info_mgmt.get('traceability_level', '')} — {info_mgmt.get('traceability_description', '')}",
            f"- **Access:** {info_mgmt.get('access_rules', '')}",
            "",
        ]

    if performance:
        recs = performance.get("recommendations", [])
        md_lines += ["## 3.5 BA Performance", ""]
        for r in recs:
            md_lines.append(f"- {r['recommendation']}")
        md_lines.append("")
        metrics = performance.get("metrics", [])
        if metrics:
            md_lines.append("**Metrics:**")
            for m in metrics:
                if isinstance(m, dict):
                    md_lines.append(f"- {m.get('name', '')}: {m.get('baseline', '')} → {m.get('target', '')}")
                else:
                    md_lines.append(f"- {m}")
            md_lines.append("")

    md_content = "\n".join(md_lines)
    artifact_result = save_artifact(md_content, f"3_ba_plan_{_safe(project_id)}", project_id=project_id)

    plan["status"] = "finalized"
    plan["finalized_on"] = str(date.today())
    _save_plan(plan, project_id)

    json_path = _plan_path(project_id)

    return (
        f"✅ BA plan finalized\n\n"
        f"  Project: {project_id}\n"
        f"  📄 JSON (for 4.x, 5.5): `{json_path}`\n"
        f"  {artifact_result}\n\n"
        f"**Next step:**\n"
        f"• Chapter 4.1 — prepare for elicitation (stakeholder registry ready)\n"
        f"• Chapter 5.5 — governance context is passed automatically\n"
    )


if __name__ == "__main__":
    mcp.run()
