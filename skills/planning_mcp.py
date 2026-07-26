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
  Output: ba_plan.json. Section 3.4 (information_management) IS read by other
  chapters — through the shared helpers in skills/common.py, so no chapter imports
  this module:
    - 4.4 prepare_communication_package — the planned level of detail per audience
    - 5.2 find_reusable_requirements    — the planned reuse scope and repository
    - 5.2 check_requirements_health     — the planned attribute set
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
    read_json_artifact, guard_artifact_errors,
    ABSTRACTION_LEVELS, PLANNABLE_ATTRIBUTES, REUSE_CATEGORIES,
    planned_attribute_set, reg_norm,
    EFFORT_LEVELS, normalize_task_ref, approach_to_timing_form, activities_section,
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

# The eight 4.4 audience archetypes. Kept in sync with the `audience_role` Literal in
# elicitation_communicate_mcp.prepare_communication_package — Chapter 3 cannot import
# Chapter 4 (different phases), so this is a copy, and
# tests/test_ch3_info_mgmt_planning.py::TestVocabulariesStayInSync pins the two
# together. A plan row naming something else is still accepted (it may be a job
# title), just flagged: the consumer matches on either identifier.
_AUDIENCE_ARCHETYPES = (
    "Business Sponsor", "Manager", "Developer", "Architect / Tech Lead",
    "Tester", "End User", "Customer", "Domain SME",
)

_CLEAR_TEXT = "-"          # explicit clearing value for free-text parameters
_CLEAR_ENUM = "None"       # explicit clearing value for the Literal parameters

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
    # Corrupt -> CorruptArtifactError, converted to a ❌ line at the tool boundary
    # by guard_artifact_errors. This module loads in EVERY phase, so a bare
    # json.load here turned one damaged plan file into a protocol error across
    # every session (the chapters-5 / 7.1-7.3 pattern).
    return read_json_artifact(path, "3.x BA plan")


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
@guard_artifact_errors
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
        f"→ Next step: `plan_stakeholder_engagement` — build the stakeholder map.\n"
        f"   Optional first: `plan_ba_activities` — which BABOK tasks run in which "
        f"period and with what effort (BABOK 3.1, elements .3 and .4). 5.5 then takes "
        f"the methodology from there instead of asking you again."
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
@guard_artifact_errors
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
@guard_artifact_errors
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


_ARCHETYPE_KEYS = {reg_norm(a) for a in _AUDIENCE_ARCHETYPES}


def _sane_info_section(section) -> dict:
    """Coerce a stored 3.4 section into the shapes the merge code and renderer assume.

    Guarding only the section itself was not enough: one level down, every branch
    called `.get()` / `.values()` / `[...]` on whatever was on disk, so a file that is
    valid JSON with `"reuse": "oops"` still killed this tool — the only tool that can
    overwrite a damaged section. A bare string where a list belongs is worse than a
    crash: `"storage_tools": "Confluence"` was accepted and echoed one entry per
    CHARACTER. Unusable values are dropped, so the merge falls back to "not planned"
    and the BA can simply plan it again.
    """
    if not isinstance(section, dict):
        return {}
    out = dict(section)
    for key in ("storage_tools", "artifact_types"):
        value = out.get(key)
        if isinstance(value, list):
            out[key] = [s for s in value if isinstance(s, str)]
        else:
            out.pop(key, None)
    rows = out.get("abstraction_levels")
    if isinstance(rows, list):
        out["abstraction_levels"] = [r for r in rows if isinstance(r, dict)]
    else:
        out.pop("abstraction_levels", None)
    for key in ("reuse", "attributes"):
        if not isinstance(out.get(key), dict):
            out.pop(key, None)
    for key in ("access_rules", "ba_notes", "traceability_level",
                "traceability_description"):
        if key in out and not isinstance(out[key], str):
            out.pop(key, None)
    return out


def _sane_activities_section(section) -> dict:
    """Coerce a stored 3.1b section into the shapes the writer and renderer assume.

    Same reasoning as `_sane_info_section`: this is the only tool that can
    overwrite a damaged section, so it must survive reading one. `periods` is
    normalised by the shared reader, which both this module and the chapter-4/5
    consumers go through — one coercion, not three.
    """
    if not isinstance(section, dict):
        return {}
    out = dict(activities_section({"ba_activities": section}))
    for key in ("timing_form", "form_source", "ba_notes", "planned_on"):
        if key in out and not isinstance(out[key], str):
            out.pop(key, None)
    constraints = out.get("timing_constraints")
    out["timing_constraints"] = ([c for c in constraints if isinstance(c, str)]
                                 if isinstance(constraints, list) else [])
    if not isinstance(out.get("generated"), bool):
        out.pop("generated", None)
    return out


