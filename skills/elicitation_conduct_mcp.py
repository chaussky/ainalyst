"""
BABOK 4.2 — Conduct Elicitation
MCP tools for processing elicitation results.

Tools:
  - process_elicitation_results  — save the structured result of a session
  - compare_elicitation_results  — compare multiple sessions, find contradictions
  - save_gap_analysis            — save gap analysis and BA recommendations

# Copyright (c) 2026 Anatoly Chaussky. AI-powered Platform AInalyst. Licensed under AGPL v3. Commercial licensing: chaussky@gmail.com
"""

import json
from datetime import date
from typing import Literal
from mcp.server.fastmcp import FastMCP
from skills.common import save_artifact, logger

mcp = FastMCP("BABOK_Elicitation_Conduct")


# ---------------------------------------------------------------------------
# 4.2.1 — Save structured results of a single session
# ---------------------------------------------------------------------------

@mcp.tool()
def process_elicitation_results(
    project_name: str,
    session_date: str,
    stakeholder_role: str,
    session_type: Literal["Interview", "Workshop", "Survey", "Observation", "Document Analysis"],
    stakeholder_profile_json: str,
    pains_json: str,
    requirements_json: str,
    gaps_and_signals: str,
    ba_recommendations: str,
    maturity_level: Literal["Low", "Medium", "Good", "High"],
    maturity_notes: str,
) -> str:
    """
    BABOK 4.2 — Saves the structured results of a single elicitation session.
    The result is passed on to task 4.3 (confirmation).

    Args:
        project_name:              Project name.
        session_date:              Session date in DD.MM.YYYY format.
        stakeholder_role:          Stakeholder role (job title / function).
        session_type:              Type of elicitation session.
        stakeholder_profile_json:  Stakeholder profile. Format:
                                   {
                                     "participation_type": "Decision maker / Influencer / End user",
                                     "influence": "High / Medium / Low",
                                     "interest": "High / Medium / Low",
                                     "attitude": "Champion / Neutral / Blocker",
                                     "key_expectations": "text",
                                     "key_concerns": "text",
                                     "related_stakeholders": ["role 1", "role 2"]
                                   }
        pains_json:                List of pain points. Format:
                                   [
                                     {
                                       "title": "short title",
                                       "description": "context and substance",
                                       "frequency": "how often",
                                       "business_impact": "impact on the business",
                                       "quote": "verbatim quote if available"
                                     }
                                   ]
        requirements_json:         Requirements by type. Format:
                                   {
                                     "functional": ["FR-001: ...", "FR-002: ..."],
                                     "non_functional": ["NFR-001: ..."],
                                     "constraints": ["..."],
                                     "business_rules": ["..."]
                                   }
        gaps_and_signals:          Analysis of blind spots and hidden signals.
                                   Text describing unspoken issues, open topics,
                                   contradictions, and political signals.
        ba_recommendations:        Specific BA recommendations: what to clarify,
                                   with whom, whether a follow-up is needed.
        maturity_level:            Overall maturity level of the requirements.
        maturity_notes:            Comment on the maturity assessment.

    Returns:
        Path to the saved elicitation results file.
    """
    logger.info(f"4.2 Saving elicitation results: project='{project_name}', type='{session_type}'")

    # Parse JSON
    try:
        profile = json.loads(stakeholder_profile_json)
        pains = json.loads(pains_json)
        reqs = json.loads(requirements_json)
    except json.JSONDecodeError as e:
        return f"❌ Error parsing JSON: {e}"

    # Build the pain points block
    pains_md = ""
    for i, p in enumerate(pains, 1):
        pains_md += f"\n### Pain point {i}: {p.get('title', '—')}\n"
        pains_md += f"- **Description:** {p.get('description', '—')}\n"
        pains_md += f"- **Frequency:** {p.get('frequency', '—')}\n"
        pains_md += f"- **Business impact:** {p.get('business_impact', '—')}\n"
        if p.get('quote'):
            pains_md += f"- **Quote:** *«{p['quote']}»*\n"

    # Build the requirements block
    def req_list(items):
        return "\n".join(f"- {r}" for r in items) if items else "- None identified"

    # Build the profile block
    related = ", ".join(profile.get("related_stakeholders", [])) or "None identified"

    content = f"""# Elicitation Results (Unconfirmed)

**Project:** {project_name}
**Session date:** {session_date}
**Session type:** {session_type}
**Stakeholder:** {stakeholder_role}
**Status:** Unconfirmed results → passed to task 4.3

---

## 1. Stakeholder Profile

| Parameter | Value |
| :--- | :--- |
| **Participation type** | {profile.get('participation_type', '—')} |
| **Influence** | {profile.get('influence', '—')} |
| **Interest** | {profile.get('interest', '—')} |
| **Attitude toward the project** | {profile.get('attitude', '—')} |
| **Key expectations** | {profile.get('key_expectations', '—')} |
| **Key concerns** | {profile.get('key_concerns', '—')} |
| **Related stakeholders** | {related} |

---

## 2. Needs and Pain Points
{pains_md}

---

## 3. Requirements

### Functional Requirements
{req_list(reqs.get('functional', []))}

### Non-Functional Requirements
{req_list(reqs.get('non_functional', []))}

### Constraints
{req_list(reqs.get('constraints', []))}

### Business Rules
{req_list(reqs.get('business_rules', []))}

---

## 4. Blind Spots and Hidden Signals

{gaps_and_signals}

---

## 5. BA Recommendations

{ba_recommendations}

---

## 6. Requirements Maturity Assessment

**Overall level:** {maturity_level}

{maturity_notes}
"""

    suffix = save_artifact(
        content,
        f"Elicitation_Results_{project_name.replace(' ', '_')}_{session_date.replace('.', '-')}",
        project_id=project_name,
    )
    return f"✅ Elicitation results saved.{suffix}"


