"""
BABOK 3 — Business Analysis Planning and Monitoring
MCP tools for business analysis planning.

Tools:
  - suggest_ba_approach           — 3.1: choose a methodology (Predictive/Agile/Hybrid)
  - plan_stakeholder_engagement   — 3.2: Power/Interest stakeholder matrix + communication plan
  - plan_ba_governance            — 3.3: governance: change control, approval, escalation
  - plan_information_management   — 3.4: artifact storage and traceability architecture
  - evaluate_ba_performance       — 3.5: BA performance metrics + improvement plan
  - save_ba_plan                  — finalize: render the Markdown BA Plan report

Storage:
  - {project}_ba_plan.json        — single JSON document with all plan sections
  - {project}_ba_plan_*.md        — Markdown report (via save_artifact)

Integration:
  Output: ba_plan.json — the record of the plan, read back by this module only.
  3.2 additionally SEEDS the living stakeholder registry
  ({project}_stakeholder_registry.json) that 4.2 maintains and 7.4 reads, so the same
  people are not entered twice. Source fields only, and only on creation for the
  assumed ones — a re-run must never overwrite what elicitation established.

  ⚠️ The remaining seams are NOT consumed programmatically by any other chapter:
    - 5.5 does not read the 3.3 governance section; approval authority and deadlines
      are applied by the BA, not automatically.
    - 7.3 takes its business context from 6.1/6.2, not from this plan.
  Wiring those two is a planned feature, not current behavior — do not promise
  them to the BA in tool output.

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
    parse_json_list as _parse_json_list,
    parse_json_str_list as _parse_string_list,
    pick_field, unrecognized_records_error,
    parse_json_dict_list as _parse_json_dict_list,
    update_stakeholder_registry_file, load_stakeholder_registry, stakeholder_identity,
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


# The 3.2 map and the 4.2 registry describe the SAME people. Seeding here is what
# stops the BA entering them twice — and 4.2's file is the one 7.4 reads.
_REGISTRY_SOURCE = "3.2 BA plan (Power/Interest map)"

# Source data only. quadrant/strategy/comm_frequency are DERIVED from influence and
# interest, and a derived value inside a file another chapter mutates goes stale
# silently: an interview that updates influence via 4.2 would leave the quadrant wrong.
_REGISTRY_SEED_FIELDS = ("name", "role", "influence", "interest", "attitude", "contact")


def _attitude_conflicts(project_id: str, planned: list) -> list:
    """Where the plan and the living registry disagree about a stakeholder's attitude.

    Returns [(name, planned_attitude, recorded_attitude)]. Only reports a genuine
    disagreement: an entry the plan left unstated carries an assumed default and is
    not evidence of anything, so it is skipped.

    Never raises — this is advisory, and planning must not fail on a registry read.
    """
    try:
        registry = load_stakeholder_registry(project_id)
    except Exception:  # noqa: BLE001 — advisory only
        return []

    recorded = {stakeholder_identity(s): s for s in registry.get("stakeholders", [])}
    conflicts = []
    for s in planned:
        stated = str(s.get("attitude") or "").strip()
        if not stated:
            continue
        entry = recorded.get(stakeholder_identity(s))
        if not entry:
            continue
        known = str(entry.get("attitude") or "").strip()
        if known and known.lower() != stated.lower():
            conflicts.append((s.get("name") or s.get("role") or "—", stated, known))
    return conflicts


def _seed_stakeholder_registry(project_id: str, stakeholders: list) -> str:
    """Seeds the living stakeholder registry from the 3.2 map. Returns a report line.

    Never raises: the plan is already saved by the time this runs, and a planning tool
    must not become unusable because a downstream file could not be written.
    """
    incoming = []
    for s in stakeholders:
        entry = {f: s.get(f) for f in _REGISTRY_SEED_FIELDS if s.get(f)}
        if entry:
            incoming.append(entry)
    if not incoming:
        return ""

    try:
        result = update_stakeholder_registry_file(
            project_id, incoming, source=_REGISTRY_SOURCE,
            insert_defaults={
                "found_through": _REGISTRY_SOURCE,
                # A stakeholder known from planning has by definition not been
                # elicited yet. Insert-only, so a later 'Elicited' is never reset.
                "coverage_status": "Not covered",
                # Insert-only for the same reason: when the BA states no attitude,
                # 'Neutral' is an assumption, and an assumption must never overwrite
                # a Blocker/Champion an interview established.
                "attitude": "Neutral",
            },
        )
    except Exception as e:  # noqa: BLE001 — never let planning fail on this
        logger.warning(f"3.2 could not seed the stakeholder registry: {e}")
        return "\n⚠️ Stakeholder registry not updated — the BA plan is saved.\n"

    if not result.get("saved"):
        return "\n⚠️ Stakeholder registry could not be written — the BA plan is saved.\n"

    return (
        f"\n📇 Stakeholder registry: {len(result['added'])} added, "
        f"{len(result['updated'])} updated "
        f"(the same living registry 4.2 `update_stakeholder_registry` maintains).\n"
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
    # Validating that the input PARSES is not validating that it FITS: this JSON is
    # written by an LLM, so a list of strings for a "list of stakeholders" parameter is
    # an ordinary case, and indexing it as objects raised AttributeError — a protocol
    # error out of an MCP tool instead of a readable answer (class CH3-A / CH4-A).
    # The other Chapter 3 tools were moved onto the shared validators; this one was the
    # last raw parse left in the module.
    stakeholders, shape_error = _parse_json_dict_list(
        stakeholders_json, "stakeholders_json",
        example='[{"name": "John Smith", "role": "Product Owner", '
                '"influence": "High", "interest": "High"}]')
    if shape_error:
        return shape_error

    if not stakeholders:
        return "⚠️ Stakeholder list is empty. Add at least one stakeholder."

    valid = []
    seed_source = []
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
        # The registry is seeded from what the BA ACTUALLY supplied, not from the plan
        # record above: that one carries a synthesized `attitude` default, and a
        # fabricated value is indistinguishable from a stated one once merged, so it
        # would overwrite an attitude an interview established. Defaults belong in
        # insert_defaults, which applies on creation only.
        seed_source.append(s)

    if errors:
        return "❌ Errors in stakeholders_json:\n" + "\n".join(f"  • {e}" for e in errors)

    plan = _load_plan(project_id)
    plan["stakeholder_engagement"] = {
        "stakeholders": valid,
        "total": len(valid),
        "updated_on": str(date.today()),
    }
    _save_plan(plan, project_id)

    # Read BEFORE seeding: an explicitly stated attitude wins as an ordinary field, so
    # after the seed the registry already agrees and there would be nothing to report.
    conflicts = _attitude_conflicts(project_id, seed_source)

    # Seed the living registry 4.2 maintains and 7.4 reads, so the same people are
    # not entered twice. Only ever reached once the plan itself is saved.
    registry_note = _seed_stakeholder_registry(project_id, seed_source)

    # Quadrant statistics
    quadrants = {}
    for s in valid:
        q = s["quadrant"]
        quadrants[q] = quadrants.get(q, 0) + 1

    blockers = [s["name"] for s in valid if s.get("attitude") == "Blocker"]

    lines = [
        # "map", not "registry": the living registry is a different artifact, and this
        # tool now reports on both in the same message.
        f"✅ Stakeholder map saved\n\n",
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

    # The blocker line above describes the PLAN just submitted, which is right — that
    # is what this tool reports on. But an attitude STATED here overwrites what an
    # interview recorded, and doing that silently is how a Blocker flagged in
    # elicitation disappears. The overwrite is intended (a stated value is the BA's
    # judgment, not an assumption); it just must not be invisible.
    if conflicts:
        lines.append(
            "\n⚠️ This plan overrides an attitude that elicitation had recorded:\n"
        )
        for name, planned, recorded in conflicts:
            lines.append(
                f"  {name}: elicitation recorded {recorded}, this plan states "
                f"{planned} — the registry now holds {planned}\n"
            )
        lines.append(
            "  If the interview is the more recent evidence, restate it here or "
            "correct it via `update_stakeholder_registry` (4.2).\n"
        )

    lines.append(registry_note)

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

    # Normalise the object entries. `metric` and `title` are the near-misses an LLM
    # writes for `name`; reading only `name` rendered "• :  → < 10% per sprint" into the
    # delivered BA Plan — a bullet with no subject — while this tool answered "recorded".
    METRIC_NAME_KEYS = ("name", "metric", "title")
    normalized_metrics = []
    named = 0
    for m in metrics:
        if isinstance(m, dict):
            name = pick_field(m, *METRIC_NAME_KEYS)
            if name:
                named += 1
            entry = dict(m)
            entry["name"] = name
            normalized_metrics.append(entry)
        else:
            normalized_metrics.append(m)
            named += 1
    if metrics and named == 0:
        return unrecognized_records_error(
            "metrics_json", METRIC_NAME_KEYS,
            '[{"name": "Defect Rate", "baseline": "15%", "target": "5%"}]')
    metrics = normalized_metrics

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

    def _notes_block(section: dict) -> list:
        """Renders the BA's own notes for a section.

        Every 3.x tool collects `ba_notes` ("additional agreements", "additional
        context"). Dropping them from the report loses context the BA deliberately
        recorded — the report is the deliverable, the JSON is not.
        """
        note = str(section.get("ba_notes", "") or "").strip()
        return [f"> **BA notes:** {note}", ""] if note else []

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
        md_lines += _notes_block(approach)

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
        md_lines += _notes_block(governance)

    if info_mgmt:
        md_lines += [
            "## 3.4 Information Management",
            "",
            f"- **Tools:** {', '.join(info_mgmt.get('storage_tools', []))}",
            f"- **Traceability:** {info_mgmt.get('traceability_level', '')} — {info_mgmt.get('traceability_description', '')}",
            f"- **Access:** {info_mgmt.get('access_rules', '')}",
        ]
        artifact_types = info_mgmt.get("artifact_types", [])
        if artifact_types:
            md_lines.append(f"- **Artifact types:** {', '.join(artifact_types)}")
        md_lines.append("")
        md_lines += _notes_block(info_mgmt)

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
        md_lines += _notes_block(performance)

    md_content = "\n".join(md_lines)
    artifact_result = save_artifact(md_content, f"3_ba_plan_{_safe(project_id)}", project_id=project_id)

    plan["status"] = "finalized"
    plan["finalized_on"] = str(date.today())
    _save_plan(plan, project_id)

    json_path = _plan_path(project_id)

    return (
        f"✅ BA plan finalized\n\n"
        f"  Project: {project_id}\n"
        f"  📄 JSON (plan record): `{json_path}`\n"
        f"  {artifact_result}\n\n"
        f"**Next step:**\n"
        f"• Chapter 4.1 — prepare for elicitation\n\n"
        f"ℹ️ The plan is a reference document: later chapters do not read it "
        f"automatically.\n"
        f"  • Stakeholders from 3.2 are ALREADY seeded into the living registry that "
        f"4.2 maintains and 7.4 reads — 4.2 adds to it as interviews reveal more\n"
        f"  • The governance rules from 3.3 are applied by you when approving in 5.5\n"
    )


if __name__ == "__main__":
    mcp.run()