def _merge_text(new: str, previous, default: str = "") -> str:
    """Merge rule for a free-text field: "" keeps, "-" clears, anything else sets."""
    if new == "":
        return previous if previous is not None else default
    return "" if new == _CLEAR_TEXT else new


@mcp.tool()
@guard_artifact_errors
def plan_information_management(
    project_id: str,
    storage_tools_json: str = "",
    traceability_level: Literal["", "Low", "Medium", "High"] = "",
    artifact_types_json: str = "",
    access_rules: str = "",
    ba_notes: str = "",
    abstraction_levels_json: str = "",
    reuse_target_scope: Literal["", "None", "initiative", "program",
                                "division", "enterprise"] = "",
    reuse_repository: str = "",
    reuse_categories_json: str = "",
    attributes_preset: Literal["", "None", "Minimum", "Standard", "Full"] = "",
    additional_attributes_json: str = "",
) -> str:
    """
    BABOK 3.4 — Plan business analysis information management.

    Defines where and how requirements and artifacts are stored, the traceability
    level, how much detail each audience gets, how requirements will be reused, and
    which attributes this project maintains.
    Saves to {project}_ba_plan.json, section 'information_management'.

    Re-running MERGES: a parameter left empty keeps its previous value. Clear a list
    with "[]", a text field with "-", an enum with "None". Two exceptions:
    `storage_tools` cannot be cleared at all (a plan with nowhere to store anything is
    an unfinished task), and clearing `access_rules` restores its standing default
    rather than emptying it.

    What reads this plan:
      - 4.4 prepare_communication_package  — the planned level of detail per audience
      - 5.2 find_reusable_requirements     — the planned reuse scope and repository
      - 5.2 check_requirements_health      — the planned attribute set

    Args:
        project_id: Project identifier
        storage_tools_json: JSON list of storage tools, e.g. '["Confluence", "Jira"]'
        traceability_level: Traceability level (Low/Medium/High). Default Medium.
        artifact_types_json: JSON list of artifact types, e.g. '["User Story", "BRD"]'
        access_rules: Access rules (who reads, who edits)
        ba_notes: Additional agreements
        abstraction_levels_json: BABOK 3.4 element .2 — JSON list of
            '[{"audience": "Business Sponsor", "level": "Summary", "note": "..."}]'.
            level: Summary | Standard | Detailed. `audience` may be one of the eight
            4.4 archetypes or a job title from the stakeholder map — 4.4 matches on
            either.
        reuse_target_scope: BABOK 3.4 element .4 — the reuse level this project aims
            for: initiative | program | division | enterprise. Becomes 5.2's DEFAULT;
            an explicit value passed to 5.2 always wins.
        reuse_repository: Where reusable requirements live and how other BAs reach it.
        reuse_categories_json: JSON list of reuse candidate categories, e.g.
            '["regulatory", "business rules"]'.
        attributes_preset: BABOK 3.4 element .6 — which attribute set this project
            maintains: Minimum | Standard | Full. 5.2's health audit checks exactly
            this set.
        additional_attributes_json: JSON list of attributes added on top of the preset.
    """
    plan = _load_plan(project_id)
    # Coerced, not just type-checked at the top: a file that is valid JSON with the
    # wrong shape anywhere inside the section passes read_json_artifact, and every
    # merge branch below reads it. This tool is the only one that can overwrite a
    # damaged section, so it must not be the tool that dies on it.
    previous = _sane_info_section(plan.get("information_management"))
    warnings = []
    kept = []

    # --- storage tools: mergeable, but never clearable ---------------------
    if storage_tools_json == "":
        storage_tools = previous.get("storage_tools", [])
        if not storage_tools:
            return ("❌ `storage_tools_json` is required the first time 3.4 is planned.\n"
                    "   Example: '[\"Confluence\", \"Jira\"]'")
        kept.append("storage tools")
    else:
        storage_tools, error = _parse_string_list(
            storage_tools_json, "storage_tools_json", required=True)
        if error:
            return error

    # --- traceability level ------------------------------------------------
    if traceability_level == "":
        level = previous.get("traceability_level", "Medium")
        if previous.get("traceability_level"):
            kept.append("traceability level")
    else:
        level = traceability_level
    trace_desc = _TRACEABILITY_LEVELS.get(level, _TRACEABILITY_LEVELS["Medium"])

    # --- artifact types ----------------------------------------------------
    if artifact_types_json == "":
        artifact_types = previous.get("artifact_types", [])
        if artifact_types:
            kept.append("artifact types")
    else:
        artifact_types, error = _parse_string_list(artifact_types_json, "artifact_types_json")
        if error:
            return error

    # --- element .2: level of abstraction ----------------------------------
    if abstraction_levels_json == "":
        abstraction_levels = previous.get("abstraction_levels", [])
        if abstraction_levels:
            kept.append("abstraction levels")
    else:
        rows, error = _parse_json_dict_list(
            abstraction_levels_json, "abstraction_levels_json",
            example='[{"audience": "Business Sponsor", "level": "Summary", "note": "..."}]')
        if error:
            return error
        abstraction_levels = []
        seen = {}
        for i, row in enumerate(rows, 1):
            audience = str(row.get("audience") or "").strip()
            if not audience:
                return (f"❌ `abstraction_levels_json`: row {i} has no `audience`.\n"
                        f"   Every row needs an audience — an archetype from 4.4 or a "
                        f"job title from the stakeholder map.")
            row_level = str(row.get("level") or "").strip()
            if row_level not in ABSTRACTION_LEVELS:
                return (f"❌ `abstraction_levels_json`: row {i} has level "
                        f"`{row_level or '(empty)'}`.\n"
                        f"   Allowed: {', '.join(ABSTRACTION_LEVELS)}")
            key = reg_norm(audience)
            # Compared through reg_norm, because that is how the CONSUMER matches:
            # a raw-casing check told the BA that "business sponsor" would "match only
            # by job title" while 4.4 resolved it as the archetype perfectly well — a
            # confident false claim, and one that also fired on the second row of any
            # case-differing duplicate.
            if key not in _ARCHETYPE_KEYS:
                warnings.append(
                    f"⚠️ `{audience}` is not one of the 4.4 audience archetypes — it will "
                    f"match only by job title.")
            entry = {"audience": audience, "level": row_level,
                     "note": str(row.get("note") or "")}
            if key in seen:
                warnings.append(f"⚠️ `{audience}` appears twice — the last row wins.")
                abstraction_levels[seen[key]] = entry
            else:
                seen[key] = len(abstraction_levels)
                abstraction_levels.append(entry)

    # --- element .4: reuse -------------------------------------------------
    prev_reuse = previous.get("reuse") or {}
    if reuse_target_scope == "":
        target_scope = prev_reuse.get("target_scope", "")
        if target_scope:
            kept.append("reuse scope")
    else:
        target_scope = "" if reuse_target_scope == _CLEAR_ENUM else reuse_target_scope

    repository = _merge_text(reuse_repository, prev_reuse.get("repository"))
    if reuse_repository == "" and prev_reuse.get("repository"):
        kept.append("reuse repository")

    if reuse_categories_json == "":
        reuse_categories = prev_reuse.get("categories", [])
        if reuse_categories:
            kept.append("reuse categories")
    else:
        reuse_categories, error = _parse_string_list(
            reuse_categories_json, "reuse_categories_json")
        if error:
            return error
        unlisted = [c for c in reuse_categories if c.lower() not in REUSE_CATEGORIES]
        if unlisted:
            # BABOK's list is explicitly open-ended, so this is a note, not a refusal.
            warnings.append(
                f"⚠️ Categories outside the BABOK list: {', '.join(unlisted)}. "
                f"Kept — the list in the guide is not exhaustive.")

    # --- element .6: attributes -------------------------------------------
    prev_attrs = previous.get("attributes") or {}
    if attributes_preset == "":
        preset = prev_attrs.get("preset", "")
        if preset:
            kept.append("attribute preset")
    else:
        preset = "" if attributes_preset == _CLEAR_ENUM else attributes_preset

    if additional_attributes_json == "":
        additional = prev_attrs.get("additional", [])
        if additional:
            kept.append("additional attributes")
    else:
        additional, error = _parse_string_list(
            additional_attributes_json, "additional_attributes_json")
        if error:
            return error
        unknown = [a for a in additional if a not in PLANNABLE_ATTRIBUTES]
        if unknown:
            # Planning an attribute the model cannot store would recreate the
            # "declared but dead" class inside this very feature.
            return (f"❌ Not stored by this platform: {', '.join(unknown)}.\n"
                    f"   Plannable attributes: {', '.join(PLANNABLE_ATTRIBUTES)}\n"
                    f"   BABOK also lists author, risks and urgency (p. 45-46); the "
                    f"requirement model has no field for them, so 5.2 could never "
                    f"check them.")

    # Tracked like every other merged field: a "Kept" line the BA is meant to trust
    # instead of opening the JSON must not under-report what actually survived.
    if access_rules == "" and previous.get("access_rules"):
        kept.append("access rules")
    if ba_notes == "" and previous.get("ba_notes"):
        kept.append("BA notes")

    info_mgmt = {
        "storage_tools": storage_tools,
        "traceability_level": level,
        "traceability_description": trace_desc,
        "artifact_types": artifact_types,
        # `-` restores the standing default rather than emptying the field: an empty
        # Access line in the delivered BA Plan is worse than the default it replaced.
        "access_rules": _merge_text(access_rules, previous.get("access_rules"),
                                    "BA edits, others read") or "BA edits, others read",
        "ba_notes": _merge_text(ba_notes, previous.get("ba_notes")),
        "abstraction_levels": abstraction_levels,
        "reuse": {"target_scope": target_scope, "repository": repository,
                  "categories": reuse_categories},
        "attributes": {"preset": preset, "additional": additional},
        "defined_on": str(date.today()),
    }

    plan["information_management"] = info_mgmt
    _save_plan(plan, project_id)

    out = [
        "✅ Information management plan recorded",
        "",
        f"  Project:           {project_id}",
        f"  Tools:             {', '.join(storage_tools)}",
        f"  Traceability:      {level} — {trace_desc}",
    ]
    if artifact_types:
        out.append(f"  Artifact types:    {', '.join(artifact_types)}")
    out.append(f"  Access:            {info_mgmt['access_rules']}")

    if abstraction_levels:
        out.append("")
        out.append("  Level of detail (read by 4.4):")
        for row in abstraction_levels:
            suffix = f" — {row['note']}" if row["note"] else ""
            out.append(f"    • {row['audience']}: {row['level']}{suffix}")

    if target_scope or repository or reuse_categories:
        out.append("")
        out.append("  Reuse (read by 5.2):")
        if target_scope:
            out.append(f"    • Target scope: {target_scope} — 5.2 ranks by it "
                       f"(it does not exclude anything below)")
        if repository:
            out.append(f"    • Repository:   {repository}")
        if reuse_categories:
            out.append(f"    • Categories:   {', '.join(reuse_categories)}")

    resolved = planned_attribute_set({"information_management": info_mgmt})
    if resolved:
        attrs, label = resolved
        out.append("")
        out.append(f"  Attributes audited by 5.2 ({label}):")
        out.append(f"    {', '.join(attrs)}")
        if "owner" not in attrs:
            out.append("    ⚠️ `owner` is not in this set — 5.2's health audit will stop "
                       "asking for it.")

    if kept:
        out.append("")
        out.append(f"  ↩️ Kept from the previous plan: {', '.join(kept)}")

    for w in warnings:
        out.append(f"\n{w}")

    out.append("")
    out.append("→ Next step: `evaluate_ba_performance` — set performance metrics.")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# 3.1 elements .3 (BA Activities) and .4 (Timing of BA Work) — B3-1