# ---------------------------------------------------------------------------
# 4.2.2 — Save the cross-analysis of multiple sessions
# ---------------------------------------------------------------------------

@mcp.tool()
def compare_elicitation_results(
    project_name: str,
    sessions_summary: str,
    contradictions: str,
    requirements_registry_json: str,
    political_map: str,
    follow_up_plan: str,
) -> str:
    """
    BABOK 4.2 — Saves the cross-analysis of multiple elicitation sessions.

    Args:
        project_name:                Project name.
        sessions_summary:            Brief description of the analyzed sessions
                                     (who, when, type).
        contradictions:              Description of contradictions between stakeholders:
                                     factual, priority-related, coverage gaps.
        requirements_registry_json:  Consolidated requirements registry. Format:
                                     [
                                       {
                                         "id": "FR-001",
                                         "requirement": "text",
                                         "sources": ["Stakeholder A", "Stakeholder B"],
                                         "priority": "High / Medium / Low / Undetermined",
                                         "status": "Agreed / Needs confirmation / Contradiction",
                                         "notes": "note"
                                       }
                                     ]
        political_map:               Observations on political dynamics among
                                     stakeholders and risks to the project.
        follow_up_plan:              Plan for further elicitation: questions, stakeholders,
                                     formats, priorities.

    Returns:
        Path to the saved cross-analysis file.
    """
    logger.info(f"4.2 Cross-analysis: project='{project_name}'")

    try:
        registry = json.loads(requirements_registry_json)
    except json.JSONDecodeError as e:
        return f"❌ Error parsing requirements_registry_json: {e}"

    # Build the registry table
    reg_rows = "\n".join([
        f"| {r.get('id','—')} | {r.get('requirement','—')} | "
        f"{', '.join(r.get('sources',[]))} | {r.get('priority','—')} | "
        f"{r.get('status','—')} | {r.get('notes','—')} |"
        for r in registry
    ])

    reg_table = (
        "| ID | Requirement | Sources | Priority | Status | Notes |\n"
        "| :--- | :--- | :--- | :---: | :--- | :--- |\n"
        + reg_rows
    )

    content = f"""# Cross-Analysis of Elicitation Results

**Project:** {project_name}
**Analysis date:** {date.today().strftime("%d.%m.%Y")}
**Status:** Unconfirmed results → passed to task 4.3

---

## 1. Analyzed Sessions

{sessions_summary}

---

## 2. Contradictions Between Stakeholders

{contradictions}

---

## 3. Consolidated Requirements Registry

{reg_table}

---

## 4. Political Map

{political_map}

---

## 5. Further Elicitation Plan

{follow_up_plan}
"""

    suffix = save_artifact(content, f"Cross_Analysis_{project_name.replace(' ', '_')}", project_id=project_name)
    return f"✅ Cross-analysis saved.{suffix}"