# ---------------------------------------------------------------------------
#
# BABOK Figure 3.1.2 (printed p. 27) ties the FORM of the breakdown to the approach:
# predictive names the activities for each deliverable and then the tasks; adaptive
# divides the work into iterations, names the deliverables of each, then the
# activities. The skeletons below are those two shapes, expressed in the platform's
# own task ids so a consumer can match them.
#
# The word "Phase" is deliberately NOT used in period names: `python phase.py`
# switches the platform's SESSION phase, and a BA reading "Phase 2" in a plan would
# reasonably think it is a phase to switch to.
_SKELETON_ITERATIONS = (
    {"name": "Iteration 1", "tasks": ["4", "6.1"],
     "deliverables": ["Elicitation results", "As-is understanding"],
     "effort": "High", "when": ""},
    {"name": "Iteration 2", "tasks": ["5", "7"],
     "deliverables": ["Prioritized backlog", "Requirement specifications"],
     "effort": "Medium", "when": ""},
)

_SKELETON_PHASES = (
    {"name": "Stage 1 — Discovery", "tasks": ["3", "4"],
     "deliverables": ["BA plan", "Elicitation results"],
     "effort": "High", "when": ""},
    {"name": "Stage 2 — Analysis", "tasks": ["6"],
     "deliverables": ["As-is / to-be models", "Change strategy"],
     "effort": "High", "when": ""},
    {"name": "Stage 3 — Specification and approval", "tasks": ["7", "5"],
     "deliverables": ["Requirement specifications", "Approved baseline"],
     "effort": "Medium", "when": ""},
)


@mcp.tool()
@guard_artifact_errors
def plan_ba_activities(
    project_id: str,
    timing_form: Literal["", "phases", "iterations"] = "",
    periods_json: str = "[]",
    timing_constraints_json: str = "[]",
    ba_notes: str = "",
) -> str:
    """
    BABOK 3.1 — plan the BA activities (element .3) and their timing (element .4).

    Optional step, run after `suggest_ba_approach`. Records WHICH BABOK tasks are
    done in which work period, with what effort, and what constrains the timing.
    Saves to {project}_ba_plan.json, section 'ba_activities'.

    Two chapters read this section afterwards:
      - 5.5 prepare_approval_package takes the methodology from the timing form,
        so the BA no longer states it a second time;
      - 4.1 save_elicitation_plan names the period that covers elicitation work.

    Args:
        project_id: Project identifier
        timing_form: "phases" (predictive) or "iterations" (adaptive). Leave empty
            to derive it from the approach chosen in 3.1.
        periods_json: JSON list of work periods. Leave empty for a starting
            skeleton generated from the approach. Format:
            '[{"name": "Iteration 1", "tasks": ["4.1", "4.2"],
               "deliverables": ["Elicitation results"], "effort": "High",
               "when": "Aug 2026"}]'
            `tasks` are BABOK task ids of this platform (3.1-7.6) or a whole
            chapter ("4").
        timing_constraints_json: JSON list of what constrains the timing, e.g.
            '["regulatory deadline 2026-12-31", "vendor available from September"]'
        ba_notes: Additional context from the BA
    """
    periods_in, error = _parse_json_dict_list(
        periods_json, "periods_json",
        example='[{"name": "Iteration 1", "tasks": ["4.1"], "effort": "High"}]')
    if error:
        return error
    constraints, error = _parse_string_list(
        timing_constraints_json, "timing_constraints_json",
        example='["regulatory deadline 2026-12-31"]')
    if error:
        return error

    plan = _load_plan(project_id)
    approach_section = plan.get("ba_approach")
    approach_label = ""
    if isinstance(approach_section, dict):
        raw_label = approach_section.get("recommended_approach")
        approach_label = raw_label if isinstance(raw_label, str) else ""
    derived = approach_to_timing_form(approach_label)

    warnings = []
    if timing_form:
        form, form_source = timing_form, "declared by the BA"
        if derived and derived != timing_form:
            warnings.append(
                f"⚠️ You declared `{timing_form}`, but the 3.1 approach "
                f"({approach_label}) implies `{derived}`. Stored what you declared — "
                f"the decision is yours.")
    elif derived:
        form, form_source = derived, f"derived from {approach_label}"
    else:
        form, form_source = "", ""

    # Nothing to derive AND nothing typed: there is nothing to store. An empty
    # section would claim the planning happened and would pass the "empty plan"
    # gate in save_ba_plan.
    if not form and not periods_in:
        reason = (f"the approach `{approach_label}` sits between predictive and "
                  f"adaptive, so the form does not follow from it"
                  if approach_label else
                  "3.1 has not been run for this project yet")
        return (
            f"⚠️ Nothing recorded — {reason}.\n\n"
            f"  Say which form the work takes and I will store it:\n"
            f"    • `timing_form=\"phases\"`     — BA tasks run in specific stages\n"
            f"    • `timing_form=\"iterations\"` — BA tasks run iteratively\n\n"
            f"  (BABOK 3.1, element .4 — I will not guess it for you: the value ends "
            f"up on the approval package that goes out for signature.)"
        )

    generated = not periods_in
    source_periods = periods_in
    if generated:
        source_periods = [dict(p) for p in
                          (_SKELETON_ITERATIONS if form == "iterations"
                           else _SKELETON_PHASES)]

    unknown_refs = []
    off_scale_efforts = []
    periods = []
    for index, raw in enumerate(source_periods, start=1):
        raw_tasks = raw.get("tasks")
        if isinstance(raw_tasks, str):
            raw_tasks = [raw_tasks]
        elif not isinstance(raw_tasks, list):
            raw_tasks = []
        tasks = []
        for candidate in raw_tasks:
            ref = normalize_task_ref(candidate)
            if ref:
                if ref not in tasks:
                    tasks.append(ref)
            else:
                unknown_refs.append(str(candidate))
        raw_deliverables = raw.get("deliverables")
        deliverables = ([d for d in raw_deliverables if isinstance(d, str)]
                        if isinstance(raw_deliverables, list) else [])
        effort = str(raw.get("effort") or "")
        if effort and effort not in EFFORT_LEVELS:
            off_scale_efforts.append(effort)
        periods.append({
            "name": str(raw.get("name") or f"Period {index}"),
            "tasks": tasks,
            "deliverables": deliverables,
            "effort": effort,
            "when": str(raw.get("when") or ""),
        })

    if not form:
        warnings.append(
            "⚠️ The timing form is not set, so 5.5 `prepare_approval_package` will "
            "NOT take the methodology from this plan — you will keep passing "
            "`approach` there by hand. Re-run with `timing_form=\"phases\"` or "
            "`timing_form=\"iterations\"` to close that.")
    if unknown_refs:
        warnings.append(
            f"⚠️ Not BABOK task ids of this platform, so they were dropped: "
            f"{', '.join(unknown_refs)}. Use 3.1-7.6 or a whole chapter (\"4\"). "
            f"Chapter 8 is not implemented yet.")
    if off_scale_efforts:
        warnings.append(
            f"⚠️ Effort outside the Low/Medium/High scale, stored as given: "
            f"{', '.join(off_scale_efforts)}.")

    plan["ba_activities"] = {
        "timing_form": form,
        "form_source": form_source,
        "generated": generated,
        "periods": periods,
        "timing_constraints": constraints,
        "ba_notes": ba_notes,
        "planned_on": str(date.today()),
    }
    _save_plan(plan, project_id)

    lines = [
        "✅ BA activities and timing recorded\n",
        f"  Project:      {project_id}",
        f"  Timing form:  {form or '(not set)'}"
        + (f" ({form_source})" if form_source else ""),
        f"  Periods:      {len(periods)}"
        + ("  ℹ️ generated from the approach — edit and re-run to make them yours"
           if generated else ""),
        "",
    ]
    for period in periods:
        lines.append(
            f"  • {period['name']}"
            f" — tasks: {', '.join(period['tasks']) or '—'}"
            f" | deliverables: {', '.join(period['deliverables']) or '—'}"
            f" | effort: {period['effort'] or '—'}"
            f" | when: {period['when'] or '—'}")
    if constraints:
        lines += ["", f"  Timing constraints ({len(constraints)}):"]
        lines += [f"    – {c}" for c in constraints]
    if ba_notes:
        lines += ["", f"  BA notes: {ba_notes}"]
    if warnings:
        lines += [""] + [f"  {w}" for w in warnings]
    lines += [
        "",
        "ℹ️ What now reads this:",
        "  • 5.5 `prepare_approval_package` — takes the methodology from the timing "
        "form, so you do not state it twice",
        "  • 4.1 `save_elicitation_plan` — names the period that covers elicitation "
        "work and its planned effort",
        "",
        "→ Next step: `plan_stakeholder_engagement` — build the stakeholder map.",
    ]
    return "\n".join(lines)