# ---------------------------------------------------------------------------
# 4.2.3 — Save the elicitation analysis in the context of a Change Request
# ---------------------------------------------------------------------------

@mcp.tool()
def save_cr_elicitation_analysis(
    project_name: str,
    cr_description: str,
    affected_artifacts_json: str,
    outdated_data: str,
    follow_up_questions: str,
    scope_assessment: str,
    workshop_needed: bool,
    workshop_notes: str = "",
) -> str:
    """
    BABOK 4.2 — Saves the elicitation analysis in the context of a Change Request.

    Args:
        project_name:              Project name.
        cr_description:            CR description: what is changing, initiator, reason.
        affected_artifacts_json:   Affected artifacts. Format:
                                   [
                                     {
                                       "artifact": "name / ID",
                                       "type": "Profile / Pain point / FR / NFR / User Story",
                                       "affected": true,
                                       "change_type": "Update / Remove / Freeze"
                                     }
                                   ]
        outdated_data:             Description of outdated data and what to do about it.
        follow_up_questions:       New elicitation questions: what, with whom,
                                   priority, format.
        scope_assessment:          Assessment of the scope and risks of further elicitation.
        workshop_needed:           Whether a workshop is needed for alignment.
        workshop_notes:            Participant list and agenda for the workshop (if needed).

    Returns:
        Path to the saved CR analysis file.
    """
    logger.info(f"4.2 CR analysis: project='{project_name}'")

    try:
        artifacts = json.loads(affected_artifacts_json)
    except json.JSONDecodeError as e:
        return f"❌ Error parsing affected_artifacts_json: {e}"

    # Build the artifacts table
    art_rows = "\n".join([
        f"| {a.get('artifact','—')} | {a.get('type','—')} | "
        f"{'✅' if a.get('affected') else '—'} | {a.get('change_type','—')} |"
        for a in artifacts
    ])

    art_table = (
        "| Artifact | Type | Affected | Action |\n"
        "| :--- | :--- | :---: | :--- |\n"
        + art_rows
    )

    workshop_block = ""
    if workshop_needed:
        workshop_block = f"\n## 6. Workshop\n\n**Needed:** Yes\n\n{workshop_notes}\n"
    else:
        workshop_block = "\n## 6. Workshop\n\n**Needed:** No\n"

    content = f"""# Elicitation Analysis in the Context of a Change Request

**Project:** {project_name}
**Analysis date:** {date.today().strftime("%d.%m.%Y")}
**Status:** Requires further elicitation

---

## 1. Change Request Description

{cr_description}

---

## 2. Impact Zone

{art_table}

---

## 3. Outdated Data

{outdated_data}

---

## 4. Further Elicitation Plan

{follow_up_questions}

---

## 5. Scope Assessment

{scope_assessment}
{workshop_block}
"""

    suffix = save_artifact(content, f"CR_Elicitation_{project_name.replace(' ', '_')}", project_id=project_name)
    return f"✅ CR analysis saved.{suffix}"


# ---------------------------------------------------------------------------
# 4.2.4 — Update the living stakeholder registry
# ---------------------------------------------------------------------------