@mcp.tool()
@guard_artifact_errors
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
@guard_artifact_errors
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
    activities = _sane_activities_section(plan.get("ba_activities"))
    # The coercion always supplies `periods` and `timing_constraints`, so the dict is
    # truthy even when nothing usable survived — and both the gate below and the
    # renderer test this value. Without the question "was anything actually planned?",
    # a damaged section produced an empty "## 3.1b" heading with a "(not set)" form
    # inside a DELIVERED document, and an empty section let an otherwise empty plan
    # through the gate.
    if not any([activities.get("timing_form"), activities.get("periods"),
                activities.get("timing_constraints"), activities.get("ba_notes")]):
        activities = {}

    # `performance` counts too: the report renders a 3.5 section when it is present,
    # so omitting it here refused a plan that actually had content.
    if not any([approach, activities, engagement, governance, info_mgmt, performance]):
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

    if activities:
        form = activities.get("timing_form", "")
        source = activities.get("form_source", "")
        md_lines += [
            "## 3.1b BA Activities and Timing",
            "",
            f"- **Timing form:** {form or '(not set)'}"
            + (f" ({source})" if source else ""),
        ]
        if activities.get("generated"):
            md_lines.append(
                "- ℹ️ Generated from the approach — edit via `plan_ba_activities`.")
        periods = activities.get("periods", [])
        if periods:
            md_lines += [
                "",
                "| Period | BABOK tasks | Deliverables | Effort | When |",
                "|--------|-------------|--------------|--------|------|",
            ]
            for period in periods:
                tasks = period.get("tasks")
                tasks = ", ".join(t for t in tasks if isinstance(t, str)) \
                    if isinstance(tasks, list) else ""
                deliverables = period.get("deliverables")
                deliverables = ", ".join(d for d in deliverables if isinstance(d, str)) \
                    if isinstance(deliverables, list) else ""
                md_lines.append(
                    f"| {period.get('name', '')} | {tasks or '—'} | "
                    f"{deliverables or '—'} | {period.get('effort', '') or '—'} | "
                    f"{period.get('when', '') or '—'} |")
        constraints = activities.get("timing_constraints", [])
        if constraints:
            md_lines += ["", "**Timing constraints:**", ""]
            md_lines += [f"- {c}" for c in constraints]
        md_lines.append("")
        md_lines += _notes_block(activities)

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

    # Pre-existing sibling of the writer's guard: a section of the wrong shape reached
    # .get() here too, at every nesting level. Same coercion as the writer, so the
    # renderer skips unusable values rather than failing the whole report.
    info_mgmt = _sane_info_section(info_mgmt)
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

        # Each block appears only when it holds data: an empty table in a document
        # that goes to people reads as a gap in the analysis, not as an unused option.
        rows = info_mgmt.get("abstraction_levels") or []
        if rows:
            md_lines += [
                "### Level of detail per audience",
                "",
                "_Read by 4.4 when a communication package is prepared._",
                "",
                "| Audience | Level | Note |",
                "|---|---|---|",
            ]
            for row in rows:
                md_lines.append(
                    f"| {row.get('audience', '—')} | {row.get('level', '—')} | "
                    f"{row.get('note') or '—'} |")
            md_lines.append("")

        reuse = info_mgmt.get("reuse") or {}
        if any(reuse.values()):
            md_lines += ["### Requirements reuse", ""]
            if reuse.get("target_scope"):
                md_lines.append(f"- **Target scope:** {reuse['target_scope']} "
                                f"(the default 5.2 applies)")
            if reuse.get("repository"):
                md_lines.append(f"- **Repository:** {reuse['repository']}")
            if reuse.get("categories"):
                md_lines.append(
                    f"- **Candidate categories:** {', '.join(reuse['categories'])}")
            md_lines.append("")

        resolved = planned_attribute_set({"information_management": info_mgmt})
        if resolved:
            attrs, label = resolved
            md_lines += [
                "### Requirements attributes",
                "",
                f"- **Maintained set** ({label}): {', '.join(attrs)}",
                "- _5.2's health audit checks exactly this set._",
                "",
            ]

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
        f"ℹ️ What is read automatically, and what is not:\n"
        f"  • Stakeholders from 3.2 are ALREADY seeded into the living registry that "
        f"4.2 maintains and 7.4 reads — 4.2 adds to it as interviews reveal more\n"
        f"  • Section 3.4 IS read: 4.4 states the planned level of detail in every "
        f"communication package, 5.2 ranks reuse candidates by the planned scope and "
        f"audits exactly the planned attribute set\n"
        f"  • The rest is a reference document — the governance rules from 3.3 are "
        f"applied by you when approving in 5.5\n"
    )


if __name__ == "__main__":
    mcp.run()