@mcp.tool()
def update_stakeholder_registry(
    project_name: str,
    session_source: str,
    new_stakeholders_json: str,
) -> str:
    """
    BABOK 4.2 / 3.2 — Updates the project's living stakeholder registry.

    The stakeholder registry is a living document. It starts with 1-2 known people
    (usually the sponsor) and grows after each elicitation session via a chain:
    each stakeholder names the next ones.

    Call this tool after every interview / workshop / document analysis.

    Args:
        project_name:           Project name.
        session_source:         Where the information about the new stakeholders came from.
                                Example: "Interview with J. Smith (CFO), 03/15/2024"
        new_stakeholders_json:  List of new or updated stakeholders. Format:
                                [
                                  {
                                    "name": "J. Doe",
                                    "role": "Head of Procurement",
                                    "department": "Procurement",
                                    "found_through": "J. Smith (CFO)",
                                    "why_important": "Makes decisions on the procurement budget",
                                    "influence": "High / Medium / Low",
                                    "interest": "High / Medium / Low",
                                    "attitude": "Champion / Neutral / Blocker / Unknown",
                                    "coverage_status": "Not covered / Planned / Elicited",
                                    "priority": "Urgent / As planned / Uncertain",
                                    "recommended_format": "Interview / Workshop / Written request",
                                    "notes": "additional information"
                                  }
                                ]

    Returns:
        Path to the updated stakeholder registry file.
    """
    logger.info(f"4.2 Updating stakeholder registry: project='{project_name}', source='{session_source}'")

    try:
        stakeholders = json.loads(new_stakeholders_json)
    except json.JSONDecodeError as e:
        return (
            f"❌ Error parsing new_stakeholders_json: {e}\n\n"
            f"Expected format: a list of objects with fields name, role, found_through, etc."
        )

    today = date.today().strftime("%d.%m.%Y")

    # New stakeholders table
    rows = []
    for s in stakeholders:
        rows.append(
            f"| {s.get('name', '—')} | {s.get('role', '—')} | "
            f"{s.get('department', '—')} | {s.get('found_through', '—')} | "
            f"{s.get('influence', '—')} | {s.get('interest', '—')} | "
            f"{s.get('attitude', 'Unknown')} | {s.get('coverage_status', '—')} | "
            f"{s.get('priority', '—')} | {s.get('recommended_format', '—')} |"
        )

    table_header = (
        "| Stakeholder | Role | Department | Found through | Influence | Interest | "
        "Attitude | Coverage status | Priority | Format |\n"
        "| :--- | :--- | :--- | :--- | :---: | :---: | :--- | :--- | :---: | :--- |\n"
    )

    # Discovery chain
    chain_lines = []
    for s in stakeholders:
        source = s.get('found_through', 'Unknown')
        name = s.get('name', '—')
        role = s.get('role', '—')
        why = s.get('why_important', '')
        chain_lines.append(f"- **{name}** ({role}) ← via: {source}" + (f"\n  > {why}" if why else ""))

    # Not covered — separate action list
    uncovered = [s for s in stakeholders if s.get('coverage_status') == 'Not covered']
    urgent = [s for s in uncovered if s.get('priority') == 'Urgent']

    uncovered_block = ""
    if uncovered:
        uncovered_block = "\n## ⚠️ Require Elicitation Coverage\n\n"
        if urgent:
            uncovered_block += "### Urgent\n"
            for s in urgent:
                uncovered_block += (
                    f"- **{s.get('name', '—')}** ({s.get('role', '—')}) — "
                    f"{s.get('recommended_format', 'Interview')}\n"
                    f"  Why important: {s.get('why_important', '—')}\n"
                )
        not_urgent = [s for s in uncovered if s.get('priority') != 'Urgent']
        if not_urgent:
            uncovered_block += "\n### As Planned\n"
            for s in not_urgent:
                uncovered_block += (
                    f"- **{s.get('name', '—')}** ({s.get('role', '—')}) — "
                    f"{s.get('recommended_format', 'Interview')}\n"
                )

    content = f"""# Stakeholder Registry (Living Document)

**Project:** {project_name}
**Last updated:** {today}
**Update source:** {session_source}

---

## New / Updated Stakeholders

{table_header}{"".join(rows) if rows else "| — | — | — | — | — | — | — | — | — | — |"}

---

## Discovery Chain

{chr(10).join(chain_lines) if chain_lines else "— No data —"}

{uncovered_block}
---

> This file is updated after every elicitation session.
> The project's full registry is built up cumulatively from all updates.
"""

    suffix = save_artifact(content, f"Stakeholder_Registry_{project_name.replace(' ', '_')}", project_id=project_name)
    return f"✅ Stakeholder registry updated. New entries: {len(stakeholders)}.{suffix}"


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
